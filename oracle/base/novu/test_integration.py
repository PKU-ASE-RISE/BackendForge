"""
BackendForge — L2 Integration Tests for Novu
Adversarial tests targeting common LLM implementation bugs.

"""

import os
import uuid
import time

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
DELIVERY_URL = (os.environ.get("DELIVERY_URL", "").strip() or "http://localhost:9998").rstrip("/")
API_KEY = "test-api-key-1"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
POLL_TIMEOUT = 5
POLL_INTERVAL = 0.05


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=30)


def post(path, json=None):
    return requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=json, timeout=30)


def patch(path, json=None):
    return requests.patch(f"{BASE_URL}{path}", headers=HEADERS, json=json, timeout=30)


def delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def clear_delivery():
    requests.post(f"{DELIVERY_URL}/v1/logs/clear", timeout=5)


def get_delivery_logs():
    return requests.get(f"{DELIVERY_URL}/v1/logs", timeout=5).json().get("messages", [])


def wait_for_activity(params):
    """Poll until activity is visible, returning the last HTTP response."""
    deadline = time.monotonic() + POLL_TIMEOUT
    while True:
        response = get("/v1/activity", params=params)
        try:
            ready = bool(response.json().get("data"))
        except (requests.exceptions.JSONDecodeError, AttributeError):
            ready = False
        if response.status_code != 200 or ready or time.monotonic() >= deadline:
            return response
        time.sleep(POLL_INTERVAL)


# ═══════════════════════════════════════════════════════════
# L2 Tests — Integration (20-30 tests)
# ═══════════════════════════════════════════════════════════


