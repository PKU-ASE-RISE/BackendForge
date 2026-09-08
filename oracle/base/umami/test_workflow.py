"""
BackendForge — L3 Workflow Tests for Umami
Multi-entity, multi-step adversarial tests targeting LLM implementation gaps.
"""

import os
import time
import uuid
import hashlib

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
ADMIN_KEY = "admin-user"
USER2_KEY = f"l3user2-{uuid.uuid4().hex[:8]}"
USER3_KEY = f"l3user3-{uuid.uuid4().hex[:8]}"
HEADERS_ADMIN = {"X-Api-Key": ADMIN_KEY, "Content-Type": "application/json"}
HEADERS_USER2 = {"X-Api-Key": USER2_KEY, "Content-Type": "application/json"}
HEADERS_USER3 = {"X-Api-Key": USER3_KEY, "Content-Type": "application/json"}
U = uuid.uuid4().hex[:8]

NOW_MS = int(time.time() * 1000)
HOUR_MS = 3600 * 1000
DAY_MS = 86400 * 1000


def get(path, params=None, h=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=h or HEADERS_ADMIN, timeout=30)


def post(path, json=None, h=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=h or HEADERS_ADMIN, timeout=30)


def put(path, json=None, h=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=h or HEADERS_ADMIN, timeout=30)


def delete(path, h=None):
    return requests.delete(f"{BASE_URL}{path}", headers=h or HEADERS_ADMIN, timeout=30)


def collect(payload):
    return requests.post(f"{BASE_URL}/api/collect", json=payload, timeout=30)


class TestCollectAndStatsWorkflow:
    """Pattern 5+7: Collect events, verify stats computed correctly."""

    def test_full_analytics_workflow(self):
        """Create website, collect pageviews from multiple visitors, verify all stats."""
        # 1. Create website
        site = post("/api/websites", {"name": f"WF-{U}", "domain": "wf.com"}).json()
        wid = site["id"]

        # 2. Collect events: 3 sessions, 5 pageviews
        # Session A: 2 pageviews (not bounce)
        collect({"websiteId": wid, "url": "/home", "ip": "10.0.1.1", "userAgent": "UA-A", "browser": "Chrome", "os": "Windows"})
        collect({"websiteId": wid, "url": "/about", "ip": "10.0.1.1", "userAgent": "UA-A"})
        # Session B: 1 pageview (bounce)
        collect({"websiteId": wid, "url": "/home", "ip": "10.0.1.2", "userAgent": "UA-B", "browser": "Firefox", "os": "Linux"})
        # Session C: 2 pageviews (not bounce)
        collect({"websiteId": wid, "url": "/home", "ip": "10.0.1.3", "userAgent": "UA-C", "browser": "Safari", "os": "MacOS"})
        collect({"websiteId": wid, "url": "/contact", "ip": "10.0.1.3", "userAgent": "UA-C"})

        # 3. Get stats
        stats = get(f"/api/websites/{wid}/stats", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        }).json()

        assert stats["pageviews"] == 5
        assert stats["visitors"] == 3
        assert stats["visits"] == 3
        # Bounce: 1 session with 1 pageview out of 3 total = 1/3
        assert abs(stats["bounceRate"] - (1.0 / 3.0)) < 0.01

        # 4. Get URL metrics
        url_metrics = get(f"/api/websites/{wid}/metrics", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "type": "url",
        }).json()
        home_metric = next((m for m in url_metrics if m["name"] == "/home"), None)
        assert home_metric is not None
        assert home_metric["count"] == 3  # 3 pageviews to /home

        # 5. Get browser metrics (counted per session)
        browser_metrics = get(f"/api/websites/{wid}/metrics", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "type": "browser",
        }).json()
        chrome = next((m for m in browser_metrics if m["name"] == "Chrome"), None)
        assert chrome is not None
        assert chrome["count"] == 1  # 1 session with Chrome


