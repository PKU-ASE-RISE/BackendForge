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


def test_first_created_user_defaults_to_org_owner():
    org = create_org()
    email = f"{unique('first')}@example.com"

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/users",
        json={
            "email": email,
            "password": "StrongPass1!",
            "firstName": "First",
            "lastName": "Owner",
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 201, response.text
    user = response.json()
    assert user.get("isOrgOwner") is True
