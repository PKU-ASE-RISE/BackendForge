"""
BackendForge — L3 Workflow Tests for InvenTree
Multi-entity, multi-step adversarial tests targeting LLM implementation gaps.
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
# L3 Tests — each: 6-12 steps, 12-20 assertions, 3+ entity types
# ════════════════════════════════════════════════════════════════


class TestBuildOrderFullLifecycle:
    """Pattern 5+7: Build completion consumes stock correctly (multi-BOM, stock deduction)."""

    def test_build_consumes_stock_from_multiple_items_lowest_id_first(self):
        """
        Build completion should deduct from lowest-ID stock items first.
        If a stock item reaches 0, it should be deleted.
        """
        # 1. Create assembly + component
        asm = post("/api/parts", {"name": f"BuildLC-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp = post("/api/parts", {"name": f"BuildLCC-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # 2. BOM: assembly needs 3x component
        post("/api/bom", {"part": asm["id"], "sub_part": comp["id"], "quantity": 3})

        # 3. Add 3 stock items for component: 2, 5, 10 (IDs in order)
        s1 = post("/api/stock", {"part": comp["id"], "quantity": 2}).json()
        s2 = post("/api/stock", {"part": comp["id"], "quantity": 5}).json()
        s3 = post("/api/stock", {"part": comp["id"], "quantity": 10}).json()

        # 4. Build 2 units → needs 2*3 = 6 from stock
        build = post("/api/builds", {"part": asm["id"], "quantity": 2}).json()
        assert build["status"] == "pending"

        # 5. Complete the build
        r = post(f"/api/builds/{build['id']}/complete")
        assert r.status_code == 200
        assert r.json()["status"] == "complete"
        assert r.json()["completion_date"] is not None

        # 6. Verify stock deduction: 6 total consumed from lowest ID first
        # s1 had 2 → all consumed → deleted
        r_s1 = get(f"/api/stock/{s1['id']}")
        assert r_s1.status_code == 404  # Deleted because reached 0

        # s2 had 5, 4 more needed after s1 → 5-4=1 remaining
        r_s2 = get(f"/api/stock/{s2['id']}")
        assert r_s2.status_code == 200
        assert r_s2.json()["quantity"] == 1

        # s3 untouched
        r_s3 = get(f"/api/stock/{s3['id']}")
        assert r_s3.status_code == 200
        assert r_s3.json()["quantity"] == 10

        # 7. Assembly should have 2 units produced
        asm_resp = get(f"/api/parts/{asm['id']}")
        assert asm_resp.json()["total_stock"] == 2

        # 8. Component total stock should be 1 + 10 = 11
        comp_resp = get(f"/api/parts/{comp['id']}")
        assert comp_resp.json()["total_stock"] == 11

    def test_build_with_multiple_bom_items_stock_verification(self):
        """Build with 3 BOM items — verify all are consumed correctly."""
        asm = post("/api/parts", {"name": f"MultiBOM-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        c1 = post("/api/parts", {"name": f"MBC1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        c2 = post("/api/parts", {"name": f"MBC2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        c3 = post("/api/parts", {"name": f"MBC3-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # BOM: 2x c1, 4x c2, 1x c3
        post("/api/bom", {"part": asm["id"], "sub_part": c1["id"], "quantity": 2})
        post("/api/bom", {"part": asm["id"], "sub_part": c2["id"], "quantity": 4})
        post("/api/bom", {"part": asm["id"], "sub_part": c3["id"], "quantity": 1})

        # Stock: 100 each
        post("/api/stock", {"part": c1["id"], "quantity": 100})
        post("/api/stock", {"part": c2["id"], "quantity": 100})
        post("/api/stock", {"part": c3["id"], "quantity": 100})

        # Build 10 units
        build = post("/api/builds", {"part": asm["id"], "quantity": 10}).json()
        r = post(f"/api/builds/{build['id']}/complete")
        assert r.status_code == 200

        # Verify: c1=100-20=80, c2=100-40=60, c3=100-10=90, asm=10
        assert get(f"/api/parts/{c1['id']}").json()["total_stock"] == 80
        assert get(f"/api/parts/{c2['id']}").json()["total_stock"] == 60
        assert get(f"/api/parts/{c3['id']}").json()["total_stock"] == 90
        assert get(f"/api/parts/{asm['id']}").json()["total_stock"] == 10


class TestPurchaseOrderFullLifecycle:
    """Pattern 5+7: PO lifecycle creates stock correctly."""

    def test_po_full_lifecycle_pending_to_received(self):
        """Full PO lifecycle: create → add lines → issue → receive → verify stock."""
        # 1. Create supplier
        sup = post("/api/suppliers", {"name": f"POLife-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # 2. Create parts
        p1 = post("/api/parts", {"name": f"POLP1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        p2 = post("/api/parts", {"name": f"POLP2-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # 3. Create location for receiving
        loc = post("/api/locations", {"name": f"POLoc-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # 4. Create PO
        po = post("/api/purchase-orders", {"supplier": sup["id"], "reference": "PO-LIFE"}).json()
        assert po["status"] == "pending"
        assert po["issue_date"] is None
        assert po["complete_date"] is None

        # 5. Add line items
        l1 = post("/api/po-lines", {"order": po["id"], "part": p1["id"], "quantity": 50, "price": 1.0}).json()
        l2 = post("/api/po-lines", {"order": po["id"], "part": p2["id"], "quantity": 25, "price": 2.0}).json()
        assert l1["order"] == po["id"]
        assert l2["order"] == po["id"]

        # 6. Issue the PO
        r_issue = post(f"/api/purchase-orders/{po['id']}/issue")
        assert r_issue.status_code == 200
        issued = r_issue.json()
        assert issued["status"] == "placed"
        assert issued["issue_date"] is not None

        # 7. Receive the PO
        r_recv = post(f"/api/purchase-orders/{po['id']}/receive", {"location": loc["id"]})
        assert r_recv.status_code == 200
        received = r_recv.json()
        assert received["status"] == "received"
        assert received["complete_date"] is not None

        # 8. Verify stock created at the specified location
        p1_stock = get(f"/api/parts/{p1['id']}").json()
        assert p1_stock["total_stock"] == 50

        p2_stock = get(f"/api/parts/{p2['id']}").json()
        assert p2_stock["total_stock"] == 25

        # 9. Verify stock items are at the correct location
        stock_resp = get("/api/stock", params={"part": p1["id"]})
        for item in stock_resp.json()["results"]:
            if item["part"] == p1["id"]:
                assert item["location"] == loc["id"]

    def test_cannot_receive_pending_po(self):
        """Receiving a PO that hasn't been issued should fail."""
        sup = post("/api/suppliers", {"name": f"NoPend-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"NoPendP-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc = post("/api/locations", {"name": f"NoPendL-{U}-{uuid.uuid4().hex[:4]}"}).json()
        po = post("/api/purchase-orders", {"supplier": sup["id"]}).json()
        post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 10})

        r = post(f"/api/purchase-orders/{po['id']}/receive", {"location": loc["id"]})
        assert r.status_code == 400

    def test_cannot_issue_already_received_po(self):
        """Cannot issue a received PO."""
        sup = post("/api/suppliers", {"name": f"NoReIss-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"NoReIssP-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc = post("/api/locations", {"name": f"NoReIssL-{U}-{uuid.uuid4().hex[:4]}"}).json()
        po = post("/api/purchase-orders", {"supplier": sup["id"]}).json()
        post("/api/po-lines", {"order": po["id"], "part": part["id"], "quantity": 10})
        post(f"/api/purchase-orders/{po['id']}/issue")
        post(f"/api/purchase-orders/{po['id']}/receive", {"location": loc["id"]})

        r = post(f"/api/purchase-orders/{po['id']}/issue")
        assert r.status_code == 400


class TestCategoryDeletionCascade:
    """Pattern 7: Category deletion cascade effects on parts and subcategories."""

    def test_deep_category_deletion_cascades(self):
        """Deleting root category cascades through all levels."""
        # 1. Create 3-level category tree
        root = post("/api/categories", {"name": f"CascRoot-{U}-{uuid.uuid4().hex[:4]}"}).json()
        mid = post("/api/categories", {"name": f"CascMid-{U}-{uuid.uuid4().hex[:4]}", "parent": root["id"]}).json()
        leaf = post("/api/categories", {"name": f"CascLeaf-{U}-{uuid.uuid4().hex[:4]}", "parent": mid["id"]}).json()

        # 2. Add parts at each level
        p_root = post("/api/parts", {"name": f"CascPR-{U}-{uuid.uuid4().hex[:4]}", "category": root["id"]}).json()
        p_mid = post("/api/parts", {"name": f"CascPM-{U}-{uuid.uuid4().hex[:4]}", "category": mid["id"]}).json()
        p_leaf = post("/api/parts", {"name": f"CascPL-{U}-{uuid.uuid4().hex[:4]}", "category": leaf["id"]}).json()

        # 3. Delete root
        r = delete(f"/api/categories/{root['id']}")
        assert r.status_code == 204

        # 4. All subcategories should be gone
        assert get(f"/api/categories/{root['id']}").status_code == 404
        assert get(f"/api/categories/{mid['id']}").status_code == 404
        assert get(f"/api/categories/{leaf['id']}").status_code == 404

        # 5. All parts still exist but with category=null
        for pid in [p_root["id"], p_mid["id"], p_leaf["id"]]:
            resp = get(f"/api/parts/{pid}")
            assert resp.status_code == 200
            assert resp.json()["category"] is None


class TestLocationDeletionCascade:
    """Pattern 7: Location deletion effects on stock items."""

    def test_deep_location_deletion_nullifies_stock(self):
        """Deleting location hierarchy nullifies all stock items."""
        # 1. Create location hierarchy
        wh = post("/api/locations", {"name": f"LCDWH-{U}-{uuid.uuid4().hex[:4]}"}).json()
        shelf = post("/api/locations", {"name": f"LCDSh-{U}-{uuid.uuid4().hex[:4]}", "parent": wh["id"]}).json()
        bin_ = post("/api/locations", {"name": f"LCDBin-{U}-{uuid.uuid4().hex[:4]}", "parent": shelf["id"]}).json()

        # 2. Create stock at each level
        part = post("/api/parts", {"name": f"LCDPart-{U}-{uuid.uuid4().hex[:4]}"}).json()
        s_wh = post("/api/stock", {"part": part["id"], "quantity": 10, "location": wh["id"]}).json()
        s_sh = post("/api/stock", {"part": part["id"], "quantity": 20, "location": shelf["id"]}).json()
        s_bin = post("/api/stock", {"part": part["id"], "quantity": 30, "location": bin_["id"]}).json()

        # 3. Delete warehouse (root)
        r = delete(f"/api/locations/{wh['id']}")
        assert r.status_code == 204

        # 4. Sublocations gone
        assert get(f"/api/locations/{wh['id']}").status_code == 404
        assert get(f"/api/locations/{shelf['id']}").status_code == 404
        assert get(f"/api/locations/{bin_['id']}").status_code == 404

        # 5. Stock items still exist with location=null
        for sid in [s_wh["id"], s_sh["id"], s_bin["id"]]:
            resp = get(f"/api/stock/{sid}")
            assert resp.status_code == 200
            assert resp.json()["location"] is None

        # 6. Part total stock preserved
        p_resp = get(f"/api/parts/{part['id']}")
        assert p_resp.json()["total_stock"] == 60  # 10 + 20 + 30


class TestPartDeletionConstraintsWorkflow:
    """Pattern 7+8: Part deletion blocked by various references."""

    def test_part_deletion_blocked_then_allowed_after_cleanup(self):
        """
        Part with stock can't be deleted, but after removing stock it can.
        """
        # 1. Create part and stock
        part = post("/api/parts", {"name": f"DelClean-{U}-{uuid.uuid4().hex[:4]}"}).json()
        stock = post("/api/stock", {"part": part["id"], "quantity": 10}).json()

        # 2. Try delete → fail
        r = delete(f"/api/parts/{part['id']}")
        assert r.status_code == 400

        # 3. Remove stock
        delete(f"/api/stock/{stock['id']}")

        # 4. Now delete succeeds
        r2 = delete(f"/api/parts/{part['id']}")
        assert r2.status_code == 204
        assert get(f"/api/parts/{part['id']}").status_code == 404

    def test_part_deletion_blocked_by_bom_then_allowed(self):
        """Part in BOM can't be deleted, but after removing BOM it can."""
        asm = post("/api/parts", {"name": f"DelBomA-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp = post("/api/parts", {"name": f"DelBomC-{U}-{uuid.uuid4().hex[:4]}"}).json()
        bom = post("/api/bom", {"part": asm["id"], "sub_part": comp["id"], "quantity": 1}).json()

        # Can't delete comp (sub_part ref)
        assert delete(f"/api/parts/{comp['id']}").status_code == 400
        # Can't delete asm (part ref)
        assert delete(f"/api/parts/{asm['id']}").status_code == 400

        # Remove BOM
        delete(f"/api/bom/{bom['id']}")

        # Now both can be deleted
        assert delete(f"/api/parts/{comp['id']}").status_code == 204
        assert delete(f"/api/parts/{asm['id']}").status_code == 204


class TestSupplierDeletionConstraintWorkflow:
    """Pattern 7: Supplier can't be deleted with supplier parts."""

    def test_supplier_deletion_blocked_then_allowed(self):
        """Supplier with parts blocked, after removing parts it can be deleted."""
        sup = post("/api/suppliers", {"name": f"SupDel-{U}-{uuid.uuid4().hex[:4]}"}).json()
        part = post("/api/parts", {"name": f"SupDelP-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sp = post("/api/supplier-parts", {
            "supplier": sup["id"],
            "part": part["id"],
            "SKU": f"SD-{uuid.uuid4().hex[:6]}",
        }).json()

        # Can't delete supplier
        r = delete(f"/api/suppliers/{sup['id']}")
        assert r.status_code == 400

        # Remove supplier part
        delete(f"/api/supplier-parts/{sp['id']}")

        # Now can delete supplier
        r2 = delete(f"/api/suppliers/{sup['id']}")
        assert r2.status_code == 204
        assert get(f"/api/suppliers/{sup['id']}").status_code == 404


class TestVariantAndTemplateWorkflow:
    """Pattern 5+8: Template/variant validation enforced."""

    def test_template_variant_lifecycle(self):
        """Full lifecycle: create template, create variants, verify constraints."""
        # 1. Create template
        tmpl = post("/api/parts", {
            "name": f"Tmpl-{U}-{uuid.uuid4().hex[:4]}",
            "is_template": True,
        }).json()
        assert tmpl["is_template"] is True
        assert tmpl["variant_of"] is None

        # 2. Create variant
        var1 = post("/api/parts", {
            "name": f"Var1-{U}-{uuid.uuid4().hex[:4]}",
            "variant_of": tmpl["id"],
        }).json()
        assert var1["variant_of"] == tmpl["id"]
        assert var1["is_template"] is False

        # 3. Can't create variant of non-template
        non_tmpl = post("/api/parts", {"name": f"NonTmpl-{U}-{uuid.uuid4().hex[:4]}"}).json()
        r = post("/api/parts", {"name": f"BadVar-{U}-{uuid.uuid4().hex[:4]}", "variant_of": non_tmpl["id"]})
        assert r.status_code == 400

        # 4. Can't create template that is also a variant
        r2 = post("/api/parts", {
            "name": f"TmplVar-{U}-{uuid.uuid4().hex[:4]}",
            "is_template": True,
            "variant_of": tmpl["id"],
        })
        assert r2.status_code == 400

        # 5. Verify template still retrievable
        tmpl_resp = get(f"/api/parts/{tmpl['id']}")
        assert tmpl_resp.status_code == 200
        assert tmpl_resp.json()["is_template"] is True


class TestBuildOrderEdgeCases:
    """Pattern 5+8: Build order edge cases and state transitions."""

    def test_cannot_complete_then_cancel_or_vice_versa(self):
        """State transition: pending->complete blocks cancel; pending->cancel blocks complete."""
        asm = post("/api/parts", {"name": f"BldEdge-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp = post("/api/parts", {"name": f"BldEdgeC-{U}-{uuid.uuid4().hex[:4]}"}).json()
        post("/api/bom", {"part": asm["id"], "sub_part": comp["id"], "quantity": 1})
        post("/api/stock", {"part": comp["id"], "quantity": 100})

        # Build 1: complete then try cancel
        b1 = post("/api/builds", {"part": asm["id"], "quantity": 1}).json()
        post(f"/api/builds/{b1['id']}/complete")
        r1 = post(f"/api/builds/{b1['id']}/cancel")
        assert r1.status_code == 400

        # Build 2: cancel then try complete
        b2 = post("/api/builds", {"part": asm["id"], "quantity": 1}).json()
        post(f"/api/builds/{b2['id']}/cancel")
        r2 = post(f"/api/builds/{b2['id']}/complete")
        assert r2.status_code == 400

        # Verify final states
        assert get(f"/api/builds/{b1['id']}").json()["status"] == "complete"
        assert get(f"/api/builds/{b2['id']}").json()["status"] == "cancelled"

    def test_build_insufficient_one_of_many_components(self):
        """If even one BOM item has insufficient stock, build fails."""
        asm = post("/api/parts", {"name": f"BldInsuf-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        c1 = post("/api/parts", {"name": f"BInsC1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        c2 = post("/api/parts", {"name": f"BInsC2-{U}-{uuid.uuid4().hex[:4]}"}).json()

        post("/api/bom", {"part": asm["id"], "sub_part": c1["id"], "quantity": 5})
        post("/api/bom", {"part": asm["id"], "sub_part": c2["id"], "quantity": 10})

        # c1 has enough, c2 does not
        post("/api/stock", {"part": c1["id"], "quantity": 100})
        post("/api/stock", {"part": c2["id"], "quantity": 5})  # Need 10*3=30, only have 5

        build = post("/api/builds", {"part": asm["id"], "quantity": 3}).json()
        r = post(f"/api/builds/{build['id']}/complete")
        assert r.status_code == 400

        # Verify no stock was consumed (transaction rollback)
        assert get(f"/api/parts/{c1['id']}").json()["total_stock"] == 100
        assert get(f"/api/parts/{c2['id']}").json()["total_stock"] == 5
        assert get(f"/api/parts/{asm['id']}").json()["total_stock"] == 0


class TestSerialNumberWorkflow:
    """Pattern 8: Serial number uniqueness per part."""

    def test_serial_number_uniqueness_full_workflow(self):
        """Serial numbers unique per part, same serial across parts OK."""
        p1 = post("/api/parts", {"name": f"SerWF1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        p2 = post("/api/parts", {"name": f"SerWF2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sn = f"SN-UNIQUE-{uuid.uuid4().hex[:6]}"

        # 1. Create with serial on p1
        s1 = post("/api/stock", {"part": p1["id"], "quantity": 1, "serial_number": sn})
        assert s1.status_code == 201
        assert s1.json()["serial_number"] == sn

        # 2. Same serial on p1 → fail
        s2 = post("/api/stock", {"part": p1["id"], "quantity": 1, "serial_number": sn})
        assert s2.status_code == 400

        # 3. Same serial on p2 → OK (different part)
        s3 = post("/api/stock", {"part": p2["id"], "quantity": 1, "serial_number": sn})
        assert s3.status_code == 201

        # 4. Null serial numbers are fine (multiple)
        s4 = post("/api/stock", {"part": p1["id"], "quantity": 5, "serial_number": None})
        assert s4.status_code == 201
        s5 = post("/api/stock", {"part": p1["id"], "quantity": 3})
        assert s5.status_code == 201

        # 5. Verify total stock
        resp = get(f"/api/parts/{p1['id']}")
        assert resp.json()["total_stock"] == 9  # 1 + 5 + 3


class TestEndToEndManufacturing:
    """Pattern 2+5+7: Full manufacturing workflow from purchase to build."""

    def test_purchase_then_build_lifecycle(self):
        """
        Purchase components → receive → build assembly → verify all stock levels.
        Covers: PO, PO lines, stock creation, BOM, build, stock consumption.
        """
        # 1. Setup: supplier, parts, location, BOM
        sup = post("/api/suppliers", {"name": f"E2ESup-{U}-{uuid.uuid4().hex[:4]}"}).json()
        asm = post("/api/parts", {"name": f"E2EAsm-{U}-{uuid.uuid4().hex[:4]}", "assembly": True}).json()
        comp_a = post("/api/parts", {"name": f"E2ECA-{U}-{uuid.uuid4().hex[:4]}"}).json()
        comp_b = post("/api/parts", {"name": f"E2ECB-{U}-{uuid.uuid4().hex[:4]}"}).json()
        loc = post("/api/locations", {"name": f"E2ELoc-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # BOM: assembly = 2x comp_a + 1x comp_b
        post("/api/bom", {"part": asm["id"], "sub_part": comp_a["id"], "quantity": 2})
        post("/api/bom", {"part": asm["id"], "sub_part": comp_b["id"], "quantity": 1})

        # 2. Purchase order for components
        po = post("/api/purchase-orders", {"supplier": sup["id"], "reference": "E2E-PO"}).json()
        post("/api/po-lines", {"order": po["id"], "part": comp_a["id"], "quantity": 20})
        post("/api/po-lines", {"order": po["id"], "part": comp_b["id"], "quantity": 10})

        # 3. Issue and receive PO
        post(f"/api/purchase-orders/{po['id']}/issue")
        recv = post(f"/api/purchase-orders/{po['id']}/receive", {"location": loc["id"]})
        assert recv.status_code == 200

        # 4. Verify stock levels after receiving
        assert get(f"/api/parts/{comp_a['id']}").json()["total_stock"] == 20
        assert get(f"/api/parts/{comp_b['id']}").json()["total_stock"] == 10

        # 5. Build 5 assemblies (needs 10x comp_a + 5x comp_b)
        build = post("/api/builds", {"part": asm["id"], "quantity": 5}).json()
        r = post(f"/api/builds/{build['id']}/complete")
        assert r.status_code == 200

        # 6. Verify final stock levels
        assert get(f"/api/parts/{comp_a['id']}").json()["total_stock"] == 10  # 20-10
        assert get(f"/api/parts/{comp_b['id']}").json()["total_stock"] == 5   # 10-5
        assert get(f"/api/parts/{asm['id']}").json()["total_stock"] == 5

        # 7. Try to build 6 more (needs 12x comp_a, only have 10) → fail
        build2 = post("/api/builds", {"part": asm["id"], "quantity": 6}).json()
        r2 = post(f"/api/builds/{build2['id']}/complete")
        assert r2.status_code == 400

        # 8. Stock unchanged after failed build
        assert get(f"/api/parts/{comp_a['id']}").json()["total_stock"] == 10
        assert get(f"/api/parts/{comp_b['id']}").json()["total_stock"] == 5
        assert get(f"/api/parts/{asm['id']}").json()["total_stock"] == 5
