"""
BackendForge — L2 Integration Tests for Focalboard
Adversarial tests targeting common LLM implementation bugs.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(user_id=None):
    uid = user_id or str(uuid.uuid4())
    return {"X-User-Id": uid, "Content-Type": "application/json"}


def _unique(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


USER1_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())

H1 = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
H2 = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
H3 = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}


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
# L2 Tests — Integration (20-30 tests)
# ═══════════════════════════════════════════════════════════


class TestBoardFieldNames:
    """Pattern 1+4: Verify exact field names (camelCase) and status codes."""

    def test_board_create_returns_all_required_fields_with_correct_casing(self):
        """Board response must have camelCase fields: id, title, type, createdBy, createdAt, updatedAt."""
        title = _unique("board-")
        r = post("/boards", {"title": title, "type": "board", "description": "test desc"})
        assert r.status_code == 201
        data = r.json()
        # Exact field names per openapi.yaml
        assert "id" in data
        assert "title" in data
        assert "type" in data
        assert "description" in data
        assert "createdBy" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "properties" in data
        # Values
        assert data["title"] == title
        assert data["type"] == "board"
        assert data["description"] == "test desc"
        assert data["createdBy"] == USER1_ID
        # UUID format
        assert len(data["id"]) >= 32  # UUID has 32 hex chars + hyphens

    def test_board_get_returns_same_fields_as_create(self):
        """GET should return identical structure to POST response."""
        title = _unique("get-board-")
        r = post("/boards", {"title": title, "type": "table"})
        assert r.status_code == 201
        board_id = r.json()["id"]
        created_at = r.json()["createdAt"]

        r = get(f"/boards/{board_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == board_id
        assert data["title"] == title
        assert data["type"] == "table"
        assert data["createdBy"] == USER1_ID
        assert data["createdAt"] == created_at
        assert "updatedAt" in data
        assert isinstance(data.get("properties"), list)


class TestCardFieldNamesAndProperties:
    """Pattern 1+2: Card fields camelCase + nested properties preserved."""

    def test_card_response_has_correct_field_names(self):
        """Card must return boardId, createdBy, createdAt, updatedAt (camelCase)."""
        r = post("/boards", {"title": _unique("card-board-"), "type": "board"})
        board_id = r.json()["id"]

        card_title = _unique("card-")
        r = post(f"/boards/{board_id}/cards", {"title": card_title, "content": "md content", "order": 2.5})
        assert r.status_code == 201
        data = r.json()
        assert data["boardId"] == board_id
        assert data["title"] == card_title
        assert data["content"] == "md content"
        assert data["order"] == 2.5
        assert data["createdBy"] == USER1_ID
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "id" in data
        # Verify no snake_case variants
        assert "board_id" not in data
        assert "created_by" not in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_card_properties_roundtrip(self):
        """Card properties object preserved on create and retrieve."""
        r = post("/boards", {"title": _unique("prop-rt-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "text"})
        prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards", {"title": "PropCard", "properties": {prop_id: "Critical"}})
        assert r.status_code == 201
        card_id = r.json()["id"]
        assert r.json()["properties"][prop_id] == "Critical"

        # Retrieve
        r = get(f"/boards/{board_id}/cards/{card_id}")
        assert r.status_code == 200
        assert r.json()["properties"][prop_id] == "Critical"

    def test_card_with_multiple_properties(self):
        """Multiple properties on a single card are all preserved."""
        r = post("/boards", {"title": _unique("multi-prop-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Status", "type": "text"})
        p1 = r.json()["id"]
        r = post(f"/boards/{board_id}/properties", {"name": "Effort", "type": "number"})
        p2 = r.json()["id"]
        r = post(f"/boards/{board_id}/properties", {"name": "URL", "type": "url"})
        p3 = r.json()["id"]

        props = {p1: "Open", p2: "5", p3: "https://example.com"}
        r = post(f"/boards/{board_id}/cards", {"title": "Multi", "properties": props})
        assert r.status_code == 201
        card_id = r.json()["id"]

        r = get(f"/boards/{board_id}/cards/{card_id}")
        data = r.json()
        assert data["properties"][p1] == "Open"
        assert data["properties"][p2] == "5"
        assert data["properties"][p3] == "https://example.com"


class TestViewNestedData:
    """Pattern 2: View filter/sort/visibleProperties nested data preserved."""

    def test_view_filter_roundtrip(self):
        """View filter with conditions stored and retrievable."""
        r = post("/boards", {"title": _unique("view-filter-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Status", "type": "text"})
        prop_id = r.json()["id"]

        filter_obj = {
            "operator": "and",
            "conditions": [
                {"propertyId": prop_id, "operator": "equals", "value": "Done"},
                {"propertyId": prop_id, "operator": "notEquals", "value": "Blocked"},
            ],
        }
        r = post(f"/boards/{board_id}/views", {"name": "Filtered", "type": "table", "filter": filter_obj})
        assert r.status_code == 201
        view_id = r.json()["id"]
        data = r.json()
        assert data["filter"]["operator"] == "and"
        assert len(data["filter"]["conditions"]) == 2
        assert data["filter"]["conditions"][0]["propertyId"] == prop_id
        assert data["filter"]["conditions"][0]["operator"] == "equals"
        assert data["filter"]["conditions"][0]["value"] == "Done"
        assert data["filter"]["conditions"][1]["operator"] == "notEquals"

        # GET the view
        r = get(f"/boards/{board_id}/views/{view_id}")
        assert r.status_code == 200
        assert r.json()["filter"]["conditions"][0]["value"] == "Done"
        assert len(r.json()["filter"]["conditions"]) == 2

    def test_view_sort_roundtrip(self):
        """View sort config preserved on create and get."""
        r = post("/boards", {"title": _unique("view-sort-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Date", "type": "date"})
        p1 = r.json()["id"]
        r = post(f"/boards/{board_id}/properties", {"name": "Priority", "type": "number"})
        p2 = r.json()["id"]

        sorts = [
            {"propertyId": p1, "direction": "desc"},
            {"propertyId": p2, "direction": "asc"},
        ]
        r = post(f"/boards/{board_id}/views", {"name": "Sorted", "type": "table", "sort": sorts})
        assert r.status_code == 201
        view_id = r.json()["id"]
        data = r.json()
        assert len(data["sort"]) == 2
        assert data["sort"][0]["propertyId"] == p1
        assert data["sort"][0]["direction"] == "desc"
        assert data["sort"][1]["propertyId"] == p2
        assert data["sort"][1]["direction"] == "asc"

        r = get(f"/boards/{board_id}/views/{view_id}")
        assert r.json()["sort"][0]["direction"] == "desc"
        assert r.json()["sort"][1]["direction"] == "asc"

    def test_view_group_by_and_visible_properties(self):
        """View groupBy and visibleProperties fields preserved."""
        r = post("/boards", {"title": _unique("view-group-"), "type": "board"})
        board_id = r.json()["id"]

        opt_id = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Category",
            "type": "select",
            "options": [{"id": opt_id, "value": "A"}],
        })
        cat_prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Notes", "type": "text"})
        notes_prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/views", {
            "name": "Grouped",
            "type": "board",
            "groupBy": cat_prop_id,
            "visibleProperties": [cat_prop_id, notes_prop_id],
        })
        assert r.status_code == 201
        data = r.json()
        assert data["groupBy"] == cat_prop_id
        assert cat_prop_id in data["visibleProperties"]
        assert notes_prop_id in data["visibleProperties"]


class TestCardFilteringActuallyWorks:
    """Pattern 3+5: Filtering/sorting params actually filter, not just accepted."""

    def test_filter_returns_subset_not_all(self):
        """filter_property+filter_value must actually reduce results."""
        r = post("/boards", {"title": _unique("filter-real-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Team", "type": "text"})
        prop_id = r.json()["id"]

        # Create 3 cards: 2 matching, 1 not
        assert post(
            f"/boards/{board_id}/cards", {"title": "Alpha", "properties": {prop_id: "frontend"}}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards", {"title": "Beta", "properties": {prop_id: "backend"}}
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards", {"title": "Gamma", "properties": {prop_id: "frontend"}}
        ).status_code == 201

        # Without filter: should have 3
        r = get(f"/boards/{board_id}/cards")
        assert len(r.json()) == 3

        # With filter: should have 2
        r = get(f"/boards/{board_id}/cards", params={"filter_property": prop_id, "filter_value": "frontend"})
        assert r.status_code == 200
        cards = r.json()
        assert len(cards) == 2
        titles = {c["title"] for c in cards}
        assert "Alpha" in titles
        assert "Gamma" in titles
        assert "Beta" not in titles

    def test_sort_by_property_changes_order(self):
        """sort_by actually reorders cards (not just accepted silently)."""
        r = post("/boards", {"title": _unique("sort-real-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Score", "type": "number"})
        prop_id = r.json()["id"]

        # Create cards with different property values
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "Mid", "properties": {prop_id: "50"}, "order": 1.0},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "Low", "properties": {prop_id: "10"}, "order": 2.0},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards",
            {"title": "High", "properties": {prop_id: "90"}, "order": 3.0},
        ).status_code == 201

        # Default order (by order field)
        r = get(f"/boards/{board_id}/cards")
        default_titles = [c["title"] for c in r.json()]
        assert default_titles == ["Mid", "Low", "High"]

        # Sort by Score (ascending)
        r = get(f"/boards/{board_id}/cards", params={"sort_by": prop_id})
        assert r.status_code == 200
        sorted_titles = [c["title"] for c in r.json()]
        assert sorted_titles == ["Low", "Mid", "High"]

    def test_card_ordering_by_order_field(self):
        """Cards returned in ascending order by 'order', then createdAt."""
        r = post("/boards", {"title": _unique("order-"), "type": "board"})
        board_id = r.json()["id"]

        assert post(f"/boards/{board_id}/cards", {"title": "C", "order": 3.0}).status_code == 201
        assert post(f"/boards/{board_id}/cards", {"title": "A", "order": 1.0}).status_code == 201
        assert post(f"/boards/{board_id}/cards", {"title": "B", "order": 2.0}).status_code == 201

        r = get(f"/boards/{board_id}/cards")
        titles = [c["title"] for c in r.json()]
        assert titles == ["A", "B", "C"]


class TestSelectPropertyValidation:
    """Pattern 5+8: Select/MultiSelect validation actually enforced."""

    def test_select_valid_option_accepted(self):
        """Card with valid select option is created successfully."""
        r = post("/boards", {"title": _unique("sel-valid-"), "type": "board"})
        board_id = r.json()["id"]

        opt1 = str(uuid.uuid4())
        opt2 = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Status",
            "type": "select",
            "options": [{"id": opt1, "value": "Open"}, {"id": opt2, "value": "Closed"}],
        })
        prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards", {"title": "Valid", "properties": {prop_id: opt1}})
        assert r.status_code == 201
        assert r.json()["properties"][prop_id] == opt1

    def test_select_invalid_option_rejected(self):
        """Card with invalid select option returns 400."""
        r = post("/boards", {"title": _unique("sel-inv-"), "type": "board"})
        board_id = r.json()["id"]

        opt1 = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Priority",
            "type": "select",
            "options": [{"id": opt1, "value": "High"}],
        })
        prop_id = r.json()["id"]

        fake_option = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/cards", {"title": "Bad", "properties": {prop_id: fake_option}})
        assert r.status_code == 400

    def test_multiselect_valid_options_accepted(self):
        """MultiSelect with all valid option IDs succeeds."""
        r = post("/boards", {"title": _unique("multi-valid-"), "type": "board"})
        board_id = r.json()["id"]

        opt_a = str(uuid.uuid4())
        opt_b = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Tags",
            "type": "multiSelect",
            "options": [{"id": opt_a, "value": "Bug"}, {"id": opt_b, "value": "Feature"}],
        })
        prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards", {"title": "Multi", "properties": {prop_id: [opt_a, opt_b]}})
        assert r.status_code == 201
        vals = r.json()["properties"][prop_id]
        assert opt_a in vals
        assert opt_b in vals

    def test_multiselect_invalid_option_rejected(self):
        """MultiSelect with one invalid option returns 400."""
        r = post("/boards", {"title": _unique("multi-inv-"), "type": "board"})
        board_id = r.json()["id"]

        opt_a = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/properties", {
            "name": "Labels",
            "type": "multiSelect",
            "options": [{"id": opt_a, "value": "UI"}],
        })
        prop_id = r.json()["id"]

        bad_id = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/cards", {"title": "Bad", "properties": {prop_id: [opt_a, bad_id]}})
        assert r.status_code == 400

    def test_unknown_property_key_silently_ignored(self):
        """Unknown property IDs are not stored on cards."""
        r = post("/boards", {"title": _unique("unk-key-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Real", "type": "text"})
        real_prop_id = r.json()["id"]

        fake_id = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/cards", {
            "title": "Mixed",
            "properties": {real_prop_id: "kept", fake_id: "dropped"},
        })
        assert r.status_code == 201
        card_data = r.json()
        assert card_data["properties"].get(real_prop_id) == "kept"
        assert fake_id not in card_data["properties"]


class TestBoardPropertyOperations:
    """Pattern 2+7: Board property CRUD and cascade to cards."""

    def test_property_shows_in_board_get(self):
        """Created properties appear in board's properties array."""
        r = post("/boards", {"title": _unique("prop-in-board-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Field1", "type": "text"})
        assert r.status_code == 201
        p1_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Field2", "type": "number"})
        p2_id = r.json()["id"]

        r = get(f"/boards/{board_id}")
        board = r.json()
        assert len(board["properties"]) == 2
        prop_ids = [p["id"] for p in board["properties"]]
        assert p1_id in prop_ids
        assert p2_id in prop_ids
        # Verify nested structure
        for p in board["properties"]:
            assert "id" in p
            assert "name" in p
            assert "type" in p

    def test_property_options_preserved(self):
        """Select property options with id, value, color preserved."""
        r = post("/boards", {"title": _unique("opts-"), "type": "board"})
        board_id = r.json()["id"]

        opt1_id = str(uuid.uuid4())
        opt2_id = str(uuid.uuid4())
        options = [
            {"id": opt1_id, "value": "Red", "color": "#ff0000"},
            {"id": opt2_id, "value": "Blue", "color": "#0000ff"},
        ]
        r = post(f"/boards/{board_id}/properties", {"name": "Color", "type": "select", "options": options})
        assert r.status_code == 201
        prop_data = r.json()
        assert len(prop_data["options"]) == 2
        opt_map = {o["id"]: o for o in prop_data["options"]}
        assert opt_map[opt1_id]["value"] == "Red"
        assert opt_map[opt1_id]["color"] == "#ff0000"
        assert opt_map[opt2_id]["value"] == "Blue"

    def test_property_delete_removes_from_cards(self):
        """Deleting a property removes that key from all card properties."""
        r = post("/boards", {"title": _unique("prop-del-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "Removable", "type": "text"})
        rem_prop_id = r.json()["id"]
        r = post(f"/boards/{board_id}/properties", {"name": "Keeper", "type": "text"})
        keep_prop_id = r.json()["id"]

        # Create card with both properties
        r = post(f"/boards/{board_id}/cards", {
            "title": "Has Both",
            "properties": {rem_prop_id: "gone", keep_prop_id: "stays"},
        })
        card_id = r.json()["id"]

        # Delete the removable property
        r = delete(f"/boards/{board_id}/properties/{rem_prop_id}")
        assert r.status_code == 204

        # Card should only have the keeper
        r = get(f"/boards/{board_id}/cards/{card_id}")
        props = r.json()["properties"]
        assert rem_prop_id not in props
        assert props[keep_prop_id] == "stays"


class TestCommentFieldsAndOwnership:
    """Pattern 1+6: Comment fields correct + ownership enforcement."""

    def test_comment_has_correct_fields(self):
        """Comment response: id, cardId, text, createdBy, createdAt, updatedAt."""
        r = post("/boards", {"title": _unique("cmt-fields-"), "type": "board"})
        board_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards", {"title": "CmtCard"})
        card_id = r.json()["id"]

        comment_text = _unique("comment-")
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": comment_text})
        assert r.status_code == 201
        data = r.json()
        assert data["text"] == comment_text
        assert data["cardId"] == card_id
        assert data["createdBy"] == USER1_ID
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        # No snake_case
        assert "card_id" not in data
        assert "created_by" not in data

    def test_comment_update_only_by_owner(self):
        """Only the comment creator can update it; others get 403."""
        r = post("/boards", {"title": _unique("cmt-own-"), "type": "board"})
        board_id = r.json()["id"]
        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "commenter"}
        ).status_code == 201

        r = post(f"/boards/{board_id}/cards", {"title": "Shared"})
        card_id = r.json()["id"]

        # User1 creates comment
        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "User1's"})
        cmt_id = r.json()["id"]

        # User2 tries to update → 403
        r = put(f"/boards/{board_id}/cards/{card_id}/comments/{cmt_id}", {"text": "hacked"}, headers=H2)
        assert r.status_code == 403

        # User1 can update → 200
        r = put(f"/boards/{board_id}/cards/{card_id}/comments/{cmt_id}", {"text": "updated"})
        assert r.status_code == 200
        assert r.json()["text"] == "updated"


