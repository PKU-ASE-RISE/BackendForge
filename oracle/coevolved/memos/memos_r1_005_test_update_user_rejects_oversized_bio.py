import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def create_host_and_user(first_user_response):
    unique = uuid.uuid4().hex
    host_resp = first_user_response
    assert host_resp.status_code == 201, host_resp.text
    host = host_resp.json()
    host_headers = headers_for(host["id"])

    user_resp = api_post(
        "/api/users",
        {
            "username": f"user_oversized_bio_{unique}",
            "nickname": "Bio Target",
            "bio": "initial bio",
        },
        headers=host_headers,
    )
    assert user_resp.status_code == 201, user_resp.text
    return user_resp.json(), host_headers


def test_update_user_rejects_oversized_bio(first_user_response):
    user, host_headers = create_host_and_user(first_user_response)
    too_long_bio = "x" * 513

    resp = api_patch(
        f"/api/users/{user['id']}",
        {"bio": too_long_bio},
        headers=host_headers,
    )

    assert resp.status_code in (400, 422), (
        f"bio longer than 512 characters must be rejected, got {resp.status_code}: {resp.text}"
    )

    fetched_resp = api_get(f"/api/users/{user['id']}", headers=host_headers)
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()
    assert fetched["bio"] == "initial bio"
    assert fetched["bio"] != too_long_bio
