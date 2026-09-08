"""
BackendForge — L2 Integration Tests for Lago Billing API
Adversarial tests targeting common LLM implementation bugs.
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


class TestResponseWrapping:
    """Pattern 1: Verify responses are wrapped in correct keys (customer, plan, etc)."""

    def test_customer_create_wrapped_in_customer_key(self):
        hdr = h()
        r = post("/customers", {"external_id": f"cust-{unique()}", "name": "Alice"}, hdr)
        assert r.status_code == 201
        body = r.json()
        assert "customer" in body
        cust = body["customer"]
        assert cust["name"] == "Alice"
        assert "id" in cust
        assert "created_at" in cust
        assert "external_id" in cust

    def test_plan_create_wrapped_in_plan_key(self):
        hdr = h()
        code = f"plan-{unique()}"
        r = post("/plans", {"name": "Pro", "code": code, "interval": "monthly", "amount_cents": 4999, "currency": "USD"}, hdr)
        assert r.status_code == 201
        body = r.json()
        assert "plan" in body
        plan = body["plan"]
        assert plan["code"] == code
        assert plan["amount_cents"] == 4999
        assert plan["interval"] == "monthly"
        assert plan["currency"] == "USD"
        assert "id" in plan
        assert "created_at" in plan

    def test_list_customers_wrapped_with_meta(self):
        hdr = h()
        post("/customers", {"external_id": f"c1-{unique()}", "name": "A"}, hdr)
        r = get("/customers", hdr)
        assert r.status_code == 200
        body = r.json()
        assert "customers" in body
        assert "meta" in body
        assert isinstance(body["customers"], list)
        meta = body["meta"]
        assert "current_page" in meta
        assert "total_pages" in meta
        assert "total_count" in meta

    def test_event_wrapped_in_event_key(self):
        hdr = h()
        post("/customers", {"external_id": "ev-cust", "name": "Ev"}, hdr)
        r = post("/events", {
            "transaction_id": f"tx-{unique()}",
            "external_customer_id": "ev-cust",
            "code": "api_calls",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "properties": {"value": 1}
        }, hdr)
        assert r.status_code == 200
        assert "event" in r.json()


class TestUniquenessConstraints:
    """Pattern 8: Duplicate codes/ids return 409."""

    def test_duplicate_customer_external_id_returns_409(self):
        hdr = h()
        ext_id = f"dup-{unique()}"
        r1 = post("/customers", {"external_id": ext_id, "name": "First"}, hdr)
        assert r1.status_code == 201
        r2 = post("/customers", {"external_id": ext_id, "name": "Second"}, hdr)
        assert r2.status_code == 409

    def test_duplicate_plan_code_returns_409(self):
        hdr = h()
        code = f"dup-plan-{unique()}"
        r1 = post("/plans", {"name": "A", "code": code, "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        assert r1.status_code == 201
        r2 = post("/plans", {"name": "B", "code": code, "interval": "yearly", "amount_cents": 200, "currency": "EUR"}, hdr)
        assert r2.status_code == 409

    def test_duplicate_metric_code_returns_409(self):
        hdr = h()
        code = f"dup-met-{unique()}"
        r1 = post("/billable_metrics", {"name": "M1", "code": code, "aggregation_type": "count"}, hdr)
        assert r1.status_code == 201
        r2 = post("/billable_metrics", {"name": "M2", "code": code, "aggregation_type": "sum", "field_name": "x"}, hdr)
        assert r2.status_code == 409

    def test_duplicate_coupon_code_returns_409(self):
        hdr = h()
        code = f"dup-cp-{unique()}"
        r1 = post("/coupons", {"name": "C1", "code": code, "coupon_type": "fixed_amount", "amount_cents": 1000, "frequency": "once"}, hdr)
        assert r1.status_code == 201
        r2 = post("/coupons", {"name": "C2", "code": code, "coupon_type": "percentage", "percentage_rate": 10, "frequency": "recurring"}, hdr)
        assert r2.status_code == 409


class TestEventIdempotency:
    """Pattern 5+8: Events are idempotent on transaction_id."""

    def test_duplicate_event_returns_200_not_duplicate(self):
        hdr = h()
        post("/customers", {"external_id": "idem-cust", "name": "Idem"}, hdr)
        tx_id = f"tx-{unique()}"
        ts = datetime.utcnow().isoformat() + "Z"
        r1 = post("/events", {"transaction_id": tx_id, "external_customer_id": "idem-cust", "code": "api_calls", "timestamp": ts, "properties": {"v": 1}}, hdr)
        assert r1.status_code == 200
        r2 = post("/events", {"transaction_id": tx_id, "external_customer_id": "idem-cust", "code": "api_calls", "timestamp": ts, "properties": {"v": 99}}, hdr)
        assert r2.status_code == 200
        # Should still only be one event
        r3 = get(f"/events/{tx_id}", hdr)
        assert r3.json()["event"]["properties"].get("v") == 1  # original value preserved


class TestSubscriptionLifecycle:
    """Pattern 5+4: Subscription status transitions."""

    def test_subscription_active_on_past_start(self):
        hdr = h()
        post("/customers", {"external_id": "sub-cust", "name": "Sub"}, hdr)
        post("/plans", {"name": "Basic", "code": "basic", "interval": "monthly", "amount_cents": 1000, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        r = post("/subscriptions", {"external_customer_id": "sub-cust", "plan_code": "basic", "started_at": past}, hdr)
        assert r.status_code == 201
        sub = r.json()["subscription"]
        assert sub["status"] == "active"
        assert sub["external_customer_id"] == "sub-cust"
        assert sub["plan_code"] == "basic"

    def test_subscription_pending_on_future_start(self):
        hdr = h()
        post("/customers", {"external_id": "fut-cust", "name": "Fut"}, hdr)
        post("/plans", {"name": "Fut", "code": "fut-plan", "interval": "monthly", "amount_cents": 2000, "currency": "USD"}, hdr)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        r = post("/subscriptions", {"external_customer_id": "fut-cust", "plan_code": "fut-plan", "started_at": future}, hdr)
        assert r.status_code == 201
        assert r.json()["subscription"]["status"] == "pending"

    def test_terminate_subscription(self):
        hdr = h()
        post("/customers", {"external_id": "term-cust", "name": "Term"}, hdr)
        post("/plans", {"name": "T", "code": "term-plan", "interval": "monthly", "amount_cents": 500, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "term-cust", "plan_code": "term-plan", "started_at": past}, hdr).json()["subscription"]
        r = delete(f"/subscriptions/{sub['id']}", hdr)
        assert r.status_code == 200
        terminated = r.json()["subscription"]
        assert terminated["status"] == "terminated"
        assert terminated["terminated_at"] is not None

    def test_cannot_terminate_already_terminated(self):
        hdr = h()
        post("/customers", {"external_id": "tt-cust", "name": "TT"}, hdr)
        post("/plans", {"name": "TT", "code": "tt-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "tt-cust", "plan_code": "tt-plan", "started_at": past}, hdr).json()["subscription"]
        delete(f"/subscriptions/{sub['id']}", hdr)
        r = delete(f"/subscriptions/{sub['id']}", hdr)
        assert r.status_code == 400


class TestDeletionConstraints:
    """Pattern 7+8: Cannot delete plan with active subs, metric with charges."""

    def test_cannot_delete_plan_with_active_subscription(self):
        hdr = h()
        post("/customers", {"external_id": "dc-cust", "name": "DC"}, hdr)
        post("/plans", {"name": "DC", "code": "dc-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        post("/subscriptions", {"external_customer_id": "dc-cust", "plan_code": "dc-plan", "started_at": past}, hdr)
        r = delete("/plans/dc-plan", hdr)
        assert r.status_code == 400

    def test_cannot_delete_metric_with_charges(self):
        hdr = h()
        post("/billable_metrics", {"name": "API", "code": "api-calls", "aggregation_type": "count"}, hdr)
        post("/plans", {"name": "P", "code": "chrg-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        post("/plans/chrg-plan/charges", {"billable_metric_code": "api-calls", "charge_model": "standard", "properties": {"amount": 10}}, hdr)
        r = delete("/billable_metrics/api-calls", hdr)
        assert r.status_code == 400

    def test_delete_customer_cascades_subscriptions(self):
        hdr = h()
        post("/customers", {"external_id": "casc-cust", "name": "Casc"}, hdr)
        post("/plans", {"name": "Casc", "code": "casc-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "casc-cust", "plan_code": "casc-plan", "started_at": past}, hdr).json()["subscription"]
        delete("/customers/casc-cust", hdr)
        r = get(f"/subscriptions/{sub['id']}", hdr)
        assert r.status_code == 404


class TestPaginationActuallyWorks:
    """Pattern 3: Pagination meta is correct and pages differ."""

    def test_customer_pagination(self):
        hdr = h()
        for i in range(5):
            post("/customers", {"external_id": f"pg-{i}-{unique()}", "name": f"C{i}"}, hdr)
        r = get("/customers", hdr, params={"per_page": 2, "page": 1})
        body = r.json()
        assert len(body["customers"]) == 2
        assert body["meta"]["current_page"] == 1
        assert body["meta"]["total_count"] >= 5

        r2 = get("/customers", hdr, params={"per_page": 2, "page": 2})
        body2 = r2.json()
        ids1 = {c["external_id"] for c in body["customers"]}
        ids2 = {c["external_id"] for c in body2["customers"]}
        assert ids1.isdisjoint(ids2)

    def test_events_filter_by_customer(self):
        hdr = h()
        post("/customers", {"external_id": "fc1", "name": "FC1"}, hdr)
        post("/customers", {"external_id": "fc2", "name": "FC2"}, hdr)
        ts = datetime.utcnow().isoformat() + "Z"
        post("/events", {"transaction_id": f"ef1-{unique()}", "external_customer_id": "fc1", "code": "x", "timestamp": ts}, hdr)
        post("/events", {"transaction_id": f"ef2-{unique()}", "external_customer_id": "fc2", "code": "x", "timestamp": ts}, hdr)

        r = get("/events", hdr, params={"external_customer_id": "fc1"})
        events = r.json()["events"]
        for ev in events:
            assert ev["external_customer_id"] == "fc1"

    def test_subscriptions_filter_by_status(self):
        hdr = h()
        post("/customers", {"external_id": "sf-cust", "name": "SF"}, hdr)
        post("/plans", {"name": "SF", "code": "sf-plan", "interval": "monthly", "amount_cents": 100, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "sf-cust", "plan_code": "sf-plan", "started_at": past}, hdr).json()["subscription"]
        delete(f"/subscriptions/{sub['id']}", hdr)

        r = get("/subscriptions", hdr, params={"status": "terminated"})
        subs = r.json()["subscriptions"]
        for s in subs:
            assert s["status"] == "terminated"


class TestWalletBalance:
    """Pattern 5: Wallet balance is computed correctly."""

    def test_wallet_initial_balance(self):
        hdr = h()
        post("/customers", {"external_id": "w-cust", "name": "W"}, hdr)
        r = post("/wallets", {"external_customer_id": "w-cust", "currency": "USD", "paid_credits": 10, "granted_credits": 5}, hdr)
        assert r.status_code == 201
        wallet = r.json()["wallet"]
        # balance_cents = (10 + 5) * 100 = 1500
        assert wallet["balance_cents"] == 1500
        assert wallet["paid_credits"] == 10
        assert wallet["granted_credits"] == 5

    def test_wallet_top_up_increases_balance(self):
        hdr = h()
        post("/customers", {"external_id": "wt-cust", "name": "WT"}, hdr)
        wallet = post("/wallets", {"external_customer_id": "wt-cust", "currency": "USD", "paid_credits": 5, "granted_credits": 0}, hdr).json()["wallet"]
        assert wallet["balance_cents"] == 500

        r = post(f"/wallets/{wallet['id']}/top_up", {"paid_credits": 10, "granted_credits": 3}, hdr)
        assert r.status_code == 200
        updated = r.json()["wallet"]
        # balance = (5+10+3) * 100 = 1800... or (5+10) paid + (0+3) granted = 18 credits = 1800 cents
        assert updated["balance_cents"] == 1800


class TestDataIsolation:
    """Pattern 6: Different API keys see different data."""

    def test_orgs_cannot_see_each_others_customers(self):
        h1 = h()
        h2 = h()
        ext_id = f"iso-{unique()}"
        post("/customers", {"external_id": ext_id, "name": "Org1 Customer"}, h1)
        # Org2 should not find it
        r = get(f"/customers/{ext_id}", h2)
        assert r.status_code == 404

    def test_orgs_cannot_see_each_others_plans(self):
        h1 = h()
        h2 = h()
        code = f"iso-plan-{unique()}"
        post("/plans", {"name": "P", "code": code, "interval": "monthly", "amount_cents": 100, "currency": "USD"}, h1)
        r = get(f"/plans/{code}", h2)
        assert r.status_code == 404

    def test_same_external_id_different_orgs(self):
        h1 = h()
        h2 = h()
        ext_id = "shared-id"
        r1 = post("/customers", {"external_id": ext_id, "name": "Org1"}, h1)
        r2 = post("/customers", {"external_id": ext_id, "name": "Org2"}, h2)
        assert r1.status_code == 201
        assert r2.status_code == 201  # No conflict across orgs


class TestChargeOnPlan:
    """Pattern 2+5: Charges are properly attached to plans."""

    def test_charge_create_and_list(self):
        hdr = h()
        post("/billable_metrics", {"name": "Requests", "code": "reqs", "aggregation_type": "count"}, hdr)
        post("/plans", {"name": "Starter", "code": "starter", "interval": "monthly", "amount_cents": 2900, "currency": "USD"}, hdr)

        r = post("/plans/starter/charges", {
            "billable_metric_code": "reqs",
            "charge_model": "standard",
            "properties": {"amount": 5}
        }, hdr)
        assert r.status_code == 201
        charge = r.json()["charge"]
        assert charge["billable_metric_code"] == "reqs"
        assert charge["charge_model"] == "standard"
        assert charge["properties"]["amount"] == 5
        assert "id" in charge

        # List charges
        r2 = get("/plans/starter/charges", hdr)
        assert r2.status_code == 200
        charges = r2.json()["charges"]
        assert len(charges) >= 1
        assert any(c["billable_metric_code"] == "reqs" for c in charges)

    def test_plan_get_includes_charges(self):
        hdr = h()
        post("/billable_metrics", {"name": "Storage", "code": "storage", "aggregation_type": "sum", "field_name": "gb"}, hdr)
        post("/plans", {"name": "Pro", "code": "pro-ch", "interval": "monthly", "amount_cents": 4999, "currency": "USD"}, hdr)
        post("/plans/pro-ch/charges", {"billable_metric_code": "storage", "charge_model": "standard", "properties": {"amount": 100}}, hdr)

        r = get("/plans/pro-ch", hdr)
        plan = r.json()["plan"]
        assert "charges" in plan
        assert len(plan["charges"]) >= 1


class TestInvoiceGeneration:
    """Pattern 5: Invoice generation with line items."""

    def test_basic_invoice_generation(self):
        hdr = h()
        post("/customers", {"external_id": "inv-cust", "name": "Invoice Cust"}, hdr)
        post("/plans", {"name": "Inv Plan", "code": "inv-plan", "interval": "monthly", "amount_cents": 5000, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "inv-cust", "plan_code": "inv-plan", "started_at": past}, hdr).json()["subscription"]

        r = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr)
        assert r.status_code == 201
        invoice = r.json()["invoice"]
        assert invoice["subscription_id"] == sub["id"]
        assert invoice["external_customer_id"] == "inv-cust"
        assert invoice["status"] == "finalized"
        assert invoice["amount_cents"] >= 5000  # at least base plan amount
        assert "line_items" in invoice
        assert len(invoice["line_items"]) >= 1
        assert invoice["currency"] == "USD"

    def test_void_invoice(self):
        hdr = h()
        post("/customers", {"external_id": "void-cust", "name": "Void"}, hdr)
        post("/plans", {"name": "Void", "code": "void-plan", "interval": "monthly", "amount_cents": 1000, "currency": "USD"}, hdr)
        past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        sub = post("/subscriptions", {"external_customer_id": "void-cust", "plan_code": "void-plan", "started_at": past}, hdr).json()["subscription"]
        invoice = post("/invoices/generate", {"subscription_id": sub["id"]}, hdr).json()["invoice"]

        r = put(f"/invoices/{invoice['id']}/void", {}, hdr)
        assert r.status_code == 200
        assert r.json()["invoice"]["status"] == "voided"


class TestAuthRequired:
    """Pattern 4: All endpoints require auth."""

    def test_missing_api_key_returns_401(self):
        endpoints = [
            ("GET", "/customers"),
            ("GET", "/plans"),
            ("GET", "/billable_metrics"),
            ("GET", "/subscriptions"),
            ("GET", "/events"),
            ("GET", "/invoices"),
            ("GET", "/wallets"),
            ("GET", "/coupons"),
        ]
        for method, path in endpoints:
            r = requests.request(method, f"{BASE_URL}{path}", timeout=30)
            assert r.status_code == 401, f"{method} {path} returned {r.status_code} without auth"

    def test_empty_api_key_returns_401(self):
        r = requests.get(f"{BASE_URL}/customers", headers={"X-Api-Key": ""}, timeout=30)
        assert r.status_code == 401


class TestCouponFields:
    """Pattern 1: Coupon fields match schema exactly."""

    def test_fixed_amount_coupon(self):
        hdr = h()
        code = f"fix-{unique()}"
        r = post("/coupons", {"name": "Fixed", "code": code, "coupon_type": "fixed_amount", "amount_cents": 2000, "frequency": "once"}, hdr)
        assert r.status_code == 201
        coupon = r.json()["coupon"]
        assert coupon["code"] == code
        assert coupon["coupon_type"] == "fixed_amount"
        assert coupon["amount_cents"] == 2000
        assert coupon["frequency"] == "once"
        assert "id" in coupon
        assert "created_at" in coupon

    def test_percentage_coupon(self):
        hdr = h()
        code = f"pct-{unique()}"
        r = post("/coupons", {"name": "Pct", "code": code, "coupon_type": "percentage", "percentage_rate": 15.5, "frequency": "recurring"}, hdr)
        assert r.status_code == 201
        coupon = r.json()["coupon"]
        assert coupon["coupon_type"] == "percentage"
        assert coupon["percentage_rate"] == 15.5
        assert coupon["frequency"] == "recurring"
