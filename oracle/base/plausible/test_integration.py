"""
L2 Integration Tests for Plausible Analytics API.
Adversarial tests targeting:
- camelCase field names (bounceRate, visitDuration, pageviews, etc.)
- Computed values actually calculated (not hardcoded)
- Filters actually working
- Correct status codes
- Event ingestion side effects (click counting)
"""
import os
import uuid
import json
import requests
import pytest
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")
ANALYTICS_TIME = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
ANALYTICS_DATE = ANALYTICS_TIME.date().isoformat()


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    if "no_auth" not in kwargs:
        headers["X-API-Key"] = API_KEY
    else:
        kwargs.pop("no_auth")
    url = f"{BASE_URL}{path}"
    return requests.request(method, url, headers=headers, **kwargs)


def create_site(domain=None):
    domain = domain or f"t{uuid.uuid4().hex}.com"
    resp = api("POST", "/api/sites", json={"domain": domain, "timezone": "UTC", "public": False})
    assert resp.status_code == 201
    return resp.json()


def ingest(domain, name="pageview", url="/", country=None, user_agent=None,
           referrer=None, screen_size=None, properties=None, timestamp=None):
    payload = {"domain": domain, "name": name, "url": url}
    if country:
        payload["country"] = country
    if user_agent:
        payload["userAgent"] = user_agent
    if referrer:
        payload["referrer"] = referrer
    if screen_size:
        payload["screenSize"] = screen_size
    if properties:
        payload["properties"] = properties
    if timestamp:
        payload["timestamp"] = timestamp
    resp = requests.post(f"{BASE_URL}/api/event", json=payload)
    assert resp.status_code == 202
    return resp.json()


# =============================================================================
# L2 TESTS
# =============================================================================


