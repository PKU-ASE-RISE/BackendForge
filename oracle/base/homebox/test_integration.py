"""
BackendForge — L2 Integration Tests for Homebox Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned correctly
- Pattern 3: Filter/search parameters declared but not implemented
- Pattern 4: Wrong status codes (200 vs 201/204)
- Pattern 5: Business logic "interface exists but behavior empty"
- Pattern 6: Data isolation/group scoping
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Uniqueness constraints and ordering

Each test: 3-5 steps, 8-12 assertions, covers 1-2 bug patterns.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

# Unique per-run to avoid collisions
RUN_ID = uuid.uuid4().hex[:8]


def make_headers(group_id=None, user_id=None):
    return {
        "X-User-Id": user_id or str(uuid.uuid4()),
        "X-Group-Id": group_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


# Default headers for tests that do not create their own groups.
GROUP_A = str(uuid.uuid4())
USER_A = str(uuid.uuid4())
HEADERS_A = make_headers(GROUP_A, USER_A)

GROUP_B = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
HEADERS_B = make_headers(GROUP_B, USER_B)


def _reset_test_context():
    """Give every test independent primary and secondary groups."""
    global RUN_ID, GROUP_A, USER_A, HEADERS_A, GROUP_B, USER_B, HEADERS_B

    RUN_ID = uuid.uuid4().hex[:8]
    GROUP_A = str(uuid.uuid4())
    USER_A = str(uuid.uuid4())
    HEADERS_A = make_headers(GROUP_A, USER_A)
    GROUP_B = str(uuid.uuid4())
    USER_B = str(uuid.uuid4())
    HEADERS_B = make_headers(GROUP_B, USER_B)


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS_A if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def post(path, json=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS_A if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def put(path, json=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS_A if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def patch(path, json=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS_A if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS_A if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


# ════════════════════════════════════════════════════════════════════
# L2 Tests
# ════════════════════════════════════════════════════════════════════


class TestItemCamelCaseFields:
    """Pattern 1: Verify camelCase field names in item responses."""

    def test_create_item_returns_camel_case_fields(self):
        """All item fields must use camelCase, not snake_case."""
        r = post("/items", {
            "name": f"CamelTest-{RUN_ID}",
            "serialNumber": "SN-001",
            "modelNumber": "MN-001",
            "purchasePrice": 49.99,
            "purchaseDate": "2024-03-01",
            "warrantyExpires": "2026-03-01",
            "locationId": None,
        })
        assert r.status_code == 201
        data = r.json()

        # camelCase fields MUST exist
        assert "id" in data
        assert "name" in data
        assert "serialNumber" in data
        assert "modelNumber" in data
        assert "purchasePrice" in data
        assert "purchaseDate" in data
        assert "warrantyExpires" in data
        assert "locationId" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "archived" in data

        # snake_case MUST NOT exist
        assert "serial_number" not in data
        assert "model_number" not in data
        assert "purchase_price" not in data
        assert "purchase_date" not in data
        assert "warranty_expires" not in data
        assert "location_id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_list_items_response_uses_camel_case_pagination(self):
        """ItemList wrapper fields must be camelCase."""
        post("/items", {"name": f"PagCamel-{RUN_ID}"})
        r = get("/items", params={"pageSize": 5})
        assert r.status_code == 200
        data = r.json()

        # Pagination wrapper fields
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pageSize" in data

        # snake_case MUST NOT exist
        assert "page_size" not in data
        assert "total_items" not in data

        # Items inside also use camelCase
        if data["items"]:
            item = data["items"][0]
            assert "createdAt" in item
            assert "created_at" not in item


class TestLocationCamelCaseAndHierarchy:
    """Pattern 1+2: camelCase in locations + children/parent structure."""

    def test_location_response_camel_case_fields(self):
        """Location responses must have camelCase fields."""
        r = post("/locations", {"name": f"LocCamel-{RUN_ID}", "description": "test"})
        assert r.status_code == 201
        data = r.json()

        assert "id" in data
        assert "name" in data
        assert "description" in data
        assert "parentId" in data
        assert "createdAt" in data
        assert "updatedAt" in data

        # snake_case must NOT exist
        assert "parent_id" not in data
        assert "created_at" not in data
        assert "updated_at" not in data
        assert "item_count" not in data

    def test_get_location_returns_children_array(self):
        """GET /locations/{id} must include children array with id and name."""
        # Create parent
        r = post("/locations", {"name": f"ParentHier-{RUN_ID}"})
        assert r.status_code == 201
        parent_id = r.json()["id"]

        # Create 2 children
        r1 = post("/locations", {"name": f"Child1-{RUN_ID}", "parentId": parent_id})
        assert r1.status_code == 201
        child1_id = r1.json()["id"]

        r2 = post("/locations", {"name": f"Child2-{RUN_ID}", "parentId": parent_id})
        assert r2.status_code == 201
        child2_id = r2.json()["id"]

        # Get parent and verify children
        r = get(f"/locations/{parent_id}")
        assert r.status_code == 200
        data = r.json()
        assert "children" in data
        assert isinstance(data["children"], list)
        assert len(data["children"]) == 2
        child_ids = [c["id"] for c in data["children"]]
        assert child1_id in child_ids
        assert child2_id in child_ids

        # Each child summary must have id and name
        for child in data["children"]:
            assert "id" in child
            assert "name" in child

    def test_location_item_count_field(self):
        """GET /locations/{id} must include itemCount (camelCase)."""
        r = post("/locations", {"name": f"ItemCountLoc-{RUN_ID}"})
        assert r.status_code == 201
        loc_id = r.json()["id"]

        post("/items", {"name": f"InLoc-{RUN_ID}", "locationId": loc_id})

        r = get(f"/locations/{loc_id}")
        assert r.status_code == 200
        data = r.json()
        assert "itemCount" in data
        assert "item_count" not in data
        assert data["itemCount"] >= 1


class TestLabelCamelCaseAndItemCount:
    """Pattern 1+2: Labels with camelCase + itemCount computed field."""

    def test_label_response_camel_case(self):
        """Label response must use camelCase fields."""
        r = post("/labels", {"name": f"LblCamel-{RUN_ID}", "color": "#abcdef", "description": "test"})
        assert r.status_code == 201
        data = r.json()

        assert "id" in data
        assert "name" in data
        assert "color" in data
        assert "description" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_label_item_count_computed(self):
        """GET /labels/{id} must compute itemCount from actual associations."""
        r = post("/labels", {"name": f"LblCount-{RUN_ID}"})
        assert r.status_code == 201
        label_id = r.json()["id"]

        # Initially 0
        r = get(f"/labels/{label_id}")
        assert r.status_code == 200
        assert r.json()["itemCount"] == 0
        assert "item_count" not in r.json()

        # Create item and attach label
        r = post("/items", {"name": f"LblCountItem-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]
        post(f"/items/{item_id}/labels", {"labelId": label_id})

        # Now must be 1
        r = get(f"/labels/{label_id}")
        assert r.status_code == 200
        assert r.json()["itemCount"] == 1


class TestItemLabelsNestedData:
    """Pattern 2: Item responses must include labels array with nested objects."""

    def test_item_labels_returned_as_array(self):
        """After attaching labels, GET item must return them in 'labels' array."""
        # Create label
        r = post("/labels", {"name": f"Nested1-{RUN_ID}", "color": "#111111"})
        assert r.status_code == 201
        label_id = r.json()["id"]
        label_name = r.json()["name"]

        # Create item
        r = post("/items", {"name": f"NestedItem-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Attach
        r = post(f"/items/{item_id}/labels", {"labelId": label_id})
        assert r.status_code == 200

        # GET item
        r = get(f"/items/{item_id}")
        assert r.status_code == 200
        data = r.json()
        assert "labels" in data
        assert isinstance(data["labels"], list)
        assert len(data["labels"]) == 1
        lbl = data["labels"][0]
        assert lbl["id"] == label_id
        assert lbl["name"] == label_name
        # LabelSummary should have color
        assert "color" in lbl

    def test_item_list_includes_labels(self):
        """Items in list endpoint also include their labels."""
        r = post("/labels", {"name": f"ListLbl-{RUN_ID}"})
        assert r.status_code == 201
        label_id = r.json()["id"]

        r = post("/items", {"name": f"ListLblItem-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]
        post(f"/items/{item_id}/labels", {"labelId": label_id})

        r = get("/items", params={"q": f"ListLblItem-{RUN_ID}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        target = next(i for i in items if i["id"] == item_id)
        assert "labels" in target
        assert len(target["labels"]) >= 1
        assert target["labels"][0]["id"] == label_id


class TestStatusCodes:
    """Pattern 4: Verify exact status codes for create/delete operations."""

    def test_create_item_returns_201(self):
        """POST /items must return 201, not 200."""
        r = post("/items", {"name": f"Status201-{RUN_ID}"})
        assert r.status_code == 201

    def test_create_location_returns_201(self):
        """POST /locations must return 201."""
        r = post("/locations", {"name": f"LocStatus-{RUN_ID}"})
        assert r.status_code == 201

    def test_create_label_returns_201(self):
        """POST /labels must return 201."""
        r = post("/labels", {"name": f"LblStatus-{RUN_ID}"})
        assert r.status_code == 201

    def test_create_attachment_returns_201(self):
        """POST /items/{id}/attachments must return 201."""
        r = post("/items", {"name": f"AttStatus-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/attachments", {"name": "doc", "type": "manual"})
        assert r.status_code == 201

    def test_create_maintenance_returns_201(self):
        """POST /items/{id}/maintenance must return 201."""
        r = post("/items", {"name": f"MntStatus-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/maintenance", {"date": "2024-01-01", "description": "test"})
        assert r.status_code == 201

    def test_delete_item_returns_204(self):
        """DELETE /items/{id} must return 204, not 200."""
        r = post("/items", {"name": f"Del204-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = delete(f"/items/{item_id}")
        assert r.status_code == 204

    def test_delete_location_returns_204(self):
        """DELETE /locations/{id} must return 204."""
        r = post("/locations", {"name": f"DelLoc204-{RUN_ID}"})
        assert r.status_code == 201
        loc_id = r.json()["id"]

        r = delete(f"/locations/{loc_id}")
        assert r.status_code == 204

    def test_delete_label_returns_204(self):
        """DELETE /labels/{id} must return 204."""
        r = post("/labels", {"name": f"DelLbl204-{RUN_ID}"})
        assert r.status_code == 201
        label_id = r.json()["id"]

        r = delete(f"/labels/{label_id}")
        assert r.status_code == 204

    def test_delete_attachment_returns_204(self):
        """DELETE /items/{id}/attachments/{attId} must return 204."""
        r = post("/items", {"name": f"DelAtt204-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/attachments", {"name": "tmp", "type": "photo"})
        assert r.status_code == 201
        att_id = r.json()["id"]

        r = delete(f"/items/{item_id}/attachments/{att_id}")
        assert r.status_code == 204

    def test_delete_maintenance_returns_204(self):
        """DELETE /items/{id}/maintenance/{mId} must return 204."""
        r = post("/items", {"name": f"DelMnt204-{RUN_ID}"})
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/maintenance", {"date": "2024-05-01", "description": "x"})
        assert r.status_code == 201
        mnt_id = r.json()["id"]

        r = delete(f"/items/{item_id}/maintenance/{mnt_id}")
        assert r.status_code == 204

    def test_nonexistent_item_returns_404_not_200(self):
        """GET /items/{fake_id} must return 404, not 200 with empty body."""
        fake_id = str(uuid.uuid4())
        r = get(f"/items/{fake_id}")
        assert r.status_code == 404


class TestSearchFilterActuallyWorks:
    """Pattern 3+5: Verify search/filter parameters produce correct results."""

    def test_search_q_actually_filters_results(self):
        """q parameter must actually filter — not return all items."""
        unique_name = f"XyzUnique-{uuid.uuid4().hex[:8]}"
        post("/items", {"name": unique_name})
        post("/items", {"name": f"Other-{RUN_ID}"})

        r = get("/items", params={"q": unique_name})
        assert r.status_code == 200
        items = r.json()["items"]
        # Must find our item
        assert any(i["name"] == unique_name for i in items)
        # Must NOT contain unrelated items (if filter works)
        for item in items:
            # Each returned item should match the query in name/desc/serial/model
            name_or_desc = (item.get("name", "") + item.get("description", "") +
                           item.get("serialNumber", "") + item.get("modelNumber", ""))
            assert unique_name.lower() in name_or_desc.lower()

    def test_location_filter_actually_restricts(self):
        """locationId parameter must restrict results to that location only."""
        r = post("/locations", {"name": f"FilterLoc-{RUN_ID}"})
        assert r.status_code == 201
        loc_id = r.json()["id"]

        # Item in location
        r = post("/items", {"name": f"InFilterLoc-{RUN_ID}", "locationId": loc_id})
        assert r.status_code == 201
        in_item_id = r.json()["id"]

        # Item NOT in location
        r = post("/items", {"name": f"OutFilterLoc-{RUN_ID}"})
        assert r.status_code == 201
        out_item_id = r.json()["id"]

        r = get("/items", params={"locationId": loc_id})
        assert r.status_code == 200
        items = r.json()["items"]
        item_ids = [i["id"] for i in items]
        assert in_item_id in item_ids
        assert out_item_id not in item_ids

    def test_label_filter_or_logic(self):
        """labels param with multiple IDs uses OR logic."""
        r1 = post("/labels", {"name": f"OrA-{RUN_ID}"})
        assert r1.status_code == 201
        lbl_a = r1.json()["id"]

        r2 = post("/labels", {"name": f"OrB-{RUN_ID}"})
        assert r2.status_code == 201
        lbl_b = r2.json()["id"]

        # Item with label A
        ri = post("/items", {"name": f"OrItemA-{RUN_ID}"})
        assert ri.status_code == 201
        item_a = ri.json()["id"]
        post(f"/items/{item_a}/labels", {"labelId": lbl_a})

        # Item with label B
        ri = post("/items", {"name": f"OrItemB-{RUN_ID}"})
        assert ri.status_code == 201
        item_b = ri.json()["id"]
        post(f"/items/{item_b}/labels", {"labelId": lbl_b})

        # Item with neither
        ri = post("/items", {"name": f"OrItemNone-{RUN_ID}"})
        assert ri.status_code == 201
        item_none = ri.json()["id"]

        # Filter with both labels
        r = get("/items", params={"labels": f"{lbl_a},{lbl_b}", "pageSize": 100})
        assert r.status_code == 200
        item_ids = [i["id"] for i in r.json()["items"]]
        assert item_a in item_ids
        assert item_b in item_ids
        assert item_none not in item_ids

    def test_pagination_actually_limits_results(self):
        """pageSize must actually limit the number of returned items."""
        # Create enough items
        for i in range(5):
            post("/items", {"name": f"PagTest-{RUN_ID}-{i}"})

        r = get("/items", params={"pageSize": 2})
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) <= 2
        assert data["total"] >= 5


class TestStatisticsComputed:
    """Pattern 5: Statistics values must be actually computed, not hardcoded."""

    def test_total_value_is_price_times_quantity(self):
        """totalValue = sum(purchasePrice * quantity) for non-archived items."""
        h = make_headers()

        # Item 1: price=10, qty=3 → 30
        post("/items", {"name": "StatA", "purchasePrice": 10.0, "quantity": 3}, headers=h)
        # Item 2: price=20, qty=2 → 40
        post("/items", {"name": "StatB", "purchasePrice": 20.0, "quantity": 2}, headers=h)

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["totalItems"] == 2
        assert data["totalValue"] == pytest.approx(70.0)

    def test_statistics_camel_case_keys(self):
        """Statistics response must use camelCase keys."""
        h = make_headers()
        post("/items", {"name": "StatCamel"}, headers=h)

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        data = r.json()

        assert "totalItems" in data
        assert "totalValue" in data
        assert "itemsByLocation" in data
        assert "itemsByLabel" in data

        # snake_case must NOT exist
        assert "total_items" not in data
        assert "total_value" not in data
        assert "items_by_location" not in data
        assert "items_by_label" not in data

    def test_statistics_location_entries_camel_case(self):
        """Each entry in itemsByLocation must use camelCase keys."""
        h = make_headers()
        r = post("/locations", {"name": "StatLocCC"}, headers=h)
        assert r.status_code == 201
        loc_id = r.json()["id"]

        post("/items", {"name": "StatLocItem", "locationId": loc_id}, headers=h)

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        locs = r.json()["itemsByLocation"]
        assert len(locs) >= 1
        entry = locs[0]
        assert "locationId" in entry
        assert "locationName" in entry
        assert "itemCount" in entry
        assert "location_id" not in entry
        assert "location_name" not in entry
        assert "item_count" not in entry


class TestDataIsolationBetweenGroups:
    """Pattern 6: Groups must be completely isolated."""

    def test_item_created_in_group_a_invisible_to_group_b(self):
        """Items from group A must not appear in group B's list."""
        h_a = make_headers()
        h_b = make_headers()

        r = post("/items", {"name": "IsoItem-A"}, headers=h_a)
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Direct get from group B should 404
        r = get(f"/items/{item_id}", headers=h_b)
        assert r.status_code == 404

        # List from group B should not contain it
        r = get("/items", headers=h_b)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert item_id not in ids

    def test_label_names_unique_per_group(self):
        """Same label name can exist in different groups."""
        h_a = make_headers()
        h_b = make_headers()
        name = f"SharedName-{RUN_ID}"

        r1 = post("/labels", {"name": name}, headers=h_a)
        assert r1.status_code == 201

        r2 = post("/labels", {"name": name}, headers=h_b)
        assert r2.status_code == 201  # Should NOT be 409

    def test_location_names_unique_per_group(self):
        """Same location name can exist in different groups."""
        h_a = make_headers()
        h_b = make_headers()
        name = f"SharedLoc-{RUN_ID}"

        r1 = post("/locations", {"name": name}, headers=h_a)
        assert r1.status_code == 201

        r2 = post("/locations", {"name": name}, headers=h_b)
        assert r2.status_code == 201  # Should NOT be 409


