"""
Comprehensive test suite for Plane project management API.
Tests cover CRUD operations, role-based access, issue identifiers,
cycles, modules, activity logging, workspace isolation, filtering,
comments, and reactions.
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
HTTP_TIMEOUT = 30

# We use fixed API keys to represent different users
ADMIN_KEY = "admin-key-001"
MEMBER_KEY = "member-key-002"
GUEST_KEY = "guest-key-003"
OTHER_ADMIN_KEY = "other-admin-key-004"


def api(method, path, key=ADMIN_KEY, **kwargs):
    """Helper to make API requests."""
    headers = kwargs.pop("headers", {})
    if key:
        headers["X-API-Key"] = key
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    resp = getattr(requests, method)(url, headers=headers, **kwargs)
    return resp


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture()
def workspace():
    """Create a workspace as admin."""
    slug = f"test-ws-{uuid.uuid4().hex[:8]}"
    resp = api("post", "/api/workspaces", json={"name": "Test Workspace", "slug": slug})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["slug"] == slug
    assert "id" in data
    yield data
    api("delete", f"/api/workspaces/{slug}")


@pytest.fixture(scope="module")
def member_user_id():
    return _get_user_id(MEMBER_KEY)


@pytest.fixture(scope="module")
def guest_user_id():
    return _get_user_id(GUEST_KEY)


@pytest.fixture()
def member_in_workspace(workspace, member_user_id):
    """Add member user to workspace."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/members",
               json={"userId": member_user_id, "role": "member"})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def guest_in_workspace(workspace, guest_user_id):
    """Add guest user to workspace."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/members",
               json={"userId": guest_user_id, "role": "guest"})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def project(workspace, member_in_workspace, guest_in_workspace):
    """Create a project within the workspace."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects",
               json={"name": "Test Project", "identifier": "PROJ", "description": "A test project"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["identifier"] == "PROJ"
    return data


@pytest.fixture()
def state_todo(workspace, project):
    """Create a 'Todo' state."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states",
               json={"name": "Todo", "group": "unstarted", "color": "#f0ad4e", "order": 1})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def state_done(workspace, project):
    """Create a 'Done' state."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states",
               json={"name": "Done", "group": "completed", "color": "#5cb85c", "order": 3})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def state_in_progress(workspace, project):
    """Create an 'In Progress' state."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states",
               json={"name": "In Progress", "group": "started", "color": "#5bc0de", "order": 2})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def label_bug(workspace, project):
    """Create a 'Bug' label."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels",
               json={"name": "Bug", "color": "#d9534f"})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def label_feature(workspace, project):
    """Create a 'Feature' label."""
    resp = api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels",
               json={"name": "Feature", "color": "#0275d8"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _get_user_id(api_key):
    """Get or create user id for an API key by listing workspaces (triggers user creation)."""
    # First call with the key to ensure user exists, then get their user ID
    resp = api("get", "/api/workspaces", key=api_key)
    # For the test to work, we need a way to identify users.
    # We'll use a special endpoint or the workspace member response.
    # Let's create a workspace to force user creation and extract user id.
    slug = f"tmp-{uuid.uuid4().hex[:8]}"
    resp = api("post", "/api/workspaces", key=api_key, json={"name": "Tmp", "slug": slug})
    if resp.status_code == 201:
        ws = resp.json()
        # Get members - the creator should be the only admin
        members_resp = api("get", f"/api/workspaces/{slug}/members", key=api_key)
        if members_resp.status_code == 200:
            members = members_resp.json()
            if members:
                user_id = members[0]["userId"]
                # Clean up - delete the temp workspace
                api("delete", f"/api/workspaces/{slug}", key=api_key)
                return user_id
    # Fallback: If already created before, try to find via existing workspace
    resp = api("get", "/api/workspaces", key=api_key)
    if resp.status_code == 200 and resp.json():
        ws = resp.json()[0]
        members_resp = api("get", f"/api/workspaces/{ws['slug']}/members", key=api_key)
        if members_resp.status_code == 200:
            members = members_resp.json()
            for m in members:
                if m["role"] == "admin":
                    # Clean up temp workspace if it exists
                    api("delete", f"/api/workspaces/{slug}", key=api_key)
                    return m["userId"]
    # Last resort - just return something
    api("delete", f"/api/workspaces/{slug}", key=api_key)
    raise RuntimeError(f"Could not determine userId for key {api_key}")


# ─────────────────────────────────────────────────────────────────────
# Test: Authentication
# ─────────────────────────────────────────────────────────────────────

class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        resp = api("get", "/api/workspaces", key=None)
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        resp = api("get", "/api/workspaces", key=ADMIN_KEY)
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# Test: Workspaces CRUD
# ─────────────────────────────────────────────────────────────────────

class TestWorkspaces:
    def test_create_workspace(self, workspace):
        assert "id" in workspace
        assert workspace["name"] == "Test Workspace"

    def test_list_workspaces(self, workspace):
        resp = api("get", "/api/workspaces")
        assert resp.status_code == 200
        slugs = [w["slug"] for w in resp.json()]
        assert workspace["slug"] in slugs

    def test_get_workspace(self, workspace):
        resp = api("get", f"/api/workspaces/{workspace['slug']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == workspace["id"]

    def test_update_workspace(self, workspace):
        resp = api("patch", f"/api/workspaces/{workspace['slug']}",
                   json={"name": "Updated Workspace"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Workspace"

    def test_duplicate_slug_returns_409(self, workspace):
        resp = api("post", "/api/workspaces",
                   json={"name": "Another", "slug": workspace["slug"]})
        assert resp.status_code == 409

    def test_get_nonexistent_workspace_returns_404(self):
        resp = api("get", "/api/workspaces/nonexistent-slug-xyz")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Test: Workspace Members
# ─────────────────────────────────────────────────────────────────────

class TestWorkspaceMembers:
    def test_add_member(self, member_in_workspace):
        assert member_in_workspace["role"] == "member"

    def test_add_guest(self, guest_in_workspace):
        assert guest_in_workspace["role"] == "guest"

    def test_list_members(self, workspace, member_in_workspace, guest_in_workspace):
        resp = api("get", f"/api/workspaces/{workspace['slug']}/members")
        assert resp.status_code == 200
        members = resp.json()
        # At least admin + member + guest
        assert len(members) >= 3

    def test_update_member_role(self, workspace, member_in_workspace):
        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/members/{member_in_workspace['id']}",
                   json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
        # Revert back to member
        api("patch",
            f"/api/workspaces/{workspace['slug']}/members/{member_in_workspace['id']}",
            json={"role": "member"})

    def test_guest_cannot_add_members(self, workspace, guest_in_workspace):
        fake_user = str(uuid.uuid4())
        resp = api("post", f"/api/workspaces/{workspace['slug']}/members",
                   key=GUEST_KEY,
                   json={"userId": fake_user, "role": "member"})
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Test: Projects CRUD
# ─────────────────────────────────────────────────────────────────────

class TestProjects:
    def test_create_project(self, project):
        assert project["identifier"] == "PROJ"
        assert project["name"] == "Test Project"

    def test_list_projects(self, workspace, project):
        resp = api("get", f"/api/workspaces/{workspace['slug']}/projects")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert project["id"] in ids

    def test_get_project(self, workspace, project):
        resp = api("get", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json()["identifier"] == "PROJ"

    def test_update_project(self, workspace, project):
        resp = api("patch", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}",
                   json={"description": "Updated description"})
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    def test_member_cannot_create_project(self, workspace, member_in_workspace):
        resp = api("post", f"/api/workspaces/{workspace['slug']}/projects",
                   key=MEMBER_KEY,
                   json={"name": "Member Project", "identifier": "MPRJ"})
        assert resp.status_code == 403

    def test_duplicate_identifier_returns_409(self, workspace, project):
        resp = api("post", f"/api/workspaces/{workspace['slug']}/projects",
                   json={"name": "Another Project", "identifier": "PROJ"})
        assert resp.status_code == 409


# ─────────────────────────────────────────────────────────────────────
# Test: States
# ─────────────────────────────────────────────────────────────────────

class TestStates:
    def test_create_state(self, state_todo):
        assert state_todo["name"] == "Todo"
        assert state_todo["group"] == "unstarted"

    def test_list_states_ordered(self, workspace, project, state_todo, state_in_progress, state_done):
        resp = api("get", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states")
        assert resp.status_code == 200
        states = resp.json()
        assert len(states) >= 3
        # Should be ordered by order field
        orders = [s["order"] for s in states]
        assert orders == sorted(orders)

    def test_update_state(self, workspace, project, state_todo):
        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states/{state_todo['id']}",
                   json={"name": "Backlog", "group": "backlog"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Backlog"
        assert resp.json()["group"] == "backlog"
        # Revert
        api("patch",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states/{state_todo['id']}",
            json={"name": "Todo", "group": "unstarted"})

    def test_get_state(self, workspace, project, state_todo):
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states/{state_todo['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == state_todo["id"]

    def test_member_cannot_create_state(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/states",
                   key=MEMBER_KEY,
                   json={"name": "Member State", "group": "started"})
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Test: Labels
# ─────────────────────────────────────────────────────────────────────

class TestLabels:
    def test_create_label(self, label_bug):
        assert label_bug["name"] == "Bug"
        assert label_bug["color"] == "#d9534f"

    def test_list_labels(self, workspace, project, label_bug, label_feature):
        resp = api("get", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels")
        assert resp.status_code == 200
        names = [l["name"] for l in resp.json()]
        assert "Bug" in names
        assert "Feature" in names

    def test_update_label(self, workspace, project, label_bug):
        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels/{label_bug['id']}",
                   json={"color": "#ff0000"})
        assert resp.status_code == 200
        assert resp.json()["color"] == "#ff0000"

    def test_get_label(self, workspace, project, label_bug):
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels/{label_bug['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bug"

    def test_member_cannot_create_label(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/labels",
                   key=MEMBER_KEY,
                   json={"name": "MemberLabel", "color": "#aaa"})
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Test: Issues
# ─────────────────────────────────────────────────────────────────────

class TestIssues:
    def test_create_issue_auto_identifier(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "First Issue", "stateId": state_todo["id"], "priority": "high"})
        assert resp.status_code == 201, resp.text
        issue = resp.json()
        assert issue["identifier"] == "PROJ-1"
        assert issue["name"] == "First Issue"
        assert issue["priority"] == "high"

    def test_sequential_identifiers(self, workspace, project, state_todo):
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "First Issue", "stateId": state_todo["id"], "priority": "high"})
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Second Issue", "stateId": state_todo["id"], "priority": "medium"})
        assert resp.status_code == 201
        issue = resp.json()
        assert issue["identifier"] == "PROJ-2"

    def test_create_issue_with_labels_and_assignees(self, workspace, project, state_todo,
                                                     label_bug, member_in_workspace):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={
                       "name": "Bug Issue",
                       "stateId": state_todo["id"],
                       "priority": "urgent",
                       "labels": [label_bug["id"]],
                       "assignees": [member_in_workspace["userId"]],
                       "dueDate": "2026-06-15",
                       "estimate": 5
                   })
        assert resp.status_code == 201
        issue = resp.json()
        assert label_bug["id"] in issue["labels"]
        assert member_in_workspace["userId"] in issue["assignees"]
        assert issue["dueDate"] == "2026-06-15"
        assert issue["estimate"] == 5

    def test_update_issue(self, workspace, project, state_todo, state_done):
        # Create an issue to update
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "To Update", "stateId": state_todo["id"], "priority": "low"})
        assert resp.status_code == 201
        issue_id = resp.json()["id"]

        # Update it
        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
                   key=MEMBER_KEY,
                   json={"name": "Updated Issue", "stateId": state_done["id"], "priority": "high"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "Updated Issue"
        assert updated["stateId"] == state_done["id"]
        assert updated["priority"] == "high"

    def test_get_issue(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Get Me", "stateId": state_todo["id"], "priority": "none"})
        issue_id = resp.json()["id"]
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_delete_issue(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Delete Me", "stateId": state_todo["id"], "priority": "none"})
        issue_id = resp.json()["id"]
        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204
        # Verify gone
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 404

    def test_guest_cannot_create_issue(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=GUEST_KEY,
                   json={"name": "Guest Issue", "stateId": state_todo["id"], "priority": "none"})
        assert resp.status_code == 403

    def test_list_issues(self, workspace, project, state_todo):
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "List Issue", "stateId": state_todo["id"], "priority": "none"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1


# ─────────────────────────────────────────────────────────────────────
# Test: Issue Filtering
# ─────────────────────────────────────────────────────────────────────

class TestIssueFiltering:
    def test_filter_by_priority(self, workspace, project, state_todo):
        # Create issues with different priorities
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Urgent one", "stateId": state_todo["id"], "priority": "urgent"})
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Low one", "stateId": state_todo["id"], "priority": "low"})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   params={"priority": "urgent"})
        assert resp.status_code == 200
        issues = resp.json()
        assert all(i["priority"] == "urgent" for i in issues)
        assert len(issues) >= 1

    def test_filter_by_state(self, workspace, project, state_todo, state_done):
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Done issue", "stateId": state_done["id"], "priority": "none"})
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Todo issue", "stateId": state_todo["id"], "priority": "none"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   params={"stateId": state_done["id"]})
        assert resp.status_code == 200
        issues = resp.json()
        assert all(i["stateId"] == state_done["id"] for i in issues)

    def test_filter_by_label(self, workspace, project, state_todo, label_bug):
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Bug issue", "stateId": state_todo["id"], "priority": "none",
                  "labels": [label_bug["id"]]})
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Unlabelled issue", "stateId": state_todo["id"], "priority": "none"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   params={"label": label_bug["id"]})
        assert resp.status_code == 200
        issues = resp.json()
        for issue in issues:
            assert label_bug["id"] in issue["labels"]

    def test_filter_by_assignee(self, workspace, project, member_in_workspace):
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Assigned issue", "priority": "none",
                  "assignees": [member_in_workspace["userId"]]})
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Unassigned issue", "priority": "none", "assignees": []})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   params={"assignee": member_in_workspace["userId"]})
        assert resp.status_code == 200
        issues = resp.json()
        for issue in issues:
            assert member_in_workspace["userId"] in issue["assignees"]

    def test_filter_by_due_date_range(self, workspace, project, state_todo):
        # Create issue with specific due date
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Due soon", "stateId": state_todo["id"], "priority": "none",
                  "dueDate": "2026-06-01"})
        api("post", f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
            key=MEMBER_KEY,
            json={"name": "Due later", "stateId": state_todo["id"], "priority": "none",
                  "dueDate": "2026-07-01"})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   params={"dueDateStart": "2026-05-01", "dueDateEnd": "2026-06-30"})
        assert resp.status_code == 200
        issues = resp.json()
        assert len(issues) >= 1
        for issue in issues:
            assert issue["dueDate"] is not None
            assert "2026-05-01" <= issue["dueDate"] <= "2026-06-30"


