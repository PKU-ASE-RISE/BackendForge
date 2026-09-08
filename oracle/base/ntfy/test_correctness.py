"""
BackendForge — Comprehensive Correctness Tests for Ntfy Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

UNIQUE = uuid.uuid4().hex[:8]

# Admin user (first user auto-created)
ADMIN_USER_ID = "admin-user"
ADMIN_TOKEN = "admin-token"
ADMIN_HEADERS = {
    "X-User-Id": ADMIN_USER_ID,
    "X-Token": ADMIN_TOKEN,
    "Content-Type": "application/json",
}

# Regular user
REG_USER_ID = f"regular-user-{UNIQUE}"
REG_TOKEN = f"regular-token-{UNIQUE}"
REG_HEADERS = {
    "X-User-Id": REG_USER_ID,
    "X-Token": REG_TOKEN,
    "Content-Type": "application/json",
}

# Another regular user
REG2_USER_ID = f"regular2-user-{UNIQUE}"
REG2_TOKEN = f"regular2-token-{UNIQUE}"
REG2_HEADERS = {
    "X-User-Id": REG2_USER_ID,
    "X-Token": REG2_TOKEN,
    "Content-Type": "application/json",
}


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or ADMIN_HEADERS, timeout=30)


def ensure_admin():
    """Make a request with ADMIN headers to ensure admin user is auto-created first."""
    api_get("/api/health")
    api_get("/api/topics", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_no_auth_required(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_headers_returns_401(self):
        ensure_admin()
        resp = requests.get(f"{BASE_URL}/api/topics", timeout=30)
        assert resp.status_code == 401

    def test_missing_user_id_returns_401(self):
        ensure_admin()
        resp = requests.get(
            f"{BASE_URL}/api/topics",
            headers={"X-Token": "some-token", "Content-Type": "application/json"},
            timeout=30
        )
        assert resp.status_code == 401

    def test_missing_token_returns_401(self):
        ensure_admin()
        resp = requests.get(
            f"{BASE_URL}/api/topics",
            headers={"X-User-Id": "some-user", "Content-Type": "application/json"},
            timeout=30
        )
        assert resp.status_code == 401

    def test_auto_create_user_on_first_request(self):
        ensure_admin()
        resp = api_get("/api/topics", headers=REG_HEADERS)
        assert resp.status_code == 200

    def test_first_user_is_admin(self):
        ensure_admin()
        resp = api_get("/api/users", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        admin_user = next((u for u in users if u["username"] == ADMIN_USER_ID), None)
        assert admin_user is not None
        assert admin_user["admin"] is True

    def test_subsequent_user_is_not_admin(self):
        ensure_admin()
        # Trigger creation
        api_get("/api/topics", headers=REG_HEADERS)
        # Try admin endpoint
        resp = api_get("/api/users", headers=REG_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 3: User Management (admin only)
# ════════════════════════════════════════════════════════════════════


class TestUserManagement:

    def test_list_users_as_admin(self):
        ensure_admin()
        resp = api_get("/api/users", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1

    def test_list_users_as_non_admin(self):
        ensure_admin()
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_get("/api/users", headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_create_user(self):
        ensure_admin()
        username = f"newuser-{UNIQUE}"
        resp = api_post("/api/users", {"username": username, "admin": False}, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        user = resp.json()
        assert user["username"] == username
        assert user["admin"] is False
        assert "id" in user

    def test_create_duplicate_user(self):
        ensure_admin()
        username = f"dupuser-{UNIQUE}"
        resp1 = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        assert resp1.status_code == 201
        resp2 = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        assert resp2.status_code == 409

    def test_get_user_by_id(self):
        ensure_admin()
        username = f"getuser-{UNIQUE}"
        create_resp = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_get(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["username"] == username

    def test_get_nonexistent_user(self):
        ensure_admin()
        resp = api_get("/api/users/999999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_update_user(self):
        ensure_admin()
        username = f"updateuser-{UNIQUE}"
        create_resp = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_put(f"/api/users/{user_id}", {
            "username": f"updated-{UNIQUE}",
            "admin": True,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["username"] == f"updated-{UNIQUE}"
        assert resp.json()["admin"] is True

    def test_update_user_duplicate_username(self):
        ensure_admin()
        username1 = f"uu1-{UNIQUE}"
        username2 = f"uu2-{UNIQUE}"
        api_post("/api/users", {"username": username1}, headers=ADMIN_HEADERS)
        resp2 = api_post("/api/users", {"username": username2}, headers=ADMIN_HEADERS)
        user2_id = resp2.json()["id"]

        resp = api_put(f"/api/users/{user2_id}", {"username": username1}, headers=ADMIN_HEADERS)
        assert resp.status_code == 409

    def test_delete_user(self):
        ensure_admin()
        username = f"deluser-{UNIQUE}"
        create_resp = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_delete(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        get_resp = api_get(f"/api/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_cannot_delete_self(self):
        ensure_admin()
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin = next(u for u in users if u["username"] == ADMIN_USER_ID)

        resp = api_delete(f"/api/users/{admin['id']}", headers=ADMIN_HEADERS)
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 4: Token Management
# ════════════════════════════════════════════════════════════════════


class TestTokenManagement:

    def test_create_token(self):
        ensure_admin()
        resp = api_post("/api/tokens", {"label": "my-token"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        token = resp.json()
        assert "id" in token
        assert "token" in token
        assert token["label"] == "my-token"

    def test_create_token_with_expires(self):
        ensure_admin()
        resp = api_post("/api/tokens", {
            "label": "expiring",
            "expires": "2099-01-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        token = resp.json()
        assert token["expires"] is not None

    def test_list_tokens(self):
        ensure_admin()
        api_post("/api/tokens", {"label": f"list-tok-{UNIQUE}"}, headers=ADMIN_HEADERS)
        resp = api_get("/api/tokens", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        tokens = resp.json()
        assert isinstance(tokens, list)
        assert len(tokens) >= 1

    def test_update_token(self):
        ensure_admin()
        create_resp = api_post("/api/tokens", {"label": "original"}, headers=ADMIN_HEADERS)
        token_id = create_resp.json()["id"]

        resp = api_patch(f"/api/tokens/{token_id}", {"label": "renamed"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["label"] == "renamed"

    def test_delete_token(self):
        ensure_admin()
        create_resp = api_post("/api/tokens", {"label": "to-delete"}, headers=ADMIN_HEADERS)
        token_id = create_resp.json()["id"]

        resp = api_delete(f"/api/tokens/{token_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_delete_nonexistent_token(self):
        ensure_admin()
        resp = api_delete("/api/tokens/999999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_token_isolation(self):
        """User A cannot see User B's tokens."""
        ensure_admin()
        api_post("/api/tokens", {"label": "admin-only-tok"}, headers=ADMIN_HEADERS)
        api_get("/api/topics", headers=REG_HEADERS)

        resp = api_get("/api/tokens", headers=REG_HEADERS)
        assert resp.status_code == 200
        labels = [t["label"] for t in resp.json()]
        assert "admin-only-tok" not in labels


