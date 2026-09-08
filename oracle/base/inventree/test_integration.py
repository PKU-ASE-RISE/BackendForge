"""
BackendForge — L2 Integration Tests for InvenTree
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30
API_KEY = "test-api-key-inventree"
HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
U = uuid.uuid4().hex[:8]


def get(path, params=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def post(path, json=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def put(path, json=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def delete(path):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


# ════════════════════════════════════════════════════════════════
# L2 Tests — each test: 3-5 steps, 8-12 assertions, covers 1-2 bug patterns
# ════════════════════════════════════════════════════════════════


class TestCategoryFieldsAndPathstring:
    """Pattern 1+2: Verify exact field names and computed pathstring."""

    def test_category_create_returns_all_fields_exact_casing(self):
        """Verify POST returns 201 and all schema fields with exact names."""
        name = f"CatFields-{U}-{uuid.uuid4().hex[:4]}"
        r = post("/api/categories", {"name": name, "description": "test desc"})
        assert r.status_code == 201
        data = r.json()
        # All required fields present with exact casing
        assert "id" in data
        assert "name" in data
        assert "description" in data
        assert "parent" in data
        assert "pathstring" in data
        # Values correct
        assert data["name"] == name
        assert data["description"] == "test desc"
        assert data["parent"] is None
        assert isinstance(data["id"], int)
        assert data["pathstring"] == name

    def test_three_level_pathstring_computed_correctly(self):
        """Verify pathstring for 3-level hierarchy is computed, not stored."""
        n1 = f"Root-{U}-{uuid.uuid4().hex[:4]}"
        n2 = f"Mid-{U}-{uuid.uuid4().hex[:4]}"
        n3 = f"Leaf-{U}-{uuid.uuid4().hex[:4]}"

        r1 = post("/api/categories", {"name": n1})
        assert r1.status_code == 201
        id1 = r1.json()["id"]

        r2 = post("/api/categories", {"name": n2, "parent": id1})
        assert r2.status_code == 201
        id2 = r2.json()["id"]

        r3 = post("/api/categories", {"name": n3, "parent": id2})
        assert r3.status_code == 201
        id3 = r3.json()["id"]

        # GET the leaf and verify full pathstring
        resp = get(f"/api/categories/{id3}")
        assert resp.status_code == 200
        cat = resp.json()
        assert cat["pathstring"] == f"{n1}/{n2}/{n3}"
        assert cat["parent"] == id2
        assert cat["id"] == id3

    def test_pathstring_updates_when_parent_renamed(self):
        """Verify pathstring reflects current parent name (computed on read)."""
        parent_name = f"OrigParent-{U}-{uuid.uuid4().hex[:4]}"
        child_name = f"Child-{U}-{uuid.uuid4().hex[:4]}"

        parent = post("/api/categories", {"name": parent_name}).json()
        child = post("/api/categories", {"name": child_name, "parent": parent["id"]}).json()

        # Rename parent
        new_parent_name = f"RenamedParent-{U}-{uuid.uuid4().hex[:4]}"
        put(f"/api/categories/{parent['id']}", {"name": new_parent_name})

        # Child's pathstring should now reflect the new name
        resp = get(f"/api/categories/{child['id']}")
        assert resp.status_code == 200
        assert resp.json()["pathstring"] == f"{new_parent_name}/{child_name}"


class TestPartComputedFields:
    """Pattern 2+5: Verify total_stock and low_stock are truly computed."""

    def test_total_stock_sums_multiple_stock_items(self):
        """total_stock must be sum of all stock items, not just the last one."""
        name = f"MultiStock-{U}-{uuid.uuid4().hex[:4]}"
        part = post("/api/parts", {"name": name}).json()
        pid = part["id"]

        # Verify starts at 0
        assert part["total_stock"] == 0
        assert part["low_stock"] is False

        # Add multiple stock items with different quantities
        post("/api/stock", {"part": pid, "quantity": 7})
        post("/api/stock", {"part": pid, "quantity": 13})
        post("/api/stock", {"part": pid, "quantity": 5})

        resp = get(f"/api/parts/{pid}")
        assert resp.status_code == 200
        p = resp.json()
        assert p["total_stock"] == 25  # 7 + 13 + 5
        assert p["low_stock"] is False

    def test_low_stock_boundary_conditions(self):
        """Verify low_stock logic at exact boundary values."""
        name = f"Boundary-{U}-{uuid.uuid4().hex[:4]}"
        part = post("/api/parts", {"name": name, "minimum_stock": 10}).json()
        pid = part["id"]

        # Add exactly 10 units (equal to minimum) — should NOT be low
        post("/api/stock", {"part": pid, "quantity": 10})
        resp = get(f"/api/parts/{pid}")
        p = resp.json()
        assert p["total_stock"] == 10
        assert p["low_stock"] is False

        # Now create a part with stock below minimum
        name2 = f"BelowMin-{U}-{uuid.uuid4().hex[:4]}"
        part2 = post("/api/parts", {"name": name2, "minimum_stock": 10}).json()
        post("/api/stock", {"part": part2["id"], "quantity": 9})
        resp2 = get(f"/api/parts/{part2['id']}")
        p2 = resp2.json()
        assert p2["total_stock"] == 9
        assert p2["low_stock"] is True

    def test_total_stock_updates_after_stock_modification(self):
        """total_stock must update when a stock item's quantity is changed."""
        name = f"StockMod-{U}-{uuid.uuid4().hex[:4]}"
        part = post("/api/parts", {"name": name}).json()
        pid = part["id"]

        s1 = post("/api/stock", {"part": pid, "quantity": 20}).json()
        post("/api/stock", {"part": pid, "quantity": 30})

        # Update first stock item quantity
        put(f"/api/stock/{s1['id']}", {"part": pid, "quantity": 5})

        resp = get(f"/api/parts/{pid}")
        assert resp.json()["total_stock"] == 35  # 5 + 30

    def test_part_fields_IPN_and_units_preserved(self):
        """Pattern 1: IPN is uppercase in schema. Verify exact casing."""
        name = f"IPNPart-{U}-{uuid.uuid4().hex[:4]}"
        r = post("/api/parts", {
            "name": name,
            "IPN": "IPN-12345",
            "units": "pcs",
            "minimum_stock": 5,
            "assembly": False,
            "is_template": False,
        })
        assert r.status_code == 201
        data = r.json()
        assert "IPN" in data  # NOT "ipn" or "Ipn"
        assert data["IPN"] == "IPN-12345"
        assert data["units"] == "pcs"
        assert data["minimum_stock"] == 5
        assert data["assembly"] is False
        assert data["is_template"] is False
        assert "total_stock" in data
        assert "low_stock" in data


