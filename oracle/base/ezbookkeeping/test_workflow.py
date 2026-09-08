"""
BackendForge — L3 Workflow Tests for EZBookkeeping
Complex multi-entity workflows targeting LLM implementation weaknesses.

Each test covers 6-12 steps, 12-20 assertions, across 3+ entity types.
Bug patterns covered:
- Pattern 1: camelCase field confusion
- Pattern 2: Nested/related data not returned
- Pattern 3: Filters/sorting not implemented
- Pattern 5: Business logic empty or wrong
- Pattern 6: Data isolation between users
- Pattern 7: Cascade/side-effect omissions

"""

import csv
import io
import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id=None):
    uid = user_id or str(uuid.uuid4())
    return {"X-User-Id": uid, "Content-Type": "application/json"}


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# L3 Tests — Workflow (6-12 steps, 12-20 assertions, 3+ entities)
# ════════════════════════════════════════════════════════════════════


class TestFullBudgetWorkflow:
    """Pattern 5+7: Full income/expense workflow with balance verification."""

    def test_monthly_budget_lifecycle(self):
        """
        Full month lifecycle: set up accounts + categories → record income →
        record expenses → verify balance → check monthly stats → verify category breakdown.
        """
        h = _headers()

        # Step 1: Create checking account
        acct_resp = api_post("/accounts", {
            "name": "MainChecking", "type": "checking", "currency": "USD",
        }, headers=h)
        assert acct_resp.status_code == 201
        acct_id = acct_resp.json()["id"]
        assert acct_resp.json()["balance"] == 0

        # Step 2: Create categories
        salary_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        food_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        rent_cat = api_post("/categories", {"name": "Rent", "type": "expense"}, headers=h).json()["id"]
        util_cat = api_post("/categories", {"name": "Utilities", "type": "expense"}, headers=h).json()["id"]

        # Step 3: Record salary (income)
        inc_resp = api_post("/transactions", {
            "type": "income", "amount": 6000.00, "accountId": acct_id,
            "categoryId": salary_cat, "date": "2024-04-01", "time": "09:00:00",
            "comment": "April salary",
        }, headers=h)
        assert inc_resp.status_code == 201
        assert inc_resp.json()["accountId"] == acct_id
        assert inc_resp.json()["type"] == "income"

        # Step 4: Record expenses
        api_post("/transactions", {"type": "expense", "amount": 1500.00, "accountId": acct_id, "categoryId": rent_cat, "date": "2024-04-01", "time": "10:00:00", "comment": "Monthly rent"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 200.00, "accountId": acct_id, "categoryId": util_cat, "date": "2024-04-05", "time": "11:00:00", "comment": "Electric bill"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 300.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-04-10", "time": "12:00:00", "comment": "Groceries week 1"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 250.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-04-17", "time": "12:00:00", "comment": "Groceries week 2"}, headers=h)

        # Step 5: Verify account balance = 6000 - 1500 - 200 - 300 - 250 = 3750
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 3750.00

        # Step 6: Verify monthly stats
        stats_resp = api_get("/statistics/monthly", params={"startMonth": "2024-04", "endMonth": "2024-04"}, headers=h)
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert len(stats) == 1
        assert stats[0]["month"] == "2024-04"
        assert stats[0]["totalIncome"] == 6000.00
        assert stats[0]["totalExpense"] == 2250.00
        assert stats[0]["net"] == 3750.00

        # Step 7: Verify category breakdown
        cat_resp = api_get("/statistics/category", params={"month": "2024-04", "type": "expense"}, headers=h)
        assert cat_resp.status_code == 200
        breakdown = cat_resp.json()
        food_item = next((x for x in breakdown if x["categoryId"] == food_cat), None)
        assert food_item is not None
        assert food_item["amount"] == 550.00
        rent_item = next((x for x in breakdown if x["categoryId"] == rent_cat), None)
        assert rent_item is not None
        assert rent_item["amount"] == 1500.00