class TestContentBlockFields:
    """Pattern 1+4: Content block fields and ordering."""

    def test_block_response_fields(self):
        """Block must have id, cardId, type, content, order, createdAt, updatedAt."""
        r = post("/boards", {"title": _unique("blk-fields-"), "type": "board"})
        board_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards", {"title": "BlockCard"})
        card_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {
            "type": "text",
            "content": "hello block",
            "order": 1.5,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["type"] == "text"
        assert data["content"] == "hello block"
        assert data["order"] == 1.5
        assert data["cardId"] == card_id
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "card_id" not in data

    def test_blocks_returned_ordered(self):
        """Blocks are listed in ascending order by 'order' field."""
        r = post("/boards", {"title": _unique("blk-ord-"), "type": "board"})
        board_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards", {"title": "OrdCard"})
        card_id = r.json()["id"]

        assert post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "text", "content": "Z-last", "order": 99.0},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "image", "content": "A-first", "order": 1.0},
        ).status_code == 201
        assert post(
            f"/boards/{board_id}/cards/{card_id}/blocks",
            {"type": "divider", "content": "M-mid", "order": 50.0},
        ).status_code == 201

        r = get(f"/boards/{board_id}/cards/{card_id}/blocks")
        assert r.status_code == 200
        blocks = r.json()
        orders = [b["order"] for b in blocks]
        assert orders == sorted(orders)
        assert blocks[0]["content"] == "A-first"
        assert blocks[1]["content"] == "M-mid"
        assert blocks[2]["content"] == "Z-last"

    def test_invalid_block_type_rejected(self):
        """Block type not in [text, image, divider, checkbox] returns 400."""
        r = post("/boards", {"title": _unique("blk-inv-"), "type": "board"})
        board_id = r.json()["id"]
        r = post(f"/boards/{board_id}/cards", {"title": "Card"})
        card_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "video", "content": "x"})
        assert r.status_code == 400

        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "audio", "content": "x"})
        assert r.status_code == 400