# ─────────────────────────────────────────────────────────────────────
# Test: Comments and Reactions
# ─────────────────────────────────────────────────────────────────────

class TestComments:
    @pytest.fixture()
    def issue_for_comments(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Commentable Issue", "stateId": state_todo["id"], "priority": "none"})
        return resp.json()

    def test_create_comment(self, workspace, project, issue_for_comments):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
                   key=MEMBER_KEY,
                   json={"content": "This is a comment"})
        assert resp.status_code == 201
        comment = resp.json()
        assert comment["content"] == "This is a comment"
        assert "id" in comment

    def test_list_comments(self, workspace, project, issue_for_comments):
        # Create a comment first
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
            key=MEMBER_KEY,
            json={"content": "List test comment"})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_comment(self, workspace, project, issue_for_comments):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
                          key=MEMBER_KEY,
                          json={"content": "Original"})
        comment_id = create_resp.json()["id"]

        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments/{comment_id}",
                   key=MEMBER_KEY,
                   json={"content": "Updated comment"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated comment"

    def test_delete_comment(self, workspace, project, issue_for_comments):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
                          key=MEMBER_KEY,
                          json={"content": "Delete me"})
        comment_id = create_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments/{comment_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204

    def test_guest_cannot_create_comment(self, workspace, project, issue_for_comments):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_for_comments['id']}/comments",
                   key=GUEST_KEY,
                   json={"content": "Guest comment"})
        assert resp.status_code == 403