class TestUniqueConstraints:
    """Pattern 8: Uniqueness enforcement within same scope."""

    def test_duplicate_label_name_same_group_returns_409(self):
        """Two labels with same name in same group → 409."""
        h = make_headers()
        name = f"DupLbl-{uuid.uuid4().hex[:6]}"
        r = post("/labels", {"name": name}, headers=h)
        assert r.status_code == 201

        r = post("/labels", {"name": name}, headers=h)
        assert r.status_code == 409

    def test_duplicate_location_name_same_parent_returns_409(self):
        """Two locations with same name under same parent → 409."""
        h = make_headers()
        name = f"DupLoc-{uuid.uuid4().hex[:6]}"
        r = post("/locations", {"name": name}, headers=h)
        assert r.status_code == 201

        r = post("/locations", {"name": name}, headers=h)
        assert r.status_code == 409

    def test_same_location_name_different_parent_allowed(self):
        """Same name under different parents is OK (no 409)."""
        h = make_headers()
        r1 = post("/locations", {"name": f"ParA-{RUN_ID}"}, headers=h)
        assert r1.status_code == 201
        par_a = r1.json()["id"]

        r2 = post("/locations", {"name": f"ParB-{RUN_ID}"}, headers=h)
        assert r2.status_code == 201
        par_b = r2.json()["id"]

        child_name = f"ChildSame-{RUN_ID}"
        r = post("/locations", {"name": child_name, "parentId": par_a}, headers=h)
        assert r.status_code == 201

        r = post("/locations", {"name": child_name, "parentId": par_b}, headers=h)
        assert r.status_code == 201  # Must succeed


