"""
Correctness tests for Zulip Topic-Based Chat API.
"""
import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
REQUEST_TIMEOUT = 10
_test_namespace = ""

# ─── Helpers ───────────────────────────────────────────────────────────────────


def request(method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, **kwargs)


def scoped_email(email):
    local_part, domain = email.rsplit("@", 1)
    return f"{local_part}-{_test_namespace}@{domain}"


def scoped_name(name):
    return f"{name}-{_test_namespace}"


def headers(email="admin@zulip.test"):
    return {"X-API-Key": "test-key", "X-User-Email": scoped_email(email)}


def create_user(email, full_name="Test User", role="member", password="password123"):
    email = scoped_email(email)
    resp = request("post", f"{API}/users", json={
        "email": email,
        "fullName": full_name,
        "password": password,
        "role": role,
    })
    return resp


def create_admin():
    global _test_namespace
    _test_namespace = uuid.uuid4().hex
    return create_user("admin@zulip.test", "Admin User", "owner")


def create_stream(name, is_private=False, email="admin@zulip.test"):
    name = scoped_name(name)
    return request("post", f"{API}/streams", json={
        "name": name,
        "description": f"Description for {name}",
        "isPrivate": is_private,
    }, headers=headers(email))


def subscribe_users(stream_id, user_ids, email="admin@zulip.test"):
    return request(
        "post",
        f"{API}/streams/{stream_id}/subscribers",
        json={"userIds": user_ids},
        headers=headers(email),
    )


def send_message(stream_id, topic, content, email="admin@zulip.test"):
    return request("post", f"{API}/messages", json={
        "streamId": stream_id,
        "topic": topic,
        "content": content,
    }, headers=headers(email))


# ─── Test Authentication ───────────────────────────────────────────────────────

