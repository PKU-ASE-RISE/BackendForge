"""
L2 Integration Tests for Plane Project Management API.

Targets LLM bug patterns:
- Pattern 1: camelCase field naming (stateId, projectId, dueDate, etc.)
- Pattern 2: Nested/relationship data not returned (assignees, labels arrays)
- Pattern 3: Filtering params declared but not implemented
- Pattern 4: Status codes wrong (201 vs 200, 204 vs 200, 404 vs empty)
- Pattern 5: Business logic empty (cycle analytics, module progress, auto-identifiers)
- Pattern 7: Cascade/side-effect missing (delete parent -> orphans)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
HTTP_TIMEOUT = 30

ADMIN_KEY = "admin-key-001"
MEMBER_KEY = "member-key-002"
GUEST_KEY = "guest-key-003"
USER2_KEY = "integ-user2-key-099"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    if key:
        headers["X-API-Key"] = key
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    return getattr(requests, method)(url, headers=headers, **kwargs)


def _get_user_id(api_key):
    slug = f"tmp-uid-{uuid.uuid4().hex[:8]}"
    resp = api("post", "/api/workspaces", key=api_key, json={"name": "Tmp", "slug": slug})
    if resp.status_code == 201:
        members_resp = api("get", f"/api/workspaces/{slug}/members", key=api_key)
        if members_resp.status_code == 200 and members_resp.json():
            user_id = members_resp.json()[0]["userId"]
            api("delete", f"/api/workspaces/{slug}", key=api_key)
            return user_id
    resp = api("get", "/api/workspaces", key=api_key)
    if resp.status_code == 200 and resp.json():
        ws = resp.json()[0]
        members_resp = api("get", f"/api/workspaces/{ws['slug']}/members", key=api_key)
        if members_resp.status_code == 200:
            for m in members_resp.json():
                if m["role"] == "admin":
                    api("delete", f"/api/workspaces/{slug}", key=api_key)
                    return m["userId"]
    api("delete", f"/api/workspaces/{slug}", key=api_key)
    raise RuntimeError(f"Could not determine userId for key {api_key}")


@pytest.fixture(scope="module")
def member_user_id():
    return _get_user_id(MEMBER_KEY)


@pytest.fixture(scope="module")
def guest_user_id():
    return _get_user_id(GUEST_KEY)


@pytest.fixture()
def setup(member_user_id, guest_user_id):
    """Create an isolated workspace, project, states, and labels for an L2 test."""
    slug = f"l2-integ-{uuid.uuid4().hex[:8]}"
    ws = api("post", "/api/workspaces", json={"name": "L2 Integration WS", "slug": slug}).json()

    member_uid = member_user_id
    api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

    guest_uid = guest_user_id
    api("post", f"/api/workspaces/{slug}/members", json={"userId": guest_uid, "role": "guest"})

    proj = api("post", f"/api/workspaces/{slug}/projects",
               json={"name": "L2 Project", "identifier": "LTWO", "description": "L2 test proj"}).json()

    state_backlog = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/states",
                        json={"name": "Backlog", "group": "backlog", "color": "#aaa", "order": 0}).json()
    state_todo = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/states",
                     json={"name": "Todo", "group": "unstarted", "color": "#bbb", "order": 1}).json()
    state_progress = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/states",
                         json={"name": "In Progress", "group": "started", "color": "#ccc", "order": 2}).json()
    state_done = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/states",
                     json={"name": "Done", "group": "completed", "color": "#ddd", "order": 3}).json()

    label_bug = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/labels",
                    json={"name": "bug", "color": "#ff0000"}).json()
    label_feat = api("post", f"/api/workspaces/{slug}/projects/{proj['id']}/labels",
                     json={"name": "feature", "color": "#00ff00"}).json()

    yield {
        "ws": ws, "slug": slug, "proj": proj,
        "state_backlog": state_backlog, "state_todo": state_todo,
        "state_progress": state_progress, "state_done": state_done,
        "label_bug": label_bug, "label_feat": label_feat,
        "member_uid": member_uid, "guest_uid": guest_uid,
    }
    api("delete", f"/api/workspaces/{slug}")


# ──────────────────────────────────────────────────────────────────────────────
# L2 Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestIssueFieldNaming:
    """Pattern 1: Verify camelCase field names in responses."""

    def test_issue_response_fields_are_camelcase(self, setup):
        """Create issue and verify all field names are camelCase, not snake_case."""
        unique_name = f"CamelCase Test {uuid.uuid4().hex[:6]}"
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": unique_name, "stateId": setup["state_todo"]["id"],
                      "priority": "high", "dueDate": "2026-07-20", "estimate": 8})
        assert r.status_code == 201
        issue = r.json()
        # Verify camelCase keys present
        assert "stateId" in issue
        assert "projectId" in issue
        assert "createdAt" in issue
        assert "updatedAt" in issue
        assert "dueDate" in issue
        assert "parentId" in issue or issue.get("parentId") is None
        # Verify snake_case NOT present
        assert "state_id" not in issue
        assert "project_id" not in issue
        assert "created_at" not in issue
        assert "due_date" not in issue
        assert "parent_id" not in issue
        # Verify values
        assert issue["name"] == unique_name
        assert issue["stateId"] == setup["state_todo"]["id"]
        assert issue["priority"] == "high"
        assert issue["dueDate"] == "2026-07-20"
        assert issue["estimate"] == 8

    def test_workspace_member_response_camelcase(self, setup):
        """WorkspaceMember response uses camelCase field names."""
        r = api("get", f"/api/workspaces/{setup['slug']}/members")
        assert r.status_code == 200
        members = r.json()
        assert len(members) >= 1
        m = members[0]
        assert "userId" in m
        assert "workspaceId" in m
        assert "createdAt" in m
        assert "user_id" not in m
        assert "workspace_id" not in m
        assert "created_at" not in m

    def test_cycle_response_camelcase(self, setup):
        """Cycle fields should be camelCase: startDate, endDate, totalIssues, etc."""
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                key=MEMBER_KEY,
                json={"name": f"CamelCycle-{uuid.uuid4().hex[:4]}", "startDate": "2026-08-01", "endDate": "2026-08-14"})
        assert r.status_code == 201
        cycle = r.json()
        assert "startDate" in cycle
        assert "endDate" in cycle
        assert "projectId" in cycle
        assert "createdAt" in cycle
        assert "start_date" not in cycle
        assert "end_date" not in cycle
        assert "project_id" not in cycle


class TestIssueAutoIdentifier:
    """Pattern 5: Business logic - auto-generated sequential identifiers."""

    def test_identifiers_sequential_and_formatted(self, setup):
        """Issues get PROJ-N identifiers sequentially."""
        # Create a fresh project to get clean sequence
        slug = setup["slug"]
        proj2 = api("post", f"/api/workspaces/{slug}/projects",
                    json={"name": "SeqProj", "identifier": "SEQ"}).json()
        st = api("post", f"/api/workspaces/{slug}/projects/{proj2['id']}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()

        ids = []
        for i in range(3):
            r = api("post", f"/api/workspaces/{slug}/projects/{proj2['id']}/issues",
                    key=MEMBER_KEY,
                    json={"name": f"Seq Issue {i}", "stateId": st["id"], "priority": "none"})
            assert r.status_code == 201
            ids.append(r.json()["identifier"])

        assert ids[0] == "SEQ-1"
        assert ids[1] == "SEQ-2"
        assert ids[2] == "SEQ-3"

    def test_identifier_persists_after_deletion(self, setup):
        """Deleting an issue should NOT reset the sequence counter."""
        slug = setup["slug"]
        proj3 = api("post", f"/api/workspaces/{slug}/projects",
                    json={"name": "DelSeqProj", "identifier": "DSQ"}).json()
        st = api("post", f"/api/workspaces/{slug}/projects/{proj3['id']}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()

        # Create issue 1
        r1 = api("post", f"/api/workspaces/{slug}/projects/{proj3['id']}/issues",
                 key=MEMBER_KEY, json={"name": "D1", "stateId": st["id"], "priority": "none"})
        assert r1.json()["identifier"] == "DSQ-1"

        # Delete issue 1
        api("delete", f"/api/workspaces/{slug}/projects/{proj3['id']}/issues/{r1.json()['id']}", key=MEMBER_KEY)

        # Create issue 2 - should be DSQ-2, NOT DSQ-1
        r2 = api("post", f"/api/workspaces/{slug}/projects/{proj3['id']}/issues",
                 key=MEMBER_KEY, json={"name": "D2", "stateId": st["id"], "priority": "none"})
        assert r2.status_code == 201
        assert r2.json()["identifier"] == "DSQ-2"


class TestIssueWithRelations:
    """Pattern 2: Nested data (assignees, labels) must be returned correctly."""

    def test_issue_returns_labels_array(self, setup):
        """Issue created with labels returns them in GET."""
        unique_name = f"Labels-Issue-{uuid.uuid4().hex[:6]}"
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": unique_name, "stateId": setup["state_todo"]["id"],
                      "priority": "low", "labels": [setup["label_bug"]["id"], setup["label_feat"]["id"]]})
        assert r.status_code == 201
        issue_id = r.json()["id"]

        # GET and verify labels preserved
        r2 = api("get", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues/{issue_id}",
                 key=MEMBER_KEY)
        assert r2.status_code == 200
        issue = r2.json()
        assert isinstance(issue["labels"], list)
        assert setup["label_bug"]["id"] in issue["labels"]
        assert setup["label_feat"]["id"] in issue["labels"]
        assert len(issue["labels"]) == 2

    def test_issue_returns_assignees_array(self, setup):
        """Issue with assignees returns them correctly."""
        unique_name = f"Assignees-Issue-{uuid.uuid4().hex[:6]}"
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": unique_name, "stateId": setup["state_todo"]["id"],
                      "priority": "medium", "assignees": [setup["member_uid"]]})
        assert r.status_code == 201
        issue_id = r.json()["id"]

        r2 = api("get", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues/{issue_id}",
                 key=MEMBER_KEY)
        assert r2.status_code == 200
        assert isinstance(r2.json()["assignees"], list)
        assert setup["member_uid"] in r2.json()["assignees"]

    def test_update_issue_labels_replaces(self, setup):
        """PATCH with new labels replaces old labels array."""
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": f"Replace-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"],
                      "priority": "none", "labels": [setup["label_bug"]["id"]]})
        issue_id = r.json()["id"]

        # Update to only feature label
        r2 = api("patch", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues/{issue_id}",
                 key=MEMBER_KEY, json={"labels": [setup["label_feat"]["id"]]})
        assert r2.status_code == 200
        assert setup["label_feat"]["id"] in r2.json()["labels"]
        assert setup["label_bug"]["id"] not in r2.json()["labels"]


class TestIssueFiltering:
    """Pattern 3: Filtering params must actually filter."""

    def test_filter_priority_excludes_others(self, setup):
        """Filter by priority=urgent should exclude low/medium/high issues."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        state_id = setup["state_todo"]["id"]

        # Create issues with different priorities
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"urgent-{uuid.uuid4().hex[:4]}", "stateId": state_id, "priority": "urgent"})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"low-{uuid.uuid4().hex[:4]}", "stateId": state_id, "priority": "low"})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"priority": "urgent"})
        assert r.status_code == 200
        issues = r.json()
        assert len(issues) >= 1
        for iss in issues:
            assert iss["priority"] == "urgent"

    def test_filter_state_only_returns_matching(self, setup):
        """Filter by stateId should only return issues in that state."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        # Create issue in done state
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"done-{uuid.uuid4().hex[:4]}", "stateId": setup["state_done"]["id"], "priority": "none"})
        # Create issue in todo state
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"todo-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"stateId": setup["state_done"]["id"]})
        assert r.status_code == 200
        for iss in r.json():
            assert iss["stateId"] == setup["state_done"]["id"]

    def test_filter_label_returns_only_matching(self, setup):
        """Filter by label returns only issues with that label."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        unique = uuid.uuid4().hex[:6]
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"bug-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "labels": [setup["label_bug"]["id"]]})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"feat-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "labels": [setup["label_feat"]["id"]]})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"label": setup["label_bug"]["id"]})
        assert r.status_code == 200
        issues = r.json()
        assert len(issues) >= 1
        for iss in issues:
            assert setup["label_bug"]["id"] in iss["labels"]

    def test_filter_assignee_returns_only_assigned(self, setup):
        """Filter by assignee only returns issues assigned to that user."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        unique = uuid.uuid4().hex[:6]
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"assigned-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "assignees": [setup["member_uid"]]})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"unassigned-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "assignees": []})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"assignee": setup["member_uid"]})
        assert r.status_code == 200
        for iss in r.json():
            assert setup["member_uid"] in iss["assignees"]

    def test_filter_due_date_range(self, setup):
        """Filter by dueDateStart/dueDateEnd works correctly."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        unique = uuid.uuid4().hex[:6]
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"due-in-range-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "dueDate": "2026-09-15"})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": f"due-outside-{unique}", "stateId": setup["state_todo"]["id"],
                  "priority": "none", "dueDate": "2027-01-15"})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"dueDateStart": "2026-09-01", "dueDateEnd": "2026-09-30"})
        assert r.status_code == 200
        issues = r.json()
        assert len(issues) >= 1
        for iss in issues:
            assert iss["dueDate"] is not None
            assert "2026-09-01" <= iss["dueDate"] <= "2026-09-30"


