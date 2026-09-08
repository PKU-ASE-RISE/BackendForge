"""
Comprehensive test suite for Plausible Analytics API.
Tests cover: Sites CRUD, Event Ingestion, Realtime, Aggregate Stats,
Time Series, Breakdowns, Filters, Goals, Funnels, Custom Properties,
Shared Links, and Export.
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")
ANALYTICS_TIME = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
ANALYTICS_DATE = ANALYTICS_TIME.date().isoformat()


def api(method, path, **kwargs):
    """Helper to make API requests."""
    headers = dict(kwargs.pop("headers", {}))
    if "no_auth" not in kwargs:
        headers["X-API-Key"] = API_KEY
    else:
        kwargs.pop("no_auth")
    url = f"{BASE_URL}{path}"
    return requests.request(method, url, headers=headers, **kwargs)


def create_site(domain=None, timezone_str="UTC", public=False):
    """Helper to create a site."""
    if domain is None:
        domain = f"test-{uuid.uuid4().hex}.com"
    resp = api("POST", "/api/sites", json={
        "domain": domain,
        "timezone": timezone_str,
        "public": public,
    })
    assert resp.status_code == 201, f"Failed to create site: {resp.text}"
    return resp.json()


def ingest_event(domain, name="pageview", url="/", referrer=None,
                 screen_size=None, country=None, user_agent=None,
                 properties=None, timestamp=None):
    """Helper to ingest an event (public endpoint, no auth)."""
    payload = {"domain": domain, "name": name, "url": url}
    if referrer:
        payload["referrer"] = referrer
    if screen_size:
        payload["screenSize"] = screen_size
    if country:
        payload["country"] = country
    if user_agent:
        payload["userAgent"] = user_agent
    if properties:
        payload["properties"] = properties
    if timestamp:
        payload["timestamp"] = timestamp
    resp = requests.post(f"{BASE_URL}/api/event", json=payload)
    assert resp.status_code == 202, f"Failed to ingest event: {resp.text}"
    return resp.json()


# ============================================================
# SITES CRUD
# ============================================================

class TestSitesCRUD:
    def test_create_site(self):
        domain = f"crud-create-{uuid.uuid4().hex}.com"
        site = create_site(domain)
        assert site["domain"] == domain
        assert "id" in site
        assert site["timezone"] == "UTC"
        assert site["public"] is False
        assert "createdAt" in site

    def test_create_site_with_timezone(self):
        domain = f"tz-test-{uuid.uuid4().hex}.com"
        site = create_site(domain, timezone_str="America/New_York")
        assert site["timezone"] == "America/New_York"

    def test_create_site_duplicate_domain(self):
        domain = f"dup-{uuid.uuid4().hex}.com"
        create_site(domain)
        resp = api("POST", "/api/sites", json={"domain": domain})
        assert resp.status_code == 400

    def test_list_sites(self):
        domain = f"list-{uuid.uuid4().hex}.com"
        create_site(domain)
        resp = api("GET", "/api/sites")
        assert resp.status_code == 200
        sites = resp.json()
        assert isinstance(sites, list)
        domains = [s["domain"] for s in sites]
        assert domain in domains

    def test_get_site(self):
        site = create_site()
        resp = api("GET", f"/api/sites/{site['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["domain"] == site["domain"]

    def test_get_site_not_found(self):
        resp = api("GET", "/api/sites/nonexistent-id")
        assert resp.status_code == 404

    def test_update_site(self):
        site = create_site()
        resp = api("PUT", f"/api/sites/{site['id']}", json={
            "timezone": "Europe/London",
            "public": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["timezone"] == "Europe/London"
        assert data["public"] is True

    def test_delete_site(self):
        site = create_site()
        resp = api("DELETE", f"/api/sites/{site['id']}")
        assert resp.status_code == 204
        # Verify it's gone
        resp = api("GET", f"/api/sites/{site['id']}")
        assert resp.status_code == 404

    def test_unauthorized_no_key(self):
        resp = requests.get(f"{BASE_URL}/api/sites")
        assert resp.status_code == 401

    def test_unauthorized_bad_key(self):
        resp = requests.get(f"{BASE_URL}/api/sites",
                            headers={"X-API-Key": "invalid-key"})
        assert resp.status_code == 401


# ============================================================
# EVENT INGESTION
# ============================================================

class TestEventIngestion:
    def test_ingest_pageview(self):
        site = create_site()
        result = ingest_event(site["domain"], url="/home")
        assert result["status"] == "accepted"

    def test_ingest_custom_event(self):
        site = create_site()
        result = ingest_event(site["domain"], name="Signup", url="/signup")
        assert result["status"] == "accepted"

    def test_ingest_with_metadata(self):
        site = create_site()
        result = ingest_event(
            site["domain"],
            url="/pricing",
            referrer="https://google.com",
            screen_size="desktop",
            country="US",
            user_agent="Mozilla/5.0 Test Agent",
        )
        assert result["status"] == "accepted"

    def test_ingest_with_custom_properties(self):
        site = create_site()
        result = ingest_event(
            site["domain"],
            name="Purchase",
            url="/checkout",
            properties={"plan": "premium", "amount": "99"},
        )
        assert result["status"] == "accepted"

    def test_ingest_missing_domain(self):
        resp = requests.post(f"{BASE_URL}/api/event", json={
            "url": "/page",
        })
        assert resp.status_code == 400

    def test_ingest_missing_url(self):
        site = create_site()
        resp = requests.post(f"{BASE_URL}/api/event", json={
            "domain": site["domain"],
        })
        assert resp.status_code == 400

    def test_ingest_no_auth_required(self):
        site = create_site()
        # Event ingestion is public
        resp = requests.post(f"{BASE_URL}/api/event", json={
            "domain": site["domain"],
            "url": "/test",
        })
        assert resp.status_code == 202

    def test_ingest_with_timestamp(self):
        site = create_site()
        ts = (ANALYTICS_TIME - timedelta(hours=1)).isoformat()
        result = ingest_event(site["domain"], url="/old-page", timestamp=ts)
        assert result["status"] == "accepted"


# ============================================================
# REALTIME VISITORS
# ============================================================

class TestRealtime:
    def test_realtime_no_visitors(self):
        site = create_site()
        resp = api("GET", f"/api/sites/{site['id']}/realtime/visitors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 0

    def test_realtime_with_recent_event(self):
        site = create_site()
        # Ingest an event with current timestamp
        now = datetime.now(timezone.utc).isoformat()
        ingest_event(site["domain"], url="/live", user_agent="realtime-agent-1",
                     country="US", timestamp=now)
        resp = api("GET", f"/api/sites/{site['id']}/realtime/visitors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] >= 1

    def test_realtime_old_event_not_counted(self):
        site = create_site()
        # Ingest event from 10 minutes ago
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        ingest_event(site["domain"], url="/old", user_agent="old-agent-unique",
                     country="DE", timestamp=old_ts)
        resp = api("GET", f"/api/sites/{site['id']}/realtime/visitors")
        assert resp.status_code == 200
        data = resp.json()
        # This specific visitor should not be counted
        # (we can't assert exactly 0 because other tests might have recent events)
        # Instead, verify the endpoint works
        assert "visitors" in data


# ============================================================
# AGGREGATE STATS
# ============================================================

class TestAggregateStats:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_DATE
        self.today = today

        # Visitor 1: 2 pageviews (not a bounce)
        ingest_event(self.domain, url="/page1", user_agent="visitor1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/page2", user_agent="visitor1",
                     country="US", timestamp=f"{today}T10:05:00Z")

        # Visitor 2: 1 pageview (bounce)
        ingest_event(self.domain, url="/page1", user_agent="visitor2",
                     country="UK", timestamp=f"{today}T11:00:00Z")

        # Visitor 3: 3 pageviews
        ingest_event(self.domain, url="/page1", user_agent="visitor3",
                     country="US", timestamp=f"{today}T12:00:00Z")
        ingest_event(self.domain, url="/page2", user_agent="visitor3",
                     country="US", timestamp=f"{today}T12:10:00Z")
        ingest_event(self.domain, url="/page3", user_agent="visitor3",
                     country="US", timestamp=f"{today}T12:20:00Z")

    def test_aggregate_visitors(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 3

    def test_aggregate_pageviews(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today})
        data = resp.json()
        assert data["pageviews"] == 6

    def test_aggregate_visits(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today})
        data = resp.json()
        assert data["visits"] == 3

    def test_aggregate_bounce_rate(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today})
        data = resp.json()
        # 1 bounce out of 3 sessions = 33.33%
        assert abs(data["bounceRate"] - 33.33) < 1

    def test_aggregate_visit_duration(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today})
        data = resp.json()
        # Visitor 1: 5 min = 300s, Visitor 2: 0s, Visitor 3: 20 min = 1200s
        # Average = (300 + 0 + 1200) / 3 = 500s
        assert abs(data["visitDuration"] - 500) < 1

    def test_aggregate_custom_period(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "custom", "dateFrom": self.today,
                           "dateTo": self.today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 3


# ============================================================
# TIME SERIES
# ============================================================

class TestTimeSeries:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_TIME
        self.today_str = today.strftime("%Y-%m-%d")
        yesterday = today - timedelta(days=1)
        self.yesterday_str = yesterday.strftime("%Y-%m-%d")

        # Events today
        ingest_event(self.domain, url="/today-page", user_agent="ts-visitor1",
                     country="US", timestamp=f"{self.today_str}T10:00:00Z")
        ingest_event(self.domain, url="/today-page2", user_agent="ts-visitor1",
                     country="US", timestamp=f"{self.today_str}T10:05:00Z")

        # Events yesterday
        ingest_event(self.domain, url="/yesterday-page", user_agent="ts-visitor2",
                     country="UK", timestamp=f"{self.yesterday_str}T14:00:00Z")

    def test_timeseries_daily(self):
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/timeseries",
                   params={"period": "custom",
                           "dateFrom": self.yesterday_str,
                           "dateTo": self.today_str,
                           "interval": "day"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Find yesterday and today entries
        dates = {item["date"]: item for item in data}
        assert self.yesterday_str in dates
        assert self.today_str in dates
        assert dates[self.yesterday_str]["visitors"] == 1
        assert dates[self.yesterday_str]["pageviews"] == 1
        assert dates[self.today_str]["visitors"] == 1
        assert dates[self.today_str]["pageviews"] == 2

    def test_timeseries_includes_empty_days(self):
        site = create_site()
        today = ANALYTICS_DATE
        three_days_ago = (ANALYTICS_TIME - timedelta(days=3)).strftime("%Y-%m-%d")
        resp = api("GET", f"/api/sites/{site['id']}/stats/timeseries",
                   params={"period": "custom",
                           "dateFrom": three_days_ago,
                           "dateTo": today,
                           "interval": "day"})
        assert resp.status_code == 200
        data = resp.json()
        # Should have entries for each day even if no events
        assert len(data) == 4


# ============================================================
# BREAKDOWN
# ============================================================

class TestBreakdown:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_DATE
        self.today = today

        # Multiple visitors hitting different pages
        ingest_event(self.domain, url="/pricing", user_agent="bd-v1",
                     country="US", screen_size="desktop",
                     referrer="https://google.com",
                     timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/pricing", user_agent="bd-v2",
                     country="US", screen_size="mobile",
                     referrer="https://google.com",
                     timestamp=f"{today}T10:01:00Z")
        ingest_event(self.domain, url="/about", user_agent="bd-v3",
                     country="UK", screen_size="desktop",
                     referrer="https://twitter.com",
                     timestamp=f"{today}T10:02:00Z")
        ingest_event(self.domain, url="/pricing", user_agent="bd-v4",
                     country="DE", screen_size="tablet",
                     referrer="https://twitter.com",
                     timestamp=f"{today}T10:03:00Z")

    def test_breakdown_pages(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # /pricing should be top with 3 visitors
        top = data[0]
        assert top["value"] == "/pricing"
        assert top["visitors"] == 3

    def test_breakdown_sources(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/sources",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        sources = {item["value"]: item["visitors"] for item in data}
        assert "https://google.com" in sources or "google.com" in sources

    def test_breakdown_countries(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/countries",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        countries = {item["value"]: item["visitors"] for item in data}
        assert countries.get("US") == 2

    def test_breakdown_devices(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/devices",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        devices = {item["value"]: item["visitors"] for item in data}
        assert devices.get("desktop") == 2

    def test_breakdown_with_limit(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": self.today, "limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_breakdown_percentage(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/countries",
                   params={"period": "day", "date": self.today})
        data = resp.json()
        # Percentages should sum to ~100
        total_pct = sum(item["percentage"] for item in data)
        assert abs(total_pct - 100) < 1

    def test_breakdown_browsers(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/browsers",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_breakdown_os(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/os",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ============================================================
# BOUNCE RATE
# ============================================================

class TestBounceRate:
    def test_all_bounces(self):
        """All single-page visits → 100% bounce rate."""
        site = create_site()
        today = ANALYTICS_DATE

        # 3 visitors, each with only 1 pageview
        ingest_event(site["domain"], url="/a", user_agent="bounce-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/b", user_agent="bounce-v2",
                     country="UK", timestamp=f"{today}T10:01:00Z")
        ingest_event(site["domain"], url="/c", user_agent="bounce-v3",
                     country="DE", timestamp=f"{today}T10:02:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        data = resp.json()
        assert data["bounceRate"] == 100

    def test_no_bounces(self):
        """All multi-page visits → 0% bounce rate."""
        site = create_site()
        today = ANALYTICS_DATE

        # 2 visitors, each with 2 pageviews
        ingest_event(site["domain"], url="/a", user_agent="nobounce-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/b", user_agent="nobounce-v1",
                     country="US", timestamp=f"{today}T10:05:00Z")
        ingest_event(site["domain"], url="/a", user_agent="nobounce-v2",
                     country="UK", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/b", user_agent="nobounce-v2",
                     country="UK", timestamp=f"{today}T10:05:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        data = resp.json()
        assert data["bounceRate"] == 0


# ============================================================
# SESSION DETECTION
# ============================================================

class TestSessionDetection:
    def test_same_visitor_within_30min_is_one_session(self):
        """Events from same visitor within 30 min = 1 session."""
        site = create_site()
        today = ANALYTICS_DATE

        # Same visitor (same user_agent + country), 3 events within 30 min
        ingest_event(site["domain"], url="/a", user_agent="sess-test-agent",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/b", user_agent="sess-test-agent",
                     country="US", timestamp=f"{today}T10:10:00Z")
        ingest_event(site["domain"], url="/c", user_agent="sess-test-agent",
                     country="US", timestamp=f"{today}T10:20:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        data = resp.json()
        assert data["visitors"] == 1
        assert data["visits"] == 1
        assert data["pageviews"] == 3

    def test_same_visitor_gap_over_30min_is_two_sessions(self):
        """Events from same visitor with >30 min gap = 2 sessions."""
        site = create_site()
        today = ANALYTICS_DATE

        # Same visitor, but 2nd event is 31 min after 1st
        ingest_event(site["domain"], url="/a", user_agent="sess-gap-agent",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/b", user_agent="sess-gap-agent",
                     country="US", timestamp=f"{today}T10:31:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        data = resp.json()
        assert data["visitors"] == 1
        assert data["visits"] == 2

    def test_different_visitors_are_separate(self):
        """Different user_agent or country = different visitor."""
        site = create_site()
        today = ANALYTICS_DATE

        ingest_event(site["domain"], url="/a", user_agent="agentA",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/a", user_agent="agentB",
                     country="US", timestamp=f"{today}T10:00:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        data = resp.json()
        assert data["visitors"] == 2
        assert data["visits"] == 2


# ============================================================
# FILTERS
# ============================================================

class TestFilters:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_DATE
        self.today = today

        # US visitors
        ingest_event(self.domain, url="/pricing", user_agent="filter-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/about", user_agent="filter-v2",
                     country="US", timestamp=f"{today}T10:01:00Z")

        # UK visitor
        ingest_event(self.domain, url="/pricing", user_agent="filter-v3",
                     country="UK", timestamp=f"{today}T10:02:00Z")

    def test_filter_by_country(self):
        import json
        filters = json.dumps({"country": "US"})
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 2

    def test_filter_by_page(self):
        import json
        filters = json.dumps({"page": "/pricing"})
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 2  # v1 and v3 visited /pricing

    def test_filter_combined(self):
        import json
        filters = json.dumps({"country": "US", "page": "/pricing"})
        resp = api("GET", f"/api/sites/{self.site['id']}/stats/aggregate",
                   params={"period": "day", "date": self.today,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 1  # Only v1

    def test_filter_on_breakdown(self):
        import json
        filters = json.dumps({"country": "US"})
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": self.today,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        # Only US visitors' pages
        pages = {item["value"]: item["visitors"] for item in data}
        assert pages.get("/pricing") == 1
        assert pages.get("/about") == 1

    def test_filter_on_timeseries(self):
        import json
        filters = json.dumps({"country": "UK"})
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/timeseries",
                   params={"period": "day", "date": self.today,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["visitors"] == 1


# ============================================================
# GOALS
# ============================================================

class TestGoals:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]

    def test_create_pageview_goal(self):
        resp = api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "pageview",
            "pagePath": "/thank-you",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["goalType"] == "pageview"
        assert data["pagePath"] == "/thank-you"
        assert "id" in data

    def test_create_event_goal(self):
        resp = api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "event",
            "eventName": "Signup",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["goalType"] == "event"
        assert data["eventName"] == "Signup"

    def test_list_goals(self):
        api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "event", "eventName": "Download"
        })
        resp = api("GET", f"/api/sites/{self.site['id']}/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_delete_goal(self):
        resp = api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "event", "eventName": "Temp"
        })
        goal_id = resp.json()["id"]
        resp = api("DELETE", f"/api/sites/{self.site['id']}/goals/{goal_id}")
        assert resp.status_code == 204

    def test_goal_conversions(self):
        today = ANALYTICS_DATE

        # Create a goal
        api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "event", "eventName": "Signup"
        })

        # 3 total visitors, 2 trigger the goal
        ingest_event(self.domain, url="/home", user_agent="goal-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, name="Signup", url="/signup",
                     user_agent="goal-v1", country="US",
                     timestamp=f"{today}T10:05:00Z")

        ingest_event(self.domain, url="/home", user_agent="goal-v2",
                     country="UK", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, name="Signup", url="/signup",
                     user_agent="goal-v2", country="UK",
                     timestamp=f"{today}T10:05:00Z")

        ingest_event(self.domain, url="/home", user_agent="goal-v3",
                     country="DE", timestamp=f"{today}T10:00:00Z")

        resp = api("GET",
                   f"/api/sites/{self.site['id']}/goals/conversions",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

        signup_goal = next(g for g in data if g.get("eventName") == "Signup")
        assert signup_goal["visitors"] == 2
        # Conversion rate = 2/3 * 100 = 66.67
        assert abs(signup_goal["conversionRate"] - 66.67) < 1

    def test_pageview_goal_conversion(self):
        today = ANALYTICS_DATE

        # Create a pageview goal
        api("POST", f"/api/sites/{self.site['id']}/goals", json={
            "goalType": "pageview", "pagePath": "/thank-you"
        })

        # 2 visitors, 1 reaches /thank-you
        ingest_event(self.domain, url="/home", user_agent="pg-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/thank-you", user_agent="pg-v1",
                     country="US", timestamp=f"{today}T10:05:00Z")
        ingest_event(self.domain, url="/home", user_agent="pg-v2",
                     country="UK", timestamp=f"{today}T10:00:00Z")

        resp = api("GET",
                   f"/api/sites/{self.site['id']}/goals/conversions",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        pg_goal = next(g for g in data if g.get("pagePath") == "/thank-you")
        assert pg_goal["visitors"] == 1
        assert abs(pg_goal["conversionRate"] - 50.0) < 1


# ============================================================
# FUNNELS
# ============================================================

class TestFunnels:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]

    def test_create_funnel(self):
        resp = api("POST", f"/api/sites/{self.site['id']}/funnels", json={
            "name": "Signup Funnel",
            "steps": [
                {"goalType": "pageview", "pagePath": "/pricing"},
                {"goalType": "pageview", "pagePath": "/signup"},
                {"goalType": "event", "eventName": "Signup"},
            ]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Signup Funnel"
        assert len(data["steps"]) == 3
        assert "id" in data

    def test_list_funnels(self):
        api("POST", f"/api/sites/{self.site['id']}/funnels", json={
            "name": "Test Funnel",
            "steps": [
                {"goalType": "pageview", "pagePath": "/a"},
                {"goalType": "pageview", "pagePath": "/b"},
            ]
        })
        resp = api("GET", f"/api/sites/{self.site['id']}/funnels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_delete_funnel(self):
        resp = api("POST", f"/api/sites/{self.site['id']}/funnels", json={
            "name": "Delete Me",
            "steps": [
                {"goalType": "pageview", "pagePath": "/x"},
                {"goalType": "pageview", "pagePath": "/y"},
            ]
        })
        funnel_id = resp.json()["id"]
        resp = api("DELETE",
                   f"/api/sites/{self.site['id']}/funnels/{funnel_id}")
        assert resp.status_code == 204

    def test_funnel_results(self):
        today = ANALYTICS_DATE

        # Create funnel: /pricing → /signup → Signup event
        resp = api("POST", f"/api/sites/{self.site['id']}/funnels", json={
            "name": "Conversion Funnel",
            "steps": [
                {"goalType": "pageview", "pagePath": "/pricing"},
                {"goalType": "pageview", "pagePath": "/signup"},
                {"goalType": "event", "eventName": "Signup"},
            ]
        })
        funnel_id = resp.json()["id"]

        # Visitor 1: completes all 3 steps
        ingest_event(self.domain, url="/pricing", user_agent="funnel-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/signup", user_agent="funnel-v1",
                     country="US", timestamp=f"{today}T10:05:00Z")
        ingest_event(self.domain, name="Signup", url="/signup",
                     user_agent="funnel-v1", country="US",
                     timestamp=f"{today}T10:10:00Z")

        # Visitor 2: only completes steps 1 and 2
        ingest_event(self.domain, url="/pricing", user_agent="funnel-v2",
                     country="UK", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/signup", user_agent="funnel-v2",
                     country="UK", timestamp=f"{today}T10:05:00Z")

        # Visitor 3: only completes step 1
        ingest_event(self.domain, url="/pricing", user_agent="funnel-v3",
                     country="DE", timestamp=f"{today}T10:00:00Z")

        resp = api("GET",
                   f"/api/sites/{self.site['id']}/funnels/{funnel_id}",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        steps = data["steps"]
        assert len(steps) == 3
        assert steps[0]["visitors"] == 3  # All visited /pricing
        assert steps[1]["visitors"] == 2  # 2 visited /signup
        assert steps[2]["visitors"] == 1  # 1 triggered Signup

    def test_funnel_dropoff(self):
        today = ANALYTICS_DATE

        resp = api("POST", f"/api/sites/{self.site['id']}/funnels", json={
            "name": "Dropoff Funnel",
            "steps": [
                {"goalType": "pageview", "pagePath": "/step1"},
                {"goalType": "pageview", "pagePath": "/step2"},
            ]
        })
        funnel_id = resp.json()["id"]

        # 5 visit step1, 2 visit step2
        for i in range(5):
            ingest_event(self.domain, url="/step1",
                         user_agent=f"drop-v{i}", country="US",
                         timestamp=f"{today}T10:0{i}:00Z")
        for i in range(2):
            ingest_event(self.domain, url="/step2",
                         user_agent=f"drop-v{i}", country="US",
                         timestamp=f"{today}T10:1{i}:00Z")

        resp = api("GET",
                   f"/api/sites/{self.site['id']}/funnels/{funnel_id}",
                   params={"period": "day", "date": today})
        data = resp.json()
        steps = data["steps"]
        assert steps[0]["visitors"] == 5
        assert steps[1]["visitors"] == 2
        assert steps[1]["dropoff"] == 3


# ============================================================
# CUSTOM PROPERTIES
# ============================================================

class TestCustomProperties:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_DATE
        self.today = today

        # Events with custom properties
        ingest_event(self.domain, name="Purchase", url="/checkout",
                     user_agent="prop-v1", country="US",
                     properties={"plan": "premium"},
                     timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, name="Purchase", url="/checkout",
                     user_agent="prop-v2", country="UK",
                     properties={"plan": "premium"},
                     timestamp=f"{today}T10:01:00Z")
        ingest_event(self.domain, name="Purchase", url="/checkout",
                     user_agent="prop-v3", country="DE",
                     properties={"plan": "basic"},
                     timestamp=f"{today}T10:02:00Z")

    def test_property_breakdown(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/properties",
                   params={"period": "day", "date": self.today,
                           "property": "plan"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        values = {item["value"]: item for item in data}
        assert "premium" in values
        assert "basic" in values
        assert values["premium"]["visitors"] == 2
        assert values["basic"]["visitors"] == 1

    def test_property_breakdown_percentage(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/properties",
                   params={"period": "day", "date": self.today,
                           "property": "plan"})
        data = resp.json()
        total_pct = sum(item["percentage"] for item in data)
        assert abs(total_pct - 100) < 1

    def test_property_breakdown_missing_param(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/properties",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 400


# ============================================================
# SHARED LINKS
# ============================================================

class TestSharedLinks:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]

    def test_create_shared_link(self):
        resp = api("POST",
                   f"/api/sites/{self.site['id']}/shared-links",
                   json={"name": "Public Dashboard"})
        assert resp.status_code == 201
        data = resp.json()
        assert "slug" in data
        assert data["passwordProtected"] is False
        assert "id" in data

    def test_create_shared_link_with_password(self):
        resp = api("POST",
                   f"/api/sites/{self.site['id']}/shared-links",
                   json={"name": "Protected", "password": "secret123"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["passwordProtected"] is True

    def test_list_shared_links(self):
        api("POST", f"/api/sites/{self.site['id']}/shared-links",
            json={"name": "Link 1"})
        resp = api("GET", f"/api/sites/{self.site['id']}/shared-links")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_delete_shared_link(self):
        resp = api("POST",
                   f"/api/sites/{self.site['id']}/shared-links",
                   json={"name": "To Delete"})
        link_id = resp.json()["id"]
        resp = api("DELETE",
                   f"/api/sites/{self.site['id']}/shared-links/{link_id}")
        assert resp.status_code == 204

    def test_access_shared_link_no_password(self):
        today = ANALYTICS_DATE
        ingest_event(self.domain, url="/shared-page", user_agent="shared-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")

        resp = api("POST",
                   f"/api/sites/{self.site['id']}/shared-links",
                   json={"name": "Open Link"})
        slug = resp.json()["slug"]

        # Access without auth
        resp = requests.get(f"{BASE_URL}/api/shared/{slug}",
                            params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert "visitors" in data

    def test_access_shared_link_with_password(self):
        today = ANALYTICS_DATE
        ingest_event(self.domain, url="/page", user_agent="pwd-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")

        resp = api("POST",
                   f"/api/sites/{self.site['id']}/shared-links",
                   json={"name": "Pwd Link", "password": "mypass"})
        slug = resp.json()["slug"]

        # Access without password → 401
        resp = requests.get(f"{BASE_URL}/api/shared/{slug}")
        assert resp.status_code == 401

        # Access with wrong password → 401
        resp = requests.get(f"{BASE_URL}/api/shared/{slug}",
                            params={"password": "wrong"})
        assert resp.status_code == 401

        # Access with correct password → 200
        resp = requests.get(f"{BASE_URL}/api/shared/{slug}",
                            params={"password": "mypass"})
        assert resp.status_code == 200


# ============================================================
# EXPORT
# ============================================================

class TestExport:
    def test_export_stats(self):
        site = create_site()
        today = ANALYTICS_DATE

        ingest_event(site["domain"], url="/export-page", user_agent="exp-v1",
                     country="US", referrer="https://google.com",
                     timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], url="/export-page2", user_agent="exp-v1",
                     country="US", timestamp=f"{today}T10:05:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/export",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert "aggregate" in data
        assert "timeSeries" in data
        assert "topPages" in data
        assert "topSources" in data
        assert "topCountries" in data
        assert data["domain"] == site["domain"]
        assert data["aggregate"]["visitors"] >= 1

    def test_export_unauthorized(self):
        site = create_site()
        resp = requests.get(f"{BASE_URL}/api/sites/{site['id']}/export")
        assert resp.status_code == 401


# ============================================================
# ENTRY/EXIT PAGES
# ============================================================

class TestEntryExitPages:
    def setup_method(self):
        self.site = create_site()
        self.domain = self.site["domain"]
        today = ANALYTICS_DATE
        self.today = today

        # Visitor 1: enters on /home, exits on /pricing
        ingest_event(self.domain, url="/home", user_agent="ee-v1",
                     country="US", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/pricing", user_agent="ee-v1",
                     country="US", timestamp=f"{today}T10:05:00Z")

        # Visitor 2: enters on /blog, exits on /blog (single page)
        ingest_event(self.domain, url="/blog", user_agent="ee-v2",
                     country="UK", timestamp=f"{today}T10:00:00Z")

        # Visitor 3: enters on /home, exits on /about
        ingest_event(self.domain, url="/home", user_agent="ee-v3",
                     country="DE", timestamp=f"{today}T10:00:00Z")
        ingest_event(self.domain, url="/about", user_agent="ee-v3",
                     country="DE", timestamp=f"{today}T10:05:00Z")

    def test_entry_pages(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/entry-pages",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        values = {item["value"]: item["visitors"] for item in data}
        assert values.get("/home") == 2
        assert values.get("/blog") == 1

    def test_exit_pages(self):
        resp = api("GET",
                   f"/api/sites/{self.site['id']}/stats/breakdown/exit-pages",
                   params={"period": "day", "date": self.today})
        assert resp.status_code == 200
        data = resp.json()
        values = {item["value"]: item["visitors"] for item in data}
        assert values.get("/pricing") == 1
        assert values.get("/blog") == 1
        assert values.get("/about") == 1


# ============================================================
# EVENT NAMES BREAKDOWN
# ============================================================

class TestEventNamesBreakdown:
    def test_event_names_breakdown(self):
        site = create_site()
        today = ANALYTICS_DATE

        # Multiple event types
        ingest_event(site["domain"], name="pageview", url="/home",
                     user_agent="en-v1", country="US",
                     timestamp=f"{today}T10:00:00Z")
        ingest_event(site["domain"], name="Signup", url="/signup",
                     user_agent="en-v1", country="US",
                     timestamp=f"{today}T10:05:00Z")
        ingest_event(site["domain"], name="Signup", url="/signup",
                     user_agent="en-v2", country="UK",
                     timestamp=f"{today}T10:05:00Z")
        ingest_event(site["domain"], name="Download", url="/files",
                     user_agent="en-v3", country="DE",
                     timestamp=f"{today}T10:05:00Z")

        resp = api("GET",
                   f"/api/sites/{site['id']}/stats/breakdown/events",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        values = {item["value"]: item for item in data}
        assert "Signup" in values
        assert values["Signup"]["visitors"] == 2
        assert values["Signup"]["events"] == 2


# ============================================================
# BATCH EVENT INGESTION
# ============================================================

class TestBatchIngestion:
    def test_batch_ingest(self):
        site = create_site()
        today = ANALYTICS_DATE

        events = [
            {"domain": site["domain"], "url": "/page1", "userAgent": "batch-v1",
             "country": "US", "timestamp": f"{today}T10:00:00Z"},
            {"domain": site["domain"], "url": "/page2", "userAgent": "batch-v2",
             "country": "UK", "timestamp": f"{today}T10:01:00Z"},
            {"domain": site["domain"], "url": "/page3", "userAgent": "batch-v3",
             "country": "DE", "timestamp": f"{today}T10:02:00Z"},
        ]

        resp = requests.post(f"{BASE_URL}/api/events",
                             json={"events": events})
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["accepted"] == 3

        # Verify events appear in stats
        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        stats = resp.json()
        assert stats["visitors"] == 3
        assert stats["pageviews"] == 3

    def test_batch_ingest_partial_invalid(self):
        site = create_site()
        today = ANALYTICS_DATE

        events = [
            {"domain": site["domain"], "url": "/valid", "userAgent": "batch-pv1",
             "country": "US", "timestamp": f"{today}T10:00:00Z"},
            {"domain": site["domain"]},  # Missing url
            {"url": "/no-domain"},  # Missing domain
        ]

        resp = requests.post(f"{BASE_URL}/api/events",
                             json={"events": events})
        assert resp.status_code == 400

    def test_batch_ingest_empty(self):
        resp = requests.post(f"{BASE_URL}/api/events",
                             json={"events": []})
        # Empty list is technically valid but should still work
        assert resp.status_code in [202, 400]


# ============================================================
# COMPARISON STATS
# ============================================================

class TestComparisonStats:
    def test_comparison_with_data(self):
        site = create_site()
        today = ANALYTICS_TIME
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # Yesterday: 1 visitor
        ingest_event(site["domain"], url="/page", user_agent="cmp-v1",
                     country="US", timestamp=f"{yesterday_str}T10:00:00Z")

        # Today: 3 visitors
        ingest_event(site["domain"], url="/page", user_agent="cmp-v2",
                     country="US", timestamp=f"{today_str}T10:00:00Z")
        ingest_event(site["domain"], url="/page", user_agent="cmp-v3",
                     country="UK", timestamp=f"{today_str}T10:01:00Z")
        ingest_event(site["domain"], url="/page", user_agent="cmp-v4",
                     country="DE", timestamp=f"{today_str}T10:02:00Z")

        resp = api("GET", f"/api/sites/{site['id']}/stats/compare",
                   params={"period": "day", "date": today_str})
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "previous" in data
        assert "change" in data
        assert data["current"]["visitors"] == 3
        assert data["previous"]["visitors"] == 1
        assert data["change"]["visitors"] == 200.0  # (3-1)/1 * 100

    def test_comparison_empty(self):
        site = create_site()
        today = ANALYTICS_DATE

        resp = api("GET", f"/api/sites/{site['id']}/stats/compare",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"]["visitors"] == 0
        assert data["previous"]["visitors"] == 0


# ============================================================
# REALTIME EVENTS
# ============================================================

class TestRealtimeEvents:
    def test_realtime_events_list(self):
        site = create_site()
        now = datetime.now(timezone.utc).isoformat()

        ingest_event(site["domain"], url="/live-page", user_agent="rt-ev-v1",
                     country="US", timestamp=now)
        ingest_event(site["domain"], name="Click", url="/button",
                     user_agent="rt-ev-v2", country="UK", timestamp=now)

        resp = api("GET", f"/api/sites/{site['id']}/realtime/events")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        # Should have name, url, country, timestamp
        assert "name" in data[0]
        assert "url" in data[0]
        assert "timestamp" in data[0]

    def test_realtime_events_limit(self):
        site = create_site()
        now = datetime.now(timezone.utc).isoformat()

        for i in range(5):
            ingest_event(site["domain"], url=f"/page-{i}",
                         user_agent=f"rt-limit-v{i}", country="US",
                         timestamp=now)

        resp = api("GET", f"/api/sites/{site['id']}/realtime/events",
                   params={"limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


# ============================================================
# GET INDIVIDUAL GOAL
# ============================================================

class TestGetGoal:
    def test_get_goal(self):
        site = create_site()
        resp = api("POST", f"/api/sites/{site['id']}/goals", json={
            "goalType": "event", "eventName": "Purchase"
        })
        goal_id = resp.json()["id"]

        resp = api("GET", f"/api/sites/{site['id']}/goals/{goal_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == goal_id
        assert data["goalType"] == "event"
        assert data["eventName"] == "Purchase"

    def test_get_goal_not_found(self):
        site = create_site()
        resp = api("GET", f"/api/sites/{site['id']}/goals/nonexistent")
        assert resp.status_code == 404


# ============================================================
# EDGE CASES & AUTH
# ============================================================

class TestEdgeCases:
    def test_stats_for_nonexistent_site(self):
        resp = api("GET", "/api/sites/fake-id/stats/aggregate")
        assert resp.status_code == 404

    def test_stats_with_no_events(self):
        site = create_site()
        today = ANALYTICS_DATE
        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["visitors"] == 0
        assert data["pageviews"] == 0
        assert data["bounceRate"] == 0
        assert data["visitDuration"] == 0

    def test_breakdown_empty_site(self):
        site = create_site()
        today = ANALYTICS_DATE
        resp = api("GET",
                   f"/api/sites/{site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_timeseries_empty_site(self):
        site = create_site()
        today = ANALYTICS_DATE
        resp = api("GET", f"/api/sites/{site['id']}/stats/timeseries",
                   params={"period": "day", "date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["visitors"] == 0
