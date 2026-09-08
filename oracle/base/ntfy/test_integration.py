"""
BackendForge — L2 Integration Tests for Ntfy Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase field names
- Pattern 2: Nested/related data not returned
- Pattern 3: Filter/sort params declared but not implemented
- Pattern 4: Wrong status codes
- Pattern 5: Business logic empty (computed values)
- Pattern 6: Data isolation between users
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Duplicate/ordering issues

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


REG_HEADERS = make_user_headers("reg")
REG2_HEADERS = make_user_headers("reg2")


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
# L2 Tests
# ════════════════════════════════════════════════════════════════════


class TestMessageCamelCaseFields:
    """Pattern 1: Verify all response fields use camelCase, not snake_case."""

    def test_publish_message_returns_camel_case_fields(self):
        """Pattern 1+4: All message fields must be camelCase and status 201."""
        ensure_admin()
        topic = f"camel-msg-{UNIQUE}"
        r = post(f"/api/topics/{topic}/messages", {
            "message": "camelCase test",
            "title": "Test Title",
            "priority": 4,
            "tags": "alert,server",
        })
        assert r.status_code == 201
        msg = r.json()

        # Verify camelCase field names exist (not snake_case)
        assert "id" in msg
        assert "topic" in msg
        assert "message" in msg
        assert "title" in msg
        assert "priority" in msg
        assert "tags" in msg
        assert "publishedAt" in msg
        assert "delivered" in msg
        assert "publisherId" in msg

        # Verify snake_case variants do NOT exist
        assert "published_at" not in msg
        assert "publisher_id" not in msg
        assert "scheduled_at" not in msg

        # Verify field values
        assert msg["topic"] == topic
        assert msg["message"] == "camelCase test"
        assert msg["title"] == "Test Title"
        assert msg["priority"] == 4
        assert msg["tags"] == ["alert", "server"]
        assert msg["delivered"] is True

    def test_subscription_camel_case_fields(self):
        """Pattern 1: Subscription response uses camelCase for filterPriority/filterTags/filterTitle."""
        ensure_admin()
        topic = f"camel-sub-{UNIQUE}"
        post("/api/topics", {"name": topic})

        r = post("/api/subscriptions", {
            "topic": topic,
            "filterPriority": 3,
            "filterTags": "important",
            "filterTitle": "Alert",
        })
        assert r.status_code == 201
        sub = r.json()

        # camelCase fields must exist
        assert "id" in sub
        assert "userId" in sub
        assert "topic" in sub
        assert "filterPriority" in sub
        assert "filterTags" in sub
        assert "filterTitle" in sub
        assert "createdAt" in sub

        # snake_case must NOT exist
        assert "user_id" not in sub
        assert "filter_priority" not in sub
        assert "filter_tags" not in sub
        assert "filter_title" not in sub
        assert "created_at" not in sub

        # Values
        assert sub["filterPriority"] == 3
        assert sub["filterTags"] == "important"
        assert sub["filterTitle"] == "Alert"

    def test_token_camel_case_fields(self):
        """Pattern 1: Token response uses camelCase for userId, createdAt."""
        ensure_admin()
        r = post("/api/tokens", {"label": f"camel-tok-{UNIQUE}", "expires": "2099-12-31T00:00:00Z"})
        assert r.status_code == 201
        tok = r.json()

        assert "id" in tok
        assert "token" in tok
        assert "userId" in tok
        assert "label" in tok
        assert "expires" in tok
        assert "createdAt" in tok

        # snake_case must NOT exist
        assert "user_id" not in tok
        assert "created_at" not in tok

        assert tok["label"] == f"camel-tok-{UNIQUE}"
        assert tok["expires"] is not None


class TestMessageDeliveryAndRetrieval:
    """Pattern 2+5: Messages with nested data are stored and retrieved correctly."""

    def test_publish_with_actions_and_retrieve(self):
        """Pattern 2: Actions array must roundtrip through publish → get."""
        ensure_admin()
        topic = f"actions-rt-{UNIQUE}"
        actions = [
            {"action": "view", "label": "Open Site", "url": "https://example.com"},
            {"action": "http", "label": "Webhook", "url": "https://hook.example.com/notify"},
        ]
        r = post(f"/api/topics/{topic}/messages", {
            "message": "action test",
            "actions": actions,
        })
        assert r.status_code == 201
        msg_id = r.json()["id"]

        # Retrieve by ID
        r2 = get(f"/api/messages/{msg_id}")
        assert r2.status_code == 200
        msg = r2.json()
        assert len(msg["actions"]) == 2
        assert msg["actions"][0]["action"] == "view"
        assert msg["actions"][0]["label"] == "Open Site"
        assert msg["actions"][0]["url"] == "https://example.com"
        assert msg["actions"][1]["action"] == "http"
        assert msg["actions"][1]["label"] == "Webhook"

    def test_publish_with_attachment_and_retrieve(self):
        """Pattern 2: Attachment metadata roundtrips through publish → get."""
        ensure_admin()
        topic = f"attach-rt-{UNIQUE}"
        attachment = {
            "name": "report.pdf",
            "url": "https://files.example.com/report.pdf",
            "type": "application/pdf",
            "size": 98765,
        }
        r = post(f"/api/topics/{topic}/messages", {
            "message": "attachment test",
            "attachment": attachment,
        })
        assert r.status_code == 201
        msg_id = r.json()["id"]

        r2 = get(f"/api/messages/{msg_id}")
        assert r2.status_code == 200
        msg = r2.json()
        assert msg["attachment"]["name"] == "report.pdf"
        assert msg["attachment"]["url"] == "https://files.example.com/report.pdf"
        assert msg["attachment"]["type"] == "application/pdf"
        assert msg["attachment"]["size"] == 98765

    def test_tags_stored_as_array_returned_as_array(self):
        """Pattern 1+2: Tags sent as comma-string, returned as JSON array consistently."""
        ensure_admin()
        topic = f"tags-arr-{UNIQUE}"
        r = post(f"/api/topics/{topic}/messages", {
            "message": "multi tag",
            "tags": "alpha,beta,gamma",
        })
        assert r.status_code == 201
        msg = r.json()
        assert isinstance(msg["tags"], list)
        assert msg["tags"] == ["alpha", "beta", "gamma"]

        # Retrieve from topic messages list
        r2 = get(f"/api/topics/{topic}/messages")
        assert r2.status_code == 200
        msgs = r2.json()
        found = next(m for m in msgs if m["id"] == msg["id"])
        assert isinstance(found["tags"], list)
        assert found["tags"] == ["alpha", "beta", "gamma"]


class TestMessageFiltering:
    """Pattern 3: Filter parameters actually filter results."""

    def test_priority_filter_excludes_lower(self):
        """Pattern 3: priority filter must actually exclude low-priority messages."""
        ensure_admin()
        topic = f"filt-pri-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "low", "priority": 1})
        post(f"/api/topics/{topic}/messages", {"message": "mid", "priority": 3})
        post(f"/api/topics/{topic}/messages", {"message": "high", "priority": 5})

        r = get(f"/api/topics/{topic}/messages", params={"priority": 4})
        assert r.status_code == 200
        msgs = r.json()
        # Only priority >= 4 should be returned
        assert len(msgs) >= 1
        for m in msgs:
            assert m["priority"] >= 4
        texts = [m["message"] for m in msgs]
        assert "low" not in texts
        assert "mid" not in texts
        assert "high" in texts

    def test_tag_filter_returns_only_matching(self):
        """Pattern 3: tags filter must only return messages with matching tag."""
        ensure_admin()
        topic = f"filt-tag-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "has-alert", "tags": "alert,info"})
        post(f"/api/topics/{topic}/messages", {"message": "has-debug", "tags": "debug"})
        post(f"/api/topics/{topic}/messages", {"message": "no-tags"})

        r = get(f"/api/topics/{topic}/messages", params={"tags": "alert"})
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 1
        for m in msgs:
            assert "alert" in m["tags"]
        texts = [m["message"] for m in msgs]
        assert "has-alert" in texts
        assert "has-debug" not in texts
        assert "no-tags" not in texts

    def test_title_filter_substring_match(self):
        """Pattern 3: title filter does substring match."""
        ensure_admin()
        topic = f"filt-title-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "a", "title": "Server Down Alert"})
        post(f"/api/topics/{topic}/messages", {"message": "b", "title": "Daily Report"})
        post(f"/api/topics/{topic}/messages", {"message": "c", "title": "Alert: Disk Full"})

        r = get(f"/api/topics/{topic}/messages", params={"title": "Alert"})
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 2
        for m in msgs:
            assert "Alert" in m["title"]
        texts = [m["message"] for m in msgs]
        assert "a" in texts
        assert "c" in texts
        assert "b" not in texts

    def test_since_filter_excludes_older_messages(self):
        """Pattern 3: since filter excludes messages before the timestamp."""
        ensure_admin()
        topic = f"filt-since-{UNIQUE}"
        # Publish first message
        old = post(f"/api/topics/{topic}/messages", {"message": "old"})

        # Use the server-issued timestamp to avoid host/service clock skew.
        since_ts = old.json()["publishedAt"]
        time.sleep(1.1)

        # Publish second message
        post(f"/api/topics/{topic}/messages", {"message": "new"})

        r = get(f"/api/topics/{topic}/messages", params={"since": since_ts})
        assert r.status_code == 200
        msgs = r.json()
        texts = [m["message"] for m in msgs]
        assert "new" in texts
        assert "old" not in texts


class TestTopicStatsComputed:
    """Pattern 5: Stats are computed from real data, not hardcoded."""

    def test_message_count_increases_with_publishes(self):
        """Pattern 5: messageCount reflects actual messages published."""
        ensure_admin()
        topic = f"stats-mc-{UNIQUE}"
        post("/api/topics", {"name": topic})

        # Initial stats
        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        assert r.json()["messageCount"] == 0

        # Publish 3 messages
        post(f"/api/topics/{topic}/messages", {"message": "one"})
        post(f"/api/topics/{topic}/messages", {"message": "two"})
        post(f"/api/topics/{topic}/messages", {"message": "three"})

        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["messageCount"] == 3
        assert stats["topic"] == topic

    def test_subscriber_count_reflects_subscriptions(self):
        """Pattern 5: subscriberCount reflects actual subscriber count."""
        ensure_admin()
        topic = f"stats-sub-{UNIQUE}"
        post("/api/topics", {"name": topic})

        # Initial stats
        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        assert r.json()["subscriberCount"] == 0

        # Subscribe with admin
        post("/api/subscriptions", {"topic": topic})
        # Subscribe with another user
        get("/api/topics", headers=REG_HEADERS)
        post("/api/subscriptions", {"topic": topic}, headers=REG_HEADERS)

        r = get(f"/api/topics/{topic}/stats")
        assert r.status_code == 200
        assert r.json()["subscriberCount"] == 2

    def test_global_stats_reflect_actual_data(self):
        """Pattern 5: Global stats must reflect real counts."""
        ensure_admin()
        # Get baseline
        r1 = get("/api/stats")
        assert r1.status_code == 200
        baseline = r1.json()
        assert "totalTopics" in baseline
        assert "totalMessages" in baseline
        assert "totalUsers" in baseline

        # Create a new topic + message
        topic = f"gstats-{UNIQUE}"
        post("/api/topics", {"name": topic})
        post(f"/api/topics/{topic}/messages", {"message": "counted"})

        r2 = get("/api/stats")
        assert r2.status_code == 200
        updated = r2.json()
        assert updated["totalTopics"] == baseline["totalTopics"] + 1
        assert updated["totalMessages"] == baseline["totalMessages"] + 1


class TestSubscriptionManagement:
    """Pattern 1+3+6: Subscription CRUD with correct fields and isolation."""

    def test_create_and_get_subscription_roundtrip(self):
        """Pattern 1+2: Create subscription, then get by ID — fields match."""
        ensure_admin()
        topic = f"sub-rt-{UNIQUE}"
        post("/api/topics", {"name": topic})

        r = post("/api/subscriptions", {
            "topic": topic,
            "filterPriority": 2,
            "filterTags": "urgent,error",
            "filterTitle": "Server",
        })
        assert r.status_code == 201
        sub = r.json()
        sub_id = sub["id"]

        # Retrieve
        r2 = get(f"/api/subscriptions/{sub_id}")
        assert r2.status_code == 200
        sub2 = r2.json()
        assert sub2["id"] == sub_id
        assert sub2["topic"] == topic
        assert sub2["filterPriority"] == 2
        assert sub2["filterTags"] == "urgent,error"
        assert sub2["filterTitle"] == "Server"
        assert "userId" in sub2
        assert "createdAt" in sub2

    def test_update_subscription_filter_fields(self):
        """Pattern 3: Update subscription filters — verify they actually change."""
        ensure_admin()
        topic = f"sub-upd-{UNIQUE}"
        post("/api/topics", {"name": topic})
        r = post("/api/subscriptions", {"topic": topic})
        assert r.status_code == 201
        sub_id = r.json()["id"]

        # Update filters
        r2 = put(f"/api/subscriptions/{sub_id}", {
            "filterPriority": 5,
            "filterTags": "critical",
            "filterTitle": "URGENT",
        })
        assert r2.status_code == 200
        updated = r2.json()
        assert updated["filterPriority"] == 5
        assert updated["filterTags"] == "critical"
        assert updated["filterTitle"] == "URGENT"

        # Verify persisted via GET
        r3 = get(f"/api/subscriptions/{sub_id}")
        assert r3.status_code == 200
        assert r3.json()["filterPriority"] == 5
        assert r3.json()["filterTags"] == "critical"
        assert r3.json()["filterTitle"] == "URGENT"

    def test_subscription_isolation_between_users(self):
        """Pattern 6: User A's subscriptions not visible to User B."""
        ensure_admin()
        topic = f"sub-iso-{UNIQUE}"
        post("/api/topics", {"name": topic})

        # Admin subscribes
        post("/api/subscriptions", {"topic": topic})

        # Reg user subscribes to different topic
        get("/api/topics", headers=REG_HEADERS)
        topic2 = f"sub-iso2-{UNIQUE}"
        post("/api/topics", {"name": topic2})
        post("/api/subscriptions", {"topic": topic2}, headers=REG_HEADERS)

        # Reg user's list should only show their subscription
        r = get("/api/subscriptions", headers=REG_HEADERS)
        assert r.status_code == 200
        subs = r.json()
        topics_list = [s["topic"] for s in subs]
        assert topic2 in topics_list
        assert topic not in topics_list


