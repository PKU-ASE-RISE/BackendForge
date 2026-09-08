"""
L2 Integration Tests for Zitadel IAM API.
Targets: camelCase, status codes, role enforcement, computed values.
"""
import os
import uuid

import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
ADMIN_TOKEN = "system_admin"

def h(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex}"

def create_org(name=None):
    name = name or unique("org")
    r = requests.post(f"{BASE_URL}/organizations", json={"name": name, "domain": f"{name}.io"}, headers=h(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201
    return r.json()

def create_human_user(org_id, email=None, password="StrongPass1!", first_name="John", last_name="Doe"):
    email = email or f"{unique('u')}@test.com"
    r = requests.post(f"{BASE_URL}/organizations/{org_id}/users", json={
        "email": email, "password": password, "firstName": first_name, "lastName": last_name
    }, headers=h(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201
    return r.json(), email, password

def login(email, password, org_id):
    return requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password, "orgId": org_id}, timeout=REQUEST_TIMEOUT)


class TestOrgFieldCasing:
    def test_org_response_camelcase(self):
        org = create_org()
        assert "id" in org
        assert "name" in org
        assert "domain" in org
        assert "createdAt" in org
        assert "created_at" not in org

class TestUserFieldCasing:
    def test_human_user_response(self):
        org = create_org()
        user, _, _ = create_human_user(org["id"])
        assert "id" in user
        assert "email" in user
        assert "firstName" in user
        assert "lastName" in user
        assert "createdAt" in user
        assert "state" in user
        assert "first_name" not in user

class TestAuthentication:
    def test_login_returns_token(self):
        org = create_org()
        user, email, pw = create_human_user(org["id"])
        r = login(email, pw, org["id"])
        assert r.status_code == 200
        data = r.json()
        assert "token" in data

    def test_login_wrong_password_fails(self):
        org = create_org()
        _, email, _ = create_human_user(org["id"])
        r = login(email, "wrong", org["id"])
        assert r.status_code == 401

    def test_missing_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/organizations", timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401

class TestLockout:
    def test_lockout_after_max_attempts(self):
        org = create_org()
        _, email, _ = create_human_user(org["id"])
        for _ in range(5):
            login(email, "wrong", org["id"])
        r = login(email, "StrongPass1!", org["id"])
        assert r.status_code == 423

class TestStatusCodes:
    def test_create_org_returns_201(self):
        r = requests.post(f"{BASE_URL}/organizations", json={"name": unique("o"), "domain": f"{unique('d')}.com"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 201

    def test_delete_org_returns_204(self):
        org = create_org()
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204

    def test_get_nonexistent_org_returns_404(self):
        r = requests.get(f"{BASE_URL}/organizations/{uuid.uuid4().hex}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 404

class TestProjects:
    def test_create_project_returns_fields(self):
        org = create_org()
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/projects",
                          json={"name": unique("proj")}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 201
        p = r.json()
        assert "id" in p
        assert "name" in p
        assert "createdAt" in p

class TestRolesAndGrants:
    def test_create_role_and_grant(self):
        org = create_org()
        proj = requests.post(f"{BASE_URL}/organizations/{org['id']}/projects",
                             json={"name": unique("p")}, headers=h(), timeout=REQUEST_TIMEOUT).json()
        role = requests.post(f"{BASE_URL}/organizations/{org['id']}/projects/{proj['id']}/roles",
                             json={"key": unique("r"), "displayName": "Test Role"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert role.status_code == 201
        role_data = role.json()
        assert "key" in role_data
        assert "displayName" in role_data

        user, _, _ = create_human_user(org["id"])
        grant = requests.post(f"{BASE_URL}/organizations/{org['id']}/grants", json={
            "userId": user["id"], "projectId": proj["id"], "roleKeys": [role_data["key"]]
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert grant.status_code == 201
        assert "id" in grant.json()

class TestOrgIsolation:
    def test_user_in_org_a_not_visible_in_org_b(self):
        org_a = create_org()
        org_b = create_org()
        user_a, _, _ = create_human_user(org_a["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org_b['id']}/users/{user_a['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 404

class TestSessionManagement:
    def test_login_creates_session(self):
        org = create_org()
        user, email, pw = create_human_user(org["id"])
        r = login(email, pw, org["id"])
        token = r.json()["token"]
        r = requests.get(f"{BASE_URL}/sessions", headers={"Authorization": f"Bearer {token}"}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        sessions = r.json()["items"]
        assert len(sessions) >= 1

class TestPasswordPolicy:
    def test_weak_password_rejected(self):
        org = create_org()
        requests.put(f"{BASE_URL}/organizations/{org['id']}/policies/password",
                     json={"minLength": 12, "requireUppercase": True, "requireNumber": True},
                     headers=h(), timeout=REQUEST_TIMEOUT)
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users", json={
            "email": f"{unique('w')}@t.com", "password": "short", "firstName": "A", "lastName": "B"
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 400

class TestAuditLog:
    def test_user_creation_logged(self):
        org = create_org()
        create_human_user(org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/events", headers=h(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        events = r.json()["items"]
        assert any(e["eventType"] == "user.created" for e in events)