class TestLocationDeleteConstraints:
    """Pattern 7: Delete constraints properly enforced."""

    def test_delete_location_with_items_returns_409(self):
        """Cannot delete a location that still has items."""
        h = make_headers()
        r = post("/locations", {"name": f"LocWithItems-{RUN_ID}"}, headers=h)
        assert r.status_code == 201
        loc_id = r.json()["id"]

        post("/items", {"name": "BlockingItem", "locationId": loc_id}, headers=h)

        r = delete(f"/locations/{loc_id}", headers=h)
        assert r.status_code == 409

    def test_delete_location_with_children_returns_409(self):
        """Cannot delete a location that has children."""
        h = make_headers()
        r = post("/locations", {"name": f"ParWithChild-{RUN_ID}"}, headers=h)
        assert r.status_code == 201
        par_id = r.json()["id"]

        post("/locations", {"name": f"BlockingChild-{RUN_ID}", "parentId": par_id}, headers=h)

        r = delete(f"/locations/{par_id}", headers=h)
        assert r.status_code == 409

    def test_delete_empty_location_succeeds(self):
        """Can delete a location with no items and no children."""
        h = make_headers()
        r = post("/locations", {"name": f"EmptyLoc-{RUN_ID}"}, headers=h)
        assert r.status_code == 201
        loc_id = r.json()["id"]

        r = delete(f"/locations/{loc_id}", headers=h)
        assert r.status_code == 204

        # Verify gone
        r = get(f"/locations/{loc_id}", headers=h)
        assert r.status_code == 404