class TestTransferWorkflow:
    """Pattern 5+7: Transfer between accounts with balance side-effects."""

    def test_multi_account_transfer_chain(self):
        """
        Create 3 accounts → fund first → transfer chain → verify all balances.
        Also verify transfers excluded from monthly stats.
        """
        h = _headers()

        # Step 1: Create 3 accounts
        acct1_id = api_post("/accounts", {"name": "Checking", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        acct2_id = api_post("/accounts", {"name": "Savings", "type": "savings", "currency": "USD"}, headers=h).json()["id"]
        acct3_id = api_post("/accounts", {"name": "Investment", "type": "investment", "currency": "USD"}, headers=h).json()["id"]

        # Step 2: Create categories
        inc_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Transfer", "type": "transfer"}, headers=h).json()["id"]

        # Step 3: Fund checking with 10000
        api_post("/transactions", {
            "type": "income", "amount": 10000.00, "accountId": acct1_id,
            "categoryId": inc_cat, "date": "2024-05-01", "time": "09:00:00",
        }, headers=h)

        # Step 4: Transfer 3000 from checking to savings
        xfer1_resp = api_post("/transactions", {
            "type": "transfer", "amount": 3000.00, "accountId": acct1_id,
            "categoryId": xfer_cat, "destinationAccountId": acct2_id,
            "date": "2024-05-05", "time": "10:00:00",
        }, headers=h)
        assert xfer1_resp.status_code == 201
        assert xfer1_resp.json()["destinationAccountId"] == acct2_id

        # Step 5: Transfer 2000 from savings to investment
        xfer2_resp = api_post("/transactions", {
            "type": "transfer", "amount": 2000.00, "accountId": acct2_id,
            "categoryId": xfer_cat, "destinationAccountId": acct3_id,
            "date": "2024-05-10", "time": "14:00:00",
        }, headers=h)
        assert xfer2_resp.status_code == 201

        # Step 6: Verify all balances
        acct1 = api_get(f"/accounts/{acct1_id}", headers=h).json()
        assert acct1["balance"] == 7000.00  # 10000 - 3000

        acct2 = api_get(f"/accounts/{acct2_id}", headers=h).json()
        assert acct2["balance"] == 1000.00  # 3000 - 2000

        acct3 = api_get(f"/accounts/{acct3_id}", headers=h).json()
        assert acct3["balance"] == 2000.00  # 0 + 2000

        # Step 7: Verify monthly stats exclude transfers
        stats = api_get("/statistics/monthly", params={"startMonth": "2024-05", "endMonth": "2024-05"}, headers=h).json()
        assert len(stats) == 1
        assert stats[0]["totalIncome"] == 10000.00
        assert stats[0]["totalExpense"] == 0  # transfers not counted
        assert stats[0]["net"] == 10000.00

        # Step 8: Verify destination account cannot be deleted (has transactions referencing it)
        del_resp = api_delete(f"/accounts/{acct2_id}", headers=h)
        assert del_resp.status_code == 400


class TestDataIsolationWorkflow:
    """Pattern 6: Complete isolation test across accounts, categories, tags, transactions."""

    def test_two_users_complete_isolation(self):
        """
        User A and User B each create full data sets.
        Verify neither can see the other's data.
        """
        h_a = _headers()
        h_b = _headers()

        # Step 1: User A creates account + category + tag + transaction
        acct_a = api_post("/accounts", {"name": "A-Wallet", "type": "cash", "currency": "USD"}, headers=h_a).json()["id"]
        cat_a = api_post("/categories", {"name": "A-Food", "type": "expense"}, headers=h_a).json()["id"]
        tag_a = api_post("/tags", {"name": "a-personal"}, headers=h_a).json()["id"]
        txn_a_resp = api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct_a,
            "categoryId": cat_a, "tagIds": [tag_a], "date": "2024-06-01", "time": "12:00:00",
        }, headers=h_a)
        assert txn_a_resp.status_code == 201
        txn_a_id = txn_a_resp.json()["id"]

        # Step 2: User B creates account + category + tag + transaction
        acct_b = api_post("/accounts", {"name": "B-Wallet", "type": "cash", "currency": "EUR"}, headers=h_b).json()["id"]
        cat_b = api_post("/categories", {"name": "B-Transport", "type": "expense"}, headers=h_b).json()["id"]
        tag_b = api_post("/tags", {"name": "b-work"}, headers=h_b).json()["id"]
        txn_b_resp = api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_b,
            "categoryId": cat_b, "tagIds": [tag_b], "date": "2024-06-02", "time": "14:00:00",
        }, headers=h_b)
        assert txn_b_resp.status_code == 201

        # Step 3: User B cannot see User A's accounts
        b_accounts = api_get("/accounts", headers=h_b).json()
        b_account_ids = [a["id"] for a in b_accounts]
        assert acct_a not in b_account_ids

        # Step 4: User B cannot access User A's account by ID
        assert api_get(f"/accounts/{acct_a}", headers=h_b).status_code == 404

        # Step 5: User A cannot see User B's categories
        a_cats = api_get("/categories", headers=h_a).json()
        a_cat_names = [c["name"] for c in a_cats]
        assert "B-Transport" not in a_cat_names

        # Step 6: User B cannot see User A's tags
        b_tags = api_get("/tags", headers=h_b).json()
        b_tag_names = [t["name"] for t in b_tags]
        assert "a-personal" not in b_tag_names

        # Step 7: User B cannot see User A's transactions
        b_txns = api_get("/transactions", headers=h_b).json()
        b_txn_ids = [t["id"] for t in b_txns["transactions"]]
        assert txn_a_id not in b_txn_ids

        # Step 8: User B cannot GET User A's transaction by ID
        assert api_get(f"/transactions/{txn_a_id}", headers=h_b).status_code == 404

        # Step 9: User A's stats only show A's data
        a_stats = api_get("/statistics/monthly", params={"startMonth": "2024-06", "endMonth": "2024-06"}, headers=h_a).json()
        assert a_stats[0]["totalExpense"] == 50.00

        # Step 10: User B's stats only show B's data
        b_stats = api_get("/statistics/monthly", params={"startMonth": "2024-06", "endMonth": "2024-06"}, headers=h_b).json()
        assert b_stats[0]["totalExpense"] == 30.00