class TestSessionDetection:
    """Pattern 5+8: Session fingerprinting and continuity logic."""

    def test_different_ip_creates_different_session(self):
        """Different IP means different fingerprint → new session."""
        site = post("/api/websites", {"name": f"SessDet-{U}", "domain": "sd.com"}).json()

        r1 = collect({"websiteId": site["id"], "url": "/x", "ip": "20.0.0.1", "userAgent": "SameUA"})
        r2 = collect({"websiteId": site["id"], "url": "/x", "ip": "20.0.0.2", "userAgent": "SameUA"})

        assert r1.json()["sessionId"] != r2.json()["sessionId"]
        assert r2.json()["isNewSession"] is True

    def test_different_useragent_creates_different_session(self):
        """Different user agent means different fingerprint → new session."""
        site = post("/api/websites", {"name": f"UASess-{U}", "domain": "ua.com"}).json()

        r1 = collect({"websiteId": site["id"], "url": "/x", "ip": "21.0.0.1", "userAgent": "UA-First"})
        r2 = collect({"websiteId": site["id"], "url": "/x", "ip": "21.0.0.1", "userAgent": "UA-Second"})

        assert r1.json()["sessionId"] != r2.json()["sessionId"]

    def test_session_metadata_preserved_from_first_event(self):
        """Session browser/os/device set from first event only."""
        site = post("/api/websites", {"name": f"Meta-{U}", "domain": "meta.com"}).json()

        collect({"websiteId": site["id"], "url": "/1", "ip": "22.0.0.1", "userAgent": "MetaUA", "browser": "Chrome", "os": "Linux", "device": "desktop", "country": "US"})
        r2 = collect({"websiteId": site["id"], "url": "/2", "ip": "22.0.0.1", "userAgent": "MetaUA", "browser": "Firefox", "os": "Windows", "device": "mobile", "country": "UK"})

        sid = r2.json()["sessionId"]
        # Get session detail to verify metadata didn't change
        detail = get(f"/api/websites/{site['id']}/sessions/{sid}").json()
        assert detail["browser"] == "Chrome"  # From first event
        assert detail["os"] == "Linux"
        assert detail["device"] == "desktop"
        assert detail["country"] == "US"
        assert len(detail["events"]) == 2


class TestWebsiteResetAndDelete:
    """Pattern 7: Reset clears data, delete cascades."""

    def test_reset_clears_all_analytics_data(self):
        """Reset should clear events and sessions but keep website."""
        site = post("/api/websites", {"name": f"Reset-{U}", "domain": "reset.com"}).json()
        collect({"websiteId": site["id"], "url": "/a", "ip": "30.0.0.1", "userAgent": "ResetUA"})
        collect({"websiteId": site["id"], "url": "/b", "ip": "30.0.0.2", "userAgent": "ResetUA2"})

        # Verify data exists
        stats = get(f"/api/websites/{site['id']}/stats", params={"startAt": NOW_MS - DAY_MS, "endAt": NOW_MS + DAY_MS}).json()
        assert stats["pageviews"] >= 2

        # Reset
        r = post(f"/api/websites/{site['id']}/reset")
        assert r.status_code == 200

        # Verify data cleared
        stats_after = get(f"/api/websites/{site['id']}/stats", params={"startAt": NOW_MS - DAY_MS, "endAt": NOW_MS + DAY_MS}).json()
        assert stats_after["pageviews"] == 0
        assert stats_after["visitors"] == 0

        # Website still exists
        assert get(f"/api/websites/{site['id']}").status_code == 200

    def test_delete_website_cascades_events(self):
        """Deleting a website should remove all its sessions and events."""
        site = post("/api/websites", {"name": f"DelCasc-{U}", "domain": "del.com"}).json()
        collect({"websiteId": site["id"], "url": "/x", "ip": "31.0.0.1", "userAgent": "DelUA"})

        delete(f"/api/websites/{site['id']}")
        assert get(f"/api/websites/{site['id']}").status_code == 404


class TestTeamWorkflow:
    """Pattern 6+7: Team sharing allows view access but not modification."""

    def test_team_sharing_gives_view_access(self):
        """Team member can view stats for shared website."""
        # 1. Admin creates website
        site = post("/api/websites", {"name": f"TeamSite-{U}", "domain": "team.com"}).json()
        collect({"websiteId": site["id"], "url": "/team", "ip": "40.0.0.1", "userAgent": "TeamUA"})

        # 2. Create team
        team = post("/api/teams", {"name": f"MyTeam-{U}"}).json()
        assert team["createdBy"] == get("/api/me").json()["id"]

        # 3. Get user2's id
        user2_me = get("/api/me", h=HEADERS_USER2).json()

        # 4. Add user2 to team
        r_add = post(f"/api/teams/{team['id']}/members", {"userId": user2_me["id"]})
        assert r_add.status_code == 201
        member = r_add.json()
        assert member["userId"] == user2_me["id"]
        assert member["role"] == "member"

        # 5. Share website with team
        r_share = post(f"/api/teams/{team['id']}/websites", {"websiteId": site["id"]})
        assert r_share.status_code == 201

        # 6. User2 can now view stats
        r_stats = get(f"/api/websites/{site['id']}/stats", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        }, h=HEADERS_USER2)
        assert r_stats.status_code == 200
        assert r_stats.json()["pageviews"] >= 1

        # 7. User2 cannot delete the website
        r_del = delete(f"/api/websites/{site['id']}", h=HEADERS_USER2)
        assert r_del.status_code == 404  # Not owner, so 404

    def test_duplicate_team_member_returns_409(self):
        """Adding the same member twice should return 409."""
        team = post("/api/teams", {"name": f"DupTeam-{U}"}).json()
        user2_id = get("/api/me", h=HEADERS_USER2).json()["id"]

        r1 = post(f"/api/teams/{team['id']}/members", {"userId": user2_id})
        assert r1.status_code == 201
        r2 = post(f"/api/teams/{team['id']}/members", {"userId": user2_id})
        assert r2.status_code == 409


