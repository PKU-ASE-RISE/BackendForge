import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

HEADERS_A = {
    "X-Group-Id": "00000000-0000-0000-0000-303000000001",
    "X-User-Id": "00000000-0000-0000-0000-303000000003",
    "X-Household-Id": "00000000-0000-0000-0000-303000000002",
    "Content-Type": "application/json",
}
HEADERS_B = {
    "X-Group-Id": "00000000-0000-0000-0000-303000000011",
    "X-User-Id": "00000000-0000-0000-0000-303000000013",
    "X-Household-Id": "00000000-0000-0000-0000-303000000012",
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


def create_unit(name, request_headers):
    response = post(
        "/api/units", {"name": name, "abbreviation": name[:3]}, request_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_unit_merge_rejects_cross_group_target():
    marker = uuid.uuid4().hex
    source_unit = create_unit(f"source-unit-{marker}", HEADERS_A)
    other_group_target = create_unit(f"target-unit-{marker}", HEADERS_B)

    merge_response = put(
        "/api/units/merge",
        {"fromUnit": source_unit["id"], "toUnit": other_group_target["id"]},
        HEADERS_A,
    )

    assert merge_response.status_code != 200, (
        "Cross-group unit merge returned success with another group's target unit"
    )
    source_after = get(f"/api/units/{source_unit['id']}", HEADERS_A)
    assert source_after.status_code == 200, "Rejected merge should not delete source unit"
    assert source_after.json()["id"] == source_unit["id"]