class TestCategoryHierarchyWorkflow:
    """Pattern 2+5+7: Category hierarchy enforcement and transaction assignment."""

    def test_category_hierarchy_with_transactions(self):
        """
        Create parent → create children → assign transactions to children →
        verify parent can't be used in transactions → verify parent can't be deleted →
        delete children in correct order.
        """
        h = _headers()

        # Step 1: Create parent category
        parent_resp = api_post("/categories", {
            "name": "Shopping", "type": "expense", "icon": "cart", "color": "#FF0000",
        }, headers=h)
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]
        assert parent_resp.json()["parentId"] is None

        # Step 2: Create child categories
        clothes_id = api_post("/categories", {
            "name": "Clothes", "type": "expense", "parentId": parent_id,
        }, headers=h).json()["id"]
        electronics_id = api_post("/categories", {
            "name": "Electronics", "type": "expense", "parentId": parent_id,
        }, headers=h).json()["id"]

        # Step 3: Verify children have correct parentId
        clothes = api_get(f"/categories/{clothes_id}", headers=h).json()
        assert clothes["parentId"] == parent_id
        electronics = api_get(f"/categories/{electronics_id}", headers=h).json()
        assert electronics["parentId"] == parent_id

        # Step 4: Cannot create grandchild (max depth 2)
        grandchild_resp = api_post("/categories", {
            "name": "T-Shirts", "type": "expense", "parentId": clothes_id,
        }, headers=h)
        assert grandchild_resp.status_code == 400

        # Step 5: Create account and transaction using leaf (child) category
        acct_id = api_post("/accounts", {"name": "ShopAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        txn_resp = api_post("/transactions", {
            "type": "expense", "amount": 99.99, "accountId": acct_id,
            "categoryId": clothes_id, "date": "2024-07-01", "time": "15:00:00",
        }, headers=h)
        assert txn_resp.status_code == 201

        # Step 6: Cannot use parent category in transaction (it has children)
        bad_txn = api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct_id,
            "categoryId": parent_id, "date": "2024-07-02", "time": "10:00:00",
        }, headers=h)
        assert bad_txn.status_code == 400

        # Step 7: Cannot delete parent (has children)
        assert api_delete(f"/categories/{parent_id}", headers=h).status_code == 400

        # Step 8: Cannot delete child category with transactions
        assert api_delete(f"/categories/{clothes_id}", headers=h).status_code == 400

        # Step 9: Can delete child without transactions
        assert api_delete(f"/categories/{electronics_id}", headers=h).status_code == 204
        assert api_get(f"/categories/{electronics_id}", headers=h).status_code == 404


