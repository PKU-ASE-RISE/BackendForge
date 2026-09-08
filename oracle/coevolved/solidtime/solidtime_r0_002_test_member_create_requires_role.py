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


def test_member_create_requires_role():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    new_user_id = str(uuid.uuid4())

    response = requests.post(
        f"{BASE_URL}/api/v1/members",
        headers=headers,
        json={"user_id": new_user_id},
        timeout=30,
    )

    assert response.status_code == 422
    members = requests.get(f"{BASE_URL}/api/v1/members", headers=headers, timeout=30).json()
    assert new_user_id not in {member["user_id"] for member in members}