class TestStockItemFields:
    """Pattern 1+4: Verify stock item field names and status codes."""

    def test_stock_item_create_returns_201_with_all_fields(self):
        """Verify 201 status and all fields with exact casing."""
        part = post("/api/parts", {"name": f"StkFld-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc = post("/api/locations", {"name": f"StkLoc-{U}-{uuid.uuid4().hex[:4]}"}).json()

        r = post("/api/stock", {
            "part": part["id"],
            "quantity": 42.5,
            "location": loc["id"],
            "serial_number": f"SN-{uuid.uuid4().hex[:6]}",
            "batch": "BATCH-001",
            "purchase_price": 3.99,
        })
        assert r.status_code == 201
        item = r.json()
        assert "id" in item
        assert item["part"] == part["id"]
        assert item["quantity"] == 42.5
        assert item["location"] == loc["id"]
        assert "serial_number" in item  # NOT serialNumber
        assert "batch" in item
        assert "purchase_price" in item  # NOT purchasePrice
        assert item["batch"] == "BATCH-001"
        assert item["purchase_price"] == 3.99

    def test_stock_delete_returns_204_not_200(self):
        """Pattern 4: DELETE must return 204, not 200."""
        part = post("/api/parts", {"name": f"Del204-{U}-{uuid.uuid4().hex[:4]}"}).json()
        stock = post("/api/stock", {"part": part["id"], "quantity": 1}).json()

        r = delete(f"/api/stock/{stock['id']}")
        assert r.status_code == 204

        # Confirm gone with 404
        r2 = get(f"/api/stock/{stock['id']}")
        assert r2.status_code == 404


class TestFilteringActuallyWorks:
    """Pattern 3: Verify filters actually filter, not return everything."""

    def test_parts_category_filter_excludes_other_categories(self):
        """Create parts in 2 categories, filter should only return one category."""
        cat1 = post("/api/categories", {"name": f"FiltCat1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        cat2 = post("/api/categories", {"name": f"FiltCat2-{U}-{uuid.uuid4().hex[:4]}"}).json()

        p1_name = f"InCat1-{U}-{uuid.uuid4().hex[:4]}"
        p2_name = f"InCat2-{U}-{uuid.uuid4().hex[:4]}"
        post("/api/parts", {"name": p1_name, "category": cat1["id"]})
        post("/api/parts", {"name": p2_name, "category": cat2["id"]})

        # Filter by cat1
        resp = get("/api/parts", params={"category": cat1["id"]})
        data = resp.json()
        assert data["count"] >= 1
        names = [p["name"] for p in data["results"]]
        assert p1_name in names
        assert p2_name not in names

    def test_stock_location_filter_excludes_other_locations(self):
        """Stock filtered by location must not include items at other locations."""
        part = post("/api/parts", {"name": f"LocFilt-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc1 = post("/api/locations", {"name": f"Loc1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc2 = post("/api/locations", {"name": f"Loc2-{U}-{uuid.uuid4().hex[:4]}"}).json()

        post("/api/stock", {"part": part["id"], "quantity": 10, "location": loc1["id"]})
        post("/api/stock", {"part": part["id"], "quantity": 20, "location": loc2["id"]})

        resp = get("/api/stock", params={"location": loc1["id"]})
        data = resp.json()
        assert data["count"] >= 1
        for item in data["results"]:
            assert item["location"] == loc1["id"]

    def test_build_orders_status_filter(self):
        """Filtering builds by status should exclude other statuses."""
        asm = post("/api/parts", {"name": f"BldFilt-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()

        b1 = post("/api/builds", {"part": asm["id"], "quantity": 1}).json()
        b2 = post("/api/builds", {"part": asm["id"], "quantity": 2}).json()
        # Cancel b2
        post(f"/api/builds/{b2['id']}/cancel")

        # Filter for pending only
        resp = get("/api/builds", params={"status": "pending"})
        data = resp.json()
        ids = [b["id"] for b in data["results"]]
        assert b1["id"] in ids
        assert b2["id"] not in ids
        for b in data["results"]:
            assert b["status"] == "pending"

    def test_pagination_limit_actually_limits(self):
        """Pattern 3: limit=2 must return at most 2, not all."""
        # Create 4 suppliers
        for i in range(4):
            post("/api/suppliers", {"name": f"PagSup-{U}-{uuid.uuid4().hex[:4]}-{i}"})

        resp = get("/api/suppliers", params={"limit": 2})
        data = resp.json()
        assert len(data["results"]) <= 2
        assert data["count"] >= 4  # count is total, not limited

    def test_pagination_offset_skips_items(self):
        """Pattern 3: offset should actually skip items."""
        cat_name_prefix = f"OffCat-{U}-{uuid.uuid4().hex[:4]}"
        for i in range(3):
            post("/api/categories", {"name": f"{cat_name_prefix}-{i}"})

        r_all = get("/api/categories", params={"limit": 200})
        total = r_all.json()["count"]

        r_offset = get("/api/categories", params={"offset": 1, "limit": 200})
        assert len(r_offset.json()["results"]) == total - 1

    def test_bom_filter_by_sub_part(self):
        """BOM list should support sub_part filter."""
        asm1 = post("/api/parts", {"name": f"BomFAsm1-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        asm2 = post("/api/parts", {"name": f"BomFAsm2-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp = post("/api/parts", {"name": f"BomFComp-{U}-{uuid.uuid4().hex[:4]}"}).json()
        other = post("/api/parts", {"name": f"BomFOther-{U}-{uuid.uuid4().hex[:4]}"}).json()

        post("/api/bom", {"part": asm1["id"], "sub_part": comp["id"], "quantity": 2})
        post("/api/bom", {"part": asm2["id"], "sub_part": other["id"], "quantity": 3})

        resp = get("/api/bom", params={"sub_part": comp["id"]})
        data = resp.json()
        assert data["count"] >= 1
        for item in data["results"]:
            assert item["sub_part"] == comp["id"]


class TestSupplierPartFields:
    """Pattern 1+4: Verify SKU casing (uppercase) and uniqueness constraint."""

    def test_supplier_part_SKU_field_casing(self):
        """SKU must be exactly 'SKU' not 'sku' or 'Sku'."""
        sup = post("/api/suppliers", {"name": f"SkuSup-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"SkuPart-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sku_val = f"SKU-{uuid.uuid4().hex[:6]}"

        r = post("/api/supplier-parts", {
            "supplier": sup["id"],
            "part": part["id"],
            "SKU": sku_val,
            "manufacturer": "TestMfg",
            "pack_quantity": 5,
            "price": 2.50,
            "lead_time": 7,
        })
        assert r.status_code == 201
        sp = r.json()
        assert "SKU" in sp  # Not "sku"
        assert sp["SKU"] == sku_val
        assert "manufacturer" in sp
        assert "pack_quantity" in sp
        assert "lead_time" in sp
        assert sp["manufacturer"] == "TestMfg"
        assert sp["pack_quantity"] == 5
        assert sp["price"] == 2.50
        assert sp["lead_time"] == 7

    def test_supplier_sku_uniqueness_different_suppliers_ok(self):
        """Same SKU on different suppliers is allowed."""
        sup1 = post("/api/suppliers", {"name": f"Sup1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sup2 = post("/api/suppliers", {"name": f"Sup2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"SkuUniq-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sku = f"SHARED-SKU-{uuid.uuid4().hex[:6]}"

        r1 = post("/api/supplier-parts", {"supplier": sup1["id"], "part": part["id"], "SKU": sku})
        assert r1.status_code == 201
        r2 = post("/api/supplier-parts", {"supplier": sup2["id"], "part": part["id"], "SKU": sku})
        assert r2.status_code == 201  # Different suppliers, same SKU is fine


class TestBuildOrderFields:
    """Pattern 1+4: Verify build order field names and status codes."""

    def test_build_order_create_fields(self):
        """Verify all fields on build order creation."""
        asm = post("/api/parts", {"name": f"BOFld-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        ref = f"BO-{uuid.uuid4().hex[:6]}"

        r = post("/api/builds", {"part": asm["id"], "quantity": 7, "reference": ref})
        assert r.status_code == 201
        bo = r.json()
        assert "id" in bo
        assert bo["part"] == asm["id"]
        assert bo["quantity"] == 7
        assert bo["status"] == "pending"
        assert bo["reference"] == ref
        assert "creation_date" in bo  # NOT creationDate
        assert "completion_date" in bo  # NOT completionDate
        assert bo["completion_date"] is None

    def test_cancel_returns_200_with_status_cancelled(self):
        """Cancel should return 200 (not 204) with updated status."""
        asm = post("/api/parts", {"name": f"BOCanc-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        bo = post("/api/builds", {"part": asm["id"], "quantity": 1}).json()

        r = post(f"/api/builds/{bo['id']}/cancel")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cancelled"
        assert data["id"] == bo["id"]


class TestPurchaseOrderFields:
    """Pattern 1+4: Verify PO field names and lifecycle status codes."""

    def test_po_create_returns_201_with_correct_fields(self):
        """Verify PO creation field names (snake_case dates)."""
        sup = post("/api/suppliers", {"name": f"POFld-{U}-{uuid.uuid4().hex[:4]}"}).json()
        ref = f"PO-{uuid.uuid4().hex[:6]}"

        r = post("/api/purchase-orders", {
            "supplier": sup["id"],
            "reference": ref,
            "description": "test po",
        })
        assert r.status_code == 201
        po = r.json()
        assert "id" in po
        assert po["supplier"] == sup["id"]
        assert po["status"] == "pending"
        assert po["reference"] == ref
        assert po["description"] == "test po"
        assert "creation_date" in po  # NOT creationDate
        assert "issue_date" in po  # NOT issueDate
        assert "complete_date" in po  # NOT completeDate
        assert po["issue_date"] is None
        assert po["complete_date"] is None

    def test_po_issue_sets_issue_date(self):
        """Issue must set issue_date to non-null."""
        sup = post("/api/suppliers", {"name": f"POIss-{U}-{uuid.uuid4().hex[:4]}"}).json()
        po = post("/api/purchase-orders", {"supplier": sup["id"]}).json()

        r = post(f"/api/purchase-orders/{po['id']}/issue")
        assert r.status_code == 200
        issued = r.json()
        assert issued["status"] == "placed"
        assert issued["issue_date"] is not None
        assert isinstance(issued["issue_date"], str)
        assert len(issued["issue_date"]) > 0


class TestPOLineItemFields:
    """Pattern 1+4: Verify PO line item fields."""

    def test_po_line_create_returns_201_with_all_fields(self):
        """Verify line item creation returns correct fields."""
        sup = post("/api/suppliers", {"name": f"LineFld-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"LinePrt-{U}-{uuid.uuid4().hex[:4]}"}).json()
        po = post("/api/purchase-orders", {"supplier": sup["id"]}).json()

        r = post("/api/po-lines", {
            "order": po["id"],
            "part": part["id"],
            "quantity": 100,
            "price": 0.75,
            "reference": "Line ref",
        })
        assert r.status_code == 201
        line = r.json()
        assert "id" in line
        assert line["order"] == po["id"]
        assert line["part"] == part["id"]
        assert line["quantity"] == 100
        assert line["price"] == 0.75
        assert line["reference"] == "Line ref"

    def test_po_line_delete_returns_204(self):
        """DELETE line item must return 204."""
        sup = post("/api/suppliers", {"name": f"LnDel-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"LnDelP-{U}-{uuid.uuid4().hex[:4]}"}).json()
        po = post("/api/purchase-orders", {"supplier": sup["id"]}).json()
        line = post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 5}).json()

        r = delete(f"/api/po-lines/{line['id']}")
        assert r.status_code == 204


class TestSearchFunctionality:
    """Pattern 3: Verify search actually searches, not returns everything."""

    def test_parts_search_by_description(self):
        """Search should match description, not just name."""
        unique_desc = f"xyzzy-{uuid.uuid4().hex[:8]}"
        part = post("/api/parts", {
            "name": f"GenericName-{U}-{uuid.uuid4().hex[:4]}",
            "description": unique_desc,
        }).json()

        resp = get("/api/parts", params={"search": unique_desc})
        data = resp.json()
        assert data["count"] >= 1
        ids = [p["id"] for p in data["results"]]
        assert part["id"] in ids

    def test_supplier_search_excludes_non_matching(self):
        """Supplier search must not return suppliers that don't match."""
        unique_name = f"UniqueSupXYZ-{uuid.uuid4().hex[:8]}"
        other_name = f"OtherSup-{uuid.uuid4().hex[:8]}"
        post("/api/suppliers", {"name": unique_name})
        post("/api/suppliers", {"name": other_name})

        resp = get("/api/suppliers", params={"search": unique_name})
        data = resp.json()
        names = [s["name"] for s in data["results"]]
        assert unique_name in names
        assert other_name not in names


class TestLocationHierarchy:
    """Pattern 2: Verify location pathstring like categories."""

    def test_location_three_level_pathstring(self):
        """Location pathstring for 3-level hierarchy."""
        n1 = f"WH-{U}-{uuid.uuid4().hex[:4]}"
        n2 = f"Shelf-{U}-{uuid.uuid4().hex[:4]}"
        n3 = f"Bin-{U}-{uuid.uuid4().hex[:4]}"

        l1 = post("/api/locations", {"name": n1}).json()
        l2 = post("/api/locations", {"name": n2, "parent": l1["id"]}).json()
        l3 = post("/api/locations", {"name": n3, "parent": l2["id"]}).json()

        resp = get(f"/api/locations/{l3['id']}")
        assert resp.status_code == 200
        loc = resp.json()
        assert loc["pathstring"] == f"{n1}/{n2}/{n3}"

    def test_location_filter_by_parent(self):
        """Filter locations by parent should work."""
        parent = post("/api/locations", {"name": f"FltPar-{U}-{uuid.uuid4().hex[:4]}"}).json()
        child1 = post("/api/locations", {"name": f"FltCh1-{U}-{uuid.uuid4().hex[:4]}", "parent": parent["id"]}).json()
        child2 = post("/api/locations", {"name": f"FltCh2-{U}-{uuid.uuid4().hex[:4]}", "parent": parent["id"]}).json()
        # Another root location to prove filtering works
        other = post("/api/locations", {"name": f"FltOth-{U}-{uuid.uuid4().hex[:4]}"}).json()

        resp = get("/api/locations", params={"parent": parent["id"]})
        data = resp.json()
        ids = [l["id"] for l in data["results"]]
        assert child1["id"] in ids
        assert child2["id"] in ids
        assert other["id"] not in ids
        for loc in data["results"]:
            assert loc["parent"] == parent["id"]


class TestBOMValidation:
    """Pattern 5+8: BOM business rules are actually enforced."""

    def test_bom_update_circular_check(self):
        """Updating a BOM item to create a cycle should fail."""
        a = post("/api/parts", {"name": f"CycUpA-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        b = post("/api/parts", {"name": f"CycUpB-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        c = post("/api/parts", {"name": f"CycUpC-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()

        # A -> B
        post("/api/bom", {"part": a["id"], "sub_part": b["id"], "quantity": 1})
        # B -> C (initially fine)
        bom_bc = post("/api/bom", {"part": b["id"], "sub_part": c["id"], "quantity": 1}).json()

        # Update B->C to B->A, which closes the A->B->A cycle.
        r = put(f"/api/bom/{bom_bc['id']}", {
            "part": b["id"],
            "sub_part": a["id"],
            "quantity": 1,
        })
        assert r.status_code == 400

    def test_bom_quantity_preserved_on_roundtrip(self):
        """BOM item quantity should be exact on GET."""
        asm = post("/api/parts", {"name": f"BomQty-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp = post("/api/parts", {"name": f"BomQtyC-{U}-{uuid.uuid4().hex[:4]}"}).json()

        bom = post("/api/bom", {
            "part": asm["id"],
            "sub_part": comp["id"],
            "quantity": 3.5,
            "reference": "C1,C2,C3",
        }).json()

        resp = get(f"/api/bom/{bom['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 3.5
        assert data["reference"] == "C1,C2,C3"
        assert data["part"] == asm["id"]
        assert data["sub_part"] == comp["id"]


class TestNotFoundReturns404:
    """Pattern 4: Verify 404 for all entity types."""

    def test_all_entities_return_404_for_nonexistent(self):
        """Every GET by ID should return 404 for non-existent IDs."""
        endpoints = [
            "/api/categories/999999",
            "/api/parts/999999",
            "/api/locations/999999",
            "/api/stock/999999",
            "/api/bom/999999",
            "/api/suppliers/999999",
            "/api/supplier-parts/999999",
            "/api/builds/999999",
            "/api/purchase-orders/999999",
            "/api/po-lines/999999",
        ]
        for ep in endpoints:
            r = get(ep)
            assert r.status_code == 404, f"Expected 404 for {ep}, got {r.status_code}"


class TestPaginationStructure:
    """Pattern 3: Verify pagination response structure."""

    def test_all_list_endpoints_return_count_and_results(self):
        """Every list endpoint must return {count, results}."""
        endpoints = [
            "/api/categories",
            "/api/parts",
            "/api/locations",
            "/api/stock",
            "/api/bom",
            "/api/suppliers",
            "/api/supplier-parts",
            "/api/builds",
            "/api/purchase-orders",
            "/api/po-lines",
        ]
        for ep in endpoints:
            r = get(ep)
            assert r.status_code == 200, f"Failed for {ep}"
            data = r.json()
            assert "count" in data, f"Missing 'count' in {ep}"
            assert "results" in data, f"Missing 'results' in {ep}"
            assert isinstance(data["results"], list), f"'results' not a list in {ep}"
            assert isinstance(data["count"], int), f"'count' not an int in {ep}"
