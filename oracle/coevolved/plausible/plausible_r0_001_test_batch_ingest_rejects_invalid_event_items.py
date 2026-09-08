import os
import uuid

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


def test_batch_ingest_rejects_invalid_event_items():
    site = create_site()
    response = requests.post(
        f"{BASE_URL}/api/events",
        json={"events": [{"domain": site["domain"], "name": "pageview"}]},
    )
    assert response.status_code == 400, response.text