class TestTokenIsolation:
    """Pattern 6: Token management is scoped per user."""

    def test_tokens_scoped_to_user(self):
        """Pattern 6: Each user only sees their own tokens."""
        ensure_admin()
        # Admin creates a token
        r1 = post("/api/tokens", {"label": f"admin-tok-{UNIQUE}"})
        assert r1.status_code == 201

        # Reg user creates a token
        get("/api/topics", headers=REG_HEADERS)
        r2 = post("/api/tokens", {"label": f"reg-tok-{UNIQUE}"}, headers=REG_HEADERS)
        assert r2.status_code == 201

        # Admin list
        r3 = get("/api/tokens")
        assert r3.status_code == 200
        admin_labels = [t["label"] for t in r3.json()]
        assert f"admin-tok-{UNIQUE}" in admin_labels
        assert f"reg-tok-{UNIQUE}" not in admin_labels

        # Reg user list
        r4 = get("/api/tokens", headers=REG_HEADERS)
        assert r4.status_code == 200
        reg_labels = [t["label"] for t in r4.json()]
        assert f"reg-tok-{UNIQUE}" in reg_labels
        assert f"admin-tok-{UNIQUE}" not in reg_labels

    def test_cannot_update_other_users_token(self):
        """Pattern 6: User cannot PATCH another user's token (should 404)."""
        ensure_admin()
        r = post("/api/tokens", {"label": f"priv-tok-{UNIQUE}"})
        assert r.status_code == 201
        token_id = r.json()["id"]

        get("/api/topics", headers=REG_HEADERS)
        r2 = patch(f"/api/tokens/{token_id}", {"label": "hacked"}, headers=REG_HEADERS)
        assert r2.status_code == 404


