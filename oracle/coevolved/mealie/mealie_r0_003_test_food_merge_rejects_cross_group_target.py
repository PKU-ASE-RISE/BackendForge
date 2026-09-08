import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

HEADERS_A = {
    "X-Group-Id": "00000000-0000-0000-0000-302000000001",
    "X-User-Id": "00000000-0000-0000-0000-302000000003",
    "X-Household-Id": "00000000-0000-0000-0000-302000000002",
    "Content-Type": "application/json",
}
HEADERS_B = {
    "X-Group-Id": "00000000-0000-0000-0000-302000000011",
    "X-User-Id": "00000000-0000-0000-0000-302000000013",
    "X-Household-Id": "00000000-0000-0000-0000-302000000012",
    "Content-Type": "application/json",
}


def post(path, payload, request_headers):
    return requests.post(
        f"{BASE_URL}{path}", json=payload, headers=request_headers, timeout=30
    )


def put(path, payload, request_headers):
    return requests.put(
        f"{BASE_URL}{path}", json=payload, headers=request_headers, timeout=30
    )


def get(path, request_headers):
    return requests.get(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


def create_food(name, request_headers):
    response = post("/api/foods", {"name": name}, request_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_food_merge_rejects_cross_group_target():
    marker = uuid.uuid4().hex
    source_food = create_food(f"source-food-{marker}", HEADERS_A)
    other_group_target = create_food(f"other-group-target-food-{marker}", HEADERS_B)

    merge_response = put(
        "/api/foods/merge",
        {"fromFood": source_food["id"], "toFood": other_group_target["id"]},
        HEADERS_A,
    )

    assert merge_response.status_code != 200, (
        "Cross-group food merge returned success with another group's target food"
    )
    source_after = get(f"/api/foods/{source_food['id']}", HEADERS_A)
    assert source_after.status_code == 200, "Rejected merge should not delete source food"
    assert source_after.json()["id"] == source_food["id"]