class TestReactions:
    @pytest.fixture()
    def comment_for_reactions(self, workspace, project, state_todo):
        issue_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                         key=MEMBER_KEY,
                         json={"name": "Reaction Issue", "stateId": state_todo["id"], "priority": "none"})
        issue_id = issue_resp.json()["id"]
        comment_resp = api("post",
                           f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}/comments",
                           key=MEMBER_KEY,
                           json={"content": "React to me"})
        return {"issueId": issue_id, "commentId": comment_resp.json()["id"]}

    def test_add_reaction(self, workspace, project, comment_for_reactions):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{comment_for_reactions['issueId']}/comments/{comment_for_reactions['commentId']}/reactions",
                   key=MEMBER_KEY,
                   json={"emoji": "thumbsup"})
        assert resp.status_code == 201
        assert resp.json()["emoji"] == "thumbsup"

    def test_remove_reaction(self, workspace, project, comment_for_reactions):
        add_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{comment_for_reactions['issueId']}/comments/{comment_for_reactions['commentId']}/reactions",
                       key=MEMBER_KEY,
                       json={"emoji": "heart"})
        reaction_id = add_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{comment_for_reactions['issueId']}/comments/{comment_for_reactions['commentId']}/reactions/{reaction_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────
# Test: Cycles
# ─────────────────────────────────────────────────────────────────────

class TestCycles:
    def test_create_cycle(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                   key=MEMBER_KEY,
                   json={"name": "Sprint 1", "description": "First sprint",
                         "startDate": "2026-05-01", "endDate": "2026-05-14"})
        assert resp.status_code == 201
        cycle = resp.json()
        assert cycle["name"] == "Sprint 1"
        assert cycle["startDate"] == "2026-05-01"
        assert cycle["endDate"] == "2026-05-14"

    def test_create_cycle_invalid_dates(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                   key=MEMBER_KEY,
                   json={"name": "Bad Sprint", "startDate": "2026-05-14", "endDate": "2026-05-01"})
        assert resp.status_code == 400

    def test_list_cycles(self, workspace, project):
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
            key=MEMBER_KEY,
            json={"name": "List Sprint", "startDate": "2026-05-01", "endDate": "2026-05-14"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_cycle_analytics(self, workspace, project, state_todo, state_done):
        # Create a cycle
        cycle_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                         key=MEMBER_KEY,
                         json={"name": "Analytics Sprint", "startDate": "2026-06-01",
                               "endDate": "2026-06-14"})
        cycle_id = cycle_resp.json()["id"]

        # Create issues
        issue1_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                          key=MEMBER_KEY,
                          json={"name": "Cycle Issue 1", "stateId": state_todo["id"], "priority": "high"})
        issue2_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                          key=MEMBER_KEY,
                          json={"name": "Cycle Issue 2", "stateId": state_done["id"], "priority": "low"})

        # Add issues to cycle
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}/issues",
            key=MEMBER_KEY,
            json={"issueId": issue1_resp.json()["id"]})
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}/issues",
            key=MEMBER_KEY,
            json={"issueId": issue2_resp.json()["id"]})

        # Get cycle with analytics
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        cycle = resp.json()
        assert cycle["totalIssues"] == 2
        assert cycle["completedIssues"] == 1  # state_done is in "completed" group
        assert cycle["pendingIssues"] == 1

    def test_remove_issue_from_cycle(self, workspace, project, state_todo):
        cycle_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                         key=MEMBER_KEY,
                         json={"name": "Remove Sprint", "startDate": "2026-07-01",
                               "endDate": "2026-07-14"})
        cycle_id = cycle_resp.json()["id"]

        issue_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                         key=MEMBER_KEY,
                         json={"name": "Remove from cycle", "stateId": state_todo["id"],
                               "priority": "none"})
        issue_id = issue_resp.json()["id"]

        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}/issues",
            key=MEMBER_KEY,
            json={"issueId": issue_id})

        # Remove
        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}/issues/{issue_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204

        # Verify
        cycle = api("get",
                    f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}",
                    key=MEMBER_KEY).json()
        assert cycle["totalIssues"] == 0

    def test_update_cycle(self, workspace, project):
        cycle_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                         key=MEMBER_KEY,
                         json={"name": "Update Me", "startDate": "2026-08-01",
                               "endDate": "2026-08-14"})
        cycle_id = cycle_resp.json()["id"]

        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}",
                   key=MEMBER_KEY,
                   json={"name": "Updated Sprint"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Sprint"

    def test_delete_cycle(self, workspace, project):
        cycle_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles",
                         key=MEMBER_KEY,
                         json={"name": "Delete Me", "startDate": "2026-09-01",
                               "endDate": "2026-09-14"})
        cycle_id = cycle_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/cycles/{cycle_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────
# Test: Modules
# ─────────────────────────────────────────────────────────────────────

class TestModules:
    def test_create_module(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                   key=MEMBER_KEY,
                   json={"name": "Auth Module", "description": "Authentication feature"})
        assert resp.status_code == 201
        module = resp.json()
        assert module["name"] == "Auth Module"

    def test_module_progress(self, workspace, project, state_todo, state_done):
        # Create a module
        mod_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                       key=MEMBER_KEY,
                       json={"name": "Progress Module", "description": "Track progress"})
        module_id = mod_resp.json()["id"]

        # Create issues - one done, two not done
        issue1 = api("post",
                     f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Mod Issue 1", "stateId": state_done["id"], "priority": "none"}).json()
        issue2 = api("post",
                     f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Mod Issue 2", "stateId": state_todo["id"], "priority": "none"}).json()
        issue3 = api("post",
                     f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Mod Issue 3", "stateId": state_todo["id"], "priority": "none"}).json()

        # Add issues to module
        for issue in [issue1, issue2, issue3]:
            api("post",
                f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}/issues",
                key=MEMBER_KEY,
                json={"issueId": issue["id"]})

        # Check progress
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        module = resp.json()
        assert module["totalIssues"] == 3
        assert module["completedIssues"] == 1

    def test_remove_issue_from_module(self, workspace, project, state_todo):
        mod_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                       key=MEMBER_KEY,
                       json={"name": "Remove Module"})
        module_id = mod_resp.json()["id"]

        issue = api("post",
                    f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                    key=MEMBER_KEY,
                    json={"name": "Remove from mod", "stateId": state_todo["id"],
                          "priority": "none"}).json()

        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}/issues",
            key=MEMBER_KEY,
            json={"issueId": issue["id"]})

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}/issues/{issue['id']}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204

        module = api("get",
                     f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}",
                     key=MEMBER_KEY).json()
        assert module["totalIssues"] == 0

    def test_list_modules(self, workspace, project):
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
            key=MEMBER_KEY,
            json={"name": "List Module"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_module(self, workspace, project):
        mod_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                       key=MEMBER_KEY,
                       json={"name": "Update Module"})
        module_id = mod_resp.json()["id"]

        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}",
                   key=MEMBER_KEY,
                   json={"name": "Renamed Module"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Module"

    def test_delete_module(self, workspace, project):
        mod_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules",
                       key=MEMBER_KEY,
                       json={"name": "Delete Module"})
        module_id = mod_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/modules/{module_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────
# Test: Views
# ─────────────────────────────────────────────────────────────────────

class TestViews:
    def test_create_view(self, workspace, project, state_todo):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
                   key=MEMBER_KEY,
                   json={"name": "My Bugs", "filters": {"stateId": state_todo["id"], "priority": "urgent"}})
        assert resp.status_code == 201
        view = resp.json()
        assert view["name"] == "My Bugs"
        assert view["filters"]["priority"] == "urgent"

    def test_list_views(self, workspace, project, state_todo):
        # Ensure at least one view exists
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
            key=MEMBER_KEY,
            json={"name": "List View", "filters": {}})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_view(self, workspace, project):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
                          key=MEMBER_KEY,
                          json={"name": "Get View", "filters": {"priority": "high"}})
        view_id = create_resp.json()["id"]

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views/{view_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get View"

    def test_update_view(self, workspace, project):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
                          key=MEMBER_KEY,
                          json={"name": "Old Name", "filters": {}})
        view_id = create_resp.json()["id"]

        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views/{view_id}",
                   key=MEMBER_KEY,
                   json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_view(self, workspace, project):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views",
                          key=MEMBER_KEY,
                          json={"name": "Delete View", "filters": {}})
        view_id = create_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/views/{view_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────
# Test: Pages
# ─────────────────────────────────────────────────────────────────────

class TestPages:
    def test_create_page(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                   key=MEMBER_KEY,
                   json={"title": "Getting Started", "content": "# Welcome\nThis is the wiki."})
        assert resp.status_code == 201
        page = resp.json()
        assert page["title"] == "Getting Started"
        assert "# Welcome" in page["content"]

    def test_nested_pages(self, workspace, project):
        parent_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                          key=MEMBER_KEY,
                          json={"title": "Parent Page", "content": "Parent content"})
        parent_id = parent_resp.json()["id"]

        child_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                         key=MEMBER_KEY,
                         json={"title": "Child Page", "content": "Child content",
                               "parentId": parent_id})
        assert child_resp.status_code == 201
        assert child_resp.json()["parentId"] == parent_id

    def test_list_pages(self, workspace, project):
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
            key=MEMBER_KEY,
            json={"title": "List Page", "content": "List content"})
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_page(self, workspace, project):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                          key=MEMBER_KEY,
                          json={"title": "Update Me", "content": "Old content"})
        page_id = create_resp.json()["id"]

        resp = api("patch",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages/{page_id}",
                   key=MEMBER_KEY,
                   json={"content": "New content"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "New content"

    def test_delete_page(self, workspace, project):
        create_resp = api("post",
                          f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                          key=MEMBER_KEY,
                          json={"title": "Delete Me", "content": ""})
        page_id = create_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages/{page_id}",
                   key=MEMBER_KEY)
        assert resp.status_code == 204

    def test_guest_cannot_create_page(self, workspace, project):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/pages",
                   key=GUEST_KEY,
                   json={"title": "Guest Page", "content": "nope"})
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# Test: Activity Log
# ─────────────────────────────────────────────────────────────────────