class TestAccessControlEnforcement:
    """Pattern 5+6: Access control actually restricts read/write."""

    def test_write_denied_without_write_permission(self):
        """Pattern 5: Setting write=false actually blocks publishing."""
        ensure_admin()
        topic = f"acl-wr-{UNIQUE}"
        post("/api/topics", {"name": topic})

        # Ensure reg user exists
        get("/api/topics", headers=REG_HEADERS)
        users = get("/api/users").json()
        reg_user = next(u for u in users if u["username"] == REG_HEADERS["X-User-Id"])

        # Give reg user read-only access (makes topic restricted)
        put(f"/api/topics/{topic}/access", {
            "userId": reg_user["id"],
            "read": True,
            "write": False,
        })

        # Reg user tries to publish — should be denied
        r = post(f"/api/topics/{topic}/messages", {"message": "blocked"}, headers=REG_HEADERS)
        assert r.status_code == 403

        # But reg user can read
        r2 = get(f"/api/topics/{topic}/messages", headers=REG_HEADERS)
        assert r2.status_code == 200

    def test_read_denied_without_read_permission(self):
        """Pattern 5: Setting read=false actually blocks reading."""
        ensure_admin()
        topic = f"acl-rd-{UNIQUE}"
        post("/api/topics", {"name": topic})
        post(f"/api/topics/{topic}/messages", {"message": "secret"})

        # Ensure reg user exists
        get("/api/topics", headers=REG_HEADERS)
        users = get("/api/users").json()
        reg_user = next(u for u in users if u["username"] == REG_HEADERS["X-User-Id"])

        # Give reg user write-only access
        put(f"/api/topics/{topic}/access", {
            "userId": reg_user["id"],
            "read": False,
            "write": True,
        })

        # Reg user cannot read
        r = get(f"/api/topics/{topic}/messages", headers=REG_HEADERS)
        assert r.status_code == 403

        # But reg user can publish
        r2 = post(f"/api/topics/{topic}/messages", {"message": "allowed"}, headers=REG_HEADERS)
        assert r2.status_code == 201


