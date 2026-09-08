"""
Test suite for Novu notification infrastructure API.
Tests cover CRUD operations, trigger execution, preferences, topics, and activity feed.
"""
import os
import time
import uuid
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


def wait_for_activity(params):
    """Poll until activity is visible, returning the last HTTP response."""
    deadline = time.monotonic() + POLL_TIMEOUT
    while True:
        response = requests.get(
            f"{BASE_URL}/v1/activity",
            headers=HEADERS,
            params=params,
        )
        try:
            ready = bool(response.json().get("data"))
        except (requests.exceptions.JSONDecodeError, AttributeError):
            ready = False
        if response.status_code != 200 or ready or time.monotonic() >= deadline:
            return response
        time.sleep(POLL_INTERVAL)


def clear_delivery_logs():
    """Clear the mock delivery service logs."""
    requests.post(f"{DELIVERY_URL}/v1/logs/clear")


def get_delivery_logs():
    """Get all messages from the mock delivery service."""
    resp = requests.get(f"{DELIVERY_URL}/v1/logs")
    return resp.json().get("messages", [])


# ============================================================
# Authentication Tests
# ============================================================

class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/v1/workflows")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/v1/workflows",
            headers={"X-API-Key": "invalid-key"}
        )
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        resp = requests.get(f"{BASE_URL}/v1/workflows", headers=HEADERS)
        assert resp.status_code == 200


# ============================================================
# Notification Groups Tests
# ============================================================

