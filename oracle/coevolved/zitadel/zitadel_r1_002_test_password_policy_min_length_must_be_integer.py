import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
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


def test_password_policy_min_length_must_be_integer():
    org = create_org()
    before = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/password", headers=h(), timeout=REQUEST_TIMEOUT)
    assert before.status_code == 200, before.text

    r = requests.put(
        f"{BASE_URL}/organizations/{org['id']}/policies/password",
        json={"minLength": "twelve"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert r.status_code == 400, r.text
    after = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/password", headers=h(), timeout=REQUEST_TIMEOUT)
    assert after.status_code == 200, after.text
    assert after.json()["minLength"] == before.json()["minLength"]
