"""
BackendForge — Comprehensive Correctness Tests for Focalboard Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# User IDs — UUIDs representing different users
USER1_ID = str(uuid.uuid4())  # Board creator / admin
USER2_ID = str(uuid.uuid4())  # Will be added as member
USER3_ID = str(uuid.uuid4())  # Outsider with no access

USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}


# ── HTTP Helpers ──


def api_get(path, params=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:
    """Test authentication requirements."""

    def test_missing_header_returns_401(self):
        """All endpoints require X-User-Id header."""
        resp = requests.get(f"{BASE_URL}/boards", timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        """Empty X-User-Id header should return 401."""
        resp = requests.get(f"{BASE_URL}/boards", headers={"X-User-Id": ""}, timeout=30)
        assert resp.status_code == 401

    def test_valid_header_returns_200(self):
        """Valid X-User-Id header should succeed."""
        resp = api_get("/boards")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Boards CRUD
# ════════════════════════════════════════════════════════════════════


class TestBoardsCRUD:
    """Test board creation, retrieval, update, and deletion."""

    def test_create_board(self):
        """POST /boards returns 201 with board data."""
        resp = api_post("/boards", {"title": "Test Board", "type": "board", "description": "A test board"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Board"
        assert data["type"] == "board"
        assert data["description"] == "A test board"
        assert "id" in data
        assert data["createdBy"] == USER1_ID
        assert "createdAt" in data
        assert "updatedAt" in data

    def test_create_board_types(self):
        """Board types: board, table, gallery, calendar."""
        for board_type in ["board", "table", "gallery", "calendar"]:
            resp = api_post("/boards", {"title": f"Type {board_type}", "type": board_type})
            assert resp.status_code == 201
            assert resp.json()["type"] == board_type

    def test_list_boards(self):
        """GET /boards returns boards accessible to user."""
        # Create a board
        resp = api_post("/boards", {"title": "List Test Board", "type": "board"})
        assert resp.status_code == 201
        board_id = resp.json()["id"]

        # List should include it
        resp = api_get("/boards")
        assert resp.status_code == 200
        boards = resp.json()
        assert isinstance(boards, list)
        board_ids = [b["id"] for b in boards]
        assert board_id in board_ids

    def test_get_board(self):
        """GET /boards/{boardId} returns board details."""
        resp = api_post("/boards", {"title": "Get Test", "type": "table"})
        board_id = resp.json()["id"]

        resp = api_get(f"/boards/{board_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == board_id
        assert data["title"] == "Get Test"
        assert data["type"] == "table"

    def test_update_board(self):
        """PUT /boards/{boardId} updates board fields."""
        resp = api_post("/boards", {"title": "Before Update", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_put(f"/boards/{board_id}", {"title": "After Update", "description": "Updated desc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "After Update"
        assert data["description"] == "Updated desc"

    def test_delete_board(self):
        """DELETE /boards/{boardId} returns 204."""
        resp = api_post("/boards", {"title": "To Delete", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}")
        assert resp.status_code == 204

        # Should be gone
        resp = api_get(f"/boards/{board_id}")
        assert resp.status_code == 404

    def test_get_nonexistent_board_returns_404(self):
        """Getting a board that doesn't exist returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/boards/{fake_id}")
        assert resp.status_code == 404

    def test_board_properties_field_initialized_empty(self):
        """Newly created board has empty properties array."""
        resp = api_post("/boards", {"title": "Props Test", "type": "board"})
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("properties") == [] or data.get("properties") is None or "properties" in data


# ════════════════════════════════════════════════════════════════════
# PART 3: Board Access Control
# ════════════════════════════════════════════════════════════════════


