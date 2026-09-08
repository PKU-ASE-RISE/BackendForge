"""
BackendForge — L2 Integration Tests for Umami
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import time
import uuid
import hashlib

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
ADMIN_KEY = "admin-user"
USER_KEY = f"umami-user-{uuid.uuid4().hex[:8]}"
HEADERS_ADMIN = {"X-Api-Key": ADMIN_KEY, "Content-Type": "application/json"}
HEADERS_USER = {"X-Api-Key": USER_KEY, "Content-Type": "application/json"}
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
    """No auth for collect endpoint."""
    return requests.post(f"{BASE_URL}/api/collect", json=payload, timeout=30)


class TestHealthAndAuth:
    """Pattern 4: Health no auth, protected endpoints need auth."""

    def test_health_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_protected_endpoint_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/websites", timeout=30)
        assert r.status_code == 401

    def test_me_returns_user_fields(self):
        r = get("/api/me")
        assert r.status_code == 200
        user = r.json()
        assert "id" in user
        assert "username" in user
        assert "isAdmin" in user  # camelCase!
        assert "createdAt" in user  # camelCase!
        assert user["username"] == ADMIN_KEY

    def test_user_has_isAdmin_field(self):
        r = get("/api/me")
        assert "isAdmin" in r.json()
        assert isinstance(r.json()["isAdmin"], bool)


class TestWebsiteFields:
    """Pattern 1+4: Verify website field names (camelCase) and status codes."""

    def test_website_create_returns_201_with_camelcase_fields(self):
        r = post("/api/websites", {"name": f"Site-{U}", "domain": f"site-{U}.com"})
        assert r.status_code == 201
        site = r.json()
        assert "id" in site
        assert "name" in site
        assert "domain" in site
        assert "shareId" in site  # NOT share_id
        assert "createdBy" in site  # NOT created_by
        assert "createdAt" in site  # NOT created_at
        assert site["name"] == f"Site-{U}"
        assert site["domain"] == f"site-{U}.com"

    def test_website_get_nonexistent_returns_404(self):
        r = get("/api/websites/999999")
        assert r.status_code == 404

    def test_website_delete_returns_200(self):
        site = post("/api/websites", {"name": f"Del-{U}-{uuid.uuid4().hex[:4]}", "domain": "del.com"}).json()
        r = delete(f"/api/websites/{site['id']}")
        assert r.status_code == 200


class TestCollectEndpoint:
    """Pattern 1+5: Verify collect response fields and session creation."""

    def test_collect_returns_sessionId_and_isNewSession(self):
        site = post("/api/websites", {"name": f"Coll-{U}", "domain": "coll.com"}).json()
        r = collect({
            "websiteId": site["id"],
            "url": "/page1",
            "ip": "1.2.3.4",
            "userAgent": "TestAgent/1.0",
        })
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "sessionId" in data  # NOT session_id
        assert "isNewSession" in data  # NOT is_new_session
        assert data["status"] == "ok"
        assert data["isNewSession"] is True

    def test_collect_same_fingerprint_reuses_session(self):
        """Same ip+userAgent within 30 min → same session."""
        site = post("/api/websites", {"name": f"Reuse-{U}", "domain": "reuse.com"}).json()
        payload = {
            "websiteId": site["id"],
            "url": "/p1",
            "ip": "10.0.0.1",
            "userAgent": "SameAgent/1.0",
        }
        r1 = collect(payload)
        assert r1.json()["isNewSession"] is True
        sid1 = r1.json()["sessionId"]

        r2 = collect({**payload, "url": "/p2"})
        assert r2.json()["isNewSession"] is False
        assert r2.json()["sessionId"] == sid1

    def test_collect_invalid_websiteId_returns_400(self):
        r = collect({"websiteId": 999999, "url": "/x", "ip": "1.1.1.1", "userAgent": "Bot"})
        assert r.status_code == 400

    def test_collect_no_auth_required(self):
        """Collect endpoint must work without X-Api-Key."""
        site = post("/api/websites", {"name": f"NoAuth-{U}", "domain": "noauth.com"}).json()
        r = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": site["id"],
            "url": "/test",
            "ip": "2.2.2.2",
            "userAgent": "TestUA",
        }, timeout=30)
        assert r.status_code == 200


class TestStatsFields:
    """Pattern 1+5: Verify stats response fields (camelCase) and computed values."""

    def test_stats_returns_all_required_fields(self):
        site = post("/api/websites", {"name": f"Stats-{U}", "domain": "stats.com"}).json()
        # Collect some data
        collect({"websiteId": site["id"], "url": "/a", "ip": "3.3.3.3", "userAgent": "UA1"})

        r = get(f"/api/websites/{site['id']}/stats", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        })
        assert r.status_code == 200
        stats = r.json()
        assert "pageviews" in stats
        assert "visitors" in stats
        assert "visits" in stats
        assert "bounceRate" in stats  # camelCase!
        assert "totaltime" in stats
        assert stats["pageviews"] >= 1

    def test_stats_bounce_rate_calculated(self):
        """Bounce rate = sessions with 1 pageview / total sessions with pageviews."""
        site = post("/api/websites", {"name": f"Bounce-{U}", "domain": "bounce.com"}).json()
        # Session 1: single pageview → bounce
        collect({"websiteId": site["id"], "url": "/x", "ip": "4.4.4.1", "userAgent": "BounceUA1"})
        # Session 2: multiple pageviews → no bounce
        collect({"websiteId": site["id"], "url": "/x", "ip": "4.4.4.2", "userAgent": "BounceUA2"})
        collect({"websiteId": site["id"], "url": "/y", "ip": "4.4.4.2", "userAgent": "BounceUA2"})

        r = get(f"/api/websites/{site['id']}/stats", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        })
        stats = r.json()
        # 1 bounce out of 2 sessions = 0.5
        assert stats["bounceRate"] == 0.5
        assert stats["pageviews"] == 3
        assert stats["visitors"] == 2
        assert stats["visits"] == 2


class TestMetricsFields:
    """Pattern 1+3: Verify metrics response structure and filtering works."""

    def test_metrics_url_returns_name_and_count(self):
        site = post("/api/websites", {"name": f"Metrics-{U}", "domain": "metrics.com"}).json()
        collect({"websiteId": site["id"], "url": "/home", "ip": "5.5.5.1", "userAgent": "MetUA1"})
        collect({"websiteId": site["id"], "url": "/home", "ip": "5.5.5.2", "userAgent": "MetUA2"})
        collect({"websiteId": site["id"], "url": "/about", "ip": "5.5.5.1", "userAgent": "MetUA1"})

        r = get(f"/api/websites/{site['id']}/metrics", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "type": "url",
        })
        assert r.status_code == 200
        metrics = r.json()
        assert isinstance(metrics, list)
        assert len(metrics) >= 2
        # Each item has name and count
        for m in metrics:
            assert "name" in m
            assert "count" in m
        # /home should have count 2
        home = next((m for m in metrics if m["name"] == "/home"), None)
        assert home is not None
        assert home["count"] == 2

    def test_metrics_browser_counts_per_session(self):
        """Browser metrics count per unique session, not per event."""
        site = post("/api/websites", {"name": f"BrMet-{U}", "domain": "brmet.com"}).json()
        # Same session, multiple events
        collect({"websiteId": site["id"], "url": "/a", "ip": "6.6.6.1", "userAgent": "BrUA1", "browser": "Chrome"})
        collect({"websiteId": site["id"], "url": "/b", "ip": "6.6.6.1", "userAgent": "BrUA1", "browser": "Chrome"})
        collect({"websiteId": site["id"], "url": "/a", "ip": "6.6.6.2", "userAgent": "BrUA2", "browser": "Firefox"})

        r = get(f"/api/websites/{site['id']}/metrics", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "type": "browser",
        })
        metrics = r.json()
        chrome = next((m for m in metrics if m["name"] == "Chrome"), None)
        assert chrome is not None
        assert chrome["count"] == 1  # 1 session, not 2 events


class TestPageviewsTimeSeries:
    """Pattern 1+5: Verify pageviews time series structure."""

    def test_pageviews_returns_pageviews_and_sessions_arrays(self):
        site = post("/api/websites", {"name": f"TSeries-{U}", "domain": "ts.com"}).json()
        collect({"websiteId": site["id"], "url": "/ts", "ip": "7.7.7.1", "userAgent": "TSUA"})

        r = get(f"/api/websites/{site['id']}/pageviews", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
            "unit": "day",
        })
        assert r.status_code == 200
        data = r.json()
        assert "pageviews" in data
        assert "sessions" in data
        assert isinstance(data["pageviews"], list)
        assert isinstance(data["sessions"], list)
        # Each item has date and count
        for item in data["pageviews"]:
            assert "date" in item
            assert "count" in item


class TestEventSummary:
    """Pattern 1+5: Custom events counted separately from pageviews."""

    def test_events_endpoint_returns_custom_events_only(self):
        site = post("/api/websites", {"name": f"Evt-{U}", "domain": "evt.com"}).json()
        # Pageview (no eventName)
        collect({"websiteId": site["id"], "url": "/x", "ip": "8.1.1.1", "userAgent": "EvtUA"})
        # Custom events
        collect({"websiteId": site["id"], "url": "/x", "ip": "8.1.1.1", "userAgent": "EvtUA", "eventName": "signup"})
        collect({"websiteId": site["id"], "url": "/x", "ip": "8.1.1.1", "userAgent": "EvtUA", "eventName": "signup"})
        collect({"websiteId": site["id"], "url": "/x", "ip": "8.1.1.1", "userAgent": "EvtUA", "eventName": "click"})

        r = get(f"/api/websites/{site['id']}/events", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        })
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)
        names = {e["eventName"]: e["count"] for e in events}
        assert "signup" in names
        assert names["signup"] == 2
        assert "click" in names
        assert names["click"] == 1


class TestActiveVisitors:
    """Pattern 1+5: Active visitors count."""

    def test_active_returns_visitors_field(self):
        site = post("/api/websites", {"name": f"Active-{U}", "domain": "active.com"}).json()
        collect({"websiteId": site["id"], "url": "/now", "ip": "9.9.9.1", "userAgent": "ActiveUA"})

        r = get(f"/api/websites/{site['id']}/active")
        assert r.status_code == 200
        data = r.json()
        assert "visitors" in data
        assert data["visitors"] >= 1


class TestAdminPermissions:
    """Pattern 6: Non-admin users get 403 on admin endpoints."""

    def test_non_admin_cannot_list_users(self):
        """Non-admin users get 403 on admin endpoints."""
        get("/api/me", h=HEADERS_USER)
        r = get("/api/users", h=HEADERS_USER)
        assert r.status_code == 403

    def test_non_admin_cannot_get_user(self):
        """Non-admin cannot get a specific user."""
        r = get("/api/users/1", h=HEADERS_USER)
        assert r.status_code == 403


class TestWebsiteIsolation:
    """Pattern 6: Users can only see their own websites."""

    def test_user_cannot_see_others_website(self):
        site = post("/api/websites", {"name": f"Private-{U}", "domain": "priv.com"}).json()
        r = get(f"/api/websites/{site['id']}", h=HEADERS_USER)
        assert r.status_code == 404

    def test_user_list_only_own_websites(self):
        post("/api/websites", {"name": f"AdminSite-{U}", "domain": "admin.com"})
        r = get("/api/websites", h=HEADERS_USER)
        assert r.status_code == 200
        sites = r.json()
        for site in sites:
            # All sites should belong to the user
            assert site["createdBy"] == get("/api/me", h=HEADERS_USER).json()["id"]


class TestSessionFields:
    """Pattern 1+2: Session response has correct camelCase fields."""

    def test_session_list_returns_session_fields(self):
        site = post("/api/websites", {"name": f"Sess-{U}", "domain": "sess.com"}).json()
        collect({"websiteId": site["id"], "url": "/s", "ip": "11.1.1.1", "userAgent": "SessUA", "browser": "Chrome", "os": "Windows", "device": "desktop", "country": "US"})

        r = get(f"/api/websites/{site['id']}/sessions", params={
            "startAt": NOW_MS - DAY_MS,
            "endAt": NOW_MS + DAY_MS,
        })
        assert r.status_code == 200
        sessions = r.json()
        assert len(sessions) >= 1
        s = sessions[0]
        assert "id" in s
        assert "websiteId" in s  # camelCase
        assert "fingerprint" in s
        assert "browser" in s
        assert "os" in s
        assert "device" in s
        assert "country" in s
        assert "createdAt" in s
        assert "lastActivityAt" in s  # camelCase


class TestTeamFields:
    """Pattern 1+4: Team CRUD field names and status codes."""

    def test_team_create_returns_201_with_fields(self):
        r = post("/api/teams", {"name": f"Team-{U}"})
        assert r.status_code == 201
        team = r.json()
        assert "id" in team
        assert "name" in team
        assert "createdBy" in team  # camelCase
        assert "createdAt" in team  # camelCase
        assert team["name"] == f"Team-{U}"