class TestMemberFields:
    """Pattern 1+4: Board member response fields."""

    def test_member_response_has_correct_fields(self):
        """Member: boardId, userId, role, addedAt."""
        r = post("/boards", {"title": _unique("mem-fields-"), "type": "board"})
        board_id = r.json()["id"]

        member_id = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/members", {"userId": member_id, "role": "editor"})
        assert r.status_code == 201
        data = r.json()
        assert data["boardId"] == board_id
        assert data["userId"] == member_id
        assert data["role"] == "editor"
        assert "addedAt" in data
        # No snake_case
        assert "board_id" not in data
        assert "user_id" not in data
        assert "added_at" not in data

    def test_list_members_returns_all(self):
        """List members returns all added members."""
        r = post("/boards", {"title": _unique("mem-list-"), "type": "board"})
        board_id = r.json()["id"]

        u1 = str(uuid.uuid4())
        u2 = str(uuid.uuid4())
        assert post(f"/boards/{board_id}/members", {"userId": u1, "role": "editor"}).status_code == 201
        assert post(f"/boards/{board_id}/members", {"userId": u2, "role": "viewer"}).status_code == 201

        r = get(f"/boards/{board_id}/members")
        assert r.status_code == 200
        members = r.json()
        user_ids = [m["userId"] for m in members]
        assert u1 in user_ids
        assert u2 in user_ids


