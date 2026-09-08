"""
BackendForge — Comprehensive Correctness Tests for Solidtime Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex

# Valid defaults are replaced with per-item UUIDs by the isolation fixture.
USER_ID = str(uuid.uuid4())
ORG_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
ORG2_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Org-Id": ORG_ID,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-User-Id": USER2_ID,
    "X-Org-Id": ORG2_ID,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_state(request):
    """Give every item fresh user and organization namespaces."""
    global USER_ID, ORG_ID, USER2_ID, ORG2_ID, HEADERS, HEADERS2, UNIQUE

    item_namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}")
    USER_ID = str(uuid.uuid5(item_namespace, "user-1"))
    ORG_ID = str(uuid.uuid5(item_namespace, "org-1"))
    USER2_ID = str(uuid.uuid5(item_namespace, "user-2"))
    ORG2_ID = str(uuid.uuid5(item_namespace, "org-2"))
    HEADERS = {
        "X-User-Id": USER_ID,
        "X-Org-Id": ORG_ID,
        "Content-Type": "application/json",
    }
    HEADERS2 = {
        "X-User-Id": USER2_ID,
        "X-Org-Id": ORG2_ID,
        "Content-Type": "application/json",
    }
    UNIQUE = item_namespace.hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_user_id_returns_401(self):
        """Requests without X-User-Id should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/v1/organizations/current",
            headers={"X-Org-Id": ORG_ID, "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_missing_org_id_returns_401(self):
        """Requests without X-Org-Id should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/v1/organizations/current",
            headers={"X-User-Id": USER_ID, "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_missing_both_headers_returns_401(self):
        """Requests without either auth header should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/v1/organizations/current",
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_auto_create_org_and_membership(self):
        """First request auto-creates org and makes user the owner."""
        resp = api_get("/api/v1/organizations/current")
        assert resp.status_code == 200
        org = resp.json()
        assert org["id"] == ORG_ID
        assert "name" in org

    def test_auto_created_user_is_owner(self):
        """Auto-created user should be owner of the org."""
        # Make sure org exists
        api_get("/api/v1/organizations/current")
        resp = api_get("/api/v1/members")
        assert resp.status_code == 200
        members = resp.json()
        my_membership = [m for m in members if m["user_id"] == USER_ID]
        assert len(my_membership) == 1
        assert my_membership[0]["role"] == "owner"


# ════════════════════════════════════════════════════════════════════
# PART 2: Organization CRUD
# ════════════════════════════════════════════════════════════════════


class TestOrganization:

    def test_get_organization(self):
        resp = api_get("/api/v1/organizations/current")
        assert resp.status_code == 200
        org = resp.json()
        assert "id" in org
        assert "name" in org
        assert org["id"] == ORG_ID

    def test_update_organization_name(self):
        resp = api_put("/api/v1/organizations/current", {"name": f"Updated Org {UNIQUE}"})
        assert resp.status_code == 200
        org = resp.json()
        assert org["name"] == f"Updated Org {UNIQUE}"

    def test_update_organization_billable_rate(self):
        resp = api_put("/api/v1/organizations/current", {"billable_rate": 5000})
        assert resp.status_code == 200
        org = resp.json()
        assert org["billable_rate"] == 5000

    def test_update_organization_billable_rate_null(self):
        resp = api_put("/api/v1/organizations/current", {"billable_rate": None})
        assert resp.status_code == 200
        org = resp.json()
        assert org["billable_rate"] is None


# ════════════════════════════════════════════════════════════════════
# PART 3: Members CRUD
# ════════════════════════════════════════════════════════════════════


class TestMembers:

    def test_list_members(self):
        resp = api_get("/api/v1/members")
        assert resp.status_code == 200
        members = resp.json()
        assert isinstance(members, list)
        assert len(members) >= 1

    def test_add_member(self):
        new_user_id = str(uuid.uuid4())
        resp = api_post("/api/v1/members", {
            "user_id": new_user_id,
            "role": "member",
            "billable_rate": 3000,
        })
        assert resp.status_code == 201
        member = resp.json()
        assert member["user_id"] == new_user_id
        assert member["role"] == "member"
        assert member["billable_rate"] == 3000
        assert "id" in member

    def test_add_duplicate_member_returns_409(self):
        """Cannot add a user who is already a member."""
        new_user_id = str(uuid.uuid4())
        api_post("/api/v1/members", {"user_id": new_user_id, "role": "member"})
        resp = api_post("/api/v1/members", {"user_id": new_user_id, "role": "member"})
        assert resp.status_code == 409

    def test_update_member_role(self):
        new_user_id = str(uuid.uuid4())
        create_resp = api_post("/api/v1/members", {"user_id": new_user_id, "role": "member"})
        member_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/members/{member_id}", {"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_update_member_billable_rate(self):
        new_user_id = str(uuid.uuid4())
        create_resp = api_post("/api/v1/members", {"user_id": new_user_id, "role": "member"})
        member_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/members/{member_id}", {"billable_rate": 7500})
        assert resp.status_code == 200
        assert resp.json()["billable_rate"] == 7500

    def test_delete_member(self):
        new_user_id = str(uuid.uuid4())
        create_resp = api_post("/api/v1/members", {"user_id": new_user_id, "role": "member"})
        member_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/members/{member_id}")
        assert resp.status_code == 204

    def test_cannot_remove_owner(self):
        """Owner cannot be removed from the org."""
        resp = api_get("/api/v1/members")
        members = resp.json()
        owner = [m for m in members if m["role"] == "owner"][0]

        resp = api_delete(f"/api/v1/members/{owner['id']}")
        assert resp.status_code == 422

    def test_cannot_change_owner_role(self):
        """Cannot change the owner's role."""
        resp = api_get("/api/v1/members")
        members = resp.json()
        owner = [m for m in members if m["role"] == "owner"][0]

        resp = api_put(f"/api/v1/members/{owner['id']}", {"role": "member"})
        assert resp.status_code == 422

    def test_update_nonexistent_member(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/api/v1/members/{fake_id}", {"role": "admin"})
        assert resp.status_code == 404

    def test_delete_nonexistent_member(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/members/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Clients CRUD
# ════════════════════════════════════════════════════════════════════


class TestClients:

    def test_create_client(self):
        resp = api_post("/api/v1/clients", {
            "name": f"Client-{UNIQUE}",
            "email": "client@example.com",
            "address": "123 Main St",
        })
        assert resp.status_code == 201
        client = resp.json()
        assert client["name"] == f"Client-{UNIQUE}"
        assert client["email"] == "client@example.com"
        assert client["address"] == "123 Main St"
        assert client["archived"] is False
        assert "id" in client

    def test_create_client_minimal(self):
        resp = api_post("/api/v1/clients", {"name": f"MinClient-{UNIQUE}"})
        assert resp.status_code == 201
        client = resp.json()
        assert client["name"] == f"MinClient-{UNIQUE}"

    def test_list_clients(self):
        api_post("/api/v1/clients", {"name": f"ListClient-{UNIQUE}"})
        resp = api_get("/api/v1/clients")
        assert resp.status_code == 200
        clients = resp.json()
        assert isinstance(clients, list)
        names = [c["name"] for c in clients]
        assert f"ListClient-{UNIQUE}" in names

    def test_update_client(self):
        create_resp = api_post("/api/v1/clients", {"name": f"UpdClient-{UNIQUE}"})
        client_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/clients/{client_id}", {
            "name": f"UpdClient-{UNIQUE}-v2",
            "email": "new@example.com",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdClient-{UNIQUE}-v2"
        assert resp.json()["email"] == "new@example.com"

    def test_archive_client(self):
        create_resp = api_post("/api/v1/clients", {"name": f"ArchClient-{UNIQUE}"})
        client_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/clients/{client_id}", {"archived": True})
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    def test_filter_clients_by_archived(self):
        # Create a non-archived client
        api_post("/api/v1/clients", {"name": f"ActiveClient-{UNIQUE}"})
        # Create and archive another
        create_resp = api_post("/api/v1/clients", {"name": f"ArchivedFilter-{UNIQUE}"})
        client_id = create_resp.json()["id"]
        api_put(f"/api/v1/clients/{client_id}", {"archived": True})

        # Filter non-archived
        resp = api_get("/api/v1/clients", params={"archived": "false"})
        assert resp.status_code == 200
        for c in resp.json():
            assert c["archived"] is False

        # Filter archived
        resp = api_get("/api/v1/clients", params={"archived": "true"})
        assert resp.status_code == 200
        for c in resp.json():
            assert c["archived"] is True

    def test_delete_client(self):
        create_resp = api_post("/api/v1/clients", {"name": f"DelClient-{UNIQUE}"})
        client_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/clients/{client_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_client(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/clients/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_client_name(self):
        name = f"DupClient-{UNIQUE}"
        api_post("/api/v1/clients", {"name": name})
        resp = api_post("/api/v1/clients", {"name": name})
        assert resp.status_code == 409

    def test_update_nonexistent_client(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/api/v1/clients/{fake_id}", {"name": "ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Projects CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjects:

    def test_create_project(self):
        resp = api_post("/api/v1/projects", {
            "name": f"Project-{UNIQUE}",
            "color": "#FF5733",
            "is_billable": True,
        })
        assert resp.status_code == 201
        project = resp.json()
        assert project["name"] == f"Project-{UNIQUE}"
        assert project["color"] == "#FF5733"
        assert project["is_billable"] is True
        assert project["archived"] is False
        assert "id" in project

    def test_create_project_with_client(self):
        client_resp = api_post("/api/v1/clients", {"name": f"ProjClient-{UNIQUE}"})
        client_id = client_resp.json()["id"]

        resp = api_post("/api/v1/projects", {
            "name": f"ProjWithClient-{UNIQUE}",
            "color": "#00FF00",
            "is_billable": False,
            "client_id": client_id,
        })
        assert resp.status_code == 201
        assert resp.json()["client_id"] == client_id

    def test_list_projects(self):
        api_post("/api/v1/projects", {
            "name": f"ListProj-{UNIQUE}",
            "color": "#123456",
            "is_billable": True,
        })
        resp = api_get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        names = [p["name"] for p in projects]
        assert f"ListProj-{UNIQUE}" in names

    def test_get_project(self):
        create_resp = api_post("/api/v1/projects", {
            "name": f"GetProj-{UNIQUE}",
            "color": "#AABBCC",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    def test_update_project(self):
        create_resp = api_post("/api/v1/projects", {
            "name": f"UpdProj-{UNIQUE}",
            "color": "#111111",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/projects/{project_id}", {
            "name": f"UpdProj-{UNIQUE}-v2",
            "color": "#222222",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdProj-{UNIQUE}-v2"
        assert resp.json()["color"] == "#222222"

    def test_archive_project(self):
        create_resp = api_post("/api/v1/projects", {
            "name": f"ArchProj-{UNIQUE}",
            "color": "#333333",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/projects/{project_id}", {"archived": True})
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    def test_filter_projects_by_archived(self):
        api_post("/api/v1/projects", {
            "name": f"ActiveProj-{UNIQUE}",
            "color": "#444444",
            "is_billable": True,
        })
        create_resp = api_post("/api/v1/projects", {
            "name": f"ArchivedProj-{UNIQUE}",
            "color": "#555555",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]
        api_put(f"/api/v1/projects/{project_id}", {"archived": True})

        resp = api_get("/api/v1/projects", params={"archived": "false"})
        assert resp.status_code == 200
        for p in resp.json():
            assert p["archived"] is False

    def test_delete_project(self):
        create_resp = api_post("/api/v1/projects", {
            "name": f"DelProj-{UNIQUE}",
            "color": "#666666",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_project(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/projects/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_project_name(self):
        name = f"DupProj-{UNIQUE}"
        api_post("/api/v1/projects", {"name": name, "color": "#777777", "is_billable": True})
        resp = api_post("/api/v1/projects", {"name": name, "color": "#888888", "is_billable": True})
        assert resp.status_code == 409

    def test_get_nonexistent_project(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/projects/{fake_id}")
        assert resp.status_code == 404

    def test_cannot_create_project_for_archived_client(self):
        """Cannot assign a project to an archived client."""
        client_resp = api_post("/api/v1/clients", {"name": f"ArchClientProj-{UNIQUE}"})
        client_id = client_resp.json()["id"]
        api_put(f"/api/v1/clients/{client_id}", {"archived": True})

        resp = api_post("/api/v1/projects", {
            "name": f"ProjArchClient-{UNIQUE}",
            "color": "#999999",
            "is_billable": True,
            "client_id": client_id,
        })
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 6: Tasks CRUD
# ════════════════════════════════════════════════════════════════════


class TestTasks:

    def test_create_task(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"TaskProj-{UNIQUE}",
            "color": "#AAAAAA",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]

        resp = api_post("/api/v1/tasks", {
            "name": f"Task-{UNIQUE}",
            "project_id": project_id,
            "estimated_seconds": 3600,
        })
        assert resp.status_code == 201
        task = resp.json()
        assert task["name"] == f"Task-{UNIQUE}"
        assert task["project_id"] == project_id
        assert task["done"] is False
        assert task["estimated_seconds"] == 3600
        assert "id" in task

    def test_list_tasks(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"ListTaskProj-{UNIQUE}",
            "color": "#BBBBBB",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        api_post("/api/v1/tasks", {"name": f"ListTask-{UNIQUE}", "project_id": project_id})

        resp = api_get("/api/v1/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert isinstance(tasks, list)
        names = [t["name"] for t in tasks]
        assert f"ListTask-{UNIQUE}" in names

    def test_filter_tasks_by_project(self):
        proj1_resp = api_post("/api/v1/projects", {
            "name": f"FilterTaskProj1-{UNIQUE}",
            "color": "#CCCCCC",
            "is_billable": True,
        })
        proj1_id = proj1_resp.json()["id"]
        proj2_resp = api_post("/api/v1/projects", {
            "name": f"FilterTaskProj2-{UNIQUE}",
            "color": "#DDDDDD",
            "is_billable": True,
        })
        proj2_id = proj2_resp.json()["id"]

        api_post("/api/v1/tasks", {"name": f"T1-{UNIQUE}", "project_id": proj1_id})
        api_post("/api/v1/tasks", {"name": f"T2-{UNIQUE}", "project_id": proj2_id})

        resp = api_get("/api/v1/tasks", params={"project_id": proj1_id})
        assert resp.status_code == 200
        tasks = resp.json()
        for t in tasks:
            assert t["project_id"] == proj1_id

    def test_filter_tasks_by_done(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"DoneTaskProj-{UNIQUE}",
            "color": "#EEEEEE",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        create_resp = api_post("/api/v1/tasks", {"name": f"DoneTask-{UNIQUE}", "project_id": project_id})
        task_id = create_resp.json()["id"]
        api_put(f"/api/v1/tasks/{task_id}", {"done": True})

        resp = api_get("/api/v1/tasks", params={"done": "true"})
        assert resp.status_code == 200
        for t in resp.json():
            assert t["done"] is True

    def test_update_task(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"UpdTaskProj-{UNIQUE}",
            "color": "#FFFFFF",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        create_resp = api_post("/api/v1/tasks", {"name": f"UpdTask-{UNIQUE}", "project_id": project_id})
        task_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/tasks/{task_id}", {
            "name": f"UpdTask-{UNIQUE}-v2",
            "done": True,
            "estimated_seconds": 7200,
        })
        assert resp.status_code == 200
        task = resp.json()
        assert task["name"] == f"UpdTask-{UNIQUE}-v2"
        assert task["done"] is True
        assert task["estimated_seconds"] == 7200

    def test_delete_task(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"DelTaskProj-{UNIQUE}",
            "color": "#000000",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        create_resp = api_post("/api/v1/tasks", {"name": f"DelTask-{UNIQUE}", "project_id": project_id})
        task_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/tasks/{fake_id}")
        assert resp.status_code == 404

    def test_update_nonexistent_task(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/api/v1/tasks/{fake_id}", {"name": "ghost"})
        assert resp.status_code == 404

    def test_create_task_nonexistent_project(self):
        fake_id = str(uuid.uuid4())
        resp = api_post("/api/v1/tasks", {"name": "orphan", "project_id": fake_id})
        assert resp.status_code == 404

    def test_task_spent_seconds(self):
        """Task response includes spent_seconds from time entries."""
        proj_resp = api_post("/api/v1/projects", {
            "name": f"SpentProj-{UNIQUE}",
            "color": "#112233",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        task_resp = api_post("/api/v1/tasks", {"name": f"SpentTask-{UNIQUE}", "project_id": project_id})
        task_id = task_resp.json()["id"]

        # Create a 1-hour time entry for this task
        start = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "task_id": task_id,
            "project_id": project_id,
            "billable": False,
        })

        # Check task spent_seconds
        resp = api_get("/api/v1/tasks")
        tasks = resp.json()
        task = [t for t in tasks if t["id"] == task_id][0]
        assert task["spent_seconds"] == 3600


# ════════════════════════════════════════════════════════════════════
# PART 7: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        resp = api_post("/api/v1/tags", {"name": f"Tag-{UNIQUE}"})
        assert resp.status_code == 201
        tag = resp.json()
        assert tag["name"] == f"Tag-{UNIQUE}"
        assert "id" in tag
        assert tag["organization_id"] == ORG_ID

    def test_list_tags(self):
        api_post("/api/v1/tags", {"name": f"ListTag-{UNIQUE}"})
        resp = api_get("/api/v1/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] for t in tags]
        assert f"ListTag-{UNIQUE}" in names

    def test_update_tag(self):
        create_resp = api_post("/api/v1/tags", {"name": f"UpdTag-{UNIQUE}"})
        tag_id = create_resp.json()["id"]

        resp = api_put(f"/api/v1/tags/{tag_id}", {"name": f"UpdTag-{UNIQUE}-v2"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdTag-{UNIQUE}-v2"

    def test_delete_tag(self):
        create_resp = api_post("/api/v1/tags", {"name": f"DelTag-{UNIQUE}"})
        tag_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/tags/{tag_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_tag(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/tags/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_tag_name(self):
        name = f"DupTag-{UNIQUE}"
        api_post("/api/v1/tags", {"name": name})
        resp = api_post("/api/v1/tags", {"name": name})
        assert resp.status_code == 409

    def test_update_nonexistent_tag(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/api/v1/tags/{fake_id}", {"name": "ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Time Entries CRUD
# ════════════════════════════════════════════════════════════════════


class TestTimeEntries:

    def test_create_time_entry(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"TEProj-{UNIQUE}",
            "color": "#ABCDEF",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]

        start = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "description": "Working on feature",
            "project_id": project_id,
            "billable": True,
        })
        assert resp.status_code == 201
        te = resp.json()
        assert te["user_id"] == USER_ID
        assert te["organization_id"] == ORG_ID
        assert te["project_id"] == project_id
        assert te["billable"] is True
        assert te["duration"] == 5400  # 1.5 hours
        assert "id" in te

    def test_create_time_entry_with_tags(self):
        tag1_resp = api_post("/api/v1/tags", {"name": f"TETag1-{UNIQUE}"})
        tag2_resp = api_post("/api/v1/tags", {"name": f"TETag2-{UNIQUE}"})
        tag1_id = tag1_resp.json()["id"]
        tag2_id = tag2_resp.json()["id"]

        start = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
            "tag_ids": [tag1_id, tag2_id],
        })
        assert resp.status_code == 201
        te = resp.json()
        assert "tags" in te
        tag_ids_returned = [t["id"] for t in te["tags"]]
        assert tag1_id in tag_ids_returned
        assert tag2_id in tag_ids_returned

    def test_list_time_entries(self):
        start = datetime(2024, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
            "description": f"ListTE-{UNIQUE}",
        })

        resp = api_get("/api/v1/time-entries")
        assert resp.status_code == 200
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1

    def test_get_time_entry(self):
        start = datetime(2024, 2, 2, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        create_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        te_id = create_resp.json()["id"]

        resp = api_get(f"/api/v1/time-entries/{te_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == te_id

    def test_update_time_entry(self):
        start = datetime(2024, 2, 3, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 3, 10, 0, 0, tzinfo=timezone.utc)
        create_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        te_id = create_resp.json()["id"]

        new_end = datetime(2024, 2, 3, 11, 0, 0, tzinfo=timezone.utc)
        resp = api_put(f"/api/v1/time-entries/{te_id}", {
            "end": new_end.isoformat(),
            "description": "Updated description",
            "billable": True,
        })
        assert resp.status_code == 200
        te = resp.json()
        assert te["description"] == "Updated description"
        assert te["billable"] is True
        assert te["duration"] == 7200  # 2 hours

    def test_delete_time_entry(self):
        start = datetime(2024, 2, 4, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 4, 10, 0, 0, tzinfo=timezone.utc)
        create_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        te_id = create_resp.json()["id"]

        resp = api_delete(f"/api/v1/time-entries/{te_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_time_entry(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/api/v1/time-entries/{fake_id}")
        assert resp.status_code == 404

    def test_get_nonexistent_time_entry(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/time-entries/{fake_id}")
        assert resp.status_code == 404

    def test_end_before_start_returns_422(self):
        start = datetime(2024, 2, 5, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 5, 9, 0, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        assert resp.status_code == 422

    def test_cannot_create_entry_for_archived_project(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"ArchTEProj-{UNIQUE}",
            "color": "#FEDCBA",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]
        api_put(f"/api/v1/projects/{project_id}", {"archived": True})

        start = datetime(2024, 2, 6, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 2, 6, 10, 0, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "project_id": project_id,
            "billable": False,
        })
        assert resp.status_code == 422

    def test_filter_time_entries_by_project(self):
        proj_resp = api_post("/api/v1/projects", {
            "name": f"FilterTEProj-{UNIQUE}",
            "color": "#AABB11",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]

        start = datetime(2024, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "project_id": project_id,
            "billable": False,
        })

        resp = api_get("/api/v1/time-entries", params={"project_id": project_id})
        assert resp.status_code == 200
        for te in resp.json():
            assert te["project_id"] == project_id

    def test_filter_time_entries_by_billable(self):
        start = datetime(2024, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 2, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": True,
        })

        resp = api_get("/api/v1/time-entries", params={"billable": "true"})
        assert resp.status_code == 200
        for te in resp.json():
            assert te["billable"] is True

    def test_filter_time_entries_by_date_range(self):
        start = datetime(2024, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
            "description": f"DateRange-{UNIQUE}",
        })

        filter_start = datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        filter_end = datetime(2024, 6, 16, 0, 0, 0, tzinfo=timezone.utc)
        resp = api_get("/api/v1/time-entries", params={
            "start": filter_start.isoformat(),
            "end": filter_end.isoformat(),
        })
        assert resp.status_code == 200
        entries = resp.json()
        descriptions = [e.get("description") for e in entries]
        assert f"DateRange-{UNIQUE}" in descriptions


# ════════════════════════════════════════════════════════════════════
# PART 9: Timer (Start/Stop)
# ════════════════════════════════════════════════════════════════════


class TestTimer:

    def test_start_timer(self):
        start = datetime(2024, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries/start", {
            "start": start.isoformat(),
            "billable": False,
            "description": f"Timer-{UNIQUE}",
        })
        assert resp.status_code == 201
        te = resp.json()
        assert te["end"] is None
        assert te["duration"] >= 0  # Running timer has computed duration

    def test_stop_timer(self):
        start = datetime(2024, 4, 2, 9, 0, 0, tzinfo=timezone.utc)
        create_resp = api_post("/api/v1/time-entries/start", {
            "start": start.isoformat(),
            "billable": False,
        })
        te_id = create_resp.json()["id"]

        end = datetime(2024, 4, 2, 10, 30, 0, tzinfo=timezone.utc)
        resp = api_put(f"/api/v1/time-entries/{te_id}/stop", {
            "end": end.isoformat(),
        })
        assert resp.status_code == 200
        te = resp.json()
        assert te["end"] is not None
        assert te["duration"] == 5400  # 1.5 hours

    def test_stop_already_stopped_returns_422(self):
        """Cannot stop a timer that already has an end time."""
        start = datetime(2024, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 4, 3, 10, 0, 0, tzinfo=timezone.utc)
        create_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        te_id = create_resp.json()["id"]

        stop_end = datetime(2024, 4, 3, 11, 0, 0, tzinfo=timezone.utc)
        resp = api_put(f"/api/v1/time-entries/{te_id}/stop", {
            "end": stop_end.isoformat(),
        })
        assert resp.status_code == 422

    def test_start_new_timer_stops_previous(self):
        """Starting a new timer auto-stops the current running one."""
        start1 = datetime(2024, 4, 4, 9, 0, 0, tzinfo=timezone.utc)
        create1_resp = api_post("/api/v1/time-entries/start", {
            "start": start1.isoformat(),
            "billable": False,
            "description": "First timer",
        })
        te1_id = create1_resp.json()["id"]

        start2 = datetime(2024, 4, 4, 10, 0, 0, tzinfo=timezone.utc)
        api_post("/api/v1/time-entries/start", {
            "start": start2.isoformat(),
            "billable": False,
            "description": "Second timer",
        })

        # First timer should now be stopped (end = start2)
        resp = api_get(f"/api/v1/time-entries/{te1_id}")
        te1 = resp.json()
        assert te1["end"] is not None
        assert te1["duration"] == 3600  # 1 hour

    def test_stop_nonexistent_timer(self):
        fake_id = str(uuid.uuid4())
        end = datetime(2024, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
        resp = api_put(f"/api/v1/time-entries/{fake_id}/stop", {
            "end": end.isoformat(),
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Billable Amount Calculation
# ════════════════════════════════════════════════════════════════════


class TestBillableAmount:

    def test_billable_amount_with_member_rate(self):
        """Billable amount = (duration_seconds / 3600) * member.billable_rate / 100."""
        # Set member billable rate
        members_resp = api_get("/api/v1/members")
        my_member = [m for m in members_resp.json() if m["user_id"] == USER_ID][0]
        member_id = my_member["id"]
        api_put(f"/api/v1/members/{member_id}", {"billable_rate": 10000})  # $100/hour in cents

        start = datetime(2024, 5, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 5, 1, 11, 0, 0, tzinfo=timezone.utc)  # 2 hours
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": True,
        })
        assert resp.status_code == 201
        te = resp.json()
        # 2 hours * 10000 cents/hour = 20000 cents
        assert te["billable_amount"] == pytest.approx(20000.0, abs=1)

    def test_non_billable_entry_amount_zero(self):
        """Non-billable entries should have billable_amount = 0."""
        start = datetime(2024, 5, 2, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        assert resp.status_code == 201
        te = resp.json()
        assert te["billable_amount"] == 0

    def test_billable_amount_with_org_rate_fallback(self):
        """If member rate is null, fall back to org rate."""
        # Create a new user/org for isolation
        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        headers = {
            "X-User-Id": user_id,
            "X-Org-Id": org_id,
            "Content-Type": "application/json",
        }
        # Auto-create org
        api_get("/api/v1/organizations/current", headers=headers)
        # Set org billable rate
        api_put("/api/v1/organizations/current", {"billable_rate": 5000}, headers=headers)  # $50/hour

        # Member rate should be null by default — verify it
        members_resp = api_get("/api/v1/members", headers=headers)
        my_member = [m for m in members_resp.json() if m["user_id"] == user_id][0]
        # Explicitly set member rate to null
        api_put(f"/api/v1/members/{my_member['id']}", {"billable_rate": None}, headers=headers)

        start = datetime(2024, 5, 3, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 5, 3, 10, 0, 0, tzinfo=timezone.utc)  # 1 hour
        resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": True,
        }, headers=headers)
        assert resp.status_code == 201
        te = resp.json()
        # 1 hour * 5000 cents/hour = 5000 cents
        assert te["billable_amount"] == pytest.approx(5000.0, abs=1)


# ════════════════════════════════════════════════════════════════════
# PART 11: Reports
# ════════════════════════════════════════════════════════════════════


class TestReports:

    def _setup_report_data(self):
        """Create known time entries for report testing."""
        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        headers = {
            "X-User-Id": user_id,
            "X-Org-Id": org_id,
            "Content-Type": "application/json",
        }
        # Auto-create
        api_get("/api/v1/organizations/current", headers=headers)
        # Set org rate
        api_put("/api/v1/organizations/current", {"billable_rate": 6000}, headers=headers)

        # Create a project
        proj_resp = api_post("/api/v1/projects", {
            "name": f"ReportProj-{uuid.uuid4().hex[:8]}",
            "color": "#112244",
            "is_billable": True,
        }, headers=headers)
        project_id = proj_resp.json()["id"]

        # Create time entries
        # Day 1: 2 hours billable
        api_post("/api/v1/time-entries", {
            "start": "2024-07-01T09:00:00Z",
            "end": "2024-07-01T11:00:00Z",
            "project_id": project_id,
            "billable": True,
        }, headers=headers)

        # Day 2: 1 hour non-billable
        api_post("/api/v1/time-entries", {
            "start": "2024-07-02T14:00:00Z",
            "end": "2024-07-02T15:00:00Z",
            "project_id": project_id,
            "billable": False,
        }, headers=headers)

        # Day 2: 30 min billable
        api_post("/api/v1/time-entries", {
            "start": "2024-07-02T16:00:00Z",
            "end": "2024-07-02T16:30:00Z",
            "project_id": project_id,
            "billable": True,
        }, headers=headers)

        return headers, project_id, user_id

    def test_report_time_total(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/time", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert "total_seconds" in report
        assert "total_billable_seconds" in report
        assert "total_billable_amount" in report
        assert "entry_count" in report
        # 2h + 1h + 0.5h = 3.5h = 12600 seconds
        assert report["total_seconds"] == 12600
        # billable: 2h + 0.5h = 2.5h = 9000 seconds
        assert report["total_billable_seconds"] == 9000
        assert report["entry_count"] == 3

    def test_report_time_filter_billable(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/time", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
            "billable": "true",
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert report["total_seconds"] == 9000
        assert report["entry_count"] == 2

    def test_report_projects(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/projects", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert isinstance(report, list)
        assert len(report) >= 1
        proj_report = [r for r in report if r["project_id"] == project_id]
        assert len(proj_report) == 1
        assert proj_report[0]["total_seconds"] == 12600
        assert proj_report[0]["entry_count"] == 3

    def test_report_members(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/members", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert isinstance(report, list)
        assert len(report) >= 1
        member_report = [r for r in report if r["user_id"] == user_id]
        assert len(member_report) == 1
        assert member_report[0]["total_seconds"] == 12600

    def test_report_daily(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/daily", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert isinstance(report, list)
        # Should have entries for day 1 and day 2
        dates = [r["date"] for r in report]
        assert "2024-07-01" in dates
        assert "2024-07-02" in dates

        day1 = [r for r in report if r["date"] == "2024-07-01"][0]
        assert day1["total_seconds"] == 7200  # 2 hours

        day2 = [r for r in report if r["date"] == "2024-07-02"][0]
        assert day2["total_seconds"] == 5400  # 1h + 30min

    def test_report_filter_by_project(self):
        headers, project_id, user_id = self._setup_report_data()

        # Create another project with entries
        proj2_resp = api_post("/api/v1/projects", {
            "name": f"ReportProj2-{uuid.uuid4().hex[:8]}",
            "color": "#AABB22",
            "is_billable": True,
        }, headers=headers)
        proj2_id = proj2_resp.json()["id"]
        api_post("/api/v1/time-entries", {
            "start": "2024-07-01T12:00:00Z",
            "end": "2024-07-01T13:00:00Z",
            "project_id": proj2_id,
            "billable": True,
        }, headers=headers)

        # Filter by first project
        resp = api_get("/api/v1/reports/time", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
            "project_id": project_id,
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert report["total_seconds"] == 12600  # Only first project entries
        assert report["entry_count"] == 3

    def test_report_filter_by_member(self):
        headers, project_id, user_id = self._setup_report_data()

        resp = api_get("/api/v1/reports/time", params={
            "start": "2024-07-01T00:00:00Z",
            "end": "2024-07-03T00:00:00Z",
            "member_id": user_id,
        }, headers=headers)
        assert resp.status_code == 200
        report = resp.json()
        assert report["total_seconds"] == 12600


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade Behavior
# ════════════════════════════════════════════════════════════════════


class TestCascadeBehavior:

    def test_delete_project_nullifies_time_entries(self):
        """Deleting a project sets project_id = null on time entries."""
        proj_resp = api_post("/api/v1/projects", {
            "name": f"CascadeProj-{UNIQUE}",
            "color": "#AA1122",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]

        start = datetime(2024, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
        te_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "project_id": project_id,
            "billable": False,
        })
        te_id = te_resp.json()["id"]

        api_delete(f"/api/v1/projects/{project_id}")

        # Time entry should still exist but project_id = null
        resp = api_get(f"/api/v1/time-entries/{te_id}")
        assert resp.status_code == 200
        assert resp.json()["project_id"] is None

    def test_delete_project_deletes_tasks(self):
        """Deleting a project deletes its tasks."""
        proj_resp = api_post("/api/v1/projects", {
            "name": f"CascadeTaskProj-{UNIQUE}",
            "color": "#BB2233",
            "is_billable": True,
        })
        project_id = proj_resp.json()["id"]

        task_resp = api_post("/api/v1/tasks", {"name": f"CascadeTask-{UNIQUE}", "project_id": project_id})
        task_id = task_resp.json()["id"]

        api_delete(f"/api/v1/projects/{project_id}")

        # Task should be gone
        resp = api_get("/api/v1/tasks")
        task_ids = [t["id"] for t in resp.json()]
        assert task_id not in task_ids

    def test_delete_client_nullifies_projects(self):
        """Deleting a client sets client_id = null on its projects."""
        client_resp = api_post("/api/v1/clients", {"name": f"CascadeClient-{UNIQUE}"})
        client_id = client_resp.json()["id"]

        proj_resp = api_post("/api/v1/projects", {
            "name": f"CascadeClientProj-{UNIQUE}",
            "color": "#CC3344",
            "is_billable": True,
            "client_id": client_id,
        })
        project_id = proj_resp.json()["id"]

        api_delete(f"/api/v1/clients/{client_id}")

        # Project still exists but client_id = null
        resp = api_get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["client_id"] is None

    def test_delete_tag_removes_from_time_entries(self):
        """Deleting a tag removes it from time entry associations."""
        tag_resp = api_post("/api/v1/tags", {"name": f"CascadeTag-{UNIQUE}"})
        tag_id = tag_resp.json()["id"]

        start = datetime(2024, 8, 2, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 8, 2, 10, 0, 0, tzinfo=timezone.utc)
        te_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
            "tag_ids": [tag_id],
        })
        te_id = te_resp.json()["id"]

        api_delete(f"/api/v1/tags/{tag_id}")

        # Time entry should still exist but tag removed
        resp = api_get(f"/api/v1/time-entries/{te_id}")
        assert resp.status_code == 200
        tag_ids_in_entry = [t["id"] for t in resp.json()["tags"]]
        assert tag_id not in tag_ids_in_entry


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation (Org Scoping)
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_projects_isolated_between_orgs(self):
        """Projects in org1 are not visible in org2."""
        # Ensure org2 exists
        api_get("/api/v1/organizations/current", headers=HEADERS2)

        # Create project in org1
        api_post("/api/v1/projects", {
            "name": f"IsoProj-{UNIQUE}",
            "color": "#DD4455",
            "is_billable": True,
        })

        # Should not appear in org2
        resp = api_get("/api/v1/projects", headers=HEADERS2)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert f"IsoProj-{UNIQUE}" not in names

    def test_clients_isolated_between_orgs(self):
        """Clients in org1 are not visible in org2."""
        api_get("/api/v1/organizations/current", headers=HEADERS2)

        api_post("/api/v1/clients", {"name": f"IsoClient-{UNIQUE}"})

        resp = api_get("/api/v1/clients", headers=HEADERS2)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert f"IsoClient-{UNIQUE}" not in names

    def test_tags_isolated_between_orgs(self):
        """Tags in org1 are not visible in org2."""
        api_get("/api/v1/organizations/current", headers=HEADERS2)

        api_post("/api/v1/tags", {"name": f"IsoTag-{UNIQUE}"})

        resp = api_get("/api/v1/tags", headers=HEADERS2)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert f"IsoTag-{UNIQUE}" not in names

    def test_time_entries_isolated_between_orgs(self):
        """Time entries in org1 are not visible in org2."""
        api_get("/api/v1/organizations/current", headers=HEADERS2)

        start = datetime(2024, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
        te_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
            "description": f"IsoTE-{UNIQUE}",
        })
        te_id = te_resp.json()["id"]

        # Should not appear in org2
        resp = api_get("/api/v1/time-entries", headers=HEADERS2)
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert te_id not in ids

    def test_cannot_access_other_org_project(self):
        """Cannot GET a project belonging to another org."""
        create_resp = api_post("/api/v1/projects", {
            "name": f"OtherOrgProj-{UNIQUE}",
            "color": "#EE5566",
            "is_billable": True,
        })
        project_id = create_resp.json()["id"]

        # Ensure org2 exists
        api_get("/api/v1/organizations/current", headers=HEADERS2)

        resp = api_get(f"/api/v1/projects/{project_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_cannot_delete_other_org_time_entry(self):
        """Cannot delete a time entry belonging to another org."""
        start = datetime(2024, 9, 2, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
        te_resp = api_post("/api/v1/time-entries", {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "billable": False,
        })
        te_id = te_resp.json()["id"]

        api_get("/api/v1/organizations/current", headers=HEADERS2)
        resp = api_delete(f"/api/v1/time-entries/{te_id}", headers=HEADERS2)
        assert resp.status_code == 404
