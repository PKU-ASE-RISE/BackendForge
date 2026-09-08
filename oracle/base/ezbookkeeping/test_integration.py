"""
BackendForge — L2 Integration Tests for EZBookkeeping
Adversarial tests targeting common LLM implementation bugs.

Bug patterns covered:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned correctly
- Pattern 3: Parameters declared but not implemented (filters, pagination, sorting)
- Pattern 4: Wrong status codes (200 vs 201/204)
- Pattern 5: Business logic exists but behavior is empty/wrong
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
# L2 Tests — Integration (3-5 steps, 8-12 assertions each)
# ════════════════════════════════════════════════════════════════════


class TestAccountCamelCaseAndFields:
    """Pattern 1+2: Verify camelCase field names and all required fields returned."""

    def test_account_create_returns_all_camelcase_fields(self):
        """Verify account creation returns 201 with all camelCase fields."""
        h = _headers()
        resp = api_post("/accounts", {
            "name": "TestWallet",
            "type": "cash",
            "currency": "USD",
            "icon": "wallet-icon",
            "displayOrder": 3,
        }, headers=h)

        # Status code check (Pattern 4)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        data = resp.json()

        # All required camelCase fields must exist (Pattern 1)
        assert "id" in data
        assert "name" in data
        assert "type" in data
        assert "currency" in data
        assert "icon" in data
        assert "balance" in data
        assert "displayOrder" in data
        assert "createdAt" in data
        assert "updatedAt" in data

        # Verify values roundtrip correctly
        assert data["name"] == "TestWallet"
        assert data["type"] == "cash"
        assert data["currency"] == "USD"
        assert data["icon"] == "wallet-icon"
        assert data["displayOrder"] == 3
        assert data["balance"] == 0  # computed, starts at 0

        # Verify snake_case alternatives do NOT exist (Pattern 1)
        assert "display_order" not in data
        assert "created_at" not in data
        assert "updated_at" not in data

    def test_account_get_roundtrip_preserves_all_fields(self):
        """Create account then GET it — all fields must match."""
        h = _headers()
        create_resp = api_post("/accounts", {
            "name": "RoundtripAcct",
            "type": "savings",
            "currency": "EUR",
            "icon": "piggy",
            "displayOrder": 7,
        }, headers=h)
        assert create_resp.status_code == 201
        created = create_resp.json()
        acct_id = created["id"]

        # GET the account back
        get_resp = api_get(f"/accounts/{acct_id}", headers=h)
        assert get_resp.status_code == 200
        fetched = get_resp.json()

        # All fields must match what was created
        assert fetched["id"] == acct_id
        assert fetched["name"] == "RoundtripAcct"
        assert fetched["type"] == "savings"
        assert fetched["currency"] == "EUR"
        assert fetched["icon"] == "piggy"
        assert fetched["displayOrder"] == 7
        assert fetched["balance"] == 0
        assert fetched["createdAt"] == created["createdAt"]

    def test_account_update_returns_updated_fields(self):
        """PUT updates name/type/currency and returns updated values."""
        h = _headers()
        create_resp = api_post("/accounts", {
            "name": "BeforeUpdate",
            "type": "cash",
            "currency": "USD",
        }, headers=h)
        acct_id = create_resp.json()["id"]

        update_resp = api_put(f"/accounts/{acct_id}", {
            "name": "AfterUpdate",
            "type": "credit_card",
            "currency": "GBP",
            "icon": "card",
            "displayOrder": 10,
        }, headers=h)
        assert update_resp.status_code == 200
        updated = update_resp.json()

        assert updated["id"] == acct_id
        assert updated["name"] == "AfterUpdate"
        assert updated["type"] == "credit_card"
        assert updated["currency"] == "GBP"
        assert updated["icon"] == "card"
        assert updated["displayOrder"] == 10
        assert "balance" in updated
        assert "createdAt" in updated
        assert "updatedAt" in updated


class TestCategoryCamelCaseAndHierarchy:
    """Pattern 1+2: camelCase fields for categories + parentId relationship."""

    def test_category_create_returns_camelcase_fields(self):
        """Verify category creation returns all camelCase fields including parentId."""
        h = _headers()
        resp = api_post("/categories", {
            "name": "Groceries",
            "type": "expense",
            "icon": "cart",
            "color": "#FF0000",
            "displayOrder": 2,
        }, headers=h)

        assert resp.status_code == 201
        data = resp.json()

        # Required camelCase fields
        assert "id" in data
        assert "name" in data
        assert "type" in data
        assert "icon" in data
        assert "color" in data
        assert "parentId" in data
        assert "displayOrder" in data
        assert "createdAt" in data
        assert "updatedAt" in data

        # Values
        assert data["name"] == "Groceries"
        assert data["type"] == "expense"
        assert data["icon"] == "cart"
        assert data["color"] == "#FF0000"
        assert data["parentId"] is None
        assert data["displayOrder"] == 2

        # snake_case must NOT exist
        assert "parent_id" not in data
        assert "display_order" not in data
        assert "created_at" not in data

    def test_child_category_parentid_returned_correctly(self):
        """Create parent then child — verify parentId is set correctly."""
        h = _headers()
        # Create parent
        parent_resp = api_post("/categories", {
            "name": "Food",
            "type": "expense",
            "icon": "food",
            "color": "#00FF00",
        }, headers=h)
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        # Create child
        child_resp = api_post("/categories", {
            "name": "Fast Food",
            "type": "expense",
            "icon": "burger",
            "color": "#FFAA00",
            "parentId": parent_id,
        }, headers=h)
        assert child_resp.status_code == 201
        child = child_resp.json()

        assert child["parentId"] == parent_id
        assert child["type"] == "expense"
        assert child["name"] == "Fast Food"

        # GET the child and verify parentId persisted
        get_resp = api_get(f"/categories/{child['id']}", headers=h)
        assert get_resp.status_code == 200
        assert get_resp.json()["parentId"] == parent_id

    def test_category_type_immutable_on_update(self):
        """Pattern 5: Category type cannot be changed via update."""
        h = _headers()
        create_resp = api_post("/categories", {
            "name": "ImmutableType",
            "type": "income",
        }, headers=h)
        assert create_resp.status_code == 201
        cat_id = create_resp.json()["id"]

        # Update without passing type — type should remain income
        update_resp = api_put(f"/categories/{cat_id}", {
            "name": "ImmutableTypeRenamed",
            "icon": "new-icon",
            "color": "#AABBCC",
        }, headers=h)
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["type"] == "income"
        assert updated["name"] == "ImmutableTypeRenamed"


class TestTransactionCamelCaseAndFields:
    """Pattern 1+2: Transaction camelCase fields including tagIds, accountId, categoryId."""

    def test_transaction_create_returns_all_camelcase_fields(self):
        """Verify transaction has accountId, categoryId, tagIds, destinationAccountId."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "TxnAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "TxnCat", "type": "expense"}, headers=h).json()["id"]
        tag_id = api_post("/tags", {"name": "txn-tag"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 55.75,
            "accountId": acct_id,
            "categoryId": cat_id,
            "tagIds": [tag_id],
            "date": "2024-05-01",
            "time": "14:30:00",
            "comment": "Test purchase",
        }, headers=h)

        assert resp.status_code == 201
        txn = resp.json()

        # camelCase fields must exist
        assert "id" in txn
        assert "type" in txn
        assert "amount" in txn
        assert "accountId" in txn
        assert "categoryId" in txn
        assert "tagIds" in txn
        assert "date" in txn
        assert "time" in txn
        assert "comment" in txn
        assert "destinationAccountId" in txn
        assert "createdAt" in txn
        assert "updatedAt" in txn

        # Values
        assert txn["type"] == "expense"
        assert txn["amount"] == 55.75
        assert txn["accountId"] == acct_id
        assert txn["categoryId"] == cat_id
        assert txn["tagIds"] == [tag_id]
        assert txn["date"] == "2024-05-01"
        assert txn["time"] == "14:30:00"
        assert txn["comment"] == "Test purchase"
        assert txn["destinationAccountId"] is None

        # snake_case must NOT exist
        assert "account_id" not in txn
        assert "category_id" not in txn
        assert "tag_ids" not in txn
        assert "destination_account_id" not in txn
        assert "created_at" not in txn

    def test_transaction_with_multiple_tags_roundtrip(self):
        """Create transaction with multiple tags — GET it back — tagIds preserved."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "TagRoundtrip", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "TagRTCat", "type": "expense"}, headers=h).json()["id"]
        tag1_id = api_post("/tags", {"name": "tag-rt-1"}, headers=h).json()["id"]
        tag2_id = api_post("/tags", {"name": "tag-rt-2"}, headers=h).json()["id"]
        tag3_id = api_post("/tags", {"name": "tag-rt-3"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 10.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "tagIds": [tag1_id, tag2_id, tag3_id],
            "date": "2024-06-01",
            "time": "10:00:00",
        }, headers=h)
        assert resp.status_code == 201
        txn_id = resp.json()["id"]

        # GET and verify tags preserved
        get_resp = api_get(f"/transactions/{txn_id}", headers=h)
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert set(fetched["tagIds"]) == {tag1_id, tag2_id, tag3_id}
        assert fetched["accountId"] == acct_id
        assert fetched["categoryId"] == cat_id


class TestAccountBalanceComputation:
    """Pattern 5: Balance is COMPUTED from transactions, not stored directly."""

    def test_balance_reflects_multiple_transactions(self):
        """Multiple income/expense transactions — balance must be computed sum."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "BalCalc", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Bills", "type": "expense"}, headers=h).json()["id"]

        # +5000 income
        api_post("/transactions", {
            "type": "income", "amount": 5000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-01-01", "time": "09:00:00",
        }, headers=h)
        # -1200 expense
        api_post("/transactions", {
            "type": "expense", "amount": 1200.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-01-05", "time": "10:00:00",
        }, headers=h)
        # -800 expense
        api_post("/transactions", {
            "type": "expense", "amount": 800.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-01-10", "time": "11:00:00",
        }, headers=h)
        # +2000 income
        api_post("/transactions", {
            "type": "income", "amount": 2000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-01-15", "time": "09:00:00",
        }, headers=h)

        # Check balance = 5000 - 1200 - 800 + 2000 = 5000
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 5000.00

        # Also verify in list endpoint
        accounts = api_get("/accounts", headers=h).json()
        target = next(a for a in accounts if a["id"] == acct_id)
        assert target["balance"] == 5000.00

    def test_transfer_affects_both_account_balances(self):
        """Transfer debits source, credits destination."""
        h = _headers()
        src_id = api_post("/accounts", {"name": "Src", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        dst_id = api_post("/accounts", {"name": "Dst", "type": "savings", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Pay", "type": "income"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Move", "type": "transfer"}, headers=h).json()["id"]

        # Give source 3000
        api_post("/transactions", {
            "type": "income", "amount": 3000.00, "accountId": src_id,
            "categoryId": inc_cat, "date": "2024-02-01", "time": "09:00:00",
        }, headers=h)

        # Transfer 1500 from src to dst
        api_post("/transactions", {
            "type": "transfer", "amount": 1500.00, "accountId": src_id,
            "categoryId": xfer_cat, "destinationAccountId": dst_id,
            "date": "2024-02-05", "time": "10:00:00",
        }, headers=h)

        src = api_get(f"/accounts/{src_id}", headers=h).json()
        dst = api_get(f"/accounts/{dst_id}", headers=h).json()
        assert src["balance"] == 1500.00
        assert dst["balance"] == 1500.00

    def test_delete_transaction_reverses_balance(self):
        """Deleting a transaction should reverse its effect on balance."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "DelBal", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Inc", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        # Add income
        api_post("/transactions", {
            "type": "income", "amount": 1000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)

        # Add expense
        exp_resp = api_post("/transactions", {
            "type": "expense", "amount": 300.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-03-05", "time": "10:00:00",
        }, headers=h)
        exp_id = exp_resp.json()["id"]

        # Balance = 700
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 700.00

        # Delete expense
        del_resp = api_delete(f"/transactions/{exp_id}", headers=h)
        assert del_resp.status_code == 204

        # Balance should be back to 1000
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 1000.00


class TestTransactionFiltersAndPagination:
    """Pattern 3: Verify filters and pagination actually work."""

    def test_pagination_offset_and_limit(self):
        """Verify offset/limit return correct slices and total count."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "PagAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "PagCat", "type": "expense"}, headers=h).json()["id"]

        # Create 7 transactions
        for i in range(7):
            api_post("/transactions", {
                "type": "expense", "amount": 10.00 + i, "accountId": acct_id,
                "categoryId": cat_id, "date": f"2024-04-{10+i:02d}", "time": "12:00:00",
            }, headers=h)

        # Page 1: offset=0, limit=3
        resp1 = api_get("/transactions", params={"offset": 0, "limit": 3}, headers=h)
        assert resp1.status_code == 200
        d1 = resp1.json()
        assert d1["total"] == 7
        assert d1["offset"] == 0
        assert d1["limit"] == 3
        assert len(d1["transactions"]) == 3

        # Page 2: offset=3, limit=3
        resp2 = api_get("/transactions", params={"offset": 3, "limit": 3}, headers=h)
        d2 = resp2.json()
        assert d2["total"] == 7
        assert d2["offset"] == 3
        assert len(d2["transactions"]) == 3

        # Page 3: offset=6, limit=3 — only 1 remaining
        resp3 = api_get("/transactions", params={"offset": 6, "limit": 3}, headers=h)
        d3 = resp3.json()
        assert d3["total"] == 7
        assert len(d3["transactions"]) == 1

        # All transaction IDs should be unique across pages
        all_ids = [t["id"] for t in d1["transactions"] + d2["transactions"] + d3["transactions"]]
        assert len(set(all_ids)) == 7

    def test_filter_by_category_id(self):
        """Verify categoryId filter actually filters results."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "CatFilter", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat1 = api_post("/categories", {"name": "Cat1", "type": "expense"}, headers=h).json()["id"]
        cat2 = api_post("/categories", {"name": "Cat2", "type": "expense"}, headers=h).json()["id"]

        # 3 transactions with cat1
        for i in range(3):
            api_post("/transactions", {
                "type": "expense", "amount": 10.00, "accountId": acct_id,
                "categoryId": cat1, "date": f"2024-05-{10+i:02d}", "time": "12:00:00",
            }, headers=h)
        # 2 transactions with cat2
        for i in range(2):
            api_post("/transactions", {
                "type": "expense", "amount": 20.00, "accountId": acct_id,
                "categoryId": cat2, "date": f"2024-05-{20+i:02d}", "time": "12:00:00",
            }, headers=h)

        resp = api_get("/transactions", params={"categoryId": cat1}, headers=h)
        data = resp.json()
        assert data["total"] == 3
        for txn in data["transactions"]:
            assert txn["categoryId"] == cat1

    def test_filter_by_date_range_inclusive(self):
        """startDate and endDate should be inclusive boundaries."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "DateRange", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "DRCat", "type": "expense"}, headers=h).json()["id"]

        dates = ["2024-03-01", "2024-03-15", "2024-03-31", "2024-04-01", "2024-04-15"]
        for d in dates:
            api_post("/transactions", {
                "type": "expense", "amount": 10.00, "accountId": acct_id,
                "categoryId": cat_id, "date": d, "time": "12:00:00",
            }, headers=h)

        # Filter March only
        resp = api_get("/transactions", params={"startDate": "2024-03-01", "endDate": "2024-03-31"}, headers=h)
        data = resp.json()
        assert data["total"] == 3
        for txn in data["transactions"]:
            assert txn["date"] >= "2024-03-01"
            assert txn["date"] <= "2024-03-31"

    def test_filter_by_type(self):
        """Type filter should return only matching transaction types."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "TypeFilt", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Inc", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "income", "amount": 100.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-06-01", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-06-02", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-06-03", "time": "11:00:00",
        }, headers=h)

        resp = api_get("/transactions", params={"type": "income"}, headers=h)
        data = resp.json()
        assert data["total"] == 1
        assert data["transactions"][0]["type"] == "income"

        resp2 = api_get("/transactions", params={"type": "expense"}, headers=h)
        data2 = resp2.json()
        assert data2["total"] == 2
        for txn in data2["transactions"]:
            assert txn["type"] == "expense"


class TestTransactionOrdering:
    """Pattern 3: Verify transactions are ordered by date DESC, then createdAt DESC."""

    def test_transactions_sorted_date_desc(self):
        """Transactions must be returned in date DESC order."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "SortAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "SortCat", "type": "expense"}, headers=h).json()["id"]

        # Create in non-chronological order
        api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-07-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-07-01", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-07-30", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 15.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-07-10", "time": "10:00:00",
        }, headers=h)

        resp = api_get("/transactions", headers=h)
        txns = resp.json()["transactions"]
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True), f"Not sorted DESC: {dates}"


