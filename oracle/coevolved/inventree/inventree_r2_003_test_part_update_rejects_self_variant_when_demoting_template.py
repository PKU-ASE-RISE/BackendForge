import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30
HEADERS = {"X-Api-Key": "test-api-key-inventree", "Content-Type": "application/json"}


def api_get(path):
    return requests.get(
        f"{BASE_URL}{path}",
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


def test_part_update_rejects_self_variant_when_demoting_template():
    token = uuid.uuid4().hex
    created = api_post("/api/parts", {"name": f"TemplateSelfVar-{token}", "is_template": True})
    assert created.status_code == 201
    part = created.json()
    assert part["is_template"] is True
    assert part["variant_of"] is None

    update = api_put(
        f"/api/parts/{part['id']}",
        {
            "name": part["name"],
            "is_template": False,
            "variant_of": part["id"],
        },
    )
    assert update.status_code == 400
    assert "error" in update.json()

    reloaded = api_get(f"/api/parts/{part['id']}")
    assert reloaded.status_code == 200
    data = reloaded.json()
    assert data["is_template"] is True
    assert data["variant_of"] is None
