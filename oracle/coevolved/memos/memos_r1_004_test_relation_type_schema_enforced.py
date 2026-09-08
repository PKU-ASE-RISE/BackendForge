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


def create_memo(headers, content):
    resp = api_post(
        "/api/memos",
        {"content": content, "visibility": "PRIVATE"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_relation_type_schema_enforced(first_user_response):
    _, host_headers = create_host(first_user_response)
    unique = uuid.uuid4().hex
    source = create_memo(host_headers, f"relation source {unique}")
    target = create_memo(host_headers, f"relation target {unique}")

    missing_type_resp = api_post(
        f"/api/memos/{source['id']}/relations",
        {"relatedMemoId": target["id"]},
        headers=host_headers,
    )
    assert missing_type_resp.status_code in (400, 422), (
        f"missing required relation type must be rejected, got "
        f"{missing_type_resp.status_code}: {missing_type_resp.text}"
    )

    invalid_type_resp = api_post(
        f"/api/memos/{source['id']}/relations",
        {"relatedMemoId": target["id"], "type": "NOT_REFERENCE"},
        headers=host_headers,
    )
    assert invalid_type_resp.status_code in (400, 422), (
        f"relation type outside the OpenAPI enum must be rejected, got "
        f"{invalid_type_resp.status_code}: {invalid_type_resp.text}"
    )

    relations_resp = api_get(f"/api/memos/{source['id']}/relations", headers=host_headers)
    assert relations_resp.status_code == 200, relations_resp.text
    assert not [
        rel
        for rel in relations_resp.json()
        if rel["memoId"] == source["id"] and rel["relatedMemoId"] == target["id"]
    ]
