"""
BackendForge — L2 Integration Tests for Vikunja Task

Each test: 3-5 steps, 8-12 assertions.
Targets LLM bug patterns: field naming, nested data, sorting/filtering,
status codes, business logic, permissions.

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())
USER_C_ID = str(uuid.uuid4())

USER_A = {"X-User-Id": USER_A_ID, "Content-Type": "application/json"}
USER_B = {"X-User-Id": USER_B_ID, "Content-Type": "application/json"}
USER_C = {"X-User-Id": USER_C_ID, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _isolated_test_users():
    """Give every item private user-scoped state."""
    global USER_A_ID, USER_B_ID, USER_C_ID
    global USER_A, USER_B, USER_C

    USER_A_ID = str(uuid.uuid4())
    USER_B_ID = str(uuid.uuid4())
    USER_C_ID = str(uuid.uuid4())
    USER_A = {"X-User-Id": USER_A_ID, "Content-Type": "application/json"}
    USER_B = {"X-User-Id": USER_B_ID, "Content-Type": "application/json"}
    USER_C = {"X-User-Id": USER_C_ID, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or USER_A, timeout=30)


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or USER_A, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or USER_A, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or USER_A, timeout=30)


# ════════════════════════════════════════════════════════════════════
# L2 Tests — Integration
# ════════════════════════════════════════════════════════════════════


class TestProjectFieldNamesAndStructure:
    """Pattern 1+2: Verify snake_case field names + complete response structure."""

    def test_create_project_response_has_all_required_fields(self):
        """Create project and verify ALL response fields are present with correct names."""
        r = post("/api/v1/projects", {"title": "Field Check", "description": "desc", "color": "#abc"})
        assert r.status_code == 201
        data = r.json()

        # Verify all required fields exist with snake_case names
        assert "id" in data
        assert "title" in data
        assert "owner_id" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify optional fields with snake_case
        assert "description" in data
        assert "color" in data
        assert "is_archived" in data
        assert "position" in data
        assert "parent_project_id" in data

        # Verify values
        assert data["title"] == "Field Check"
        assert data["description"] == "desc"
        assert data["color"] == "#abc"
        assert data["owner_id"] == USER_A_ID
        assert data["is_archived"] is False
        assert isinstance(data["id"], int)

    def test_task_create_response_has_full_structure(self):
        """Pattern 1+2: Task response includes nested arrays and correct field naming."""
        proj = post("/api/v1/projects", {"title": "TaskStruct"}).json()
        pid = proj["id"]

        r = post(f"/api/v1/projects/{pid}/tasks", {
            "title": "Full Task",
            "description": "detailed",
            "priority": 3,
            "due_date": "2025-12-01T10:00:00Z",
            "percent_done": 0.4,
            "position": 2.5,
        })
        assert r.status_code == 201
        task = r.json()

        # Snake_case field names
        assert "project_id" in task
        assert "created_by_id" in task
        assert "bucket_id" in task
        assert "due_date" in task
        assert "start_date" in task
        assert "end_date" in task
        assert "percent_done" in task
        assert "created_at" in task
        assert "updated_at" in task

        # Nested arrays present
        assert "assignees" in task
        assert "labels" in task
        assert "relations" in task
        assert isinstance(task["assignees"], list)
        assert isinstance(task["labels"], list)
        assert isinstance(task["relations"], dict)

        # Value checks
        assert task["project_id"] == pid
        assert task["created_by_id"] == USER_A_ID
        assert task["priority"] == 3
        assert task["percent_done"] == 0.4
        assert task["done"] is False
        assert task["bucket_id"] is None


class TestTaskSortingActuallyWorks:
    """Pattern 3: Verify sorting params are actually implemented, not just accepted."""

    def test_sort_by_priority_ascending(self):
        """Create tasks with different priorities, sort asc, verify order."""
        proj = post("/api/v1/projects", {"title": "SortPriAsc"}).json()
        pid = proj["id"]

        post(f"/api/v1/projects/{pid}/tasks", {"title": "T-pri5", "priority": 5})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "T-pri1", "priority": 1})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "T-pri3", "priority": 3})

        r = get(f"/api/v1/projects/{pid}/tasks", params={"sort_by": "priority", "order_by": "asc"})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 3
        priorities = [t["priority"] for t in tasks]
        assert priorities == sorted(priorities), f"Expected ascending priorities, got {priorities}"

    def test_sort_by_priority_descending(self):
        """Sort by priority desc: highest first."""
        proj = post("/api/v1/projects", {"title": "SortPriDesc"}).json()
        pid = proj["id"]

        post(f"/api/v1/projects/{pid}/tasks", {"title": "P2", "priority": 2})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P5", "priority": 5})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P0", "priority": 0})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P4", "priority": 4})

        r = get(f"/api/v1/projects/{pid}/tasks", params={"sort_by": "priority", "order_by": "desc"})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 4
        priorities = [t["priority"] for t in tasks]
        assert priorities == sorted(priorities, reverse=True), f"Expected descending, got {priorities}"

    def test_sort_by_due_date_ascending(self):
        """Sort by due_date asc: earliest first (nulls handling may vary)."""
        proj = post("/api/v1/projects", {"title": "SortDue"}).json()
        pid = proj["id"]

        post(f"/api/v1/projects/{pid}/tasks", {"title": "Late", "due_date": "2025-12-31T00:00:00Z"})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "Early", "due_date": "2025-01-01T00:00:00Z"})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "Mid", "due_date": "2025-06-15T00:00:00Z"})

        r = get(f"/api/v1/projects/{pid}/tasks", params={"sort_by": "due_date", "order_by": "asc"})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 3
        # All have due dates, so ordering should be chronological
        dates = [t["due_date"] for t in tasks]
        assert dates == sorted(dates), f"Expected ascending dates, got {dates}"

    def test_filter_done_true_only_returns_completed(self):
        """Pattern 3+5: filter_done=true actually filters, not just accepted."""
        proj = post("/api/v1/projects", {"title": "FilterDone"}).json()
        pid = proj["id"]

        post(f"/api/v1/projects/{pid}/tasks", {"title": "Done1", "done": True})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "Done2", "done": True})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "NotDone", "done": False})

        r = get(f"/api/v1/projects/{pid}/tasks", params={"filter_done": "true"})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2
        assert all(t["done"] is True for t in tasks)
        titles = [t["title"] for t in tasks]
        assert "NotDone" not in titles

    def test_filter_priority_gte_threshold(self):
        """filter_priority filters tasks with priority >= value."""
        proj = post("/api/v1/projects", {"title": "FilterPri"}).json()
        pid = proj["id"]

        post(f"/api/v1/projects/{pid}/tasks", {"title": "Low", "priority": 1})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "Med", "priority": 3})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "High", "priority": 5})

        r = get(f"/api/v1/projects/{pid}/tasks", params={"filter_priority": 3})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2
        assert all(t["priority"] >= 3 for t in tasks)
        titles = [t["title"] for t in tasks]
        assert "Low" not in titles
        assert "Med" in titles
        assert "High" in titles


class TestLabelAttachmentRoundtrip:
    """Pattern 2: Labels actually linked to tasks and visible in GET response."""

    def test_attach_label_visible_in_task_get(self):
        """Attach label, then GET task — label must appear in labels array."""
        proj = post("/api/v1/projects", {"title": "LabelRT"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Labeled"}).json()
        tid = task["id"]
        label = post("/api/v1/labels", {"title": "Bug", "color": "#ff0000"}).json()
        lid = label["id"]

        # Attach
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": lid})
        assert r.status_code == 201

        # Get task — verify label is in the labels array
        r = get(f"/api/v1/tasks/{tid}")
        assert r.status_code == 200
        task_data = r.json()
        assert "labels" in task_data
        assert isinstance(task_data["labels"], list)
        assert len(task_data["labels"]) == 1
        attached = task_data["labels"][0]
        assert attached["id"] == lid
        assert attached["title"] == "Bug"
        assert attached["color"] == "#ff0000"
        assert "created_at" in attached

    def test_multiple_labels_all_visible(self):
        """Attach multiple labels, all visible in GET."""
        proj = post("/api/v1/projects", {"title": "MultiLabel"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "MultiLabeled"}).json()
        tid = task["id"]

        l1 = post("/api/v1/labels", {"title": "Feature"}).json()
        l2 = post("/api/v1/labels", {"title": "Urgent"}).json()
        l3 = post("/api/v1/labels", {"title": "Backend"}).json()

        post(f"/api/v1/tasks/{tid}/labels", {"label_id": l1["id"]})
        post(f"/api/v1/tasks/{tid}/labels", {"label_id": l2["id"]})
        post(f"/api/v1/tasks/{tid}/labels", {"label_id": l3["id"]})

        r = get(f"/api/v1/tasks/{tid}")
        assert r.status_code == 200
        labels = r.json()["labels"]
        assert len(labels) == 3
        label_ids = {l["id"] for l in labels}
        assert l1["id"] in label_ids
        assert l2["id"] in label_ids
        assert l3["id"] in label_ids


class TestAssigneeRoundtrip:
    """Pattern 2: Assignees actually linked and visible in task GET."""

    def test_assign_user_visible_in_task(self):
        """Assign user to task, verify visible in GET task response."""
        proj = post("/api/v1/projects", {"title": "AssigneeRT"}).json()
        pid = proj["id"]

        # Ensure user B exists
        get("/api/v1/projects", headers=USER_B)
        # Add user B as member
        post(f"/api/v1/projects/{pid}/members", {"user_id": USER_B_ID, "role": "editor"})

        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Assigned"}).json()
        tid = task["id"]

        # Assign
        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": USER_B_ID})
        assert r.status_code == 201
        assignee_resp = r.json()
        assert assignee_resp["id"] == USER_B_ID
        assert "username" in assignee_resp

        # GET task — verify assignees array
        r = get(f"/api/v1/tasks/{tid}")
        assert r.status_code == 200
        assignees = r.json()["assignees"]
        assert len(assignees) == 1
        assert assignees[0]["id"] == USER_B_ID
        assert "username" in assignees[0]

    def test_owner_can_self_assign(self):
        """Project owner can assign themselves to a task."""
        proj = post("/api/v1/projects", {"title": "SelfAssign"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Mine"}).json()
        tid = task["id"]

        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": USER_A_ID})
        assert r.status_code == 201

        task_data = get(f"/api/v1/tasks/{tid}").json()
        assert len(task_data["assignees"]) == 1
        assert task_data["assignees"][0]["id"] == USER_A_ID


class TestCommentCRUDAndOwnership:
    """Pattern 2+6: Comments linked to tasks, ownership enforced."""

    def test_comment_roundtrip_with_correct_fields(self):
        """Create comment, GET it, verify all fields present."""
        proj = post("/api/v1/projects", {"title": "CommentRT"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Commented"}).json()
        tid = task["id"]

        r = post(f"/api/v1/tasks/{tid}/comments", {"comment": "Hello world"})
        assert r.status_code == 201
        comment = r.json()
        assert "id" in comment
        assert comment["comment"] == "Hello world"
        assert comment["author_id"] == USER_A_ID
        assert "created_at" in comment
        assert "updated_at" in comment
        cid = comment["id"]

        # GET single comment
        r = get(f"/api/v1/tasks/{tid}/comments/{cid}")
        assert r.status_code == 200
        fetched = r.json()
        assert fetched["id"] == cid
        assert fetched["comment"] == "Hello world"
        assert fetched["author_id"] == USER_A_ID

    def test_comment_list_returns_all_comments(self):
        """List comments returns all task comments."""
        proj = post("/api/v1/projects", {"title": "CommentList"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "ManyComments"}).json()
        tid = task["id"]

        post(f"/api/v1/tasks/{tid}/comments", {"comment": "First"})
        post(f"/api/v1/tasks/{tid}/comments", {"comment": "Second"})
        post(f"/api/v1/tasks/{tid}/comments", {"comment": "Third"})

        r = get(f"/api/v1/tasks/{tid}/comments")
        assert r.status_code == 200
        comments = r.json()
        assert isinstance(comments, list)
        assert len(comments) == 3
        texts = [c["comment"] for c in comments]
        assert "First" in texts
        assert "Second" in texts
        assert "Third" in texts


class TestRelationBidirectionality:
    """Pattern 5+7: Relations are truly bidirectional, not just stored one-way."""

    def test_blocks_creates_inverse_blocked_by(self):
        """Creating A blocks B creates B blocked_by A — verified via GET."""
        proj = post("/api/v1/projects", {"title": "RelBidir"}).json()
        pid = proj["id"]
        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Blocker"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Blocked"}).json()

        r = post(f"/api/v1/tasks/{t1['id']}/relations", {
            "other_task_id": t2["id"],
            "relation_kind": "blocks",
        })
        assert r.status_code == 201
        rel = r.json()
        assert rel["task_id"] == t1["id"]
        assert rel["other_task_id"] == t2["id"]
        assert rel["relation_kind"] == "blocks"

        # Verify task A has blocks relation
        a_data = get(f"/api/v1/tasks/{t1['id']}").json()
        assert "blocks" in a_data["relations"]
        assert t2["id"] in a_data["relations"]["blocks"]

        # Verify task B has blocked_by relation
        b_data = get(f"/api/v1/tasks/{t2['id']}").json()
        assert "blocked_by" in b_data["relations"]
        assert t1["id"] in b_data["relations"]["blocked_by"]

    def test_duplicates_creates_inverse_duplicated_by(self):
        """duplicates/duplicated_by pair is bidirectional."""
        proj = post("/api/v1/projects", {"title": "RelDup"}).json()
        pid = proj["id"]
        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Original"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Duplicate"}).json()

        r = post(f"/api/v1/tasks/{t1['id']}/relations", {
            "other_task_id": t2["id"],
            "relation_kind": "duplicates",
        })
        assert r.status_code == 201

        a_data = get(f"/api/v1/tasks/{t1['id']}").json()
        assert "duplicates" in a_data["relations"]
        assert t2["id"] in a_data["relations"]["duplicates"]

        b_data = get(f"/api/v1/tasks/{t2['id']}").json()
        assert "duplicated_by" in b_data["relations"]
        assert t1["id"] in b_data["relations"]["duplicated_by"]

    def test_subtask_of_creates_inverse_parent_of(self):
        """subtask_of/parent_of pair is bidirectional."""
        proj = post("/api/v1/projects", {"title": "RelSub"}).json()
        pid = proj["id"]
        parent = post(f"/api/v1/projects/{pid}/tasks", {"title": "Parent"}).json()
        child = post(f"/api/v1/projects/{pid}/tasks", {"title": "Child"}).json()

        r = post(f"/api/v1/tasks/{child['id']}/relations", {
            "other_task_id": parent["id"],
            "relation_kind": "subtask_of",
        })
        assert r.status_code == 201

        child_data = get(f"/api/v1/tasks/{child['id']}").json()
        assert "subtask_of" in child_data["relations"]
        assert parent["id"] in child_data["relations"]["subtask_of"]

        parent_data = get(f"/api/v1/tasks/{parent['id']}").json()
        assert "parent_of" in parent_data["relations"]
        assert child["id"] in parent_data["relations"]["parent_of"]


class TestBucketLimitEnforcement:
    """Pattern 5: Bucket limits actually enforced, not just stored."""

    def test_bucket_limit_blocks_overfill(self):
        """Bucket with limit=2 rejects 3rd task."""
        proj = post("/api/v1/projects", {"title": "BucketLimit"}).json()
        pid = proj["id"]
        bucket = post(f"/api/v1/projects/{pid}/buckets", {"title": "Limited", "limit": 2}).json()
        bid = bucket["id"]

        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "T1"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "T2"}).json()
        t3 = post(f"/api/v1/projects/{pid}/tasks", {"title": "T3"}).json()

        r1 = put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": bid})
        assert r1.status_code == 200
        r2 = put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": bid})
        assert r2.status_code == 200

        # 3rd should fail
        r3 = put(f"/api/v1/tasks/{t3['id']}/bucket", {"bucket_id": bid})
        assert r3.status_code == 400

    def test_moving_task_out_frees_slot(self):
        """Moving task out of a full bucket allows a new one in."""
        proj = post("/api/v1/projects", {"title": "BucketFree"}).json()
        pid = proj["id"]
        b1 = post(f"/api/v1/projects/{pid}/buckets", {"title": "Full", "limit": 1}).json()
        b2 = post(f"/api/v1/projects/{pid}/buckets", {"title": "Other", "limit": 0}).json()

        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "First"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Second"}).json()

        # Fill b1
        put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": b1["id"]})
        # t2 can't go in
        r = put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": b1["id"]})
        assert r.status_code == 400

        # Move t1 out
        put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": b2["id"]})

        # Now t2 can go in
        r = put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": b1["id"]})
        assert r.status_code == 200
        assert r.json()["bucket_id"] == b1["id"]


class TestTaskDonePercentDoneBehavior:
    """Pattern 5: Business logic - done sets percent_done, undone doesn't reset."""

    def test_setting_done_true_forces_percent_done_to_1(self):
        """When done=true, percent_done auto-set to 1.0 regardless of input."""
        proj = post("/api/v1/projects", {"title": "DonePct"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {
            "title": "Partial",
            "percent_done": 0.3,
        }).json()
        tid = task["id"]
        assert task["percent_done"] == 0.3

        # Mark done
        r = put(f"/api/v1/tasks/{tid}", {"title": "Partial", "done": True})
        assert r.status_code == 200
        assert r.json()["done"] is True
        assert r.json()["percent_done"] == 1.0

    def test_setting_done_false_keeps_percent_done(self):
        """When done=false, percent_done stays as-is (does NOT reset to 0)."""
        proj = post("/api/v1/projects", {"title": "UndonePct"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {
            "title": "WasDone",
            "done": True,
        }).json()
        tid = task["id"]
        assert task["percent_done"] == 1.0

        # Unmark done
        r = put(f"/api/v1/tasks/{tid}", {"title": "WasDone", "done": False})
        assert r.status_code == 200
        assert r.json()["done"] is False
        assert r.json()["percent_done"] == 1.0  # NOT reset

    def test_create_task_done_true_sets_percent_1(self):
        """Creating a task with done=true auto-sets percent_done=1.0."""
        proj = post("/api/v1/projects", {"title": "CreateDone"}).json()
        pid = proj["id"]
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "BornDone", "done": True})
        assert r.status_code == 201
        assert r.json()["done"] is True
        assert r.json()["percent_done"] == 1.0