class TestScheduledMessageBehavior:
    """Pattern 3+5: Scheduled message filtering is correctly implemented."""

    def test_scheduled_excluded_from_regular_list(self):
        """Pattern 3: Regular message list must NOT include undelivered scheduled messages."""
        ensure_admin()
        topic = f"sched-excl-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "immediate"})
        post(f"/api/topics/{topic}/messages", {
            "message": "future",
            "scheduledAt": "2099-01-01T00:00:00Z",
        })

        r = get(f"/api/topics/{topic}/messages")
        assert r.status_code == 200
        msgs = r.json()
        texts = [m["message"] for m in msgs]
        assert "immediate" in texts
        assert "future" not in texts

    def test_scheduled_endpoint_returns_only_scheduled(self):
        """Pattern 3: /scheduled endpoint only returns undelivered scheduled msgs."""
        ensure_admin()
        topic = f"sched-only-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "normal"})
        post(f"/api/topics/{topic}/messages", {
            "message": "scheduled",
            "scheduledAt": "2099-06-15T00:00:00Z",
        })

        r = get(f"/api/topics/{topic}/messages/scheduled")
        assert r.status_code == 200
        msgs = r.json()
        texts = [m["message"] for m in msgs]
        assert "scheduled" in texts
        assert "normal" not in texts
        # All must be undelivered
        for m in msgs:
            assert m["delivered"] is False

    def test_scheduled_flag_includes_all(self):
        """Pattern 3: ?scheduled=true includes both regular and scheduled messages."""
        ensure_admin()
        topic = f"sched-all-{UNIQUE}"
        post(f"/api/topics/{topic}/messages", {"message": "regular"})
        post(f"/api/topics/{topic}/messages", {
            "message": "sched",
            "scheduledAt": "2099-01-01T00:00:00Z",
        })

        r = get(f"/api/topics/{topic}/messages", params={"scheduled": "true"})
        assert r.status_code == 200
        msgs = r.json()
        texts = [m["message"] for m in msgs]
        assert "regular" in texts
        assert "sched" in texts


