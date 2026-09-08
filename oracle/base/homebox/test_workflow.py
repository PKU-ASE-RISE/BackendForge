"""
BackendForge — L3 Workflow Tests for Homebox Task

Multi-step adversarial workflows that cross 3+ entity types.
Each test: 6-12 steps, 12-20 assertions, covers 2+ bug patterns.

Target patterns:
- Pattern 1: camelCase fields
- Pattern 2: Nested data completeness
- Pattern 3: Filter/search actually implemented
- Pattern 5: Computed values (statistics, counts)
- Pattern 6: Data isolation
- Pattern 7: Cascade deletes and side effects
- Pattern 8: Unique constraints, ordering
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

RUN_ID = uuid.uuid4().hex[:8]


def make_headers(group_id=None, user_id=None):
    return {
        "X-User-Id": user_id or str(uuid.uuid4()),
        "X-Group-Id": group_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=REQUEST_TIMEOUT)


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers, timeout=REQUEST_TIMEOUT)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers, timeout=REQUEST_TIMEOUT)


def patch(path, json=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json, headers=headers, timeout=REQUEST_TIMEOUT)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=REQUEST_TIMEOUT)


class TestFullItemLifecycle:
    """Pattern 1+2+7: Create item → add labels/attachments/maintenance → delete cascades all."""

    def test_item_with_all_relations_cascade_delete(self):
        """Full item lifecycle: create with location/labels/attachments/maintenance, then delete."""
        h = make_headers()

        # 1. Create location
        r = post("/locations", {"name": "LifecycleLoc"}, headers=h)
        assert r.status_code == 201
        loc_id = r.json()["id"]

        # 2. Create label
        r = post("/labels", {"name": "LifecycleLbl"}, headers=h)
        assert r.status_code == 201
        label_id = r.json()["id"]

        # 3. Create item in location
        r = post("/items", {
            "name": "LifecycleItem",
            "locationId": loc_id,
            "purchasePrice": 50.0,
            "quantity": 2,
            "serialNumber": "SN-LIFE",
        }, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]
        assert r.json()["locationId"] == loc_id
        assert r.json()["serialNumber"] == "SN-LIFE"

        # 4. Attach label
        r = post(f"/items/{item_id}/labels", {"labelId": label_id}, headers=h)
        assert r.status_code == 200
        assert len(r.json()["labels"]) == 1

        # 5. Add attachment
        r = post(f"/items/{item_id}/attachments", {"name": "Manual", "type": "manual"}, headers=h)
        assert r.status_code == 201
        att_id = r.json()["id"]

        # 6. Add maintenance entry
        r = post(f"/items/{item_id}/maintenance", {
            "date": "2024-01-15",
            "description": "Initial setup",
            "cost": 10.0,
        }, headers=h)
        assert r.status_code == 201
        mnt_id = r.json()["id"]

        # 7. Verify statistics include this item
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 1
        assert r.json()["totalValue"] == pytest.approx(100.0)  # 50 * 2

        # 8. Delete item
        r = delete(f"/items/{item_id}", headers=h)
        assert r.status_code == 204

        # 9. Verify item gone
        r = get(f"/items/{item_id}", headers=h)
        assert r.status_code == 404

        # 10. Verify attachments endpoint also 404 (item gone)
        r = get(f"/items/{item_id}/attachments", headers=h)
        assert r.status_code == 404

        # 11. Verify maintenance endpoint also 404 (item gone)
        r = get(f"/items/{item_id}/maintenance", headers=h)
        assert r.status_code == 404

        # 12. Statistics should now show 0
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 0
        assert r.json()["totalValue"] == pytest.approx(0.0)

        # 13. Label itemCount should be 0 now
        r = get(f"/labels/{label_id}", headers=h)
        assert r.status_code == 200
        assert r.json()["itemCount"] == 0


class TestLocationHierarchyWithStatistics:
    """Pattern 2+5: Location tree + recursive item counting in statistics."""

    def test_recursive_item_count_in_statistics(self):
        """Statistics itemsByLocation must count items recursively through hierarchy."""
        h = make_headers()

        # 1. Create hierarchy: House → Room → Shelf
        r = post("/locations", {"name": "House"}, headers=h)
        assert r.status_code == 201
        house_id = r.json()["id"]

        r = post("/locations", {"name": "Room", "parentId": house_id}, headers=h)
        assert r.status_code == 201
        room_id = r.json()["id"]

        r = post("/locations", {"name": "Shelf", "parentId": room_id}, headers=h)
        assert r.status_code == 201
        shelf_id = r.json()["id"]

        # 2. Place items at different levels
        post("/items", {"name": "HouseItem", "locationId": house_id}, headers=h)
        post("/items", {"name": "RoomItem", "locationId": room_id}, headers=h)
        post("/items", {"name": "ShelfItem1", "locationId": shelf_id}, headers=h)
        post("/items", {"name": "ShelfItem2", "locationId": shelf_id}, headers=h)

        # 3. Verify statistics
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["totalItems"] == 4

        loc_stats = {l["locationId"]: l["itemCount"] for l in data["itemsByLocation"]}

        # House should have >= 4 (1 direct + 1 room + 2 shelf)
        assert loc_stats.get(house_id, 0) >= 4
        # Room should have >= 3 (1 direct + 2 shelf)
        assert loc_stats.get(room_id, 0) >= 3
        # Shelf should have exactly 2
        assert loc_stats.get(shelf_id, 0) == 2

        # 4. Verify itemsByLocation entries have correct camelCase fields
        for entry in data["itemsByLocation"]:
            assert "locationId" in entry
            assert "locationName" in entry
            assert "itemCount" in entry


class TestArchiveExclusionWorkflow:
    """Pattern 3+5+7: Archive item → verify excluded from stats, list, export."""

    def test_archive_excludes_from_all_computed_views(self):
        """Archived items must be excluded from statistics, export, and default list."""
        h = make_headers()

        # 1. Create location and label
        r = post("/locations", {"name": "ArchLoc"}, headers=h)
        assert r.status_code == 201
        loc_id = r.json()["id"]

        r = post("/labels", {"name": "ArchLbl"}, headers=h)
        assert r.status_code == 201
        label_id = r.json()["id"]

        # 2. Create two items
        r = post("/items", {"name": "KeepActive", "purchasePrice": 100.0, "locationId": loc_id}, headers=h)
        assert r.status_code == 201
        active_id = r.json()["id"]
        post(f"/items/{active_id}/labels", {"labelId": label_id}, headers=h)

        r = post("/items", {"name": "WillArchive", "purchasePrice": 200.0, "locationId": loc_id}, headers=h)
        assert r.status_code == 201
        archive_id = r.json()["id"]
        post(f"/items/{archive_id}/labels", {"labelId": label_id}, headers=h)

        # 3. Archive one item
        r = patch(f"/items/{archive_id}/archive", {"archived": True}, headers=h)
        assert r.status_code == 200
        assert r.json()["archived"] is True

        # 4. Default item list excludes archived
        r = get("/items", headers=h)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["items"]]
        assert active_id in ids
        assert archive_id not in ids

        # 5. Statistics exclude archived
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        stats = r.json()
        assert stats["totalItems"] == 1
        assert stats["totalValue"] == pytest.approx(100.0)

        # 6. Export excludes archived
        r = get("/export/csv", headers=h)
        assert r.status_code == 200
        export_names = [i["name"] for i in r.json()]
        assert "KeepActive" in export_names
        assert "WillArchive" not in export_names

        # 7. Statistics itemsByLocation only counts non-archived
        loc_stats = {l["locationId"]: l["itemCount"] for l in stats["itemsByLocation"]}
        if loc_id in loc_stats:
            assert loc_stats[loc_id] == 1

        # 8. Location itemCount only counts non-archived
        r = get(f"/locations/{loc_id}", headers=h)
        assert r.status_code == 200
        assert r.json()["itemCount"] == 1

        # 9. Unarchive and verify restored
        r = patch(f"/items/{archive_id}/archive", {"archived": False}, headers=h)
        assert r.status_code == 200
        assert r.json()["archived"] is False

        # 10. Statistics restored
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 2
        assert r.json()["totalValue"] == pytest.approx(300.0)


class TestLabelDeleteSideEffects:
    """Pattern 7: Deleting a label removes it from all items."""

    def test_delete_label_removes_from_all_items(self):
        """When a label is deleted, items lose that label but keep others."""
        h = make_headers()

        # 1. Create two labels
        r = post("/labels", {"name": "LabelToKeep"}, headers=h)
        assert r.status_code == 201
        keep_id = r.json()["id"]

        r = post("/labels", {"name": "LabelToDelete"}, headers=h)
        assert r.status_code == 201
        del_id = r.json()["id"]

        # 2. Create item and attach both labels
        r = post("/items", {"name": "MultiLabelItem"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        post(f"/items/{item_id}/labels", {"labelId": keep_id}, headers=h)
        post(f"/items/{item_id}/labels", {"labelId": del_id}, headers=h)

        # 3. Verify item has both labels
        r = get(f"/items/{item_id}", headers=h)
        assert r.status_code == 200
        label_ids = [l["id"] for l in r.json()["labels"]]
        assert keep_id in label_ids
        assert del_id in label_ids

        # 4. Delete one label
        r = delete(f"/labels/{del_id}", headers=h)
        assert r.status_code == 204

        # 5. Verify label is gone
        r = get(f"/labels/{del_id}", headers=h)
        assert r.status_code == 404

        # 6. Verify item lost the deleted label but kept the other
        r = get(f"/items/{item_id}", headers=h)
        assert r.status_code == 200
        label_ids = [l["id"] for l in r.json()["labels"]]
        assert del_id not in label_ids
        assert keep_id in label_ids

        # 7. Statistics should reflect the change
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        label_stats = r.json()["itemsByLabel"]
        stat_label_ids = [l["labelId"] for l in label_stats]
        assert del_id not in stat_label_ids


class TestImportExportRoundtrip:
    """Pattern 1+5: Import items → verify creation → export → verify format."""

    def test_import_then_export_consistency(self):
        """Items imported should be exportable with correct field mapping."""
        h = make_headers()

        # 1. Create location for import
        r = post("/locations", {"name": "ImportLoc"}, headers=h)
        assert r.status_code == 201

        # 2. Import items
        import_data = [
            {"name": "ImportedA", "purchasePrice": 15.5, "quantity": 2, "locationName": "ImportLoc"},
            {"name": "ImportedB", "description": "Second item", "serialNumber": "IMP-SN-2"},
            {"name": "ImportedC", "manufacturer": "TestMfg"},
        ]
        r = post("/import/csv", import_data, headers=h)
        assert r.status_code == 200
        assert r.json()["imported"] == 3

        # 3. Verify items exist by searching
        r = get("/items", params={"q": "ImportedA"}, headers=h)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        item_a = items[0]
        assert item_a["name"] == "ImportedA"
        assert item_a["purchasePrice"] == pytest.approx(15.5)
        assert item_a["quantity"] == 2

        # 4. Verify location was resolved
        assert item_a["locationId"] is not None

        # 5. Export and verify structure
        r = get("/export/csv", headers=h)
        assert r.status_code == 200
        export = r.json()
        assert isinstance(export, list)
        assert len(export) == 3

        # 6. Find ImportedA in export
        exp_a = next((e for e in export if e["name"] == "ImportedA"), None)
        assert exp_a is not None
        assert "locationName" in exp_a
        assert exp_a["locationName"] == "ImportLoc"
        assert "labelNames" in exp_a

        # 7. Verify export has correct camelCase fields
        for item in export:
            assert "id" in item
            assert "name" in item
            assert "purchasePrice" in item or "purchasePrice" in item
            assert "purchase_price" not in item
            assert "serial_number" not in item
            assert "location_name" not in item
            assert "label_names" not in item

        # 8. Statistics should reflect imported items
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 3


class TestMultiGroupIsolation:
    """Pattern 6: Complete data isolation workflow across multiple groups."""

    def test_two_groups_completely_isolated(self):
        """Two groups operate independently — no data leaks."""
        h_a = make_headers()
        h_b = make_headers()

        # 1. Group A creates location + label + item
        r = post("/locations", {"name": "GroupALoc"}, headers=h_a)
        assert r.status_code == 201
        loc_a = r.json()["id"]

        r = post("/labels", {"name": "GroupALabel"}, headers=h_a)
        assert r.status_code == 201
        lbl_a = r.json()["id"]

        r = post("/items", {"name": "GroupAItem", "locationId": loc_a, "purchasePrice": 500.0}, headers=h_a)
        assert r.status_code == 201
        item_a = r.json()["id"]
        post(f"/items/{item_a}/labels", {"labelId": lbl_a}, headers=h_a)

        # 2. Group B creates its own data
        r = post("/locations", {"name": "GroupBLoc"}, headers=h_b)
        assert r.status_code == 201

        r = post("/items", {"name": "GroupBItem", "purchasePrice": 100.0}, headers=h_b)
        assert r.status_code == 201

        # 3. Group B cannot see Group A's item
        r = get(f"/items/{item_a}", headers=h_b)
        assert r.status_code == 404

        # 4. Group B cannot see Group A's location
        r = get(f"/locations/{loc_a}", headers=h_b)
        assert r.status_code == 404

        # 5. Group B cannot see Group A's label
        r = get(f"/labels/{lbl_a}", headers=h_b)
        assert r.status_code == 404

        # 6. Group A statistics isolated
        r = get("/statistics", headers=h_a)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 1
        assert r.json()["totalValue"] == pytest.approx(500.0)

        # 7. Group B statistics isolated
        r = get("/statistics", headers=h_b)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 1
        assert r.json()["totalValue"] == pytest.approx(100.0)

        # 8. Group A export only has A's items
        r = get("/export/csv", headers=h_a)
        assert r.status_code == 200
        names = [i["name"] for i in r.json()]
        assert "GroupAItem" in names
        assert "GroupBItem" not in names


class TestSearchAcrossMultipleFields:
    """Pattern 3+5: Search parameter must work across name, description, serialNumber, modelNumber."""

    def test_search_matches_all_specified_fields(self):
        """q param must search name, description, serialNumber, and modelNumber."""
        h = make_headers()
        unique_token = f"Xq{uuid.uuid4().hex[:6]}"

        # 1. Item found by name
        r = post("/items", {"name": f"Name{unique_token}"}, headers=h)
        assert r.status_code == 201
        name_item = r.json()["id"]

        # 2. Item found by description
        r = post("/items", {"name": "DescItem", "description": f"Desc{unique_token}"}, headers=h)
        assert r.status_code == 201
        desc_item = r.json()["id"]

        # 3. Item found by serialNumber
        r = post("/items", {"name": "SerialItem", "serialNumber": f"SN{unique_token}"}, headers=h)
        assert r.status_code == 201
        serial_item = r.json()["id"]

        # 4. Item found by modelNumber
        r = post("/items", {"name": "ModelItem", "modelNumber": f"MN{unique_token}"}, headers=h)
        assert r.status_code == 201
        model_item = r.json()["id"]

        # 5. Item that should NOT be found
        r = post("/items", {"name": "Unrelated"}, headers=h)
        assert r.status_code == 201
        unrelated = r.json()["id"]

        # 6. Search with the unique token
        r = get("/items", params={"q": unique_token, "pageSize": 100}, headers=h)
        assert r.status_code == 200
        items = r.json()["items"]
        found_ids = [i["id"] for i in items]

        assert name_item in found_ids
        assert desc_item in found_ids
        assert serial_item in found_ids
        assert model_item in found_ids
        assert unrelated not in found_ids


class TestLocationCircularReferencePrevention:
    """Pattern 8: Circular references in location hierarchy must be prevented."""

    def test_prevent_self_reference_and_circular(self):
        """Location cannot be its own parent, and circular chains prevented."""
        h = make_headers()

        # 1. Create A → B → C chain
        r = post("/locations", {"name": "CircA"}, headers=h)
        assert r.status_code == 201
        a_id = r.json()["id"]

        r = post("/locations", {"name": "CircB", "parentId": a_id}, headers=h)
        assert r.status_code == 201
        b_id = r.json()["id"]

        r = post("/locations", {"name": "CircC", "parentId": b_id}, headers=h)
        assert r.status_code == 201
        c_id = r.json()["id"]

        # 2. Self-reference: A.parentId = A → should fail
        r = put(f"/locations/{a_id}", {"name": "CircA", "parentId": a_id}, headers=h)
        assert r.status_code == 400

        # 3. Circular: A.parentId = C (C→B→A→C) → should fail
        r = put(f"/locations/{a_id}", {"name": "CircA", "parentId": c_id}, headers=h)
        assert r.status_code == 400

        # 4. Valid reparenting: C moves to root → should succeed
        r = put(f"/locations/{c_id}", {"name": "CircC", "parentId": None}, headers=h)
        assert r.status_code == 200
        assert r.json()["parentId"] is None


class TestItemUpdatePreservesRelations:
    """Pattern 2+7: Updating item fields must not lose labels or other relations."""

    def test_update_item_preserves_labels(self):
        """PUT /items/{id} must not strip existing labels."""
        h = make_headers()

        # 1. Create label and item
        r = post("/labels", {"name": "PreserveLbl"}, headers=h)
        assert r.status_code == 201
        label_id = r.json()["id"]

        r = post("/items", {"name": "PreserveItem", "purchasePrice": 10.0}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        # 2. Attach label
        r = post(f"/items/{item_id}/labels", {"labelId": label_id}, headers=h)
        assert r.status_code == 200

        # 3. Update item (change name and price)
        r = put(f"/items/{item_id}", {
            "name": "PreserveItemUpdated",
            "purchasePrice": 20.0,
        }, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "PreserveItemUpdated"
        assert data["purchasePrice"] == pytest.approx(20.0)

        # 4. Labels must still be there
        assert "labels" in data
        assert len(data["labels"]) == 1
        assert data["labels"][0]["id"] == label_id

        # 5. GET to double-check
        r = get(f"/items/{item_id}", headers=h)
        assert r.status_code == 200
        assert len(r.json()["labels"]) == 1
        assert r.json()["labels"][0]["id"] == label_id


class TestMaintenanceAndAttachmentWorkflow:
    """Pattern 1+4+7: Full CRUD on maintenance and attachments with proper codes."""

    def test_full_maintenance_and_attachment_lifecycle(self):
        """Create/update/delete maintenance+attachments with correct status codes."""
        h = make_headers()

        # 1. Create item
        r = post("/items", {"name": "MaintAttItem"}, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        # 2. Create maintenance (201)
        r = post(f"/items/{item_id}/maintenance", {
            "date": "2024-03-01",
            "description": "First service",
            "cost": 25.0,
            "scheduledDate": "2024-09-01",
        }, headers=h)
        assert r.status_code == 201
        mnt = r.json()
        mnt_id = mnt["id"]
        assert mnt["scheduledDate"] == "2024-09-01"
        assert "scheduled_date" not in mnt

        # 3. Create attachment (201)
        r = post(f"/items/{item_id}/attachments", {"name": "Receipt.pdf", "type": "receipt"}, headers=h)
        assert r.status_code == 201
        att = r.json()
        att_id = att["id"]
        assert att["type"] == "receipt"
        assert "createdAt" in att

        # 4. Update maintenance (200)
        r = put(f"/items/{item_id}/maintenance/{mnt_id}", {
            "date": "2024-03-15",
            "description": "Updated service",
            "cost": 30.0,
        }, headers=h)
        assert r.status_code == 200
        assert r.json()["cost"] == pytest.approx(30.0)
        assert r.json()["description"] == "Updated service"

        # 5. Update attachment (200)
        r = put(f"/items/{item_id}/attachments/{att_id}", {
            "name": "Warranty.pdf",
            "type": "warranty",
        }, headers=h)
        assert r.status_code == 200
        assert r.json()["name"] == "Warranty.pdf"
        assert r.json()["type"] == "warranty"

        # 6. List maintenance
        r = get(f"/items/{item_id}/maintenance", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 1

        # 7. List attachments
        r = get(f"/items/{item_id}/attachments", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 1

        # 8. Delete maintenance (204)
        r = delete(f"/items/{item_id}/maintenance/{mnt_id}", headers=h)
        assert r.status_code == 204

        # 9. Delete attachment (204)
        r = delete(f"/items/{item_id}/attachments/{att_id}", headers=h)
        assert r.status_code == 204

        # 10. Verify both gone
        r = get(f"/items/{item_id}/maintenance", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 0

        r = get(f"/items/{item_id}/attachments", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 0


class TestStatisticsAccuracyWorkflow:
    """Pattern 5: Statistics must reflect actual data changes in real time."""

    def test_statistics_track_item_changes(self):
        """Statistics update as items are added, modified, archived, deleted."""
        h = make_headers()

        # 1. Start empty
        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 0
        assert r.json()["totalValue"] == pytest.approx(0.0)

        # 2. Add item: price=10, qty=3 → value 30
        r = post("/items", {"name": "StatTrack1", "purchasePrice": 10.0, "quantity": 3}, headers=h)
        assert r.status_code == 201
        item1_id = r.json()["id"]

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 1
        assert r.json()["totalValue"] == pytest.approx(30.0)

        # 3. Add another: price=20, qty=1 → value 20; total=50
        r = post("/items", {"name": "StatTrack2", "purchasePrice": 20.0, "quantity": 1}, headers=h)
        assert r.status_code == 201
        item2_id = r.json()["id"]

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 2
        assert r.json()["totalValue"] == pytest.approx(50.0)

        # 4. Archive item1 → excluded from stats; only item2 remains
        patch(f"/items/{item1_id}/archive", {"archived": True}, headers=h)

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 1
        assert r.json()["totalValue"] == pytest.approx(20.0)

        # 5. Delete item2 → 0 non-archived items
        delete(f"/items/{item2_id}", headers=h)

        r = get("/statistics", headers=h)
        assert r.status_code == 200
        assert r.json()["totalItems"] == 0
        assert r.json()["totalValue"] == pytest.approx(0.0)


class TestPaginationWorkflow:
    """Pattern 3: Pagination must work correctly with total count."""

    def test_pagination_pages_are_consistent(self):
        """Multiple pages should cover all items without duplicates or gaps."""
        h = make_headers()

        # 1. Create exactly 7 items
        item_ids = []
        for i in range(7):
            r = post("/items", {"name": f"PagFlow-{i}"}, headers=h)
            assert r.status_code == 201
            item_ids.append(r.json()["id"])

        # 2. Get page 1, pageSize=3
        r = get("/items", params={"page": 1, "pageSize": 3}, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 7
        assert data["page"] == 1
        assert data["pageSize"] == 3
        assert len(data["items"]) == 3
        page1_ids = [i["id"] for i in data["items"]]

        # 3. Get page 2
        r = get("/items", params={"page": 2, "pageSize": 3}, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 7
        assert data["page"] == 2
        assert len(data["items"]) == 3
        page2_ids = [i["id"] for i in data["items"]]

        # 4. Get page 3 (should have 1 item)
        r = get("/items", params={"page": 3, "pageSize": 3}, headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 7
        assert len(data["items"]) == 1
        page3_ids = [i["id"] for i in data["items"]]

        # 5. No duplicates across pages
        all_paged = page1_ids + page2_ids + page3_ids
        assert len(all_paged) == len(set(all_paged))  # All unique
        assert len(all_paged) == 7

        # 6. All our created items are accounted for
        for item_id in item_ids:
            assert item_id in all_paged


class TestExportFieldCompleteness:
    """Pattern 1+2: Export must include all specified fields with correct names."""

    def test_export_includes_all_fields_with_camel_case(self):
        """Export items must have all ExportItem schema fields."""
        h = make_headers()

        # 1. Create location and label
        r = post("/locations", {"name": "ExportLoc"}, headers=h)
        assert r.status_code == 201

        r = post("/labels", {"name": "ExportLbl"}, headers=h)
        assert r.status_code == 201
        label_id = r.json()["id"]

        # 2. Create item with all fields
        r = post("/items", {
            "name": "ExportFull",
            "description": "Full item for export",
            "quantity": 2,
            "serialNumber": "EXP-SN",
            "modelNumber": "EXP-MN",
            "manufacturer": "ExportCorp",
            "purchasePrice": 99.99,
            "purchaseDate": "2024-01-01",
            "warrantyExpires": "2026-01-01",
            "locationId": None,
            "notes": "export notes",
        }, headers=h)
        assert r.status_code == 201
        item_id = r.json()["id"]

        # 3. Move item to location
        r = put(f"/items/{item_id}", {
            "name": "ExportFull",
            "locationId": post("/locations", {"name": "ExportLoc2"}, headers=h).json()["id"],
        }, headers=h)

        # 4. Attach label
        post(f"/items/{item_id}/labels", {"labelId": label_id}, headers=h)

        # 5. Export
        r = get("/export/csv", headers=h)
        assert r.status_code == 200
        export = r.json()
        assert len(export) >= 1

        exp_item = next((e for e in export if e["name"] == "ExportFull"), None)
        assert exp_item is not None

        # 6. Verify all ExportItem fields present
        assert "id" in exp_item
        assert "name" in exp_item
        assert "description" in exp_item
        assert "quantity" in exp_item
        assert "serialNumber" in exp_item
        assert "modelNumber" in exp_item
        assert "manufacturer" in exp_item
        assert "purchasePrice" in exp_item
        assert "locationName" in exp_item
        assert "labelNames" in exp_item
        assert "notes" in exp_item

        # 7. snake_case must NOT exist
        assert "serial_number" not in exp_item
        assert "model_number" not in exp_item
        assert "purchase_price" not in exp_item
        assert "purchase_date" not in exp_item
        assert "warranty_expires" not in exp_item
        assert "location_name" not in exp_item
        assert "label_names" not in exp_item
