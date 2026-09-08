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


def create_user(org_id, first_name, is_org_owner=False):
    email = f"{unique(first_name.lower())}@example.com"
    password = "StrongPass1!"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": password,
            "firstName": first_name,
            "lastName": "User",
            "isOrgOwner": is_org_owner,
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json(), email, password


def login(email, password, org_id):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password, "orgId": org_id},
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_regular_user_cannot_create_pat_for_other_user():
    org = create_org()
    create_user(org["id"], "Owner", is_org_owner=True)
    actor, actor_email, actor_password = create_user(org["id"], "Actor")
    target, _, _ = create_user(org["id"], "Target")
    token = login(actor_email, actor_password, org["id"])
    expires_at = VALID_PAT_EXPIRY

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/users/{target['id']}/pats",
        json={"name": unique("pat"), "scopes": ["read"], "expiresAt": expires_at},
        headers=headers(token),
        timeout=REQUEST_TIMEOUT,
    )

    assert actor["id"] != target["id"]
    assert response.status_code == 403, response.text
