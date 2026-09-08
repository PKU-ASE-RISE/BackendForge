"""
L3 Workflow Tests for Plane Project Management API.

Multi-step cross-entity workflows testing:
- Pattern 1: camelCase field naming across multiple entities
- Pattern 2: Nested data and relationships preserved end-to-end
- Pattern 5: Business logic actually works (analytics, identifiers, computed values)
- Pattern 6: Data isolation between users/workspaces
- Pattern 7: Cascade/side-effects (delete, state changes updating counters)
- Pattern 8: Order-sensitive operations and uniqueness constraints
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
USER2_KEY = "workflow-user2-key-050"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    if key:
        headers["X-API-Key"] = key
    url = f"{BASE_URL}{path}"
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    return getattr(requests, method)(url, headers=headers, **kwargs)


def _get_user_id(api_key):
    slug = f"tmp-wf-{uuid.uuid4().hex[:8]}"
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


class TestSprintLifecycleWorkflow:
    """
    Full sprint lifecycle: create project → states → issues → cycle → add issues →
    verify analytics → complete issues → verify analytics update → remove issue → verify.
    Patterns: 5 (analytics computation), 7 (side effects), 1 (field naming)
    """

    def test_sprint_lifecycle(self):
        slug = f"wf-sprint-{uuid.uuid4().hex[:8]}"
        # 1. Create workspace
        ws = api("post", "/api/workspaces", json={"name": "Sprint WF", "slug": slug})
        assert ws.status_code == 201
        assert ws.json()["slug"] == slug

        # 2. Add member
        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        # 3. Create project
        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Sprint Project", "identifier": "SPR"})
        assert proj.status_code == 201
        proj_id = proj.json()["id"]
        assert proj.json()["identifier"] == "SPR"

        # 4. Create states
        st_todo = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Todo", "group": "unstarted", "color": "#aaa", "order": 1}).json()
        st_done = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Done", "group": "completed", "color": "#0f0", "order": 2}).json()

        # 5. Create issues
        iss1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Sprint Task 1", "stateId": st_todo["id"], "priority": "high"}).json()
        iss2 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Sprint Task 2", "stateId": st_todo["id"], "priority": "medium"}).json()
        iss3 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                   key=MEMBER_KEY,
                   json={"name": "Sprint Task 3", "stateId": st_done["id"], "priority": "low"}).json()

        assert iss1["identifier"] == "SPR-1"
        assert iss2["identifier"] == "SPR-2"
        assert iss3["identifier"] == "SPR-3"

        # 6. Create cycle
        cycle = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles",
                    key=MEMBER_KEY,
                    json={"name": "Sprint 1", "startDate": "2027-01-01", "endDate": "2027-01-14"})
        assert cycle.status_code == 201
        cycle_id = cycle.json()["id"]
        assert "totalIssues" in cycle.json()

        # 7. Add issues to cycle
        for iss in [iss1, iss2, iss3]:
            r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle_id}/issues",
                    key=MEMBER_KEY, json={"issueId": iss["id"]})
            assert r.status_code == 201

        # 8. Verify analytics: 3 total, 1 completed (iss3), 2 pending
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle_id}", key=MEMBER_KEY)
        assert r.status_code == 200
        assert r.json()["totalIssues"] == 3
        assert r.json()["completedIssues"] == 1
        assert r.json()["pendingIssues"] == 2

        # 9. Complete iss1
        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss1['id']}",
            key=MEMBER_KEY, json={"stateId": st_done["id"]})

        # 10. Verify analytics updated: 2 completed now
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle_id}", key=MEMBER_KEY)
        assert r.json()["completedIssues"] == 2
        assert r.json()["pendingIssues"] == 1

        # 11. Remove iss2 from cycle
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle_id}/issues/{iss2['id']}",
                key=MEMBER_KEY)
        assert r.status_code == 204

        # 12. Final analytics: 2 total, 2 completed, 0 pending
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/cycles/{cycle_id}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 2
        assert r.json()["completedIssues"] == 2
        assert r.json()["pendingIssues"] == 0


class TestModuleFeatureTrackingWorkflow:
    """
    Module feature tracking: create module → add issues → verify progress →
    complete issues → verify updated progress → remove issue → verify.
    Patterns: 5 (computed progress), 7 (side effects), 2 (nested data)
    """

    def test_module_progress_workflow(self):
        slug = f"wf-mod-{uuid.uuid4().hex[:8]}"
        ws = api("post", "/api/workspaces", json={"name": "Module WF", "slug": slug}).json()

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Feature Project", "identifier": "FEA"}).json()
        proj_id = proj["id"]

        st_todo = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Open", "group": "unstarted", "color": "#111", "order": 1}).json()
        st_done = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Closed", "group": "completed", "color": "#222", "order": 2}).json()

        label = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/labels",
                    json={"name": "auth", "color": "#abcdef"}).json()

        # Create module
        mod = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/modules",
                  key=MEMBER_KEY,
                  json={"name": "Authentication", "description": "Auth feature",
                        "startDate": "2027-02-01", "endDate": "2027-03-01"})
        assert mod.status_code == 201
        mod_id = mod.json()["id"]
        assert mod.json()["name"] == "Authentication"

        # Create issues with labels
        issues = []
        for i in range(4):
            iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                      key=MEMBER_KEY,
                      json={"name": f"Auth task {i}", "stateId": st_todo["id"],
                            "priority": "medium", "labels": [label["id"]]}).json()
            issues.append(iss)
            # Add to module
            r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{mod_id}/issues",
                    key=MEMBER_KEY, json={"issueId": iss["id"]})
            assert r.status_code == 201

        # Verify progress: 4 total, 0 completed
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{mod_id}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 4
        assert r.json()["completedIssues"] == 0

        # Complete 2 issues
        for iss in issues[:2]:
            api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}",
                key=MEMBER_KEY, json={"stateId": st_done["id"]})

        # Verify: 4 total, 2 completed
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{mod_id}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 4
        assert r.json()["completedIssues"] == 2

        # Remove one issue from module
        api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{mod_id}/issues/{issues[3]['id']}",
            key=MEMBER_KEY)

        # Verify: 3 total, 2 completed
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/modules/{mod_id}", key=MEMBER_KEY)
        assert r.json()["totalIssues"] == 3
        assert r.json()["completedIssues"] == 2

        # Verify the issues still have their labels (Pattern 2)
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issues[0]['id']}", key=MEMBER_KEY)
        assert label["id"] in r.json()["labels"]


class TestWorkspaceIsolationWorkflow:
    """
    Data isolation: Two users create workspaces → verify can't access each other's data.
    Patterns: 6 (data isolation), 4 (correct error codes)
    """

    def test_workspace_isolation(self):
        slug_a = f"wf-iso-a-{uuid.uuid4().hex[:8]}"
        slug_b = f"wf-iso-b-{uuid.uuid4().hex[:8]}"

        # User A creates workspace A
        ws_a = api("post", "/api/workspaces", key=ADMIN_KEY,
                   json={"name": "Workspace A", "slug": slug_a})
        assert ws_a.status_code == 201

        # User B creates workspace B
        ws_b = api("post", "/api/workspaces", key=USER2_KEY,
                   json={"name": "Workspace B", "slug": slug_b})
        assert ws_b.status_code == 201

        # User B creates project in B
        proj_b = api("post", f"/api/workspaces/{slug_b}/projects", key=USER2_KEY,
                     json={"name": "Secret", "identifier": "SEC"})
        assert proj_b.status_code == 201

        # User A can't see workspace B's projects
        r = api("get", f"/api/workspaces/{slug_b}/projects", key=ADMIN_KEY)
        assert r.status_code in (403, 404)

        # User A's workspace list doesn't include B
        r = api("get", "/api/workspaces", key=ADMIN_KEY)
        slugs = [w["slug"] for w in r.json()]
        assert slug_b not in slugs

        # User B's workspace list doesn't include A
        r = api("get", "/api/workspaces", key=USER2_KEY)
        slugs = [w["slug"] for w in r.json()]
        assert slug_a not in slugs

        # User A can't delete workspace B
        r = api("delete", f"/api/workspaces/{slug_b}", key=ADMIN_KEY)
        assert r.status_code in (403, 404)


class TestIssueActivityTrackingWorkflow:
    """
    Issue lifecycle with activity tracking: create → update multiple fields →
    verify each change has activity entry with correct old/new values.
    Patterns: 5 (activity logic works), 1 (field naming in activity), 7 (side effects)
    """

    def test_activity_tracks_all_changes(self):
        slug = f"wf-act-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Activity WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Activity Project", "identifier": "ACT"}).json()
        proj_id = proj["id"]

        st1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                  json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()
        st2 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                  json={"name": "In Progress", "group": "started", "color": "#111", "order": 2}).json()
        st3 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                  json={"name": "Done", "group": "completed", "color": "#222", "order": 3}).json()

        # Create issue
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": "Track Me", "stateId": st1["id"], "priority": "low"}).json()
        issue_id = iss["id"]

        # Change state: Open -> In Progress
        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}",
            key=MEMBER_KEY, json={"stateId": st2["id"]})

        # Change priority: low -> urgent
        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}",
            key=MEMBER_KEY, json={"priority": "urgent"})

        # Change state: In Progress -> Done
        api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}",
            key=MEMBER_KEY, json={"stateId": st3["id"]})

        # Fetch activities
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/activities",
                key=MEMBER_KEY)
        assert r.status_code == 200
        activities = r.json()

        # Verify state changes
        state_changes = [a for a in activities if a["field"] == "stateId"]
        assert len(state_changes) >= 2
        # First change: st1 -> st2
        assert state_changes[0]["oldValue"] == st1["id"]
        assert state_changes[0]["newValue"] == st2["id"]
        # Second change: st2 -> st3
        assert state_changes[1]["oldValue"] == st2["id"]
        assert state_changes[1]["newValue"] == st3["id"]

        # Verify priority change
        priority_changes = [a for a in activities if a["field"] == "priority"]
        assert len(priority_changes) >= 1
        assert priority_changes[0]["oldValue"] == "low"
        assert priority_changes[0]["newValue"] == "urgent"

        # Verify all activities have required fields
        for a in activities:
            assert "id" in a
            assert "actorId" in a
            assert "createdAt" in a
            assert "field" in a


class TestRolePermissionsWorkflow:
    """
    Role-based access: admin creates resources → member can create issues/comments →
    guest cannot create issues → member cannot create states.
    Patterns: 6 (permission enforcement), 4 (correct 403 codes)
    """

    def test_role_permissions_enforced(self):
        slug = f"wf-role-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Role WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        guest_uid = _get_user_id(GUEST_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})
        api("post", f"/api/workspaces/{slug}/members", json={"userId": guest_uid, "role": "guest"})

        # Admin creates project (should succeed)
        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Role Project", "identifier": "ROL"})
        assert proj.status_code == 201
        proj_id = proj.json()["id"]

        # Member cannot create project
        r = api("post", f"/api/workspaces/{slug}/projects", key=MEMBER_KEY,
                json={"name": "Member Proj", "identifier": "MEM"})
        assert r.status_code == 403

        # Admin creates state
        st = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1})
        assert st.status_code == 201
        state_id = st.json()["id"]

        # Member cannot create state
        r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states", key=MEMBER_KEY,
                json={"name": "MemState", "group": "started"})
        assert r.status_code == 403

        # Member can create issue
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues", key=MEMBER_KEY,
                  json={"name": "Member Issue", "stateId": state_id, "priority": "high"})
        assert iss.status_code == 201
        issue_id = iss.json()["id"]

        # Guest cannot create issue
        r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues", key=GUEST_KEY,
                json={"name": "Guest Issue", "stateId": state_id, "priority": "none"})
        assert r.status_code == 403

        # Member can create comment
        comment = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments",
                      key=MEMBER_KEY, json={"content": "Member comment"})
        assert comment.status_code == 201

        # Guest cannot create comment
        r = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments",
                key=GUEST_KEY, json={"content": "Guest comment"})
        assert r.status_code == 403

        # Member cannot delete workspace
        r = api("delete", f"/api/workspaces/{slug}", key=MEMBER_KEY)
        assert r.status_code == 403


class TestCommentReactionWorkflow:
    """
    Comments and reactions: create issue → add comments → add reactions →
    verify all data → delete reaction → verify removed.
    Patterns: 4 (status codes), 1 (camelCase fields), 2 (nested data)
    """

    def test_comment_reaction_lifecycle(self):
        slug = f"wf-cmt-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Comment WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Comment Project", "identifier": "CMT"}).json()
        proj_id = proj["id"]
        st = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()

        # Create issue
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": "Comment Test", "stateId": st["id"], "priority": "none"}).json()
        issue_id = iss["id"]

        # Create comments
        c1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments",
                 key=MEMBER_KEY, json={"content": "First comment"})
        assert c1.status_code == 201
        assert c1.json()["content"] == "First comment"
        assert "actorId" in c1.json()
        assert "issueId" in c1.json()
        comment_id = c1.json()["id"]

        c2 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments",
                 key=MEMBER_KEY, json={"content": "Second comment"})
        assert c2.status_code == 201

        # List comments
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments",
                key=MEMBER_KEY)
        assert r.status_code == 200
        assert len(r.json()) >= 2

        # Add reactions
        rx1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments/{comment_id}/reactions",
                  key=MEMBER_KEY, json={"emoji": "thumbsup"})
        assert rx1.status_code == 201
        assert rx1.json()["emoji"] == "thumbsup"
        assert "commentId" in rx1.json()
        assert "actorId" in rx1.json()
        reaction_id = rx1.json()["id"]

        # Delete reaction
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments/{comment_id}/reactions/{reaction_id}",
                key=MEMBER_KEY)
        assert r.status_code == 204

        # Verify reaction gone (re-delete should 404)
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments/{comment_id}/reactions/{reaction_id}",
                key=MEMBER_KEY)
        assert r.status_code == 404

        # Update comment
        r = api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments/{comment_id}",
                key=MEMBER_KEY, json={"content": "Updated first"})
        assert r.status_code == 200
        assert r.json()["content"] == "Updated first"

        # Delete comment
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{issue_id}/comments/{comment_id}",
                key=MEMBER_KEY)
        assert r.status_code == 204


class TestIssueSubIssueWorkflow:
    """
    Sub-issues: create parent → create children → verify parentId → delete parent.
    Patterns: 2 (parentId relation), 7 (cascade), 5 (identifier sequencing)
    """

    def test_sub_issue_hierarchy(self):
        slug = f"wf-sub-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "SubIssue WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Sub Project", "identifier": "SUB"}).json()
        proj_id = proj["id"]
        st = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()

        # Create parent issue
        parent = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Epic: User Auth", "stateId": st["id"], "priority": "high"}).json()
        assert parent["identifier"] == "SUB-1"
        parent_id = parent["id"]

        # Create child issues
        child1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Login page", "stateId": st["id"], "priority": "medium",
                           "parentId": parent_id}).json()
        assert child1["identifier"] == "SUB-2"
        assert child1["parentId"] == parent_id

        child2 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                     key=MEMBER_KEY,
                     json={"name": "Register page", "stateId": st["id"], "priority": "medium",
                           "parentId": parent_id}).json()
        assert child2["identifier"] == "SUB-3"
        assert child2["parentId"] == parent_id

        # GET child confirms parentId
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{child1['id']}", key=MEMBER_KEY)
        assert r.json()["parentId"] == parent_id

        # GET parent - parentId should be null
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{parent_id}", key=MEMBER_KEY)
        assert r.json()["parentId"] is None

        # Delete parent
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{parent_id}", key=MEMBER_KEY)
        assert r.status_code == 204

        # Parent is gone
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{parent_id}", key=MEMBER_KEY)
        assert r.status_code == 404


class TestViewsAndFilteringWorkflow:
    """
    Views with filtering: create saved view → create matching/non-matching issues →
    apply filter params → verify only matching returned.
    Patterns: 3 (filtering actually works), 2 (filters stored correctly), 5 (logic)
    """

    def test_view_creation_and_issue_filtering(self):
        slug = f"wf-view-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "View WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "View Project", "identifier": "VEW"}).json()
        proj_id = proj["id"]

        st_open = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()
        st_done = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                      json={"name": "Done", "group": "completed", "color": "#0f0", "order": 2}).json()

        label_bug = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/labels",
                        json={"name": "bug", "color": "#f00"}).json()
        label_feat = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/labels",
                         json={"name": "feature", "color": "#0f0"}).json()

        # Create view with filters
        view = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/views",
                   key=MEMBER_KEY,
                   json={"name": "High Priority Bugs",
                         "filters": {"priority": "high", "labels": [label_bug["id"]]}})
        assert view.status_code == 201
        assert view.json()["filters"]["priority"] == "high"
        assert label_bug["id"] in view.json()["filters"]["labels"]

        # GET view preserves filters
        view_id = view.json()["id"]
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/views/{view_id}", key=MEMBER_KEY)
        assert r.json()["name"] == "High Priority Bugs"
        assert r.json()["filters"]["priority"] == "high"

        # Create issues
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": "High bug", "stateId": st_open["id"], "priority": "high",
                  "labels": [label_bug["id"]]})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": "Low bug", "stateId": st_open["id"], "priority": "low",
                  "labels": [label_bug["id"]]})
        api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
            key=MEMBER_KEY,
            json={"name": "High feature", "stateId": st_open["id"], "priority": "high",
                  "labels": [label_feat["id"]]})

        # Filter by priority=high
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"priority": "high"})
        assert r.status_code == 200
        high_issues = r.json()
        assert all(i["priority"] == "high" for i in high_issues)
        assert len(high_issues) >= 2

        # Filter by label=bug
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                key=MEMBER_KEY, params={"label": label_bug["id"]})
        assert r.status_code == 200
        bug_issues = r.json()
        assert all(label_bug["id"] in i["labels"] for i in bug_issues)
        assert len(bug_issues) >= 2


class TestProjectDeletionCascadeWorkflow:
    """
    Cascade on project deletion: create project with issues, states, labels →
    delete project → verify 404 on all resources.
    Patterns: 7 (cascade deletion), 4 (404 status codes)
    """

    def test_project_delete_cascades(self):
        slug = f"wf-cas-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Cascade WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Cascade Project", "identifier": "CAS"}).json()
        proj_id = proj["id"]

        st = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/states",
                 json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()
        label = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/labels",
                    json={"name": "test", "color": "#fff"}).json()
        iss = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/issues",
                  key=MEMBER_KEY,
                  json={"name": "Cascade Issue", "stateId": st["id"], "priority": "none"}).json()

        # Delete the project
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}")
        assert r.status_code == 204

        # Verify project is gone
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}")
        assert r.status_code == 404

        # Verify issues under the project are gone
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/issues/{iss['id']}", key=MEMBER_KEY)
        assert r.status_code == 404

        # Verify states under the project are gone
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/states/{st['id']}", key=MEMBER_KEY)
        assert r.status_code == 404


class TestUniqueConstraintsWorkflow:
    """
    Uniqueness: duplicate slugs, duplicate identifiers rejected.
    Patterns: 8 (uniqueness constraints), 4 (409 status codes)
    """

    def test_unique_constraints_enforced(self):
        slug = f"wf-uniq-{uuid.uuid4().hex[:8]}"
        ws = api("post", "/api/workspaces", json={"name": "Unique WF", "slug": slug})
        assert ws.status_code == 201

        # Duplicate workspace slug
        r = api("post", "/api/workspaces", json={"name": "Dup", "slug": slug})
        assert r.status_code == 409

        # Create project
        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Unique Project", "identifier": "UNQ"})
        assert proj.status_code == 201

        # Duplicate project identifier in same workspace
        r = api("post", f"/api/workspaces/{slug}/projects",
                json={"name": "Dup Project", "identifier": "UNQ"})
        assert r.status_code == 409

        # Different workspace can have same identifier
        slug2 = f"wf-uniq2-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Other WF", "slug": slug2})
        r = api("post", f"/api/workspaces/{slug2}/projects",
                json={"name": "Same ID", "identifier": "UNQ"})
        assert r.status_code == 201


class TestPageWikiWorkflow:
    """
    Wiki pages: create parent → create children → update → verify hierarchy.
    Patterns: 2 (parentId), 1 (camelCase), 4 (status codes)
    """

    def test_wiki_page_hierarchy(self):
        slug = f"wf-wiki-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Wiki WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        proj = api("post", f"/api/workspaces/{slug}/projects",
                   json={"name": "Wiki Project", "identifier": "WIK"}).json()
        proj_id = proj["id"]

        # Create root page
        root = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/pages",
                   key=MEMBER_KEY,
                   json={"title": "Documentation", "content": "# Docs\nWelcome."})
        assert root.status_code == 201
        assert root.json()["title"] == "Documentation"
        assert "projectId" in root.json()
        assert root.json()["parentId"] is None
        root_id = root.json()["id"]

        # Create child pages
        child1 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/pages",
                     key=MEMBER_KEY,
                     json={"title": "Getting Started", "content": "# Getting Started",
                           "parentId": root_id}).json()
        assert child1["parentId"] == root_id

        child2 = api("post", f"/api/workspaces/{slug}/projects/{proj_id}/pages",
                     key=MEMBER_KEY,
                     json={"title": "API Reference", "content": "# API",
                           "parentId": root_id}).json()
        assert child2["parentId"] == root_id

        # Update child content
        r = api("patch", f"/api/workspaces/{slug}/projects/{proj_id}/pages/{child1['id']}",
                key=MEMBER_KEY, json={"content": "# Getting Started\nUpdated content."})
        assert r.status_code == 200
        assert "Updated content" in r.json()["content"]
        assert r.json()["parentId"] == root_id  # parentId preserved after update

        # List pages
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/pages", key=MEMBER_KEY)
        assert r.status_code == 200
        titles = [p["title"] for p in r.json()]
        assert "Documentation" in titles
        assert "Getting Started" in titles
        assert "API Reference" in titles

        # Delete child
        r = api("delete", f"/api/workspaces/{slug}/projects/{proj_id}/pages/{child2['id']}", key=MEMBER_KEY)
        assert r.status_code == 204

        # Verify deleted
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_id}/pages/{child2['id']}", key=MEMBER_KEY)
        assert r.status_code == 404


class TestMultiProjectIsolationWorkflow:
    """
    Issue identifiers are project-scoped, not global.
    Patterns: 5 (identifier logic), 6 (project isolation)
    """

    def test_identifiers_scoped_per_project(self):
        slug = f"wf-multi-{uuid.uuid4().hex[:8]}"
        api("post", "/api/workspaces", json={"name": "Multi WF", "slug": slug})

        member_uid = _get_user_id(MEMBER_KEY)
        api("post", f"/api/workspaces/{slug}/members", json={"userId": member_uid, "role": "member"})

        # Create two projects
        proj_a = api("post", f"/api/workspaces/{slug}/projects",
                     json={"name": "Project A", "identifier": "AAA"}).json()
        proj_b = api("post", f"/api/workspaces/{slug}/projects",
                     json={"name": "Project B", "identifier": "BBB"}).json()

        st_a = api("post", f"/api/workspaces/{slug}/projects/{proj_a['id']}/states",
                   json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()
        st_b = api("post", f"/api/workspaces/{slug}/projects/{proj_b['id']}/states",
                   json={"name": "Open", "group": "unstarted", "color": "#000", "order": 1}).json()

        # Create issues in both projects
        iss_a1 = api("post", f"/api/workspaces/{slug}/projects/{proj_a['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "A Issue 1", "stateId": st_a["id"], "priority": "none"}).json()
        iss_a2 = api("post", f"/api/workspaces/{slug}/projects/{proj_a['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "A Issue 2", "stateId": st_a["id"], "priority": "none"}).json()

        iss_b1 = api("post", f"/api/workspaces/{slug}/projects/{proj_b['id']}/issues",
                     key=MEMBER_KEY,
                     json={"name": "B Issue 1", "stateId": st_b["id"], "priority": "none"}).json()

        # Project A identifiers: AAA-1, AAA-2
        assert iss_a1["identifier"] == "AAA-1"
        assert iss_a2["identifier"] == "AAA-2"

        # Project B identifiers: BBB-1 (independent sequence)
        assert iss_b1["identifier"] == "BBB-1"

        # Issues from project A don't show in project B listing
        r = api("get", f"/api/workspaces/{slug}/projects/{proj_b['id']}/issues", key=MEMBER_KEY)
        issue_ids = [i["id"] for i in r.json()]
        assert iss_a1["id"] not in issue_ids
        assert iss_a2["id"] not in issue_ids
        assert iss_b1["id"] in issue_ids
