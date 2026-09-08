"""
BackendForge — Comprehensive Correctness Tests for InvenTree Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

API_KEY = "test-api-key-inventree"

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path, json_data=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path, json_data=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_delete(path):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


# ════════════════════════════════════════════════════════════════════
# PART 1: Health Check (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(
            f"{BASE_URL}/api/health",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(
            f"{BASE_URL}/api/health",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/parts",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_missing_header_on_categories(self):
        resp = requests.get(
            f"{BASE_URL}/api/categories",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_missing_header_on_stock(self):
        resp = requests.get(
            f"{BASE_URL}/api/stock",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_missing_header_on_post(self):
        resp = requests.post(
            f"{BASE_URL}/api/parts",
            json={"name": "test"},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        """Empty X-Api-Key should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/parts",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_valid_api_key_works(self):
        """Any non-empty key should work."""
        resp = api_get("/api/parts")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 3: Part Categories CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryCRUD:

    def test_create_category(self):
        resp = api_post("/api/categories", {"name": f"Electronics-{UNIQUE}"})
        assert resp.status_code == 201
        cat = resp.json()
        assert cat["name"] == f"Electronics-{UNIQUE}"
        assert "id" in cat
        assert cat["parent"] is None

    def test_create_subcategory(self):
        parent_resp = api_post("/api/categories", {"name": f"Parent-{UNIQUE}"})
        parent = parent_resp.json()
        parent_id = parent["id"]

        resp = api_post("/api/categories", {"name": f"Child-{UNIQUE}", "parent": parent_id})
        assert resp.status_code == 201
        child = resp.json()
        assert child["parent"] == parent_id

    def test_get_category(self):
        create_resp = api_post("/api/categories", {"name": f"GetCat-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_get(f"/api/categories/{cat_id}")
        assert resp.status_code == 200
        cat = resp.json()
        assert cat["id"] == cat_id
        assert cat["name"] == f"GetCat-{UNIQUE}"

    def test_get_nonexistent_category(self):
        resp = api_get("/api/categories/999999")
        assert resp.status_code == 404

    def test_update_category(self):
        create_resp = api_post("/api/categories", {"name": f"UpdCat-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_put(f"/api/categories/{cat_id}", {"name": f"UpdatedCat-{UNIQUE}", "description": "Updated"})
        assert resp.status_code == 200
        cat = resp.json()
        assert cat["name"] == f"UpdatedCat-{UNIQUE}"
        assert cat["description"] == "Updated"

    def test_delete_category(self):
        create_resp = api_post("/api/categories", {"name": f"DelCat-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_delete(f"/api/categories/{cat_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/categories/{cat_id}")
        assert get_resp.status_code == 404

    def test_list_categories(self):
        api_post("/api/categories", {"name": f"ListCat-{UNIQUE}"})
        resp = api_get("/api/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        assert data["count"] >= 1

    def test_pathstring_single_level(self):
        create_resp = api_post("/api/categories", {"name": f"RootPath-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_get(f"/api/categories/{cat_id}")
        cat = resp.json()
        assert cat["pathstring"] == f"RootPath-{UNIQUE}"

    def test_pathstring_nested(self):
        parent_resp = api_post("/api/categories", {"name": f"Level1-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/api/categories", {"name": f"Level2-{UNIQUE}", "parent": parent_id})
        child_id = child_resp.json()["id"]

        resp = api_get(f"/api/categories/{child_id}")
        cat = resp.json()
        assert cat["pathstring"] == f"Level1-{UNIQUE}/Level2-{UNIQUE}"

    def test_filter_by_parent(self):
        parent_resp = api_post("/api/categories", {"name": f"FilterParent-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        api_post("/api/categories", {"name": f"FilterChild1-{UNIQUE}", "parent": parent_id})
        api_post("/api/categories", {"name": f"FilterChild2-{UNIQUE}", "parent": parent_id})

        resp = api_get("/api/categories", params={"parent": parent_id})
        data = resp.json()
        assert data["count"] >= 2
        for cat in data["results"]:
            assert cat["parent"] == parent_id

    def test_search_categories(self):
        api_post("/api/categories", {"name": f"SearchTarget-{UNIQUE}"})
        resp = api_get("/api/categories", params={"search": f"SearchTarget-{UNIQUE}"})
        data = resp.json()
        assert data["count"] >= 1
        names = [c["name"] for c in data["results"]]
        assert f"SearchTarget-{UNIQUE}" in names


# ════════════════════════════════════════════════════════════════════
# PART 4: Parts CRUD
# ════════════════════════════════════════════════════════════════════


class TestPartCRUD:

    def test_create_part(self):
        resp = api_post("/api/parts", {"name": f"Resistor-{UNIQUE}", "description": "10k ohm"})
        assert resp.status_code == 201
        part = resp.json()
        assert part["name"] == f"Resistor-{UNIQUE}"
        assert part["description"] == "10k ohm"
        assert "id" in part
        assert part["total_stock"] == 0
        assert part["low_stock"] is False

    def test_create_part_with_category(self):
        cat_resp = api_post("/api/categories", {"name": f"PartCatTest-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/api/parts", {"name": f"CatPart-{UNIQUE}", "category": cat_id})
        assert resp.status_code == 201
        part = resp.json()
        assert part["category"] == cat_id

    def test_create_assembly_part(self):
        resp = api_post("/api/parts", {"name": f"Assembly-{UNIQUE}", "assembly": True})
        assert resp.status_code == 201
        part = resp.json()
        assert part["assembly"] is True

    def test_get_part(self):
        create_resp = api_post("/api/parts", {"name": f"GetPart-{UNIQUE}"})
        part_id = create_resp.json()["id"]

        resp = api_get(f"/api/parts/{part_id}")
        assert resp.status_code == 200
        part = resp.json()
        assert part["id"] == part_id

    def test_get_nonexistent_part(self):
        resp = api_get("/api/parts/999999")
        assert resp.status_code == 404

    def test_update_part(self):
        create_resp = api_post("/api/parts", {"name": f"UpdPart-{UNIQUE}"})
        part_id = create_resp.json()["id"]

        resp = api_put(f"/api/parts/{part_id}", {"name": f"Updated-{UNIQUE}", "description": "changed"})
        assert resp.status_code == 200
        part = resp.json()
        assert part["name"] == f"Updated-{UNIQUE}"
        assert part["description"] == "changed"

    def test_delete_part(self):
        create_resp = api_post("/api/parts", {"name": f"DelPart-{UNIQUE}"})
        part_id = create_resp.json()["id"]

        resp = api_delete(f"/api/parts/{part_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/parts/{part_id}")
        assert get_resp.status_code == 404

    def test_list_parts(self):
        api_post("/api/parts", {"name": f"ListPart-{UNIQUE}"})
        resp = api_get("/api/parts")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1

    def test_filter_parts_by_category(self):
        cat_resp = api_post("/api/categories", {"name": f"FilterCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        api_post("/api/parts", {"name": f"FilteredPart-{UNIQUE}", "category": cat_id})

        resp = api_get("/api/parts", params={"category": cat_id})
        data = resp.json()
        assert data["count"] >= 1
        for part in data["results"]:
            assert part["category"] == cat_id

    def test_filter_parts_assembly(self):
        api_post("/api/parts", {"name": f"AsmFilter-{UNIQUE}", "assembly": True})
        resp = api_get("/api/parts", params={"assembly": "true"})
        data = resp.json()
        assert data["count"] >= 1
        for part in data["results"]:
            assert part["assembly"] is True

    def test_search_parts(self):
        api_post("/api/parts", {"name": f"UniqueSearchPart-{UNIQUE}"})
        resp = api_get("/api/parts", params={"search": f"UniqueSearchPart-{UNIQUE}"})
        data = resp.json()
        assert data["count"] >= 1
        names = [p["name"] for p in data["results"]]
        assert f"UniqueSearchPart-{UNIQUE}" in names

    def test_variant_of_must_be_template(self):
        """variant_of must reference a part with is_template=true."""
        non_template = api_post("/api/parts", {"name": f"NonTemplate-{UNIQUE}"}).json()

        resp = api_post("/api/parts", {"name": f"Variant-{UNIQUE}", "variant_of": non_template["id"]})
        assert resp.status_code == 400

    def test_variant_of_template(self):
        """Creating a variant of a template should succeed."""
        template = api_post("/api/parts", {"name": f"Template-{UNIQUE}", "is_template": True}).json()

        resp = api_post("/api/parts", {"name": f"GoodVariant-{UNIQUE}", "variant_of": template["id"]})
        assert resp.status_code == 201
        part = resp.json()
        assert part["variant_of"] == template["id"]

    def test_template_cannot_be_variant(self):
        """A part with is_template=true cannot have variant_of set."""
        template = api_post("/api/parts", {"name": f"TplBase-{UNIQUE}", "is_template": True}).json()

        resp = api_post("/api/parts", {
            "name": f"TplVariant-{UNIQUE}",
            "is_template": True,
            "variant_of": template["id"],
        })
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 5: Stock Locations CRUD
# ════════════════════════════════════════════════════════════════════


class TestLocationCRUD:

    def test_create_location(self):
        resp = api_post("/api/locations", {"name": f"Warehouse-{UNIQUE}"})
        assert resp.status_code == 201
        loc = resp.json()
        assert loc["name"] == f"Warehouse-{UNIQUE}"
        assert "id" in loc
        assert loc["parent"] is None

    def test_create_sublocation(self):
        parent_resp = api_post("/api/locations", {"name": f"WH-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        resp = api_post("/api/locations", {"name": f"Shelf-{UNIQUE}", "parent": parent_id})
        assert resp.status_code == 201
        loc = resp.json()
        assert loc["parent"] == parent_id

    def test_location_pathstring(self):
        parent_resp = api_post("/api/locations", {"name": f"LocA-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/api/locations", {"name": f"LocB-{UNIQUE}", "parent": parent_id})
        child_id = child_resp.json()["id"]

        resp = api_get(f"/api/locations/{child_id}")
        loc = resp.json()
        assert loc["pathstring"] == f"LocA-{UNIQUE}/LocB-{UNIQUE}"

    def test_get_location(self):
        create_resp = api_post("/api/locations", {"name": f"GetLoc-{UNIQUE}"})
        loc_id = create_resp.json()["id"]

        resp = api_get(f"/api/locations/{loc_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == loc_id

    def test_get_nonexistent_location(self):
        resp = api_get("/api/locations/999999")
        assert resp.status_code == 404

    def test_update_location(self):
        create_resp = api_post("/api/locations", {"name": f"UpdLoc-{UNIQUE}"})
        loc_id = create_resp.json()["id"]

        resp = api_put(f"/api/locations/{loc_id}", {"name": f"Updated-Loc-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated-Loc-{UNIQUE}"

    def test_delete_location(self):
        create_resp = api_post("/api/locations", {"name": f"DelLoc-{UNIQUE}"})
        loc_id = create_resp.json()["id"]

        resp = api_delete(f"/api/locations/{loc_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/locations/{loc_id}")
        assert get_resp.status_code == 404

    def test_list_locations(self):
        api_post("/api/locations", {"name": f"ListLoc-{UNIQUE}"})
        resp = api_get("/api/locations")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1


# ════════════════════════════════════════════════════════════════════
# PART 6: Stock Items CRUD
# ════════════════════════════════════════════════════════════════════


class TestStockItemCRUD:

    def test_create_stock_item(self):
        part_resp = api_post("/api/parts", {"name": f"StockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]

        resp = api_post("/api/stock", {"part": part_id, "quantity": 100})
        assert resp.status_code == 201
        item = resp.json()
        assert item["part"] == part_id
        assert item["quantity"] == 100
        assert "id" in item

    def test_create_stock_with_location(self):
        part_resp = api_post("/api/parts", {"name": f"StockLocPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        loc_resp = api_post("/api/locations", {"name": f"StockLoc-{UNIQUE}"})
        loc_id = loc_resp.json()["id"]

        resp = api_post("/api/stock", {"part": part_id, "quantity": 50, "location": loc_id})
        assert resp.status_code == 201
        item = resp.json()
        assert item["location"] == loc_id

    def test_create_stock_with_serial(self):
        part_resp = api_post("/api/parts", {"name": f"SerialPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]

        resp = api_post("/api/stock", {"part": part_id, "quantity": 1, "serial_number": f"SN-{UNIQUE}"})
        assert resp.status_code == 201
        item = resp.json()
        assert item["serial_number"] == f"SN-{UNIQUE}"

    def test_serial_number_uniqueness(self):
        """Serial numbers must be unique per part."""
        part_resp = api_post("/api/parts", {"name": f"SerUniq-{UNIQUE}"})
        part_id = part_resp.json()["id"]

        api_post("/api/stock", {"part": part_id, "quantity": 1, "serial_number": f"DUP-{UNIQUE}"})
        resp = api_post("/api/stock", {"part": part_id, "quantity": 1, "serial_number": f"DUP-{UNIQUE}"})
        assert resp.status_code == 400

    def test_serial_uniqueness_different_parts_ok(self):
        """Same serial number on different parts is OK."""
        part1 = api_post("/api/parts", {"name": f"SerPart1-{UNIQUE}"}).json()
        part2 = api_post("/api/parts", {"name": f"SerPart2-{UNIQUE}"}).json()

        serial = f"SHARED-{UNIQUE}"
        resp1 = api_post("/api/stock", {"part": part1["id"], "quantity": 1, "serial_number": serial})
        assert resp1.status_code == 201
        resp2 = api_post("/api/stock", {"part": part2["id"], "quantity": 1, "serial_number": serial})
        assert resp2.status_code == 201

    def test_get_stock_item(self):
        part_resp = api_post("/api/parts", {"name": f"GetStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        create_resp = api_post("/api/stock", {"part": part_id, "quantity": 10})
        item_id = create_resp.json()["id"]

        resp = api_get(f"/api/stock/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id

    def test_get_nonexistent_stock(self):
        resp = api_get("/api/stock/999999")
        assert resp.status_code == 404

    def test_update_stock_item(self):
        part_resp = api_post("/api/parts", {"name": f"UpdStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        create_resp = api_post("/api/stock", {"part": part_id, "quantity": 10})
        item_id = create_resp.json()["id"]

        resp = api_put(f"/api/stock/{item_id}", {"part": part_id, "quantity": 25})
        assert resp.status_code == 200
        assert resp.json()["quantity"] == 25

    def test_delete_stock_item(self):
        part_resp = api_post("/api/parts", {"name": f"DelStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        create_resp = api_post("/api/stock", {"part": part_id, "quantity": 5})
        item_id = create_resp.json()["id"]

        resp = api_delete(f"/api/stock/{item_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/stock/{item_id}")
        assert get_resp.status_code == 404

    def test_list_stock(self):
        part_resp = api_post("/api/parts", {"name": f"ListStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        api_post("/api/stock", {"part": part_id, "quantity": 5})

        resp = api_get("/api/stock")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1

    def test_filter_stock_by_part(self):
        part_resp = api_post("/api/parts", {"name": f"FilterStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        api_post("/api/stock", {"part": part_id, "quantity": 7})

        resp = api_get("/api/stock", params={"part": part_id})
        data = resp.json()
        assert data["count"] >= 1
        for item in data["results"]:
            assert item["part"] == part_id

    def test_filter_stock_by_location(self):
        part_resp = api_post("/api/parts", {"name": f"LocFilterPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]
        loc_resp = api_post("/api/locations", {"name": f"LocFilter-{UNIQUE}"})
        loc_id = loc_resp.json()["id"]
        api_post("/api/stock", {"part": part_id, "quantity": 3, "location": loc_id})

        resp = api_get("/api/stock", params={"location": loc_id})
        data = resp.json()
        assert data["count"] >= 1
        for item in data["results"]:
            assert item["location"] == loc_id


# ════════════════════════════════════════════════════════════════════
# PART 7: Stock Tracking (total_stock & low_stock)
# ════════════════════════════════════════════════════════════════════


class TestStockTracking:

    def test_total_stock_computed(self):
        """total_stock should be the sum of all stock items for that part."""
        part_resp = api_post("/api/parts", {"name": f"TotalStockPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]

        api_post("/api/stock", {"part": part_id, "quantity": 30})
        api_post("/api/stock", {"part": part_id, "quantity": 20})
        api_post("/api/stock", {"part": part_id, "quantity": 50})

        resp = api_get(f"/api/parts/{part_id}")
        part = resp.json()
        assert part["total_stock"] == 100

    def test_total_stock_after_delete(self):
        """total_stock should update when stock items are deleted."""
        part_resp = api_post("/api/parts", {"name": f"TotalDelPart-{UNIQUE}"})
        part_id = part_resp.json()["id"]

        item1 = api_post("/api/stock", {"part": part_id, "quantity": 40}).json()
        api_post("/api/stock", {"part": part_id, "quantity": 60})

        # Delete first item
        api_delete(f"/api/stock/{item1['id']}")

        resp = api_get(f"/api/parts/{part_id}")
        part = resp.json()
        assert part["total_stock"] == 60

    def test_low_stock_false_when_sufficient(self):
        """low_stock should be false when total_stock >= minimum_stock."""
        part_resp = api_post("/api/parts", {"name": f"NotLow-{UNIQUE}", "minimum_stock": 10})
        part_id = part_resp.json()["id"]

        api_post("/api/stock", {"part": part_id, "quantity": 15})

        resp = api_get(f"/api/parts/{part_id}")
        part = resp.json()
        assert part["low_stock"] is False

    def test_low_stock_true_when_insufficient(self):
        """low_stock should be true when total_stock < minimum_stock."""
        part_resp = api_post("/api/parts", {"name": f"LowStock-{UNIQUE}", "minimum_stock": 50})
        part_id = part_resp.json()["id"]

        api_post("/api/stock", {"part": part_id, "quantity": 10})

        resp = api_get(f"/api/parts/{part_id}")
        part = resp.json()
        assert part["low_stock"] is True

    def test_low_stock_false_when_no_minimum(self):
        """low_stock should be false when minimum_stock is 0."""
        part_resp = api_post("/api/parts", {"name": f"NoMin-{UNIQUE}", "minimum_stock": 0})
        part_id = part_resp.json()["id"]

        resp = api_get(f"/api/parts/{part_id}")
        part = resp.json()
        assert part["low_stock"] is False

    def test_filter_low_stock(self):
        """Filter parts by low_stock=true should only return low stock parts."""
        part_resp = api_post("/api/parts", {"name": f"LowFilter-{UNIQUE}", "minimum_stock": 100})
        part_id = part_resp.json()["id"]
        api_post("/api/stock", {"part": part_id, "quantity": 5})

        resp = api_get("/api/parts", params={"low_stock": "true"})
        data = resp.json()
        assert data["count"] >= 1
        for p in data["results"]:
            assert p["low_stock"] is True


# ════════════════════════════════════════════════════════════════════
# PART 8: BOM (Bill of Materials)
# ════════════════════════════════════════════════════════════════════


class TestBOM:

    def test_create_bom_item(self):
        assembly = api_post("/api/parts", {"name": f"BOMAssembly-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"BOMComponent-{UNIQUE}"}).json()

        resp = api_post("/api/bom", {
            "part": assembly["id"],
            "sub_part": component["id"],
            "quantity": 5,
        })
        assert resp.status_code == 201
        bom = resp.json()
        assert bom["part"] == assembly["id"]
        assert bom["sub_part"] == component["id"]
        assert bom["quantity"] == 5
        assert "id" in bom

    def test_bom_part_must_be_assembly(self):
        """BOM item's part must have assembly=true."""
        non_assembly = api_post("/api/parts", {"name": f"NonAsm-{UNIQUE}", "assembly": False}).json()
        component = api_post("/api/parts", {"name": f"BOMComp2-{UNIQUE}"}).json()

        resp = api_post("/api/bom", {
            "part": non_assembly["id"],
            "sub_part": component["id"],
            "quantity": 3,
        })
        assert resp.status_code == 400

    def test_bom_self_reference_rejected(self):
        """A part cannot be in its own BOM."""
        assembly = api_post("/api/parts", {"name": f"SelfBOM-{UNIQUE}", "assembly": True}).json()

        resp = api_post("/api/bom", {
            "part": assembly["id"],
            "sub_part": assembly["id"],
            "quantity": 1,
        })
        assert resp.status_code == 400

    def test_bom_circular_reference_rejected(self):
        """Circular BOM references should be rejected."""
        asm_a = api_post("/api/parts", {"name": f"CircA-{UNIQUE}", "assembly": True}).json()
        asm_b = api_post("/api/parts", {"name": f"CircB-{UNIQUE}", "assembly": True}).json()

        # A needs B
        resp1 = api_post("/api/bom", {"part": asm_a["id"], "sub_part": asm_b["id"], "quantity": 1})
        assert resp1.status_code == 201

        # B needs A → cycle!
        resp2 = api_post("/api/bom", {"part": asm_b["id"], "sub_part": asm_a["id"], "quantity": 1})
        assert resp2.status_code == 400

    def test_bom_circular_reference_indirect(self):
        """Indirect circular references should also be rejected (A→B→C→A)."""
        asm_a = api_post("/api/parts", {"name": f"IndA-{UNIQUE}", "assembly": True}).json()
        asm_b = api_post("/api/parts", {"name": f"IndB-{UNIQUE}", "assembly": True}).json()
        asm_c = api_post("/api/parts", {"name": f"IndC-{UNIQUE}", "assembly": True}).json()

        # A→B
        assert api_post("/api/bom", {"part": asm_a["id"], "sub_part": asm_b["id"], "quantity": 1}).status_code == 201
        # B→C
        assert api_post("/api/bom", {"part": asm_b["id"], "sub_part": asm_c["id"], "quantity": 1}).status_code == 201
        # C→A → cycle!
        resp = api_post("/api/bom", {"part": asm_c["id"], "sub_part": asm_a["id"], "quantity": 1})
        assert resp.status_code == 400

    def test_get_bom_item(self):
        assembly = api_post("/api/parts", {"name": f"GetBOMAsm-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"GetBOMComp-{UNIQUE}"}).json()
        create_resp = api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 2})
        bom_id = create_resp.json()["id"]

        resp = api_get(f"/api/bom/{bom_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == bom_id

    def test_update_bom_item(self):
        assembly = api_post("/api/parts", {"name": f"UpdBOMAsm-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"UpdBOMComp-{UNIQUE}"}).json()
        create_resp = api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 2})
        bom_id = create_resp.json()["id"]

        resp = api_put(f"/api/bom/{bom_id}", {
            "part": assembly["id"],
            "sub_part": component["id"],
            "quantity": 10,
            "reference": "R1,R2",
        })
        assert resp.status_code == 200
        bom = resp.json()
        assert bom["quantity"] == 10
        assert bom["reference"] == "R1,R2"

    def test_delete_bom_item(self):
        assembly = api_post("/api/parts", {"name": f"DelBOMAsm-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"DelBOMComp-{UNIQUE}"}).json()
        create_resp = api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 1})
        bom_id = create_resp.json()["id"]

        resp = api_delete(f"/api/bom/{bom_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/bom/{bom_id}")
        assert get_resp.status_code == 404

    def test_list_bom_filter_by_part(self):
        assembly = api_post("/api/parts", {"name": f"ListBOMAsm-{UNIQUE}", "assembly": True}).json()
        comp1 = api_post("/api/parts", {"name": f"ListBOMC1-{UNIQUE}"}).json()
        comp2 = api_post("/api/parts", {"name": f"ListBOMC2-{UNIQUE}"}).json()
        api_post("/api/bom", {"part": assembly["id"], "sub_part": comp1["id"], "quantity": 3})
        api_post("/api/bom", {"part": assembly["id"], "sub_part": comp2["id"], "quantity": 7})

        resp = api_get("/api/bom", params={"part": assembly["id"]})
        data = resp.json()
        assert data["count"] >= 2
        for item in data["results"]:
            assert item["part"] == assembly["id"]


# ════════════════════════════════════════════════════════════════════
# PART 9: Build Orders
# ════════════════════════════════════════════════════════════════════


class TestBuildOrders:

    def test_create_build_order(self):
        assembly = api_post("/api/parts", {"name": f"BuildAsm-{UNIQUE}", "assembly": True}).json()

        resp = api_post("/api/builds", {"part": assembly["id"], "quantity": 10, "reference": "BO-001"})
        assert resp.status_code == 201
        build = resp.json()
        assert build["part"] == assembly["id"]
        assert build["quantity"] == 10
        assert build["status"] == "pending"
        assert build["reference"] == "BO-001"
        assert "id" in build
        assert "creation_date" in build

    def test_get_build_order(self):
        assembly = api_post("/api/parts", {"name": f"GetBuildAsm-{UNIQUE}", "assembly": True}).json()
        create_resp = api_post("/api/builds", {"part": assembly["id"], "quantity": 5})
        build_id = create_resp.json()["id"]

        resp = api_get(f"/api/builds/{build_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == build_id

    def test_get_nonexistent_build(self):
        resp = api_get("/api/builds/999999")
        assert resp.status_code == 404

    def test_list_builds(self):
        assembly = api_post("/api/parts", {"name": f"ListBuildAsm-{UNIQUE}", "assembly": True}).json()
        api_post("/api/builds", {"part": assembly["id"], "quantity": 1})

        resp = api_get("/api/builds")
        data = resp.json()
        assert data["count"] >= 1

    def test_filter_builds_by_status(self):
        assembly = api_post("/api/parts", {"name": f"FilterBuildAsm-{UNIQUE}", "assembly": True}).json()
        api_post("/api/builds", {"part": assembly["id"], "quantity": 1})

        resp = api_get("/api/builds", params={"status": "pending"})
        data = resp.json()
        assert data["count"] >= 1
        for build in data["results"]:
            assert build["status"] == "pending"

    def test_cancel_build_order(self):
        assembly = api_post("/api/parts", {"name": f"CancelBuildAsm-{UNIQUE}", "assembly": True}).json()
        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 5}).json()

        resp = api_post(f"/api/builds/{build['id']}/cancel")
        assert resp.status_code == 200
        cancelled = resp.json()
        assert cancelled["status"] == "cancelled"

    def test_cancel_already_cancelled(self):
        assembly = api_post("/api/parts", {"name": f"CancelTwice-{UNIQUE}", "assembly": True}).json()
        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 5}).json()
        api_post(f"/api/builds/{build['id']}/cancel")

        resp = api_post(f"/api/builds/{build['id']}/cancel")
        assert resp.status_code == 400

    def test_complete_build_order(self):
        """Completing a build should consume BOM items and produce output."""
        # Create assembly and components
        assembly = api_post("/api/parts", {"name": f"CompBuildAsm-{UNIQUE}", "assembly": True}).json()
        comp1 = api_post("/api/parts", {"name": f"CompBuildC1-{UNIQUE}"}).json()
        comp2 = api_post("/api/parts", {"name": f"CompBuildC2-{UNIQUE}"}).json()

        # Define BOM: assembly needs 2x comp1 and 3x comp2
        api_post("/api/bom", {"part": assembly["id"], "sub_part": comp1["id"], "quantity": 2})
        api_post("/api/bom", {"part": assembly["id"], "sub_part": comp2["id"], "quantity": 3})

        # Add stock: 20x comp1, 30x comp2
        api_post("/api/stock", {"part": comp1["id"], "quantity": 20})
        api_post("/api/stock", {"part": comp2["id"], "quantity": 30})

        # Create build for 5 units
        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 5}).json()

        # Complete the build
        resp = api_post(f"/api/builds/{build['id']}/complete")
        assert resp.status_code == 200
        completed = resp.json()
        assert completed["status"] == "complete"
        assert completed["completion_date"] is not None

        # Verify stock consumed: comp1 should have 20 - 5*2 = 10
        comp1_resp = api_get(f"/api/parts/{comp1['id']}")
        assert comp1_resp.json()["total_stock"] == 10

        # comp2 should have 30 - 5*3 = 15
        comp2_resp = api_get(f"/api/parts/{comp2['id']}")
        assert comp2_resp.json()["total_stock"] == 15

        # Assembly should have 5 units produced
        asm_resp = api_get(f"/api/parts/{assembly['id']}")
        assert asm_resp.json()["total_stock"] == 5

    def test_complete_build_insufficient_stock(self):
        """Completing a build with insufficient stock should fail."""
        assembly = api_post("/api/parts", {"name": f"InsuffBuildAsm-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"InsuffBuildComp-{UNIQUE}"}).json()

        api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 10})
        api_post("/api/stock", {"part": component["id"], "quantity": 5})  # Only 5, need 10*2=20

        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 2}).json()

        resp = api_post(f"/api/builds/{build['id']}/complete")
        assert resp.status_code == 400

    def test_complete_already_complete(self):
        """Cannot complete an already completed build."""
        assembly = api_post("/api/parts", {"name": f"DblComplete-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"DblCompComp-{UNIQUE}"}).json()
        api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 1})
        api_post("/api/stock", {"part": component["id"], "quantity": 100})

        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 1}).json()
        api_post(f"/api/builds/{build['id']}/complete")

        resp = api_post(f"/api/builds/{build['id']}/complete")
        assert resp.status_code == 400

    def test_complete_cancelled_build(self):
        """Cannot complete a cancelled build."""
        assembly = api_post("/api/parts", {"name": f"CompCancel-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"CompCancelC-{UNIQUE}"}).json()
        api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 1})
        api_post("/api/stock", {"part": component["id"], "quantity": 100})

        build = api_post("/api/builds", {"part": assembly["id"], "quantity": 1}).json()
        api_post(f"/api/builds/{build['id']}/cancel")

        resp = api_post(f"/api/builds/{build['id']}/complete")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 10: Purchase Orders
# ════════════════════════════════════════════════════════════════════


class TestPurchaseOrders:

    def test_create_purchase_order(self):
        supplier = api_post("/api/suppliers", {"name": f"POSupplier-{UNIQUE}"}).json()

        resp = api_post("/api/purchase-orders", {
            "supplier": supplier["id"],
            "reference": "PO-001",
            "description": "Test order",
        })
        assert resp.status_code == 201
        po = resp.json()
        assert po["supplier"] == supplier["id"]
        assert po["status"] == "pending"
        assert po["reference"] == "PO-001"
        assert "id" in po

    def test_get_purchase_order(self):
        supplier = api_post("/api/suppliers", {"name": f"GetPOSup-{UNIQUE}"}).json()
        create_resp = api_post("/api/purchase-orders", {"supplier": supplier["id"]})
        po_id = create_resp.json()["id"]

        resp = api_get(f"/api/purchase-orders/{po_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == po_id

    def test_issue_purchase_order(self):
        supplier = api_post("/api/suppliers", {"name": f"IssuePOSup-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()

        resp = api_post(f"/api/purchase-orders/{po['id']}/issue")
        assert resp.status_code == 200
        issued = resp.json()
        assert issued["status"] == "placed"
        assert issued["issue_date"] is not None

    def test_issue_already_placed(self):
        """Cannot issue a PO that's already placed."""
        supplier = api_post("/api/suppliers", {"name": f"Issue2POSup-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        api_post(f"/api/purchase-orders/{po['id']}/issue")

        resp = api_post(f"/api/purchase-orders/{po['id']}/issue")
        assert resp.status_code == 400

    def test_receive_purchase_order(self):
        """Receiving a PO should create stock items for each line item."""
        supplier = api_post("/api/suppliers", {"name": f"RcvPOSup-{UNIQUE}"}).json()
        part1 = api_post("/api/parts", {"name": f"RcvPOPart1-{UNIQUE}"}).json()
        part2 = api_post("/api/parts", {"name": f"RcvPOPart2-{UNIQUE}"}).json()
        location = api_post("/api/locations", {"name": f"RcvLoc-{UNIQUE}"}).json()

        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()

        # Add line items
        api_post("/api/po-lines", {"order": po["id"], "part": part1["id"], "quantity": 100, "price": 0.50})
        api_post("/api/po-lines", {"order": po["id"], "part": part2["id"], "quantity": 50, "price": 1.20})

        # Issue and receive
        api_post(f"/api/purchase-orders/{po['id']}/issue")
        resp = api_post(f"/api/purchase-orders/{po['id']}/receive", {"location": location["id"]})
        assert resp.status_code == 200
        received = resp.json()
        assert received["status"] == "received"
        assert received["complete_date"] is not None

        # Verify stock was created
        part1_stock = api_get(f"/api/parts/{part1['id']}").json()
        assert part1_stock["total_stock"] == 100

        part2_stock = api_get(f"/api/parts/{part2['id']}").json()
        assert part2_stock["total_stock"] == 50

    def test_receive_not_placed(self):
        """Cannot receive a pending PO."""
        supplier = api_post("/api/suppliers", {"name": f"RcvPendingSup-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        location = api_post("/api/locations", {"name": f"RcvPendLoc-{UNIQUE}"}).json()

        resp = api_post(f"/api/purchase-orders/{po['id']}/receive", {"location": location["id"]})
        assert resp.status_code == 400

    def test_receive_no_line_items(self):
        """Cannot receive a PO with no line items."""
        supplier = api_post("/api/suppliers", {"name": f"EmptyPOSup-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        location = api_post("/api/locations", {"name": f"EmptyPOLoc-{UNIQUE}"}).json()

        api_post(f"/api/purchase-orders/{po['id']}/issue")
        resp = api_post(f"/api/purchase-orders/{po['id']}/receive", {"location": location["id"]})
        assert resp.status_code == 400

    def test_list_purchase_orders(self):
        supplier = api_post("/api/suppliers", {"name": f"ListPOSup-{UNIQUE}"}).json()
        api_post("/api/purchase-orders", {"supplier": supplier["id"]})

        resp = api_get("/api/purchase-orders")
        data = resp.json()
        assert data["count"] >= 1

    def test_filter_po_by_status(self):
        supplier = api_post("/api/suppliers", {"name": f"FilterPOSup-{UNIQUE}"}).json()
        api_post("/api/purchase-orders", {"supplier": supplier["id"]})

        resp = api_get("/api/purchase-orders", params={"status": "pending"})
        data = resp.json()
        for po in data["results"]:
            assert po["status"] == "pending"


# ════════════════════════════════════════════════════════════════════
# PART 11: PO Line Items
# ════════════════════════════════════════════════════════════════════


class TestPOLineItems:

    def test_create_po_line(self):
        supplier = api_post("/api/suppliers", {"name": f"LineSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"LinePart-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()

        resp = api_post("/api/po-lines", {
            "order": po["id"],
            "part": part["id"],
            "quantity": 25,
            "price": 3.50,
        })
        assert resp.status_code == 201
        line = resp.json()
        assert line["order"] == po["id"]
        assert line["part"] == part["id"]
        assert line["quantity"] == 25
        assert line["price"] == 3.50

    def test_get_po_line(self):
        supplier = api_post("/api/suppliers", {"name": f"GetLineSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"GetLinePart-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        line = api_post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 10}).json()

        resp = api_get(f"/api/po-lines/{line['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == line["id"]

    def test_update_po_line(self):
        supplier = api_post("/api/suppliers", {"name": f"UpdLineSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"UpdLinePart-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        line = api_post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 10}).json()

        resp = api_put(f"/api/po-lines/{line['id']}", {
            "order": po["id"],
            "part": part["id"],
            "quantity": 50,
            "price": 2.00,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["quantity"] == 50
        assert updated["price"] == 2.00

    def test_delete_po_line(self):
        supplier = api_post("/api/suppliers", {"name": f"DelLineSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"DelLinePart-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        line = api_post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 10}).json()

        resp = api_delete(f"/api/po-lines/{line['id']}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/po-lines/{line['id']}")
        assert get_resp.status_code == 404

    def test_list_po_lines_filter_by_order(self):
        supplier = api_post("/api/suppliers", {"name": f"ListLineSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"ListLinePart-{UNIQUE}"}).json()
        po = api_post("/api/purchase-orders", {"supplier": supplier["id"]}).json()
        api_post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 5})

        resp = api_get("/api/po-lines", params={"order": po["id"]})
        data = resp.json()
        assert data["count"] >= 1
        for line in data["results"]:
            assert line["order"] == po["id"]


# ════════════════════════════════════════════════════════════════════
# PART 12: Suppliers CRUD
# ════════════════════════════════════════════════════════════════════


class TestSupplierCRUD:

    def test_create_supplier(self):
        resp = api_post("/api/suppliers", {
            "name": f"Acme-{UNIQUE}",
            "contact": "John Doe",
            "email": "john@acme.com",
        })
        assert resp.status_code == 201
        sup = resp.json()
        assert sup["name"] == f"Acme-{UNIQUE}"
        assert sup["contact"] == "John Doe"
        assert sup["email"] == "john@acme.com"
        assert "id" in sup

    def test_get_supplier(self):
        create_resp = api_post("/api/suppliers", {"name": f"GetSup-{UNIQUE}"})
        sup_id = create_resp.json()["id"]

        resp = api_get(f"/api/suppliers/{sup_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sup_id

    def test_get_nonexistent_supplier(self):
        resp = api_get("/api/suppliers/999999")
        assert resp.status_code == 404

    def test_update_supplier(self):
        create_resp = api_post("/api/suppliers", {"name": f"UpdSup-{UNIQUE}"})
        sup_id = create_resp.json()["id"]

        resp = api_put(f"/api/suppliers/{sup_id}", {"name": f"Updated-Sup-{UNIQUE}", "phone": "555-1234"})
        assert resp.status_code == 200
        sup = resp.json()
        assert sup["name"] == f"Updated-Sup-{UNIQUE}"
        assert sup["phone"] == "555-1234"

    def test_delete_supplier(self):
        create_resp = api_post("/api/suppliers", {"name": f"DelSup-{UNIQUE}"})
        sup_id = create_resp.json()["id"]

        resp = api_delete(f"/api/suppliers/{sup_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/suppliers/{sup_id}")
        assert get_resp.status_code == 404

    def test_delete_supplier_with_parts_rejected(self):
        """Cannot delete supplier if it has supplier parts."""
        supplier = api_post("/api/suppliers", {"name": f"DelSupWithParts-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"DelSupPart-{UNIQUE}"}).json()
        api_post("/api/supplier-parts", {
            "supplier": supplier["id"],
            "part": part["id"],
            "SKU": f"SKU-Del-{UNIQUE}",
        })

        resp = api_delete(f"/api/suppliers/{supplier['id']}")
        assert resp.status_code == 400

    def test_list_suppliers(self):
        api_post("/api/suppliers", {"name": f"ListSup-{UNIQUE}"})
        resp = api_get("/api/suppliers")
        data = resp.json()
        assert data["count"] >= 1

    def test_search_suppliers(self):
        api_post("/api/suppliers", {"name": f"UniqueSupSearch-{UNIQUE}"})
        resp = api_get("/api/suppliers", params={"search": f"UniqueSupSearch-{UNIQUE}"})
        data = resp.json()
        assert data["count"] >= 1


# ════════════════════════════════════════════════════════════════════
# PART 13: Supplier Parts
# ════════════════════════════════════════════════════════════════════


class TestSupplierParts:

    def test_create_supplier_part(self):
        supplier = api_post("/api/suppliers", {"name": f"SPSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"SPPart-{UNIQUE}"}).json()

        resp = api_post("/api/supplier-parts", {
            "supplier": supplier["id"],
            "part": part["id"],
            "SKU": f"SKU-{UNIQUE}",
            "price": 1.50,
            "pack_quantity": 10,
        })
        assert resp.status_code == 201
        sp = resp.json()
        assert sp["supplier"] == supplier["id"]
        assert sp["part"] == part["id"]
        assert sp["SKU"] == f"SKU-{UNIQUE}"
        assert sp["price"] == 1.50
        assert sp["pack_quantity"] == 10

    def test_duplicate_supplier_sku_rejected(self):
        """Combination of (supplier, SKU) must be unique."""
        supplier = api_post("/api/suppliers", {"name": f"DupSKUSup-{UNIQUE}"}).json()
        part1 = api_post("/api/parts", {"name": f"DupSKUPart1-{UNIQUE}"}).json()
        part2 = api_post("/api/parts", {"name": f"DupSKUPart2-{UNIQUE}"}).json()

        sku = f"DUP-SKU-{UNIQUE}"
        resp1 = api_post("/api/supplier-parts", {"supplier": supplier["id"], "part": part1["id"], "SKU": sku})
        assert resp1.status_code == 201

        resp2 = api_post("/api/supplier-parts", {"supplier": supplier["id"], "part": part2["id"], "SKU": sku})
        assert resp2.status_code == 400

    def test_get_supplier_part(self):
        supplier = api_post("/api/suppliers", {"name": f"GetSPSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"GetSPPart-{UNIQUE}"}).json()
        sp = api_post("/api/supplier-parts", {
            "supplier": supplier["id"], "part": part["id"], "SKU": f"GSP-{UNIQUE}",
        }).json()

        resp = api_get(f"/api/supplier-parts/{sp['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sp["id"]

    def test_update_supplier_part(self):
        supplier = api_post("/api/suppliers", {"name": f"UpdSPSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"UpdSPPart-{UNIQUE}"}).json()
        sp = api_post("/api/supplier-parts", {
            "supplier": supplier["id"], "part": part["id"], "SKU": f"USP-{UNIQUE}",
        }).json()

        resp = api_put(f"/api/supplier-parts/{sp['id']}", {
            "supplier": supplier["id"],
            "part": part["id"],
            "SKU": f"USP-{UNIQUE}",
            "price": 9.99,
            "lead_time": 14,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["price"] == 9.99
        assert updated["lead_time"] == 14

    def test_delete_supplier_part(self):
        supplier = api_post("/api/suppliers", {"name": f"DelSPSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"DelSPPart-{UNIQUE}"}).json()
        sp = api_post("/api/supplier-parts", {
            "supplier": supplier["id"], "part": part["id"], "SKU": f"DSP-{UNIQUE}",
        }).json()

        resp = api_delete(f"/api/supplier-parts/{sp['id']}")
        assert resp.status_code == 204

    def test_list_supplier_parts_filter(self):
        supplier = api_post("/api/suppliers", {"name": f"ListSPSup-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"ListSPPart-{UNIQUE}"}).json()
        api_post("/api/supplier-parts", {
            "supplier": supplier["id"], "part": part["id"], "SKU": f"LSP-{UNIQUE}",
        })

        resp = api_get("/api/supplier-parts", params={"supplier": supplier["id"]})
        data = resp.json()
        assert data["count"] >= 1
        for sp in data["results"]:
            assert sp["supplier"] == supplier["id"]


# ════════════════════════════════════════════════════════════════════
# PART 14: Hierarchy Deletion Behavior
# ════════════════════════════════════════════════════════════════════


class TestHierarchyDeletion:

    def test_delete_category_uncategorizes_parts(self):
        """Deleting a category sets parts' category to null."""
        cat = api_post("/api/categories", {"name": f"DelHierCat-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"DelHierPart-{UNIQUE}", "category": cat["id"]}).json()

        api_delete(f"/api/categories/{cat['id']}")

        part_resp = api_get(f"/api/parts/{part['id']}")
        assert part_resp.status_code == 200
        assert part_resp.json()["category"] is None

    def test_delete_category_recursive(self):
        """Deleting a parent category also deletes sub-categories."""
        parent = api_post("/api/categories", {"name": f"RecParent-{UNIQUE}"}).json()
        child = api_post("/api/categories", {"name": f"RecChild-{UNIQUE}", "parent": parent["id"]}).json()

        api_delete(f"/api/categories/{parent['id']}")

        # Child should be gone
        resp = api_get(f"/api/categories/{child['id']}")
        assert resp.status_code == 404

    def test_delete_location_nullifies_stock(self):
        """Deleting a location sets stock items' location to null."""
        loc = api_post("/api/locations", {"name": f"DelLocNull-{UNIQUE}"}).json()
        part = api_post("/api/parts", {"name": f"DelLocPart-{UNIQUE}"}).json()
        stock = api_post("/api/stock", {"part": part["id"], "quantity": 10, "location": loc["id"]}).json()

        api_delete(f"/api/locations/{loc['id']}")

        stock_resp = api_get(f"/api/stock/{stock['id']}")
        assert stock_resp.status_code == 200
        assert stock_resp.json()["location"] is None

    def test_delete_location_recursive(self):
        """Deleting a parent location also deletes sub-locations."""
        parent = api_post("/api/locations", {"name": f"RecLocParent-{UNIQUE}"}).json()
        child = api_post("/api/locations", {"name": f"RecLocChild-{UNIQUE}", "parent": parent["id"]}).json()

        api_delete(f"/api/locations/{parent['id']}")

        resp = api_get(f"/api/locations/{child['id']}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Part Deletion Constraints
# ════════════════════════════════════════════════════════════════════


class TestPartDeletionConstraints:

    def test_cannot_delete_part_with_stock(self):
        """Part with stock items cannot be deleted."""
        part = api_post("/api/parts", {"name": f"HasStock-{UNIQUE}"}).json()
        api_post("/api/stock", {"part": part["id"], "quantity": 5})

        resp = api_delete(f"/api/parts/{part['id']}")
        assert resp.status_code == 400

    def test_cannot_delete_part_in_bom_as_parent(self):
        """Part referenced as 'part' in BOM cannot be deleted."""
        assembly = api_post("/api/parts", {"name": f"BOMParentDel-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"BOMParentComp-{UNIQUE}"}).json()
        api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 1})

        resp = api_delete(f"/api/parts/{assembly['id']}")
        assert resp.status_code == 400

    def test_cannot_delete_part_in_bom_as_sub_part(self):
        """Part referenced as 'sub_part' in BOM cannot be deleted."""
        assembly = api_post("/api/parts", {"name": f"BOMSubDel-{UNIQUE}", "assembly": True}).json()
        component = api_post("/api/parts", {"name": f"BOMSubComp-{UNIQUE}"}).json()
        api_post("/api/bom", {"part": assembly["id"], "sub_part": component["id"], "quantity": 1})

        resp = api_delete(f"/api/parts/{component['id']}")
        assert resp.status_code == 400

    def test_cannot_delete_part_with_pending_build(self):
        """Part with pending build orders cannot be deleted."""
        assembly = api_post("/api/parts", {"name": f"BuildDelPart-{UNIQUE}", "assembly": True}).json()
        api_post("/api/builds", {"part": assembly["id"], "quantity": 5})

        resp = api_delete(f"/api/parts/{assembly['id']}")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 16: Pagination
# ════════════════════════════════════════════════════════════════════


class TestPagination:

    def test_default_limit(self):
        """Default limit should be 50."""
        # Create enough entries
        for i in range(3):
            api_post("/api/parts", {"name": f"PagPart-{UNIQUE}-{i}"})

        resp = api_get("/api/parts")
        data = resp.json()
        assert len(data["results"]) <= 50

    def test_custom_limit(self):
        """Custom limit should be respected."""
        for i in range(5):
            api_post("/api/parts", {"name": f"LimPart-{UNIQUE}-{i}"})

        resp = api_get("/api/parts", params={"limit": 2})
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_offset(self):
        """Offset should skip items."""
        prefix = f"OffsetPart-{UNIQUE}"
        for i in range(3):
            api_post("/api/parts", {"name": f"{prefix}-{i}"})

        resp_full = api_get("/api/parts", params={"limit": 200})
        total = resp_full.json()["count"]

        if total >= 3:
            resp_offset = api_get(
                "/api/parts",
                params={"offset": 2, "limit": 200},
            )
            data = resp_offset.json()
            assert len(data["results"]) == total - 2

    def test_count_reflects_total(self):
        """Count should reflect total matching items regardless of limit."""
        # Ensure at least 3 items
        for i in range(3):
            api_post("/api/categories", {"name": f"CountCat-{UNIQUE}-{i}"})

        resp = api_get("/api/categories", params={"limit": 1})
        data = resp.json()
        assert data["count"] >= 3
        assert len(data["results"]) == 1
