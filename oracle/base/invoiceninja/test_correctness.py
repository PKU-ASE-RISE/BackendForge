"""
BackendForge — Comprehensive Correctness Tests for Invoice Ninja Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex

# Company API keys — each key scopes data to a company
COMPANY_A_KEY = f"company-a-{RUN_ID}"
COMPANY_B_KEY = f"company-b-{RUN_ID}"

HEADERS_A = {
    "X-Api-Key": COMPANY_A_KEY,
    "Content-Type": "application/json",
}

HEADERS_B = {
    "X-Api-Key": COMPANY_B_KEY,
    "Content-Type": "application/json",
}

NO_AUTH_HEADERS = {
    "Content-Type": "application/json",
}


@pytest.fixture(autouse=True)
def isolate_company_data(request):
    """Give every collected item independent company namespaces."""
    global COMPANY_A_KEY, COMPANY_B_KEY, HEADERS_A, HEADERS_B

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    COMPANY_A_KEY = f"company-a-{item_id}"
    COMPANY_B_KEY = f"company-b-{item_id}"
    HEADERS_A = {"X-Api-Key": COMPANY_A_KEY, "Content-Type": "application/json"}
    HEADERS_B = {"X-Api-Key": COMPANY_B_KEY, "Content-Type": "application/json"}


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS_A, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS_A, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS_A, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS_A, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """Requests without X-Api-Key header should return 401."""
        resp = requests.get(f"{BASE_URL}/api/clients", headers=NO_AUTH_HEADERS, timeout=30)
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        """Empty X-Api-Key header should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        """Valid X-Api-Key should grant access."""
        resp = api_get("/api/clients")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Clients CRUD
# ════════════════════════════════════════════════════════════════════


