"""
L2 Integration Tests for Zulip Topic-Based Chat API.

Targets LLM bug patterns:
- Pattern 1: camelCase fields (fullName, isPrivate, streamId, senderId, etc.)
- Pattern 2: Nested data (reactions in messages, stages in topics)
- Pattern 3: Filtering (messages by stream/topic/sender/keyword)
- Pattern 4: Status codes (201/204/404/403)
- Pattern 5: Business logic (unread counts, edit history, topic auto-creation)
- Pattern 6: Role permissions (admin, guest, moderator)
- Pattern 7: Side effects (unsubscribe, delete message, read markers)
"""

import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def api(method, path, email=None, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = "test-key"
    if email is not None:
        headers["X-User-Email"] = email
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(
        method,
        url,
        headers=headers,
        **kwargs,
    )


def make_unique_email(prefix="user"):
    return f"{prefix}-{uuid.uuid4().hex}@test.com"


@pytest.fixture
def setup():
    """Create users and stream for tests."""
    owner_email = make_unique_email("owner")
    admin_email = make_unique_email("admin")
    member_email = make_unique_email("member")
    guest_email = make_unique_email("guest")

    owner = api("post", "/api/users", json={"email": owner_email, "fullName": "Owner User", "password": "pass123", "role": "owner"}).json()
    admin = api("post", "/api/users", json={"email": admin_email, "fullName": "Admin User", "password": "pass123", "role": "admin"}).json()
    member = api("post", "/api/users", json={"email": member_email, "fullName": "Member User", "password": "pass123", "role": "member"}).json()
    guest = api("post", "/api/users", json={"email": guest_email, "fullName": "Guest User", "password": "pass123", "role": "guest"}).json()

    # Create a public stream
    stream = api("post", "/api/streams", email=member_email, json={"name": f"general-{uuid.uuid4().hex}", "description": "General chat"}).json()

    # Subscribe all users
    api("post", f"/api/streams/{stream['id']}/subscribers", email=member_email, json={"userIds": [owner["id"], admin["id"], member["id"], guest["id"]]})

    return {
        "owner": owner, "admin": admin, "member": member, "guest": guest,
        "owner_email": owner_email, "admin_email": admin_email,
        "member_email": member_email, "guest_email": guest_email,
        "stream": stream,
    }


class TestUserFieldNaming:
    """Pattern 1: camelCase fields on User responses."""

    def test_user_response_camelcase(self, setup):
        r = api("get", f"/api/users/{setup['member']['id']}", email=setup["member_email"])
        assert r.status_code == 200
        u = r.json()
        assert "fullName" in u
        assert "isActive" in u
        assert "dateJoined" in u
        assert "full_name" not in u
        assert "is_active" not in u
        assert "date_joined" not in u

    def test_stream_response_camelcase(self, setup):
        r = api("get", f"/api/streams/{setup['stream']['id']}", email=setup["member_email"])
        assert r.status_code == 200
        s = r.json()
        assert "isPrivate" in s
        assert "creatorId" in s
        assert "dateCreated" in s
        assert "is_private" not in s
        assert "creator_id" not in s


class TestMessageFieldNaming:
    """Pattern 1: Message response camelCase."""

    def test_message_response_camelcase(self, setup):
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": f"Hello-{uuid.uuid4().hex}", "streamId": setup["stream"]["id"], "topic": "cameltest"
        })
        assert msg.status_code == 201
        m = msg.json()
        assert "senderId" in m
        assert "streamId" in m
        assert "isEdited" in m
        assert "dmConversationId" in m or m.get("dmConversationId") is None
        assert "sender_id" not in m
        assert "stream_id" not in m
        assert "is_edited" not in m


class TestStatusCodes:
    """Pattern 4: Correct HTTP status codes."""

    def test_create_user_returns_201(self):
        e = make_unique_email("sc")
        r = api("post", "/api/users", json={"email": e, "fullName": "SC User", "password": "pass"})
        assert r.status_code == 201

    def test_create_stream_returns_201(self, setup):
        r = api("post", "/api/streams", email=setup["member_email"], json={"name": f"sc-{uuid.uuid4().hex}"})
        assert r.status_code == 201

    def test_send_message_returns_201(self, setup):
        r = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Test message", "streamId": setup["stream"]["id"], "topic": "sc-topic"
        })
        assert r.status_code == 201

    def test_delete_stream_returns_204(self, setup):
        s = api("post", "/api/streams", email=setup["admin_email"], json={"name": f"del-{uuid.uuid4().hex}"}).json()
        r = api("delete", f"/api/streams/{s['id']}", email=setup["admin_email"])
        assert r.status_code == 204

    def test_get_nonexistent_user_returns_404(self, setup):
        r = api("get", "/api/users/0", email=setup["member_email"])
        assert r.status_code == 404

    def test_delete_message_returns_204(self, setup):
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Delete me", "streamId": setup["stream"]["id"], "topic": "del-topic"
        }).json()
        r = api("delete", f"/api/messages/{msg['id']}", email=setup["member_email"])
        assert r.status_code == 204