class TestPermissionEnforcement:
    """Pattern 6: Permission checks - viewer vs editor vs non-member."""

    def test_viewer_cannot_create_or_update_tasks(self):
        """Viewer can read but not write tasks."""
        proj = post("/api/v1/projects", {"title": "ViewerPerm"}).json()
        pid = proj["id"]

        # Ensure user B exists and add as viewer
        get("/api/v1/projects", headers=USER_B)
        post(f"/api/v1/projects/{pid}/members", {"user_id": USER_B_ID, "role": "viewer"})

        # Owner creates a task
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Protected"}).json()
        tid = task["id"]

        # Viewer can read
        r = get(f"/api/v1/projects/{pid}/tasks", headers=USER_B)
        assert r.status_code == 200
        assert len(r.json()) >= 1

        r = get(f"/api/v1/tasks/{tid}", headers=USER_B)
        assert r.status_code == 200

        # Viewer cannot create task
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "Nope"}, headers=USER_B)
        assert r.status_code == 403

        # Viewer cannot update task
        r = put(f"/api/v1/tasks/{tid}", {"title": "Hacked"}, headers=USER_B)
        assert r.status_code == 403

        # Viewer cannot delete task
        r = delete(f"/api/v1/tasks/{tid}", headers=USER_B)
        assert r.status_code == 403

    def test_non_member_cannot_access_project_tasks(self):
        """A user with no project access gets 403."""
        proj = post("/api/v1/projects", {"title": "NoAccess"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Secret"}).json()
        tid = task["id"]

        # Ensure user C exists
        get("/api/v1/projects", headers=USER_C)

        # Non-member cannot list tasks
        r = get(f"/api/v1/projects/{pid}/tasks", headers=USER_C)
        assert r.status_code == 403

        # Non-member cannot get task
        r = get(f"/api/v1/tasks/{tid}", headers=USER_C)
        assert r.status_code == 403

    def test_editor_can_create_and_update_tasks(self):
        """Editor member can create and update tasks."""
        proj = post("/api/v1/projects", {"title": "EditorPerm"}).json()
        pid = proj["id"]

        get("/api/v1/projects", headers=USER_B)
        post(f"/api/v1/projects/{pid}/members", {"user_id": USER_B_ID, "role": "editor"})

        # Editor can create task
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "EditorTask"}, headers=USER_B)
        assert r.status_code == 201
        tid = r.json()["id"]

        # Editor can update task
        r = put(f"/api/v1/tasks/{tid}", {"title": "EditorUpdated"}, headers=USER_B)
        assert r.status_code == 200
        assert r.json()["title"] == "EditorUpdated"