class TestPublicShareWorkflow:
    """Pattern 5+6: Public share endpoint works without auth."""

    def test_public_share_returns_stats(self):
        """Set shareId on website, access stats via public endpoint."""
        share_id = f"share-{uuid.uuid4().hex[:8]}"
        site = post("/api/websites", {"name": f"Shared-{U}", "domain": "shared.com", "shareId": share_id}).json()
        assert site["shareId"] == share_id

        # Collect some data
        collect({"websiteId": site["id"], "url": "/public", "ip": "50.0.0.1", "userAgent": "PublicUA"})

        # Access via public share (no auth)
        r = requests.get(f"{BASE_URL}/api/share/{share_id}", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        }, timeout=30)
        assert r.status_code == 200
        stats = r.json()
        assert "pageviews" in stats
        assert stats["pageviews"] >= 1

    def test_invalid_share_id_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/share/nonexistent-id", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        }, timeout=30)
        assert r.status_code == 404


class TestAdminWorkflow:
    """Pattern 6: Admin user management endpoints return 403 for non-admins."""

    def test_non_admin_cannot_delete_users(self):
        """Non-admin trying to delete user returns 403."""
        get("/api/me", h=HEADERS_USER2)  # ensure exists
        me = get("/api/me", h=HEADERS_USER2).json()
        r = delete(f"/api/users/{me['id']}", h=HEADERS_USER2)
        assert r.status_code == 403

    def test_non_admin_cannot_update_users(self):
        """Non-admin trying to update user returns 403."""
        get("/api/me", h=HEADERS_USER2)
        me = get("/api/me", h=HEADERS_USER2).json()
        r = put(f"/api/users/{me['id']}", {"isAdmin": True}, h=HEADERS_USER2)
        assert r.status_code == 403


class TestCustomEventsWorkflow:
    """Pattern 5: Custom events tracked separately with correct eventType."""

    def test_custom_events_in_session_detail(self):
        """Session detail shows events with correct eventType."""
        site = post("/api/websites", {"name": f"CustEvt-{U}", "domain": "custevt.com"}).json()

        # Mix of pageview and custom events
        r1 = collect({"websiteId": site["id"], "url": "/page", "ip": "60.0.0.1", "userAgent": "CustUA"})
        collect({"websiteId": site["id"], "url": "/page", "ip": "60.0.0.1", "userAgent": "CustUA", "eventName": "button_click", "eventData": {"btn": "submit"}})

        sid = r1.json()["sessionId"]
        detail = get(f"/api/websites/{site['id']}/sessions/{sid}").json()
        assert len(detail["events"]) == 2

        event_types = [e["eventType"] for e in detail["events"]]
        assert "pageview" in event_types
        assert "custom" in event_types

        custom_evt = next(e for e in detail["events"] if e["eventType"] == "custom")
        assert custom_evt["eventName"] == "button_click"


class TestMetricsEventType:
    """Pattern 5: Metrics type=event returns custom events only."""

    def test_event_metrics_returns_event_names(self):
        site = post("/api/websites", {"name": f"EvtMet-{U}", "domain": "evtmet.com"}).json()
        collect({"websiteId": site["id"], "url": "/x", "ip": "70.0.0.1", "userAgent": "EM-UA"})
        collect({"websiteId": site["id"], "url": "/x", "ip": "70.0.0.1", "userAgent": "EM-UA", "eventName": "purchase"})
        collect({"websiteId": site["id"], "url": "/x", "ip": "70.0.0.2", "userAgent": "EM-UA2", "eventName": "purchase"})
        collect({"websiteId": site["id"], "url": "/x", "ip": "70.0.0.1", "userAgent": "EM-UA", "eventName": "subscribe"})

        r = get(f"/api/websites/{site['id']}/metrics", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "type": "event",
        })
        metrics = r.json()
        purchase = next((m for m in metrics if m["name"] == "purchase"), None)
        subscribe = next((m for m in metrics if m["name"] == "subscribe"), None)
        assert purchase is not None
        assert purchase["count"] == 2
        assert subscribe is not None
        assert subscribe["count"] == 1
