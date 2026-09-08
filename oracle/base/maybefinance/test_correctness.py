"""
BackendForge — Comprehensive Correctness Tests for Maybe Finance Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

HEADERS = {"X-User-Id": USER_ID, "Content-Type": "application/json"}
HEADERS2 = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_state():
    global USER_ID, USER2_ID, HEADERS, HEADERS2, UNIQUE

    USER_ID = str(uuid.uuid4())
    USER2_ID = str(uuid.uuid4())
    HEADERS = {"X-User-Id": USER_ID, "Content-Type": "application/json"}
    HEADERS2 = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
    UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401_accounts(self):
        resp = requests.get(f"{BASE_URL}/accounts", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_transactions(self):
        resp = requests.get(f"{BASE_URL}/transactions", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_categories(self):
        resp = requests.get(f"{BASE_URL}/categories", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_tags(self):
        resp = requests.get(f"{BASE_URL}/tags", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_net_worth(self):
        resp = requests.get(f"{BASE_URL}/net-worth", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_budgets(self):
        resp = requests.get(f"{BASE_URL}/budgets", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_insights(self):
        resp = requests.get(f"{BASE_URL}/insights/spending-by-category", timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        resp = requests.get(f"{BASE_URL}/accounts", headers={"X-User-Id": ""}, timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 2: Account CRUD
# ════════════════════════════════════════════════════════════════════


class TestAccountCRUD:

    def test_create_account(self):
        resp = api_post("/accounts", {
            "name": f"Checking-{UNIQUE}",
            "account_type": "depository",
            "balance": 100000,
            "currency": "USD",
            "institution_name": "Chase"
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        acct = resp.json()
        assert acct["name"] == f"Checking-{UNIQUE}"
        assert acct["account_type"] == "depository"
        assert acct["balance"] == 100000
        assert acct["currency"] == "USD"
        assert acct["institution_name"] == "Chase"
        assert "id" in acct
        assert "created_at" in acct
        assert "updated_at" in acct
        assert acct["user_id"] == USER_ID

    def test_create_account_minimal(self):
        resp = api_post("/accounts", {
            "name": f"Minimal-{UNIQUE}",
            "account_type": "other",
            "balance": 0
        })
        assert resp.status_code == 201
        acct = resp.json()
        assert acct["name"] == f"Minimal-{UNIQUE}"
        assert acct["currency"] == "USD"  # default

    def test_create_account_loan_negative_balance(self):
        resp = api_post("/accounts", {
            "name": f"Mortgage-{UNIQUE}",
            "account_type": "loan",
            "balance": -25000000
        })
        assert resp.status_code == 201
        acct = resp.json()
        assert acct["balance"] == -25000000

    def test_list_accounts(self):
        # Create one first
        api_post("/accounts", {"name": f"ListAcct-{UNIQUE}", "account_type": "depository", "balance": 5000})
        resp = api_get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()
        assert isinstance(accounts, list)
        assert len(accounts) >= 1
        names = [a["name"] for a in accounts]
        assert f"ListAcct-{UNIQUE}" in names

    def test_get_account(self):
        create_resp = api_post("/accounts", {"name": f"GetAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = create_resp.json()["id"]
        resp = api_get(f"/accounts/{acct_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == acct_id
        assert resp.json()["name"] == f"GetAcct-{UNIQUE}"

    def test_get_account_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_update_account(self):
        create_resp = api_post("/accounts", {"name": f"UpdAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = create_resp.json()["id"]
        resp = api_put(f"/accounts/{acct_id}", {"name": f"Updated-{UNIQUE}", "balance": 2000})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated-{UNIQUE}"
        assert resp.json()["balance"] == 2000

    def test_delete_account(self):
        create_resp = api_post("/accounts", {"name": f"DelAcct-{UNIQUE}", "account_type": "depository", "balance": 500})
        acct_id = create_resp.json()["id"]
        resp = api_delete(f"/accounts/{acct_id}")
        assert resp.status_code == 204
        # Verify gone
        get_resp = api_get(f"/accounts/{acct_id}")
        assert get_resp.status_code == 404

    def test_delete_account_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/accounts/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Category CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryCRUD:

    def test_create_category(self):
        resp = api_post("/categories", {
            "name": f"Groceries-{UNIQUE}",
            "color": "#4CAF50",
            "category_type": "expense"
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        cat = resp.json()
        assert cat["name"] == f"Groceries-{UNIQUE}"
        assert cat["color"] == "#4CAF50"
        assert cat["category_type"] == "expense"
        assert cat["parent_id"] is None
        assert "id" in cat
        assert cat["user_id"] == USER_ID

    def test_create_category_with_parent(self):
        # Create parent
        parent_resp = api_post("/categories", {"name": f"Food-{UNIQUE}", "color": "#FF0000", "category_type": "expense"})
        parent_id = parent_resp.json()["id"]
        # Create child
        child_resp = api_post("/categories", {
            "name": f"Restaurants-{UNIQUE}",
            "color": "#FF5722",
            "category_type": "expense",
            "parent_id": parent_id
        })
        assert child_resp.status_code == 201
        child = child_resp.json()
        assert child["parent_id"] == parent_id

    def test_create_category_no_grandchildren(self):
        """Cannot set parent_id to a category that already has a parent."""
        parent_resp = api_post("/categories", {"name": f"P-{UNIQUE}-gc", "color": "#000", "category_type": "expense"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/categories", {
            "name": f"C-{UNIQUE}-gc",
            "color": "#111",
            "category_type": "expense",
            "parent_id": parent_id
        })
        child_id = child_resp.json()["id"]
        # Try to create grandchild
        gc_resp = api_post("/categories", {
            "name": f"GC-{UNIQUE}",
            "color": "#222",
            "category_type": "expense",
            "parent_id": child_id
        })
        assert gc_resp.status_code == 400

    def test_create_category_self_parent(self):
        """Cannot set parent_id to self."""
        resp = api_post("/categories", {"name": f"Self-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = resp.json()["id"]
        upd = api_put(f"/categories/{cat_id}", {"parent_id": cat_id})
        assert upd.status_code == 400

    def test_list_categories(self):
        api_post("/categories", {"name": f"ListCat-{UNIQUE}", "color": "#ABC", "category_type": "income"})
        resp = api_get("/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        names = [c["name"] for c in cats]
        assert f"ListCat-{UNIQUE}" in names

    def test_get_category(self):
        create_resp = api_post("/categories", {"name": f"GetCat-{UNIQUE}", "color": "#DEF", "category_type": "expense"})
        cat_id = create_resp.json()["id"]
        resp = api_get(f"/categories/{cat_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cat_id

    def test_update_category(self):
        create_resp = api_post("/categories", {"name": f"UpdCat-{UNIQUE}", "color": "#111", "category_type": "expense"})
        cat_id = create_resp.json()["id"]
        resp = api_put(f"/categories/{cat_id}", {"name": f"Renamed-{UNIQUE}", "color": "#999"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Renamed-{UNIQUE}"
        assert resp.json()["color"] == "#999"

    def test_delete_category(self):
        create_resp = api_post("/categories", {"name": f"DelCat-{UNIQUE}", "color": "#333", "category_type": "expense"})
        cat_id = create_resp.json()["id"]
        resp = api_delete(f"/categories/{cat_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/categories/{cat_id}")
        assert get_resp.status_code == 404

    def test_delete_parent_nullifies_children(self):
        """Deleting a parent category sets children's parent_id to null."""
        parent_resp = api_post("/categories", {"name": f"DelParent-{UNIQUE}", "color": "#000", "category_type": "expense"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/categories", {
            "name": f"Orphan-{UNIQUE}",
            "color": "#111",
            "category_type": "expense",
            "parent_id": parent_id
        })
        child_id = child_resp.json()["id"]

        api_delete(f"/categories/{parent_id}")
        child = api_get(f"/categories/{child_id}").json()
        assert child["parent_id"] is None


