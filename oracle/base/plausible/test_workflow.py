"""
L3 Workflow Tests for Plausible Analytics API.
Multi-step workflows covering:
- Complete analytics pipeline (ingest -> query)
- Funnel analysis
- Goal conversions
- Multi-site isolation
- Breakdown + filter combinations
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
# L3 TESTS — Workflow
# =============================================================================


class TestAnalyticsPipeline:
    """Full pipeline: ingest events -> query aggregate + breakdown + timeseries."""

    def test_full_analytics_pipeline(self):
        """
        Pattern 5+3: Ingest multiple events with varied metadata,
        verify aggregate stats, breakdown, and timeseries all reflect the data.
        """
        site = create_site()
        now = ANALYTICS_TIME

        # 1. Ingest events from different visitors/pages/countries
        # Visitor A: 2 pageviews (not a bounce)
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=60)).isoformat()
        ingest(site["domain"], url="/home", timestamp=t1, user_agent="VisitorA", country="US", referrer="https://google.com")
        ingest(site["domain"], url="/about", timestamp=t2, user_agent="VisitorA", country="US")

        # Visitor B: 1 pageview (bounce)
        ingest(site["domain"], url="/pricing", timestamp=t1, user_agent="VisitorB", country="UK", referrer="https://twitter.com")

        # Visitor C: 1 pageview (bounce)
        ingest(site["domain"], url="/home", timestamp=t1, user_agent="VisitorC", country="DE", screen_size="mobile")

        # 2. Check aggregate stats
        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["visitors"] == 3
        assert stats["pageviews"] == 4
        assert stats["visits"] == 3
        # 2 of 3 sessions are bounces -> ~67%
        assert stats["bounceRate"] == pytest.approx(67, abs=1)

        # 3. Breakdown by page
        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": ANALYTICS_DATE})
        pages = resp.json()
        page_map = {p["value"]: p for p in pages}
        assert "/home" in page_map
        assert page_map["/home"]["visitors"] == 2
        assert "/pricing" in page_map
        assert page_map["/pricing"]["visitors"] == 1

        # 4. Breakdown by country
        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/countries",
                   params={"period": "day", "date": ANALYTICS_DATE})
        countries = resp.json()
        country_map = {c["value"]: c for c in countries}
        assert "US" in country_map
        assert "UK" in country_map
        assert "DE" in country_map

        # 5. Timeseries
        resp = api("GET", f"/api/sites/{site['id']}/stats/timeseries",
                   params={"period": "7d", "date": ANALYTICS_DATE})
        assert resp.status_code == 200
        ts = resp.json()
        assert isinstance(ts, list)
        assert len(ts) > 0
        # Today's entry should have data
        today = now.strftime("%Y-%m-%d")
        today_point = next((p for p in ts if p["date"] == today), None)
        assert today_point is not None
        assert today_point["visitors"] == 3
        assert today_point["pageviews"] == 4


class TestGoalConversions:
    """Goal creation and conversion rate tracking."""

    def test_goal_conversion_workflow(self):
        """
        Pattern 5+2: Create goals, ingest events matching goals,
        verify conversion rates are calculated correctly.
        """
        site = create_site()
        now = ANALYTICS_TIME.isoformat()

        # 1. Create goals
        goal1 = api("POST", f"/api/sites/{site['id']}/goals", json={
            "goalType": "event", "eventName": "Signup"
        }).json()
        goal2 = api("POST", f"/api/sites/{site['id']}/goals", json={
            "goalType": "pageview", "pagePath": "/thank-you"
        }).json()

        # 2. Ingest events: 3 visitors, 2 do Signup, 1 visits thank-you
        ingest(site["domain"], url="/", timestamp=now, user_agent="G1", country="US")
        ingest(site["domain"], name="Signup", url="/", timestamp=now, user_agent="G1", country="US")

        ingest(site["domain"], url="/", timestamp=now, user_agent="G2", country="UK")
        ingest(site["domain"], name="Signup", url="/", timestamp=now, user_agent="G2", country="UK")
        ingest(site["domain"], url="/thank-you", timestamp=now, user_agent="G2", country="UK")

        ingest(site["domain"], url="/", timestamp=now, user_agent="G3", country="DE")

        # 3. Check goal conversions
        resp = api(
            "GET",
            f"/api/sites/{site['id']}/goals/conversions",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        conversions = resp.json()
        assert isinstance(conversions, list)

        # Find Signup goal
        signup_conv = next((c for c in conversions if c.get("eventName") == "Signup"), None)
        assert signup_conv is not None
        assert signup_conv["visitors"] == 2
        # 2 of 3 total visitors -> ~66.7%
        assert signup_conv["conversionRate"] == pytest.approx(66.7, abs=1)

        # Find pageview goal
        page_conv = next((c for c in conversions if c.get("pagePath") == "/thank-you"), None)
        assert page_conv is not None
        assert page_conv["visitors"] == 1


class TestFunnelWorkflow:
    """Funnel analysis with step-by-step tracking."""

    def test_funnel_analysis(self):
        """
        Pattern 5+2: Create funnel, ingest events matching steps,
        verify step visitors and dropoff.
        """
        site = create_site()
        now = ANALYTICS_TIME

        # 1. Create funnel
        resp = api("POST", f"/api/sites/{site['id']}/funnels", json={
            "name": "Signup Funnel",
            "steps": [
                {"goalType": "pageview", "pagePath": "/landing"},
                {"goalType": "pageview", "pagePath": "/signup"},
                {"goalType": "event", "eventName": "FormSubmit"}
            ]
        })
        assert resp.status_code == 201
        funnel = resp.json()
        assert funnel["name"] == "Signup Funnel"
        assert len(funnel["steps"]) == 3

        # 2. Ingest events for 3 visitors with different progression
        t = now.isoformat()
        # Visitor A: completes all 3 steps
        ingest(site["domain"], url="/landing", timestamp=t, user_agent="FunnelA", country="US")
        ingest(site["domain"], url="/signup", timestamp=t, user_agent="FunnelA", country="US")
        ingest(site["domain"], name="FormSubmit", url="/signup", timestamp=t, user_agent="FunnelA", country="US")

        # Visitor B: completes step 1 and 2 only
        ingest(site["domain"], url="/landing", timestamp=t, user_agent="FunnelB", country="UK")
        ingest(site["domain"], url="/signup", timestamp=t, user_agent="FunnelB", country="UK")

        # Visitor C: completes step 1 only
        ingest(site["domain"], url="/landing", timestamp=t, user_agent="FunnelC", country="DE")

        # 3. Get funnel results
        resp = api("GET", f"/api/sites/{site['id']}/funnels/{funnel['id']}",
                   params={"period": "day", "date": ANALYTICS_DATE})
        assert resp.status_code == 200
        result = resp.json()
        assert "steps" in result
        steps = result["steps"]
        assert len(steps) == 3

        # Step 1: 3 visitors
        assert steps[0]["visitors"] == 3
        # Step 2: 2 visitors
        assert steps[1]["visitors"] == 2
        # Step 3: 1 visitor
        assert steps[2]["visitors"] == 1


class TestSiteIsolation:
    """Pattern 6: Data from different sites is completely isolated."""

    def test_sites_do_not_share_data(self):
        """Events on site A should not appear in site B's stats."""
        site_a = create_site()
        site_b = create_site()
        now = ANALYTICS_TIME.isoformat()

        # Ingest events on site A only
        ingest(site_a["domain"], url="/a-page", timestamp=now, user_agent="Iso1", country="US")
        ingest(site_a["domain"], url="/a-page2", timestamp=now, user_agent="Iso2", country="UK")

        # Site A stats should have data
        resp = api(
            "GET",
            f"/api/sites/{site_a['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.json()["visitors"] == 2

        # Site B stats should be empty
        resp = api(
            "GET",
            f"/api/sites/{site_b['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        stats_b = resp.json()
        assert stats_b["visitors"] == 0
        assert stats_b["pageviews"] == 0


class TestFilteredBreakdowns:
    """Pattern 3: Filters combined with breakdowns."""

    def test_breakdown_with_country_filter(self):
        """Apply country filter on page breakdown."""
        site = create_site()
        now = ANALYTICS_TIME.isoformat()

        ingest(site["domain"], url="/page1", timestamp=now, user_agent="FB1", country="US")
        ingest(site["domain"], url="/page2", timestamp=now, user_agent="FB2", country="US")
        ingest(site["domain"], url="/page1", timestamp=now, user_agent="FB3", country="UK")

        # Breakdown by page, filtered to US only
        filters = json.dumps({"country": "US"})
        resp = api("GET", f"/api/sites/{site['id']}/stats/breakdown/pages",
                   params={"period": "day", "date": ANALYTICS_DATE,
                           "filters": filters})
        assert resp.status_code == 200
        data = resp.json()
        # Should only have US visitors
        total_visitors = sum(p["visitors"] for p in data)
        assert total_visitors == 2


class TestCustomEvents:
    """Custom events and properties."""

    def test_custom_event_tracking(self):
        """
        Pattern 5: Custom events appear in aggregate and can be filtered by eventName.
        """
        site = create_site()
        now = ANALYTICS_TIME.isoformat()

        # 1. Ingest pageviews and custom events
        ingest(site["domain"], url="/", timestamp=now, user_agent="CE1", country="US")
        ingest(site["domain"], name="Download", url="/", timestamp=now, user_agent="CE1", country="US",
               properties={"file": "report.pdf"})
        ingest(site["domain"], name="Download", url="/", timestamp=now, user_agent="CE2", country="UK",
               properties={"file": "guide.pdf"})

        # 2. Aggregate should count all events
        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        stats = resp.json()
        assert stats["events"] >= 3

        # 3. Filter by eventName
        filters = json.dumps({"eventName": "Download"})
        resp = api("GET", f"/api/sites/{site['id']}/stats/aggregate",
                   params={"period": "day", "date": ANALYTICS_DATE,
                           "filters": filters})
        filtered = resp.json()
        assert filtered["events"] == 2
        assert filtered["visitors"] == 2


class TestSharedLinkWorkflow:
    """Shared links creation and access."""

    def test_shared_link_lifecycle(self):
        """Pattern 1+4+7: Create, list, delete shared links."""
        site = create_site()

        # 1. Create shared link
        resp = api("POST", f"/api/sites/{site['id']}/shared-links", json={
            "name": "Team Dashboard"
        })
        assert resp.status_code == 201
        link = resp.json()
        assert link["siteId"] == site["id"]
        assert "slug" in link
        assert link["passwordProtected"] is False

        # 2. List shared links
        resp = api("GET", f"/api/sites/{site['id']}/shared-links")
        assert resp.status_code == 200
        links = resp.json()
        assert any(l["id"] == link["id"] for l in links)

        # 3. Delete shared link
        resp = api("DELETE", f"/api/sites/{site['id']}/shared-links/{link['id']}")
        assert resp.status_code == 204

        # 4. Verify gone from list
        resp = api("GET", f"/api/sites/{site['id']}/shared-links")
        links = resp.json()
        assert not any(l["id"] == link["id"] for l in links)


class TestExportWorkflow:
    """Export data in structured format."""

    def test_export_contains_all_sections(self):
        """Pattern 2: Export contains aggregate, timeseries, and breakdowns."""
        site = create_site()
        now = ANALYTICS_TIME.isoformat()
        ingest(site["domain"], url="/export-page", timestamp=now, user_agent="Exp1", country="US", referrer="https://google.com")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/export",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "siteId" in data
        assert "domain" in data
        assert data["domain"] == site["domain"]
        assert "aggregate" in data
        assert "timeSeries" in data
        assert "topPages" in data
        assert "topSources" in data
        assert "topCountries" in data
        # Verify aggregate has data
        assert data["aggregate"]["visitors"] >= 1
        assert data["aggregate"]["pageviews"] >= 1


class TestVisitDuration:
    """Pattern 5: Visit duration actually computed from timestamps."""

    def test_visit_duration_calculated(self):
        """Sessions with multiple events should have non-zero duration."""
        site = create_site()
        now = ANALYTICS_TIME
        t1 = now.isoformat()
        t2 = (now + timedelta(seconds=120)).isoformat()

        # Visitor with 2 events 120 seconds apart
        ingest(site["domain"], url="/start", timestamp=t1, user_agent="Duration1", country="US")
        ingest(site["domain"], url="/end", timestamp=t2, user_agent="Duration1", country="US")

        resp = api(
            "GET",
            f"/api/sites/{site['id']}/stats/aggregate",
            params={"period": "day", "date": ANALYTICS_DATE},
        )
        stats = resp.json()
        # Average duration should be 120 seconds (only 1 session)
        assert stats["visitDuration"] == 120
