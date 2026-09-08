"""
BackendForge — Comprehensive Correctness Tests for Umami Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import time
import uuid
import hashlib

import pytest
import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

# User keys — the key IS the username (auto-created on first request)
ADMIN_KEY = "admin-user"  # First user auto-created becomes admin
USER_KEY = f"regular-user-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"another-user-{uuid.uuid4().hex[:8]}"

ADMIN_HEADERS = {
    "X-Api-Key": ADMIN_KEY,
    "Content-Type": "application/json",
}

USER_HEADERS = {
    "X-Api-Key": USER_KEY,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
    "X-Api-Key": USER2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_delete(path, params=None, headers=None):
    return requests.delete(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


def ensure_admin():
    """Make a request with ADMIN_KEY to ensure the admin user is auto-created first."""
    api_get("/api/me", headers=ADMIN_HEADERS)


def compute_fingerprint(website_id, ip, user_agent):
    """Compute session fingerprint the same way the server should."""
    raw = f"{website_id}{ip}{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication & User Management
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_auth_returns_401(self):
        """Endpoints requiring auth should return 401 without header."""
        resp = requests.get(f"{BASE_URL}/api/me", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_first_user_is_admin(self):
        """First user auto-created should be admin."""
        ensure_admin()
        resp = api_get("/api/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == ADMIN_KEY
        assert data["isAdmin"] is True

    def test_auto_create_subsequent_user_is_not_admin(self):
        """Subsequent users should not be admin."""
        resp = api_get("/api/me", headers=USER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == USER_KEY
        assert data["isAdmin"] is False

    def test_get_me_returns_user_fields(self):
        """GET /api/me should return id, username, isAdmin, createdAt."""
        resp = api_get("/api/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "username" in data
        assert "isAdmin" in data
        assert "createdAt" in data


class TestUserManagement:

    def test_list_users_admin_only(self):
        """Non-admin users should get 403 on user list."""
        ensure_admin()
        # Ensure non-admin user exists
        api_get("/api/me", headers=USER_HEADERS)

        resp = api_get("/api/users", headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_list_users_as_admin(self):
        """Admin should see all users."""
        api_get("/api/me", headers=USER_HEADERS)
        resp = api_get("/api/users", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least admin + user

    def test_get_user_by_id(self):
        """Admin can get user by ID."""
        resp = api_get("/api/me", headers=ADMIN_HEADERS)
        admin_id = resp.json()["id"]

        resp = api_get(f"/api/users/{admin_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == admin_id

    def test_get_user_not_found(self):
        """Getting a non-existent user returns 404."""
        resp = api_get("/api/users/99999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_update_user(self):
        """Admin can update user's isAdmin status."""
        # Get USER's ID
        resp = api_get("/api/me", headers=USER_HEADERS)
        user_id = resp.json()["id"]

        resp = api_put(f"/api/users/{user_id}", json_data={"isAdmin": False}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["isAdmin"] is False

    def test_cannot_delete_self(self):
        """Admin cannot delete themselves."""
        resp = api_get("/api/me", headers=ADMIN_HEADERS)
        admin_id = resp.json()["id"]

        resp = api_delete(f"/api/users/{admin_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_delete_user(self):
        """Admin can delete another user."""
        # Create a user to delete
        delete_key = f"to-delete-{uuid.uuid4().hex[:8]}"
        resp = api_get("/api/me", headers={"X-Api-Key": delete_key, "Content-Type": "application/json"})
        assert resp.status_code == 200
        user_id = resp.json()["id"]

        resp = api_delete(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Verify user is gone
        resp = api_get(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_non_admin_cannot_manage_users(self):
        """Non-admin cannot access user management endpoints."""
        resp = api_get("/api/users/1", headers=USER_HEADERS)
        assert resp.status_code == 403

        resp = api_put("/api/users/1", json_data={"isAdmin": True}, headers=USER_HEADERS)
        assert resp.status_code == 403

        resp = api_delete("/api/users/1", headers=USER_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 3: Websites CRUD
# ════════════════════════════════════════════════════════════════════


class TestWebsites:

    def test_create_website(self):
        """Create a website returns 201 with correct fields."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Test Site {UNIQUE}",
            "domain": "example.com"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Test Site {UNIQUE}"
        assert data["domain"] == "example.com"
        assert "id" in data
        assert "createdBy" in data
        assert "createdAt" in data

    def test_create_website_with_share_id(self):
        """Create a website with shareId."""
        share_id = f"share-{uuid.uuid4().hex[:8]}"
        resp = api_post("/api/websites", json_data={
            "name": f"Shared Site {UNIQUE}",
            "domain": "shared.example.com",
            "shareId": share_id
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["shareId"] == share_id

    def test_list_websites(self):
        """List websites returns user's websites."""
        resp = api_get("/api/websites")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_website_by_id(self):
        """Get a specific website."""
        # Create first
        resp = api_post("/api/websites", json_data={
            "name": f"GetTest {UNIQUE}",
            "domain": "gettest.com"
        })
        website_id = resp.json()["id"]

        resp = api_get(f"/api/websites/{website_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == website_id
        assert resp.json()["name"] == f"GetTest {UNIQUE}"

    def test_update_website(self):
        """Update a website."""
        resp = api_post("/api/websites", json_data={
            "name": f"UpdateTest {UNIQUE}",
            "domain": "update.com"
        })
        website_id = resp.json()["id"]

        resp = api_put(f"/api/websites/{website_id}", json_data={
            "name": "Updated Name",
            "domain": "updated.com"
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["domain"] == "updated.com"

    def test_delete_website(self):
        """Delete a website."""
        resp = api_post("/api/websites", json_data={
            "name": f"DeleteTest {UNIQUE}",
            "domain": "delete.com"
        })
        website_id = resp.json()["id"]

        resp = api_delete(f"/api/websites/{website_id}")
        assert resp.status_code == 200

        # Verify it's gone
        resp = api_get(f"/api/websites/{website_id}")
        assert resp.status_code == 404

    def test_website_ownership_isolation(self):
        """Users cannot see other users' websites."""
        # Admin creates a website
        resp = api_post("/api/websites", json_data={
            "name": f"Admin Only {UNIQUE}",
            "domain": "admin.com"
        }, headers=ADMIN_HEADERS)
        website_id = resp.json()["id"]

        # Regular user cannot access it
        resp = api_get(f"/api/websites/{website_id}", headers=USER_HEADERS)
        assert resp.status_code == 404

    def test_website_not_found(self):
        """Getting non-existent website returns 404."""
        resp = api_get("/api/websites/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Event Collection & Session Detection
# ════════════════════════════════════════════════════════════════════


class TestEventCollection:

    def setup_method(self):
        """Create a website for testing."""
        ensure_admin()

    def _create_website(self, name_suffix=""):
        resp = api_post("/api/websites", json_data={
            "name": f"Collect Test {UNIQUE}{name_suffix}",
            "domain": "collect.example.com"
        })
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_collect_no_auth_required(self):
        """POST /api/collect should work without auth."""
        website_id = self._create_website("-noauth")
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/test",
            "ip": "1.2.3.4",
            "userAgent": "TestBot/1.0"
        }, timeout=30)
        assert resp.status_code == 200

    def test_collect_returns_session_id(self):
        """Collect should return status, sessionId, isNewSession."""
        website_id = self._create_website("-session")
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/page1",
            "ip": "10.0.0.1",
            "userAgent": "Mozilla/5.0"
        }, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "sessionId" in data
        assert "isNewSession" in data
        assert data["isNewSession"] is True

    def test_collect_invalid_website_id(self):
        """Collect with invalid websiteId returns 400."""
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": 99999,
            "url": "/test",
            "ip": "1.1.1.1",
            "userAgent": "Bot"
        }, timeout=30)
        assert resp.status_code == 400

    def test_collect_missing_required_fields(self):
        """Collect without required fields returns 400."""
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": 1
        }, timeout=30)
        assert resp.status_code == 400

    def test_session_reuse_same_fingerprint(self):
        """Same IP+UA+website within 30 min should reuse session."""
        website_id = self._create_website("-reuse")
        payload = {
            "websiteId": website_id,
            "url": "/page1",
            "ip": "192.168.1.1",
            "userAgent": "SessionBot/1.0"
        }

        # First event - new session
        resp1 = requests.post(f"{BASE_URL}/api/collect", json=payload, timeout=30)
        assert resp1.status_code == 200
        session_id1 = resp1.json()["sessionId"]
        assert resp1.json()["isNewSession"] is True

        # Second event - same session (within 30 min)
        payload2 = dict(payload)
        payload2["url"] = "/page2"
        resp2 = requests.post(f"{BASE_URL}/api/collect", json=payload2, timeout=30)
        assert resp2.status_code == 200
        session_id2 = resp2.json()["sessionId"]
        assert resp2.json()["isNewSession"] is False
        assert session_id1 == session_id2

    def test_different_fingerprint_new_session(self):
        """Different IP or UA should create a new session."""
        website_id = self._create_website("-diffsess")

        resp1 = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/page1",
            "ip": "10.10.10.1",
            "userAgent": "BrowserA/1.0"
        }, timeout=30)
        session_id1 = resp1.json()["sessionId"]

        resp2 = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/page1",
            "ip": "10.10.10.2",
            "userAgent": "BrowserB/2.0"
        }, timeout=30)
        session_id2 = resp2.json()["sessionId"]

        assert session_id1 != session_id2

    def test_collect_pageview_event(self):
        """Event without eventName is a pageview."""
        website_id = self._create_website("-pv")
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/about",
            "ip": "5.5.5.5",
            "userAgent": "Chrome/100"
        }, timeout=30)
        assert resp.status_code == 200

    def test_collect_custom_event(self):
        """Event with eventName is a custom event."""
        website_id = self._create_website("-custom")
        resp = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/pricing",
            "ip": "6.6.6.6",
            "userAgent": "Firefox/99",
            "eventName": "button_click",
            "eventData": {"button": "signup"}
        }, timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 5: Stats Aggregation