class TestStatusCodes:
    """Pattern 4: Correct HTTP status codes."""

    def test_create_workspace_returns_201(self):
        slug = f"sc-{uuid.uuid4().hex[:8]}"
        r = api("post", "/api/workspaces", json={"name": "SC Test", "slug": slug})
        assert r.status_code == 201
        api("delete", f"/api/workspaces/{slug}")

    def test_create_issue_returns_201(self, setup):
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": f"SC-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"})
        assert r.status_code == 201

    def test_delete_issue_returns_204(self, setup):
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                key=MEMBER_KEY,
                json={"name": f"Del-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"})
        issue_id = r.json()["id"]
        r2 = api("delete", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues/{issue_id}",
                 key=MEMBER_KEY)
        assert r2.status_code == 204

    def test_get_nonexistent_issue_returns_404(self, setup):
        fake_id = str(uuid.uuid4())
        r = api("get", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues/{fake_id}",
                key=MEMBER_KEY)
        assert r.status_code == 404

    def test_create_cycle_returns_201(self, setup):
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                key=MEMBER_KEY,
                json={"name": f"SC-Cycle-{uuid.uuid4().hex[:4]}", "startDate": "2026-10-01", "endDate": "2026-10-14"})
        assert r.status_code == 201

    def test_delete_cycle_returns_204(self, setup):
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                key=MEMBER_KEY,
                json={"name": f"DelCycle-{uuid.uuid4().hex[:4]}", "startDate": "2026-11-01", "endDate": "2026-11-14"})
        cycle_id = r.json()["id"]
        r2 = api("delete", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles/{cycle_id}",
                 key=MEMBER_KEY)
        assert r2.status_code == 204

    def test_add_issue_to_cycle_returns_201(self, setup):
        cycle = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                    key=MEMBER_KEY,
                    json={"name": f"AddCycle-{uuid.uuid4().hex[:4]}", "startDate": "2026-12-01", "endDate": "2026-12-14"}).json()
        issue = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/issues",
                    key=MEMBER_KEY,
                    json={"name": f"AddI-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles/{cycle['id']}/issues",
                key=MEMBER_KEY, json={"issueId": issue["id"]})
        assert r.status_code == 201


