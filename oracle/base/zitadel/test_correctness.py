"""
Correctness tests for Zitadel IAM API.
"""

import os
import uuid
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
VALID_PAT_EXPIRY = "2099-01-01T00:00:00+00:00"
EXPIRED_PAT_EXPIRY = "2000-01-01T00:00:00+00:00"
ADMIN_TOKEN = "system_admin"


def headers(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def unique(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex}"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def create_org(name=None, domain=None):
    name = name or unique("org")
    domain = domain or f"{name}.example.com"
    r = requests.post(f"{BASE_URL}/organizations", json={"name": name, "domain": domain}, headers=headers(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


def create_human_user(org_id, email=None, password="StrongPass1!", first_name="John", last_name="Doe", is_org_owner=False):
    email = email or f"{unique('user')}@example.com"
    payload = {
        "email": email,
        "password": password,
        "firstName": first_name,
        "lastName": last_name,
        "isOrgOwner": is_org_owner,
    }
    r = requests.post(f"{BASE_URL}/organizations/{org_id}/users", json=payload, headers=headers(), timeout=REQUEST_TIMEOUT)
    return r


def create_machine_user(org_id, name=None):
    name = name or unique("machine")
    payload = {"name": name, "description": "A machine user", "type": "machine"}
    r = requests.post(f"{BASE_URL}/organizations/{org_id}/users", json=payload, headers=headers(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


def login(email, password, org_id):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password, "orgId": org_id}, timeout=REQUEST_TIMEOUT)
    return r


def create_project(org_id, name=None):
    name = name or unique("project")
    r = requests.post(f"{BASE_URL}/organizations/{org_id}/projects", json={"name": name}, headers=headers(), timeout=REQUEST_TIMEOUT)
    assert r.status_code == 201, r.text
    return r.json()


def create_role(org_id, project_id, key=None, display_name=None):
    key = key or unique("role")
    display_name = display_name or f"Role {key}"
    r = requests.post(
        f"{BASE_URL}/organizations/{org_id}/projects/{project_id}/roles",
        json={"key": key, "displayName": display_name},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert r.status_code == 201, r.text
    return r.json()


def create_grant(org_id, user_id, project_id, role_keys):
    r = requests.post(
        f"{BASE_URL}/organizations/{org_id}/grants",
        json={"userId": user_id, "projectId": project_id, "roleKeys": role_keys},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert r.status_code == 201, r.text
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Organization Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestOrganizations:
    def test_create_organization(self):
        org = create_org()
        assert "id" in org
        assert org["name"].startswith("org_") or "name" in org
        assert "domain" in org
        assert "createdAt" in org

    def test_list_organizations(self):
        create_org()
        r = requests.get(f"{BASE_URL}/organizations", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "totalCount" in data
        assert data["totalCount"] >= 1

    def test_get_organization(self):
        org = create_org()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == org["id"]

    def test_update_organization(self):
        org = create_org()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}",
            json={"name": "Updated Name"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_delete_organization(self):
        org = create_org()
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 404

    def test_create_organization_missing_fields(self):
        r = requests.post(f"{BASE_URL}/organizations", json={"name": ""}, headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 400

    def test_get_nonexistent_organization(self):
        fake_id = str(uuid.uuid4())
        r = requests.get(f"{BASE_URL}/organizations/{fake_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 404

    def test_unauthorized_access(self):
        r = requests.get(f"{BASE_URL}/organizations", timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401

    def test_invalid_token(self):
        r = requests.get(f"{BASE_URL}/organizations", headers=headers("invalid_token_xyz"), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# User Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestUsers:
    def test_create_human_user(self):
        org = create_org()
        r = create_human_user(org["id"])
        assert r.status_code == 201
        user = r.json()
        assert user["type"] == "human"
        assert user["state"] == "active"
        assert "id" in user
        assert user["orgId"] == org["id"]

    def test_create_machine_user(self):
        org = create_org()
        user = create_machine_user(org["id"])
        assert user["type"] == "machine"
        assert user["state"] == "active"

    def test_list_users(self):
        org = create_org()
        create_human_user(org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["totalCount"] >= 1

    def test_get_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == user["id"]

    def test_update_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}",
            json={"firstName": "Jane", "lastName": "Smith"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["firstName"] == "Jane"
        assert data["lastName"] == "Smith"

    def test_delete_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204

    def test_deactivate_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/deactivate", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["state"] == "inactive"

    def test_reactivate_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/deactivate", headers=headers(), timeout=REQUEST_TIMEOUT)
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/reactivate", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["state"] == "active"

    def test_lock_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/lock", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["state"] == "locked"

    def test_unlock_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/lock", headers=headers(), timeout=REQUEST_TIMEOUT)
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/unlock", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["state"] == "active"

    def test_create_user_weak_password(self):
        """Password must meet default policy (min 8 chars)."""
        org = create_org()
        r = create_human_user(org["id"], password="short")
        assert r.status_code == 400
        assert "error" in r.json()

    def test_user_not_found(self):
        org = create_org()
        fake_id = str(uuid.uuid4())
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users/{fake_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Authentication Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAuthentication:
    def test_login_success(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["userId"] is not None
        assert data["orgId"] == org["id"]

    def test_login_wrong_password(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        r = login(email, "WrongPassword!", org["id"])
        assert r.status_code == 401

    def test_login_nonexistent_user(self):
        org = create_org()
        r = login("nonexistent@example.com", "whatever", org["id"])
        assert r.status_code == 401

    def test_login_locked_user(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        user_r = create_human_user(org["id"], email=email, password="ValidPass1!")
        user = user_r.json()
        # Lock the user
        requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/lock", headers=headers(), timeout=REQUEST_TIMEOUT)
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 423

    def test_token_validation(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        r = requests.post(f"{BASE_URL}/auth/token/validate", json={"token": token}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["userId"] is not None
        assert data["orgId"] == org["id"]

    def test_token_validation_invalid(self):
        r = requests.post(f"{BASE_URL}/auth/token/validate", json={"token": "invalid_garbage_token"}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False

    def test_password_change(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        r = requests.post(
            f"{BASE_URL}/auth/password/change",
            json={"currentPassword": "ValidPass1!", "newPassword": "NewValid2!"},
            headers=headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        # Login with new password
        r2 = login(email, "NewValid2!", org["id"])
        assert r2.status_code == 200

    def test_password_change_wrong_current(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        r = requests.post(
            f"{BASE_URL}/auth/password/change",
            json={"currentPassword": "WrongCurrent!", "newPassword": "NewValid2!"},
            headers=headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 401

    def test_password_change_weak_new_password(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        r = requests.post(
            f"{BASE_URL}/auth/password/change",
            json={"currentPassword": "ValidPass1!", "newPassword": "short"},
            headers=headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 400

    def test_use_session_token_for_api(self):
        """A session token from login can be used to access the API."""
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!", is_org_owner=True)
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        # User can list users in their org
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Session Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSessions:
    def test_list_sessions(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        r = requests.get(f"{BASE_URL}/sessions", headers=headers(token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["totalCount"] >= 1

    def test_revoke_session(self):
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        # Get sessions
        sessions_r = requests.get(f"{BASE_URL}/sessions", headers=headers(token), timeout=REQUEST_TIMEOUT)
        sessions = sessions_r.json()["items"]
        assert len(sessions) >= 1
        session_id = sessions[0]["id"]
        # Revoke
        r = requests.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers(token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204

    def test_revoked_session_token_invalid(self):
        """After revoking, the token should not validate."""
        org = create_org()
        email = f"{unique('login')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login_r = login(email, "ValidPass1!", org["id"])
        token = login_r.json()["token"]
        sessions_r = requests.get(f"{BASE_URL}/sessions", headers=headers(token), timeout=REQUEST_TIMEOUT)
        sessions = sessions_r.json()["items"]
        session_id = sessions[0]["id"]
        requests.delete(f"{BASE_URL}/sessions/{session_id}", headers=headers(token), timeout=REQUEST_TIMEOUT)
        # Token should now be invalid
        r = requests.post(f"{BASE_URL}/auth/token/validate", json={"token": token}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["valid"] is False


# ──────────────────────────────────────────────────────────────────────────────
# Project Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProjects:
    def test_create_project(self):
        org = create_org()
        project = create_project(org["id"])
        assert "id" in project
        assert project["orgId"] == org["id"]
        assert project["state"] == "active"

    def test_list_projects(self):
        org = create_org()
        create_project(org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/projects", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 1

    def test_get_project(self):
        org = create_org()
        project = create_project(org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == project["id"]

    def test_update_project(self):
        org = create_org()
        project = create_project(org["id"])
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}",
            json={"name": "Updated Project"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Project"

    def test_delete_project(self):
        org = create_org()
        project = create_project(org["id"])
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204


# ──────────────────────────────────────────────────────────────────────────────
# Role Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRoles:
    def test_create_role(self):
        org = create_org()
        project = create_project(org["id"])
        role = create_role(org["id"], project["id"], key="admin", display_name="Administrator")
        assert role["key"] == "admin"
        assert role["displayName"] == "Administrator"
        assert role["projectId"] == project["id"]

    def test_list_roles(self):
        org = create_org()
        project = create_project(org["id"])
        create_role(org["id"], project["id"])
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}/roles",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 1

    def test_get_role(self):
        org = create_org()
        project = create_project(org["id"])
        role = create_role(org["id"], project["id"])
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}/roles/{role['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["id"] == role["id"]

    def test_delete_role(self):
        org = create_org()
        project = create_project(org["id"])
        role = create_role(org["id"], project["id"])
        r = requests.delete(
            f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}/roles/{role['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 204

    def test_duplicate_role_key(self):
        org = create_org()
        project = create_project(org["id"])
        create_role(org["id"], project["id"], key="viewer")
        r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/projects/{project['id']}/roles",
            json={"key": "viewer", "displayName": "Viewer 2"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# Grant Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestGrants:
    def test_create_grant(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        project = create_project(org["id"])
        role = create_role(org["id"], project["id"], key="editor")
        grant = create_grant(org["id"], user["id"], project["id"], ["editor"])
        assert grant["userId"] == user["id"]
        assert grant["projectId"] == project["id"]
        assert "editor" in grant["roleKeys"]

    def test_list_grants(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        project = create_project(org["id"])
        create_role(org["id"], project["id"], key="admin")
        create_grant(org["id"], user["id"], project["id"], ["admin"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/grants", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 1

    def test_list_grants_filter_by_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        project = create_project(org["id"])
        create_role(org["id"], project["id"], key="viewer")
        create_grant(org["id"], user["id"], project["id"], ["viewer"])
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/grants?userId={user['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["totalCount"] >= 1
        for g in data["items"]:
            assert g["userId"] == user["id"]

    def test_get_grant(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        project = create_project(org["id"])
        create_role(org["id"], project["id"], key="admin")
        grant = create_grant(org["id"], user["id"], project["id"], ["admin"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/grants/{grant['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == grant["id"]

    def test_revoke_grant(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        project = create_project(org["id"])
        create_role(org["id"], project["id"], key="admin")
        grant = create_grant(org["id"], user["id"], project["id"], ["admin"])
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}/grants/{grant['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204


# ──────────────────────────────────────────────────────────────────────────────
# Policy Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPolicies:
    def test_get_password_policy_defaults(self):
        org = create_org()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/password", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["minLength"] == 8
        assert data["orgId"] == org["id"]

    def test_update_password_policy(self):
        org = create_org()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/password",
            json={"minLength": 12, "requireUppercase": True, "requireSymbol": True},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["minLength"] == 12
        assert data["requireUppercase"] is True
        assert data["requireSymbol"] is True

    def test_password_policy_enforcement(self):
        """After setting strict policy, creating user with weak password should fail."""
        org = create_org()
        requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/password",
            json={"minLength": 12, "requireUppercase": True, "requireNumber": True, "requireSymbol": True},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        # Try to create user with weak password
        r = create_human_user(org["id"], password="short")
        assert r.status_code == 400
        # Try with password that doesn't have uppercase
        r = create_human_user(org["id"], password="nouppercase123!")
        assert r.status_code == 400
        # Valid password that meets all requirements
        r = create_human_user(org["id"], password="StrongPass123!!")
        assert r.status_code == 201

    def test_get_login_policy_defaults(self):
        org = create_org()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/login", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["mfaRequired"] is False
        assert data["allowUsernamePassword"] is True

    def test_update_login_policy(self):
        org = create_org()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/login",
            json={"mfaRequired": True, "sessionLifetime": 7200},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mfaRequired"] is True
        assert data["sessionLifetime"] == 7200

    def test_get_lockout_policy_defaults(self):
        org = create_org()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/policies/lockout", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["maxAttempts"] == 5

    def test_update_lockout_policy(self):
        org = create_org()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/lockout",
            json={"maxAttempts": 3},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["maxAttempts"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# Lockout Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestLockout:
    def test_lockout_after_max_attempts(self):
        """User gets locked after exceeding max login attempts."""
        org = create_org()
        # Set lockout to 3 attempts
        requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/lockout",
            json={"maxAttempts": 3},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        email = f"{unique('lock')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")

        # Fail 3 times
        for _ in range(3):
            r = login(email, "WrongPassword!", org["id"])
            assert r.status_code == 401

        # Now user should be locked
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 423

    def test_admin_unlock_after_lockout(self):
        """Admin can unlock a locked user."""
        org = create_org()
        requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/lockout",
            json={"maxAttempts": 2},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        email = f"{unique('lock')}@example.com"
        user_r = create_human_user(org["id"], email=email, password="ValidPass1!")
        user = user_r.json()

        # Fail 2 times to trigger lock
        for _ in range(2):
            login(email, "Wrong!", org["id"])

        # Verify locked
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 423

        # Admin unlocks
        r = requests.post(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/unlock", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200

        # Can login again
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# MFA Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMFA:
    def test_mfa_required_flow(self):
        """When MFA is required, login returns mfaRequired and mfaToken."""
        org = create_org()
        # Enable MFA
        requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/login",
            json={"mfaRequired": True},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        email = f"{unique('mfa')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")

        # First login
        r = login(email, "ValidPass1!", org["id"])
        assert r.status_code == 200
        data = r.json()
        assert data["mfaRequired"] is True
        assert "mfaToken" in data
        assert "token" not in data or data.get("token") is None

    def test_mfa_complete_login(self):
        """Complete MFA with code gives full session token."""
        org = create_org()
        requests.put(
            f"{BASE_URL}/organizations/{org['id']}/policies/login",
            json={"mfaRequired": True},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        email = f"{unique('mfa')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")

        login_r = login(email, "ValidPass1!", org["id"])
        mfa_token = login_r.json()["mfaToken"]

        # Complete MFA (any 6-digit code is accepted)
        r = requests.post(f"{BASE_URL}/auth/login/mfa", json={"mfaToken": mfa_token, "code": "123456"}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["token"] is not None

    def test_mfa_invalid_token(self):
        r = requests.post(f"{BASE_URL}/auth/login/mfa", json={"mfaToken": "invalid", "code": "123456"}, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Organization Isolation Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestOrganizationIsolation:
    def test_user_cannot_see_other_org_users(self):
        """A user logged into org A cannot access org B users."""
        org_a = create_org()
        org_b = create_org()
        email_a = f"{unique('iso')}@example.com"
        create_human_user(org_a["id"], email=email_a, password="ValidPass1!", is_org_owner=True)
        create_human_user(org_b["id"])

        # Login as org A user
        token_a = login(email_a, "ValidPass1!", org_a["id"]).json()["token"]

        # Try to access org B users
        r = requests.get(f"{BASE_URL}/organizations/{org_b['id']}/users", headers=headers(token_a), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 403

    def test_user_can_see_own_org_users(self):
        """A user logged into org A can access org A users."""
        org = create_org()
        email = f"{unique('iso')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!", is_org_owner=True)
        create_human_user(org["id"])

        token = login(email, "ValidPass1!", org["id"]).json()["token"]
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 2


# ──────────────────────────────────────────────────────────────────────────────
# Actions Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestActions:
    def test_create_action(self):
        org = create_org()
        r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/actions",
            json={
                "name": "Log Login",
                "eventType": "post.login",
                "script": "console.log('user logged in');",
            },
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Log Login"
        assert data["eventType"] == "post.login"
        assert data["enabled"] is True

    def test_list_actions(self):
        org = create_org()
        requests.post(
            f"{BASE_URL}/organizations/{org['id']}/actions",
            json={"name": "Hook1", "eventType": "pre.login", "script": "x"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/actions", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 1

    def test_get_action(self):
        org = create_org()
        create_r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/actions",
            json={"name": "Hook2", "eventType": "post.registration", "script": "y"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        action = create_r.json()
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/actions/{action['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["id"] == action["id"]

    def test_update_action(self):
        org = create_org()
        create_r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/actions",
            json={"name": "Hook3", "eventType": "pre.registration", "script": "z"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        action = create_r.json()
        r = requests.put(
            f"{BASE_URL}/organizations/{org['id']}/actions/{action['id']}",
            json={"enabled": False, "script": "updated_script();"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["script"] == "updated_script();"

    def test_delete_action(self):
        org = create_org()
        create_r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/actions",
            json={"name": "Hook4", "eventType": "post.login", "script": "w"},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        action = create_r.json()
        r = requests.delete(f"{BASE_URL}/organizations/{org['id']}/actions/{action['id']}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 204


# ──────────────────────────────────────────────────────────────────────────────
# Personal Access Token Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPAT:
    def test_create_pat(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        expires = VALID_PAT_EXPIRY
        r = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "My Token", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 201
        data = r.json()
        assert "token" in data
        assert data["name"] == "My Token"
        assert data["userId"] == user["id"]

    def test_list_pats(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        expires = VALID_PAT_EXPIRY
        requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "Token1", "scopes": ["read"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 1

    def test_get_pat(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        expires = VALID_PAT_EXPIRY
        pat = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "Token2", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats/{pat['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert r.json()["id"] == pat["id"]

    def test_revoke_pat(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        expires = VALID_PAT_EXPIRY
        pat = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "Token3", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()
        r = requests.delete(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats/{pat['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 204

    def test_use_pat_for_authentication(self):
        """PAT can be used as Bearer token for API access."""
        org = create_org()
        user = create_human_user(org["id"], is_org_owner=True).json()
        expires = VALID_PAT_EXPIRY
        pat = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "API Token", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()
        pat_token = pat["token"]
        # Use PAT to access API
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(pat_token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200

    def test_expired_pat_rejected(self):
        """An expired PAT should return 401."""
        org = create_org()
        user = create_human_user(org["id"], is_org_owner=True).json()
        # Create PAT that's already expired
        expires = EXPIRED_PAT_EXPIRY
        pat = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "Expired Token", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()
        pat_token = pat["token"]
        # Try to use expired PAT
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(pat_token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401

    def test_revoked_pat_rejected(self):
        """A revoked PAT should return 401."""
        org = create_org()
        user = create_human_user(org["id"], is_org_owner=True).json()
        expires = VALID_PAT_EXPIRY
        pat = requests.post(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats",
            json={"name": "Revokable", "scopes": ["admin"], "expiresAt": expires},
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()
        pat_token = pat["token"]
        # Revoke the PAT
        requests.delete(
            f"{BASE_URL}/organizations/{org['id']}/users/{user['id']}/pats/{pat['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        # Try to use revoked PAT
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/users", headers=headers(pat_token), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Audit Events Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditEvents:
    def test_user_created_event(self):
        org = create_org()
        create_human_user(org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/events", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        events = r.json()["items"]
        event_types = [e["eventType"] for e in events]
        assert "user.created" in event_types

    def test_login_success_event(self):
        org = create_org()
        email = f"{unique('audit')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login(email, "ValidPass1!", org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/events", headers=headers(), timeout=REQUEST_TIMEOUT)
        events = r.json()["items"]
        event_types = [e["eventType"] for e in events]
        assert "login.succeeded" in event_types

    def test_login_failed_event(self):
        org = create_org()
        email = f"{unique('audit')}@example.com"
        create_human_user(org["id"], email=email, password="ValidPass1!")
        login(email, "WrongPass!", org["id"])
        r = requests.get(f"{BASE_URL}/organizations/{org['id']}/events", headers=headers(), timeout=REQUEST_TIMEOUT)
        events = r.json()["items"]
        event_types = [e["eventType"] for e in events]
        assert "login.failed" in event_types

    def test_filter_events_by_type(self):
        org = create_org()
        create_human_user(org["id"])
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/events?eventType=user.created",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        events = r.json()["items"]
        for e in events:
            assert e["eventType"] == "user.created"

    def test_filter_events_by_user(self):
        org = create_org()
        user = create_human_user(org["id"]).json()
        r = requests.get(
            f"{BASE_URL}/organizations/{org['id']}/events?userId={user['id']}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        events = r.json()["items"]
        for e in events:
            assert e["userId"] == user["id"]


# ──────────────────────────────────────────────────────────────────────────────
# OIDC/OAuth Metadata Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestOIDC:
    def test_well_known_endpoint(self):
        r = requests.get(f"{BASE_URL}/.well-known/openid-configuration", timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "issuer" in data
        assert "authorizationEndpoint" in data
        assert "tokenEndpoint" in data
        assert "jwksUri" in data

    def test_jwks_endpoint(self):
        r = requests.get(f"{BASE_URL}/.well-known/jwks.json", timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert "keys" in data
        assert isinstance(data["keys"], list)
        if len(data["keys"]) > 0:
            key = data["keys"][0]
            assert "kty" in key
            assert "kid" in key