# ════════════════════════════════════════════════════════════════════


class TestStats:

    @pytest.fixture(autouse=True)
    def setup_website_with_events(self):
        """Create a website and populate with known events."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Stats Site {UNIQUE}",
            "domain": "stats.example.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

        # Visitor 1: 3 pageviews (NOT a bounce)
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": f"/page{i}",
                "ip": "100.0.0.1",
                "userAgent": "Visitor1/1.0",
                "browser": "Chrome",
                "os": "Windows",
                "device": "desktop",
                "country": "US"
            }, timeout=30)

        # Visitor 2: 1 pageview (bounce)
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/landing",
            "ip": "100.0.0.2",
            "userAgent": "Visitor2/1.0",
            "browser": "Firefox",
            "os": "Mac",
            "device": "desktop",
            "country": "UK"
        }, timeout=30)

        # Visitor 3: 2 pageviews (NOT a bounce)
        for i in range(2):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": f"/blog{i}",
                "ip": "100.0.0.3",
                "userAgent": "Visitor3/1.0",
                "browser": "Safari",
                "os": "Mac",
                "device": "mobile",
                "country": "US"
            }, timeout=30)

        # Use wide time range to include all events
        self.start_at = 0
        self.end_at = int(time.time() * 1000) + 86400000

    def test_stats_returns_correct_fields(self):
        """Stats should return pageviews, visitors, visits, bounceRate, totaltime."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "pageviews" in data
        assert "visitors" in data
        assert "visits" in data
        assert "bounceRate" in data
        assert "totaltime" in data

    def test_stats_pageview_count(self):
        """Pageviews = total pageview events."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        # 3 + 1 + 2 = 6 pageviews
        assert data["pageviews"] == 6

    def test_stats_visitor_count(self):
        """Visitors = distinct session fingerprints."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        # 3 distinct visitors
        assert data["visitors"] == 3

    def test_stats_visit_count(self):
        """Visits = distinct sessions."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        # 3 distinct sessions
        assert data["visits"] == 3

    def test_stats_bounce_rate(self):
        """Bounce rate = sessions with 1 pageview / total sessions with pageviews."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        # 1 bounce out of 3 sessions = ~0.333
        bounce_rate = data["bounceRate"]
        assert abs(bounce_rate - (1.0 / 3.0)) < 0.01

    def test_stats_totaltime_type(self):
        """Totaltime should be an integer (seconds)."""
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        assert isinstance(data["totaltime"], int)

    def test_stats_website_not_found(self):
        """Stats for non-existent website returns 404."""
        resp = api_get("/api/websites/99999/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Metrics
# ════════════════════════════════════════════════════════════════════


class TestMetrics:

    @pytest.fixture(autouse=True)
    def setup_website_with_events(self):
        """Create a website and populate with known events for metrics."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Metrics Site {UNIQUE}",
            "domain": "metrics.example.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

        # 3 visitors hitting various URLs
        # Visitor A: Chrome, Windows, desktop, US
        for url in ["/home", "/about", "/contact"]:
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": url,
                "ip": "200.0.0.1",
                "userAgent": "VisitorA",
                "browser": "Chrome",
                "os": "Windows",
                "device": "desktop",
                "country": "US",
                "referrer": "https://google.com"
            }, timeout=30)

        # Visitor B: Firefox, Linux, desktop, DE
        for url in ["/home", "/pricing"]:
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": url,
                "ip": "200.0.0.2",
                "userAgent": "VisitorB",
                "browser": "Firefox",
                "os": "Linux",
                "device": "desktop",
                "country": "DE",
                "referrer": "https://bing.com"
            }, timeout=30)

        # Visitor C: Safari, Mac, mobile, US - with custom event
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/home",
            "ip": "200.0.0.3",
            "userAgent": "VisitorC",
            "browser": "Safari",
            "os": "Mac",
            "device": "mobile",
            "country": "US"
        }, timeout=30)
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/pricing",
            "ip": "200.0.0.3",
            "userAgent": "VisitorC",
            "browser": "Safari",
            "os": "Mac",
            "device": "mobile",
            "country": "US",
            "eventName": "signup_click"
        }, timeout=30)

        self.start_at = 0
        self.end_at = int(time.time() * 1000) + 86400000

    def test_metrics_url(self):
        """URL metrics returns top pages by visitor count."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "url"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # /home was visited by all 3 visitors
        names = [item["name"] for item in data]
        assert "/home" in names
        home_item = next(item for item in data if item["name"] == "/home")
        assert home_item["count"] == 3  # 3 unique sessions viewed /home

    def test_metrics_browser(self):
        """Browser metrics returns browsers by session count."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "browser"
        })
        assert resp.status_code == 200
        data = resp.json()
        names = [item["name"] for item in data]
        assert "Chrome" in names
        assert "Firefox" in names
        assert "Safari" in names
        # Each browser has 1 session
        for item in data:
            assert item["count"] == 1

    def test_metrics_country(self):
        """Country metrics returns countries by session count."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "country"
        })
        assert resp.status_code == 200
        data = resp.json()
        names = [item["name"] for item in data]
        assert "US" in names
        us_item = next(item for item in data if item["name"] == "US")
        assert us_item["count"] == 2  # Visitor A and C are from US

    def test_metrics_event(self):
        """Event metrics returns custom event names."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "event"
        })
        assert resp.status_code == 200
        data = resp.json()
        names = [item["name"] for item in data]
        assert "signup_click" in names

    def test_metrics_sorted_by_count_desc(self):
        """Metrics should be sorted by count descending."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "url"
        })
        data = resp.json()
        counts = [item["count"] for item in data]
        assert counts == sorted(counts, reverse=True)

    def test_metrics_referrer(self):
        """Referrer metrics returns referrer URLs."""
        resp = api_get(f"/api/websites/{self.website_id}/metrics", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "type": "referrer"
        })
        assert resp.status_code == 200
        data = resp.json()
        names = [item["name"] for item in data]
        assert "https://google.com" in names
        assert "https://bing.com" in names


