"""
BackendForge — L3 Workflow Tests for Focalboard
Multi-step, multi-entity adversarial tests targeting complex LLM implementation bugs.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _unique(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


USER1_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())
USER4_ID = str(uuid.uuid4())

H1 = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
H2 = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
H3 = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}
H4 = {"X-User-Id": USER4_ID, "Content-Type": "application/json"}


def post(path, json=None, headers=None):
    request_headers = H1 if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def get(path, params=None, headers=None):
    request_headers = H1 if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def put(path, json=None, headers=None):
    request_headers = H1 if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def delete(path, headers=None):
    request_headers = H1 if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


# ═══════════════════════════════════════════════════════════
# L3 Tests — Workflows (10-15 tests)
# ═══════════════════════════════════════════════════════════


class TestBoardLifecycleWorkflow:
    """Full board lifecycle: create → populate → share → restrict → delete cascade."""

    def test_full_board_lifecycle_with_cascade_delete(self):
        """Pattern 2+4+7: Create board with cards/views/comments/blocks → delete board → all gone."""
        # 1. Create board
        r = post("/boards", {"title": _unique("lifecycle-"), "type": "board"})
        assert r.status_code == 201
        board_id = r.json()["id"]
        assert r.json()["createdBy"] == USER1_ID

        # 2. Add properties
        r = post(f"/boards/{board_id}/properties", {"name": "Status", "type": "text"})
        assert r.status_code == 201
        prop_id = r.json()["id"]

        # 3. Create cards with properties
        r = post(f"/boards/{board_id}/cards", {"title": "Card1", "properties": {prop_id: "active"}})
        assert r.status_code == 201
        card1_id = r.json()["id"]
        assert r.json()["boardId"] == board_id

        r = post(f"/boards/{board_id}/cards", {"title": "Card2", "properties": {prop_id: "done"}})
        card2_id = r.json()["id"]

        # 4. Add comments to card1
        r = post(f"/boards/{board_id}/cards/{card1_id}/comments", {"text": "comment on card1"})
        assert r.status_code == 201
        assert r.json()["cardId"] == card1_id

        # 5. Add blocks to card1
        r = post(f"/boards/{board_id}/cards/{card1_id}/blocks", {"type": "text", "content": "block1"})
        assert r.status_code == 201
        assert r.json()["cardId"] == card1_id

        # 6. Create view
        r = post(f"/boards/{board_id}/views", {"name": "MainView", "type": "board"})
        assert r.status_code == 201
        assert r.json()["boardId"] == board_id

        # 7. Add member
        r = post(f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"})
        assert r.status_code == 201
        assert r.json()["boardId"] == board_id

        # 8. Verify board has everything
        r = get(f"/boards/{board_id}")
        assert r.status_code == 200
        assert len(r.json()["properties"]) == 1

        r = get(f"/boards/{board_id}/cards")
        assert len(r.json()) == 2

        r = get(f"/boards/{board_id}/views")
        assert len(r.json()) == 1

        # 9. DELETE board → cascade
        r = delete(f"/boards/{board_id}")
        assert r.status_code == 204

        # 10. Verify EVERYTHING is gone
        assert get(f"/boards/{board_id}").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card1_id}").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card2_id}").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card1_id}/comments").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card1_id}/blocks").status_code == 404
        assert get(f"/boards/{board_id}/views").status_code == 404

        # 11. User2 also lost access
        assert get(f"/boards/{board_id}", headers=H2).status_code == 404

    def test_card_delete_cascades_comments_and_blocks(self):
        """Pattern 7: Deleting card removes its comments and blocks, but not other cards."""
        r = post("/boards", {"title": _unique("card-cascade-"), "type": "board"})
        board_id = r.json()["id"]

        # Create 2 cards
        r = post(f"/boards/{board_id}/cards", {"title": "KeepCard"})
        keep_card_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards", {"title": "DeleteCard"})
        del_card_id = r.json()["id"]

        # Add comments and blocks to BOTH
        r = post(f"/boards/{board_id}/cards/{keep_card_id}/comments", {"text": "keep cmt"})
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/cards/{del_card_id}/comments", {"text": "del cmt"})
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/cards/{keep_card_id}/blocks", {"type": "text", "content": "keep blk"})
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/cards/{del_card_id}/blocks", {"type": "text", "content": "del blk"})
        assert r.status_code == 201

        # Delete the second card
        r = delete(f"/boards/{board_id}/cards/{del_card_id}")
        assert r.status_code == 204

        # First card and its data still exist
        r = get(f"/boards/{board_id}/cards/{keep_card_id}")
        assert r.status_code == 200
        r = get(f"/boards/{board_id}/cards/{keep_card_id}/comments")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["text"] == "keep cmt"
        r = get(f"/boards/{board_id}/cards/{keep_card_id}/blocks")
        assert r.status_code == 200
        assert len(r.json()) == 1

        # Deleted card's endpoints return 404
        assert get(f"/boards/{board_id}/cards/{del_card_id}").status_code == 404
        assert get(f"/boards/{board_id}/cards/{del_card_id}/comments").status_code == 404
        assert get(f"/boards/{board_id}/cards/{del_card_id}/blocks").status_code == 404


class TestRoleBasedAccessWorkflow:
    """Multi-user workflow testing all role permissions."""

    def test_role_hierarchy_permissions(self):
        """Pattern 6: Admin > Editor > Commenter > Viewer permission hierarchy."""
        # 1. User1 creates board (becomes admin)
        r = post("/boards", {"title": _unique("roles-"), "type": "board"})
        assert r.status_code == 201
        board_id = r.json()["id"]

        # 2. Add users with different roles
        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/members", {"userId": USER3_ID, "role": "commenter"}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/members", {"userId": USER4_ID, "role": "viewer"}
        ).status_code == 201

        # 3. Create a card (by admin)
        r = post(f"/boards/{board_id}/cards", {"title": "TestCard"})
        card_id = r.json()["id"]

        # 4. EDITOR can create cards, views, blocks, comments
        r = post(f"/boards/{board_id}/cards", {"title": "EditorCard"}, headers=H2)
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/views", {"name": "EditorView", "type": "board"}, headers=H2)
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text", "content": "e"}, headers=H2)
        assert r.status_code == 201
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "editor cmt"}, headers=H2)
        assert r.status_code == 201

        # 5. EDITOR cannot update board or manage members
        r = put(f"/boards/{board_id}", {"title": "Hacked"}, headers=H2)
        assert r.status_code == 403
        r = post(f"/boards/{board_id}/members", {"userId": str(uuid.uuid4()), "role": "viewer"}, headers=H2)
        assert r.status_code == 403

        # 6. COMMENTER can create/update own comments, but NOT cards/views/blocks
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "commenter says"}, headers=H3)
        assert r.status_code == 201
        cmt_id = r.json()["id"]
        r = put(f"/boards/{board_id}/cards/{card_id}/comments/{cmt_id}", {"text": "edited"}, headers=H3)
        assert r.status_code == 200

        r = post(f"/boards/{board_id}/cards", {"title": "Illegal"}, headers=H3)
        assert r.status_code == 403
        r = post(f"/boards/{board_id}/views", {"name": "Illegal", "type": "board"}, headers=H3)
        assert r.status_code == 403
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text"}, headers=H3)
        assert r.status_code == 403

        # 7. VIEWER can only read
        r = get(f"/boards/{board_id}", headers=H4)
        assert r.status_code == 200
        r = get(f"/boards/{board_id}/cards", headers=H4)
        assert r.status_code == 200
        r = get(f"/boards/{board_id}/views", headers=H4)
        assert r.status_code == 200

        r = post(f"/boards/{board_id}/cards", {"title": "Illegal"}, headers=H4)
        assert r.status_code == 403
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "nope"}, headers=H4)
        assert r.status_code == 403

    def test_member_removal_revokes_access(self):
        """Pattern 6+7: Removing member immediately revokes all access."""
        r = post("/boards", {"title": _unique("revoke-"), "type": "board"})
        board_id = r.json()["id"]

        # Add and verify access
        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201
        r = get(f"/boards/{board_id}", headers=H2)
        assert r.status_code == 200

        # Create a card as editor
        r = post(f"/boards/{board_id}/cards", {"title": "EditorCard"}, headers=H2)
        assert r.status_code == 201

        # Remove membership
        r = delete(f"/boards/{board_id}/members/{USER2_ID}")
        assert r.status_code == 204

        # Access revoked
        r = get(f"/boards/{board_id}", headers=H2)
        assert r.status_code == 404
        r = get("/boards", headers=H2)
        board_ids = [b["id"] for b in r.json()]
        assert board_id not in board_ids


class TestPropertyWorkflow:
    """Property lifecycle and card interaction workflow."""

    def test_property_crud_with_card_interaction(self):
        """Pattern 5+7: Full property lifecycle affecting cards."""
        # 1. Create board
        r = post("/boards", {"title": _unique("prop-flow-"), "type": "board"})
        board_id = r.json()["id"]

        # 2. Add select property with options
        opt_todo = str(uuid.uuid4())
        opt_doing = str(uuid.uuid4())
        opt_done = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Status",
            "type": "select",
            "options": [
                {"id": opt_todo, "value": "Todo"},
                {"id": opt_doing, "value": "Doing"},
                {"id": opt_done, "value": "Done"},
            ],
        })
        assert r.status_code == 201
        status_prop = r.json()["id"]
        assert r.json()["name"] == "Status"
        assert len(r.json()["options"]) == 3

        # 3. Add text property
        r = post(f"/boards/{board_id}/properties", {"name": "Assignee", "type": "text"})
        assignee_prop = r.json()["id"]

        # 4. Create cards with properties
        r = post(f"/boards/{board_id}/cards", {
            "title": "Task A",
            "properties": {status_prop: opt_todo, assignee_prop: "Alice"},
        })
        assert r.status_code == 201
        card_a = r.json()["id"]
        assert r.json()["properties"][status_prop] == opt_todo
        assert r.json()["properties"][assignee_prop] == "Alice"

        r = post(f"/boards/{board_id}/cards", {
            "title": "Task B",
            "properties": {status_prop: opt_done, assignee_prop: "Bob"},
        })
        card_b = r.json()["id"]

        # 5. Filter by status=Done
        r = get(f"/boards/{board_id}/cards", params={"filter_property": status_prop, "filter_value": opt_done})
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["title"] == "Task B"

        # 6. Update card A's status
        r = put(f"/boards/{board_id}/cards/{card_a}", {"properties": {status_prop: opt_doing, assignee_prop: "Alice"}})
        assert r.status_code == 200
        assert r.json()["properties"][status_prop] == opt_doing

        # 7. Filter for Todo should now be empty
        r = get(f"/boards/{board_id}/cards", params={"filter_property": status_prop, "filter_value": opt_todo})
        assert len(r.json()) == 0

        # 8. Delete the Assignee property
        r = delete(f"/boards/{board_id}/properties/{assignee_prop}")
        assert r.status_code == 204

        # 9. Verify cards no longer have Assignee, but still have Status
        r = get(f"/boards/{board_id}/cards/{card_a}")
        assert assignee_prop not in r.json()["properties"]
        assert r.json()["properties"][status_prop] == opt_doing

        r = get(f"/boards/{board_id}/cards/{card_b}")
        assert assignee_prop not in r.json()["properties"]
        assert r.json()["properties"][status_prop] == opt_done

        # 10. Board properties list updated
        r = get(f"/boards/{board_id}")
        prop_names = [p["name"] for p in r.json()["properties"]]
        assert "Assignee" not in prop_names
        assert "Status" in prop_names


class TestTemplateWorkflow:
    """Template creation and board instantiation workflow."""

    def test_template_to_board_deep_copy_workflow(self):
        """Pattern 2+5: Template → Board copies properties/views with new IDs."""
        # 1. Create template
        r = post("/templates", {"title": _unique("sprint-tmpl-"), "type": "board", "description": "Sprint board"})
        assert r.status_code == 201
        tmpl_id = r.json()["id"]
        assert r.json()["createdBy"] == USER1_ID
        assert r.json()["description"] == "Sprint board"

        # 2. Add properties to template
        opt_a = str(uuid.uuid4())
        opt_b = str(uuid.uuid4())
        opt_c = str(uuid.uuid4())
        r = post(f"/templates/{tmpl_id}/properties", {
            "name": "Priority",
            "type": "select",
            "options": [
                {"id": opt_a, "value": "High", "color": "red"},
                {"id": opt_b, "value": "Medium", "color": "yellow"},
                {"id": opt_c, "value": "Low", "color": "green"},
            ],
        })
        assert r.status_code == 201
        tmpl_priority_prop = r.json()["id"]

        r = post(f"/templates/{tmpl_id}/properties", {"name": "Estimate", "type": "number"})
        tmpl_estimate_prop = r.json()["id"]

        # 3. Add views to template
        r = post(f"/templates/{tmpl_id}/views", {
            "name": "Board View",
            "type": "board",
            "groupBy": tmpl_priority_prop,
            "visibleProperties": [tmpl_priority_prop, tmpl_estimate_prop],
        })
        assert r.status_code == 201
        tmpl_view_id = r.json()["id"]

        r = post(f"/templates/{tmpl_id}/views", {
            "name": "Table View",
            "type": "table",
            "sort": [{"propertyId": tmpl_estimate_prop, "direction": "desc"}],
        })
        assert r.status_code == 201

        # 4. Create board from template with custom title
        custom_title = _unique("my-sprint-")
        r = post(f"/templates/{tmpl_id}/create-board", {"title": custom_title})
        assert r.status_code == 201
        board = r.json()
        board_id = board["id"]

        # 5. Verify board metadata
        assert board["title"] == custom_title
        assert board["type"] == "board"
        assert board["createdBy"] == USER1_ID

        # 6. Verify properties copied with NEW IDs
        assert len(board["properties"]) == 2
        board_props = {p["name"]: p for p in board["properties"]}
        assert "Priority" in board_props
        assert "Estimate" in board_props
        assert board_props["Priority"]["id"] != tmpl_priority_prop
        assert board_props["Estimate"]["id"] != tmpl_estimate_prop
        assert board_props["Priority"]["type"] == "select"
        assert len(board_props["Priority"]["options"]) == 3

        # 7. Verify views copied
        r = get(f"/boards/{board_id}/views")
        views = r.json()
        assert len(views) == 2
        view_names = {v["name"] for v in views}
        assert "Board View" in view_names
        assert "Table View" in view_names

        # 8. Views have NEW IDs
        for v in views:
            assert v["id"] != tmpl_view_id

        # 9. Board is independent — create cards on it
        new_priority_prop = board_props["Priority"]["id"]
        new_opt = board_props["Priority"]["options"][0]["id"]
        r = post(f"/boards/{board_id}/cards", {
            "title": "Sprint task",
            "properties": {new_priority_prop: new_opt},
        })
        assert r.status_code == 201

        # 10. Template still exists and is unchanged
        r = get(f"/templates/{tmpl_id}")
        assert r.status_code == 200
        assert len(r.json()["properties"]) == 2

    def test_template_default_title_and_user_isolation(self):
        """Pattern 5+6: No title override uses template title; other users can't see template."""
        tmpl_title = _unique("tmpl-default-")
        r = post("/templates", {"title": tmpl_title, "type": "calendar"})
        tmpl_id = r.json()["id"]

        # Create board without title override
        r = post(f"/templates/{tmpl_id}/create-board", {})
        assert r.status_code == 201
        assert r.json()["title"] == tmpl_title

        # User2 cannot access template
        r = get(f"/templates/{tmpl_id}", headers=H2)
        assert r.status_code == 404

        # User2 cannot create board from User1's template
        r = post(f"/templates/{tmpl_id}/create-board", {"title": "Stolen"}, headers=H2)
        assert r.status_code == 404


