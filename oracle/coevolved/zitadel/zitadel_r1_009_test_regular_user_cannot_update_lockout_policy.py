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


def create_human_user(org_id, is_org_owner=False):
    email = f"{unique('user')}@example.com"
    password = "StrongPass1!"
    r = requests.post(
        f"{BASE_URL}/organizations/{org_id}/users",
        json={"email": email, "password": password, "firstName": "Test", "lastName": "User", "isOrgOwner": is_org_owner},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert r.status_code == 201, r.text
    return r.json(), email, password


def login(email, password, org_id):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password, "orgId": org_id}, timeout=REQUEST_TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_regular_user_cannot_update_lockout_policy():
    org = create_org()
    create_human_user(org["id"], is_org_owner=True)
    _, email, password = create_human_user(org["id"], is_org_owner=False)
    token = login(email, password, org["id"])
    before = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/lockout", headers=h(), timeout=REQUEST_TIMEOUT)
    assert before.status_code == 200, before.text

    r = requests.put(
        f"{BASE_URL}/organizations/{org['id']}/policies/lockout",
        json={"maxAttempts": 2, "lockoutDuration": 60},
        headers=h(token),
        timeout=REQUEST_TIMEOUT,
    )

    assert r.status_code == 403, r.text
    after = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/lockout", headers=h(), timeout=REQUEST_TIMEOUT)
    assert after.status_code == 200, after.text
    assert after.json()["maxAttempts"] == before.json()["maxAttempts"]
    assert after.json()["lockoutDuration"] == before.json()["lockoutDuration"]