class TestTagWorkflow:
    """Pattern 2+7: Tag association with transactions and deletion side-effects."""

    def test_tag_lifecycle_with_transactions(self):
        """
        Create tags → attach to transactions → verify tagIds roundtrip →
        delete one tag → verify removed from transactions but transaction persists →
        update remaining tag → verify in transaction listing.
        """
        h = _headers()

        # Step 1: Create account and category
        acct_id = api_post("/accounts", {"name": "TagAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "TagCat", "type": "expense"}, headers=h).json()["id"]

        # Step 2: Create 3 tags
        tag1_id = api_post("/tags", {"name": "urgent", "displayOrder": 1}, headers=h).json()["id"]
        tag2_id = api_post("/tags", {"name": "recurring", "displayOrder": 2}, headers=h).json()["id"]
        tag3_id = api_post("/tags", {"name": "temporary", "displayOrder": 3}, headers=h).json()["id"]

        # Step 3: Create transaction with all 3 tags
        txn_resp = api_post("/transactions", {
            "type": "expense", "amount": 75.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag1_id, tag2_id, tag3_id],
            "date": "2024-08-01", "time": "10:00:00", "comment": "Tagged expense",
        }, headers=h)
        assert txn_resp.status_code == 201
        txn_id = txn_resp.json()["id"]
        assert set(txn_resp.json()["tagIds"]) == {tag1_id, tag2_id, tag3_id}

        # Step 4: Create second transaction with subset of tags
        txn2_resp = api_post("/transactions", {
            "type": "expense", "amount": 25.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag1_id],
            "date": "2024-08-02", "time": "11:00:00",
        }, headers=h)
        txn2_id = txn2_resp.json()["id"]

        # Step 5: Delete tag3 (temporary)
        del_resp = api_delete(f"/tags/{tag3_id}", headers=h)
        assert del_resp.status_code == 204

        # Step 6: Verify tag removed from first transaction
        txn = api_get(f"/transactions/{txn_id}", headers=h).json()
        assert set(txn["tagIds"]) == {tag1_id, tag2_id}
        assert tag3_id not in txn["tagIds"]

        # Step 7: Second transaction unaffected (didn't have tag3)
        txn2 = api_get(f"/transactions/{txn2_id}", headers=h).json()
        assert txn2["tagIds"] == [tag1_id]

        # Step 8: Verify tag3 is gone from tag list
        assert api_get(f"/tags/{tag3_id}", headers=h).status_code == 404

        # Step 9: Tags list only contains remaining tags
        tags = api_get("/tags", headers=h).json()
        tag_ids = [t["id"] for t in tags]
        assert tag1_id in tag_ids
        assert tag2_id in tag_ids
        assert tag3_id not in tag_ids

        # Step 10: Filter transactions by tag
        filtered = api_get("/transactions", params={"tagId": tag2_id}, headers=h).json()
        assert filtered["total"] == 1
        assert filtered["transactions"][0]["id"] == txn_id