class TestDataIsolation:
    """Pattern 6: Users cannot see each other's boards/data."""

    def test_boards_isolated_between_users(self):
        """User B cannot see User A's board in list or directly."""
        r = post("/boards", {"title": _unique("iso-"), "type": "board"})
        board_id = r.json()["id"]

        # User3 direct access
        r = get(f"/boards/{board_id}", headers=H3)
        assert r.status_code == 404

        # User3 list
        r = get("/boards", headers=H3)
        board_ids = [b["id"] for b in r.json()]
        assert board_id not in board_ids

    def test_templates_isolated_between_users(self):
        """User B cannot see User A's templates."""
        r = post("/templates", {"title": _unique("tmpl-iso-"), "type": "board"})
        tmpl_id = r.json()["id"]

        # User2 direct access
        r = get(f"/templates/{tmpl_id}", headers=H2)
        assert r.status_code == 404

        # User2 list
        r = get("/templates", headers=H2)
        tmpl_ids = [t["id"] for t in r.json()]
        assert tmpl_id not in tmpl_ids

    def test_member_gets_board_access(self):
        """After being added as member, user can see board in list and directly."""
        r = post("/boards", {"title": _unique("access-"), "type": "board"})
        board_id = r.json()["id"]

        # Before membership
        r = get(f"/boards/{board_id}", headers=H2)
        assert r.status_code == 404

        # Add membership
        assert post(
            f"/boards/{board_id}/members", {"userId": USER2_ID, "role": "viewer"}
        ).status_code == 201

        # After membership
        r = get(f"/boards/{board_id}", headers=H2)
        assert r.status_code == 200
        assert r.json()["id"] == board_id

        r = get("/boards", headers=H2)
        board_ids = [b["id"] for b in r.json()]
        assert board_id in board_ids