class TestTopicAutoCreation:
    """Pattern 5: Topics created implicitly when first message sent."""

    def test_topic_created_on_first_message(self, setup):
        topic_name = f"auto-topic-{uuid.uuid4().hex}"
        # Send message to a new topic
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "First message", "streamId": setup["stream"]["id"], "topic": topic_name
        })
        assert msg.status_code == 201
        assert msg.json()["topic"] == topic_name

        # Topic should appear in topics list
        r = api("get", f"/api/streams/{setup['stream']['id']}/topics", email=setup["member_email"])
        assert r.status_code == 200
        topic_names = [t["name"] for t in r.json()]
        assert topic_name in topic_names

    def test_topic_message_count(self, setup):
        topic_name = f"count-topic-{uuid.uuid4().hex}"
        for i in range(3):
            api("post", "/api/messages", email=setup["member_email"], json={
                "content": f"Msg {i}", "streamId": setup["stream"]["id"], "topic": topic_name
            })

        r = api("get", f"/api/streams/{setup['stream']['id']}/topics", email=setup["member_email"])
        topics = r.json()
        t = next((t for t in topics if t["name"] == topic_name), None)
        assert t is not None
        assert t["messageCount"] == 3
        assert t["streamId"] == setup["stream"]["id"]


class TestMessageFiltering:
    """Pattern 3: Message filtering by stream, topic, sender, keyword."""

    def test_filter_by_stream(self, setup):
        topic = f"filter-{uuid.uuid4().hex}"
        api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Stream filter test", "streamId": setup["stream"]["id"], "topic": topic
        })
        r = api("get", "/api/messages", email=setup["member_email"], params={"streamId": setup["stream"]["id"]})
        assert r.status_code == 200
        for m in r.json():
            assert m["streamId"] == setup["stream"]["id"]

    def test_filter_by_topic(self, setup):
        topic = f"specific-{uuid.uuid4().hex}"
        api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Topic filter", "streamId": setup["stream"]["id"], "topic": topic
        })
        r = api("get", "/api/messages", email=setup["member_email"],
                params={"streamId": setup["stream"]["id"], "topic": topic})
        assert r.status_code == 200
        for m in r.json():
            assert m["topic"] == topic

    def test_filter_by_keyword(self, setup):
        unique_word = f"xyzzy{uuid.uuid4().hex}"
        api("post", "/api/messages", email=setup["member_email"], json={
            "content": f"Hello {unique_word} world", "streamId": setup["stream"]["id"], "topic": "keyword-test"
        })
        r = api("get", "/api/messages", email=setup["member_email"], params={"keyword": unique_word})
        assert r.status_code == 200
        assert len(r.json()) >= 1
        for m in r.json():
            assert unique_word.lower() in m["content"].lower()

    def test_filter_by_sender(self, setup):
        api("post", "/api/messages", email=setup["admin_email"], json={
            "content": "Admin msg", "streamId": setup["stream"]["id"], "topic": "sender-test"
        })
        r = api("get", "/api/messages", email=setup["member_email"], params={"senderId": setup["admin"]["id"]})
        assert r.status_code == 200
        for m in r.json():
            assert m["senderId"] == setup["admin"]["id"]


class TestEditHistory:
    """Pattern 5: Edit history records previous content."""

    def test_edit_preserves_history(self, setup):
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Original content", "streamId": setup["stream"]["id"], "topic": "edit-test"
        }).json()

        # Edit message
        r = api("patch", f"/api/messages/{msg['id']}", email=setup["member_email"],
                json={"content": "Edited content"})
        assert r.status_code == 200
        assert r.json()["isEdited"] == True
        assert r.json()["content"] == "Edited content"

        # Check edit history
        r = api("get", f"/api/messages/{msg['id']}/edit-history", email=setup["member_email"])
        assert r.status_code == 200
        history = r.json()
        assert len(history) >= 1
        assert history[0]["previousContent"] == "Original content"
        assert "editedAt" in history[0]


class TestReactions:
    """Pattern 2+5: Reactions nested in messages."""

    def test_add_and_get_reaction(self, setup):
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "React to me", "streamId": setup["stream"]["id"], "topic": "reactions"
        }).json()

        # Add reaction
        r = api("post", f"/api/messages/{msg['id']}/reactions/thumbsup", email=setup["member_email"])
        assert r.status_code == 200

        # Get reactions
        r = api("get", f"/api/messages/{msg['id']}/reactions", email=setup["member_email"])
        assert r.status_code == 200
        reactions = r.json()
        thumbsup = next((rx for rx in reactions if rx["emoji"] == "thumbsup"), None)
        assert thumbsup is not None
        assert setup["member"]["id"] in thumbsup["userIds"]

    def test_reactions_in_message_response(self, setup):
        msg = api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Check reactions field", "streamId": setup["stream"]["id"], "topic": "rxfield"
        }).json()
        api("post", f"/api/messages/{msg['id']}/reactions/heart", email=setup["member_email"])

        r = api("get", f"/api/messages/{msg['id']}", email=setup["member_email"])
        assert r.status_code == 200
        assert "reactions" in r.json()
        reactions = r.json()["reactions"]
        assert any(rx["emoji"] == "heart" for rx in reactions)


