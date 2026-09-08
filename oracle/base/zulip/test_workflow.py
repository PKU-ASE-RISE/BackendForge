"""
L3 Workflow Tests for Zulip Topic-Based Chat API.

Multi-step cross-entity workflows:
- Pattern 1: camelCase consistency
- Pattern 3: Message filtering and search
- Pattern 5: Business logic (unread tracking, edit history, topic auto-creation)
- Pattern 6: Role permissions across workflow
- Pattern 7: Side effects (mark-read, reactions, subscriptions)
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


def make_email(prefix="user"):
    return f"{prefix}-{uuid.uuid4().hex}@test.com"


class TestFullConversationWorkflow:
    """
    Full conversation: register → create stream → subscribe → send messages →
    topics auto-created → filter → edit → verify history.
    Patterns: 5 (auto-creation, edit history), 3 (filtering), 1 (camelCase)
    """

    def test_conversation_lifecycle(self):
        # 1. Register users
        alice_email = make_email("alice")
        bob_email = make_email("bob")
        alice = api("post", "/api/users", json={"email": alice_email, "fullName": "Alice Smith", "password": "pass", "role": "member"}).json()
        bob = api("post", "/api/users", json={"email": bob_email, "fullName": "Bob Jones", "password": "pass", "role": "member"}).json()
        assert alice["fullName"] == "Alice Smith"
        assert alice["isActive"] == True

        # 2. Create stream
        stream = api("post", "/api/streams", email=alice_email, json={
            "name": f"project-{uuid.uuid4().hex}", "description": "Project discussions"
        }).json()
        assert stream["isPrivate"] == False
        assert stream["creatorId"] == alice["id"]
        stream_id = stream["id"]

        # 3. Subscribe both
        api("post", f"/api/streams/{stream_id}/subscribers", email=alice_email,
            json={"userIds": [alice["id"], bob["id"]]})

        # 4. Verify subscribers
        r = api("get", f"/api/streams/{stream_id}/subscribers", email=alice_email)
        assert alice["id"] in r.json()
        assert bob["id"] in r.json()

        # 5. Send messages to different topics
        msg1 = api("post", "/api/messages", email=alice_email, json={
            "content": "Let's discuss the API design", "streamId": stream_id, "topic": "api-design"
        }).json()
        msg2 = api("post", "/api/messages", email=bob_email, json={
            "content": "I think REST is the way to go", "streamId": stream_id, "topic": "api-design"
        }).json()
        msg3 = api("post", "/api/messages", email=alice_email, json={
            "content": "Database schema needs review", "streamId": stream_id, "topic": "database"
        }).json()

        # 6. Verify topics auto-created
        r = api("get", f"/api/streams/{stream_id}/topics", email=alice_email)
        topic_names = [t["name"] for t in r.json()]
        assert "api-design" in topic_names
        assert "database" in topic_names
        api_topic = next(t for t in r.json() if t["name"] == "api-design")
        assert api_topic["messageCount"] == 2

        # 7. Filter by topic
        r = api("get", "/api/messages", email=alice_email, params={"streamId": stream_id, "topic": "api-design"})
        assert len(r.json()) == 2
        for m in r.json():
            assert m["topic"] == "api-design"

        # 8. Filter by sender
        r = api("get", "/api/messages", email=alice_email, params={"senderId": bob["id"]})
        for m in r.json():
            assert m["senderId"] == bob["id"]

        # 9. Edit message
        r = api("patch", f"/api/messages/{msg1['id']}", email=alice_email,
                json={"content": "Let's discuss the REST API design"})
        assert r.status_code == 200
        assert r.json()["isEdited"] == True

        # 10. Verify edit history
        r = api("get", f"/api/messages/{msg1['id']}/edit-history", email=alice_email)
        assert len(r.json()) >= 1
        assert r.json()[0]["previousContent"] == "Let's discuss the API design"

        # 11. Delete message
        r = api("delete", f"/api/messages/{msg3['id']}", email=alice_email)
        assert r.status_code == 204

        # 12. Verify deleted
        r = api("get", f"/api/messages/{msg3['id']}", email=alice_email)
        assert r.status_code == 404


class TestUnreadTrackingWorkflow:
    """
    Unread tracking: send messages → verify unreads → mark read → verify cleared.
    Patterns: 5 (unread logic), 7 (mark-read side effects)
    """

    def test_unread_tracking_lifecycle(self):
        alice_email = make_email("alice")
        bob_email = make_email("bob")
        alice = api("post", "/api/users", json={"email": alice_email, "fullName": "Alice", "password": "p", "role": "member"}).json()
        bob = api("post", "/api/users", json={"email": bob_email, "fullName": "Bob", "password": "p", "role": "member"}).json()

        stream = api("post", "/api/streams", email=alice_email, json={"name": f"unread-{uuid.uuid4().hex}"}).json()
        api("post", f"/api/streams/{stream['id']}/subscribers", email=alice_email,
            json={"userIds": [alice["id"], bob["id"]]})

        # Mark all read for bob
        api("post", "/api/mark-read/all", email=bob_email)

        # Alice sends messages
        topic1 = f"topic1-{uuid.uuid4().hex}"
        topic2 = f"topic2-{uuid.uuid4().hex}"
        api("post", "/api/messages", email=alice_email, json={"content": "T1 M1", "streamId": stream["id"], "topic": topic1})
        api("post", "/api/messages", email=alice_email, json={"content": "T1 M2", "streamId": stream["id"], "topic": topic1})
        api("post", "/api/messages", email=alice_email, json={"content": "T2 M1", "streamId": stream["id"], "topic": topic2})

        # Bob should have unreads
        r = api("get", "/api/unread-counts", email=bob_email)
        unreads = r.json()
        t1_unread = next((u for u in unreads if u["streamId"] == stream["id"] and u["topic"] == topic1), None)
        t2_unread = next((u for u in unreads if u["streamId"] == stream["id"] and u["topic"] == topic2), None)
        assert t1_unread is not None
        assert t1_unread["unreadCount"] == 2
        assert t2_unread is not None
        assert t2_unread["unreadCount"] == 1

        # Mark topic1 as read
        api("post", f"/api/mark-read/stream/{stream['id']}/topic/{topic1}", email=bob_email)

        # Verify topic1 cleared, topic2 still unread
        r = api("get", "/api/unread-counts", email=bob_email)
        unreads = r.json()
        t1_unread = next((u for u in unreads if u["streamId"] == stream["id"] and u["topic"] == topic1), None)
        t2_unread = next((u for u in unreads if u["streamId"] == stream["id"] and u["topic"] == topic2), None)
        assert t1_unread is None or t1_unread["unreadCount"] == 0
        assert t2_unread is not None
        assert t2_unread["unreadCount"] == 1

        # Mark stream as read
        api("post", f"/api/mark-read/stream/{stream['id']}", email=bob_email)

        # All unreads in this stream should be 0
        r = api("get", "/api/unread-counts", email=bob_email)
        unreads = r.json()
        stream_unreads = [u for u in unreads if u["streamId"] == stream["id"] and u.get("unreadCount", 0) > 0]
        assert len(stream_unreads) == 0


class TestDirectMessageWorkflow:
    """
    DM conversations: create DM → send messages → filter → verify.
    Patterns: 5 (DM logic), 1 (camelCase), 4 (status codes)
    """

    def test_dm_conversation_lifecycle(self):
        alice_email = make_email("alice")
        bob_email = make_email("bob")
        alice = api("post", "/api/users", json={"email": alice_email, "fullName": "Alice", "password": "p", "role": "member"}).json()
        bob = api("post", "/api/users", json={"email": bob_email, "fullName": "Bob", "password": "p", "role": "member"}).json()

        # Create DM
        dm = api("post", "/api/dm-conversations", email=alice_email, json={"participantIds": [bob["id"]]})
        assert dm.status_code == 201
        dm_data = dm.json()
        assert "participantIds" in dm_data
        assert alice["id"] in dm_data["participantIds"]
        assert bob["id"] in dm_data["participantIds"]
        dm_id = dm_data["id"]

        # Send messages
        msg1 = api("post", "/api/messages", email=alice_email, json={
            "content": "Hey Bob!", "dmConversationId": dm_id
        })
        assert msg1.status_code == 201
        assert msg1.json()["dmConversationId"] == dm_id

        msg2 = api("post", "/api/messages", email=bob_email, json={
            "content": "Hey Alice!", "dmConversationId": dm_id
        })
        assert msg2.status_code == 201

        # Get DM messages
        r = api("get", f"/api/dm-conversations/{dm_id}/messages", email=alice_email)
        assert r.status_code == 200
        assert len(r.json()) == 2

        # List DM conversations
        r = api("get", "/api/dm-conversations", email=alice_email)
        assert r.status_code == 200
        dm_ids = [d["id"] for d in r.json()]
        assert dm_id in dm_ids

        # Filter messages by DM conversation
        r = api("get", "/api/messages", email=alice_email, params={"dmConversationId": dm_id})
        assert r.status_code == 200
        assert len(r.json()) >= 2
        for m in r.json():
            assert m["dmConversationId"] == dm_id


class TestReactionsWorkflow:
    """
    Reactions: multiple users react → verify aggregation → remove → verify.
    Patterns: 2 (nested reactions), 5 (dedup logic), 7 (side effects)
    """

    def test_reactions_aggregation(self):
        alice_email = make_email("alice")
        bob_email = make_email("bob")
        alice = api("post", "/api/users", json={"email": alice_email, "fullName": "Alice", "password": "p", "role": "member"}).json()
        bob = api("post", "/api/users", json={"email": bob_email, "fullName": "Bob", "password": "p", "role": "member"}).json()

        stream = api("post", "/api/streams", email=alice_email, json={"name": f"react-{uuid.uuid4().hex}"}).json()
        api("post", f"/api/streams/{stream['id']}/subscribers", email=alice_email,
            json={"userIds": [alice["id"], bob["id"]]})

        msg = api("post", "/api/messages", email=alice_email, json={
            "content": "Great news!", "streamId": stream["id"], "topic": "reactions"
        }).json()

        # Both users react with thumbsup
        api("post", f"/api/messages/{msg['id']}/reactions/thumbsup", email=alice_email)
        api("post", f"/api/messages/{msg['id']}/reactions/thumbsup", email=bob_email)
        # Alice also reacts with heart
        api("post", f"/api/messages/{msg['id']}/reactions/heart", email=alice_email)

        # Get reactions
        r = api("get", f"/api/messages/{msg['id']}/reactions", email=alice_email)
        reactions = r.json()
        thumbsup = next(rx for rx in reactions if rx["emoji"] == "thumbsup")
        assert alice["id"] in thumbsup["userIds"]
        assert bob["id"] in thumbsup["userIds"]
        heart = next(rx for rx in reactions if rx["emoji"] == "heart")
        assert alice["id"] in heart["userIds"]

        # Remove alice's thumbsup
        api("delete", f"/api/messages/{msg['id']}/reactions/thumbsup", email=alice_email)

        # Verify alice removed from thumbsup
        r = api("get", f"/api/messages/{msg['id']}/reactions", email=alice_email)
        reactions = r.json()
        thumbsup = next(rx for rx in reactions if rx["emoji"] == "thumbsup")
        assert alice["id"] not in thumbsup["userIds"]
        assert bob["id"] in thumbsup["userIds"]


class TestRolePermissionsWorkflow:
    """
    Role permissions: guest restrictions → admin powers → owner role change.
    Patterns: 6 (permissions), 4 (status codes), 1 (fields)
    """

    def test_role_enforcement(self):
        owner_email = make_email("owner")
        admin_email = make_email("admin")
        member_email = make_email("member")
        guest_email = make_email("guest")

        owner = api("post", "/api/users", json={"email": owner_email, "fullName": "Owner", "password": "p", "role": "owner"}).json()
        admin = api("post", "/api/users", json={"email": admin_email, "fullName": "Admin", "password": "p", "role": "admin"}).json()
        member = api("post", "/api/users", json={"email": member_email, "fullName": "Member", "password": "p", "role": "member"}).json()
        guest = api("post", "/api/users", json={"email": guest_email, "fullName": "Guest", "password": "p", "role": "guest"}).json()

        # Guest cannot create streams
        r = api("post", "/api/streams", email=guest_email, json={"name": "guest-stream"})
        assert r.status_code == 403

        # Member can create stream
        stream = api("post", "/api/streams", email=member_email, json={"name": f"perm-{uuid.uuid4().hex}"}).json()

        # Member cannot delete stream (requires admin)
        r = api("delete", f"/api/streams/{stream['id']}", email=member_email)
        assert r.status_code == 403

        # Admin can delete stream
        r = api("delete", f"/api/streams/{stream['id']}", email=admin_email)
        assert r.status_code == 204

        # Admin can deactivate user
        r = api("post", f"/api/users/{guest['id']}/deactivate", email=admin_email)
        assert r.status_code == 200
        assert r.json()["isActive"] == False

        # Owner can change roles
        r = api("patch", f"/api/users/{member['id']}", email=owner_email, json={"role": "moderator"})
        assert r.status_code == 200
        assert r.json()["role"] == "moderator"


class TestStarredMessagesWorkflow:
    """
    Starred messages: star → list → unstar → verify removed.
    Patterns: 4 (status codes), 7 (side effects)
    """

    def test_starred_messages_lifecycle(self):
        email = make_email("star")
        user = api("post", "/api/users", json={"email": email, "fullName": "Star User", "password": "p", "role": "member"}).json()

        stream = api("post", "/api/streams", email=email, json={"name": f"star-{uuid.uuid4().hex}"}).json()
        api("post", f"/api/streams/{stream['id']}/subscribers", email=email, json={"userIds": [user["id"]]})

        msg1 = api("post", "/api/messages", email=email, json={"content": "Star me 1", "streamId": stream["id"], "topic": "star"}).json()
        msg2 = api("post", "/api/messages", email=email, json={"content": "Star me 2", "streamId": stream["id"], "topic": "star"}).json()

        # Star messages
        api("post", "/api/starred-messages", email=email, json={"messageId": msg1["id"]})
        api("post", "/api/starred-messages", email=email, json={"messageId": msg2["id"]})

        # List starred
        r = api("get", "/api/starred-messages", email=email)
        assert r.status_code == 200
        starred_ids = [m["id"] for m in r.json()]
        assert msg1["id"] in starred_ids
        assert msg2["id"] in starred_ids

        # Unstar
        r = api("delete", f"/api/starred-messages/{msg1['id']}", email=email)
        assert r.status_code == 204

        # Verify removed
        r = api("get", "/api/starred-messages", email=email)
        starred_ids = [m["id"] for m in r.json()]
        assert msg1["id"] not in starred_ids
        assert msg2["id"] in starred_ids


class TestPrivateStreamWorkflow:
    """
    Private streams: create → only subscribers see it → non-subscriber blocked.
    Patterns: 6 (access control), 4 (403), 7 (subscription effects)
    """

    def test_private_stream_isolation(self):
        alice_email = make_email("alice")
        bob_email = make_email("bob")
        alice = api("post", "/api/users", json={"email": alice_email, "fullName": "Alice", "password": "p", "role": "admin"}).json()
        bob = api("post", "/api/users", json={"email": bob_email, "fullName": "Bob", "password": "p", "role": "member"}).json()

        # Alice creates private stream
        priv = api("post", "/api/streams", email=alice_email, json={
            "name": f"secret-{uuid.uuid4().hex}", "isPrivate": True
        }).json()
        assert priv["isPrivate"] == True

        # Subscribe only alice
        api("post", f"/api/streams/{priv['id']}/subscribers", email=alice_email,
            json={"userIds": [alice["id"]]})

        # Bob cannot see it in list
        r = api("get", "/api/streams", email=bob_email)
        stream_ids = [s["id"] for s in r.json()]
        assert priv["id"] not in stream_ids

        # Bob cannot get it directly
        r = api("get", f"/api/streams/{priv['id']}", email=bob_email)
        assert r.status_code == 403

        # Alice sends message
        msg = api("post", "/api/messages", email=alice_email, json={
            "content": "Secret stuff", "streamId": priv["id"], "topic": "private-topic"
        })
        assert msg.status_code == 201

        # Bob cannot send to it
        r = api("post", "/api/messages", email=bob_email, json={
            "content": "Can I?", "streamId": priv["id"], "topic": "private-topic"
        })
        assert r.status_code == 403

        # Subscribe bob
        api("post", f"/api/streams/{priv['id']}/subscribers", email=alice_email,
            json={"userIds": [bob["id"]]})

        # Now bob can see it
        r = api("get", f"/api/streams/{priv['id']}", email=bob_email)
        assert r.status_code == 200


class TestUserGroupWorkflow:
    """
    User groups: create → add members → verify → remove member → verify.
    Patterns: 2 (memberIds array), 7 (side effects), 4 (status codes)
    """

    def test_user_group_lifecycle(self):
        email = make_email("grp")
        user1 = api("post", "/api/users", json={"email": make_email("g1"), "fullName": "G1", "password": "p", "role": "member"}).json()
        user2 = api("post", "/api/users", json={"email": make_email("g2"), "fullName": "G2", "password": "p", "role": "member"}).json()
        user3 = api("post", "/api/users", json={"email": make_email("g3"), "fullName": "G3", "password": "p", "role": "member"}).json()
        admin = api("post", "/api/users", json={"email": email, "fullName": "GroupAdmin", "password": "p", "role": "admin"}).json()

        # Create group
        grp = api("post", "/api/user-groups", email=email, json={
            "name": f"team-{uuid.uuid4().hex}", "description": "Dev team",
            "memberIds": [user1["id"], user2["id"]]
        })
        assert grp.status_code == 201
        assert user1["id"] in grp.json()["memberIds"]
        assert user2["id"] in grp.json()["memberIds"]
        grp_id = grp.json()["id"]

        # Add user3
        r = api("post", f"/api/user-groups/{grp_id}/members", email=email, json={"userIds": [user3["id"]]})
        assert r.status_code == 200
        assert user3["id"] in r.json()["memberIds"]

        # Remove user1
        r = api("delete", f"/api/user-groups/{grp_id}/members/{user1['id']}", email=email)
        assert r.status_code == 204

        # Verify
        r = api("get", f"/api/user-groups/{grp_id}", email=email)
        assert user1["id"] not in r.json()["memberIds"]
        assert user2["id"] in r.json()["memberIds"]
        assert user3["id"] in r.json()["memberIds"]

        # Delete group
        r = api("delete", f"/api/user-groups/{grp_id}", email=email)
        assert r.status_code == 204

        # Verify gone
        r = api("get", f"/api/user-groups/{grp_id}", email=email)
        assert r.status_code == 404


class TestMuteTopicWorkflow:
    """
    Topic muting: subscribe → mute topic → verify.
    Patterns: 5 (mute logic), 1 (camelCase: isMuted)
    """

    def test_mute_and_unmute_topic(self):
        email = make_email("mute")
        user = api("post", "/api/users", json={"email": email, "fullName": "Muter", "password": "p", "role": "member"}).json()

        stream = api("post", "/api/streams", email=email, json={"name": f"mute-{uuid.uuid4().hex}"}).json()
        api("post", f"/api/streams/{stream['id']}/subscribers", email=email, json={"userIds": [user["id"]]})

        # Send message to create topic
        api("post", "/api/messages", email=email, json={
            "content": "Mute test", "streamId": stream["id"], "topic": "noisy-topic"
        })

        # Mute the topic
        r = api("post", f"/api/streams/{stream['id']}/mute-topic", email=email,
                json={"topic": "noisy-topic", "isMuted": True})
        assert r.status_code == 200
        assert r.json()["isMuted"] == True

        # Unmute
        r = api("post", f"/api/streams/{stream['id']}/mute-topic", email=email,
                json={"topic": "noisy-topic", "isMuted": False})
        assert r.status_code == 200
        assert r.json()["isMuted"] == False
