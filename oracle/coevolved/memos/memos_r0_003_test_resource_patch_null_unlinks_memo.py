import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def api_post(path, payload, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_patch(path, payload, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def create_first_user(first_user_response):
    response = first_user_response
    assert response.status_code == 201, response.text
    user = response.json()
    return user, {"X-User-Id": user["id"], "Content-Type": "application/json"}


def test_resource_patch_null_unlinks_memo(first_user_response):
    user, headers = create_first_user(first_user_response)
    unique = uuid.uuid4().hex

    memo_response = api_post(
        "/api/memos",
        {
            "content": f"resource unlink target {unique}",
            "visibility": "PRIVATE",
        },
        headers=headers,
    )
    assert memo_response.status_code == 201, memo_response.text
    memo = memo_response.json()
    assert memo["creatorId"] == user["id"]

    resource_response = api_post(
        "/api/resources",
        {
            "filename": f"unlink-{unique}.png",
            "type": "image/png",
            "size": 128,
            "memoId": memo["id"],
        },
        headers=headers,
    )
    assert resource_response.status_code == 201, resource_response.text
    resource = resource_response.json()
    assert resource["memoId"] == memo["id"]

    patch_response = api_patch(
        f"/api/resources/{resource['id']}",
        {"memoId": None},
        headers=headers,
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["id"] == resource["id"]
    assert patched["memoId"] is None

    fetched_response = api_get(f"/api/resources/{resource['id']}", headers=headers)
    assert fetched_response.status_code == 200, fetched_response.text
    fetched = fetched_response.json()
    assert fetched["creatorId"] == user["id"]
    assert fetched["memoId"] is None