class TestDisplayOrderSorting:
    """Pattern 3: Verify displayOrder sorting for accounts, categories, tags."""

    def test_accounts_sorted_by_display_order_then_created(self):
        """Accounts should be sorted by displayOrder ASC, then createdAt ASC."""
        h = _headers()
        # Create in reverse displayOrder
        api_post("/accounts", {"name": "Z-Last", "type": "cash", "currency": "USD", "displayOrder": 3}, headers=h)
        api_post("/accounts", {"name": "A-First", "type": "cash", "currency": "USD", "displayOrder": 1}, headers=h)
        api_post("/accounts", {"name": "M-Middle", "type": "cash", "currency": "USD", "displayOrder": 2}, headers=h)

        resp = api_get("/accounts", headers=h)
        accounts = resp.json()
        names = [a["name"] for a in accounts]
        assert names == ["A-First", "M-Middle", "Z-Last"]

    def test_categories_sorted_by_display_order(self):
        """Categories should be sorted by displayOrder ASC."""
        h = _headers()
        api_post("/categories", {"name": "CatC", "type": "expense", "displayOrder": 30}, headers=h)
        api_post("/categories", {"name": "CatA", "type": "expense", "displayOrder": 10}, headers=h)
        api_post("/categories", {"name": "CatB", "type": "expense", "displayOrder": 20}, headers=h)

        resp = api_get("/categories", headers=h)
        cats = resp.json()
        orders = [c["displayOrder"] for c in cats]
        assert orders == sorted(orders)

    def test_tags_sorted_by_display_order(self):
        """Tags should be sorted by displayOrder ASC."""
        h = _headers()
        api_post("/tags", {"name": "TagZ", "displayOrder": 99}, headers=h)
        api_post("/tags", {"name": "TagA", "displayOrder": 1}, headers=h)
        api_post("/tags", {"name": "TagM", "displayOrder": 50}, headers=h)

        resp = api_get("/tags", headers=h)
        tags = resp.json()
        orders = [t["displayOrder"] for t in tags]
        assert orders == sorted(orders)