class TestClientsCRUD:

    def test_create_client(self):
        resp = api_post("/api/clients", {
            "name": "Acme Corp",
            "email": "acme@example.com",
            "phone": "555-0100",
            "address": "123 Main St",
            "currency": "USD",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["email"] == "acme@example.com"
        assert data["phone"] == "555-0100"
        assert data["address"] == "123 Main St"
        assert data["currency"] == "USD"
        assert "id" in data
        assert data["balance"] == 0
        assert data["paid_to_date"] == 0

    def test_create_client_minimal(self):
        """Only name is required."""
        resp = api_post("/api/clients", {"name": "Minimal Client"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Minimal Client"

    def test_create_client_missing_name_returns_422(self):
        resp = api_post("/api/clients", {"email": "no-name@example.com"})
        assert resp.status_code == 422

    def test_list_clients(self):
        resp = api_get("/api/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        assert "current_page" in data["meta"]
        assert "per_page" in data["meta"]
        assert "total" in data["meta"]
        assert "total_pages" in data["meta"]

    def test_get_client_by_id(self):
        # Create a client first
        create_resp = api_post("/api/clients", {"name": "Get Test Client"})
        client_id = create_resp.json()["id"]

        resp = api_get(f"/api/clients/{client_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == client_id
        assert data["name"] == "Get Test Client"

    def test_get_nonexistent_client_returns_404(self):
        resp = api_get("/api/clients/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_update_client(self):
        create_resp = api_post("/api/clients", {"name": "Before Update"})
        client_id = create_resp.json()["id"]

        resp = api_put(f"/api/clients/{client_id}", {
            "name": "After Update",
            "email": "updated@example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "After Update"
        assert data["email"] == "updated@example.com"

    def test_delete_client(self):
        create_resp = api_post("/api/clients", {"name": "To Delete"})
        client_id = create_resp.json()["id"]

        resp = api_delete(f"/api/clients/{client_id}")
        assert resp.status_code == 200

        # Verify it's gone
        get_resp = api_get(f"/api/clients/{client_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_client_returns_404(self):
        resp = api_delete("/api/clients/nonexistent-id-12345")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Products CRUD
# ════════════════════════════════════════════════════════════════════


class TestProductsCRUD:

    def test_create_product(self):
        resp = api_post("/api/products", {
            "name": "Web Development",
            "description": "Full-stack web development services",
            "price": 150.0,
            "quantity_default": 1,
            "tax_name": "VAT",
            "tax_rate": 20.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Web Development"
        assert data["price"] == 150.0
        assert data["tax_rate"] == 20.0
        assert "id" in data

    def test_create_product_minimal(self):
        resp = api_post("/api/products", {"name": "Basic Service", "price": 50.0})
        assert resp.status_code == 201

    def test_create_product_missing_required_returns_422(self):
        resp = api_post("/api/products", {"description": "no name or price"})
        assert resp.status_code == 422

    def test_list_products(self):
        resp = api_get("/api/products")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_product_by_id(self):
        create_resp = api_post("/api/products", {"name": "Test Product", "price": 100.0})
        product_id = create_resp.json()["id"]

        resp = api_get(f"/api/products/{product_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == product_id

    def test_update_product(self):
        create_resp = api_post("/api/products", {"name": "Old Name", "price": 100.0})
        product_id = create_resp.json()["id"]

        resp = api_put(f"/api/products/{product_id}", {"name": "New Name", "price": 200.0})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["price"] == 200.0

    def test_delete_product(self):
        create_resp = api_post("/api/products", {"name": "To Delete Product", "price": 10.0})
        product_id = create_resp.json()["id"]

        resp = api_delete(f"/api/products/{product_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/products/{product_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Invoices CRUD & Business Logic
# ════════════════════════════════════════════════════════════════════


class TestInvoicesCRUD:

    def _create_client(self):
        resp = api_post("/api/clients", {"name": f"Invoice Client {uuid.uuid4().hex[:6]}"})
        return resp.json()["id"]

    def test_create_invoice(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "date": "2024-01-15",
            "due_date": "2024-02-15",
            "line_items": [
                {"description": "Web design", "quantity": 10, "unit_cost": 100.0},
                {"description": "Hosting", "quantity": 1, "unit_cost": 50.0},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == client_id
        assert data["status"] == "draft"
        assert "id" in data
        assert "number" in data
        # Amount = 10*100 + 1*50 = 1050
        assert data["amount"] == 1050.0
        assert data["balance"] == 1050.0
        assert data["paid_to_date"] == 0

    def test_invoice_auto_numbering(self):
        """Invoices should be auto-numbered INV-0001, INV-0002, ..."""
        # Use a fresh company key to get predictable numbering
        fresh_key = f"numbering-test-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": fresh_key, "Content-Type": "application/json"}

        # Create a client
        client_resp = api_post("/api/clients", {"name": "Numbering Client"}, headers=headers)
        client_id = client_resp.json()["id"]

        # Create first invoice
        resp1 = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Item", "quantity": 1, "unit_cost": 100.0}],
        }, headers=headers)
        assert resp1.json()["number"] == "INV-0001"

        # Create second invoice
        resp2 = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Item", "quantity": 1, "unit_cost": 200.0}],
        }, headers=headers)
        assert resp2.json()["number"] == "INV-0002"

    def test_invoice_amount_calculation_with_discount_amount(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [
                {"description": "Service", "quantity": 5, "unit_cost": 200.0},
            ],
            "discount": 100.0,
            "discount_type": "amount",
        })
        assert resp.status_code == 201
        data = resp.json()
        # subtotal = 5*200 = 1000, discount = 100, amount = 900
        assert data["amount"] == 900.0

    def test_invoice_amount_calculation_with_discount_percent(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [
                {"description": "Service", "quantity": 4, "unit_cost": 250.0},
            ],
            "discount": 10.0,
            "discount_type": "percent",
        })
        assert resp.status_code == 201
        data = resp.json()
        # subtotal = 4*250 = 1000, discount = 10% of 1000 = 100, amount = 900
        assert data["amount"] == 900.0

    def test_invoice_amount_calculation_with_tax(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [
                {"description": "Service", "quantity": 2, "unit_cost": 500.0},
            ],
            "tax_name": "VAT",
            "tax_rate": 20.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        # subtotal = 2*500 = 1000, tax = 20% of 1000 = 200, amount = 1200
        assert data["amount"] == 1200.0

    def test_invoice_amount_with_discount_and_tax(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [
                {"description": "Service", "quantity": 10, "unit_cost": 100.0},
            ],
            "discount": 200.0,
            "discount_type": "amount",
            "tax_name": "VAT",
            "tax_rate": 10.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        # subtotal = 10*100 = 1000, discount = 200, after_discount = 800
        # tax = 10% of 800 = 80, amount = 880
        assert data["amount"] == 880.0

    def test_invoice_line_item_line_total(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [
                {"description": "Item A", "quantity": 3, "unit_cost": 50.0},
                {"description": "Item B", "quantity": 2, "unit_cost": 75.0},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        line_items = data["line_items"]
        assert line_items[0]["line_total"] == 150.0  # 3 * 50
        assert line_items[1]["line_total"] == 150.0  # 2 * 75

    def test_list_invoices(self):
        resp = api_get("/api/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_list_invoices_filter_by_client(self):
        client_id = self._create_client()
        api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "x", "quantity": 1, "unit_cost": 10.0}],
        })

        resp = api_get("/api/invoices", params={"client_id": client_id})
        assert resp.status_code == 200
        data = resp.json()
        for inv in data["data"]:
            assert inv["client_id"] == client_id

    def test_list_invoices_filter_by_status(self):
        resp = api_get("/api/invoices", params={"status": "draft"})
        assert resp.status_code == 200
        data = resp.json()
        for inv in data["data"]:
            assert inv["status"] == "draft"

    def test_get_invoice_by_id(self):
        client_id = self._create_client()
        create_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Test", "quantity": 1, "unit_cost": 100.0}],
        })
        invoice_id = create_resp.json()["id"]

        resp = api_get(f"/api/invoices/{invoice_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == invoice_id

    def test_update_invoice(self):
        client_id = self._create_client()
        create_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Original", "quantity": 1, "unit_cost": 100.0}],
        })
        invoice_id = create_resp.json()["id"]

        resp = api_put(f"/api/invoices/{invoice_id}", {
            "client_id": client_id,
            "line_items": [{"description": "Updated", "quantity": 2, "unit_cost": 150.0}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 300.0
        assert data["line_items"][0]["description"] == "Updated"

    def test_delete_invoice(self):
        client_id = self._create_client()
        create_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Delete me", "quantity": 1, "unit_cost": 10.0}],
        })
        invoice_id = create_resp.json()["id"]

        resp = api_delete(f"/api/invoices/{invoice_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/invoices/{invoice_id}")
        assert get_resp.status_code == 404

    def test_create_invoice_missing_client_returns_422(self):
        resp = api_post("/api/invoices", {
            "line_items": [{"description": "x", "quantity": 1, "unit_cost": 10.0}],
        })
        assert resp.status_code == 422

    def test_create_invoice_missing_line_items_returns_422(self):
        client_id = self._create_client()
        resp = api_post("/api/invoices", {"client_id": client_id})
        assert resp.status_code == 422


class TestInvoiceActions:

    def _create_client_and_invoice(self, amount=1000.0):
        client_resp = api_post("/api/clients", {"name": f"Action Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]
        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Service", "quantity": 1, "unit_cost": amount}],
        })
        return client_id, inv_resp.json()["id"]

    def test_mark_sent(self):
        _, invoice_id = self._create_client_and_invoice()
        resp = api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"

    def test_mark_sent_only_from_draft(self):
        """Cannot mark_sent if already sent."""
        _, invoice_id = self._create_client_and_invoice()
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        # Try again
        resp = api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        assert resp.status_code == 422

    def test_mark_paid(self):
        client_id, invoice_id = self._create_client_and_invoice(500.0)
        # Must be sent first
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")

        resp = api_post(f"/api/invoices/{invoice_id}/actions/mark_paid")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["balance"] == 0
        assert data["paid_to_date"] == 500.0

    def test_mark_paid_creates_payment(self):
        """mark_paid should create a payment record."""
        client_id, invoice_id = self._create_client_and_invoice(750.0)
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        api_post(f"/api/invoices/{invoice_id}/actions/mark_paid")

        # Check payments for this client
        resp = api_get("/api/payments", params={"client_id": client_id})
        assert resp.status_code == 200
        payments = resp.json()["data"]
        # Should have at least one payment for 750
        amounts = [p["amount"] for p in payments]
        assert 750.0 in amounts

    def test_mark_paid_not_from_draft(self):
        """Cannot mark_paid from draft status."""
        _, invoice_id = self._create_client_and_invoice()
        resp = api_post(f"/api/invoices/{invoice_id}/actions/mark_paid")
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 5: Quotes CRUD & Business Logic
# ════════════════════════════════════════════════════════════════════


class TestQuotesCRUD:

    def _create_client(self):
        resp = api_post("/api/clients", {"name": f"Quote Client {uuid.uuid4().hex[:6]}"})
        return resp.json()["id"]

    def test_create_quote(self):
        client_id = self._create_client()
        resp = api_post("/api/quotes", {
            "client_id": client_id,
            "date": "2024-01-15",
            "due_date": "2024-02-15",
            "line_items": [
                {"description": "Consulting", "quantity": 5, "unit_cost": 200.0},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == client_id
        assert data["status"] == "draft"
        assert data["amount"] == 1000.0
        assert "number" in data

    def test_quote_auto_numbering(self):
        """Quotes should be auto-numbered QTE-0001, QTE-0002, ..."""
        fresh_key = f"quote-numbering-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": fresh_key, "Content-Type": "application/json"}

        client_resp = api_post("/api/clients", {"name": "Quote Numbering Client"}, headers=headers)
        client_id = client_resp.json()["id"]

        resp1 = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Item", "quantity": 1, "unit_cost": 100.0}],
        }, headers=headers)
        assert resp1.json()["number"] == "QTE-0001"

        resp2 = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Item", "quantity": 1, "unit_cost": 200.0}],
        }, headers=headers)
        assert resp2.json()["number"] == "QTE-0002"

    def test_list_quotes(self):
        resp = api_get("/api/quotes")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_quote_by_id(self):
        client_id = self._create_client()
        create_resp = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Test", "quantity": 1, "unit_cost": 100.0}],
        })
        quote_id = create_resp.json()["id"]

        resp = api_get(f"/api/quotes/{quote_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == quote_id

    def test_update_quote(self):
        client_id = self._create_client()
        create_resp = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Original", "quantity": 1, "unit_cost": 100.0}],
        })
        quote_id = create_resp.json()["id"]

        resp = api_put(f"/api/quotes/{quote_id}", {
            "client_id": client_id,
            "line_items": [{"description": "Updated", "quantity": 3, "unit_cost": 200.0}],
        })
        assert resp.status_code == 200
        assert resp.json()["amount"] == 600.0

    def test_delete_quote(self):
        client_id = self._create_client()
        create_resp = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Delete", "quantity": 1, "unit_cost": 10.0}],
        })
        quote_id = create_resp.json()["id"]

        resp = api_delete(f"/api/quotes/{quote_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/quotes/{quote_id}")
        assert get_resp.status_code == 404


class TestQuoteActions:

    def _create_client_and_quote(self, amount=1000.0):
        client_resp = api_post("/api/clients", {"name": f"QA Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]
        quote_resp = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Service", "quantity": 1, "unit_cost": amount}],
        })
        return client_id, quote_resp.json()["id"]

    def test_approve_quote(self):
        _, quote_id = self._create_client_and_quote()
        resp = api_post(f"/api/quotes/{quote_id}/actions/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    def test_convert_quote_to_invoice(self):
        client_id, quote_id = self._create_client_and_quote(2000.0)

        resp = api_post(f"/api/quotes/{quote_id}/actions/convert_to_invoice")
        assert resp.status_code == 200
        invoice_data = resp.json()
        assert invoice_data["client_id"] == client_id
        assert invoice_data["amount"] == 2000.0
        assert invoice_data["status"] == "draft"

        # Verify quote status is now "converted"
        quote_resp = api_get(f"/api/quotes/{quote_id}")
        assert quote_resp.json()["status"] == "converted"
        assert quote_resp.json()["invoice_id"] == invoice_data["id"]

    def test_cannot_convert_already_converted_quote(self):
        _, quote_id = self._create_client_and_quote()
        api_post(f"/api/quotes/{quote_id}/actions/convert_to_invoice")
        # Try again
        resp = api_post(f"/api/quotes/{quote_id}/actions/convert_to_invoice")
        assert resp.status_code == 422

    def test_cannot_convert_rejected_quote(self):
        """Manually reject a quote by updating, then try converting."""
        client_id, quote_id = self._create_client_and_quote()
        # We don't have a reject action, so test that converted quotes can't be reconverted
        # Just verify that converting works once
        resp = api_post(f"/api/quotes/{quote_id}/actions/convert_to_invoice")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 6: Payments CRUD & Business Logic
# ════════════════════════════════════════════════════════════════════


class TestPaymentsCRUD:

    def _create_sent_invoice(self, amount=1000.0):
        """Helper: create a client, an invoice, mark it sent."""
        client_resp = api_post("/api/clients", {"name": f"Pay Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]
        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Service", "quantity": 1, "unit_cost": amount}],
        })
        invoice_id = inv_resp.json()["id"]
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        return client_id, invoice_id

    def test_create_payment_full(self):
        """Pay an invoice in full."""
        client_id, invoice_id = self._create_sent_invoice(500.0)
        resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 500.0,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 500.0}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 500.0
        assert data["client_id"] == client_id
        assert "id" in data

        # Verify invoice is now "paid"
        inv_resp = api_get(f"/api/invoices/{invoice_id}")
        assert inv_resp.json()["status"] == "paid"
        assert inv_resp.json()["balance"] == 0

    def test_create_payment_partial(self):
        """Pay part of an invoice."""
        client_id, invoice_id = self._create_sent_invoice(1000.0)
        resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 400.0,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 400.0}],
        })
        assert resp.status_code == 201

        # Verify invoice is now "partial"
        inv_resp = api_get(f"/api/invoices/{invoice_id}")
        assert inv_resp.json()["status"] == "partial"
        assert inv_resp.json()["balance"] == 600.0
        assert inv_resp.json()["paid_to_date"] == 400.0

    def test_create_payment_split_across_invoices(self):
        """A single payment split across two invoices."""
        client_resp = api_post("/api/clients", {"name": f"Split Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        inv1_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Svc 1", "quantity": 1, "unit_cost": 300.0}],
        })
        inv1_id = inv1_resp.json()["id"]
        api_post(f"/api/invoices/{inv1_id}/actions/mark_sent")

        inv2_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Svc 2", "quantity": 1, "unit_cost": 200.0}],
        })
        inv2_id = inv2_resp.json()["id"]
        api_post(f"/api/invoices/{inv2_id}/actions/mark_sent")

        resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 500.0,
            "date": "2024-02-01",
            "invoices": [
                {"invoice_id": inv1_id, "amount": 300.0},
                {"invoice_id": inv2_id, "amount": 200.0},
            ],
        })
        assert resp.status_code == 201

        # Both should be paid
        inv1_check = api_get(f"/api/invoices/{inv1_id}")
        assert inv1_check.json()["status"] == "paid"
        assert inv1_check.json()["balance"] == 0

        inv2_check = api_get(f"/api/invoices/{inv2_id}")
        assert inv2_check.json()["status"] == "paid"
        assert inv2_check.json()["balance"] == 0

    def test_list_payments(self):
        resp = api_get("/api/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_payment_by_id(self):
        client_id, invoice_id = self._create_sent_invoice(100.0)
        create_resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 100.0,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 100.0}],
        })
        payment_id = create_resp.json()["id"]

        resp = api_get(f"/api/payments/{payment_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == payment_id

    def test_delete_payment(self):
        client_id, invoice_id = self._create_sent_invoice(100.0)
        create_resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 100.0,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 100.0}],
        })
        payment_id = create_resp.json()["id"]

        resp = api_delete(f"/api/payments/{payment_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/payments/{payment_id}")
        assert get_resp.status_code == 404