class TestSiteFieldCasing:
    """Pattern 1: Verify camelCase fields in site responses."""

    def test_create_site_returns_camelcase_fields(self):
        domain = f"t{uuid.uuid4().hex}.com"
        resp = api("POST", "/api/sites", json={"domain": domain, "timezone": "US/Eastern", "public": True})
        assert resp.status_code == 201
        site = resp.json()
        assert "id" in site
        assert "domain" in site and site["domain"] == domain
        assert "timezone" in site and site["timezone"] == "US/Eastern"
        assert "public" in site and site["public"] is True
        assert "createdAt" in site
        # No snake_case
        assert "created_at" not in site

    def test_get_site_preserves_fields(self):
        site = create_site()
        resp = api("GET", f"/api/sites/{site['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == site["id"]
        assert data["domain"] == site["domain"]
        assert "createdAt" in data


class TestEventIngestion:
    """Pattern 4+5: Event ingestion status codes and side effects."""

    def test_ingest_returns_202(self):
        site = create_site()
        resp = requests.post(f"{BASE_URL}/api/event", json={
            "domain": site["domain"], "name": "pageview", "url": "/test"
        })
        assert resp.status_code == 202

    def test_ingest_no_auth_required(self):
        site = create_site()
        resp = requests.post(f"{BASE_URL}/api/event", json={
            "domain": site["domain"], "url": "/"
        })
        assert resp.status_code == 202

    def test_ingest_updates_aggregate_stats(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/page1", timestamp=now, user_agent="UA1", country="US")
        ingest(site["domain"], url="/page2", timestamp=now, user_agent="UA2", country="UK")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["pageviews"] >= 2
        assert stats["visitors"] >= 2


class TestAggregateStatsCasing:
    """Pattern 1+5: Aggregate stats fields and computed values."""

    def test_aggregate_stats_returns_camelcase(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/", timestamp=now, user_agent="Bot1", country="US")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert "visitors" in stats
        assert "pageviews" in stats
        assert "bounceRate" in stats
        assert "visitDuration" in stats
        assert "visits" in stats
        assert "events" in stats
        # No snake_case
        assert "bounce_rate" not in stats
        assert "visit_duration" not in stats

    def test_bounce_rate_computed_correctly(self):
        """Single-pageview sessions should have 100% bounce rate."""
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        # Two different visitors, each with one pageview (bounce)
        ingest(site["domain"], url="/page1", timestamp=now, user_agent="BounceA", country="US")
        ingest(site["domain"], url="/page2", timestamp=now, user_agent="BounceB", country="UK")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        stats = resp.json()
        # Both sessions have only 1 pageview -> 100% bounce rate
        assert stats["bounceRate"] == 100

    def test_multiple_pageviews_reduce_bounce_rate(self):
        """Visitor with 2+ pageviews should not be a bounce."""
        site = create_site()
        now = ANALYTICS_TIME
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=30)).isoformat()
        # Visitor A: 2 pageviews (not a bounce)
        ingest(site["domain"], url="/p1", timestamp=t1, user_agent="NoBounce", country="US")
        ingest(site["domain"], url="/p2", timestamp=t2, user_agent="NoBounce", country="US")
        # Visitor B: 1 pageview (bounce)
        ingest(site["domain"], url="/p3", timestamp=t1, user_agent="YesBounce", country="UK")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        stats = resp.json()
        # 1 of 2 sessions is a bounce -> 50%
        assert stats["bounceRate"] == 50


class TestTimeSeries:
    """Pattern 1+3: Time series returns correct structure."""

    def test_timeseries_returns_correct_fields(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/", timestamp=now, user_agent="TS1", country="US")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/timeseries",
            params={"period": "7d", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        point = data[0]
        assert "date" in point
        assert "visitors" in point
        assert "pageviews" in point
        assert "events" in point
        assert "visits" in point


class TestBreakdowns:
    """Pattern 3+5: Breakdown by dimension returns actual data."""

    def test_breakdown_by_page(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/about", timestamp=now, user_agent="P1", country="US")
        ingest(site["domain"], url="/about", timestamp=now, user_agent="P2", country="UK")
        ingest(site["domain"], url="/pricing", timestamp=now, user_agent="P3", country="DE")

        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": ANALYTICS_DATE})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        page_map = {item["value"]: item for item in data}
        assert "/about" in page_map
        assert page_map["/about"]["visitors"] == 2
        assert "/pricing" in page_map
        assert page_map["/pricing"]["visitors"] == 1

    def test_breakdown_by_country(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/", timestamp=now, user_agent="C1", country="US")
        ingest(site["domain"], url="/", timestamp=now, user_agent="C2", country="US")
        ingest(site["domain"], url="/", timestamp=now, user_agent="C3", country="DE")

        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/countries",
                   params={"period": "day", "date": ANALYTICS_DATE})
        assert resp.status_code == 200
        data = resp.json()
        country_map = {item["value"]: item for item in data}
        assert "US" in country_map
        assert country_map["US"]["visitors"] == 2
        assert "DE" in country_map

    def test_breakdown_item_has_expected_fields(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/x", timestamp=now, user_agent="F1", country="FR")

        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": ANALYTICS_DATE})
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "value" in item
        assert "visitors" in item
        assert "pageviews" in item or "events" in item


class TestFilters:
    """Pattern 3: Filters actually narrow results."""

    def test_country_filter(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/a", timestamp=now, user_agent="F1", country="US")
        ingest(site["domain"], url="/b", timestamp=now, user_agent="F2", country="UK")

        filters = json.dumps({"country": "US"})
        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": ANALYTICS_DATE,
                           "filters": filters})
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["visitors"] == 1

    def test_page_filter(self):
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/target", timestamp=now, user_agent="PF1", country="US")
        ingest(site["domain"], url="/other", timestamp=now, user_agent="PF2", country="UK")

        filters = json.dumps({"page": "/target"})
        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": ANALYTICS_DATE,
                           "filters": filters})
        stats = resp.json()
        assert stats["pageviews"] == 1


class TestGoals:
    """Pattern 1+4: Goal CRUD with correct status codes and fields."""

    def test_create_goal_returns_201(self):
        site = create_site()
        resp = api("POST", f"/api/sites/{site['id']}/goals", json={
            "goalType": "event", "eventName": "Signup"
        })
        assert resp.status_code == 201
        goal = resp.json()
        assert "id" in goal
        assert goal["siteId"] == site["id"]
        assert goal["goalType"] == "event"
        assert goal["eventName"] == "Signup"
        assert "createdAt" in goal

    def test_delete_goal_returns_204(self):
        site = create_site()
        goal = api("POST", f"/api/sites/{site['id']}/goals", json={
            "goalType": "pageview", "pagePath": "/thank-you"
        }).json()
        resp = api("DELETE", f"/api/sites/{site['id']}/goals/{goal['id']}")
        assert resp.status_code == 204


class TestSharedLinks:
    """Pattern 1+4: Shared link fields."""

    def test_create_shared_link(self):
        site = create_site()
        resp = api("POST", f"/api/sites/{site['id']}/shared-links", json={
            "name": "Public Dashboard"
        })
        assert resp.status_code == 201
        link = resp.json()
        assert "id" in link
        assert "slug" in link
        assert link["siteId"] == site["id"]
        assert "passwordProtected" in link
        assert link["passwordProtected"] is False
        assert "createdAt" in link

    def test_shared_link_with_password(self):
        site = create_site()
        resp = api("POST", f"/api/sites/{site['id']}/shared-links", json={
            "name": "Protected", "password": "secret123"
        })
        assert resp.status_code == 201
        assert resp.json()["passwordProtected"] is True


class TestStatusCodes:
    """Pattern 4: Exact status codes."""

    def test_create_site_returns_201(self):
        resp = api("POST", "/api/sites", json={"domain": f"t{uuid.uuid4().hex}.com"})
        assert resp.status_code == 201

    def test_delete_site_returns_204(self):
        site = create_site()
        resp = api("DELETE", f"/api/sites/{site['id']}")
        assert resp.status_code == 204

    def test_get_nonexistent_site_returns_404(self):
        resp = api("GET", "/api/sites/nonexistent-id-xyz")
        assert resp.status_code == 404

    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/sites")
        assert resp.status_code == 401


class TestRealtimeVisitors:
    """Pattern 5: Realtime count reflects recent events."""

    def test_realtime_after_recent_event(self):
        site = create_site()
        now = datetime.now(timezone.utc).isoformat()
        ingest(site["domain"], url="/", timestamp=now, user_agent="Realtime1", country="US")

        resp = api("GET", f"/api/sites/{site['id']}/realtime/visitors")
        assert resp.status_code == 200
        data = resp.json()
        assert "visitors" in data
        assert data["visitors"] >= 1
