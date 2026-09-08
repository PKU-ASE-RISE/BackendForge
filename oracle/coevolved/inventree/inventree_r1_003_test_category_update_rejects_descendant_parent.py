import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30
HEADERS = {"X-Api-Key": "test-api-key-inventree", "Content-Type": "application/json"}


def api_get(path, params=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path, payload):
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path, payload):
    return requests.put(
        f"{BASE_URL}{path}",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def test_category_update_rejects_descendant_parent():
    suffix = uuid.uuid4().hex
    root = api_post("/api/categories", {"name": f"Root-{suffix}"}).json()
    child = api_post("/api/categories", {"name": f"Child-{suffix}", "parent": root["id"]}).json()

    response = api_put(f"/api/categories/{root['id']}", {"name": root["name"], "parent": child["id"]})

    assert response.status_code == 400
    assert "error" in response.json()

    root_after = api_get(f"/api/categories/{root['id']}").json()
    child_after = api_get(f"/api/categories/{child['id']}").json()
    assert root_after["parent"] is None
    assert root_after["pathstring"] == root["name"]
    assert child_after["parent"] == root["id"]
    assert child_after["pathstring"] == f"{root['name']}/{child['name']}"
