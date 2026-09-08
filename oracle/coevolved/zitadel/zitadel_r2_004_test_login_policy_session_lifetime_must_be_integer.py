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


def test_login_policy_session_lifetime_must_be_integer():
    org = create_org()

    before = requests.get(
        f"{BASE_URL}/organizations/{org['id']}/policies/login",
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert before.status_code == 200, before.text
    original_lifetime = before.json()["sessionLifetime"]
    assert isinstance(original_lifetime, int)

    response = requests.put(
        f"{BASE_URL}/organizations/{org['id']}/policies/login",
        json={"sessionLifetime": "3600"},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 400, response.text

    after = requests.get(
        f"{BASE_URL}/organizations/{org['id']}/policies/login",
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert after.status_code == 200, after.text
    assert after.json()["sessionLifetime"] == original_lifetime
    assert isinstance(after.json()["sessionLifetime"], int)
