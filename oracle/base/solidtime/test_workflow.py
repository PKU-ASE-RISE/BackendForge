"""
BackendForge — L3 Workflow Tests for Solidtime
Multi-step, cross-entity workflow tests targeting LLM implementation weaknesses.

Each test: 6-12 steps, 12-20 assertions, crossing 3+ entity types.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
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
# L3-01: Full Project Lifecycle with Billing
# Entities: Organization, Member, Client, Project, TimeEntry, Reports
# Patterns: 5 (business logic), 7 (cascade), 1 (field names)
# ════════════════════════════════════════════════════════════════════


class TestProjectLifecycleWithBilling:

    def test_full_project_billing_workflow(self):
        """
        Complete billing workflow:
        1. Setup org with billing rate
        2. Create client → project
        3. Log billable time entries
        4. Verify billable_amount computed correctly
        5. Check project report aggregation
        6. Archive project → verify can't add new entries
        7. Verify existing entries still accessible
        """
        h = fresh_headers()
        # 1. Setup org
        api_get("/api/v1/organizations/current", headers=h)
        api_put("/api/v1/organizations/current", {"billable_rate": 7500}, headers=h)  # $75/hr

        # Set member rate to verify it takes precedence
        members = api_get("/api/v1/members", headers=h).json()
        member_id = members[0]["id"]
        user_id = h["X-User-Id"]
        api_put(f"/api/v1/members/{member_id}", {"billable_rate": 12000}, headers=h)  # $120/hr

        # 2. Create client and project
        client = api_post("/api/v1/clients", {
            "name": f"Acme Corp-{UNIQUE}",
            "email": "billing@acme.com",
        }, headers=h).json()
        assert client["archived"] is False

        project = api_post("/api/v1/projects", {
            "name": f"Website Redesign-{UNIQUE}",
            "color": "#3498DB",
            "is_billable": True,
            "client_id": client["id"],
        }, headers=h).json()
        assert project["client_id"] == client["id"]
        assert project["is_billable"] is True
        assert project["color"] == "#3498DB"

        # 3. Log billable time entries
        # Entry 1: 2 hours
        te1 = api_post("/api/v1/time-entries", {
            "start": "2024-09-01T09:00:00Z",
            "end": "2024-09-01T11:00:00Z",
            "project_id": project["id"],
            "billable": True,
            "description": "Design mockups",
        }, headers=h).json()
        assert te1["duration"] == 7200
        # Member rate: 2h * 12000 = 24000
        assert te1["billable_amount"] == pytest.approx(24000.0, abs=1)

        # Entry 2: 1.5 hours
        te2 = api_post("/api/v1/time-entries", {
            "start": "2024-09-01T14:00:00Z",
            "end": "2024-09-01T15:30:00Z",
            "project_id": project["id"],
            "billable": True,
            "description": "Frontend coding",
        }, headers=h).json()
        assert te2["duration"] == 5400
        # 1.5h * 12000 = 18000
        assert te2["billable_amount"] == pytest.approx(18000.0, abs=1)

        # 4. Non-billable entry
        te3 = api_post("/api/v1/time-entries", {
            "start": "2024-09-02T09:00:00Z",
            "end": "2024-09-02T10:00:00Z",
            "project_id": project["id"],
            "billable": False,
        }, headers=h).json()
        assert te3["billable_amount"] == 0

        # 5. Check report
        rpt = api_get("/api/v1/reports/projects", params={
            "start": "2024-09-01T00:00:00Z",
            "end": "2024-09-03T00:00:00Z",
        }, headers=h).json()
        proj_rpt = [r for r in rpt if r["project_id"] == project["id"]]
        assert len(proj_rpt) == 1
        assert proj_rpt[0]["total_seconds"] == 16200  # 2h + 1.5h + 1h = 4.5h
        assert proj_rpt[0]["total_billable_seconds"] == 12600  # 2h + 1.5h = 3.5h
        assert proj_rpt[0]["entry_count"] == 3
        # Billable amount: 24000 + 18000 = 42000
        assert proj_rpt[0]["total_billable_amount"] == pytest.approx(42000.0, abs=1)

        # 6. Archive project → can't add new entries
        api_put(f"/api/v1/projects/{project['id']}", {"archived": True}, headers=h)
        r_fail = api_post("/api/v1/time-entries", {
            "start": "2024-09-03T09:00:00Z",
            "end": "2024-09-03T10:00:00Z",
            "project_id": project["id"],
            "billable": True,
        }, headers=h)
        assert r_fail.status_code == 422

        # 7. Existing entries still accessible
        r_existing = api_get(f"/api/v1/time-entries/{te1['id']}", headers=h)
        assert r_existing.status_code == 200
        assert r_existing.json()["project_id"] == project["id"]


# ════════════════════════════════════════════════════════════════════
# L3-02: Timer Workflow with Auto-Stop and Reports
# Entities: Organization, Project, TimeEntry (timers), Reports
# Patterns: 5 (timer logic), 7 (side effects), 2 (computed fields)
# ════════════════════════════════════════════════════════════════════


class TestTimerWorkflow:

    def test_timer_chain_and_report(self):
        """
        1. Start timer A on project 1
        2. Start timer B on project 2 (auto-stops A)
        3. Verify A stopped with correct duration
        4. Stop B manually
        5. Verify B duration
        6. Check that reports reflect both entries correctly
        7. Start timer C, verify running timer in report
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        p1 = api_post("/api/v1/projects", {
            "name": f"timer-p1-{UNIQUE}", "color": "#E74C3C", "is_billable": True
        }, headers=h).json()
        p2 = api_post("/api/v1/projects", {
            "name": f"timer-p2-{UNIQUE}", "color": "#2ECC71", "is_billable": True
        }, headers=h).json()

        # 1. Start timer A at 09:00
        a = api_post("/api/v1/time-entries/start", {
            "start": "2024-09-15T09:00:00Z",
            "billable": True,
            "project_id": p1["id"],
            "description": "Task A",
        }, headers=h)
        assert a.status_code == 201
        a_id = a.json()["id"]
        assert a.json()["end"] is None

        # 2. Start timer B at 10:30 (auto-stops A)
        b = api_post("/api/v1/time-entries/start", {
            "start": "2024-09-15T10:30:00Z",
            "billable": False,
            "project_id": p2["id"],
            "description": "Task B",
        }, headers=h)
        assert b.status_code == 201
        b_id = b.json()["id"]
        assert b.json()["end"] is None

        # 3. Verify A is stopped (duration = 1.5h = 5400s)
        a_check = api_get(f"/api/v1/time-entries/{a_id}", headers=h).json()
        assert a_check["end"] is not None
        assert a_check["duration"] == 5400
        assert a_check["project_id"] == p1["id"]

        # 4. Stop B manually at 12:00
        b_stop = api_put(f"/api/v1/time-entries/{b_id}/stop", {
            "end": "2024-09-15T12:00:00Z"
        }, headers=h)
        assert b_stop.status_code == 200

        # 5. Verify B duration = 1.5h = 5400s
        b_check = api_get(f"/api/v1/time-entries/{b_id}", headers=h).json()
        assert b_check["duration"] == 5400
        assert b_check["project_id"] == p2["id"]

        # 6. Check reports
        rpt = api_get("/api/v1/reports/time", params={
            "start": "2024-09-15T00:00:00Z",
            "end": "2024-09-16T00:00:00Z",
        }, headers=h).json()
        assert rpt["total_seconds"] == 10800  # 5400 + 5400
        assert rpt["entry_count"] == 2
        assert rpt["total_billable_seconds"] == 5400  # Only A is billable

        # Project report
        proj_rpt = api_get("/api/v1/reports/projects", params={
            "start": "2024-09-15T00:00:00Z",
            "end": "2024-09-16T00:00:00Z",
        }, headers=h).json()
        p1_rpt = [r for r in proj_rpt if r["project_id"] == p1["id"]]
        p2_rpt = [r for r in proj_rpt if r["project_id"] == p2["id"]]
        assert p1_rpt[0]["total_seconds"] == 5400
        assert p2_rpt[0]["total_seconds"] == 5400