class TestUserManagementFields:
    """Pattern 1+4: User CRUD returns correct fields and status codes."""

    def test_create_user_returns_201_with_all_fields(self):
        """Pattern 1+4: POST /api/users returns 201, not 200, with correct fields."""
        ensure_admin()
        username = f"l2-user-{UNIQUE}"
        r = post("/api/users", {"username": username, "admin": False})
        assert r.status_code == 201
        user = r.json()
        assert "id" in user
        assert user["username"] == username
        assert user["admin"] is False
        assert "createdAt" in user
        assert "created_at" not in user

    def test_update_user_tier_field(self):
        """Pattern 1+3: Updating tier field persists and is returned."""
        ensure_admin()
        # Create tier
        tier_r = post("/api/tiers", {
            "name": f"tier-upd-{UNIQUE}",
            "messagesPerDay": 100,
            "messagesPerMinute": 10,
        })
        assert tier_r.status_code == 201
        tier_name = tier_r.json()["name"]

        # Create user and assign tier
        user_r = post("/api/users", {"username": f"tiered-{UNIQUE}"})
        user_id = user_r.json()["id"]

        r = put(f"/api/users/{user_id}", {"tier": tier_name})
        assert r.status_code == 200
        assert r.json()["tier"] == tier_name

        # Verify via GET
        r2 = get(f"/api/users/{user_id}")
        assert r2.status_code == 200
        assert r2.json()["tier"] == tier_name