# ════════════════════════════════════════════════════════════════════
# PART 7: Pageviews Time Series
# ════════════════════════════════════════════════════════════════════


class TestPageviews:

    @pytest.fixture(autouse=True)
    def setup_website_with_events(self):
        """Create a website with known pageview events."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Pageviews Site {UNIQUE}",
            "domain": "pageviews.example.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

        # Create several pageviews
        for i in range(5):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": f"/page{i}",
                "ip": f"50.0.0.{i+1}",
                "userAgent": f"Bot{i}",
                "browser": "Chrome",
                "os": "Windows",
                "device": "desktop",
                "country": "US"
            }, timeout=30)

        self.start_at = 0
        self.end_at = int(time.time() * 1000) + 86400000

    def test_pageviews_by_day(self):
        """Pageviews grouped by day."""
        resp = api_get(f"/api/websites/{self.website_id}/pageviews", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "unit": "day"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "pageviews" in data
        assert "sessions" in data
        assert isinstance(data["pageviews"], list)
        assert isinstance(data["sessions"], list)

    def test_pageviews_items_have_date_and_count(self):
        """Each item should have date and count fields."""
        resp = api_get(f"/api/websites/{self.website_id}/pageviews", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "unit": "day"
        })
        data = resp.json()
        for item in data["pageviews"]:
            assert "date" in item
            assert "count" in item

    def test_pageviews_total_matches_stats(self):
        """Sum of pageviews time series should match stats total."""
        resp_ts = api_get(f"/api/websites/{self.website_id}/pageviews", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "unit": "day"
        })
        resp_stats = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        ts_total = sum(item["count"] for item in resp_ts.json()["pageviews"])
        stats_total = resp_stats.json()["pageviews"]
        assert ts_total == stats_total

    def test_pageviews_by_hour(self):
        """Pageviews grouped by hour should have HH:00:00 format."""
        resp = api_get(f"/api/websites/{self.website_id}/pageviews", params={
            "startAt": self.start_at,
            "endAt": self.end_at,
            "unit": "hour"
        })
        assert resp.status_code == 200
        data = resp.json()
        if data["pageviews"]:
            # Date should contain T and :00:00
            date_str = data["pageviews"][0]["date"]
            assert "T" in date_str
            assert ":00:00" in date_str


# ════════════════════════════════════════════════════════════════════
# PART 8: Events (Custom Event Summary)
# ════════════════════════════════════════════════════════════════════


class TestEvents:

    @pytest.fixture(autouse=True)
    def setup_website_with_events(self):
        """Create a website with custom events."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Events Site {UNIQUE}",
            "domain": "events.example.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

        # Create custom events
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": "/pricing",
                "ip": f"60.0.0.{i+1}",
                "userAgent": f"EventBot{i}",
                "eventName": "button_click"
            }, timeout=30)

        for i in range(2):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": self.website_id,
                "url": "/signup",
                "ip": f"60.0.1.{i+1}",
                "userAgent": f"EventBot2{i}",
                "eventName": "form_submit"
            }, timeout=30)

        # A pageview (should NOT appear in event summary)
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/home",
            "ip": "60.0.2.1",
            "userAgent": "PageBot"
        }, timeout=30)

        self.start_at = 0
        self.end_at = int(time.time() * 1000) + 86400000

    def test_events_summary(self):
        """Events endpoint returns custom event summary."""
        resp = api_get(f"/api/websites/{self.website_id}/events", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        names = [item["eventName"] for item in data]
        assert "button_click" in names
        assert "form_submit" in names

    def test_events_counts(self):
        """Event counts should reflect actual event occurrences."""
        resp = api_get(f"/api/websites/{self.website_id}/events", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        btn_item = next(item for item in data if item["eventName"] == "button_click")
        form_item = next(item for item in data if item["eventName"] == "form_submit")
        assert btn_item["count"] == 3
        assert form_item["count"] == 2

    def test_events_excludes_pageviews(self):
        """Pageview events should not appear in event summary."""
        resp = api_get(f"/api/websites/{self.website_id}/events", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        # Only custom events, no pageviews
        for item in data:
            assert item["eventName"] != ""
            assert item["eventName"] is not None


# ════════════════════════════════════════════════════════════════════
# PART 9: Realtime / Active Visitors
# ════════════════════════════════════════════════════════════════════


class TestRealtime:

    def test_active_visitors(self):
        """Active endpoint returns visitors in last 5 minutes."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Realtime Site {UNIQUE}",
            "domain": "realtime.example.com"
        })
        assert resp.status_code == 201
        website_id = resp.json()["id"]

        # Create recent events (within last 5 min)
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": website_id,
                "url": "/live",
                "ip": f"70.0.0.{i+1}",
                "userAgent": f"LiveBot{i}"
            }, timeout=30)

        resp = api_get(f"/api/websites/{website_id}/active")
        assert resp.status_code == 200
        data = resp.json()
        assert "visitors" in data
        assert data["visitors"] == 3

    def test_active_visitors_empty(self):
        """Active endpoint returns 0 for website with no recent events."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"EmptyRT Site {UNIQUE}",
            "domain": "emptyrt.example.com"
        })
        assert resp.status_code == 201
        website_id = resp.json()["id"]

        resp = api_get(f"/api/websites/{website_id}/active")
        assert resp.status_code == 200
        assert resp.json()["visitors"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 10: Sessions
# ════════════════════════════════════════════════════════════════════


class TestSessions:

    @pytest.fixture(autouse=True)
    def setup_website_with_sessions(self):
        """Create a website with sessions."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Sessions Site {UNIQUE}",
            "domain": "sessions.example.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

        # Create 2 sessions
        resp1 = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/home",
            "ip": "80.0.0.1",
            "userAgent": "SessionBot1",
            "browser": "Chrome",
            "os": "Windows",
            "device": "desktop",
            "country": "US"
        }, timeout=30)
        self.session1_id = resp1.json()["sessionId"]

        resp2 = requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/about",
            "ip": "80.0.0.2",
            "userAgent": "SessionBot2",
            "browser": "Firefox",
            "os": "Linux",
            "device": "mobile",
            "country": "DE"
        }, timeout=30)
        self.session2_id = resp2.json()["sessionId"]

        self.start_at = 0
        self.end_at = int(time.time() * 1000) + 86400000

    def test_list_sessions(self):
        """List sessions for a website."""
        resp = api_get(f"/api/websites/{self.website_id}/sessions", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_session_has_required_fields(self):
        """Sessions should have all required fields."""
        resp = api_get(f"/api/websites/{self.website_id}/sessions", params={
            "startAt": self.start_at,
            "endAt": self.end_at
        })
        data = resp.json()
        session = data[0]
        assert "id" in session
        assert "websiteId" in session
        assert "fingerprint" in session
        assert "browser" in session
        assert "os" in session
        assert "device" in session
        assert "country" in session
        assert "createdAt" in session
        assert "lastActivityAt" in session

    def test_get_session_detail(self):
        """Get session detail includes events."""
        resp = api_get(f"/api/websites/{self.website_id}/sessions/{self.session1_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == self.session1_id
        assert "events" in data
        assert isinstance(data["events"], list)
        assert len(data["events"]) >= 1

    def test_session_detail_event_fields(self):
        """Events in session detail should have correct fields."""
        resp = api_get(f"/api/websites/{self.website_id}/sessions/{self.session1_id}")
        data = resp.json()
        event = data["events"][0]
        assert "id" in event
        assert "sessionId" in event
        assert "websiteId" in event
        assert "eventType" in event
        assert "url" in event
        assert "createdAt" in event

    def test_session_not_found(self):
        """Getting non-existent session returns 404."""
        resp = api_get(f"/api/websites/{self.website_id}/sessions/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Teams
# ════════════════════════════════════════════════════════════════════


class TestTeams:

    def test_create_team(self):
        """Create a team returns 201."""
        ensure_admin()
        resp = api_post("/api/teams", json_data={"name": f"Team {UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Team {UNIQUE}"
        assert "id" in data
        assert "createdBy" in data
        assert "createdAt" in data

    def test_list_teams(self):
        """List teams returns teams the user belongs to."""
        # Create a team first
        api_post("/api/teams", json_data={"name": f"ListTeam {UNIQUE}"})

        resp = api_get("/api/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_team(self):
        """Get team by ID."""
        resp = api_post("/api/teams", json_data={"name": f"GetTeam {UNIQUE}"})
        team_id = resp.json()["id"]

        resp = api_get(f"/api/teams/{team_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == team_id

    def test_update_team(self):
        """Update team name."""
        resp = api_post("/api/teams", json_data={"name": f"UpdateTeam {UNIQUE}"})
        team_id = resp.json()["id"]

        resp = api_put(f"/api/teams/{team_id}", json_data={"name": "New Team Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Team Name"

    def test_delete_team(self):
        """Delete team (owner only)."""
        resp = api_post("/api/teams", json_data={"name": f"DeleteTeam {UNIQUE}"})
        team_id = resp.json()["id"]

        resp = api_delete(f"/api/teams/{team_id}")
        assert resp.status_code == 200

        # Verify it's gone
        resp = api_get(f"/api/teams/{team_id}")
        assert resp.status_code == 404

    def test_non_owner_cannot_delete_team(self):
        """Non-owner cannot delete a team."""
        ensure_admin()
        # Admin creates team
        resp = api_post("/api/teams", json_data={"name": f"ProtectedTeam {UNIQUE}"})
        team_id = resp.json()["id"]

        # Regular user tries to delete
        resp = api_delete(f"/api/teams/{team_id}", headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_team_not_found(self):
        """Getting non-existent team returns 404."""
        resp = api_get("/api/teams/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Team Members
# ════════════════════════════════════════════════════════════════════


class TestTeamMembers:

    @pytest.fixture(autouse=True)
    def setup_team(self):
        """Create a team for member tests."""
        ensure_admin()
        resp = api_post("/api/teams", json_data={"name": f"MemberTeam {UNIQUE}"})
        assert resp.status_code == 201
        self.team_id = resp.json()["id"]

        # Ensure USER exists and get their ID
        resp = api_get("/api/me", headers=USER_HEADERS)
        self.user_id = resp.json()["id"]

    def test_add_member(self):
        """Add a member to team."""
        resp = api_post(f"/api/teams/{self.team_id}/members", json_data={
            "userId": self.user_id
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["userId"] == self.user_id
        assert data["teamId"] == self.team_id
        assert data["role"] == "member"

    def test_list_members(self):
        """List team members includes owner."""
        resp = api_get(f"/api/teams/{self.team_id}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Owner is always a member
        assert len(data) >= 1

    def test_cannot_add_duplicate_member(self):
        """Adding same user twice returns 409."""
        api_post(f"/api/teams/{self.team_id}/members", json_data={
            "userId": self.user_id
        })
        resp = api_post(f"/api/teams/{self.team_id}/members", json_data={
            "userId": self.user_id
        })
        assert resp.status_code == 409

    def test_remove_member(self):
        """Remove a member from team."""
        api_post(f"/api/teams/{self.team_id}/members", json_data={
            "userId": self.user_id
        })
        resp = api_delete(f"/api/teams/{self.team_id}/members/{self.user_id}")
        assert resp.status_code == 200

    def test_non_owner_cannot_add_member(self):
        """Non-owner cannot add members."""
        # Get user2's id
        resp = api_get("/api/me", headers=USER2_HEADERS)
        user2_id = resp.json()["id"]

        # user (non-owner) tries to add user2
        resp = api_post(f"/api/teams/{self.team_id}/members", json_data={
            "userId": user2_id
        }, headers=USER_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 13: Team Websites
# ════════════════════════════════════════════════════════════════════


class TestTeamWebsites:

    @pytest.fixture(autouse=True)
    def setup_team_and_website(self):
        """Create a team and website for sharing tests."""
        ensure_admin()
        resp = api_post("/api/teams", json_data={"name": f"WebTeam {UNIQUE}"})
        assert resp.status_code == 201
        self.team_id = resp.json()["id"]

        resp = api_post("/api/websites", json_data={
            "name": f"TeamSite {UNIQUE}",
            "domain": "teamsite.com"
        })
        assert resp.status_code == 201
        self.website_id = resp.json()["id"]

    def test_share_website_with_team(self):
        """Share a website with a team."""
        resp = api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["teamId"] == self.team_id
        assert data["websiteId"] == self.website_id

    def test_list_team_websites(self):
        """List websites shared with team."""
        api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })
        resp = api_get(f"/api/teams/{self.team_id}/websites")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_cannot_share_duplicate(self):
        """Sharing same website twice returns 409."""
        api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })
        resp = api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })
        assert resp.status_code == 409

    def test_remove_website_from_team(self):
        """Remove website from team."""
        api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })
        resp = api_delete(f"/api/teams/{self.team_id}/websites/{self.website_id}")
        assert resp.status_code == 200

    def test_team_member_can_view_shared_website_stats(self):
        """Team member can view stats for shared website."""
        # Add USER to team
        resp = api_get("/api/me", headers=USER_HEADERS)
        user_id = resp.json()["id"]
        api_post(f"/api/teams/{self.team_id}/members", json_data={"userId": user_id})

        # Share website with team
        api_post(f"/api/teams/{self.team_id}/websites", json_data={
            "websiteId": self.website_id
        })

        # Send some events
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": self.website_id,
            "url": "/shared-page",
            "ip": "90.0.0.1",
            "userAgent": "SharedBot"
        }, timeout=30)

        # USER should be able to view stats
        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{self.website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        }, headers=USER_HEADERS)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 14: Public Share
# ════════════════════════════════════════════════════════════════════


class TestPublicShare:

    def test_share_endpoint_returns_stats(self):
        """Public share endpoint returns stats."""
        ensure_admin()
        share_id = f"pub-{uuid.uuid4().hex[:8]}"
        resp = api_post("/api/websites", json_data={
            "name": f"Public Site {UNIQUE}",
            "domain": "public.example.com",
            "shareId": share_id
        })
        assert resp.status_code == 201
        website_id = resp.json()["id"]

        # Add some events
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/public-page",
            "ip": "95.0.0.1",
            "userAgent": "PublicBot"
        }, timeout=30)

        now = int(time.time() * 1000) + 86400000
        resp = requests.get(f"{BASE_URL}/api/share/{share_id}", params={
            "startAt": 0,
            "endAt": now
        }, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "pageviews" in data
        assert "visitors" in data
        assert "visits" in data

    def test_share_endpoint_no_auth_required(self):
        """Share endpoint works without auth."""
        ensure_admin()
        share_id = f"noauth-{uuid.uuid4().hex[:8]}"
        api_post("/api/websites", json_data={
            "name": f"NoAuth Share {UNIQUE}",
            "domain": "noauth.example.com",
            "shareId": share_id
        })

        now = int(time.time() * 1000) + 86400000
        resp = requests.get(f"{BASE_URL}/api/share/{share_id}", params={
            "startAt": 0,
            "endAt": now
        }, timeout=30)
        assert resp.status_code == 200

    def test_share_invalid_id_returns_404(self):
        """Invalid share ID returns 404."""
        resp = requests.get(f"{BASE_URL}/api/share/nonexistent-id", params={
            "startAt": 0,
            "endAt": int(time.time() * 1000) + 86400000
        }, timeout=30)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Website Reset
# ════════════════════════════════════════════════════════════════════


class TestWebsiteReset:

    def test_reset_clears_analytics(self):
        """Reset removes all events and sessions but keeps website."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"Reset Site {UNIQUE}",
            "domain": "reset.example.com"
        })
        assert resp.status_code == 201
        website_id = resp.json()["id"]

        # Add events
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": website_id,
                "url": f"/page{i}",
                "ip": f"85.0.0.{i+1}",
                "userAgent": f"ResetBot{i}"
            }, timeout=30)

        # Verify events exist
        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        assert resp.json()["pageviews"] == 3

        # Reset
        resp = api_post(f"/api/websites/{website_id}/reset")
        assert resp.status_code == 200

        # Verify events are gone
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        assert resp.json()["pageviews"] == 0

        # Verify website still exists
        resp = api_get(f"/api/websites/{website_id}")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 16: Advanced Session & Bounce Logic