# ════════════════════════════════════════════════════════════════════
# L3-03: Multi-org Data Isolation
# Entities: Organization, Client, Project, TimeEntry, Tags
# Patterns: 6 (data isolation), 1 (field names), 8 (concurrent)
# ════════════════════════════════════════════════════════════════════


class TestMultiOrgIsolation:

    def test_complete_isolation_between_orgs(self):
        """
        1. Create entities in org1
        2. Create entities in org2
        3. Verify org1 can't see org2's data (and vice versa)
        4. Verify same names allowed in different orgs
        5. Verify can't access cross-org resources by ID
        6. Verify reports are scoped to org
        """
        h1 = fresh_headers()
        h2 = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h1)
        api_get("/api/v1/organizations/current", headers=h2)

        shared_name = f"SharedProject-{UNIQUE}"

        # 1. Create in org1
        c1 = api_post("/api/v1/clients", {"name": f"Org1Client-{UNIQUE}"}, headers=h1).json()
        p1 = api_post("/api/v1/projects", {
            "name": shared_name, "color": "#FF0000", "is_billable": True, "client_id": c1["id"]
        }, headers=h1).json()
        tag1 = api_post("/api/v1/tags", {"name": f"org1-tag-{UNIQUE}"}, headers=h1).json()
        te1 = api_post("/api/v1/time-entries", {
            "start": "2024-08-01T09:00:00Z", "end": "2024-08-01T11:00:00Z",
            "project_id": p1["id"], "billable": True, "tag_ids": [tag1["id"]],
        }, headers=h1).json()

        # 2. Create in org2 (same project name allowed!)
        p2 = api_post("/api/v1/projects", {
            "name": shared_name, "color": "#0000FF", "is_billable": False
        }, headers=h2)
        assert p2.status_code == 201, "Same name must be allowed in different orgs"
        p2 = p2.json()

        api_post("/api/v1/time-entries", {
            "start": "2024-08-01T09:00:00Z", "end": "2024-08-01T10:00:00Z",
            "project_id": p2["id"], "billable": False,
        }, headers=h2)

        # 3. Org2 can't see org1's data
        org2_projects = api_get("/api/v1/projects", headers=h2).json()
        org2_project_ids = [p["id"] for p in org2_projects]
        assert p1["id"] not in org2_project_ids

        org2_clients = api_get("/api/v1/clients", headers=h2).json()
        assert len([c for c in org2_clients if c["name"] == f"Org1Client-{UNIQUE}"]) == 0

        org2_tags = api_get("/api/v1/tags", headers=h2).json()
        assert tag1["id"] not in [t["id"] for t in org2_tags]

        org2_entries = api_get("/api/v1/time-entries", headers=h2).json()
        assert te1["id"] not in [e["id"] for e in org2_entries]

        # 4. Can't access org1's project by ID from org2
        r = api_get(f"/api/v1/projects/{p1['id']}", headers=h2)
        assert r.status_code == 404

        # 5. Can't delete org1's time entry from org2
        r = api_delete(f"/api/v1/time-entries/{te1['id']}", headers=h2)
        assert r.status_code == 404

        # 6. Reports are org-scoped
        rpt1 = api_get("/api/v1/reports/time", params={
            "start": "2024-08-01T00:00:00Z", "end": "2024-08-02T00:00:00Z",
        }, headers=h1).json()
        rpt2 = api_get("/api/v1/reports/time", params={
            "start": "2024-08-01T00:00:00Z", "end": "2024-08-02T00:00:00Z",
        }, headers=h2).json()

        assert rpt1["total_seconds"] == 7200  # 2 hours org1
        assert rpt2["total_seconds"] == 3600  # 1 hour org2