class TestAttachmentTypeValidation:
    """Pattern 4+8: Attachment type validation + correct error codes."""

    def test_invalid_attachment_type_returns_400(self):
        """Invalid type like 'invalid' must return 400."""
        h = make_headers()
        r = post("/items", {"name": "AttTypeItem"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/attachments", {"name": "bad", "type": "invalid"}, headers=h)
        assert r.status_code == 400

    def test_valid_attachment_types_accepted(self):
        """All valid types (manual, receipt, warranty, photo) work."""
        h = make_headers()
        r = post("/items", {"name": "AttTypeValid"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        for atype in ["manual", "receipt", "warranty", "photo"]:
            r = post(f"/items/{item_id}/attachments", {"name": f"test-{atype}", "type": atype}, headers=h)
            assert r.status_code == 201
            assert r.json()["type"] == atype


class TestMaintenanceCamelCase:
    """Pattern 1: Maintenance entries must use camelCase."""

    def test_maintenance_response_camel_case(self):
        """Maintenance entry fields must be camelCase."""
        h = make_headers()
        r = post("/items", {"name": "MntCamelItem"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = post(f"/items/{item_id}/maintenance", {
            "date": "2024-06-01",
            "description": "Oil change",
            "cost": 55.0,
            "scheduledDate": "2025-06-01",
        }, headers=h)
        assert r.status_code == 201
        data = r.json()

        assert "id" in data
        assert "date" in data
        assert "description" in data
        assert "cost" in data
        assert "scheduledDate" in data
        assert "createdAt" in data

        # snake_case must NOT exist
        assert "scheduled_date" not in data
        assert "created_at" not in data

        # Verify values
        assert data["date"] == "2024-06-01"
        assert data["cost"] == 55.0
        assert data["scheduledDate"] == "2025-06-01"


class TestArchiveFilterBehavior:
    """Pattern 3+5: Archive filter actually works correctly."""

    def test_default_excludes_archived(self):
        """Default list excludes archived items."""
        h = make_headers()
        r = post("/items", {"name": "ArchiveDefault"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Archive it
        patch(f"/items/{item_id}/archive", {"archived": True}, headers=h)

        # Default listing should not include it
        r = get("/items", headers=h)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert item_id not in ids

    def test_archived_true_shows_only_archived(self):
        """archived=true shows only archived items, not all items."""
        h = make_headers()
        r1 = post("/items", {"name": "ActiveArchTest"}, headers=h)
        assert r1.status_code == 201
        active_id = r1.json()["id"]

        r2 = post("/items", {"name": "ArchivedArchTest"}, headers=h)
        assert r2.status_code == 201
        archived_id = r2.json()["id"]
        patch(f"/items/{archived_id}/archive", {"archived": True}, headers=h)

        r = get("/items", params={"archived": "true"}, headers=h)
        assert r.status_code == 200
        items = r.json()["items"]
        ids = [i["id"] for i in items]
        assert archived_id in ids
        assert active_id not in ids

    def test_archived_all_shows_everything(self):
        """archived=all shows both archived and non-archived."""
        h = make_headers()
        r1 = post("/items", {"name": "AllActive"}, headers=h)
        assert r1.status_code == 201
        active_id = r1.json()["id"]

        r2 = post("/items", {"name": "AllArchived"}, headers=h)
        assert r2.status_code == 201
        archived_id = r2.json()["id"]
        patch(f"/items/{archived_id}/archive", {"archived": True}, headers=h)

        r = get("/items", params={"archived": "all", "pageSize": 100}, headers=h)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert active_id in ids
        assert archived_id in ids
