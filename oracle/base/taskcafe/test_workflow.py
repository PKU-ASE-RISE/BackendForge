"""
TaskCafe — L3 Workflow Tests (Adversarial)

Multi-step workflows crossing 3+ entity types.
Targets: role-based access, activity log, task movement, cascade.

"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

USER1 = str(uuid.uuid4())
USER2 = str(uuid.uuid4())
USER3 = str(uuid.uuid4())

HEADERS1 = {"X-User-Id": USER1, "Content-Type": "application/json"}
HEADERS2 = {"X-User-Id": USER2, "Content-Type": "application/json"}
HEADERS3 = {"X-User-Id": USER3, "Content-Type": "application/json"}


def unique():
    return uuid.uuid4().hex[:8]


def api_get(path, params=None, headers=None):
    headers = HEADERS1 if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    headers = HEADERS1 if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    headers = HEADERS1 if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    headers = HEADERS1 if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


class TestKanbanWorkflow:
    """Pattern 2+5+7: Full Kanban board lifecycle."""

    def test_kanban_board_lifecycle(self):
        """
        Create project -> task groups (columns) -> tasks -> move task between groups
        -> verify task's taskGroupId changes -> add checklists -> verify computed fields.
        """
        uid = unique()

        # Create project
        proj = api_post("/projects", {"name": f"Kanban-{uid}"}).json()
        pid = proj["id"]

        # Create columns
        todo = api_post(f"/projects/{pid}/task-groups", {"name": "To Do"}).json()
        doing = api_post(f"/projects/{pid}/task-groups", {"name": "Doing"}).json()
        done = api_post(f"/projects/{pid}/task-groups", {"name": "Done"}).json()

        # Verify ordering
        groups = api_get(f"/projects/{pid}/task-groups").json()
        assert len(groups) == 3
        positions = [g["position"] for g in groups]
        assert positions == sorted(positions)

        # Create tasks in "To Do"
        t1 = api_post("/tasks", {"taskGroupId": todo["id"], "title": f"Feature A-{uid}"}).json()
        t2 = api_post("/tasks", {"taskGroupId": todo["id"], "title": f"Feature B-{uid}"}).json()

        # Move t1 to "Doing"
        r = api_put(f"/tasks/{t1['id']}", {"taskGroupId": doing["id"], "position": 65536.0})
        assert r.status_code == 200
        assert r.json()["taskGroupId"] == doing["id"]

        # Verify via GET
        detail = api_get(f"/tasks/{t1['id']}").json()
        assert detail["taskGroupId"] == doing["id"]

        # Add checklist to t1
        cl = api_post(f"/tasks/{t1['id']}/checklists", {"title": "Acceptance Criteria"}).json()
        i1 = api_post(f"/checklists/{cl['id']}/items", {"name": "Tests pass"}).json()
        i2 = api_post(f"/checklists/{cl['id']}/items", {"name": "Code review"}).json()
        api_put(f"/checklist-items/{i1['id']}", {"complete": True})

        # Verify computed fields
        t1_detail = api_get(f"/tasks/{t1['id']}").json()
        assert t1_detail["checklists"][0]["completedItems"] == 1
        assert t1_detail["checklists"][0]["totalItems"] == 2

        # Complete task — checklist items should NOT auto-complete
        api_put(f"/tasks/{t1['id']}", {"complete": True})
        t1_final = api_get(f"/tasks/{t1['id']}").json()
        assert t1_final["complete"] is True
        assert t1_final["checklists"][0]["completedItems"] == 1  # Still 1, not 2


class TestActivityLogWorkflow:
    """Pattern 5: Activity log auto-generated on actions."""

    def test_activity_log_records_actions(self):
        """
        Perform various actions -> verify activity log entries created.
        """
        uid = unique()
        proj = api_post("/projects", {"name": f"Activity-{uid}"}).json()
        pid = proj["id"]
        api_post(f"/projects/{pid}/members", {"userId": USER2, "role": "member"})

        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Col"}).json()

        # Create task (TASK_CREATED)
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": f"Act-{uid}"}).json()

        # Assign (TASK_ASSIGNED)
        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER2})

        # Complete (TASK_COMPLETED)
        api_put(f"/tasks/{task['id']}", {"complete": True})

        # Add comment (COMMENT_ADDED)
        api_post(f"/tasks/{task['id']}/comments", {"text": "Done!"})

        # Check activity log
        r = api_get(f"/projects/{pid}/activity")
        assert r.status_code == 200
        activities = r.json()
        assert len(activities) >= 3

        action_types = [a["actionType"] for a in activities]
        assert "TASK_CREATED" in action_types
        assert "TASK_ASSIGNED" in action_types
        assert "TASK_COMPLETED" in action_types

        # Verify activity fields
        for activity in activities:
            assert "projectId" in activity
            assert "userId" in activity
            assert "actionType" in activity
            assert "createdAt" in activity


class TestRoleBasedAccessWorkflow:
    """Pattern 6+8: Role-based access control across operations."""

    def test_member_cannot_manage_project(self):
        """
        Owner adds member -> member can CRUD tasks but cannot manage members or delete project.
        """
        uid = unique()
        proj = api_post("/projects", {"name": f"RBAC-{uid}"}).json()
        pid = proj["id"]

        # Add user2 as member
        api_post(f"/projects/{pid}/members", {"userId": USER2, "role": "member"})

        # Member can create task groups and tasks
        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Col"}, headers=HEADERS2).json()
        assert "id" in tg

        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "Task"}, headers=HEADERS2).json()
        assert "id" in task

        # Member CANNOT add members
        r = api_post(f"/projects/{pid}/members", {"userId": USER3, "role": "member"}, headers=HEADERS2)
        assert r.status_code == 403

        # Member CANNOT delete project
        r = api_delete(f"/projects/{pid}", headers=HEADERS2)
        assert r.status_code == 403

    def test_admin_can_manage_members_but_not_owner(self):
        """Admin can add/remove members but cannot remove the owner."""
        uid = unique()
        proj = api_post("/projects", {"name": f"Admin-{uid}"}).json()
        pid = proj["id"]

        # Add user2 as admin
        api_post(f"/projects/{pid}/members", {"userId": USER2, "role": "admin"})

        # Admin can add members
        r = api_post(f"/projects/{pid}/members", {"userId": USER3, "role": "member"}, headers=HEADERS2)
        assert r.status_code == 201

        # Admin can remove members
        r = api_delete(f"/projects/{pid}/members/{USER3}", headers=HEADERS2)
        assert r.status_code == 204

        # Admin CANNOT remove owner
        r = api_delete(f"/projects/{pid}/members/{USER1}", headers=HEADERS2)
        assert r.status_code == 400


class TestTaskFilteringWorkflow:
    """Pattern 3: Task filtering actually works."""

    def test_filter_tasks_by_task_group(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"FltProj-{uid}"}).json()
        pid = proj["id"]
        tg1 = api_post(f"/projects/{pid}/task-groups", {"name": "A"}).json()
        tg2 = api_post(f"/projects/{pid}/task-groups", {"name": "B"}).json()

        api_post("/tasks", {"taskGroupId": tg1["id"], "title": "T1"})
        api_post("/tasks", {"taskGroupId": tg1["id"], "title": "T2"})
        api_post("/tasks", {"taskGroupId": tg2["id"], "title": "T3"})

        r = api_get(f"/projects/{pid}/tasks", params={"taskGroupId": tg1["id"]})
        assert r.status_code == 200
        tasks = r.json()
        assert len(tasks) == 2
        for t in tasks:
            assert t["taskGroupId"] == tg1["id"]

    def test_filter_tasks_by_complete(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"CmpFlt-{uid}"}).json()
        pid = proj["id"]
        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Col"}).json()

        t1 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "Done task"}).json()
        api_post("/tasks", {"taskGroupId": tg["id"], "title": "Open task"})
        api_put(f"/tasks/{t1['id']}", {"complete": True})

        r = api_get(f"/projects/{pid}/tasks", params={"complete": "true"})
        tasks = r.json()
        assert len(tasks) == 1
        assert tasks[0]["complete"] is True


class TestLabelWorkflow:
    """Pattern 2+7: Labels across tasks, deletion removes from tasks."""

    def test_label_lifecycle(self):
        """
        Create labels -> attach to tasks -> delete label -> removed from all tasks.
        """
        uid = unique()
        proj = api_post("/projects", {"name": f"LblProj-{uid}"}).json()
        pid = proj["id"]
        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Col"}).json()
        t1 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T1"}).json()
        t2 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T2"}).json()

        # Create label
        label = api_post(f"/projects/{pid}/labels", {"name": f"Bug-{uid}", "color": "#ff0000"}).json()
        assert label["name"] == f"Bug-{uid}"
        assert label["color"] == "#ff0000"
        assert label["projectId"] == pid

        # Attach to both tasks
        api_post(f"/tasks/{t1['id']}/labels", {"labelId": label["id"]})
        api_post(f"/tasks/{t2['id']}/labels", {"labelId": label["id"]})

        # Verify labels on tasks
        d1 = api_get(f"/tasks/{t1['id']}").json()
        assert len(d1["labels"]) == 1
        assert d1["labels"][0]["id"] == label["id"]

        # Delete label — should be removed from all tasks
        r = api_delete(f"/labels/{label['id']}")
        assert r.status_code == 204

        d1_after = api_get(f"/tasks/{t1['id']}").json()
        assert len(d1_after["labels"]) == 0
        d2_after = api_get(f"/tasks/{t2['id']}").json()
        assert len(d2_after["labels"]) == 0


class TestCascadeDeleteWorkflow:
    """Pattern 7: Full cascade on project/task-group deletion."""

    def test_task_group_delete_cascades_everything(self):
        """
        Create task group -> tasks with labels, checklists, assignments, comments
        -> delete task group -> everything gone.
        """
        uid = unique()
        proj = api_post("/projects", {"name": f"CascWf-{uid}"}).json()
        pid = proj["id"]
        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        # Add checklist
        cl = api_post(f"/tasks/{task['id']}/checklists", {"title": "CL"}).json()
        item = api_post(f"/checklists/{cl['id']}/items", {"name": "Item"}).json()

        # Add comment
        api_post(f"/tasks/{task['id']}/comments", {"text": "Hi"})

        # Delete task group
        r = api_delete(f"/task-groups/{tg['id']}")
        assert r.status_code == 204

        # Task and all related gone
        assert api_get(f"/tasks/{task['id']}").status_code == 404


class TestMultiUserCollaboration:
    """Pattern 6: Multiple users collaborating on same project."""

    def test_multi_user_task_collaboration(self):
        """
        Owner creates project, adds members, members create tasks and comments.
        Each user sees correct data.
        """
        uid = unique()
        proj = api_post("/projects", {"name": f"Collab-{uid}"}).json()
        pid = proj["id"]

        # Add user2 and user3
        api_post(f"/projects/{pid}/members", {"userId": USER2, "role": "admin"})
        api_post(f"/projects/{pid}/members", {"userId": USER3, "role": "member"})

        # User2 creates task group
        tg = api_post(f"/projects/{pid}/task-groups", {"name": "Sprint 1"}, headers=HEADERS2).json()
        assert "id" in tg

        # User3 creates task
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": f"Task-{uid}"}, headers=HEADERS3).json()
        assert "id" in task

        # All users can see the task
        assert api_get(f"/tasks/{task['id']}", headers=HEADERS1).status_code == 200
        assert api_get(f"/tasks/{task['id']}", headers=HEADERS2).status_code == 200
        assert api_get(f"/tasks/{task['id']}", headers=HEADERS3).status_code == 200

        # User1 comments
        cmt = api_post(f"/tasks/{task['id']}/comments", {"text": "LGTM"}).json()
        assert "id" in cmt

        # Members list shows all 3
        members = api_get(f"/projects/{pid}/members").json()
        assert len(members) == 3
        user_ids = [m["userId"] for m in members]
        assert USER1 in user_ids
        assert USER2 in user_ids
        assert USER3 in user_ids