# ════════════════════════════════════════════════════════════════════
# L3-04: Task Tracking with Time and Cascade
# Entities: Project, Task, TimeEntry, Tags
# Patterns: 5 (spent_seconds), 7 (cascade delete), 2 (nested data)
# ════════════════════════════════════════════════════════════════════


class TestTaskTrackingWorkflow:

    def test_task_lifecycle_with_time_tracking(self):
        """
        1. Create project with 2 tasks (estimated time)
        2. Log time entries against each task
        3. Verify spent_seconds computed for each task
        4. Mark task as done
        5. Delete project → tasks are removed
        6. Time entries remain but project_id = null
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # 1. Create project with tasks
        project = api_post("/api/v1/projects", {
            "name": f"TaskTrack-{UNIQUE}", "color": "#9B59B6", "is_billable": True
        }, headers=h).json()

        task_a = api_post("/api/v1/tasks", {
            "name": f"Backend API-{UNIQUE}",
            "project_id": project["id"],
            "estimated_seconds": 14400,  # 4 hours estimate
        }, headers=h).json()
        assert task_a["done"] is False
        assert task_a["estimated_seconds"] == 14400

        task_b = api_post("/api/v1/tasks", {
            "name": f"Frontend UI-{UNIQUE}",
            "project_id": project["id"],
            "estimated_seconds": 7200,  # 2 hours estimate
        }, headers=h).json()

        # 2. Log time entries
        te1 = api_post("/api/v1/time-entries", {
            "start": "2024-10-05T09:00:00Z", "end": "2024-10-05T11:00:00Z",
            "project_id": project["id"], "task_id": task_a["id"], "billable": True,
        }, headers=h).json()
        assert te1["task_id"] == task_a["id"]

        te2 = api_post("/api/v1/time-entries", {
            "start": "2024-10-05T13:00:00Z", "end": "2024-10-05T14:30:00Z",
            "project_id": project["id"], "task_id": task_a["id"], "billable": True,
        }, headers=h).json()

        te3 = api_post("/api/v1/time-entries", {
            "start": "2024-10-05T15:00:00Z", "end": "2024-10-05T16:00:00Z",
            "project_id": project["id"], "task_id": task_b["id"], "billable": True,
        }, headers=h).json()

        # 3. Verify spent_seconds
        tasks = api_get("/api/v1/tasks", params={"project_id": project["id"]}, headers=h).json()
        ta = [t for t in tasks if t["id"] == task_a["id"]][0]
        tb = [t for t in tasks if t["id"] == task_b["id"]][0]
        # Task A: 2h + 1.5h = 12600s
        assert ta["spent_seconds"] == 12600
        # Task B: 1h = 3600s
        assert tb["spent_seconds"] == 3600

        # 4. Mark task as done
        r = api_put(f"/api/v1/tasks/{task_a['id']}", {"done": True}, headers=h)
        assert r.status_code == 200
        assert r.json()["done"] is True

        # Filter done tasks
        done_tasks = api_get("/api/v1/tasks", params={"done": "true"}, headers=h).json()
        done_ids = [t["id"] for t in done_tasks]
        assert task_a["id"] in done_ids
        assert task_b["id"] not in done_ids

        # 5. Delete project → tasks removed
        api_delete(f"/api/v1/projects/{project['id']}", headers=h)
        remaining_tasks = api_get("/api/v1/tasks", headers=h).json()
        remaining_ids = [t["id"] for t in remaining_tasks]
        assert task_a["id"] not in remaining_ids
        assert task_b["id"] not in remaining_ids

        # 6. Time entries still exist with null project_id
        r = api_get(f"/api/v1/time-entries/{te1['id']}", headers=h)
        assert r.status_code == 200
        assert r.json()["project_id"] is None


# ════════════════════════════════════════════════════════════════════
# L3-05: Client-Project Cascade Workflow
# Entities: Client, Project, TimeEntry, Task
# Patterns: 7 (cascade), 5 (constraints), 6 (isolation)
# ════════════════════════════════════════════════════════════════════


class TestClientProjectCascade:

    def test_client_deletion_cascade_and_constraints(self):
        """
        1. Create client
        2. Create project linked to client
        3. Create task for project
        4. Log time against task
        5. Archive client → verify can't create new project
        6. Un-archive client → can create project again
        7. Delete client → project's client_id becomes null
        8. Verify task and time entry still exist
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # 1. Create client
        client = api_post("/api/v1/clients", {
            "name": f"BigCorp-{UNIQUE}", "email": "contact@bigcorp.com"
        }, headers=h).json()
        assert client["organization_id"] == h["X-Org-Id"]

        # 2. Create project linked to client
        project = api_post("/api/v1/projects", {
            "name": f"BigCorpProj-{UNIQUE}", "color": "#E67E22",
            "is_billable": True, "client_id": client["id"],
        }, headers=h).json()
        assert project["client_id"] == client["id"]

        # 3. Create task
        task = api_post("/api/v1/tasks", {
            "name": f"BigTask-{UNIQUE}", "project_id": project["id"],
        }, headers=h).json()

        # 4. Log time
        te = api_post("/api/v1/time-entries", {
            "start": "2024-10-20T09:00:00Z", "end": "2024-10-20T10:00:00Z",
            "project_id": project["id"], "task_id": task["id"], "billable": True,
        }, headers=h).json()

        # 5. Archive client → can't create new project for it
        api_put(f"/api/v1/clients/{client['id']}", {"archived": True}, headers=h)
        r = api_post("/api/v1/projects", {
            "name": f"NewProjFail-{UNIQUE}", "color": "#000000",
            "is_billable": True, "client_id": client["id"],
        }, headers=h)
        assert r.status_code == 422

        # 6. Un-archive → can create again
        api_put(f"/api/v1/clients/{client['id']}", {"archived": False}, headers=h)
        r = api_post("/api/v1/projects", {
            "name": f"NewProjOk-{UNIQUE}", "color": "#111111",
            "is_billable": True, "client_id": client["id"],
        }, headers=h)
        assert r.status_code == 201

        # 7. Delete client → project's client_id null
        api_delete(f"/api/v1/clients/{client['id']}", headers=h)
        proj_after = api_get(f"/api/v1/projects/{project['id']}", headers=h).json()
        assert proj_after["client_id"] is None

        # 8. Task and time entry still exist
        tasks = api_get("/api/v1/tasks", params={"project_id": project["id"]}, headers=h).json()
        assert any(t["id"] == task["id"] for t in tasks)

        te_after = api_get(f"/api/v1/time-entries/{te['id']}", headers=h).json()
        assert te_after["project_id"] == project["id"]
        assert te_after["task_id"] == task["id"]


