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
    email = f"{unique('user')}@example.com"
    password = "StrongPass1!"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": password,
            "firstName": "Tenant",
            "lastName": "Reader",
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


def create_project(org_id):
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/projects",
        json={"name": unique("project")},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_role(org_id, project_id):
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/projects/{project_id}/roles",
        json={"key": unique("role"), "displayName": "Private Role"},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_org_role_lookup_not_visible():
    org_a = create_org()
    project_a = create_project(org_a["id"])
    role_a = create_role(org_a["id"], project_a["id"])
    org_b = create_org()
    email_b, password_b = create_user(org_b["id"])
    token_b = login(email_b, password_b, org_b["id"])

    response = requests.get(
        f"{BASE_URL}/organizations/{org_b['id']}/projects/{project_a['id']}/roles/{role_a['id']}",
        headers=headers(token_b),
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code in {403, 404}, response.text
