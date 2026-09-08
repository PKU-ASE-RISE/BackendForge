"""
BackendForge — Comprehensive Correctness Tests for Gotify Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# User keys — the key IS the username (auto-created on first request)
ADMIN_KEY = "admin-user"  # First user auto-created becomes admin
USER_KEY = f"regular-user-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"another-user-{uuid.uuid4().hex[:8]}"

ADMIN_HEADERS = {
    "X-Gotify-Key": ADMIN_KEY,
    "Content-Type": "application/json",
}

USER_HEADERS = {
    "X-Gotify-Key": USER_KEY,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
    "X-Gotify-Key": USER2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, params=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def missing_id(items):
    used_ids = {item["id"] for item in items}
    return next(candidate for candidate in range(999999, 999999 + len(used_ids) + 1) if candidate not in used_ids)


# ── Setup: ensure admin user is created first ──

def ensure_admin():
    """Make a request with ADMIN_KEY to ensure the admin user is auto-created first."""
    api_get("/current/user", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health & Version (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealthAndVersion:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "health" in data
        assert "database" in data

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200

    def test_version_endpoint(self):
        resp = requests.get(f"{BASE_URL}/version", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "commit" in data
        assert "buildDate" in data

    def test_version_no_auth_required(self):
        """Version endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/version", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Gotify-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/applications", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_messages(self):
        resp = requests.get(f"{BASE_URL}/messages", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_clients(self):
        resp = requests.get(f"{BASE_URL}/clients", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_user(self):
        """A new key should auto-create a user."""
        ensure_admin()
        new_key = f"new-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": new_key, "Content-Type": "application/json"}
        resp = api_get("/current/user", headers=headers)
        assert resp.status_code == 200
        user = resp.json()
        assert user["name"] == new_key
        assert user["id"] is not None

    def test_first_user_is_admin(self):
        """The first auto-created user (ADMIN_KEY) should be admin."""
        ensure_admin()
        resp = api_get("/current/user", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["admin"] is True, f"First user should be admin, got {user}"

    def test_subsequent_user_is_not_admin(self):
        """Users created after the first should not be admin."""
        ensure_admin()
        resp = api_get("/current/user", headers=USER_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["admin"] is False, f"Subsequent user should not be admin, got {user}"


# ════════════════════════════════════════════════════════════════════
# PART 3: Application CRUD
# ════════════════════════════════════════════════════════════════════


class TestApplicationCRUD:

    def test_create_application(self):
        ensure_admin()
        resp = api_post("/applications", {"name": f"TestApp-{UNIQUE}", "description": "A test app"})
        assert resp.status_code == 200
        app = resp.json()
        assert app["name"] == f"TestApp-{UNIQUE}"
        assert app["description"] == "A test app"
        assert "id" in app
        assert "token" in app
        assert len(app["token"]) >= 15, f"Token too short: {app['token']}"

    def test_create_application_minimal(self):
        ensure_admin()
        resp = api_post("/applications", {"name": f"MinApp-{UNIQUE}"})
        assert resp.status_code == 200
        app = resp.json()
        assert app["name"] == f"MinApp-{UNIQUE}"
        assert app["description"] == ""  # default empty

    def test_list_applications(self):
        ensure_admin()
        # Create one first
        api_post("/applications", {"name": f"ListApp-{UNIQUE}"})
        resp = api_get("/applications")
        assert resp.status_code == 200
        apps = resp.json()
        assert isinstance(apps, list)
        assert len(apps) >= 1
        names = [a["name"] for a in apps]
        assert f"ListApp-{UNIQUE}" in names

    def test_update_application(self):
        ensure_admin()
        create_resp = api_post("/applications", {"name": f"UpdateApp-{UNIQUE}"})
        app = create_resp.json()
        app_id = app["id"]
        original_token = app["token"]

        resp = api_put(f"/applications/{app_id}", {
            "name": f"UpdatedApp-{UNIQUE}",
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdatedApp-{UNIQUE}"
        assert updated["description"] == "Updated desc"
        # Token should NOT change on update
        assert updated["token"] == original_token

    def test_delete_application(self):
        ensure_admin()
        create_resp = api_post("/applications", {"name": f"DelApp-{UNIQUE}"})
        app = create_resp.json()
        app_id = app["id"]

        resp = api_delete(f"/applications/{app_id}")
        assert resp.status_code == 200

        # Should no longer appear in list
        list_resp = api_get("/applications")
        app_ids = [a["id"] for a in list_resp.json()]
        assert app_id not in app_ids

    def test_delete_nonexistent_application(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-app-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_delete("/applications/999999", headers=headers)
        assert resp.status_code == 404

    def test_update_nonexistent_application(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-app-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_put("/applications/999999", {"name": "ghost"}, headers=headers)
        assert resp.status_code == 404

    def test_duplicate_application_name(self):
        """Same user cannot have two apps with the same name."""
        ensure_admin()
        name = f"DupApp-{UNIQUE}"
        resp1 = api_post("/applications", {"name": name})
        assert resp1.status_code == 200
        resp2 = api_post("/applications", {"name": name})
        assert resp2.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 4: Client CRUD
# ════════════════════════════════════════════════════════════════════


class TestClientCRUD:

    def test_create_client(self):
        ensure_admin()
        resp = api_post("/clients", {"name": f"TestClient-{UNIQUE}"})
        assert resp.status_code == 200
        client = resp.json()
        assert client["name"] == f"TestClient-{UNIQUE}"
        assert "id" in client
        assert "token" in client
        assert len(client["token"]) >= 15, f"Client token too short: {client['token']}"

    def test_list_clients(self):
        ensure_admin()
        api_post("/clients", {"name": f"ListClient-{UNIQUE}"})
        resp = api_get("/clients")
        assert resp.status_code == 200
        clients = resp.json()
        assert isinstance(clients, list)
        assert len(clients) >= 1

    def test_update_client(self):
        ensure_admin()
        create_resp = api_post("/clients", {"name": f"UpdateClient-{UNIQUE}"})
        client = create_resp.json()
        client_id = client["id"]
        original_token = client["token"]

        resp = api_put(f"/clients/{client_id}", {"name": f"RenamedClient-{UNIQUE}"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"RenamedClient-{UNIQUE}"
        # Token should NOT change on update
        assert updated["token"] == original_token

    def test_delete_client(self):
        ensure_admin()
        create_resp = api_post("/clients", {"name": f"DelClient-{UNIQUE}"})
        client = create_resp.json()
        client_id = client["id"]

        resp = api_delete(f"/clients/{client_id}")
        assert resp.status_code == 200

        # Should no longer appear
        list_resp = api_get("/clients")
        ids = [c["id"] for c in list_resp.json()]
        assert client_id not in ids

    def test_delete_nonexistent_client(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-client-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_delete("/clients/999999", headers=headers)
        assert resp.status_code == 404

    def test_update_nonexistent_client(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-client-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_put("/clients/999999", {"name": "ghost"}, headers=headers)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Message CRUD
# ════════════════════════════════════════════════════════════════════


class TestMessageCRUD:

    def test_create_message(self):
        ensure_admin()
        # Create an app first
        app_resp = api_post("/applications", {"name": f"MsgApp-{UNIQUE}-create"})
        app = app_resp.json()
        app_id = app["id"]

        resp = api_post("/messages", {
            "message": f"Hello {UNIQUE}",
            "title": "Test Title",
            "priority": 5,
            "appid": app_id,
        })
        assert resp.status_code == 200
        msg = resp.json()
        assert msg["message"] == f"Hello {UNIQUE}"
        assert msg["title"] == "Test Title"
        assert msg["priority"] == 5
        assert msg["appid"] == app_id
        assert "id" in msg
        assert "date" in msg

    def test_create_message_minimal(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"MsgApp-{UNIQUE}-minimal"})
        app = app_resp.json()
        app_id = app["id"]

        resp = api_post("/messages", {"message": "Just text", "appid": app_id})
        assert resp.status_code == 200
        msg = resp.json()
        assert msg["message"] == "Just text"

    def test_create_message_with_extras(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"MsgApp-{UNIQUE}-extras"})
        app = app_resp.json()
        app_id = app["id"]

        extras = {"client::display": {"contentType": "text/markdown"}}
        resp = api_post("/messages", {
            "message": "With extras",
            "appid": app_id,
            "extras": extras,
        })
        assert resp.status_code == 200
        msg = resp.json()
        assert msg.get("extras") == extras

    def test_create_message_invalid_appid(self):
        """Creating a message with an invalid appid should fail."""
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-app-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_post("/messages", {"message": "Bad app", "appid": 999999}, headers=headers)
        assert resp.status_code == 400

    def test_list_messages(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"MsgApp-{UNIQUE}-list"})
        app = app_resp.json()
        app_id = app["id"]

        # Create a few messages
        for i in range(3):
            api_post("/messages", {"message": f"Msg {i} {UNIQUE}", "appid": app_id})

        resp = api_get("/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert "paging" in data
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) >= 3

    def test_list_messages_paging_structure(self):
        """Verify the paging object has required fields."""
        ensure_admin()
        resp = api_get("/messages")
        assert resp.status_code == 200
        data = resp.json()
        paging = data["paging"]
        assert "size" in paging
        assert "since" in paging
        assert "limit" in paging

    def test_delete_single_message(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"MsgApp-{UNIQUE}-delsingle"})
        app = app_resp.json()
        app_id = app["id"]

        msg_resp = api_post("/messages", {"message": "To delete", "appid": app_id})
        msg_id = msg_resp.json()["id"]

        resp = api_delete(f"/messages/{msg_id}")
        assert resp.status_code == 200

        # Verify it's gone
        msgs_resp = api_get("/messages")
        msg_ids = [m["id"] for m in msgs_resp.json()["messages"]]
        assert msg_id not in msg_ids

    def test_delete_nonexistent_message(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-message-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_delete("/messages/999999", headers=headers)
        assert resp.status_code == 404

    def test_delete_all_messages(self):
        ensure_admin()
        # Use a separate user so we don't affect other tests' messages
        key = f"delall-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        # Create app and messages
        app_resp = api_post("/applications", {"name": f"DelAllApp-{UNIQUE}"}, headers=headers)
        app = app_resp.json()
        app_id = app["id"]

        api_post("/messages", {"message": "Msg A", "appid": app_id}, headers=headers)
        api_post("/messages", {"message": "Msg B", "appid": app_id}, headers=headers)

        # Delete all
        resp = api_delete("/messages", headers=headers)
        assert resp.status_code == 200

        # Verify empty
        msgs_resp = api_get("/messages", headers=headers)
        assert len(msgs_resp.json()["messages"]) == 0


# ════════════════════════════════════════════════════════════════════
# PART 6: Application Messages
# ════════════════════════════════════════════════════════════════════


class TestApplicationMessages:

    def test_get_app_messages(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"AppMsg-{UNIQUE}-get"})
        app = app_resp.json()
        app_id = app["id"]

        api_post("/messages", {"message": "App msg 1", "appid": app_id})
        api_post("/messages", {"message": "App msg 2", "appid": app_id})

        resp = api_get(f"/applications/{app_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert "paging" in data
        assert len(data["messages"]) >= 2
        # All messages should belong to this app
        for msg in data["messages"]:
            assert msg["appid"] == app_id

    def test_get_app_messages_nonexistent_app(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-app-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_get("/applications/999999/messages", headers=headers)
        assert resp.status_code == 404

    def test_delete_app_messages(self):
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"AppMsg-{UNIQUE}-del"})
        app = app_resp.json()
        app_id = app["id"]

        api_post("/messages", {"message": "To be wiped", "appid": app_id})

        resp = api_delete(f"/applications/{app_id}/messages")
        assert resp.status_code == 200

        # Messages for this app should be gone
        msgs_resp = api_get(f"/applications/{app_id}/messages")
        assert len(msgs_resp.json()["messages"]) == 0

    def test_delete_app_messages_nonexistent_app(self):
        ensure_admin()
        headers = {"X-Gotify-Key": f"missing-app-{uuid.uuid4().hex}", "Content-Type": "application/json"}
        resp = api_delete("/applications/999999/messages", headers=headers)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: User Management (Admin)
# ════════════════════════════════════════════════════════════════════


class TestUserManagement:

    def test_list_users_as_admin(self):
        ensure_admin()
        resp = api_get("/users", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1

    def test_list_users_as_non_admin(self):
        """Non-admin should get 403."""
        ensure_admin()
        # Trigger user creation
        api_get("/current/user", headers=USER_HEADERS)
        resp = api_get("/users", headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_create_user_as_admin(self):
        ensure_admin()
        name = f"created-{UNIQUE}"
        resp = api_post("/users", {
            "name": name,
            "pass": "secret123",
            "admin": False,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["name"] == name
        assert user["admin"] is False
        assert "id" in user

    def test_create_user_as_non_admin(self):
        """Non-admin should get 403."""
        ensure_admin()
        api_get("/current/user", headers=USER_HEADERS)
        resp = api_post("/users", {
            "name": f"hack-{UNIQUE}",
            "pass": "hacker",
            "admin": True,
        }, headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_get_user_by_id(self):
        ensure_admin()
        # Create a user first
        create_resp = api_post("/users", {
            "name": f"getby-{UNIQUE}",
            "pass": "pass123",
            "admin": False,
        }, headers=ADMIN_HEADERS)
        user = create_resp.json()
        user_id = user["id"]

        resp = api_get(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == f"getby-{UNIQUE}"

    def test_get_nonexistent_user(self):
        ensure_admin()
        users = api_get("/users", headers=ADMIN_HEADERS).json()
        user_id = missing_id(users)
        resp = api_get(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_update_user(self):
        ensure_admin()
        create_resp = api_post("/users", {
            "name": f"toupdate-{UNIQUE}",
            "pass": "pass123",
            "admin": False,
        }, headers=ADMIN_HEADERS)
        user = create_resp.json()
        user_id = user["id"]

        resp = api_put(f"/users/{user_id}", {
            "name": f"updated-{UNIQUE}",
            "admin": True,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"updated-{UNIQUE}"
        assert updated["admin"] is True

    def test_delete_user(self):
        ensure_admin()
        create_resp = api_post("/users", {
            "name": f"todelete-{UNIQUE}",
            "pass": "pass123",
            "admin": False,
        }, headers=ADMIN_HEADERS)
        user = create_resp.json()
        user_id = user["id"]

        resp = api_delete(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Verify gone
        get_resp = api_get(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_cannot_delete_self(self):
        """Admin cannot delete their own account."""
        ensure_admin()
        me = api_get("/current/user", headers=ADMIN_HEADERS).json()
        my_id = me["id"]

        resp = api_delete(f"/users/{my_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_duplicate_username(self):
        """Cannot create two users with the same name."""
        ensure_admin()
        name = f"dupuser-{UNIQUE}"
        resp1 = api_post("/users", {"name": name, "pass": "p1", "admin": False}, headers=ADMIN_HEADERS)
        assert resp1.status_code == 200
        resp2 = api_post("/users", {"name": name, "pass": "p2", "admin": False}, headers=ADMIN_HEADERS)
        assert resp2.status_code == 400

    def test_get_current_user(self):
        ensure_admin()
        resp = api_get("/current/user", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert "id" in user
        assert "name" in user
        assert "admin" in user


# ════════════════════════════════════════════════════════════════════
# PART 8: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_application_isolation(self):
        """User A's apps are not visible to User B."""
        ensure_admin()
        # User A creates an app
        app_name = f"IsoApp-{UNIQUE}"
        api_post("/applications", {"name": app_name}, headers=ADMIN_HEADERS)

        # User B should not see it
        resp = api_get("/applications", headers=USER_HEADERS)
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert app_name not in names

    def test_client_isolation(self):
        """User A's clients are not visible to User B."""
        ensure_admin()
        client_name = f"IsoClient-{UNIQUE}"
        api_post("/clients", {"name": client_name}, headers=ADMIN_HEADERS)

        resp = api_get("/clients", headers=USER_HEADERS)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert client_name not in names

    def test_message_isolation(self):
        """User A's messages are not visible to User B."""
        ensure_admin()
        # Admin creates app + message
        app_resp = api_post("/applications", {"name": f"IsoMsgApp-{UNIQUE}"}, headers=ADMIN_HEADERS)
        app_id = app_resp.json()["id"]
        api_post("/messages", {"message": f"Secret-{UNIQUE}", "appid": app_id}, headers=ADMIN_HEADERS)

        # User B should not see it
        resp = api_get("/messages", headers=USER_HEADERS)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        texts = [m["message"] for m in messages]
        assert f"Secret-{UNIQUE}" not in texts

    def test_cannot_delete_other_users_app(self):
        """User B cannot delete User A's application (returns 404)."""
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"ProtectedApp-{UNIQUE}"}, headers=ADMIN_HEADERS)
        app_id = app_resp.json()["id"]

        resp = api_delete(f"/applications/{app_id}", headers=USER_HEADERS)
        assert resp.status_code == 404

    def test_cannot_delete_other_users_message(self):
        """User B cannot delete User A's message (returns 404)."""
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"ProtectedMsgApp-{UNIQUE}"}, headers=ADMIN_HEADERS)
        app_id = app_resp.json()["id"]
        msg_resp = api_post("/messages", {"message": "Protected", "appid": app_id}, headers=ADMIN_HEADERS)
        msg_id = msg_resp.json()["id"]

        resp = api_delete(f"/messages/{msg_id}", headers=USER_HEADERS)
        assert resp.status_code == 404

    def test_cannot_access_other_users_app_messages(self):
        """User B cannot GET messages for User A's app (returns 404)."""
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"OtherAppMsg-{UNIQUE}"}, headers=ADMIN_HEADERS)
        app_id = app_resp.json()["id"]

        resp = api_get(f"/applications/{app_id}/messages", headers=USER_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Pagination (Messages)
# ════════════════════════════════════════════════════════════════════


class TestPagination:

    def test_limit_parameter(self):
        """Limit should restrict the number of messages returned."""
        ensure_admin()
        # Create app and some messages
        key = f"pag-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"PagApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"Pag msg {i}", "appid": app_id}, headers=headers)

        resp = api_get("/messages", params={"limit": 3}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) <= 3
        assert data["paging"]["limit"] == 3

    def test_since_parameter(self):
        """Since should return messages with ID < since value."""
        ensure_admin()
        key = f"since-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"SinceApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        # Create messages
        msg_ids = []
        for i in range(5):
            r = api_post("/messages", {"message": f"Since msg {i}", "appid": app_id}, headers=headers)
            msg_ids.append(r.json()["id"])

        # Get messages since the 3rd message (should get messages with id < msg_ids[2])
        since_id = msg_ids[2]
        resp = api_get("/messages", params={"since": since_id}, headers=headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        for msg in messages:
            assert msg["id"] < since_id, f"Message id {msg['id']} should be < since={since_id}"

    def test_messages_ordered_newest_first(self):
        """Messages should be returned in descending order by ID."""
        ensure_admin()
        key = f"order-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"OrderApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"Order msg {i}", "appid": app_id}, headers=headers)

        resp = api_get("/messages", headers=headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        if len(messages) >= 2:
            ids = [m["id"] for m in messages]
            assert ids == sorted(ids, reverse=True), f"Messages not in descending order: {ids}"

    def test_paging_next_field(self):
        """When there are more messages, paging.next should be non-empty."""
        ensure_admin()
        key = f"next-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"NextApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"Next msg {i}", "appid": app_id}, headers=headers)

        resp = api_get("/messages", params={"limit": 2}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # With 5 messages and limit=2, there should be more
        assert len(data["messages"]) == 2
        paging = data["paging"]
        assert paging["size"] == 2
        # next should be non-empty since there are more messages
        assert paging.get("next", "") != "", "paging.next should point to next page"

    def test_paging_size_field(self):
        """paging.size should reflect the actual number of messages returned."""
        ensure_admin()
        key = f"size-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"SizeApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        for i in range(3):
            api_post("/messages", {"message": f"Size msg {i}", "appid": app_id}, headers=headers)

        resp = api_get("/messages", params={"limit": 10}, headers=headers)
        data = resp.json()
        assert data["paging"]["size"] == len(data["messages"])

    def test_app_messages_pagination(self):
        """GET /applications/{id}/messages should also support limit and since."""
        ensure_admin()
        key = f"apppag-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"AppPagApp-{UNIQUE}"}, headers=headers)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"AppPag msg {i}", "appid": app_id}, headers=headers)

        resp = api_get(f"/applications/{app_id}/messages", params={"limit": 2}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) <= 2
        assert "paging" in data


# ════════════════════════════════════════════════════════════════════
# PART 10: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_app_deletes_messages(self):
        """Rule 5: Deleting an application should delete all its messages."""
        ensure_admin()
        key = f"cascade-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}

        app_resp = api_post("/applications", {"name": f"CascadeApp-{UNIQUE}"}, headers=headers)
        app = app_resp.json()
        app_id = app["id"]

        # Create messages for this app
        msg_ids = []
        for i in range(3):
            r = api_post("/messages", {"message": f"Cascade msg {i}", "appid": app_id}, headers=headers)
            msg_ids.append(r.json()["id"])

        # Delete app
        resp = api_delete(f"/applications/{app_id}", headers=headers)
        assert resp.status_code == 200

        # All messages should be gone
        msgs_resp = api_get("/messages", headers=headers)
        remaining_ids = [m["id"] for m in msgs_resp.json()["messages"]]
        for mid in msg_ids:
            assert mid not in remaining_ids, f"Message {mid} should be deleted with app"

    def test_delete_user_deletes_everything(self):
        """Rule 6: Deleting a user should delete their apps, clients, and messages."""
        ensure_admin()
        # Create a user
        name = f"cascade-del-{UNIQUE}"
        create_resp = api_post("/users", {
            "name": name, "pass": "pass", "admin": False,
        }, headers=ADMIN_HEADERS)
        user = create_resp.json()
        user_id = user["id"]

        # Act as that user
        user_headers = {"X-Gotify-Key": name, "Content-Type": "application/json"}

        # Create app, client, message
        app_resp = api_post("/applications", {"name": "UserApp"}, headers=user_headers)
        app_id = app_resp.json()["id"]
        client_resp = api_post("/clients", {"name": "UserClient"}, headers=user_headers)
        api_post("/messages", {"message": "UserMsg", "appid": app_id}, headers=user_headers)

        # Delete the user (as admin)
        resp = api_delete(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Verify user is gone
        get_resp = api_get(f"/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_create_message_without_appid_fails(self):
        """Message must have appid."""
        ensure_admin()
        resp = api_post("/messages", {"message": "No app"})
        assert resp.status_code == 400

    def test_message_default_priority_zero(self):
        """If no priority specified, default to 0."""
        ensure_admin()
        app_resp = api_post("/applications", {"name": f"DefPriApp-{UNIQUE}"})
        app_id = app_resp.json()["id"]

        resp = api_post("/messages", {"message": "No priority", "appid": app_id})
        assert resp.status_code == 200
        msg = resp.json()
        assert msg.get("priority", 0) == 0

    def test_application_default_priority(self):
        """Application with defaultPriority."""
        ensure_admin()
        resp = api_post("/applications", {
            "name": f"PriorityApp-{UNIQUE}",
            "defaultPriority": 7,
        })
        assert resp.status_code == 200
        app = resp.json()
        assert app.get("defaultPriority") == 7

    def test_empty_messages_list(self):
        """New user should have empty message list."""
        ensure_admin()
        key = f"empty-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}
        resp = api_get("/messages", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["paging"]["size"] == 0

    def test_empty_applications_list(self):
        """New user should have empty applications list."""
        ensure_admin()
        key = f"emptyapps-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}
        resp = api_get("/applications", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_clients_list(self):
        """New user should have empty clients list."""
        ensure_admin()
        key = f"emptyclients-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Gotify-Key": key, "Content-Type": "application/json"}
        resp = api_get("/clients", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_message_appid_must_belong_to_user(self):
        """Cannot create message for another user's app."""
        ensure_admin()
        # Admin creates an app
        app_resp = api_post("/applications", {"name": f"OwnedApp-{UNIQUE}"}, headers=ADMIN_HEADERS)
        admin_app_id = app_resp.json()["id"]

        # Regular user tries to use admin's app id
        resp = api_post("/messages", {"message": "Stolen", "appid": admin_app_id}, headers=USER_HEADERS)
        assert resp.status_code == 400
