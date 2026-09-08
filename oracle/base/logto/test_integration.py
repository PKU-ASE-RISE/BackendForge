"""
BackendForge — L2 Integration Tests for Logto Management API
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

HDR = {"X-Api-Key": "test-key", "Content-Type": "application/json"}


def unique():
    return uuid.uuid4().hex[:8]


def post(path, data):
    return requests.post(f"{BASE_URL}{path}", json=data, headers=HDR, timeout=30)


def get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HDR, timeout=30)


def patch(path, data):
    return requests.patch(f"{BASE_URL}{path}", json=data, headers=HDR, timeout=30)


def delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HDR, timeout=30)


class TestUserFieldsAndCamelCase:
    """Pattern 1: Verify camelCase field names from schema."""

    def test_user_create_returns_camelcase_fields(self):
        uname = f"user_{unique()}"
        r = post("/api/users", {"username": uname, "email": f"{uname}@test.com", "name": "Test User", "customData": {"key": "val"}})
        assert r.status_code == 201
        user = r.json()
        assert user["username"] == uname
        assert user["email"] == f"{uname}@test.com"
        assert user["name"] == "Test User"
        assert user["customData"] == {"key": "val"}
        assert "isSuspended" in user
        assert user["isSuspended"] is False
        assert "id" in user
        assert "createdAt" in user

    def test_user_custom_data_defaults_to_empty_object(self):
        r = post("/api/users", {"username": f"nocd_{unique()}"})
        assert r.status_code == 201
        assert r.json()["customData"] == {}

    def test_user_update_uses_patch_not_put(self):
        user = post("/api/users", {"username": f"upd_{unique()}", "name": "Before"}).json()
        r = patch(f"/api/users/{user['id']}", {"name": "After"})
        assert r.status_code == 200
        assert r.json()["name"] == "After"
        assert r.json()["username"] == user["username"]  # unchanged


class TestApplicationAutoGeneration:
    """Pattern 5: clientId and clientSecret are auto-generated."""

    def test_app_creates_with_client_credentials(self):
        r = post("/api/applications", {"name": f"App-{unique()}", "description": "Test", "type": "SPA"})
        assert r.status_code == 201
        app = r.json()
        assert "clientId" in app
        assert "clientSecret" in app
        assert len(app["clientId"]) > 0
        assert len(app["clientSecret"]) == 32
        assert app["type"] == "SPA"
        assert "id" in app
        assert "createdAt" in app

    def test_app_type_validation(self):
        r = post("/api/applications", {"name": f"Bad-{unique()}", "type": "InvalidType"})
        assert r.status_code == 422

    def test_app_filter_by_type(self):
        post("/api/applications", {"name": f"SPA-{unique()}", "type": "SPA"})
        post("/api/applications", {"name": f"Trad-{unique()}", "type": "Traditional"})
        r = get("/api/applications", params={"type": "SPA"})
        assert r.status_code == 200
        apps = r.json()
        for app in apps:
            assert app["type"] == "SPA"


class TestResourceAndScopes:
    """Pattern 2+7: Resources include scopes, cascade deletes work."""

    def test_resource_get_includes_scopes(self):
        res = post("/api/resources", {"name": f"API-{unique()}", "indicator": f"https://api-{unique()}.com"}).json()
        scope = post(f"/api/resources/{res['id']}/scopes", {"name": f"read:{unique()}", "description": "Read access"}).json()
        r = get(f"/api/resources/{res['id']}")
        resource = r.json()
        assert "scopes" in resource
        assert len(resource["scopes"]) >= 1
        assert any(s["id"] == scope["id"] for s in resource["scopes"])

    def test_scope_uniqueness_within_resource(self):
        res = post("/api/resources", {"name": f"Uniq-{unique()}", "indicator": f"https://uniq-{unique()}.com"}).json()
        name = f"scope-{unique()}"
        r1 = post(f"/api/resources/{res['id']}/scopes", {"name": name, "description": "A"})
        assert r1.status_code == 201
        r2 = post(f"/api/resources/{res['id']}/scopes", {"name": name, "description": "B"})
        assert r2.status_code == 409

    def test_delete_resource_cascades_scopes(self):
        res = post("/api/resources", {"name": f"Casc-{unique()}", "indicator": f"https://casc-{unique()}.com"}).json()
        scope = post(f"/api/resources/{res['id']}/scopes", {"name": f"s-{unique()}", "description": "x"}).json()
        delete(f"/api/resources/{res['id']}")
        assert get(f"/api/resources/{res['id']}").status_code == 404


class TestRoleTypeEnforcement:
    """Pattern 5+4: Role type determines what can be assigned."""

    def test_m2m_role_cannot_be_assigned_to_user(self):
        user = post("/api/users", {"username": f"m2m_{unique()}"}).json()
        role = post("/api/roles", {"name": f"M2MRole-{unique()}", "description": "Machine", "type": "MachineToMachine"}).json()
        r = post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        assert r.status_code == 422

    def test_user_role_can_be_assigned(self):
        user = post("/api/users", {"username": f"ur_{unique()}"}).json()
        role = post("/api/roles", {"name": f"UserRole-{unique()}", "description": "User", "type": "User"}).json()
        r = post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        assert r.status_code == 201

    def test_role_name_uniqueness(self):
        name = f"Role-{unique()}"
        r1 = post("/api/roles", {"name": name, "description": "A", "type": "User"})
        assert r1.status_code == 201
        r2 = post("/api/roles", {"name": name, "description": "B", "type": "User"})
        assert r2.status_code == 409


class TestPermissionResolution:
    """Pattern 5: Effective permissions are computed correctly."""

    def test_user_permissions_union_of_role_scopes(self):
        # Create resources and scopes
        res1 = post("/api/resources", {"name": f"R1-{unique()}", "indicator": f"https://r1-{unique()}.com"}).json()
        s1 = post(f"/api/resources/{res1['id']}/scopes", {"name": f"read-{unique()}", "description": "read"}).json()
        s2 = post(f"/api/resources/{res1['id']}/scopes", {"name": f"write-{unique()}", "description": "write"}).json()

        # Create role and assign scopes
        role = post("/api/roles", {"name": f"Admin-{unique()}", "description": "Admin", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [s1["id"], s2["id"]]})

        # Create user and assign role
        user = post("/api/users", {"username": f"perm_{unique()}"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Check permissions
        r = get(f"/api/users/{user['id']}/permissions")
        assert r.status_code == 200
        perms = r.json()
        assert len(perms) == 2
        scope_ids = {p["scopeId"] for p in perms}
        assert s1["id"] in scope_ids
        assert s2["id"] in scope_ids
        # Verify required fields
        for p in perms:
            assert "resourceId" in p
            assert "resourceIndicator" in p
            assert "scopeId" in p
            assert "scopeName" in p

    def test_suspended_user_permissions_empty(self):
        res = post("/api/resources", {"name": f"Sus-{unique()}", "indicator": f"https://sus-{unique()}.com"}).json()
        scope = post(f"/api/resources/{res['id']}/scopes", {"name": f"read-{unique()}", "description": "r"}).json()
        role = post("/api/roles", {"name": f"SusRole-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        user = post("/api/users", {"username": f"sus_{unique()}", "isSuspended": True}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        r = get(f"/api/users/{user['id']}/permissions")
        assert r.json() == []


class TestSearchFilter:
    """Pattern 3: Search actually filters results."""

    def test_user_search_by_username(self):
        keyword = f"searchable{unique()}"
        post("/api/users", {"username": keyword, "name": "Normal Name"})
        post("/api/users", {"username": f"other_{unique()}", "name": "Other"})

        r = get("/api/users", params={"search": keyword})
        users = r.json()
        assert len(users) >= 1
        assert all(keyword in u.get("username", "") or keyword in (u.get("name") or "") or keyword in (u.get("email") or "") for u in users)

    def test_role_search_by_name(self):
        keyword = f"findme{unique()}"
        post("/api/roles", {"name": keyword, "description": "x", "type": "User"})
        r = get("/api/roles", params={"search": keyword})
        roles = r.json()
        assert len(roles) >= 1
        assert any(keyword in role["name"] for role in roles)


class TestOrganizationMembers:
    """Pattern 5+7: Org membership idempotency and cascades."""

    def test_add_member_idempotent(self):
        org = post("/api/organizations", {"name": f"Org-{unique()}", "description": "test"}).json()
        user = post("/api/users", {"username": f"mem_{unique()}"}).json()
        r1 = post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})
        assert r1.status_code == 201
        # Adding again should not error
        r2 = post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})
        assert r2.status_code == 201

    def test_remove_non_member_returns_404(self):
        org = post("/api/organizations", {"name": f"NoMem-{unique()}", "description": "test"}).json()
        user = post("/api/users", {"username": f"nm_{unique()}"}).json()
        r = delete(f"/api/organizations/{org['id']}/members/{user['id']}")
        assert r.status_code == 404

    def test_delete_org_cascades_members(self):
        org = post("/api/organizations", {"name": f"DelOrg-{unique()}", "description": "x"}).json()
        user = post("/api/users", {"username": f"do_{unique()}"}).json()
        post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})
        delete(f"/api/organizations/{org['id']}")
        assert get(f"/api/organizations/{org['id']}").status_code == 404


class TestAuditLogs:
    """Pattern 5: Audit logs are auto-generated."""

    def test_user_create_generates_log(self):
        user = post("/api/users", {"username": f"log_{unique()}"}).json()
        r = get("/api/logs", params={"userId": user["id"], "type": "User.Created"})
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["type"] == "User.Created"
        assert logs[0]["userId"] == user["id"]

    def test_user_delete_generates_log(self):
        user = post("/api/users", {"username": f"dlog_{unique()}"}).json()
        delete(f"/api/users/{user['id']}")
        r = get("/api/logs", params={"type": "User.Deleted"})
        logs = r.json()
        assert any(log["userId"] == user["id"] for log in logs)


class TestSignInExperience:
    """Pattern 5: Sign-in experience is gettable and updateable."""

    def test_sign_in_exp_structure(self):
        r = get("/api/sign-in-exp")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "default"
        assert "branding" in data
        assert "primaryColor" in data["branding"]

    def test_sign_in_exp_update(self):
        r = patch("/api/sign-in-exp", {"branding": {"primaryColor": "#00FF00", "darkMode": True}})
        assert r.status_code == 200
        data = r.json()
        assert data["branding"]["primaryColor"] == "#00FF00"
        assert data["branding"]["darkMode"] is True
        # Verify GET returns updated value
        r2 = get("/api/sign-in-exp")
        assert r2.json()["branding"]["primaryColor"] == "#00FF00"


class TestCascadeDeletes:
    """Pattern 7: Cascade deletes properly remove assignments."""

    def test_delete_user_removes_role_assignment(self):
        user = post("/api/users", {"username": f"cu_{unique()}"}).json()
        role = post("/api/roles", {"name": f"CU-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        # Verify assigned
        users = get(f"/api/roles/{role['id']}/users").json()
        assert any(u["id"] == user["id"] for u in users)
        # Delete user
        delete(f"/api/users/{user['id']}")
        # Verify removed from role
        users2 = get(f"/api/roles/{role['id']}/users").json()
        assert not any(u["id"] == user["id"] for u in users2)

    def test_delete_role_removes_assignments(self):
        user = post("/api/users", {"username": f"dr_{unique()}"}).json()
        role = post("/api/roles", {"name": f"DR-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        delete(f"/api/roles/{role['id']}")
        # User's roles should no longer include deleted role
        roles = get(f"/api/users/{user['id']}/roles").json()
        assert not any(r["id"] == role["id"] for r in roles)


class TestAuthRequired:
    """Pattern 4: All endpoints require X-Api-Key."""

    def test_missing_key_returns_401(self):
        endpoints = [
            "/api/users", "/api/applications", "/api/resources",
            "/api/roles", "/api/organizations", "/api/logs", "/api/sign-in-exp"
        ]
        for path in endpoints:
            r = requests.get(f"{BASE_URL}{path}", timeout=30)
            assert r.status_code == 401, f"GET {path} without key returned {r.status_code}"

    def test_empty_key_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/users", headers={"X-Api-Key": ""}, timeout=30)
        assert r.status_code == 401


class TestUniquenessConstraints:
    """Pattern 8: Uniqueness violations return 409."""

    def test_username_uniqueness(self):
        uname = f"uniq_{unique()}"
        r1 = post("/api/users", {"username": uname})
        assert r1.status_code == 201
        r2 = post("/api/users", {"username": uname})
        assert r2.status_code == 409

    def test_resource_indicator_uniqueness(self):
        ind = f"https://uniq-{unique()}.com"
        r1 = post("/api/resources", {"name": "R1", "indicator": ind})
        assert r1.status_code == 201
        r2 = post("/api/resources", {"name": "R2", "indicator": ind})
        assert r2.status_code == 409