class TestCycleAnalytics:
    """Pattern 5: Cycle analytics must compute real values."""

    def test_cycle_counts_update_when_issues_added(self, setup):
        """totalIssues/completedIssues/pendingIssues are computed not hardcoded."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        cycle = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles",
                    key=MEMBER_KEY,
                    json={"name": f"Analytics-{uuid.uuid4().hex[:4]}", "startDate": "2027-01-01", "endDate": "2027-01-14"}).json()

        # Initially zero
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 0
        assert r.json()["completedIssues"] == 0
        assert r.json()["pendingIssues"] == 0

        # Add a completed issue
        iss_done = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                       key=MEMBER_KEY,
                       json={"name": f"Done-{uuid.uuid4().hex[:4]}", "stateId": setup["state_done"]["id"], "priority": "none"}).json()
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}/issues",
            key=MEMBER_KEY, json={"issueId": iss_done["id"]})

        # Add a pending issue
        iss_todo = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                       key=MEMBER_KEY,
                       json={"name": f"Todo-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}/issues",
            key=MEMBER_KEY, json={"issueId": iss_todo["id"]})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.status_code == 200
        data = r.json()
        assert data["totalIssues"] == 2
        assert data["completedIssues"] == 1
        assert data["pendingIssues"] == 1

    def test_cycle_analytics_updates_on_state_change(self, setup):
        """Changing issue state from todo->done should update cycle analytics."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        cycle = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles",
                    key=MEMBER_KEY,
                    json={"name": f"StateChange-{uuid.uuid4().hex[:4]}", "startDate": "2027-02-01", "endDate": "2027-02-14"}).json()

        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": f"WillComplete-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}/issues",
            key=MEMBER_KEY, json={"issueId": iss["id"]})

        # Before: 1 total, 0 completed
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.json()["completedIssues"] == 0

        # Change state to done
        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}",
            key=MEMBER_KEY, json={"stateId": setup["state_done"]["id"]})

        # After: 1 completed
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.json()["completedIssues"] == 1
        assert r.json()["totalIssues"] == 1