class TestTierCamelCase:
    """Pattern 1: Tier fields use camelCase."""

    def test_tier_fields_are_camel_case(self):
        """Pattern 1: messagesPerDay and messagesPerMinute, not snake_case."""
        ensure_admin()
        r = post("/api/tiers", {
            "name": f"camel-tier-{UNIQUE}",
            "messagesPerDay": 500,
            "messagesPerMinute": 50,
        })
        assert r.status_code == 201
        tier = r.json()
        assert "id" in tier
        assert "name" in tier
        assert "messagesPerDay" in tier
        assert "messagesPerMinute" in tier
        assert "messages_per_day" not in tier
        assert "messages_per_minute" not in tier
        assert tier["messagesPerDay"] == 500
        assert tier["messagesPerMinute"] == 50


class TestTopicAutoCreation:
    """Pattern 5+8: Publishing to non-existent topic auto-creates it."""

    def test_auto_create_topic_on_publish(self):
        """Pattern 5: Publishing creates the topic — verify it's retrievable."""
        ensure_admin()
        topic = f"auto-{UNIQUE}"
        # Topic doesn't exist yet
        r1 = get(f"/api/topics/{topic}")
        assert r1.status_code == 404

        # Publish creates it
        r2 = post(f"/api/topics/{topic}/messages", {"message": "create topic"})
        assert r2.status_code == 201
        assert r2.json()["topic"] == topic

        # Now it exists
        r3 = get(f"/api/topics/{topic}")
        assert r3.status_code == 200
        assert r3.json()["name"] == topic


