"""
BackendForge — Correctness Tests for Leantime Task (Goal-focused Project Management)

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

RUN_ID = uuid.uuid4()
ORG_ID = str(uuid.uuid4())
ORG2_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Org-Id": ORG_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-User-Id": USER2_ID,
    "X-Org-Id": ORG_ID,
    "Content-Type": "application/json",
}

HEADERS_ORG2 = {
    "X-User-Id": USER_ID,
    "X-Org-Id": ORG2_ID,
    "Content-Type": "application/json",
}


@pytest.fixture(autouse=True)
def isolate_test_identity(request):
    """Give every item a fresh namespace while preserving within-test identities."""
    global ORG_ID, ORG2_ID, USER_ID, USER2_ID

    node_id = request.node.nodeid
    ORG_ID = str(uuid.uuid5(RUN_ID, f"{node_id}:org"))
    ORG2_ID = str(uuid.uuid5(RUN_ID, f"{node_id}:other-org"))
    USER_ID = str(uuid.uuid5(RUN_ID, f"{node_id}:user"))
    USER2_ID = str(uuid.uuid5(RUN_ID, f"{node_id}:other-user"))
    HEADERS.update({"X-User-Id": USER_ID, "X-Org-Id": ORG_ID})
    HEADERS_USER2.update({"X-User-Id": USER2_ID, "X-Org-Id": ORG_ID})
    HEADERS_ORG2.update({"X-User-Id": USER_ID, "X-Org-Id": ORG2_ID})


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health Check
# ════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_no_auth(self):
        """Health endpoint requires no auth."""
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_missing_user_id(self):
        """Missing X-User-Id returns 401."""
        headers = {"X-Org-Id": ORG_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/clients", headers=headers, timeout=30)
        assert resp.status_code == 401

    def test_missing_org_id(self):
        """Missing X-Org-Id returns 401."""
        headers = {"X-User-Id": USER_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/clients", headers=headers, timeout=30)
        assert resp.status_code == 401

    def test_empty_user_id(self):
        """Empty X-User-Id returns 401."""
        headers = {"X-User-Id": "", "X-Org-Id": ORG_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/clients", headers=headers, timeout=30)
        assert resp.status_code == 401

    def test_empty_org_id(self):
        """Empty X-Org-Id returns 401."""
        headers = {"X-User-Id": USER_ID, "X-Org-Id": "", "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/clients", headers=headers, timeout=30)
        assert resp.status_code == 401

    def test_both_missing(self):
        """Missing both headers returns 401."""
        resp = requests.get(f"{BASE_URL}/projects", headers={"Content-Type": "application/json"}, timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 3: Clients CRUD
# ════════════════════════════════════════════════════════════════════

class TestClients:
    def test_create_client(self):
        resp = api_post("/clients", {"name": "Acme Corp", "email": "info@acme.com", "phone": "555-1234", "company": "Acme"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["email"] == "info@acme.com"
        assert data["phone"] == "555-1234"
        assert data["company"] == "Acme"
        assert "id" in data
        assert "created_at" in data

    def test_list_clients(self):
        # Create a client first
        api_post("/clients", {"name": f"ListClient-{uuid.uuid4().hex[:8]}"})
        resp = api_get("/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_client(self):
        resp = api_post("/clients", {"name": "GetClient"})
        client_id = resp.json()["id"]
        resp = api_get(f"/clients/{client_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetClient"

    def test_update_client(self):
        resp = api_post("/clients", {"name": "OldName"})
        client_id = resp.json()["id"]
        resp = api_put(f"/clients/{client_id}", {"name": "NewName", "email": "new@test.com"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"
        assert resp.json()["email"] == "new@test.com"

    def test_delete_client(self):
        resp = api_post("/clients", {"name": "ToDelete"})
        client_id = resp.json()["id"]
        resp = api_delete(f"/clients/{client_id}")
        assert resp.status_code == 204
        resp = api_get(f"/clients/{client_id}")
        assert resp.status_code == 404

    def test_get_nonexistent_client(self):
        resp = api_get(f"/clients/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_client_org_isolation(self):
        """Client created in org1 not visible in org2."""
        resp = api_post("/clients", {"name": "OrgIsolatedClient"})
        client_id = resp.json()["id"]
        resp = api_get(f"/clients/{client_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Projects CRUD
# ════════════════════════════════════════════════════════════════════

class TestProjects:
    def test_create_project(self):
        resp = api_post("/projects", {"name": "Project Alpha", "description": "Test project"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Project Alpha"
        assert data["description"] == "Test project"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data

    def test_create_project_with_client(self):
        client_resp = api_post("/clients", {"name": "ProjectClient"})
        client_id = client_resp.json()["id"]
        resp = api_post("/projects", {"name": "ClientProject", "client_id": client_id})
        assert resp.status_code == 201
        assert resp.json()["client_id"] == client_id

    def test_create_project_with_invalid_client(self):
        resp = api_post("/projects", {"name": "BadClient", "client_id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_list_projects(self):
        api_post("/projects", {"name": f"ListProject-{uuid.uuid4().hex[:8]}"})
        resp = api_get("/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_projects_filter_status(self):
        api_post("/projects", {"name": "ActiveProject", "status": "active"})
        api_post("/projects", {"name": "ArchivedProject", "status": "archived"})
        resp = api_get("/projects", params={"status": "active"})
        assert resp.status_code == 200
        for p in resp.json():
            assert p["status"] == "active"

    def test_get_project(self):
        resp = api_post("/projects", {"name": "GetProject"})
        project_id = resp.json()["id"]
        resp = api_get(f"/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetProject"
        assert "progress" in resp.json()

    def test_update_project(self):
        resp = api_post("/projects", {"name": "OldProject"})
        project_id = resp.json()["id"]
        resp = api_put(f"/projects/{project_id}", {"name": "UpdatedProject", "description": "updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "UpdatedProject"

    def test_delete_project(self):
        resp = api_post("/projects", {"name": "DeleteMe"})
        project_id = resp.json()["id"]
        resp = api_delete(f"/projects/{project_id}")
        assert resp.status_code == 204
        resp = api_get(f"/projects/{project_id}")
        assert resp.status_code == 404

    def test_project_progress_no_milestones(self):
        """Project with no milestones has progress 0."""
        resp = api_post("/projects", {"name": "NoMilestones"})
        project_id = resp.json()["id"]
        resp = api_get(f"/projects/{project_id}")
        assert resp.json()["progress"] == 0

    def test_project_org_isolation(self):
        resp = api_post("/projects", {"name": "OrgProject"})
        project_id = resp.json()["id"]
        resp = api_get(f"/projects/{project_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Goals CRUD + Progress
# ════════════════════════════════════════════════════════════════════

class TestGoals:
    def _create_project(self):
        resp = api_post("/projects", {"name": f"GoalProject-{uuid.uuid4().hex[:8]}"})
        return resp.json()["id"]

    def test_create_goal(self):
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Increase Revenue",
            "description": "Q1 target",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 1000,
            "current_value": 250
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Increase Revenue"
        assert data["metric_type"] == "number"
        assert data["target_value"] == 1000
        assert data["current_value"] == 250
        assert "id" in data
        assert "progress" in data

    def test_create_goal_invalid_project(self):
        resp = api_post("/goals", {
            "title": "Bad Goal",
            "project_id": str(uuid.uuid4()),
            "metric_type": "number",
            "target_value": 100
        })
        assert resp.status_code == 404

    def test_goal_progress_number(self):
        """Number metric: progress = current/target * 100."""
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Number Goal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 200,
            "current_value": 100
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["progress"] == 50.0

    def test_goal_progress_percent(self):
        """Percent metric: progress = current/target * 100."""
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Percent Goal",
            "project_id": project_id,
            "metric_type": "percent",
            "target_value": 80,
            "current_value": 40
        })
        assert resp.status_code == 201
        assert resp.json()["progress"] == 50.0

    def test_goal_progress_boolean(self):
        """Boolean metric: progress = 100 if current_value >= 1, else 0."""
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Boolean Goal Done",
            "project_id": project_id,
            "metric_type": "boolean",
            "target_value": 1,
            "current_value": 1
        })
        assert resp.json()["progress"] == 100.0

        resp = api_post("/goals", {
            "title": "Boolean Goal Not Done",
            "project_id": project_id,
            "metric_type": "boolean",
            "target_value": 1,
            "current_value": 0
        })
        assert resp.json()["progress"] == 0.0

    def test_goal_progress_zero_target(self):
        """target_value=0 means progress=0."""
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Zero Target",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 0,
            "current_value": 50
        })
        assert resp.json()["progress"] == 0.0

    def test_goal_progress_clamped(self):
        """Progress should be clamped to 0-100."""
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "Over Target",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "current_value": 150
        })
        assert resp.json()["progress"] == 100.0

    def test_goal_hierarchy_progress(self):
        """Parent goal progress = average of children's progress."""
        project_id = self._create_project()
        # Create parent goal
        parent_resp = api_post("/goals", {
            "title": "Parent Goal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "current_value": 10
        })
        parent_id = parent_resp.json()["id"]

        # Create child goals
        api_post("/goals", {
            "title": "Child 1",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "current_value": 50,
            "parent_goal_id": parent_id
        })
        api_post("/goals", {
            "title": "Child 2",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "current_value": 100,
            "parent_goal_id": parent_id
        })

        # Parent progress should be average of children (50 + 100) / 2 = 75
        resp = api_get(f"/goals/{parent_id}")
        assert resp.status_code == 200
        assert resp.json()["progress"] == 75.0

    def test_list_goals_filter_project(self):
        project_id = self._create_project()
        api_post("/goals", {
            "title": "Filtered Goal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100
        })
        other_project_id = self._create_project()
        api_post("/goals", {
            "title": "Other Project Goal",
            "project_id": other_project_id,
            "metric_type": "number",
            "target_value": 100
        })
        resp = api_get("/goals", params={"project_id": project_id})
        assert resp.status_code == 200
        for g in resp.json():
            assert g["project_id"] == project_id

    def test_update_goal(self):
        project_id = self._create_project()
        resp = api_post("/goals", {
            "title": "UpdateGoal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100
        })
        goal_id = resp.json()["id"]
        resp = api_put(f"/goals/{goal_id}", {"current_value": 75})
        assert resp.status_code == 200
        assert resp.json()["current_value"] == 75
        assert resp.json()["progress"] == 75.0

    def test_delete_goal_orphans_children(self):
        """Deleting a parent goal sets children's parent_goal_id to null."""
        project_id = self._create_project()
        parent_resp = api_post("/goals", {
            "title": "ParentToDelete",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100
        })
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/goals", {
            "title": "ChildGoal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "parent_goal_id": parent_id
        })
        child_id = child_resp.json()["id"]

        # Delete parent
        resp = api_delete(f"/goals/{parent_id}")
        assert resp.status_code == 204

        # Child should still exist with null parent
        resp = api_get(f"/goals/{child_id}")
        assert resp.status_code == 200
        assert resp.json()["parent_goal_id"] is None

    def test_create_goal_with_parent_different_project(self):
        """Parent goal must be in same project."""
        project1 = self._create_project()
        project2 = self._create_project()
        parent_resp = api_post("/goals", {
            "title": "Parent",
            "project_id": project1,
            "metric_type": "number",
            "target_value": 100
        })
        parent_id = parent_resp.json()["id"]
        resp = api_post("/goals", {
            "title": "Child Different Project",
            "project_id": project2,
            "metric_type": "number",
            "target_value": 100,
            "parent_goal_id": parent_id
        })
        # Parent not found in same project -> 404
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Milestones CRUD + Progress
# ════════════════════════════════════════════════════════════════════