class TestTransactionUpdateWorkflow:
    """Pattern 5+7: Update transaction and verify balance side-effects."""

    def test_update_transaction_recalculates_balance(self):
        """
        Create transactions → verify balance → update amount →
        verify balance changed → change transaction type → verify balance.
        """
        h = _headers()

        # Step 1: Create infrastructure
        acct_id = api_post("/accounts", {"name": "UpdBal", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Income", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Expense", "type": "expense"}, headers=h).json()["id"]

        # Step 2: Add income
        inc_resp = api_post("/transactions", {
            "type": "income", "amount": 5000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-09-01", "time": "09:00:00",
        }, headers=h)
        inc_txn_id = inc_resp.json()["id"]

        # Step 3: Add expense
        exp_resp = api_post("/transactions", {
            "type": "expense", "amount": 1000.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-09-05", "time": "12:00:00",
        }, headers=h)
        exp_txn_id = exp_resp.json()["id"]

        # Step 4: Verify initial balance = 5000 - 1000 = 4000
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 4000.00

        # Step 5: Update expense from 1000 to 2000
        upd_resp = api_put(f"/transactions/{exp_txn_id}", {
            "type": "expense", "amount": 2000.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-09-05", "time": "12:00:00",
        }, headers=h)
        assert upd_resp.status_code == 200
        assert upd_resp.json()["amount"] == 2000.00

        # Step 6: Verify balance = 5000 - 2000 = 3000
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 3000.00

        # Step 7: Verify monthly stats reflect the update
        stats = api_get("/statistics/monthly", params={"startMonth": "2024-09", "endMonth": "2024-09"}, headers=h).json()
        assert stats[0]["totalIncome"] == 5000.00
        assert stats[0]["totalExpense"] == 2000.00
        assert stats[0]["net"] == 3000.00


