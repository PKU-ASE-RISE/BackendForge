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
    email = f"{unique('login')}@example.com"
    password = "StrongPass1!"
    response = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={
            "email": email,
            "password": password,
            "firstName": "Login",
            "lastName": "Policy",
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return email, password


def test_login_policy_disallows_username_password_login():
    org = create_org()
    email, password = create_user(org["id"])
    policy_response = requests.put(
        f"{BASE_URL}/organizations/{org['id']}/policies/login",
        json={"allowUsernamePassword": False, "mfaRequired": False},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert policy_response.status_code == 200, policy_response.text
    assert policy_response.json()["allowUsernamePassword"] is False

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password, "orgId": org["id"]},
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 401, response.text
