"""
BackendForge — Comprehensive Correctness Tests for Logto Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = "test-management-api-key"

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_patch(path, json_data=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ── Helpers ──

def create_user(username=None, **kwargs):
    """Helper: create a user and return the response JSON."""
    username = username or f"user-{uuid.uuid4().hex[:8]}"
    data = {"username": username, **kwargs}
    resp = api_post("/api/users", data)
    assert resp.status_code == 201, f"Failed to create user: {resp.status_code} {resp.text}"
    return resp.json()


def create_resource(name=None, indicator=None):
    """Helper: create a resource."""
    name = name or f"resource-{uuid.uuid4().hex[:8]}"
    indicator = indicator or f"https://api-{uuid.uuid4().hex[:8]}.example.com"
    resp = api_post("/api/resources", {"name": name, "indicator": indicator})
    assert resp.status_code == 201, f"Failed to create resource: {resp.status_code} {resp.text}"
    return resp.json()


def create_scope(resource_id, name=None, description=""):
    """Helper: create a scope within a resource."""
    name = name or f"scope-{uuid.uuid4().hex[:8]}"
    resp = api_post(f"/api/resources/{resource_id}/scopes", {"name": name, "description": description})
    assert resp.status_code == 201, f"Failed to create scope: {resp.status_code} {resp.text}"
    return resp.json()


def create_role(name=None, role_type="User", description=""):
    """Helper: create a role."""
    name = name or f"role-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/roles", {"name": name, "type": role_type, "description": description})
    assert resp.status_code == 201, f"Failed to create role: {resp.status_code} {resp.text}"
    return resp.json()


def create_organization(name=None, description=""):
    """Helper: create an organization."""
    name = name or f"org-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/organizations", {"name": name, "description": description})
    assert resp.status_code == 201, f"Failed to create org: {resp.status_code} {resp.text}"
    return resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/users", timeout=30)
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        """Empty X-Api-Key should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/users",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=30
        )
        assert resp.status_code == 401

    def test_valid_api_key_succeeds(self):
        """Any non-empty X-Api-Key should be accepted."""
        resp = api_get("/api/users")
        assert resp.status_code == 200

    def test_401_response_body(self):
        """401 should return a JSON body with message."""
        resp = requests.get(f"{BASE_URL}/api/users", timeout=30)
        assert resp.status_code == 401
        data = resp.json()
        assert "message" in data

    def test_missing_key_on_applications(self):
        resp = requests.get(f"{BASE_URL}/api/applications", timeout=30)
        assert resp.status_code == 401

    def test_missing_key_on_roles(self):
        resp = requests.get(f"{BASE_URL}/api/roles", timeout=30)
        assert resp.status_code == 401

    def test_missing_key_on_resources(self):
        resp = requests.get(f"{BASE_URL}/api/resources", timeout=30)
        assert resp.status_code == 401

    def test_missing_key_on_organizations(self):
        resp = requests.get(f"{BASE_URL}/api/organizations", timeout=30)
        assert resp.status_code == 401

    def test_missing_key_on_logs(self):
        resp = requests.get(f"{BASE_URL}/api/logs", timeout=30)
        assert resp.status_code == 401

    def test_missing_key_on_sign_in_exp(self):
        resp = requests.get(f"{BASE_URL}/api/sign-in-exp", timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 2: Users CRUD
# ════════════════════════════════════════════════════════════════════


class TestUsersCRUD:

    def test_create_user(self):
        username = f"testuser-{UNIQUE}"
        resp = api_post("/api/users", {
            "username": username,
            "email": "test@example.com",
            "name": "Test User",
            "avatar": "https://example.com/avatar.png",
            "customData": {"key": "value"},
        })
        assert resp.status_code == 201
        user = resp.json()
        assert user["username"] == username
        assert user["email"] == "test@example.com"
        assert user["name"] == "Test User"
        assert user["avatar"] == "https://example.com/avatar.png"
        assert user["customData"] == {"key": "value"}
        assert user["isSuspended"] is False
        assert "id" in user
        assert "createdAt" in user

    def test_create_user_minimal(self):
        username = f"minimal-{UNIQUE}"
        resp = api_post("/api/users", {"username": username})
        assert resp.status_code == 201
        user = resp.json()
        assert user["username"] == username
        assert user["customData"] == {}
        assert user["isSuspended"] is False

    def test_create_user_duplicate_username(self):
        username = f"dupuser-{UNIQUE}"
        resp1 = api_post("/api/users", {"username": username})
        assert resp1.status_code == 201
        resp2 = api_post("/api/users", {"username": username})
        assert resp2.status_code == 409

    def test_get_user_by_id(self):
        user = create_user()
        resp = api_get(f"/api/users/{user['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == user["id"]
        assert fetched["username"] == user["username"]

    def test_get_nonexistent_user(self):
        resp = api_get("/api/users/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_user(self):
        user = create_user()
        resp = api_patch(f"/api/users/{user['id']}", {
            "name": "Updated Name",
            "email": "updated@example.com",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "Updated Name"
        assert updated["email"] == "updated@example.com"
        # Username should remain unchanged
        assert updated["username"] == user["username"]

    def test_update_user_custom_data(self):
        user = create_user()
        resp = api_patch(f"/api/users/{user['id']}", {
            "customData": {"newKey": "newValue"},
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["customData"] == {"newKey": "newValue"}

    def test_update_user_suspend(self):
        user = create_user()
        resp = api_patch(f"/api/users/{user['id']}", {"isSuspended": True})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["isSuspended"] is True

    def test_update_nonexistent_user(self):
        resp = api_patch("/api/users/nonexistent-id-12345", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_update_user_duplicate_username(self):
        user1 = create_user()
        user2 = create_user()
        resp = api_patch(f"/api/users/{user2['id']}", {"username": user1["username"]})
        assert resp.status_code == 409

    def test_delete_user(self):
        user = create_user()
        resp = api_delete(f"/api/users/{user['id']}")
        assert resp.status_code == 204
        # Verify gone
        get_resp = api_get(f"/api/users/{user['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_user(self):
        resp = api_delete("/api/users/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_users(self):
        user = create_user()
        resp = api_get("/api/users", params={"page_size": 100})
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        ids = [u["id"] for u in users]
        assert user["id"] in ids

    def test_list_users_pagination(self):
        # Create a few users
        for i in range(3):
            create_user()
        resp = api_get("/api/users", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) <= 2
        # Check X-Total-Count header
        assert "X-Total-Count" in resp.headers
        total = int(resp.headers["X-Total-Count"])
        assert total >= 3

    def test_list_users_search(self):
        username = f"searchable-{uuid.uuid4().hex[:8]}"
        create_user(username=username, name="Searchable Person")
        resp = api_get("/api/users", params={"search": "searchable"})
        assert resp.status_code == 200
        users = resp.json()
        found = [u for u in users if u["username"] == username]
        assert len(found) == 1

    def test_list_users_search_by_email(self):
        unique_email = f"findme-{uuid.uuid4().hex[:8]}@example.com"
        user = create_user(email=unique_email)
        resp = api_get("/api/users", params={"search": unique_email[:10]})
        assert resp.status_code == 200
        users = resp.json()
        found = [u for u in users if u["id"] == user["id"]]
        assert len(found) == 1


# ════════════════════════════════════════════════════════════════════
# PART 3: Applications CRUD
# ════════════════════════════════════════════════════════════════════


class TestApplicationsCRUD:

    def test_create_application_spa(self):
        resp = api_post("/api/applications", {
            "name": f"My SPA-{UNIQUE}",
            "description": "Single page app",
            "type": "SPA",
        })
        assert resp.status_code == 201
        app = resp.json()
        assert app["name"] == f"My SPA-{UNIQUE}"
        assert app["description"] == "Single page app"
        assert app["type"] == "SPA"
        assert "clientId" in app
        assert "clientSecret" in app
        assert len(app["clientId"]) >= 32  # UUID format
        assert len(app["clientSecret"]) == 32
        assert "id" in app
        assert "createdAt" in app

    def test_create_application_traditional(self):
        resp = api_post("/api/applications", {
            "name": f"Traditional App-{UNIQUE}",
            "type": "Traditional",
        })
        assert resp.status_code == 201
        app = resp.json()
        assert app["type"] == "Traditional"

    def test_create_application_m2m(self):
        resp = api_post("/api/applications", {
            "name": f"M2M App-{UNIQUE}",
            "type": "MachineToMachine",
        })
        assert resp.status_code == 201
        app = resp.json()
        assert app["type"] == "MachineToMachine"

    def test_create_application_invalid_type(self):
        resp = api_post("/api/applications", {
            "name": f"Bad App-{UNIQUE}",
            "type": "InvalidType",
        })
        assert resp.status_code == 422

    def test_create_application_default_description(self):
        resp = api_post("/api/applications", {
            "name": f"No Desc App-{UNIQUE}",
            "type": "SPA",
        })
        assert resp.status_code == 201
        app = resp.json()
        assert app["description"] == ""

    def test_get_application_by_id(self):
        create_resp = api_post("/api/applications", {
            "name": f"GetApp-{UNIQUE}",
            "type": "SPA",
        })
        app = create_resp.json()
        resp = api_get(f"/api/applications/{app['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == app["id"]
        assert fetched["clientId"] == app["clientId"]

    def test_get_nonexistent_application(self):
        resp = api_get("/api/applications/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_application(self):
        create_resp = api_post("/api/applications", {
            "name": f"UpdateApp-{UNIQUE}",
            "type": "SPA",
        })
        app = create_resp.json()
        resp = api_patch(f"/api/applications/{app['id']}", {
            "name": f"UpdatedApp-{UNIQUE}",
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdatedApp-{UNIQUE}"
        assert updated["description"] == "Updated desc"
        # clientId and clientSecret should NOT change
        assert updated["clientId"] == app["clientId"]
        assert updated["clientSecret"] == app["clientSecret"]

    def test_update_nonexistent_application(self):
        resp = api_patch("/api/applications/nonexistent-id-12345", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_application(self):
        create_resp = api_post("/api/applications", {
            "name": f"DelApp-{UNIQUE}",
            "type": "SPA",
        })
        app = create_resp.json()
        resp = api_delete(f"/api/applications/{app['id']}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/applications/{app['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_application(self):
        resp = api_delete("/api/applications/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_applications(self):
        create_resp = api_post("/api/applications", {
            "name": f"ListApp-{UNIQUE}",
            "type": "Traditional",
        })
        app = create_resp.json()
        resp = api_get("/api/applications", params={"page_size": 100})
        assert resp.status_code == 200
        apps = resp.json()
        assert isinstance(apps, list)
        ids = [a["id"] for a in apps]
        assert app["id"] in ids

    def test_list_applications_filter_by_type(self):
        api_post("/api/applications", {"name": f"FilterSPA-{UNIQUE}", "type": "SPA"})
        api_post("/api/applications", {"name": f"FilterM2M-{UNIQUE}", "type": "MachineToMachine"})
        resp = api_get("/api/applications", params={"type": "SPA"})
        assert resp.status_code == 200
        apps = resp.json()
        for app in apps:
            assert app["type"] == "SPA"

    def test_list_applications_pagination(self):
        for i in range(3):
            api_post("/api/applications", {"name": f"PagApp-{UNIQUE}-{i}", "type": "SPA"})
        resp = api_get("/api/applications", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        apps = resp.json()
        assert len(apps) <= 2
        assert "X-Total-Count" in resp.headers


# ════════════════════════════════════════════════════════════════════
# PART 4: Resources CRUD
# ════════════════════════════════════════════════════════════════════


class TestResourcesCRUD:

    def test_create_resource(self):
        resp = api_post("/api/resources", {
            "name": f"My API-{UNIQUE}",
            "indicator": f"https://api-{UNIQUE}.example.com",
        })
        assert resp.status_code == 201
        resource = resp.json()
        assert resource["name"] == f"My API-{UNIQUE}"
        assert resource["indicator"] == f"https://api-{UNIQUE}.example.com"
        assert "id" in resource
        assert "createdAt" in resource
        assert "scopes" in resource
        assert resource["scopes"] == []

    def test_create_resource_duplicate_indicator(self):
        indicator = f"https://dup-{UNIQUE}.example.com"
        resp1 = api_post("/api/resources", {"name": "API 1", "indicator": indicator})
        assert resp1.status_code == 201
        resp2 = api_post("/api/resources", {"name": "API 2", "indicator": indicator})
        assert resp2.status_code == 409

    def test_get_resource_by_id(self):
        resource = create_resource()
        resp = api_get(f"/api/resources/{resource['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == resource["id"]
        assert "scopes" in fetched

    def test_get_nonexistent_resource(self):
        resp = api_get("/api/resources/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_resource(self):
        resource = create_resource()
        new_name = f"Updated API-{uuid.uuid4().hex[:8]}"
        resp = api_patch(f"/api/resources/{resource['id']}", {"name": new_name})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["indicator"] == resource["indicator"]

    def test_update_resource_duplicate_indicator(self):
        resource1 = create_resource()
        resource2 = create_resource()
        resp = api_patch(f"/api/resources/{resource2['id']}", {
            "indicator": resource1["indicator"],
        })
        assert resp.status_code == 409

    def test_update_nonexistent_resource(self):
        resp = api_patch("/api/resources/nonexistent-id-12345", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_resource(self):
        resource = create_resource()
        resp = api_delete(f"/api/resources/{resource['id']}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/resources/{resource['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_resource(self):
        resp = api_delete("/api/resources/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_resources(self):
        resource = create_resource()
        resp = api_get("/api/resources", params={"page_size": 100})
        assert resp.status_code == 200
        resources = resp.json()
        assert isinstance(resources, list)
        ids = [r["id"] for r in resources]
        assert resource["id"] in ids

    def test_list_resources_pagination(self):
        for i in range(3):
            create_resource()
        resp = api_get("/api/resources", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        resources = resp.json()
        assert len(resources) <= 2
        assert "X-Total-Count" in resp.headers


# ════════════════════════════════════════════════════════════════════
# PART 5: Scopes CRUD
# ════════════════════════════════════════════════════════════════════


class TestScopesCRUD:

    def test_create_scope(self):
        resource = create_resource()
        resp = api_post(f"/api/resources/{resource['id']}/scopes", {
            "name": f"read:data-{UNIQUE}",
            "description": "Read data permission",
        })
        assert resp.status_code == 201
        scope = resp.json()
        assert scope["name"] == f"read:data-{UNIQUE}"
        assert scope["description"] == "Read data permission"
        assert scope["resourceId"] == resource["id"]
        assert "id" in scope
        assert "createdAt" in scope

    def test_create_scope_default_description(self):
        resource = create_resource()
        resp = api_post(f"/api/resources/{resource['id']}/scopes", {
            "name": f"write:data-{UNIQUE}",
        })
        assert resp.status_code == 201
        scope = resp.json()
        assert scope["description"] == ""

    def test_create_scope_duplicate_name(self):
        resource = create_resource()
        name = f"dup-scope-{UNIQUE}"
        resp1 = api_post(f"/api/resources/{resource['id']}/scopes", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/resources/{resource['id']}/scopes", {"name": name})
        assert resp2.status_code == 409

    def test_create_scope_same_name_different_resource(self):
        """Same scope name allowed in different resources."""
        resource1 = create_resource()
        resource2 = create_resource()
        name = f"common-scope-{UNIQUE}"
        resp1 = api_post(f"/api/resources/{resource1['id']}/scopes", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/resources/{resource2['id']}/scopes", {"name": name})
        assert resp2.status_code == 201

    def test_create_scope_nonexistent_resource(self):
        resp = api_post("/api/resources/nonexistent-id-12345/scopes", {"name": "test"})
        assert resp.status_code == 404

    def test_list_scopes(self):
        resource = create_resource()
        scope = create_scope(resource["id"])
        resp = api_get(f"/api/resources/{resource['id']}/scopes")
        assert resp.status_code == 200
        scopes = resp.json()
        assert isinstance(scopes, list)
        ids = [s["id"] for s in scopes]
        assert scope["id"] in ids

    def test_list_scopes_nonexistent_resource(self):
        resp = api_get("/api/resources/nonexistent-id-12345/scopes")
        assert resp.status_code == 404

    def test_update_scope(self):
        resource = create_resource()
        scope = create_scope(resource["id"])
        new_name = f"updated-scope-{uuid.uuid4().hex[:8]}"
        resp = api_patch(f"/api/resources/{resource['id']}/scopes/{scope['id']}", {
            "name": new_name,
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["description"] == "Updated desc"

    def test_update_scope_duplicate_name(self):
        resource = create_resource()
        scope1 = create_scope(resource["id"])
        scope2 = create_scope(resource["id"])
        resp = api_patch(f"/api/resources/{resource['id']}/scopes/{scope2['id']}", {
            "name": scope1["name"],
        })
        assert resp.status_code == 409

    def test_update_nonexistent_scope(self):
        resource = create_resource()
        resp = api_patch(f"/api/resources/{resource['id']}/scopes/nonexistent-id", {
            "name": "ghost",
        })
        assert resp.status_code == 404

    def test_delete_scope(self):
        resource = create_resource()
        scope = create_scope(resource["id"])
        resp = api_delete(f"/api/resources/{resource['id']}/scopes/{scope['id']}")
        assert resp.status_code == 204
        # Verify gone
        list_resp = api_get(f"/api/resources/{resource['id']}/scopes")
        ids = [s["id"] for s in list_resp.json()]
        assert scope["id"] not in ids

    def test_delete_nonexistent_scope(self):
        resource = create_resource()
        resp = api_delete(f"/api/resources/{resource['id']}/scopes/nonexistent-id")
        assert resp.status_code == 404

    def test_resource_get_includes_scopes(self):
        """GET /api/resources/{id} should include scopes."""
        resource = create_resource()
        scope = create_scope(resource["id"])
        resp = api_get(f"/api/resources/{resource['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert "scopes" in fetched
        scope_ids = [s["id"] for s in fetched["scopes"]]
        assert scope["id"] in scope_ids


# ════════════════════════════════════════════════════════════════════
# PART 6: Roles CRUD
# ════════════════════════════════════════════════════════════════════


class TestRolesCRUD:

    def test_create_role_user_type(self):
        resp = api_post("/api/roles", {
            "name": f"Admin Role-{UNIQUE}",
            "description": "Administrator role",
            "type": "User",
        })
        assert resp.status_code == 201
        role = resp.json()
        assert role["name"] == f"Admin Role-{UNIQUE}"
        assert role["description"] == "Administrator role"
        assert role["type"] == "User"
        assert "id" in role
        assert "createdAt" in role

    def test_create_role_m2m_type(self):
        resp = api_post("/api/roles", {
            "name": f"M2M Role-{UNIQUE}",
            "type": "MachineToMachine",
        })
        assert resp.status_code == 201
        role = resp.json()
        assert role["type"] == "MachineToMachine"

    def test_create_role_duplicate_name(self):
        name = f"dup-role-{UNIQUE}"
        resp1 = api_post("/api/roles", {"name": name, "type": "User"})
        assert resp1.status_code == 201
        resp2 = api_post("/api/roles", {"name": name, "type": "User"})
        assert resp2.status_code == 409

    def test_create_role_default_description(self):
        resp = api_post("/api/roles", {
            "name": f"NoDesc Role-{UNIQUE}",
            "type": "User",
        })
        assert resp.status_code == 201
        role = resp.json()
        assert role["description"] == ""

    def test_get_role_by_id(self):
        role = create_role()
        resp = api_get(f"/api/roles/{role['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == role["id"]

    def test_get_nonexistent_role(self):
        resp = api_get("/api/roles/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_role(self):
        role = create_role()
        new_name = f"updated-role-{uuid.uuid4().hex[:8]}"
        resp = api_patch(f"/api/roles/{role['id']}", {
            "name": new_name,
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["description"] == "Updated desc"

    def test_update_role_duplicate_name(self):
        role1 = create_role()
        role2 = create_role()
        resp = api_patch(f"/api/roles/{role2['id']}", {"name": role1["name"]})
        assert resp.status_code == 409

    def test_update_nonexistent_role(self):
        resp = api_patch("/api/roles/nonexistent-id-12345", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_role(self):
        role = create_role()
        resp = api_delete(f"/api/roles/{role['id']}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/roles/{role['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_role(self):
        resp = api_delete("/api/roles/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_roles(self):
        role = create_role()
        resp = api_get("/api/roles", params={"page_size": 100})
        assert resp.status_code == 200
        roles = resp.json()
        assert isinstance(roles, list)
        ids = [r["id"] for r in roles]
        assert role["id"] in ids

    def test_list_roles_filter_by_type(self):
        create_role(role_type="User")
        create_role(role_type="MachineToMachine")
        resp = api_get("/api/roles", params={"type": "User"})
        assert resp.status_code == 200
        roles = resp.json()
        for r in roles:
            assert r["type"] == "User"

    def test_list_roles_search(self):
        name = f"findme-role-{uuid.uuid4().hex[:8]}"
        create_role(name=name)
        resp = api_get("/api/roles", params={"search": "findme-role"})
        assert resp.status_code == 200
        roles = resp.json()
        found = [r for r in roles if r["name"] == name]
        assert len(found) == 1

    def test_list_roles_pagination(self):
        for i in range(3):
            create_role()
        resp = api_get("/api/roles", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        roles = resp.json()
        assert len(roles) <= 2
        assert "X-Total-Count" in resp.headers


# ════════════════════════════════════════════════════════════════════
# PART 7: Role-User Assignment
# ════════════════════════════════════════════════════════════════════


class TestRoleUserAssignment:

    def test_assign_user_to_role(self):
        role = create_role(role_type="User")
        user = create_user()
        resp = api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        assert resp.status_code == 201

        # Verify assignment
        list_resp = api_get(f"/api/roles/{role['id']}/users")
        assert list_resp.status_code == 200
        users = list_resp.json()
        user_ids = [u["id"] for u in users]
        assert user["id"] in user_ids

    def test_assign_multiple_users_to_role(self):
        role = create_role(role_type="User")
        user1 = create_user()
        user2 = create_user()
        resp = api_post(f"/api/roles/{role['id']}/users", {
            "userIds": [user1["id"], user2["id"]],
        })
        assert resp.status_code == 201

        list_resp = api_get(f"/api/roles/{role['id']}/users")
        users = list_resp.json()
        user_ids = [u["id"] for u in users]
        assert user1["id"] in user_ids
        assert user2["id"] in user_ids

    def test_assign_m2m_role_to_user_fails(self):
        """MachineToMachine roles cannot be assigned to users."""
        role = create_role(role_type="MachineToMachine")
        user = create_user()
        resp = api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        assert resp.status_code == 422

    def test_assign_to_nonexistent_role(self):
        user = create_user()
        resp = api_post("/api/roles/nonexistent-id-12345/users", {"userIds": [user["id"]]})
        assert resp.status_code == 404

    def test_assign_nonexistent_user_to_role(self):
        role = create_role(role_type="User")
        resp = api_post(f"/api/roles/{role['id']}/users", {"userIds": ["nonexistent-user-id"]})
        assert resp.status_code == 404

    def test_remove_user_from_role(self):
        role = create_role(role_type="User")
        user = create_user()
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        resp = api_delete(f"/api/roles/{role['id']}/users/{user['id']}")
        assert resp.status_code == 204

        # Verify removal
        list_resp = api_get(f"/api/roles/{role['id']}/users")
        user_ids = [u["id"] for u in list_resp.json()]
        assert user["id"] not in user_ids

    def test_remove_nonexistent_assignment(self):
        role = create_role(role_type="User")
        user = create_user()
        resp = api_delete(f"/api/roles/{role['id']}/users/{user['id']}")
        assert resp.status_code == 404

    def test_list_role_users_nonexistent_role(self):
        resp = api_get("/api/roles/nonexistent-id-12345/users")
        assert resp.status_code == 404

    def test_user_roles_endpoint(self):
        """GET /api/users/{userId}/roles should list roles assigned to user."""
        role = create_role(role_type="User")
        user = create_user()
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        resp = api_get(f"/api/users/{user['id']}/roles")
        assert resp.status_code == 200
        roles = resp.json()
        role_ids = [r["id"] for r in roles]
        assert role["id"] in role_ids

    def test_user_roles_nonexistent_user(self):
        resp = api_get("/api/users/nonexistent-id-12345/roles")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Role-Scope Assignment
# ════════════════════════════════════════════════════════════════════


class TestRoleScopeAssignment:

    def test_assign_scope_to_role(self):
        role = create_role()
        resource = create_resource()
        scope = create_scope(resource["id"])

        resp = api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        assert resp.status_code == 201

        # Verify
        list_resp = api_get(f"/api/roles/{role['id']}/scopes")
        assert list_resp.status_code == 200
        scopes = list_resp.json()
        scope_ids = [s["id"] for s in scopes]
        assert scope["id"] in scope_ids

    def test_assign_multiple_scopes_to_role(self):
        role = create_role()
        resource = create_resource()
        scope1 = create_scope(resource["id"])
        scope2 = create_scope(resource["id"])

        resp = api_post(f"/api/roles/{role['id']}/scopes", {
            "scopeIds": [scope1["id"], scope2["id"]],
        })
        assert resp.status_code == 201

        list_resp = api_get(f"/api/roles/{role['id']}/scopes")
        scopes = list_resp.json()
        scope_ids = [s["id"] for s in scopes]
        assert scope1["id"] in scope_ids
        assert scope2["id"] in scope_ids

    def test_assign_scope_to_nonexistent_role(self):
        resource = create_resource()
        scope = create_scope(resource["id"])
        resp = api_post("/api/roles/nonexistent-id-12345/scopes", {"scopeIds": [scope["id"]]})
        assert resp.status_code == 404

    def test_assign_nonexistent_scope_to_role(self):
        role = create_role()
        resp = api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": ["nonexistent-scope-id"]})
        assert resp.status_code == 404

    def test_remove_scope_from_role(self):
        role = create_role()
        resource = create_resource()
        scope = create_scope(resource["id"])
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})

        resp = api_delete(f"/api/roles/{role['id']}/scopes/{scope['id']}")
        assert resp.status_code == 204

        # Verify removal
        list_resp = api_get(f"/api/roles/{role['id']}/scopes")
        scope_ids = [s["id"] for s in list_resp.json()]
        assert scope["id"] not in scope_ids

    def test_remove_nonexistent_scope_assignment(self):
        role = create_role()
        resource = create_resource()
        scope = create_scope(resource["id"])
        resp = api_delete(f"/api/roles/{role['id']}/scopes/{scope['id']}")
        assert resp.status_code == 404

    def test_list_role_scopes_nonexistent_role(self):
        resp = api_get("/api/roles/nonexistent-id-12345/scopes")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Permission Resolution
# ════════════════════════════════════════════════════════════════════


class TestPermissionResolution:

    def test_basic_permission_resolution(self):
        """User's permissions = union of scopes from assigned roles."""
        user = create_user()
        resource = create_resource()
        scope1 = create_scope(resource["id"], name=f"read-{uuid.uuid4().hex[:8]}")
        scope2 = create_scope(resource["id"], name=f"write-{uuid.uuid4().hex[:8]}")
        role = create_role(role_type="User")

        # Assign scopes to role
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope1["id"], scope2["id"]]})
        # Assign role to user
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Get permissions
        resp = api_get(f"/api/users/{user['id']}/permissions")
        assert resp.status_code == 200
        permissions = resp.json()
        assert isinstance(permissions, list)
        assert len(permissions) >= 2

        # Verify structure
        scope_ids = [p["scopeId"] for p in permissions]
        assert scope1["id"] in scope_ids
        assert scope2["id"] in scope_ids

        # Verify fields
        for perm in permissions:
            assert "resourceId" in perm
            assert "resourceIndicator" in perm
            assert "scopeId" in perm
            assert "scopeName" in perm
            assert "scopeDescription" in perm

    def test_permission_resolution_multiple_roles(self):
        """Permissions from multiple roles are unioned."""
        user = create_user()
        resource = create_resource()
        scope1 = create_scope(resource["id"], name=f"perm1-{uuid.uuid4().hex[:8]}")
        scope2 = create_scope(resource["id"], name=f"perm2-{uuid.uuid4().hex[:8]}")
        role1 = create_role(role_type="User")
        role2 = create_role(role_type="User")

        api_post(f"/api/roles/{role1['id']}/scopes", {"scopeIds": [scope1["id"]]})
        api_post(f"/api/roles/{role2['id']}/scopes", {"scopeIds": [scope2["id"]]})
        api_post(f"/api/roles/{role1['id']}/users", {"userIds": [user["id"]]})
        api_post(f"/api/roles/{role2['id']}/users", {"userIds": [user["id"]]})

        resp = api_get(f"/api/users/{user['id']}/permissions")
        permissions = resp.json()
        scope_ids = [p["scopeId"] for p in permissions]
        assert scope1["id"] in scope_ids
        assert scope2["id"] in scope_ids

    def test_permission_resolution_deduplicated(self):
        """Same scope in multiple roles appears only once."""
        user = create_user()
        resource = create_resource()
        scope = create_scope(resource["id"], name=f"shared-{uuid.uuid4().hex[:8]}")
        role1 = create_role(role_type="User")
        role2 = create_role(role_type="User")

        # Both roles have the same scope
        api_post(f"/api/roles/{role1['id']}/scopes", {"scopeIds": [scope["id"]]})
        api_post(f"/api/roles/{role2['id']}/scopes", {"scopeIds": [scope["id"]]})
        api_post(f"/api/roles/{role1['id']}/users", {"userIds": [user["id"]]})
        api_post(f"/api/roles/{role2['id']}/users", {"userIds": [user["id"]]})

        resp = api_get(f"/api/users/{user['id']}/permissions")
        permissions = resp.json()
        scope_ids = [p["scopeId"] for p in permissions]
        # Should appear only once
        assert scope_ids.count(scope["id"]) == 1

    def test_suspended_user_no_permissions(self):
        """Suspended users have empty permissions."""
        user = create_user()
        resource = create_resource()
        scope = create_scope(resource["id"])
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        # Suspend the user
        api_patch(f"/api/users/{user['id']}", {"isSuspended": True})

        resp = api_get(f"/api/users/{user['id']}/permissions")
        assert resp.status_code == 200
        permissions = resp.json()
        assert permissions == []

    def test_user_no_roles_empty_permissions(self):
        """User with no roles has empty permissions."""
        user = create_user()
        resp = api_get(f"/api/users/{user['id']}/permissions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_permissions_nonexistent_user(self):
        resp = api_get("/api/users/nonexistent-id-12345/permissions")
        assert resp.status_code == 404

    def test_permission_includes_resource_info(self):
        """Each permission should include resource indicator."""
        user = create_user()
        indicator = f"https://perm-api-{uuid.uuid4().hex[:8]}.example.com"
        resource = create_resource(indicator=indicator)
        scope = create_scope(resource["id"], name=f"read-{uuid.uuid4().hex[:8]}", description="Read access")
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        resp = api_get(f"/api/users/{user['id']}/permissions")
        permissions = resp.json()
        assert len(permissions) == 1
        perm = permissions[0]
        assert perm["resourceId"] == resource["id"]
        assert perm["resourceIndicator"] == indicator
        assert perm["scopeId"] == scope["id"]
        assert perm["scopeName"] == scope["name"]
        assert perm["scopeDescription"] == "Read access"


# ════════════════════════════════════════════════════════════════════
# PART 10: Organizations CRUD
# ════════════════════════════════════════════════════════════════════


class TestOrganizationsCRUD:

    def test_create_organization(self):
        resp = api_post("/api/organizations", {
            "name": f"Acme Corp-{UNIQUE}",
            "description": "A great company",
        })
        assert resp.status_code == 201
        org = resp.json()
        assert org["name"] == f"Acme Corp-{UNIQUE}"
        assert org["description"] == "A great company"
        assert "id" in org
        assert "createdAt" in org

    def test_create_organization_default_description(self):
        resp = api_post("/api/organizations", {"name": f"Simple Org-{UNIQUE}"})
        assert resp.status_code == 201
        org = resp.json()
        assert org["description"] == ""

    def test_get_organization_by_id(self):
        org = create_organization()
        resp = api_get(f"/api/organizations/{org['id']}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == org["id"]

    def test_get_nonexistent_organization(self):
        resp = api_get("/api/organizations/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_organization(self):
        org = create_organization()
        resp = api_patch(f"/api/organizations/{org['id']}", {
            "name": f"Updated Org-{uuid.uuid4().hex[:8]}",
            "description": "Updated",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["description"] == "Updated"

    def test_update_nonexistent_organization(self):
        resp = api_patch("/api/organizations/nonexistent-id-12345", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_organization(self):
        org = create_organization()
        resp = api_delete(f"/api/organizations/{org['id']}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/organizations/{org['id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_organization(self):
        resp = api_delete("/api/organizations/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_list_organizations(self):
        org = create_organization()
        resp = api_get("/api/organizations", params={"page_size": 100})
        assert resp.status_code == 200
        orgs = resp.json()
        assert isinstance(orgs, list)
        ids = [o["id"] for o in orgs]
        assert org["id"] in ids

    def test_list_organizations_pagination(self):
        for i in range(3):
            create_organization()
        resp = api_get("/api/organizations", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        orgs = resp.json()
        assert len(orgs) <= 2
        assert "X-Total-Count" in resp.headers


# ════════════════════════════════════════════════════════════════════
# PART 11: Organization Members
# ════════════════════════════════════════════════════════════════════


class TestOrganizationMembers:

    def test_add_member_to_organization(self):
        org = create_organization()
        user = create_user()
        resp = api_post(f"/api/organizations/{org['id']}/members", {
            "userIds": [user["id"]],
        })
        assert resp.status_code == 201

        # Verify
        list_resp = api_get(f"/api/organizations/{org['id']}/members")
        assert list_resp.status_code == 200
        members = list_resp.json()
        member_ids = [m["id"] for m in members]
        assert user["id"] in member_ids

    def test_add_multiple_members(self):
        org = create_organization()
        user1 = create_user()
        user2 = create_user()
        resp = api_post(f"/api/organizations/{org['id']}/members", {
            "userIds": [user1["id"], user2["id"]],
        })
        assert resp.status_code == 201

        list_resp = api_get(f"/api/organizations/{org['id']}/members")
        members = list_resp.json()
        member_ids = [m["id"] for m in members]
        assert user1["id"] in member_ids
        assert user2["id"] in member_ids

    def test_add_member_idempotent(self):
        """Adding an existing member should succeed silently."""
        org = create_organization()
        user = create_user()
        resp1 = api_post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})
        assert resp2.status_code == 201

        # Should still be only one entry
        list_resp = api_get(f"/api/organizations/{org['id']}/members")
        members = list_resp.json()
        member_ids = [m["id"] for m in members]
        assert member_ids.count(user["id"]) == 1

    def test_add_member_nonexistent_org(self):
        user = create_user()
        resp = api_post("/api/organizations/nonexistent-id-12345/members", {
            "userIds": [user["id"]],
        })
        assert resp.status_code == 404

    def test_add_nonexistent_user_to_org(self):
        org = create_organization()
        resp = api_post(f"/api/organizations/{org['id']}/members", {
            "userIds": ["nonexistent-user-id"],
        })
        assert resp.status_code == 404

    def test_remove_member_from_organization(self):
        org = create_organization()
        user = create_user()
        api_post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})

        resp = api_delete(f"/api/organizations/{org['id']}/members/{user['id']}")
        assert resp.status_code == 204

        # Verify removal
        list_resp = api_get(f"/api/organizations/{org['id']}/members")
        member_ids = [m["id"] for m in list_resp.json()]
        assert user["id"] not in member_ids

    def test_remove_non_member(self):
        """Removing a user who is not a member should return 404."""
        org = create_organization()
        user = create_user()
        resp = api_delete(f"/api/organizations/{org['id']}/members/{user['id']}")
        assert resp.status_code == 404

    def test_list_members_nonexistent_org(self):
        resp = api_get("/api/organizations/nonexistent-id-12345/members")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Sign-in Experience
# ════════════════════════════════════════════════════════════════════


class TestSignInExperience:

    @pytest.fixture(autouse=True)
    def _restore_default_branding(self):
        yield
        try:
            api_patch("/api/sign-in-exp", {
                "branding": {
                    "logoUrl": "",
                    "darkLogoUrl": "",
                    "primaryColor": "#6C63FF",
                    "darkMode": False,
                },
            })
        except requests.RequestException:
            pass

    def test_get_default_sign_in_experience(self):
        resp = api_get("/api/sign-in-exp")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "branding" in data
        branding = data["branding"]
        assert "logoUrl" in branding
        assert "darkLogoUrl" in branding
        assert "primaryColor" in branding
        assert "darkMode" in branding

    def test_get_default_values(self):
        resp = api_get("/api/sign-in-exp")
        data = resp.json()
        assert data["id"] == "default"
        assert data["branding"]["primaryColor"] == "#6C63FF"
        assert data["branding"]["darkMode"] is False

    def test_update_sign_in_experience(self):
        resp = api_patch("/api/sign-in-exp", {
            "branding": {
                "logoUrl": "https://example.com/logo.png",
                "primaryColor": "#FF0000",
                "darkMode": True,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["branding"]["logoUrl"] == "https://example.com/logo.png"
        assert data["branding"]["primaryColor"] == "#FF0000"
        assert data["branding"]["darkMode"] is True

    def test_update_partial_branding(self):
        """Partial branding update should merge with existing."""
        # First set some values
        api_patch("/api/sign-in-exp", {
            "branding": {
                "logoUrl": "https://example.com/logo2.png",
                "darkLogoUrl": "https://example.com/dark2.png",
            },
        })
        # Now update only one field
        resp = api_patch("/api/sign-in-exp", {
            "branding": {
                "primaryColor": "#00FF00",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["branding"]["primaryColor"] == "#00FF00"
        # Previously set values should persist
        assert data["branding"]["logoUrl"] == "https://example.com/logo2.png"
        assert data["branding"]["darkLogoUrl"] == "https://example.com/dark2.png"

    def test_get_after_update(self):
        """GET should return the updated values."""
        api_patch("/api/sign-in-exp", {
            "branding": {"primaryColor": "#AABBCC"},
        })
        resp = api_get("/api/sign-in-exp")
        assert resp.status_code == 200
        assert resp.json()["branding"]["primaryColor"] == "#AABBCC"


# ════════════════════════════════════════════════════════════════════
# PART 13: Audit Logs
# ════════════════════════════════════════════════════════════════════


class TestAuditLogs:

    def test_user_created_generates_log(self):
        user = create_user()
        resp = api_get("/api/logs", params={"userId": user["id"], "type": "User.Created"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        log = logs[0]
        assert log["type"] == "User.Created"
        assert log["userId"] == user["id"]
        assert "id" in log
        assert "createdAt" in log
        assert "payload" in log

    def test_user_updated_generates_log(self):
        user = create_user()
        api_patch(f"/api/users/{user['id']}", {"name": "Updated"})
        resp = api_get("/api/logs", params={"userId": user["id"], "type": "User.Updated"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        found = [l for l in logs if l["type"] == "User.Updated"]
        assert len(found) >= 1

    def test_user_deleted_generates_log(self):
        user = create_user()
        user_id = user["id"]
        api_delete(f"/api/users/{user_id}")
        resp = api_get("/api/logs", params={"userId": user_id, "type": "User.Deleted"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        found = [l for l in logs if l["type"] == "User.Deleted"]
        assert len(found) >= 1

    def test_role_assigned_generates_log(self):
        user = create_user()
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        resp = api_get("/api/logs", params={"type": "Role.User.Assigned"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1

    def test_role_unassigned_generates_log(self):
        user = create_user()
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})
        api_delete(f"/api/roles/{role['id']}/users/{user['id']}")
        resp = api_get("/api/logs", params={"type": "Role.User.Unassigned"})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1

    def test_get_log_by_id(self):
        user = create_user()
        resp = api_get("/api/logs", params={"userId": user["id"], "type": "User.Created"})
        logs = resp.json()
        assert len(logs) >= 1
        log_id = logs[0]["id"]

        detail_resp = api_get(f"/api/logs/{log_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == log_id

    def test_get_nonexistent_log(self):
        resp = api_get("/api/logs/nonexistent-log-id-12345")
        assert resp.status_code == 404

    def test_list_logs_pagination(self):
        # Create several users to generate logs
        for i in range(3):
            create_user()
        resp = api_get("/api/logs", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) <= 2
        assert "X-Total-Count" in resp.headers

    def test_list_logs_filter_by_type(self):
        create_user()
        resp = api_get("/api/logs", params={"type": "User.Created"})
        assert resp.status_code == 200
        logs = resp.json()
        for log in logs:
            assert log["type"] == "User.Created"

    def test_list_logs_filter_by_user_id(self):
        user = create_user()
        resp = api_get("/api/logs", params={"userId": user["id"]})
        assert resp.status_code == 200
        logs = resp.json()
        for log in logs:
            assert log["userId"] == user["id"]


# ════════════════════════════════════════════════════════════════════
# PART 14: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_user_removes_role_assignments(self):
        """Deleting a user removes their role assignments."""
        user = create_user()
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        api_delete(f"/api/users/{user['id']}")

        # Role should have no users now
        list_resp = api_get(f"/api/roles/{role['id']}/users")
        user_ids = [u["id"] for u in list_resp.json()]
        assert user["id"] not in user_ids

    def test_delete_user_removes_org_memberships(self):
        """Deleting a user removes their org memberships."""
        user = create_user()
        org = create_organization()
        api_post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})

        api_delete(f"/api/users/{user['id']}")

        # Org should not have this member
        list_resp = api_get(f"/api/organizations/{org['id']}/members")
        member_ids = [m["id"] for m in list_resp.json()]
        assert user["id"] not in member_ids

    def test_delete_role_removes_user_assignments(self):
        """Deleting a role removes all user-role assignments."""
        user = create_user()
        role = create_role(role_type="User")
        api_post(f"/api/roles/{role['id']}/users", {"userIds": [user["id"]]})

        api_delete(f"/api/roles/{role['id']}")

        # User should no longer have this role
        roles_resp = api_get(f"/api/users/{user['id']}/roles")
        role_ids = [r["id"] for r in roles_resp.json()]
        assert role["id"] not in role_ids

    def test_delete_role_removes_scope_assignments(self):
        """Deleting a role removes all role-scope assignments."""
        role = create_role()
        resource = create_resource()
        scope = create_scope(resource["id"])
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})

        api_delete(f"/api/roles/{role['id']}")
        # Role is gone, no direct way to verify scope assignment gone
        # but scope should still exist
        scope_resp = api_get(f"/api/resources/{resource['id']}/scopes")
        scope_ids = [s["id"] for s in scope_resp.json()]
        assert scope["id"] in scope_ids

    def test_delete_resource_removes_scopes(self):
        """Deleting a resource removes all its scopes."""
        resource = create_resource()
        scope = create_scope(resource["id"])

        api_delete(f"/api/resources/{resource['id']}")

        # Resource and scope should be gone
        resp = api_get(f"/api/resources/{resource['id']}")
        assert resp.status_code == 404

    def test_delete_resource_removes_scope_from_roles(self):
        """Deleting a resource removes scopes from roles."""
        resource = create_resource()
        scope = create_scope(resource["id"])
        role = create_role()
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})

        api_delete(f"/api/resources/{resource['id']}")

        # Role should no longer have that scope
        list_resp = api_get(f"/api/roles/{role['id']}/scopes")
        scope_ids = [s["id"] for s in list_resp.json()]
        assert scope["id"] not in scope_ids

    def test_delete_scope_removes_from_roles(self):
        """Deleting a scope removes it from roles."""
        resource = create_resource()
        scope = create_scope(resource["id"])
        role = create_role()
        api_post(f"/api/roles/{role['id']}/scopes", {"scopeIds": [scope["id"]]})

        api_delete(f"/api/resources/{resource['id']}/scopes/{scope['id']}")

        # Role should no longer have that scope
        list_resp = api_get(f"/api/roles/{role['id']}/scopes")
        scope_ids = [s["id"] for s in list_resp.json()]
        assert scope["id"] not in scope_ids

    def test_delete_organization_removes_memberships(self):
        """Deleting an org removes all memberships."""
        org = create_organization()
        user = create_user()
        api_post(f"/api/organizations/{org['id']}/members", {"userIds": [user["id"]]})

        api_delete(f"/api/organizations/{org['id']}")

        # Org should be gone
        resp = api_get(f"/api/organizations/{org['id']}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_user_custom_data_default_empty_object(self):
        """customData defaults to {} if not provided."""
        user = create_user()
        assert user["customData"] == {}

    def test_user_custom_data_json(self):
        """customData accepts arbitrary JSON."""
        user = create_user(customData={"nested": {"key": [1, 2, 3]}})
        assert user["customData"] == {"nested": {"key": [1, 2, 3]}}

    def test_application_client_secret_length(self):
        """clientSecret should be exactly 32 characters."""
        resp = api_post("/api/applications", {
            "name": f"SecretLen-{uuid.uuid4().hex[:8]}",
            "type": "SPA",
        })
        app = resp.json()
        assert len(app["clientSecret"]) == 32

    def test_application_client_id_is_uuid_format(self):
        """clientId should be UUID-like (at least 32 chars with dashes)."""
        resp = api_post("/api/applications", {
            "name": f"UUIDCheck-{uuid.uuid4().hex[:8]}",
            "type": "SPA",
        })
        app = resp.json()
        # UUID format: 8-4-4-4-12 = 36 chars or 32 hex chars without dashes
        assert len(app["clientId"]) >= 32

    def test_ids_are_strings(self):
        """All entity IDs should be strings."""
        user = create_user()
        assert isinstance(user["id"], str)

        resource = create_resource()
        assert isinstance(resource["id"], str)

        role = create_role()
        assert isinstance(role["id"], str)

    def test_created_at_is_iso_format(self):
        """createdAt should be ISO 8601 format."""
        user = create_user()
        created_at = user["createdAt"]
        assert "T" in created_at  # ISO 8601 has T separator
        assert len(created_at) >= 19  # At minimum YYYY-MM-DDTHH:MM:SS

    def test_empty_lists_on_fresh_start(self):
        """List endpoints should work even if empty (initial state handled by pagination)."""
        # These should all return 200 with valid response
        resp = api_get("/api/users")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = api_get("/api/applications")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = api_get("/api/resources")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = api_get("/api/roles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = api_get("/api/organizations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_pagination_page_beyond_results(self):
        """Requesting a page beyond available results returns empty array."""
        resp = api_get("/api/users", params={"page": 9999, "page_size": 20})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_user_does_not_overwrite_unset_fields(self):
        """PATCH should only update provided fields."""
        user = create_user(email="original@example.com", name="Original Name")
        # Update only name
        resp = api_patch(f"/api/users/{user['id']}", {"name": "New Name"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "New Name"
        assert updated["email"] == "original@example.com"  # Should remain unchanged