class TestMultiUserCollaborationWorkflow:
    """Multi-user scenario with shared board."""

    def test_collaborative_board_workflow(self):
        """Pattern 6+7: Multiple users collaborate on a shared board."""
        # 1. Admin creates board
        r = post("/boards", {"title": _unique("collab-"), "type": "board"})
        board_id = r.json()["id"]

        # 2. Add property
        r = post(f"/boards/{board_id}/properties", {"name": "Owner", "type": "text"})
        owner_prop = r.json()["id"]

        # 3. Add members
        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/members", {"userId": USER3_ID, "role": "commenter"}
        ).status_code == 201

        # 4. Editor creates a card
        r = post(f"/boards/{board_id}/cards", {
            "title": "Editor's Task",
            "properties": {owner_prop: "User2"},
        }, headers=H2)
        assert r.status_code == 201
        card_id = r.json()["id"]
        assert r.json()["createdBy"] == USER2_ID

        # 5. Admin creates a card
        r = post(f"/boards/{board_id}/cards", {
            "title": "Admin's Task",
            "properties": {owner_prop: "User1"},
        })
        admin_card_id = r.json()["id"]

        # 6. Commenter can read cards
        r = get(f"/boards/{board_id}/cards", headers=H3)
        assert r.status_code == 200
        assert len(r.json()) == 2

        # 7. Commenter adds comment to editor's card
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Nice work!"}, headers=H3)
        assert r.status_code == 201
        cmt_id = r.json()["id"]
        assert r.json()["createdBy"] == USER3_ID

        # 8. Commenter cannot edit editor's comment
        # First, editor adds their own comment
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "My note"}, headers=H2)
        editor_cmt_id = r.json()["id"]
        r = put(f"/boards/{board_id}/cards/{card_id}/comments/{editor_cmt_id}", {"text": "hacked"}, headers=H3)
        assert r.status_code == 403

        # 9. Commenter can edit their own comment
        r = put(f"/boards/{board_id}/cards/{card_id}/comments/{cmt_id}", {"text": "Great work!"}, headers=H3)
        assert r.status_code == 200
        assert r.json()["text"] == "Great work!"

        # 10. Filter cards by property
        r = get(f"/boards/{board_id}/cards", params={"filter_property": owner_prop, "filter_value": "User2"})
        assert len(r.json()) == 1
        assert r.json()[0]["title"] == "Editor's Task"

        # 11. Upgrade commenter to editor
        r = put(f"/boards/{board_id}/members/{USER3_ID}", {"role": "editor"})
        assert r.status_code == 200
        assert r.json()["role"] == "editor"

        # 12. Now User3 can create cards
        r = post(f"/boards/{board_id}/cards", {"title": "User3 Card"}, headers=H3)
        assert r.status_code == 201

    def test_outsider_isolation_throughout_workflow(self):
        """Pattern 6: Outsider cannot access anything throughout the workflow."""
        r = post("/boards", {"title": _unique("private-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards", {"title": "Private Card"})
        card_id = r.json()["id"]
        r = post(f"/boards/{board_id}/views", {"name": "Private View", "type": "board"})
        view_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Secret"})
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text", "content": "Hidden"})

        # User3 (outsider) cannot access ANY of these
        assert get(f"/boards/{board_id}", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/cards", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/cards/{card_id}", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/views", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/views/{view_id}", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/cards/{card_id}/comments", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/cards/{card_id}/blocks", headers=H3).status_code == 404
        assert get(f"/boards/{board_id}/members", headers=H3).status_code == 404

        # Outsider cannot create anything
        assert post(f"/boards/{board_id}/cards", {"title": "X"}, headers=H3).status_code in [403, 404]
        assert post(f"/boards/{board_id}/views", {"name": "X", "type": "board"}, headers=H3).status_code in [403, 404]


class TestComplexCardWorkflow:
    """Card with properties, blocks, comments — full lifecycle."""

    def test_card_full_lifecycle(self):
        """Pattern 2+7: Card with nested data → update → verify → delete cascade."""
        # 1. Setup board with properties
        r = post("/boards", {"title": _unique("card-life-"), "type": "board"})
        board_id = r.json()["id"]

        opt_open = str(uuid.uuid4())
        opt_closed = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Status",
            "type": "select",
            "options": [{"id": opt_open, "value": "Open"}, {"id": opt_closed, "value": "Closed"}],
        })
        status_prop = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Description", "type": "text"})
        desc_prop = r.json()["id"]

        # 2. Create card with properties
        r = post(f"/boards/{board_id}/cards", {
            "title": "Bug Fix",
            "content": "# Fix login\nSee details below",
            "order": 1.5,
            "properties": {status_prop: opt_open, desc_prop: "Login page broken"},
        })
        assert r.status_code == 201
        card_id = r.json()["id"]
        assert r.json()["order"] == 1.5
        assert r.json()["content"] == "# Fix login\nSee details below"

        # 3. Add multiple blocks
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text", "content": "Step 1", "order": 1.0})
        blk1_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "checkbox", "content": "Done?", "order": 2.0})
        blk2_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "image", "content": "screenshot.png", "order": 3.0})
        blk3_id = r.json()["id"]

        # 4. Verify blocks ordered
        r = get(f"/boards/{board_id}/cards/{card_id}/blocks")
        blocks = r.json()
        assert len(blocks) == 3
        assert blocks[0]["content"] == "Step 1"
        assert blocks[1]["content"] == "Done?"
        assert blocks[2]["content"] == "screenshot.png"
        assert blocks[0]["order"] < blocks[1]["order"] < blocks[2]["order"]

        # 5. Add comments
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Working on it"})
        cmt1_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Almost done"})
        cmt2_id = r.json()["id"]

        # 6. Update card status
        r = put(f"/boards/{board_id}/cards/{card_id}", {
            "properties": {status_prop: opt_closed, desc_prop: "Fixed!"},
        })
        assert r.status_code == 200
        assert r.json()["properties"][status_prop] == opt_closed
        assert r.json()["properties"][desc_prop] == "Fixed!"

        # 7. Verify full card state
        r = get(f"/boards/{board_id}/cards/{card_id}")
        card = r.json()
        assert card["title"] == "Bug Fix"
        assert card["properties"][status_prop] == opt_closed
        assert card["boardId"] == board_id

        # 8. Delete card
        r = delete(f"/boards/{board_id}/cards/{card_id}")
        assert r.status_code == 204

        # 9. Verify card and all nested data gone
        assert get(f"/boards/{board_id}/cards/{card_id}").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card_id}/comments").status_code == 404
        assert get(f"/boards/{board_id}/cards/{card_id}/blocks").status_code == 404

        # 10. Board still exists
        assert get(f"/boards/{board_id}").status_code == 200


