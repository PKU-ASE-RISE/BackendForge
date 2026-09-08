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
        json=payload or {},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def test_build_complete_rejects_duplicate_bom_aggregate_shortage():
    token = uuid.uuid4().hex
    assembly = api_post("/api/parts", {"name": f"AsmAggShort-{token}", "assembly": True}).json()
    component = api_post("/api/parts", {"name": f"CompAggShort-{token}"}).json()

    first_bom = api_post(
        "/api/bom",
        {"part": assembly["id"], "sub_part": component["id"], "quantity": 4, "reference": "A"},
    )
    assert first_bom.status_code == 201
    second_bom = api_post(
        "/api/bom",
        {"part": assembly["id"], "sub_part": component["id"], "quantity": 4, "reference": "B"},
    )
    assert second_bom.status_code == 201

    stock = api_post("/api/stock", {"part": component["id"], "quantity": 6})
    assert stock.status_code == 201

    build = api_post("/api/builds", {"part": assembly["id"], "quantity": 1}).json()
    assert build["status"] == "pending"

    complete = api_post(f"/api/builds/{build['id']}/complete")
    assert complete.status_code == 400
    assert "error" in complete.json()

    reloaded_build = api_get(f"/api/builds/{build['id']}")
    assert reloaded_build.status_code == 200
    assert reloaded_build.json()["status"] == "pending"

    reloaded_component = api_get(f"/api/parts/{component['id']}")
    assert reloaded_component.status_code == 200
    assert reloaded_component.json()["total_stock"] == 6

    reloaded_assembly = api_get(f"/api/parts/{assembly['id']}")
    assert reloaded_assembly.status_code == 200
    assert reloaded_assembly.json()["total_stock"] == 0
