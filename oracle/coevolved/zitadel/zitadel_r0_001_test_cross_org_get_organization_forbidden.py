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
            "firstName": "Cross",
            "lastName": "Tenant",
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


def test_cross_org_get_organization_forbidden():
    org_a = create_org()
    org_b = create_org()
    email, password = create_user(org_a["id"])
    token = login(email, password, org_a["id"])

    response = requests.get(f"{BASE_URL}/organizations/{org_b['id']}", headers=headers(token), timeout=REQUEST_TIMEOUT)

    assert response.status_code == 403, response.text