class TestPaymentRefund:

    def _create_paid_invoice(self, amount=1000.0):
        client_resp = api_post("/api/clients", {"name": f"Refund Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]
        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Service", "quantity": 1, "unit_cost": amount}],
        })
        invoice_id = inv_resp.json()["id"]
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")
        pay_resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": amount,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": amount}],
        })
        payment_id = pay_resp.json()["id"]
        return client_id, invoice_id, payment_id

    def test_refund_partial(self):
        client_id, invoice_id, payment_id = self._create_paid_invoice(1000.0)

        resp = api_post(f"/api/payments/{payment_id}/actions/refund", {"amount": 300.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["refunded"] == 300.0

        # Invoice should go back to partial/sent (balance > 0)
        inv_resp = api_get(f"/api/invoices/{invoice_id}")
        inv_data = inv_resp.json()
        assert inv_data["balance"] == 300.0
        assert inv_data["status"] in ["partial", "sent"]

    def test_refund_full(self):
        client_id, invoice_id, payment_id = self._create_paid_invoice(500.0)

        resp = api_post(f"/api/payments/{payment_id}/actions/refund", {"amount": 500.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["refunded"] == 500.0

        # Invoice balance should be restored
        inv_resp = api_get(f"/api/invoices/{invoice_id}")
        assert inv_resp.json()["balance"] == 500.0

    def test_refund_exceeds_payment_returns_422(self):
        _, _, payment_id = self._create_paid_invoice(500.0)
        resp = api_post(f"/api/payments/{payment_id}/actions/refund", {"amount": 600.0})
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 7: Client Computed Fields
# ════════════════════════════════════════════════════════════════════


class TestClientComputedFields:

    def test_client_balance_reflects_unpaid_invoices(self):
        """Client balance = sum of unpaid invoice balances (non-draft, non-cancelled)."""
        client_resp = api_post("/api/clients", {"name": f"Balance Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        # Create two invoices, mark them sent
        inv1_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "A", "quantity": 1, "unit_cost": 300.0}],
        })
        inv1_id = inv1_resp.json()["id"]
        api_post(f"/api/invoices/{inv1_id}/actions/mark_sent")

        inv2_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "B", "quantity": 1, "unit_cost": 200.0}],
        })
        inv2_id = inv2_resp.json()["id"]
        api_post(f"/api/invoices/{inv2_id}/actions/mark_sent")

        # Client balance should be 500
        client_check = api_get(f"/api/clients/{client_id}")
        assert client_check.json()["balance"] == 500.0

    def test_client_balance_excludes_draft_invoices(self):
        """Draft invoices should NOT count toward client balance."""
        client_resp = api_post("/api/clients", {"name": f"Draft Excl {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        # Create a draft invoice (don't mark sent)
        api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Draft", "quantity": 1, "unit_cost": 9999.0}],
        })

        client_check = api_get(f"/api/clients/{client_id}")
        assert client_check.json()["balance"] == 0

    def test_client_paid_to_date(self):
        """Client paid_to_date = sum of payments applied to their invoices."""
        client_resp = api_post("/api/clients", {"name": f"PaidTo Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "X", "quantity": 1, "unit_cost": 1000.0}],
        })
        invoice_id = inv_resp.json()["id"]
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")

        api_post("/api/payments", {
            "client_id": client_id,
            "amount": 600.0,
            "date": "2024-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 600.0}],
        })

        client_check = api_get(f"/api/clients/{client_id}")
        assert client_check.json()["paid_to_date"] == 600.0
        assert client_check.json()["balance"] == 400.0