# ════════════════════════════════════════════════════════════════════
# L3-06: Multi-member Report Aggregation
# Entities: Organization, Member, TimeEntry, Reports
# Patterns: 5 (aggregation), 3 (filters), 6 (member scoping)
# ════════════════════════════════════════════════════════════════════


class TestMultiMemberReports:

    def test_member_report_with_multiple_users(self):
        """
        1. Setup org with 2 members
        2. Both members log time
        3. Report grouped by member shows correct totals
        4. Filter by member_id works
        5. Billable amounts are per-member rate
        """
        h = fresh_headers()
        user1_id = h["X-User-Id"]
        org_id = h["X-Org-Id"]
        api_get("/api/v1/organizations/current", headers=h)

        # Set org rate
        api_put("/api/v1/organizations/current", {"billable_rate": 5000}, headers=h)

        # Set user1 rate
        members = api_get("/api/v1/members", headers=h).json()
        m1 = members[0]
        api_put(f"/api/v1/members/{m1['id']}", {"billable_rate": 10000}, headers=h)

        # Add second member
        user2_id = str(uuid.uuid4())
        m2 = api_post("/api/v1/members", {
            "user_id": user2_id, "role": "member", "billable_rate": 8000,
        }, headers=h).json()

        # Headers for user2
        h2 = {"X-User-Id": user2_id, "X-Org-Id": org_id, "Content-Type": "application/json"}

        # User1 logs 2 hours
        api_post("/api/v1/time-entries", {
            "start": "2024-11-01T09:00:00Z", "end": "2024-11-01T11:00:00Z", "billable": True,
        }, headers=h)

        # User2 logs 3 hours
        api_post("/api/v1/time-entries", {
            "start": "2024-11-01T09:00:00Z", "end": "2024-11-01T12:00:00Z", "billable": True,
        }, headers=h2)

        # 3. Member report
        rpt = api_get("/api/v1/reports/members", params={
            "start": "2024-11-01T00:00:00Z", "end": "2024-11-02T00:00:00Z",
        }, headers=h).json()
        assert isinstance(rpt, list)
        assert len(rpt) >= 2

        u1_rpt = [r for r in rpt if r["user_id"] == user1_id]
        u2_rpt = [r for r in rpt if r["user_id"] == user2_id]
        assert len(u1_rpt) == 1
        assert len(u2_rpt) == 1

        assert u1_rpt[0]["total_seconds"] == 7200   # 2h
        assert u2_rpt[0]["total_seconds"] == 10800  # 3h

        # Billable amounts: u1: 2h*10000=20000, u2: 3h*8000=24000
        assert u1_rpt[0]["total_billable_amount"] == pytest.approx(20000.0, abs=1)
        assert u2_rpt[0]["total_billable_amount"] == pytest.approx(24000.0, abs=1)

        # 4. Filter time report by member_id
        rpt_u1 = api_get("/api/v1/reports/time", params={
            "start": "2024-11-01T00:00:00Z", "end": "2024-11-02T00:00:00Z",
            "member_id": user1_id,
        }, headers=h).json()
        assert rpt_u1["total_seconds"] == 7200
        assert rpt_u1["entry_count"] == 1

        rpt_u2 = api_get("/api/v1/reports/time", params={
            "start": "2024-11-01T00:00:00Z", "end": "2024-11-02T00:00:00Z",
            "member_id": user2_id,
        }, headers=h).json()
        assert rpt_u2["total_seconds"] == 10800
        assert rpt_u2["entry_count"] == 1


