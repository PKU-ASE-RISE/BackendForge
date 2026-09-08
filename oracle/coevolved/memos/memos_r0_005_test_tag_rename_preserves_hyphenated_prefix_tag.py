import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def api_post(path, payload, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def create_first_user(first_user_response):
    response = first_user_response
    assert response.status_code == 201, response.text
    user = response.json()
    return user, {"X-User-Id": user["id"], "Content-Type": "application/json"}


def test_tag_rename_preserves_hyphenated_prefix_tag(first_user_response):
    _user, headers = create_first_user(first_user_response)
    old = f"tren{uuid.uuid4().hex[:10]}"
    new = f"tnew{uuid.uuid4().hex[:10]}"
    hyphenated_old = f"{old}-extra"

    create_response = api_post(
        "/api/memos",
        {
            "content": f"alpha #{hyphenated_old} beta #{old} gamma",
            "visibility": "PRIVATE",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    memo = create_response.json()
    assert old in memo["tags"]
    assert hyphenated_old in memo["tags"]

    rename_response = api_post(
        "/api/tags/rename",
        {"oldName": old, "newName": new},
        headers=headers,
    )
    assert rename_response.status_code == 200, rename_response.text
    assert rename_response.json() == {"oldName": old, "newName": new}

    fetched_response = api_get(f"/api/memos/{memo['id']}", headers=headers)
    assert fetched_response.status_code == 200, fetched_response.text
    fetched = fetched_response.json()
    assert f"#{hyphenated_old}" in fetched["content"]
    assert f"#{new}-extra" not in fetched["content"]
    assert f"#{new} gamma" in fetched["content"]
    assert hyphenated_old in fetched["tags"]
    assert new in fetched["tags"]
    assert old not in fetched["tags"]
    assert f"{new}-extra" not in fetched["tags"]
