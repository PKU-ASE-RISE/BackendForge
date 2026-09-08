"""
BackendForge — L3 Workflow Tests for Logto Management API
Complex multi-step workflows that cross multiple entity types.
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


class TestRBACFullWorkflow:
    """Pattern 2+5+7: Complete RBAC setup with permission resolution."""

    def test_full_rbac_lifecycle(self):
        # 1. Create API resource with scopes
        res = post("/api/resources", {"name": f"OrdersAPI-{unique()}", "indicator": f"https://orders-{unique()}.com"}).json()
        s_read = post(f"/api/resources/{res['id']}/scopes", {"name": f"orders:read-{unique()}", "description": "Read orders"}).json()
        s_write = post(f"/api/resources/{res['id']}/scopes", {"name": f"orders:write-{unique()}", "description": "Write orders"}).json()
        s_delete = post(f"/api/resources/{res['id']}/scopes", {"name": f"orders:delete-{unique()}", "description": "Delete orders"}).json()

        # 2. Create roles with different scope sets
        admin_role = post("/api/roles", {"name": f"OrderAdmin-{unique()}", "description": "Full access", "type": "User"}).json()
        viewer_role = post("/api/roles", {"name": f"OrderViewer-{unique()}", "description": "Read only", "type": "User"}).json()

        # 3. Assign scopes to roles
        post(f"/api/roles/{admin_role['id']}/scopes", {"scopeIds": [s_read["id"], s_write["id"], s_delete["id"]]})
        post(f"/api/roles/{viewer_role['id']}/scopes", {"scopeIds": [s_read["id"]]})

        # 4. Verify role scopes
        admin_scopes = get(f"/api/roles/{admin_role['id']}/scopes").json()
        assert len(admin_scopes) == 3
        viewer_scopes = get(f"/api/roles/{viewer_role['id']}/scopes").json()
        assert len(viewer_scopes) == 1

        # 5. Create users
        admin_user = post("/api/users", {"username": f"admin_{unique()}", "email": "admin@test.com"}).json()
        viewer_user = post("/api/users", {"username": f"viewer_{unique()}", "email": "viewer@test.com"}).json()

        # 6. Assign roles
        post(f"/api/roles/{admin_role['id']}/users", {"userIds": [admin_user["id"]]})
        post(f"/api/roles/{viewer_role['id']}/users", {"userIds": [viewer_user["id"]]})

        # 7. Verify user roles
        admin_roles = get(f"/api/users/{admin_user['id']}/roles").json()
        assert any(r["id"] == admin_role["id"] for r in admin_roles)

        # 8. Check admin permissions (should have all 3)
        admin_perms = get(f"/api/users/{admin_user['id']}/permissions").json()
        assert len(admin_perms) == 3
        perm_scope_ids = {p["scopeId"] for p in admin_perms}
        assert s_read["id"] in perm_scope_ids
        assert s_write["id"] in perm_scope_ids
        assert s_delete["id"] in perm_scope_ids
        # Verify field structure
        for p in admin_perms:
            assert p["resourceId"] == res["id"]
            assert "resourceIndicator" in p
            assert "scopeName" in p

        # 9. Check viewer permissions (should have only read)
        viewer_perms = get(f"/api/users/{viewer_user['id']}/permissions").json()
        assert len(viewer_perms) == 1
        assert viewer_perms[0]["scopeId"] == s_read["id"]

        # 10. Suspend admin → permissions become empty
        patch(f"/api/users/{admin_user['id']}", {"isSuspended": True})
        suspended_perms = get(f"/api/users/{admin_user['id']}/permissions").json()
        assert suspended_perms == []

        # 11. Unsuspend → permissions return
        patch(f"/api/users/{admin_user['id']}", {"isSuspended": False})
        restored_perms = get(f"/api/users/{admin_user['id']}/permissions").json()
        assert len(restored_perms) == 3


class TestMultiRolePermissionUnion:
    """Pattern 5: Permissions from multiple roles are unioned."""

    def test_multiple_roles_union_permissions(self):
        # Two resources with different scopes
        res1 = post("/api/resources", {"name": f"Res1-{unique()}", "indicator": f"https://r1-{unique()}.com"}).json()
        res2 = post("/api/resources", {"name": f"Res2-{unique()}", "indicator": f"https://r2-{unique()}.com"}).json()
        s1 = post(f"/api/resources/{res1['id']}/scopes", {"name": f"s1-{unique()}", "description": "Scope 1"}).json()
        s2 = post(f"/api/resources/{res2['id']}/scopes", {"name": f"s2-{unique()}", "description": "Scope 2"}).json()

        # Two roles, each with one scope
        role1 = post("/api/roles", {"name": f"R1-{unique()}", "description": "x", "type": "User"}).json()
        role2 = post("/api/roles", {"name": f"R2-{unique()}", "description": "y", "type": "User"}).json()
        post(f"/api/roles/{role1['id']}/scopes", {"scopeIds": [s1["id"]]})
        post(f"/api/roles/{role2['id']}/scopes", {"scopeIds": [s2["id"]]})

        # User with both roles
        user = post("/api/users", {"username": f"multi_{unique()}"}).json()
        post(f"/api/roles/{role1['id']}/users", {"userIds": [user["id"]]})
        post(f"/api/roles/{role2['id']}/users", {"userIds": [user["id"]]})

        # Permissions should include both scopes
        perms = get(f"/api/users/{user['id']}/permissions").json()
        scope_ids = {p["scopeId"] for p in perms}
        assert s1["id"] in scope_ids
        assert s2["id"] in scope_ids
        assert len(perms) == 2


class TestResourceDeletionCascade:
    """Pattern 7: Deleting a resource cascades to scopes and role-scope assignments."""

    def test_delete_resource_removes_role_scope_assignments(self):
        # Setup
        res = post("/api/resources", {"name": f"CascRes-{unique()}", "indicator": f"https://casc-{unique()}.com"}).json()
        scope = post(f"/api/resources/{res['id']}/scopes", {"name": f"casc-{unique()}", "description": "x"}).json()
        role = post("/api/roles", {"name": f"CascRole-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        user = post("/api/users", {"username": f"casc_{unique()}"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Verify permission exists
        perms = get(f"/api/users/{user['id']}/permissions").json()
        assert len(perms) == 1

        # Delete resource
        delete(f"/api/resources/{res['id']}")

        # Permissions should be empty (scope gone)
        perms2 = get(f"/api/users/{user['id']}/permissions").json()
        assert len(perms2) == 0

        # Role scopes should be empty
        role_scopes = get(f"/api/roles/{role['id']}/scopes").json()
        assert len(role_scopes) == 0


class TestUserDeletionCascade:
    """Pattern 7: Deleting a user removes role assignments and org memberships."""

    def test_delete_user_full_cascade(self):
        # Setup user with role and org membership
        user = post("/api/users", {"username": f"deluser_{unique()}"}).json()
        role = post("/api/roles", {"name": f"DelRole-{unique()}", "description": "x", "type": "User"}).json()
        org = post("/api/organizations", {"name": f"DelOrg-{unique()}", "description": "x"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})

        # Verify membership
        members = get(f"/api/organizations/{org['id']}/members").json()
        assert any(m["id"] == user["id"] for m in members)
        role_users = get(f"/api/roles/{role['id']}/users").json()
        assert any(u["id"] == user["id"] for u in role_users)

        # Delete user
        r = delete(f"/api/users/{user['id']}")
        assert r.status_code == 204

        # Verify removed from role and org
        role_users2 = get(f"/api/roles/{role['id']}/users").json()
        assert not any(u["id"] == user["id"] for u in role_users2)
        members2 = get(f"/api/organizations/{org['id']}/members").json()
        assert not any(m["id"] == user["id"] for m in members2)


class TestAuditLogWorkflow:
    """Pattern 5: Audit logs are generated for key actions."""

    def test_user_lifecycle_generates_logs(self):
        # Create user
        user = post("/api/users", {"username": f"audit_{unique()}"}).json()

        # Update user
        patch(f"/api/users/{user['id']}", {"name": "Updated"})

        # Assign role
        role = post("/api/roles", {"name": f"AuditRole-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Check logs
        logs = get("/api/logs", params={"userId": user["id"]}).json()
        log_types = [l["type"] for l in logs]
        assert "User.Created" in log_types
        assert "User.Updated" in log_types
        assert "Role.User.Assigned" in log_types

        # Delete user
        delete(f"/api/users/{user['id']}")
        logs2 = get("/api/logs", params={"userId": user["id"]}).json()
        log_types2 = [l["type"] for l in logs2]
        assert "User.Deleted" in log_types2


class TestOrganizationWorkflow:
    """Pattern 5+7: Organization creation, membership, deletion."""

    def test_org_full_lifecycle(self):
        # 1. Create org
        org = post("/api/organizations", {"name": f"DevTeam-{unique()}", "description": "Dev team"}).json()
        assert "id" in org
        assert "createdAt" in org

        # 2. Create users
        u1 = post("/api/users", {"username": f"org1_{unique()}"}).json()
        u2 = post("/api/users", {"username": f"org2_{unique()}"}).json()

        # 3. Add members
        post(f"/api/organizations/{org['id']}/members", {"userIds": [u1["id"], u2["id"]]})

        # 4. List members
        members = get(f"/api/organizations/{org['id']}/members").json()
        member_user_ids = [m["id"] for m in members]
        assert u1["id"] in member_user_ids
        assert u2["id"] in member_user_ids

        # 5. Remove one member
        r = delete(f"/api/organizations/{org['id']}/members/{u1['id']}")
        assert r.status_code == 204

        # 6. Verify removal
        members2 = get(f"/api/organizations/{org['id']}/members").json()
        member_ids2 = [m["id"] for m in members2]
        assert u1["id"] not in member_ids2
        assert u2["id"] in member_ids2

        # 7. Delete org
        delete(f"/api/organizations/{org['id']}")
        assert get(f"/api/organizations/{org['id']}").status_code == 404


class TestApplicationWorkflow:
    """Pattern 1+5: Application CRUD with auto-generated credentials."""

    def test_application_lifecycle(self):
        # 1. Create
        app = post("/api/applications", {"name": f"MyApp-{unique()}", "description": "Test app", "type": "Traditional"}).json()
        assert app["type"] == "Traditional"
        assert len(app["clientId"]) > 0
        assert len(app["clientSecret"]) == 32
        original_client_id = app["clientId"]
        original_secret = app["clientSecret"]

        # 2. Get
        fetched = get(f"/api/applications/{app['id']}").json()
        assert fetched["clientId"] == original_client_id
        assert fetched["clientSecret"] == original_secret

        # 3. Update — clientId/clientSecret should NOT change
        updated = patch(f"/api/applications/{app['id']}", {"name": "Renamed", "description": "Updated"}).json()
        assert updated["name"] == "Renamed"
        assert updated["clientId"] == original_client_id
        assert updated["clientSecret"] == original_secret

        # 4. Delete
        r = delete(f"/api/applications/{app['id']}")
        assert r.status_code == 204
        assert get(f"/api/applications/{app['id']}").status_code == 404


class TestScopeRemovalFromRole:
    """Pattern 7: Removing a scope from a role affects user permissions."""

    def test_remove_scope_affects_permissions(self):
        res = post("/api/resources", {"name": f"ScopeRm-{unique()}", "indicator": f"https://srm-{unique()}.com"}).json()
        s1 = post(f"/api/resources/{res['id']}/scopes", {"name": f"a-{unique()}", "description": "A"}).json()
        s2 = post(f"/api/resources/{res['id']}/scopes", {"name": f"b-{unique()}", "description": "B"}).json()
        role = post("/api/roles", {"name": f"SRRole-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [s1["id"], s2["id"]]})
        user = post("/api/users", {"username": f"srm_{unique()}"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Verify 2 permissions
        perms = get(f"/api/users/{user['id']}/permissions").json()
        assert len(perms) == 2

        # Remove one scope from role
        delete(f"/api/roles/{role['id']}/scopes/{s1['id']}")

        # Verify only 1 permission
        perms2 = get(f"/api/users/{user['id']}/permissions").json()
        assert len(perms2) == 1
        assert perms2[0]["scopeId"] == s2["id"]


class TestRoleDeletionCascade:
    """Pattern 7: Deleting a role removes all assignments."""

    def test_delete_role_removes_user_assignments_and_scope_links(self):
        res = post("/api/resources", {"name": f"RD-{unique()}", "indicator": f"https://rd-{unique()}.com"}).json()
        scope = post(f"/api/resources/{res['id']}/scopes", {"name": f"rd-{unique()}", "description": "x"}).json()
        role = post("/api/roles", {"name": f"RD-{unique()}", "description": "x", "type": "User"}).json()
        post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        user = post("/api/users", {"username": f"rd_{unique()}"}).json()
        post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Verify
        assert len(get(f"/api/users/{user['id']}/permissions").json()) == 1

        # Delete role
        delete(f"/api/roles/{role['id']}")
        assert get(f"/api/roles/{role['id']}").status_code == 404

        # User should have no permissions from this role
        assert len(get(f"/api/users/{user['id']}/permissions").json()) == 0
        assert not any(r["id"] == role["id"] for r in get(f"/api/users/{user['id']}/roles").json())