# ════════════════════════════════════════════════════════════════════
# L3-07: Tag Workflow Across Time Entries
# Entities: Tag, TimeEntry, Project
# Patterns: 2 (nested data), 7 (cascade), 3 (filter)
# ════════════════════════════════════════════════════════════════════


class TestTagWorkflowAcrossEntries:

    def test_tags_lifecycle_with_time_entries(self):
        """
        1. Create multiple tags
        2. Create time entries with different tag combinations
        3. Verify tags returned correctly on GET
        4. Update entry tags → verify old tags removed
        5. Delete a tag → verify removed from all entries
        6. Remaining entries unaffected
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # 1. Create tags
        tag_dev = api_post("/api/v1/tags", {"name": f"development-{UNIQUE}"}, headers=h).json()
        tag_review = api_post("/api/v1/tags", {"name": f"code-review-{UNIQUE}"}, headers=h).json()
        tag_meeting = api_post("/api/v1/tags", {"name": f"meeting-{UNIQUE}"}, headers=h).json()

        # 2. Create entries with different tags
        te1 = api_post("/api/v1/time-entries", {
            "start": "2024-10-15T09:00:00Z", "end": "2024-10-15T11:00:00Z",
            "billable": False, "tag_ids": [tag_dev["id"], tag_review["id"]],
        }, headers=h).json()

        te2 = api_post("/api/v1/time-entries", {
            "start": "2024-10-15T14:00:00Z", "end": "2024-10-15T15:00:00Z",
            "billable": False, "tag_ids": [tag_meeting["id"]],
        }, headers=h).json()

        te3 = api_post("/api/v1/time-entries", {
            "start": "2024-10-15T16:00:00Z", "end": "2024-10-15T17:00:00Z",
            "billable": False, "tag_ids": [tag_dev["id"]],
        }, headers=h).json()

        # 3. Verify tags on GET
        te1_get = api_get(f"/api/v1/time-entries/{te1['id']}", headers=h).json()
        te1_tag_ids = {t["id"] for t in te1_get["tags"]}
        assert tag_dev["id"] in te1_tag_ids
        assert tag_review["id"] in te1_tag_ids
        assert len(te1_get["tags"]) == 2

        # 4. Update te1 to only have meeting tag
        r = api_put(f"/api/v1/time-entries/{te1['id']}", {
            "tag_ids": [tag_meeting["id"]],
        }, headers=h)
        assert r.status_code == 200
        updated_tags = {t["id"] for t in r.json()["tags"]}
        assert tag_meeting["id"] in updated_tags
        assert tag_dev["id"] not in updated_tags
        assert tag_review["id"] not in updated_tags
        assert len(r.json()["tags"]) == 1

        # 5. Delete dev tag → removed from te3
        api_delete(f"/api/v1/tags/{tag_dev['id']}", headers=h)
        te3_after = api_get(f"/api/v1/time-entries/{te3['id']}", headers=h).json()
        assert len(te3_after["tags"]) == 0

        # 6. te2 unaffected (still has meeting tag)
        te2_after = api_get(f"/api/v1/time-entries/{te2['id']}", headers=h).json()
        assert len(te2_after["tags"]) == 1
        assert te2_after["tags"][0]["id"] == tag_meeting["id"]


# ════════════════════════════════════════════════════════════════════
# L3-08: Daily Report With Mixed Data
# Entities: Project, TimeEntry, Reports
# Patterns: 5 (aggregation), 3 (date grouping), 1 (field format)
# ════════════════════════════════════════════════════════════════════


class TestDailyReportMixedData:

    def test_daily_report_accuracy_across_days(self):
        """
        1. Create entries across 3 days with mixed billable/non-billable
        2. Verify daily report groups correctly
        3. Verify date format is YYYY-MM-DD
        4. Verify totals match per day
        5. Verify billable amounts computed per day
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)
        api_put("/api/v1/organizations/current", {"billable_rate": 4000}, headers=h)

        # Day 1: 3h billable + 1h non-billable
        api_post("/api/v1/time-entries", {
            "start": "2024-12-01T08:00:00Z", "end": "2024-12-01T11:00:00Z", "billable": True,
        }, headers=h)
        api_post("/api/v1/time-entries", {
            "start": "2024-12-01T14:00:00Z", "end": "2024-12-01T15:00:00Z", "billable": False,
        }, headers=h)

        # Day 2: 2h billable
        api_post("/api/v1/time-entries", {
            "start": "2024-12-02T09:00:00Z", "end": "2024-12-02T11:00:00Z", "billable": True,
        }, headers=h)

        # Day 3: 30min non-billable
        api_post("/api/v1/time-entries", {
            "start": "2024-12-03T10:00:00Z", "end": "2024-12-03T10:30:00Z", "billable": False,
        }, headers=h)

        rpt = api_get("/api/v1/reports/daily", params={
            "start": "2024-12-01T00:00:00Z", "end": "2024-12-04T00:00:00Z",
        }, headers=h).json()
        assert isinstance(rpt, list)

        # Verify date format
        for entry in rpt:
            assert "date" in entry
            # YYYY-MM-DD format check
            parts = entry["date"].split("-")
            assert len(parts) == 3
            assert len(parts[0]) == 4

        d1 = [r for r in rpt if r["date"] == "2024-12-01"]
        d2 = [r for r in rpt if r["date"] == "2024-12-02"]
        d3 = [r for r in rpt if r["date"] == "2024-12-03"]

        assert len(d1) == 1
        assert len(d2) == 1
        assert len(d3) == 1

        # Day 1: 3h + 1h = 14400s total, 10800s billable
        assert d1[0]["total_seconds"] == 14400
        assert d1[0]["total_billable_seconds"] == 10800
        assert d1[0]["entry_count"] == 2
        # Billable amount: 3h * 4000 = 12000
        assert d1[0]["total_billable_amount"] == pytest.approx(12000.0, abs=1)

        # Day 2: 2h = 7200s total, all billable
        assert d2[0]["total_seconds"] == 7200
        assert d2[0]["total_billable_seconds"] == 7200
        assert d2[0]["entry_count"] == 1
        assert d2[0]["total_billable_amount"] == pytest.approx(8000.0, abs=1)

        # Day 3: 30min = 1800s, non-billable
        assert d3[0]["total_seconds"] == 1800
        assert d3[0]["total_billable_seconds"] == 0
        assert d3[0]["entry_count"] == 1
        assert d3[0]["total_billable_amount"] == 0


