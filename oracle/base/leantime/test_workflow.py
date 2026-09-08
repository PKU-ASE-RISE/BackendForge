"""
BackendForge — L3 Workflow Tests for Leantime
"""
import os, uuid, requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RUN_ID = uuid.uuid4()
USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
HA = {"X-User-Id": USER_A, "X-Org-Id": ORG_A, "Content-Type": "application/json"}
HB_ORG = {"X-User-Id": USER_B, "X-Org-Id": ORG_A, "Content-Type": "application/json"}  # same org, different user
H_OTHER_ORG = {"X-User-Id": USER_A, "X-Org-Id": ORG_B, "Content-Type": "application/json"}
U = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_identity(request):
    """Give every item a fresh namespace while preserving within-test identities."""
    global USER_A, USER_B, ORG_A, ORG_B, U

    node_id = request.node.nodeid
    USER_A = str(uuid.uuid5(RUN_ID, f"{node_id}:user"))
    USER_B = str(uuid.uuid5(RUN_ID, f"{node_id}:other-user"))
    ORG_A = str(uuid.uuid5(RUN_ID, f"{node_id}:org"))
    ORG_B = str(uuid.uuid5(RUN_ID, f"{node_id}:other-org"))
    U = uuid.uuid5(RUN_ID, f"{node_id}:marker").hex[:8]
    HA.update({"X-User-Id": USER_A, "X-Org-Id": ORG_A})
    HB_ORG.update({"X-User-Id": USER_B, "X-Org-Id": ORG_A})
    H_OTHER_ORG.update({"X-User-Id": USER_A, "X-Org-Id": ORG_B})

def get(p, params=None, h=None): return requests.get(f"{BASE_URL}{p}", params=params, headers=h or HA, timeout=30)
def post(p, json=None, h=None): return requests.post(f"{BASE_URL}{p}", json=json, headers=h or HA, timeout=30)
def put(p, json=None, h=None): return requests.put(f"{BASE_URL}{p}", json=json, headers=h or HA, timeout=30)
def delete(p, h=None): return requests.delete(f"{BASE_URL}{p}", headers=h or HA, timeout=30)