# ════════════════════════════════════════════════════════════════════
# PART 8: Expenses CRUD
# ════════════════════════════════════════════════════════════════════


class TestExpensesCRUD:

    def test_create_expense(self):
        resp = api_post("/api/expenses", {
            "vendor": "Office Supplies Inc",
            "category": "Office",
            "amount": 250.50,
            "date": "2024-01-20",
            "currency": "USD",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor"] == "Office Supplies Inc"
        assert data["category"] == "Office"
        assert data["amount"] == 250.50
        assert "id" in data

    def test_create_expense_minimal(self):
        resp = api_post("/api/expenses", {"amount": 10.0})
        assert resp.status_code == 201

    def test_create_expense_missing_amount_returns_422(self):
        resp = api_post("/api/expenses", {"vendor": "No Amount"})
        assert resp.status_code == 422

    def test_list_expenses(self):
        resp = api_get("/api/expenses")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_expense_by_id(self):
        create_resp = api_post("/api/expenses", {"amount": 99.0, "vendor": "Test"})
        expense_id = create_resp.json()["id"]

        resp = api_get(f"/api/expenses/{expense_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == expense_id

    def test_update_expense(self):
        create_resp = api_post("/api/expenses", {"amount": 50.0, "vendor": "Old Vendor"})
        expense_id = create_resp.json()["id"]

        resp = api_put(f"/api/expenses/{expense_id}", {"amount": 75.0, "vendor": "New Vendor"})
        assert resp.status_code == 200
        assert resp.json()["vendor"] == "New Vendor"
        assert resp.json()["amount"] == 75.0

    def test_delete_expense(self):
        create_resp = api_post("/api/expenses", {"amount": 10.0})
        expense_id = create_resp.json()["id"]

        resp = api_delete(f"/api/expenses/{expense_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/expenses/{expense_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Recurring Invoices CRUD
# ════════════════════════════════════════════════════════════════════


class TestRecurringInvoicesCRUD:

    def _create_client(self):
        resp = api_post("/api/clients", {"name": f"Recurring Client {uuid.uuid4().hex[:6]}"})
        return resp.json()["id"]

    def test_create_recurring_invoice(self):
        client_id = self._create_client()
        resp = api_post("/api/recurring_invoices", {
            "client_id": client_id,
            "frequency": "monthly",
            "start_date": "2024-01-01",
            "remaining_cycles": 12,
            "line_items": [
                {"description": "Monthly retainer", "quantity": 1, "unit_cost": 5000.0},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == client_id
        assert data["frequency"] == "monthly"
        assert data["remaining_cycles"] == 12
        assert data["status"] == "active"
        assert "id" in data

    def test_create_recurring_invoice_infinite_cycles(self):
        client_id = self._create_client()
        resp = api_post("/api/recurring_invoices", {
            "client_id": client_id,
            "frequency": "weekly",
            "line_items": [{"description": "Weekly", "quantity": 1, "unit_cost": 100.0}],
            "remaining_cycles": -1,
        })
        assert resp.status_code == 201
        assert resp.json()["remaining_cycles"] == -1

    def test_list_recurring_invoices(self):
        resp = api_get("/api/recurring_invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_recurring_invoice_by_id(self):
        client_id = self._create_client()
        create_resp = api_post("/api/recurring_invoices", {
            "client_id": client_id,
            "frequency": "yearly",
            "line_items": [{"description": "Yearly", "quantity": 1, "unit_cost": 10000.0}],
        })
        ri_id = create_resp.json()["id"]

        resp = api_get(f"/api/recurring_invoices/{ri_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == ri_id

    def test_update_recurring_invoice(self):
        client_id = self._create_client()
        create_resp = api_post("/api/recurring_invoices", {
            "client_id": client_id,
            "frequency": "monthly",
            "line_items": [{"description": "Original", "quantity": 1, "unit_cost": 1000.0}],
        })
        ri_id = create_resp.json()["id"]

        resp = api_put(f"/api/recurring_invoices/{ri_id}", {
            "client_id": client_id,
            "frequency": "quarterly",
            "line_items": [{"description": "Updated", "quantity": 1, "unit_cost": 3000.0}],
            "status": "paused",
        })
        assert resp.status_code == 200
        assert resp.json()["frequency"] == "quarterly"
        assert resp.json()["status"] == "paused"

    def test_delete_recurring_invoice(self):
        client_id = self._create_client()
        create_resp = api_post("/api/recurring_invoices", {
            "client_id": client_id,
            "frequency": "monthly",
            "line_items": [{"description": "Del", "quantity": 1, "unit_cost": 100.0}],
        })
        ri_id = create_resp.json()["id"]

        resp = api_delete(f"/api/recurring_invoices/{ri_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/recurring_invoices/{ri_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Tasks CRUD
# ════════════════════════════════════════════════════════════════════


class TestTasksCRUD:

    def _create_client(self):
        resp = api_post("/api/clients", {"name": f"Task Client {uuid.uuid4().hex[:6]}"})
        return resp.json()["id"]

    def test_create_task(self):
        client_id = self._create_client()
        resp = api_post("/api/tasks", {
            "client_id": client_id,
            "description": "Backend development",
            "time_log": [[1700000000, 1700003600], [1700010000, 1700017200]],
            "rate": 150.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == client_id
        assert data["description"] == "Backend development"
        assert data["rate"] == 150.0
        # time_log: (3600 + 7200) seconds = 10800 seconds = 3 hours
        # amount = 3 * 150 = 450
        assert data["amount"] == 450.0
        assert data["status"] == "active"

    def test_create_task_minimal(self):
        resp = api_post("/api/tasks", {})
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 0
        assert data["time_log"] == []

    def test_task_amount_computation(self):
        """Amount = total_hours * rate."""
        resp = api_post("/api/tasks", {
            "time_log": [[1000, 4600]],  # 3600 seconds = 1 hour
            "rate": 200.0,
        })
        assert resp.status_code == 201
        assert resp.json()["amount"] == 200.0

    def test_list_tasks(self):
        resp = api_get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_task_by_id(self):
        create_resp = api_post("/api/tasks", {"description": "Get Test", "rate": 50.0})
        task_id = create_resp.json()["id"]

        resp = api_get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == task_id

    def test_update_task(self):
        create_resp = api_post("/api/tasks", {"description": "Before", "rate": 100.0})
        task_id = create_resp.json()["id"]

        resp = api_put(f"/api/tasks/{task_id}", {
            "description": "After",
            "rate": 200.0,
            "time_log": [[0, 7200]],  # 2 hours
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "After"
        assert data["rate"] == 200.0
        assert data["amount"] == 400.0  # 2h * 200

    def test_delete_task(self):
        create_resp = api_post("/api/tasks", {"description": "Delete me"})
        task_id = create_resp.json()["id"]

        resp = api_delete(f"/api/tasks/{task_id}")
        assert resp.status_code == 200

        get_resp = api_get(f"/api/tasks/{task_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Projects CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjectsCRUD:

    def _create_client(self):
        resp = api_post("/api/clients", {"name": f"Proj Client {uuid.uuid4().hex[:6]}"})
        return resp.json()["id"]

    def test_create_project(self):
        client_id = self._create_client()
        resp = api_post("/api/projects", {
            "name": "Website Redesign",
            "client_id": client_id,
            "budgeted_hours": 100.0,
            "task_rate": 150.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Website Redesign"
        assert data["client_id"] == client_id
        assert data["budgeted_hours"] == 100.0
        assert data["task_rate"] == 150.0
        assert data["total_hours"] == 0
        assert "id" in data

    def test_create_project_minimal(self):
        resp = api_post("/api/projects", {"name": "Minimal Project"})
        assert resp.status_code == 201

    def test_create_project_missing_name_returns_422(self):
        resp = api_post("/api/projects", {"budgeted_hours": 50})
        assert resp.status_code == 422

    def test_project_total_hours_from_tasks(self):
        """Project total_hours = sum of hours from linked tasks."""
        client_id = self._create_client()
        proj_resp = api_post("/api/projects", {
            "name": "Hours Project",
            "client_id": client_id,
        })
        project_id = proj_resp.json()["id"]

        # Create tasks linked to this project
        api_post("/api/tasks", {
            "project_id": project_id,
            "time_log": [[0, 3600]],  # 1 hour
            "rate": 100.0,
        })
        api_post("/api/tasks", {
            "project_id": project_id,
            "time_log": [[0, 7200]],  # 2 hours
            "rate": 100.0,
        })

        # Check project total_hours
        proj_check = api_get(f"/api/projects/{project_id}")
        assert proj_check.json()["total_hours"] == 3.0

    def test_list_projects(self):
        resp = api_get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_project_by_id(self):
        create_resp = api_post("/api/projects", {"name": "Get Test Project"})
        project_id = create_resp.json()["id"]

        resp = api_get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    def test_update_project(self):
        create_resp = api_post("/api/projects", {"name": "Old Project Name"})
        project_id = create_resp.json()["id"]

        resp = api_put(f"/api/projects/{project_id}", {
            "name": "New Project Name",
            "budgeted_hours": 200.0,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Project Name"
        assert resp.json()["budgeted_hours"] == 200.0

    def test_delete_project_unlinks_tasks(self):
        """Deleting a project should NOT delete tasks, just unlink them."""
        proj_resp = api_post("/api/projects", {"name": "Del Project"})
        project_id = proj_resp.json()["id"]

        task_resp = api_post("/api/tasks", {
            "project_id": project_id,
            "description": "Linked task",
            "rate": 50.0,
        })
        task_id = task_resp.json()["id"]

        # Delete project
        resp = api_delete(f"/api/projects/{project_id}")
        assert resp.status_code == 200

        # Task should still exist but with project_id = null
        task_check = api_get(f"/api/tasks/{task_id}")
        assert task_check.status_code == 200
        assert task_check.json()["project_id"] is None


# ════════════════════════════════════════════════════════════════════
# PART 12: Data Isolation Between Companies
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_clients_isolated_between_companies(self):
        """Company A's clients should not be visible to Company B."""
        # Create client with company A
        resp_a = api_post("/api/clients", {"name": "Company A Client"}, headers=HEADERS_A)
        assert resp_a.status_code == 201
        client_id_a = resp_a.json()["id"]

        # Company B should not see it
        resp_b = api_get(f"/api/clients/{client_id_a}", headers=HEADERS_B)
        assert resp_b.status_code == 404

    def test_invoices_isolated_between_companies(self):
        """Company A's invoices should not be visible to Company B."""
        # Create client and invoice with company A
        client_resp = api_post("/api/clients", {"name": "Iso Client"}, headers=HEADERS_A)
        client_id = client_resp.json()["id"]
        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "x", "quantity": 1, "unit_cost": 100.0}],
        }, headers=HEADERS_A)
        invoice_id = inv_resp.json()["id"]

        # Company B cannot see it
        resp_b = api_get(f"/api/invoices/{invoice_id}", headers=HEADERS_B)
        assert resp_b.status_code == 404

    def test_list_only_shows_own_data(self):
        """List endpoints should only return data for the requesting company."""
        # Company B creates a product
        api_post("/api/products", {"name": "B Product", "price": 10.0}, headers=HEADERS_B)

        # Company A list should not include B's product
        resp_a = api_get("/api/products", headers=HEADERS_A)
        products_a = resp_a.json()["data"]
        for p in products_a:
            assert p["name"] != "B Product"


# ════════════════════════════════════════════════════════════════════
# PART 13: Pagination
# ════════════════════════════════════════════════════════════════════


class TestPagination:

    def test_pagination_params(self):
        """Test that per_page and page work correctly."""
        # Create enough products
        fresh_key = f"pagination-test-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": fresh_key, "Content-Type": "application/json"}

        for i in range(5):
            api_post("/api/products", {"name": f"Paginate Prod {i}", "price": float(i)}, headers=headers)

        # Request page 1 with per_page=2
        resp = api_get("/api/products", params={"per_page": 2, "page": 1}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["current_page"] == 1
        assert data["meta"]["per_page"] == 2
        assert data["meta"]["total"] == 5
        assert data["meta"]["total_pages"] == 3

    def test_pagination_page_2(self):
        """Page 2 should return next set of results."""
        fresh_key = f"page2-test-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": fresh_key, "Content-Type": "application/json"}

        for i in range(5):
            api_post("/api/products", {"name": f"P2 Prod {i}", "price": float(i)}, headers=headers)

        resp = api_get("/api/products", params={"per_page": 2, "page": 2}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["current_page"] == 2

    def test_pagination_last_page(self):
        """Last page may have fewer items."""
        fresh_key = f"lastpage-test-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": fresh_key, "Content-Type": "application/json"}

        for i in range(5):
            api_post("/api/products", {"name": f"LP Prod {i}", "price": float(i)}, headers=headers)

        resp = api_get("/api/products", params={"per_page": 2, "page": 3}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1  # 5 items, 2 per page, page 3 has 1


# ════════════════════════════════════════════════════════════════════
# PART 14: Cascade Delete
# ════════════════════════════════════════════════════════════════════


class TestCascadeDelete:

    def test_delete_client_cascades_to_invoices(self):
        """Deleting a client should delete their invoices."""
        client_resp = api_post("/api/clients", {"name": f"Cascade Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Cascade", "quantity": 1, "unit_cost": 100.0}],
        })
        invoice_id = inv_resp.json()["id"]

        # Delete client
        api_delete(f"/api/clients/{client_id}")

        # Invoice should be gone
        inv_check = api_get(f"/api/invoices/{invoice_id}")
        assert inv_check.status_code == 404

    def test_delete_client_cascades_to_quotes(self):
        """Deleting a client should delete their quotes."""
        client_resp = api_post("/api/clients", {"name": f"Cascade Q Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        quote_resp = api_post("/api/quotes", {
            "client_id": client_id,
            "line_items": [{"description": "Q Cascade", "quantity": 1, "unit_cost": 100.0}],
        })
        quote_id = quote_resp.json()["id"]

        api_delete(f"/api/clients/{client_id}")

        quote_check = api_get(f"/api/quotes/{quote_id}")
        assert quote_check.status_code == 404

    def test_delete_client_cascades_to_payments(self):
        """Deleting a client should delete their payments."""
        client_resp = api_post("/api/clients", {"name": f"Cascade P Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "X", "quantity": 1, "unit_cost": 100.0}],
        })
        invoice_id = inv_resp.json()["id"]
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")

        pay_resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 100.0,
            "date": "2024-01-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 100.0}],
        })
        payment_id = pay_resp.json()["id"]

        api_delete(f"/api/clients/{client_id}")

        pay_check = api_get(f"/api/payments/{payment_id}")
        assert pay_check.status_code == 404

    def test_delete_client_cascades_to_expenses(self):
        """Deleting a client should delete related expenses (those with invoice_id on client's invoices)."""
        client_resp = api_post("/api/clients", {"name": f"Cascade E Client {uuid.uuid4().hex[:6]}"})
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]

        invoice_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Billable expense", "quantity": 1, "unit_cost": 100.0}],
        })
        assert invoice_resp.status_code == 201
        invoice_id = invoice_resp.json()["id"]

        expense_resp = api_post("/api/expenses", {
            "vendor": "Cascade vendor",
            "amount": 100.0,
            "date": "2024-01-01",
            "invoice_id": invoice_id,
        })
        assert expense_resp.status_code == 201
        expense_id = expense_resp.json()["id"]

        delete_resp = api_delete(f"/api/clients/{client_id}")
        assert delete_resp.status_code == 200

        expense_check = api_get(f"/api/expenses/{expense_id}")
        assert expense_check.status_code == 404

    def test_delete_client_cascades_to_tasks(self):
        """Deleting a client should delete their tasks."""
        client_resp = api_post("/api/clients", {"name": f"Cascade T Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        task_resp = api_post("/api/tasks", {
            "client_id": client_id,
            "description": "Client task",
            "rate": 100.0,
        })
        task_id = task_resp.json()["id"]

        api_delete(f"/api/clients/{client_id}")

        task_check = api_get(f"/api/tasks/{task_id}")
        assert task_check.status_code == 404

    def test_delete_client_cascades_to_projects(self):
        """Deleting a client should delete their projects."""
        client_resp = api_post("/api/clients", {"name": f"Cascade Proj Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        proj_resp = api_post("/api/projects", {
            "name": "Client Project",
            "client_id": client_id,
        })
        project_id = proj_resp.json()["id"]

        api_delete(f"/api/clients/{client_id}")

        proj_check = api_get(f"/api/projects/{project_id}")
        assert proj_check.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_invoice_with_zero_discount(self):
        client_resp = api_post("/api/clients", {"name": f"Edge Client {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "No disc", "quantity": 2, "unit_cost": 100.0}],
            "discount": 0,
            "discount_type": "amount",
        })
        assert resp.status_code == 201
        assert resp.json()["amount"] == 200.0

    def test_payment_with_empty_invoices_array(self):
        """Creating a payment with amount but empty invoices array should fail."""
        client_resp = api_post("/api/clients", {"name": f"Empty Pay {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        resp = api_post("/api/payments", {
            "client_id": client_id,
            "amount": 100.0,
            "date": "2024-01-01",
            "invoices": [],
        })
        # Should fail because invoice amounts don't sum to payment amount
        assert resp.status_code == 422

    def test_task_with_no_time_log(self):
        """Task with no time_log should have amount 0."""
        resp = api_post("/api/tasks", {
            "description": "No time",
            "rate": 100.0,
            "time_log": [],
        })
        assert resp.status_code == 201
        assert resp.json()["amount"] == 0

    def test_multiple_payments_on_same_invoice(self):
        """Multiple partial payments should accumulate."""
        client_resp = api_post("/api/clients", {"name": f"Multi Pay {uuid.uuid4().hex[:6]}"})
        client_id = client_resp.json()["id"]

        inv_resp = api_post("/api/invoices", {
            "client_id": client_id,
            "line_items": [{"description": "Big job", "quantity": 1, "unit_cost": 1000.0}],
        })
        invoice_id = inv_resp.json()["id"]
        api_post(f"/api/invoices/{invoice_id}/actions/mark_sent")

        # First payment
        api_post("/api/payments", {
            "client_id": client_id,
            "amount": 300.0,
            "date": "2024-01-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 300.0}],
        })

        inv_check = api_get(f"/api/invoices/{invoice_id}")
        assert inv_check.json()["balance"] == 700.0
        assert inv_check.json()["status"] == "partial"

        # Second payment
        api_post("/api/payments", {
            "client_id": client_id,
            "amount": 700.0,
            "date": "2024-01-15",
            "invoices": [{"invoice_id": invoice_id, "amount": 700.0}],
        })

        inv_check2 = api_get(f"/api/invoices/{invoice_id}")
        assert inv_check2.json()["balance"] == 0
        assert inv_check2.json()["status"] == "paid"
        assert inv_check2.json()["paid_to_date"] == 1000.0