# ════════════════════════════════════════════════════════════════════
# L3-09: Member Management and Permissions
# Entities: Organization, Member
# Patterns: 5 (role rules), 8 (constraint enforcement), 4 (status codes)
# ════════════════════════════════════════════════════════════════════


class TestMemberManagementWorkflow:

    def test_member_role_rules_and_constraints(self):
        """
        1. Auto-created user is owner
        2. Add member with role 'member'
        3. Update member to 'admin'
        4. Try to change owner's role → 422
        5. Try to remove owner → 422
        6. Remove admin → succeeds
        7. Add duplicate member → 409
        8. Verify member list reflects changes
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # 1. Auto-created is owner
        members = api_get("/api/v1/members", headers=h).json()
        assert len(members) == 1
        owner = members[0]
        assert owner["role"] == "owner"
        assert owner["user_id"] == h["X-User-Id"]

        # 2. Add member
        user2 = str(uuid.uuid4())
        m2 = api_post("/api/v1/members", {
            "user_id": user2, "role": "member", "billable_rate": 5000,
        }, headers=h)
        assert m2.status_code == 201
        m2_data = m2.json()
        assert m2_data["role"] == "member"
        assert m2_data["billable_rate"] == 5000

        # 3. Update to admin
        r = api_put(f"/api/v1/members/{m2_data['id']}", {"role": "admin"}, headers=h)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

        # 4. Can't change owner's role
        r = api_put(f"/api/v1/members/{owner['id']}", {"role": "member"}, headers=h)
        assert r.status_code == 422

        # 5. Can't remove owner
        r = api_delete(f"/api/v1/members/{owner['id']}", headers=h)
        assert r.status_code == 422

        # 6. Remove admin
        r = api_delete(f"/api/v1/members/{m2_data['id']}", headers=h)
        assert r.status_code == 204

        # 7. Can't add same user again after removal? Actually can re-add
        # Let's try adding duplicate of owner
        r = api_post("/api/v1/members", {
            "user_id": h["X-User-Id"], "role": "member",
        }, headers=h)
        assert r.status_code == 409  # Owner already exists as member

        # 8. Verify final state
        final_members = api_get("/api/v1/members", headers=h).json()
        final_ids = [m["user_id"] for m in final_members]
        assert h["X-User-Id"] in final_ids
        assert user2 not in final_ids


# ════════════════════════════════════════════════════════════════════
# L3-10: Complete Time Entry CRUD with All Fields
# Entities: Project, Task, Tag, TimeEntry
# Patterns: 1 (all field names), 2 (nested data), 5 (computed fields)
# ════════════════════════════════════════════════════════════════════


class TestTimeEntryCRUDComplete:

    def test_full_time_entry_lifecycle(self):
        """
        1. Create project, task, and tags
        2. Create time entry with ALL fields
        3. Verify GET returns all fields correctly (including nested tags)
        4. Update time entry (change description, tags, billable, end)
        5. Verify duration recomputed after update
        6. Verify billable_amount recomputed
        7. Delete time entry → verify 404 on GET
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)
        api_put("/api/v1/organizations/current", {"billable_rate": 6000}, headers=h)

        # 1. Create supporting entities
        project = api_post("/api/v1/projects", {
            "name": f"CRUD-proj-{UNIQUE}", "color": "#1ABC9C", "is_billable": True
        }, headers=h).json()
        task = api_post("/api/v1/tasks", {
            "name": f"CRUD-task-{UNIQUE}", "project_id": project["id"],
        }, headers=h).json()
        tag1 = api_post("/api/v1/tags", {"name": f"crud-t1-{UNIQUE}"}, headers=h).json()
        tag2 = api_post("/api/v1/tags", {"name": f"crud-t2-{UNIQUE}"}, headers=h).json()

        # 2. Create time entry with all fields
        te = api_post("/api/v1/time-entries", {
            "start": "2024-11-20T09:00:00Z",
            "end": "2024-11-20T11:00:00Z",
            "description": "Initial work",
            "project_id": project["id"],
            "task_id": task["id"],
            "billable": True,
            "tag_ids": [tag1["id"], tag2["id"]],
        }, headers=h)
        assert te.status_code == 201
        te_data = te.json()
        te_id = te_data["id"]

        # 3. Verify all fields on GET
        r = api_get(f"/api/v1/time-entries/{te_id}", headers=h)
        assert r.status_code == 200
        entry = r.json()
        assert entry["id"] == te_id
        assert entry["user_id"] == h["X-User-Id"]
        assert entry["organization_id"] == h["X-Org-Id"]
        assert entry["project_id"] == project["id"]
        assert entry["task_id"] == task["id"]
        assert entry["description"] == "Initial work"
        assert entry["billable"] is True
        assert entry["duration"] == 7200
        assert entry["billable_amount"] == pytest.approx(12000.0, abs=1)  # 2h * 6000
        assert len(entry["tags"]) == 2

        # 4. Update
        r = api_put(f"/api/v1/time-entries/{te_id}", {
            "end": "2024-11-20T12:00:00Z",  # Extend to 3 hours
            "description": "Extended work",
            "billable": False,
            "tag_ids": [tag1["id"]],  # Remove tag2
        }, headers=h)
        assert r.status_code == 200
        updated = r.json()

        # 5. Duration recomputed
        assert updated["duration"] == 10800  # 3 hours

        # 6. Billable amount recomputed (now non-billable)
        assert updated["billable_amount"] == 0
        assert updated["description"] == "Extended work"
        assert len(updated["tags"]) == 1
        assert updated["tags"][0]["id"] == tag1["id"]

        # 7. Delete
        r = api_delete(f"/api/v1/time-entries/{te_id}", headers=h)
        assert r.status_code == 204
        r = api_get(f"/api/v1/time-entries/{te_id}", headers=h)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L3-11: Auto-join and Member Data Persistence