class TestTaskStatusTransitions:
    """Pattern 5+8: Valid/invalid status transitions."""

    def test_valid_transitions_workflow(self):
        """new -> in_progress -> done -> in_progress (reopen)."""
        proj = post("/projects", {"name": f"Trans-{U}"}).json()
        task = post("/tasks", {"title": "ttask", "project_id": proj["id"]}).json()
        assert task["status"] == "new"

        # new -> in_progress
        r = put(f"/tasks/{task['id']}", {"status": "in_progress"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

        # in_progress -> done
        r = put(f"/tasks/{task['id']}", {"status": "done"})
        assert r.status_code == 200
        assert r.json()["status"] == "done"

        # done -> in_progress (reopen)
        r = put(f"/tasks/{task['id']}", {"status": "in_progress"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_invalid_transition_returns_422(self):
        """new -> done is invalid."""
        proj = post("/projects", {"name": f"InvTrans-{U}"}).json()
        task = post("/tasks", {"title": "inv", "project_id": proj["id"]}).json()

        r = put(f"/tasks/{task['id']}", {"status": "done"})
        assert r.status_code == 422

    def test_same_status_is_noop(self):
        """Setting same status should succeed."""
        proj = post("/projects", {"name": f"Noop-{U}"}).json()
        task = post("/tasks", {"title": "noop", "project_id": proj["id"]}).json()
        r = put(f"/tasks/{task['id']}", {"status": "new"})
        assert r.status_code == 200


class TestProjectLifecycle:
    """Pattern 5+7: Project closure rule and cascade delete."""

    def test_cannot_close_project_with_open_milestones(self):
        """Project closure blocked by non-completed milestones."""
        proj = post("/projects", {"name": f"Close-{U}"}).json()
        post("/milestones", {"title": "ms", "project_id": proj["id"]})

        r = put(f"/projects/{proj['id']}", {"status": "closed"})
        assert r.status_code == 409

    def test_can_close_project_when_milestones_completed(self):
        """Project can close when all milestones completed."""
        proj = post("/projects", {"name": f"CloseOK-{U}"}).json()
        ms = post("/milestones", {"title": "ms", "project_id": proj["id"]}).json()
        put(f"/milestones/{ms['id']}", {"status": "completed"})

        r = put(f"/projects/{proj['id']}", {"status": "closed"})
        assert r.status_code == 200
        assert r.json()["status"] == "closed"

    def test_delete_project_cascades_everything(self):
        """Deleting project removes milestones, tasks, goals."""
        proj = post("/projects", {"name": f"Casc-{U}"}).json()
        ms = post("/milestones", {"title": "cms", "project_id": proj["id"]}).json()
        task = post("/tasks", {"title": "ctask", "project_id": proj["id"]}).json()
        goal = post("/goals", {"title": "cgoal", "project_id": proj["id"], "metric_type": "number", "target_value": 10}).json()

        r = delete(f"/projects/{proj['id']}")
        assert r.status_code == 204

        assert get(f"/milestones/{ms['id']}").status_code == 404
        assert get(f"/tasks/{task['id']}").status_code == 404
        assert get(f"/goals/{goal['id']}").status_code == 404


class TestMilestoneDeletionConstraint:
    """Pattern 7+8: Milestone with tasks can't be deleted."""

    def test_cannot_delete_milestone_with_tasks(self):
        proj = post("/projects", {"name": f"MSDel-{U}"}).json()
        ms = post("/milestones", {"title": "ms", "project_id": proj["id"]}).json()
        post("/tasks", {"title": "blocking", "project_id": proj["id"], "milestone_id": ms["id"]})

        r = delete(f"/milestones/{ms['id']}")
        assert r.status_code == 409

    def test_can_delete_milestone_without_tasks(self):
        proj = post("/projects", {"name": f"MSDelOK-{U}"}).json()
        ms = post("/milestones", {"title": "empty-ms", "project_id": proj["id"]}).json()
        r = delete(f"/milestones/{ms['id']}")
        assert r.status_code == 204


class TestSprintVelocityWorkflow:
    """Pattern 5+7: Sprint velocity computed from done tasks."""

    def test_sprint_velocity_computed_correctly(self):
        """Velocity = sum of estimated_hours of done tasks in sprint."""
        proj = post("/projects", {"name": f"Vel-{U}"}).json()
        sprint = post("/sprints", {"name": "s1", "project_id": proj["id"], "start_date": "2024-01-01", "end_date": "2024-01-14"}).json()

        # Create tasks with different estimated hours
        t1 = post("/tasks", {"title": "vt1", "project_id": proj["id"], "estimated_hours": 5}).json()
        t2 = post("/tasks", {"title": "vt2", "project_id": proj["id"], "estimated_hours": 3}).json()
        t3 = post("/tasks", {"title": "vt3", "project_id": proj["id"], "estimated_hours": 8}).json()

        # Add tasks to sprint
        post(f"/sprints/{sprint['id']}/tasks", {"task_id": t1["id"]})
        post(f"/sprints/{sprint['id']}/tasks", {"task_id": t2["id"]})
        post(f"/sprints/{sprint['id']}/tasks", {"task_id": t3["id"]})

        # Complete t1 and t2
        put(f"/tasks/{t1['id']}", {"status": "in_progress"})
        put(f"/tasks/{t1['id']}", {"status": "done"})
        put(f"/tasks/{t2['id']}", {"status": "in_progress"})
        put(f"/tasks/{t2['id']}", {"status": "done"})

        # Get velocity
        r = get(f"/sprints/{sprint['id']}/velocity")
        assert r.status_code == 200
        data = r.json()
        assert data["velocity"] == 8  # 5 + 3
        assert data["completed_tasks"] == 2
        assert data["total_tasks"] == 3


class TestGoalHierarchyProgress:
    """Pattern 5: Goal with children uses average of children's progress."""

    def test_parent_goal_progress_from_children(self):
        """Parent goal progress = average of children's progress."""
        proj = post("/projects", {"name": f"GHier-{U}"}).json()
        parent = post("/goals", {"title": "parent", "project_id": proj["id"], "metric_type": "number", "target_value": 100, "current_value": 0}).json()

        # Create children with different progress
        c1 = post("/goals", {"title": "c1", "project_id": proj["id"], "metric_type": "number", "target_value": 100, "current_value": 50, "parent_goal_id": parent["id"]}).json()
        c2 = post("/goals", {"title": "c2", "project_id": proj["id"], "metric_type": "number", "target_value": 100, "current_value": 100, "parent_goal_id": parent["id"]}).json()

        # c1 progress = 50, c2 progress = 100 → parent = avg(50, 100) = 75
        parent_resp = get(f"/goals/{parent['id']}").json()
        assert parent_resp["progress"] == 75


class TestTimesheetOwnership:
    """Pattern 6: Only author can update/delete timesheets."""

    def test_other_user_cannot_delete_timesheet(self):
        proj = post("/projects", {"name": f"TSOwn-{U}"}).json()
        task = post("/tasks", {"title": "tstask", "project_id": proj["id"]}).json()
        ts = post("/timesheets", {"task_id": task["id"], "hours": 2, "date": "2024-03-01"}).json()

        # Different user tries to delete
        r = delete(f"/timesheets/{ts['id']}", h=HB_ORG)
        assert r.status_code == 403

    def test_other_user_cannot_update_timesheet(self):
        proj = post("/projects", {"name": f"TSUpd-{U}"}).json()
        task = post("/tasks", {"title": "tstask2", "project_id": proj["id"]}).json()
        ts = post("/timesheets", {"task_id": task["id"], "hours": 2, "date": "2024-03-01"}).json()

        r = put(f"/timesheets/{ts['id']}", {"hours": 5}, h=HB_ORG)
        assert r.status_code == 403


class TestCommentOwnership:
    """Pattern 6: Only author can delete comments."""

    def test_comment_author_can_delete(self):
        proj = post("/projects", {"name": f"CmtProj-{U}"}).json()
        task = post("/tasks", {"title": "cmttask", "project_id": proj["id"]}).json()
        cmt = post(f"/tasks/{task['id']}/comments", {"content": "my comment"}).json()
        assert cmt["user_id"] == USER_A

        r = delete(f"/comments/{cmt['id']}")
        assert r.status_code == 204

    def test_other_user_cannot_delete_comment(self):
        proj = post("/projects", {"name": f"CmtDel-{U}"}).json()
        task = post("/tasks", {"title": "cmttask2", "project_id": proj["id"]}).json()
        cmt = post(f"/tasks/{task['id']}/comments", {"content": "protected"}).json()

        r = delete(f"/comments/{cmt['id']}", h=HB_ORG)
        assert r.status_code == 403


class TestGoalDeletionOrphans:
    """Pattern 7: Deleting parent goal orphans children."""

    def test_delete_parent_goal_orphans_children(self):
        proj = post("/projects", {"name": f"OrphGoal-{U}"}).json()
        parent = post("/goals", {"title": "parent", "project_id": proj["id"], "metric_type": "number", "target_value": 10}).json()
        child = post("/goals", {"title": "child", "project_id": proj["id"], "metric_type": "number", "target_value": 5, "parent_goal_id": parent["id"]}).json()

        # Delete parent
        r = delete(f"/goals/{parent['id']}")
        assert r.status_code in (200, 204)

        # Child still exists with parent_goal_id = null
        child_resp = get(f"/goals/{child['id']}").json()
        assert child_resp["parent_goal_id"] is None


class TestProjectProgressComputation:
    """Pattern 5: Project progress = average of milestone progress."""

    def test_project_progress_from_milestones(self):
        proj = post("/projects", {"name": f"ProjProg-{U}"}).json()
        ms1 = post("/milestones", {"title": "ms1", "project_id": proj["id"]}).json()
        ms2 = post("/milestones", {"title": "ms2", "project_id": proj["id"]}).json()

        # ms1: 1/1 done = 100%
        t1 = post("/tasks", {"title": "t1", "project_id": proj["id"], "milestone_id": ms1["id"]}).json()
        put(f"/tasks/{t1['id']}", {"status": "in_progress"})
        put(f"/tasks/{t1['id']}", {"status": "done"})

        # ms2: 0/1 done = 0%
        post("/tasks", {"title": "t2", "project_id": proj["id"], "milestone_id": ms2["id"]})

        # Project progress = avg(100, 0) = 50
        p = get(f"/projects/{proj['id']}").json()
        assert p["progress"] == 50
