import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
ADMIN_TOKEN = "system_admin"


def headers(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_org():
    name = unique("org")
    response = requests.post(
        f"{BASE_URL}/organizations",
        json={"name": name, "domain": f"{name}.example.com"},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_user(org_id):
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": f"{unique('pat')}@example.com",
            "password": "StrongPass1!",
            "firstName": "Pat",
            "lastName": "Owner",
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_invalid_pat_expires_at_rejected():
    org = create_org()
    user = create_user(org["id"])

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
        json={"name": unique("pat"), "scopes": ["read"], "expiresAt": "not-a-date"},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 400, response.text
