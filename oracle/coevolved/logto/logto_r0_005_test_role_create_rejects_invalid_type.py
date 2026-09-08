import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {"X-Api-Key": "direct-reference-prober", "Content-Type": "application/json"}


def test_role_create_rejects_invalid_type():
    role_name = f"invalid-role-type-{uuid.uuid4().hex}"
    invalid_type = f"InvalidType-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/roles",
        json={"name": role_name, "description": "must not persist", "type": invalid_type},
        headers=HEADERS,
        timeout=30,
    )

    created_role_id = None
    if response.status_code == 201:
        created_role_id = response.json().get("id")
        if created_role_id:
            requests.delete(f"{BASE_URL}/api/roles/{created_role_id}", headers=HEADERS, timeout=30)

    assert response.status_code != 201, response.text

    roles_response = requests.get(
        f"{BASE_URL}/api/roles",
        params={"search": role_name},
        headers=HEADERS,
        timeout=30,
    )
    assert roles_response.status_code == 200
    assert all(role["name"] != role_name for role in roles_response.json())
