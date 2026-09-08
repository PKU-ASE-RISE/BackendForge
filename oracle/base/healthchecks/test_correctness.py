"""
BackendForge — Comprehensive Correctness Tests for Healthchecks Task

Tests ALL business rules and ALL endpoint groups.
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
API_KEY_1 = f"test-api-key-project-1-{RUN_ID}"
API_KEY_2 = f"test-api-key-project-2-{RUN_ID}"

HEADERS = {
    "X-Api-Key": API_KEY_1,
    "Content-Type": "application/json",
}

HEADERS_PROJECT2 = {
    "X-Api-Key": API_KEY_2,
    "Content-Type": "application/json",
}

UNIQUE = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent project namespaces."""
    global API_KEY_1, API_KEY_2, HEADERS, HEADERS_PROJECT2, UNIQUE

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    API_KEY_1 = f"test-api-key-project-1-{item_id}"
    API_KEY_2 = f"test-api-key-project-2-{item_id}"
    HEADERS = {"X-Api-Key": API_KEY_1, "Content-Type": "application/json"}
    HEADERS_PROJECT2 = {"X-Api-Key": API_KEY_2, "Content-Type": "application/json"}
    UNIQUE = item_id[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS if headers is None else headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS if headers is None else headers, timeout=30)


def api_post_text(path, data=None, headers=None):
    """POST with text/plain body (for ping endpoints)."""
    h = {}
    if headers:
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
    return requests.post(f"{BASE_URL}{path}", data=data or "", headers=h, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS if headers is None else headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS if headers is None else headers, timeout=30)


# ── Domain Helpers ──

def create_check(name=None, **kwargs):
    """Create a check and return the full check object."""
    data = {}
    if name:
        data["name"] = name
    data.update(kwargs)
    resp = api_post("/api/v1/checks/", data)
    assert resp.status_code == 201, f"Create check failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_channel(kind="email", name=None, **kwargs):
    """Create a channel and return the full channel object."""
    data = {"kind": kind}
    if name:
        data["name"] = name
    if kind == "email":
        data["email"] = kwargs.pop("email", f"test-{uuid.uuid4().hex[:8]}@example.com")
    elif kind in ("webhook", "slack", "pagerduty", "opsgenie"):
        data["webhook_url"] = kwargs.pop("webhook_url", f"https://example.com/hook/{uuid.uuid4().hex[:8]}")
    data.update(kwargs)
    resp = api_post("/api/v1/channels/", data)
    assert resp.status_code == 201, f"Create channel failed: {resp.status_code} {resp.text}"
    return resp.json()


def ping_check(check_id, action="success", body=None):
    """Send a ping to a check."""
    if action == "success":
        path = f"/ping/{check_id}"
    else:
        path = f"/ping/{check_id}/{action}"
    resp = api_post_text(path, data=body)
    assert resp.status_code == 200, f"Ping failed: {resp.status_code} {resp.text}"
    return resp


# ════════════════════════════════════════════════════════════════════
# PART 1: Basic CRUD — Checks
# ════════════════════════════════════════════════════════════════════