class TestViewComplexWorkflow:
    """View with complex filter/sort configuration workflow."""

    def test_view_creation_with_full_config(self):
        """Pattern 2+3: View with filter + sort + groupBy + visibleProperties."""
        r = post("/boards", {"title": _unique("view-full-"), "type": "board"})
        board_id = r.json()["id"]

        # Create properties
        opt1 = str(uuid.uuid4())
        opt2 = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Status",
            "type": "select",
            "options": [{"id": opt1, "value": "Active"}, {"id": opt2, "value": "Archived"}],
        })
        status_prop = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "number"})
        priority_prop = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Notes", "type": "text"})
        notes_prop = r.json()["id"]

        # Create complex view
        r = post(f"/boards/{board_id}/views", {
            "name": "Active High Priority",
            "type": "board",
            "filter": {
                "operator": "and",
                "conditions": [
                    {"propertyId": status_prop, "operator": "equals", "value": opt1},
                ],
            },
            "sort": [
                {"propertyId": priority_prop, "direction": "desc"},
            ],
            "groupBy": status_prop,
            "visibleProperties": [status_prop, priority_prop, notes_prop],
        })
        assert r.status_code == 201
        view_id = r.json()["id"]
        view_data = r.json()

        # Verify all nested data
        assert view_data["name"] == "Active High Priority"
        assert view_data["type"] == "board"
        assert view_data["boardId"] == board_id
        assert view_data["filter"]["operator"] == "and"
        assert view_data["filter"]["conditions"][0]["propertyId"] == status_prop
        assert view_data["filter"]["conditions"][0]["operator"] == "equals"
        assert view_data["filter"]["conditions"][0]["value"] == opt1
        assert view_data["sort"][0]["propertyId"] == priority_prop
        assert view_data["sort"][0]["direction"] == "desc"
        assert view_data["groupBy"] == status_prop
        assert len(view_data["visibleProperties"]) == 3

        # Update view
        r = put(f"/boards/{board_id}/views/{view_id}", {
            "name": "Updated View",
            "filter": {
                "operator": "or",
                "conditions": [
                    {"propertyId": status_prop, "operator": "equals", "value": opt1},
                    {"propertyId": status_prop, "operator": "equals", "value": opt2},
                ],
            },
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Updated View"
        assert r.json()["filter"]["operator"] == "or"
        assert len(r.json()["filter"]["conditions"]) == 2

        # GET view
        r = get(f"/boards/{board_id}/views/{view_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Updated View"
        assert r.json()["filter"]["operator"] == "or"


class TestBoardUpdateWorkflow:
    """Board update operations and permission checks."""

    def test_board_update_preserves_unmodified_fields(self):
        """Pattern 5: Updating one field doesn't reset others."""
        title = _unique("update-preserve-")
        r = post("/boards", {"title": title, "type": "gallery", "description": "keep this"})
        board_id = r.json()["id"]

        # Update only title
        new_title = _unique("updated-")
        r = put(f"/boards/{board_id}", {"title": new_title})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == new_title
        assert data["description"] == "keep this"  # preserved
        assert data["type"] == "gallery"  # preserved

        # Update only description
        r = put(f"/boards/{board_id}", {"description": "new desc"})
        assert r.status_code == 200
        assert r.json()["title"] == new_title  # preserved
        assert r.json()["description"] == "new desc"
        assert r.json()["type"] == "gallery"  # preserved

    def test_board_admin_member_can_update_and_delete(self):
        """Pattern 6: Admin member (not creator) can update/delete board."""
        # User1 creates, adds User2 as admin
        r = post("/boards", {"title": _unique("admin-mem-"), "type": "board"})
        board_id = r.json()["id"]

        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "admin"}
        ).status_code == 201

        # User2 (admin member) can update board
        r = put(f"/boards/{board_id}", {"title": "Admin Updated"}, headers=H2)
        assert r.status_code == 200
        assert r.json()["title"] == "Admin Updated"

        # User2 can manage members
        r = post(f"/boards/{board_id}/members", {"userId": USER3_ID, "role": "viewer"}, headers=H2)
        assert r.status_code == 201

        # User2 can delete board
        r = delete(f"/boards/{board_id}", headers=H2)
        assert r.status_code == 204


class TestFilterAndSortWorkflow:
    """Comprehensive filtering and sorting verification."""

    def test_filter_with_select_options_and_sort_combined(self):
        """Pattern 3+5: filter and sort together work correctly."""
        r = post("/boards", {"title": _unique("filter-sort-"), "type": "board"})
        board_id = r.json()["id"]

        # Create select property
        opt_frontend = str(uuid.uuid4())
        opt_backend = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Team",
            "type": "select",
            "options": [
                {"id": opt_frontend, "value": "Frontend"},
                {"id": opt_backend, "value": "Backend"},
            ],
        })
        team_prop = r.json()["id"]

        # Create number property for sorting
        r = post(f"/boards/{board_id}/properties", {"name": "Points", "type": "number"})
        points_prop = r.json()["id"]

        # Create multiple cards
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "FE-Low", "properties": {team_prop: opt_frontend, points_prop: "2"}},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "FE-High", "properties": {team_prop: opt_frontend, points_prop: "8"}},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "FE-Mid", "properties": {team_prop: opt_frontend, points_prop: "5"}},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "BE-Task", "properties": {team_prop: opt_backend, points_prop: "3"}},
        ).status_code == 201

        # Filter for frontend only
        r = get(f"/boards/{board_id}/cards", params={"filter_property": team_prop, "filter_value": opt_frontend})
        cards = r.json()
        assert len(cards) == 3
        assert all(c["properties"][team_prop] == opt_frontend for c in cards)

        # Sort by points
        r = get(f"/boards/{board_id}/cards", params={"sort_by": points_prop})
        cards = r.json()
        assert len(cards) == 4
        titles = [c["title"] for c in cards]
        assert titles == ["FE-Low", "BE-Task", "FE-Mid", "FE-High"]

    def test_filter_with_no_matches_returns_empty(self):
        """Pattern 3: Filter that matches nothing returns empty array (not error)."""
        r = post("/boards", {"title": _unique("empty-filter-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Tag", "type": "text"})
        prop_id = r.json()["id"]

        assert post(
            f"/boards/{board_id}/cards", {"title": "Card1", "properties": {prop_id: "alpha"}}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards", {"title": "Card2", "properties": {prop_id: "beta"}}
        ).status_code == 201

        # Filter for non-existent value
        r = get(f"/boards/{board_id}/cards", params={"filter_property": prop_id, "filter_value": "gamma"})
        assert r.status_code == 200
        assert r.json() == []