# ════════════════════════════════════════════════════════════════════
# PART 4: Tag CRUD
# ════════════════════════════════════════════════════════════════════


class TestTagCRUD:

    def test_create_tag(self):
        resp = api_post("/tags", {"name": f"Travel-{UNIQUE}", "color": "#2196F3"})
        assert resp.status_code == 201
        tag = resp.json()
        assert tag["name"] == f"Travel-{UNIQUE}"
        assert tag["color"] == "#2196F3"
        assert "id" in tag
        assert tag["user_id"] == USER_ID

    def test_list_tags(self):
        api_post("/tags", {"name": f"ListTag-{UNIQUE}", "color": "#FFF"})
        resp = api_get("/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] for t in tags]
        assert f"ListTag-{UNIQUE}" in names

    def test_get_tag(self):
        create_resp = api_post("/tags", {"name": f"GetTag-{UNIQUE}", "color": "#AAA"})
        tag_id = create_resp.json()["id"]
        resp = api_get(f"/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tag_id

    def test_update_tag(self):
        create_resp = api_post("/tags", {"name": f"UpdTag-{UNIQUE}", "color": "#BBB"})
        tag_id = create_resp.json()["id"]
        resp = api_put(f"/tags/{tag_id}", {"name": f"RenamedTag-{UNIQUE}", "color": "#CCC"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"RenamedTag-{UNIQUE}"
        assert resp.json()["color"] == "#CCC"

    def test_delete_tag(self):
        create_resp = api_post("/tags", {"name": f"DelTag-{UNIQUE}", "color": "#DDD"})
        tag_id = create_resp.json()["id"]
        resp = api_delete(f"/tags/{tag_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/tags/{tag_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Transaction CRUD
# ════════════════════════════════════════════════════════════════════


class TestTransactionCRUD:

    def test_create_transaction(self):
        # Create account first
        acct_resp = api_post("/accounts", {"name": f"TxnAcct-{UNIQUE}", "account_type": "depository", "balance": 50000})
        acct_id = acct_resp.json()["id"]
        # Create category
        cat_resp = api_post("/categories", {"name": f"TxnCat-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/transactions", {
            "account_id": acct_id,
            "date": "2024-03-15",
            "amount": 5000,
            "name": f"Grocery Store-{UNIQUE}",
            "category_id": cat_id,
            "notes": "Weekly groceries"
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        txn = resp.json()
        assert txn["account_id"] == acct_id
        assert txn["date"] == "2024-03-15"
        assert txn["amount"] == 5000
        assert txn["name"] == f"Grocery Store-{UNIQUE}"
        assert txn["category_id"] == cat_id
        assert txn["notes"] == "Weekly groceries"
        assert txn["excluded"] is False
        assert txn["user_id"] == USER_ID
        assert "id" in txn

    def test_create_transaction_with_tags(self):
        acct_resp = api_post("/accounts", {"name": f"TagTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        tag1_resp = api_post("/tags", {"name": f"Tag1-{UNIQUE}", "color": "#111"})
        tag1_id = tag1_resp.json()["id"]
        tag2_resp = api_post("/tags", {"name": f"Tag2-{UNIQUE}", "color": "#222"})
        tag2_id = tag2_resp.json()["id"]

        resp = api_post("/transactions", {
            "account_id": acct_id,
            "date": "2024-03-16",
            "amount": 2000,
            "name": "Tagged purchase",
            "tags": [tag1_id, tag2_id]
        })
        assert resp.status_code == 201
        txn = resp.json()
        assert set(txn["tags"]) == {tag1_id, tag2_id}

    def test_create_transaction_invalid_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "account_id": fake_id,
            "date": "2024-03-15",
            "amount": 1000,
            "name": "Bad"
        })
        assert resp.status_code == 400

    def test_create_transaction_invalid_category(self):
        acct_resp = api_post("/accounts", {"name": f"InvCatAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        fake_cat_id = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "account_id": acct_id,
            "date": "2024-03-15",
            "amount": 1000,
            "name": "Bad cat",
            "category_id": fake_cat_id
        })
        assert resp.status_code == 400

    def test_create_transaction_invalid_tag(self):
        acct_resp = api_post("/accounts", {"name": f"InvTagAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        fake_tag_id = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "account_id": acct_id,
            "date": "2024-03-15",
            "amount": 1000,
            "name": "Bad tag",
            "tags": [fake_tag_id]
        })
        assert resp.status_code == 400

    def test_list_transactions(self):
        acct_resp = api_post("/accounts", {"name": f"ListTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-10", "amount": 100, "name": "T1"})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-11", "amount": 200, "name": "T2"})

        resp = api_get("/transactions")
        assert resp.status_code == 200
        txns = resp.json()
        assert isinstance(txns, list)
        assert len(txns) >= 2

    def test_list_transactions_filter_by_account(self):
        acct1_resp = api_post("/accounts", {"name": f"FilterAcct1-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"FilterAcct2-{UNIQUE}", "account_type": "depository", "balance": 2000})
        acct2_id = acct2_resp.json()["id"]

        api_post("/transactions", {"account_id": acct1_id, "date": "2024-03-10", "amount": 100, "name": "A1"})
        api_post("/transactions", {"account_id": acct2_id, "date": "2024-03-10", "amount": 200, "name": "A2"})

        resp = api_get("/transactions", params={"account_id": acct1_id})
        txns = resp.json()
        for txn in txns:
            assert txn["account_id"] == acct1_id

    def test_list_transactions_filter_by_date_range(self):
        acct_resp = api_post("/accounts", {"name": f"DateAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        api_post("/transactions", {"account_id": acct_id, "date": "2024-01-15", "amount": 100, "name": "Jan"})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 200, "name": "Mar"})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-06-15", "amount": 300, "name": "Jun"})

        resp = api_get("/transactions", params={"start_date": "2024-02-01", "end_date": "2024-04-30"})
        txns = resp.json()
        for txn in txns:
            assert txn["date"] >= "2024-02-01"
            assert txn["date"] <= "2024-04-30"

    def test_list_transactions_filter_by_excluded(self):
        acct_resp = api_post("/accounts", {"name": f"ExclAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 100, "name": "Normal", "excluded": False})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 200, "name": "Excluded", "excluded": True})

        resp = api_get("/transactions", params={"excluded": "true"})
        txns = resp.json()
        for txn in txns:
            assert txn["excluded"] is True

    def test_get_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"GetTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "Get me"})
        txn_id = create_resp.json()["id"]

        resp = api_get(f"/transactions/{txn_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == txn_id

    def test_update_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"UpdTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "Before"})
        txn_id = create_resp.json()["id"]

        resp = api_put(f"/transactions/{txn_id}", {"name": "After", "amount": 750})
        assert resp.status_code == 200
        assert resp.json()["name"] == "After"
        assert resp.json()["amount"] == 750

    def test_update_transaction_set_null_category(self):
        acct_resp = api_post("/accounts", {"name": f"NullCatAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"TmpCat-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        create_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 100, "name": "X", "category_id": cat_id})
        txn_id = create_resp.json()["id"]

        resp = api_put(f"/transactions/{txn_id}", {"category_id": None})
        assert resp.status_code == 200
        assert resp.json()["category_id"] is None

    def test_delete_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"DelTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "Del me"})
        txn_id = create_resp.json()["id"]

        resp = api_delete(f"/transactions/{txn_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/transactions/{txn_id}")
        assert get_resp.status_code == 404

    def test_delete_transaction_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/transactions/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Holdings CRUD
# ════════════════════════════════════════════════════════════════════


class TestHoldingsCRUD:

    def test_create_holding(self):
        acct_resp = api_post("/accounts", {"name": f"InvAcct-{UNIQUE}", "account_type": "investment", "balance": 100000})
        acct_id = acct_resp.json()["id"]

        resp = api_post(f"/accounts/{acct_id}/holdings", {
            "symbol": "AAPL",
            "shares": 10.5,
            "cost_basis": 150000,
            "current_value": 175000
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        holding = resp.json()
        assert holding["symbol"] == "AAPL"
        assert holding["shares"] == 10.5
        assert holding["cost_basis"] == 150000
        assert holding["current_value"] == 175000
        assert holding["account_id"] == acct_id
        assert "id" in holding

    def test_create_holding_non_investment_account(self):
        acct_resp = api_post("/accounts", {"name": f"NonInvAcct-{UNIQUE}", "account_type": "depository", "balance": 5000})
        acct_id = acct_resp.json()["id"]
        resp = api_post(f"/accounts/{acct_id}/holdings", {
            "symbol": "GOOG",
            "shares": 5,
            "cost_basis": 100000,
            "current_value": 110000
        })
        assert resp.status_code == 400

    def test_list_holdings(self):
        acct_resp = api_post("/accounts", {"name": f"ListHoldAcct-{UNIQUE}", "account_type": "investment", "balance": 50000})
        acct_id = acct_resp.json()["id"]
        api_post(f"/accounts/{acct_id}/holdings", {"symbol": "MSFT", "shares": 20, "cost_basis": 200000, "current_value": 250000})
        api_post(f"/accounts/{acct_id}/holdings", {"symbol": "TSLA", "shares": 5, "cost_basis": 100000, "current_value": 90000})

        resp = api_get(f"/accounts/{acct_id}/holdings")
        assert resp.status_code == 200
        holdings = resp.json()
        assert isinstance(holdings, list)
        assert len(holdings) >= 2
        symbols = [h["symbol"] for h in holdings]
        assert "MSFT" in symbols
        assert "TSLA" in symbols

    def test_get_holding(self):
        acct_resp = api_post("/accounts", {"name": f"GetHoldAcct-{UNIQUE}", "account_type": "investment", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post(f"/accounts/{acct_id}/holdings", {"symbol": "VTI", "shares": 50, "cost_basis": 500000, "current_value": 550000})
        holding_id = create_resp.json()["id"]

        resp = api_get(f"/accounts/{acct_id}/holdings/{holding_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == holding_id
        assert resp.json()["symbol"] == "VTI"

    def test_update_holding(self):
        acct_resp = api_post("/accounts", {"name": f"UpdHoldAcct-{UNIQUE}", "account_type": "investment", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post(f"/accounts/{acct_id}/holdings", {"symbol": "AMD", "shares": 100, "cost_basis": 1000000, "current_value": 1200000})
        holding_id = create_resp.json()["id"]

        resp = api_put(f"/accounts/{acct_id}/holdings/{holding_id}", {"current_value": 1500000})
        assert resp.status_code == 200
        assert resp.json()["current_value"] == 1500000

    def test_delete_holding(self):
        acct_resp = api_post("/accounts", {"name": f"DelHoldAcct-{UNIQUE}", "account_type": "investment", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post(f"/accounts/{acct_id}/holdings", {"symbol": "NVDA", "shares": 10, "cost_basis": 500000, "current_value": 600000})
        holding_id = create_resp.json()["id"]

        resp = api_delete(f"/accounts/{acct_id}/holdings/{holding_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/accounts/{acct_id}/holdings/{holding_id}")
        assert get_resp.status_code == 404

    def test_holdings_not_found_for_bad_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/accounts/{fake_id}/holdings")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Net Worth
# ════════════════════════════════════════════════════════════════════


class TestNetWorth:

    def test_net_worth_empty(self):
        """New user with no accounts should have 0 net worth."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}
        resp = api_get("/net-worth", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["net_worth"] == 0
        assert data["assets"] == 0
        assert data["liabilities"] == 0
        assert data["accounts"] == []

    def test_net_worth_basic(self):
        """Net worth with depository and loan accounts."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        # Create depository account (asset)
        api_post("/accounts", {"name": "Savings", "account_type": "depository", "balance": 500000}, headers=headers)
        # Create loan (liability)
        api_post("/accounts", {"name": "Car Loan", "account_type": "loan", "balance": -200000}, headers=headers)

        resp = api_get("/net-worth", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["assets"] == 500000
        assert data["liabilities"] == 200000
        assert data["net_worth"] == 300000

    def test_net_worth_with_holdings(self):
        """Investment account value includes holdings."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        # Create investment account with cash balance
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={
            "name": "Brokerage", "account_type": "investment", "balance": 50000
        }, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        # Add holdings
        requests.post(f"{BASE_URL}/accounts/{acct_id}/holdings", json={
            "symbol": "AAPL", "shares": 10, "cost_basis": 100000, "current_value": 150000
        }, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/accounts/{acct_id}/holdings", json={
            "symbol": "GOOG", "shares": 5, "cost_basis": 200000, "current_value": 250000
        }, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/net-worth", headers=headers, timeout=30)
        data = resp.json()
        # assets = balance (50000) + holdings (150000 + 250000) = 450000
        assert data["assets"] == 450000
        assert data["net_worth"] == 450000

    def test_net_worth_accounts_list(self):
        """Net worth response includes accounts breakdown."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        api_post("/accounts", {"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers)
        resp = api_get("/net-worth", headers=headers)
        data = resp.json()
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["name"] == "Checking"
        assert data["accounts"][0]["balance"] == 100000


# ════════════════════════════════════════════════════════════════════
# PART 8: Account Syncs
# ════════════════════════════════════════════════════════════════════


class TestAccountSyncs:

    def test_create_sync(self):
        acct_resp = api_post("/accounts", {"name": f"SyncAcct-{UNIQUE}", "account_type": "depository", "balance": 100000})
        acct_id = acct_resp.json()["id"]

        resp = api_post(f"/accounts/{acct_id}/syncs", {
            "balance": 95000,
            "transactions": [
                {"date": "2024-03-15", "amount": 3000, "name": "Coffee Shop"},
                {"date": "2024-03-16", "amount": 2000, "name": "Gas Station"}
            ]
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        sync = resp.json()
        assert sync["account_id"] == acct_id
        assert sync["balance_before"] == 100000
        assert sync["balance_after"] == 95000
        assert sync["transactions_created"] == 2
        assert "id" in sync
        assert "created_at" in sync

    def test_sync_updates_account_balance(self):
        acct_resp = api_post("/accounts", {"name": f"SyncBalAcct-{UNIQUE}", "account_type": "depository", "balance": 50000})
        acct_id = acct_resp.json()["id"]

        api_post(f"/accounts/{acct_id}/syncs", {"balance": 45000, "transactions": []})

        acct = api_get(f"/accounts/{acct_id}").json()
        assert acct["balance"] == 45000

    def test_sync_creates_transactions(self):
        acct_resp = api_post("/accounts", {"name": f"SyncTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 80000})
        acct_id = acct_resp.json()["id"]

        api_post(f"/accounts/{acct_id}/syncs", {
            "balance": 75000,
            "transactions": [
                {"date": "2024-03-20", "amount": 5000, "name": "Restaurant"}
            ]
        })

        txns = api_get("/transactions", params={"account_id": acct_id}).json()
        names = [t["name"] for t in txns]
        assert "Restaurant" in names

    def test_list_syncs(self):
        acct_resp = api_post("/accounts", {"name": f"ListSyncAcct-{UNIQUE}", "account_type": "depository", "balance": 60000})
        acct_id = acct_resp.json()["id"]

        api_post(f"/accounts/{acct_id}/syncs", {"balance": 58000, "transactions": []})
        api_post(f"/accounts/{acct_id}/syncs", {"balance": 55000, "transactions": []})

        resp = api_get(f"/accounts/{acct_id}/syncs")
        assert resp.status_code == 200
        syncs = resp.json()
        assert isinstance(syncs, list)
        assert len(syncs) >= 2

    def test_sync_not_found_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/accounts/{fake_id}/syncs", {"balance": 0, "transactions": []})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Budgets
# ════════════════════════════════════════════════════════════════════


class TestBudgets:

    def test_create_budget(self):
        cat_resp = api_post("/categories", {"name": f"BudCat-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/budgets", {
            "category_id": cat_id,
            "month": 3,
            "year": 2024,
            "amount": 50000
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        budget = resp.json()
        assert budget["category_id"] == cat_id
        assert budget["month"] == 3
        assert budget["year"] == 2024
        assert budget["amount"] == 50000
        assert "id" in budget

    def test_create_budget_duplicate(self):
        cat_resp = api_post("/categories", {"name": f"DupBudCat-{UNIQUE}", "color": "#111", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]

        api_post("/budgets", {"category_id": cat_id, "month": 4, "year": 2024, "amount": 30000})
        resp = api_post("/budgets", {"category_id": cat_id, "month": 4, "year": 2024, "amount": 40000})
        assert resp.status_code == 400

    def test_list_budgets(self):
        cat_resp = api_post("/categories", {"name": f"ListBudCat-{UNIQUE}", "color": "#222", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        api_post("/budgets", {"category_id": cat_id, "month": 5, "year": 2024, "amount": 20000})

        resp = api_get("/budgets")
        assert resp.status_code == 200
        budgets = resp.json()
        assert isinstance(budgets, list)
        assert len(budgets) >= 1

    def test_list_budgets_filter_month_year(self):
        cat_resp = api_post("/categories", {"name": f"FilterBudCat-{UNIQUE}", "color": "#333", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        api_post("/budgets", {"category_id": cat_id, "month": 6, "year": 2024, "amount": 25000})
        api_post("/budgets", {"category_id": cat_id, "month": 7, "year": 2024, "amount": 35000})

        resp = api_get("/budgets", params={"month": 6, "year": 2024})
        assert resp.status_code == 200
        budgets = resp.json()
        for b in budgets:
            assert b["month"] == 6
            assert b["year"] == 2024

    def test_list_budgets_missing_year_returns_400(self):
        resp = api_get("/budgets", params={"month": 6})
        assert resp.status_code == 400

    def test_list_budgets_missing_month_returns_400(self):
        resp = api_get("/budgets", params={"year": 2024})
        assert resp.status_code == 400

    def test_get_budget_with_actual(self):
        """Budget actual should be sum of transactions in the category for that month."""
        cat_resp = api_post("/categories", {"name": f"ActBudCat-{UNIQUE}", "color": "#444", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"BudAcct-{UNIQUE}", "account_type": "depository", "balance": 100000})
        acct_id = acct_resp.json()["id"]

        # Create transactions in March 2024
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-10", "amount": 5000, "name": "T1", "category_id": cat_id})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-20", "amount": 3000, "name": "T2", "category_id": cat_id})
        # Transaction in different month — should NOT count
        api_post("/transactions", {"account_id": acct_id, "date": "2024-04-05", "amount": 9000, "name": "T3", "category_id": cat_id})

        budget_resp = api_post("/budgets", {"category_id": cat_id, "month": 3, "year": 2024, "amount": 20000})
        budget_id = budget_resp.json()["id"]

        resp = api_get(f"/budgets/{budget_id}")
        assert resp.status_code == 200
        budget = resp.json()
        assert budget["actual"] == 8000  # 5000 + 3000
        assert budget["remaining"] == 12000  # 20000 - 8000

    def test_budget_excludes_excluded_transactions(self):
        """Excluded transactions should not count toward budget actual."""
        cat_resp = api_post("/categories", {"name": f"ExclBudCat-{UNIQUE}", "color": "#555", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"ExclBudAcct-{UNIQUE}", "account_type": "depository", "balance": 100000})
        acct_id = acct_resp.json()["id"]

        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-10", "amount": 5000, "name": "Normal", "category_id": cat_id})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 3000, "name": "Excluded", "category_id": cat_id, "excluded": True})

        budget_resp = api_post("/budgets", {"category_id": cat_id, "month": 3, "year": 2024, "amount": 10000})
        budget_id = budget_resp.json()["id"]

        budget = api_get(f"/budgets/{budget_id}").json()
        assert budget["actual"] == 5000  # only the non-excluded one

    def test_update_budget(self):
        cat_resp = api_post("/categories", {"name": f"UpdBudCat-{UNIQUE}", "color": "#666", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        budget_resp = api_post("/budgets", {"category_id": cat_id, "month": 8, "year": 2024, "amount": 30000})
        budget_id = budget_resp.json()["id"]

        resp = api_put(f"/budgets/{budget_id}", {"amount": 40000})
        assert resp.status_code == 200
        assert resp.json()["amount"] == 40000

    def test_delete_budget(self):
        cat_resp = api_post("/categories", {"name": f"DelBudCat-{UNIQUE}", "color": "#777", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        budget_resp = api_post("/budgets", {"category_id": cat_id, "month": 9, "year": 2024, "amount": 15000})
        budget_id = budget_resp.json()["id"]

        resp = api_delete(f"/budgets/{budget_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/budgets/{budget_id}")
        assert get_resp.status_code == 404

    def test_budget_child_category_rollup(self):
        """Budget for parent category should include transactions in child categories."""
        parent_resp = api_post("/categories", {"name": f"BudParent-{UNIQUE}", "color": "#000", "category_type": "expense"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/categories", {
            "name": f"BudChild-{UNIQUE}", "color": "#111", "category_type": "expense", "parent_id": parent_id
        })
        child_id = child_resp.json()["id"]

        acct_resp = api_post("/accounts", {"name": f"BudRollAcct-{UNIQUE}", "account_type": "depository", "balance": 100000})
        acct_id = acct_resp.json()["id"]

        # Transaction in parent
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-05", "amount": 2000, "name": "Parent txn", "category_id": parent_id})
        # Transaction in child
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-10", "amount": 3000, "name": "Child txn", "category_id": child_id})

        budget_resp = api_post("/budgets", {"category_id": parent_id, "month": 3, "year": 2024, "amount": 10000})
        budget_id = budget_resp.json()["id"]

        budget = api_get(f"/budgets/{budget_id}").json()
        assert budget["actual"] == 5000  # 2000 + 3000


# ════════════════════════════════════════════════════════════════════
# PART 10: Insights
# ════════════════════════════════════════════════════════════════════


class TestInsights:

    def test_spending_by_category_missing_params(self):
        resp = api_get("/insights/spending-by-category")
        assert resp.status_code == 400

    def test_spending_by_category_missing_year(self):
        resp = api_get("/insights/spending-by-category", params={"month": 3})
        assert resp.status_code == 400

    def test_income_vs_expenses_missing_params(self):
        resp = api_get("/insights/income-vs-expenses")
        assert resp.status_code == 400

    def test_savings_rate_missing_params(self):
        resp = api_get("/insights/savings-rate")
        assert resp.status_code == 400

    def test_spending_by_category(self):
        """Returns spending amounts by category for the given month."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Dining", "color": "#F00", "category_type": "expense"}, headers=headers, timeout=30)
        cat_id = cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        # March transactions
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 3000, "name": "Dinner", "category_id": cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-20", "amount": 2000, "name": "Lunch", "category_id": cat_id}, headers=headers, timeout=30)
        # February transactions (previous month)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-02-15", "amount": 4000, "name": "Feb dinner", "category_id": cat_id}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/spending-by-category", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        dining = next(d for d in data if d["category_id"] == cat_id)
        assert dining["amount"] == 5000  # 3000 + 2000
        assert dining["previous_amount"] == 4000
        # change_percent = (5000 - 4000) / 4000 * 100 = 25.0
        assert dining["change_percent"] == pytest.approx(25.0, abs=0.1)

    def test_spending_by_category_excludes_excluded(self):
        """Excluded transactions should not appear in spending insights."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Shopping", "color": "#00F", "category_type": "expense"}, headers=headers, timeout=30)
        cat_id = cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 5000, "name": "Normal", "category_id": cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-15", "amount": 3000, "name": "Excluded", "category_id": cat_id, "excluded": True}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/spending-by-category", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        data = resp.json()
        cat_data = next(d for d in data if d["category_id"] == cat_id)
        assert cat_data["amount"] == 5000  # excluded one not counted

    def test_spending_by_category_child_rollup(self):
        """Child category spending rolls up to parent."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        parent_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Food", "color": "#0F0", "category_type": "expense"}, headers=headers, timeout=30)
        parent_id = parent_resp.json()["id"]
        child_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Fast Food", "color": "#0FF", "category_type": "expense", "parent_id": parent_id}, headers=headers, timeout=30)
        child_id = child_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 2000, "name": "Groceries", "category_id": parent_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-15", "amount": 1500, "name": "McDonalds", "category_id": child_id}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/spending-by-category", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        data = resp.json()
        # Parent should show total = 2000 + 1500 = 3500
        parent_entry = next(d for d in data if d["category_id"] == parent_id)
        assert parent_entry["amount"] == 3500

    def test_income_vs_expenses(self):
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        inc_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Salary", "color": "#0F0", "category_type": "income"}, headers=headers, timeout=30)
        inc_cat_id = inc_cat_resp.json()["id"]
        exp_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Rent", "color": "#F00", "category_type": "expense"}, headers=headers, timeout=30)
        exp_cat_id = exp_cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 500000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        # Income transaction
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-01", "amount": 500000, "name": "March Salary", "category_id": inc_cat_id}, headers=headers, timeout=30)
        # Expense transactions
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-05", "amount": 150000, "name": "Rent", "category_id": exp_cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 50000, "name": "Utilities", "category_id": exp_cat_id}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/income-vs-expenses", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["income"] == 500000
        assert data["expenses"] == 200000
        assert data["net"] == 300000

    def test_income_vs_expenses_excludes_excluded(self):
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        inc_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Salary", "color": "#0F0", "category_type": "income"}, headers=headers, timeout=30)
        inc_cat_id = inc_cat_resp.json()["id"]
        exp_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Rent", "color": "#F00", "category_type": "expense"}, headers=headers, timeout=30)
        exp_cat_id = exp_cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-01", "amount": 100000, "name": "Salary", "category_id": inc_cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 30000, "name": "Rent", "category_id": exp_cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-15", "amount": 20000, "name": "Transfer", "category_id": exp_cat_id, "excluded": True}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/income-vs-expenses", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        data = resp.json()
        assert data["income"] == 100000
        assert data["expenses"] == 30000  # excluded one not counted
        assert data["net"] == 70000

    def test_savings_rate(self):
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        inc_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Salary", "color": "#0F0", "category_type": "income"}, headers=headers, timeout=30)
        inc_cat_id = inc_cat_resp.json()["id"]
        exp_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Expenses", "color": "#F00", "category_type": "expense"}, headers=headers, timeout=30)
        exp_cat_id = exp_cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-01", "amount": 100000, "name": "Salary", "category_id": inc_cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 60000, "name": "Spending", "category_id": exp_cat_id}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/savings-rate", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        # savings_rate = (100000 - 60000) / 100000 * 100 = 40.0
        assert data["savings_rate"] == pytest.approx(40.0, abs=0.01)
        assert data["income"] == 100000
        assert data["expenses"] == 60000

    def test_savings_rate_zero_income(self):
        """When income is 0, savings_rate should be 0."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        resp = requests.get(f"{BASE_URL}/insights/savings-rate", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["savings_rate"] == 0.0
        assert data["income"] == 0
        assert data["expenses"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 11: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_account_isolation(self):
        """User A's accounts are not visible to User B."""
        acct_name = f"IsoAcct-{UNIQUE}"
        api_post("/accounts", {"name": acct_name, "account_type": "depository", "balance": 1000})

        resp = api_get("/accounts", headers=HEADERS2)
        names = [a["name"] for a in resp.json()]
        assert acct_name not in names

    def test_transaction_isolation(self):
        """User A's transactions are not visible to User B."""
        acct_resp = api_post("/accounts", {"name": f"IsoTxnAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": f"Secret-{UNIQUE}"})

        resp = api_get("/transactions", headers=HEADERS2)
        names = [t["name"] for t in resp.json()]
        assert f"Secret-{UNIQUE}" not in names

    def test_cannot_access_other_users_account(self):
        """User B gets 404 when trying to GET User A's account."""
        acct_resp = api_post("/accounts", {"name": f"ProtAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]

        resp = api_get(f"/accounts/{acct_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_cannot_delete_other_users_account(self):
        acct_resp = api_post("/accounts", {"name": f"ProtDelAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]

        resp = api_delete(f"/accounts/{acct_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_cannot_create_transaction_with_other_users_account(self):
        """Cannot use another user's account_id."""
        acct_resp = api_post("/accounts", {"name": f"OtherAcct-{UNIQUE}", "account_type": "depository", "balance": 1000})
        acct_id = acct_resp.json()["id"]

        resp = api_post("/transactions", {
            "account_id": acct_id,
            "date": "2024-03-15",
            "amount": 100,
            "name": "Stolen"
        }, headers=HEADERS2)
        assert resp.status_code == 400

    def test_category_isolation(self):
        """User A's categories are not visible to User B."""
        cat_name = f"IsoCat-{UNIQUE}"
        api_post("/categories", {"name": cat_name, "color": "#000", "category_type": "expense"})

        resp = api_get("/categories", headers=HEADERS2)
        names = [c["name"] for c in resp.json()]
        assert cat_name not in names

    def test_tag_isolation(self):
        """User A's tags are not visible to User B."""
        tag_name = f"IsoTag-{UNIQUE}"
        api_post("/tags", {"name": tag_name, "color": "#000"})

        resp = api_get("/tags", headers=HEADERS2)
        names = [t["name"] for t in resp.json()]
        assert tag_name not in names


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_account_cascades_transactions(self):
        """Deleting an account should delete its transactions."""
        acct_resp = api_post("/accounts", {"name": f"CascAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        txn_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "Cascade txn"})
        txn_id = txn_resp.json()["id"]

        api_delete(f"/accounts/{acct_id}")

        # Transaction should be gone
        get_resp = api_get(f"/transactions/{txn_id}")
        assert get_resp.status_code == 404

    def test_delete_account_cascades_holdings(self):
        """Deleting an investment account should delete its holdings."""
        acct_resp = api_post("/accounts", {"name": f"CascHoldAcct-{UNIQUE}", "account_type": "investment", "balance": 50000})
        acct_id = acct_resp.json()["id"]
        hold_resp = api_post(f"/accounts/{acct_id}/holdings", {"symbol": "SPY", "shares": 10, "cost_basis": 100000, "current_value": 110000})
        hold_id = hold_resp.json()["id"]

        api_delete(f"/accounts/{acct_id}")

        # Holding should be gone (account not found)
        get_resp = api_get(f"/accounts/{acct_id}/holdings/{hold_id}")
        assert get_resp.status_code == 404

    def test_delete_account_cascades_syncs(self):
        """Deleting an account should delete its syncs."""
        acct_resp = api_post("/accounts", {"name": f"CascSyncAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        api_post(f"/accounts/{acct_id}/syncs", {"balance": 9000, "transactions": []})

        api_delete(f"/accounts/{acct_id}")

        # Syncs should be gone (account not found)
        get_resp = api_get(f"/accounts/{acct_id}/syncs")
        assert get_resp.status_code == 404

    def test_delete_category_nullifies_transactions(self):
        """Deleting a category sets category_id to null on transactions."""
        cat_resp = api_post("/categories", {"name": f"CascCat-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"CascCatAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        txn_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "CascCatTxn", "category_id": cat_id})
        txn_id = txn_resp.json()["id"]

        api_delete(f"/categories/{cat_id}")

        txn = api_get(f"/transactions/{txn_id}").json()
        assert txn["category_id"] is None

    def test_delete_category_deletes_budgets(self):
        """Deleting a category should delete budgets for that category."""
        cat_resp = api_post("/categories", {"name": f"CascBudCat-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]
        budget_resp = api_post("/budgets", {"category_id": cat_id, "month": 10, "year": 2024, "amount": 10000})
        budget_id = budget_resp.json()["id"]

        api_delete(f"/categories/{cat_id}")

        get_resp = api_get(f"/budgets/{budget_id}")
        assert get_resp.status_code == 404

    def test_delete_tag_removes_from_transactions(self):
        """Deleting a tag should remove it from transactions."""
        tag_resp = api_post("/tags", {"name": f"CascTag-{UNIQUE}", "color": "#000"})
        tag_id = tag_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"CascTagAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        txn_resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 500, "name": "TaggedTxn", "tags": [tag_id]})
        txn_id = txn_resp.json()["id"]

        api_delete(f"/tags/{tag_id}")

        txn = api_get(f"/transactions/{txn_id}").json()
        assert tag_id not in txn["tags"]


# ════════════════════════════════════════════════════════════════════
# PART 13: Investment Account Holdings Value
# ════════════════════════════════════════════════════════════════════


class TestInvestmentAccountHoldingsValue:

    def test_get_account_includes_holdings_value(self):
        """GET /accounts/{id} for investment accounts should include holdings_value."""
        acct_resp = api_post("/accounts", {"name": f"HoldValAcct-{UNIQUE}", "account_type": "investment", "balance": 50000})
        acct_id = acct_resp.json()["id"]
        api_post(f"/accounts/{acct_id}/holdings", {"symbol": "AAPL", "shares": 10, "cost_basis": 100000, "current_value": 150000})
        api_post(f"/accounts/{acct_id}/holdings", {"symbol": "GOOG", "shares": 5, "cost_basis": 200000, "current_value": 250000})

        resp = api_get(f"/accounts/{acct_id}")
        acct = resp.json()
        assert acct["holdings_value"] == 400000  # 150000 + 250000


# ════════════════════════════════════════════════════════════════════
# PART 14: Edge Cases & Additional Validation
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_transaction_without_category(self):
        """Transaction without category_id should be allowed."""
        acct_resp = api_post("/accounts", {"name": f"NoCatAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 1000, "name": "Uncategorized"})
        assert resp.status_code == 201
        assert resp.json()["category_id"] is None

    def test_transaction_without_tags(self):
        """Transaction without tags should have empty array."""
        acct_resp = api_post("/accounts", {"name": f"NoTagAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        resp = api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 1000, "name": "No tags"})
        assert resp.status_code == 201
        assert resp.json()["tags"] == []

    def test_list_transactions_filter_by_category(self):
        acct_resp = api_post("/accounts", {"name": f"CatFilterAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"CatFilter-{UNIQUE}", "color": "#000", "category_type": "expense"})
        cat_id = cat_resp.json()["id"]

        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 1000, "name": "With cat", "category_id": cat_id})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 2000, "name": "Without cat"})

        resp = api_get("/transactions", params={"category_id": cat_id})
        txns = resp.json()
        for txn in txns:
            assert txn["category_id"] == cat_id

    def test_list_transactions_filter_by_tag(self):
        acct_resp = api_post("/accounts", {"name": f"TagFilterAcct-{UNIQUE}", "account_type": "depository", "balance": 10000})
        acct_id = acct_resp.json()["id"]
        tag_resp = api_post("/tags", {"name": f"TagFilter-{UNIQUE}", "color": "#000"})
        tag_id = tag_resp.json()["id"]

        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 1000, "name": "Tagged", "tags": [tag_id]})
        api_post("/transactions", {"account_id": acct_id, "date": "2024-03-15", "amount": 2000, "name": "Untagged"})

        resp = api_get("/transactions", params={"tag_id": tag_id})
        txns = resp.json()
        for txn in txns:
            assert tag_id in txn["tags"]

    def test_spending_by_category_only_expense_categories(self):
        """Spending by category should only include expense categories."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        inc_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Salary", "color": "#0F0", "category_type": "income"}, headers=headers, timeout=30)
        inc_cat_id = inc_cat_resp.json()["id"]
        exp_cat_resp = requests.post(f"{BASE_URL}/categories", json={"name": "Food", "color": "#F00", "category_type": "expense"}, headers=headers, timeout=30)
        exp_cat_id = exp_cat_resp.json()["id"]
        acct_resp = requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 100000}, headers=headers, timeout=30)
        acct_id = acct_resp.json()["id"]

        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-01", "amount": 100000, "name": "Salary", "category_id": inc_cat_id}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/transactions", json={"account_id": acct_id, "date": "2024-03-10", "amount": 5000, "name": "Lunch", "category_id": exp_cat_id}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/insights/spending-by-category", params={"month": 3, "year": 2024}, headers=headers, timeout=30)
        data = resp.json()
        cat_ids = [d["category_id"] for d in data]
        assert inc_cat_id not in cat_ids  # income should not appear
        assert exp_cat_id in cat_ids

    def test_net_worth_credit_card_as_liability(self):
        """Credit card balance (negative) counts as liability."""
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "Content-Type": "application/json"}

        requests.post(f"{BASE_URL}/accounts", json={"name": "CC", "account_type": "credit_card", "balance": -50000}, headers=headers, timeout=30)
        requests.post(f"{BASE_URL}/accounts", json={"name": "Checking", "account_type": "depository", "balance": 200000}, headers=headers, timeout=30)

        resp = requests.get(f"{BASE_URL}/net-worth", headers=headers, timeout=30)
        data = resp.json()
        assert data["assets"] == 200000
        assert data["liabilities"] == 50000
        assert data["net_worth"] == 150000