class TestTransactionTypeValidation:
    """Pattern 5: Business rule enforcement — type/category matching, transfer rules."""

    def test_income_requires_income_category(self):
        """Income transaction must use income category."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "TypeVal", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "ExpCat", "type": "expense"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "income", "amount": 100.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-01-01", "time": "09:00:00",
        }, headers=h)
        assert resp.status_code == 400

    def test_transfer_requires_destination_account(self):
        """Transfer without destinationAccountId must fail."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "XferVal", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Xfer", "type": "transfer"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "transfer", "amount": 100.00, "accountId": acct_id,
            "categoryId": xfer_cat, "date": "2024-01-01", "time": "09:00:00",
        }, headers=h)
        assert resp.status_code == 400

    def test_transfer_same_account_fails(self):
        """Transfer source and destination must differ."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "SameAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "XferSame", "type": "transfer"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "transfer", "amount": 100.00, "accountId": acct_id,
            "categoryId": xfer_cat, "destinationAccountId": acct_id,
            "date": "2024-01-01", "time": "09:00:00",
        }, headers=h)
        assert resp.status_code == 400

    def test_expense_with_transfer_category_fails(self):
        """Expense transaction cannot use transfer category."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "ExpXfer", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "XferCat", "type": "transfer"}, headers=h).json()["id"]

        resp = api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct_id,
            "categoryId": xfer_cat, "date": "2024-01-01", "time": "09:00:00",
        }, headers=h)
        assert resp.status_code == 400


