"""
TaskCafe — L2 Integration Tests (Adversarial)

Targets LLM bug patterns:
- Pattern 1: camelCase fields (taskGroupId, dueDate, createdAt, assignedMembers)
- Pattern 2: Nested data (task detail with checklists, labels, members)
- Pattern 3: Filtering actually implemented
- Pattern 4: Exact status codes (201, 204, 403, 409)
- Pattern 5: Computed values (checklist completedItems/totalItems)
- Pattern 6: Project membership data isolation
- Pattern 7: Cascade deletes
- Pattern 8: Duplicate prevention, role constraints

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


class TestProjectCreation:
    """Pattern 1+4: Project fields and auto-owner membership."""

    def test_create_project_returns_201_with_owner(self):
        uid = unique()
        r = api_post("/projects", {"name": f"Proj-{uid}"})
        assert r.status_code == 201
        proj = r.json()
        assert "id" in proj
        assert proj["name"] == f"Proj-{uid}"
        assert "createdAt" in proj
        assert "members" in proj
        assert len(proj["members"]) == 1
        assert proj["members"][0]["userId"] == USER1
        assert proj["members"][0]["role"] == "owner"

    def test_project_detail_has_members(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"Detail-{uid}"}).json()
        r = api_get(f"/projects/{proj['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["id"] == proj["id"]
        assert len(detail["members"]) >= 1


class TestProjectMembership:
    """Pattern 6+8: Membership and access control."""

    def test_non_member_gets_403(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"Private-{uid}"}).json()
        r = api_get(f"/projects/{proj['id']}", headers=HEADERS2)
        assert r.status_code == 403

    def test_add_member_then_can_access(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"AddMem-{uid}"}).json()
        r = api_post(f"/projects/{proj['id']}/members", {"userId": USER2, "role": "member"})
        assert r.status_code == 201

        # User2 can now access
        r2 = api_get(f"/projects/{proj['id']}", headers=HEADERS2)
        assert r2.status_code == 200

    def test_duplicate_member_returns_409(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"DupMem-{uid}"}).json()
        api_post(f"/projects/{proj['id']}/members", {"userId": USER2, "role": "member"})
        r = api_post(f"/projects/{proj['id']}/members", {"userId": USER2, "role": "admin"})
        assert r.status_code == 409

    def test_cannot_remove_owner(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"NoRmOwn-{uid}"}).json()
        r = api_delete(f"/projects/{proj['id']}/members/{USER1}")
        assert r.status_code == 400


class TestTaskGroupAndTasks:
    """Pattern 1+2: Task groups and tasks with correct field names."""

    def test_task_group_fields(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"TGProj-{uid}"}).json()
        r = api_post(f"/projects/{proj['id']}/task-groups", {"name": f"Todo-{uid}"})
        assert r.status_code == 201
        tg = r.json()
        assert "id" in tg
        assert "projectId" in tg
        assert tg["projectId"] == proj["id"]
        assert tg["name"] == f"Todo-{uid}"
        assert "position" in tg
        assert "createdAt" in tg

    def test_task_create_and_fields(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"TskProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Backlog"}).json()

        r = api_post("/tasks", {
            "taskGroupId": tg["id"],
            "title": f"Task-{uid}",
            "description": "A task"
        })
        assert r.status_code == 201
        task = r.json()
        assert task["title"] == f"Task-{uid}"
        assert task["taskGroupId"] == tg["id"]
        assert task["complete"] is False
        assert "id" in task
        assert "position" in task
        assert "createdAt" in task

    def test_task_auto_position(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"PosProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()

        t1 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T1"}).json()
        t2 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T2"}).json()
        # Second task should have higher position
        assert t2["position"] > t1["position"]


class TestTaskDetail:
    """Pattern 2: Task detail includes nested assignedMembers, labels, checklists."""

    def test_task_detail_nested_data(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"DetProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": f"Det-{uid}"}).json()

        # Add assignment
        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER1})

        # Add label
        label = api_post(f"/projects/{proj['id']}/labels", {"name": "Bug", "color": "#ff0000"}).json()
        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})

        # Add checklist with items
        cl = api_post(f"/tasks/{task['id']}/checklists", {"title": "Steps"}).json()
        api_post(f"/checklists/{cl['id']}/items", {"name": "Step 1"})
        api_post(f"/checklists/{cl['id']}/items", {"name": "Step 2"})

        # Get task detail
        detail = api_get(f"/tasks/{task['id']}").json()
        assert "assignedMembers" in detail
        assert USER1 in detail["assignedMembers"]
        assert "labels" in detail
        assert len(detail["labels"]) == 1
        assert detail["labels"][0]["id"] == label["id"]
        assert "checklists" in detail
        assert len(detail["checklists"]) == 1
        assert detail["checklists"][0]["totalItems"] == 2
        assert detail["checklists"][0]["completedItems"] == 0


class TestChecklistComputed:
    """Pattern 5: Checklist completedItems/totalItems computed."""

    def test_checklist_completed_count(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"CLProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "CL Task"}).json()
        cl = api_post(f"/tasks/{task['id']}/checklists", {"title": "Checklist"}).json()

        i1 = api_post(f"/checklists/{cl['id']}/items", {"name": "Item 1"}).json()
        i2 = api_post(f"/checklists/{cl['id']}/items", {"name": "Item 2"}).json()
        i3 = api_post(f"/checklists/{cl['id']}/items", {"name": "Item 3"}).json()

        # Mark 2 complete
        api_put(f"/checklist-items/{i1['id']}", {"complete": True})
        api_put(f"/checklist-items/{i3['id']}", {"complete": True})

        detail = api_get(f"/tasks/{task['id']}").json()
        cl_data = detail["checklists"][0]
        assert cl_data["totalItems"] == 3
        assert cl_data["completedItems"] == 2


class TestDuplicatePrevention:
    """Pattern 8: Cannot assign/label same thing twice."""

    def test_duplicate_assignment_returns_409(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"DupAsgn-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        api_post(f"/tasks/{task['id']}/assignments", {"userId": USER1})
        r = api_post(f"/tasks/{task['id']}/assignments", {"userId": USER1})
        assert r.status_code == 409

    def test_duplicate_label_on_task_returns_409(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"DupLbl-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()
        label = api_post(f"/projects/{proj['id']}/labels", {"name": "Bug", "color": "#f00"}).json()

        api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        r = api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        assert r.status_code == 409


class TestAssignmentValidation:
    """Pattern 8: Can only assign project members."""

    def test_assign_non_member_returns_400(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"NonMem-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        # USER3 is not a member
        r = api_post(f"/tasks/{task['id']}/assignments", {"userId": USER3})
        assert r.status_code == 400


class TestCascadeDelete:
    """Pattern 7: Cascade deletes."""

    def test_delete_task_group_cascades_tasks(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"CascProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        t1 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T1"}).json()
        t2 = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T2"}).json()

        r = api_delete(f"/task-groups/{tg['id']}")
        assert r.status_code == 204

        assert api_get(f"/tasks/{t1['id']}").status_code == 404
        assert api_get(f"/tasks/{t2['id']}").status_code == 404

    def test_delete_project_cascades_all(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"DelProj-{uid}"}).json()
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        r = api_delete(f"/projects/{proj['id']}")
        assert r.status_code == 204

        assert api_get(f"/projects/{proj['id']}").status_code in (403, 404)
        assert api_get(f"/tasks/{task['id']}").status_code in (403, 404)


class TestCommentAuthorRestriction:
    """Pattern 8: Only comment author can edit/delete."""

    def test_non_author_cannot_edit_comment(self):
        uid = unique()
        proj = api_post("/projects", {"name": f"CmtProj-{uid}"}).json()
        api_post(f"/projects/{proj['id']}/members", {"userId": USER2, "role": "member"})
        tg = api_post(f"/projects/{proj['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        # User1 adds comment
        cmt = api_post(f"/tasks/{task['id']}/comments", {"text": "Hello"}).json()

        # User2 tries to edit — 403
        r = api_put(f"/comments/{cmt['id']}", {"text": "Hacked"}, headers=HEADERS2)
        assert r.status_code == 403


class TestAuthValidation:
    """Pattern 4: Auth header validation."""

    def test_missing_header_returns_401(self):
        r = requests.get(f"{BASE_URL}/projects", timeout=30)
        assert r.status_code == 401

    def test_invalid_uuid_returns_401(self):
        r = requests.get(f"{BASE_URL}/projects", headers={"X-User-Id": "not-a-uuid"}, timeout=30)
        assert r.status_code == 401


class TestLabelProjectScope:
    """Pattern 8: Labels scoped to project."""

    def test_cross_project_label_rejected(self):
        uid = unique()
        proj1 = api_post("/projects", {"name": f"LP1-{uid}"}).json()
        proj2 = api_post("/projects", {"name": f"LP2-{uid}"}).json()
        tg = api_post(f"/projects/{proj2['id']}/task-groups", {"name": "Col"}).json()
        task = api_post("/tasks", {"taskGroupId": tg["id"], "title": "T"}).json()

        # Label from proj1
        label = api_post(f"/projects/{proj1['id']}/labels", {"name": "Bug", "color": "#f00"}).json()

        # Try to add proj1 label to proj2 task
        r = api_post(f"/tasks/{task['id']}/labels", {"labelId": label["id"]})
        assert r.status_code == 400