class TestArchivedProjectBehavior:
    """Pattern 5: Archived project business logic enforced."""

    def test_archived_project_rejects_new_tasks(self):
        """Archived project returns 400 when creating tasks."""
        proj = post("/api/v1/projects", {"title": "ArchiveTest"}).json()
        pid = proj["id"]

        # Create a task first
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "PreArchive"}).json()
        tid = task["id"]

        # Archive the project
        r = put(f"/api/v1/projects/{pid}", {"title": "ArchiveTest", "is_archived": True})
        assert r.status_code == 200
        assert r.json()["is_archived"] is True

        # Cannot create new task
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "PostArchive"})
        assert r.status_code == 400

        # Cannot update existing task
        r = put(f"/api/v1/tasks/{tid}", {"title": "Modified"})
        assert r.status_code == 400

        # CAN still read task
        r = get(f"/api/v1/tasks/{tid}")
        assert r.status_code == 200
        assert r.json()["title"] == "PreArchive"


class TestCascadeDeleteEffects:
    """Pattern 7: Cascade deletes actually remove related data."""

    def test_delete_project_removes_tasks_and_buckets(self):
        """Deleting project removes its tasks and buckets."""
        proj = post("/api/v1/projects", {"title": "CascadeDel"}).json()
        pid = proj["id"]

        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Doomed"}).json()
        tid = task["id"]
        bucket = post(f"/api/v1/projects/{pid}/buckets", {"title": "DoomedBucket"}).json()
        bid = bucket["id"]

        # Delete project
        r = delete(f"/api/v1/projects/{pid}")
        assert r.status_code == 204

        # Task is gone
        r = get(f"/api/v1/tasks/{tid}")
        assert r.status_code == 404

        # Bucket is gone (project is 404)
        r = get(f"/api/v1/projects/{pid}/buckets/{bid}")
        assert r.status_code == 404

    def test_delete_task_removes_comments_and_relations(self):
        """Deleting a task removes its comments and relations."""
        proj = post("/api/v1/projects", {"title": "CascadeTask"}).json()
        pid = proj["id"]

        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "TaskA"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "TaskB"}).json()

        # Add comment to t1
        comment = post(f"/api/v1/tasks/{t1['id']}/comments", {"comment": "Will die"}).json()
        cid = comment["id"]

        # Add relation t1 blocks t2
        post(f"/api/v1/tasks/{t1['id']}/relations", {
            "other_task_id": t2["id"],
            "relation_kind": "blocks",
        })

        # Delete t1
        r = delete(f"/api/v1/tasks/{t1['id']}")
        assert r.status_code == 204

        # Comment is gone
        r = get(f"/api/v1/tasks/{t1['id']}/comments/{cid}")
        assert r.status_code == 404

        # t2 should no longer have blocked_by relation to t1
        t2_data = get(f"/api/v1/tasks/{t2['id']}").json()
        blocked_by = t2_data["relations"].get("blocked_by", [])
        assert t1["id"] not in blocked_by

    def test_delete_label_detaches_from_all_tasks(self):
        """Deleting a label removes it from tasks it was attached to."""
        proj = post("/api/v1/projects", {"title": "LabelCascade"}).json()
        pid = proj["id"]
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "HasLabel"}).json()
        tid = task["id"]

        label = post("/api/v1/labels", {"title": "Temp"}).json()
        lid = label["id"]
        post(f"/api/v1/tasks/{tid}/labels", {"label_id": lid})

        # Verify attached
        task_data = get(f"/api/v1/tasks/{tid}").json()
        assert any(l["id"] == lid for l in task_data["labels"])

        # Delete label
        r = delete(f"/api/v1/labels/{lid}")
        assert r.status_code == 204

        # Task no longer has label
        task_data = get(f"/api/v1/tasks/{tid}").json()
        assert not any(l["id"] == lid for l in task_data["labels"])