class TestAuthentication:
    def setup_method(self):
        # Ensure admin user exists for auth tests
        create_admin()

    def test_missing_api_key(self):
        resp = request(
            "get",
            f"{API}/streams",
            headers={"X-User-Email": scoped_email("admin@zulip.test")},
        )
        assert resp.status_code == 401

    def test_missing_email(self):
        resp = request("get", f"{API}/streams", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 401

    def test_no_headers(self):
        resp = request("get", f"{API}/streams")
        assert resp.status_code == 401

    def test_invalid_email(self):
        resp = request("get", f"{API}/streams", headers={
            "X-API-Key": "test-key",
            "X-User-Email": scoped_email("nonexistent@zulip.test"),
        })
        assert resp.status_code == 401

    def test_valid_auth(self):
        resp = request("get", f"{API}/streams", headers=headers("admin@zulip.test"))
        assert resp.status_code == 200


# ─── Test Users ────────────────────────────────────────────────────────────────

class TestUsers:
    def setup_method(self):
        create_admin()

    def test_create_user(self):
        resp = create_user("newuser1@zulip.test", "New User 1")
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == scoped_email("newuser1@zulip.test")
        assert data["fullName"] == "New User 1"
        assert data["role"] == "member"
        assert data["isActive"] is True
        assert "id" in data

    def test_create_user_duplicate_email(self):
        create_user("dup@zulip.test")
        resp = create_user("dup@zulip.test")
        assert resp.status_code == 400

    def test_create_user_missing_fields(self):
        resp = request(
            "post",
            f"{API}/users",
            json={"email": scoped_email("incomplete@zulip.test")},
        )
        assert resp.status_code == 400

    def test_list_users(self):
        create_user("listuser@zulip.test", "List User")
        resp = request("get", f"{API}/users", headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        emails = [u["email"] for u in data]
        assert scoped_email("listuser@zulip.test") in emails

    def test_get_user(self):
        resp = create_user("getuser@zulip.test", "Get User")
        user_id = resp.json()["id"]
        resp = request("get", f"{API}/users/{user_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["email"] == scoped_email("getuser@zulip.test")

    def test_get_user_not_found(self):
        resp = request("get", f"{API}/users/0", headers=headers())
        assert resp.status_code == 404

    def test_update_user(self):
        resp = create_user("update@zulip.test", "Old Name")
        user_id = resp.json()["id"]
        resp = request("patch", f"{API}/users/{user_id}", json={
            "fullName": "New Name",
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["fullName"] == "New Name"

    def test_deactivate_user_requires_admin(self):
        create_user("member@zulip.test", "Member", "member")
        resp = create_user("target@zulip.test", "Target")
        target_id = resp.json()["id"]
        # member cannot deactivate
        resp = request(
            "post",
            f"{API}/users/{target_id}/deactivate",
            headers=headers("member@zulip.test"),
        )
        assert resp.status_code == 403

    def test_deactivate_user_as_admin(self):
        resp = create_user("deactivateme@zulip.test", "Deactivate Me")
        user_id = resp.json()["id"]
        resp = request(
            "post",
            f"{API}/users/{user_id}/deactivate",
            headers=headers("admin@zulip.test"),
        )
        assert resp.status_code == 200
        assert resp.json()["isActive"] is False

    def test_change_role_requires_owner(self):
        create_user("adminuser@zulip.test", "Admin", "admin")
        resp = create_user("rolechange@zulip.test", "Role Change")
        user_id = resp.json()["id"]
        # admin cannot change roles
        resp = request("patch", f"{API}/users/{user_id}", json={
            "role": "moderator"
        }, headers=headers("adminuser@zulip.test"))
        assert resp.status_code == 403


# ─── Test Streams ──────────────────────────────────────────────────────────────

class TestStreams:
    def setup_method(self):
        create_admin()

    def test_create_stream(self):
        resp = create_stream("general")
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == scoped_name("general")
        assert data["isPrivate"] is False
        assert "id" in data

    def test_create_stream_guest_forbidden(self):
        create_user("guest@zulip.test", "Guest", "guest")
        resp = create_stream("guest-stream", email="guest@zulip.test")
        assert resp.status_code == 403

    def test_list_streams(self):
        create_stream("public-list")
        resp = request("get", f"{API}/streams", headers=headers())
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert scoped_name("public-list") in names

    def test_private_stream_not_visible_to_non_subscriber(self):
        create_user("outsider@zulip.test", "Outsider")
        create_stream("secret-stream", is_private=True)
        resp = request("get", f"{API}/streams", headers=headers("outsider@zulip.test"))
        names = [s["name"] for s in resp.json()]
        assert scoped_name("secret-stream") not in names

    def test_private_stream_visible_to_subscriber(self):
        create_user("insider@zulip.test", "Insider")
        resp = create_stream("private-visible", is_private=True)
        stream_id = resp.json()["id"]
        insider = request("get", f"{API}/users", headers=headers())
        insider_user = [u for u in insider.json() if u["email"] == scoped_email("insider@zulip.test")][0]
        subscribe_users(stream_id, [insider_user["id"]])
        resp = request("get", f"{API}/streams", headers=headers("insider@zulip.test"))
        names = [s["name"] for s in resp.json()]
        assert scoped_name("private-visible") in names

    def test_get_stream(self):
        resp = create_stream("get-me")
        stream_id = resp.json()["id"]
        resp = request("get", f"{API}/streams/{stream_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == scoped_name("get-me")

    def test_update_stream_requires_admin(self):
        create_user("member2@zulip.test", "Member 2", "member")
        resp = create_stream("admin-only")
        stream_id = resp.json()["id"]
        resp = request("patch", f"{API}/streams/{stream_id}", json={
            "description": "Updated"
        }, headers=headers("member2@zulip.test"))
        assert resp.status_code == 403

    def test_update_stream_as_admin(self):
        resp = create_stream("updateable")
        stream_id = resp.json()["id"]
        resp = request("patch", f"{API}/streams/{stream_id}", json={
            "description": "New desc"
        }, headers=headers("admin@zulip.test"))
        assert resp.status_code == 200
        assert resp.json()["description"] == "New desc"

    def test_delete_stream(self):
        resp = create_stream("deleteme")
        stream_id = resp.json()["id"]
        resp = request("delete", f"{API}/streams/{stream_id}", headers=headers())
        assert resp.status_code == 204

    def test_delete_stream_not_found(self):
        resp = request("delete", f"{API}/streams/0", headers=headers())
        assert resp.status_code == 404


# ─── Test Subscriptions ────────────────────────────────────────────────────────

class TestSubscriptions:
    def setup_method(self):
        create_admin()

    def test_subscribe_to_stream(self):
        resp = create_user("sub1@zulip.test", "Sub 1")
        user_id = resp.json()["id"]
        resp = create_stream("sub-stream")
        stream_id = resp.json()["id"]
        resp = subscribe_users(stream_id, [user_id])
        assert resp.status_code == 200
        assert user_id in resp.json()["subscribed"]

    def test_list_subscribers(self):
        resp = create_user("sub2@zulip.test", "Sub 2")
        user_id = resp.json()["id"]
        resp = create_stream("sub2-stream")
        stream_id = resp.json()["id"]
        subscribe_users(stream_id, [user_id])
        resp = request(
            "get",
            f"{API}/streams/{stream_id}/subscribers",
            headers=headers(),
        )
        assert resp.status_code == 200
        assert user_id in resp.json()

    def test_unsubscribe(self):
        resp = create_user("unsub@zulip.test", "Unsub")
        user_id = resp.json()["id"]
        resp = create_stream("unsub-stream")
        stream_id = resp.json()["id"]
        subscribe_users(stream_id, [user_id])
        resp = request(
            "delete",
            f"{API}/streams/{stream_id}/subscribers/{user_id}",
            headers=headers(),
        )
        assert resp.status_code == 204

    def test_list_user_subscriptions(self):
        resp = create_user("mysubs@zulip.test", "My Subs")
        user_id = resp.json()["id"]
        resp = create_stream("mysubs-stream")
        stream_id = resp.json()["id"]
        subscribe_users(stream_id, [user_id])
        resp = request(
            "get",
            f"{API}/users/{user_id}/subscriptions",
            headers=headers(),
        )
        assert resp.status_code == 200
        stream_ids = [s["streamId"] for s in resp.json()]
        assert stream_id in stream_ids

    def test_mute_topic(self):
        resp = create_stream("mute-stream")
        stream_id = resp.json()["id"]
        # Need admin to be subscribed first
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        send_message(stream_id, "mute-topic", "hello")
        resp = request("post", f"{API}/streams/{stream_id}/mute-topic", json={
            "topic": "mute-topic",
            "isMuted": True,
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["isMuted"] is True


# ─── Test Messages & Topics ────────────────────────────────────────────────────

class TestMessages:
    def setup_method(self):
        create_admin()

    def test_send_message_creates_topic(self):
        resp = create_stream("msg-stream")
        stream_id = resp.json()["id"]
        # Subscribe admin
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        # Send message to new topic
        resp = send_message(stream_id, "new-topic", "Hello World!")
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Hello World!"
        assert data["topic"] == "new-topic"
        assert data["streamId"] == stream_id
        # Verify topic was created
        resp = request("get", f"{API}/streams/{stream_id}/topics", headers=headers())
        topics = [t["name"] for t in resp.json()]
        assert "new-topic" in topics

    def test_send_message_not_subscribed(self):
        create_user("outsider2@zulip.test", "Outsider 2")
        resp = create_stream("restricted-stream")
        stream_id = resp.json()["id"]
        resp = request("post", f"{API}/messages", json={
            "streamId": stream_id,
            "topic": "test",
            "content": "not allowed"
        }, headers=headers("outsider2@zulip.test"))
        assert resp.status_code == 403

    def test_get_message(self):
        resp = create_stream("get-msg-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "get-topic", "Get me!")
        msg_id = resp.json()["id"]
        resp = request("get", f"{API}/messages/{msg_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["content"] == "Get me!"

    def test_edit_message(self):
        resp = create_stream("edit-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "edit-topic", "Original content")
        msg_id = resp.json()["id"]
        resp = request("patch", f"{API}/messages/{msg_id}", json={
            "content": "Edited content"
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["content"] == "Edited content"
        assert resp.json()["isEdited"] is True

    def test_edit_message_not_sender(self):
        create_user("other@zulip.test", "Other")
        resp = create_stream("edit-perm-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "edit-perm-topic", "My message")
        msg_id = resp.json()["id"]
        resp = request("patch", f"{API}/messages/{msg_id}", json={
            "content": "Hacked"
        }, headers=headers("other@zulip.test"))
        assert resp.status_code == 403

    def test_edit_history(self):
        resp = create_stream("history-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "history-topic", "Version 1")
        msg_id = resp.json()["id"]
        request("patch", f"{API}/messages/{msg_id}", json={"content": "Version 2"}, headers=headers())
        request("patch", f"{API}/messages/{msg_id}", json={"content": "Version 3"}, headers=headers())
        resp = request("get", f"{API}/messages/{msg_id}/edit-history", headers=headers())
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2
        contents = [h["previousContent"] for h in history]
        assert "Version 1" in contents
        assert "Version 2" in contents

    def test_delete_own_message(self):
        resp = create_stream("del-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "del-topic", "Delete me")
        msg_id = resp.json()["id"]
        resp = request("delete", f"{API}/messages/{msg_id}", headers=headers())
        assert resp.status_code == 204

    def test_delete_other_message_requires_moderator(self):
        create_user("sender@zulip.test", "Sender", "member")
        create_user("delmember@zulip.test", "DelMember", "member")
        resp = create_stream("del-perm-stream")
        stream_id = resp.json()["id"]
        # Subscribe the sender
        users = request("get", f"{API}/users", headers=headers())
        sender_id = [u for u in users.json() if u["email"] == scoped_email("sender@zulip.test")][0]["id"]
        subscribe_users(stream_id, [sender_id])
        resp = send_message(stream_id, "del-perm-topic", "My message", email="sender@zulip.test")
        msg_id = resp.json()["id"]
        # member cannot delete other's message
        resp = request("delete", f"{API}/messages/{msg_id}", headers=headers("delmember@zulip.test"))
        assert resp.status_code == 403

    def test_delete_other_message_as_moderator(self):
        create_user("sender2@zulip.test", "Sender 2", "member")
        create_user("mod@zulip.test", "Moderator", "moderator")
        resp = create_stream("mod-del-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        sender_id = [u for u in users.json() if u["email"] == scoped_email("sender2@zulip.test")][0]["id"]
        subscribe_users(stream_id, [sender_id])
        resp = send_message(stream_id, "mod-topic", "Delete me", email="sender2@zulip.test")
        msg_id = resp.json()["id"]
        resp = request("delete", f"{API}/messages/{msg_id}", headers=headers("mod@zulip.test"))
        assert resp.status_code == 204

    def test_filter_messages_by_stream(self):
        resp = create_stream("filter-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        send_message(stream_id, "filter-topic", "Filtered message")
        resp = request("get", f"{API}/messages", params={"streamId": stream_id}, headers=headers())
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert all(m["streamId"] == stream_id for m in resp.json())

    def test_filter_messages_by_topic(self):
        resp = create_stream("topic-filter-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        send_message(stream_id, "topicA", "Message in A")
        send_message(stream_id, "topicB", "Message in B")
        resp = request("get", f"{API}/messages", params={
            "streamId": stream_id, "topic": "topicA"
        }, headers=headers())
        assert resp.status_code == 200
        assert all(m["topic"] == "topicA" for m in resp.json())

    def test_filter_messages_by_keyword(self):
        resp = create_stream("keyword-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        send_message(stream_id, "keyword-topic", "The quick brown fox")
        send_message(stream_id, "keyword-topic", "Hello world")
        resp = request("get", f"{API}/messages", params={"keyword": "quick"}, headers=headers())
        assert resp.status_code == 200
        assert any("quick" in m["content"].lower() for m in resp.json())

    def test_filter_messages_by_sender(self):
        create_user("sender3@zulip.test", "Sender 3")
        resp = create_stream("sender-filter-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        sender_id = [u for u in users.json() if u["email"] == scoped_email("sender3@zulip.test")][0]["id"]
        subscribe_users(stream_id, [sender_id])
        send_message(stream_id, "sender-topic", "From sender", email="sender3@zulip.test")
        resp = request("get", f"{API}/messages", params={"senderId": sender_id}, headers=headers())
        assert resp.status_code == 200
        assert all(m["senderId"] == sender_id for m in resp.json())


# ─── Test Reactions ────────────────────────────────────────────────────────────

class TestReactions:
    def setup_method(self):
        create_admin()

    def test_add_reaction(self):
        resp = create_stream("react-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "react-topic", "React to me!")
        msg_id = resp.json()["id"]
        resp = request(
            "post",
            f"{API}/messages/{msg_id}/reactions/thumbsup",
            headers=headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["emoji"] == "thumbsup"
        assert admin_id in resp.json()["userIds"]

    def test_add_reaction_multiple_users(self):
        create_user("reactor@zulip.test", "Reactor")
        resp = create_stream("multireact-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        reactor_id = [u for u in users.json() if u["email"] == scoped_email("reactor@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id, reactor_id])
        resp = send_message(stream_id, "multi-topic", "Multi react")
        msg_id = resp.json()["id"]
        request("post", f"{API}/messages/{msg_id}/reactions/heart", headers=headers())
        request("post", f"{API}/messages/{msg_id}/reactions/heart", headers=headers("reactor@zulip.test"))
        resp = request("get", f"{API}/messages/{msg_id}/reactions", headers=headers())
        assert resp.status_code == 200
        heart = [r for r in resp.json() if r["emoji"] == "heart"][0]
        assert admin_id in heart["userIds"]
        assert reactor_id in heart["userIds"]

    def test_remove_reaction(self):
        resp = create_stream("unreact-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "unreact-topic", "Unreact me!")
        msg_id = resp.json()["id"]
        request("post", f"{API}/messages/{msg_id}/reactions/thumbsup", headers=headers())
        resp = request("delete", f"{API}/messages/{msg_id}/reactions/thumbsup", headers=headers())
        assert resp.status_code == 200
        # Verify it's gone
        resp = request("get", f"{API}/messages/{msg_id}/reactions", headers=headers())
        thumbsups = [r for r in resp.json() if r["emoji"] == "thumbsup"]
        if thumbsups:
            assert admin_id not in thumbsups[0]["userIds"]

    def test_duplicate_reaction_idempotent(self):
        resp = create_stream("dup-react-stream")
        stream_id = resp.json()["id"]
        admin_user = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in admin_user.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "dup-react-topic", "Dup react")
        msg_id = resp.json()["id"]
        request("post", f"{API}/messages/{msg_id}/reactions/star", headers=headers())
        resp = request("post", f"{API}/messages/{msg_id}/reactions/star", headers=headers())
        assert resp.status_code == 200
        # Should still only have one entry for admin
        resp = request("get", f"{API}/messages/{msg_id}/reactions", headers=headers())
        stars = [r for r in resp.json() if r["emoji"] == "star"][0]
        assert stars["userIds"].count(admin_id) == 1


# ─── Test Direct Messages ─────────────────────────────────────────────────────

class TestDirectMessages:
    def setup_method(self):
        create_admin()

    def test_create_dm_conversation(self):
        create_user("dm1@zulip.test", "DM User 1")
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        dm1_id = [u for u in users.json() if u["email"] == scoped_email("dm1@zulip.test")][0]["id"]
        resp = request("post", f"{API}/dm-conversations", json={
            "participantIds": [admin_id, dm1_id]
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert admin_id in data["participantIds"]
        assert dm1_id in data["participantIds"]

    def test_send_dm_message(self):
        create_user("dm2@zulip.test", "DM User 2")
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        dm2_id = [u for u in users.json() if u["email"] == scoped_email("dm2@zulip.test")][0]["id"]
        resp = request("post", f"{API}/dm-conversations", json={
            "participantIds": [admin_id, dm2_id]
        }, headers=headers())
        conv_id = resp.json()["id"]
        resp = request("post", f"{API}/messages", json={
            "dmConversationId": conv_id,
            "content": "Hello via DM!"
        }, headers=headers())
        assert resp.status_code == 201
        assert resp.json()["content"] == "Hello via DM!"
        assert resp.json()["dmConversationId"] == conv_id

    def test_list_dm_conversations(self):
        create_user("dm3@zulip.test", "DM User 3")
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        dm3_id = [u for u in users.json() if u["email"] == scoped_email("dm3@zulip.test")][0]["id"]
        request("post", f"{API}/dm-conversations", json={
            "participantIds": [admin_id, dm3_id]
        }, headers=headers())
        resp = request("get", f"{API}/dm-conversations", headers=headers())
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_dm_messages(self):
        create_user("dm4@zulip.test", "DM User 4")
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        dm4_id = [u for u in users.json() if u["email"] == scoped_email("dm4@zulip.test")][0]["id"]
        resp = request("post", f"{API}/dm-conversations", json={
            "participantIds": [admin_id, dm4_id]
        }, headers=headers())
        conv_id = resp.json()["id"]
        request("post", f"{API}/messages", json={
            "dmConversationId": conv_id,
            "content": "DM msg 1"
        }, headers=headers())
        request("post", f"{API}/messages", json={
            "dmConversationId": conv_id,
            "content": "DM msg 2"
        }, headers=headers())
        resp = request("get", f"{API}/dm-conversations/{conv_id}/messages", headers=headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ─── Test Presence ─────────────────────────────────────────────────────────────

class TestPresence:
    def setup_method(self):
        create_admin()

    def test_update_presence(self):
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        resp = request("post", f"{API}/users/{admin_id}/presence", json={
            "status": "online"
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "online"

    def test_get_presence(self):
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        request("post", f"{API}/users/{admin_id}/presence", json={
            "status": "idle"
        }, headers=headers())
        resp = request("get", f"{API}/users/{admin_id}/presence", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    def test_cannot_update_others_presence(self):
        create_user("other2@zulip.test", "Other 2")
        users = request("get", f"{API}/users", headers=headers())
        other_id = [u for u in users.json() if u["email"] == scoped_email("other2@zulip.test")][0]["id"]
        resp = request("post", f"{API}/users/{other_id}/presence", json={
            "status": "online"
        }, headers=headers())
        assert resp.status_code == 403

    def test_get_all_presence(self):
        resp = request("get", f"{API}/presence", headers=headers())
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ─── Test Drafts ───────────────────────────────────────────────────────────────

class TestDrafts:
    def setup_method(self):
        create_admin()

    def test_create_draft(self):
        stream_id = create_stream("draft-stream").json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [
            user["id"]
            for user in users.json()
            if user["email"] == scoped_email("admin@zulip.test")
        ][0]
        subscribe_users(stream_id, [admin_id])
        resp = request("post", f"{API}/drafts", json={
            "content": "Draft message",
            "streamId": stream_id,
            "topic": "draft-topic",
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Draft message"
        assert "id" in data

    def test_list_drafts(self):
        request("post", f"{API}/drafts", json={
            "content": "My draft",
        }, headers=headers())
        resp = request("get", f"{API}/drafts", headers=headers())
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_draft(self):
        resp = request("post", f"{API}/drafts", json={
            "content": "Original draft",
        }, headers=headers())
        draft_id = resp.json()["id"]
        resp = request("patch", f"{API}/drafts/{draft_id}", json={
            "content": "Updated draft",
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated draft"

    def test_delete_draft(self):
        resp = request("post", f"{API}/drafts", json={
            "content": "Deletable draft",
        }, headers=headers())
        draft_id = resp.json()["id"]
        resp = request("delete", f"{API}/drafts/{draft_id}", headers=headers())
        assert resp.status_code == 204

    def test_get_draft(self):
        resp = request("post", f"{API}/drafts", json={
            "content": "Get this draft",
        }, headers=headers())
        draft_id = resp.json()["id"]
        resp = request("get", f"{API}/drafts/{draft_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["content"] == "Get this draft"


# ─── Test Read Markers & Unread Counts ─────────────────────────────────────────

class TestReadMarkers:
    def setup_method(self):
        create_admin()

    def test_unread_count_on_new_message(self):
        create_user("reader@zulip.test", "Reader")
        resp = create_stream("unread-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        reader_id = [u for u in users.json() if u["email"] == scoped_email("reader@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id, reader_id])
        # Admin sends message - reader should have unread
        send_message(stream_id, "unread-topic", "New message")
        resp = request("get", f"{API}/unread-counts", headers=headers("reader@zulip.test"))
        assert resp.status_code == 200
        unreads = resp.json()
        stream_unreads = [u for u in unreads if u["streamId"] == stream_id and u["topic"] == "unread-topic"]
        assert len(stream_unreads) > 0
        assert stream_unreads[0]["unreadCount"] >= 1

    def test_sender_no_unread(self):
        resp = create_stream("sender-unread-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        send_message(stream_id, "sender-topic", "I sent this")
        resp = request("get", f"{API}/unread-counts", headers=headers())
        unreads = resp.json()
        stream_unreads = [u for u in unreads if u["streamId"] == stream_id and u["topic"] == "sender-topic"]
        # Sender should have 0 unreads or not appear
        if stream_unreads:
            assert stream_unreads[0]["unreadCount"] == 0

    def test_mark_stream_read(self):
        create_user("markread@zulip.test", "Mark Read")
        resp = create_stream("markread-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        reader_id = [u for u in users.json() if u["email"] == scoped_email("markread@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id, reader_id])
        send_message(stream_id, "topicX", "msg1")
        send_message(stream_id, "topicY", "msg2")
        # Mark entire stream as read
        resp = request(
            "post",
            f"{API}/mark-read/stream/{stream_id}",
            headers=headers("markread@zulip.test"),
        )
        assert resp.status_code == 200
        # Unread counts should be 0
        resp = request("get", f"{API}/unread-counts", headers=headers("markread@zulip.test"))
        stream_unreads = [u for u in resp.json() if u["streamId"] == stream_id]
        for u in stream_unreads:
            assert u["unreadCount"] == 0

    def test_mark_topic_read(self):
        create_user("topicread@zulip.test", "Topic Read")
        resp = create_stream("topicread-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        reader_id = [u for u in users.json() if u["email"] == scoped_email("topicread@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id, reader_id])
        send_message(stream_id, "topicM", "msg in M")
        send_message(stream_id, "topicN", "msg in N")
        # Mark only topicM as read
        resp = request(
            "post",
            f"{API}/mark-read/stream/{stream_id}/topic/topicM",
            headers=headers("topicread@zulip.test"),
        )
        assert resp.status_code == 200
        # topicM should be 0, topicN still has unread
        resp = request("get", f"{API}/unread-counts", headers=headers("topicread@zulip.test"))
        unreads = resp.json()
        topic_m = [u for u in unreads if u["streamId"] == stream_id and u["topic"] == "topicM"]
        topic_n = [u for u in unreads if u["streamId"] == stream_id and u["topic"] == "topicN"]
        if topic_m:
            assert topic_m[0]["unreadCount"] == 0
        assert len(topic_n) > 0
        assert topic_n[0]["unreadCount"] >= 1

    def test_mark_all_read(self):
        create_user("allread@zulip.test", "All Read")
        resp = create_stream("allread-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        reader_id = [u for u in users.json() if u["email"] == scoped_email("allread@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id, reader_id])
        send_message(stream_id, "allread-topic", "Unread msg")
        resp = request("post", f"{API}/mark-read/all", headers=headers("allread@zulip.test"))
        assert resp.status_code == 200
        resp = request("get", f"{API}/unread-counts", headers=headers("allread@zulip.test"))
        for u in resp.json():
            assert u["unreadCount"] == 0


# ─── Test User Groups ─────────────────────────────────────────────────────────

class TestUserGroups:
    def setup_method(self):
        create_admin()

    def test_create_user_group(self):
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("engineering"),
            "description": "Engineering team",
            "memberIds": [],
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == scoped_name("engineering")
        assert "id" in data

    def test_list_user_groups(self):
        request("post", f"{API}/user-groups", json={
            "name": scoped_name("design"),
        }, headers=headers())
        resp = request("get", f"{API}/user-groups", headers=headers())
        assert resp.status_code == 200
        names = [g["name"] for g in resp.json()]
        assert scoped_name("design") in names

    def test_get_user_group(self):
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("marketing"),
        }, headers=headers())
        group_id = resp.json()["id"]
        resp = request("get", f"{API}/user-groups/{group_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == scoped_name("marketing")

    def test_update_user_group(self):
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("old-name"),
        }, headers=headers())
        group_id = resp.json()["id"]
        resp = request("patch", f"{API}/user-groups/{group_id}", json={
            "name": scoped_name("new-name"),
            "description": "Updated desc",
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == scoped_name("new-name")
        assert resp.json()["description"] == "Updated desc"

    def test_delete_user_group(self):
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("temp-group"),
        }, headers=headers())
        group_id = resp.json()["id"]
        resp = request("delete", f"{API}/user-groups/{group_id}", headers=headers())
        assert resp.status_code == 204

    def test_add_members_to_group(self):
        create_user("groupmem@zulip.test", "Group Member")
        users = request("get", f"{API}/users", headers=headers())
        mem_id = [u for u in users.json() if u["email"] == scoped_email("groupmem@zulip.test")][0]["id"]
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("add-members-group"),
        }, headers=headers())
        group_id = resp.json()["id"]
        resp = request("post", f"{API}/user-groups/{group_id}/members", json={
            "userIds": [mem_id]
        }, headers=headers())
        assert resp.status_code == 200
        assert mem_id in resp.json()["memberIds"]

    def test_remove_member_from_group(self):
        create_user("removemem@zulip.test", "Remove Member")
        users = request("get", f"{API}/users", headers=headers())
        mem_id = [u for u in users.json() if u["email"] == scoped_email("removemem@zulip.test")][0]["id"]
        resp = request("post", f"{API}/user-groups", json={
            "name": scoped_name("remove-members-group"),
            "memberIds": [mem_id],
        }, headers=headers())
        group_id = resp.json()["id"]
        resp = request(
            "delete",
            f"{API}/user-groups/{group_id}/members/{mem_id}",
            headers=headers(),
        )
        assert resp.status_code == 204


# ─── Test Starred Messages ─────────────────────────────────────────────────────

class TestStarredMessages:
    def setup_method(self):
        create_admin()

    def test_star_message(self):
        resp = create_stream("star-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "star-topic", "Star this!")
        msg_id = resp.json()["id"]
        resp = request("post", f"{API}/starred-messages", json={
            "messageId": msg_id
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_list_starred_messages(self):
        resp = create_stream("star-list-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "star-list-topic", "Starred msg")
        msg_id = resp.json()["id"]
        request("post", f"{API}/starred-messages", json={
            "messageId": msg_id
        }, headers=headers())
        resp = request("get", f"{API}/starred-messages", headers=headers())
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()]
        assert msg_id in ids

    def test_unstar_message(self):
        resp = create_stream("unstar-stream")
        stream_id = resp.json()["id"]
        users = request("get", f"{API}/users", headers=headers())
        admin_id = [u for u in users.json() if u["email"] == scoped_email("admin@zulip.test")][0]["id"]
        subscribe_users(stream_id, [admin_id])
        resp = send_message(stream_id, "unstar-topic", "Unstar this!")
        msg_id = resp.json()["id"]
        request("post", f"{API}/starred-messages", json={
            "messageId": msg_id
        }, headers=headers())
        resp = request("delete", f"{API}/starred-messages/{msg_id}", headers=headers())
        assert resp.status_code == 204
        # Verify it's no longer starred
        resp = request("get", f"{API}/starred-messages", headers=headers())
        ids = [m["id"] for m in resp.json()]
        assert msg_id not in ids