# ════════════════════════════════════════════════════════════════════


class TestBounceRate:

    def test_all_bounces(self):
        """All single-pageview sessions = 100% bounce rate."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"AllBounce Site {UNIQUE}",
            "domain": "allbounce.example.com"
        })
        website_id = resp.json()["id"]

        # 3 visitors, each with exactly 1 pageview
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": website_id,
                "url": "/landing",
                "ip": f"110.0.0.{i+1}",
                "userAgent": f"Bouncer{i}"
            }, timeout=30)

        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        data = resp.json()
        assert data["bounceRate"] == 1.0

    def test_no_bounces(self):
        """All multi-pageview sessions = 0% bounce rate."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"NoBounce Site {UNIQUE}",
            "domain": "nobounce.example.com"
        })
        website_id = resp.json()["id"]

        # 2 visitors, each with 2 pageviews
        for i in range(2):
            for j in range(2):
                requests.post(f"{BASE_URL}/api/collect", json={
                    "websiteId": website_id,
                    "url": f"/page{j}",
                    "ip": f"111.0.0.{i+1}",
                    "userAgent": f"NonBouncer{i}"
                }, timeout=30)

        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        data = resp.json()
        assert data["bounceRate"] == 0.0

    def test_custom_events_dont_affect_bounce(self):
        """Custom events should not count toward pageviews for bounce calc."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"CustomBounce Site {UNIQUE}",
            "domain": "custombounce.example.com"
        })
        website_id = resp.json()["id"]

        # 1 visitor: 1 pageview + 1 custom event = still a bounce
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/page",
            "ip": "112.0.0.1",
            "userAgent": "BounceCustomBot"
        }, timeout=30)
        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/page",
            "ip": "112.0.0.1",
            "userAgent": "BounceCustomBot",
            "eventName": "click_button"
        }, timeout=30)

        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        data = resp.json()
        # Only 1 pageview in this session, so it's a bounce
        assert data["bounceRate"] == 1.0

    def test_empty_website_bounce_rate_zero(self):
        """Website with no events should have 0 bounce rate."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"EmptyBounce Site {UNIQUE}",
            "domain": "emptybounce.example.com"
        })
        website_id = resp.json()["id"]

        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        data = resp.json()
        assert data["bounceRate"] == 0.0


