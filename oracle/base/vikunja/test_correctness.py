"""
BackendForge — Comprehensive Correctness Tests for Vikunja Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# User IDs — UUIDs, auto-created on first request
USER1_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())

USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolated_test_state():
    """Keep each item independent without relying on destructive cleanup."""
    global USER1_ID, USER2_ID, USER3_ID
    global USER1_HEADERS, USER2_HEADERS, USER3_HEADERS, UNIQUE

    USER1_ID = str(uuid.uuid4())
    USER2_ID = str(uuid.uuid4())
    USER3_ID = str(uuid.uuid4())
    USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
    USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
    USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}
    UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or USER1_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or USER1_HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or USER1_HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or USER1_HEADERS, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-User-Id header should return 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/projects", timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        """Empty X-User-Id header should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/v1/projects",
            headers={"X-User-Id": "", "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_valid_header_auto_creates_user(self):
        """A valid UUID header should auto-create the user and succeed."""
        resp = api_get("/api/v1/projects", headers=USER1_HEADERS)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Projects CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjectsCRUD:

    def test_create_project(self):
        """Create a new project with required fields."""
        resp = api_post("/api/v1/projects", {"title": f"Test Project {UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"Test Project {UNIQUE}"
        assert "id" in data
        assert data["owner_id"] == USER1_ID
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_project_with_all_fields(self):
        """Create a project with all optional fields."""
        resp = api_post("/api/v1/projects", {
            "title": f"Full Project {UNIQUE}",
            "description": "A full project",
            "color": "#ff0000",
            "is_archived": False,
            "position": 1.5,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "A full project"
        assert data["color"] == "#ff0000"
        assert data["is_archived"] is False
        assert data["position"] == 1.5

    def test_create_project_missing_title_returns_400(self):
        """Title is required."""
        resp = api_post("/api/v1/projects", {"description": "no title"})
        assert resp.status_code == 400

    def test_list_projects(self):
        """List should include the user's projects."""
        # Create a project first
        create_resp = api_post("/api/v1/projects", {"title": f"List Test {UNIQUE}"})
        assert create_resp.status_code == 201

        resp = api_get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        titles = [p["title"] for p in data]
        assert f"List Test {UNIQUE}" in titles

    def test_get_project(self):
        """Get a project by ID."""
        create_resp = api_post("/api/v1/projects", {"title": f"Get Test {UNIQUE}"})
        project_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == f"Get Test {UNIQUE}"

    def test_update_project(self):
        """Update a project's title and description."""
        create_resp = api_post("/api/v1/projects", {"title": f"Update Test {UNIQUE}"})
        project_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/projects/{project_id}", {
            "title": f"Updated {UNIQUE}",
            "description": "Updated description",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == f"Updated {UNIQUE}"
        assert data["description"] == "Updated description"

    def test_delete_project(self):
        """Delete a project."""
        create_resp = api_post("/api/v1/projects", {"title": f"Delete Test {UNIQUE}"})
        project_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = api_get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 404

    def test_get_nonexistent_project_returns_404(self):
        """Accessing a non-existent project returns 404."""
        resp = api_get("/api/v1/projects/99999")
        assert resp.status_code == 404

    def test_nested_project(self):
        """Create a child project under a parent."""
        parent_resp = api_post("/api/v1/projects", {"title": f"Parent {UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/api/v1/projects", {
            "title": f"Child {UNIQUE}",
            "parent_project_id": parent_id,
        })
        assert child_resp.status_code == 201
        assert child_resp.json()["parent_project_id"] == parent_id


# ════════════════════════════════════════════════════════════════════
# PART 3: Project Access Control
# ════════════════════════════════════════════════════════════════════


class TestProjectAccessControl:

    def test_other_user_cannot_access_project(self):
        """A user who is not owner or member cannot access the project."""
        create_resp = api_post("/api/v1/projects", {"title": f"Private {UNIQUE}"})
        project_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/projects/{project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_other_user_cannot_see_project_in_list(self):
        """Projects are not visible to non-members in listing."""
        create_resp = api_post("/api/v1/projects", {"title": f"Hidden {UNIQUE}"})
        project_id = create_resp.json()["id"]

        resp = api_get("/api/v1/projects", headers=USER2_HEADERS)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert project_id not in ids

    def test_member_can_access_project(self):
        """A member added to a project can access it."""
        create_resp = api_post("/api/v1/projects", {"title": f"Shared {UNIQUE}"})
        project_id = create_resp.json()["id"]

        # Trigger user2 creation
        api_get("/api/v1/projects", headers=USER2_HEADERS)

        # Add user2 as editor
        member_resp = api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })
        assert member_resp.status_code == 201

        # User2 can now access
        resp = api_get(f"/api/v1/projects/{project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_only_owner_can_delete_project(self):
        """Only the owner can delete a project."""
        create_resp = api_post("/api/v1/projects", {"title": f"OwnerOnly {UNIQUE}"})
        project_id = create_resp.json()["id"]

        # Add user2 as editor
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        # User2 cannot delete
        resp = api_delete(f"/api/v1/projects/{project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_parent_access_grants_child_access(self):
        """Access to parent project grants access to child projects."""
        parent_resp = api_post("/api/v1/projects", {"title": f"ParentAccess {UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/api/v1/projects", {
            "title": f"ChildAccess {UNIQUE}",
            "parent_project_id": parent_id,
        })
        child_id = child_resp.json()["id"]

        # Add user2 as member of parent
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{parent_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        # User2 can access child
        resp = api_get(f"/api/v1/projects/{child_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_child_access_does_not_grant_parent_access(self):
        """Access to a child does NOT grant access to parent."""
        parent_resp = api_post("/api/v1/projects", {"title": f"NoParent {UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/api/v1/projects", {
            "title": f"ChildOnly {UNIQUE}",
            "parent_project_id": parent_id,
        })
        child_id = child_resp.json()["id"]

        # Add user3 as member of child only
        api_get("/api/v1/projects", headers=USER3_HEADERS)
        api_post(f"/api/v1/projects/{child_id}/members", {
            "user_id": USER3_ID,
            "role": "editor",
        })

        # User3 cannot access parent
        resp = api_get(f"/api/v1/projects/{parent_id}", headers=USER3_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 4: Tasks CRUD
# ════════════════════════════════════════════════════════════════════


class TestTasksCRUD:

    @pytest.fixture(autouse=True)
    def setup_project(self, _isolated_test_state):
        """Create a project for task tests."""
        resp = api_post("/api/v1/projects", {"title": f"TaskProject {UNIQUE} {uuid.uuid4().hex[:4]}"})
        assert resp.status_code == 201
        self.project_id = resp.json()["id"]

    def test_create_task(self):
        """Create a basic task."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "My Task",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Task"
        assert data["project_id"] == self.project_id
        assert data["done"] is False
        assert data["priority"] == 0
        assert data["percent_done"] == 0
        assert "id" in data
        assert "created_at" in data
        assert data["created_by_id"] == USER1_ID
        assert data["assignees"] == []
        assert data["labels"] == []

    def test_create_task_with_all_fields(self):
        """Create a task with all optional fields."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Full Task",
            "description": "A detailed task",
            "done": False,
            "priority": 3,
            "due_date": "2025-06-15T10:00:00Z",
            "start_date": "2025-06-01T08:00:00Z",
            "end_date": "2025-06-15T18:00:00Z",
            "percent_done": 0.5,
            "position": 2.5,
            "reminders": ["2025-06-14T10:00:00Z"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == 3
        assert data["percent_done"] == 0.5
        assert data["position"] == 2.5
        assert data["description"] == "A detailed task"

    def test_create_task_invalid_priority_returns_400(self):
        """Priority must be 0-5."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Bad Priority",
            "priority": 6,
        })
        assert resp.status_code == 400

    def test_create_task_invalid_percent_done_returns_400(self):
        """Percent done must be 0.0-1.0."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Bad Percent",
            "percent_done": 1.5,
        })
        assert resp.status_code == 400

    def test_get_task(self):
        """Get a task by ID."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Get Task",
        })
        task_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Task"

    def test_update_task(self):
        """Update a task's fields."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Update Me",
        })
        task_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/tasks/{task_id}", {
            "title": "Updated Task",
            "priority": 4,
            "description": "Now updated",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Task"
        assert data["priority"] == 4
        assert data["description"] == "Now updated"

    def test_delete_task(self):
        """Delete a task."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Delete Me",
        })
        task_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = api_get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 404

    def test_list_project_tasks(self):
        """List tasks in a project."""
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Task A"})
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Task B"})

        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_done_sets_percent_done_to_1(self):
        """Setting done=true auto-sets percent_done to 1.0."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Done Task",
            "percent_done": 0.5,
        })
        task_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/tasks/{task_id}", {
            "title": "Done Task",
            "done": True,
        })
        assert resp.status_code == 200
        assert resp.json()["done"] is True
        assert resp.json()["percent_done"] == 1.0

    def test_undone_does_not_reset_percent_done(self):
        """Setting done=false does NOT auto-change percent_done."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Undone Task",
            "done": True,
        })
        task_id = create_resp.json()["id"]
        # percent_done should be 1.0 from done=true
        assert create_resp.json()["percent_done"] == 1.0

        resp = api_put(f"/api/v1/tasks/{task_id}", {
            "title": "Undone Task",
            "done": False,
        })
        assert resp.status_code == 200
        assert resp.json()["done"] is False
        # percent_done stays at 1.0
        assert resp.json()["percent_done"] == 1.0


# ════════════════════════════════════════════════════════════════════
# PART 5: Archived Projects
# ════════════════════════════════════════════════════════════════════


class TestArchivedProjects:

    def test_cannot_create_task_in_archived_project(self):
        """Tasks cannot be created in archived projects."""
        # Create and archive a project
        create_resp = api_post("/api/v1/projects", {"title": f"Archived {UNIQUE}"})
        project_id = create_resp.json()["id"]

        api_put(f"/api/v1/projects/{project_id}", {
            "title": f"Archived {UNIQUE}",
            "is_archived": True,
        })

        # Try to create task
        resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Should Fail"})
        assert resp.status_code == 400

    def test_cannot_update_task_in_archived_project(self):
        """Tasks in archived projects cannot be updated."""
        create_resp = api_post("/api/v1/projects", {"title": f"ArchUpd {UNIQUE}"})
        project_id = create_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Pre-archive"})
        task_id = task_resp.json()["id"]

        # Archive the project
        api_put(f"/api/v1/projects/{project_id}", {
            "title": f"ArchUpd {UNIQUE}",
            "is_archived": True,
        })

        # Try to update task
        resp = api_put(f"/api/v1/tasks/{task_id}", {"title": "Should Fail"})
        assert resp.status_code == 400

    def test_can_read_tasks_in_archived_project(self):
        """Tasks in archived projects can still be read."""
        create_resp = api_post("/api/v1/projects", {"title": f"ArchRead {UNIQUE}"})
        project_id = create_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Readable"})
        task_id = task_resp.json()["id"]

        # Archive the project
        api_put(f"/api/v1/projects/{project_id}", {
            "title": f"ArchRead {UNIQUE}",
            "is_archived": True,
        })

        # Can still read tasks
        resp = api_get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Readable"

        # Can still list tasks
        resp = api_get(f"/api/v1/projects/{project_id}/tasks")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 6: Task Filtering and Sorting
# ════════════════════════════════════════════════════════════════════


class TestTaskFiltering:

    @pytest.fixture(autouse=True)
    def setup_project_with_tasks(self, _isolated_test_state):
        """Create a project with various tasks for filtering."""
        resp = api_post("/api/v1/projects", {"title": f"FilterProject {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = resp.json()["id"]

        # Create tasks with different attributes
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Low Priority", "priority": 1, "position": 3.0,
        })
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "High Priority", "priority": 5, "position": 1.0,
        })
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {
            "title": "Done Task", "priority": 2, "done": True, "position": 2.0,
        })

    def test_filter_by_done_true(self):
        """Filter only done tasks."""
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", params={"filter_done": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["done"] is True for t in data)
        assert len(data) >= 1

    def test_filter_by_done_false(self):
        """Filter only undone tasks."""
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", params={"filter_done": "false"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["done"] is False for t in data)
        assert len(data) >= 2

    def test_filter_by_priority(self):
        """Filter tasks with priority >= given value."""
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", params={"filter_priority": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["priority"] >= 3 for t in data)
        assert len(data) >= 1

    def test_sort_by_priority_desc(self):
        """Sort tasks by priority descending."""
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", params={
            "sort_by": "priority", "order_by": "desc",
        })
        assert resp.status_code == 200
        data = resp.json()
        priorities = [t["priority"] for t in data]
        assert priorities == sorted(priorities, reverse=True)

    def test_sort_by_position_asc(self):
        """Sort tasks by position ascending (default)."""
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", params={
            "sort_by": "position", "order_by": "asc",
        })
        assert resp.status_code == 200
        data = resp.json()
        positions = [t["position"] for t in data]
        assert positions == sorted(positions)


# ════════════════════════════════════════════════════════════════════
# PART 7: Labels CRUD
# ════════════════════════════════════════════════════════════════════


class TestLabelsCRUD:

    def test_create_label(self):
        """Create a label."""
        resp = api_post("/api/v1/labels", {
            "title": f"Bug {UNIQUE}",
            "color": "#ff0000",
            "description": "Bug label",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"Bug {UNIQUE}"
        assert data["color"] == "#ff0000"
        assert "id" in data

    def test_list_labels(self):
        """List labels for current user."""
        api_post("/api/v1/labels", {"title": f"ListLabel {UNIQUE}"})

        resp = api_get("/api/v1/labels")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        titles = [l["title"] for l in data]
        assert f"ListLabel {UNIQUE}" in titles

    def test_get_label(self):
        """Get a label by ID."""
        create_resp = api_post("/api/v1/labels", {"title": f"GetLabel {UNIQUE}"})
        label_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/labels/{label_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == f"GetLabel {UNIQUE}"

    def test_update_label(self):
        """Update a label."""
        create_resp = api_post("/api/v1/labels", {"title": f"UpdLabel {UNIQUE}"})
        label_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/labels/{label_id}", {
            "title": f"Updated Label {UNIQUE}",
            "color": "#00ff00",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == f"Updated Label {UNIQUE}"
        assert resp.json()["color"] == "#00ff00"

    def test_delete_label(self):
        """Delete a label."""
        create_resp = api_post("/api/v1/labels", {"title": f"DelLabel {UNIQUE}"})
        label_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/labels/{label_id}")
        assert resp.status_code == 204

        resp = api_get(f"/api/v1/labels/{label_id}")
        assert resp.status_code == 404

    def test_labels_are_user_scoped(self):
        """Users cannot see each other's labels."""
        create_resp = api_post("/api/v1/labels", {"title": f"User1Label {UNIQUE}"})
        label_id = create_resp.json()["id"]

        # User2 cannot see user1's label
        resp = api_get(f"/api/v1/labels/{label_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

        # User2's label list doesn't include user1's labels
        resp = api_get("/api/v1/labels", headers=USER2_HEADERS)
        ids = [l["id"] for l in resp.json()]
        assert label_id not in ids


# ════════════════════════════════════════════════════════════════════
# PART 8: Task Labels
# ════════════════════════════════════════════════════════════════════


class TestTaskLabels:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create project, task, and label."""
        proj_resp = api_post("/api/v1/projects", {"title": f"LabelProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Labeled Task"})
        self.task_id = task_resp.json()["id"]

        label_resp = api_post("/api/v1/labels", {"title": f"Attach {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.label_id = label_resp.json()["id"]

    def test_attach_label_to_task(self):
        """Attach a label to a task."""
        resp = api_post(f"/api/v1/tasks/{self.task_id}/labels", {"label_id": self.label_id})
        assert resp.status_code == 201

        # Verify label appears on task
        task_resp = api_get(f"/api/v1/tasks/{self.task_id}")
        labels = task_resp.json()["labels"]
        assert any(l["id"] == self.label_id for l in labels)

    def test_detach_label_from_task(self):
        """Detach a label from a task."""
        api_post(f"/api/v1/tasks/{self.task_id}/labels", {"label_id": self.label_id})

        resp = api_delete(f"/api/v1/tasks/{self.task_id}/labels/{self.label_id}")
        assert resp.status_code == 204

        # Verify label removed from task
        task_resp = api_get(f"/api/v1/tasks/{self.task_id}")
        labels = task_resp.json()["labels"]
        assert not any(l["id"] == self.label_id for l in labels)

    def test_cannot_attach_other_users_label(self):
        """Cannot attach a label owned by another user."""
        # Create a label as user2
        label2_resp = api_post("/api/v1/labels", {"title": f"User2Label {UNIQUE}"}, headers=USER2_HEADERS)
        label2_id = label2_resp.json()["id"]

        # User1 tries to attach user2's label
        resp = api_post(f"/api/v1/tasks/{self.task_id}/labels", {"label_id": label2_id})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 9: Task Assignees
# ════════════════════════════════════════════════════════════════════


class TestTaskAssignees:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create project and task, add user2 as member."""
        proj_resp = api_post("/api/v1/projects", {"title": f"AssignProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

        # Ensure user2 exists
        api_get("/api/v1/projects", headers=USER2_HEADERS)

        # Add user2 as editor
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        task_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Assign Task"})
        self.task_id = task_resp.json()["id"]

    def test_assign_user_to_task(self):
        """Assign a project member to a task."""
        resp = api_post(f"/api/v1/tasks/{self.task_id}/assignees", {"user_id": USER2_ID})
        assert resp.status_code == 201

        # Verify assignee on task
        task_resp = api_get(f"/api/v1/tasks/{self.task_id}")
        assignees = task_resp.json()["assignees"]
        assert any(a["id"] == USER2_ID for a in assignees)

    def test_unassign_user_from_task(self):
        """Unassign a user from a task."""
        api_post(f"/api/v1/tasks/{self.task_id}/assignees", {"user_id": USER2_ID})

        resp = api_delete(f"/api/v1/tasks/{self.task_id}/assignees/{USER2_ID}")
        assert resp.status_code == 204

        # Verify unassigned
        task_resp = api_get(f"/api/v1/tasks/{self.task_id}")
        assignees = task_resp.json()["assignees"]
        assert not any(a["id"] == USER2_ID for a in assignees)

    def test_cannot_assign_non_member(self):
        """Cannot assign a user who is not a project member."""
        # User3 is not a member
        api_get("/api/v1/projects", headers=USER3_HEADERS)
        resp = api_post(f"/api/v1/tasks/{self.task_id}/assignees", {"user_id": USER3_ID})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 10: Task Comments
# ════════════════════════════════════════════════════════════════════


class TestTaskComments:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create project and task."""
        proj_resp = api_post("/api/v1/projects", {"title": f"CommentProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Comment Task"})
        self.task_id = task_resp.json()["id"]

    def test_create_comment(self):
        """Create a comment on a task."""
        resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "First comment"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["comment"] == "First comment"
        assert data["author_id"] == USER1_ID
        assert "id" in data
        assert "created_at" in data

    def test_list_comments(self):
        """List comments on a task."""
        api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Comment A"})
        api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Comment B"})

        resp = api_get(f"/api/v1/tasks/{self.task_id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_comment(self):
        """Get a single comment."""
        create_resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Get me"})
        comment_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/tasks/{self.task_id}/comments/{comment_id}")
        assert resp.status_code == 200
        assert resp.json()["comment"] == "Get me"

    def test_update_comment(self):
        """Update a comment."""
        create_resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Original"})
        comment_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/tasks/{self.task_id}/comments/{comment_id}", {"comment": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["comment"] == "Updated"

    def test_delete_comment(self):
        """Delete a comment."""
        create_resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Delete me"})
        comment_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/tasks/{self.task_id}/comments/{comment_id}")
        assert resp.status_code == 204

        resp = api_get(f"/api/v1/tasks/{self.task_id}/comments/{comment_id}")
        assert resp.status_code == 404

    def test_only_author_can_update_comment(self):
        """Only the comment author can update their comment."""
        # Add user2 as editor
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        # User1 creates comment
        create_resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Mine"})
        comment_id = create_resp.json()["id"]

        # User2 tries to update
        resp = api_put(
            f"/api/v1/tasks/{self.task_id}/comments/{comment_id}",
            {"comment": "Hijacked"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_only_author_can_delete_comment(self):
        """Only the comment author can delete their comment."""
        # Add user2 as editor
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        create_resp = api_post(f"/api/v1/tasks/{self.task_id}/comments", {"comment": "Protected"})
        comment_id = create_resp.json()["id"]

        resp = api_delete(
            f"/api/v1/tasks/{self.task_id}/comments/{comment_id}",
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 11: Task Relations
# ════════════════════════════════════════════════════════════════════


class TestTaskRelations:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create project with two tasks."""
        proj_resp = api_post("/api/v1/projects", {"title": f"RelProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

        task1_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Task A"})
        self.task_a_id = task1_resp.json()["id"]

        task2_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Task B"})
        self.task_b_id = task2_resp.json()["id"]

    def test_create_relation(self):
        """Create a relation between two tasks."""
        resp = api_post(f"/api/v1/tasks/{self.task_a_id}/relations", {
            "other_task_id": self.task_b_id,
            "relation_kind": "blocks",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == self.task_a_id
        assert data["other_task_id"] == self.task_b_id
        assert data["relation_kind"] == "blocks"

    def test_relation_is_bidirectional(self):
        """Creating 'A blocks B' also creates 'B blocked_by A'."""
        api_post(f"/api/v1/tasks/{self.task_a_id}/relations", {
            "other_task_id": self.task_b_id,
            "relation_kind": "blocks",
        })

        # Check task A has "blocks" relation
        task_a = api_get(f"/api/v1/tasks/{self.task_a_id}").json()
        assert "blocks" in task_a["relations"]
        assert self.task_b_id in task_a["relations"]["blocks"]

        # Check task B has "blocked_by" relation
        task_b = api_get(f"/api/v1/tasks/{self.task_b_id}").json()
        assert "blocked_by" in task_b["relations"]
        assert self.task_a_id in task_b["relations"]["blocked_by"]

    def test_delete_relation_removes_both_sides(self):
        """Deleting one side of a relation removes both sides."""
        api_post(f"/api/v1/tasks/{self.task_a_id}/relations", {
            "other_task_id": self.task_b_id,
            "relation_kind": "blocks",
        })

        # Delete from A's side
        resp = api_delete(f"/api/v1/tasks/{self.task_a_id}/relations/blocks/{self.task_b_id}")
        assert resp.status_code == 204

        # Both sides should be gone
        task_a = api_get(f"/api/v1/tasks/{self.task_a_id}").json()
        task_b = api_get(f"/api/v1/tasks/{self.task_b_id}").json()

        blocks_a = task_a["relations"].get("blocks", [])
        blocked_b = task_b["relations"].get("blocked_by", [])
        assert self.task_b_id not in blocks_a
        assert self.task_a_id not in blocked_b

    def test_relation_related_is_symmetric(self):
        """'related' relation is symmetric (same kind on both sides)."""
        api_post(f"/api/v1/tasks/{self.task_a_id}/relations", {
            "other_task_id": self.task_b_id,
            "relation_kind": "related",
        })

        task_a = api_get(f"/api/v1/tasks/{self.task_a_id}").json()
        task_b = api_get(f"/api/v1/tasks/{self.task_b_id}").json()

        assert self.task_b_id in task_a["relations"].get("related", [])
        assert self.task_a_id in task_b["relations"].get("related", [])


# ════════════════════════════════════════════════════════════════════
# PART 12: Project Members
# ════════════════════════════════════════════════════════════════════


class TestProjectMembers:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create a project."""
        proj_resp = api_post("/api/v1/projects", {"title": f"MemberProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]
        # Ensure user2 exists
        api_get("/api/v1/projects", headers=USER2_HEADERS)

    def test_add_member(self):
        """Add a member to a project."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == USER2_ID
        assert data["role"] == "editor"

    def test_list_members(self):
        """List project members (includes owner)."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_get(f"/api/v1/projects/{self.project_id}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should include owner and user2
        user_ids = [m["user_id"] for m in data]
        assert USER1_ID in user_ids
        assert USER2_ID in user_ids

    def test_update_member_role(self):
        """Update a member's role."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_put(f"/api/v1/projects/{self.project_id}/members/{USER2_ID}", {
            "role": "editor",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "editor"

    def test_remove_member(self):
        """Remove a member from a project."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        resp = api_delete(f"/api/v1/projects/{self.project_id}/members/{USER2_ID}")
        assert resp.status_code == 204

        # User2 can no longer access
        resp = api_get(f"/api/v1/projects/{self.project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_only_owner_can_manage_members(self):
        """Only the owner can add/remove members."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        # User2 (editor) tries to add user3
        api_get("/api/v1/projects", headers=USER3_HEADERS)
        resp = api_post(
            f"/api/v1/projects/{self.project_id}/members",
            {"user_id": USER3_ID, "role": "viewer"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_viewer_cannot_create_tasks(self):
        """Viewers cannot create tasks."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_post(
            f"/api/v1/projects/{self.project_id}/tasks",
            {"title": "Should Fail"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_viewer_can_read_tasks(self):
        """Viewers can read tasks."""
        api_post(f"/api/v1/projects/{self.project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        # Owner creates task
        api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Viewable"})

        # Viewer can list tasks
        resp = api_get(f"/api/v1/projects/{self.project_id}/tasks", headers=USER2_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ════════════════════════════════════════════════════════════════════
# PART 13: Buckets (Kanban)
# ════════════════════════════════════════════════════════════════════


class TestBuckets:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create a project."""
        proj_resp = api_post("/api/v1/projects", {"title": f"BucketProj {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

    def test_create_bucket(self):
        """Create a bucket in a project."""
        resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {
            "title": "To Do",
            "position": 1.0,
            "limit": 5,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "To Do"
        assert data["position"] == 1.0
        assert data["limit"] == 5
        assert data["project_id"] == self.project_id

    def test_list_buckets(self):
        """List buckets in a project."""
        api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Backlog"})
        api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Done"})

        resp = api_get(f"/api/v1/projects/{self.project_id}/buckets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_bucket(self):
        """Get a bucket by ID."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Get Me"})
        bucket_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/projects/{self.project_id}/buckets/{bucket_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Me"

    def test_update_bucket(self):
        """Update a bucket."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Old Title"})
        bucket_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/projects/{self.project_id}/buckets/{bucket_id}", {
            "title": "New Title",
            "limit": 10,
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        assert resp.json()["limit"] == 10

    def test_delete_empty_bucket(self):
        """Delete a bucket with no tasks."""
        create_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Empty"})
        bucket_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/projects/{self.project_id}/buckets/{bucket_id}")
        assert resp.status_code == 204

    def test_cannot_delete_bucket_with_tasks(self):
        """Cannot delete a bucket that has tasks in it."""
        bucket_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {"title": "Has Tasks"})
        bucket_id = bucket_resp.json()["id"]

        # Create a task and move it to this bucket
        task_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "In Bucket"})
        task_id = task_resp.json()["id"]
        api_put(f"/api/v1/tasks/{task_id}/bucket", {"bucket_id": bucket_id})

        # Try to delete bucket
        resp = api_delete(f"/api/v1/projects/{self.project_id}/buckets/{bucket_id}")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 14: Task Buckets (Move tasks between buckets)
# ════════════════════════════════════════════════════════════════════


class TestTaskBuckets:

    @pytest.fixture(autouse=True)
    def setup(self, _isolated_test_state):
        """Create project, buckets, and task."""
        proj_resp = api_post("/api/v1/projects", {"title": f"MoveBucket {UNIQUE} {uuid.uuid4().hex[:4]}"})
        self.project_id = proj_resp.json()["id"]

        bucket1_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {
            "title": "Bucket 1", "limit": 2,
        })
        self.bucket1_id = bucket1_resp.json()["id"]

        bucket2_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {
            "title": "Bucket 2", "limit": 1,
        })
        self.bucket2_id = bucket2_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Move Me"})
        self.task_id = task_resp.json()["id"]

    def test_move_task_to_bucket(self):
        """Move a task to a bucket."""
        resp = api_put(f"/api/v1/tasks/{self.task_id}/bucket", {"bucket_id": self.bucket1_id})
        assert resp.status_code == 200
        assert resp.json()["bucket_id"] == self.bucket1_id

    def test_bucket_limit_enforcement(self):
        """Cannot move task to a full bucket."""
        # bucket2 has limit=1, fill it
        task2_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": "Fill"})
        task2_id = task2_resp.json()["id"]
        api_put(f"/api/v1/tasks/{task2_id}/bucket", {"bucket_id": self.bucket2_id})

        # Try to move another task to the full bucket
        resp = api_put(f"/api/v1/tasks/{self.task_id}/bucket", {"bucket_id": self.bucket2_id})
        assert resp.status_code == 400

    def test_move_task_between_buckets(self):
        """Move a task from one bucket to another."""
        # Move to bucket1
        api_put(f"/api/v1/tasks/{self.task_id}/bucket", {"bucket_id": self.bucket1_id})

        # Move to bucket2 (empty now, limit=1, should work)
        resp = api_put(f"/api/v1/tasks/{self.task_id}/bucket", {"bucket_id": self.bucket2_id})
        assert resp.status_code == 200
        assert resp.json()["bucket_id"] == self.bucket2_id

    def test_unlimited_bucket(self):
        """Bucket with limit=0 accepts unlimited tasks."""
        # Create unlimited bucket
        bucket_resp = api_post(f"/api/v1/projects/{self.project_id}/buckets", {
            "title": "Unlimited", "limit": 0,
        })
        unlimited_id = bucket_resp.json()["id"]

        # Add multiple tasks
        for i in range(5):
            t_resp = api_post(f"/api/v1/projects/{self.project_id}/tasks", {"title": f"Task {i}"})
            resp = api_put(f"/api/v1/tasks/{t_resp.json()['id']}/bucket", {"bucket_id": unlimited_id})
            assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 15: Filters (Saved Filters)
# ════════════════════════════════════════════════════════════════════


class TestFilters:

    def test_create_filter(self):
        """Create a saved filter."""
        resp = api_post("/api/v1/filters", {
            "title": f"High Priority {UNIQUE}",
            "filter_query": "priority>=3",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"High Priority {UNIQUE}"
        assert data["filter_query"] == "priority>=3"
        assert "id" in data

    def test_list_filters(self):
        """List saved filters."""
        api_post("/api/v1/filters", {"title": f"ListFilter {UNIQUE}", "filter_query": "done=true"})

        resp = api_get("/api/v1/filters")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        titles = [f["title"] for f in data]
        assert f"ListFilter {UNIQUE}" in titles

    def test_get_filter(self):
        """Get a filter by ID."""
        create_resp = api_post("/api/v1/filters", {"title": f"GetFilter {UNIQUE}", "filter_query": "x=1"})
        filter_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/filters/{filter_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == f"GetFilter {UNIQUE}"

    def test_update_filter(self):
        """Update a saved filter."""
        create_resp = api_post("/api/v1/filters", {"title": f"UpdFilter {UNIQUE}", "filter_query": "old"})
        filter_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/filters/{filter_id}", {
            "title": f"Updated Filter {UNIQUE}",
            "filter_query": "new_query",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == f"Updated Filter {UNIQUE}"
        assert resp.json()["filter_query"] == "new_query"

    def test_delete_filter(self):
        """Delete a saved filter."""
        create_resp = api_post("/api/v1/filters", {"title": f"DelFilter {UNIQUE}", "filter_query": "x"})
        filter_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/filters/{filter_id}")
        assert resp.status_code == 204

        resp = api_get(f"/api/v1/filters/{filter_id}")
        assert resp.status_code == 404

    def test_filters_are_user_scoped(self):
        """Users cannot see each other's filters."""
        create_resp = api_post("/api/v1/filters", {"title": f"Private {UNIQUE}", "filter_query": "mine"})
        filter_id = create_resp.json()["id"]

        # User2 cannot see it
        resp = api_get(f"/api/v1/filters/{filter_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

        resp = api_get("/api/v1/filters", headers=USER2_HEADERS)
        ids = [f["id"] for f in resp.json()]
        assert filter_id not in ids


# ════════════════════════════════════════════════════════════════════
# PART 16: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_project_cascades_tasks(self):
        """Deleting a project deletes all its tasks."""
        proj_resp = api_post("/api/v1/projects", {"title": f"CascadeProj {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Cascade Task"})
        task_id = task_resp.json()["id"]

        api_delete(f"/api/v1/projects/{project_id}")

        # Task should be gone
        resp = api_get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 404

    def test_delete_project_cascades_buckets(self):
        """Deleting a project deletes all its buckets."""
        proj_resp = api_post("/api/v1/projects", {"title": f"CascadeBucket {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        bucket_resp = api_post(f"/api/v1/projects/{project_id}/buckets", {"title": "Cascade Bucket"})
        bucket_id = bucket_resp.json()["id"]

        api_delete(f"/api/v1/projects/{project_id}")

        # Bucket endpoint should 404
        resp = api_get(f"/api/v1/projects/{project_id}/buckets/{bucket_id}")
        assert resp.status_code == 404

    def test_delete_task_cascades_comments(self):
        """Deleting a task deletes all its comments."""
        proj_resp = api_post("/api/v1/projects", {"title": f"CascadeComment {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Has Comments"})
        task_id = task_resp.json()["id"]

        comment_resp = api_post(f"/api/v1/tasks/{task_id}/comments", {"comment": "Will be deleted"})
        comment_id = comment_resp.json()["id"]

        api_delete(f"/api/v1/tasks/{task_id}")

        # Comment should be gone (task is gone, so this returns 404)
        resp = api_get(f"/api/v1/tasks/{task_id}/comments/{comment_id}")
        assert resp.status_code == 404

    def test_delete_label_detaches_from_tasks(self):
        """Deleting a label removes it from all tasks."""
        proj_resp = api_post("/api/v1/projects", {"title": f"LabelCascade {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Labeled"})
        task_id = task_resp.json()["id"]

        label_resp = api_post("/api/v1/labels", {"title": f"TempLabel {UNIQUE}"})
        label_id = label_resp.json()["id"]

        api_post(f"/api/v1/tasks/{task_id}/labels", {"label_id": label_id})

        # Delete the label
        api_delete(f"/api/v1/labels/{label_id}")

        # Task should no longer have the label
        task = api_get(f"/api/v1/tasks/{task_id}").json()
        assert not any(l["id"] == label_id for l in task["labels"])


# ════════════════════════════════════════════════════════════════════
# PART 17: Edge Cases and Validation
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_create_task_in_nonexistent_project(self):
        """Creating a task in a non-existent project returns 404."""
        resp = api_post("/api/v1/projects/99999/tasks", {"title": "No Project"})
        assert resp.status_code == 404

    def test_create_task_missing_title(self):
        """Task title is required."""
        proj_resp = api_post("/api/v1/projects", {"title": f"NoTitle {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"description": "no title"})
        assert resp.status_code == 400

    def test_negative_priority_returns_400(self):
        """Negative priority is invalid."""
        proj_resp = api_post("/api/v1/projects", {"title": f"NegPri {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/tasks", {
            "title": "Bad", "priority": -1,
        })
        assert resp.status_code == 400

    def test_percent_done_negative_returns_400(self):
        """Negative percent_done is invalid."""
        proj_resp = api_post("/api/v1/projects", {"title": f"NegPct {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/tasks", {
            "title": "Bad", "percent_done": -0.1,
        })
        assert resp.status_code == 400

    def test_invalid_relation_kind_returns_400(self):
        """Invalid relation_kind should return 400."""
        proj_resp = api_post("/api/v1/projects", {"title": f"BadRel {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "T1"})
        task_id = task_resp.json()["id"]

        task2_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "T2"})
        task2_id = task2_resp.json()["id"]

        resp = api_post(f"/api/v1/tasks/{task_id}/relations", {
            "other_task_id": task2_id,
            "relation_kind": "invalid_kind",
        })
        assert resp.status_code == 400

    def test_move_task_to_bucket_in_different_project(self):
        """Cannot move a task to a bucket in a different project."""
        proj1_resp = api_post("/api/v1/projects", {"title": f"Proj1 {UNIQUE}"})
        proj1_id = proj1_resp.json()["id"]

        proj2_resp = api_post("/api/v1/projects", {"title": f"Proj2 {UNIQUE}"})
        proj2_id = proj2_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{proj1_id}/tasks", {"title": "Wrong Bucket"})
        task_id = task_resp.json()["id"]

        bucket_resp = api_post(f"/api/v1/projects/{proj2_id}/buckets", {"title": "Other Bucket"})
        bucket_id = bucket_resp.json()["id"]

        resp = api_put(f"/api/v1/tasks/{task_id}/bucket", {"bucket_id": bucket_id})
        assert resp.status_code == 400

    def test_project_member_appears_in_list(self):
        """Projects where user is a member appear in their project list."""
        proj_resp = api_post("/api/v1/projects", {"title": f"MemberList {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        # Add user2
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "editor",
        })

        # User2's project list should include this project
        resp = api_get("/api/v1/projects", headers=USER2_HEADERS)
        ids = [p["id"] for p in resp.json()]
        assert project_id in ids

    def test_viewer_cannot_update_task(self):
        """Viewers cannot update tasks."""
        proj_resp = api_post("/api/v1/projects", {"title": f"ViewerUpd {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Protected"})
        task_id = task_resp.json()["id"]

        # Add user2 as viewer
        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_put(f"/api/v1/tasks/{task_id}", {"title": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_viewer_cannot_delete_task(self):
        """Viewers cannot delete tasks."""
        proj_resp = api_post("/api/v1/projects", {"title": f"ViewerDel {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "Protected"})
        task_id = task_resp.json()["id"]

        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_delete(f"/api/v1/tasks/{task_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_viewer_cannot_create_comment(self):
        """Viewers cannot create comments."""
        proj_resp = api_post("/api/v1/projects", {"title": f"ViewerCmt {UNIQUE}"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post(f"/api/v1/projects/{project_id}/tasks", {"title": "No Comment"})
        task_id = task_resp.json()["id"]

        api_get("/api/v1/projects", headers=USER2_HEADERS)
        api_post(f"/api/v1/projects/{project_id}/members", {
            "user_id": USER2_ID,
            "role": "viewer",
        })

        resp = api_post(
            f"/api/v1/tasks/{task_id}/comments",
            {"comment": "Not allowed"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403
