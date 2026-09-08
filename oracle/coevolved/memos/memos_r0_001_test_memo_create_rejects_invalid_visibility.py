import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def api_post(path, payload, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def create_first_user(first_user_response):
    response = first_user_response
    assert response.status_code == 201, response.text
    user = response.json()
    return user, {"X-User-Id": user["id"], "Content-Type": "application/json"}


def test_memo_create_rejects_invalid_visibility(first_user_response):
    _user, headers = create_first_user(first_user_response)
    unique = uuid.uuid4().hex
    content = f"invalid visibility probe {unique}"

    response = api_post(
        "/api/memos",
        {
            "content": content,
            "visibility": "SECRET",
            "pinned": False,
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text

    list_response = api_get(
        "/api/memos",
        params={"search": unique, "limit": 10, "offset": 0},
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed["total"] == 0
    assert listed["memos"] == []