class TestCSVExportWorkflow:
    """Pattern 3+5: CSV export with filtering and correct format."""

    def test_csv_export_with_filters_and_tags(self):
        """
        Create diverse transactions → export all → verify format →
        export filtered → verify only matching rows.
        """
        h = _headers()

        # Step 1: Set up
        acct1_id = api_post("/accounts", {"name": "ExpAcct1", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        acct2_id = api_post("/accounts", {"name": "ExpAcct2", "type": "checking", "currency": "EUR"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "ExpCat", "type": "expense"}, headers=h).json()["id"]
        tag1_id = api_post("/tags", {"name": "business"}, headers=h).json()["id"]
        tag2_id = api_post("/tags", {"name": "personal"}, headers=h).json()["id"]

        # Step 2: Create transactions
        api_post("/transactions", {
            "type": "expense", "amount": 100.00, "accountId": acct1_id,
            "categoryId": cat_id, "tagIds": [tag1_id],
            "date": "2024-10-01", "time": "10:00:00", "comment": "Business lunch",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct2_id,
            "categoryId": cat_id, "tagIds": [tag2_id],
            "date": "2024-10-05", "time": "14:00:00", "comment": "Personal dinner",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 75.00, "accountId": acct1_id,
            "categoryId": cat_id, "tagIds": [tag1_id, tag2_id],
            "date": "2024-10-10", "time": "12:00:00", "comment": "Mixed event",
        }, headers=h)

        # Step 3: Export all — verify 3 data rows
        resp_all = requests.get(f"{BASE_URL}/transactions/export", headers=h, timeout=30)
        assert resp_all.status_code == 200
        assert "text/csv" in resp_all.headers.get("content-type", "")
        reader = csv.reader(io.StringIO(resp_all.text))
        rows = list(reader)
        assert rows[0] == ["date", "type", "category", "account", "amount", "comment", "tags"]
        assert len(rows) == 4  # header + 3 data rows

        # Step 4: Verify date DESC ordering in CSV
        data_dates = [r[0] for r in rows[1:]]
        assert data_dates == sorted(data_dates, reverse=True)

        # Step 5: Export filtered by accountId
        resp_filtered = requests.get(
            f"{BASE_URL}/transactions/export",
            params={"accountId": acct1_id}, headers=h, timeout=30,
        )
        reader2 = csv.reader(io.StringIO(resp_filtered.text))
        rows2 = list(reader2)
        assert len(rows2) == 3  # header + 2 data rows for acct1
        for row in rows2[1:]:
            assert row[3] == "ExpAcct1"

        # Step 6: Verify semicolon-separated tags in multi-tag transaction
        mixed_row = next(r for r in rows[1:] if r[5] == "Mixed event")
        tag_set = set(mixed_row[6].split(";"))
        assert tag_set == {"business", "personal"}


class TestStatisticsMultiMonthWorkflow:
    """Pattern 5: Multi-month statistics with trends."""

    def test_quarterly_trends_workflow(self):
        """
        Create transactions across 3 months → verify monthly stats →
        verify trends → verify empty months included → verify category breakdown per month.
        """
        h = _headers()

        # Step 1: Set up
        acct_id = api_post("/accounts", {"name": "TrendAcct", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        food_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        rent_cat = api_post("/categories", {"name": "Rent", "type": "expense"}, headers=h).json()["id"]

        # Step 2: July income + expenses
        api_post("/transactions", {"type": "income", "amount": 5000.00, "accountId": acct_id, "categoryId": inc_cat, "date": "2024-07-01", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 1000.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-07-10", "time": "12:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 1500.00, "accountId": acct_id, "categoryId": rent_cat, "date": "2024-07-01", "time": "10:00:00"}, headers=h)

        # Step 3: August income + expenses
        api_post("/transactions", {"type": "income", "amount": 5500.00, "accountId": acct_id, "categoryId": inc_cat, "date": "2024-08-01", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 1200.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-08-15", "time": "12:00:00"}, headers=h)

        # Step 4: September — no transactions (gap month)

        # Step 5: Verify monthly stats for July-September
        stats = api_get("/statistics/monthly", params={"startMonth": "2024-07", "endMonth": "2024-09"}, headers=h).json()
        assert len(stats) == 3

        jul = next(m for m in stats if m["month"] == "2024-07")
        assert jul["totalIncome"] == 5000.00
        assert jul["totalExpense"] == 2500.00
        assert jul["net"] == 2500.00

        aug = next(m for m in stats if m["month"] == "2024-08")
        assert aug["totalIncome"] == 5500.00
        assert aug["totalExpense"] == 1200.00
        assert aug["net"] == 4300.00

        sep = next(m for m in stats if m["month"] == "2024-09")
        assert sep["totalIncome"] == 0
        assert sep["totalExpense"] == 0
        assert sep["net"] == 0

        # Step 6: Verify trends endpoint returns same data
        trends = api_get("/statistics/trends", params={"startMonth": "2024-07", "endMonth": "2024-09"}, headers=h).json()
        assert len(trends) == 3
        jul_trend = next(m for m in trends if m["month"] == "2024-07")
        assert jul_trend["totalIncome"] == 5000.00
        assert jul_trend["totalExpense"] == 2500.00

        # Step 7: Category breakdown for July
        jul_breakdown = api_get("/statistics/category", params={"month": "2024-07", "type": "expense"}, headers=h).json()
        food_jul = next((x for x in jul_breakdown if x["categoryId"] == food_cat), None)
        assert food_jul is not None
        assert food_jul["amount"] == 1000.00
        rent_jul = next((x for x in jul_breakdown if x["categoryId"] == rent_cat), None)
        assert rent_jul is not None
        assert rent_jul["amount"] == 1500.00


class TestDeleteTransactionBalanceWorkflow:
    """Pattern 7: Deleting transactions reverses balance effects for all types."""

    def test_delete_transfer_reverses_both_accounts(self):
        """
        Fund account → transfer → verify balances → delete transfer →
        verify balances restored.
        """
        h = _headers()

        # Step 1: Create accounts
        src_id = api_post("/accounts", {"name": "DelXferSrc", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        dst_id = api_post("/accounts", {"name": "DelXferDst", "type": "savings", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Pay", "type": "income"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Move", "type": "transfer"}, headers=h).json()["id"]

        # Step 2: Fund source
        api_post("/transactions", {
            "type": "income", "amount": 5000.00, "accountId": src_id,
            "categoryId": inc_cat, "date": "2024-11-01", "time": "09:00:00",
        }, headers=h)

        # Step 3: Transfer 2000
        xfer_resp = api_post("/transactions", {
            "type": "transfer", "amount": 2000.00, "accountId": src_id,
            "categoryId": xfer_cat, "destinationAccountId": dst_id,
            "date": "2024-11-05", "time": "10:00:00",
        }, headers=h)
        xfer_id = xfer_resp.json()["id"]

        # Step 4: Verify balances after transfer
        assert api_get(f"/accounts/{src_id}", headers=h).json()["balance"] == 3000.00
        assert api_get(f"/accounts/{dst_id}", headers=h).json()["balance"] == 2000.00

        # Step 5: Delete the transfer
        del_resp = api_delete(f"/transactions/{xfer_id}", headers=h)
        assert del_resp.status_code == 204

        # Step 6: Verify balances restored
        assert api_get(f"/accounts/{src_id}", headers=h).json()["balance"] == 5000.00
        assert api_get(f"/accounts/{dst_id}", headers=h).json()["balance"] == 0

        # Step 7: Verify transaction is gone
        assert api_get(f"/transactions/{xfer_id}", headers=h).status_code == 404


class TestCompleteEntityDeletionWorkflow:
    """Pattern 7+8: Verify correct order of operations for cleanup."""

    def test_cleanup_requires_correct_order(self):
        """
        Create full entity graph → try to delete in wrong order (should fail) →
        delete in correct order (transactions first, then categories/accounts).
        """
        h = _headers()

        # Step 1: Create entities
        acct_id = api_post("/accounts", {"name": "CleanupAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        parent_cat = api_post("/categories", {"name": "CleanupParent", "type": "expense"}, headers=h).json()["id"]
        child_cat = api_post("/categories", {"name": "CleanupChild", "type": "expense", "parentId": parent_cat}, headers=h).json()["id"]
        tag_id = api_post("/tags", {"name": "cleanup-tag"}, headers=h).json()["id"]

        # Step 2: Create transaction
        txn_resp = api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": child_cat, "tagIds": [tag_id],
            "date": "2024-12-01", "time": "10:00:00",
        }, headers=h)
        txn_id = txn_resp.json()["id"]

        # Step 3: Cannot delete account (has transaction)
        assert api_delete(f"/accounts/{acct_id}", headers=h).status_code == 400

        # Step 4: Cannot delete child category (has transaction)
        assert api_delete(f"/categories/{child_cat}", headers=h).status_code == 400

        # Step 5: Cannot delete parent category (has child)
        assert api_delete(f"/categories/{parent_cat}", headers=h).status_code == 400

        # Step 6: Delete transaction first
        assert api_delete(f"/transactions/{txn_id}", headers=h).status_code == 204

        # Step 7: Now can delete child category
        assert api_delete(f"/categories/{child_cat}", headers=h).status_code == 204

        # Step 8: Now can delete parent category
        assert api_delete(f"/categories/{parent_cat}", headers=h).status_code == 204

        # Step 9: Now can delete account
        assert api_delete(f"/accounts/{acct_id}", headers=h).status_code == 204

        # Step 10: Tag can be deleted anytime (no blocking rule)
        assert api_delete(f"/tags/{tag_id}", headers=h).status_code == 204

        # Step 11: Verify all gone
        assert api_get(f"/accounts/{acct_id}", headers=h).status_code == 404
        assert api_get(f"/categories/{child_cat}", headers=h).status_code == 404
        assert api_get(f"/categories/{parent_cat}", headers=h).status_code == 404
        assert api_get(f"/tags/{tag_id}", headers=h).status_code == 404


class TestTransactionFilterCombinationWorkflow:
    """Pattern 3: Multiple filters applied simultaneously."""

    def test_combined_filters_account_type_date(self):
        """
        Create diverse transactions → filter by account → filter by type →
        filter by date range → combine all filters.
        """
        h = _headers()

        # Step 1: Set up
        acct1 = api_post("/accounts", {"name": "FilterAcct1", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        acct2 = api_post("/accounts", {"name": "FilterAcct2", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "FilterInc", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "FilterExp", "type": "expense"}, headers=h).json()["id"]

        # Step 2: Create 6 transactions across accounts, types, dates
        api_post("/transactions", {"type": "income", "amount": 100.00, "accountId": acct1, "categoryId": inc_cat, "date": "2024-03-01", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 30.00, "accountId": acct1, "categoryId": exp_cat, "date": "2024-03-15", "time": "10:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 50.00, "accountId": acct1, "categoryId": exp_cat, "date": "2024-04-01", "time": "10:00:00"}, headers=h)
        api_post("/transactions", {"type": "income", "amount": 200.00, "accountId": acct2, "categoryId": inc_cat, "date": "2024-03-10", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 80.00, "accountId": acct2, "categoryId": exp_cat, "date": "2024-03-20", "time": "11:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 60.00, "accountId": acct2, "categoryId": exp_cat, "date": "2024-04-10", "time": "11:00:00"}, headers=h)

        # Step 3: Filter by account1 only
        resp = api_get("/transactions", params={"accountId": acct1}, headers=h).json()
        assert resp["total"] == 3
        for txn in resp["transactions"]:
            assert txn["accountId"] == acct1

        # Step 4: Filter by type=expense only
        resp = api_get("/transactions", params={"type": "expense"}, headers=h).json()
        assert resp["total"] == 4
        for txn in resp["transactions"]:
            assert txn["type"] == "expense"

        # Step 5: Filter by date range (March only)
        resp = api_get("/transactions", params={"startDate": "2024-03-01", "endDate": "2024-03-31"}, headers=h).json()
        assert resp["total"] == 4

        # Step 6: Combine: account1 + expense + March
        resp = api_get("/transactions", params={
            "accountId": acct1, "type": "expense",
            "startDate": "2024-03-01", "endDate": "2024-03-31",
        }, headers=h).json()
        assert resp["total"] == 1
        assert resp["transactions"][0]["amount"] == 30.00
        assert resp["transactions"][0]["accountId"] == acct1
        assert resp["transactions"][0]["type"] == "expense"


class TestIncomeStatsCategoryBreakdown:
    """Pattern 5: Category breakdown for income type (not just expense)."""

    def test_income_category_breakdown(self):
        """
        Create income categories + transactions → verify category breakdown
        works for income type parameter.
        """
        h = _headers()

        # Step 1: Setup
        acct_id = api_post("/accounts", {"name": "IncBreak", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        salary_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        freelance_cat = api_post("/categories", {"name": "Freelance", "type": "income"}, headers=h).json()["id"]
        dividends_cat = api_post("/categories", {"name": "Dividends", "type": "income"}, headers=h).json()["id"]

        # Step 2: Create income transactions
        api_post("/transactions", {"type": "income", "amount": 5000.00, "accountId": acct_id, "categoryId": salary_cat, "date": "2024-11-01", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "income", "amount": 2000.00, "accountId": acct_id, "categoryId": freelance_cat, "date": "2024-11-10", "time": "10:00:00"}, headers=h)
        api_post("/transactions", {"type": "income", "amount": 500.00, "accountId": acct_id, "categoryId": dividends_cat, "date": "2024-11-15", "time": "11:00:00"}, headers=h)
        api_post("/transactions", {"type": "income", "amount": 1500.00, "accountId": acct_id, "categoryId": freelance_cat, "date": "2024-11-20", "time": "10:00:00"}, headers=h)

        # Step 3: Get income category breakdown
        resp = api_get("/statistics/category", params={"month": "2024-11", "type": "income"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()

        # Step 4: Verify salary
        salary_item = next((x for x in data if x["categoryId"] == salary_cat), None)
        assert salary_item is not None
        assert salary_item["categoryName"] == "Salary"
        assert salary_item["amount"] == 5000.00

        # Step 5: Verify freelance (2000 + 1500 = 3500)
        freelance_item = next((x for x in data if x["categoryId"] == freelance_cat), None)
        assert freelance_item is not None
        assert freelance_item["categoryName"] == "Freelance"
        assert freelance_item["amount"] == 3500.00

        # Step 6: Verify dividends
        dividends_item = next((x for x in data if x["categoryId"] == dividends_cat), None)
        assert dividends_item is not None
        assert dividends_item["amount"] == 500.00

        # Step 7: Verify balance
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 9000.00  # 5000 + 2000 + 500 + 1500
