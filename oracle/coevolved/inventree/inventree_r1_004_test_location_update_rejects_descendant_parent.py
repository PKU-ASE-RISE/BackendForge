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


def test_location_update_rejects_descendant_parent():
    suffix = uuid.uuid4().hex
    warehouse = api_post("/api/locations", {"name": f"Warehouse-{suffix}"}).json()
    shelf = api_post("/api/locations", {"name": f"Shelf-{suffix}", "parent": warehouse["id"]}).json()

    response = api_put(f"/api/locations/{warehouse['id']}", {"name": warehouse["name"], "parent": shelf["id"]})

    assert response.status_code == 400
    assert "error" in response.json()

    warehouse_after = api_get(f"/api/locations/{warehouse['id']}").json()
    shelf_after = api_get(f"/api/locations/{shelf['id']}").json()
    assert warehouse_after["parent"] is None
    assert warehouse_after["pathstring"] == warehouse["name"]
    assert shelf_after["parent"] == warehouse["id"]
    assert shelf_after["pathstring"] == f"{warehouse['name']}/{shelf['name']}"