class TestStatusCodeCorrectness:
    """Pattern 4: Correct HTTP status codes for all operations."""

    def test_create_operations_return_201(self):
        """POST creates return 201, not 200."""
        proj = post("/api/v1/projects", {"title": "SC201"})
        assert proj.status_code == 201
        pid = proj.json()["id"]

        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task201"})
        assert task.status_code == 201

        label = post("/api/v1/labels", {"title": "Label201"})
        assert label.status_code == 201

        bucket = post(f"/api/v1/projects/{pid}/buckets", {"title": "Bucket201"})
        assert bucket.status_code == 201

        comment = post(f"/api/v1/tasks/{task.json()['id']}/comments", {"comment": "Comment201"})
        assert comment.status_code == 201

        filt = post("/api/v1/filters", {"title": "Filter201", "filter_query": "x"})
        assert filt.status_code == 201

    def test_delete_operations_return_204(self):
        """DELETE operations return 204, not 200."""
        proj = post("/api/v1/projects", {"title": "SC204"}).json()
        pid = proj["id"]

        label = post("/api/v1/labels", {"title": "Del204"}).json()
        r = delete(f"/api/v1/labels/{label['id']}")
        assert r.status_code == 204

        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Del204"}).json()
        r = delete(f"/api/v1/tasks/{task['id']}")
        assert r.status_code == 204

        filt = post("/api/v1/filters", {"title": "Del204", "filter_query": "x"}).json()
        r = delete(f"/api/v1/filters/{filt['id']}")
        assert r.status_code == 204

    def test_not_found_returns_404(self):
        """Accessing non-existent resources returns 404, not 200 empty."""
        r = get("/api/v1/projects/999999")
        assert r.status_code == 404

        r = get("/api/v1/tasks/999999")
        assert r.status_code == 404

        r = get("/api/v1/labels/999999")
        assert r.status_code == 404

        r = get("/api/v1/filters/999999")
        assert r.status_code == 404