class TestRolePermissions:
    """Pattern 6: Role-based access control."""

    def test_guest_cannot_create_stream(self, setup):
        r = api("post", "/api/streams", email=setup["guest_email"], json={"name": "guest-stream"})
        assert r.status_code == 403

    def test_member_cannot_delete_others_messages(self, setup):
        msg = api("post", "/api/messages", email=setup["admin_email"], json={
            "content": "Admin msg", "streamId": setup["stream"]["id"], "topic": "perm-test"
        }).json()
        r = api("delete", f"/api/messages/{msg['id']}", email=setup["member_email"])
        assert r.status_code == 403

    def test_admin_can_delete_stream(self, setup):
        s = api("post", "/api/streams", email=setup["member_email"], json={"name": f"admin-del-{uuid.uuid4().hex}"}).json()
        r = api("delete", f"/api/streams/{s['id']}", email=setup["admin_email"])
        assert r.status_code == 204


class TestUnreadCounts:
    """Pattern 5: Unread count tracking."""

    def test_message_creates_unread_for_others(self, setup):
        topic = f"unread-{uuid.uuid4().hex}"
        # Mark all read first
        api("post", "/api/mark-read/all", email=setup["admin_email"])

        # Member sends message - admin should get unread
        api("post", "/api/messages", email=setup["member_email"], json={
            "content": "Unread test", "streamId": setup["stream"]["id"], "topic": topic
        })

        r = api("get", "/api/unread-counts", email=setup["admin_email"])
        assert r.status_code == 200
        unreads = r.json()
        # Should have at least one unread in the stream/topic
        matching = [u for u in unreads if u["streamId"] == setup["stream"]["id"] and u["topic"] == topic]
        assert len(matching) >= 1
        assert matching[0]["unreadCount"] >= 1


class TestPrivateStream:
    """Pattern 6: Private stream visibility."""

    def test_private_stream_not_visible_to_non_subscribers(self, setup):
        # Create private stream, only subscribe admin
        priv = api("post", "/api/streams", email=setup["admin_email"],
                   json={"name": f"private-{uuid.uuid4().hex}", "isPrivate": True}).json()
        api("post", f"/api/streams/{priv['id']}/subscribers", email=setup["admin_email"],
            json={"userIds": [setup["admin"]["id"]]})

        # Member should not see it in stream list
        r = api("get", "/api/streams", email=setup["member_email"])
        stream_ids = [s["id"] for s in r.json()]
        assert priv["id"] not in stream_ids


class TestDraftsCRUD:
    """Pattern 1+4: Drafts with camelCase fields and correct status codes."""

    def test_draft_lifecycle(self, setup):
        # Create
        r = api("post", "/api/drafts", email=setup["member_email"], json={
            "content": "Draft content", "streamId": setup["stream"]["id"], "topic": "draft-topic"
        })
        assert r.status_code == 201
        draft = r.json()
        assert draft["content"] == "Draft content"
        assert draft["streamId"] == setup["stream"]["id"]
        assert "updatedAt" in draft
        draft_id = draft["id"]

        # Get
        r = api("get", f"/api/drafts/{draft_id}", email=setup["member_email"])
        assert r.status_code == 200
        assert r.json()["content"] == "Draft content"

        # Update
        r = api("patch", f"/api/drafts/{draft_id}", email=setup["member_email"],
                json={"content": "Updated draft"})
        assert r.status_code == 200
        assert r.json()["content"] == "Updated draft"

        # Delete
        r = api("delete", f"/api/drafts/{draft_id}", email=setup["member_email"])
        assert r.status_code == 204


class TestSubscription:
    """Pattern 7: Subscription side effects."""

    def test_unsubscribe_removes_from_subscribers(self, setup):
        stream = api("post", "/api/streams", email=setup["member_email"],
                     json={"name": f"unsub-{uuid.uuid4().hex}"}).json()
        api("post", f"/api/streams/{stream['id']}/subscribers", email=setup["member_email"],
            json={"userIds": [setup["member"]["id"], setup["admin"]["id"]]})

        # Unsubscribe admin
        r = api("delete", f"/api/streams/{stream['id']}/subscribers/{setup['admin']['id']}", email=setup["admin_email"])
        assert r.status_code == 204

        # Verify admin is gone
        r = api("get", f"/api/streams/{stream['id']}/subscribers", email=setup["member_email"])
        assert setup["admin"]["id"] not in r.json()