class TestModuleProgress:
    """Pattern 5: Module progress computation."""

    def test_module_progress_computed(self, setup):
        """Module totalIssues and completedIssues are dynamically computed."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        module = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/modules",
                     key=MEMBER_KEY,
                     json={"name": f"Progress-{uuid.uuid4().hex[:4]}"}).json()

        # Add 2 done + 1 todo
        for _ in range(2):
            iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                      key=MEMBER_KEY,
                      json={"name": f"ModDone-{uuid.uuid4().hex[:4]}", "stateId": setup["state_done"]["id"], "priority": "none"}).json()
            api("post", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{module['id']}/issues",
                key=MEMBER_KEY, json={"issueId": iss["id"]})

        iss_todo = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                       key=MEMBER_KEY,
                       json={"name": f"ModTodo-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{module['id']}/issues",
            key=MEMBER_KEY, json={"issueId": iss_todo["id"]})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{module['id']}", key=MEMBER_KEY)
        assert r.status_code == 200
        assert r.json()["totalIssues"] == 3
        assert r.json()["completedIssues"] == 2


class TestActivityLog:
    """Pattern 5+7: Activity log records real changes."""

    def test_activity_records_name_change(self, setup):
        """Changing issue name should produce an activity entry."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        old_name = f"OldName-{uuid.uuid4().hex[:6]}"
        new_name = f"NewName-{uuid.uuid4().hex[:6]}"
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": old_name, "stateId": setup["state_todo"]["id"], "priority": "none"}).json()

        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}",
            key=MEMBER_KEY, json={"name": new_name})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}/activities", key=MEMBER_KEY)
        assert r.status_code == 200
        activities = r.json()
        name_changes = [a for a in activities if a["field"] == "name"]
        assert len(name_changes) >= 1
        assert name_changes[-1]["oldValue"] == old_name
        assert name_changes[-1]["newValue"] == new_name

    def test_activity_has_actor_id(self, setup):
        """Activity entries include actorId field."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": f"Actor-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "low"}).json()

        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}",
            key=MEMBER_KEY, json={"priority": "high"})

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}/activities", key=MEMBER_KEY)
        activities = r.json()
        assert len(activities) >= 1
        assert "actorId" in activities[-1]
        assert activities[-1]["actorId"] is not None
        assert "createdAt" in activities[-1]


class TestViewFilters:
    """Pattern 2: View stores filters object correctly."""

    def test_view_preserves_complex_filters(self, setup):
        """View with multiple filter keys preserves all of them on GET."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        filters = {
            "stateId": setup["state_todo"]["id"],
            "priority": "high",
            "labels": [setup["label_bug"]["id"]],
        }
        r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/views",
                key=MEMBER_KEY, json={"name": f"Complex-{uuid.uuid4().hex[:4]}", "filters": filters})
        assert r.status_code == 201
        view_id = r.json()["id"]

        r2 = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/views/{view_id}", key=MEMBER_KEY)
        assert r2.status_code == 200
        retrieved_filters = r2.json()["filters"]
        assert retrieved_filters["stateId"] == setup["state_todo"]["id"]
        assert retrieved_filters["priority"] == "high"
        assert setup["label_bug"]["id"] in retrieved_filters["labels"]


