import os
import uuid
from datetime import datetime, timedelta, timezone

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = API_KEY
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def create_site():
    domain = f"drp-{uuid.uuid4().hex}.example.com"
    response = api("POST", "/api/sites", json={"domain": domain, "timezone": "UTC"})
    assert response.status_code == 201, response.text
    return response.json()


def test_realtime_excludes_future_events():
    site = create_site()
    future_url = f"/future-{uuid.uuid4().hex}"
    future_timestamp = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    ingested = requests.post(
        f"{BASE_URL}/api/event",
        json={
            "domain": site["domain"],
            "url": future_url,
            "userAgent": f"FutureUA-{uuid.uuid4().hex}",
            "country": "US",
            "timestamp": future_timestamp,
        },
    )
    assert ingested.status_code == 202, ingested.text

    visitors = api("GET", f"/api/sites/{site['id']}/realtime/visitors")
    assert visitors.status_code == 200, visitors.text
    assert visitors.json()["visitors"] == 0

    events = api("GET", f"/api/sites/{site['id']}/realtime/events")
    assert events.status_code == 200, events.text
    assert all(event["url"] != future_url for event in events.json())
