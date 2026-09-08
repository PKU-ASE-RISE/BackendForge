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


def test_goal_delete_respects_site_scope():
    owner_site = create_site()
    other_site = create_site()
    event_name = f"Signup-{uuid.uuid4().hex}"

    created = api(
        "POST",
        f"/api/sites/{owner_site['id']}/goals",
        json={"goalType": "event", "eventName": event_name},
    )
    assert created.status_code == 201, created.text
    goal = created.json()

    wrong_site_delete = api("DELETE", f"/api/sites/{other_site['id']}/goals/{goal['id']}")
    assert wrong_site_delete.status_code == 404, wrong_site_delete.text

    still_there = api("GET", f"/api/sites/{owner_site['id']}/goals/{goal['id']}")
    assert still_there.status_code == 200, still_there.text
    assert still_there.json()["id"] == goal["id"]
