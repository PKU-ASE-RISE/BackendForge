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


def create_project(org_id):
    name = unique("project")
    r = requests.post(f"{BASE_URL}/organizations/{org_id}/projects", json={"name": name}, headers=h(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


def test_regular_user_cannot_update_project():
    org = create_org()
    create_human_user(org["id"], is_org_owner=True)
    _, email, password = create_human_user(org["id"], is_org_owner=False)
    project = create_project(org["id"])
    token = login(email, password, org["id"])

    r = requests.put(
        f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}",
        json={"name": unique("renamed_project")},
        headers=h(token),
        timeout=REQUEST_TIMEOUT,
    )

    assert r.status_code == 403, r.text
    fresh = requests.get(f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["name"] == project["name"]