class TestActivity:
    def test_activity_on_state_change(self, workspace, project, state_todo, state_done):
        # Create issue
        issue_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                         key=MEMBER_KEY,
                         json={"name": "Activity Test", "stateId": state_todo["id"], "priority": "none"})
        issue_id = issue_resp.json()["id"]

        # Change state
        api("patch",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
            key=MEMBER_KEY,
            json={"stateId": state_done["id"]})

        # Check activity
        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}/activities",
                   key=MEMBER_KEY)
        assert resp.status_code == 200
        activities = resp.json()
        state_changes = [a for a in activities if a["field"] == "stateId"]
        assert len(state_changes) >= 1
        latest = state_changes[-1]
        assert latest["oldValue"] == state_todo["id"]
        assert latest["newValue"] == state_done["id"]

    def test_activity_on_priority_change(self, workspace, project, state_todo):
        issue_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                         key=MEMBER_KEY,
                         json={"name": "Priority Activity", "stateId": state_todo["id"],
                               "priority": "low"})
        issue_id = issue_resp.json()["id"]

        api("patch",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
            key=MEMBER_KEY,
            json={"priority": "urgent"})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}/activities",
                   key=MEMBER_KEY)
        activities = resp.json()
        priority_changes = [a for a in activities if a["field"] == "priority"]
        assert len(priority_changes) >= 1
        assert priority_changes[-1]["oldValue"] == "low"
        assert priority_changes[-1]["newValue"] == "urgent"

    def test_activity_on_assignee_change(self, workspace, project, state_todo, member_in_workspace):
        issue_resp = api("post",
                         f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues",
                         key=MEMBER_KEY,
                         json={"name": "Assignee Activity", "stateId": state_todo["id"],
                               "priority": "none"})
        issue_id = issue_resp.json()["id"]

        api("patch",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}",
            key=MEMBER_KEY,
            json={"assignees": [member_in_workspace["userId"]]})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/issues/{issue_id}/activities",
                   key=MEMBER_KEY)
        activities = resp.json()
        assignee_changes = [a for a in activities if a["field"] == "assignees"]
        assert len(assignee_changes) >= 1