class TestBucketFieldsAndCrossProject:
    """Pattern 1+8: Bucket fields and cross-project validation."""

    def test_bucket_response_has_correct_fields(self):
        """Bucket response includes project_id and all required fields."""
        proj = post("/api/v1/projects", {"title": "BucketFields"}).json()
        pid = proj["id"]

        r = post(f"/api/v1/projects/{pid}/buckets", {
            "title": "Backlog",
            "position": 1.0,
            "limit": 10,
        })
        assert r.status_code == 201
        bucket = r.json()
        assert "id" in bucket
        assert bucket["title"] == "Backlog"
        assert bucket["position"] == 1.0
        assert bucket["limit"] == 10
        assert bucket["project_id"] == pid
        assert "created_at" in bucket
        assert "updated_at" in bucket

    def test_cannot_move_task_to_bucket_in_different_project(self):
        """Pattern 8: Cross-project bucket move is rejected."""
        p1 = post("/api/v1/projects", {"title": "ProjX"}).json()
        p2 = post("/api/v1/projects", {"title": "ProjY"}).json()

        task = post(f"/api/v1/projects/{p1['id']}/tasks", {"title": "TaskX"}).json()
        bucket = post(f"/api/v1/projects/{p2['id']}/buckets", {"title": "BucketY"}).json()

        r = put(f"/api/v1/tasks/{task['id']}/bucket", {"bucket_id": bucket["id"]})
        assert r.status_code == 400


