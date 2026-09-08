"""
BackendForge — L2 Integration Tests for Maybe Finance
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def unique():
    return uuid.uuid4().hex[:8]


def headers(user_id=None):
    uid = user_id or str(uuid.uuid4())
    return {"X-User-Id": uid, "Content-Type": "application/json"}


def post(path, json_data, h):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=h, timeout=30)


def get(path, h, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=h, timeout=30)


def put(path, json_data, h):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=h, timeout=30)


def delete(path, h):
    return requests.delete(f"{BASE_URL}{path}", headers=h, timeout=30)


# ═══════════════════════════════════════════════════════════════
# L2 Tests — 3-5 steps, 8-12 assertions each
# ═══════════════════════════════════════════════════════════════


class TestAccountFieldsAndStatusCodes:
    """Pattern 1+4: Verify exact field names from openapi.yaml and correct status codes."""

    def test_account_create_returns_all_required_fields(self):
        h = headers()
        uid = h["X-User-Id"]
        name = f"Acct-{unique()}"
        r = post("/accounts", {"name": name, "account_type": "depository", "balance": 12345, "currency": "EUR", "institution_name": "TestBank"}, h)
        assert r.status_code == 201
        data = r.json()
        # Verify ALL required fields from schema
        assert "id" in data
        assert data["user_id"] == uid
        assert data["name"] == name
        assert data["account_type"] == "depository"
        assert data["balance"] == 12345
        assert data["currency"] == "EUR"
        assert data["institution_name"] == "TestBank"
        assert "created_at" in data
        assert "updated_at" in data
        # Verify UUID format for id
        uuid.UUID(data["id"])

    def test_account_update_preserves_unchanged_fields(self):
        h = headers()
        name = f"Preserve-{unique()}"
        r = post("/accounts", {"name": name, "account_type": "crypto", "balance": 99999, "currency": "BTC", "institution_name": "Coinbase"}, h)
        acct_id = r.json()["id"]
        # Update only name
        r2 = put(f"/accounts/{acct_id}", {"name": "NewName"}, h)
        assert r2.status_code == 200
        data = r2.json()
        assert data["name"] == "NewName"
        assert data["account_type"] == "crypto"
        assert data["balance"] == 99999
        assert data["currency"] == "BTC"
        assert data["institution_name"] == "Coinbase"
        assert data["id"] == acct_id

    def test_account_delete_returns_204_not_200(self):
        h = headers()
        r = post("/accounts", {"name": f"Del-{unique()}", "account_type": "other", "balance": 0}, h)
        acct_id = r.json()["id"]
        r2 = delete(f"/accounts/{acct_id}", h)
        assert r2.status_code == 204
        # Verify truly gone
        r3 = get(f"/accounts/{acct_id}", h)
        assert r3.status_code == 404
        assert "error" in r3.json()


class TestTransactionFieldIntegrity:
    """Pattern 1+2: Verify transaction fields including tags array and nullable fields."""

    def test_transaction_roundtrip_with_all_fields(self):
        h = headers()
        acct = post("/accounts", {"name": f"A-{unique()}", "account_type": "depository", "balance": 50000}, h).json()
        cat = post("/categories", {"name": f"C-{unique()}", "color": "#ABCDEF", "category_type": "expense"}, h).json()
        tag1 = post("/tags", {"name": f"T1-{unique()}", "color": "#111111"}, h).json()
        tag2 = post("/tags", {"name": f"T2-{unique()}", "color": "#222222"}, h).json()

        txn_name = f"Txn-{unique()}"
        r = post("/transactions", {
            "account_id": acct["id"],
            "date": "2024-07-19",
            "amount": 7777,
            "name": txn_name,
            "category_id": cat["id"],
            "tags": [tag1["id"], tag2["id"]],
            "notes": "Test notes here",
            "excluded": True
        }, h)
        assert r.status_code == 201
        txn = r.json()
        assert txn["account_id"] == acct["id"]
        assert txn["date"] == "2024-07-19"
        assert txn["amount"] == 7777
        assert txn["name"] == txn_name
        assert txn["category_id"] == cat["id"]
        assert set(txn["tags"]) == {tag1["id"], tag2["id"]}
        assert txn["notes"] == "Test notes here"
        assert txn["excluded"] is True

        # GET should return same data
        r2 = get(f"/transactions/{txn['id']}", h)
        assert r2.status_code == 200
        txn2 = r2.json()
        assert txn2["name"] == txn_name
        assert set(txn2["tags"]) == {tag1["id"], tag2["id"]}
        assert txn2["notes"] == "Test notes here"
        assert txn2["excluded"] is True

    def test_transaction_tags_are_array_not_string(self):
        """Verify tags field is always an array, never a string or null."""
        h = headers()
        acct = post("/accounts", {"name": f"A-{unique()}", "account_type": "depository", "balance": 1000}, h).json()
        r = post("/transactions", {"account_id": acct["id"], "date": "2024-05-01", "amount": 100, "name": "NoTags"}, h)
        assert r.status_code == 201
        txn = r.json()
        assert isinstance(txn["tags"], list)
        assert txn["tags"] == []
        # GET same transaction
        r2 = get(f"/transactions/{txn['id']}", h)
        assert isinstance(r2.json()["tags"], list)


class TestTransactionFiltersActuallyWork:
    """Pattern 3: Verify filters aren't just declared but actually filter results."""

    def test_account_id_filter_excludes_other_accounts(self):
        h = headers()
        acct1 = post("/accounts", {"name": f"FA1-{unique()}", "account_type": "depository", "balance": 1000}, h).json()
        acct2 = post("/accounts", {"name": f"FA2-{unique()}", "account_type": "depository", "balance": 2000}, h).json()
        # Create transactions in both accounts
        t1_name = f"InAcct1-{unique()}"
        t2_name = f"InAcct2-{unique()}"
        post("/transactions", {"account_id": acct1["id"], "date": "2024-03-01", "amount": 100, "name": t1_name}, h)
        post("/transactions", {"account_id": acct2["id"], "date": "2024-03-01", "amount": 200, "name": t2_name}, h)

        r = get("/transactions", h, params={"account_id": acct1["id"]})
        txns = r.json()
        names = [t["name"] for t in txns]
        assert t1_name in names
        assert t2_name not in names
        for t in txns:
            assert t["account_id"] == acct1["id"]

    def test_date_range_filter_is_inclusive(self):
        h = headers()
        acct = post("/accounts", {"name": f"DR-{unique()}", "account_type": "depository", "balance": 10000}, h).json()
        post("/transactions", {"account_id": acct["id"], "date": "2024-01-01", "amount": 100, "name": "Jan1"}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-01-15", "amount": 200, "name": "Jan15"}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-01-31", "amount": 300, "name": "Jan31"}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-02-01", "amount": 400, "name": "Feb1"}, h)

        r = get("/transactions", h, params={"start_date": "2024-01-15", "end_date": "2024-01-31", "account_id": acct["id"]})
        txns = r.json()
        names = [t["name"] for t in txns]
        assert "Jan15" in names
        assert "Jan31" in names
        assert "Jan1" not in names
        assert "Feb1" not in names

    def test_category_filter_only_returns_matching(self):
        h = headers()
        acct = post("/accounts", {"name": f"CF-{unique()}", "account_type": "depository", "balance": 5000}, h).json()
        cat1 = post("/categories", {"name": f"CatA-{unique()}", "color": "#AAA", "category_type": "expense"}, h).json()
        cat2 = post("/categories", {"name": f"CatB-{unique()}", "color": "#BBB", "category_type": "expense"}, h).json()
        n1 = f"WithCat1-{unique()}"
        n2 = f"WithCat2-{unique()}"
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 100, "name": n1, "category_id": cat1["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 200, "name": n2, "category_id": cat2["id"]}, h)

        r = get("/transactions", h, params={"category_id": cat1["id"]})
        txns = r.json()
        assert any(t["name"] == n1 for t in txns)
        assert not any(t["name"] == n2 for t in txns)
        for t in txns:
            assert t["category_id"] == cat1["id"]

    def test_tag_filter_returns_only_tagged_transactions(self):
        h = headers()
        acct = post("/accounts", {"name": f"TF-{unique()}", "account_type": "depository", "balance": 5000}, h).json()
        tag = post("/tags", {"name": f"FilterTag-{unique()}", "color": "#FFF"}, h).json()
        n1 = f"Tagged-{unique()}"
        n2 = f"Untagged-{unique()}"
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 100, "name": n1, "tags": [tag["id"]]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 200, "name": n2}, h)

        r = get("/transactions", h, params={"tag_id": tag["id"]})
        txns = r.json()
        assert any(t["name"] == n1 for t in txns)
        assert not any(t["name"] == n2 for t in txns)

    def test_excluded_filter_works_both_ways(self):
        h = headers()
        acct = post("/accounts", {"name": f"EF-{unique()}", "account_type": "depository", "balance": 5000}, h).json()
        n1 = f"Normal-{unique()}"
        n2 = f"Excluded-{unique()}"
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 100, "name": n1, "excluded": False}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 200, "name": n2, "excluded": True}, h)

        # Filter for excluded=true
        r1 = get("/transactions", h, params={"excluded": "true"})
        names1 = [t["name"] for t in r1.json()]
        assert n2 in names1
        assert n1 not in names1

        # Filter for excluded=false
        r2 = get("/transactions", h, params={"excluded": "false"})
        names2 = [t["name"] for t in r2.json()]
        assert n1 in names2
        assert n2 not in names2