# ─────────────────────────────────────────────────────────────────────
# Test: Workspace Isolation
# ─────────────────────────────────────────────────────────────────────

class TestWorkspaceIsolation:
    def test_user_cannot_access_other_workspace(self):
        """Users in workspace A cannot see data in workspace B."""
        # Create workspace A with admin
        slug_a = f"ws-a-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", key=ADMIN_KEY,
            json={"name": "Workspace A", "slug": slug_a})

        # Create workspace B with other admin
        slug_b = f"ws-b-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", key=OTHER_ADMIN_KEY,
            json={"name": "Workspace B", "slug": slug_b})

        # Create a project in workspace B
        proj_resp = api("post", f"/api/workspaces/{slug_b}/projects", key=OTHER_ADMIN_KEY,
                        json={"name": "Secret Project", "identifier": "SEC"})
        assert proj_resp.status_code == 201

        # Admin of workspace A should not see workspace B's projects
        resp = api("get", f"/api/workspaces/{slug_b}/projects", key=ADMIN_KEY)
        # Should get 403 or 404 since ADMIN_KEY is not a member of workspace B
        assert resp.status_code in (403, 404)

    def test_workspace_list_only_shows_own(self):
        """Each user only sees workspaces they belong to."""
        slug = f"exclusive-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", key=OTHER_ADMIN_KEY,
            json={"name": "Exclusive", "slug": slug})

        # ADMIN_KEY should not see this workspace
        resp = api("get", "/api/workspaces", key=ADMIN_KEY)
        slugs = [w["slug"] for w in resp.json()]
        assert slug not in slugs


