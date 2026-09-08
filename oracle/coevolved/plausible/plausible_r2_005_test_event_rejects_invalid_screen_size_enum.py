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


def test_event_rejects_invalid_screen_size_enum():
    domain = f"screen-enum-{uuid.uuid4().hex}.example"
    site_resp = api("POST", "/api/sites", json={"domain": domain})
    assert site_resp.status_code == 201, site_resp.text
    site = site_resp.json()

    resp = requests.post(
        f"{BASE_URL}/api/event",
        json={
            "domain": domain,
            "name": "pageview",
            "url": "screen-size-page",
            "screenSize": "console",
            "userAgent": f"screen-agent-{uuid.uuid4().hex}",
            "country": "US",
            "timestamp": ANALYTICS_TIMESTAMP,
        },
    )

    assert resp.status_code == 400, resp.text

    stats_resp = api(
        "GET",
        f"/api/sites/{site['id']}/stats/aggregate",
        params={"period": "day", "date": ANALYTICS_DATE},
    )
    assert stats_resp.status_code == 200, stats_resp.text
    assert stats_resp.json()["events"] == 0
