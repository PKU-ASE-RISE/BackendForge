"""
BackendForge — L3 Workflow Tests for Ntfy Task

Multi-step workflow tests crossing 3+ entity types with 6-12 steps each.
Targets adversarial patterns:
- Pattern 1: camelCase field names
- Pattern 2: Nested/related data
- Pattern 3: Filter params not implemented
- Pattern 5: Business logic not computed
- Pattern 6: Data isolation
- Pattern 7: Cascade/side-effect
- Pattern 8: Duplicate/ordering

"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
UNIQUE = uuid.uuid4().hex[:8]

ADMIN_USER_ID = "integration-admin"
ADMIN_TOKEN = "integration-admin-token"
ADMIN_HEADERS = {
    "X-User-Id": ADMIN_USER_ID,
    "X-Token": ADMIN_TOKEN,
    "Content-Type": "application/json",
}


def make_user_headers(name):
    return {
        "X-User-Id": f"{name}-{UNIQUE}",
        "X-Token": f"token-{name}-{UNIQUE}",
        "Content-Type": "application/json",
    }


# ── HTTP Helpers ──

def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


def post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or ADMIN_HEADERS, timeout=30)


def ensure_admin():
    """Ensure admin user is the first user created."""
    get("/api/health")
    get("/api/topics", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════
# L3 Workflow Tests
# ════════════════════════════════════════════════════════════════════


class TestWorkflowPublishSubscribeFilter:
    """Pattern 1+2+3+5: Full pub/sub workflow with filtering and stats."""

    def test_full_pubsub_lifecycle_with_stats(self):
        """
        Workflow: Create topic → publish messages with varied priority/tags →
        subscribe → filter messages → verify stats computation.
        Patterns: 1 (camelCase), 3 (filtering works), 5 (stats computed)
        """
        ensure_admin()
        topic = f"wf-pubsub-{UNIQUE}"

        # 1. Create topic
        r = post("/api/topics", {"name": topic, "description": "workflow topic"})
        assert r.status_code == 201
        assert r.json()["name"] == topic
        assert "createdAt" in r.json()

        # 2. Subscribe to topic
        r = post("/api/subscriptions", {"topic": topic, "filterPriority": 3})
        assert r.status_code == 201
        sub_id = r.json()["id"]
        assert r.json()["filterPriority"] == 3
        assert "userId" in r.json()

        # 3. Publish multiple messages with different priorities and tags
        r = post(f"/api/topics/{topic}/messages", {
            "message": "low priority info",
            "priority": 1,
            "tags": "info",
            "title": "Info Update",
        })
        assert r.status_code == 201
        assert r.json()["publishedAt"] is not None

        r = post(f"/api/topics/{topic}/messages", {
            "message": "critical alert",
            "priority": 5,
            "tags": "alert,critical",
            "title": "CRITICAL Alert",
        })
        assert r.status_code == 201
        msg_high_id = r.json()["id"]

        r = post(f"/api/topics/{topic}/messages", {
            "message": "medium warning",
            "priority": 3,
            "tags": "warning",
            "title": "Warning Notice",
        })
        assert r.status_code == 201

        # 4. Filter by priority — only high priority
        r = get(f"/api/topics/{topic}/messages", params={"priority": 4})
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 1
        assert msgs[0]["priority"] == 5
        assert msgs[0]["message"] == "critical alert"
        assert msgs[0]["tags"] == ["alert", "critical"]

        # 5. Filter by tags
        r = get(f"/api/topics/{topic}/messages", params={"tags": "warning"})
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 1
        assert "warning" in msgs[0]["tags"]

        # 6. Filter by title
        r = get(f"/api/topics/{topic}/messages", params={"title": "CRITICAL"})
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 1
        assert "CRITICAL" in msgs[0]["title"]

        # 7. Verify stats are correctly computed
        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["topic"] == topic
        assert stats["messageCount"] == 3
        assert stats["subscriberCount"] == 1

        # 8. Get message by ID — verify all fields
        r = get(f"/api/messages/{msg_high_id}")
        assert r.status_code == 200
        msg = r.json()
        assert msg["id"] == msg_high_id
        assert msg["topic"] == topic
        assert msg["priority"] == 5
        assert isinstance(msg["tags"], list)
        assert "publishedAt" in msg
        assert "publisherId" in msg


class TestWorkflowAccessControlLifecycle:
    """Pattern 5+6+7: Access control restricts then opens access."""

    def test_access_control_restrict_then_open(self):
        """
        Workflow: Create topic → open by default → restrict → verify denied →
        grant access → verify allowed → remove rules → open again.
        Patterns: 5 (ACL enforced), 6 (isolation), 7 (side effects)
        """
        ensure_admin()
        user_headers = make_user_headers("acl-user")
        topic = f"wf-acl-{UNIQUE}"

        # 1. Create topic (open by default)
        r = post("/api/topics", {"name": topic})
        assert r.status_code == 201

        # 2. User can publish to open topic
        get("/api/topics", headers=user_headers)  # auto-create user
        r = post(f"/api/topics/{topic}/messages", {"message": "open access"}, headers=user_headers)
        assert r.status_code == 201

        # 3. Admin restricts topic — give only admin access
        users = get("/api/users").json()
        admin_user = next(u for u in users if u["username"] == ADMIN_HEADERS["X-User-Id"])
        put(f"/api/topics/{topic}/access", {
            "userId": admin_user["id"],
            "read": True,
            "write": True,
        })

        # 4. User is now denied write
        r = post(f"/api/topics/{topic}/messages", {"message": "denied"}, headers=user_headers)
        assert r.status_code == 403

        # 5. User is also denied read
        r = get(f"/api/topics/{topic}/messages", headers=user_headers)
        assert r.status_code == 403

        # 6. Admin grants user read+write
        acl_user = next(u for u in users if u["username"] == user_headers["X-User-Id"])
        r = put(f"/api/topics/{topic}/access", {
            "userId": acl_user["id"],
            "read": True,
            "write": True,
        })
        assert r.status_code == 200
        assert r.json()["read"] is True
        assert r.json()["write"] is True

        # 7. User can now publish
        r = post(f"/api/topics/{topic}/messages", {"message": "allowed now"}, headers=user_headers)
        assert r.status_code == 201

        # 8. User can now read
        r = get(f"/api/topics/{topic}/messages", headers=user_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # 9. Remove all access rules → topic becomes open again
        delete(f"/api/topics/{topic}/access/{admin_user['id']}")
        delete(f"/api/topics/{topic}/access/{acl_user['id']}")

        # 10. A third user (no rule) can now access the open topic
        user3_headers = make_user_headers("acl-user3")
        get("/api/topics", headers=user3_headers)
        r = post(f"/api/topics/{topic}/messages", {"message": "open again"}, headers=user3_headers)
        assert r.status_code == 201


class TestWorkflowCascadeDeleteTopic:
    """Pattern 7: Deleting a topic cascades to messages, subscriptions, access rules."""

    def test_topic_delete_cascades_all_related(self):
        """
        Workflow: Create topic → publish messages → subscribe → add access rules →
        delete topic → verify all related data is gone.
        Patterns: 7 (cascade), 5 (stats updated)
        """
        ensure_admin()
        topic = f"wf-cascade-{UNIQUE}"
        user_headers = make_user_headers("cascade-user")

        # 1. Create topic
        r = post("/api/topics", {"name": topic})
        assert r.status_code == 201

        # 2. Publish messages
        r = post(f"/api/topics/{topic}/messages", {"message": "msg1"})
        assert r.status_code == 201
        msg1_id = r.json()["id"]

        r = post(f"/api/topics/{topic}/messages", {"message": "msg2"})
        assert r.status_code == 201
        msg2_id = r.json()["id"]

        # 3. Subscribe
        r = post("/api/subscriptions", {"topic": topic})
        assert r.status_code == 201
        sub_id = r.json()["id"]

        # 4. Ensure second user and subscribe them too
        get("/api/topics", headers=user_headers)
        r = post("/api/subscriptions", {"topic": topic}, headers=user_headers)
        assert r.status_code == 201
        sub2_id = r.json()["id"]

        # 5. Add access rule
        users = get("/api/users").json()
        cascade_user = next(u for u in users if u["username"] == user_headers["X-User-Id"])
        put(f"/api/topics/{topic}/access", {
            "userId": cascade_user["id"],
            "read": True,
            "write": True,
        })

        # 6. Delete topic
        r = delete(f"/api/topics/{topic}")
        assert r.status_code == 200

        # 7. Topic is gone
        r = get(f"/api/topics/{topic}")
        assert r.status_code == 404

        # 8. Messages are gone
        r = get(f"/api/messages/{msg1_id}")
        assert r.status_code == 404
        r = get(f"/api/messages/{msg2_id}")
        assert r.status_code == 404

        # 9. Subscriptions are gone
        r = get(f"/api/subscriptions/{sub_id}")
        assert r.status_code == 404
        r = get(f"/api/subscriptions/{sub2_id}", headers=user_headers)
        assert r.status_code == 404


class TestWorkflowScheduledMessageLifecycle:
    """Pattern 3+5: Scheduled messages appear/disappear from correct endpoints."""

    def test_scheduled_message_full_lifecycle(self):
        """
        Workflow: Publish regular + scheduled → verify regular list → verify scheduled list →
        cancel scheduled → verify gone → publish past-scheduled → verify delivered.
        Patterns: 3 (filtering), 5 (delivered flag), 4 (status codes)
        """
        ensure_admin()
        topic = f"wf-sched-{UNIQUE}"

        # 1. Publish regular message
        r = post(f"/api/topics/{topic}/messages", {"message": "immediate"})
        assert r.status_code == 201
        imm_id = r.json()["id"]
        assert r.json()["delivered"] is True

        # 2. Publish scheduled (future) message
        r = post(f"/api/topics/{topic}/messages", {
            "message": "future delivery",
            "scheduledAt": "2099-12-31T23:59:59Z",
        })
        assert r.status_code == 201
        sched_id = r.json()["id"]
        assert r.json()["delivered"] is False
        assert r.json()["scheduledAt"] is not None

        # 3. Regular list excludes scheduled
        r = get(f"/api/topics/{topic}/messages")
        assert r.status_code == 200
        msgs = r.json()
        ids = [m["id"] for m in msgs]
        assert imm_id in ids
        assert sched_id not in ids

        # 4. Scheduled endpoint includes only scheduled
        r = get(f"/api/topics/{topic}/messages/scheduled")
        assert r.status_code == 200
        msgs = r.json()
        ids = [m["id"] for m in msgs]
        assert sched_id in ids
        assert imm_id not in ids

        # 5. ?scheduled=true shows both
        r = get(f"/api/topics/{topic}/messages", params={"scheduled": "true"})
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert imm_id in ids
        assert sched_id in ids

        # 6. Cancel scheduled message
        r = delete(f"/api/messages/{sched_id}/schedule")
        assert r.status_code == 200

        # 7. Scheduled message is completely gone
        r = get(f"/api/messages/{sched_id}")
        assert r.status_code == 404

        # 8. Cannot cancel an already-delivered message
        r = delete(f"/api/messages/{imm_id}/schedule")
        assert r.status_code == 400

        # 9. Publish with past scheduledAt — treated as immediate
        r = post(f"/api/topics/{topic}/messages", {
            "message": "past scheduled",
            "scheduledAt": "2000-01-01T00:00:00Z",
        })
        assert r.status_code == 201
        assert r.json()["delivered"] is True

        # 10. Verify it appears in regular list
        r = get(f"/api/topics/{topic}/messages")
        assert r.status_code == 200
        texts = [m["message"] for m in r.json()]
        assert "past scheduled" in texts


class TestWorkflowRateLimitingLifecycle:
    """Pattern 5+7: Rate limiting with tier assignment and reset."""

    def test_rate_limit_assign_exceed_reset(self):
        """
        Workflow: Create tier → create user → assign tier → publish up to limit →
        exceed → get 429 → admin resets → can publish again.
        Patterns: 5 (rate limit enforced), 7 (reset side effect)
        """
        ensure_admin()
        user_headers = make_user_headers("ratelim")

        # 1. Create tier with strict limits
        r = post("/api/tiers", {
            "name": f"strict-{UNIQUE}",
            "messagesPerDay": 100,
            "messagesPerMinute": 2,
        })
        assert r.status_code == 201
        tier = r.json()
        assert tier["messagesPerDay"] == 100
        assert tier["messagesPerMinute"] == 2
        tier_name = tier["name"]

        # 2. Ensure user exists
        get("/api/topics", headers=user_headers)

        # 3. Assign tier to user
        users = get("/api/users").json()
        rate_user = next(u for u in users if u["username"] == user_headers["X-User-Id"])
        r = put(f"/api/users/{rate_user['id']}", {"tier": tier_name})
        assert r.status_code == 200
        assert r.json()["tier"] == tier_name

        # 4. Publish up to the per-minute limit
        topic = f"ratelim-topic-{UNIQUE}"
        for i in range(2):
            r = post(f"/api/topics/{topic}/messages", {"message": f"msg-{i}"}, headers=user_headers)
            assert r.status_code == 201

        # 5. Exceeding limit → 429
        r = post(f"/api/topics/{topic}/messages", {"message": "over"}, headers=user_headers)
        assert r.status_code == 429

        # 6. Admin resets rate limit
        r = post("/api/admin/rate-reset", {"userId": rate_user["id"]})
        assert r.status_code == 200

        # 7. User can publish again
        r = post(f"/api/topics/{topic}/messages", {"message": "after reset"}, headers=user_headers)
        assert r.status_code == 201
        assert r.json()["message"] == "after reset"


class TestWorkflowUserDeletionCascade:
    """Pattern 7: Deleting a user cascades to tokens, subscriptions, published messages."""

    def test_user_delete_cascades(self):
        """
        Workflow: Create user → user creates token → user subscribes →
        user publishes → admin deletes user → verify tokens/subs/messages gone.
        Patterns: 7 (cascade), 6 (isolation)
        """
        ensure_admin()
        username = f"doomed-{UNIQUE}"
        user_headers = {
            "X-User-Id": username,
            "X-Token": f"token-{username}",
            "Content-Type": "application/json",
        }

        # 1. Auto-create user
        get("/api/topics", headers=user_headers)

        # 2. User creates a token
        r = post("/api/tokens", {"label": "doomed-token"}, headers=user_headers)
        assert r.status_code == 201
        token_id = r.json()["id"]

        # 3. User subscribes to a topic
        topic = f"doomed-topic-{UNIQUE}"
        post("/api/topics", {"name": topic})
        r = post("/api/subscriptions", {"topic": topic}, headers=user_headers)
        assert r.status_code == 201
        sub_id = r.json()["id"]

        # 4. User publishes a message
        r = post(f"/api/topics/{topic}/messages", {"message": "my message"}, headers=user_headers)
        assert r.status_code == 201
        msg_id = r.json()["id"]

        # 5. Admin finds the user and deletes them
        users = get("/api/users").json()
        doomed = next(u for u in users if u["username"] == username)
        r = delete(f"/api/users/{doomed['id']}")
        assert r.status_code == 200

        # 6. User is gone
        r = get(f"/api/users/{doomed['id']}")
        assert r.status_code == 404

        # 7. Token is gone (admin creates own token list, won't see doomed's)
        # We can try to access subscription
        r = get(f"/api/subscriptions/{sub_id}")
        assert r.status_code == 404

        # 8. Message is gone (published messages cascade)
        r = get(f"/api/messages/{msg_id}")
        assert r.status_code == 404


class TestWorkflowMultiUserTopicInteraction:
    """Pattern 6+5+1: Multiple users interact on same topic — isolation of subs, shared messages."""

    def test_multi_user_topic_messages_shared_subs_isolated(self):
        """
        Workflow: Two users publish to same topic → both see all messages →
        subscriptions are user-scoped → stats reflect both.
        Patterns: 6 (sub isolation), 5 (stats), 1 (camelCase)
        """
        ensure_admin()
        user_a = make_user_headers("multi-a")
        user_b = make_user_headers("multi-b")
        topic = f"wf-multi-{UNIQUE}"

        # 1. Create topic
        r = post("/api/topics", {"name": topic})
        assert r.status_code == 201

        # 2. Both users auto-create
        get("/api/topics", headers=user_a)
        get("/api/topics", headers=user_b)

        # 3. User A publishes
        r = post(f"/api/topics/{topic}/messages", {
            "message": "from A",
            "priority": 2,
            "tags": "team-a",
        }, headers=user_a)
        assert r.status_code == 201
        assert r.json()["publisherId"] is not None
        pub_a_id = r.json()["publisherId"]

        # 4. User B publishes
        r = post(f"/api/topics/{topic}/messages", {
            "message": "from B",
            "priority": 4,
            "tags": "team-b",
        }, headers=user_b)
        assert r.status_code == 201
        pub_b_id = r.json()["publisherId"]
        assert pub_b_id != pub_a_id  # different users

        # 5. User A can see both messages
        r = get(f"/api/topics/{topic}/messages", headers=user_a)
        assert r.status_code == 200
        msgs = r.json()
        texts = [m["message"] for m in msgs]
        assert "from A" in texts
        assert "from B" in texts

        # 6. User A subscribes
        r = post("/api/subscriptions", {"topic": topic}, headers=user_a)
        assert r.status_code == 201

        # 7. User B subscribes
        r = post("/api/subscriptions", {"topic": topic}, headers=user_b)
        assert r.status_code == 201

        # 8. User A's subscription list doesn't include User B's sub
        r = get("/api/subscriptions", headers=user_a)
        assert r.status_code == 200
        a_subs = r.json()
        assert len(a_subs) >= 1
        # Check that all subs belong to user A
        a_user_ids = set(s["userId"] for s in a_subs)
        assert len(a_user_ids) == 1  # all same userId

        # 9. Stats show both subscribers
        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["messageCount"] == 2
        assert stats["subscriberCount"] == 2
        assert stats["topic"] == topic

        # 10. Filtering still works - filter by priority
        r = get(f"/api/topics/{topic}/messages", params={"priority": 4}, headers=user_b)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 1
        assert msgs[0]["message"] == "from B"
        assert msgs[0]["priority"] == 4


class TestWorkflowTierLifecycle:
    """Pattern 5+7+8: Tier management lifecycle with constraints."""

    def test_tier_create_assign_prevent_delete(self):
        """
        Workflow: Create tier → assign to user → try delete (blocked) →
        unassign user → delete succeeds.
        Patterns: 5 (logic enforced), 7 (assignment side effect), 8 (ordering)
        """
        ensure_admin()

        # 1. Create tier
        r = post("/api/tiers", {
            "name": f"lifecycle-tier-{UNIQUE}",
            "messagesPerDay": 200,
            "messagesPerMinute": 20,
        })
        assert r.status_code == 201
        tier_id = r.json()["id"]
        tier_name = r.json()["name"]
        assert r.json()["messagesPerDay"] == 200
        assert r.json()["messagesPerMinute"] == 20

        # 2. Create user
        username = f"tier-lifecycle-user-{UNIQUE}"
        r = post("/api/users", {"username": username})
        assert r.status_code == 201
        user_id = r.json()["id"]

        # 3. Assign tier to user
        r = put(f"/api/users/{user_id}", {"tier": tier_name})
        assert r.status_code == 200
        assert r.json()["tier"] == tier_name

        # 4. Try to delete tier — should fail (in use)
        r = delete(f"/api/tiers/{tier_id}")
        assert r.status_code == 400

        # 5. Unassign tier from user
        r = put(f"/api/users/{user_id}", {"tier": None})
        assert r.status_code == 200
        assert r.json()["tier"] is None

        # 6. Now delete tier — should succeed
        r = delete(f"/api/tiers/{tier_id}")
        assert r.status_code == 200

        # 7. Tier is gone from list
        r = get("/api/tiers")
        assert r.status_code == 200
        tier_names = [t["name"] for t in r.json()]
        assert tier_name not in tier_names


class TestWorkflowAdminPruneMessages:
    """Pattern 5+7: Prune operation actually deletes old messages and updates stats."""

    def test_prune_removes_old_keeps_recent(self):
        """
        Workflow: Publish messages → wait → publish more → prune →
        verify old gone, new remain → stats updated.
        Patterns: 5 (prune logic), 7 (side effect on stats)
        """
        ensure_admin()
        topic = f"wf-prune-{UNIQUE}"

        # 1. Publish "old" messages
        r = post(f"/api/topics/{topic}/messages", {"message": "old-1"})
        assert r.status_code == 201
        old_id_1 = r.json()["id"]

        r = post(f"/api/topics/{topic}/messages", {"message": "old-2"})
        assert r.status_code == 201
        old_id_2 = r.json()["id"]

        # 2. Wait so they become "old"
        time.sleep(2)

        # 3. Publish "new" message
        r = post(f"/api/topics/{topic}/messages", {"message": "new-1"})
        assert r.status_code == 201
        new_id = r.json()["id"]

        # 4. Prune messages older than 1 second
        r = post("/api/admin/prune", {"olderThanSeconds": 1})
        assert r.status_code == 200
        result = r.json()
        assert "pruned" in result
        assert result["pruned"] >= 2

        # 5. Old messages are gone
        r = get(f"/api/messages/{old_id_1}")
        assert r.status_code == 404
        r = get(f"/api/messages/{old_id_2}")
        assert r.status_code == 404

        # 6. New message still exists
        r = get(f"/api/messages/{new_id}")
        assert r.status_code == 200
        assert r.json()["message"] == "new-1"

        # 7. Stats reflect the pruned state
        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        assert r.json()["messageCount"] == 1


class TestWorkflowMessageActionsAttachmentRoundtrip:
    """Pattern 1+2: Full roundtrip of complex message with actions and attachment."""

    def test_complex_message_roundtrip_through_all_endpoints(self):
        """
        Workflow: Publish complex message → get by ID → get from topic list →
        verify all nested data intact through each retrieval path.
        Patterns: 1 (camelCase), 2 (nested data), 4 (status codes)
        """
        ensure_admin()
        topic = f"wf-complex-{UNIQUE}"

        # 1. Publish message with all optional fields
        actions = [
            {"action": "view", "label": "Open Dashboard", "url": "https://dash.example.com"},
            {"action": "http", "label": "Acknowledge", "url": "https://api.example.com/ack"},
            {"action": "broadcast", "label": "Share"},
        ]
        attachment = {
            "name": "logs.tar.gz",
            "url": "https://storage.example.com/logs.tar.gz",
            "type": "application/gzip",
            "size": 1048576,
        }
        r = post(f"/api/topics/{topic}/messages", {
            "message": "Complex notification body",
            "title": "System Alert: CPU High",
            "priority": 5,
            "tags": "alert,cpu,production",
            "actions": actions,
            "attachment": attachment,
        })
        assert r.status_code == 201
        msg = r.json()
        msg_id = msg["id"]

        # Verify creation response
        assert msg["message"] == "Complex notification body"
        assert msg["title"] == "System Alert: CPU High"
        assert msg["priority"] == 5
        assert msg["tags"] == ["alert", "cpu", "production"]
        assert msg["topic"] == topic
        assert msg["delivered"] is True
        assert "publishedAt" in msg
        assert "publisherId" in msg

        # 2. Get by ID — full integrity check
        r = get(f"/api/messages/{msg_id}")
        assert r.status_code == 200
        msg2 = r.json()
        assert msg2["id"] == msg_id
        assert msg2["message"] == "Complex notification body"
        assert msg2["title"] == "System Alert: CPU High"
        assert msg2["priority"] == 5
        assert msg2["tags"] == ["alert", "cpu", "production"]
        assert len(msg2["actions"]) == 3
        assert msg2["actions"][0]["action"] == "view"
        assert msg2["actions"][0]["label"] == "Open Dashboard"
        assert msg2["actions"][0]["url"] == "https://dash.example.com"
        assert msg2["actions"][1]["action"] == "http"
        assert msg2["actions"][2]["action"] == "broadcast"
        assert msg2["attachment"]["name"] == "logs.tar.gz"
        assert msg2["attachment"]["url"] == "https://storage.example.com/logs.tar.gz"
        assert msg2["attachment"]["type"] == "application/gzip"
        assert msg2["attachment"]["size"] == 1048576

        # 3. Get from topic message list — same integrity
        r = get(f"/api/topics/{topic}/messages")
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 1
        found = next(m for m in msgs if m["id"] == msg_id)
        assert found["actions"] is not None
        assert len(found["actions"]) == 3
        assert found["attachment"]["name"] == "logs.tar.gz"
        assert found["attachment"]["size"] == 1048576

        # 4. Delete message
        r = delete(f"/api/messages/{msg_id}")
        assert r.status_code == 200

        # 5. Confirm deletion
        r = get(f"/api/messages/{msg_id}")
        assert r.status_code == 404


class TestWorkflowTokenManagementScoped:
    """Pattern 1+6: Token CRUD scoped to individual users."""

    def test_token_full_lifecycle_per_user(self):
        """
        Workflow: Two users create tokens → list shows only own →
        update own → delete own → verify.
        Patterns: 1 (camelCase), 6 (isolation), 4 (status codes)
        """
        ensure_admin()
        user_a = make_user_headers("tok-a")
        user_b = make_user_headers("tok-b")
        get("/api/topics", headers=user_a)
        get("/api/topics", headers=user_b)

        # 1. User A creates token
        r = post("/api/tokens", {"label": "a-token-1", "expires": "2099-06-01T00:00:00Z"}, headers=user_a)
        assert r.status_code == 201
        tok_a = r.json()
        assert tok_a["label"] == "a-token-1"
        assert "userId" in tok_a
        assert "token" in tok_a
        assert "createdAt" in tok_a
        tok_a_id = tok_a["id"]

        # 2. User B creates token
        r = post("/api/tokens", {"label": "b-token-1"}, headers=user_b)
        assert r.status_code == 201
        tok_b = r.json()
        tok_b_id = tok_b["id"]

        # 3. User A list — only sees own
        r = get("/api/tokens", headers=user_a)
        assert r.status_code == 200
        a_labels = [t["label"] for t in r.json()]
        assert "a-token-1" in a_labels
        assert "b-token-1" not in a_labels

        # 4. User B list — only sees own
        r = get("/api/tokens", headers=user_b)
        assert r.status_code == 200
        b_labels = [t["label"] for t in r.json()]
        assert "b-token-1" in b_labels
        assert "a-token-1" not in b_labels

        # 5. User A updates own token
        r = patch(f"/api/tokens/{tok_a_id}", {"label": "a-token-renamed"}, headers=user_a)
        assert r.status_code == 200
        assert r.json()["label"] == "a-token-renamed"

        # 6. User B cannot update User A's token
        r = patch(f"/api/tokens/{tok_a_id}", {"label": "hacked"}, headers=user_b)
        assert r.status_code == 404

        # 7. User A deletes own token
        r = delete(f"/api/tokens/{tok_a_id}", headers=user_a)
        assert r.status_code == 200

        # 8. Token is gone from User A's list
        r = get("/api/tokens", headers=user_a)
        assert r.status_code == 200
        a_ids = [t["id"] for t in r.json()]
        assert tok_a_id not in a_ids


class TestWorkflowGlobalStatsReflectOperations:
    """Pattern 5: Global stats correctly reflect all CRUD operations."""

    def test_global_stats_accuracy_across_operations(self):
        """
        Workflow: Record baseline → create topics, users, messages →
        verify stats increase → delete some → verify stats decrease.
        Patterns: 5 (computed stats), 7 (cascade affects counts)
        """
        ensure_admin()

        # 1. Get baseline
        r = get("/api/stats")
        assert r.status_code == 200
        baseline = r.json()
        assert "totalTopics" in baseline
        assert "totalMessages" in baseline
        assert "totalUsers" in baseline

        # 2. Create 2 topics
        topic1 = f"gs-t1-{UNIQUE}"
        topic2 = f"gs-t2-{UNIQUE}"
        post("/api/topics", {"name": topic1})
        post("/api/topics", {"name": topic2})

        # 3. Publish 3 messages
        post(f"/api/topics/{topic1}/messages", {"message": "gs1"})
        post(f"/api/topics/{topic1}/messages", {"message": "gs2"})
        post(f"/api/topics/{topic2}/messages", {"message": "gs3"})

        # 4. Create a user
        new_user = f"gs-user-{UNIQUE}"
        post("/api/users", {"username": new_user})

        # 5. Verify increases
        r = get("/api/stats")
        assert r.status_code == 200
        after_create = r.json()
        assert after_create["totalTopics"] == baseline["totalTopics"] + 2
        assert after_create["totalMessages"] == baseline["totalMessages"] + 3
        assert after_create["totalUsers"] == baseline["totalUsers"] + 1

        # 6. Delete topic1 (cascades: removes its 2 messages)
        delete(f"/api/topics/{topic1}")

        # 7. Verify stats updated
        r = get("/api/stats")
        assert r.status_code == 200
        after_delete = r.json()
        assert after_delete["totalTopics"] == baseline["totalTopics"] + 1
        assert after_delete["totalMessages"] == baseline["totalMessages"] + 1