class TestCheckCRUD:
    """Create → read → update → delete checks."""

    def test_create_check_minimal(self):
        """Create a check with no fields — should get defaults."""
        resp = api_post("/api/v1/checks/", {})
        assert resp.status_code == 201
        check = resp.json()
        assert "id" in check
        assert check["status"] == "new"
        assert check["kind"] == "simple"
        assert check["timeout"] == 86400  # default 1 day
        assert check["grace"] == 3600  # default 1 hour

    def test_create_check_with_name_and_tags(self):
        """Create a check with name and tags."""
        name = f"My Check {UNIQUE}"
        check = create_check(name=name, tags=f"prod web {UNIQUE}")
        assert check["name"] == name
        assert UNIQUE in check["tags"]

    def test_get_check_by_id(self):
        """GET /api/v1/checks/{id} returns the check."""
        check = create_check(name=f"GetMe {UNIQUE}")
        check_id = check["id"]

        resp = api_get(f"/api/v1/checks/{check_id}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == check_id
        assert fetched["name"] == check["name"]

    def test_update_check(self):
        """POST /api/v1/checks/{id} updates specific fields."""
        check = create_check(name=f"UpdateMe {UNIQUE}")
        check_id = check["id"]

        resp = api_post(f"/api/v1/checks/{check_id}", {"name": f"Updated {UNIQUE}", "tags": "updated"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"Updated {UNIQUE}"
        assert updated["tags"] == "updated"

    def test_update_preserves_unchanged_fields(self):
        """Partial update: fields not in body remain unchanged."""
        check = create_check(name=f"Partial {UNIQUE}", tags="keep-this", timeout=7200)
        check_id = check["id"]

        # Only update name
        resp = api_post(f"/api/v1/checks/{check_id}", {"name": f"NewName {UNIQUE}"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"NewName {UNIQUE}"
        assert updated["tags"] == "keep-this"  # unchanged
        assert updated["timeout"] == 7200  # unchanged

    def test_delete_check(self):
        """DELETE /api/v1/checks/{id} removes the check and returns it."""
        check = create_check(name=f"DeleteMe {UNIQUE}")
        check_id = check["id"]

        resp = api_delete(f"/api/v1/checks/{check_id}")
        assert resp.status_code == 200
        deleted = resp.json()
        assert deleted["id"] == check_id

        # Should be gone
        resp = api_get(f"/api/v1/checks/{check_id}")
        assert resp.status_code == 404

    def test_list_checks(self):
        """GET /api/v1/checks/ returns checks in the project."""
        name = f"Listed {UNIQUE}"
        create_check(name=name)

        resp = api_get("/api/v1/checks/")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        names = [c["name"] for c in data["checks"]]
        assert name in names

    def test_create_check_with_timeout(self):
        """Create a simple check with custom timeout."""
        check = create_check(name=f"Custom TO {UNIQUE}", timeout=3600, grace=600)
        assert check["timeout"] == 3600
        assert check["grace"] == 600
        assert check["kind"] == "simple"

    def test_create_check_with_schedule(self):
        """Create a cron check with schedule."""
        check = create_check(name=f"Cron {UNIQUE}", schedule="*/5 * * * *", tz="UTC", grace=300)
        assert check["schedule"] == "*/5 * * * *"
        assert check["kind"] == "cron"
        assert check["tz"] == "UTC"

    def test_check_has_all_expected_fields(self):
        """A returned check has all fields from the schema."""
        check = create_check(name=f"Fields {UNIQUE}")
        expected_fields = [
            "id", "name", "slug", "tags", "desc", "grace", "n_pings",
            "status", "kind", "timeout", "tz", "last_ping", "last_start",
            "last_duration", "channels", "manual_resume", "methods",
            "subject", "subject_fail", "start_kw", "success_kw",
            "failure_kw", "filter_subject", "filter_body", "unique_key"
        ]
        for field in expected_fields:
            assert field in check, f"Missing field '{field}' in check response"


# ════════════════════════════════════════════════════════════════════
# PART 2: Basic CRUD — Channels
# ════════════════════════════════════════════════════════════════════


class TestChannelCRUD:
    """Create → read → update → delete channels."""

    def test_create_email_channel(self):
        """Create an email notification channel."""
        ch = create_channel(kind="email", name=f"Email {UNIQUE}", email=f"alert-{UNIQUE}@test.com")
        assert ch["kind"] == "email"
        assert ch["email"] == f"alert-{UNIQUE}@test.com"
        assert "id" in ch

    def test_create_webhook_channel(self):
        """Create a webhook notification channel."""
        ch = create_channel(kind="webhook", name=f"Webhook {UNIQUE}",
                           webhook_url=f"https://hooks.example.com/{UNIQUE}")
        assert ch["kind"] == "webhook"
        assert ch["webhook_url"] == f"https://hooks.example.com/{UNIQUE}"

    def test_get_channel(self):
        """GET /api/v1/channels/{id} returns the channel."""
        ch = create_channel(kind="email", email=f"get-{UNIQUE}@test.com")
        ch_id = ch["id"]

        resp = api_get(f"/api/v1/channels/{ch_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == ch_id

    def test_update_channel(self):
        """PUT /api/v1/channels/{id} updates the channel."""
        ch = create_channel(kind="email", name=f"OldName {UNIQUE}", email=f"old-{UNIQUE}@test.com")
        ch_id = ch["id"]

        resp = api_put(f"/api/v1/channels/{ch_id}", {"name": f"NewName {UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"NewName {UNIQUE}"

    def test_delete_channel(self):
        """DELETE /api/v1/channels/{id} removes the channel."""
        ch = create_channel(kind="email", email=f"del-{UNIQUE}@test.com")
        ch_id = ch["id"]

        resp = api_delete(f"/api/v1/channels/{ch_id}")
        assert resp.status_code == 200

        resp = api_get(f"/api/v1/channels/{ch_id}")
        assert resp.status_code == 404

    def test_list_channels(self):
        """GET /api/v1/channels/ returns channels in envelope."""
        ch = create_channel(kind="email", name=f"ListCh {UNIQUE}", email=f"list-{UNIQUE}@test.com")

        resp = api_get("/api/v1/channels/")
        assert resp.status_code == 200
        data = resp.json()
        assert "channels" in data
        ids = [c["id"] for c in data["channels"]]
        assert ch["id"] in ids

    def test_channel_has_checks_field(self):
        """Channel response includes a 'checks' array."""
        ch = create_channel(kind="email", email=f"checks-field-{UNIQUE}@test.com")
        assert "checks" in ch
        assert isinstance(ch["checks"], list)


# ════════════════════════════════════════════════════════════════════
# PART 3: Basic CRUD — Integrations
# ════════════════════════════════════════════════════════════════════


class TestIntegrationCRUD:
    """Create → read → update → delete integrations."""

    def test_create_integration(self):
        """Create a webhook integration."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"Int {UNIQUE}",
            "webhook_url": f"https://int.example.com/{UNIQUE}",
        })
        assert resp.status_code == 201
        integration = resp.json()
        assert integration["kind"] == "webhook"
        assert integration["name"] == f"Int {UNIQUE}"
        assert integration["is_active"] is True
        assert "id" in integration

    def test_get_integration(self):
        """GET /api/v1/integrations/{id} returns the integration."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "slack",
            "name": f"GetInt {UNIQUE}",
            "webhook_url": f"https://slack.example.com/{UNIQUE}",
        })
        assert resp.status_code == 201
        int_id = resp.json()["id"]

        resp = api_get(f"/api/v1/integrations/{int_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == int_id

    def test_update_integration(self):
        """PUT /api/v1/integrations/{id} updates."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"UpdInt {UNIQUE}",
            "webhook_url": "https://example.com/hook",
        })
        assert resp.status_code == 201
        int_id = resp.json()["id"]

        resp = api_put(f"/api/v1/integrations/{int_id}", {"name": f"Updated Int {UNIQUE}", "is_active": False})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated Int {UNIQUE}"
        assert resp.json()["is_active"] is False

    def test_delete_integration(self):
        """DELETE /api/v1/integrations/{id}."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "email",
            "name": f"DelInt {UNIQUE}",
            "email": f"del-int-{UNIQUE}@test.com",
        })
        assert resp.status_code == 201
        int_id = resp.json()["id"]

        resp = api_delete(f"/api/v1/integrations/{int_id}")
        assert resp.status_code == 200

        resp = api_get(f"/api/v1/integrations/{int_id}")
        assert resp.status_code == 404

    def test_list_integrations(self):
        """GET /api/v1/integrations/ returns integrations in envelope."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"ListInt {UNIQUE}",
            "webhook_url": "https://list.example.com",
        })
        assert resp.status_code == 201
        int_id = resp.json()["id"]

        resp = api_get("/api/v1/integrations/")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data
        ids = [i["id"] for i in data["integrations"]]
        assert int_id in ids


# ════════════════════════════════════════════════════════════════════
# PART 4: Ping Endpoints
# ════════════════════════════════════════════════════════════════════


class TestPingEndpoints:
    """Ping endpoints record pings and update check status."""

    def test_ping_success(self):
        """POST /ping/{id} records a success ping."""
        check = create_check(name=f"PingSuccess {UNIQUE}")
        resp = api_post_text(f"/ping/{check['id']}")
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_ping_fail(self):
        """POST /ping/{id}/fail records a failure ping."""
        check = create_check(name=f"PingFail {UNIQUE}")
        resp = api_post_text(f"/ping/{check['id']}/fail")
        assert resp.status_code == 200

    def test_ping_start(self):
        """POST /ping/{id}/start records a start ping."""
        check = create_check(name=f"PingStart {UNIQUE}")
        resp = api_post_text(f"/ping/{check['id']}/start")
        assert resp.status_code == 200

    def test_ping_log(self):
        """POST /ping/{id}/log records a log ping."""
        check = create_check(name=f"PingLog {UNIQUE}")
        resp = api_post_text(f"/ping/{check['id']}/log")
        assert resp.status_code == 200

    def test_ping_nonexistent_check(self):
        """Pinging a non-existent check returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post_text(f"/ping/{fake_id}")
        assert resp.status_code == 404

    def test_ping_get_method(self):
        """GET /ping/{id} also records a success ping."""
        check = create_check(name=f"PingGet {UNIQUE}")
        resp = requests.get(f"{BASE_URL}/ping/{check['id']}", timeout=30)
        assert resp.status_code == 200

    def test_ping_increments_n_pings(self):
        """Each ping increments n_pings counter."""
        check = create_check(name=f"NPings {UNIQUE}")
        assert check["n_pings"] == 0

        ping_check(check["id"])
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}")
        updated = resp.json()
        assert updated["n_pings"] == 2

    def test_ping_updates_last_ping(self):
        """Success ping updates last_ping timestamp."""
        check = create_check(name=f"LastPing {UNIQUE}")
        assert check["last_ping"] is None

        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}")
        updated = resp.json()
        assert updated["last_ping"] is not None

    def test_ping_with_body(self):
        """Ping can include a body that is recorded."""
        check = create_check(name=f"PingBody {UNIQUE}")
        body_text = f"Build #{UNIQUE} passed"
        ping_check(check["id"], body=body_text)

        resp = api_get(f"/api/v1/checks/{check['id']}/pings/")
        pings = resp.json()["pings"]
        assert len(pings) >= 1
        assert pings[0]["body"] == body_text


# ════════════════════════════════════════════════════════════════════
# PART 5: Status Logic (Business Rules 1-4)
# ════════════════════════════════════════════════════════════════════


class TestStatusLogic:
    """Check status transitions based on pings."""

    def test_new_check_status(self):
        """A newly created check has status 'new'."""
        check = create_check(name=f"NewStatus {UNIQUE}")
        assert check["status"] == "new"

    def test_success_ping_sets_up(self):
        """After a success ping, status becomes 'up'."""
        check = create_check(name=f"UpStatus {UNIQUE}", timeout=86400, grace=3600)
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "up"

    def test_fail_ping_sets_down(self):
        """After a failure ping, status becomes 'down' immediately."""
        check = create_check(name=f"DownStatus {UNIQUE}", timeout=86400, grace=3600)
        # First a success to set up
        ping_check(check["id"])
        # Then a fail
        ping_check(check["id"], action="fail")

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "down"

    def test_start_ping_does_not_change_status(self):
        """A start ping does not change the status (stays 'new' if never pinged)."""
        check = create_check(name=f"StartNoChange {UNIQUE}")
        ping_check(check["id"], action="start")

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "new"

    def test_log_ping_does_not_change_status(self):
        """A log ping does not change status."""
        check = create_check(name=f"LogNoChange {UNIQUE}")
        ping_check(check["id"])  # Set to up first

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "up"

        ping_check(check["id"], action="log")

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "up"  # Still up

    def test_fail_after_success_sets_down(self):
        """Fail ping always sets status to 'down', even if previously 'up'."""
        check = create_check(name=f"FailOverride {UNIQUE}")
        ping_check(check["id"])  # up
        ping_check(check["id"], action="fail")  # down

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "down"

    def test_success_after_fail_sets_up(self):
        """Success ping after a fail sets status back to 'up'."""
        check = create_check(name=f"Recovery {UNIQUE}", timeout=86400, grace=3600)
        ping_check(check["id"], action="fail")  # down
        ping_check(check["id"])  # up again

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["status"] == "up"

    def test_log_does_not_update_last_ping(self):
        """A log ping should NOT update last_ping."""
        check = create_check(name=f"LogNoPing {UNIQUE}")
        # Never pinged, last_ping should be None
        ping_check(check["id"], action="log")

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["last_ping"] is None

    def test_start_updates_last_start(self):
        """A start ping updates last_start."""
        check = create_check(name=f"StartLS {UNIQUE}")
        assert check["last_start"] is None

        ping_check(check["id"], action="start")

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["last_start"] is not None


# ════════════════════════════════════════════════════════════════════
# PART 6: Pause/Resume (Business Rule 6)
# ════════════════════════════════════════════════════════════════════


class TestPauseResume:
    """Pause and resume checks."""

    def test_pause_check(self):
        """Pausing a check sets status to 'paused'."""
        check = create_check(name=f"Pause {UNIQUE}")
        ping_check(check["id"])  # set to up

        resp = api_post(f"/api/v1/checks/{check['id']}/pause", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_resume_paused_check(self):
        """Resuming a paused check sets status to 'new'."""
        check = create_check(name=f"Resume {UNIQUE}")
        api_post(f"/api/v1/checks/{check['id']}/pause", {})

        resp = api_post(f"/api/v1/checks/{check['id']}/resume", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "new"

    def test_resume_non_paused_returns_409(self):
        """Resuming a check that is not paused returns 409."""
        check = create_check(name=f"NotPaused {UNIQUE}")
        ping_check(check["id"])  # Set to "up"

        resp = api_post(f"/api/v1/checks/{check['id']}/resume", {})
        assert resp.status_code == 409

    def test_pause_already_paused_is_ok(self):
        """Pausing an already-paused check returns 200."""
        check = create_check(name=f"AlreadyPaused {UNIQUE}")
        api_post(f"/api/v1/checks/{check['id']}/pause", {})
        resp = api_post(f"/api/v1/checks/{check['id']}/pause", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_resume_clears_last_ping(self):
        """After resume, last_ping should be cleared."""
        check = create_check(name=f"ResumeClear {UNIQUE}")
        ping_check(check["id"])
        api_post(f"/api/v1/checks/{check['id']}/pause", {})
        resp = api_post(f"/api/v1/checks/{check['id']}/resume", {})
        assert resp.status_code == 200
        assert resp.json()["last_ping"] is None

    def test_pause_new_check(self):
        """Pausing a new (never pinged) check also works."""
        check = create_check(name=f"PauseNew {UNIQUE}")
        resp = api_post(f"/api/v1/checks/{check['id']}/pause", {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"


# ════════════════════════════════════════════════════════════════════
# PART 7: Channel Assignment (Business Rule 7)
# ════════════════════════════════════════════════════════════════════


class TestChannelAssignment:
    """Assign/remove channels to/from checks."""

    def test_assign_channel_to_check(self):
        """POST /api/v1/checks/{id}/channels/{ch_id} assigns."""
        check = create_check(name=f"AssignCh {UNIQUE}")
        ch = create_channel(kind="email", email=f"assign-{UNIQUE}@test.com")

        resp = api_post(f"/api/v1/checks/{check['id']}/channels/{ch['id']}", {})
        assert resp.status_code == 200

        # Verify check now has the channel
        resp = api_get(f"/api/v1/checks/{check['id']}")
        check_data = resp.json()
        assert ch["id"] in check_data["channels"]

    def test_remove_channel_from_check(self):
        """DELETE /api/v1/checks/{id}/channels/{ch_id} removes."""
        check = create_check(name=f"RemoveCh {UNIQUE}")
        ch = create_channel(kind="email", email=f"remove-{UNIQUE}@test.com")

        # Assign first
        api_post(f"/api/v1/checks/{check['id']}/channels/{ch['id']}", {})

        # Remove
        resp = api_delete(f"/api/v1/checks/{check['id']}/channels/{ch['id']}")
        assert resp.status_code == 200

        # Verify removed
        resp = api_get(f"/api/v1/checks/{check['id']}")
        check_data = resp.json()
        assert ch["id"] not in check_data.get("channels", "")

    def test_create_check_with_channels_star(self):
        """Creating a check with channels='*' assigns all project channels."""
        ch1 = create_channel(kind="email", email=f"star1-{UNIQUE}@test.com")
        ch2 = create_channel(kind="webhook", webhook_url=f"https://star-{UNIQUE}.example.com")

        check = create_check(name=f"StarChannels {UNIQUE}", channels="*")
        # Both channels should be assigned
        assert ch1["id"] in check["channels"]
        assert ch2["id"] in check["channels"]

    def test_create_check_with_channels_empty(self):
        """Creating a check with channels='' assigns no channels."""
        check = create_check(name=f"NoChannels {UNIQUE}", channels="")
        assert check["channels"] == ""

    def test_update_check_with_specific_channels(self):
        """Updating channels with comma-separated IDs assigns those specific channels."""
        check = create_check(name=f"SpecificCh {UNIQUE}")
        ch = create_channel(kind="email", email=f"specific-{UNIQUE}@test.com")

        resp = api_post(f"/api/v1/checks/{check['id']}", {"channels": ch["id"]})
        assert resp.status_code == 200
        assert ch["id"] in resp.json()["channels"]

    def test_channel_shows_assigned_checks(self):
        """Channel's 'checks' field lists assigned check IDs."""
        check = create_check(name=f"ChShowsCheck {UNIQUE}")
        ch = create_channel(kind="email", email=f"showcheck-{UNIQUE}@test.com")

        api_post(f"/api/v1/checks/{check['id']}/channels/{ch['id']}", {})

        resp = api_get(f"/api/v1/channels/{ch['id']}")
        assert resp.status_code == 200
        ch_data = resp.json()
        assert check["id"] in ch_data["checks"]


# ════════════════════════════════════════════════════════════════════
# PART 8: Unique Check Lookup (Business Rule 8)
# ════════════════════════════════════════════════════════════════════


class TestUniqueCheckLookup:
    """unique field enables upsert semantics."""

    def test_unique_by_name_creates_new(self):
        """First creation with unique=['name'] creates a new check (201)."""
        name = f"Unique {UNIQUE} first"
        resp = api_post("/api/v1/checks/", {"name": name, "unique": ["name"]})
        assert resp.status_code == 201

    def test_unique_by_name_updates_existing(self):
        """Second creation with same name + unique=['name'] returns 200 (upsert)."""
        name = f"Unique {UNIQUE} upsert"
        resp1 = api_post("/api/v1/checks/", {"name": name, "unique": ["name"]})
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        resp2 = api_post("/api/v1/checks/", {"name": name, "tags": "updated", "unique": ["name"]})
        assert resp2.status_code == 200
        id2 = resp2.json()["id"]
        assert id1 == id2
        assert resp2.json()["tags"] == "updated"

    def test_unique_by_name_and_tags(self):
        """unique=['name', 'tags'] requires both to match for upsert."""
        name = f"UniqueNT {UNIQUE}"
        resp1 = api_post("/api/v1/checks/", {"name": name, "tags": "a", "unique": ["name", "tags"]})
        assert resp1.status_code == 201

        # Different tags → new check
        resp2 = api_post("/api/v1/checks/", {"name": name, "tags": "b", "unique": ["name", "tags"]})
        assert resp2.status_code == 201
        assert resp2.json()["id"] != resp1.json()["id"]

    def test_unique_same_fields_returns_same_id(self):
        """With same unique fields, same check ID is returned."""
        name = f"UniqueID {UNIQUE}"
        resp1 = api_post("/api/v1/checks/", {"name": name, "tags": "x", "unique": ["name", "tags"]})
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        resp2 = api_post("/api/v1/checks/", {"name": name, "tags": "x", "unique": ["name", "tags"]})
        assert resp2.status_code == 200
        assert resp2.json()["id"] == id1


# ════════════════════════════════════════════════════════════════════
# PART 9: Tag Filtering (Business Rule 9)
# ════════════════════════════════════════════════════════════════════


class TestTagFiltering:
    """GET /api/v1/checks/?tag=X filters by tag."""

    def test_filter_by_single_tag(self):
        """Filtering by tag returns only matching checks."""
        tag = f"filtertag-{UNIQUE}"
        create_check(name=f"Tagged {UNIQUE}", tags=tag)
        create_check(name=f"Untagged {UNIQUE}", tags="other")

        resp = api_get("/api/v1/checks/", params={"tag": tag})
        assert resp.status_code == 200
        checks = resp.json()["checks"]
        for c in checks:
            assert tag in c["tags"], f"Check {c['name']} missing tag {tag}"

    def test_filter_by_tag_no_results(self):
        """Filtering by non-existent tag returns empty."""
        resp = api_get("/api/v1/checks/", params={"tag": "nonexistent-zzz-999"})
        assert resp.status_code == 200
        assert len(resp.json()["checks"]) == 0

    def test_filter_by_tag_multiple_tags_on_check(self):
        """A check with multiple tags can be found by any one of them."""
        tag_a = f"multi-a-{UNIQUE}"
        tag_b = f"multi-b-{UNIQUE}"
        check = create_check(name=f"MultiTag {UNIQUE}", tags=f"{tag_a} {tag_b}")

        resp = api_get("/api/v1/checks/", params={"tag": tag_a})
        ids_a = [c["id"] for c in resp.json()["checks"]]
        assert check["id"] in ids_a

        resp = api_get("/api/v1/checks/", params={"tag": tag_b})
        ids_b = [c["id"] for c in resp.json()["checks"]]
        assert check["id"] in ids_b


# ════════════════════════════════════════════════════════════════════
# PART 10: Ping History
# ════════════════════════════════════════════════════════════════════


class TestPingHistory:
    """GET /api/v1/checks/{id}/pings/ returns ping log."""

    def test_ping_history_recorded(self):
        """After pinging, ping history shows entries."""
        check = create_check(name=f"PingHist {UNIQUE}")
        ping_check(check["id"])
        ping_check(check["id"], action="fail")
        ping_check(check["id"], action="start")

        resp = api_get(f"/api/v1/checks/{check['id']}/pings/")
        assert resp.status_code == 200
        data = resp.json()
        assert "pings" in data
        pings = data["pings"]
        assert len(pings) >= 3

    def test_ping_history_types(self):
        """Ping history records correct types."""
        check = create_check(name=f"PingTypes {UNIQUE}")
        ping_check(check["id"])
        ping_check(check["id"], action="fail")
        ping_check(check["id"], action="start")
        ping_check(check["id"], action="log")

        resp = api_get(f"/api/v1/checks/{check['id']}/pings/")
        pings = resp.json()["pings"]
        types = [p["type"] for p in pings]
        assert "success" in types
        assert "fail" in types
        assert "start" in types
        assert "log" in types

    def test_ping_history_order(self):
        """Ping history is in reverse chronological order (most recent first)."""
        check = create_check(name=f"PingOrder {UNIQUE}")
        ping_check(check["id"])
        time.sleep(0.1)
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}/pings/")
        pings = resp.json()["pings"]
        if len(pings) >= 2:
            # Most recent should be first (higher n)
            assert pings[0]["n"] > pings[1]["n"]

    def test_ping_history_has_expected_fields(self):
        """Each ping entry has the expected fields."""
        check = create_check(name=f"PingFields {UNIQUE}")
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}/pings/")
        pings = resp.json()["pings"]
        assert len(pings) >= 1
        ping = pings[0]
        assert "type" in ping
        assert "date" in ping
        assert "n" in ping
        assert "scheme" in ping
        assert "remote_addr" in ping
        assert "method" in ping


# ════════════════════════════════════════════════════════════════════
# PART 11: Flips (Business Rule 11)
# ════════════════════════════════════════════════════════════════════


class TestFlips:
    """Status flips are recorded when check status changes."""

    def test_flip_recorded_on_status_change(self):
        """A flip is recorded when status changes from new→up."""
        check = create_check(name=f"FlipRecord {UNIQUE}")
        ping_check(check["id"])  # new → up

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        assert resp.status_code == 200
        data = resp.json()
        assert "flips" in data
        assert len(data["flips"]) >= 1

    def test_flip_down(self):
        """A flip is recorded when status changes from up→down."""
        check = create_check(name=f"FlipDown {UNIQUE}")
        ping_check(check["id"])  # new → up
        ping_check(check["id"], action="fail")  # up → down

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        flips = resp.json()["flips"]
        # Should have flips for up and down
        assert len(flips) >= 2

    def test_flip_has_timestamp(self):
        """Each flip has a timestamp."""
        check = create_check(name=f"FlipTS {UNIQUE}")
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        flips = resp.json()["flips"]
        if len(flips) > 0:
            assert "timestamp" in flips[0]
            assert "up" in flips[0]

    def test_flip_up_field_values(self):
        """Flip 'up' field is 1 for up transitions, 0 for down."""
        check = create_check(name=f"FlipUp {UNIQUE}")
        ping_check(check["id"])  # new → up: up=1
        ping_check(check["id"], action="fail")  # up → down: up=0

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        flips = resp.json()["flips"]
        up_values = [f["up"] for f in flips]
        assert 1 in up_values
        assert 0 in up_values

    def test_no_flip_on_same_status(self):
        """No flip is recorded if status doesn't change (repeated success)."""
        check = create_check(name=f"NoFlip {UNIQUE}")
        ping_check(check["id"])  # new → up: 1 flip

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        count_before = len(resp.json()["flips"])

        ping_check(check["id"])  # up → up: no new flip

        resp = api_get(f"/api/v1/checks/{check['id']}/flips/")
        count_after = len(resp.json()["flips"])
        assert count_after == count_before


# ════════════════════════════════════════════════════════════════════
# PART 12: Badges (Business Rule 10)
# ════════════════════════════════════════════════════════════════════


class TestBadges:
    """Badge endpoints return aggregated status."""

    def test_badge_all_up(self):
        """When all checks are up, badge shows 'up'."""
        tag = f"badge-{UNIQUE}"
        check = create_check(name=f"BadgeUp {UNIQUE}", tags=tag, timeout=86400, grace=3600)
        ping_check(check["id"])

        resp = api_get(f"/api/v1/badges/{tag}")
        assert resp.status_code == 200
        badge = resp.json()
        assert badge["status"] == "up"
        assert badge["total"] >= 1
        assert badge["down"] == 0

    def test_badge_with_down_check(self):
        """When a check is down, badge shows 'down'."""
        tag = f"badgedown-{UNIQUE}"
        check = create_check(name=f"BadgeDown {UNIQUE}", tags=tag)
        ping_check(check["id"], action="fail")

        resp = api_get(f"/api/v1/badges/{tag}")
        assert resp.status_code == 200
        badge = resp.json()
        assert badge["status"] == "down"
        assert badge["down"] >= 1

    def test_badge_star_all_checks(self):
        """Badge with '*' covers all checks in the project."""
        resp = api_get("/api/v1/badges/*")
        assert resp.status_code == 200
        badge = resp.json()
        assert "status" in badge
        assert "total" in badge

    def test_list_badges(self):
        """GET /api/v1/badges/ returns badge info per tag."""
        tag = f"listbadge-{UNIQUE}"
        check = create_check(name=f"ListBadge {UNIQUE}", tags=tag)
        ping_check(check["id"])

        resp = api_get("/api/v1/badges/")
        assert resp.status_code == 200
        data = resp.json()
        assert "badges" in data
        # Should include "*" and the tag
        assert "*" in data["badges"]

    def test_badge_mixed_status(self):
        """Badge reports correctly when checks have mixed statuses."""
        tag = f"mixbadge-{UNIQUE}"
        check_up = create_check(name=f"MixUp {UNIQUE}", tags=tag, timeout=86400, grace=3600)
        check_down = create_check(name=f"MixDown {UNIQUE}", tags=tag)

        ping_check(check_up["id"])
        ping_check(check_down["id"], action="fail")

        resp = api_get(f"/api/v1/badges/{tag}")
        badge = resp.json()
        assert badge["status"] == "down"  # Any down → badge is down
        assert badge["total"] >= 2
        assert badge["down"] >= 1


# ════════════════════════════════════════════════════════════════════
# PART 13: Project Info
# ════════════════════════════════════════════════════════════════════


class TestProjectInfo:
    """GET /api/v1/project/ returns project-level info."""

    def test_project_info(self):
        """Returns project with check_count and channel_count."""
        resp = api_get("/api/v1/project/")
        assert resp.status_code == 200
        data = resp.json()
        assert "check_count" in data
        assert "channel_count" in data
        assert isinstance(data["check_count"], int)
        assert isinstance(data["channel_count"], int)

    def test_project_info_includes_api_key(self):
        """Project info includes the api_key used."""
        resp = api_get("/api/v1/project/")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data
        assert data["api_key"] == API_KEY_1

    def test_project_check_count_increases(self):
        """check_count reflects actual number of checks."""
        resp1 = api_get("/api/v1/project/")
        count_before = resp1.json()["check_count"]

        create_check(name=f"ProjCount {UNIQUE}")

        resp2 = api_get("/api/v1/project/")
        count_after = resp2.json()["check_count"]
        assert count_after == count_before + 1


# ════════════════════════════════════════════════════════════════════
# PART 14: Authentication & Isolation
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:
    """Missing API key returns 401."""

    def test_missing_api_key_checks(self):
        """Request without X-Api-Key header returns 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/checks/", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_channels(self):
        """Channels endpoint without key returns 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/channels/", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_project(self):
        """Project endpoint without key returns 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/project/", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_integrations(self):
        """Integrations endpoint without key returns 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/integrations/", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_badges(self):
        """Badges endpoint without key returns 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/badges/", timeout=30)
        assert resp.status_code == 401

    def test_ping_does_not_need_api_key(self):
        """Ping endpoints don't require API key (they use check UUID)."""
        check = create_check(name=f"NoPingAuth {UNIQUE}")
        # Ping without any headers
        resp = requests.post(f"{BASE_URL}/ping/{check['id']}", timeout=30)
        assert resp.status_code == 200


class TestProjectIsolation:
    """Data created by project A is invisible to project B."""

    def test_check_isolation(self):
        """Checks from project A are not visible to project B."""
        name = f"IsoCheck-{UNIQUE}"
        create_check(name=name)

        # Project B should not see it
        resp = api_get("/api/v1/checks/", headers=HEADERS_PROJECT2)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["checks"]]
        assert name not in names

    def test_channel_isolation(self):
        """Channels from project A are not visible to project B."""
        ch = create_channel(kind="email", name=f"IsoCh-{UNIQUE}", email=f"iso-{UNIQUE}@test.com")

        resp = api_get("/api/v1/channels/", headers=HEADERS_PROJECT2)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()["channels"]]
        assert ch["id"] not in ids

    def test_cannot_access_other_projects_check(self):
        """Getting a check from another project returns 403."""
        check = create_check(name=f"OtherProj {UNIQUE}")

        resp = api_get(f"/api/v1/checks/{check['id']}", headers=HEADERS_PROJECT2)
        assert resp.status_code == 403

    def test_integration_isolation(self):
        """Integrations from project A are not visible to project B."""
        resp = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"IsoInt-{UNIQUE}",
            "webhook_url": "https://iso.example.com",
        })
        assert resp.status_code == 201
        int_id = resp.json()["id"]

        resp = api_get("/api/v1/integrations/", headers=HEADERS_PROJECT2)
        assert resp.status_code == 200
        ids = [i["id"] for i in resp.json()["integrations"]]
        assert int_id not in ids


# ════════════════════════════════════════════════════════════════════
# PART 15: 404 Handling
# ════════════════════════════════════════════════════════════════════


class TestNotFound:
    """Non-existent resources return 404."""

    def test_check_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/checks/{fake_id}")
        assert resp.status_code == 404

    def test_channel_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/channels/{fake_id}")
        assert resp.status_code == 404

    def test_integration_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/integrations/{fake_id}")
        assert resp.status_code == 404

    def test_pings_for_nonexistent_check(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/checks/{fake_id}/pings/")
        assert resp.status_code == 404

    def test_flips_for_nonexistent_check(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/checks/{fake_id}/flips/")
        assert resp.status_code == 404

    def test_delete_nonexistent_check(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/checks/{fake_id}")
        assert resp.status_code == 404

    def test_update_nonexistent_check(self):
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/api/v1/checks/{fake_id}", {"name": "nope"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 16: Validation (Business Rule 14)
# ════════════════════════════════════════════════════════════════════


class TestValidation:
    """Input validation returns 400."""

    def test_invalid_timeout_too_small(self):
        """Timeout below 60 seconds is rejected."""
        resp = api_post("/api/v1/checks/", {"timeout": 10})
        assert resp.status_code == 400

    def test_invalid_timeout_too_large(self):
        """Timeout above 31536000 is rejected."""
        resp = api_post("/api/v1/checks/", {"timeout": 99999999})
        assert resp.status_code == 400

    def test_invalid_grace_too_small(self):
        """Grace below 60 seconds is rejected."""
        resp = api_post("/api/v1/checks/", {"grace": 10})
        assert resp.status_code == 400

    def test_invalid_grace_too_large(self):
        """Grace above 31536000 is rejected."""
        resp = api_post("/api/v1/checks/", {"grace": 50000000})
        assert resp.status_code == 400

    def test_invalid_cron_expression(self):
        """Invalid cron expression is rejected."""
        resp = api_post("/api/v1/checks/", {"schedule": "not a cron"})
        assert resp.status_code == 400

    def test_channel_create_missing_kind(self):
        """Creating a channel without 'kind' is rejected."""
        resp = api_post("/api/v1/channels/", {"name": "No Kind"})
        assert resp.status_code == 400

    def test_channel_create_invalid_kind(self):
        """Creating a channel with invalid kind is rejected."""
        resp = api_post("/api/v1/channels/", {"kind": "invalid_kind"})
        assert resp.status_code == 400

    def test_valid_timeout_boundary_60(self):
        """Timeout of exactly 60 is accepted."""
        resp = api_post("/api/v1/checks/", {"timeout": 60, "grace": 60})
        assert resp.status_code == 201

    def test_valid_timeout_boundary_max(self):
        """Timeout of exactly 31536000 is accepted."""
        resp = api_post("/api/v1/checks/", {"timeout": 31536000, "grace": 60})
        assert resp.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 17: Duration Calculation (Business Rule 13)
# ════════════════════════════════════════════════════════════════════


class TestDuration:
    """Duration is computed when start is followed by success/fail."""

    def test_duration_after_start_then_success(self):
        """start → success: last_duration is computed."""
        check = create_check(name=f"Duration {UNIQUE}")
        ping_check(check["id"], action="start")
        time.sleep(0.2)
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}")
        data = resp.json()
        assert data["last_duration"] is not None
        assert data["last_duration"] >= 0.1  # at least ~0.2s

    def test_no_duration_without_start(self):
        """Without a preceding start, no duration is set."""
        check = create_check(name=f"NoDuration {UNIQUE}")
        ping_check(check["id"])

        resp = api_get(f"/api/v1/checks/{check['id']}")
        assert resp.json()["last_duration"] is None
