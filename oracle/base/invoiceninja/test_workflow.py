"""
BackendForge — L3 Workflow Tests for Invoice Ninja
Complex multi-step workflows that cross multiple entity types.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def unique():
    return uuid.uuid4().hex[:8]


def h(key=None):
    return {"X-Api-Key": key or f"company-{unique()}", "Content-Type": "application/json"}


def post(path, data, hdr):
    return requests.post(f"{BASE_URL}{path}", json=data, headers=hdr, timeout=30)


def get(path, hdr, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=hdr, timeout=30)


def put(path, data, hdr):
    return requests.put(f"{BASE_URL}{path}", json=data, headers=hdr, timeout=30)


def delete(path, hdr):
    return requests.delete(f"{BASE_URL}{path}", headers=hdr, timeout=30)


class TestFullInvoicingWorkflow:
    """Pattern 5+7: Complete invoicing cycle with payments and client balance."""

    def test_create_invoice_pay_verify_balances(self):
        hdr = h()
        # 1. Create client
        client = post("/api/clients", {"name": f"FullWF-{unique()}", "email": "wf@test.com", "currency": "USD"}, hdr).json()
        assert client["balance"] == 0
        assert client["paid_to_date"] == 0

        # 2. Create invoice
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [
                {"description": "Consulting", "quantity": 10, "unit_cost": 15000},
                {"description": "Support", "quantity": 5, "unit_cost": 5000}
            ],
            "tax_name": "GST",
            "tax_rate": 10
        }, hdr).json()
        # subtotal = 10*15000 + 5*5000 = 175000
        # tax = 175000 * 10/100 = 17500
        # amount = 175000 + 17500 = 192500
        assert inv["amount"] == 192500
        assert inv["balance"] == 192500
        assert inv["status"] == "draft"
        assert inv["number"] == "INV-0001"

        # 3. Mark sent
        r = post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        assert r.json()["status"] == "sent"

        # 4. Client balance should reflect
        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["balance"] == 192500

        # 5. Partial payment
        pmt = post("/api/payments", {
            "client_id": client["id"],
            "amount": 100000,
            "date": "2024-06-01",
            "invoices": [{"invoice_id": inv["id"], "amount": 100000}]
        }, hdr).json()
        assert pmt["amount"] == 100000

        # 6. Invoice status → partial
        inv2 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv2["status"] == "partial"
        assert inv2["balance"] == 92500
        assert inv2["paid_to_date"] == 100000

        # 7. Client balance updated
        c2 = get(f"/api/clients/{client['id']}", hdr).json()
        assert c2["balance"] == 92500
        assert c2["paid_to_date"] == 100000

        # 8. Full remaining payment
        post("/api/payments", {
            "client_id": client["id"],
            "amount": 92500,
            "date": "2024-06-15",
            "invoices": [{"invoice_id": inv["id"], "amount": 92500}]
        }, hdr)

        # 9. Invoice → paid
        inv3 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv3["status"] == "paid"
        assert inv3["balance"] == 0

        # 10. Client fully paid
        c3 = get(f"/api/clients/{client['id']}", hdr).json()
        assert c3["balance"] == 0
        assert c3["paid_to_date"] == 192500


class TestQuoteToInvoiceWorkflow:
    """Pattern 5+7: Quote lifecycle through conversion."""

    def test_quote_approval_and_conversion(self):
        hdr = h()
        client = post("/api/clients", {"name": f"QWF-{unique()}"}, hdr).json()

        # 1. Create quote
        quote = post("/api/quotes", {
            "client_id": client["id"],
            "line_items": [
                {"description": "Project Phase 1", "quantity": 1, "unit_cost": 50000},
                {"description": "Project Phase 2", "quantity": 1, "unit_cost": 30000}
            ],
            "discount": 5000,
            "discount_type": "amount"
        }, hdr).json()
        assert quote["number"] == "QTE-0001"
        assert quote["status"] == "draft"
        # amount = 80000 - 5000 = 75000
        assert quote["amount"] == 75000

        # 2. Approve
        r = post(f"/api/quotes/{quote['id']}/actions/approve", {}, hdr)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        # 3. Convert to invoice — returns the new invoice
        r2 = post(f"/api/quotes/{quote['id']}/actions/convert_to_invoice", {}, hdr)
        assert r2.status_code == 200
        new_invoice = r2.json()
        assert new_invoice["client_id"] == client["id"]
        assert len(new_invoice["line_items"]) == 2

        # 4. Verify quote is now converted
        q2 = get(f"/api/quotes/{quote['id']}", hdr).json()
        assert q2["status"] == "converted"
        assert q2["invoice_id"] == new_invoice["id"]

        # 5. Verify invoice amount
        inv = get(f"/api/invoices/{new_invoice['id']}", hdr).json()
        assert inv["amount"] == 75000

        # 5. Cannot convert again
        r3 = post(f"/api/quotes/{quote['id']}/actions/convert_to_invoice", {}, hdr)
        assert r3.status_code == 422


class TestRefundWorkflow:
    """Pattern 5+7: Full refund lifecycle."""

    def test_payment_refund_restores_invoice_balance(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Refund-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 20000}]}, hdr).json()
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)

        # 1. Full payment
        pmt = post("/api/payments", {"client_id": client["id"], "amount": 20000, "date": "2024-05-01", "invoices": [{"invoice_id": inv["id"], "amount": 20000}]}, hdr).json()

        # 2. Invoice paid
        assert get(f"/api/invoices/{inv['id']}", hdr).json()["status"] == "paid"

        # 3. Refund 8000
        r = post(f"/api/payments/{pmt['id']}/actions/refund", {"amount": 8000}, hdr)
        assert r.status_code == 200
        assert r.json()["refunded"] == 8000

        # 4. Invoice balance restored
        inv2 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv2["balance"] == 8000
        # Status should no longer be "paid"
        assert inv2["status"] != "paid"

        # 5. Client balance updated
        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["balance"] == 8000
        # paid_to_date = 20000 - 8000 = 12000
        assert c["paid_to_date"] == 12000


class TestProjectTaskWorkflow:
    """Pattern 2+5: Projects with tasks and computed hours."""

    def test_project_total_hours_from_tasks(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Proj-{unique()}"}, hdr).json()
        project = post("/api/projects", {"name": f"BigProject-{unique()}", "client_id": client["id"], "task_rate": 12000, "budgeted_hours": 100}, hdr).json()

        end_timestamp = 1_700_007_200
        # Task 1: 2 hours
        t1 = post("/api/tasks", {
            "client_id": client["id"],
            "project_id": project["id"],
            "description": "Backend",
            "rate": 12000,
            "time_log": [[end_timestamp - 7200, end_timestamp]]
        }, hdr).json()
        assert t1["amount"] == 24000  # 2h * 12000

        # Task 2: 1.5 hours
        t2 = post("/api/tasks", {
            "client_id": client["id"],
            "project_id": project["id"],
            "description": "Frontend",
            "rate": 12000,
            "time_log": [[end_timestamp - 5400, end_timestamp]]
        }, hdr).json()

        # Project total_hours should be sum
        proj = get(f"/api/projects/{project['id']}", hdr).json()
        assert proj["total_hours"] == pytest.approx(3.5, abs=0.01)


class TestCascadeDeleteClient:
    """Pattern 7: Client deletion cascades to all related entities."""

    def test_delete_client_cascades(self):
        hdr = h()
        client = post("/api/clients", {"name": f"CascCli-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 1000}]}, hdr).json()
        quote = post("/api/quotes", {"client_id": client["id"], "line_items": [{"description": "Y", "quantity": 1, "unit_cost": 500}]}, hdr).json()
        project = post("/api/projects", {"name": "P", "client_id": client["id"]}, hdr).json()

        # Delete client
        r = delete(f"/api/clients/{client['id']}", hdr)
        assert r.status_code == 200

        # Everything should be gone
        assert get(f"/api/clients/{client['id']}", hdr).status_code == 404
        assert get(f"/api/invoices/{inv['id']}", hdr).status_code == 404
        assert get(f"/api/quotes/{quote['id']}", hdr).status_code == 404
        assert get(f"/api/projects/{project['id']}", hdr).status_code == 404


class TestDeleteProjectUnlinksTasks:
    """Pattern 7: Deleting project doesn't delete tasks, just unlinks."""

    def test_delete_project_keeps_tasks(self):
        hdr = h()
        client = post("/api/clients", {"name": f"DPT-{unique()}"}, hdr).json()
        project = post("/api/projects", {"name": f"DelProj-{unique()}", "client_id": client["id"]}, hdr).json()
        end_timestamp = 1_700_007_200
        task = post("/api/tasks", {
            "client_id": client["id"],
            "project_id": project["id"],
            "description": "Linked task",
            "rate": 5000,
            "time_log": [[end_timestamp - 3600, end_timestamp]]
        }, hdr).json()

        # Delete project
        delete(f"/api/projects/{project['id']}", hdr)

        # Task still exists but project_id is null
        t = get(f"/api/tasks/{task['id']}", hdr).json()
        assert t["id"] == task["id"]
        assert t["project_id"] is None