class TestHoldingsValidation:
    """Pattern 4+5: Status codes and business rule enforcement for holdings."""

    def test_holding_on_non_investment_returns_400(self):
        h = headers()
        acct = post("/accounts", {"name": f"NonInv-{unique()}", "account_type": "depository", "balance": 5000}, h).json()
        r = post(f"/accounts/{acct['id']}/holdings", {"symbol": "X", "shares": 1, "cost_basis": 100, "current_value": 110}, h)
        assert r.status_code == 400
        assert "error" in r.json()

    def test_holding_crud_full_lifecycle(self):
        h = headers()
        acct = post("/accounts", {"name": f"Inv-{unique()}", "account_type": "investment", "balance": 100000}, h).json()
        # Create
        r = post(f"/accounts/{acct['id']}/holdings", {"symbol": "NVDA", "shares": 25.5, "cost_basis": 500000, "current_value": 750000}, h)
        assert r.status_code == 201
        holding = r.json()
        assert holding["symbol"] == "NVDA"
        assert holding["shares"] == 25.5
        assert holding["cost_basis"] == 500000
        assert holding["current_value"] == 750000
        assert holding["account_id"] == acct["id"]
        assert "id" in holding
        assert "created_at" in holding
        assert "updated_at" in holding

        # Update
        r2 = put(f"/accounts/{acct['id']}/holdings/{holding['id']}", {"current_value": 800000, "shares": 30.0}, h)
        assert r2.status_code == 200
        assert r2.json()["current_value"] == 800000
        assert r2.json()["shares"] == 30.0
        assert r2.json()["symbol"] == "NVDA"  # unchanged

        # Delete
        r3 = delete(f"/accounts/{acct['id']}/holdings/{holding['id']}", h)
        assert r3.status_code == 204
        r4 = get(f"/accounts/{acct['id']}/holdings/{holding['id']}", h)
        assert r4.status_code == 404

    def test_holdings_value_computed_on_account_get(self):
        """Pattern 5: holdings_value is actually computed, not always 0 or null."""
        h = headers()
        acct = post("/accounts", {"name": f"HV-{unique()}", "account_type": "investment", "balance": 10000}, h).json()
        post(f"/accounts/{acct['id']}/holdings", {"symbol": "A", "shares": 10, "cost_basis": 1000, "current_value": 15000}, h)
        post(f"/accounts/{acct['id']}/holdings", {"symbol": "B", "shares": 5, "cost_basis": 2000, "current_value": 25000}, h)

        r = get(f"/accounts/{acct['id']}", h)
        assert r.json()["holdings_value"] == 40000  # 15000 + 25000