class TestNotificationGroups:
    def test_create_notification_group(self):
        resp = requests.post(
            f"{BASE_URL}/v1/notification-groups",
            headers=HEADERS,
            json={"name": "Marketing"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Marketing"
        assert "id" in data

    def test_list_notification_groups(self):
        requests.post(
            f"{BASE_URL}/v1/notification-groups",
            headers=HEADERS,
            json={"name": "Transactional"}
        )
        resp = requests.get(f"{BASE_URL}/v1/notification-groups", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["total"] >= 1

    def test_get_notification_group(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/notification-groups",
            headers=HEADERS,
            json={"name": "Alerts"}
        )
        group_id = create_resp.json()["id"]
        resp = requests.get(
            f"{BASE_URL}/v1/notification-groups/{group_id}",
            headers=HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Alerts"

    def test_update_notification_group(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/notification-groups",
            headers=HEADERS,
            json={"name": "OldName"}
        )
        group_id = create_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/notification-groups/{group_id}",
            headers=HEADERS,
            json={"name": "NewName"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_delete_notification_group(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/notification-groups",
            headers=HEADERS,
            json={"name": "ToDelete"}
        )
        group_id = create_resp.json()["id"]
        resp = requests.delete(
            f"{BASE_URL}/v1/notification-groups/{group_id}",
            headers=HEADERS
        )
        assert resp.status_code == 204

        resp = requests.get(
            f"{BASE_URL}/v1/notification-groups/{group_id}",
            headers=HEADERS
        )
        assert resp.status_code == 404

    def test_get_nonexistent_group_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/v1/notification-groups/nonexistent-id",
            headers=HEADERS
        )
        assert resp.status_code == 404


# ============================================================
# Environments Tests
# ============================================================

class TestEnvironments:
    def test_create_environment(self):
        resp = requests.post(
            f"{BASE_URL}/v1/environments",
            headers=HEADERS,
            json={"name": "Development"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Development"
        assert "id" in data

    def test_list_environments(self):
        requests.post(
            f"{BASE_URL}/v1/environments",
            headers=HEADERS,
            json={"name": "Production"}
        )
        resp = requests.get(f"{BASE_URL}/v1/environments", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    def test_get_environment(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/environments",
            headers=HEADERS,
            json={"name": "Staging"}
        )
        env_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/v1/environments/{env_id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Staging"

    def test_update_environment(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/environments",
            headers=HEADERS,
            json={"name": "OldEnv"}
        )
        env_id = create_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/environments/{env_id}",
            headers=HEADERS,
            json={"name": "NewEnv"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewEnv"

    def test_delete_environment(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/environments",
            headers=HEADERS,
            json={"name": "TempEnv"}
        )
        env_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/v1/environments/{env_id}", headers=HEADERS)
        assert resp.status_code == 204


# ============================================================
# Integrations Tests
# ============================================================

class TestIntegrations:
    def test_create_integration(self):
        resp = requests.post(
            f"{BASE_URL}/v1/integrations",
            headers=HEADERS,
            json={
                "channel": "email",
                "providerId": "mock-email",
                "credentials": {"apiKey": "mock-key", "from": "noreply@test.com"},
                "active": True
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "email"
        assert data["providerId"] == "mock-email"
        assert data["active"] is True

    def test_list_integrations(self):
        resp = requests.get(f"{BASE_URL}/v1/integrations", headers=HEADERS)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_list_integrations_filter_by_channel(self):
        requests.post(
            f"{BASE_URL}/v1/integrations",
            headers=HEADERS,
            json={
                "channel": "sms",
                "providerId": "mock-sms",
                "credentials": {"apiKey": "sms-key", "from": "+1000000000"}
            }
        )
        resp = requests.get(
            f"{BASE_URL}/v1/integrations?channel=sms",
            headers=HEADERS
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        for item in data:
            assert item["channel"] == "sms"

    def test_update_integration(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/integrations",
            headers=HEADERS,
            json={
                "channel": "push",
                "providerId": "mock-push",
                "credentials": {"serverKey": "old-key"}
            }
        )
        int_id = create_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/integrations/{int_id}",
            headers=HEADERS,
            json={"active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_delete_integration(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/integrations",
            headers=HEADERS,
            json={
                "channel": "chat",
                "providerId": "mock-chat",
                "credentials": {"webhook": "http://example.com"}
            }
        )
        int_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/v1/integrations/{int_id}", headers=HEADERS)
        assert resp.status_code == 204


# ============================================================
# Workflows Tests
# ============================================================

class TestWorkflows:
    def test_create_workflow(self):
        resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Welcome Email",
                "triggerIdentifier": "welcome-email",
                "description": "Send welcome email to new users",
                "active": True
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Welcome Email"
        assert data["triggerIdentifier"] == "welcome-email"
        assert data["active"] is True

    def test_create_workflow_with_steps(self):
        resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Multi-Channel",
                "triggerIdentifier": "multi-channel-wf",
                "steps": [
                    {
                        "channel": "email",
                        "template": {"subject": "Hello {{name}}", "body": "Welcome {{name}}!"},
                        "order": 1
                    },
                    {
                        "channel": "sms",
                        "template": {"body": "Hi {{name}}, welcome!"},
                        "order": 2
                    }
                ]
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["steps"]) == 2

    def test_list_workflows(self):
        resp = requests.get(f"{BASE_URL}/v1/workflows", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_get_workflow(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Test WF",
                "triggerIdentifier": "test-wf-get"
            }
        )
        wf_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/v1/workflows/{wf_id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["triggerIdentifier"] == "test-wf-get"

    def test_update_workflow(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Original Name",
                "triggerIdentifier": "update-test-wf"
            }
        )
        wf_id = create_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/workflows/{wf_id}",
            headers=HEADERS,
            json={"name": "Updated Name", "active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["active"] is False

    def test_delete_workflow(self):
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "To Delete",
                "triggerIdentifier": "delete-wf"
            }
        )
        wf_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/v1/workflows/{wf_id}", headers=HEADERS)
        assert resp.status_code == 204

    def test_get_nonexistent_workflow_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/v1/workflows/nonexistent-id",
            headers=HEADERS
        )
        assert resp.status_code == 404


# ============================================================
# Steps Tests
# ============================================================

class TestSteps:
    def _create_workflow(self):
        resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Step Test WF",
                "triggerIdentifier": _u("step-test-")
            }
        )
        return resp.json()["id"]

    def test_create_step(self):
        wf_id = self._create_workflow()
        resp = requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={
                "channel": "email",
                "template": {"subject": "Test", "body": "Hello"},
                "order": 1
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "email"
        assert data["workflowId"] == wf_id

    def test_list_steps(self):
        wf_id = self._create_workflow()
        requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={"channel": "email", "template": {"subject": "S1", "body": "B1"}, "order": 1}
        )
        requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={"channel": "sms", "template": {"body": "B2"}, "order": 2}
        )
        resp = requests.get(f"{BASE_URL}/v1/workflows/{wf_id}/steps", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_get_step(self):
        wf_id = self._create_workflow()
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={"channel": "push", "template": {"title": "T", "body": "B"}, "order": 1}
        )
        step_id = create_resp.json()["id"]
        resp = requests.get(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps/{step_id}",
            headers=HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["channel"] == "push"

    def test_update_step(self):
        wf_id = self._create_workflow()
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={"channel": "email", "template": {"subject": "Old", "body": "Old"}, "order": 1}
        )
        step_id = create_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps/{step_id}",
            headers=HEADERS,
            json={"template": {"subject": "New", "body": "New"}, "active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["template"]["subject"] == "New"
        assert resp.json()["active"] is False

    def test_delete_step(self):
        wf_id = self._create_workflow()
        create_resp = requests.post(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps",
            headers=HEADERS,
            json={"channel": "sms", "template": {"body": "Test"}, "order": 1}
        )
        step_id = create_resp.json()["id"]
        resp = requests.delete(
            f"{BASE_URL}/v1/workflows/{wf_id}/steps/{step_id}",
            headers=HEADERS
        )
        assert resp.status_code == 204


# ============================================================
# Subscribers Tests
# ============================================================

class TestSubscribers:
    def test_create_subscriber(self):
        resp = requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={
                "subscriberId": "user-001",
                "firstName": "John",
                "lastName": "Doe",
                "email": "john@example.com",
                "phone": "+1234567890"
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subscriberId"] == "user-001"
        assert data["email"] == "john@example.com"

    def test_list_subscribers(self):
        resp = requests.get(f"{BASE_URL}/v1/subscribers", headers=HEADERS)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_subscriber(self):
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": "user-get-test", "email": "get@test.com"}
        )
        resp = requests.get(
            f"{BASE_URL}/v1/subscribers/user-get-test",
            headers=HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["subscriberId"] == "user-get-test"

    def test_update_subscriber(self):
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": "user-update-test", "email": "old@test.com"}
        )
        resp = requests.patch(
            f"{BASE_URL}/v1/subscribers/user-update-test",
            headers=HEADERS,
            json={"email": "new@test.com", "firstName": "Jane"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@test.com"
        assert resp.json()["firstName"] == "Jane"

    def test_delete_subscriber(self):
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": "user-delete-test"}
        )
        resp = requests.delete(
            f"{BASE_URL}/v1/subscribers/user-delete-test",
            headers=HEADERS
        )
        assert resp.status_code == 204

        resp = requests.get(
            f"{BASE_URL}/v1/subscribers/user-delete-test",
            headers=HEADERS
        )
        assert resp.status_code == 404

    def test_get_nonexistent_subscriber_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/v1/subscribers/nonexistent-user",
            headers=HEADERS
        )
        assert resp.status_code == 404

    def test_create_duplicate_subscriber_id(self):
        sub_id = _u("dup-test-")
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": "a@test.com"}
        )
        resp = requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": "b@test.com"}
        )
        # Should return conflict or validation error
        assert resp.status_code in [409, 422]


# ============================================================
# Subscriber Preferences Tests
# ============================================================

class TestPreferences:
    def _create_subscriber(self, sub_id):
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": f"{sub_id}@test.com", "phone": "+1111111111"}
        )

    def test_get_preferences_empty(self):
        sub_id = _u("pref-test-")
        self._create_subscriber(sub_id)
        resp = requests.get(
            f"{BASE_URL}/v1/subscribers/{sub_id}/preferences",
            headers=HEADERS
        )
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_update_global_preference(self):
        sub_id = _u("pref-global-")
        self._create_subscriber(sub_id)
        resp = requests.patch(
            f"{BASE_URL}/v1/subscribers/{sub_id}/preferences",
            headers=HEADERS,
            json={"channel": "email", "enabled": False}
        )
        assert resp.status_code == 200
        assert resp.json()["channel"] == "email"
        assert resp.json()["enabled"] is False

    def test_update_workflow_specific_preference(self):
        sub_id = _u("pref-wf-")
        self._create_subscriber(sub_id)
        # Create a workflow first
        wf_resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={"name": "Pref WF", "triggerIdentifier": _u("pref-wf-")}
        )
        wf_id = wf_resp.json()["id"]
        resp = requests.patch(
            f"{BASE_URL}/v1/subscribers/{sub_id}/preferences",
            headers=HEADERS,
            json={"channel": "sms", "enabled": False, "workflowId": wf_id}
        )
        assert resp.status_code == 200
        assert resp.json()["workflowId"] == wf_id


# ============================================================
# Topics Tests
# ============================================================

class TestTopics:
    def test_create_topic(self):
        resp = requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": "news-updates", "name": "News Updates"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "news-updates"
        assert data["name"] == "News Updates"

    def test_list_topics(self):
        resp = requests.get(f"{BASE_URL}/v1/topics", headers=HEADERS)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_topic(self):
        key = _u("topic-get-")
        requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": key, "name": "Get Test"}
        )
        resp = requests.get(f"{BASE_URL}/v1/topics/{key}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["key"] == key

    def test_update_topic(self):
        key = _u("topic-upd-")
        requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": key, "name": "Old Name"}
        )
        resp = requests.patch(
            f"{BASE_URL}/v1/topics/{key}",
            headers=HEADERS,
            json={"name": "New Name"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_topic(self):
        key = _u("topic-del-")
        requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": key, "name": "Delete Me"}
        )
        resp = requests.delete(f"{BASE_URL}/v1/topics/{key}", headers=HEADERS)
        assert resp.status_code == 204

    def test_add_subscribers_to_topic(self):
        key = _u("topic-sub-")
        requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": key, "name": "Sub Topic"}
        )
        sub1 = _u("tsub1-")
        sub2 = _u("tsub2-")
        requests.post(f"{BASE_URL}/v1/subscribers", headers=HEADERS, json={"subscriberId": sub1, "email": f"{sub1}@test.com"})
        requests.post(f"{BASE_URL}/v1/subscribers", headers=HEADERS, json={"subscriberId": sub2, "email": f"{sub2}@test.com"})

        resp = requests.post(
            f"{BASE_URL}/v1/topics/{key}/subscribers",
            headers=HEADERS,
            json={"subscriberIds": [sub1, sub2]}
        )
        assert resp.status_code == 200

        # Verify subscribers are listed
        resp = requests.get(f"{BASE_URL}/v1/topics/{key}/subscribers", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert sub1 in data
        assert sub2 in data

    def test_remove_subscribers_from_topic(self):
        key = _u("topic-rm-")
        requests.post(
            f"{BASE_URL}/v1/topics",
            headers=HEADERS,
            json={"key": key, "name": "Remove Topic"}
        )
        sub1 = _u("rmsub-")
        requests.post(f"{BASE_URL}/v1/subscribers", headers=HEADERS, json={"subscriberId": sub1, "email": f"{sub1}@test.com"})
        requests.post(
            f"{BASE_URL}/v1/topics/{key}/subscribers",
            headers=HEADERS,
            json={"subscriberIds": [sub1]}
        )

        resp = requests.post(
            f"{BASE_URL}/v1/topics/{key}/subscribers/remove",
            headers=HEADERS,
            json={"subscriberIds": [sub1]}
        )
        assert resp.status_code == 200

        # Verify subscriber removed
        resp = requests.get(f"{BASE_URL}/v1/topics/{key}/subscribers", headers=HEADERS)
        data = resp.json()["data"]
        assert sub1 not in data

    def test_get_nonexistent_topic_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/v1/topics/nonexistent-topic-key",
            headers=HEADERS
        )
        assert resp.status_code == 404


# ============================================================
# Trigger Tests
# ============================================================

class TestTriggers:
    def _setup_workflow_and_subscriber(self, trigger_id=None, email="trigger@test.com", phone="+1999999999"):
        """Helper to create a workflow with steps and a subscriber."""
        if trigger_id is None:
            trigger_id = _u("trigger-")
        sub_id = _u("sub-")

        # Create workflow with email and sms steps
        wf_resp = requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Trigger Test WF",
                "triggerIdentifier": trigger_id,
                "active": True,
                "steps": [
                    {
                        "channel": "email",
                        "template": {"subject": "Hello {{name}}", "body": "Welcome {{name}}!"},
                        "order": 1,
                        "active": True
                    },
                    {
                        "channel": "sms",
                        "template": {"body": "Hi {{name}}, check your email!"},
                        "order": 2,
                        "active": True
                    }
                ]
            }
        )
        wf_id = wf_resp.json()["id"]

        # Create subscriber
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": email, "phone": phone}
        )

        return trigger_id, sub_id, wf_id

    def test_trigger_nonexistent_workflow_returns_404(self):
        sub_id = _u("sub-404-")
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": "test@test.com"}
        )
        resp = requests.post(
            f"{BASE_URL}/v1/triggers",
            headers=HEADERS,
            json={
                "workflowIdentifier": "nonexistent-workflow",
                "to": sub_id,
                "payload": {}
            }
        )
        assert resp.status_code == 404

