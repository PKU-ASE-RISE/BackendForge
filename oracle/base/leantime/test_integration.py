"""
BackendForge — L2 Integration Tests for Leantime
"""
import os, uuid, requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RUN_ID = uuid.uuid4()
USER_A = str(uuid.uuid4())
ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
HA = {"X-User-Id": USER_A, "X-Org-Id": ORG_A, "Content-Type": "application/json"}
HB = {"X-User-Id": USER_A, "X-Org-Id": ORG_B, "Content-Type": "application/json"}
U = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_identity(request):
    """Give every item a fresh namespace while preserving within-test identities."""
    global USER_A, ORG_A, ORG_B, U

    node_id = request.node.nodeid
    USER_A = str(uuid.uuid5(RUN_ID, f"{node_id}:user"))
    ORG_A = str(uuid.uuid5(RUN_ID, f"{node_id}:org"))
    ORG_B = str(uuid.uuid5(RUN_ID, f"{node_id}:other-org"))
    U = uuid.uuid5(RUN_ID, f"{node_id}:marker").hex[:8]
    HA.update({"X-User-Id": USER_A, "X-Org-Id": ORG_A})
    HB.update({"X-User-Id": USER_A, "X-Org-Id": ORG_B})

def get(p, params=None, h=None): return requests.get(f"{BASE_URL}{p}", params=params, headers=h or HA, timeout=30)
def post(p, json=None, h=None): return requests.post(f"{BASE_URL}{p}", json=json, headers=h or HA, timeout=30)
def put(p, json=None, h=None): return requests.put(f"{BASE_URL}{p}", json=json, headers=h or HA, timeout=30)
def delete(p, h=None): return requests.delete(f"{BASE_URL}{p}", headers=h or HA, timeout=30)


