"""
BackendForge — L2 Integration Tests for Solidtime
Adversarial tests targeting common LLM implementation mistakes.

Each test: 3-5 steps, 8-12 assertions, covering 1-2 bug patterns.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# Each test class gets its own user/org to avoid interference
UNIQUE = uuid.uuid4().hex[:8]


def fresh_headers():
    """Create a fresh user+org pair for isolation."""
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# L2-01: Time entry duration is COMPUTED from start/end
# Patterns: 1 (field names), 5 (business logic truly computes)
# ════════════════════════════════════════════════════════════════════


class TestTimeEntryDurationComputed:

    def test_duration_computed_from_start_end(self):
        """Duration must be computed as (end - start) in seconds, not echoed from request."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        start = datetime(2024, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 10, 10, 30, 0, tzinfo=timezone.utc)  # 2.5 hours = 9000s
        r = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        te = r.json()

        # Verify field names are snake_case as per spec
        assert "duration" in te, "Response must have 'duration' field"
        assert "start" in te, "Response must have 'start' field"
        assert "end" in te, "Response must have 'end' field"
        assert "user_id" in te, "Response must have 'user_id' field"
        assert "organization_id" in te, "Response must have 'organization_id' field"
        assert "billable" in te, "Response must have 'billable' field"
        assert "billable_amount" in te, "Response must have 'billable_amount' field"

        # Duration MUST be computed, not just 0 or None
        assert te["duration"] == 9000, f"Expected 9000 seconds, got {te['duration']}"
        assert isinstance(te["duration"], int), "Duration must be an integer"

    def test_duration_changes_when_end_updated(self):
        """Updating end time must recompute duration."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        start = datetime(2024, 3, 11, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 11, 10, 0, 0, tzinfo=timezone.utc)  # 1 hour
        r = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        te_id = r.json()["id"]
        assert r.json()["duration"] == 3600

        # Update end to 2 hours later
        new_end = datetime(2024, 3, 11, 11, 0, 0, tzinfo=timezone.utc)
        r2 = api_put(f"/api/v1/time-entries/{te_id}", {
            "end": new_end.isoformat(),
        }, headers=h)
        assert r2.status_code == 200
        assert r2.json()["duration"] == 7200, "Duration must be recomputed on update"

        # GET should also reflect new duration
        r3 = api_get(f"/api/v1/time-entries/{te_id}", headers=h)
        assert r3.status_code == 200
        assert r3.json()["duration"] == 7200

    def test_duration_various_lengths(self):
        """Test duration computation for various time spans."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # 15 minutes = 900 seconds
        r = api_post("/api/v1/time-entries", {
            "start": "2024-03-12T09:00:00Z",
            "end": "2024-03-12T09:15:00Z",
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        assert r.json()["duration"] == 900

        # 8 hours = 28800 seconds
        r = api_post("/api/v1/time-entries", {
            "start": "2024-03-12T09:00:00Z",
            "end": "2024-03-12T17:00:00Z",
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        assert r.json()["duration"] == 28800

        # 1 second
        r = api_post("/api/v1/time-entries", {
            "start": "2024-03-12T09:00:00Z",
            "end": "2024-03-12T09:00:01Z",
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        assert r.json()["duration"] == 1


# ════════════════════════════════════════════════════════════════════
# L2-02: Billable rate hierarchy (member → org → 0)
# Patterns: 5 (business logic), 1 (field names)
# ════════════════════════════════════════════════════════════════════


class TestBillableRateHierarchy:

    def test_member_rate_takes_precedence_over_org_rate(self):
        """When both member and org rates set, member rate wins."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Set org rate to 5000 cents/hour
        api_put("/api/v1/organizations/current", {"billable_rate": 5000}, headers=h)

        # Set member rate to 10000 cents/hour
        members = api_get("/api/v1/members", headers=h).json()
        member = members[0]
        api_put(f"/api/v1/members/{member['id']}", {"billable_rate": 10000}, headers=h)

        # Create 1-hour billable entry
        r = api_post("/api/v1/time-entries", {
            "start": "2024-04-01T09:00:00Z",
            "end": "2024-04-01T10:00:00Z",
            "billable": True,
        }, headers=h)
        assert r.status_code == 201
        te = r.json()
        # Should use member rate: 1h * 10000 = 10000
        assert te["billable_amount"] == pytest.approx(10000.0, abs=1)
        assert te["duration"] == 3600

    def test_org_rate_used_when_member_rate_null(self):
        """When member rate is null, org rate is used."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Set org rate
        api_put("/api/v1/organizations/current", {"billable_rate": 8000}, headers=h)

        # Ensure member rate is null
        members = api_get("/api/v1/members", headers=h).json()
        member = members[0]
        api_put(f"/api/v1/members/{member['id']}", {"billable_rate": None}, headers=h)

        # Create 2-hour billable entry
        r = api_post("/api/v1/time-entries", {
            "start": "2024-04-02T09:00:00Z",
            "end": "2024-04-02T11:00:00Z",
            "billable": True,
        }, headers=h)
        assert r.status_code == 201
        te = r.json()
        # Should use org rate: 2h * 8000 = 16000
        assert te["billable_amount"] == pytest.approx(16000.0, abs=1)

    def test_zero_amount_when_both_rates_null(self):
        """When both rates null, billable_amount should be 0."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Ensure org rate null
        api_put("/api/v1/organizations/current", {"billable_rate": None}, headers=h)

        # Ensure member rate null
        members = api_get("/api/v1/members", headers=h).json()
        member = members[0]
        api_put(f"/api/v1/members/{member['id']}", {"billable_rate": None}, headers=h)

        # Create billable entry
        r = api_post("/api/v1/time-entries", {
            "start": "2024-04-03T09:00:00Z",
            "end": "2024-04-03T10:00:00Z",
            "billable": True,
        }, headers=h)
        assert r.status_code == 201
        te = r.json()
        assert te["billable_amount"] == 0.0 or te["billable_amount"] == 0

    def test_non_billable_always_zero(self):
        """Non-billable entries always have 0 billable_amount regardless of rates."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Set high rates
        api_put("/api/v1/organizations/current", {"billable_rate": 99999}, headers=h)
        members = api_get("/api/v1/members", headers=h).json()
        api_put(f"/api/v1/members/{members[0]['id']}", {"billable_rate": 99999}, headers=h)

        # Non-billable entry
        r = api_post("/api/v1/time-entries", {
            "start": "2024-04-04T09:00:00Z",
            "end": "2024-04-04T10:00:00Z",
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        assert r.json()["billable_amount"] == 0


# ════════════════════════════════════════════════════════════════════
# L2-03: Timer auto-stop behavior
# Patterns: 5 (business logic), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestTimerAutoStop:

    def test_start_timer_auto_stops_previous(self):
        """Starting a new timer must stop the previous one, setting end = new start."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Start first timer
        r1 = api_post("/api/v1/time-entries/start", {
            "start": "2024-05-01T09:00:00Z",
            "billable": False,
            "description": "Timer 1",
        }, headers=h)
        assert r1.status_code == 201
        t1_id = r1.json()["id"]
        assert r1.json()["end"] is None

        # Start second timer
        r2 = api_post("/api/v1/time-entries/start", {
            "start": "2024-05-01T10:30:00Z",
            "billable": False,
            "description": "Timer 2",
        }, headers=h)
        assert r2.status_code == 201
        t2_id = r2.json()["id"]
        assert r2.json()["end"] is None

        # Verify first timer is stopped with correct end time
        r_check = api_get(f"/api/v1/time-entries/{t1_id}", headers=h)
        assert r_check.status_code == 200
        t1 = r_check.json()
        assert t1["end"] is not None, "First timer must be auto-stopped"
        assert t1["duration"] == 5400, "Duration must be 1.5 hours (5400s)"

    def test_timer_running_has_positive_duration(self):
        """A running timer (end=null) must have duration > 0 computed from now."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Start timer 1 hour in the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = api_post("/api/v1/time-entries/start", {
            "start": past,
            "billable": False,
        }, headers=h)
        assert r.status_code == 201
        te = r.json()
        assert te["end"] is None
        # Duration should be approximately 3600 seconds (allow 60s tolerance)
        assert te["duration"] >= 3500, f"Running timer duration too low: {te['duration']}"
        assert te["duration"] <= 3700, f"Running timer duration too high: {te['duration']}"


# ════════════════════════════════════════════════════════════════════
# L2-04: Tag association on time entries (nested data)
# Patterns: 2 (nested data returned), 1 (field names)
# ════════════════════════════════════════════════════════════════════


class TestTagAssociation:

    def test_time_entry_with_tags_roundtrip(self):
        """Create time entry with tags → GET returns full tag objects."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Create tags
        t1 = api_post("/api/v1/tags", {"name": f"urgent-{UNIQUE}"}, headers=h)
        t2 = api_post("/api/v1/tags", {"name": f"meeting-{UNIQUE}"}, headers=h)
        assert t1.status_code == 201
        assert t2.status_code == 201
        tag1_id = t1.json()["id"]
        tag2_id = t2.json()["id"]

        # Create time entry with tags
        r = api_post("/api/v1/time-entries", {
            "start": "2024-06-01T09:00:00Z",
            "end": "2024-06-01T10:00:00Z",
            "billable": False,
            "tag_ids": [tag1_id, tag2_id],
        }, headers=h)
        assert r.status_code == 201
        te = r.json()
        assert "tags" in te, "Response must include 'tags' field"
        assert isinstance(te["tags"], list), "'tags' must be a list"
        assert len(te["tags"]) == 2, "Must have 2 tags"

        # Verify tag objects have correct fields
        tag_ids_returned = {t["id"] for t in te["tags"]}
        assert tag1_id in tag_ids_returned
        assert tag2_id in tag_ids_returned
        for tag in te["tags"]:
            assert "id" in tag
            assert "name" in tag
            assert "organization_id" in tag

        # GET should also return tags
        r2 = api_get(f"/api/v1/time-entries/{te['id']}", headers=h)
        assert r2.status_code == 200
        assert len(r2.json()["tags"]) == 2

    def test_update_time_entry_tags(self):
        """Updating tag_ids replaces all tags on the entry."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        t1 = api_post("/api/v1/tags", {"name": f"tag-a-{UNIQUE}"}, headers=h).json()
        t2 = api_post("/api/v1/tags", {"name": f"tag-b-{UNIQUE}"}, headers=h).json()
        t3 = api_post("/api/v1/tags", {"name": f"tag-c-{UNIQUE}"}, headers=h).json()

        # Create with tag1 and tag2
        r = api_post("/api/v1/time-entries", {
            "start": "2024-06-02T09:00:00Z",
            "end": "2024-06-02T10:00:00Z",
            "billable": False,
            "tag_ids": [t1["id"], t2["id"]],
        }, headers=h)
        te_id = r.json()["id"]

        # Update to tag2 and tag3 only
        r2 = api_put(f"/api/v1/time-entries/{te_id}", {
            "tag_ids": [t2["id"], t3["id"]],
        }, headers=h)
        assert r2.status_code == 200
        tag_ids = {t["id"] for t in r2.json()["tags"]}
        assert t1["id"] not in tag_ids, "tag-a should be removed"
        assert t2["id"] in tag_ids, "tag-b should remain"
        assert t3["id"] in tag_ids, "tag-c should be added"


# ════════════════════════════════════════════════════════════════════
# L2-05: Project/Client filter parameters actually work
# Patterns: 3 (filter params implemented), 4 (status codes)
# ════════════════════════════════════════════════════════════════════


class TestFilterParameters:

    def test_time_entries_filter_by_project_id(self):
        """project_id filter must actually filter, not return all."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p1 = api_post("/api/v1/projects", {
            "name": f"filter-p1-{UNIQUE}", "color": "#111111", "is_billable": True
        }, headers=h).json()
        p2 = api_post("/api/v1/projects", {
            "name": f"filter-p2-{UNIQUE}", "color": "#222222", "is_billable": True
        }, headers=h).json()

        # Create entries for each project
        api_post("/api/v1/time-entries", {
            "start": "2024-07-01T09:00:00Z", "end": "2024-07-01T10:00:00Z",
            "project_id": p1["id"], "billable": False,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-07-01T11:00:00Z", "end": "2024-07-01T12:00:00Z",
            "project_id": p2["id"], "billable": False,
        }, headers=h)

        # Filter by p1
        r = api_get("/api/v1/time-entries", params={"project_id": p1["id"]}, headers=h)
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) >= 1
        for e in entries:
            assert e["project_id"] == p1["id"], "Filter must exclude other projects"

    def test_time_entries_filter_by_billable(self):
        """billable filter must actually work."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        api_post("/api/v1/time-entries", {
            "start": "2024-07-02T09:00:00Z", "end": "2024-07-02T10:00:00Z",
            "billable": True,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-07-02T11:00:00Z", "end": "2024-07-02T12:00:00Z",
            "billable": False,
        }, headers=h)

        r = api_get("/api/v1/time-entries", params={"billable": "true"}, headers=h)
        assert r.status_code == 200
        for e in r.json():
            assert e["billable"] is True

        r = api_get("/api/v1/time-entries", params={"billable": "false"}, headers=h)
        assert r.status_code == 200
        for e in r.json():
            assert e["billable"] is False

    def test_tasks_filter_by_project_id(self):
        """Tasks must filter by project_id."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p1 = api_post("/api/v1/projects", {
            "name": f"task-filter-p1-{UNIQUE}", "color": "#333333", "is_billable": True
        }, headers=h).json()
        p2 = api_post("/api/v1/projects", {
            "name": f"task-filter-p2-{UNIQUE}", "color": "#444444", "is_billable": True
        }, headers=h).json()

        api_post("/api/v1/tasks", {"name": f"task-a-{UNIQUE}", "project_id": p1["id"]}, headers=h)
        api_post("/api/v1/tasks", {"name": f"task-b-{UNIQUE}", "project_id": p2["id"]}, headers=h)

        r = api_get("/api/v1/tasks", params={"project_id": p1["id"]}, headers=h)
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) >= 1
        for t in tasks:
            assert t["project_id"] == p1["id"]

    def test_tasks_filter_by_done(self):
        """Tasks must filter by done status."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p = api_post("/api/v1/projects", {
            "name": f"done-filter-p-{UNIQUE}", "color": "#555555", "is_billable": True
        }, headers=h).json()

        t1 = api_post("/api/v1/tasks", {"name": f"done-t1-{UNIQUE}", "project_id": p["id"]}, headers=h).json()
        api_post("/api/v1/tasks", {"name": f"done-t2-{UNIQUE}", "project_id": p["id"]}, headers=h)
        api_put(f"/api/v1/tasks/{t1['id']}", {"done": True}, headers=h)

        r = api_get("/api/v1/tasks", params={"done": "true"}, headers=h)
        assert r.status_code == 200
        for t in r.json():
            assert t["done"] is True

        r = api_get("/api/v1/tasks", params={"done": "false"}, headers=h)
        assert r.status_code == 200
        for t in r.json():
            assert t["done"] is False


# ════════════════════════════════════════════════════════════════════
# L2-06: Status code correctness
# Patterns: 4 (correct status codes)
# ════════════════════════════════════════════════════════════════════


class TestStatusCodes:

    def test_create_returns_201(self):
        """POST creating a resource must return 201, not 200."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Client
        r = api_post("/api/v1/clients", {"name": f"sc-client-{UNIQUE}"}, headers=h)
        assert r.status_code == 201, f"Client create returned {r.status_code}, expected 201"

        # Project
        r = api_post("/api/v1/projects", {
            "name": f"sc-proj-{UNIQUE}", "color": "#AABBCC", "is_billable": True
        }, headers=h)
        assert r.status_code == 201, f"Project create returned {r.status_code}, expected 201"

        # Tag
        r = api_post("/api/v1/tags", {"name": f"sc-tag-{UNIQUE}"}, headers=h)
        assert r.status_code == 201, f"Tag create returned {r.status_code}, expected 201"

        # Time entry
        r = api_post("/api/v1/time-entries", {
            "start": "2024-08-01T09:00:00Z", "end": "2024-08-01T10:00:00Z", "billable": False
        }, headers=h)
        assert r.status_code == 201, f"Time entry create returned {r.status_code}, expected 201"

        # Timer start
        r = api_post("/api/v1/time-entries/start", {
            "start": "2024-08-01T11:00:00Z", "billable": False
        }, headers=h)
        assert r.status_code == 201, f"Timer start returned {r.status_code}, expected 201"

    def test_delete_returns_204(self):
        """DELETE must return 204, not 200."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Client
        c = api_post("/api/v1/clients", {"name": f"del-c-{UNIQUE}"}, headers=h).json()
        r = api_delete(f"/api/v1/clients/{c['id']}", headers=h)
        assert r.status_code == 204, f"Client delete returned {r.status_code}, expected 204"

        # Tag
        t = api_post("/api/v1/tags", {"name": f"del-t-{UNIQUE}"}, headers=h).json()
        r = api_delete(f"/api/v1/tags/{t['id']}", headers=h)
        assert r.status_code == 204, f"Tag delete returned {r.status_code}, expected 204"

        # Project
        p = api_post("/api/v1/projects", {
            "name": f"del-p-{UNIQUE}", "color": "#DDEEFF", "is_billable": True
        }, headers=h).json()
        r = api_delete(f"/api/v1/projects/{p['id']}", headers=h)
        assert r.status_code == 204, f"Project delete returned {r.status_code}, expected 204"

    def test_not_found_returns_404(self):
        """Accessing nonexistent resources must return 404, not 200 empty."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)
        fake_id = str(uuid.uuid4())

        r = api_get(f"/api/v1/projects/{fake_id}", headers=h)
        assert r.status_code == 404

        r = api_get(f"/api/v1/time-entries/{fake_id}", headers=h)
        assert r.status_code == 404

        r = api_put(f"/api/v1/tasks/{fake_id}", {"name": "x"}, headers=h)
        assert r.status_code == 404

        r = api_delete(f"/api/v1/tags/{fake_id}", headers=h)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L2-07: Unique constraint enforcement
# Patterns: 8 (unique constraints)
# ════════════════════════════════════════════════════════════════════


class TestUniqueConstraints:

    def test_duplicate_tag_name_returns_409(self):
        """Creating a tag with a duplicate name returns 409."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        name = f"dup-tag-{UNIQUE}"
        r1 = api_post("/api/v1/tags", {"name": name}, headers=h)
        assert r1.status_code == 201

        r2 = api_post("/api/v1/tags", {"name": name}, headers=h)
        assert r2.status_code == 409, f"Duplicate tag returned {r2.status_code}, expected 409"

    def test_duplicate_project_name_returns_409(self):
        """Creating a project with a duplicate name returns 409."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        name = f"dup-proj-{UNIQUE}"
        r1 = api_post("/api/v1/projects", {"name": name, "color": "#AAAAAA", "is_billable": True}, headers=h)
        assert r1.status_code == 201

        r2 = api_post("/api/v1/projects", {"name": name, "color": "#BBBBBB", "is_billable": False}, headers=h)
        assert r2.status_code == 409

    def test_duplicate_client_name_returns_409(self):
        """Creating a client with a duplicate name returns 409."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        name = f"dup-client-{UNIQUE}"
        r1 = api_post("/api/v1/clients", {"name": name}, headers=h)
        assert r1.status_code == 201

        r2 = api_post("/api/v1/clients", {"name": name}, headers=h)
        assert r2.status_code == 409

    def test_duplicate_member_returns_409(self):
        """Adding same user to org twice returns 409."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        user = str(uuid.uuid4())
        r1 = api_post("/api/v1/members", {"user_id": user, "role": "member"}, headers=h)
        assert r1.status_code == 201

        r2 = api_post("/api/v1/members", {"user_id": user, "role": "admin"}, headers=h)
        assert r2.status_code == 409

    def test_same_name_different_orgs_allowed(self):
        """Same name in different orgs should not conflict."""
        h1 = fresh_headers()
        h2 = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h1)
        api_get("/api/v1/organizations/current", headers=h2)

        name = f"shared-name-{UNIQUE}"
        r1 = api_post("/api/v1/tags", {"name": name}, headers=h1)
        assert r1.status_code == 201
        r2 = api_post("/api/v1/tags", {"name": name}, headers=h2)
        assert r2.status_code == 201, "Same name in different orgs must be allowed"


# ════════════════════════════════════════════════════════════════════
# L2-08: Report aggregation correctness
# Patterns: 5 (business logic computes correctly)
# ════════════════════════════════════════════════════════════════════


class TestReportAggregation:

    def test_report_time_sums_correctly(self):
        """Total report must sum durations accurately across entries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)
        api_put("/api/v1/organizations/current", {"billable_rate": 6000}, headers=h)

        # 2 hours billable
        api_post("/api/v1/time-entries", {
            "start": "2024-10-01T09:00:00Z", "end": "2024-10-01T11:00:00Z", "billable": True,
        }, headers=h)
        # 1 hour non-billable
        api_post("/api/v1/time-entries", {
            "start": "2024-10-01T13:00:00Z", "end": "2024-10-01T14:00:00Z", "billable": False,
        }, headers=h)
        # 30 min billable
        api_post("/api/v1/time-entries", {
            "start": "2024-10-01T15:00:00Z", "end": "2024-10-01T15:30:00Z", "billable": True,
        }, headers=h)

        r = api_get("/api/v1/reports/time", params={
            "start": "2024-10-01T00:00:00Z", "end": "2024-10-02T00:00:00Z",
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()

        assert rpt["total_seconds"] == 12600, f"Expected 12600, got {rpt['total_seconds']}"
        assert rpt["total_billable_seconds"] == 9000
        assert rpt["entry_count"] == 3
        # Billable amount: 2.5h * 6000 = 15000
        assert rpt["total_billable_amount"] == pytest.approx(15000.0, abs=1)

    def test_report_projects_groups_correctly(self):
        """Project report must group by project, not just total."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p1 = api_post("/api/v1/projects", {
            "name": f"rpt-p1-{UNIQUE}", "color": "#AA0000", "is_billable": True
        }, headers=h).json()
        p2 = api_post("/api/v1/projects", {
            "name": f"rpt-p2-{UNIQUE}", "color": "#00BB00", "is_billable": True
        }, headers=h).json()

        # P1: 3 hours
        api_post("/api/v1/time-entries", {
            "start": "2024-10-02T09:00:00Z", "end": "2024-10-02T12:00:00Z",
            "project_id": p1["id"], "billable": False,
        }, headers=h)
        # P2: 1 hour
        api_post("/api/v1/time-entries", {
            "start": "2024-10-02T13:00:00Z", "end": "2024-10-02T14:00:00Z",
            "project_id": p2["id"], "billable": False,
        }, headers=h)

        r = api_get("/api/v1/reports/projects", params={
            "start": "2024-10-02T00:00:00Z", "end": "2024-10-03T00:00:00Z",
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()
        assert isinstance(rpt, list)

        p1_report = [x for x in rpt if x["project_id"] == p1["id"]]
        p2_report = [x for x in rpt if x["project_id"] == p2["id"]]
        assert len(p1_report) == 1
        assert len(p2_report) == 1
        assert p1_report[0]["total_seconds"] == 10800  # 3h
        assert p2_report[0]["total_seconds"] == 3600   # 1h
        assert p1_report[0]["entry_count"] == 1
        assert p2_report[0]["entry_count"] == 1

    def test_report_daily_groups_by_date(self):
        """Daily report must group by date correctly."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Day 1: 2 entries
        api_post("/api/v1/time-entries", {
            "start": "2024-10-10T09:00:00Z", "end": "2024-10-10T10:00:00Z", "billable": False,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-10-10T14:00:00Z", "end": "2024-10-10T15:30:00Z", "billable": False,
        }, headers=h)
        # Day 2: 1 entry
        api_post("/api/v1/time-entries", {
            "start": "2024-10-11T08:00:00Z", "end": "2024-10-11T12:00:00Z", "billable": False,
        }, headers=h)

        r = api_get("/api/v1/reports/daily", params={
            "start": "2024-10-10T00:00:00Z", "end": "2024-10-12T00:00:00Z",
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()

        day1 = [x for x in rpt if x["date"] == "2024-10-10"]
        day2 = [x for x in rpt if x["date"] == "2024-10-11"]
        assert len(day1) == 1
        assert len(day2) == 1
        # Day 1: 1h + 1.5h = 9000s
        assert day1[0]["total_seconds"] == 9000
        assert day1[0]["entry_count"] == 2
        # Day 2: 4h = 14400s
        assert day2[0]["total_seconds"] == 14400
        assert day2[0]["entry_count"] == 1


# ════════════════════════════════════════════════════════════════════
# L2-09: Cascade delete effects
# Patterns: 7 (cascade/side effects)
# ════════════════════════════════════════════════════════════════════


class TestCascadeEffects:

    def test_delete_project_nullifies_time_entry_project_id(self):
        """Deleting project sets project_id=null on its time entries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p = api_post("/api/v1/projects", {
            "name": f"cascade-p-{UNIQUE}", "color": "#FF0000", "is_billable": True
        }, headers=h).json()

        te = api_post("/api/v1/time-entries", {
            "start": "2024-11-01T09:00:00Z", "end": "2024-11-01T10:00:00Z",
            "project_id": p["id"], "billable": False,
        }, headers=h).json()

        # Delete project
        r = api_delete(f"/api/v1/projects/{p['id']}", headers=h)
        assert r.status_code == 204

        # Time entry still exists with null project_id
        r2 = api_get(f"/api/v1/time-entries/{te['id']}", headers=h)
        assert r2.status_code == 200
        assert r2.json()["project_id"] is None

    def test_delete_project_removes_its_tasks(self):
        """Deleting a project removes all its tasks."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p = api_post("/api/v1/projects", {
            "name": f"cascade-task-p-{UNIQUE}", "color": "#00FF00", "is_billable": True
        }, headers=h).json()

        t1 = api_post("/api/v1/tasks", {"name": f"ct1-{UNIQUE}", "project_id": p["id"]}, headers=h).json()
        t2 = api_post("/api/v1/tasks", {"name": f"ct2-{UNIQUE}", "project_id": p["id"]}, headers=h).json()

        api_delete(f"/api/v1/projects/{p['id']}", headers=h)

        # Tasks should be gone
        all_tasks = api_get("/api/v1/tasks", headers=h).json()
        task_ids = [t["id"] for t in all_tasks]
        assert t1["id"] not in task_ids
        assert t2["id"] not in task_ids

    def test_delete_client_nullifies_project_client_id(self):
        """Deleting client sets client_id=null on its projects."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        c = api_post("/api/v1/clients", {"name": f"cascade-c-{UNIQUE}"}, headers=h).json()
        p = api_post("/api/v1/projects", {
            "name": f"cascade-cp-{UNIQUE}", "color": "#0000FF", "is_billable": True,
            "client_id": c["id"],
        }, headers=h).json()

        api_delete(f"/api/v1/clients/{c['id']}", headers=h)

        r = api_get(f"/api/v1/projects/{p['id']}", headers=h)
        assert r.status_code == 200
        assert r.json()["client_id"] is None

    def test_delete_tag_removes_from_time_entries(self):
        """Deleting a tag removes it from associated time entries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        tag = api_post("/api/v1/tags", {"name": f"cascade-tag-{UNIQUE}"}, headers=h).json()

        te = api_post("/api/v1/time-entries", {
            "start": "2024-11-02T09:00:00Z", "end": "2024-11-02T10:00:00Z",
            "billable": False, "tag_ids": [tag["id"]],
        }, headers=h).json()
        assert len(te["tags"]) == 1

        api_delete(f"/api/v1/tags/{tag['id']}", headers=h)

        r = api_get(f"/api/v1/time-entries/{te['id']}", headers=h)
        assert r.status_code == 200
        assert len(r.json()["tags"]) == 0


# ════════════════════════════════════════════════════════════════════
# L2-10: Task spent_seconds computation
# Patterns: 5 (business logic), 2 (computed fields in response)
# ════════════════════════════════════════════════════════════════════


class TestTaskSpentSeconds:

    def test_spent_seconds_sums_time_entries(self):
        """Task's spent_seconds = sum of durations of all time entries for that task."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p = api_post("/api/v1/projects", {
            "name": f"spent-p-{UNIQUE}", "color": "#ABCDEF", "is_billable": True
        }, headers=h).json()
        task = api_post("/api/v1/tasks", {
            "name": f"spent-task-{UNIQUE}", "project_id": p["id"], "estimated_seconds": 7200
        }, headers=h).json()

        # Add two time entries: 1h + 30min = 5400s
        api_post("/api/v1/time-entries", {
            "start": "2024-12-01T09:00:00Z", "end": "2024-12-01T10:00:00Z",
            "task_id": task["id"], "project_id": p["id"], "billable": False,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-12-01T14:00:00Z", "end": "2024-12-01T14:30:00Z",
            "task_id": task["id"], "project_id": p["id"], "billable": False,
        }, headers=h)

        # Check task
        tasks = api_get("/api/v1/tasks", params={"project_id": p["id"]}, headers=h).json()
        my_task = [t for t in tasks if t["id"] == task["id"]][0]
        assert "spent_seconds" in my_task, "Task response must include 'spent_seconds'"
        assert my_task["spent_seconds"] == 5400, f"Expected 5400, got {my_task['spent_seconds']}"
        assert my_task["estimated_seconds"] == 7200


# ════════════════════════════════════════════════════════════════════
# L2-11: Archived entity constraints
# Patterns: 5 (business rules enforced), 8 (ordering/state)
# ════════════════════════════════════════════════════════════════════


class TestArchivedConstraints:

    def test_cannot_create_time_entry_for_archived_project(self):
        """Time entries for archived projects must be rejected with 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p = api_post("/api/v1/projects", {
            "name": f"arch-te-p-{UNIQUE}", "color": "#123456", "is_billable": True
        }, headers=h).json()
        api_put(f"/api/v1/projects/{p['id']}", {"archived": True}, headers=h)

        r = api_post("/api/v1/time-entries", {
            "start": "2024-12-10T09:00:00Z", "end": "2024-12-10T10:00:00Z",
            "project_id": p["id"], "billable": False,
        }, headers=h)
        assert r.status_code == 422

    def test_cannot_create_project_for_archived_client(self):
        """Projects for archived clients must be rejected with 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        c = api_post("/api/v1/clients", {"name": f"arch-c-{UNIQUE}"}, headers=h).json()
        api_put(f"/api/v1/clients/{c['id']}", {"archived": True}, headers=h)

        r = api_post("/api/v1/projects", {
            "name": f"arch-cp-{UNIQUE}", "color": "#654321", "is_billable": True,
            "client_id": c["id"],
        }, headers=h)
        assert r.status_code == 422

    def test_archived_filter_on_clients(self):
        """Clients archived filter must actually filter."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        c1 = api_post("/api/v1/clients", {"name": f"active-c-{UNIQUE}"}, headers=h).json()
        c2 = api_post("/api/v1/clients", {"name": f"archived-c-{UNIQUE}"}, headers=h).json()
        api_put(f"/api/v1/clients/{c2['id']}", {"archived": True}, headers=h)

        active = api_get("/api/v1/clients", params={"archived": "false"}, headers=h).json()
        archived = api_get("/api/v1/clients", params={"archived": "true"}, headers=h).json()

        active_ids = [c["id"] for c in active]
        archived_ids = [c["id"] for c in archived]

        assert c1["id"] in active_ids
        assert c1["id"] not in archived_ids
        assert c2["id"] in archived_ids
        assert c2["id"] not in active_ids


# ════════════════════════════════════════════════════════════════════
# L2-12: Member role protection
# Patterns: 5 (business rules), 4 (status codes)
# ════════════════════════════════════════════════════════════════════


class TestMemberRoleProtection:

    def test_cannot_remove_owner(self):
        """Owner cannot be removed from org - returns 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        members = api_get("/api/v1/members", headers=h).json()
        owner = [m for m in members if m["role"] == "owner"][0]

        r = api_delete(f"/api/v1/members/{owner['id']}", headers=h)
        assert r.status_code == 422

    def test_cannot_change_owner_role(self):
        """Owner's role cannot be changed - returns 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        members = api_get("/api/v1/members", headers=h).json()
        owner = [m for m in members if m["role"] == "owner"][0]

        r = api_put(f"/api/v1/members/{owner['id']}", {"role": "member"}, headers=h)
        assert r.status_code == 422

        r = api_put(f"/api/v1/members/{owner['id']}", {"role": "admin"}, headers=h)
        assert r.status_code == 422


# ════════════════════════════════════════════════════════════════════
# L2-13: Time entry validation
# Patterns: 4 (status codes), 8 (edge cases)
# ════════════════════════════════════════════════════════════════════


class TestTimeEntryValidation:

    def test_end_before_start_rejected(self):
        """If end < start, must return 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        r = api_post("/api/v1/time-entries", {
            "start": "2024-12-15T10:00:00Z",
            "end": "2024-12-15T09:00:00Z",
            "billable": False,
        }, headers=h)
        assert r.status_code == 422

    def test_stop_already_stopped_timer(self):
        """Stopping a timer that already has end must return 422."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        te = api_post("/api/v1/time-entries", {
            "start": "2024-12-16T09:00:00Z",
            "end": "2024-12-16T10:00:00Z",
            "billable": False,
        }, headers=h).json()

        r = api_put(f"/api/v1/time-entries/{te['id']}/stop", {
            "end": "2024-12-16T11:00:00Z"
        }, headers=h)
        assert r.status_code == 422

    def test_missing_auth_headers_401(self):
        """Missing auth headers returns 401."""
        r = requests.get(f"{BASE_URL}/api/v1/organizations/current",
                         headers={"Content-Type": "application/json"}, timeout=30)
        assert r.status_code == 401

        r = requests.get(f"{BASE_URL}/api/v1/projects",
                         headers={"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"},
                         timeout=30)
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# L2-14: Report filtering
# Patterns: 3 (filter params work), 5 (aggregation correct)
# ════════════════════════════════════════════════════════════════════


class TestReportFiltering:

    def test_report_filter_by_project_id(self):
        """Project filter on time report must only include matching entries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p1 = api_post("/api/v1/projects", {
            "name": f"rpt-filter-p1-{UNIQUE}", "color": "#AA1111", "is_billable": True
        }, headers=h).json()
        p2 = api_post("/api/v1/projects", {
            "name": f"rpt-filter-p2-{UNIQUE}", "color": "#BB2222", "is_billable": True
        }, headers=h).json()

        # P1: 2 hours
        api_post("/api/v1/time-entries", {
            "start": "2024-11-10T09:00:00Z", "end": "2024-11-10T11:00:00Z",
            "project_id": p1["id"], "billable": False,
        }, headers=h)
        # P2: 1 hour
        api_post("/api/v1/time-entries", {
            "start": "2024-11-10T12:00:00Z", "end": "2024-11-10T13:00:00Z",
            "project_id": p2["id"], "billable": False,
        }, headers=h)

        r = api_get("/api/v1/reports/time", params={
            "start": "2024-11-10T00:00:00Z", "end": "2024-11-11T00:00:00Z",
            "project_id": p1["id"],
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()
        assert rpt["total_seconds"] == 7200, "Filter must only include P1 entries"
        assert rpt["entry_count"] == 1

    def test_report_filter_by_billable(self):
        """Billable filter on reports must only include matching entries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        api_post("/api/v1/time-entries", {
            "start": "2024-11-11T09:00:00Z", "end": "2024-11-11T10:00:00Z",
            "billable": True,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-11-11T11:00:00Z", "end": "2024-11-11T13:00:00Z",
            "billable": False,
        }, headers=h)

        r = api_get("/api/v1/reports/time", params={
            "start": "2024-11-11T00:00:00Z", "end": "2024-11-12T00:00:00Z",
            "billable": "true",
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()
        assert rpt["total_seconds"] == 3600
        assert rpt["entry_count"] == 1

    def test_report_filter_by_date_range(self):
        """Date range filter on reports must respect boundaries."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Entry inside range
        api_post("/api/v1/time-entries", {
            "start": "2024-11-15T09:00:00Z", "end": "2024-11-15T10:00:00Z", "billable": False,
        }, headers=h)
        # Entry outside range
        api_post("/api/v1/time-entries", {
            "start": "2024-11-20T09:00:00Z", "end": "2024-11-20T10:00:00Z", "billable": False,
        }, headers=h)

        r = api_get("/api/v1/reports/time", params={
            "start": "2024-11-15T00:00:00Z", "end": "2024-11-16T00:00:00Z",
        }, headers=h)
        assert r.status_code == 200
        rpt = r.json()
        assert rpt["total_seconds"] == 3600
        assert rpt["entry_count"] == 1


# ════════════════════════════════════════════════════════════════════
# L2-15: Organization auto-create and response structure
# Patterns: 1 (field names), 4 (status codes)
# ════════════════════════════════════════════════════════════════════


class TestOrganizationAutoCreate:

    def test_first_request_creates_org_with_correct_fields(self):
        """First request auto-creates org with expected fields."""
        h = fresh_headers()
        r = api_get("/api/v1/organizations/current", headers=h)
        assert r.status_code == 200
        org = r.json()

        assert "id" in org
        assert "name" in org
        assert "billable_rate" in org
        assert org["id"] == h["X-Org-Id"]
        assert isinstance(org["name"], str)
        assert len(org["name"]) > 0

    def test_auto_created_member_is_owner(self):
        """Auto-created membership has role=owner."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        members = api_get("/api/v1/members", headers=h).json()
        assert len(members) >= 1
        owner = [m for m in members if m["user_id"] == h["X-User-Id"]]
        assert len(owner) == 1
        assert owner[0]["role"] == "owner"
        assert owner[0]["organization_id"] == h["X-Org-Id"]
        assert "id" in owner[0]

    def test_update_org_name_and_verify(self):
        """Update org name and verify it persists."""
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        new_name = f"Updated-Org-{UNIQUE}"
        r = api_put("/api/v1/organizations/current", {"name": new_name}, headers=h)
        assert r.status_code == 200
        assert r.json()["name"] == new_name

        # GET should reflect the update
        r2 = api_get("/api/v1/organizations/current", headers=h)
        assert r2.json()["name"] == new_name
