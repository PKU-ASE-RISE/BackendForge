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


def create_host(first_user_response):
    resp = first_user_response
    assert resp.status_code == 201, resp.text
    host = resp.json()
    return host, headers_for(host["id"])


def test_create_resource_rejects_invalid_memo_id_format(first_user_response):
    _, host_headers = create_host(first_user_response)
    filename = f"invalid_memo_link_{uuid.uuid4().hex}.png"

    resp = api_post(
        "/api/resources",
        {
            "filename": filename,
            "type": "image/png",
            "size": 64,
            "memoId": "not-a-uuid",
        },
        headers=host_headers,
    )

    assert resp.status_code in (400, 422), (
        f"non-UUID memoId must be rejected as a bad request, got {resp.status_code}: {resp.text}"
    )

    resources_resp = api_get("/api/resources", headers=host_headers)
    assert resources_resp.status_code == 200, resources_resp.text
    assert filename not in [resource["filename"] for resource in resources_resp.json()]
