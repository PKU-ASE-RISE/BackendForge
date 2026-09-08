"""
BackendForge — L3 Workflow Tests for Vikunja Task

Each test: 6-12 steps, 12-20 assertions.
Cross 3+ entity types, cover 2+ bug patterns, verify side effects.

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

OWNER_ID = str(uuid.uuid4())
EDITOR_ID = str(uuid.uuid4())
VIEWER_ID = str(uuid.uuid4())
OUTSIDER_ID = str(uuid.uuid4())

OWNER = {"X-User-Id": OWNER_ID, "Content-Type": "application/json"}
EDITOR = {"X-User-Id": EDITOR_ID, "Content-Type": "application/json"}
VIEWER = {"X-User-Id": VIEWER_ID, "Content-Type": "application/json"}
OUTSIDER = {"X-User-Id": OUTSIDER_ID, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _isolated_test_users():
    """Give every workflow private user-scoped state."""
    global OWNER_ID, EDITOR_ID, VIEWER_ID, OUTSIDER_ID
    global OWNER, EDITOR, VIEWER, OUTSIDER

    OWNER_ID = str(uuid.uuid4())
    EDITOR_ID = str(uuid.uuid4())
    VIEWER_ID = str(uuid.uuid4())
    OUTSIDER_ID = str(uuid.uuid4())
    OWNER = {"X-User-Id": OWNER_ID, "Content-Type": "application/json"}
    EDITOR = {"X-User-Id": EDITOR_ID, "Content-Type": "application/json"}
    VIEWER = {"X-User-Id": VIEWER_ID, "Content-Type": "application/json"}
    OUTSIDER = {"X-User-Id": OUTSIDER_ID, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or OWNER, timeout=30)


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or OWNER, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or OWNER, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or OWNER, timeout=30)


# ════════════════════════════════════════════════════════════════════
# L3 Tests — Complex Workflows
# ════════════════════════════════════════════════════════════════════


class TestKanbanBoardWorkflow:
    """Pattern 2+5+7: Full kanban workflow with buckets, limits, task moves."""

    def test_kanban_board_lifecycle(self):
        """
        1. Create project
        2. Create 3 buckets (Backlog, In Progress limit=2, Done)
        3. Create 3 tasks
        4. Move tasks to Backlog
        5. Move 2 tasks to In Progress
        6. Attempt 3rd move to In Progress (should fail - limit)
        7. Move 1 task to Done
        8. Now move 3rd task to In Progress (succeeds)
        9. Verify task bucket_id updated correctly
        10. Verify list tasks shows correct bucket_ids
        """
        # 1. Create project
        proj = post("/api/v1/projects", {"title": "Kanban Board"})
        assert proj.status_code == 201
        pid = proj.json()["id"]

        # 2. Create buckets
        backlog = post(f"/api/v1/projects/{pid}/buckets", {"title": "Backlog", "position": 1.0, "limit": 0})
        assert backlog.status_code == 201
        backlog_id = backlog.json()["id"]

        in_prog = post(f"/api/v1/projects/{pid}/buckets", {"title": "In Progress", "position": 2.0, "limit": 2})
        assert in_prog.status_code == 201
        in_prog_id = in_prog.json()["id"]

        done_b = post(f"/api/v1/projects/{pid}/buckets", {"title": "Done", "position": 3.0, "limit": 0})
        assert done_b.status_code == 201
        done_b_id = done_b.json()["id"]

        # 3. Create 3 tasks
        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task 1"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task 2"}).json()
        t3 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task 3"}).json()

        # 4. Move all to Backlog
        for t in [t1, t2, t3]:
            r = put(f"/api/v1/tasks/{t['id']}/bucket", {"bucket_id": backlog_id})
            assert r.status_code == 200
            assert r.json()["bucket_id"] == backlog_id

        # 5. Move 2 to In Progress
        r = put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": in_prog_id})
        assert r.status_code == 200
        r = put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": in_prog_id})
        assert r.status_code == 200

        # 6. 3rd move should fail (limit=2)
        r = put(f"/api/v1/tasks/{t3['id']}/bucket", {"bucket_id": in_prog_id})
        assert r.status_code == 400

        # 7. Move t1 to Done
        r = put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": done_b_id})
        assert r.status_code == 200
        assert r.json()["bucket_id"] == done_b_id

        # 8. Now t3 can move to In Progress
        r = put(f"/api/v1/tasks/{t3['id']}/bucket", {"bucket_id": in_prog_id})
        assert r.status_code == 200
        assert r.json()["bucket_id"] == in_prog_id

        # 9. Verify final state via GET
        t1_final = get(f"/api/v1/tasks/{t1['id']}").json()
        t2_final = get(f"/api/v1/tasks/{t2['id']}").json()
        t3_final = get(f"/api/v1/tasks/{t3['id']}").json()
        assert t1_final["bucket_id"] == done_b_id
        assert t2_final["bucket_id"] == in_prog_id
        assert t3_final["bucket_id"] == in_prog_id


class TestProjectCollaborationWorkflow:
    """Pattern 6+4+2: Multi-user collaboration with role-based access."""

    def test_full_collaboration_lifecycle(self):
        """
        1. Owner creates project
        2. Add editor and viewer members
        3. Editor creates task
        4. Viewer tries to create task (403)
        5. Editor updates task
        6. Viewer tries to update task (403)
        7. Viewer reads task (200)
        8. Owner adds comment
        9. Editor adds comment
        10. Viewer tries to add comment (403)
        11. Editor tries to delete owner's comment (403)
        12. Owner deletes own comment (204)
        """
        # Ensure users exist
        get("/api/v1/projects", headers=EDITOR)
        get("/api/v1/projects", headers=VIEWER)

        # 1. Owner creates project
        proj = post("/api/v1/projects", {"title": "Collab Project"})
        assert proj.status_code == 201
        pid = proj.json()["id"]
        assert proj.json()["owner_id"] == OWNER_ID

        # 2. Add members
        r = post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "editor"})
        assert r.status_code == 201
        assert r.json()["role"] == "editor"

        r = post(f"/api/v1/projects/{pid}/members", {"user_id": VIEWER_ID, "role": "viewer"})
        assert r.status_code == 201
        assert r.json()["role"] == "viewer"

        # 3. Editor creates task
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Editor's Task", "priority": 3}, headers=EDITOR)
        assert task.status_code == 201
        tid = task.json()["id"]
        assert task.json()["created_by_id"] == EDITOR_ID

        # 4. Viewer cannot create task
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "Nope"}, headers=VIEWER)
        assert r.status_code == 403

        # 5. Editor updates task
        r = put(f"/api/v1/tasks/{tid}", {"title": "Updated by Editor", "priority": 4}, headers=EDITOR)
        assert r.status_code == 200
        assert r.json()["title"] == "Updated by Editor"

        # 6. Viewer cannot update
        r = put(f"/api/v1/tasks/{tid}", {"title": "Hacked"}, headers=VIEWER)
        assert r.status_code == 403

        # 7. Viewer can read
        r = get(f"/api/v1/tasks/{tid}", headers=VIEWER)
        assert r.status_code == 200
        assert r.json()["title"] == "Updated by Editor"

        # 8. Owner adds comment
        c1 = post(f"/api/v1/tasks/{tid}/comments", {"comment": "Owner says hi"})
        assert c1.status_code == 201
        c1_id = c1.json()["id"]

        # 9. Editor adds comment
        c2 = post(f"/api/v1/tasks/{tid}/comments", {"comment": "Editor says hi"}, headers=EDITOR)
        assert c2.status_code == 201

        # 10. Viewer cannot add comment
        r = post(f"/api/v1/tasks/{tid}/comments", {"comment": "Viewer says hi"}, headers=VIEWER)
        assert r.status_code == 403

        # 11. Editor cannot delete owner's comment
        r = delete(f"/api/v1/tasks/{tid}/comments/{c1_id}", headers=EDITOR)
        assert r.status_code == 403

        # 12. Owner deletes own comment
        r = delete(f"/api/v1/tasks/{tid}/comments/{c1_id}")
        assert r.status_code == 204


class TestTaskMetadataFullLifecycle:
    """Pattern 1+2+5: Task with labels, assignees, relations — full lifecycle."""

    def test_task_with_full_metadata(self):
        """
        1. Create project, add member
        2. Create task with priority & due date
        3. Create labels, attach to task
        4. Assign member to task
        5. Create relation to another task
        6. GET task — verify ALL metadata present
        7. Update task (done=true), verify percent_done=1.0
        8. Detach a label, verify removed
        9. Unassign user, verify removed
        10. Delete relation, verify both sides cleared
        """
        # Ensure editor exists
        get("/api/v1/projects", headers=EDITOR)

        # 1. Create project, add member
        proj = post("/api/v1/projects", {"title": "Meta Project"}).json()
        pid = proj["id"]
        post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # 2. Create task
        task = post(f"/api/v1/projects/{pid}/tasks", {
            "title": "Full Meta",
            "priority": 4,
            "due_date": "2025-12-25T00:00:00Z",
            "percent_done": 0.5,
        }).json()
        tid = task["id"]
        assert task["priority"] == 4
        assert task["percent_done"] == 0.5

        # 3. Create and attach labels
        l1 = post("/api/v1/labels", {"title": "Bug", "color": "#ff0000"}).json()
        l2 = post("/api/v1/labels", {"title": "Feature", "color": "#00ff00"}).json()
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": l1["id"]})
        assert r.status_code == 201
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": l2["id"]})
        assert r.status_code == 201

        # 4. Assign member
        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": EDITOR_ID})
        assert r.status_code == 201

        # 5. Create another task and relate
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Related Task"}).json()
        r = post(f"/api/v1/tasks/{tid}/relations", {
            "other_task_id": t2["id"],
            "relation_kind": "blocks",
        })
        assert r.status_code == 201

        # 6. GET task — verify ALL metadata
        full_task = get(f"/api/v1/tasks/{tid}").json()
        assert full_task["title"] == "Full Meta"
        assert full_task["priority"] == 4
        assert full_task["percent_done"] == 0.5
        assert len(full_task["labels"]) == 2
        assert len(full_task["assignees"]) == 1
        assert full_task["assignees"][0]["id"] == EDITOR_ID
        assert "blocks" in full_task["relations"]
        assert t2["id"] in full_task["relations"]["blocks"]
        label_ids = {l["id"] for l in full_task["labels"]}
        assert l1["id"] in label_ids
        assert l2["id"] in label_ids

        # 7. Mark done
        r = put(f"/api/v1/tasks/{tid}", {"title": "Full Meta", "done": True})
        assert r.status_code == 200
        assert r.json()["done"] is True
        assert r.json()["percent_done"] == 1.0

        # 8. Detach label
        r = delete(f"/api/v1/tasks/{tid}/labels/{l1['id']}")
        assert r.status_code == 204
        task_after = get(f"/api/v1/tasks/{tid}").json()
        label_ids_after = {l["id"] for l in task_after["labels"]}
        assert l1["id"] not in label_ids_after
        assert l2["id"] in label_ids_after

        # 9. Unassign
        r = delete(f"/api/v1/tasks/{tid}/assignees/{EDITOR_ID}")
        assert r.status_code == 204
        task_after = get(f"/api/v1/tasks/{tid}").json()
        assert len(task_after["assignees"]) == 0

        # 10. Delete relation
        r = delete(f"/api/v1/tasks/{tid}/relations/blocks/{t2['id']}")
        assert r.status_code == 204
        task_after = get(f"/api/v1/tasks/{tid}").json()
        assert t2["id"] not in task_after["relations"].get("blocks", [])
        t2_after = get(f"/api/v1/tasks/{t2['id']}").json()
        assert tid not in t2_after["relations"].get("blocked_by", [])


class TestProjectDeletionCascadeWorkflow:
    """Pattern 7+2: Delete project cascades to all children entities."""

    def test_project_deletion_cascades_everything(self):
        """
        1. Create project
        2. Create multiple tasks
        3. Create labels, attach to tasks
        4. Create buckets, move tasks to buckets
        5. Add comments to tasks
        6. Add member
        7. Delete project
        8. Verify all tasks 404
        9. Verify buckets 404
        10. Verify comments 404
        11. Verify labels still exist (labels are user-scoped, not project-scoped)
        12. Verify member can no longer see project
        """
        # Ensure editor exists
        get("/api/v1/projects", headers=EDITOR)

        # 1. Create project
        proj = post("/api/v1/projects", {"title": "Cascade All"}).json()
        pid = proj["id"]

        # 2. Create tasks
        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task1"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "Task2"}).json()

        # 3. Create labels and attach
        label = post("/api/v1/labels", {"title": "Persist"}).json()
        post(f"/api/v1/tasks/{t1['id']}/labels", {"label_id": label["id"]})

        # 4. Create bucket
        bucket = post(f"/api/v1/projects/{pid}/buckets", {"title": "Column"}).json()
        put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": bucket["id"]})

        # 5. Add comment
        comment = post(f"/api/v1/tasks/{t1['id']}/comments", {"comment": "Doomed"}).json()

        # 6. Add member
        post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # Verify editor can see project
        r = get(f"/api/v1/projects/{pid}", headers=EDITOR)
        assert r.status_code == 200

        # 7. Delete project
        r = delete(f"/api/v1/projects/{pid}")
        assert r.status_code == 204

        # 8. Tasks are 404
        assert get(f"/api/v1/tasks/{t1['id']}").status_code == 404
        assert get(f"/api/v1/tasks/{t2['id']}").status_code == 404

        # 9. Buckets 404 (project gone)
        assert get(f"/api/v1/projects/{pid}/buckets/{bucket['id']}").status_code == 404

        # 10. Comments 404 (task gone)
        assert get(f"/api/v1/tasks/{t1['id']}/comments/{comment['id']}").status_code == 404

        # 11. Label still exists (user-scoped, not project-scoped)
        r = get(f"/api/v1/labels/{label['id']}")
        assert r.status_code == 200
        assert r.json()["title"] == "Persist"

        # 12. Project gone from editor's list
        r = get("/api/v1/projects", headers=EDITOR)
        pids = [p["id"] for p in r.json()]
        assert pid not in pids


class TestProjectHierarchyAccessWorkflow:
    """Pattern 6+8: Parent/child project access inheritance."""

    def test_parent_access_grants_child_access_not_reverse(self):
        """
        1. Create parent project
        2. Create child project under parent
        3. Add editor to parent only
        4. Editor can access parent (200)
        5. Editor can access child (200, inherited)
        6. Create outsider, add to child only
        7. Outsider can access child (200)
        8. Outsider cannot access parent (403)
        9. Editor creates task in child (200, inherited permission)
        10. Outsider cannot access tasks in parent
        """
        get("/api/v1/projects", headers=EDITOR)
        get("/api/v1/projects", headers=OUTSIDER)

        # 1. Parent project
        parent = post("/api/v1/projects", {"title": "Parent Proj"}).json()
        parent_id = parent["id"]

        # 2. Child project
        child = post("/api/v1/projects", {
            "title": "Child Proj",
            "parent_project_id": parent_id,
        }).json()
        child_id = child["id"]
        assert child["parent_project_id"] == parent_id

        # 3. Add editor to parent
        r = post(f"/api/v1/projects/{parent_id}/members", {"user_id": EDITOR_ID, "role": "editor"})
        assert r.status_code == 201

        # 4. Editor can access parent
        r = get(f"/api/v1/projects/{parent_id}", headers=EDITOR)
        assert r.status_code == 200

        # 5. Editor can access child (inherited)
        r = get(f"/api/v1/projects/{child_id}", headers=EDITOR)
        assert r.status_code == 200

        # 6. Add outsider to child only
        r = post(f"/api/v1/projects/{child_id}/members", {"user_id": OUTSIDER_ID, "role": "editor"})
        assert r.status_code == 201

        # 7. Outsider can access child
        r = get(f"/api/v1/projects/{child_id}", headers=OUTSIDER)
        assert r.status_code == 200

        # 8. Outsider cannot access parent
        r = get(f"/api/v1/projects/{parent_id}", headers=OUTSIDER)
        assert r.status_code == 403

        # 9. Editor creates task in child
        r = post(f"/api/v1/projects/{child_id}/tasks", {"title": "Child Task"}, headers=EDITOR)
        assert r.status_code == 201
        assert r.json()["project_id"] == child_id

        # 10. Create task in parent, outsider can't access
        parent_task = post(f"/api/v1/projects/{parent_id}/tasks", {"title": "Parent Task"}).json()
        r = get(f"/api/v1/tasks/{parent_task['id']}", headers=OUTSIDER)
        assert r.status_code == 403


class TestTaskRelationDeleteCascadeWorkflow:
    """Pattern 7+5: Relations cleaned up when tasks deleted."""

    def test_delete_task_with_multiple_relations(self):
        """
        1. Create project with 3 tasks (A, B, C)
        2. A blocks B
        3. A is related to C
        4. Verify A has 2 relations
        5. Verify B has blocked_by A
        6. Verify C has related A
        7. Delete task A
        8. B no longer has blocked_by A
        9. C no longer has related A
        10. B and C still exist with their own data
        """
        proj = post("/api/v1/projects", {"title": "RelCascade"}).json()
        pid = proj["id"]

        # 1. Create 3 tasks
        a = post(f"/api/v1/projects/{pid}/tasks", {"title": "A"}).json()
        b = post(f"/api/v1/projects/{pid}/tasks", {"title": "B"}).json()
        c = post(f"/api/v1/projects/{pid}/tasks", {"title": "C"}).json()

        # 2. A blocks B
        r = post(f"/api/v1/tasks/{a['id']}/relations", {
            "other_task_id": b["id"], "relation_kind": "blocks"
        })
        assert r.status_code == 201

        # 3. A related to C
        r = post(f"/api/v1/tasks/{a['id']}/relations", {
            "other_task_id": c["id"], "relation_kind": "related"
        })
        assert r.status_code == 201

        # 4. Verify A has 2 relation types
        a_data = get(f"/api/v1/tasks/{a['id']}").json()
        assert b["id"] in a_data["relations"].get("blocks", [])
        assert c["id"] in a_data["relations"].get("related", [])

        # 5. B has blocked_by
        b_data = get(f"/api/v1/tasks/{b['id']}").json()
        assert a["id"] in b_data["relations"].get("blocked_by", [])

        # 6. C has related
        c_data = get(f"/api/v1/tasks/{c['id']}").json()
        assert a["id"] in c_data["relations"].get("related", [])

        # 7. Delete A
        r = delete(f"/api/v1/tasks/{a['id']}")
        assert r.status_code == 204

        # 8. B no longer has blocked_by A
        b_data = get(f"/api/v1/tasks/{b['id']}").json()
        assert a["id"] not in b_data["relations"].get("blocked_by", [])

        # 9. C no longer has related A
        c_data = get(f"/api/v1/tasks/{c['id']}").json()
        assert a["id"] not in c_data["relations"].get("related", [])

        # 10. B and C still exist
        assert b_data["title"] == "B"
        assert c_data["title"] == "C"


class TestFilteringAndSortingCombined:
    """Pattern 3+5: Filtering and sorting work together correctly."""

    def test_filter_and_sort_combined(self):
        """
        1. Create project
        2. Create 5 tasks with varying priority, done status
        3. Filter done=false + sort by priority desc
        4. Verify only undone tasks returned
        5. Verify order is correct
        6. Filter priority>=3 + sort by priority asc
        7. Verify only high priority tasks
        8. Verify ascending order
        9. Filter done=true
        10. Verify only done tasks
        """
        proj = post("/api/v1/projects", {"title": "FilterSort"}).json()
        pid = proj["id"]

        # 2. Create diverse tasks
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P1-undone", "priority": 1, "done": False})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P5-undone", "priority": 5, "done": False})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P3-done", "priority": 3, "done": True})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P4-undone", "priority": 4, "done": False})
        post(f"/api/v1/projects/{pid}/tasks", {"title": "P2-done", "priority": 2, "done": True})

        # 3. Filter undone + sort priority desc
        r = get(f"/api/v1/projects/{pid}/tasks", params={
            "filter_done": "false", "sort_by": "priority", "order_by": "desc"
        })
        assert r.status_code == 200
        tasks = r.json()

        # 4. Only undone tasks
        assert len(tasks) == 3
        assert all(t["done"] is False for t in tasks)

        # 5. Priority descending
        priorities = [t["priority"] for t in tasks]
        assert priorities == sorted(priorities, reverse=True)
        assert priorities[0] == 5

        # 6. Filter priority>=3 + sort asc
        r = get(f"/api/v1/projects/{pid}/tasks", params={
            "filter_priority": 3, "sort_by": "priority", "order_by": "asc"
        })
        assert r.status_code == 200
        tasks = r.json()

        # 7. Only priority >= 3
        assert len(tasks) == 3  # P3-done, P4-undone, P5-undone
        assert all(t["priority"] >= 3 for t in tasks)

        # 8. Ascending order
        priorities = [t["priority"] for t in tasks]
        assert priorities == sorted(priorities)

        # 9. Filter done=true
        r = get(f"/api/v1/projects/{pid}/tasks", params={"filter_done": "true"})
        assert r.status_code == 200
        tasks = r.json()

        # 10. Only done tasks
        assert len(tasks) == 2
        assert all(t["done"] is True for t in tasks)


class TestLabelScopingAndCrossUserIsolation:
    """Pattern 6+8: Labels are user-scoped, cross-user attacks blocked."""

    def test_label_scoping_full_workflow(self):
        """
        1. Owner creates labels
        2. Editor creates their own labels (different)
        3. Owner lists labels - only sees own
        4. Editor lists labels - only sees own
        5. Owner creates project, adds editor
        6. Owner creates task
        7. Owner attaches own label to task (OK)
        8. Editor tries to attach their label to owner's task (400)
        9. Editor creates their own label and attaches (since they are editor and own the label)
        10. Verify task has only owner's label attached
        """
        get("/api/v1/projects", headers=EDITOR)

        # 1. Owner creates labels
        ol1 = post("/api/v1/labels", {"title": "Owner-Bug", "color": "#red"}).json()
        ol2 = post("/api/v1/labels", {"title": "Owner-Feature"}).json()

        # 2. Editor creates labels
        el1 = post("/api/v1/labels", {"title": "Editor-Bug"}, headers=EDITOR).json()

        # 3. Owner only sees own
        r = get("/api/v1/labels")
        owner_labels = r.json()
        owner_label_ids = {l["id"] for l in owner_labels}
        assert ol1["id"] in owner_label_ids
        assert ol2["id"] in owner_label_ids
        assert el1["id"] not in owner_label_ids

        # 4. Editor only sees own
        r = get("/api/v1/labels", headers=EDITOR)
        editor_labels = r.json()
        editor_label_ids = {l["id"] for l in editor_labels}
        assert el1["id"] in editor_label_ids
        assert ol1["id"] not in editor_label_ids

        # 5. Create project, add editor
        proj = post("/api/v1/projects", {"title": "Label Scope Proj"}).json()
        pid = proj["id"]
        post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # 6. Create task
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Label Test"}).json()
        tid = task["id"]

        # 7. Owner attaches own label
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": ol1["id"]})
        assert r.status_code == 201

        # 8. Editor tries to attach THEIR label (should fail - not their label as seen by task owner context)
        # Actually, the editor attaches from their own context — label_id belongs to editor
        # The rule is: "Attaching a label you don't own to a task returns 400"
        # Editor using their own label should work since they own it
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": el1['id']}, headers=EDITOR)
        assert r.status_code == 201

        # 9. Owner tries to attach editor's label (should fail - owner doesn't own editor's label)
        r = post(f"/api/v1/tasks/{tid}/labels", {"label_id": el1["id"]})
        assert r.status_code == 400

        # 10. Verify task has both labels from respective owners
        task_data = get(f"/api/v1/tasks/{tid}").json()
        task_label_ids = {l["id"] for l in task_data["labels"]}
        assert ol1["id"] in task_label_ids
        assert el1["id"] in task_label_ids


class TestMemberManagementWorkflow:
    """Pattern 6+4: Member CRUD with permission enforcement."""

    def test_member_role_lifecycle(self):
        """
        1. Create project
        2. Add user as viewer
        3. Verify viewer in members list
        4. Viewer can read but not write
        5. Upgrade viewer to editor
        6. Now editor can create tasks
        7. Downgrade back to viewer
        8. Cannot create tasks again
        9. Remove member
        10. Member gets 403 on project access
        """
        get("/api/v1/projects", headers=EDITOR)

        # 1. Create project
        proj = post("/api/v1/projects", {"title": "Member Lifecycle"}).json()
        pid = proj["id"]

        # 2. Add as viewer
        r = post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "viewer"})
        assert r.status_code == 201
        assert r.json()["role"] == "viewer"

        # 3. Verify in members list
        r = get(f"/api/v1/projects/{pid}/members")
        assert r.status_code == 200
        members = r.json()
        member_map = {m["user_id"]: m["role"] for m in members}
        assert EDITOR_ID in member_map
        assert member_map[EDITOR_ID] == "viewer"
        assert OWNER_ID in member_map

        # 4. Viewer cannot write
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "Nope"}, headers=EDITOR)
        assert r.status_code == 403

        # 5. Upgrade to editor
        r = put(f"/api/v1/projects/{pid}/members/{EDITOR_ID}", {"role": "editor"})
        assert r.status_code == 200
        assert r.json()["role"] == "editor"

        # 6. Now can create tasks
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "Editor Task"}, headers=EDITOR)
        assert r.status_code == 201
        tid = r.json()["id"]

        # 7. Downgrade to viewer
        r = put(f"/api/v1/projects/{pid}/members/{EDITOR_ID}", {"role": "viewer"})
        assert r.status_code == 200

        # 8. Cannot create tasks again
        r = post(f"/api/v1/projects/{pid}/tasks", {"title": "Nope Again"}, headers=EDITOR)
        assert r.status_code == 403

        # 9. Remove member
        r = delete(f"/api/v1/projects/{pid}/members/{EDITOR_ID}")
        assert r.status_code == 204

        # 10. No access
        r = get(f"/api/v1/projects/{pid}", headers=EDITOR)
        assert r.status_code == 403


class TestTaskAssigneeValidationWorkflow:
    """Pattern 5+6+8: Assignee must be project member, cross-validated."""

    def test_assignee_must_be_project_member(self):
        """
        1. Create project
        2. Add editor as member
        3. Create task
        4. Assign editor (OK - is member)
        5. Try assign outsider (400 - not member)
        6. Verify assignees list correct
        7. Add outsider as member
        8. Now assign outsider (OK)
        9. Remove outsider from project (but keep assignee? — implementation may cascade)
        10. Verify task state
        """
        get("/api/v1/projects", headers=EDITOR)
        get("/api/v1/projects", headers=OUTSIDER)

        # 1. Create project
        proj = post("/api/v1/projects", {"title": "Assignee Validation"}).json()
        pid = proj["id"]

        # 2. Add editor
        post(f"/api/v1/projects/{pid}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # 3. Create task
        task = post(f"/api/v1/projects/{pid}/tasks", {"title": "Assign Test"}).json()
        tid = task["id"]

        # 4. Assign editor (OK)
        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": EDITOR_ID})
        assert r.status_code == 201
        assert r.json()["id"] == EDITOR_ID

        # 5. Assign outsider (not member - 400)
        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": OUTSIDER_ID})
        assert r.status_code == 400

        # 6. Verify assignees
        task_data = get(f"/api/v1/tasks/{tid}").json()
        assert len(task_data["assignees"]) == 1
        assert task_data["assignees"][0]["id"] == EDITOR_ID

        # 7. Add outsider as member
        post(f"/api/v1/projects/{pid}/members", {"user_id": OUTSIDER_ID, "role": "editor"})

        # 8. Now assign outsider (OK)
        r = post(f"/api/v1/tasks/{tid}/assignees", {"user_id": OUTSIDER_ID})
        assert r.status_code == 201

        # 9. Verify both assigned
        task_data = get(f"/api/v1/tasks/{tid}").json()
        assignee_ids = {a["id"] for a in task_data["assignees"]}
        assert EDITOR_ID in assignee_ids
        assert OUTSIDER_ID in assignee_ids

        # 10. Unassign editor
        r = delete(f"/api/v1/tasks/{tid}/assignees/{EDITOR_ID}")
        assert r.status_code == 204
        task_data = get(f"/api/v1/tasks/{tid}").json()
        assert len(task_data["assignees"]) == 1
        assert task_data["assignees"][0]["id"] == OUTSIDER_ID


class TestDeleteBucketWithTasksWorkflow:
    """Pattern 5+7: Cannot delete bucket with tasks; must move first."""

    def test_bucket_delete_requires_empty(self):
        """
        1. Create project
        2. Create 2 buckets
        3. Create tasks
        4. Move tasks to bucket A
        5. Try delete bucket A (400 - has tasks)
        6. Move tasks to bucket B
        7. Delete bucket A (204 - now empty)
        8. Verify bucket A is gone
        9. Verify tasks still in bucket B
        """
        proj = post("/api/v1/projects", {"title": "BucketDel"}).json()
        pid = proj["id"]

        # 2. Create buckets
        ba = post(f"/api/v1/projects/{pid}/buckets", {"title": "A"}).json()
        bb = post(f"/api/v1/projects/{pid}/buckets", {"title": "B"}).json()

        # 3. Create tasks
        t1 = post(f"/api/v1/projects/{pid}/tasks", {"title": "T1"}).json()
        t2 = post(f"/api/v1/projects/{pid}/tasks", {"title": "T2"}).json()

        # 4. Move to bucket A
        put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": ba["id"]})
        put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": ba["id"]})

        # 5. Cannot delete bucket A
        r = delete(f"/api/v1/projects/{pid}/buckets/{ba['id']}")
        assert r.status_code == 400

        # 6. Move tasks to B
        put(f"/api/v1/tasks/{t1['id']}/bucket", {"bucket_id": bb["id"]})
        put(f"/api/v1/tasks/{t2['id']}/bucket", {"bucket_id": bb["id"]})

        # 7. Now delete A
        r = delete(f"/api/v1/projects/{pid}/buckets/{ba['id']}")
        assert r.status_code == 204

        # 8. Bucket A is gone
        r = get(f"/api/v1/projects/{pid}/buckets/{ba['id']}")
        assert r.status_code == 404

        # 9. Tasks still in B
        t1_data = get(f"/api/v1/tasks/{t1['id']}").json()
        t2_data = get(f"/api/v1/tasks/{t2['id']}").json()
        assert t1_data["bucket_id"] == bb["id"]
        assert t2_data["bucket_id"] == bb["id"]


class TestProjectListingVisibility:
    """Pattern 6+2: Project listing respects ownership and membership."""

    def test_project_listing_correctness(self):
        """
        1. Owner creates project A
        2. Owner creates project B
        3. Editor not a member of anything yet
        4. Editor's project list doesn't include A or B
        5. Add editor to project A
        6. Editor's list includes A but not B
        7. Add editor to project B
        8. Editor's list includes both
        9. Remove editor from A
        10. Editor only sees B
        """
        get("/api/v1/projects", headers=EDITOR)

        # 1-2. Create projects
        pa = post("/api/v1/projects", {"title": f"ListA-{uuid.uuid4().hex[:6]}"}).json()
        pb = post("/api/v1/projects", {"title": f"ListB-{uuid.uuid4().hex[:6]}"}).json()

        # 4. Editor sees neither
        r = get("/api/v1/projects", headers=EDITOR)
        editor_pids = {p["id"] for p in r.json()}
        assert pa["id"] not in editor_pids
        assert pb["id"] not in editor_pids

        # 5. Add editor to A
        post(f"/api/v1/projects/{pa['id']}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # 6. Editor sees A but not B
        r = get("/api/v1/projects", headers=EDITOR)
        editor_pids = {p["id"] for p in r.json()}
        assert pa["id"] in editor_pids
        assert pb["id"] not in editor_pids

        # 7. Add editor to B
        post(f"/api/v1/projects/{pb['id']}/members", {"user_id": EDITOR_ID, "role": "editor"})

        # 8. Editor sees both
        r = get("/api/v1/projects", headers=EDITOR)
        editor_pids = {p["id"] for p in r.json()}
        assert pa["id"] in editor_pids
        assert pb["id"] in editor_pids

        # 9. Remove from A
        delete(f"/api/v1/projects/{pa['id']}/members/{EDITOR_ID}")

        # 10. Editor only sees B
        r = get("/api/v1/projects", headers=EDITOR)
        editor_pids = {p["id"] for p in r.json()}
        assert pa["id"] not in editor_pids
        assert pb["id"] in editor_pids