class TestMilestones:
    def _create_project(self):
        resp = api_post("/projects", {"name": f"MilestoneProject-{uuid.uuid4().hex[:8]}"})
        return resp.json()["id"]

    def test_create_milestone(self):
        project_id = self._create_project()
        resp = api_post("/milestones", {
            "title": "v1.0 Release",
            "project_id": project_id,
            "due_date": "2025-06-01",
            "sort_order": 1
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "v1.0 Release"
        assert data["status"] == "open"
        assert data["sort_order"] == 1
        assert data["progress"] == 0
        assert "id" in data

    def test_create_milestone_invalid_project(self):
        resp = api_post("/milestones", {
            "title": "Bad Milestone",
            "project_id": str(uuid.uuid4())
        })
        assert resp.status_code == 404

    def test_list_milestones_ordered_by_sort(self):
        project_id = self._create_project()
        api_post("/milestones", {"title": "Second", "project_id": project_id, "sort_order": 2})
        api_post("/milestones", {"title": "First", "project_id": project_id, "sort_order": 1})
        api_post("/milestones", {"title": "Third", "project_id": project_id, "sort_order": 3})

        resp = api_get("/milestones", params={"project_id": project_id})
        assert resp.status_code == 200
        milestones = resp.json()
        sort_orders = [m["sort_order"] for m in milestones]
        assert sort_orders == sorted(sort_orders)

    def test_milestone_progress(self):
        """Progress = done tasks / total tasks * 100."""
        project_id = self._create_project()
        ms_resp = api_post("/milestones", {"title": "Progress MS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]

        # Create 4 tasks, 2 done
        for i in range(2):
            resp = api_post("/tasks", {
                "title": f"Done Task {i}",
                "project_id": project_id,
                "milestone_id": ms_id,
                "status": "new"
            })
            task_id = resp.json()["id"]
            api_put(f"/tasks/{task_id}", {"status": "in_progress"})
            api_put(f"/tasks/{task_id}", {"status": "done"})

        for i in range(2):
            api_post("/tasks", {
                "title": f"Open Task {i}",
                "project_id": project_id,
                "milestone_id": ms_id
            })

        resp = api_get(f"/milestones/{ms_id}")
        assert resp.status_code == 200
        assert resp.json()["progress"] == 50.0

    def test_milestone_progress_no_tasks(self):
        project_id = self._create_project()
        ms_resp = api_post("/milestones", {"title": "Empty MS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        resp = api_get(f"/milestones/{ms_id}")
        assert resp.json()["progress"] == 0

    def test_delete_milestone_with_tasks(self):
        """Cannot delete milestone that has tasks."""
        project_id = self._create_project()
        ms_resp = api_post("/milestones", {"title": "ProtectedMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        api_post("/tasks", {"title": "Blocking Task", "project_id": project_id, "milestone_id": ms_id})

        resp = api_delete(f"/milestones/{ms_id}")
        assert resp.status_code == 409

    def test_delete_milestone_empty(self):
        """Can delete milestone with no tasks."""
        project_id = self._create_project()
        ms_resp = api_post("/milestones", {"title": "EmptyMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        resp = api_delete(f"/milestones/{ms_id}")
        assert resp.status_code == 204

    def test_update_milestone(self):
        project_id = self._create_project()
        ms_resp = api_post("/milestones", {"title": "OldMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        resp = api_put(f"/milestones/{ms_id}", {"title": "NewMS", "status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "NewMS"
        assert resp.json()["status"] == "in_progress"


# ════════════════════════════════════════════════════════════════════
# PART 7: Tasks CRUD + Status Transitions
# ════════════════════════════════════════════════════════════════════

class TestTasks:
    def _create_project(self):
        resp = api_post("/projects", {"name": f"TaskProject-{uuid.uuid4().hex[:8]}"})
        return resp.json()["id"]

    def test_create_task(self):
        project_id = self._create_project()
        resp = api_post("/tasks", {
            "title": "Implement login",
            "description": "Add OAuth",
            "project_id": project_id,
            "priority": "high",
            "estimated_hours": 8,
            "tags": ["auth", "backend"]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Implement login"
        assert data["status"] == "new"
        assert data["priority"] == "high"
        assert data["estimated_hours"] == 8
        assert data["spent_hours"] == 0
        assert data["tags"] == ["auth", "backend"]
        assert "id" in data

    def test_create_task_invalid_project(self):
        resp = api_post("/tasks", {"title": "Bad", "project_id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_create_task_invalid_milestone(self):
        project_id = self._create_project()
        resp = api_post("/tasks", {
            "title": "Bad MS",
            "project_id": project_id,
            "milestone_id": str(uuid.uuid4())
        })
        assert resp.status_code == 404

    def test_task_status_valid_transitions(self):
        """Test all valid status transitions."""
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Transition Task", "project_id": project_id})
        task_id = resp.json()["id"]

        # new -> in_progress
        resp = api_put(f"/tasks/{task_id}", {"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

        # in_progress -> done
        resp = api_put(f"/tasks/{task_id}", {"status": "done"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

        # done -> in_progress (reopen)
        resp = api_put(f"/tasks/{task_id}", {"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

        # in_progress -> blocked
        resp = api_put(f"/tasks/{task_id}", {"status": "blocked"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

        # blocked -> in_progress
        resp = api_put(f"/tasks/{task_id}", {"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_task_status_invalid_transition(self):
        """new -> done is invalid."""
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Invalid Transition", "project_id": project_id})
        task_id = resp.json()["id"]

        resp = api_put(f"/tasks/{task_id}", {"status": "done"})
        assert resp.status_code == 422

    def test_task_status_same_is_noop(self):
        """Setting same status is always allowed."""
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Same Status", "project_id": project_id})
        task_id = resp.json()["id"]

        resp = api_put(f"/tasks/{task_id}", {"status": "new"})
        assert resp.status_code == 200

    def test_task_new_to_blocked(self):
        """new -> blocked is valid."""
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Block Me", "project_id": project_id})
        task_id = resp.json()["id"]
        resp = api_put(f"/tasks/{task_id}", {"status": "blocked"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

    def test_task_blocked_to_new(self):
        """blocked -> new is valid."""
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Unblock Me", "project_id": project_id})
        task_id = resp.json()["id"]
        api_put(f"/tasks/{task_id}", {"status": "blocked"})
        resp = api_put(f"/tasks/{task_id}", {"status": "new"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "new"

    def test_list_tasks_filter_status(self):
        project_id = self._create_project()
        api_post("/tasks", {"title": "NewTask", "project_id": project_id, "status": "new"})
        other = api_post("/tasks", {"title": "InProgressTask", "project_id": project_id}).json()
        api_put(f"/tasks/{other['id']}", {"status": "in_progress"})
        resp = api_get("/tasks", params={"project_id": project_id, "status": "new"})
        assert resp.status_code == 200
        for t in resp.json():
            assert t["status"] == "new"

    def test_list_tasks_filter_priority(self):
        project_id = self._create_project()
        api_post("/tasks", {"title": "UrgentTask", "project_id": project_id, "priority": "urgent"})
        api_post("/tasks", {"title": "LowPriorityTask", "project_id": project_id, "priority": "low"})
        resp = api_get("/tasks", params={"project_id": project_id, "priority": "urgent"})
        assert resp.status_code == 200
        for t in resp.json():
            assert t["priority"] == "urgent"

    def test_list_tasks_filter_tags(self):
        project_id = self._create_project()
        api_post("/tasks", {"title": "TaggedTask", "project_id": project_id, "tags": ["frontend", "ui"]})
        api_post("/tasks", {"title": "OtherTask", "project_id": project_id, "tags": ["backend"]})
        resp = api_get("/tasks", params={"project_id": project_id, "tags": "frontend"})
        assert resp.status_code == 200
        tasks = resp.json()
        assert any("frontend" in t["tags"] for t in tasks)

    def test_delete_task(self):
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "DeleteTask", "project_id": project_id})
        task_id = resp.json()["id"]
        resp = api_delete(f"/tasks/{task_id}")
        assert resp.status_code == 204
        resp = api_get(f"/tasks/{task_id}")
        assert resp.status_code == 404

    def test_task_default_values(self):
        project_id = self._create_project()
        resp = api_post("/tasks", {"title": "Defaults", "project_id": project_id})
        data = resp.json()
        assert data["status"] == "new"
        assert data["priority"] == "medium"
        assert data["estimated_hours"] == 0
        assert data["spent_hours"] == 0
        assert data["tags"] == []
        assert data["description"] == ""


# ════════════════════════════════════════════════════════════════════
# PART 8: Comments
# ════════════════════════════════════════════════════════════════════

class TestComments:
    def _create_task(self):
        project_resp = api_post("/projects", {"name": f"CommentProject-{uuid.uuid4().hex[:8]}"})
        project_id = project_resp.json()["id"]
        task_resp = api_post("/tasks", {"title": "CommentTask", "project_id": project_id})
        return task_resp.json()["id"]

    def test_create_comment(self):
        task_id = self._create_task()
        resp = api_post(f"/tasks/{task_id}/comments", {"content": "Looks good!"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Looks good!"
        assert data["user_id"] == USER_ID
        assert data["task_id"] == task_id
        assert "id" in data
        assert "created_at" in data

    def test_list_comments(self):
        task_id = self._create_task()
        api_post(f"/tasks/{task_id}/comments", {"content": "First"})
        api_post(f"/tasks/{task_id}/comments", {"content": "Second"})
        resp = api_get(f"/tasks/{task_id}/comments")
        assert resp.status_code == 200
        comments = resp.json()
        assert len(comments) >= 2
        # Should be ordered by created_at ascending
        assert comments[-2]["content"] == "First" or comments[-1]["content"] == "Second"

    def test_delete_comment_by_author(self):
        task_id = self._create_task()
        resp = api_post(f"/tasks/{task_id}/comments", {"content": "Delete me"})
        comment_id = resp.json()["id"]
        resp = api_delete(f"/comments/{comment_id}")
        assert resp.status_code == 204

    def test_delete_comment_by_other_user(self):
        """Only author can delete comment."""
        task_id = self._create_task()
        resp = api_post(f"/tasks/{task_id}/comments", {"content": "My comment"})
        comment_id = resp.json()["id"]
        resp = api_delete(f"/comments/{comment_id}", headers=HEADERS_USER2)
        assert resp.status_code == 403

    def test_comment_on_nonexistent_task(self):
        resp = api_post(f"/tasks/{uuid.uuid4()}/comments", {"content": "No task"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Timesheets
# ════════════════════════════════════════════════════════════════════

class TestTimesheets:
    def _create_task(self):
        project_resp = api_post("/projects", {"name": f"TSProject-{uuid.uuid4().hex[:8]}"})
        project_id = project_resp.json()["id"]
        task_resp = api_post("/tasks", {"title": "TSTask", "project_id": project_id})
        return task_resp.json()["id"], project_id

    def test_create_timesheet(self):
        task_id, _ = self._create_task()
        resp = api_post("/timesheets", {
            "task_id": task_id,
            "hours": 2.5,
            "date": "2025-03-15",
            "description": "Worked on feature"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == task_id
        assert data["user_id"] == USER_ID
        assert data["hours"] == 2.5
        assert data["date"] == "2025-03-15"
        assert "id" in data

    def test_create_timesheet_invalid_task(self):
        resp = api_post("/timesheets", {
            "task_id": str(uuid.uuid4()),
            "hours": 1,
            "date": "2025-03-15"
        })
        assert resp.status_code == 404

    def test_list_timesheets_filter_task(self):
        task_id, _ = self._create_task()
        api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        other_task_id, _ = self._create_task()
        api_post("/timesheets", {"task_id": other_task_id, "hours": 2, "date": "2025-03-15"})
        resp = api_get("/timesheets", params={"task_id": task_id})
        assert resp.status_code == 200
        for ts in resp.json():
            assert ts["task_id"] == task_id

    def test_list_timesheets_filter_date_range(self):
        task_id, _ = self._create_task()
        api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-10"})
        api_post("/timesheets", {"task_id": task_id, "hours": 2, "date": "2025-03-20"})
        api_post("/timesheets", {"task_id": task_id, "hours": 3, "date": "2025-04-01"})

        resp = api_get("/timesheets", params={"date_from": "2025-03-01", "date_to": "2025-03-31"})
        assert resp.status_code == 200
        for ts in resp.json():
            assert "2025-03" in ts["date"]

    def test_update_timesheet_by_author(self):
        task_id, _ = self._create_task()
        resp = api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        ts_id = resp.json()["id"]
        resp = api_put(f"/timesheets/{ts_id}", {"hours": 3})
        assert resp.status_code == 200
        assert resp.json()["hours"] == 3

    def test_update_timesheet_by_other_user(self):
        """Only author can update timesheet."""
        task_id, _ = self._create_task()
        resp = api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        ts_id = resp.json()["id"]
        resp = api_put(f"/timesheets/{ts_id}", {"hours": 5}, headers=HEADERS_USER2)
        assert resp.status_code == 403

    def test_delete_timesheet_by_author(self):
        task_id, _ = self._create_task()
        resp = api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        ts_id = resp.json()["id"]
        resp = api_delete(f"/timesheets/{ts_id}")
        assert resp.status_code == 204

    def test_delete_timesheet_by_other_user(self):
        task_id, _ = self._create_task()
        resp = api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        ts_id = resp.json()["id"]
        resp = api_delete(f"/timesheets/{ts_id}", headers=HEADERS_USER2)
        assert resp.status_code == 403

    def test_timesheet_summary(self):
        task_id, project_id = self._create_task()
        api_post("/timesheets", {"task_id": task_id, "hours": 2, "date": "2025-03-15"})
        api_post("/timesheets", {"task_id": task_id, "hours": 3, "date": "2025-03-16"})
        other_task_id, _ = self._create_task()
        api_post("/timesheets", {"task_id": other_task_id, "hours": 7, "date": "2025-03-16"})
        resp = api_get("/timesheets/summary", params={"task_id": task_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hours"] == 5
        assert data["entries_count"] == 2

    def test_timesheet_summary_by_project(self):
        task_id, project_id = self._create_task()
        api_post("/timesheets", {"task_id": task_id, "hours": 4, "date": "2025-03-15"})
        resp = api_get("/timesheets/summary", params={"project_id": project_id})
        assert resp.status_code == 200
        assert resp.json()["total_hours"] >= 4

    def test_task_spent_hours(self):
        """Task's spent_hours should reflect sum of timesheets."""
        task_id, _ = self._create_task()
        api_post("/timesheets", {"task_id": task_id, "hours": 2, "date": "2025-03-15"})
        api_post("/timesheets", {"task_id": task_id, "hours": 3, "date": "2025-03-16"})
        resp = api_get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["spent_hours"] == 5


# ════════════════════════════════════════════════════════════════════
# PART 10: Sprints
# ════════════════════════════════════════════════════════════════════

class TestSprints:
    def _create_project(self):
        resp = api_post("/projects", {"name": f"SprintProject-{uuid.uuid4().hex[:8]}"})
        return resp.json()["id"]

    def _create_task(self, project_id, status="new", estimated_hours=0):
        resp = api_post("/tasks", {
            "title": f"SprintTask-{uuid.uuid4().hex[:8]}",
            "project_id": project_id,
            "estimated_hours": estimated_hours
        })
        task_id = resp.json()["id"]
        if status == "in_progress":
            api_put(f"/tasks/{task_id}", {"status": "in_progress"})
        elif status == "done":
            api_put(f"/tasks/{task_id}", {"status": "in_progress"})
            api_put(f"/tasks/{task_id}", {"status": "done"})
        elif status == "blocked":
            api_put(f"/tasks/{task_id}", {"status": "blocked"})
        return task_id

    def test_create_sprint(self):
        project_id = self._create_project()
        resp = api_post("/sprints", {
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Sprint 1"
        assert data["project_id"] == project_id
        assert data["start_date"] == "2025-03-01"
        assert data["end_date"] == "2025-03-14"
        assert data["tasks"] == []
        assert data["velocity"] == 0
        assert "id" in data

    def test_create_sprint_invalid_project(self):
        resp = api_post("/sprints", {
            "name": "Bad Sprint",
            "project_id": str(uuid.uuid4()),
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        assert resp.status_code == 404

    def test_add_task_to_sprint(self):
        project_id = self._create_project()
        task_id = self._create_task(project_id)
        sprint_resp = api_post("/sprints", {
            "name": "Task Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]

        resp = api_post(f"/sprints/{sprint_id}/tasks", {"task_id": task_id})
        assert resp.status_code == 200
        assert task_id in resp.json()["tasks"]

    def test_add_task_wrong_project(self):
        """Task must belong to same project as sprint."""
        project1 = self._create_project()
        project2 = self._create_project()
        task_id = self._create_task(project2)
        sprint_resp = api_post("/sprints", {
            "name": "Wrong Project Sprint",
            "project_id": project1,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]
        resp = api_post(f"/sprints/{sprint_id}/tasks", {"task_id": task_id})
        assert resp.status_code == 400

    def test_remove_task_from_sprint(self):
        project_id = self._create_project()
        task_id = self._create_task(project_id)
        sprint_resp = api_post("/sprints", {
            "name": "Remove Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]
        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": task_id})

        resp = api_delete(f"/sprints/{sprint_id}/tasks/{task_id}")
        assert resp.status_code == 204

        # Task should no longer be in sprint
        resp = api_get(f"/sprints/{sprint_id}")
        assert task_id not in resp.json()["tasks"]

    def test_sprint_velocity(self):
        """Velocity = sum of estimated_hours of done tasks in sprint."""
        project_id = self._create_project()
        done_task1 = self._create_task(project_id, status="done", estimated_hours=5)
        done_task2 = self._create_task(project_id, status="done", estimated_hours=3)
        open_task = self._create_task(project_id, status="new", estimated_hours=8)

        sprint_resp = api_post("/sprints", {
            "name": "Velocity Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]

        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": done_task1})
        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": done_task2})
        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": open_task})

        resp = api_get(f"/sprints/{sprint_id}")
        assert resp.json()["velocity"] == 8  # 5 + 3 from done tasks

    def test_sprint_velocity_endpoint(self):
        """GET /sprints/{id}/velocity returns detailed velocity info."""
        project_id = self._create_project()
        done_task = self._create_task(project_id, status="done", estimated_hours=4)
        open_task = self._create_task(project_id, status="new", estimated_hours=6)

        sprint_resp = api_post("/sprints", {
            "name": "Velocity Endpoint Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]

        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": done_task})
        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": open_task})

        resp = api_get(f"/sprints/{sprint_id}/velocity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["velocity"] == 4
        assert data["completed_tasks"] == 1
        assert data["total_tasks"] == 2

    def test_update_sprint(self):
        project_id = self._create_project()
        sprint_resp = api_post("/sprints", {
            "name": "Old Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]
        resp = api_put(f"/sprints/{sprint_id}", {"name": "New Sprint"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Sprint"

    def test_delete_sprint(self):
        """Deleting sprint does not delete tasks."""
        project_id = self._create_project()
        task_id = self._create_task(project_id)
        sprint_resp = api_post("/sprints", {
            "name": "Delete Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]
        api_post(f"/sprints/{sprint_id}/tasks", {"task_id": task_id})

        resp = api_delete(f"/sprints/{sprint_id}")
        assert resp.status_code == 204

        # Task should still exist
        resp = api_get(f"/tasks/{task_id}")
        assert resp.status_code == 200

    def test_list_sprints_filter_project(self):
        project_id = self._create_project()
        api_post("/sprints", {
            "name": "Filtered Sprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        other_project_id = self._create_project()
        api_post("/sprints", {
            "name": "Other Project Sprint",
            "project_id": other_project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        resp = api_get("/sprints", params={"project_id": project_id})
        assert resp.status_code == 200
        for s in resp.json():
            assert s["project_id"] == project_id


# ════════════════════════════════════════════════════════════════════
# PART 11: Project Progress (computed from milestones)
# ════════════════════════════════════════════════════════════════════

class TestProjectProgress:
    def test_project_progress_from_milestones(self):
        """Project progress = average of milestone progress values."""
        project_resp = api_post("/projects", {"name": "ProgressProject"})
        project_id = project_resp.json()["id"]

        # Milestone 1: 2 tasks, 1 done → 50%
        ms1_resp = api_post("/milestones", {"title": "MS1", "project_id": project_id})
        ms1_id = ms1_resp.json()["id"]
        t1 = api_post("/tasks", {"title": "T1", "project_id": project_id, "milestone_id": ms1_id}).json()["id"]
        api_put(f"/tasks/{t1}", {"status": "in_progress"})
        api_put(f"/tasks/{t1}", {"status": "done"})
        api_post("/tasks", {"title": "T2", "project_id": project_id, "milestone_id": ms1_id})

        # Milestone 2: 1 task, 1 done → 100%
        ms2_resp = api_post("/milestones", {"title": "MS2", "project_id": project_id})
        ms2_id = ms2_resp.json()["id"]
        t3 = api_post("/tasks", {"title": "T3", "project_id": project_id, "milestone_id": ms2_id}).json()["id"]
        api_put(f"/tasks/{t3}", {"status": "in_progress"})
        api_put(f"/tasks/{t3}", {"status": "done"})

        # Project progress = (50 + 100) / 2 = 75
        resp = api_get(f"/projects/{project_id}")
        assert resp.json()["progress"] == 75.0


# ════════════════════════════════════════════════════════════════════
# PART 12: Project Closure Rule
# ════════════════════════════════════════════════════════════════════

class TestProjectClosure:
    def test_cannot_close_project_with_open_milestones(self):
        project_resp = api_post("/projects", {"name": "ClosureProject"})
        project_id = project_resp.json()["id"]
        api_post("/milestones", {"title": "OpenMS", "project_id": project_id})

        resp = api_put(f"/projects/{project_id}", {"status": "closed"})
        assert resp.status_code == 409

    def test_can_close_project_all_milestones_completed(self):
        project_resp = api_post("/projects", {"name": "ClosableProject"})
        project_id = project_resp.json()["id"]
        ms_resp = api_post("/milestones", {"title": "DoneMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        api_put(f"/milestones/{ms_id}", {"status": "completed"})

        resp = api_put(f"/projects/{project_id}", {"status": "closed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_can_close_project_no_milestones(self):
        project_resp = api_post("/projects", {"name": "NoMSProject"})
        project_id = project_resp.json()["id"]
        resp = api_put(f"/projects/{project_id}", {"status": "closed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation Between Orgs
# ════════════════════════════════════════════════════════════════════

class TestDataIsolation:
    def test_project_isolation(self):
        """Projects in one org are not visible in another."""
        resp = api_post("/projects", {"name": "Org1Project"})
        project_id = resp.json()["id"]
        resp = api_get(f"/projects/{project_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404

    def test_task_isolation(self):
        """Tasks in one org are not visible in another."""
        project_resp = api_post("/projects", {"name": "IsoProject"})
        project_id = project_resp.json()["id"]
        task_resp = api_post("/tasks", {"title": "IsoTask", "project_id": project_id})
        task_id = task_resp.json()["id"]
        resp = api_get(f"/tasks/{task_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404

    def test_milestone_isolation(self):
        project_resp = api_post("/projects", {"name": "IsoMSProject"})
        project_id = project_resp.json()["id"]
        ms_resp = api_post("/milestones", {"title": "IsoMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]
        resp = api_get(f"/milestones/{ms_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404

    def test_sprint_isolation(self):
        project_resp = api_post("/projects", {"name": "IsoSprintProject"})
        project_id = project_resp.json()["id"]
        sprint_resp = api_post("/sprints", {
            "name": "IsoSprint",
            "project_id": project_id,
            "start_date": "2025-03-01",
            "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]
        resp = api_get(f"/sprints/{sprint_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404

    def test_goal_isolation(self):
        project_resp = api_post("/projects", {"name": "IsoGoalProject"})
        project_id = project_resp.json()["id"]
        goal_resp = api_post("/goals", {
            "title": "IsoGoal",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100
        })
        goal_id = goal_resp.json()["id"]
        resp = api_get(f"/goals/{goal_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404

    def test_timesheet_isolation(self):
        project_resp = api_post("/projects", {"name": "IsoTSProject"})
        project_id = project_resp.json()["id"]
        task_resp = api_post("/tasks", {"title": "IsoTSTask", "project_id": project_id})
        task_id = task_resp.json()["id"]
        ts_resp = api_post("/timesheets", {"task_id": task_id, "hours": 1, "date": "2025-03-15"})
        ts_id = ts_resp.json()["id"]
        resp = api_get(f"/timesheets/{ts_id}", headers=HEADERS_ORG2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Cascade Deletion
# ════════════════════════════════════════════════════════════════════

class TestCascadeDeletion:
    def test_delete_project_cascades(self):
        """Deleting project removes milestones, tasks, goals, sprints."""
        project_resp = api_post("/projects", {"name": "CascadeProject"})
        project_id = project_resp.json()["id"]

        ms_resp = api_post("/milestones", {"title": "CascadeMS", "project_id": project_id})
        ms_id = ms_resp.json()["id"]

        task_resp = api_post("/tasks", {"title": "CascadeTask", "project_id": project_id, "milestone_id": ms_id})
        task_id = task_resp.json()["id"]

        goal_resp = api_post("/goals", {
            "title": "CascadeGoal", "project_id": project_id,
            "metric_type": "number", "target_value": 100
        })
        goal_id = goal_resp.json()["id"]

        sprint_resp = api_post("/sprints", {
            "name": "CascadeSprint", "project_id": project_id,
            "start_date": "2025-03-01", "end_date": "2025-03-14"
        })
        sprint_id = sprint_resp.json()["id"]

        # Delete project
        resp = api_delete(f"/projects/{project_id}")
        assert resp.status_code == 204

        # All related resources should be gone
        assert api_get(f"/milestones/{ms_id}").status_code == 404
        assert api_get(f"/tasks/{task_id}").status_code == 404
        assert api_get(f"/goals/{goal_id}").status_code == 404
        assert api_get(f"/sprints/{sprint_id}").status_code == 404

    def test_delete_task_cascades_timesheets_comments(self):
        """Deleting task removes its timesheets and comments."""
        project_resp = api_post("/projects", {"name": "TaskCascade"})
        project_id = project_resp.json()["id"]
        task_resp = api_post("/tasks", {"title": "CascadeTask2", "project_id": project_id})
        task_id = task_resp.json()["id"]

        ts_resp = api_post("/timesheets", {"task_id": task_id, "hours": 2, "date": "2025-03-15"})
        ts_id = ts_resp.json()["id"]
        comment_resp = api_post(f"/tasks/{task_id}/comments", {"content": "Cascade comment"})
        comment_id = comment_resp.json()["id"]

        api_delete(f"/tasks/{task_id}")

        assert api_get(f"/timesheets/{ts_id}").status_code == 404
