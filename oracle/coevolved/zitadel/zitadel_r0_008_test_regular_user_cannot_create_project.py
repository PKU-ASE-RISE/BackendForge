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


def create_user(org_id, is_org_owner=False):
    email = f"{unique('user')}@example.com"
    password = "StrongPass1!"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": password,
            "firstName": "Regular",
            "lastName": "User",
            "isOrgOwner": is_org_owner,
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return email, password


def login(email, password, org_id):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password, "orgId": org_id},
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_regular_user_cannot_create_project():
    org = create_org()
    create_user(org["id"], is_org_owner=True)
    email, password = create_user(org["id"], is_org_owner=False)
    token = login(email, password, org["id"])

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/projects",
        json={"name": unique("project")},
        headers=headers(token),
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 403, response.text