class TestStatusCodes:
    """Pattern 4: Exact HTTP status codes per spec."""

    def test_create_endpoints_return_201(self):
        """All POST create endpoints return 201."""
        r = post("/boards", {"title": _unique("201-"), "type": "board"})
        assert r.status_code == 201
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "P", "type": "text"})
        assert r.status_code == 201

        r = post(f"/boards/{board_id}/cards", {"title": "Card"})
        assert r.status_code == 201
        card_id = r.json()["id"]

        r = post(f"/boards/{board_id}/views", {"name": "V", "type": "board"})
        assert r.status_code == 201

        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "t"})
        assert r.status_code == 201

        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text", "content": "c"})
        assert r.status_code == 201

        uid = str(uuid.uuid4())
        r = post(f"/boards/{board_id}/members", {"userId": uid, "role": "viewer"})
        assert r.status_code == 201

        r = post("/templates", {"title": _unique("t-"), "type": "board"})
        assert r.status_code == 201

    def test_delete_endpoints_return_204(self):
        """All DELETE endpoints return 204 with no body."""
        r = post("/boards", {"title": _unique("204-"), "type": "board"})
        board_id = r.json()["id"]

        r = post(f"/boards/{board_id}/properties", {"name": "X", "type": "text"})
        prop_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards", {"title": "C"})
        card_id = r.json()["id"]

        r = post(f"/boards/{board_id}/views", {"name": "V", "type": "board"})
        view_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards/{card_id}/comments", {"text": "t"})
        cmt_id = r.json()["id"]

        r = post(f"/boards/{board_id}/cards/{card_id}/blocks", {"type": "text"})
        blk_id = r.json()["id"]

        uid = str(uuid.uuid4())
        assert post(f"/boards/{board_id}/members", {"userId": uid, "role": "viewer"}).status_code == 201

        # Delete in reverse dependency order
        r = delete(f"/boards/{board_id}/members/{uid}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}/cards/{card_id}/blocks/{blk_id}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}/cards/{card_id}/comments/{cmt_id}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}/views/{view_id}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}/cards/{card_id}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}/properties/{prop_id}")
        assert r.status_code == 204

        r = delete(f"/boards/{board_id}")
        assert r.status_code == 204

    def test_nonexistent_resources_return_404(self):
        """Accessing nonexistent resources returns 404."""
        fake = str(uuid.uuid4())
        assert get(f"/boards/{fake}").status_code == 404
        assert get(f"/templates/{fake}").status_code == 404

        # Create board, use fake card/view IDs
        r = post("/boards", {"title": _unique("404-"), "type": "board"})
        board_id = r.json()["id"]
        assert get(f"/boards/{board_id}/cards/{fake}").status_code == 404
        assert get(f"/boards/{board_id}/views/{fake}").status_code == 404

    def test_wrong_board_context_returns_404(self):
        """Card from board A accessed via board B returns 404."""
        r = post("/boards", {"title": _unique("ctx-a-"), "type": "board"})
        board_a = r.json()["id"]
        r = post("/boards", {"title": _unique("ctx-b-"), "type": "board"})
        board_b = r.json()["id"]

        r = post(f"/boards/{board_a}/cards", {"title": "InA"})
        card_id = r.json()["id"]

        r = get(f"/boards/{board_b}/cards/{card_id}")
        assert r.status_code == 404


