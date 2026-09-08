import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
VALID_PAT_EXPIRY = "2099-01-01T00:00:00+00:00"
ADMIN_TOKEN = "system_admin"


def h(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_org():
    name = unique("org")
    r = requests.post(f"{BASE_URL}/organizations", json={"name": name, "domain": f"{name}.example.com"}, headers=h(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


def create_human_user(org_id):
    r = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": f"{unique('user')}@example.com",
            "password": "StrongPass1!",
            "firstName": "Token",
            "lastName": "Owner",
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_pat_scopes_must_be_array():
    org = create_org()
    user = create_human_user(org["id"])
    expires_at = VALID_PAT_EXPIRY

    r = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
        json={"name": unique("pat"), "scopes": "read", "expiresAt": expires_at},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert r.status_code == 400, r.text