# Entities: Organization, Member, TimeEntry
# Patterns: 6 (auto-join), 7 (member removal doesn't delete entries)
# ════════════════════════════════════════════════════════════════════


class TestAutoJoinAndPersistence:

    def test_new_user_auto_joins_and_entries_persist_after_removal(self):
        """
        1. Create org with user1 (owner)
        2. user2 makes request → auto-joins as member
        3. user2 creates time entries
        4. Remove user2 from org
        5. Verify user2's time entries STILL exist (attributed to user2)
        6. Verify user2's entries appear in reports
        """
        h1 = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h1)
        org_id = h1["X-Org-Id"]

        # 2. User2 auto-joins
        user2_id = str(uuid.uuid4())
        h2 = {"X-User-Id": user2_id, "X-Org-Id": org_id, "Content-Type": "application/json"}
        api_get("/api/v1/organizations/current", headers=h2)

        # Verify user2 is member
        members = api_get("/api/v1/members", headers=h1).json()
        u2_member = [m for m in members if m["user_id"] == user2_id]
        assert len(u2_member) == 1
        u2_member_id = u2_member[0]["id"]

        # 3. User2 creates time entries
        te = api_post("/api/v1/time-entries", {
            "start": "2024-12-20T09:00:00Z", "end": "2024-12-20T11:00:00Z",
            "billable": False,
        }, headers=h2).json()
        te_id = te["id"]
        assert te["user_id"] == user2_id

        # 4. Remove user2
        r = api_delete(f"/api/v1/members/{u2_member_id}", headers=h1)
        assert r.status_code == 204

        # 5. Time entries still exist (checked by user1 who is owner)
        r = api_get(f"/api/v1/time-entries/{te_id}", headers=h1)
        assert r.status_code == 200
        assert r.json()["user_id"] == user2_id

        # 6. Reports include user2's entries
        rpt = api_get("/api/v1/reports/time", params={
            "start": "2024-12-20T00:00:00Z", "end": "2024-12-21T00:00:00Z",
        }, headers=h1).json()
        assert rpt["total_seconds"] >= 7200


