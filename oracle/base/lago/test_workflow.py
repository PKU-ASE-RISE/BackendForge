"""
BackendForge — L3 Workflow Tests for Lago Billing API
Complex multi-step workflows that cross multiple entity types.
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def unique():
    return uuid.uuid4().hex[:8]


def api_key():
    return f"org-{unique()}"


def h(key=None):
    return {"X-Api-Key": key or api_key(), "Content-Type": "application/json"}


def post(path, data, headers):
    return requests.post(f"{BASE_URL}{path}", json=data, headers=headers, timeout=30)


def get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def put(path, data, headers):
    return requests.put(f"{BASE_URL}{path}", json=data, headers=headers, timeout=30)


def delete(path, headers):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


class TestFullBillingWorkflow:
    """Pattern 5+7: Complete billing cycle: customer → plan → subscription → events → invoice."""

    def test_standard_charge_billing_cycle(self):
        hdr = h()
        # 1. Create customer
        cust = post("/customers", {"external_id": "billing-cust", "name": "Billing Corp", "email": "billing@corp.com", "currency": "USD"}, hdr).json()["customer"]
        assert cust["external_id"] == "billing-cust"

        # 2. Create billable metric
        metric = post("/billable_metrics", {"name": "API Calls", "code": "api_calls", "aggregation_type": "count"}, hdr).json()["billable_metric"]
        assert metric["aggregation_type"] == "count"

        # 3. Create plan
        plan = post("/plans", {"name": "Starter", "code": "starter", "interval": "monthly", "amount_cents": 2900, "currency": "USD"}, hdr).json()["plan"]
        assert plan["amount_cents"] == 2900

        # 4. Add charge to plan
        charge = post("/plans/starter/charges", {
            "billable_metric_code": "api_calls",
            "charge_model": "standard",
            "properties": {"amount": 10}
        }, hdr).json()["charge"]
        assert charge["charge_model"] == "standard"

        # 5. Create subscription
        past = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "billing-cust", "plan_code": "starter", "started_at": past}, hdr).json()["subscription"]
        assert sub["status"] == "active"

        # 6. Ingest usage events
        ts = (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z"
        for i in range(5):
            r = post("/events", {
                "transaction_id": f"tx-billing-{i}-{unique()}",
                "external_customer_id": "billing-cust",
                "code": "api_calls",
                "timestamp": ts,
                "properties": {}
            }, hdr)
            assert r.status_code == 200

        # 7. Generate invoice
        inv = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]
        assert inv["status"] == "finalized"
        assert inv["external_customer_id"] == "billing-cust"
        # Base plan (2900) + 5 events * 10 per unit = 2900 + 50 = 2950
        assert inv["amount_cents"] == 2950
        assert len(inv["line_items"]) >= 2  # plan + charge

        # 8. Verify invoice in list
        invoices = get("/invoices", hdr, params={"external_customer_id": "billing-cust"}).json()["invoices"]
        assert any(i["id"] == inv["id"] for i in invoices)


class TestWalletCreditDeduction:
    """Pattern 5+7: Wallet credits offset invoice amounts."""

    def test_wallet_reduces_invoice_amount(self):
        hdr = h()
        # 1. Setup
        post("/customers", {"external_id": "wallet-cust", "name": "Wallet User"}, hdr)
        post("/plans", {"name": "WPlan", "code": "w-plan", "interval": "monthly", "amount_cents": 5000, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "wallet-cust", "plan_code": "w-plan", "started_at": past}, hdr).json()["subscription"]

        # 2. Create wallet with credits
        wallet = post("/wallets", {"external_customer_id": "wallet-cust", "currency": "USD", "paid_credits": 20, "granted_credits": 10}, hdr).json()["wallet"]
        assert wallet["balance_cents"] == 3000  # 30 credits * 100

        # 3. Generate invoice — should deduct from wallet
        inv = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]
        # Invoice was 5000, wallet had 3000, so final amount should be 2000
        assert inv["amount_cents"] == 2000

        # 4. Check wallet balance decreased
        wallet2 = get(f"/wallets/{wallet['id']}", hdr).json()["wallet"]
        assert wallet2["balance_cents"] == 0  # 3000 - 3000 used = 0


class TestSubscriptionFilterWorkflow:
    """Pattern 3: Subscription filters actually work."""

    def test_filter_subscriptions_by_customer_and_status(self):
        hdr = h()
        post("/customers", {"external_id": "filt-a", "name": "A"}, hdr)
        post("/customers", {"external_id": "filt-b", "name": "B"}, hdr)
        post("/plans", {"name": "F", "code": "filt-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

        # Create subs for both customers
        sub_a = post("/subscriptions", {"external_customer_id": "filt-a", "plan_code": "filt-plan", "started_at": past}, hdr).json()["subscription"]
        sub_b = post("/subscriptions", {"external_customer_id": "filt-b", "plan_code": "filt-plan", "started_at": past}, hdr).json()["subscription"]

        # Terminate sub_a
        delete(f"/subscriptions/{sub_a['id']}", hdr)

        # Filter by customer
        r = get("/subscriptions", hdr, params={"external_customer_id": "filt-a"})
        subs = r.json()["subscriptions"]
        for s in subs:
            assert s["external_customer_id"] == "filt-a"

        # Filter by status=active
        r2 = get("/subscriptions", hdr, params={"status": "active"})
        subs2 = r2.json()["subscriptions"]
        for s in subs2:
            assert s["status"] == "active"
        sub_ids = [s["id"] for s in subs2]
        assert sub_b["id"] in sub_ids
        assert sub_a["id"] not in sub_ids


class TestInvoiceVoidWorkflow:
    """Pattern 5+4: Invoice voiding rules."""

    def test_cannot_void_draft_invoice(self):
        """Only finalized invoices can be voided — but our generate always finalizes."""
        hdr = h()
        post("/customers", {"external_id": "v-cust", "name": "V"}, hdr)
        post("/plans", {"name": "V", "code": "v-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "v-cust", "plan_code": "v-plan", "started_at": past}, hdr).json()["subscription"]
        invoice = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]

        # Void it
        r = put(f"/invoices/{invoice['id']}/void", {}, hdr)
        assert r.status_code == 200
        assert r.json()["invoice"]["status"] == "voided"

        # Cannot void again
        r2 = put(f"/invoices/{invoice['id']}/void", {}, hdr)
        assert r2.status_code == 400


class TestCustomerDeletionCascade:
    """Pattern 7: Deleting customer cascades to subscriptions and wallets."""

    def test_delete_customer_cascades_all(self):
        hdr = h()
        # 1. Create customer with subscription and wallet
        post("/customers", {"external_id": "del-cust", "name": "Del"}, hdr)
        post("/plans", {"name": "Del", "code": "del-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "del-cust", "plan_code": "del-plan", "started_at": past}, hdr).json()["subscription"]
        wallet = post("/wallets", {"external_customer_id": "del-cust", "currency": "USD", "paid_credits": 5}, hdr).json()["wallet"]

        # 2. Delete customer
        r = delete("/customers/del-cust", hdr)
        assert r.status_code == 200

        # 3. Customer gone
        assert get("/customers/del-cust", hdr).status_code == 404

        # 4. Subscription gone
        assert get(f"/subscriptions/{sub['id']}", hdr).status_code == 404

        # 5. Wallet gone
        assert get(f"/wallets/{wallet['id']}", hdr).status_code == 404


class TestSumAggregationWorkflow:
    """Pattern 5: Sum aggregation for usage-based charges."""

    def test_sum_aggregation_invoice(self):
        hdr = h()
        post("/customers", {"external_id": "sum-cust", "name": "Sum"}, hdr)
        post("/billable_metrics", {"name": "Bandwidth", "code": "bandwidth", "aggregation_type": "sum", "field_name": "gb_used"}, hdr)
        post("/plans", {"name": "BW Plan", "code": "bw-plan", "interval": "monthly", "amount_cents": 1000, "currency": "USD"}, hdr)
        post("/plans/bw-plan/charges", {"billable_metric_code": "bandwidth", "charge_model": "standard", "properties": {"amount": 50}}, hdr)

        past = (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "sum-cust", "plan_code": "bw-plan", "started_at": past}, hdr).json()["subscription"]

        # Ingest events with gb_used values
        ts = (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z"
        post("/events", {"transaction_id": f"bw1-{unique()}", "external_customer_id": "sum-cust", "code": "bandwidth", "timestamp": ts, "properties": {"gb_used": 3}}, hdr)
        post("/events", {"transaction_id": f"bw2-{unique()}", "external_customer_id": "sum-cust", "code": "bandwidth", "timestamp": ts, "properties": {"gb_used": 7}}, hdr)

        # Generate invoice: base 1000 + sum(3+7)*50 = 1000 + 500 = 1500
        inv = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]
        assert inv["amount_cents"] == 1500


class TestMultipleChargesOnPlan:
    """Pattern 2+5: Multiple charges on a single plan."""

    def test_plan_with_multiple_charges(self):
        hdr = h()
        post("/customers", {"external_id": "mc-cust", "name": "MC"}, hdr)
        post("/billable_metrics", {"name": "API", "code": "mc-api", "aggregation_type": "count"}, hdr)
        post("/billable_metrics", {"name": "Storage", "code": "mc-store", "aggregation_type": "sum", "field_name": "mb"}, hdr)
        post("/plans", {"name": "MC Plan", "code": "mc-plan", "interval": "monthly", "amount_cents": 2000, "currency": "USD"}, hdr)

        # Add two charges
        post("/plans/mc-plan/charges", {"billable_metric_code": "mc-api", "charge_model": "standard", "properties": {"amount": 5}}, hdr)
        post("/plans/mc-plan/charges", {"billable_metric_code": "mc-store", "charge_model": "standard", "properties": {"amount": 20}}, hdr)

        past = (datetime.utcnow() - timedelta(days=2)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "mc-cust", "plan_code": "mc-plan", "started_at": past}, hdr).json()["subscription"]

        ts = (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z"
        # 3 API calls
        for i in range(3):
            post("/events", {"transaction_id": f"mc-api-{i}-{unique()}", "external_customer_id": "mc-cust", "code": "mc-api", "timestamp": ts, "properties": {}}, hdr)
        # Storage usage: 10 + 20 = 30 mb
        post("/events", {"transaction_id": f"mc-st1-{unique()}", "external_customer_id": "mc-cust", "code": "mc-store", "timestamp": ts, "properties": {"mb": 10}}, hdr)
        post("/events", {"transaction_id": f"mc-st2-{unique()}", "external_customer_id": "mc-cust", "code": "mc-store", "timestamp": ts, "properties": {"mb": 20}}, hdr)

        # Invoice: base 2000 + api(3*5=15) + storage(30*20=600) = 2615
        inv = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]
        assert inv["amount_cents"] == 2615
        assert len(inv["line_items"]) >= 3  # plan + 2 charges


class TestEventIdempotencyWorkflow:
    """Pattern 8: Events are properly deduplicated."""

    def test_idempotent_events_not_double_counted(self):
        hdr = h()
        post("/customers", {"external_id": "idem-wf", "name": "Idem"}, hdr)
        post("/billable_metrics", {"name": "Hits", "code": "hits", "aggregation_type": "count"}, hdr)
        post("/plans", {"name": "Idem", "code": "idem-plan", "interval": "monthly", "amount_cents": 1000, "currency": "USD"}, hdr)
        post("/plans/idem-plan/charges", {"billable_metric_code": "hits", "charge_model": "standard", "properties": {"amount": 100}}, hdr)

        past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "idem-wf", "plan_code": "idem-plan", "started_at": past}, hdr).json()["subscription"]

        ts = (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z"
        tx_id = f"idem-tx-{unique()}"
        # Send same event 3 times
        post("/events", {"transaction_id": tx_id, "external_customer_id": "idem-wf", "code": "hits", "timestamp": ts}, hdr)
        post("/events", {"transaction_id": tx_id, "external_customer_id": "idem-wf", "code": "hits", "timestamp": ts}, hdr)
        post("/events", {"transaction_id": tx_id, "external_customer_id": "idem-wf", "code": "hits", "timestamp": ts}, hdr)
        # Plus one unique event
        post("/events", {"transaction_id": f"unique-{unique()}", "external_customer_id": "idem-wf", "code": "hits", "timestamp": ts}, hdr)

        # Invoice should count 2 events (1 deduplicated + 1 unique), not 4
        inv = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]
        # base 1000 + 2 * 100 = 1200
        assert inv["amount_cents"] == 1200


class TestOrgIsolationWorkflow:
    """Pattern 6: Complete data isolation across organizations."""

    def test_full_isolation(self):
        h1 = h()
        h2 = h()

        # Org1 creates full setup
        post("/customers", {"external_id": "shared", "name": "Org1 Cust"}, h1)
        post("/plans", {"name": "Shared", "code": "shared", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, h1)
        post("/billable_metrics", {"name": "Shared", "code": "shared", "aggregation_type": "count"}, h1)
        post("/coupons", {"name": "Shared", "code": "shared", "coupon_type": "fixed_amount", "amount_cents": 50, "frequency": "once"}, h1)

        # Org2 cannot access org1's resources
        assert get("/customers/shared", h2).status_code == 404
        assert get("/plans/shared", h2).status_code == 404
        assert get("/billable_metrics/shared", h2).status_code == 404
        assert get("/coupons/shared", h2).status_code == 404

        # Org2 can create same codes without conflict
        r1 = post("/customers", {"external_id": "shared", "name": "Org2 Cust"}, h2)
        assert r1.status_code == 201
        r2 = post("/plans", {"name": "Shared", "code": "shared", "interval": "yearly", "amount_cents": 999, "currency": "EUR"}, h2)
        assert r2.status_code == 201

        # Each org sees their own data
        c1 = get("/customers/shared", h1).json()["customer"]
        c2 = get("/customers/shared", h2).json()["customer"]
        assert c1["name"] == "Org1 Cust"
        assert c2["name"] == "Org2 Cust"


class TestChargeRemoval:
    """Pattern 7: Removing a charge from a plan."""

    def test_delete_charge_from_plan(self):
        hdr = h()
        post("/billable_metrics", {"name": "Calls", "code": "rm-calls", "aggregation_type": "count"}, hdr)
        post("/plans", {"name": "RM", "code": "rm-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        charge = post("/plans/rm-plan/charges", {"billable_metric_code": "rm-calls", "charge_model": "standard", "properties": {"amount": 10}}, hdr).json()["charge"]

        # Verify charge exists
        charges = get("/plans/rm-plan/charges", hdr).json()["charges"]
        assert len(charges) == 1

        # Delete charge
        r = delete(f"/plans/rm-plan/charges/{charge['id']}", hdr)
        assert r.status_code == 200

        # Verify removed
        charges2 = get("/plans/rm-plan/charges", hdr).json()["charges"]
        assert len(charges2) == 0

        # Now metric can be deleted (no more charges reference it)
        r2 = delete("/billable_metrics/rm-calls", hdr)
        assert r2.status_code == 200
