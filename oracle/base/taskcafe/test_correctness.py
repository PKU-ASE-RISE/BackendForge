"""
BackendForge — Comprehensive Correctness Tests for TaskCafe

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

# User IDs (UUIDs) — trusted directly
USER_A = str(uuid.uuid4())  # Will be project owner in most tests
USER_B = str(uuid.uuid4())  # Will be added as member
USER_C = str(uuid.uuid4())  # Outsider / non-member

HEADERS_A = {"X-User-Id": USER_A, "Content-Type": "application/json"}
HEADERS_B = {"X-User-Id": USER_B, "Content-Type": "application/json"}
HEADERS_C = {"X-User-Id": USER_C, "Content-Type": "application/json"}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    headers = HEADERS_A if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    headers = HEADERS_A if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    headers = HEADERS_A if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    headers = HEADERS_A if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ── Test Helpers ──

def create_project(name=None, headers=None):
    """Create a project and return its data."""
    name = name or f"Project-{uuid.uuid4().hex[:8]}"
    resp = api_post("/projects", {"name": name}, headers=headers)
    assert resp.status_code == 201, f"Failed to create project: {resp.status_code} {resp.text}"
    return resp.json()


def create_task_group(project_id, name=None, headers=None):
    """Create a task group and return its data."""
    name = name or f"TaskGroup-{uuid.uuid4().hex[:8]}"
    resp = api_post(f"/projects/{project_id}/task-groups", {"name": name}, headers=headers)
    assert resp.status_code == 201, f"Failed to create task group: {resp.status_code} {resp.text}"
    return resp.json()


def create_task(task_group_id, title=None, headers=None, **kwargs):
    """Create a task and return its data."""
    title = title or f"Task-{uuid.uuid4().hex[:8]}"
    body = {"taskGroupId": task_group_id, "title": title, **kwargs}
    resp = api_post("/tasks", body, headers=headers)
    assert resp.status_code == 201, f"Failed to create task: {resp.status_code} {resp.text}"
    return resp.json()


def add_member(project_id, user_id, role="member", headers=None):
    """Add a member to a project."""
    resp = api_post(f"/projects/{project_id}/members", {"userId": user_id, "role": role}, headers=headers)
    assert resp.status_code == 201, f"Failed to add member: {resp.status_code} {resp.text}"
    return resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-User-Id should return 401."""
        resp = requests.get(f"{BASE_URL}/projects", timeout=30)
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"] == "missing X-User-Id header"

    def test_invalid_uuid_returns_401(self):
        """Non-UUID value in X-User-Id should return 401."""
        headers = {"X-User-Id": "not-a-uuid", "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/projects", headers=headers, timeout=30)
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"] == "invalid X-User-Id header"

    def test_valid_uuid_accepted(self):
        """A valid UUID in X-User-Id should be accepted."""
        resp = api_get("/projects")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Project CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjectCRUD:

    def test_create_project(self):
        proj = create_project(f"TestProj-{UNIQUE}")
        assert "id" in proj
        assert proj["name"] == f"TestProj-{UNIQUE}"
        assert "createdAt" in proj
        assert "members" in proj
        # Creator should be owner
        assert len(proj["members"]) == 1
        assert proj["members"][0]["userId"] == USER_A
        assert proj["members"][0]["role"] == "owner"

    def test_list_projects(self):
        name = f"ListProj-{UNIQUE}"
        create_project(name)
        resp = api_get("/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        names = [p["name"] for p in projects]
        assert name in names

    def test_list_projects_only_member_projects(self):
        """User C should not see User A's projects."""
        name = f"PrivateProj-{UNIQUE}"
        create_project(name)
        resp = api_get("/projects", headers=HEADERS_C)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert name not in names

    def test_get_project(self):
        proj = create_project(f"GetProj-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == proj["id"]
        assert data["name"] == proj["name"]
        assert "members" in data

    def test_get_project_not_member(self):
        """Non-member should get 403."""
        proj = create_project(f"ForbidProj-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}", headers=HEADERS_C)
        assert resp.status_code == 403

    def test_get_project_not_found(self):
        """Non-existent project should return 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/projects/{fake_id}")
        assert resp.status_code == 404

    def test_update_project(self):
        proj = create_project(f"UpdateProj-{UNIQUE}")
        resp = api_put(f"/projects/{proj['id']}", {"name": f"Updated-{UNIQUE}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"Updated-{UNIQUE}"

    def test_update_project_member_forbidden(self):
        """Regular member cannot update project."""
        proj = create_project(f"NoUpdateProj-{UNIQUE}")
        add_member(proj["id"], USER_B)
        resp = api_put(f"/projects/{proj['id']}", {"name": "Hacked"}, headers=HEADERS_B)
        assert resp.status_code == 403

    def test_update_project_admin_allowed(self):
        """Admin can update project."""
        proj = create_project(f"AdminUpdateProj-{UNIQUE}")
        add_member(proj["id"], USER_B, role="admin")
        resp = api_put(f"/projects/{proj['id']}", {"name": f"AdminUpdated-{UNIQUE}"}, headers=HEADERS_B)
        assert resp.status_code == 200
        assert resp.json()["name"] == f"AdminUpdated-{UNIQUE}"

    def test_delete_project(self):
        proj = create_project(f"DelProj-{UNIQUE}")
        resp = api_delete(f"/projects/{proj['id']}")
        assert resp.status_code == 204

        # Should be gone
        resp2 = api_get(f"/projects/{proj['id']}")
        assert resp2.status_code == 404

    def test_delete_project_non_owner_forbidden(self):
        """Only owner can delete project."""
        proj = create_project(f"NoDelProj-{UNIQUE}")
        add_member(proj["id"], USER_B, role="admin")
        resp = api_delete(f"/projects/{proj['id']}", headers=HEADERS_B)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 3: Project Members
# ════════════════════════════════════════════════════════════════════


class TestProjectMembers:

    def test_list_members(self):
        proj = create_project(f"MemberProj-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}/members")
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 1
        assert members[0]["userId"] == USER_A
        assert members[0]["role"] == "owner"

    def test_add_member(self):
        proj = create_project(f"AddMember-{UNIQUE}")
        resp = api_post(f"/projects/{proj['id']}/members", {
            "userId": USER_B,
            "role": "member",
        })
        assert resp.status_code == 201
        member = resp.json()
        assert member["userId"] == USER_B
        assert member["role"] == "member"

    def test_add_member_duplicate(self):
        """Cannot add same user twice."""
        proj = create_project(f"DupMember-{UNIQUE}")
        add_member(proj["id"], USER_B)
        resp = api_post(f"/projects/{proj['id']}/members", {
            "userId": USER_B,
            "role": "member",
        })
        assert resp.status_code == 409

    def test_add_member_non_admin_forbidden(self):
        """Regular member cannot add other members."""
        proj = create_project(f"NoAddMember-{UNIQUE}")
        add_member(proj["id"], USER_B)
        new_user = str(uuid.uuid4())
        resp = api_post(f"/projects/{proj['id']}/members", {
            "userId": new_user,
            "role": "member",
        }, headers=HEADERS_B)
        assert resp.status_code == 403

    def test_remove_member(self):
        proj = create_project(f"RmMember-{UNIQUE}")
        add_member(proj["id"], USER_B)
        resp = api_delete(f"/projects/{proj['id']}/members/{USER_B}")
        assert resp.status_code == 204

        # Verify removed
        members_resp = api_get(f"/projects/{proj['id']}/members")
        user_ids = [m["userId"] for m in members_resp.json()]
        assert USER_B not in user_ids

    def test_cannot_remove_owner(self):
        """Owner cannot be removed."""
        proj = create_project(f"NoRmOwner-{UNIQUE}")
        resp = api_delete(f"/projects/{proj['id']}/members/{USER_A}")
        assert resp.status_code == 400
        assert resp.json()["error"] == "cannot remove project owner"

    def test_non_member_cannot_list_members(self):
        proj = create_project(f"SecretMembers-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}/members", headers=HEADERS_C)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 4: Task Groups
# ════════════════════════════════════════════════════════════════════


class TestTaskGroups:

    def test_create_task_group(self):
        proj = create_project(f"TGProj-{UNIQUE}")
        tg = create_task_group(proj["id"], f"Backlog-{UNIQUE}")
        assert "id" in tg
        assert tg["name"] == f"Backlog-{UNIQUE}"
        assert tg["projectId"] == proj["id"]
        assert "position" in tg
        assert "createdAt" in tg

    def test_list_task_groups_ordered(self):
        proj = create_project(f"TGOrder-{UNIQUE}")
        tg1 = create_task_group(proj["id"], "First")
        tg2 = create_task_group(proj["id"], "Second")
        tg3 = create_task_group(proj["id"], "Third")

        resp = api_get(f"/projects/{proj['id']}/task-groups")
        assert resp.status_code == 200
        groups = resp.json()
        assert len(groups) >= 3
        # Should be ordered by position
        positions = [g["position"] for g in groups]
        assert positions == sorted(positions)

    def test_update_task_group(self):
        proj = create_project(f"TGUpdate-{UNIQUE}")
        tg = create_task_group(proj["id"], "OldName")
        resp = api_put(f"/task-groups/{tg['id']}", {"name": "NewName", "position": 100.0})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "NewName"
        assert updated["position"] == 100.0

    def test_delete_task_group(self):
        proj = create_project(f"TGDel-{UNIQUE}")
        tg = create_task_group(proj["id"], "ToDelete")
        resp = api_delete(f"/task-groups/{tg['id']}")
        assert resp.status_code == 204

        # Should be gone
        groups_resp = api_get(f"/projects/{proj['id']}/task-groups")
        ids = [g["id"] for g in groups_resp.json()]
        assert tg["id"] not in ids

    def test_task_group_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/task-groups/{fake_id}", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_task_group_non_member_forbidden(self):
        proj = create_project(f"TGForbid-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}/task-groups", headers=HEADERS_C)
        assert resp.status_code == 403

    def test_auto_position_assignment(self):
        """Task groups created without position should get auto-assigned positions."""
        proj = create_project(f"TGAutoPos-{UNIQUE}")
        tg1 = create_task_group(proj["id"], "A")
        tg2 = create_task_group(proj["id"], "B")
        assert tg2["position"] > tg1["position"]


# ════════════════════════════════════════════════════════════════════
# PART 5: Tasks CRUD
# ════════════════════════════════════════════════════════════════════


class TestTaskCRUD:

    def test_create_task(self):
        proj = create_project(f"TaskProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Backlog")
        task = create_task(tg["id"], f"MyTask-{UNIQUE}")
        assert "id" in task
        assert task["title"] == f"MyTask-{UNIQUE}"
        assert task["taskGroupId"] == tg["id"]
        assert task["complete"] is False
        assert "position" in task
        assert "createdAt" in task

    def test_create_task_with_description(self):
        proj = create_project(f"TaskDescProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Todo")
        task = create_task(tg["id"], "WithDesc", description="Some details")
        assert task["description"] == "Some details"

    def test_create_task_with_due_date(self):
        proj = create_project(f"TaskDueProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Sprint")
        due = "2030-01-15"
        task = create_task(tg["id"], "DueTask", dueDate=due)
        assert task["dueDate"] == due

    def test_list_tasks(self):
        proj = create_project(f"TaskListProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        create_task(tg["id"], "T1")
        create_task(tg["id"], "T2")

        resp = api_get(f"/projects/{proj['id']}/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert isinstance(tasks, list)
        assert len(tasks) >= 2

    def test_list_tasks_filter_by_complete(self):
        proj = create_project(f"TaskFilterProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        t1 = create_task(tg["id"], "Done Task")
        create_task(tg["id"], "Not Done")

        # Mark t1 as complete
        api_put(f"/tasks/{t1['id']}", {"complete": True})

        resp = api_get(f"/projects/{proj['id']}/tasks", params={"complete": "true"})
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["complete"] for t in tasks)

        resp2 = api_get(f"/projects/{proj['id']}/tasks", params={"complete": "false"})
        assert resp2.status_code == 200
        tasks2 = resp2.json()
        assert all(not t["complete"] for t in tasks2)

    def test_list_tasks_filter_by_task_group(self):
        proj = create_project(f"TaskFilterTG-{UNIQUE}")
        tg1 = create_task_group(proj["id"], "Col1")
        tg2 = create_task_group(proj["id"], "Col2")
        create_task(tg1["id"], "In Col1")
        create_task(tg2["id"], "In Col2")

        resp = api_get(f"/projects/{proj['id']}/tasks", params={"taskGroupId": tg1["id"]})
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["taskGroupId"] == tg1["id"] for t in tasks)

    def test_get_task_detail(self):
        proj = create_project(f"TaskDetailProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "DetailTask")

        resp = api_get(f"/tasks/{task['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == task["id"]
        assert "assignedMembers" in detail
        assert "labels" in detail
        assert "checklists" in detail
        assert isinstance(detail["assignedMembers"], list)
        assert isinstance(detail["labels"], list)
        assert isinstance(detail["checklists"], list)

    def test_update_task(self):
        proj = create_project(f"TaskUpdateProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Original")

        resp = api_put(f"/tasks/{task['id']}", {
            "title": "Renamed",
            "description": "New desc",
            "complete": True,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Renamed"
        assert updated["description"] == "New desc"
        assert updated["complete"] is True

    def test_move_task_between_groups(self):
        proj = create_project(f"TaskMoveProj-{UNIQUE}")
        tg1 = create_task_group(proj["id"], "From")
        tg2 = create_task_group(proj["id"], "To")
        task = create_task(tg1["id"], "Movable")

        resp = api_put(f"/tasks/{task['id']}", {
            "taskGroupId": tg2["id"],
            "position": 1000.0,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["taskGroupId"] == tg2["id"]

    def test_delete_task(self):
        proj = create_project(f"TaskDelProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "ToDelete")

        resp = api_delete(f"/tasks/{task['id']}")
        assert resp.status_code == 204

        # Should be gone
        resp2 = api_get(f"/tasks/{task['id']}")
        assert resp2.status_code == 404

    def test_task_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/tasks/{fake_id}")
        assert resp.status_code == 404

    def test_task_non_member_forbidden(self):
        proj = create_project(f"TaskForbidProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Secret")
        resp = api_get(f"/tasks/{task['id']}", headers=HEADERS_C)
        assert resp.status_code == 403

    def test_auto_position_tasks(self):
        """Tasks created without position get auto-assigned increasing positions."""
        proj = create_project(f"TaskAutoPos-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        t1 = create_task(tg["id"], "T1")
        t2 = create_task(tg["id"], "T2")
        assert t2["position"] > t1["position"]


# ════════════════════════════════════════════════════════════════════
# PART 6: Task Assignments
# ════════════════════════════════════════════════════════════════════


class TestTaskAssignments:

    def test_assign_member(self):
        proj = create_project(f"AssignProj-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Assignable")

        resp = api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        assert resp.status_code == 201
        data = resp.json()
        assert data["taskId"] == task["id"]
        assert data["userId"] == USER_B

    def test_assign_reflected_in_task_detail(self):
        proj = create_project(f"AssignDetail-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "AssignCheck")

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})

        detail = api_get(f"/tasks/{task['id']}").json()
        assert USER_B in detail["assignedMembers"]

    def test_assign_non_member_fails(self):
        """Cannot assign a user who is not a project member."""
        proj = create_project(f"AssignNonMem-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        non_member = str(uuid.uuid4())

        resp = api_post(f"/tasks/{task['id']}/assignments", {"userId": non_member})
        assert resp.status_code == 400
        assert resp.json()["error"] == "user is not a project member"

    def test_assign_duplicate_fails(self):
        """Cannot assign same user twice."""
        proj = create_project(f"AssignDup-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        resp = api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        assert resp.status_code == 409

    def test_unassign_member(self):
        proj = create_project(f"Unassign-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        resp = api_delete(f"/tasks/{task['id']}/assignments/{USER_B}")
        assert resp.status_code == 204

        # Verify unassigned
        detail = api_get(f"/tasks/{task['id']}").json()
        assert USER_B not in detail["assignedMembers"]

    def test_unassign_not_found(self):
        proj = create_project(f"UnassignNF-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        fake_user = str(uuid.uuid4())

        resp = api_delete(f"/tasks/{task['id']}/assignments/{fake_user}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Labels
# ════════════════════════════════════════════════════════════════════


class TestLabels:

    def test_create_label(self):
        proj = create_project(f"LabelProj-{UNIQUE}")
        resp = api_post(f"/projects/{proj['id']}/labels", {
            "name": "Bug",
            "color": "#ff0000",
        })
        assert resp.status_code == 201
        label = resp.json()
        assert label["name"] == "Bug"
        assert label["color"] == "#ff0000"
        assert label["projectId"] == proj["id"]
        assert "id" in label

    def test_list_labels(self):
        proj = create_project(f"ListLabelProj-{UNIQUE}")
        api_post(f"/projects/{proj['id']}/labels", {"name": "Feature", "color": "#00ff00"})
        resp = api_get(f"/projects/{proj['id']}/labels")
        assert resp.status_code == 200
        labels = resp.json()
        assert isinstance(labels, list)
        assert len(labels) >= 1

    def test_update_label(self):
        proj = create_project(f"UpdateLabelProj-{UNIQUE}")
        create_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Old", "color": "#000"})
        label = create_resp.json()

        resp = api_put(f"/labels/{label['id']}", {"name": "New", "color": "#fff"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "New"
        assert updated["color"] == "#fff"

    def test_delete_label(self):
        proj = create_project(f"DelLabelProj-{UNIQUE}")
        create_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "ToDelete", "color": "#abc"})
        label = create_resp.json()

        resp = api_delete(f"/labels/{label['id']}")
        assert resp.status_code == 204

        # Should be gone
        labels_resp = api_get(f"/projects/{proj['id']}/labels")
        ids = [l["id"] for l in labels_resp.json()]
        assert label["id"] not in ids

    def test_label_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/labels/{fake_id}", {"name": "Ghost", "color": "#000"})
        assert resp.status_code == 404

    def test_add_label_to_task(self):
        proj = create_project(f"TaskLabelProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "LabeledTask")
        label_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Priority", "color": "#f00"})
        label = label_resp.json()

        resp = api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        assert resp.status_code == 201
        data = resp.json()
        assert data["taskId"] == task["id"]
        assert data["labelId"] == label["id"]

    def test_label_in_task_detail(self):
        proj = create_project(f"TaskLabelDetail-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        label_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "UI", "color": "#0f0"})
        label = label_resp.json()
        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})

        detail = api_get(f"/tasks/{task['id']}").json()
        label_ids = [l["id"] for l in detail["labels"]]
        assert label["id"] in label_ids

    def test_remove_label_from_task(self):
        proj = create_project(f"RmTaskLabel-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        label_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Temp", "color": "#aaa"})
        label = label_resp.json()
        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})

        resp = api_delete(f"/tasks/{task['id']}/labels/{label['id']}")
        assert resp.status_code == 204

        detail = api_get(f"/tasks/{task['id']}").json()
        label_ids = [l["id"] for l in detail["labels"]]
        assert label["id"] not in label_ids

    def test_add_label_duplicate_fails(self):
        """Cannot add same label twice."""
        proj = create_project(f"DupTaskLabel-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        label_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Dup", "color": "#000"})
        label = label_resp.json()

        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        resp = api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        assert resp.status_code == 409

    def test_add_label_cross_project_fails(self):
        """Cannot add label from a different project."""
        proj1 = create_project(f"LabelCross1-{UNIQUE}")
        proj2 = create_project(f"LabelCross2-{UNIQUE}")
        tg = create_task_group(proj1["id"], "Column")
        task = create_task(tg["id"], "Task")
        # Label from proj2
        label_resp = api_post(f"/projects/{proj2['id']}/labels", {"name": "Other", "color": "#ccc"})
        label = label_resp.json()

        resp = api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        assert resp.status_code == 400

    def test_delete_label_removes_from_tasks(self):
        """Deleting a label should remove it from all tasks."""
        proj = create_project(f"DelLabelCascade-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        label_resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Gone", "color": "#bbb"})
        label = label_resp.json()
        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})

        # Delete the label
        api_delete(f"/labels/{label['id']}")

        # Task should no longer have the label
        detail = api_get(f"/tasks/{task['id']}").json()
        label_ids = [l["id"] for l in detail["labels"]]
        assert label["id"] not in label_ids


# ════════════════════════════════════════════════════════════════════
# PART 8: Checklists
# ════════════════════════════════════════════════════════════════════


class TestChecklists:

    def test_create_checklist(self):
        proj = create_project(f"CLProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "Steps"})
        assert resp.status_code == 201
        cl = resp.json()
        assert cl["title"] == "Steps"
        assert cl["taskId"] == task["id"]
        assert "id" in cl
        assert "position" in cl

    def test_update_checklist(self):
        proj = create_project(f"CLUpdate-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "Old"})
        cl = cl_resp.json()

        resp = api_put(f"/checklists/{cl['id']}", {"title": "New", "position": 500.0})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "New"
        assert updated["position"] == 500.0

    def test_delete_checklist(self):
        proj = create_project(f"CLDel-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "Gone"})
        cl = cl_resp.json()

        resp = api_delete(f"/checklists/{cl['id']}")
        assert resp.status_code == 204

    def test_checklist_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/checklists/{fake_id}", {"title": "Ghost"})
        assert resp.status_code == 404

    def test_create_checklist_item(self):
        proj = create_project(f"CLItemProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "List"})
        cl = cl_resp.json()

        resp = api_post(f"/checklists/{cl['id']}/items", {"name": "Step 1"})
        assert resp.status_code == 201
        item = resp.json()
        assert item["name"] == "Step 1"
        assert item["complete"] is False
        assert item["checklistId"] == cl["id"]
        assert "id" in item
        assert "position" in item

    def test_update_checklist_item(self):
        proj = create_project(f"CLItemUpdate-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "List"})
        cl = cl_resp.json()
        item_resp = api_post(f"/checklists/{cl['id']}/items", {"name": "Old"})
        item = item_resp.json()

        resp = api_put(f"/checklist-items/{item['id']}", {
            "name": "New",
            "complete": True,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "New"
        assert updated["complete"] is True

    def test_delete_checklist_item(self):
        proj = create_project(f"CLItemDel-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "List"})
        cl = cl_resp.json()
        item_resp = api_post(f"/checklists/{cl['id']}/items", {"name": "Bye"})
        item = item_resp.json()

        resp = api_delete(f"/checklist-items/{item['id']}")
        assert resp.status_code == 204

    def test_checklist_item_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/checklist-items/{fake_id}", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_checklist_progress_in_task_detail(self):
        """Task detail should show computed completedItems/totalItems."""
        proj = create_project(f"CLProgress-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "Progress"})
        cl = cl_resp.json()

        # Add 3 items, complete 2
        item1 = api_post(f"/checklists/{cl['id']}/items", {"name": "A"}).json()
        item2 = api_post(f"/checklists/{cl['id']}/items", {"name": "B"}).json()
        api_post(f"/checklists/{cl['id']}/items", {"name": "C"})

        api_put(f"/checklist-items/{item1['id']}", {"complete": True})
        api_put(f"/checklist-items/{item2['id']}", {"complete": True})

        detail = api_get(f"/tasks/{task['id']}").json()
        checklist = detail["checklists"][0]
        assert checklist["totalItems"] == 3
        assert checklist["completedItems"] == 2

    def test_task_complete_does_not_cascade_to_checklist(self):
        """Marking a task complete does NOT auto-complete checklist items."""
        proj = create_project(f"NoCascade-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "List"})
        cl = cl_resp.json()
        api_post(f"/checklists/{cl['id']}/items", {"name": "Incomplete"})

        # Complete the task
        api_put(f"/tasks/{task['id']}", {"complete": True})

        # Checklist items should still be incomplete
        detail = api_get(f"/tasks/{task['id']}").json()
        checklist = detail["checklists"][0]
        assert checklist["completedItems"] == 0
        assert checklist["totalItems"] == 1

    def test_delete_checklist_deletes_items(self):
        """Deleting a checklist should delete its items."""
        proj = create_project(f"CLCascade-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "CascadeList"})
        cl = cl_resp.json()
        item_resp = api_post(f"/checklists/{cl['id']}/items", {"name": "Item"})
        item = item_resp.json()

        api_delete(f"/checklists/{cl['id']}")

        # Item should be gone (trying to update it should 404)
        resp = api_put(f"/checklist-items/{item['id']}", {"name": "Ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Comments
# ════════════════════════════════════════════════════════════════════


class TestComments:

    def test_create_comment(self):
        proj = create_project(f"CommentProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        resp = api_post(f"/tasks/{task['id']}/comments", {"text": "Hello!"})
        assert resp.status_code == 201
        comment = resp.json()
        assert comment["text"] == "Hello!"
        assert comment["userId"] == USER_A
        assert comment["taskId"] == task["id"]
        assert "id" in comment
        assert "createdAt" in comment
        assert "updatedAt" in comment

    def test_list_comments(self):
        proj = create_project(f"ListComment-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        api_post(f"/tasks/{task['id']}/comments", {"text": "First"})
        api_post(f"/tasks/{task['id']}/comments", {"text": "Second"})

        resp = api_get(f"/tasks/{task['id']}/comments")
        assert resp.status_code == 200
        comments = resp.json()
        assert isinstance(comments, list)
        assert len(comments) >= 2

    def test_comments_newest_first(self):
        """Comments should be returned newest first."""
        proj = create_project(f"CommentOrder-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        api_post(f"/tasks/{task['id']}/comments", {"text": "Older"})
        api_post(f"/tasks/{task['id']}/comments", {"text": "Newer"})

        resp = api_get(f"/tasks/{task['id']}/comments")
        comments = resp.json()
        if len(comments) >= 2:
            assert comments[0]["createdAt"] >= comments[1]["createdAt"]

    def test_update_comment_by_author(self):
        proj = create_project(f"EditComment-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        comment_resp = api_post(f"/tasks/{task['id']}/comments", {"text": "Original"})
        comment = comment_resp.json()

        resp = api_put(f"/comments/{comment['id']}", {"text": "Edited"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["text"] == "Edited"

    def test_update_comment_non_author_forbidden(self):
        """Non-author cannot edit comment."""
        proj = create_project(f"NoEditComment-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        comment_resp = api_post(f"/tasks/{task['id']}/comments", {"text": "Mine"})
        comment = comment_resp.json()

        resp = api_put(f"/comments/{comment['id']}", {"text": "Hacked"}, headers=HEADERS_B)
        assert resp.status_code == 403
        assert resp.json()["error"] == "not comment author"

    def test_delete_comment_by_author(self):
        proj = create_project(f"DelComment-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        comment_resp = api_post(f"/tasks/{task['id']}/comments", {"text": "ToDelete"})
        comment = comment_resp.json()

        resp = api_delete(f"/comments/{comment['id']}")
        assert resp.status_code == 204

    def test_delete_comment_non_author_forbidden(self):
        proj = create_project(f"NoDelComment-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        comment_resp = api_post(f"/tasks/{task['id']}/comments", {"text": "Protected"})
        comment = comment_resp.json()

        resp = api_delete(f"/comments/{comment['id']}", headers=HEADERS_B)
        assert resp.status_code == 403

    def test_comment_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/comments/{fake_id}", {"text": "Ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Activity Log
# ════════════════════════════════════════════════════════════════════


class TestActivityLog:

    def test_task_created_activity(self):
        proj = create_project(f"ActivityProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        create_task(tg["id"], "ActivityTask")

        resp = api_get(f"/projects/{proj['id']}/activity")
        assert resp.status_code == 200
        activities = resp.json()
        assert isinstance(activities, list)
        # Should have at least one TASK_CREATED entry
        action_types = [a["actionType"] for a in activities]
        assert "TASK_CREATED" in action_types

    def test_task_completed_activity(self):
        proj = create_project(f"CompleteActivity-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "CompleteMe")

        api_put(f"/tasks/{task['id']}", {"complete": True})

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "TASK_COMPLETED" in action_types

    def test_task_uncompleted_activity(self):
        proj = create_project(f"UncompleteActivity-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "UncompleteMe")

        api_put(f"/tasks/{task['id']}", {"complete": True})
        api_put(f"/tasks/{task['id']}", {"complete": False})

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "TASK_UNCOMPLETED" in action_types

    def test_task_moved_activity(self):
        proj = create_project(f"MoveActivity-{UNIQUE}")
        tg1 = create_task_group(proj["id"], "From")
        tg2 = create_task_group(proj["id"], "To")
        task = create_task(tg1["id"], "Mover")

        api_put(f"/tasks/{task['id']}", {"taskGroupId": tg2["id"], "position": 1.0})

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "TASK_MOVED" in action_types

    def test_task_assigned_activity(self):
        proj = create_project(f"AssignActivity-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "TASK_ASSIGNED" in action_types

    def test_task_unassigned_activity(self):
        proj = create_project(f"UnassignActivity-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        api_delete(f"/tasks/{task['id']}/assignments/{USER_B}")

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "TASK_UNASSIGNED" in action_types

    def test_comment_added_activity(self):
        proj = create_project(f"CommentActivity-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        api_post(f"/tasks/{task['id']}/comments", {"text": "Discussion"})

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        action_types = [a["actionType"] for a in activities]
        assert "COMMENT_ADDED" in action_types

    def test_activity_newest_first(self):
        """Activity should be ordered newest first."""
        proj = create_project(f"ActivityOrder-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        create_task(tg["id"], "Task1")
        create_task(tg["id"], "Task2")

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        if len(activities) >= 2:
            assert activities[0]["createdAt"] >= activities[1]["createdAt"]

    def test_activity_pagination(self):
        """Activity supports limit and offset."""
        proj = create_project(f"ActivityPag-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        for i in range(5):
            create_task(tg["id"], f"PagTask-{i}")

        resp = api_get(f"/projects/{proj['id']}/activity", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        activities = resp.json()
        assert len(activities) <= 2

    def test_activity_has_required_fields(self):
        """Each activity entry should have all required fields."""
        proj = create_project(f"ActivityFields-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        create_task(tg["id"], "Task")

        resp = api_get(f"/projects/{proj['id']}/activity")
        activities = resp.json()
        assert len(activities) >= 1
        entry = activities[0]
        assert "id" in entry
        assert "projectId" in entry
        assert "userId" in entry
        assert "actionType" in entry
        assert "detail" in entry
        assert "createdAt" in entry

    def test_activity_non_member_forbidden(self):
        proj = create_project(f"ActivityForbid-{UNIQUE}")
        resp = api_get(f"/projects/{proj['id']}/activity", headers=HEADERS_C)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 11: Overdue Filter
# ════════════════════════════════════════════════════════════════════


class TestOverdueFilter:

    def test_overdue_tasks(self):
        """Tasks with dueDate < today and not complete should appear in overdue filter."""
        proj = create_project(f"OverdueProj-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")

        past_due_date = "2000-01-01"
        future_due_date = "2999-12-31"

        # Overdue and incomplete
        t_overdue = create_task(tg["id"], "Overdue", dueDate=past_due_date)
        # Future due date
        create_task(tg["id"], "Future", dueDate=future_due_date)
        # Overdue but complete
        t_complete = create_task(tg["id"], "DoneOverdue", dueDate=past_due_date)
        api_put(f"/tasks/{t_complete['id']}", {"complete": True})

        resp = api_get(f"/projects/{proj['id']}/tasks", params={"overdue": "true"})
        assert resp.status_code == 200
        tasks = resp.json()
        task_ids = [t["id"] for t in tasks]
        assert t_overdue["id"] in task_ids
        assert t_complete["id"] not in task_ids


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_task_group_cascades_tasks(self):
        """Deleting a task group should delete all its tasks."""
        proj = create_project(f"TGCascade-{UNIQUE}")
        tg = create_task_group(proj["id"], "Doomed")
        task = create_task(tg["id"], "WillDie")

        api_delete(f"/task-groups/{tg['id']}")

        # Task should be gone
        resp = api_get(f"/tasks/{task['id']}")
        assert resp.status_code == 404

    def test_delete_project_cascades_everything(self):
        """Deleting a project should delete task groups, tasks, labels, etc."""
        proj = create_project(f"ProjCascade-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        api_post(f"/projects/{proj['id']}/labels", {"name": "Label", "color": "#000"})

        api_delete(f"/projects/{proj['id']}")

        # Task should be gone
        resp = api_get(f"/tasks/{task['id']}")
        assert resp.status_code == 404

    def test_delete_task_cascades_assignments_and_comments(self):
        """Deleting a task should delete its assignments, checklists, and comments."""
        proj = create_project(f"TaskCascade-{UNIQUE}")
        add_member(proj["id"], USER_B)
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        # Add assignment, checklist, comment
        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER_B})
        cl_resp = api_post(f"/tasks/{task['id']}/checklists", {"title": "List"})
        cl = cl_resp.json()
        item_resp = api_post(f"/checklists/{cl['id']}/items", {"name": "Item"})
        item = item_resp.json()
        api_post(f"/tasks/{task['id']}/comments", {"text": "Comment"})

        api_delete(f"/tasks/{task['id']}")

        # Checklist item should be gone
        resp = api_put(f"/checklist-items/{item['id']}", {"name": "Ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Position Management
# ════════════════════════════════════════════════════════════════════


class TestPositionManagement:

    def test_task_group_explicit_position(self):
        """Creating a task group with explicit position."""
        proj = create_project(f"TGExplPos-{UNIQUE}")
        tg = create_task_group(proj["id"], "First")
        # Create with explicit position between
        resp = api_post(f"/projects/{proj['id']}/task-groups", {
            "name": "Inserted",
            "position": tg["position"] / 2,
        })
        assert resp.status_code == 201
        inserted = resp.json()
        assert inserted["position"] < tg["position"]

    def test_task_position_reorder(self):
        """Update task position to reorder within group."""
        proj = create_project(f"TaskReorder-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        t1 = create_task(tg["id"], "First")
        t2 = create_task(tg["id"], "Second")
        t3 = create_task(tg["id"], "Third")

        # Move t3 between t1 and t2
        new_pos = (t1["position"] + t2["position"]) / 2
        resp = api_put(f"/tasks/{t3['id']}", {"position": new_pos})
        assert resp.status_code == 200
        assert resp.json()["position"] == new_pos


# ════════════════════════════════════════════════════════════════════
# PART 14: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_non_member_cannot_create_task_group(self):
        proj = create_project(f"IsoTG-{UNIQUE}")
        resp = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Hack"}, headers=HEADERS_C)
        assert resp.status_code == 403

    def test_non_member_cannot_create_task(self):
        proj = create_project(f"IsoTask-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        resp = api_post("/tasks", {"taskGroupId": tg["id"], "title": "Hack"}, headers=HEADERS_C)
        assert resp.status_code == 403

    def test_non_member_cannot_create_label(self):
        proj = create_project(f"IsoLabel-{UNIQUE}")
        resp = api_post(f"/projects/{proj['id']}/labels", {"name": "Hack", "color": "#000"}, headers=HEADERS_C)
        assert resp.status_code == 403

    def test_non_member_cannot_comment(self):
        proj = create_project(f"IsoComment-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")
        resp = api_post(f"/tasks/{task['id']}/comments", {"text": "Hack"}, headers=HEADERS_C)
        assert resp.status_code == 403

    def test_member_can_access_after_added(self):
        """After being added as member, user can access project resources."""
        proj = create_project(f"IsoAccess-{UNIQUE}")
        tg = create_task_group(proj["id"], "Column")
        task = create_task(tg["id"], "Task")

        # B cannot access before being added
        resp = api_get(f"/tasks/{task['id']}", headers=HEADERS_B)
        assert resp.status_code == 403

        # Add B as member
        add_member(proj["id"], USER_B)

        # Now B can access
        resp = api_get(f"/tasks/{task['id']}", headers=HEADERS_B)
        assert resp.status_code == 200
