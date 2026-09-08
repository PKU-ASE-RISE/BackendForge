"""
BackendForge — L2 Integration Tests for Invoice Ninja
Adversarial tests targeting common LLM implementation bugs.
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


class TestInvoiceAmountComputation:
    """Pattern 5: Invoice amount is actually computed from line items."""

    def test_invoice_amount_computed_from_line_items(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Client-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [
                {"description": "Service A", "quantity": 2, "unit_cost": 10000},
                {"description": "Service B", "quantity": 1, "unit_cost": 5000}
            ]
        }, hdr).json()
        # subtotal = 2*10000 + 1*5000 = 25000
        assert inv["amount"] == 25000
        assert inv["balance"] == 25000

    def test_invoice_with_percentage_discount(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Disc-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [{"description": "Work", "quantity": 1, "unit_cost": 10000}],
            "discount": 10,
            "discount_type": "percent"
        }, hdr).json()
        # subtotal=10000, discount=10000*10/100=1000, amount=9000
        assert inv["amount"] == 9000

    def test_invoice_with_amount_discount(self):
        hdr = h()
        client = post("/api/clients", {"name": f"AmDisc-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [{"description": "Work", "quantity": 1, "unit_cost": 10000}],
            "discount": 2000,
            "discount_type": "amount"
        }, hdr).json()
        # subtotal=10000, discount=2000, amount=8000
        assert inv["amount"] == 8000

    def test_invoice_with_tax(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Tax-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {
            "client_id": client["id"],
            "line_items": [{"description": "Work", "quantity": 1, "unit_cost": 10000}],
            "tax_name": "VAT",
            "tax_rate": 20
        }, hdr).json()
        # subtotal=10000, tax=10000*20/100=2000, amount=12000
        assert inv["amount"] == 12000


class TestInvoiceNumbering:
    """Pattern 5+8: Invoice auto-numbering."""

    def test_invoices_auto_numbered_sequentially(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Num-{unique()}"}, hdr).json()
        inv1 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "A", "quantity": 1, "unit_cost": 100}]}, hdr).json()
        inv2 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "B", "quantity": 1, "unit_cost": 200}]}, hdr).json()
        assert inv1["number"] == "INV-0001"
        assert inv2["number"] == "INV-0002"

    def test_quote_numbering_separate(self):
        hdr = h()
        client = post("/api/clients", {"name": f"QNum-{unique()}"}, hdr).json()
        q1 = post("/api/quotes", {"client_id": client["id"], "line_items": [{"description": "Q", "quantity": 1, "unit_cost": 100}]}, hdr).json()
        assert q1["number"] == "QTE-0001"


class TestPaymentApplication:
    """Pattern 5+7: Payments reduce invoice balance."""

    def test_payment_reduces_invoice_balance(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Pay-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 10000}]}, hdr).json()
        # Mark sent first
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)

        # Apply partial payment
        pmt = post("/api/payments", {
            "client_id": client["id"],
            "amount": 4000,
            "date": "2024-03-15",
            "invoices": [{"invoice_id": inv["id"], "amount": 4000}]
        }, hdr).json()
        assert pmt["amount"] == 4000

        # Invoice balance should decrease
        inv2 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv2["balance"] == 6000
        assert inv2["paid_to_date"] == 4000
        assert inv2["status"] == "partial"

    def test_full_payment_marks_invoice_paid(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Full-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 5000}]}, hdr).json()
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        post("/api/payments", {"client_id": client["id"], "amount": 5000, "date": "2024-03-15", "invoices": [{"invoice_id": inv["id"], "amount": 5000}]}, hdr)

        inv2 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv2["balance"] == 0
        assert inv2["status"] == "paid"


class TestClientComputedFields:
    """Pattern 5: Client balance and paid_to_date are computed."""

    def test_client_balance_reflects_unpaid_invoices(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Bal-{unique()}"}, hdr).json()
        inv1 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "A", "quantity": 1, "unit_cost": 10000}]}, hdr).json()
        inv2 = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "B", "quantity": 1, "unit_cost": 5000}]}, hdr).json()
        # Mark both sent (drafts don't count in balance)
        post(f"/api/invoices/{inv1['id']}/actions/mark_sent", {}, hdr)
        post(f"/api/invoices/{inv2['id']}/actions/mark_sent", {}, hdr)

        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["balance"] == 15000

    def test_client_paid_to_date_reflects_payments(self):
        hdr = h()
        client = post("/api/clients", {"name": f"PTD-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 8000}]}, hdr).json()
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        post("/api/payments", {"client_id": client["id"], "amount": 3000, "date": "2024-03-15", "invoices": [{"invoice_id": inv["id"], "amount": 3000}]}, hdr)

        c = get(f"/api/clients/{client['id']}", hdr).json()
        assert c["paid_to_date"] == 3000
        assert c["balance"] == 5000


class TestInvoiceStatusTransitions:
    """Pattern 4+5: Status transitions and action endpoints."""

    def test_mark_sent_changes_status(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Sent-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 1000}]}, hdr).json()
        assert inv["status"] == "draft"
        r = post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        assert r.status_code == 200
        assert r.json()["status"] == "sent"

    def test_mark_paid_creates_payment(self):
        hdr = h()
        client = post("/api/clients", {"name": f"MPaid-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 7000}]}, hdr).json()
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        r = post(f"/api/invoices/{inv['id']}/actions/mark_paid", {}, hdr)
        assert r.status_code == 200
        assert r.json()["status"] == "paid"
        assert r.json()["balance"] == 0


class TestQuoteConversion:
    """Pattern 5+7: Quote to invoice conversion."""

    def test_convert_quote_creates_invoice(self):
        hdr = h()
        client = post("/api/clients", {"name": f"QConv-{unique()}"}, hdr).json()
        quote = post("/api/quotes", {
            "client_id": client["id"],
            "line_items": [{"description": "Consulting", "quantity": 10, "unit_cost": 15000}],
            "discount": 5,
            "discount_type": "percent"
        }, hdr).json()
        assert quote["status"] == "draft"

        # Approve first
        post(f"/api/quotes/{quote['id']}/actions/approve", {}, hdr)

        # Convert — returns the new invoice
        r = post(f"/api/quotes/{quote['id']}/actions/convert_to_invoice", {}, hdr)
        assert r.status_code == 200
        new_invoice = r.json()
        assert new_invoice["client_id"] == client["id"]
        assert len(new_invoice["line_items"]) == 1
        assert new_invoice["line_items"][0]["unit_cost"] == 15000

        # Verify quote is now converted
        q2 = get(f"/api/quotes/{quote['id']}", hdr).json()
        assert q2["status"] == "converted"
        assert q2["invoice_id"] is not None
        assert q2["invoice_id"] == new_invoice["id"]

    def test_cannot_convert_already_converted_quote(self):
        hdr = h()
        client = post("/api/clients", {"name": f"DConv-{unique()}"}, hdr).json()
        quote = post("/api/quotes", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 100}]}, hdr).json()
        post(f"/api/quotes/{quote['id']}/actions/approve", {}, hdr)
        post(f"/api/quotes/{quote['id']}/actions/convert_to_invoice", {}, hdr)
        r = post(f"/api/quotes/{quote['id']}/actions/convert_to_invoice", {}, hdr)
        assert r.status_code == 422


class TestTaskTimeComputation:
    """Pattern 5: Task amount computed from time_log * rate."""

    def test_task_amount_computed(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Task-{unique()}"}, hdr).json()
        end_timestamp = 1_700_007_200
        task = post("/api/tasks", {
            "client_id": client["id"],
            "description": "Development",
            "rate": 10000,
            "time_log": [
                [end_timestamp - 7200, end_timestamp - 3600],
                [end_timestamp - 3600, end_timestamp],
            ],  # 2 hours total
        }, hdr).json()
        # 2 hours * 10000 = 20000
        assert task["amount"] == 20000


class TestDataIsolation:
    """Pattern 6: Different API keys have isolated data."""

    def test_companies_cannot_see_each_other(self):
        h1 = h()
        h2 = h()
        client = post("/api/clients", {"name": f"Private-{unique()}"}, h1).json()
        r = get(f"/api/clients/{client['id']}", h2)
        assert r.status_code == 404

    def test_invoice_numbering_isolated_per_company(self):
        h1 = h()
        h2 = h()
        c1 = post("/api/clients", {"name": "C1"}, h1).json()
        c2 = post("/api/clients", {"name": "C2"}, h2).json()
        inv1 = post("/api/invoices", {"client_id": c1["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 100}]}, h1).json()
        inv2 = post("/api/invoices", {"client_id": c2["id"], "line_items": [{"description": "Y", "quantity": 1, "unit_cost": 200}]}, h2).json()
        assert inv1["number"] == "INV-0001"
        assert inv2["number"] == "INV-0001"  # independent counters


class TestPaginationMeta:
    """Pattern 3: Pagination metadata is correct."""

    def test_clients_pagination(self):
        hdr = h()
        for i in range(5):
            post("/api/clients", {"name": f"PgClient{i}-{unique()}"}, hdr)
        r = get("/api/clients", hdr, params={"per_page": 2, "page": 1})
        body = r.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["current_page"] == 1
        assert body["meta"]["per_page"] == 2
        assert body["meta"]["total"] >= 5
        assert len(body["data"]) == 2


class TestRefundWorkflow:
    """Pattern 5+7: Refund increases invoice balance."""

    def test_refund_increases_invoice_balance(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Ref-{unique()}"}, hdr).json()
        inv = post("/api/invoices", {"client_id": client["id"], "line_items": [{"description": "X", "quantity": 1, "unit_cost": 10000}]}, hdr).json()
        post(f"/api/invoices/{inv['id']}/actions/mark_sent", {}, hdr)
        pmt = post("/api/payments", {"client_id": client["id"], "amount": 10000, "date": "2024-03-15", "invoices": [{"invoice_id": inv["id"], "amount": 10000}]}, hdr).json()

        # Invoice should be paid
        inv2 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv2["status"] == "paid"

        # Refund half
        r = post(f"/api/payments/{pmt['id']}/actions/refund", {"amount": 5000}, hdr)
        assert r.status_code == 200

        # Invoice balance should increase
        inv3 = get(f"/api/invoices/{inv['id']}", hdr).json()
        assert inv3["balance"] == 5000


class TestAuthRequired:
    """Pattern 4: Auth enforcement."""

    def test_missing_key_returns_401(self):
        endpoints = ["/api/clients", "/api/invoices", "/api/products", "/api/payments"]
        for path in endpoints:
            r = requests.get(f"{BASE_URL}{path}", timeout=30)
            assert r.status_code == 401

    def test_delete_returns_200_with_message(self):
        hdr = h()
        client = post("/api/clients", {"name": f"Del-{unique()}"}, hdr).json()
        r = delete(f"/api/clients/{client['id']}", hdr)
        assert r.status_code == 200
        assert r.json()["message"] == "deleted"