class TestHealthAndAuth:
    def test_health_no_auth(self):
        r = requests.get(f"{BASE_URL}/health", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_missing_headers_returns_401(self):
        r = requests.get(f"{BASE_URL}/projects", timeout=30)
        assert r.status_code == 401

    def test_missing_org_returns_401(self):
        r = requests.get(f"{BASE_URL}/projects", headers={"X-User-Id": USER_A}, timeout=30)
        assert r.status_code == 401


class TestClientFields:
    """Pattern 1+4: Verify client fields and status codes."""
    def test_client_create_201_with_fields(self):
        r = post("/clients", {"name": f"Client-{U}", "email": "a@b.com", "phone": "123", "company": "Acme"})
        assert r.status_code == 201
        c = r.json()
        assert "id" in c
        assert "name" in c
        assert "email" in c
        assert "phone" in c
        assert "company" in c
        assert "created_at" in c
        assert c["name"] == f"Client-{U}"
        assert c["email"] == "a@b.com"

    def test_client_delete_returns_204(self):
        c = post("/clients", {"name": f"Del-{U}"}).json()
        r = delete(f"/clients/{c['id']}")
        assert r.status_code == 204

    def test_client_404(self):
        r = get(f"/clients/{uuid.uuid4()}")
        assert r.status_code == 404


class TestProjectFields:
    """Pattern 1+5: Project fields including computed progress."""
    def test_project_create_with_computed_progress(self):
        r = post("/projects", {"name": f"Proj-{U}"})
        assert r.status_code == 201
        p = r.json()
        assert "id" in p
        assert "name" in p
        assert "status" in p
        assert "progress" in p
        assert "created_at" in p
        assert p["status"] == "active"
        assert p["progress"] == 0

    def test_project_with_client_ref(self):
        client = post("/clients", {"name": f"ProjClient-{U}"}).json()
        proj = post("/projects", {"name": f"RefProj-{U}", "client_id": client["id"]}).json()
        assert proj["client_id"] == client["id"]

    def test_project_nonexistent_client_404(self):
        r = post("/projects", {"name": "bad", "client_id": str(uuid.uuid4())})
        assert r.status_code == 404


class TestTaskFields:
    """Pattern 1+5: Task fields including computed spent_hours."""
    def test_task_create_with_all_fields(self):
        proj = post("/projects", {"name": f"TProj-{U}"}).json()
        r = post("/tasks", {
            "title": f"Task-{U}",
            "description": "desc",
            "project_id": proj["id"],
            "priority": "high",
            "tags": ["bug", "urgent"],
            "estimated_hours": 4,
        })
        assert r.status_code == 201
        t = r.json()
        assert "id" in t
        assert "title" in t
        assert "project_id" in t
        assert "status" in t
        assert "priority" in t
        assert "tags" in t
        assert "spent_hours" in t
        assert "estimated_hours" in t
        assert "created_at" in t
        assert t["status"] == "new"
        assert t["priority"] == "high"
        assert t["tags"] == ["bug", "urgent"]
        assert t["spent_hours"] == 0
        assert t["estimated_hours"] == 4

    def test_task_nonexistent_project_404(self):
        r = post("/tasks", {"title": "x", "project_id": str(uuid.uuid4())})
        assert r.status_code == 404


class TestGoalFields:
    """Pattern 1+5: Goal fields and progress computation."""
    def test_goal_create_with_progress(self):
        proj = post("/projects", {"name": f"GProj-{U}"}).json()
        r = post("/goals", {
            "title": f"Goal-{U}",
            "project_id": proj["id"],
            "metric_type": "number",
            "target_value": 100,
            "current_value": 25,
        })
        assert r.status_code == 201
        g = r.json()
        assert "id" in g
        assert "progress" in g
        assert "metric_type" in g
        assert "target_value" in g
        assert "current_value" in g
        assert g["progress"] == 25  # 25/100 * 100

    def test_boolean_goal_progress(self):
        proj = post("/projects", {"name": f"BoolProj-{U}"}).json()
        g = post("/goals", {"title": "bg", "project_id": proj["id"], "metric_type": "boolean", "target_value": 1, "current_value": 0}).json()
        assert g["progress"] == 0
        # Update to done
        g2 = put(f"/goals/{g['id']}", {"current_value": 1}).json()
        assert g2["progress"] == 100


class TestMilestoneFields:
    """Pattern 1+5: Milestone with computed progress."""
    def test_milestone_progress_computed(self):
        proj = post("/projects", {"name": f"MProj-{U}"}).json()
        ms = post("/milestones", {"title": f"MS-{U}", "project_id": proj["id"]}).json()
        assert ms["progress"] == 0

        # Add tasks: 1 done, 1 not done
        t1 = post("/tasks", {"title": "t1", "project_id": proj["id"], "milestone_id": ms["id"]}).json()
        t2 = post("/tasks", {"title": "t2", "project_id": proj["id"], "milestone_id": ms["id"]}).json()
        put(f"/tasks/{t1['id']}", {"status": "in_progress"})
        put(f"/tasks/{t1['id']}", {"status": "done"})

        ms_resp = get(f"/milestones/{ms['id']}").json()
        assert ms_resp["progress"] == 50  # 1/2 * 100


class TestTimesheetFields:
    """Pattern 1+4: Timesheet fields and status codes."""
    def test_timesheet_create_sets_user_id(self):
        proj = post("/projects", {"name": f"TSProj-{U}"}).json()
        task = post("/tasks", {"title": "tstask", "project_id": proj["id"]}).json()
        r = post("/timesheets", {"task_id": task["id"], "hours": 2.5, "date": "2024-01-15"})
        assert r.status_code == 201
        ts = r.json()
        assert "id" in ts
        assert "user_id" in ts
        assert "hours" in ts
        assert "date" in ts
        assert ts["user_id"] == USER_A
        assert ts["hours"] == 2.5

    def test_task_spent_hours_computed(self):
        """spent_hours = sum of timesheet hours."""
        proj = post("/projects", {"name": f"SpHProj-{U}"}).json()
        task = post("/tasks", {"title": "sptask", "project_id": proj["id"]}).json()
        post("/timesheets", {"task_id": task["id"], "hours": 3, "date": "2024-01-10"})
        post("/timesheets", {"task_id": task["id"], "hours": 2, "date": "2024-01-11"})
        t = get(f"/tasks/{task['id']}").json()
        assert t["spent_hours"] == 5


class TestDataIsolation:
    """Pattern 6: Org A can't see Org B's data."""
    def test_projects_isolated_by_org(self):
        proj = post("/projects", {"name": f"IsoProj-{U}"}).json()
        r = get(f"/projects/{proj['id']}", h=HB)
        assert r.status_code == 404

    def test_tasks_isolated_by_org(self):
        proj = post("/projects", {"name": f"IsoTaskProj-{U}"}).json()
        task = post("/tasks", {"title": "isotask", "project_id": proj["id"]}).json()
        r = get(f"/tasks/{task['id']}", h=HB)
        assert r.status_code == 404


class TestFiltering:
    """Pattern 3: Filters actually filter."""
    def test_tasks_filter_by_status(self):
        proj = post("/projects", {"name": f"FiltProj-{U}"}).json()
        t1 = post("/tasks", {"title": "new-task", "project_id": proj["id"]}).json()
        t2 = post("/tasks", {"title": "ip-task", "project_id": proj["id"]}).json()
        put(f"/tasks/{t2['id']}", {"status": "in_progress"})

        r = get("/tasks", params={"status": "new"})
        ids = [t["id"] for t in r.json()]
        assert t1["id"] in ids
        assert t2["id"] not in ids

    def test_tasks_filter_by_tags(self):
        proj = post("/projects", {"name": f"TagFilt-{U}"}).json()
        t1 = post("/tasks", {"title": "tagged", "project_id": proj["id"], "tags": ["frontend"]}).json()
        t2 = post("/tasks", {"title": "untagged", "project_id": proj["id"], "tags": ["backend"]}).json()

        r = get("/tasks", params={"tags": "frontend"})
        ids = [t["id"] for t in r.json()]
        assert t1["id"] in ids
        assert t2["id"] not in ids


class TestSprintFields:
    """Pattern 1+5: Sprint with computed velocity."""
    def test_sprint_create_with_fields(self):
        proj = post("/projects", {"name": f"SpProj-{U}"}).json()
        r = post("/sprints", {"name": f"Sprint-{U}", "project_id": proj["id"], "start_date": "2024-01-01", "end_date": "2024-01-14"})
        assert r.status_code == 201
        sp = r.json()
        assert "id" in sp
        assert "name" in sp
        assert "project_id" in sp
        assert "start_date" in sp
        assert "end_date" in sp
        assert "velocity" in sp
        assert sp["velocity"] == 0


class TestTimesheetSummary:
    """Pattern 5: Summary computes correctly."""
    def test_summary_totals(self):
        proj = post("/projects", {"name": f"SumProj-{U}"}).json()
        task = post("/tasks", {"title": "sumtask", "project_id": proj["id"]}).json()
        post("/timesheets", {"task_id": task["id"], "hours": 4, "date": "2024-02-01"})
        post("/timesheets", {"task_id": task["id"], "hours": 3, "date": "2024-02-02"})
        other_task = post("/tasks", {"title": "other-sumtask", "project_id": proj["id"]}).json()
        post("/timesheets", {"task_id": other_task["id"], "hours": 5, "date": "2024-02-02"})

        r = get("/timesheets/summary", params={"task_id": task["id"]})
        assert r.status_code == 200
        data = r.json()
        assert "total_hours" in data
        assert "entries_count" in data
        assert data["total_hours"] == 7
        assert data["entries_count"] == 2