class TestCascadeDelete:
    """Pattern 7: Cascade/side-effect behavior."""

    def test_removing_issue_from_cycle_updates_count(self, setup):
        """Removing an issue from a cycle decreases totalIssues."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        cycle = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles",
                    key=MEMBER_KEY,
                    json={"name": f"Cascade-{uuid.uuid4().hex[:4]}", "startDate": "2027-03-01", "endDate": "2027-03-14"}).json()
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": f"CascadeIss-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}/issues",
            key=MEMBER_KEY, json={"issueId": iss["id"]})

        # Verify count is 1
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 1

        # Remove
        api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}/issues/{iss['id']}",
            key=MEMBER_KEY)

        # Count should be 0
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle['id']}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 0

    def test_delete_workspace_returns_404_on_get(self):
        """Deleted workspace is gone."""
        slug = f"del-ws-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Del WS", "slug": slug})
        r = api("delete", f"/api/workspaces/{slug}")
        assert r.status_code == 204
        r2 = api("get", f"/api/workspaces/{slug}")
        assert r2.status_code == 404


class TestStatesOrdering:
    """Pattern 3: States ordered by order field."""

    def test_states_returned_in_order(self, setup):
        """GET states returns them sorted by the order field."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/states", key=MEMBER_KEY)
        assert r.status_code == 200
        states = r.json()
        orders = [s["order"] for s in states]
        assert orders == sorted(orders)
        # Also verify all states have required fields
        for s in states:
            assert "id" in s
            assert "name" in s
            assert "group" in s
            assert "color" in s
            assert "order" in s
            assert "projectId" in s


