import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")
ANALYTICS_DATE = "2024-01-15"
ANALYTICS_TIMESTAMP = f"{ANALYTICS_DATE}T12:00:00+00:00"


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = API_KEY
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def create_site():
    domain = f"events-breakdown-{uuid.uuid4().hex}.example"
    resp = api("POST", "/api/sites", json={"domain": domain})
    assert resp.status_code == 201, resp.text
    return resp.json()


def ingest(domain, name, url_value, user_agent):
    resp = requests.post(
        f"{BASE_URL}/api/event",
        json={
            "domain": domain,
            "name": name,
            "url": url_value,
            "userAgent": user_agent,
            "country": "US",
            "timestamp": ANALYTICS_TIMESTAMP,
        },
    )
    assert resp.status_code == 202, resp.text


def test_event_breakdown_excludes_pageview_events():
    site = create_site()
    suffix = uuid.uuid4().hex
    ingest(site["domain"], "pageview", f"landing-{suffix}", f"visitor-pageview-{suffix}")
    ingest(site["domain"], "Signup", f"signup-{suffix}", f"visitor-signup-{suffix}")

    resp = api(
        "GET",
        f"/api/sites/{site['id']}/stats/breakdown/events",
        params={"period": "day", "date": ANALYTICS_DATE},
    )

    assert resp.status_code == 200, resp.text
    values = {item["value"] for item in resp.json()}
    assert "Signup" in values
    assert "pageview" not in values
