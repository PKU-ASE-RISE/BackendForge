"""
BackendForge — L3 Workflow Tests for Novu
Multi-step notification delivery workflows testing trigger execution, preferences, and activity.

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


def wait_for_stats_above(total):
    """Poll until the activity total advances, returning the last response."""
    deadline = time.monotonic() + POLL_TIMEOUT
    while True:
        response = get("/v1/activity/stats")
        try:
            current_total = response.json().get("total")
        except (requests.exceptions.JSONDecodeError, AttributeError):
            current_total = None
        if (
            response.status_code != 200
            or isinstance(current_total, int) and current_total > total
            or time.monotonic() >= deadline
        ):
            return response
        time.sleep(POLL_INTERVAL)


# ═══════════════════════════════════════════════════════════
# L3 Tests — Workflows (10-15 tests)
# ═══════════════════════════════════════════════════════════


class TestNotificationDeliveryWorkflow:
    """Full trigger → delivery → activity workflow."""

class TestPreferenceOptOutWorkflow:
    """Subscriber preferences opt-out affects delivery."""

class TestTopicBroadcastWorkflow:
    """Broadcast to topic sends to all topic subscribers."""

class TestActivityStatsWorkflow:
    """Activity stats reflect actual delivery results."""

    def test_activity_stats_reflect_deliveries(self):
        """Pattern 5: Stats endpoint returns aggregated counts."""
        # Get initial stats
        r = get("/v1/activity/stats")
        assert r.status_code == 200
        initial = r.json()
        assert "total" in initial
        assert "sent" in initial
        assert "failed" in initial
        assert "skipped" in initial

        # Trigger a successful delivery
        trigger_id = _u("stats-")
        post("/v1/workflows", {
            "name": "Stats WF",
            "triggerIdentifier": trigger_id,
            "steps": [{"channel": "email", "template": {"subject": "S", "body": "B"}, "order": 1}],
        })
        sub_id = _u("stats-sub-")
        post("/v1/subscribers", {"subscriberId": sub_id, "email": "stats@ok.com"})
        post("/v1/triggers", {"workflowIdentifier": trigger_id, "to": sub_id, "payload": {}})

        # Stats should increase
        r = wait_for_stats_above(initial["total"])
        updated = r.json()
        assert updated["total"] > initial["total"]


class TestWorkflowCRUDWorkflow:
    """Full workflow CRUD lifecycle."""

    def test_workflow_full_lifecycle(self):
        """Pattern 2+4+7: Create → update → add steps → delete."""
        # 1. Create workflow
        trigger_id = _u("lifecycle-")
        r = post("/v1/workflows", {
            "name": "Lifecycle WF",
            "triggerIdentifier": trigger_id,
            "description": "Original",
            "steps": [{"channel": "email", "template": {"subject": "Hi", "body": "Hello"}, "order": 1}],
        })
        assert r.status_code == 201
        wf_id = r.json()["id"]
        assert r.json()["name"] == "Lifecycle WF"
        assert len(r.json()["steps"]) == 1

        # 2. Update workflow name
        r = patch(f"/v1/workflows/{wf_id}", {"name": "Updated WF", "description": "Changed"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated WF"
        assert r.json()["description"] == "Changed"

        # 3. Add another step
        r = post(f"/v1/workflows/{wf_id}/steps", {
            "channel": "sms",
            "template": {"body": "SMS {{msg}}"},
            "order": 2,
        })
        assert r.status_code == 201
        step_id = r.json()["id"]

        # 4. Verify workflow has 2 steps
        r = get(f"/v1/workflows/{wf_id}")
        assert len(r.json()["steps"]) == 2

        # 5. Update step
        r = patch(f"/v1/workflows/{wf_id}/steps/{step_id}", {"active": False})
        assert r.status_code == 200
        assert r.json()["active"] is False

        # 6. Delete step
        r = delete(f"/v1/workflows/{wf_id}/steps/{step_id}")
        assert r.status_code == 204

        # 7. Verify 1 step remaining
        r = get(f"/v1/workflows/{wf_id}")
        assert len(r.json()["steps"]) == 1

        # 8. Delete workflow
        r = delete(f"/v1/workflows/{wf_id}")
        assert r.status_code == 204
        assert get(f"/v1/workflows/{wf_id}").status_code == 404


class TestSubscriberLifecycleWorkflow:
    """Subscriber full lifecycle."""

    def test_subscriber_crud_with_preferences(self):
        """Pattern 2+5: Subscriber CRUD + preferences + trigger interaction."""
        # 1. Create subscriber
        sub_id = _u("life-sub-")
        r = post("/v1/subscribers", {
            "subscriberId": sub_id,
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com",
            "phone": "+1555999888",
            "data": {"tier": "free"},
        })
        assert r.status_code == 201
        assert r.json()["subscriberId"] == sub_id
        assert r.json()["firstName"] == "John"
        assert r.json()["data"]["tier"] == "free"

        # 2. Update subscriber
        r = patch(f"/v1/subscribers/{sub_id}", {"firstName": "Jane", "data": {"tier": "pro"}})
        assert r.status_code == 200
        assert r.json()["firstName"] == "Jane"
        assert r.json()["data"]["tier"] == "pro"
        # lastName preserved
        assert r.json()["lastName"] == "Doe"

        # 3. Set preferences
        r = patch(f"/v1/subscribers/{sub_id}/preferences", {"channel": "sms", "enabled": False})
        assert r.status_code == 200

        # 4. Verify preferences
        r = get(f"/v1/subscribers/{sub_id}/preferences")
        prefs = r.json()["data"]
        sms_pref = next((p for p in prefs if p["channel"] == "sms"), None)
        assert sms_pref is not None
        assert sms_pref["enabled"] is False

        # 5. Delete subscriber
        r = delete(f"/v1/subscribers/{sub_id}")
        assert r.status_code == 204
        assert get(f"/v1/subscribers/{sub_id}").status_code == 404


class TestTemplateVariableSubstitution:
    """Verify template variables are actually substituted."""

class TestDeliveryFailureHandling:
    """Handling delivery failures (mock returns failure for "fail" addresses)."""

class TestWorkflowWithNotificationGroup:
    """Workflow associated with notification group."""

    def test_workflow_group_association(self):
        """Pattern 2: Workflow references notification group."""
        # Create group
        r = post("/v1/notification-groups", {"name": _u("wf-grp-")})
        assert r.status_code == 201
        grp_id = r.json()["id"]

        # Create workflow with group
        r = post("/v1/workflows", {
            "name": _u("grp-wf-"),
            "triggerIdentifier": _u("grp-trig-"),
            "notificationGroupId": grp_id,
            "steps": [{"channel": "email", "template": {"subject": "Hi", "body": "Body"}, "order": 1}],
        })
        assert r.status_code == 201
        assert r.json()["notificationGroupId"] == grp_id

        # GET workflow should still have group reference
        wf_id = r.json()["id"]
        r = get(f"/v1/workflows/{wf_id}")
        assert r.json()["notificationGroupId"] == grp_id
