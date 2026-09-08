"""
BackendForge — L3 Workflow Tests for Maybe Finance
Complex multi-step workflows that cross multiple entity types.
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


class TestFullBudgetWorkflow:
    """Pattern 2+5+7: Complete budget lifecycle with computed fields and cascades."""

    def test_budget_lifecycle_with_transactions_and_child_categories(self):
        h = headers()
        # 1. Create parent expense category
        parent_cat = post("/categories", {"name": f"Food-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        # 2. Create child category
        child_cat = post("/categories", {"name": f"FastFood-{unique()}", "color": "#FF0", "category_type": "expense", "parent_id": parent_cat["id"]}, h).json()
        assert child_cat["parent_id"] == parent_cat["id"]

        # 3. Create account
        acct = post("/accounts", {"name": f"BudWF-{unique()}", "account_type": "depository", "balance": 200000}, h).json()

        # 4. Create budget for parent category
        budget = post("/budgets", {"category_id": parent_cat["id"], "month": 6, "year": 2025, "amount": 40000}, h).json()
        assert budget["category_id"] == parent_cat["id"]
        assert budget["amount"] == 40000

        # 5. Verify initial actual=0
        b = get(f"/budgets/{budget['id']}", h).json()
        assert b["actual"] == 0
        assert b["remaining"] == 40000

        # 6. Add transaction in parent category
        post("/transactions", {"account_id": acct["id"], "date": "2025-06-10", "amount": 15000, "name": "Groceries", "category_id": parent_cat["id"]}, h)
        b2 = get(f"/budgets/{budget['id']}", h).json()
        assert b2["actual"] == 15000
        assert b2["remaining"] == 25000

        # 7. Add transaction in child category — should roll up to parent budget
        post("/transactions", {"account_id": acct["id"], "date": "2025-06-15", "amount": 8000, "name": "McDonalds", "category_id": child_cat["id"]}, h)
        b3 = get(f"/budgets/{budget['id']}", h).json()
        assert b3["actual"] == 23000  # 15000 + 8000
        assert b3["remaining"] == 17000

        # 8. Add excluded transaction — should NOT affect budget
        post("/transactions", {"account_id": acct["id"], "date": "2025-06-20", "amount": 50000, "name": "Gift", "category_id": parent_cat["id"], "excluded": True}, h)
        b4 = get(f"/budgets/{budget['id']}", h).json()
        assert b4["actual"] == 23000  # unchanged

        # 9. Transaction in different month — should NOT affect this budget
        post("/transactions", {"account_id": acct["id"], "date": "2025-07-01", "amount": 10000, "name": "July", "category_id": parent_cat["id"]}, h)
        b5 = get(f"/budgets/{budget['id']}", h).json()
        assert b5["actual"] == 23000  # unchanged

        # 10. Update budget amount
        r = put(f"/budgets/{budget['id']}", {"amount": 30000}, h)
        assert r.status_code == 200
        assert r.json()["amount"] == 30000

        # 11. Verify remaining recalculated
        b6 = get(f"/budgets/{budget['id']}", h).json()
        assert b6["remaining"] == 7000  # 30000 - 23000

        # 12. Delete category → budget should be deleted
        delete(f"/categories/{parent_cat['id']}", h)
        r2 = get(f"/budgets/{budget['id']}", h)
        assert r2.status_code == 404


class TestInvestmentPortfolioWorkflow:
    """Pattern 2+5+7: Investment account with holdings affecting net worth."""

    def test_investment_lifecycle_affects_net_worth(self):
        h = headers()
        # 1. Create checking account
        checking = post("/accounts", {"name": f"Checking-{unique()}", "account_type": "depository", "balance": 500000}, h).json()

        # 2. Create investment account
        investment = post("/accounts", {"name": f"Brokerage-{unique()}", "account_type": "investment", "balance": 100000}, h).json()

        # 3. Verify initial net worth
        nw = get("/net-worth", h).json()
        assert nw["assets"] == 600000
        assert nw["liabilities"] == 0
        assert nw["net_worth"] == 600000

        # 4. Add holdings
        h1 = post(f"/accounts/{investment['id']}/holdings", {"symbol": "AAPL", "shares": 10, "cost_basis": 150000, "current_value": 180000}, h).json()
        h2 = post(f"/accounts/{investment['id']}/holdings", {"symbol": "MSFT", "shares": 5, "cost_basis": 200000, "current_value": 220000}, h).json()

        # 5. Verify account holdings_value
        acct = get(f"/accounts/{investment['id']}", h).json()
        assert acct["holdings_value"] == 400000  # 180000 + 220000

        # 6. Verify net worth includes holdings
        nw2 = get("/net-worth", h).json()
        # assets = 500000 (checking) + 100000 (inv cash) + 180000 + 220000 (holdings) = 1000000
        assert nw2["assets"] == 1000000
        assert nw2["net_worth"] == 1000000

        # 7. Update a holding value
        put(f"/accounts/{investment['id']}/holdings/{h1['id']}", {"current_value": 200000}, h)
        nw3 = get("/net-worth", h).json()
        assert nw3["assets"] == 1020000  # +20000 from AAPL increase

        # 8. Add a loan (liability)
        post("/accounts", {"name": f"Loan-{unique()}", "account_type": "loan", "balance": -300000}, h)
        nw4 = get("/net-worth", h).json()
        assert nw4["liabilities"] == 300000
        assert nw4["net_worth"] == 720000  # 1020000 - 300000

        # 9. Delete a holding
        delete(f"/accounts/{investment['id']}/holdings/{h2['id']}", h)
        nw5 = get("/net-worth", h).json()
        assert nw5["assets"] == 800000  # 1020000 - 220000

        # 10. Delete investment account — cascades holdings
        delete(f"/accounts/{investment['id']}", h)
        nw6 = get("/net-worth", h).json()
        # Only checking remains as asset
        assert nw6["assets"] == 500000


class TestSyncWorkflow:
    """Pattern 5+7: Sync creates transactions and updates balance correctly."""

    def test_multiple_syncs_track_balance_history(self):
        h = headers()
        # 1. Create account
        acct = post("/accounts", {"name": f"SyncWF-{unique()}", "account_type": "depository", "balance": 100000}, h).json()

        # 2. First sync
        s1 = post(f"/accounts/{acct['id']}/syncs", {
            "balance": 95000,
            "transactions": [
                {"date": "2024-06-01", "amount": 3000, "name": f"Coffee-{unique()}"},
                {"date": "2024-06-02", "amount": 2000, "name": f"Gas-{unique()}"}
            ]
        }, h).json()
        assert s1["balance_before"] == 100000
        assert s1["balance_after"] == 95000
        assert s1["transactions_created"] == 2

        # 3. Verify account balance
        acct2 = get(f"/accounts/{acct['id']}", h).json()
        assert acct2["balance"] == 95000

        # 4. Second sync
        s2 = post(f"/accounts/{acct['id']}/syncs", {
            "balance": 88000,
            "transactions": [
                {"date": "2024-06-03", "amount": 7000, "name": f"Dinner-{unique()}"}
            ]
        }, h).json()
        assert s2["balance_before"] == 95000
        assert s2["balance_after"] == 88000
        assert s2["transactions_created"] == 1

        # 5. Verify sync history
        syncs = get(f"/accounts/{acct['id']}/syncs", h).json()
        assert len(syncs) >= 2

        # 6. Verify all transactions exist
        txns = get("/transactions", h, params={"account_id": acct["id"]}).json()
        assert len(txns) >= 3

        # 7. Verify account balance after second sync
        acct3 = get(f"/accounts/{acct['id']}", h).json()
        assert acct3["balance"] == 88000

        # 8. Delete account → cascades syncs and transactions
        delete(f"/accounts/{acct['id']}", h)
        r = get(f"/accounts/{acct['id']}/syncs", h)
        assert r.status_code == 404


class TestSpendingInsightsWorkflow:
    """Pattern 5+7: Spending insights with category rollup and month-over-month comparison."""

    def test_spending_insights_with_rollup_and_change_percent(self):
        h = headers()
        # 1. Create parent category
        parent = post("/categories", {"name": f"Transport-{unique()}", "color": "#00F", "category_type": "expense"}, h).json()
        # 2. Create child category
        child = post("/categories", {"name": f"Uber-{unique()}", "color": "#0FF", "category_type": "expense", "parent_id": parent["id"]}, h).json()
        # 3. Create income category (should NOT appear in spending)
        inc_cat = post("/categories", {"name": f"Salary-{unique()}", "color": "#0F0", "category_type": "income"}, h).json()
        # 4. Create account
        acct = post("/accounts", {"name": f"SI-{unique()}", "account_type": "depository", "balance": 500000}, h).json()

        # 5. Create February (previous month) transactions
        post("/transactions", {"account_id": acct["id"], "date": "2024-02-10", "amount": 10000, "name": "Feb bus", "category_id": parent["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-02-20", "amount": 5000, "name": "Feb uber", "category_id": child["id"]}, h)

        # 6. Create March (current month) transactions
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-05", "amount": 8000, "name": "Mar bus", "category_id": parent["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-15", "amount": 12000, "name": "Mar uber", "category_id": child["id"]}, h)
        # Excluded transaction should NOT count
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-20", "amount": 50000, "name": "Excluded trip", "category_id": parent["id"], "excluded": True}, h)
        # Income should NOT appear
        post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 300000, "name": "Salary", "category_id": inc_cat["id"]}, h)

        # 7. Get spending by category for March
        r = get("/insights/spending-by-category", h, params={"month": 3, "year": 2024})
        assert r.status_code == 200
        data = r.json()

        # 8. Verify parent includes child rollup
        parent_entry = next(d for d in data if d["category_id"] == parent["id"])
        assert parent_entry["amount"] == 20000  # 8000 + 12000
        assert parent_entry["previous_amount"] == 15000  # 10000 + 5000
        # change_percent = (20000 - 15000) / 15000 * 100 = 33.33...
        assert parent_entry["change_percent"] == pytest.approx(33.33, abs=0.5)
        assert parent_entry["category_name"] == parent["name"]

        # 9. Verify income category NOT in results
        cat_ids = [d["category_id"] for d in data]
        assert inc_cat["id"] not in cat_ids


class TestCompleteDataIsolationWorkflow:
    """Pattern 6: Full isolation test across all entity types."""

    def test_complete_isolation_between_users(self):
        h1 = headers()
        h2 = headers()

        # 1. User1 creates full data set
        acct1 = post("/accounts", {"name": f"U1Acct-{unique()}", "account_type": "investment", "balance": 50000}, h1).json()
        cat1 = post("/categories", {"name": f"U1Cat-{unique()}", "color": "#000", "category_type": "expense"}, h1).json()
        tag1 = post("/tags", {"name": f"U1Tag-{unique()}", "color": "#111"}, h1).json()
        txn1 = post("/transactions", {"account_id": acct1["id"], "date": "2024-03-01", "amount": 1000, "name": f"U1Txn-{unique()}", "category_id": cat1["id"], "tags": [tag1["id"]]}, h1).json()
        post(f"/accounts/{acct1['id']}/holdings", {"symbol": "SPY", "shares": 10, "cost_basis": 100000, "current_value": 110000}, h1)

        # 2. User2 cannot access any of user1's resources
        assert get(f"/accounts/{acct1['id']}", h2).status_code == 404
        assert get(f"/categories/{cat1['id']}", h2).status_code == 404
        assert get(f"/tags/{tag1['id']}", h2).status_code == 404
        assert get(f"/transactions/{txn1['id']}", h2).status_code == 404
        assert get(f"/accounts/{acct1['id']}/holdings", h2).status_code == 404

        # 3. User2 cannot delete user1's resources
        assert delete(f"/accounts/{acct1['id']}", h2).status_code == 404
        assert delete(f"/categories/{cat1['id']}", h2).status_code == 404
        assert delete(f"/tags/{tag1['id']}", h2).status_code == 404
        assert delete(f"/transactions/{txn1['id']}", h2).status_code == 404

        # 4. User2 cannot use user1's account for transactions
        acct2 = post("/accounts", {"name": f"U2Acct-{unique()}", "account_type": "depository", "balance": 1000}, h2).json()
        r = post("/transactions", {"account_id": acct1["id"], "date": "2024-03-01", "amount": 100, "name": "Steal"}, h2)
        assert r.status_code == 400

        # 5. User2's net worth is independent
        nw2 = get("/net-worth", h2).json()
        assert nw2["net_worth"] == 1000  # only u2's account

        # 6. User1's net worth includes their holdings
        nw1 = get("/net-worth", h1).json()
        assert nw1["assets"] == 160000  # 50000 + 110000


class TestTransactionUpdateWorkflow:
    """Pattern 1+7: Transaction updates with category/tag changes and effects."""

    def test_transaction_category_change_affects_budgets(self):
        h = headers()
        cat1 = post("/categories", {"name": f"Cat1-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        cat2 = post("/categories", {"name": f"Cat2-{unique()}", "color": "#0F0", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"TUA-{unique()}", "account_type": "depository", "balance": 100000}, h).json()

        # 1. Create budgets for both categories
        b1 = post("/budgets", {"category_id": cat1["id"], "month": 9, "year": 2025, "amount": 50000}, h).json()
        b2 = post("/budgets", {"category_id": cat2["id"], "month": 9, "year": 2025, "amount": 30000}, h).json()

        # 2. Create transaction in cat1
        txn = post("/transactions", {"account_id": acct["id"], "date": "2025-09-15", "amount": 10000, "name": "Moveable", "category_id": cat1["id"]}, h).json()

        # 3. Verify budget1 actual
        assert get(f"/budgets/{b1['id']}", h).json()["actual"] == 10000
        assert get(f"/budgets/{b2['id']}", h).json()["actual"] == 0

        # 4. Move transaction to cat2
        put(f"/transactions/{txn['id']}", {"category_id": cat2["id"]}, h)

        # 5. Verify budget1 actual decreased, budget2 increased
        assert get(f"/budgets/{b1['id']}", h).json()["actual"] == 0
        assert get(f"/budgets/{b2['id']}", h).json()["actual"] == 10000

        # 6. Set category to null
        put(f"/transactions/{txn['id']}", {"category_id": None}, h)
        assert get(f"/budgets/{b1['id']}", h).json()["actual"] == 0
        assert get(f"/budgets/{b2['id']}", h).json()["actual"] == 0

    def test_transaction_tag_update_replaces_tags(self):
        h = headers()
        acct = post("/accounts", {"name": f"TT-{unique()}", "account_type": "depository", "balance": 5000}, h).json()
        tag1 = post("/tags", {"name": f"TagA-{unique()}", "color": "#111"}, h).json()
        tag2 = post("/tags", {"name": f"TagB-{unique()}", "color": "#222"}, h).json()
        tag3 = post("/tags", {"name": f"TagC-{unique()}", "color": "#333"}, h).json()

        # Create with tag1 and tag2
        txn = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 100, "name": "TagTest", "tags": [tag1["id"], tag2["id"]]}, h).json()
        assert set(txn["tags"]) == {tag1["id"], tag2["id"]}

        # Update to tag2 and tag3
        r = put(f"/transactions/{txn['id']}", {"tags": [tag2["id"], tag3["id"]]}, h)
        assert r.status_code == 200
        updated = r.json()
        assert set(updated["tags"]) == {tag2["id"], tag3["id"]}

        # Verify on GET
        fetched = get(f"/transactions/{txn['id']}", h).json()
        assert set(fetched["tags"]) == {tag2["id"], tag3["id"]}


class TestAccountDeletionCascadeWorkflow:
    """Pattern 7: Comprehensive cascade delete verification."""

    def test_account_delete_cascades_everything(self):
        h = headers()
        # 1. Create investment account
        acct = post("/accounts", {"name": f"CascWF-{unique()}", "account_type": "investment", "balance": 100000}, h).json()

        # 2. Add holdings
        hold = post(f"/accounts/{acct['id']}/holdings", {"symbol": "VTI", "shares": 50, "cost_basis": 500000, "current_value": 600000}, h).json()

        # 3. Add transactions
        txn = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 5000, "name": f"CascTxn-{unique()}"}, h).json()

        # 4. Add syncs
        sync = post(f"/accounts/{acct['id']}/syncs", {"balance": 95000, "transactions": []}, h).json()

        # 5. Verify all exist
        assert get(f"/accounts/{acct['id']}", h).status_code == 200
        assert get(f"/accounts/{acct['id']}/holdings/{hold['id']}", h).status_code == 200
        assert get(f"/transactions/{txn['id']}", h).status_code == 200
        assert len(get(f"/accounts/{acct['id']}/syncs", h).json()) >= 1

        # 6. Delete account
        r = delete(f"/accounts/{acct['id']}", h)
        assert r.status_code == 204

        # 7. Verify everything is gone
        assert get(f"/accounts/{acct['id']}", h).status_code == 404
        assert get(f"/transactions/{txn['id']}", h).status_code == 404
        assert get(f"/accounts/{acct['id']}/holdings/{hold['id']}", h).status_code == 404
        assert get(f"/accounts/{acct['id']}/syncs", h).status_code == 404


class TestSavingsRateWorkflow:
    """Pattern 5: Savings rate calculation with various scenarios."""

    def test_savings_rate_with_excluded_and_multiple_categories(self):
        h = headers()
        # 1. Setup
        inc1 = post("/categories", {"name": f"Salary-{unique()}", "color": "#0F0", "category_type": "income"}, h).json()
        inc2 = post("/categories", {"name": f"Freelance-{unique()}", "color": "#0A0", "category_type": "income"}, h).json()
        exp1 = post("/categories", {"name": f"Rent-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        exp2 = post("/categories", {"name": f"Food-{unique()}", "color": "#A00", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"SRW-{unique()}", "account_type": "depository", "balance": 1000000}, h).json()

        # 2. Add income transactions for Oct 2024
        post("/transactions", {"account_id": acct["id"], "date": "2024-10-01", "amount": 500000, "name": "Salary", "category_id": inc1["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-10-15", "amount": 100000, "name": "Freelance", "category_id": inc2["id"]}, h)

        # 3. Add expense transactions
        post("/transactions", {"account_id": acct["id"], "date": "2024-10-03", "amount": 200000, "name": "Rent", "category_id": exp1["id"]}, h)
        post("/transactions", {"account_id": acct["id"], "date": "2024-10-10", "amount": 50000, "name": "Groceries", "category_id": exp2["id"]}, h)

        # 4. Add excluded transaction (should not count)
        post("/transactions", {"account_id": acct["id"], "date": "2024-10-20", "amount": 300000, "name": "Transfer", "category_id": exp1["id"], "excluded": True}, h)

        # 5. Get savings rate
        r = get("/insights/savings-rate", h, params={"month": 10, "year": 2024})
        assert r.status_code == 200
        data = r.json()
        assert data["income"] == 600000  # 500000 + 100000
        assert data["expenses"] == 250000  # 200000 + 50000
        # savings_rate = (600000 - 250000) / 600000 * 100 = 58.33
        assert data["savings_rate"] == pytest.approx(58.33, abs=0.01)

        # 6. Get income vs expenses
        r2 = get("/insights/income-vs-expenses", h, params={"month": 10, "year": 2024})
        data2 = r2.json()
        assert data2["income"] == 600000
        assert data2["expenses"] == 250000
        assert data2["net"] == 350000

    def test_savings_rate_zero_income(self):
        h = headers()
        r = get("/insights/savings-rate", h, params={"month": 1, "year": 2099})
        assert r.status_code == 200
        assert r.json()["savings_rate"] == 0.0
        assert r.json()["income"] == 0
        assert r.json()["expenses"] == 0


class TestCategoryDeletionWorkflow:
    """Pattern 7: Category deletion effects on transactions, budgets, and children."""

    def test_parent_category_deletion_full_effects(self):
        h = headers()
        # 1. Create parent with child
        parent = post("/categories", {"name": f"Parent-{unique()}", "color": "#000", "category_type": "expense"}, h).json()
        child = post("/categories", {"name": f"Child-{unique()}", "color": "#111", "category_type": "expense", "parent_id": parent["id"]}, h).json()
        assert child["parent_id"] == parent["id"]

        # 2. Create transactions in parent
        acct = post("/accounts", {"name": f"CDW-{unique()}", "account_type": "depository", "balance": 100000}, h).json()
        txn_parent = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 5000, "name": "ParentTxn", "category_id": parent["id"]}, h).json()
        txn_child = post("/transactions", {"account_id": acct["id"], "date": "2024-03-01", "amount": 3000, "name": "ChildTxn", "category_id": child["id"]}, h).json()

        # 3. Create budget for parent
        budget = post("/budgets", {"category_id": parent["id"], "month": 3, "year": 2024, "amount": 20000}, h).json()

        # 4. Verify budget actual includes child rollup
        b = get(f"/budgets/{budget['id']}", h).json()
        assert b["actual"] == 8000  # 5000 + 3000

        # 5. Delete parent category
        r = delete(f"/categories/{parent['id']}", h)
        assert r.status_code == 204

        # 6. Verify child's parent_id is now null
        child2 = get(f"/categories/{child['id']}", h).json()
        assert child2["parent_id"] is None

        # 7. Verify parent transaction's category_id is null
        txn_p2 = get(f"/transactions/{txn_parent['id']}", h).json()
        assert txn_p2["category_id"] is None

        # 8. Verify child transaction still has its category
        txn_c2 = get(f"/transactions/{txn_child['id']}", h).json()
        assert txn_c2["category_id"] == child["id"]

        # 9. Budget for parent should be deleted
        r2 = get(f"/budgets/{budget['id']}", h)
        assert r2.status_code == 404


class TestHoldingsOnNonInvestmentAccounts:
    """Pattern 4+8: Holdings are only valid on investment accounts."""

    def test_holdings_rejected_for_all_non_investment_types(self):
        h = headers()
        non_inv_types = ["depository", "crypto", "property", "vehicle", "loan", "credit_card", "other"]
        for acct_type in non_inv_types:
            balance = -1000 if acct_type in {"loan", "credit_card"} else 1000
            acct = post("/accounts", {"name": f"NI-{acct_type}-{unique()}", "account_type": acct_type, "balance": balance}, h).json()
            r = post(f"/accounts/{acct['id']}/holdings", {"symbol": "X", "shares": 1, "cost_basis": 100, "current_value": 110}, h)
            assert r.status_code == 400, f"Holdings should be rejected for {acct_type} account"


class TestSyncWithCategoryWorkflow:
    """Pattern 5+7: Sync can create transactions with categories."""

    def test_sync_transactions_with_category_appear_in_insights(self):
        h = headers()
        # 1. Setup
        cat = post("/categories", {"name": f"SyncCat-{unique()}", "color": "#F00", "category_type": "expense"}, h).json()
        acct = post("/accounts", {"name": f"SyncIns-{unique()}", "account_type": "depository", "balance": 100000}, h).json()

        # 2. Sync with categorized transactions
        post(f"/accounts/{acct['id']}/syncs", {
            "balance": 85000,
            "transactions": [
                {"date": "2024-04-05", "amount": 8000, "name": f"SyncDinner-{unique()}", "category_id": cat["id"]},
                {"date": "2024-04-10", "amount": 7000, "name": f"SyncLunch-{unique()}", "category_id": cat["id"]}
            ]
        }, h)

        # 3. Verify balance updated
        acct2 = get(f"/accounts/{acct['id']}", h).json()
        assert acct2["balance"] == 85000

        # 4. Verify transactions appear in insights
        r = get("/insights/spending-by-category", h, params={"month": 4, "year": 2024})
        data = r.json()
        entry = next(d for d in data if d["category_id"] == cat["id"])
        assert entry["amount"] == 15000  # 8000 + 7000

        # 5. Create budget and verify sync transactions count
        budget = post("/budgets", {"category_id": cat["id"], "month": 4, "year": 2024, "amount": 20000}, h).json()
        b = get(f"/budgets/{budget['id']}", h).json()
        assert b["actual"] == 15000
        assert b["remaining"] == 5000