# ============================================================
# Subscriber Preferences and Trigger Interaction Tests
# ============================================================

class TestPreferencesAndTrigger:
    pass
# ============================================================
# Topic Broadcast Tests
# ============================================================

class TestTopicBroadcast:
    pass
# ============================================================
# Activity Feed Tests
# ============================================================

class TestActivityFeed:
    def test_activity_filter_by_subscriber(self):
        trigger_id = _u("act-filter-")
        sub_id = _u("sub-filter-")

        requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "Filter WF",
                "triggerIdentifier": trigger_id,
                "active": True,
                "steps": [
                    {"channel": "email", "template": {"subject": "T", "body": "B"}, "order": 1, "active": True}
                ]
            }
        )
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": "filter@test.com"}
        )
        requests.post(
            f"{BASE_URL}/v1/triggers",
            headers=HEADERS,
            json={"workflowIdentifier": trigger_id, "to": sub_id, "payload": {}}
        )

        resp = wait_for_activity({"subscriberId": sub_id})
        assert resp.status_code == 200
        for a in resp.json()["data"]:
            assert a["subscriberId"] == sub_id

    def test_get_activity_by_id(self):
        trigger_id = _u("act-get-")
        sub_id = _u("sub-actget-")

        requests.post(
            f"{BASE_URL}/v1/workflows",
            headers=HEADERS,
            json={
                "name": "GetAct WF",
                "triggerIdentifier": trigger_id,
                "active": True,
                "steps": [
                    {"channel": "email", "template": {"subject": "T", "body": "B"}, "order": 1, "active": True}
                ]
            }
        )
        requests.post(
            f"{BASE_URL}/v1/subscribers",
            headers=HEADERS,
            json={"subscriberId": sub_id, "email": "actget@test.com"}
        )
        requests.post(
            f"{BASE_URL}/v1/triggers",
            headers=HEADERS,
            json={"workflowIdentifier": trigger_id, "to": sub_id, "payload": {}}
        )

        list_resp = wait_for_activity({"subscriberId": sub_id})
        activities = list_resp.json()["data"]
        assert len(activities) >= 1
        activity_id = activities[0]["id"]

        resp = requests.get(f"{BASE_URL}/v1/activity/{activity_id}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == activity_id

    def test_activity_stats(self):
        resp = requests.get(f"{BASE_URL}/v1/activity/stats", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "sent" in data
        assert "failed" in data

    def test_get_nonexistent_activity_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/v1/activity/nonexistent-activity-id",
            headers=HEADERS
        )
        assert resp.status_code == 404


# ============================================================
# Multi-step Workflow Tests
# ============================================================

class TestMultiStepWorkflow:
    pass
# ============================================================
# Pagination Tests
# ============================================================

class TestPagination:
    def test_workflows_pagination(self):
        # Create several workflows
        for i in range(3):
            requests.post(
                f"{BASE_URL}/v1/workflows",
                headers=HEADERS,
                json={
                    "name": f"Paginated WF {i}",
                    "triggerIdentifier": _u(f"paginated-{i}-")
                }
            )

        resp = requests.get(f"{BASE_URL}/v1/workflows?page=0&limit=2", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 2
        assert data["limit"] == 2
        assert data["page"] == 0

    def test_subscribers_pagination(self):
        resp = requests.get(f"{BASE_URL}/v1/subscribers?page=0&limit=5", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["page"] == 0