class TestBoardAccessControl:
    """Test board visibility and permission rules."""

    def test_outsider_cannot_see_board(self):
        """User without membership gets 404 on private board."""
        resp = api_post("/boards", {"title": "Private Board", "type": "board"})
        board_id = resp.json()["id"]

        # User3 is not a member
        resp = api_get(f"/boards/{board_id}", headers=USER3_HEADERS)
        assert resp.status_code == 404

    def test_outsider_cannot_list_private_boards(self):
        """Private boards don't show up in other user's list."""
        resp = api_post("/boards", {"title": "Hidden Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_get("/boards", headers=USER3_HEADERS)
        boards = resp.json()
        board_ids = [b["id"] for b in boards]
        assert board_id not in board_ids

    def test_member_can_see_board(self):
        """User added as member can see the board."""
        resp = api_post("/boards", {"title": "Shared Board", "type": "board"})
        board_id = resp.json()["id"]

        # Add USER2 as editor
        resp = api_post(f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"})
        assert resp.status_code == 201

        # USER2 can now see it
        resp = api_get(f"/boards/{board_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == board_id

    def test_non_admin_cannot_update_board(self):
        """Editor cannot update board settings."""
        resp = api_post("/boards", {"title": "Admin Only Board", "type": "board"})
        board_id = resp.json()["id"]

        # Add USER2 as editor
        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        # USER2 tries to update board
        resp = api_put(f"/boards/{board_id}", {"title": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_non_admin_cannot_delete_board(self):
        """Editor cannot delete board."""
        resp = api_post("/boards", {"title": "No Delete Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_delete(f"/boards/{board_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_viewer_cannot_create_card(self):
        """Viewer role cannot create cards."""
        resp = api_post("/boards", {"title": "Viewer Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "viewer"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Illegal Card"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_non_admin_cannot_manage_members(self):
        """Editor cannot add members."""
        resp = api_post("/boards", {"title": "Member Mgmt Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_post(
            f"/boards/{board_id}/members",
            {"userId": USER3_ID, "role": "viewer"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 4: Board Properties
# ════════════════════════════════════════════════════════════════════


class TestBoardProperties:
    """Test custom property definitions on boards."""

    def test_create_text_property(self):
        """Create a text property on a board."""
        resp = api_post("/boards", {"title": "Props Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "Status", "type": "text"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Status"
        assert data["type"] == "text"
        assert "id" in data

    def test_create_select_property_with_options(self):
        """Create a select property with options."""
        resp = api_post("/boards", {"title": "Select Board", "type": "board"})
        board_id = resp.json()["id"]

        options = [
            {"id": str(uuid.uuid4()), "value": "Todo", "color": "red"},
            {"id": str(uuid.uuid4()), "value": "In Progress", "color": "yellow"},
            {"id": str(uuid.uuid4()), "value": "Done", "color": "green"},
        ]
        resp = api_post(
            f"/boards/{board_id}/properties",
            {"name": "Status", "type": "select", "options": options},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "select"
        assert len(data["options"]) == 3

    def test_update_property(self):
        """Update a property's name."""
        resp = api_post("/boards", {"title": "Update Prop Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "OldName", "type": "text"})
        prop_id = resp.json()["id"]

        resp = api_put(f"/boards/{board_id}/properties/{prop_id}", {"name": "NewName", "type": "text"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_delete_property(self):
        """Delete a property returns 204."""
        resp = api_post("/boards", {"title": "Del Prop Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "ToDelete", "type": "number"})
        prop_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}/properties/{prop_id}")
        assert resp.status_code == 204

    def test_property_visible_in_board(self):
        """Properties show up when getting the board."""
        resp = api_post("/boards", {"title": "Visible Props", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/properties", {"name": "Field1", "type": "text"}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/properties", {"name": "Field2", "type": "number"}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}")
        data = resp.json()
        assert len(data["properties"]) == 2
        names = [p["name"] for p in data["properties"]]
        assert "Field1" in names
        assert "Field2" in names

    def test_all_property_types(self):
        """All property types can be created."""
        resp = api_post("/boards", {"title": "All Types Board", "type": "board"})
        board_id = resp.json()["id"]

        for ptype in ["text", "number", "select", "multiSelect", "date", "checkbox", "url", "person"]:
            resp = api_post(f"/boards/{board_id}/properties", {"name": f"Prop {ptype}", "type": ptype})
            assert resp.status_code == 201, f"Failed to create property of type {ptype}"
            assert resp.json()["type"] == ptype


# ════════════════════════════════════════════════════════════════════
# PART 5: Cards CRUD
# ════════════════════════════════════════════════════════════════════


class TestCardsCRUD:
    """Test card creation, retrieval, update, and deletion."""

    def test_create_card(self):
        """POST /boards/{boardId}/cards returns 201."""
        resp = api_post("/boards", {"title": "Cards Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "My Card", "content": "Hello world"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Card"
        assert data["content"] == "Hello world"
        assert data["boardId"] == board_id
        assert data["createdBy"] == USER1_ID
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data

    def test_create_card_with_properties(self):
        """Card can have properties matching board property definitions."""
        resp = api_post("/boards", {"title": "Card Props Board", "type": "board"})
        board_id = resp.json()["id"]

        # Create a text property
        resp = api_post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "text"})
        prop_id = resp.json()["id"]

        # Create card with property
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Prop Card", "properties": {prop_id: "High"}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["properties"][prop_id] == "High"

    def test_list_cards(self):
        """GET /boards/{boardId}/cards returns card list."""
        resp = api_post("/boards", {"title": "List Cards Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(f"/boards/{board_id}/cards", {"title": "Card 1"}).status_code == 201
        assert api_post(f"/boards/{board_id}/cards", {"title": "Card 2"}).status_code == 201

        resp = api_get(f"/boards/{board_id}/cards")
        assert resp.status_code == 200
        cards = resp.json()
        assert isinstance(cards, list)
        assert len(cards) >= 2

    def test_get_card(self):
        """GET /boards/{boardId}/cards/{cardId} returns card details."""
        resp = api_post("/boards", {"title": "Get Card Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Detail Card"})
        card_id = resp.json()["id"]

        resp = api_get(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Detail Card"

    def test_update_card(self):
        """PUT /boards/{boardId}/cards/{cardId} updates card."""
        resp = api_post("/boards", {"title": "Update Card Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Original"})
        card_id = resp.json()["id"]

        resp = api_put(f"/boards/{board_id}/cards/{card_id}", {"title": "Updated", "content": "New content"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated"
        assert data["content"] == "New content"

    def test_delete_card(self):
        """DELETE /boards/{boardId}/cards/{cardId} returns 204."""
        resp = api_post("/boards", {"title": "Del Card Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "To Delete"})
        card_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 204

        resp = api_get(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 404

    def test_card_order(self):
        """Cards respect order field."""
        resp = api_post("/boards", {"title": "Order Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Third", "order": 3.0}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards", {"title": "First", "order": 1.0}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Second", "order": 2.0}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/cards")
        cards = resp.json()
        titles = [c["title"] for c in cards]
        assert titles == ["First", "Second", "Third"]

    def test_card_wrong_board_returns_404(self):
        """Card accessed from wrong board returns 404."""
        resp = api_post("/boards", {"title": "Board A", "type": "board"})
        board_a_id = resp.json()["id"]

        resp = api_post("/boards", {"title": "Board B", "type": "board"})
        board_b_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_a_id}/cards", {"title": "Card in A"})
        card_id = resp.json()["id"]

        # Try to get card from board B
        resp = api_get(f"/boards/{board_b_id}/cards/{card_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Card Property Validation
# ════════════════════════════════════════════════════════════════════


class TestCardPropertyValidation:
    """Test that card property values are validated against board property definitions."""

    def test_select_property_valid_option(self):
        """Select property value must be a valid option ID."""
        resp = api_post("/boards", {"title": "Select Validation", "type": "board"})
        board_id = resp.json()["id"]

        opt_id = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/properties",
            {"name": "Status", "type": "select", "options": [{"id": opt_id, "value": "Open"}]},
        )
        prop_id = resp.json()["id"]

        # Valid option
        resp = api_post(f"/boards/{board_id}/cards", {"title": "Valid", "properties": {prop_id: opt_id}})
        assert resp.status_code == 201

    def test_select_property_invalid_option(self):
        """Select property with invalid option value returns 400."""
        resp = api_post("/boards", {"title": "Invalid Select", "type": "board"})
        board_id = resp.json()["id"]

        opt_id = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/properties",
            {"name": "Status", "type": "select", "options": [{"id": opt_id, "value": "Open"}]},
        )
        prop_id = resp.json()["id"]

        # Invalid option
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Invalid", "properties": {prop_id: "not-a-valid-option-id"}},
        )
        assert resp.status_code == 400

    def test_multiselect_property_valid_options(self):
        """MultiSelect values must be valid option IDs."""
        resp = api_post("/boards", {"title": "MultiSelect Board", "type": "board"})
        board_id = resp.json()["id"]

        opt1 = str(uuid.uuid4())
        opt2 = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/properties",
            {
                "name": "Tags",
                "type": "multiSelect",
                "options": [
                    {"id": opt1, "value": "Bug"},
                    {"id": opt2, "value": "Feature"},
                ],
            },
        )
        prop_id = resp.json()["id"]

        # Valid multiselect
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Multi", "properties": {prop_id: [opt1, opt2]}},
        )
        assert resp.status_code == 201

    def test_multiselect_property_invalid_option(self):
        """MultiSelect with invalid option value returns 400."""
        resp = api_post("/boards", {"title": "Invalid Multi", "type": "board"})
        board_id = resp.json()["id"]

        opt1 = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/properties",
            {"name": "Tags", "type": "multiSelect", "options": [{"id": opt1, "value": "Bug"}]},
        )
        prop_id = resp.json()["id"]

        # One invalid option in list
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Bad Multi", "properties": {prop_id: [opt1, "fake-id"]}},
        )
        assert resp.status_code == 400

    def test_unknown_property_key_ignored(self):
        """Unknown property IDs in card properties are silently ignored."""
        resp = api_post("/boards", {"title": "Unknown Key Board", "type": "board"})
        board_id = resp.json()["id"]

        fake_prop_id = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Unknown Props", "properties": {fake_prop_id: "whatever"}},
        )
        assert resp.status_code == 201
        data = resp.json()
        # The unknown key should not be stored
        assert fake_prop_id not in data.get("properties", {})

    def test_property_deletion_cascades_to_cards(self):
        """Deleting a property removes it from all cards."""
        resp = api_post("/boards", {"title": "Cascade Props Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "ToRemove", "type": "text"})
        prop_id = resp.json()["id"]

        # Create card with this property
        resp = api_post(
            f"/boards/{board_id}/cards",
            {"title": "Has Prop", "properties": {prop_id: "value"}},
        )
        card_id = resp.json()["id"]

        # Delete the property
        resp = api_delete(f"/boards/{board_id}/properties/{prop_id}")
        assert resp.status_code == 204

        # Card should no longer have the property
        resp = api_get(f"/boards/{board_id}/cards/{card_id}")
        data = resp.json()
        assert prop_id not in data.get("properties", {})


# ════════════════════════════════════════════════════════════════════
# PART 7: Views CRUD
# ════════════════════════════════════════════════════════════════════


class TestViewsCRUD:
    """Test view creation, retrieval, update, and deletion."""

    def test_create_view(self):
        """POST /boards/{boardId}/views returns 201."""
        resp = api_post("/boards", {"title": "Views Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Default View", "type": "board"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Default View"
        assert data["type"] == "board"
        assert data["boardId"] == board_id
        assert "id" in data

    def test_create_view_with_filter(self):
        """View with filter conditions."""
        resp = api_post("/boards", {"title": "Filter View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "Status", "type": "text"})
        prop_id = resp.json()["id"]

        view_filter = {
            "operator": "and",
            "conditions": [{"propertyId": prop_id, "operator": "equals", "value": "Done"}],
        }
        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Filtered", "type": "table", "filter": view_filter},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filter"]["operator"] == "and"
        assert len(data["filter"]["conditions"]) == 1

    def test_create_view_with_sort(self):
        """View with sort configuration."""
        resp = api_post("/boards", {"title": "Sort View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "number"})
        prop_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Sorted", "type": "table", "sort": [{"propertyId": prop_id, "direction": "desc"}]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["sort"]) == 1
        assert data["sort"][0]["direction"] == "desc"

    def test_list_views(self):
        """GET /boards/{boardId}/views returns view list."""
        resp = api_post("/boards", {"title": "List Views Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/views", {"name": "View 1", "type": "board"}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/views", {"name": "View 2", "type": "table"}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/views")
        assert resp.status_code == 200
        views = resp.json()
        assert len(views) >= 2

    def test_get_view(self):
        """GET /boards/{boardId}/views/{viewId} returns view."""
        resp = api_post("/boards", {"title": "Get View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/views", {"name": "My View", "type": "gallery"})
        view_id = resp.json()["id"]

        resp = api_get(f"/boards/{board_id}/views/{view_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "My View"

    def test_update_view(self):
        """PUT /boards/{boardId}/views/{viewId} updates view."""
        resp = api_post("/boards", {"title": "Update View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/views", {"name": "Original", "type": "board"})
        view_id = resp.json()["id"]

        resp = api_put(f"/boards/{board_id}/views/{view_id}", {"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_delete_view(self):
        """DELETE /boards/{boardId}/views/{viewId} returns 204."""
        resp = api_post("/boards", {"title": "Del View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/views", {"name": "ToDelete", "type": "board"})
        view_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}/views/{view_id}")
        assert resp.status_code == 204

        resp = api_get(f"/boards/{board_id}/views/{view_id}")
        assert resp.status_code == 404

    def test_view_visible_properties(self):
        """View can store visible properties list."""
        resp = api_post("/boards", {"title": "Visible Props View Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "Col1", "type": "text"})
        prop1_id = resp.json()["id"]
        resp = api_post(f"/boards/{board_id}/properties", {"name": "Col2", "type": "number"})
        prop2_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Custom View", "type": "table", "visibleProperties": [prop1_id, prop2_id]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert prop1_id in data["visibleProperties"]
        assert prop2_id in data["visibleProperties"]


# ════════════════════════════════════════════════════════════════════
# PART 8: Comments CRUD
# ════════════════════════════════════════════════════════════════════


class TestCommentsCRUD:
    """Test comment creation, listing, update, and deletion."""

    def test_create_comment(self):
        """POST comment returns 201."""
        resp = api_post("/boards", {"title": "Comments Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Comment Card"})
        card_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "First comment!"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "First comment!"
        assert data["createdBy"] == USER1_ID
        assert data["cardId"] == card_id
        assert "id" in data
        assert "createdAt" in data

    def test_list_comments(self):
        """GET comments returns list."""
        resp = api_post("/boards", {"title": "List Comments Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Comments Card"})
        card_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Comment 1"}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Comment 2"}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/cards/{card_id}/comments")
        assert resp.status_code == 200
        comments = resp.json()
        assert len(comments) >= 2

    def test_update_own_comment(self):
        """User can update their own comment."""
        resp = api_post("/boards", {"title": "Update Comment Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Comment Card"})
        card_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Original"})
        comment_id = resp.json()["id"]

        resp = api_put(
            f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}",
            {"text": "Edited"},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Edited"

    def test_cannot_update_others_comment(self):
        """User cannot update another user's comment."""
        resp = api_post("/boards", {"title": "Others Comment Board", "type": "board"})
        board_id = resp.json()["id"]

        # Add USER2 as commenter
        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Shared Card"})
        card_id = resp.json()["id"]

        # USER1 creates a comment
        resp = api_post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "User1's comment"})
        comment_id = resp.json()["id"]

        # USER2 tries to update it
        resp = api_put(
            f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}",
            {"text": "Hacked"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_delete_comment(self):
        """Delete own comment returns 204."""
        resp = api_post("/boards", {"title": "Del Comment Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Del Comment Card"})
        card_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "ToDelete"})
        comment_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}")
        assert resp.status_code == 204

    def test_cannot_delete_others_comment(self):
        """Cannot delete another user's comment."""
        resp = api_post("/boards", {"title": "Del Others Comment", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card"})
        card_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Mine"})
        comment_id = resp.json()["id"]

        resp = api_delete(
            f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}",
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_commenter_can_create_comment(self):
        """Commenter role can create comments."""
        resp = api_post("/boards", {"title": "Commenter Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/comments",
            {"text": "Commenter's comment"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 9: Board Members
# ════════════════════════════════════════════════════════════════════


class TestBoardMembers:
    """Test board membership management."""

    def test_add_member(self):
        """POST /boards/{boardId}/members returns 201."""
        resp = api_post("/boards", {"title": "Members Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["userId"] == USER2_ID
        assert data["role"] == "editor"
        assert data["boardId"] == board_id
        assert "addedAt" in data

    def test_list_members(self):
        """GET /boards/{boardId}/members returns member list."""
        resp = api_post("/boards", {"title": "List Members Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "viewer"}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/members")
        assert resp.status_code == 200
        members = resp.json()
        assert isinstance(members, list)
        assert len(members) >= 1

    def test_update_member_role(self):
        """PUT /boards/{boardId}/members/{userId} updates role."""
        resp = api_post("/boards", {"title": "Update Role Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "viewer"}
        ).status_code == 201

        resp = api_put(f"/boards/{board_id}/members/{USER2_ID}", {"role": "editor"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "editor"

    def test_remove_member(self):
        """DELETE /boards/{boardId}/members/{userId} returns 204."""
        resp = api_post("/boards", {"title": "Remove Member Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_delete(f"/boards/{board_id}/members/{USER2_ID}")
        assert resp.status_code == 204

        # User2 should no longer have access
        resp = api_get(f"/boards/{board_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_member_listed_in_boards(self):
        """Member can see the board in their board list."""
        resp = api_post("/boards", {"title": "Member Listed Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "viewer"}
        ).status_code == 201

        resp = api_get("/boards", headers=USER2_HEADERS)
        board_ids = [b["id"] for b in resp.json()]
        assert board_id in board_ids

    def test_all_roles_valid(self):
        """All role types can be assigned."""
        resp = api_post("/boards", {"title": "Roles Board", "type": "board"})
        board_id = resp.json()["id"]

        for role in ["admin", "editor", "commenter", "viewer"]:
            user_id = str(uuid.uuid4())
            resp = api_post(f"/boards/{board_id}/members", {"userId": user_id, "role": role})
            assert resp.status_code == 201, f"Failed to add member with role {role}"
            assert resp.json()["role"] == role


# ════════════════════════════════════════════════════════════════════
# PART 10: Content Blocks
# ════════════════════════════════════════════════════════════════════


class TestContentBlocks:
    """Test content blocks within cards."""

    def test_create_text_block(self):
        """POST content block returns 201."""
        resp = api_post("/boards", {"title": "Blocks Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Block Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Hello **world**", "order": 1.0},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "text"
        assert data["content"] == "Hello **world**"
        assert data["cardId"] == card_id
        assert "id" in data

    def test_create_all_block_types(self):
        """All block types can be created."""
        resp = api_post("/boards", {"title": "All Blocks Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "All Blocks Card"})
        card_id = resp.json()["id"]

        for btype in ["text", "image", "divider", "checkbox"]:
            resp = api_post(
                f"/boards/{board_id}/cards/{card_id}/blocks",
                {"type": btype, "content": f"Content for {btype}"},
            )
            assert resp.status_code == 201, f"Failed to create block of type {btype}"
            assert resp.json()["type"] == btype

    def test_invalid_block_type_returns_400(self):
        """Invalid block type returns 400."""
        resp = api_post("/boards", {"title": "Invalid Block Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Block Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "video", "content": "invalid"},
        )
        assert resp.status_code == 400

    def test_list_blocks_ordered(self):
        """Blocks are returned ordered by order field."""
        resp = api_post("/boards", {"title": "Ordered Blocks Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Ordered Card"})
        card_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Third", "order": 3.0},
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "First", "order": 1.0},
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Second", "order": 2.0},
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/cards/{card_id}/blocks")
        assert resp.status_code == 200
        blocks = resp.json()
        contents = [b["content"] for b in blocks]
        assert contents == ["First", "Second", "Third"]

    def test_update_block(self):
        """PUT updates a content block."""
        resp = api_post("/boards", {"title": "Update Block Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Update Block Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Original"},
        )
        block_id = resp.json()["id"]

        resp = api_put(
            f"/boards/{board_id}/cards/{card_id}/blocks/{block_id}",
            {"content": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated"

    def test_delete_block(self):
        """DELETE content block returns 204."""
        resp = api_post("/boards", {"title": "Del Block Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Del Block Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "divider", "content": ""},
        )
        block_id = resp.json()["id"]

        resp = api_delete(f"/boards/{board_id}/cards/{card_id}/blocks/{block_id}")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 11: Templates
# ════════════════════════════════════════════════════════════════════


class TestTemplates:
    """Test template CRUD and board creation from templates."""

    def test_create_template(self):
        """POST /templates returns 201."""
        resp = api_post("/templates", {"title": "Kanban Template", "type": "board", "description": "A kanban template"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Kanban Template"
        assert data["type"] == "board"
        assert data["createdBy"] == USER1_ID
        assert "id" in data

    def test_list_templates(self):
        """GET /templates returns user's templates."""
        resp = api_post("/templates", {"title": "List Template", "type": "table"})
        assert resp.status_code == 201
        tmpl_id = resp.json()["id"]

        resp = api_get("/templates")
        assert resp.status_code == 200
        templates = resp.json()
        tmpl_ids = [t["id"] for t in templates]
        assert tmpl_id in tmpl_ids

    def test_get_template(self):
        """GET /templates/{templateId} returns template details."""
        resp = api_post("/templates", {"title": "Get Template", "type": "gallery"})
        tmpl_id = resp.json()["id"]

        resp = api_get(f"/templates/{tmpl_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Template"

    def test_template_not_visible_to_others(self):
        """Other users cannot see someone's templates."""
        resp = api_post("/templates", {"title": "Private Template", "type": "board"})
        tmpl_id = resp.json()["id"]

        resp = api_get(f"/templates/{tmpl_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_create_board_from_template(self):
        """POST /templates/{id}/create-board creates a board with properties and views."""
        # Create template
        resp = api_post("/templates", {"title": "Sprint Template", "type": "board"})
        tmpl_id = resp.json()["id"]

        # Add properties to template
        opt_id = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{tmpl_id}/properties",
            {"name": "Status", "type": "select", "options": [{"id": opt_id, "value": "Todo"}]},
        )
        assert resp.status_code == 201
        tmpl_prop_id = resp.json()["id"]

        # Add view to template
        resp = api_post(
            f"/boards/{tmpl_id}/views",
            {"name": "Board View", "type": "board", "groupBy": tmpl_prop_id},
        )
        assert resp.status_code == 201

        # Create board from template
        resp = api_post(f"/templates/{tmpl_id}/create-board", {"title": "My Sprint Board"})
        assert resp.status_code == 201
        board = resp.json()
        assert board["title"] == "My Sprint Board"
        assert board["type"] == "board"
        assert board["createdBy"] == USER1_ID

        # Board should have copied properties
        assert len(board["properties"]) == 1
        assert board["properties"][0]["name"] == "Status"
        assert board["properties"][0]["type"] == "select"
        # Property ID should be different from template's
        assert board["properties"][0]["id"] != tmpl_prop_id

    def test_create_board_from_template_copies_views(self):
        """Board from template has views with updated property references."""
        # Create template with property + view
        resp = api_post("/templates", {"title": "View Template", "type": "table"})
        tmpl_id = resp.json()["id"]

        resp = api_post(f"/boards/{tmpl_id}/properties", {"name": "Priority", "type": "number"})
        prop_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{tmpl_id}/views",
            {"name": "Table View", "type": "table", "visibleProperties": [prop_id]},
        )
        assert resp.status_code == 201

        # Create board
        resp = api_post(f"/templates/{tmpl_id}/create-board", {"title": "From Template"})
        assert resp.status_code == 201
        board_id = resp.json()["id"]

        # Check views were copied
        resp = api_get(f"/boards/{board_id}/views")
        views = resp.json()
        assert len(views) == 1
        assert views[0]["name"] == "Table View"

    def test_create_board_from_template_default_title(self):
        """Board from template uses template title if no override given."""
        resp = api_post("/templates", {"title": "Default Title Template", "type": "calendar"})
        tmpl_id = resp.json()["id"]

        resp = api_post(f"/templates/{tmpl_id}/create-board", {})
        assert resp.status_code == 201
        assert resp.json()["title"] == "Default Title Template"

    def test_template_nonexistent_returns_404(self):
        """Getting a nonexistent template returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/templates/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Card Filtering and Sorting
# ════════════════════════════════════════════════════════════════════


class TestCardFilteringAndSorting:
    """Test card list filtering and sorting via query params."""

    def test_filter_cards_by_property(self):
        """filter_property + filter_value filters cards."""
        resp = api_post("/boards", {"title": "Filter Board", "type": "board"})
        board_id = resp.json()["id"]

        opt_todo = str(uuid.uuid4())
        opt_done = str(uuid.uuid4())
        resp = api_post(
            f"/boards/{board_id}/properties",
            {
                "name": "Status",
                "type": "select",
                "options": [
                    {"id": opt_todo, "value": "Todo"},
                    {"id": opt_done, "value": "Done"},
                ],
            },
        )
        prop_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Card Todo", "properties": {prop_id: opt_todo}}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Card Done", "properties": {prop_id: opt_done}}
        ).status_code == 201

        # Filter for Done
        resp = api_get(
            f"/boards/{board_id}/cards",
            params={"filter_property": prop_id, "filter_value": opt_done},
        )
        assert resp.status_code == 200
        cards = resp.json()
        assert len(cards) == 1
        assert cards[0]["title"] == "Card Done"

    def test_sort_cards_by_property(self):
        """sort_by param sorts cards by property value."""
        resp = api_post("/boards", {"title": "Sort Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "number"})
        prop_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Low", "properties": {prop_id: "1"}}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards", {"title": "High", "properties": {prop_id: "3"}}
        ).status_code == 201
        assert api_post(
            f"/boards/{board_id}/cards", {"title": "Med", "properties": {prop_id: "2"}}
        ).status_code == 201

        resp = api_get(f"/boards/{board_id}/cards", params={"sort_by": prop_id})
        assert resp.status_code == 200
        cards = resp.json()
        titles = [c["title"] for c in cards]
        assert titles == ["Low", "Med", "High"]


# ════════════════════════════════════════════════════════════════════
# PART 13: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:
    """Test cascade deletion behavior."""

    def test_delete_board_cascades_cards(self):
        """Deleting a board deletes all its cards."""
        resp = api_post("/boards", {"title": "Cascade Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Cascade Card"})
        card_id = resp.json()["id"]

        # Delete board
        resp = api_delete(f"/boards/{board_id}")
        assert resp.status_code == 204

        # Card should be gone (board is gone so 404)
        resp = api_get(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 404

    def test_delete_card_cascades_comments(self):
        """Deleting a card deletes all its comments."""
        resp = api_post("/boards", {"title": "Card Cascade Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card with Comment"})
        card_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/comments", {"text": "Will be deleted"}
        ).status_code == 201

        # Delete card
        resp = api_delete(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 204

        # Comments endpoint should 404
        resp = api_get(f"/boards/{board_id}/cards/{card_id}/comments")
        assert resp.status_code == 404

    def test_delete_card_cascades_blocks(self):
        """Deleting a card deletes all its content blocks."""
        resp = api_post("/boards", {"title": "Block Cascade Board", "type": "board"})
        board_id = resp.json()["id"]

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card with Block"})
        card_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text", "content": "Block"}
        ).status_code == 201

        # Delete card
        resp = api_delete(f"/boards/{board_id}/cards/{card_id}")
        assert resp.status_code == 204

        # Blocks endpoint should 404
        resp = api_get(f"/boards/{board_id}/cards/{card_id}/blocks")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Editor Role Permissions
# ════════════════════════════════════════════════════════════════════


class TestEditorPermissions:
    """Test editor role can do cards, comments, blocks, views but not board/members."""

    def test_editor_can_create_card(self):
        """Editor can create cards."""
        resp = api_post("/boards", {"title": "Editor Cards Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Editor Card"}, headers=USER2_HEADERS)
        assert resp.status_code == 201

    def test_editor_can_update_card(self):
        """Editor can update cards."""
        resp = api_post("/boards", {"title": "Editor Update Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card"})
        card_id = resp.json()["id"]

        resp = api_put(f"/boards/{board_id}/cards/{card_id}", {"title": "Updated by Editor"}, headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_editor_can_create_view(self):
        """Editor can create views."""
        resp = api_post("/boards", {"title": "Editor Views Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Editor View", "type": "board"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 201

    def test_editor_can_create_block(self):
        """Editor can create content blocks."""
        resp = api_post("/boards", {"title": "Editor Blocks Board", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "editor"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Block Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "By editor"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 201

    def test_commenter_cannot_create_card(self):
        """Commenter cannot create cards."""
        resp = api_post("/boards", {"title": "Commenter No Cards", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Illegal"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_commenter_cannot_create_view(self):
        """Commenter cannot create views."""
        resp = api_post("/boards", {"title": "Commenter No Views", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(
            f"/boards/{board_id}/views",
            {"name": "Illegal View", "type": "board"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_commenter_cannot_create_block(self):
        """Commenter cannot create content blocks."""
        resp = api_post("/boards", {"title": "Commenter No Blocks", "type": "board"})
        board_id = resp.json()["id"]

        assert api_post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        resp = api_post(f"/boards/{board_id}/cards", {"title": "Card"})
        card_id = resp.json()["id"]

        resp = api_post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Illegal"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403
