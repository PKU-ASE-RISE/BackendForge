import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def api_post(path, payload, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


def create_first_user(first_user_response):
    response = first_user_response
    assert response.status_code == 201, response.text
    user = response.json()
    return user, {"X-User-Id": user["id"], "Content-Type": "application/json"}


def tags_by_name(headers):
    response = api_get("/api/tags", headers=headers)
    assert response.status_code == 200, response.text
    return {item["tag"]: item["count"] for item in response.json()}


def test_tag_delete_preserves_hyphenated_prefix_tag(first_user_response):
    _user, headers = create_first_user(first_user_response)
    base = f"tdel{uuid.uuid4().hex[:10]}"
    hyphenated = f"{base}-extra"

    create_response = api_post(
        "/api/memos",
        {
            "content": f"alpha #{hyphenated} beta #{base} gamma",
            "visibility": "PRIVATE",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    memo = create_response.json()
    assert base in memo["tags"]
    assert hyphenated in memo["tags"]
    assert tags_by_name(headers)[hyphenated] == 1

    delete_response = api_delete(f"/api/tags/{base}", headers=headers)
    assert delete_response.status_code == 204, delete_response.text

    fetched_response = api_get(f"/api/memos/{memo['id']}", headers=headers)
    assert fetched_response.status_code == 200, fetched_response.text
    fetched = fetched_response.json()
    assert f"#{hyphenated}" in fetched["content"]
    assert f"#{base} gamma" not in fetched["content"]
    assert hyphenated in fetched["tags"]
    assert base not in fetched["tags"]

    remaining_tags = tags_by_name(headers)
    assert remaining_tags.get(hyphenated) == 1
    assert base not in remaining_tags