# ════════════════════════════════════════════════════════════════════
# PART 17: Date Filtering
# ════════════════════════════════════════════════════════════════════


class TestDateFiltering:

    def test_stats_respect_date_range(self):
        """Stats should only include events within the date range."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"DateFilter Site {UNIQUE}",
            "domain": "datefilter.example.com"
        })
        website_id = resp.json()["id"]

        # Create events now
        for i in range(3):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": website_id,
                "url": f"/page{i}",
                "ip": f"120.0.0.{i+1}",
                "userAgent": f"DateBot{i}"
            }, timeout=30)

        # Query with a future range (should get 0)
        future_start = int(time.time() * 1000) + 86400000 * 10  # 10 days from now
        future_end = future_start + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": future_start,
            "endAt": future_end
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["pageviews"] == 0
        assert data["visitors"] == 0
        assert data["visits"] == 0

    def test_stats_include_current_events(self):
        """Stats with range including now should include recent events."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"CurrentFilter Site {UNIQUE}",
            "domain": "currentfilter.example.com"
        })
        website_id = resp.json()["id"]

        # Create events now
        for i in range(2):
            requests.post(f"{BASE_URL}/api/collect", json={
                "websiteId": website_id,
                "url": f"/current{i}",
                "ip": f"121.0.0.{i+1}",
                "userAgent": f"CurrentBot{i}"
            }, timeout=30)

        now = int(time.time() * 1000) + 86400000
        resp = api_get(f"/api/websites/{website_id}/stats", params={
            "startAt": 0,
            "endAt": now
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["pageviews"] == 2


# ════════════════════════════════════════════════════════════════════
# PART 18: Delete Cascade
# ════════════════════════════════════════════════════════════════════


class TestDeleteCascade:

    def test_delete_website_cascades_sessions(self):
        """Deleting a website removes its sessions."""
        ensure_admin()
        resp = api_post("/api/websites", json_data={
            "name": f"CascadeSite {UNIQUE}",
            "domain": "cascade.example.com"
        })
        website_id = resp.json()["id"]

        requests.post(f"{BASE_URL}/api/collect", json={
            "websiteId": website_id,
            "url": "/cascade",
            "ip": "130.0.0.1",
            "userAgent": "CascadeBot"
        }, timeout=30)

        # Delete website
        resp = api_delete(f"/api/websites/{website_id}")
        assert resp.status_code == 200

        # Website should be gone
        resp = api_get(f"/api/websites/{website_id}")
        assert resp.status_code == 404

    def test_delete_user_cascades_websites(self):
        """Deleting a user removes their websites."""
        ensure_admin()
        # Create user
        cascade_key = f"cascade-user-{uuid.uuid4().hex[:8]}"
        cascade_headers = {"X-Api-Key": cascade_key, "Content-Type": "application/json"}
        resp = api_get("/api/me", headers=cascade_headers)
        user_id = resp.json()["id"]

        # Create website as that user
        resp = api_post("/api/websites", json_data={
            "name": f"UserCascade {UNIQUE}",
            "domain": "usercascade.com"
        }, headers=cascade_headers)
        assert resp.status_code == 201
        website_id = resp.json()["id"]

        # Admin deletes user
        resp = api_delete(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Website should be gone (admin can't find it either)
        resp = api_get(f"/api/websites/{website_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 404