# ─────────────────────────────────────────────────────────────────────
# Test: Project Members
# ─────────────────────────────────────────────────────────────────────

class TestProjectMembers:
    def test_add_project_member(self, workspace, project, member_in_workspace):
        resp = api("post",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/members",
                   json={"memberId": member_in_workspace["id"], "role": "member"})
        assert resp.status_code == 201
        assert resp.json()["role"] == "member"

    def test_list_project_members(self, workspace, project, member_in_workspace):
        # Ensure member is added
        api("post",
            f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/members",
            json={"memberId": member_in_workspace["id"], "role": "member"})

        resp = api("get",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/members")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_remove_project_member(self, workspace, project, member_in_workspace):
        # Add then remove
        add_resp = api("post",
                       f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/members",
                       json={"memberId": member_in_workspace["id"], "role": "member"})
        pm_id = add_resp.json()["id"]

        resp = api("delete",
                   f"/api/workspaces/{workspace['slug']}/projects/{project['id']}/members/{pm_id}")
        assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────
# Test: Delete workspace
# ─────────────────────────────────────────────────────────────────────

class TestWorkspaceDelete:
    def test_delete_workspace(self):
        slug = f"delete-me-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Delete", "slug": slug})
        resp = api("delete", f"/api/workspaces/{slug}")
        assert resp.status_code == 204
        # Verify gone
        resp = api("get", f"/api/workspaces/{slug}")
        assert resp.status_code == 404

    def test_member_cannot_delete_workspace(self, workspace, member_in_workspace):
        resp = api("delete", f"/api/workspaces/{workspace['slug']}", key=MEMBER_KEY)
        assert resp.status_code == 403