class TestStatisticsComputation:
    """Pattern 5: Verify statistics are actually computed, not just echoed."""

    def test_monthly_stats_correct_aggregation(self):
        """Monthly stats must aggregate income/expense correctly, exclude transfers."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "Stats", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        acct2_id = api_post("/accounts", {"name": "Stats2", "type": "savings", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Pay", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Xfer", "type": "transfer"}, headers=h).json()["id"]

        # January: income 4000, expense 1500, transfer 500 (excluded)
        api_post("/transactions", {"type": "income", "amount": 4000.00, "accountId": acct_id, "categoryId": inc_cat, "date": "2024-01-05", "time": "09:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 1500.00, "accountId": acct_id, "categoryId": exp_cat, "date": "2024-01-10", "time": "12:00:00"}, headers=h)
        api_post("/transactions", {"type": "transfer", "amount": 500.00, "accountId": acct_id, "categoryId": xfer_cat, "destinationAccountId": acct2_id, "date": "2024-01-15", "time": "14:00:00"}, headers=h)

        resp = api_get("/statistics/monthly", params={"startMonth": "2024-01", "endMonth": "2024-01"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        jan = data[0]
        assert jan["month"] == "2024-01"
        assert jan["totalIncome"] == 4000.00
        assert jan["totalExpense"] == 1500.00
        assert jan["net"] == 2500.00  # 4000 - 1500

    def test_category_breakdown_sums_amounts(self):
        """Category breakdown must sum amounts per category, not just count."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "CatBrk", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        food_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        transport_cat = api_post("/categories", {"name": "Transport", "type": "expense"}, headers=h).json()["id"]

        # Food: 50 + 75 + 25 = 150
        api_post("/transactions", {"type": "expense", "amount": 50.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-08-05", "time": "12:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 75.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-08-10", "time": "12:00:00"}, headers=h)
        api_post("/transactions", {"type": "expense", "amount": 25.00, "accountId": acct_id, "categoryId": food_cat, "date": "2024-08-15", "time": "12:00:00"}, headers=h)
        # Transport: 40
        api_post("/transactions", {"type": "expense", "amount": 40.00, "accountId": acct_id, "categoryId": transport_cat, "date": "2024-08-12", "time": "08:00:00"}, headers=h)

        resp = api_get("/statistics/category", params={"month": "2024-08", "type": "expense"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()

        food_item = next((x for x in data if x["categoryId"] == food_cat), None)
        assert food_item is not None
        assert food_item["categoryName"] == "Food"
        assert food_item["amount"] == 150.00

        transport_item = next((x for x in data if x["categoryId"] == transport_cat), None)
        assert transport_item is not None
        assert transport_item["categoryName"] == "Transport"
        assert transport_item["amount"] == 40.00

    def test_monthly_stats_camelcase_fields(self):
        """Verify monthly stats use camelCase: totalIncome, totalExpense, not total_income."""
        h = _headers()
        resp = api_get("/statistics/monthly", params={"startMonth": "2024-01", "endMonth": "2024-01"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        entry = data[0]
        assert "month" in entry
        assert "totalIncome" in entry
        assert "totalExpense" in entry
        assert "net" in entry
        # snake_case must NOT exist
        assert "total_income" not in entry
        assert "total_expense" not in entry

    def test_category_breakdown_camelcase_fields(self):
        """Verify category breakdown uses categoryId, categoryName camelCase."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "CBField", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "CamelCat", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {"type": "expense", "amount": 10.00, "accountId": acct_id, "categoryId": cat_id, "date": "2024-09-01", "time": "12:00:00"}, headers=h)

        resp = api_get("/statistics/category", params={"month": "2024-09", "type": "expense"}, headers=h)
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "categoryId" in item
        assert "categoryName" in item
        assert "amount" in item
        # snake_case alternatives must NOT exist
        assert "category_id" not in item
        assert "category_name" not in item


class TestUniqueConstraints:
    """Pattern 8: Unique constraints for names."""

    def test_duplicate_account_name_rejected(self):
        """Same user cannot have two accounts with same name."""
        h = _headers()
        name = f"UniqueAcct-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/accounts", {"name": name, "type": "cash", "currency": "USD"}, headers=h)
        assert resp1.status_code == 201
        resp2 = api_post("/accounts", {"name": name, "type": "checking", "currency": "EUR"}, headers=h)
        assert resp2.status_code == 400

    def test_duplicate_tag_name_rejected(self):
        """Same user cannot have two tags with same name."""
        h = _headers()
        name = f"UniqueTag-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/tags", {"name": name}, headers=h)
        assert resp1.status_code == 201
        resp2 = api_post("/tags", {"name": name}, headers=h)
        assert resp2.status_code == 400

    def test_duplicate_category_same_type_parent_rejected(self):
        """Same name + same type + same parent → 400."""
        h = _headers()
        name = f"UniqueCat-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/categories", {"name": name, "type": "expense"}, headers=h)
        assert resp1.status_code == 201
        resp2 = api_post("/categories", {"name": name, "type": "expense"}, headers=h)
        assert resp2.status_code == 400

    def test_same_category_name_different_type_allowed(self):
        """Same name but different type should be allowed."""
        h = _headers()
        name = f"DualCat-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/categories", {"name": name, "type": "income"}, headers=h)
        assert resp1.status_code == 201
        resp2 = api_post("/categories", {"name": name, "type": "expense"}, headers=h)
        assert resp2.status_code == 201


class TestDeletionBlocking:
    """Pattern 7: Verify deletion is blocked when dependencies exist."""

    def test_account_with_transaction_cannot_be_deleted(self):
        """Account referenced by transaction → 400 on delete."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "BlockDel", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-01-01", "time": "12:00:00",
        }, headers=h)

        resp = api_delete(f"/accounts/{acct_id}", headers=h)
        assert resp.status_code == 400

    def test_category_with_children_cannot_be_deleted(self):
        """Parent category with children → 400 on delete."""
        h = _headers()
        parent_id = api_post("/categories", {"name": "Parent", "type": "expense"}, headers=h).json()["id"]
        api_post("/categories", {"name": "Child", "type": "expense", "parentId": parent_id}, headers=h)

        resp = api_delete(f"/categories/{parent_id}", headers=h)
        assert resp.status_code == 400

    def test_tag_deletion_removes_from_transaction(self):
        """Deleting tag removes it from transaction's tagIds but doesn't delete the transaction."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "TagDel", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]
        tag1_id = api_post("/tags", {"name": "keep-tag"}, headers=h).json()["id"]
        tag2_id = api_post("/tags", {"name": "delete-tag"}, headers=h).json()["id"]

        txn_resp = api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag1_id, tag2_id],
            "date": "2024-01-01", "time": "12:00:00",
        }, headers=h)
        txn_id = txn_resp.json()["id"]

        # Delete one tag
        del_resp = api_delete(f"/tags/{tag2_id}", headers=h)
        assert del_resp.status_code == 204

        # Transaction still exists with remaining tag
        txn = api_get(f"/transactions/{txn_id}", headers=h).json()
        assert txn["id"] == txn_id
        assert tag1_id in txn["tagIds"]
        assert tag2_id not in txn["tagIds"]


class TestExchangeRatesAndCSV:
    """Pattern 1+5: Exchange rates structure and CSV export format."""

    def test_exchange_rates_structure(self):
        """Exchange rates must have base and rates fields."""
        h = _headers()
        resp = api_get("/exchange-rates", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "base" in data
        assert "rates" in data
        assert data["base"] == "USD"
        assert isinstance(data["rates"], dict)
        assert len(data["rates"]) > 0

    def test_exchange_rates_custom_base(self):
        """Exchange rates with base=EUR should return EUR as base."""
        h = _headers()
        resp = api_get("/exchange-rates", params={"base": "EUR"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["base"] == "EUR"

    def test_csv_export_header_and_format(self):
        """CSV export must have correct header columns."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": "CSVAcct", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "CSVCat", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 42.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-10-01", "time": "10:00:00",
            "comment": "CSV test",
        }, headers=h)

        resp = requests.get(f"{BASE_URL}/transactions/export", headers=h, timeout=30)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        # Header check
        assert rows[0] == ["date", "type", "category", "account", "amount", "comment", "tags"]
        # Data row check
        assert len(rows) >= 2
        assert rows[1][0] == "2024-10-01"
        assert rows[1][1] == "expense"
        assert rows[1][2] == "CSVCat"
        assert rows[1][3] == "CSVAcct"
        assert float(rows[1][4]) == 42.00
        assert rows[1][5] == "CSV test"


class TestTransactionListStructure:
    """Pattern 1+2: Verify TransactionList wrapping object."""

    def test_transaction_list_wrapper_fields(self):
        """GET /transactions must return {transactions, total, offset, limit}."""
        h = _headers()
        resp = api_get("/transactions", headers=h)
        assert resp.status_code == 200
        data = resp.json()

        # Must have the wrapping fields
        assert "transactions" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

        assert isinstance(data["transactions"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["offset"], int)
        assert isinstance(data["limit"], int)

    def test_default_pagination_values(self):
        """Default offset=0, limit=50."""
        h = _headers()
        resp = api_get("/transactions", headers=h)
        data = resp.json()
        assert data["offset"] == 0
        assert data["limit"] == 50


class TestStatusCodes:
    """Pattern 4: Verify correct HTTP status codes."""

    def test_create_returns_201(self):
        """POST creates should return 201, not 200."""
        h = _headers()
        resp = api_post("/accounts", {"name": f"SC-{uuid.uuid4().hex[:8]}", "type": "cash", "currency": "USD"}, headers=h)
        assert resp.status_code == 201

        resp = api_post("/categories", {"name": f"SC-{uuid.uuid4().hex[:8]}", "type": "expense"}, headers=h)
        assert resp.status_code == 201

        resp = api_post("/tags", {"name": f"SC-{uuid.uuid4().hex[:8]}"}, headers=h)
        assert resp.status_code == 201

    def test_delete_returns_204(self):
        """DELETE should return 204, not 200."""
        h = _headers()
        acct_id = api_post("/accounts", {"name": f"Del204-{uuid.uuid4().hex[:8]}", "type": "cash", "currency": "USD"}, headers=h).json()["id"]
        resp = api_delete(f"/accounts/{acct_id}", headers=h)
        assert resp.status_code == 204

    def test_not_found_returns_404(self):
        """Accessing nonexistent resources should return 404, not 200 or 500."""
        h = _headers()
        fake_id = str(uuid.uuid4())
        assert api_get(f"/accounts/{fake_id}", headers=h).status_code == 404
        assert api_get(f"/categories/{fake_id}", headers=h).status_code == 404
        assert api_get(f"/tags/{fake_id}", headers=h).status_code == 404
        assert api_get(f"/transactions/{fake_id}", headers=h).status_code == 404

    def test_missing_auth_returns_401(self):
        """Missing X-User-Id header should return 401."""
        resp = requests.get(f"{BASE_URL}/accounts", timeout=30)
        assert resp.status_code == 401
        resp = requests.get(f"{BASE_URL}/transactions", timeout=30)
        assert resp.status_code == 401