# ════════════════════════════════════════════════════════════════════
# L3-12: Time Entry Date Range Filtering
# Entities: TimeEntry, Reports
# Patterns: 3 (filter params), 5 (boundary conditions)
# ════════════════════════════════════════════════════════════════════


class TestTimeEntryDateFiltering:

    def test_date_range_boundaries(self):
        """
        1. Create entries on different dates
        2. Filter with start/end params
        3. Verify boundary conditions (inclusive start, exclusive end)
        4. Verify entries outside range not included
        5. Verify report respects same boundaries
        """
        h = fresh_headers()
        api_get("/api/v1/organizations/current", headers=h)

        # Create entries on different days
        # Jan 5 at 09:00
        te_jan5 = api_post("/api/v1/time-entries", {
            "start": "2024-01-05T09:00:00Z", "end": "2024-01-05T10:00:00Z", "billable": False,
        }, headers=h).json()
        # Jan 10 at 09:00
        te_jan10 = api_post("/api/v1/time-entries", {
            "start": "2024-01-10T09:00:00Z", "end": "2024-01-10T10:00:00Z", "billable": False,
        }, headers=h).json()
        # Jan 15 at 09:00
        te_jan15 = api_post("/api/v1/time-entries", {
            "start": "2024-01-15T09:00:00Z", "end": "2024-01-15T10:00:00Z", "billable": False,
        }, headers=h).json()

        # Filter: Jan 5 00:00 to Jan 11 00:00 (should include Jan 5 and Jan 10)
        r = api_get("/api/v1/time-entries", params={
            "start": "2024-01-05T00:00:00Z", "end": "2024-01-11T00:00:00Z",
        }, headers=h)
        assert r.status_code == 200
        entries = r.json()
        entry_ids = [e["id"] for e in entries]
        assert te_jan5["id"] in entry_ids
        assert te_jan10["id"] in entry_ids
        assert te_jan15["id"] not in entry_ids

        # Report should match
        rpt = api_get("/api/v1/reports/time", params={
            "start": "2024-01-05T00:00:00Z", "end": "2024-01-11T00:00:00Z",
        }, headers=h).json()
        assert rpt["entry_count"] == 2
        assert rpt["total_seconds"] == 7200  # 2 * 1h
