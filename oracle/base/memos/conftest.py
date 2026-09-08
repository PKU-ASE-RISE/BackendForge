"""
Shared fixtures for Memos integration and workflow tests.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
UNIQUE = uuid.uuid4().hex[:8]


def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


@pytest.fixture(scope="session")
def base_users():
    """
    Create HOST + 2 regular users once per session.
    All test files share this fixture via conftest.
    """
    # Create HOST (first user — no auth header needed)
    resp = api_post("/api/users", {
        "username": f"host_{UNIQUE}",
        "nickname": "Session Host",
        "bio": "Host user for all tests"
    }, headers={"Content-Type": "application/json"})
    assert resp.status_code == 201, f"Failed to create HOST: {resp.status_code} {resp.text}"
    host = resp.json()
    host_headers = headers_for(host["id"])

    # Create regular user A
    resp = api_post("/api/users", {
        "username": f"usera_{UNIQUE}",
        "nickname": "User A",
        "bio": "Regular user A"
    }, headers=host_headers)
    assert resp.status_code == 201, f"Failed to create user A: {resp.text}"
    user_a = resp.json()

    # Create regular user B
    resp = api_post("/api/users", {
        "username": f"userb_{UNIQUE}",
        "nickname": "User B",
        "bio": "Regular user B"
    }, headers=host_headers)
    assert resp.status_code == 201, f"Failed to create user B: {resp.text}"
    user_b = resp.json()

    return {
        "host": host,
        "host_headers": host_headers,
        "user_a": user_a,
        "user_a_headers": headers_for(user_a["id"]),
        "user_b": user_b,
        "user_b_headers": headers_for(user_b["id"]),
    }
