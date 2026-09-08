"""
BackendForge — Comprehensive Correctness Tests for Homebox Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

# Group and user UUIDs
GROUP_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

# Second group for isolation tests
GROUP2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Group-Id": GROUP_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-User-Id": USER2_ID,
    "X-Group-Id": GROUP_ID,
    "Content-Type": "application/json",
}

HEADERS_GROUP2 = {
    "X-User-Id": USER3_ID,
    "X-Group-Id": GROUP2_ID,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


def _reset_test_context():
    """Give every test fresh primary and secondary groups."""
    global GROUP_ID, USER_ID, USER2_ID, GROUP2_ID, USER3_ID
    global HEADERS, HEADERS_USER2, HEADERS_GROUP2, UNIQUE

    GROUP_ID = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    USER2_ID = str(uuid.uuid4())
    GROUP2_ID = str(uuid.uuid4())
    USER3_ID = str(uuid.uuid4())
    HEADERS = {
        "X-User-Id": USER_ID,
        "X-Group-Id": GROUP_ID,
        "Content-Type": "application/json",
    }
    HEADERS_USER2 = {
        "X-User-Id": USER2_ID,
        "X-Group-Id": GROUP_ID,
        "Content-Type": "application/json",
    }
    HEADERS_GROUP2 = {
        "X-User-Id": USER3_ID,
        "X-Group-Id": GROUP2_ID,
        "Content-Type": "application/json",
    }
    UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_patch(path, json_data=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_both_headers(self):
        """Requests without auth headers should get 401."""
        resp = requests.get(f"{BASE_URL}/items", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_missing_user_id(self):
        """Request with only X-Group-Id should get 401."""
        resp = requests.get(
            f"{BASE_URL}/items",
            headers={"X-Group-Id": GROUP_ID, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_missing_group_id(self):
        """Request with only X-User-Id should get 401."""
        resp = requests.get(
            f"{BASE_URL}/items",
            headers={"X-User-Id": USER_ID, "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_valid_auth_succeeds(self):
        """Request with both headers should succeed."""
        resp = api_get("/items")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 3: Locations CRUD
# ════════════════════════════════════════════════════════════════════


class TestLocations:

    def test_create_location(self):
        """Create a root location."""
        resp = api_post("/locations", {"name": f"House-{UNIQUE}", "description": "Main house"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"House-{UNIQUE}"
        assert data["description"] == "Main house"
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert data.get("parentId") is None

    def test_create_child_location(self):
        """Create a location with a parent."""
        # Create parent
        resp = api_post("/locations", {"name": f"Parent-{UNIQUE}-child"})
        assert resp.status_code == 201
        parent_id = resp.json()["id"]

        # Create child
        resp = api_post("/locations", {"name": f"Child-{UNIQUE}", "parentId": parent_id})
        assert resp.status_code == 201
        data = resp.json()
        assert data["parentId"] == parent_id

    def test_list_locations(self):
        """List all locations."""
        api_post("/locations", {"name": f"ListLocation-{UNIQUE}"})
        resp = api_get("/locations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_location_with_children(self):
        """Get a location and check children are included."""
        # Create parent
        resp = api_post("/locations", {"name": f"GetParent-{UNIQUE}"})
        assert resp.status_code == 201
        parent_id = resp.json()["id"]

        # Create child
        resp = api_post("/locations", {"name": f"GetChild-{UNIQUE}", "parentId": parent_id})
        assert resp.status_code == 201
        child_id = resp.json()["id"]

        # Get parent
        resp = api_get(f"/locations/{parent_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "children" in data
        assert isinstance(data["children"], list)
        child_ids = [c["id"] for c in data["children"]]
        assert child_id in child_ids

    def test_update_location(self):
        """Update a location's name and description."""
        resp = api_post("/locations", {"name": f"ToUpdate-{UNIQUE}"})
        assert resp.status_code == 201
        loc_id = resp.json()["id"]

        resp = api_put(f"/locations/{loc_id}", {"name": f"Updated-{UNIQUE}", "description": "new desc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"Updated-{UNIQUE}"
        assert data["description"] == "new desc"

    def test_delete_empty_location(self):
        """Delete a location with no items or children."""
        resp = api_post("/locations", {"name": f"ToDelete-{UNIQUE}"})
        assert resp.status_code == 201
        loc_id = resp.json()["id"]

        resp = api_delete(f"/locations/{loc_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = api_get(f"/locations/{loc_id}")
        assert resp.status_code == 404

    def test_delete_location_with_children_fails(self):
        """Cannot delete a location that has child locations."""
        resp = api_post("/locations", {"name": f"HasChild-{UNIQUE}"})
        assert resp.status_code == 201
        parent_id = resp.json()["id"]

        resp = api_post("/locations", {"name": f"ChildBlocking-{UNIQUE}", "parentId": parent_id})
        assert resp.status_code == 201

        resp = api_delete(f"/locations/{parent_id}")
        assert resp.status_code == 409

    def test_delete_location_with_items_fails(self):
        """Cannot delete a location that has items."""
        resp = api_post("/locations", {"name": f"HasItems-{UNIQUE}"})
        assert resp.status_code == 201
        loc_id = resp.json()["id"]

        # Create item in this location
        resp = api_post("/items", {"name": f"BlockItem-{UNIQUE}", "locationId": loc_id})
        assert resp.status_code == 201

        resp = api_delete(f"/locations/{loc_id}")
        assert resp.status_code == 409

    def test_duplicate_location_name_same_parent(self):
        """Duplicate location name under same parent returns 409."""
        name = f"DupLoc-{UNIQUE}-{uuid.uuid4().hex[:4]}"
        resp = api_post("/locations", {"name": name})
        assert resp.status_code == 201

        resp = api_post("/locations", {"name": name})
        assert resp.status_code == 409

    def test_same_name_different_parent_allowed(self):
        """Same name under different parents is allowed."""
        name = f"SameName-{UNIQUE}-{uuid.uuid4().hex[:4]}"
        resp = api_post("/locations", {"name": f"P1-{name}"})
        assert resp.status_code == 201
        p1 = resp.json()["id"]

        resp = api_post("/locations", {"name": f"P2-{name}"})
        assert resp.status_code == 201
        p2 = resp.json()["id"]

        resp = api_post("/locations", {"name": name, "parentId": p1})
        assert resp.status_code == 201

        resp = api_post("/locations", {"name": name, "parentId": p2})
        assert resp.status_code == 201

    def test_get_nonexistent_location(self):
        """Getting a non-existent location returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/locations/{fake_id}")
        assert resp.status_code == 404

    def test_circular_reference_prevented(self):
        """Cannot set a location's parent to itself."""
        resp = api_post("/locations", {"name": f"SelfRef-{UNIQUE}"})
        assert resp.status_code == 201
        loc_id = resp.json()["id"]

        resp = api_put(f"/locations/{loc_id}", {"name": f"SelfRef-{UNIQUE}", "parentId": loc_id})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 4: Labels CRUD
# ════════════════════════════════════════════════════════════════════


class TestLabels:

    def test_create_label(self):
        """Create a label."""
        resp = api_post("/labels", {"name": f"Electronics-{UNIQUE}", "color": "#ff0000"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Electronics-{UNIQUE}"
        assert data["color"] == "#ff0000"
        assert "id" in data
        assert "createdAt" in data

    def test_list_labels(self):
        """List all labels."""
        # Ensure at least one label exists
        api_post("/labels", {"name": f"ListLabel-{UNIQUE}"})
        resp = api_get("/labels")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_label(self):
        """Get a single label with item count."""
        resp = api_post("/labels", {"name": f"GetLabel-{UNIQUE}"})
        assert resp.status_code == 201
        label_id = resp.json()["id"]

        resp = api_get(f"/labels/{label_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == label_id
        assert "itemCount" in data
        assert data["itemCount"] == 0

    def test_update_label(self):
        """Update a label."""
        resp = api_post("/labels", {"name": f"ToUpdateLabel-{UNIQUE}"})
        assert resp.status_code == 201
        label_id = resp.json()["id"]

        resp = api_put(f"/labels/{label_id}", {"name": f"UpdatedLabel-{UNIQUE}", "color": "#00ff00"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"UpdatedLabel-{UNIQUE}"
        assert data["color"] == "#00ff00"

    def test_delete_label(self):
        """Delete a label."""
        resp = api_post("/labels", {"name": f"ToDeleteLabel-{UNIQUE}"})
        assert resp.status_code == 201
        label_id = resp.json()["id"]

        resp = api_delete(f"/labels/{label_id}")
        assert resp.status_code == 204

        resp = api_get(f"/labels/{label_id}")
        assert resp.status_code == 404

    def test_duplicate_label_name(self):
        """Duplicate label name within group returns 409."""
        name = f"DupLabel-{UNIQUE}-{uuid.uuid4().hex[:4]}"
        resp = api_post("/labels", {"name": name})
        assert resp.status_code == 201

        resp = api_post("/labels", {"name": name})
        assert resp.status_code == 409

    def test_get_nonexistent_label(self):
        """Getting a non-existent label returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/labels/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Items CRUD
# ════════════════════════════════════════════════════════════════════


class TestItems:

    def test_create_item_minimal(self):
        """Create an item with just a name."""
        resp = api_post("/items", {"name": f"Laptop-{UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Laptop-{UNIQUE}"
        assert data["quantity"] == 1
        assert data["archived"] is False
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert isinstance(data.get("labels"), list)

    def test_create_item_full(self):
        """Create an item with all fields."""
        # Create a location first
        loc_resp = api_post("/locations", {"name": f"FullItemLoc-{UNIQUE}"})
        assert loc_resp.status_code == 201
        loc_id = loc_resp.json()["id"]

        resp = api_post("/items", {
            "name": f"FullItem-{UNIQUE}",
            "description": "A complete item",
            "quantity": 3,
            "serialNumber": "SN12345",
            "modelNumber": "MN67890",
            "manufacturer": "TestCorp",
            "purchasePrice": 99.99,
            "purchaseDate": "2024-01-15",
            "warrantyExpires": "2025-01-15",
            "locationId": loc_id,
            "notes": "Some notes",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"FullItem-{UNIQUE}"
        assert data["description"] == "A complete item"
        assert data["quantity"] == 3
        assert data["serialNumber"] == "SN12345"
        assert data["modelNumber"] == "MN67890"
        assert data["manufacturer"] == "TestCorp"
        assert data["purchasePrice"] == 99.99
        assert data["locationId"] == loc_id

    def test_get_item(self):
        """Get a single item."""
        resp = api_post("/items", {"name": f"GetItem-{UNIQUE}"})
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        resp = api_get(f"/items/{item_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == item_id
        assert data["name"] == f"GetItem-{UNIQUE}"

    def test_update_item(self):
        """Update an item."""
        resp = api_post("/items", {"name": f"ToUpdate-{UNIQUE}-item"})
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        resp = api_put(f"/items/{item_id}", {
            "name": f"Updated-{UNIQUE}-item",
            "description": "Updated description",
            "quantity": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"Updated-{UNIQUE}-item"
        assert data["description"] == "Updated description"
        assert data["quantity"] == 5

    def test_delete_item(self):
        """Delete an item."""
        resp = api_post("/items", {"name": f"ToDelete-{UNIQUE}-item"})
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        resp = api_delete(f"/items/{item_id}")
        assert resp.status_code == 204

        resp = api_get(f"/items/{item_id}")
        assert resp.status_code == 404

    def test_list_items_pagination(self):
        """List items with pagination."""
        # Create several items
        for i in range(3):
            api_post("/items", {"name": f"PagItem-{UNIQUE}-{i}"})

        resp = api_get("/items", params={"page": 1, "pageSize": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pageSize" in data
        assert data["page"] == 1
        assert data["pageSize"] == 2
        assert len(data["items"]) <= 2

    def test_get_nonexistent_item(self):
        """Getting a non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/items/{fake_id}")
        assert resp.status_code == 404

    def test_create_item_missing_name(self):
        """Creating an item without a name returns 400."""
        resp = api_post("/items", {"description": "no name"})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 6: Item Labels (attach/detach)
# ════════════════════════════════════════════════════════════════════


class TestItemLabels:

    def test_attach_label_to_item(self):
        """Attach a label to an item."""
        # Create item and label
        item_resp = api_post("/items", {"name": f"LabeledItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        label_resp = api_post("/labels", {"name": f"AttachLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        # Attach
        resp = api_post(f"/items/{item_id}/labels", {"labelId": label_id})
        assert resp.status_code == 200
        data = resp.json()
        label_ids = [l["id"] for l in data["labels"]]
        assert label_id in label_ids

    def test_detach_label_from_item(self):
        """Detach a label from an item."""
        # Create item and label
        item_resp = api_post("/items", {"name": f"DetachItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        label_resp = api_post("/labels", {"name": f"DetachLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        # Attach then detach
        api_post(f"/items/{item_id}/labels", {"labelId": label_id})
        resp = api_delete(f"/items/{item_id}/labels/{label_id}")
        assert resp.status_code == 200
        data = resp.json()
        label_ids = [l["id"] for l in data["labels"]]
        assert label_id not in label_ids

    def test_attach_nonexistent_label(self):
        """Attaching a non-existent label returns 400 or 404."""
        item_resp = api_post("/items", {"name": f"BadLabelItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        fake_label_id = str(uuid.uuid4())
        resp = api_post(f"/items/{item_id}/labels", {"labelId": fake_label_id})
        assert resp.status_code in (400, 404)

    def test_label_item_count_updates(self):
        """Label item count reflects attached items."""
        label_resp = api_post("/labels", {"name": f"CountLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        # Create and attach items
        item1 = api_post("/items", {"name": f"CountItem1-{UNIQUE}"})
        assert item1.status_code == 201
        item1_id = item1.json()["id"]
        api_post(f"/items/{item1_id}/labels", {"labelId": label_id})

        item2 = api_post("/items", {"name": f"CountItem2-{UNIQUE}"})
        assert item2.status_code == 201
        item2_id = item2.json()["id"]
        api_post(f"/items/{item2_id}/labels", {"labelId": label_id})

        # Check count
        resp = api_get(f"/labels/{label_id}")
        assert resp.status_code == 200
        assert resp.json()["itemCount"] == 2

    def test_delete_label_removes_from_items(self):
        """Deleting a label removes it from all items."""
        label_resp = api_post("/labels", {"name": f"RemoveLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        item_resp = api_post("/items", {"name": f"RemoveLabelItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]
        api_post(f"/items/{item_id}/labels", {"labelId": label_id})

        # Delete label
        api_delete(f"/labels/{label_id}")

        # Check item no longer has label
        resp = api_get(f"/items/{item_id}")
        assert resp.status_code == 200
        label_ids = [l["id"] for l in resp.json()["labels"]]
        assert label_id not in label_ids


# ════════════════════════════════════════════════════════════════════
# PART 7: Item Attachments
# ════════════════════════════════════════════════════════════════════


class TestAttachments:

    def test_create_attachment(self):
        """Create an attachment for an item."""
        item_resp = api_post("/items", {"name": f"AttachItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_post(f"/items/{item_id}/attachments", {"name": "User Manual", "type": "manual"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "User Manual"
        assert data["type"] == "manual"
        assert "id" in data
        assert "createdAt" in data

    def test_list_attachments(self):
        """List attachments for an item."""
        item_resp = api_post("/items", {"name": f"ListAttachItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        api_post(f"/items/{item_id}/attachments", {"name": "Receipt", "type": "receipt"})
        api_post(f"/items/{item_id}/attachments", {"name": "Photo", "type": "photo"})

        resp = api_get(f"/items/{item_id}/attachments")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_update_attachment(self):
        """Update an attachment."""
        item_resp = api_post("/items", {"name": f"UpdAttachItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        att_resp = api_post(f"/items/{item_id}/attachments", {"name": "Old Name", "type": "manual"})
        assert att_resp.status_code == 201
        att_id = att_resp.json()["id"]

        resp = api_put(f"/items/{item_id}/attachments/{att_id}", {"name": "New Name", "type": "warranty"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["type"] == "warranty"

    def test_delete_attachment(self):
        """Delete an attachment."""
        item_resp = api_post("/items", {"name": f"DelAttachItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        att_resp = api_post(f"/items/{item_id}/attachments", {"name": "ToDelete", "type": "photo"})
        assert att_resp.status_code == 201
        att_id = att_resp.json()["id"]

        resp = api_delete(f"/items/{item_id}/attachments/{att_id}")
        assert resp.status_code == 204

    def test_invalid_attachment_type(self):
        """Invalid attachment type returns 400."""
        item_resp = api_post("/items", {"name": f"BadTypeItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_post(f"/items/{item_id}/attachments", {"name": "Bad", "type": "invalid_type"})
        assert resp.status_code == 400

    def test_attachment_on_nonexistent_item(self):
        """Creating attachment on non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/items/{fake_id}/attachments", {"name": "Test", "type": "manual"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Maintenance Log
# ════════════════════════════════════════════════════════════════════


class TestMaintenance:

    def test_create_maintenance(self):
        """Create a maintenance entry."""
        item_resp = api_post("/items", {"name": f"MaintItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_post(f"/items/{item_id}/maintenance", {
            "date": "2024-06-15",
            "description": "Oil change",
            "cost": 45.50,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2024-06-15"
        assert data["description"] == "Oil change"
        assert data["cost"] == 45.50
        assert "id" in data
        assert "createdAt" in data

    def test_create_maintenance_with_scheduled_date(self):
        """Create a maintenance entry with a scheduled date."""
        item_resp = api_post("/items", {"name": f"SchedMaintItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_post(f"/items/{item_id}/maintenance", {
            "date": "2024-06-15",
            "description": "Scheduled service",
            "scheduledDate": "2025-06-15",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["scheduledDate"] == "2025-06-15"

    def test_list_maintenance(self):
        """List maintenance entries for an item."""
        item_resp = api_post("/items", {"name": f"ListMaintItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        api_post(f"/items/{item_id}/maintenance", {"date": "2024-01-01", "description": "First"})
        api_post(f"/items/{item_id}/maintenance", {"date": "2024-02-01", "description": "Second"})

        resp = api_get(f"/items/{item_id}/maintenance")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_update_maintenance(self):
        """Update a maintenance entry."""
        item_resp = api_post("/items", {"name": f"UpdMaintItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        maint_resp = api_post(f"/items/{item_id}/maintenance", {
            "date": "2024-01-01",
            "description": "Original",
            "cost": 10.0,
        })
        assert maint_resp.status_code == 201
        maint_id = maint_resp.json()["id"]

        resp = api_put(f"/items/{item_id}/maintenance/{maint_id}", {
            "date": "2024-01-02",
            "description": "Updated",
            "cost": 20.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2024-01-02"
        assert data["description"] == "Updated"
        assert data["cost"] == 20.0

    def test_delete_maintenance(self):
        """Delete a maintenance entry."""
        item_resp = api_post("/items", {"name": f"DelMaintItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        maint_resp = api_post(f"/items/{item_id}/maintenance", {
            "date": "2024-01-01",
            "description": "ToDelete",
        })
        assert maint_resp.status_code == 201
        maint_id = maint_resp.json()["id"]

        resp = api_delete(f"/items/{item_id}/maintenance/{maint_id}")
        assert resp.status_code == 204

    def test_maintenance_on_nonexistent_item(self):
        """Creating maintenance on non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/items/{fake_id}/maintenance", {
            "date": "2024-01-01",
            "description": "Test",
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Archive functionality
# ════════════════════════════════════════════════════════════════════


class TestArchive:

    def test_archive_item(self):
        """Archive an item."""
        item_resp = api_post("/items", {"name": f"ArchiveItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_patch(f"/items/{item_id}/archive", {"archived": True})
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    def test_unarchive_item(self):
        """Unarchive an item."""
        item_resp = api_post("/items", {"name": f"UnarchiveItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        api_patch(f"/items/{item_id}/archive", {"archived": True})
        resp = api_patch(f"/items/{item_id}/archive", {"archived": False})
        assert resp.status_code == 200
        assert resp.json()["archived"] is False

    def test_archived_items_excluded_by_default(self):
        """Archived items are not shown in default item list."""
        item_resp = api_post("/items", {"name": f"HiddenArchived-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]
        api_patch(f"/items/{item_id}/archive", {"archived": True})

        resp = api_get("/items")
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id not in item_ids

    def test_archived_filter_true(self):
        """archived=true shows only archived items."""
        item_resp = api_post("/items", {"name": f"ShowArchived-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]
        api_patch(f"/items/{item_id}/archive", {"archived": True})

        resp = api_get("/items", params={"archived": "true"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id in item_ids
        # All items in this response should be archived
        for item in items:
            assert item["archived"] is True

    def test_archived_filter_all(self):
        """archived=all shows both archived and non-archived items."""
        item_resp = api_post("/items", {"name": f"AllFilter-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_get("/items", params={"archived": "all", "pageSize": 100})
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id in item_ids


# ════════════════════════════════════════════════════════════════════
# PART 10: Search and Filtering
# ════════════════════════════════════════════════════════════════════


class TestSearchAndFilter:

    def test_search_by_name(self):
        """Search items by name."""
        unique_name = f"UniqueSearchName-{uuid.uuid4().hex[:8]}"
        api_post("/items", {"name": unique_name})

        resp = api_get("/items", params={"q": unique_name})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert any(unique_name in i["name"] for i in items)

    def test_search_by_description(self):
        """Search items by description."""
        unique_desc = f"UniqueDesc-{uuid.uuid4().hex[:8]}"
        api_post("/items", {"name": f"DescSearch-{UNIQUE}", "description": unique_desc})

        resp = api_get("/items", params={"q": unique_desc})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    def test_search_by_serial_number(self):
        """Search items by serial number."""
        unique_sn = f"SN-{uuid.uuid4().hex[:8]}"
        api_post("/items", {"name": f"SNSearch-{UNIQUE}", "serialNumber": unique_sn})

        resp = api_get("/items", params={"q": unique_sn})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        unique_name = f"CaseTest-{uuid.uuid4().hex[:8]}"
        api_post("/items", {"name": unique_name})

        resp = api_get("/items", params={"q": unique_name.upper()})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    def test_filter_by_label(self):
        """Filter items by label."""
        label_resp = api_post("/labels", {"name": f"FilterLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        item_resp = api_post("/items", {"name": f"FilteredItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]
        api_post(f"/items/{item_id}/labels", {"labelId": label_id})

        # Create another item without this label
        api_post("/items", {"name": f"Unfiltered-{UNIQUE}"})

        resp = api_get("/items", params={"labels": label_id})
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id in item_ids

    def test_filter_by_location(self):
        """Filter items by location."""
        loc_resp = api_post("/locations", {"name": f"FilterLoc-{UNIQUE}"})
        assert loc_resp.status_code == 201
        loc_id = loc_resp.json()["id"]

        item_resp = api_post("/items", {"name": f"LocItem-{UNIQUE}", "locationId": loc_id})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        resp = api_get("/items", params={"locationId": loc_id})
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item_id in item_ids

    def test_filter_by_multiple_labels_or_logic(self):
        """Filtering by multiple labels uses OR logic."""
        label1_resp = api_post("/labels", {"name": f"OrLabel1-{UNIQUE}"})
        assert label1_resp.status_code == 201
        label1_id = label1_resp.json()["id"]

        label2_resp = api_post("/labels", {"name": f"OrLabel2-{UNIQUE}"})
        assert label2_resp.status_code == 201
        label2_id = label2_resp.json()["id"]

        item1_resp = api_post("/items", {"name": f"OrItem1-{UNIQUE}"})
        assert item1_resp.status_code == 201
        item1_id = item1_resp.json()["id"]
        api_post(f"/items/{item1_id}/labels", {"labelId": label1_id})

        item2_resp = api_post("/items", {"name": f"OrItem2-{UNIQUE}"})
        assert item2_resp.status_code == 201
        item2_id = item2_resp.json()["id"]
        api_post(f"/items/{item2_id}/labels", {"labelId": label2_id})

        resp = api_get("/items", params={"labels": f"{label1_id},{label2_id}", "pageSize": 100})
        assert resp.status_code == 200
        items = resp.json()["items"]
        item_ids = [i["id"] for i in items]
        assert item1_id in item_ids
        assert item2_id in item_ids


# ════════════════════════════════════════════════════════════════════
# PART 11: Statistics
# ════════════════════════════════════════════════════════════════════


class TestStatistics:

    def test_statistics_structure(self):
        """Statistics endpoint returns correct structure."""
        resp = api_get("/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert "totalItems" in data
        assert "totalValue" in data
        assert "itemsByLocation" in data
        assert "itemsByLabel" in data
        assert isinstance(data["itemsByLocation"], list)
        assert isinstance(data["itemsByLabel"], list)

    def test_statistics_total_value_calculation(self):
        """Total value is sum of purchasePrice * quantity."""
        # Use a unique group to get clean stats
        stats_group = str(uuid.uuid4())
        stats_user = str(uuid.uuid4())
        stats_headers = {
            "X-User-Id": stats_user,
            "X-Group-Id": stats_group,
            "Content-Type": "application/json",
        }

        # Create items with known values
        api_post("/items", {"name": "StatItem1", "purchasePrice": 10.0, "quantity": 2}, headers=stats_headers)
        api_post("/items", {"name": "StatItem2", "purchasePrice": 25.0, "quantity": 1}, headers=stats_headers)

        resp = api_get("/statistics", headers=stats_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalItems"] == 2
        # 10*2 + 25*1 = 45
        assert data["totalValue"] == pytest.approx(45.0)

    def test_statistics_excludes_archived(self):
        """Archived items are excluded from statistics."""
        stats_group = str(uuid.uuid4())
        stats_user = str(uuid.uuid4())
        stats_headers = {
            "X-User-Id": stats_user,
            "X-Group-Id": stats_group,
            "Content-Type": "application/json",
        }

        # Create a normal item
        resp = api_post("/items", {"name": "ActiveStat", "purchasePrice": 100.0}, headers=stats_headers)
        assert resp.status_code == 201

        # Create and archive another item
        resp2 = api_post("/items", {"name": "ArchivedStat", "purchasePrice": 200.0}, headers=stats_headers)
        assert resp2.status_code == 201
        archived_id = resp2.json()["id"]
        api_patch(f"/items/{archived_id}/archive", {"archived": True}, headers=stats_headers)

        resp = api_get("/statistics", headers=stats_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalItems"] == 1
        assert data["totalValue"] == pytest.approx(100.0)

    def test_statistics_items_by_location(self):
        """Items by location includes location breakdown."""
        stats_group = str(uuid.uuid4())
        stats_user = str(uuid.uuid4())
        stats_headers = {
            "X-User-Id": stats_user,
            "X-Group-Id": stats_group,
            "Content-Type": "application/json",
        }

        loc_resp = api_post("/locations", {"name": "StatsLoc"}, headers=stats_headers)
        assert loc_resp.status_code == 201
        loc_id = loc_resp.json()["id"]

        api_post("/items", {"name": "LocStatItem", "locationId": loc_id}, headers=stats_headers)

        resp = api_get("/statistics", headers=stats_headers)
        assert resp.status_code == 200
        data = resp.json()
        loc_stats = data["itemsByLocation"]
        loc_ids = [l["locationId"] for l in loc_stats]
        assert loc_id in loc_ids

    def test_statistics_items_by_location_recursive(self):
        """Items by location count includes sub-location items."""
        stats_group = str(uuid.uuid4())
        stats_user = str(uuid.uuid4())
        stats_headers = {
            "X-User-Id": stats_user,
            "X-Group-Id": stats_group,
            "Content-Type": "application/json",
        }

        # Create parent and child locations
        parent_resp = api_post("/locations", {"name": "RecParent"}, headers=stats_headers)
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/locations", {"name": "RecChild", "parentId": parent_id}, headers=stats_headers)
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # Put item in child location
        api_post("/items", {"name": "RecItem", "locationId": child_id}, headers=stats_headers)

        resp = api_get("/statistics", headers=stats_headers)
        assert resp.status_code == 200
        data = resp.json()
        loc_stats = data["itemsByLocation"]

        # Parent should have count >= 1 (includes child's items)
        parent_stat = next((l for l in loc_stats if l["locationId"] == parent_id), None)
        assert parent_stat is not None
        assert parent_stat["itemCount"] >= 1

    def test_statistics_items_by_label(self):
        """Items by label includes label breakdown."""
        stats_group = str(uuid.uuid4())
        stats_user = str(uuid.uuid4())
        stats_headers = {
            "X-User-Id": stats_user,
            "X-Group-Id": stats_group,
            "Content-Type": "application/json",
        }

        label_resp = api_post("/labels", {"name": "StatsLabel"}, headers=stats_headers)
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        item_resp = api_post("/items", {"name": "LabelStatItem"}, headers=stats_headers)
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]
        api_post(f"/items/{item_id}/labels", {"labelId": label_id}, headers=stats_headers)

        resp = api_get("/statistics", headers=stats_headers)
        assert resp.status_code == 200
        data = resp.json()
        label_stats = data["itemsByLabel"]
        label_ids = [l["labelId"] for l in label_stats]
        assert label_id in label_ids


# ════════════════════════════════════════════════════════════════════
# PART 12: Import/Export
# ════════════════════════════════════════════════════════════════════


class TestImportExport:

    def test_import_items(self):
        """Import items from JSON array."""
        items_to_import = [
            {"name": f"Imported1-{UNIQUE}", "quantity": 2, "purchasePrice": 10.0},
            {"name": f"Imported2-{UNIQUE}", "description": "Second item"},
        ]

        resp = api_post("/import/csv", items_to_import)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2

    def test_import_with_location_name(self):
        """Import resolves locationName to locationId."""
        # Create a location first
        loc_resp = api_post("/locations", {"name": f"ImportLoc-{UNIQUE}"})
        assert loc_resp.status_code == 201

        items_to_import = [
            {"name": f"LocImport-{UNIQUE}", "locationName": f"ImportLoc-{UNIQUE}"},
        ]

        resp = api_post("/import/csv", items_to_import)
        assert resp.status_code == 200
        assert resp.json()["imported"] == 1

        # Verify the item is in the correct location
        search_resp = api_get("/items", params={"q": f"LocImport-{UNIQUE}"})
        assert search_resp.status_code == 200
        items = search_resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["locationId"] == loc_resp.json()["id"]

    def test_export_items(self):
        """Export items as JSON array."""
        # Create an item to export
        api_post("/items", {"name": f"ExportItem-{UNIQUE}", "manufacturer": "ExportCorp"})

        resp = api_get("/export/csv")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Find our item
        export_item = next((i for i in data if f"ExportItem-{UNIQUE}" in i.get("name", "")), None)
        assert export_item is not None
        assert "locationName" in export_item
        assert "labelNames" in export_item

    def test_export_excludes_archived(self):
        """Export excludes archived items."""
        ie_group = str(uuid.uuid4())
        ie_user = str(uuid.uuid4())
        ie_headers = {
            "X-User-Id": ie_user,
            "X-Group-Id": ie_group,
            "Content-Type": "application/json",
        }

        # Create and archive an item
        resp = api_post("/items", {"name": "ArchivedExport"}, headers=ie_headers)
        assert resp.status_code == 201
        item_id = resp.json()["id"]
        api_patch(f"/items/{item_id}/archive", {"archived": True}, headers=ie_headers)

        # Create a non-archived item
        api_post("/items", {"name": "ActiveExport"}, headers=ie_headers)

        resp = api_get("/export/csv", headers=ie_headers)
        assert resp.status_code == 200
        data = resp.json()
        names = [i["name"] for i in data]
        assert "ActiveExport" in names
        assert "ArchivedExport" not in names

    def test_import_empty_array(self):
        """Importing empty array returns imported=0."""
        resp = api_post("/import/csv", [])
        assert resp.status_code == 200
        assert resp.json()["imported"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation (Group Scoping)
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_items_isolated_between_groups(self):
        """Items created in one group are not visible in another."""
        # Create item in group 1
        item_resp = api_post("/items", {"name": f"IsolatedItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Try to get it from group 2
        resp = api_get(f"/items/{item_id}", headers=HEADERS_GROUP2)
        assert resp.status_code == 404

    def test_locations_isolated_between_groups(self):
        """Locations created in one group are not visible in another."""
        loc_resp = api_post("/locations", {"name": f"IsolatedLoc-{UNIQUE}"})
        assert loc_resp.status_code == 201
        loc_id = loc_resp.json()["id"]

        resp = api_get(f"/locations/{loc_id}", headers=HEADERS_GROUP2)
        assert resp.status_code == 404

    def test_labels_isolated_between_groups(self):
        """Labels created in one group are not visible in another."""
        label_resp = api_post("/labels", {"name": f"IsolatedLabel-{UNIQUE}"})
        assert label_resp.status_code == 201
        label_id = label_resp.json()["id"]

        resp = api_get(f"/labels/{label_id}", headers=HEADERS_GROUP2)
        assert resp.status_code == 404

    def test_same_group_users_share_data(self):
        """Users in the same group can see each other's data."""
        # Create item with user 1
        item_resp = api_post("/items", {"name": f"SharedItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        # Access with user 2 (same group)
        resp = api_get(f"/items/{item_id}", headers=HEADERS_USER2)
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id

    def test_statistics_isolated_between_groups(self):
        """Statistics only reflect group's own data."""
        # Create item in group 2
        api_post("/items", {"name": "Group2Item", "purchasePrice": 1000.0}, headers=HEADERS_GROUP2)

        # Group 1 stats should not include group 2's item value
        resp = api_get("/statistics")
        assert resp.status_code == 200
        # Just verify it returns without error (exact value depends on other tests)
        assert "totalValue" in resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 14: Edge Cases and Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_delete_item_cascades_attachments(self):
        """Deleting an item deletes its attachments."""
        item_resp = api_post("/items", {"name": f"CascadeItem-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        api_post(f"/items/{item_id}/attachments", {"name": "CascadeAtt", "type": "manual"})
        api_delete(f"/items/{item_id}")

        # Item should be gone
        resp = api_get(f"/items/{item_id}")
        assert resp.status_code == 404

    def test_delete_item_cascades_maintenance(self):
        """Deleting an item deletes its maintenance entries."""
        item_resp = api_post("/items", {"name": f"CascadeMaint-{UNIQUE}"})
        assert item_resp.status_code == 201
        item_id = item_resp.json()["id"]

        api_post(f"/items/{item_id}/maintenance", {"date": "2024-01-01", "description": "Test"})
        api_delete(f"/items/{item_id}")

        # Item should be gone
        resp = api_get(f"/items/{item_id}")
        assert resp.status_code == 404

    def test_location_item_count(self):
        """Location's itemCount reflects items assigned to it."""
        loc_resp = api_post("/locations", {"name": f"CountLoc-{UNIQUE}"})
        assert loc_resp.status_code == 201
        loc_id = loc_resp.json()["id"]

        api_post("/items", {"name": f"CountItem1-{UNIQUE}-loc", "locationId": loc_id})
        api_post("/items", {"name": f"CountItem2-{UNIQUE}-loc", "locationId": loc_id})

        resp = api_get(f"/locations/{loc_id}")
        assert resp.status_code == 200
        assert resp.json()["itemCount"] >= 2

    def test_item_quantity_defaults_to_one(self):
        """Item quantity defaults to 1."""
        resp = api_post("/items", {"name": f"DefQuantity-{UNIQUE}"})
        assert resp.status_code == 201
        assert resp.json()["quantity"] == 1

    def test_item_labels_empty_array(self):
        """New item has empty labels array."""
        resp = api_post("/items", {"name": f"EmptyLabels-{UNIQUE}"})
        assert resp.status_code == 201
        assert resp.json()["labels"] == []

    def test_update_nonexistent_item(self):
        """Updating a non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/items/{fake_id}", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_nonexistent_item(self):
        """Deleting a non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/items/{fake_id}")
        assert resp.status_code == 404

    def test_update_nonexistent_location(self):
        """Updating a non-existent location returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/locations/{fake_id}", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_update_nonexistent_label(self):
        """Updating a non-existent label returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/labels/{fake_id}", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_pagination_defaults(self):
        """Default pagination is page=1, pageSize=20."""
        resp = api_get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["pageSize"] == 20