# ════════════════════════════════════════════════════════════════════
# PART 5: Topics
# ════════════════════════════════════════════════════════════════════


class TestTopics:

    def test_create_topic(self):
        ensure_admin()
        name = f"topic-{UNIQUE}"
        resp = api_post("/api/topics", {"name": name, "description": "Test topic"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        topic = resp.json()
        assert topic["name"] == name
        assert topic["description"] == "Test topic"
        assert "id" in topic

    def test_create_duplicate_topic(self):
        ensure_admin()
        name = f"dup-topic-{UNIQUE}"
        resp1 = api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)
        assert resp1.status_code == 201
        resp2 = api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)
        assert resp2.status_code == 409

    def test_list_topics(self):
        ensure_admin()
        name = f"list-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)

        resp = api_get("/api/topics", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        topics = resp.json()
        assert isinstance(topics, list)
        names = [t["name"] for t in topics]
        assert name in names

    def test_get_topic(self):
        ensure_admin()
        name = f"get-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name, "description": "desc"}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{name}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == name
        assert resp.json()["description"] == "desc"

    def test_get_nonexistent_topic(self):
        ensure_admin()
        resp = api_get("/api/topics/nonexistent-xyz-999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_update_topic(self):
        ensure_admin()
        name = f"upd-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name, "description": "old"}, headers=ADMIN_HEADERS)

        resp = api_put(f"/api/topics/{name}", {"description": "new desc"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["description"] == "new desc"

    def test_update_topic_non_admin(self):
        ensure_admin()
        name = f"upd-na-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)

        resp = api_put(f"/api/topics/{name}", {"description": "hack"}, headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_delete_topic(self):
        ensure_admin()
        name = f"del-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)

        resp = api_delete(f"/api/topics/{name}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        get_resp = api_get(f"/api/topics/{name}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_delete_topic_non_admin(self):
        ensure_admin()
        name = f"del-na-topic-{UNIQUE}"
        api_post("/api/topics", {"name": name}, headers=ADMIN_HEADERS)

        resp = api_delete(f"/api/topics/{name}", headers=REG_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 6: Messages — Publish & Retrieve
# ════════════════════════════════════════════════════════════════════


class TestMessages:

    def test_publish_message(self):
        ensure_admin()
        topic = f"msg-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Hello World",
            "title": "Test",
            "priority": 4,
            "tags": "info,urgent",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["message"] == "Hello World"
        assert msg["title"] == "Test"
        assert msg["priority"] == 4
        assert msg["tags"] == ["info", "urgent"]
        assert msg["topic"] == topic
        assert "id" in msg
        assert "publishedAt" in msg
        assert msg["delivered"] is True

    def test_publish_auto_creates_topic(self):
        ensure_admin()
        topic = f"auto-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Auto-created topic",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201

        # Topic should exist
        get_resp = api_get(f"/api/topics/{topic}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == topic

    def test_publish_default_priority(self):
        ensure_admin()
        topic = f"defpri-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Default priority",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["priority"] == 3

    def test_publish_priority_clamped_low(self):
        ensure_admin()
        topic = f"clamplo-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Low priority",
            "priority": -5,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["priority"] == 1

    def test_publish_priority_clamped_high(self):
        ensure_admin()
        topic = f"clamphi-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "High priority",
            "priority": 99,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["priority"] == 5

    def test_publish_with_actions(self):
        ensure_admin()
        topic = f"actions-topic-{UNIQUE}"
        actions = [
            {"action": "view", "label": "Open", "url": "https://example.com"},
            {"action": "http", "label": "Callback", "url": "https://api.example.com/hook"},
        ]
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "With actions",
            "actions": actions,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert len(msg["actions"]) == 2
        assert msg["actions"][0]["action"] == "view"
        assert msg["actions"][1]["action"] == "http"

    def test_publish_with_attachment(self):
        ensure_admin()
        topic = f"attach-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "With attachment",
            "attachment": {"name": "file.pdf", "url": "https://example.com/file.pdf", "type": "application/pdf", "size": 12345},
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["attachment"]["name"] == "file.pdf"
        assert msg["attachment"]["size"] == 12345

    def test_get_topic_messages(self):
        ensure_admin()
        topic = f"getmsgs-topic-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "msg1"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "msg2"}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        assert isinstance(msgs, list)
        assert len(msgs) >= 2

    def test_get_message_by_id(self):
        ensure_admin()
        topic = f"getmsg-topic-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {"message": "findme"}, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        resp = api_get(f"/api/messages/{msg_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "findme"
        assert resp.json()["id"] == msg_id

    def test_get_nonexistent_message(self):
        ensure_admin()
        resp = api_get("/api/messages/999999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_delete_message_as_publisher(self):
        ensure_admin()
        topic = f"delmsg-topic-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {"message": "to delete"}, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        resp = api_delete(f"/api/messages/{msg_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        get_resp = api_get(f"/api/messages/{msg_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_delete_message_unauthorized(self):
        """Non-admin, non-publisher cannot delete."""
        ensure_admin()
        topic = f"delmsg-unauth-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {"message": "protected"}, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        # Ensure reg user exists
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_delete(f"/api/messages/{msg_id}", headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_tags_as_array(self):
        ensure_admin()
        topic = f"tags-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Tagged",
            "tags": "warning,backup,server",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["tags"] == ["warning", "backup", "server"]

    def test_empty_tags(self):
        ensure_admin()
        topic = f"notags-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "No tags",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["tags"] == []


# ════════════════════════════════════════════════════════════════════
# PART 7: Message Filtering
# ════════════════════════════════════════════════════════════════════


class TestMessageFiltering:

    def test_filter_by_priority(self):
        ensure_admin()
        topic = f"filtpri-topic-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "low", "priority": 1}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "high", "priority": 5}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", params={"priority": 4}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        for msg in msgs:
            assert msg["priority"] >= 4

    def test_filter_by_tags(self):
        ensure_admin()
        topic = f"filttag-topic-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "a", "tags": "alert,server"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "b", "tags": "info"}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", params={"tags": "alert"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) >= 1
        for msg in msgs:
            assert "alert" in msg["tags"]

    def test_filter_by_title(self):
        ensure_admin()
        topic = f"filttitle-topic-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "a", "title": "Server Alert"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "b", "title": "Info Update"}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", params={"title": "Alert"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) >= 1
        for msg in msgs:
            assert "Alert" in msg["title"]


# ════════════════════════════════════════════════════════════════════
# PART 8: Scheduled Messages
# ════════════════════════════════════════════════════════════════════


class TestScheduledMessages:

    def test_publish_scheduled_message(self):
        ensure_admin()
        topic = f"sched-topic-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "Future message",
            "scheduledAt": "2099-01-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["delivered"] is False
        assert msg["scheduledAt"] is not None

    def test_scheduled_not_in_regular_list(self):
        ensure_admin()
        topic = f"sched-hide-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "immediate"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {
            "message": "future",
            "scheduledAt": "2099-06-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        messages_text = [m["message"] for m in msgs]
        assert "immediate" in messages_text
        assert "future" not in messages_text

    def test_scheduled_in_scheduled_endpoint(self):
        ensure_admin()
        topic = f"sched-list-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {
            "message": "scheduled one",
            "scheduledAt": "2099-12-31T00:00:00Z",
        }, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages/scheduled", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) >= 1
        assert any(m["message"] == "scheduled one" for m in msgs)

    def test_cancel_scheduled_message(self):
        ensure_admin()
        topic = f"sched-cancel-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "to cancel",
            "scheduledAt": "2099-03-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        resp = api_delete(f"/api/messages/{msg_id}/schedule", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Message should be gone
        get_resp = api_get(f"/api/messages/{msg_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_cannot_cancel_delivered_message(self):
        ensure_admin()
        topic = f"sched-nodelete-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "already delivered",
        }, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        resp = api_delete(f"/api/messages/{msg_id}/schedule", headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_scheduled_with_past_time_is_delivered(self):
        ensure_admin()
        topic = f"sched-past-{UNIQUE}"
        resp = api_post(f"/api/topics/{topic}/messages", {
            "message": "past schedule",
            "scheduledAt": "2000-01-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        msg = resp.json()
        assert msg["delivered"] is True

    def test_include_scheduled_with_flag(self):
        ensure_admin()
        topic = f"sched-flag-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "normal"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {
            "message": "scheduled",
            "scheduledAt": "2099-06-01T00:00:00Z",
        }, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/messages", params={"scheduled": "true"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        msgs = resp.json()
        messages_text = [m["message"] for m in msgs]
        assert "normal" in messages_text
        assert "scheduled" in messages_text


# ════════════════════════════════════════════════════════════════════
# PART 9: Subscriptions
# ════════════════════════════════════════════════════════════════════


class TestSubscriptions:

    def test_create_subscription(self):
        ensure_admin()
        topic = f"sub-topic-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        sub = resp.json()
        assert sub["topic"] == topic
        assert "id" in sub

    def test_duplicate_subscription(self):
        ensure_admin()
        topic = f"dup-sub-topic-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)

        resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        assert resp.status_code == 409

    def test_list_subscriptions(self):
        ensure_admin()
        topic = f"list-sub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)

        resp = api_get("/api/subscriptions", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        subs = resp.json()
        assert isinstance(subs, list)
        topics = [s["topic"] for s in subs]
        assert topic in topics

    def test_get_subscription(self):
        ensure_admin()
        topic = f"getsub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        create_resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        sub_id = create_resp.json()["id"]

        resp = api_get(f"/api/subscriptions/{sub_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["topic"] == topic

    def test_update_subscription(self):
        ensure_admin()
        topic = f"updsub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        create_resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        sub_id = create_resp.json()["id"]

        resp = api_put(f"/api/subscriptions/{sub_id}", {
            "filterPriority": 3,
            "filterTags": "important",
            "filterTitle": "Alert",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        sub = resp.json()
        assert sub["filterPriority"] == 3
        assert sub["filterTags"] == "important"
        assert sub["filterTitle"] == "Alert"

    def test_delete_subscription(self):
        ensure_admin()
        topic = f"delsub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        create_resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        sub_id = create_resp.json()["id"]

        resp = api_delete(f"/api/subscriptions/{sub_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        get_resp = api_get(f"/api/subscriptions/{sub_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_subscription_isolation(self):
        """User A's subscriptions are not visible to User B."""
        ensure_admin()
        topic = f"iso-sub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)

        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_get("/api/subscriptions", headers=REG_HEADERS)
        assert resp.status_code == 200
        topics = [s["topic"] for s in resp.json()]
        assert topic not in topics


# ════════════════════════════════════════════════════════════════════
# PART 10: Access Control
# ════════════════════════════════════════════════════════════════════


class TestAccessControl:

    def test_default_open_access(self):
        """By default topics are open — any user can publish and read."""
        ensure_admin()
        topic = f"open-topic-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        # Regular user should be able to publish
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "open access"}, headers=REG_HEADERS)
        assert resp.status_code == 201

        # Regular user should be able to read
        resp = api_get(f"/api/topics/{topic}/messages", headers=REG_HEADERS)
        assert resp.status_code == 200

    def test_set_access_rule(self):
        ensure_admin()
        topic = f"acl-topic-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        # Get admin user id
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin_user = next(u for u in users if u["username"] == ADMIN_USER_ID)

        resp = api_put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        rule = resp.json()
        assert rule["userId"] == admin_user["id"]
        assert rule["read"] is True
        assert rule["write"] is True

    def test_restricted_topic_denies_unlisted_user(self):
        """When access rules exist, unlisted users are denied."""
        ensure_admin()
        topic = f"restricted-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        # Get admin user id and set access rule (makes topic restricted)
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin_user = next(u for u in users if u["username"] == ADMIN_USER_ID)

        api_put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        }, headers=ADMIN_HEADERS)

        # Regular user tries to publish — should be denied
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "blocked"}, headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_restricted_topic_denies_read(self):
        """Restricted topic denies read for unlisted users."""
        ensure_admin()
        topic = f"restricted-read-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin_user = next(u for u in users if u["username"] == ADMIN_USER_ID)

        api_put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        }, headers=ADMIN_HEADERS)

        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_get(f"/api/topics/{topic}/messages", headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_admin_always_has_access(self):
        """Admin always has access even without explicit rule."""
        ensure_admin()
        topic = f"admin-access-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        # Create a rule for some other user to restrict the topic
        api_get("/api/topics", headers=REG_HEADERS)
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        reg_user = next(u for u in users if u["username"] == REG_USER_ID)

        api_put(f"/api/topics/{topic}/access", {
            "userId": reg_user["id"],
            "read": True,
            "write": False,
        }, headers=ADMIN_HEADERS)

        # Admin should still be able to publish (even without explicit rule)
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "admin override"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 201

    def test_list_access_rules(self):
        ensure_admin()
        topic = f"listacl-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin_user = next(u for u in users if u["username"] == ADMIN_USER_ID)

        api_put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        }, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/access", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        rules = resp.json()
        assert isinstance(rules, list)
        assert len(rules) >= 1

    def test_delete_access_rule(self):
        ensure_admin()
        topic = f"delacl-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        admin_user = next(u for u in users if u["username"] == ADMIN_USER_ID)

        api_put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        }, headers=ADMIN_HEADERS)

        resp = api_delete(f"/api/topics/{topic}/access/{admin_user['id']}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Now the topic is open again (no rules)
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "open again"}, headers=REG_HEADERS)
        assert resp.status_code == 201

    def test_access_non_admin_denied(self):
        ensure_admin()
        topic = f"acl-nonadmin-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)

        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_get(f"/api/topics/{topic}/access", headers=REG_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 11: Stats
# ════════════════════════════════════════════════════════════════════


class TestStats:

    def test_topic_stats(self):
        ensure_admin()
        topic = f"stats-topic-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "s1"}, headers=ADMIN_HEADERS)
        api_post(f"/api/topics/{topic}/messages", {"message": "s2"}, headers=ADMIN_HEADERS)
        api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)

        resp = api_get(f"/api/topics/{topic}/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["topic"] == topic
        assert stats["messageCount"] >= 2
        assert stats["subscriberCount"] >= 1

    def test_topic_stats_not_found(self):
        ensure_admin()
        resp = api_get("/api/topics/nonexistent-stats-xyz/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_global_stats(self):
        ensure_admin()
        resp = api_get("/api/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        stats = resp.json()
        assert "totalTopics" in stats
        assert "totalMessages" in stats
        assert "totalUsers" in stats
        assert stats["totalTopics"] >= 0
        assert stats["totalMessages"] >= 0
        assert stats["totalUsers"] >= 1

    def test_global_stats_non_admin(self):
        ensure_admin()
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_get("/api/stats", headers=REG_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 12: Tiers
# ════════════════════════════════════════════════════════════════════


class TestTiers:

    def test_create_tier(self):
        ensure_admin()
        resp = api_post("/api/tiers", {
            "name": f"free-{UNIQUE}",
            "messagesPerDay": 100,
            "messagesPerMinute": 10,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        tier = resp.json()
        assert tier["name"] == f"free-{UNIQUE}"
        assert tier["messagesPerDay"] == 100
        assert tier["messagesPerMinute"] == 10
        assert "id" in tier

    def test_create_tier_non_admin(self):
        ensure_admin()
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post("/api/tiers", {
            "name": "hack-tier",
            "messagesPerDay": 999,
            "messagesPerMinute": 99,
        }, headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_list_tiers(self):
        ensure_admin()
        api_post("/api/tiers", {
            "name": f"list-tier-{UNIQUE}",
            "messagesPerDay": 50,
            "messagesPerMinute": 5,
        }, headers=ADMIN_HEADERS)

        resp = api_get("/api/tiers", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        tiers = resp.json()
        assert isinstance(tiers, list)
        assert len(tiers) >= 1

    def test_update_tier(self):
        ensure_admin()
        create_resp = api_post("/api/tiers", {
            "name": f"upd-tier-{UNIQUE}",
            "messagesPerDay": 50,
            "messagesPerMinute": 5,
        }, headers=ADMIN_HEADERS)
        tier_id = create_resp.json()["id"]

        resp = api_put(f"/api/tiers/{tier_id}", {
            "name": f"upd-tier-{UNIQUE}-v2",
            "messagesPerDay": 200,
            "messagesPerMinute": 20,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["messagesPerDay"] == 200

    def test_delete_tier(self):
        ensure_admin()
        create_resp = api_post("/api/tiers", {
            "name": f"del-tier-{UNIQUE}",
            "messagesPerDay": 10,
            "messagesPerMinute": 1,
        }, headers=ADMIN_HEADERS)
        tier_id = create_resp.json()["id"]

        resp = api_delete(f"/api/tiers/{tier_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_delete_tier_in_use(self):
        ensure_admin()
        # Create tier
        create_resp = api_post("/api/tiers", {
            "name": f"inuse-tier-{UNIQUE}",
            "messagesPerDay": 10,
            "messagesPerMinute": 1,
        }, headers=ADMIN_HEADERS)
        tier_id = create_resp.json()["id"]
        tier_name = create_resp.json()["name"]

        # Assign tier to a user
        username = f"tiered-user-{UNIQUE}"
        user_resp = api_post("/api/users", {"username": username}, headers=ADMIN_HEADERS)
        user_id = user_resp.json()["id"]
        api_put(f"/api/users/{user_id}", {"tier": tier_name}, headers=ADMIN_HEADERS)

        # Try to delete — should fail
        resp = api_delete(f"/api/tiers/{tier_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 13: Rate Limiting
# ════════════════════════════════════════════════════════════════════


class TestRateLimiting:

    def test_rate_limit_per_minute(self):
        ensure_admin()
        # Create tier with low limit
        tier_resp = api_post("/api/tiers", {
            "name": f"ratelimit-{UNIQUE}",
            "messagesPerDay": 1000,
            "messagesPerMinute": 2,
        }, headers=ADMIN_HEADERS)
        tier_name = tier_resp.json()["name"]

        # Create user with that tier
        username = f"limited-user-{UNIQUE}"
        user_headers = {
            "X-User-Id": username,
            "X-Token": f"token-{username}",
            "Content-Type": "application/json",
        }
        api_get("/api/topics", headers=user_headers)
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        limited_user = next(u for u in users if u["username"] == username)
        api_put(f"/api/users/{limited_user['id']}", {"tier": tier_name}, headers=ADMIN_HEADERS)

        topic = f"ratelimit-topic-{UNIQUE}"

        # Publish up to limit
        for i in range(2):
            resp = api_post(f"/api/topics/{topic}/messages", {"message": f"msg{i}"}, headers=user_headers)
            assert resp.status_code == 201

        # Next should be rate limited
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "over limit"}, headers=user_headers)
        assert resp.status_code == 429

    def test_no_rate_limit_without_tier(self):
        ensure_admin()
        username = f"nolimit-{UNIQUE}"
        user_headers = {
            "X-User-Id": username,
            "X-Token": f"token-{username}",
            "Content-Type": "application/json",
        }
        api_get("/api/topics", headers=user_headers)
        topic = f"nolimit-topic-{UNIQUE}"

        # Should be able to publish many messages
        for i in range(10):
            resp = api_post(f"/api/topics/{topic}/messages", {"message": f"m{i}"}, headers=user_headers)
            assert resp.status_code == 201

    def test_rate_reset(self):
        ensure_admin()
        # Create tier with low limit
        tier_resp = api_post("/api/tiers", {
            "name": f"reset-tier-{UNIQUE}",
            "messagesPerDay": 1000,
            "messagesPerMinute": 1,
        }, headers=ADMIN_HEADERS)
        tier_name = tier_resp.json()["name"]

        # Create user with that tier
        username = f"reset-user-{UNIQUE}"
        user_headers = {
            "X-User-Id": username,
            "X-Token": f"token-{username}",
            "Content-Type": "application/json",
        }
        api_get("/api/topics", headers=user_headers)
        users = api_get("/api/users", headers=ADMIN_HEADERS).json()
        limited_user = next(u for u in users if u["username"] == username)
        api_put(f"/api/users/{limited_user['id']}", {"tier": tier_name}, headers=ADMIN_HEADERS)

        topic = f"reset-topic-{UNIQUE}"
        api_post(f"/api/topics/{topic}/messages", {"message": "first"}, headers=user_headers)

        # Should be rate limited
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "blocked"}, headers=user_headers)
        assert resp.status_code == 429

        # Admin resets
        resp = api_post("/api/admin/rate-reset", {"userId": limited_user["id"]}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Should work again
        resp = api_post(f"/api/topics/{topic}/messages", {"message": "unblocked"}, headers=user_headers)
        assert resp.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 14: Admin Operations
# ════════════════════════════════════════════════════════════════════


class TestAdminOperations:

    def test_prune_messages(self):
        ensure_admin()
        topic = f"prune-topic-{UNIQUE}"
        # Publish a message (immediate delivery)
        api_post(f"/api/topics/{topic}/messages", {"message": "old message"}, headers=ADMIN_HEADERS)

        # Wait beyond the strict one-second cutoff before pruning.
        time.sleep(2)
        resp = api_post("/api/admin/prune", {"olderThanSeconds": 1}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        result = resp.json()
        assert "pruned" in result
        assert result["pruned"] >= 1

    def test_prune_non_admin(self):
        ensure_admin()
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post("/api/admin/prune", {"olderThanSeconds": 3600}, headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_rate_reset_non_admin(self):
        ensure_admin()
        api_get("/api/topics", headers=REG_HEADERS)
        resp = api_post("/api/admin/rate-reset", {"userId": 1}, headers=REG_HEADERS)
        assert resp.status_code == 403

    def test_rate_reset_nonexistent_user(self):
        ensure_admin()
        resp = api_post("/api/admin/rate-reset", {"userId": 999999}, headers=ADMIN_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_topic_deletes_messages(self):
        ensure_admin()
        topic = f"cascade-topic-{UNIQUE}"
        pub_resp = api_post(f"/api/topics/{topic}/messages", {"message": "cascade me"}, headers=ADMIN_HEADERS)
        msg_id = pub_resp.json()["id"]

        api_delete(f"/api/topics/{topic}", headers=ADMIN_HEADERS)

        # Message should be gone
        resp = api_get(f"/api/messages/{msg_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_delete_topic_deletes_subscriptions(self):
        ensure_admin()
        topic = f"cascade-sub-{UNIQUE}"
        api_post("/api/topics", {"name": topic}, headers=ADMIN_HEADERS)
        sub_resp = api_post("/api/subscriptions", {"topic": topic}, headers=ADMIN_HEADERS)
        sub_id = sub_resp.json()["id"]

        api_delete(f"/api/topics/{topic}", headers=ADMIN_HEADERS)

        resp = api_get(f"/api/subscriptions/{sub_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 404