class TestTemplateDeepCopy:
    """Pattern 2+5: Template creates board with new IDs, not references to template."""

    def test_template_properties_get_new_ids(self):
        """Board from template has properties with NEW UUIDs, not template prop IDs."""
        r = post("/templates", {"title": _unique("tmpl-cp-"), "type": "board"})
        tmpl_id = r.json()["id"]

        opt_id = str(uuid.uuid4())
        r = post(f"/boards/{tmpl_id}/properties", {
            "name": "Status",
            "type": "select",
            "options": [{"id": opt_id, "value": "Open"}],
        })
        tmpl_prop_id = r.json()["id"]

        r = post(f"/templates/{tmpl_id}/create-board", {"title": _unique("from-tmpl-")})
        assert r.status_code == 201
        board = r.json()
        assert len(board["properties"]) == 1
        new_prop_id = board["properties"][0]["id"]
        assert new_prop_id != tmpl_prop_id  # NEW ID
        assert board["properties"][0]["name"] == "Status"
        assert board["properties"][0]["type"] == "select"
        assert len(board["properties"][0]["options"]) == 1

    def test_template_views_copied_with_new_ids(self):
        """Views from template are copied with new IDs."""
        r = post("/templates", {"title": _unique("tmpl-view-"), "type": "table"})
        tmpl_id = r.json()["id"]

        r = post(f"/boards/{tmpl_id}/properties", {"name": "Col", "type": "text"})
        prop_id = r.json()["id"]

        r = post(f"/boards/{tmpl_id}/views", {
            "name": "MainView",
            "type": "table",
            "visibleProperties": [prop_id],
        })
        tmpl_view_id = r.json()["id"]

        r = post(f"/templates/{tmpl_id}/create-board", {"title": _unique("board-from-")})
        assert r.status_code == 201
        board_id = r.json()["id"]

        r = get(f"/boards/{board_id}/views")
        views = r.json()
        assert len(views) == 1
        assert views[0]["name"] == "MainView"
        assert views[0]["id"] != tmpl_view_id  # NEW ID