class TestMultiInvoicePayment:
    """Pattern 5: Payment applied across multiple invoices."""

    def test_payment_across_two_invoices(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Multi-{unique()}"}, hdr).json()
        inv1 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "A", "quantity": 1, "unit_cost": 5000}]}, hdr).json()
        inv2 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "B", "quantity": 1, "unit_cost": 3000}]}, hdr).json()
        post(f"/api/invoices/{inv1['id']}/actions/mark_sent", {}, hdr)
        post(f"/api/invoices/{inv2['id']}/actions/mark_sent", {}, hdr)

        # Single payment covering both invoices
        pmt = post("/api/payments", {
            "client_id": client["id"],
            "amount": 8000,
            "date": "2024-07-01",
            "invoices": [
                {"invoice_id": inv1["id"], "amount": 5000},
                {"invoice_id": inv2["id"], "amount": 3000}
            ]
        }, hdr).json()
        assert pmt["amount"] == 8000

        # Both should be paid
        assert get(f"/api/invoices/{inv1['id']}", hdr).json()["status"] == "paid"
        assert get(f"/api/invoices/{inv2['id']}", hdr).json()["status"] == "paid"

        # Client fully paid
        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["balance"] == 0
        assert c["paid_to_date"] == 8000


class TestMarkPaidAction:
    """Pattern 5: mark_paid creates full payment automatically."""

    def test_mark_paid_updates_all_balances(self):
        hdr = h()
        client = post("/api/clients", {"name": f"MP-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [{"description": "Dev", "quantity": 20, "unit_cost": 7500}]
        }, hdr).json()
        assert inv["amount"] == 150000
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)

        # Mark paid
        r = post(f"/api/invoices/{inv['id']}/actions/mark_paid", {}, hdr)
        assert r.status_code == 200
        paid = r.json()
        assert paid["status"] == "paid"
        assert paid["balance"] == 0
        assert paid["paid_to_date"] == 150000

        # Client should reflect
        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["paid_to_date"] == 150000
        assert c["balance"] == 0


class TestExpenseWorkflow:
    """Pattern 1+2: Expense CRUD with fields."""

    def test_expense_crud(self):
        hdr = h()
        # Create
        exp = post("/api/expenses", {
            "vendor": f"Vendor-{unique()}",
            "category": "Software",
            "amount": 9900,
            "date": "2024-04-01",
            "currency": "USD"
        }, hdr).json()
        assert exp["vendor"].startswith("Vendor-")
        assert exp["amount"] == 9900
        assert exp["category"] == "Software"
        assert "id" in exp

        # Update
        r = put(f"/api/expenses/{exp['id']}", {"amount": 12000, "category": "Hardware"}, hdr)
        assert r.status_code == 200
        assert r.json()["amount"] == 12000
        assert r.json()["category"] == "Hardware"

        # Delete
        r2 = delete(f"/api/expenses/{exp['id']}", hdr)
        assert r2.status_code == 200
        assert get(f"/api/expenses/{exp['id']}", hdr).status_code == 404
