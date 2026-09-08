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


def create_human_user(org_id, is_org_owner=False):
    email = f"{unique('user')}@example.com"
    password = "StrongPass1!"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": password,
            "firstName": "Test",
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


def test_regular_user_cannot_delete_organization():
    org = create_org()
    create_human_user(org["id"], is_org_owner=True)
    _, member_email, member_password = create_human_user(org["id"], is_org_owner=False)
    member_token = login(member_email, member_password, org["id"])

    delete_response = requests.delete(
        f"{BASE_URL}/organizations/{org['id']}",
        headers=headers(member_token),
        timeout=REQUEST_TIMEOUT,
    )
    assert delete_response.status_code == 403, delete_response.text

    reload_response = requests.get(
        f"{BASE_URL}/organizations/{org['id']}",
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert reload_response.status_code == 200, reload_response.text
    assert reload_response.json()["id"] == org["id"]
