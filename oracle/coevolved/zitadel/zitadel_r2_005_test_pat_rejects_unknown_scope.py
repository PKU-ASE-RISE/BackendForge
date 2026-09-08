import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
VALID_PAT_EXPIRY = "2099-01-01T00:00:00+00:00"
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


def create_human_user(org_id):
    email = f"{unique('user')}@example.com"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": "StrongPass1!",
            "firstName": "Test",
            "lastName": "User",
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pat_rejects_unknown_scope():
    org = create_org()
    user = create_human_user(org["id"])
    pat_name = unique("pat")
    expires_at = VALID_PAT_EXPIRY

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
        json={"name": pat_name, "scopes": ["superuser"], "expiresAt": expires_at},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 400, response.text

    pats = requests.get(
        f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert pats.status_code == 200, pats.text
    assert all(item["name"] != pat_name for item in pats.json()["items"])