class TestDuplicateHandling:
    """Pattern 8: Duplicates return 409 Conflict."""

    def test_duplicate_topic_returns_409(self):
        """Pattern 8: Creating a topic with existing name → 409."""
        ensure_admin()
        name = f"dup-top-{UNIQUE}"
        r1 = post("/api/topics", {"name": name})
        assert r1.status_code == 201
        r2 = post("/api/topics", {"name": name})
        assert r2.status_code == 409

    def test_duplicate_subscription_returns_409(self):
        """Pattern 8: Subscribing to same topic twice → 409."""
        ensure_admin()
        topic = f"dup-sub-{UNIQUE}"
        post("/api/topics", {"name": topic})
        r1 = post("/api/subscriptions", {"topic": topic})
        assert r1.status_code == 201
        r2 = post("/api/subscriptions", {"topic": topic})
        assert r2.status_code == 409

    def test_duplicate_username_returns_409(self):
        """Pattern 8: Creating user with existing username → 409."""
        ensure_admin()
        username = f"dup-user-{UNIQUE}"
        r1 = post("/api/users", {"username": username})
        assert r1.status_code == 201
        r2 = post("/api/users", {"username": username})
        assert r2.status_code == 409


class TestAuthEnforcement:
    """Pattern 4+6: Auth required and admin-only endpoints enforced."""

    def test_no_auth_returns_401(self):
        """Pattern 4: Missing auth headers → 401."""
        ensure_admin()
        r = requests.get(f"{BASE_URL}/api/topics", timeout=30)
        assert r.status_code == 401

    def test_missing_token_returns_401(self):
        """Pattern 4: Missing X-Token → 401."""
        ensure_admin()
        r = requests.get(f"{BASE_URL}/api/topics",
                         headers={"X-User-Id": "someone", "Content-Type": "application/json"},
                         timeout=30)
        assert r.status_code == 401

    def test_admin_only_endpoint_returns_403_for_regular(self):
        """Pattern 4+6: Non-admin calling admin endpoint → 403."""
        ensure_admin()
        get("/api/topics", headers=REG_HEADERS)  # ensure user exists
        r = get("/api/users", headers=REG_HEADERS)
        assert r.status_code == 403

    def test_delete_user_non_admin_returns_403(self):
        """Pattern 4: Non-admin cannot delete users."""
        ensure_admin()
        get("/api/topics", headers=REG_HEADERS)
        r = delete("/api/users/1", headers=REG_HEADERS)
        assert r.status_code == 403


class TestPriorityClampingEdge:
    """Pattern 5: Priority clamping actually works at boundaries."""

    def test_priority_clamped_to_1_when_zero(self):
        """Pattern 5: priority=0 → clamped to 1."""
        ensure_admin()
        topic = f"clamp0-{UNIQUE}"
        r = post(f"/api/topics/{topic}/messages", {"message": "zero", "priority": 0})
        assert r.status_code == 201
        assert r.json()["priority"] == 1

    def test_priority_clamped_to_5_when_ten(self):
        """Pattern 5: priority=10 → clamped to 5."""
        ensure_admin()
        topic = f"clamp10-{UNIQUE}"
        r = post(f"/api/topics/{topic}/messages", {"message": "ten", "priority": 10})
        assert r.status_code == 201
        assert r.json()["priority"] == 5

    def test_priority_boundaries_valid(self):
        """Pattern 5: priority=1 and priority=5 are valid (not clamped)."""
        ensure_admin()
        topic = f"clampv-{UNIQUE}"
        r1 = post(f"/api/topics/{topic}/messages", {"message": "one", "priority": 1})
        assert r1.status_code == 201
        assert r1.json()["priority"] == 1

        r2 = post(f"/api/topics/{topic}/messages", {"message": "five", "priority": 5})
        assert r2.status_code == 201
        assert r2.json()["priority"] == 5
