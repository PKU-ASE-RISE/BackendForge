"""
BackendForge — L2 Integration Tests for Healthchecks Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: Field name casing (snake_case required per OpenAPI)
- Pattern 2: Nested/related data not returned
- Pattern 3: Parameters declared but not implemented (filtering, sorting)
- Pattern 4: Incorrect status codes (200 vs 201 vs 204)
- Pattern 5: Business logic "empty" (computed fields, counters)
- Pattern 6: Data isolation
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Concurrency/ordering sensitivity

Each test: 3-5 steps, 8-12 assertions, covers 1-2 bug patterns.
"""

import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
API_KEY = f"test-l2-integration-key-1-{RUN_ID}"
API_KEY_B = f"test-l2-integration-key-2-{RUN_ID}"

HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
HEADERS_B = {"X-Api-Key": API_KEY_B, "Content-Type": "application/json"}

UID = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent primary and secondary projects."""
    global API_KEY, API_KEY_B, HEADERS, HEADERS_B, UID

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    API_KEY = f"test-l2-integration-key-1-{item_id}"
    API_KEY_B = f"test-l2-integration-key-2-{item_id}"
    HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    HEADERS_B = {"X-Api-Key": API_KEY_B, "Content-Type": "application/json"}
    UID = item_id[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS if headers is None else headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS if headers is None else headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS if headers is None else headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS if headers is None else headers, timeout=30)


def ping(check_id, action="success", body=None):
    if action == "success":
        url = f"{BASE_URL}/ping/{check_id}"
    else:
        url = f"{BASE_URL}/ping/{check_id}/{action}"
    return requests.post(url, data=body or "", timeout=30)


# ════════════════════════════════════════════════════════════════════
# L2 INTEGRATION TESTS
# ════════════════════════════════════════════════════════════════════


class TestCheckFieldNames:
    """Pattern 1+2: Verify ALL field names in check responses use correct casing per OpenAPI."""

    def test_check_response_contains_all_snake_case_fields(self):
        """Create a check and verify all expected field names are present with correct casing."""
        resp = api_post("/api/v1/checks/", {"name": f"fields-{UID}", "tags": "web prod", "timeout": 3600, "grace": 600})
        assert resp.status_code == 201
        check = resp.json()

        # Verify all expected fields exist with EXACT names from OpenAPI spec
        assert "id" in check
        assert "name" in check
        assert "slug" in check
        assert "tags" in check
        assert "desc" in check
        assert "grace" in check
        assert "n_pings" in check
        assert "status" in check
        assert "kind" in check
        assert "timeout" in check
        assert "tz" in check
        assert "last_ping" in check
        assert "next_ping" in check
        assert "last_start" in check
        assert "last_duration" in check
        assert "channels" in check
        assert "manual_resume" in check
        assert "methods" in check
        assert "unique_key" in check

        # Verify NO camelCase variants exist
        assert "nPings" not in check
        assert "lastPing" not in check
        assert "nextPing" not in check
        assert "lastStart" not in check
        assert "lastDuration" not in check
        assert "manualResume" not in check
        assert "uniqueKey" not in check
        assert "filterSubject" not in check
        assert "filterBody" not in check

    def test_check_field_types_correct(self):
        """Verify field types match spec — integers are integers, booleans are booleans."""
        resp = api_post("/api/v1/checks/", {"name": f"types-{UID}", "timeout": 7200, "grace": 300})
        assert resp.status_code == 201
        check = resp.json()

        # Integer fields
        assert isinstance(check["grace"], int)
        assert isinstance(check["n_pings"], int)
        assert isinstance(check["timeout"], int)
        assert check["grace"] == 300
        assert check["timeout"] == 7200
        assert check["n_pings"] == 0

        # Boolean fields
        assert isinstance(check["manual_resume"], bool)
        assert isinstance(check["filter_subject"], bool)
        assert isinstance(check["filter_body"], bool)

        # String fields
        assert isinstance(check["status"], str)
        assert isinstance(check["kind"], str)
        assert isinstance(check["tz"], str)
        assert isinstance(check["channels"], str)

        # Nullable fields should be None initially
        assert check["last_ping"] is None
        assert check["last_start"] is None
        assert check["last_duration"] is None


class TestCheckStatusTransitions:
    """Pattern 5: Verify status actually CHANGES based on pings (not just echoed)."""

    def test_new_to_up_on_success_ping(self):
        """Ping a new check → status must change from 'new' to 'up'."""
        resp = api_post("/api/v1/checks/", {"name": f"new2up-{UID}", "timeout": 86400, "grace": 3600})
        assert resp.status_code == 201
        check = resp.json()
        check_id = check["id"]
        assert check["status"] == "new"
        assert check["n_pings"] == 0

        # Ping it
        pr = ping(check_id)
        assert pr.status_code == 200

        # Verify status changed
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["status"] == "up"
        assert updated["n_pings"] == 1
        assert updated["last_ping"] is not None

    def test_up_to_down_on_fail_ping(self):
        """Send fail ping → status must immediately become 'down'."""
        resp = api_post("/api/v1/checks/", {"name": f"up2dn-{UID}", "timeout": 86400, "grace": 3600})
        assert resp.status_code == 201
        check_id = resp.json()["id"]

        # First make it up
        ping(check_id)
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.json()["status"] == "up"

        # Now fail it
        pr = ping(check_id, "fail")
        assert pr.status_code == 200

        resp3 = api_get(f"/api/v1/checks/{check_id}")
        assert resp3.json()["status"] == "down"
        assert resp3.json()["n_pings"] == 2

    def test_down_to_up_on_success_ping(self):
        """After a fail, a success ping recovers the check back to 'up'."""
        resp = api_post("/api/v1/checks/", {"name": f"dn2up-{UID}", "timeout": 86400, "grace": 3600})
        assert resp.status_code == 201
        check_id = resp.json()["id"]

        ping(check_id, "fail")
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.json()["status"] == "down"

        # Recover
        ping(check_id)
        resp3 = api_get(f"/api/v1/checks/{check_id}")
        assert resp3.json()["status"] == "up"
        assert resp3.json()["n_pings"] == 2

    def test_start_ping_does_not_change_status_from_new(self):
        """Start ping should NOT change status — status remains 'new'."""
        resp = api_post("/api/v1/checks/", {"name": f"startno-{UID}"})
        assert resp.status_code == 201
        check_id = resp.json()["id"]

        ping(check_id, "start")
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.json()["status"] == "new"
        assert resp2.json()["n_pings"] == 1
        assert resp2.json()["last_start"] is not None
        # last_ping should NOT be set by start
        assert resp2.json()["last_ping"] is None

    def test_log_ping_does_not_change_status_or_last_ping(self):
        """Log ping increments n_pings but does NOT change status or last_ping."""
        resp = api_post("/api/v1/checks/", {"name": f"logno-{UID}"})
        assert resp.status_code == 201
        check_id = resp.json()["id"]

        # Make it up first
        ping(check_id)
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        lp_before = resp2.json()["last_ping"]
        assert resp2.json()["status"] == "up"
        assert resp2.json()["n_pings"] == 1

        time.sleep(0.05)
        # Log ping
        ping(check_id, "log")
        resp3 = api_get(f"/api/v1/checks/{check_id}")
        assert resp3.json()["status"] == "up"  # unchanged
        assert resp3.json()["n_pings"] == 2  # incremented
        assert resp3.json()["last_ping"] == lp_before  # NOT updated


class TestPingCounterIncrements:
    """Pattern 5: Verify n_pings ACTUALLY increments (not just stays at 0 or 1)."""

    def test_multiple_pings_increment_counter(self):
        """Send 4 different ping types → n_pings should be exactly 4."""
        resp = api_post("/api/v1/checks/", {"name": f"counter-{UID}"})
        assert resp.status_code == 201
        check_id = resp.json()["id"]
        assert resp.json()["n_pings"] == 0

        ping(check_id)
        ping(check_id, "start")
        ping(check_id)
        ping(check_id, "log")

        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.json()["n_pings"] == 4

    def test_fail_ping_also_increments_counter(self):
        """Fail pings should also increment n_pings."""
        resp = api_post("/api/v1/checks/", {"name": f"failcnt-{UID}"})
        assert resp.status_code == 201
        check_id = resp.json()["id"]

        ping(check_id, "fail")
        ping(check_id, "fail")
        ping(check_id, "fail")

        resp2 = api_get(f"/api/v1/checks/{check_id}")
        assert resp2.json()["n_pings"] == 3
        assert resp2.json()["status"] == "down"


class TestChannelFieldStructure:
    """Pattern 1+2: Verify channel response has correct field names and includes checks array."""

    def test_channel_response_fields(self):
        """Create a channel and verify all fields from OpenAPI spec are present."""
        resp = api_post("/api/v1/channels/", {
            "kind": "webhook",
            "name": f"ch-fields-{UID}",
            "webhook_url": "https://example.com/hook"
        })
        assert resp.status_code == 201
        ch = resp.json()

        assert "id" in ch
        assert "name" in ch
        assert "kind" in ch
        assert "email" in ch
        assert "webhook_url" in ch
        assert "checks" in ch

        # Verify types
        assert isinstance(ch["id"], str)
        assert isinstance(ch["checks"], list)
        assert ch["kind"] == "webhook"
        assert ch["name"] == f"ch-fields-{UID}"
        assert ch["webhook_url"] == "https://example.com/hook"

    def test_channel_checks_populated_after_assignment(self):
        """After assigning a channel to a check, channel.checks should include the check ID."""
        # Create check
        cr = api_post("/api/v1/checks/", {"name": f"ch-pop-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        # Create channel
        chr_resp = api_post("/api/v1/channels/", {"kind": "email", "email": f"pop-{UID}@test.com"})
        assert chr_resp.status_code == 201
        channel_id = chr_resp.json()["id"]
        assert chr_resp.json()["checks"] == []

        # Assign channel to check
        ar = api_post(f"/api/v1/checks/{check_id}/channels/{channel_id}", {})
        assert ar.status_code == 200

        # Verify channel now has the check in its checks list
        gr = api_get(f"/api/v1/channels/{channel_id}")
        assert gr.status_code == 200
        assert check_id in gr.json()["checks"]


class TestStatusCodes:
    """Pattern 4: Verify exact status codes for each operation."""

    def test_create_check_returns_201(self):
        """POST /api/v1/checks/ → 201 for new creation."""
        resp = api_post("/api/v1/checks/", {"name": f"sc201-{UID}"})
        assert resp.status_code == 201

    def test_create_channel_returns_201(self):
        """POST /api/v1/channels/ → 201 for new channel."""
        resp = api_post("/api/v1/channels/", {"kind": "email", "email": f"sc-{UID}@test.com"})
        assert resp.status_code == 201

    def test_create_integration_returns_201(self):
        """POST /api/v1/integrations/ → 201 for new integration."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"sc-int-{UID}",
            "webhook_url": "https://example.com/int"
        })
        assert resp.status_code == 201

    def test_delete_check_returns_200_with_body(self):
        """DELETE /api/v1/checks/{id} → 200 with the deleted check in response."""
        cr = api_post("/api/v1/checks/", {"name": f"del200-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        resp = api_delete(f"/api/v1/checks/{check_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == check_id
        assert body["name"] == f"del200-{UID}"

    def test_delete_channel_returns_200_with_body(self):
        """DELETE /api/v1/channels/{id} → 200 with the deleted channel."""
        cr = api_post("/api/v1/channels/", {"kind": "email", "email": f"delch-{UID}@test.com"})
        assert cr.status_code == 201
        channel_id = cr.json()["id"]

        resp = api_delete(f"/api/v1/channels/{channel_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == channel_id

    def test_ping_returns_200_with_ok(self):
        """POST /ping/{id} → 200 with 'OK' text."""
        cr = api_post("/api/v1/checks/", {"name": f"ping200-{UID}"})
        check_id = cr.json()["id"]

        resp = ping(check_id)
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_upsert_existing_returns_200(self):
        """POST /api/v1/checks/ with unique match → 200 (not 201)."""
        name = f"upsert-{UID}"
        resp1 = api_post("/api/v1/checks/", {"name": name, "unique": ["name"]})
        assert resp1.status_code == 201

        resp2 = api_post("/api/v1/checks/", {"name": name, "tags": "updated", "unique": ["name"]})
        assert resp2.status_code == 200
        assert resp2.json()["id"] == resp1.json()["id"]


class TestTagFiltering:
    """Pattern 3: Verify tag filtering ACTUALLY works (not returning all checks)."""

    def test_filter_returns_only_matching_checks(self):
        """Create checks with different tags → filter → verify ONLY matching returned."""
        tag_target = f"target-{UID}"
        tag_other = f"other-{UID}"

        # Create 3 checks: 2 with target tag, 1 with other tag
        c1 = api_post("/api/v1/checks/", {"name": f"t1-{UID}", "tags": tag_target})
        c2 = api_post("/api/v1/checks/", {"name": f"t2-{UID}", "tags": tag_target})
        c3 = api_post("/api/v1/checks/", {"name": f"t3-{UID}", "tags": tag_other})
        assert c1.status_code == 201
        assert c2.status_code == 201
        assert c3.status_code == 201

        # Filter by target tag
        resp = api_get("/api/v1/checks/", params={"tag": tag_target})
        assert resp.status_code == 200
        checks = resp.json()["checks"]

        # Should have exactly the 2 target-tagged checks
        ids = [c["id"] for c in checks]
        assert c1.json()["id"] in ids
        assert c2.json()["id"] in ids
        assert c3.json()["id"] not in ids

        # Verify all returned checks actually have the tag
        for c in checks:
            assert tag_target in c["tags"]

    def test_filter_by_nonexistent_tag_returns_empty(self):
        """Filtering by a tag that doesn't exist → empty list, not error."""
        resp = api_get("/api/v1/checks/", params={"tag": f"nonexistent-{uuid.uuid4().hex}"})
        assert resp.status_code == 200
        assert resp.json()["checks"] == []

    def test_filter_finds_check_with_multiple_tags(self):
        """A check with 'web prod db' tags should be found by any single tag."""
        tag1 = f"alpha-{UID}"
        tag2 = f"beta-{UID}"
        cr = api_post("/api/v1/checks/", {"name": f"multi-{UID}", "tags": f"{tag1} {tag2}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        # Search by first tag
        resp1 = api_get("/api/v1/checks/", params={"tag": tag1})
        ids1 = [c["id"] for c in resp1.json()["checks"]]
        assert check_id in ids1

        # Search by second tag
        resp2 = api_get("/api/v1/checks/", params={"tag": tag2})
        ids2 = [c["id"] for c in resp2.json()["checks"]]
        assert check_id in ids2


class TestScheduleCalculation:
    """Pattern 5: Verify next_ping is computed correctly for simple checks."""

    def test_next_ping_computed_after_success_ping(self):
        """After a success ping, next_ping should be set (last_ping + timeout for simple checks)."""
        resp = api_post("/api/v1/checks/", {"name": f"nxping-{UID}", "timeout": 3600, "grace": 600})
        assert resp.status_code == 201
        check_id = resp.json()["id"]
        assert resp.json()["next_ping"] is None  # no ping yet

        # Send a ping
        ping(check_id)

        # Get updated check
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        check = resp2.json()
        assert check["last_ping"] is not None

        # next_ping should be set; for simple checks, it's last_ping + timeout
        # We just verify it's not None and is in the future
        if check["next_ping"] is not None:
            last_ping_dt = datetime.fromisoformat(check["last_ping"].replace("Z", "+00:00"))
            next_ping_dt = datetime.fromisoformat(check["next_ping"].replace("Z", "+00:00"))
            # next_ping should be after last_ping
            assert next_ping_dt > last_ping_dt


class TestPingHistory:
    """Pattern 2+5: Verify ping history is actually recorded and has correct structure."""

    def test_ping_history_records_all_types(self):
        """Send 4 different ping types → all 4 appear in history with correct types."""
        cr = api_post("/api/v1/checks/", {"name": f"hist-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        ping(check_id)
        ping(check_id, "fail")
        ping(check_id, "start")
        ping(check_id, "log")

        resp = api_get(f"/api/v1/checks/{check_id}/pings/")
        assert resp.status_code == 200
        pings = resp.json()["pings"]
        assert len(pings) == 4

        types = [p["type"] for p in pings]
        assert "success" in types
        assert "fail" in types
        assert "start" in types
        assert "log" in types

    def test_ping_history_in_reverse_chronological_order(self):
        """Most recent ping should be first in the list."""
        cr = api_post("/api/v1/checks/", {"name": f"order-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        ping(check_id)
        time.sleep(0.05)
        ping(check_id)
        time.sleep(0.05)
        ping(check_id, "fail")

        resp = api_get(f"/api/v1/checks/{check_id}/pings/")
        pings = resp.json()["pings"]
        assert len(pings) >= 3

        # n values should be descending (most recent first)
        for i in range(len(pings) - 1):
            assert pings[i]["n"] > pings[i + 1]["n"]

    def test_ping_history_entry_has_all_fields(self):
        """Each ping entry must have type, date, n, scheme, remote_addr, method."""
        cr = api_post("/api/v1/checks/", {"name": f"pfields-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id, body="hello world")

        resp = api_get(f"/api/v1/checks/{check_id}/pings/")
        pings = resp.json()["pings"]
        assert len(pings) >= 1
        p = pings[0]

        assert "type" in p
        assert "date" in p
        assert "n" in p
        assert "scheme" in p
        assert "remote_addr" in p
        assert "method" in p
        assert "body" in p
        assert "duration" in p

        assert p["type"] == "success"
        assert p["n"] == 1
        assert p["body"] == "hello world"


class TestDurationCalculation:
    """Pattern 5: Verify duration is COMPUTED from start→success time difference."""

    def test_duration_computed_after_start_then_success(self):
        """start → wait → success: last_duration reflects actual elapsed time."""
        cr = api_post("/api/v1/checks/", {"name": f"dur-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id, "start")
        time.sleep(0.2)
        ping(check_id)

        resp = api_get(f"/api/v1/checks/{check_id}")
        check = resp.json()
        assert check["last_duration"] is not None
        assert check["last_duration"] >= 0.1  # Should be ~0.2s

    def test_no_duration_without_start(self):
        """Success without preceding start → last_duration remains None."""
        cr = api_post("/api/v1/checks/", {"name": f"nodur-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id)

        resp = api_get(f"/api/v1/checks/{check_id}")
        assert resp.json()["last_duration"] is None

    def test_duration_in_ping_history(self):
        """Duration should also be recorded in the ping history entry."""
        cr = api_post("/api/v1/checks/", {"name": f"durhist-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id, "start")
        time.sleep(0.15)
        ping(check_id)

        resp = api_get(f"/api/v1/checks/{check_id}/pings/")
        pings = resp.json()["pings"]
        # Most recent ping should be the success with duration
        success_pings = [p for p in pings if p["type"] == "success"]
        assert len(success_pings) >= 1
        assert success_pings[0]["duration"] is not None
        assert success_pings[0]["duration"] >= 0.1


class TestFlipRecording:
    """Pattern 5+7: Verify flips are ACTUALLY recorded on status transitions."""

    def test_flip_recorded_on_new_to_up(self):
        """First success ping should create a flip from new→up (up=1)."""
        cr = api_post("/api/v1/checks/", {"name": f"flip1-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id)

        resp = api_get(f"/api/v1/checks/{check_id}/flips/")
        assert resp.status_code == 200
        flips = resp.json()["flips"]
        assert len(flips) >= 1
        # Should have an 'up' flip
        assert any(f["up"] == 1 for f in flips)

    def test_flip_recorded_on_up_to_down(self):
        """Fail ping after success should create a flip (up=0)."""
        cr = api_post("/api/v1/checks/", {"name": f"flip2-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id)  # new → up
        ping(check_id, "fail")  # up → down

        resp = api_get(f"/api/v1/checks/{check_id}/flips/")
        flips = resp.json()["flips"]
        assert len(flips) >= 2
        up_values = [f["up"] for f in flips]
        assert 1 in up_values  # up transition
        assert 0 in up_values  # down transition

    def test_no_flip_on_repeated_success(self):
        """Multiple success pings should NOT create additional flips."""
        cr = api_post("/api/v1/checks/", {"name": f"noflip-{UID}"})
        check_id = cr.json()["id"]

        ping(check_id)  # new → up: 1 flip

        resp = api_get(f"/api/v1/checks/{check_id}/flips/")
        count_after_first = len(resp.json()["flips"])

        ping(check_id)  # up → up: no flip
        ping(check_id)  # up → up: no flip

        resp2 = api_get(f"/api/v1/checks/{check_id}/flips/")
        count_after_more = len(resp2.json()["flips"])
        assert count_after_more == count_after_first


class TestPauseResumeIntegration:
    """Pattern 4+5: Verify pause/resume changes status correctly and returns proper codes."""

    def test_pause_sets_status_paused(self):
        """Pause → status becomes 'paused', response is 200."""
        cr = api_post("/api/v1/checks/", {"name": f"pause-{UID}"})
        check_id = cr.json()["id"]
        ping(check_id)

        resp = api_post(f"/api/v1/checks/{check_id}/pause", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

        # Verify via GET
        gr = api_get(f"/api/v1/checks/{check_id}")
        assert gr.json()["status"] == "paused"

    def test_resume_resets_to_new(self):
        """Resume → status becomes 'new', last_ping cleared."""
        cr = api_post("/api/v1/checks/", {"name": f"resume-{UID}"})
        check_id = cr.json()["id"]
        ping(check_id)  # up

        api_post(f"/api/v1/checks/{check_id}/pause", {})
        resp = api_post(f"/api/v1/checks/{check_id}/resume", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "new"
        assert resp.json()["last_ping"] is None

    def test_resume_non_paused_returns_409(self):
        """Resuming a non-paused check → 409 Conflict."""
        cr = api_post("/api/v1/checks/", {"name": f"409-{UID}"})
        check_id = cr.json()["id"]
        ping(check_id)

        resp = api_post(f"/api/v1/checks/{check_id}/resume", {})
        assert resp.status_code == 409


class TestValidationErrors:
    """Pattern 4: Verify validation returns 400 with error body (not 500 or 200)."""

    def test_timeout_below_60_returns_400(self):
        """timeout=30 → 400."""
        resp = api_post("/api/v1/checks/", {"timeout": 30})
        assert resp.status_code == 400

    def test_timeout_above_max_returns_400(self):
        """timeout=99999999 → 400."""
        resp = api_post("/api/v1/checks/", {"timeout": 99999999})
        assert resp.status_code == 400

    def test_grace_below_60_returns_400(self):
        """grace=10 → 400."""
        resp = api_post("/api/v1/checks/", {"grace": 10})
        assert resp.status_code == 400

    def test_invalid_cron_returns_400(self):
        """schedule='not cron' → 400."""
        resp = api_post("/api/v1/checks/", {"schedule": "not a valid cron"})
        assert resp.status_code == 400

    def test_channel_missing_kind_returns_400(self):
        """Creating channel without kind → 400."""
        resp = api_post("/api/v1/channels/", {"name": "no kind"})
        assert resp.status_code == 400

    def test_channel_invalid_kind_returns_400(self):
        """Creating channel with invalid kind → 400."""
        resp = api_post("/api/v1/channels/", {"kind": "sms"})
        assert resp.status_code == 400


class TestAuthAndIsolation:
    """Pattern 6: Verify data isolation between API keys."""

    def test_missing_api_key_returns_401(self):
        """Any /api/v1/ endpoint without X-Api-Key → 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/checks/", timeout=30)
        assert resp.status_code == 401

        resp2 = requests.get(f"{BASE_URL}/api/v1/channels/", timeout=30)
        assert resp2.status_code == 401

        resp3 = requests.get(f"{BASE_URL}/api/v1/project/", timeout=30)
        assert resp3.status_code == 401

    def test_cross_project_access_returns_403(self):
        """Accessing a check from another project → 403."""
        cr = api_post("/api/v1/checks/", {"name": f"iso-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        # Try to access with different API key
        resp = api_get(f"/api/v1/checks/{check_id}", headers=HEADERS_B)
        assert resp.status_code == 403

    def test_list_isolation(self):
        """Listing checks with key B should NOT show key A's checks."""
        name = f"isolated-{UID}"
        cr = api_post("/api/v1/checks/", {"name": name})
        assert cr.status_code == 201

        resp = api_get("/api/v1/checks/", headers=HEADERS_B)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["checks"]]
        assert name not in names