class TestSubIssues:
    """Pattern 2: parentId relation works."""

    def test_create_sub_issue(self, setup):
        """Creating sub-issue with parentId is preserved."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        parent = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                     key=MEMBER_KEY,
                     json={"name": f"Parent-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"], "priority": "none"}).json()
        child = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                    key=MEMBER_KEY,
                    json={"name": f"Child-{uuid.uuid4().hex[:4]}", "stateId": setup["state_todo"]["id"],
                          "priority": "none", "parentId": parent["id"]})
        assert child.status_code == 201
        assert child.json()["parentId"] == parent["id"]

        # GET confirms parentId
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{child.json()['id']}", key=MEMBER_KEY)
        assert r.json()["parentId"] == parent["id"]


class TestCycleDateValidation:
    """Pattern 8: Business logic validation - endDate must be after startDate."""

    def test_invalid_cycle_dates_return_400(self, setup):
        """Cycle with endDate before startDate returns 400."""
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                key=MEMBER_KEY,
                json={"name": "BadDates", "startDate": "2027-05-10", "endDate": "2027-05-01"})
        assert r.status_code == 400

    def test_valid_cycle_dates_succeed(self, setup):
        """Cycle with valid dates returns 201."""
        r = api("post", f"/api/workspaces/{setup['slug']}/projects/{setup['proj']['id']}/cycles",
                key=MEMBER_KEY,
                json={"name": f"GoodDates-{uuid.uuid4().hex[:4]}", "startDate": "2027-06-01", "endDate": "2027-06-14"})
        assert r.status_code == 201
        assert r.json()["startDate"] == "2027-06-01"
        assert r.json()["endDate"] == "2027-06-14"


class TestPageNesting:
    """Pattern 2: Page parentId preserved."""

    def test_page_parent_child_relationship(self, setup):
        """Page with parentId is stored and returned correctly."""
        slug, proj_id = setup["slug"], setup["proj"]["id"]
        parent = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/pages",
                     key=MEMBER_KEY,
                     json={"title": f"ParentPage-{uuid.uuid4().hex[:4]}", "content": "Parent"}).json()
        child = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/pages",
                    key=MEMBER_KEY,
                    json={"title": f"ChildPage-{uuid.uuid4().hex[:4]}", "content": "Child",
                          "parentId": parent["id"]})
        assert child.status_code == 201
        assert child.json()["parentId"] == parent["id"]

        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/pages/{child.json()['id']}", key=MEMBER_KEY)
        assert r.json()["parentId"] == parent["id"]
        assert r.json()["title"] == child.json()["title"]