class TestCategoryHierarchyRules:
    """Pattern 5+8: Business rules for parent/child categories."""

    def test_cannot_create_grandchild_category(self):
        h = headers()
        parent = post("/categories", {"name": f"P-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        child = post("/categories", {"name": f"C-{unique()}", "color": "#111", "category_type": "expense", "parent_id": parent["id"]}, h).json()
        # Try to make child a parent
        r = post("/categories", {"name": f"GC-{unique()}", "color": "#222", "category_type": "expense", "parent_id": child["id"]}, h)
        assert r.status_code == 400

    def test_cannot_set_self_as_parent(self):
        h = headers()
        cat = post("/categories", {"name": f"Self-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        r = put(f"/categories/{cat['id']}", {"parent_id": cat["id"]}, h)
        assert r.status_code == 400

    def test_delete_parent_orphans_children(self):
        h = headers()
        parent = post("/categories", {"name": f"DP-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        child = post("/categories", {"name": f"DC-{unique()}", "color": "#111", "category_type": "expense", "parent_id": parent["id"]}, h).json()
        assert child["parent_id"] == parent["id"]

        delete(f"/categories/{parent['id']}", h)
        # Child should still exist but with null parent
        r = get(f"/categories/{child['id']}", h)
        assert r.status_code == 200
        assert r.json()["parent_id"] is None

    def test_category_fields_complete(self):
        h = headers()
        uid = h["X-User-Id"]
        r = post("/categories", {"name": f"Full-{unique()}", "color": "#CAFE00", "category_type": "income"}, h)
        assert r.status_code == 201
        cat = r.json()
        assert "id" in cat
        assert cat["user_id"] == uid
        assert cat["color"] == "#CAFE00"
        assert cat["category_type"] == "income"
        assert "created_at" in cat
        assert "updated_at" in cat
        assert cat["parent_id"] is None


class TestBudgetComputedFields:
    """Pattern 5: Budget actual/remaining are truly computed, not hardcoded."""

    def test_budget_actual_changes_with_new_transactions(self):
        h = headers()
        cat = post("/categories", {"name": f"BC-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"BA-{unique()}", "account_type": "depository", "balance": 100000}, h).json()
        budget = post("/budgets", {"category_id": cat["id"], "month": 11, "year": 2025, "amount": 50000}, h).json()

        # Initially no transactions → actual should be 0
        r = get(f"/budgets/{budget['id']}", h)
        assert r.json()["actual"] == 0
        assert r.json()["remaining"] == 50000

        # Add a transaction
        post("/transactions", {"account_id": acct["id"], "date": "2025-11-10", "amount": 12000, "name": "T1", "category_id": cat["id"]}, h)
        r2 = get(f"/budgets/{budget['id']}", h)
        assert r2.json()["actual"] == 12000
        assert r2.json()["remaining"] == 38000

        # Add another transaction
        post("/transactions", {"account_id": acct["id"], "date": "2025-11-20", "amount": 8000, "name": "T2", "category_id": cat["id"]}, h)
        r3 = get(f"/budgets/{budget['id']}", h)
        assert r3.json()["actual"] == 20000
        assert r3.json()["remaining"] == 30000

    def test_budget_actual_ignores_excluded_transactions(self):
        h = headers()
        cat = post("/categories", {"name": f"BE-{unique()}", "color": "#111", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"BEA-{unique()}", "account_type": "depository", "balance": 100000}, h).json()
        budget = post("/budgets", {"category_id": cat["id"], "month": 12, "year": 2025, "amount": 30000}, h).json()

        post("/transactions", {"account_id": acct["id"], "date": "2025-12-05", "amount": 5000, "name": "Normal", "category_id": cat["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2025-12-10", "amount": 9000, "name": "Excl", "category_id": cat["id"], "excluded": True}, h)

        r = get(f"/budgets/{budget['id']}", h)
        assert r.json()["actual"] == 5000  # excluded one not counted
        assert r.json()["remaining"] == 25000

    def test_budget_duplicate_returns_400(self):
        h = headers()
        cat = post("/categories", {"name": f"BD-{unique()}", "color": "#222", "category_type": "expense"}, h).json()
        r1 = post("/budgets", {"category_id": cat["id"], "month": 1, "year": 2030, "amount": 10000}, h)
        assert r1.status_code == 201
        r2 = post("/budgets", {"category_id": cat["id"], "month": 1, "year": 2030, "amount": 20000}, h)
        assert r2.status_code == 400

    def test_budget_filter_requires_both_month_and_year(self):
        h = headers()
        r1 = get("/budgets", h, params={"month": 5})
        assert r1.status_code == 400
        r2 = get("/budgets", h, params={"year": 2024})
        assert r2.status_code == 400
        # Both provided should work
        r3 = get("/budgets", h, params={"month": 5, "year": 2024})
        assert r3.status_code == 200


class TestNetWorthComputation:
    """Pattern 5: Net worth values are actually computed correctly."""

    def test_net_worth_with_mixed_account_types(self):
        h = headers()
        # Depository (asset)
        post("/accounts", {"name": f"Dep-{unique()}", "account_type": "depository", "balance": 100000}, h)
        # Investment with holdings
        inv = post("/accounts", {"name": f"Inv-{unique()}", "account_type": "investment", "balance": 20000}, h).json()
        post(f"/accounts/{inv['id']}/holdings", {"symbol": "SPY", "shares": 10, "cost_basis": 50000, "current_value": 60000}, h)
        # Credit card (liability)
        post("/accounts", {"name": f"CC-{unique()}", "account_type": "credit_card", "balance": -30000}, h)
        # Loan (liability)
        post("/accounts", {"name": f"Loan-{unique()}", "account_type": "loan", "balance": -50000}, h)

        r = get("/net-worth", h)
        assert r.status_code == 200
        data = r.json()
        # assets = 100000 (dep) + 20000 (inv balance) + 60000 (holdings) = 180000
        assert data["assets"] == 180000
        # liabilities = 30000 (cc) + 50000 (loan) = 80000
        assert data["liabilities"] == 80000
        assert data["net_worth"] == 100000
        # Accounts list should be present
        assert "accounts" in data
        assert isinstance(data["accounts"], list)
        assert len(data["accounts"]) == 4

    def test_net_worth_accounts_have_required_fields(self):
        h = headers()
        name = f"NWAcct-{unique()}"
        acct = post("/accounts", {"name": name, "account_type": "depository", "balance": 77777}, h).json()
        r = get("/net-worth", h)
        data = r.json()
        acct_entry = next(a for a in data["accounts"] if a["id"] == acct["id"])
        assert acct_entry["name"] == name
        assert acct_entry["account_type"] == "depository"
        assert acct_entry["balance"] == 77777
        assert "holdings_value" in acct_entry


class TestSyncBehavior:
    """Pattern 5+7: Sync actually updates balance and creates transactions."""

    def test_sync_records_before_after_balance(self):
        h = headers()
        acct = post("/accounts", {"name": f"Sync-{unique()}", "account_type": "depository", "balance": 80000}, h).json()
        r = post(f"/accounts/{acct['id']}/syncs", {
            "balance": 75000,
            "transactions": [
                {"date": "2024-06-01", "amount": 3000, "name": f"SyncTxn1-{unique()}"},
                {"date": "2024-06-02", "amount": 2000, "name": f"SyncTxn2-{unique()}"}
            ]
        }, h)
        assert r.status_code == 201
        sync = r.json()
        assert sync["balance_before"] == 80000
        assert sync["balance_after"] == 75000
        assert sync["transactions_created"] == 2
        assert sync["account_id"] == acct["id"]
        assert "id" in sync
        assert "created_at" in sync

        # Verify account balance actually updated
        acct2 = get(f"/accounts/{acct['id']}", h).json()
        assert acct2["balance"] == 75000

    def test_sync_transactions_appear_in_list(self):
        h = headers()
        acct = post("/accounts", {"name": f"SyncList-{unique()}", "account_type": "depository", "balance": 50000}, h).json()
        txn_name = f"SyncCreated-{unique()}"
        post(f"/accounts/{acct['id']}/syncs", {
            "balance": 47000,
            "transactions": [{"date": "2024-06-10", "amount": 3000, "name": txn_name}]
        }, h)

        r = get("/transactions", h, params={"account_id": acct["id"]})
        names = [t["name"] for t in r.json()]
        assert txn_name in names

    def test_sync_on_nonexistent_account_returns_404(self):
        h = headers()
        fake_id = str(uuid.uuid4())
        r = post(f"/accounts/{fake_id}/syncs", {"balance": 0, "transactions": []}, h)
        assert r.status_code == 404


class TestInsightsComputation:
    """Pattern 5: Insights are actually computed from data, not hardcoded."""

    def test_income_vs_expenses_computed_correctly(self):
        h = headers()
        inc_cat = post("/categories", {"name": f"Inc-{unique()}", "color": "#0F0", "category_type": "income"}, h).json()
        exp_cat = post("/categories", {"name": f"Exp-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"IE-{unique()}", "account_type": "depository", "balance": 500000}, h).json()

        post("/transactions", {"account_id": acct["id"], "date": "2024-05-01", "amount": 300000, "name": "Salary", "category_id": inc_cat["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-05-05", "amount": 80000, "name": "Rent", "category_id": exp_cat["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-05-10", "amount": 20000, "name": "Food", "category_id": exp_cat["id"]}, h)

        r = get("/insights/income-vs-expenses", h, params={"month": 5, "year": 2024})
        assert r.status_code == 200
        data = r.json()
        assert data["income"] == 300000
        assert data["expenses"] == 100000
        assert data["net"] == 200000

    def test_savings_rate_computed_correctly(self):
        h = headers()
        inc_cat = post("/categories", {"name": f"SRInc-{unique()}", "color": "#0F0", "category_type": "income"}, h).json()
        exp_cat = post("/categories", {"name": f"SRExp-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"SR-{unique()}", "account_type": "depository", "balance": 200000}, h).json()

        post("/transactions", {"account_id": acct["id"], "date": "2024-08-01", "amount": 200000, "name": "Salary", "category_id": inc_cat["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-08-10", "amount": 50000, "name": "Expense", "category_id": exp_cat["id"]}, h)

        r = get("/insights/savings-rate", h, params={"month": 8, "year": 2024})
        assert r.status_code == 200
        data = r.json()
        # savings_rate = (200000-50000)/200000 * 100 = 75.0
        assert data["savings_rate"] == pytest.approx(75.0, abs=0.01)
        assert data["income"] == 200000
        assert data["expenses"] == 50000

    def test_insights_missing_params_return_400(self):
        h = headers()
        r1 = get("/insights/spending-by-category", h, params={"month": 3})
        assert r1.status_code == 400
        r2 = get("/insights/income-vs-expenses", h, params={"year": 2024})
        assert r2.status_code == 400
        r3 = get("/insights/savings-rate", h)
        assert r3.status_code == 400

    def test_spending_by_category_has_required_fields(self):
        h = headers()
        cat = post("/categories", {"name": f"SpCat-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"SpA-{unique()}", "account_type": "depository", "balance": 100000}, h).json()
        post("/transactions", {"account_id": acct["id"], "date": "2024-04-10", "amount": 5000, "name": "X", "category_id": cat["id"]}, h)

        r = get("/insights/spending-by-category", h, params={"month": 4, "year": 2024})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        entry = next(d for d in data if d["category_id"] == cat["id"])
        assert "category_name" in entry
        assert "amount" in entry
        assert "previous_amount" in entry
        assert "change_percent" in entry
        assert entry["amount"] == 5000


class TestDataIsolationBetweenUsers:
    """Pattern 6: Data isolation is strictly enforced."""

    def test_user_cannot_see_others_accounts(self):
        h1 = headers()
        h2 = headers()
        name = f"Private-{unique()}"
        acct = post("/accounts", {"name": name, "account_type": "depository", "balance": 1000}, h1).json()

        # Direct access returns 404
        r = get(f"/accounts/{acct['id']}", h2)
        assert r.status_code == 404

        # Not in list
        r2 = get("/accounts", h2)
        names = [a["name"] for a in r2.json()]
        assert name not in names

    def test_user_cannot_use_others_category_in_transaction(self):
        h1 = headers()
        h2 = headers()
        cat = post("/categories", {"name": f"Cat-{unique()}", "color": "#000", "category_type": "expense"}, h1).json()
        acct = post("/accounts", {"name": f"Acct-{unique()}", "account_type": "depository", "balance": 5000}, h2).json()

        r = post("/transactions", {
            "account_id": acct["id"],
            "date": "2024-03-01",
            "amount": 100,
            "name": "Stolen",
            "category_id": cat["id"]
        }, h2)
        assert r.status_code == 400

    def test_user_cannot_use_others_tag_in_transaction(self):
        h1 = headers()
        h2 = headers()
        tag = post("/tags", {"name": f"Tag-{unique()}", "color": "#000"}, h1).json()
        acct = post("/accounts", {"name": f"Acct-{unique()}", "account_type": "depository", "balance": 5000}, h2).json()

        r = post("/transactions", {
            "account_id": acct["id"],
            "date": "2024-03-01",
            "amount": 100,
            "name": "Stolen",
            "tags": [tag["id"]]
        }, h2)
        assert r.status_code == 400


class TestCascadeDeleteSideEffects:
    """Pattern 7: Verify cascade/side effects are actually implemented."""

    def test_delete_account_removes_transactions(self):
        h = headers()
        acct = post("/accounts", {"name": f"CascA-{unique()}", "account_type": "depository", "balance": 10000}, h).json()
        txn = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 500, "name": f"CascTxn-{unique()}"}, h).json()

        r = delete(f"/accounts/{acct['id']}", h)
        assert r.status_code == 204

        r2 = get(f"/transactions/{txn['id']}", h)
        assert r2.status_code == 404

    def test_delete_category_nullifies_transaction_category(self):
        h = headers()
        cat = post("/categories", {"name": f"CascCat-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"CascCatA-{unique()}", "account_type": "depository", "balance": 10000}, h).json()
        txn = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 500, "name": "X", "category_id": cat["id"]}, h).json()

        delete(f"/categories/{cat['id']}", h)
        txn2 = get(f"/transactions/{txn['id']}", h).json()
        assert txn2["category_id"] is None

    def test_delete_category_deletes_associated_budgets(self):
        h = headers()
        cat = post("/categories", {"name": f"CascBudCat-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        budget = post("/budgets", {"category_id": cat["id"], "month": 2, "year": 2030, "amount": 10000}, h).json()

        delete(f"/categories/{cat['id']}", h)
        r = get(f"/budgets/{budget['id']}", h)
        assert r.status_code == 404

    def test_delete_tag_removes_from_transaction_tags(self):
        h = headers()
        tag = post("/tags", {"name": f"CascTag-{unique()}", "color": "#000"}, h).json()
        acct = post("/accounts", {"name": f"CascTagA-{unique()}", "account_type": "depository", "balance": 10000}, h).json()
        txn = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 500, "name": "Y", "tags": [tag["id"]]}, h).json()
        assert tag["id"] in txn["tags"]

        delete(f"/tags/{tag['id']}", h)
        txn2 = get(f"/transactions/{txn['id']}", h).json()
        assert tag["id"] not in txn2["tags"]


class TestAuthenticationEnforcement:
    """Pattern 4: 401 for missing/empty auth header."""

    def test_all_endpoints_require_auth(self):
        endpoints = [
            ("GET", "/accounts"),
            ("GET", "/transactions"),
            ("GET", "/categories"),
            ("GET", "/tags"),
            ("GET", "/budgets"),
            ("GET", "/net-worth"),
            ("GET", "/insights/spending-by-category?month=1&year=2024"),
            ("GET", "/insights/income-vs-expenses?month=1&year=2024"),
            ("GET", "/insights/savings-rate?month=1&year=2024"),
        ]
        for method, path in endpoints:
            r = requests.request(method, f"{BASE_URL}{path}", timeout=30)
            assert r.status_code == 401, f"{method} {path} returned {r.status_code} without auth"

    def test_empty_user_id_returns_401(self):
        r = requests.get(f"{BASE_URL}/accounts", headers={"X-User-Id": ""}, timeout=30)
        assert r.status_code == 401