class TestFilterUserScoping:
    """Pattern 6: Filters are user-scoped - isolation between users."""

    def test_filters_isolated_between_users(self):
        """User A's filters are invisible to User B."""
        # User A creates filter
        r = post("/api/v1/filters", {"title": "My Filter", "filter_query": "priority>=3"})
        assert r.status_code == 201
        fid = r.json()["id"]

        # User B cannot see it by ID
        r = get(f"/api/v1/filters/{fid}", headers=USER_B)
        assert r.status_code == 404

        # User B cannot see it in list
        r = get("/api/v1/filters", headers=USER_B)
        assert r.status_code == 200
        ids = [f["id"] for f in r.json()]
        assert fid not in ids

    def test_filter_crud_roundtrip(self):
        """Create, read, update, delete filter with correct status codes."""
        # Create
        r = post("/api/v1/filters", {"title": "CRUD", "filter_query": "done=false"})
        assert r.status_code == 201
        f = r.json()
        assert f["title"] == "CRUD"
        assert f["filter_query"] == "done=false"
        fid = f["id"]

        # Read
        r = get(f"/api/v1/filters/{fid}")
        assert r.status_code == 200
        assert r.json()["filter_query"] == "done=false"

        # Update
        r = put(f"/api/v1/filters/{fid}", {"title": "Updated", "filter_query": "done=true"})
        assert r.status_code == 200
        assert r.json()["title"] == "Updated"
        assert r.json()["filter_query"] == "done=true"

        # Delete
        r = delete(f"/api/v1/filters/{fid}")
        assert r.status_code == 204

        # Verify gone
        r = get(f"/api/v1/filters/{fid}")
        assert r.status_code == 404