class TestWorkflowFields:
    """Pattern 1+2: Workflow response fields and nested steps."""

    def test_workflow_create_returns_correct_fields(self):
        """Workflow response must have correct camelCase fields."""
        trigger_id = _u("wf-trigger-")
        r = post("/v1/workflows", {
            "name": "Welcome Flow",
            "triggerIdentifier": trigger_id,
            "description": "Send welcome email",
            "active": True,
            "steps": [{"channel": "email", "template": {"subject": "Hi", "body": "Welcome"}, "order": 1}],
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Welcome Flow"
        assert data["triggerIdentifier"] == trigger_id
        assert data["description"] == "Send welcome email"
        assert data["active"] is True
        assert "id" in data
        assert "organizationId" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "steps" in data
        assert len(data["steps"]) == 1
        # No snake_case
        assert "trigger_identifier" not in data
        assert "notification_group_id" not in data
        assert "organization_id" not in data

    def test_workflow_steps_nested_in_response(self):
        """Steps are returned nested in workflow GET response."""
        r = post("/v1/workflows", {
            "name": _u("wf-nested-"),
            "triggerIdentifier": _u("trig-"),
            "steps": [
                {"channel": "email", "template": {"subject": "S1", "body": "B1"}, "order": 1},
                {"channel": "sms", "template": {"body": "SMS body"}, "order": 2},
            ],
        })
        assert r.status_code == 201
        wf_id = r.json()["id"]

        r = get(f"/v1/workflows/{wf_id}")
        assert r.status_code == 200
        wf = r.json()
        assert len(wf["steps"]) == 2
        channels = [s["channel"] for s in wf["steps"]]
        assert "email" in channels
        assert "sms" in channels


class TestStepFields:
    """Pattern 1+2: Step response fields and template nested object."""

    def test_step_response_fields(self):
        """Step has id, workflowId, channel, template, active, order, createdAt, updatedAt."""
        r = post("/v1/workflows", {"name": _u("sf-"), "triggerIdentifier": _u("trig-"), "steps": []})
        wf_id = r.json()["id"]

        r = post(f"/v1/workflows/{wf_id}/steps", {
            "channel": "push",
            "template": {"title": "Alert", "body": "Something happened"},
            "active": True,
            "order": 1,
        })
        assert r.status_code == 201
        step = r.json()
        assert step["channel"] == "push"
        assert step["template"]["title"] == "Alert"
        assert step["template"]["body"] == "Something happened"
        assert step["active"] is True
        assert step["order"] == 1
        assert "id" in step
        assert "workflowId" in step
        assert "createdAt" in step
        assert "updatedAt" in step
        assert "workflow_id" not in step


class TestSubscriberFields:
    """Pattern 1: Subscriber response fields."""

    def test_subscriber_create_returns_correct_fields(self):
        """Subscriber has subscriberId, firstName, lastName, email, phone, pushTokens, data."""
        sub_id = _u("sub-")
        r = post("/v1/subscribers", {
            "subscriberId": sub_id,
            "firstName": "Alice",
            "lastName": "Smith",
            "email": "alice@example.com",
            "phone": "+1234567890",
            "pushTokens": ["token-abc"],
            "data": {"plan": "pro"},
        })
        assert r.status_code == 201
        data = r.json()
        assert data["subscriberId"] == sub_id
        assert data["firstName"] == "Alice"
        assert data["lastName"] == "Smith"
        assert data["email"] == "alice@example.com"
        assert data["phone"] == "+1234567890"
        assert "token-abc" in data["pushTokens"]
        assert data["data"]["plan"] == "pro"
        assert "id" in data
        assert "organizationId" in data
        assert "createdAt" in data
        # No snake_case
        assert "subscriber_id" not in data
        assert "first_name" not in data
        assert "push_tokens" not in data


class TestPaginationActuallyWorks:
    """Pattern 3: Pagination params actually limit/offset results."""

    def test_workflows_pagination(self):
        """limit param restricts result count, total reflects full count."""
        # Create 3 workflows
        for i in range(3):
            post("/v1/workflows", {"name": _u("pag-"), "triggerIdentifier": _u("t-"), "steps": []})

        r = get("/v1/workflows", params={"page": 0, "limit": 2})
        assert r.status_code == 200
        resp = r.json()
        assert len(resp["data"]) <= 2
        assert resp["total"] >= 3
        assert resp["page"] == 0
        assert resp["limit"] == 2

    def test_subscribers_pagination_offset(self):
        """page param skips results."""
        for i in range(3):
            post("/v1/subscribers", {"subscriberId": _u("pag-sub-")})

        r1 = get("/v1/subscribers", params={"page": 0, "limit": 100})
        r2 = get("/v1/subscribers", params={"page": 1, "limit": 2})
        # Page 1 should have different items than page 0 first 2
        if r1.json()["total"] > 2:
            page0_ids = [s["subscriberId"] for s in r1.json()["data"][:2]]
            page1_ids = [s["subscriberId"] for s in r2.json()["data"]]
            # page1 should not have page0's first 2 items
            for pid in page1_ids:
                assert pid not in page0_ids


class TestTopicFields:
    """Pattern 1: Topic response fields."""

    def test_topic_create_and_get_fields(self):
        """Topic has id, key, name, organizationId, createdAt, updatedAt."""
        key = _u("topic-")
        r = post("/v1/topics", {"key": key, "name": "Announcements"})
        assert r.status_code == 201
        data = r.json()
        assert data["key"] == key
        assert data["name"] == "Announcements"
        assert "id" in data
        assert "organizationId" in data
        assert "createdAt" in data
        assert "updatedAt" in data

        # GET by key
        r = get(f"/v1/topics/{key}")
        assert r.status_code == 200
        assert r.json()["key"] == key
        assert r.json()["name"] == "Announcements"


class TestTopicSubscribers:
    """Pattern 5+7: Topic subscriber management actually works."""

    def test_add_and_list_topic_subscribers(self):
        """Adding subscribers to topic actually persists them."""
        key = _u("ts-topic-")
        post("/v1/topics", {"key": key, "name": "Test"})

        sub1 = _u("ts-sub1-")
        sub2 = _u("ts-sub2-")
        post("/v1/subscribers", {"subscriberId": sub1, "email": "a@b.com"})
        post("/v1/subscribers", {"subscriberId": sub2, "email": "c@d.com"})

        r = post(f"/v1/topics/{key}/subscribers", {"subscriberIds": [sub1, sub2]})
        assert r.status_code == 200

        r = get(f"/v1/topics/{key}/subscribers")
        assert r.status_code == 200
        subs = r.json()["data"]
        assert sub1 in subs
        assert sub2 in subs
        assert r.json()["total"] >= 2

    def test_remove_topic_subscribers(self):
        """Removing subscriber from topic actually removes them."""
        key = _u("rm-topic-")
        post("/v1/topics", {"key": key, "name": "Remove Test"})

        sub = _u("rm-sub-")
        post("/v1/subscribers", {"subscriberId": sub})
        post(f"/v1/topics/{key}/subscribers", {"subscriberIds": [sub]})

        r = post(f"/v1/topics/{key}/subscribers/remove", {"subscriberIds": [sub]})
        assert r.status_code == 200

        r = get(f"/v1/topics/{key}/subscribers")
        assert sub not in r.json()["data"]


class TestPreferences:
    """Pattern 5: Preferences actually affect delivery."""

    def test_set_and_get_preferences(self):
        """Setting preferences persists and returns correct data."""
        sub_id = _u("pref-sub-")
        post("/v1/subscribers", {"subscriberId": sub_id, "email": "pref@x.com"})

        # Disable email
        r = patch(f"/v1/subscribers/{sub_id}/preferences", {"channel": "email", "enabled": False})
        assert r.status_code == 200
        assert r.json()["channel"] == "email"
        assert r.json()["enabled"] is False

        # Get preferences
        r = get(f"/v1/subscribers/{sub_id}/preferences")
        assert r.status_code == 200
        prefs = r.json()["data"]
        email_pref = next((p for p in prefs if p["channel"] == "email"), None)
        assert email_pref is not None
        assert email_pref["enabled"] is False


class TestTriggerExecution:
    """Pattern 5: Trigger actually calls delivery service."""

class TestActivityFeed:
    """Pattern 5+3: Activity feed records and filters."""

    def test_activity_recorded_after_trigger(self):
        """Triggering creates activity records."""
        trigger_id = _u("act-trig-")
        post("/v1/workflows", {
            "name": "Activity WF",
            "triggerIdentifier": trigger_id,
            "steps": [{"channel": "email", "template": {"subject": "Hi", "body": "Body"}, "order": 1}],
        })
        sub_id = _u("act-sub-")
        post("/v1/subscribers", {"subscriberId": sub_id, "email": "act@test.com"})

        r = post("/v1/triggers", {"workflowIdentifier": trigger_id, "to": sub_id, "payload": {}})
        tx_id = r.json()["transactionId"]

        r = wait_for_activity({"transactionId": tx_id})
        assert r.status_code == 200
        activities = r.json()["data"]
        assert len(activities) >= 1
        act = activities[0]
        assert "id" in act
        assert act["transactionId"] == tx_id
        assert act["subscriberId"] == sub_id
        assert act["channel"] == "email"
        assert act["status"] in ["sent", "delivered", "pending"]

    def test_activity_filter_by_subscriber(self):
        """Activity can be filtered by subscriberId."""
        trigger_id = _u("filt-trig-")
        post("/v1/workflows", {
            "name": "Filter WF",
            "triggerIdentifier": trigger_id,
            "steps": [{"channel": "email", "template": {"subject": "X", "body": "Y"}, "order": 1}],
        })
        sub1 = _u("filt-sub1-")
        sub2 = _u("filt-sub2-")
        post("/v1/subscribers", {"subscriberId": sub1, "email": "s1@t.com"})
        post("/v1/subscribers", {"subscriberId": sub2, "email": "s2@t.com"})

        post("/v1/triggers", {"workflowIdentifier": trigger_id, "to": sub1, "payload": {}})
        post("/v1/triggers", {"workflowIdentifier": trigger_id, "to": sub2, "payload": {}})

        r = wait_for_activity({"subscriberId": sub1})
        activities = r.json()["data"]
        for act in activities:
            assert act["subscriberId"] == sub1


class TestStatusCodes:
    """Pattern 4: Exact status codes."""

    def test_create_returns_201(self):
        """POST create endpoints return 201."""
        r = post("/v1/notification-groups", {"name": _u("sc-")})
        assert r.status_code == 201

        r = post("/v1/environments", {"name": _u("sc-env-")})
        assert r.status_code == 201

        r = post("/v1/subscribers", {"subscriberId": _u("sc-sub-")})
        assert r.status_code == 201

        r = post("/v1/topics", {"key": _u("sc-t-"), "name": "SC Topic"})
        assert r.status_code == 201

    def test_delete_returns_204(self):
        """DELETE endpoints return 204."""
        r = post("/v1/notification-groups", {"name": _u("del-")})
        gid = r.json()["id"]
        r = delete(f"/v1/notification-groups/{gid}")
        assert r.status_code == 204

    def test_not_found_returns_404(self):
        """Nonexistent resources return 404."""
        fake = str(uuid.uuid4())
        assert get(f"/v1/workflows/{fake}").status_code == 404
        assert get(f"/v1/subscribers/{fake}").status_code == 404
        assert get(f"/v1/topics/{fake}").status_code == 404
        assert get(f"/v1/notification-groups/{fake}").status_code == 404

    def test_missing_auth_returns_401(self):
        """Missing API key returns 401."""
        r = requests.get(f"{BASE_URL}/v1/workflows", timeout=30)
        assert r.status_code == 401


class TestIntegrationFields:
    """Pattern 1: Integration response fields."""

    def test_integration_create_and_get(self):
        """Integration has channel, providerId, credentials, active, etc."""
        r = post("/v1/integrations", {
            "channel": "email",
            "providerId": "sendgrid",
            "credentials": {"apiKey": "sg-key-123"},
            "active": True,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["channel"] == "email"
        assert data["providerId"] == "sendgrid"
        assert data["credentials"]["apiKey"] == "sg-key-123"
        assert data["active"] is True
        assert "id" in data
        assert "organizationId" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "provider_id" not in data

        # GET
        r = get(f"/v1/integrations/{data['id']}")
        assert r.status_code == 200
        assert r.json()["providerId"] == "sendgrid"


class TestEnvironmentCRUD:
    """Pattern 4+1: Environment CRUD with correct fields."""

    def test_environment_full_crud(self):
        """Create, get, update, delete environment."""
        name = _u("env-")
        r = post("/v1/environments", {"name": name})
        assert r.status_code == 201
        env = r.json()
        assert env["name"] == name
        env_id = env["id"]

        r = get(f"/v1/environments/{env_id}")
        assert r.status_code == 200
        assert r.json()["name"] == name

        r = patch(f"/v1/environments/{env_id}", {"name": "updated-env"})
        assert r.status_code == 200
        assert r.json()["name"] == "updated-env"

        r = delete(f"/v1/environments/{env_id}")
        assert r.status_code == 204

        r = get(f"/v1/environments/{env_id}")
        assert r.status_code == 404


class TestNotificationGroupFields:
    """Pattern 1: NotificationGroup fields."""

    def test_notification_group_fields(self):
        """Group has id, name, organizationId, createdAt, updatedAt."""
        name = _u("ng-")
        r = post("/v1/notification-groups", {"name": name})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == name
        assert "id" in data
        assert "organizationId" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "organization_id" not in data
