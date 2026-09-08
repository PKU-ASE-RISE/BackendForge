import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_invalid_member_role_is_client_error_and_grants_no_access():
    admin_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    admin_headers = _headers(admin_id)
    target_headers = _headers(target_id)

    board_resp = requests.post(
        f"{BASE_URL}/boards",
        json={"title": f"invalid-role-{uuid.uuid4().hex}", "type": "board"},
        headers=admin_headers,
        timeout=30,
    )
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    invalid_role = f"owner-{uuid.uuid4().hex}"
    add_resp = requests.post(
        f"{BASE_URL}/boards/{board_id}/members",
        json={"userId": target_id, "role": invalid_role},
        headers=admin_headers,
        timeout=30,
    )
    assert 400 <= add_resp.status_code < 500

    members_resp = requests.get(
        f"{BASE_URL}/boards/{board_id}/members",
        headers=admin_headers,
        timeout=30,
    )
    assert members_resp.status_code == 200
    assert target_id not in {member["userId"] for member in members_resp.json()}

    target_board_resp = requests.get(
        f"{BASE_URL}/boards/{board_id}",
        headers=target_headers,
        timeout=30,
    )
    assert target_board_resp.status_code == 404
