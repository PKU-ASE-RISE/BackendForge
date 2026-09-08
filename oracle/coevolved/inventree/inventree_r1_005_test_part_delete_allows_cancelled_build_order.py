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


def api_post(path, payload=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_delete(path):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def test_part_delete_allows_cancelled_build_order():
    suffix = uuid.uuid4().hex
    part = api_post("/api/parts", {"name": f"CancelledBuildPart-{suffix}", "assembly": True}).json()
    build = api_post("/api/builds", {"part": part["id"], "quantity": 1}).json()
    cancelled = api_post(f"/api/builds/{build['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"

    response = api_delete(f"/api/parts/{part['id']}")

    assert response.status_code == 204
    assert api_get(f"/api/parts/{part['id']}").status_code == 404
