import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def create_host(first_user_response):
    resp = first_user_response
    assert resp.status_code == 201, resp.text
    host = resp.json()
    return host, headers_for(host["id"])


def test_memo_list_rejects_invalid_query_values(first_user_response):
    _, host_headers = create_host(first_user_response)
    marker = f"invalid-query-{uuid.uuid4().hex}"
    create_resp = api_post(
        "/api/memos",
        {"content": marker, "visibility": "PUBLIC", "pinned": False},
        headers=host_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    invalid_visibility_resp = api_get(
        "/api/memos",
        params={"visibility": "SECRET", "search": marker},
        headers=host_headers,
    )
    assert invalid_visibility_resp.status_code in (400, 422), (
        f"visibility outside the OpenAPI enum must be rejected, got "
        f"{invalid_visibility_resp.status_code}: {invalid_visibility_resp.text}"
    )

    invalid_pinned_resp = api_get(
        "/api/memos",
        params={"pinned": "definitely-not-a-boolean", "search": marker},
        headers=host_headers,
    )
    assert invalid_pinned_resp.status_code in (400, 422), (
        f"invalid boolean pinned value must be rejected, got "
        f"{invalid_pinned_resp.status_code}: {invalid_pinned_resp.text}"
    )
