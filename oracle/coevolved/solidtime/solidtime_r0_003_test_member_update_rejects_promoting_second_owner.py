import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_member_update_rejects_promoting_second_owner():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    create_response = requests.post(
        f"{BASE_URL}/api/v1/members",
        headers=headers,
        json={
            "user_id": str(uuid.uuid4()),
            "role": "member",
        },
        timeout=30,
    )
    assert create_response.status_code == 201
    member = create_response.json()

    update_response = requests.put(
        f"{BASE_URL}/api/v1/members/{member['id']}",
        headers=headers,
        json={"role": "owner"},
        timeout=30,
    )

    assert update_response.status_code == 422
    after_members = requests.get(f"{BASE_URL}/api/v1/members", headers=headers, timeout=30).json()
    reloaded_member = [item for item in after_members if item["id"] == member["id"]][0]
    assert reloaded_member["role"] == "member"
    assert sum(1 for item in after_members if item["role"] == "owner") == 1
