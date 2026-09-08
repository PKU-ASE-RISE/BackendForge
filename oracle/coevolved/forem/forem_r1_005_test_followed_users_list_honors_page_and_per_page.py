import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user_id=None):
    return {
        "X-User-Id": user_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def current_user(user_headers):
    response = requests.get(
        f"{BASE_URL}/users/me",
        headers=user_headers,
        timeout=30,
    )
    assert response.status_code == 200
    return response.json()


def test_followed_users_list_honors_page_and_per_page():
    follower_headers = headers()
    target_one_headers = headers()
    target_two_headers = headers()
    target_one = current_user(target_one_headers)
    target_two = current_user(target_two_headers)

    for target in (target_one, target_two):
        response = requests.post(
            f"{BASE_URL}/follows/users/{target['id']}",
            headers=follower_headers,
            timeout=30,
        )
        assert response.status_code == 201

    page_response = requests.get(
        f"{BASE_URL}/follows/users",
        params={"page": 2, "per_page": 1},
        headers=follower_headers,
        timeout=30,
    )
    assert page_response.status_code == 200
    payload = page_response.json()

    assert payload["meta"]["total"] == 2
    assert payload["meta"]["page"] == 2
    assert payload["meta"]["per_page"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["id"] in {target_one["id"], target_two["id"]}
