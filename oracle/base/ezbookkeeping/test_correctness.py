"""
BackendForge — Comprehensive Correctness Tests for EZBookkeeping Task

Tests ALL business rules and ALL endpoint groups.
"""

import csv
import io
import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-User-Id": USER2_ID,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401_accounts(self):
        resp = requests.get(f"{BASE_URL}/accounts", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_categories(self):
        resp = requests.get(f"{BASE_URL}/categories", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_tags(self):
        resp = requests.get(f"{BASE_URL}/tags", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_transactions(self):
        resp = requests.get(f"{BASE_URL}/transactions", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_statistics(self):
        resp = requests.get(f"{BASE_URL}/statistics/monthly", params={"startMonth": "2024-01", "endMonth": "2024-12"}, timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_exchange_rates(self):
        resp = requests.get(f"{BASE_URL}/exchange-rates", timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        resp = requests.get(f"{BASE_URL}/accounts", headers={"X-User-Id": ""}, timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 3: Account CRUD
# ════════════════════════════════════════════════════════════════════


class TestAccountCRUD:

    def test_create_account(self):
        resp = api_post("/accounts", {
            "name": f"Wallet-{UNIQUE}",
            "type": "cash",
            "currency": "USD",
            "icon": "wallet",
            "displayOrder": 1,
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        account = resp.json()
        assert account["name"] == f"Wallet-{UNIQUE}"
        assert account["type"] == "cash"
        assert account["currency"] == "USD"
        assert account["icon"] == "wallet"
        assert account["displayOrder"] == 1
        assert account["balance"] == 0
        assert "id" in account
        assert "createdAt" in account
        assert "updatedAt" in account

    def test_create_account_minimal(self):
        resp = api_post("/accounts", {
            "name": f"MinAccount-{UNIQUE}",
            "type": "checking",
            "currency": "EUR",
        })
        assert resp.status_code == 201
        account = resp.json()
        assert account["name"] == f"MinAccount-{UNIQUE}"
        assert account["type"] == "checking"
        assert account["currency"] == "EUR"
        assert account["displayOrder"] == 0  # default

    def test_create_account_all_types(self):
        """All account types should be accepted."""
        for acct_type in ["cash", "checking", "savings", "credit_card", "investment"]:
            resp = api_post("/accounts", {
                "name": f"Type-{acct_type}-{UNIQUE}",
                "type": acct_type,
                "currency": "USD",
            })
            assert resp.status_code == 201, f"Failed for type {acct_type}: {resp.text}"

    def test_list_accounts(self):
        # Create one first
        api_post("/accounts", {"name": f"ListAcct-{UNIQUE}", "type": "savings", "currency": "USD"})
        resp = api_get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()
        assert isinstance(accounts, list)
        names = [a["name"] for a in accounts]
        assert f"ListAcct-{UNIQUE}" in names

    def test_list_accounts_sorted_by_display_order(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        api_post("/accounts", {"name": "C-acct", "type": "cash", "currency": "USD", "displayOrder": 3}, headers=h)
        api_post("/accounts", {"name": "A-acct", "type": "cash", "currency": "USD", "displayOrder": 1}, headers=h)
        api_post("/accounts", {"name": "B-acct", "type": "cash", "currency": "USD", "displayOrder": 2}, headers=h)

        resp = api_get("/accounts", headers=h)
        accounts = resp.json()
        orders = [a["displayOrder"] for a in accounts]
        assert orders == sorted(orders), f"Accounts not sorted by displayOrder: {orders}"

    def test_get_account(self):
        create_resp = api_post("/accounts", {"name": f"GetAcct-{UNIQUE}", "type": "cash", "currency": "USD"})
        acct_id = create_resp.json()["id"]

        resp = api_get(f"/accounts/{acct_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == acct_id
        assert resp.json()["name"] == f"GetAcct-{UNIQUE}"

    def test_get_nonexistent_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_update_account(self):
        create_resp = api_post("/accounts", {"name": f"UpdAcct-{UNIQUE}", "type": "cash", "currency": "USD"})
        acct_id = create_resp.json()["id"]

        resp = api_put(f"/accounts/{acct_id}", {
            "name": f"UpdAcct-Modified-{UNIQUE}",
            "type": "checking",
            "currency": "EUR",
            "icon": "bank",
            "displayOrder": 5,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdAcct-Modified-{UNIQUE}"
        assert updated["type"] == "checking"
        assert updated["currency"] == "EUR"
        assert updated["icon"] == "bank"
        assert updated["displayOrder"] == 5

    def test_update_nonexistent_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/accounts/{fake_id}", {"name": "ghost", "type": "cash", "currency": "USD"})
        assert resp.status_code == 404

    def test_delete_account_no_transactions(self):
        create_resp = api_post("/accounts", {"name": f"DelAcct-{UNIQUE}", "type": "cash", "currency": "USD"})
        acct_id = create_resp.json()["id"]

        resp = api_delete(f"/accounts/{acct_id}")
        assert resp.status_code == 204

        # Verify gone
        get_resp = api_get(f"/accounts/{acct_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_account_name(self):
        name = f"DupAcct-{UNIQUE}"
        resp1 = api_post("/accounts", {"name": name, "type": "cash", "currency": "USD"})
        assert resp1.status_code == 201
        resp2 = api_post("/accounts", {"name": name, "type": "checking", "currency": "EUR"})
        assert resp2.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 4: Category CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryCRUD:

    def test_create_category(self):
        resp = api_post("/categories", {
            "name": f"Food-{UNIQUE}",
            "type": "expense",
            "icon": "food",
            "color": "#FF5733",
            "displayOrder": 1,
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        cat = resp.json()
        assert cat["name"] == f"Food-{UNIQUE}"
        assert cat["type"] == "expense"
        assert cat["icon"] == "food"
        assert cat["color"] == "#FF5733"
        assert cat["parentId"] is None
        assert cat["displayOrder"] == 1
        assert "id" in cat
        assert "createdAt" in cat

    def test_create_child_category(self):
        # Create parent
        parent_resp = api_post("/categories", {"name": f"Parent-{UNIQUE}", "type": "expense"})
        assert parent_resp.status_code == 201
        parent_id = parent_resp.json()["id"]

        # Create child
        child_resp = api_post("/categories", {
            "name": f"Child-{UNIQUE}",
            "type": "expense",
            "parentId": parent_id,
        })
        assert child_resp.status_code == 201
        child = child_resp.json()
        assert child["parentId"] == parent_id

    def test_create_category_max_depth_2(self):
        """Cannot create a child of a child (max 2 levels)."""
        parent_resp = api_post("/categories", {"name": f"L1-{UNIQUE}", "type": "expense"})
        parent_id = parent_resp.json()["id"]

        child_resp = api_post("/categories", {"name": f"L2-{UNIQUE}", "type": "expense", "parentId": parent_id})
        child_id = child_resp.json()["id"]

        # Try to create grandchild — should fail
        grandchild_resp = api_post("/categories", {
            "name": f"L3-{UNIQUE}",
            "type": "expense",
            "parentId": child_id,
        })
        assert grandchild_resp.status_code == 400

    def test_create_category_type_mismatch_parent(self):
        """Child must have same type as parent."""
        parent_resp = api_post("/categories", {"name": f"IncParent-{UNIQUE}", "type": "income"})
        parent_id = parent_resp.json()["id"]

        resp = api_post("/categories", {
            "name": f"ExpChild-{UNIQUE}",
            "type": "expense",
            "parentId": parent_id,
        })
        assert resp.status_code == 400

    def test_list_categories(self):
        api_post("/categories", {"name": f"ListCat-{UNIQUE}", "type": "income"})
        resp = api_get("/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        names = [c["name"] for c in cats]
        assert f"ListCat-{UNIQUE}" in names

    def test_get_category(self):
        create_resp = api_post("/categories", {"name": f"GetCat-{UNIQUE}", "type": "expense"})
        cat_id = create_resp.json()["id"]

        resp = api_get(f"/categories/{cat_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cat_id

    def test_get_nonexistent_category(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/categories/{fake_id}")
        assert resp.status_code == 404

    def test_update_category(self):
        create_resp = api_post("/categories", {"name": f"UpdCat-{UNIQUE}", "type": "expense", "icon": "old", "color": "#000000"})
        cat_id = create_resp.json()["id"]

        resp = api_put(f"/categories/{cat_id}", {
            "name": f"UpdCat-Modified-{UNIQUE}",
            "icon": "new-icon",
            "color": "#FFFFFF",
            "displayOrder": 10,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdCat-Modified-{UNIQUE}"
        assert updated["icon"] == "new-icon"
        assert updated["color"] == "#FFFFFF"
        assert updated["displayOrder"] == 10
        # Type should NOT change
        assert updated["type"] == "expense"

    def test_update_category_type_immutable(self):
        """Type should remain unchanged even if passed in update."""
        create_resp = api_post("/categories", {"name": f"ImmutType-{UNIQUE}", "type": "income"})
        cat_id = create_resp.json()["id"]

        resp = api_put(f"/categories/{cat_id}", {"name": f"ImmutType-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["type"] == "income"

    def test_delete_category_no_children_no_transactions(self):
        create_resp = api_post("/categories", {"name": f"DelCat-{UNIQUE}", "type": "expense"})
        cat_id = create_resp.json()["id"]

        resp = api_delete(f"/categories/{cat_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/categories/{cat_id}")
        assert get_resp.status_code == 404

    def test_delete_category_with_children_fails(self):
        """Cannot delete a parent category that has children."""
        parent_resp = api_post("/categories", {"name": f"ParentDel-{UNIQUE}", "type": "expense"})
        parent_id = parent_resp.json()["id"]

        api_post("/categories", {"name": f"ChildDel-{UNIQUE}", "type": "expense", "parentId": parent_id})

        resp = api_delete(f"/categories/{parent_id}")
        assert resp.status_code == 400

    def test_delete_nonexistent_category(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/categories/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_category_name_same_type_and_parent(self):
        name = f"DupCat-{UNIQUE}"
        resp1 = api_post("/categories", {"name": name, "type": "expense"})
        assert resp1.status_code == 201
        resp2 = api_post("/categories", {"name": name, "type": "expense"})
        assert resp2.status_code == 400

    def test_same_name_different_type_allowed(self):
        """Same name but different type is allowed."""
        name = f"SameNameDiffType-{UNIQUE}"
        resp1 = api_post("/categories", {"name": name, "type": "income"})
        assert resp1.status_code == 201
        resp2 = api_post("/categories", {"name": name, "type": "expense"})
        assert resp2.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 5: Tag CRUD
# ════════════════════════════════════════════════════════════════════


class TestTagCRUD:

    def test_create_tag(self):
        resp = api_post("/tags", {"name": f"vacation-{UNIQUE}", "displayOrder": 1})
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        tag = resp.json()
        assert tag["name"] == f"vacation-{UNIQUE}"
        assert tag["displayOrder"] == 1
        assert "id" in tag
        assert "createdAt" in tag

    def test_create_tag_minimal(self):
        resp = api_post("/tags", {"name": f"mintag-{UNIQUE}"})
        assert resp.status_code == 201
        assert resp.json()["displayOrder"] == 0  # default

    def test_list_tags(self):
        api_post("/tags", {"name": f"listtag-{UNIQUE}"})
        resp = api_get("/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] for t in tags]
        assert f"listtag-{UNIQUE}" in names

    def test_get_tag(self):
        create_resp = api_post("/tags", {"name": f"gettag-{UNIQUE}"})
        tag_id = create_resp.json()["id"]

        resp = api_get(f"/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tag_id

    def test_get_nonexistent_tag(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/tags/{fake_id}")
        assert resp.status_code == 404

    def test_update_tag(self):
        create_resp = api_post("/tags", {"name": f"updtag-{UNIQUE}", "displayOrder": 1})
        tag_id = create_resp.json()["id"]

        resp = api_put(f"/tags/{tag_id}", {"name": f"updtag-modified-{UNIQUE}", "displayOrder": 5})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"updtag-modified-{UNIQUE}"
        assert updated["displayOrder"] == 5

    def test_update_nonexistent_tag(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/tags/{fake_id}", {"name": "ghost"})
        assert resp.status_code == 404

    def test_delete_tag(self):
        create_resp = api_post("/tags", {"name": f"deltag-{UNIQUE}"})
        tag_id = create_resp.json()["id"]

        resp = api_delete(f"/tags/{tag_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/tags/{tag_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_tag(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/tags/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_tag_name(self):
        name = f"duptag-{UNIQUE}"
        resp1 = api_post("/tags", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/tags", {"name": name})
        assert resp2.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 6: Transaction CRUD
# ════════════════════════════════════════════════════════════════════


class TestTransactionCRUD:

    def _create_test_account(self, name_suffix="", headers=None):
        resp = api_post("/accounts", {
            "name": f"TxnAcct-{name_suffix}-{UNIQUE}-{uuid.uuid4().hex[:4]}",
            "type": "checking",
            "currency": "USD",
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def _create_test_category(self, cat_type="expense", parent_id=None, headers=None):
        data = {
            "name": f"TxnCat-{cat_type}-{UNIQUE}-{uuid.uuid4().hex[:4]}",
            "type": cat_type,
        }
        if parent_id:
            data["parentId"] = parent_id
        resp = api_post("/categories", data, headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_create_expense_transaction(self):
        acct_id = self._create_test_account("exp")
        cat_id = self._create_test_category("expense")

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 42.50,
            "accountId": acct_id,
            "categoryId": cat_id,
            "date": "2024-03-15",
            "time": "10:30:00",
            "comment": "Lunch",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        txn = resp.json()
        assert txn["type"] == "expense"
        assert txn["amount"] == 42.50
        assert txn["accountId"] == acct_id
        assert txn["categoryId"] == cat_id
        assert txn["date"] == "2024-03-15"
        assert txn["time"] == "10:30:00"
        assert txn["comment"] == "Lunch"
        assert txn["destinationAccountId"] is None
        assert "id" in txn
        assert "createdAt" in txn

    def test_create_income_transaction(self):
        acct_id = self._create_test_account("inc")
        cat_id = self._create_test_category("income")

        resp = api_post("/transactions", {
            "type": "income",
            "amount": 5000.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "date": "2024-03-01",
            "time": "09:00:00",
            "comment": "Salary",
        })
        assert resp.status_code == 201
        txn = resp.json()
        assert txn["type"] == "income"
        assert txn["amount"] == 5000.00

    def test_create_transfer_transaction(self):
        acct_src = self._create_test_account("src")
        acct_dst = self._create_test_account("dst")
        cat_id = self._create_test_category("transfer")

        resp = api_post("/transactions", {
            "type": "transfer",
            "amount": 200.00,
            "accountId": acct_src,
            "categoryId": cat_id,
            "destinationAccountId": acct_dst,
            "date": "2024-03-10",
            "time": "15:00:00",
            "comment": "Move to savings",
        })
        assert resp.status_code == 201
        txn = resp.json()
        assert txn["type"] == "transfer"
        assert txn["destinationAccountId"] == acct_dst

    def test_create_transfer_missing_destination_fails(self):
        acct_id = self._create_test_account("no-dst")
        cat_id = self._create_test_category("transfer")

        resp = api_post("/transactions", {
            "type": "transfer",
            "amount": 100.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "date": "2024-03-10",
            "time": "12:00:00",
        })
        assert resp.status_code == 400

    def test_create_transfer_same_account_fails(self):
        acct_id = self._create_test_account("same")
        cat_id = self._create_test_category("transfer")

        resp = api_post("/transactions", {
            "type": "transfer",
            "amount": 100.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "destinationAccountId": acct_id,
            "date": "2024-03-10",
            "time": "12:00:00",
        })
        assert resp.status_code == 400

    def test_create_transaction_type_category_mismatch(self):
        """Expense transaction cannot use income category."""
        acct_id = self._create_test_account("mismatch")
        income_cat = self._create_test_category("income")

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 10.00,
            "accountId": acct_id,
            "categoryId": income_cat,
            "date": "2024-03-15",
            "time": "10:00:00",
        })
        assert resp.status_code == 400

    def test_create_transaction_with_tags(self):
        acct_id = self._create_test_account("tags")
        cat_id = self._create_test_category("expense")

        tag1_resp = api_post("/tags", {"name": f"tag1-txn-{UNIQUE}-{uuid.uuid4().hex[:4]}"})
        tag2_resp = api_post("/tags", {"name": f"tag2-txn-{UNIQUE}-{uuid.uuid4().hex[:4]}"})
        tag1_id = tag1_resp.json()["id"]
        tag2_id = tag2_resp.json()["id"]

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 25.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "tagIds": [tag1_id, tag2_id],
            "date": "2024-03-15",
            "time": "11:00:00",
        })
        assert resp.status_code == 201
        txn = resp.json()
        assert set(txn["tagIds"]) == {tag1_id, tag2_id}

    def test_create_transaction_zero_amount_fails(self):
        acct_id = self._create_test_account("zero")
        cat_id = self._create_test_category("expense")

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": 0,
            "accountId": acct_id,
            "categoryId": cat_id,
            "date": "2024-03-15",
            "time": "10:00:00",
        })
        assert resp.status_code == 400

    def test_create_transaction_negative_amount_fails(self):
        acct_id = self._create_test_account("neg")
        cat_id = self._create_test_category("expense")

        resp = api_post("/transactions", {
            "type": "expense",
            "amount": -10.00,
            "accountId": acct_id,
            "categoryId": cat_id,
            "date": "2024-03-15",
            "time": "10:00:00",
        })
        assert resp.status_code == 400

    def test_list_transactions(self):
        acct_id = self._create_test_account("list")
        cat_id = self._create_test_category("expense")

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        })

        resp = api_get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "transactions" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert isinstance(data["transactions"], list)
        assert data["total"] >= 1

    def test_list_transactions_pagination(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = self._create_test_account("pag", headers=h)
        cat_id = self._create_test_category("expense", headers=h)

        for i in range(5):
            api_post("/transactions", {
                "type": "expense", "amount": 10.00 + i, "accountId": acct_id,
                "categoryId": cat_id, "date": f"2024-03-{15+i:02d}", "time": "10:00:00",
            }, headers=h)

        resp = api_get("/transactions", params={"limit": 2, "offset": 0}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["transactions"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_list_transactions_filter_by_type(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = self._create_test_account("filter", headers=h)
        exp_cat = self._create_test_category("expense", headers=h)
        inc_cat = self._create_test_category("income", headers=h)

        api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "income", "amount": 100.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-03-15", "time": "11:00:00",
        }, headers=h)

        resp = api_get("/transactions", params={"type": "expense"}, headers=h)
        data = resp.json()
        assert data["total"] == 1
        assert data["transactions"][0]["type"] == "expense"

    def test_list_transactions_filter_by_date_range(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = self._create_test_account("daterange", headers=h)
        cat_id = self._create_test_category("expense", headers=h)

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-01-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-06-15", "time": "10:00:00",
        }, headers=h)

        resp = api_get("/transactions", params={"startDate": "2024-02-01", "endDate": "2024-04-30"}, headers=h)
        data = resp.json()
        assert data["total"] == 1
        assert data["transactions"][0]["amount"] == 20.00

    def test_list_transactions_filter_by_account(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct1 = self._create_test_account("a1", headers=h)
        acct2 = self._create_test_account("a2", headers=h)
        cat_id = self._create_test_category("expense", headers=h)

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct1,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct2,
            "categoryId": cat_id, "date": "2024-03-15", "time": "11:00:00",
        }, headers=h)

        resp = api_get("/transactions", params={"accountId": acct1}, headers=h)
        data = resp.json()
        assert data["total"] == 1
        assert data["transactions"][0]["accountId"] == acct1

    def test_get_transaction(self):
        acct_id = self._create_test_account("get")
        cat_id = self._create_test_category("expense")

        create_resp = api_post("/transactions", {
            "type": "expense", "amount": 15.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        })
        txn_id = create_resp.json()["id"]

        resp = api_get(f"/transactions/{txn_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == txn_id

    def test_get_nonexistent_transaction(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/transactions/{fake_id}")
        assert resp.status_code == 404

    def test_update_transaction(self):
        acct_id = self._create_test_account("upd")
        cat_id = self._create_test_category("expense")

        create_resp = api_post("/transactions", {
            "type": "expense", "amount": 15.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
            "comment": "original",
        })
        txn_id = create_resp.json()["id"]

        resp = api_put(f"/transactions/{txn_id}", {
            "type": "expense", "amount": 25.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-16", "time": "11:00:00",
            "comment": "updated",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["amount"] == 25.00
        assert updated["date"] == "2024-03-16"
        assert updated["comment"] == "updated"

    def test_delete_transaction(self):
        acct_id = self._create_test_account("del")
        cat_id = self._create_test_category("expense")

        create_resp = api_post("/transactions", {
            "type": "expense", "amount": 15.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        })
        txn_id = create_resp.json()["id"]

        resp = api_delete(f"/transactions/{txn_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/transactions/{txn_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_transaction(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/transactions/{fake_id}")
        assert resp.status_code == 404

    def test_transaction_must_use_leaf_category(self):
        """Cannot use a parent category that has children."""
        parent_resp = api_post("/categories", {"name": f"ParentOnly-{UNIQUE}-{uuid.uuid4().hex[:4]}", "type": "expense"})
        parent_id = parent_resp.json()["id"]
        # Create a child under it
        api_post("/categories", {"name": f"ChildLeaf-{UNIQUE}-{uuid.uuid4().hex[:4]}", "type": "expense", "parentId": parent_id})

        acct_id = self._create_test_account("leaf")
        resp = api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": parent_id, "date": "2024-03-15", "time": "10:00:00",
        })
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 7: Account Balance (computed)
# ════════════════════════════════════════════════════════════════════


class TestAccountBalance:

    def test_income_increases_balance(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        acct_resp = api_post("/accounts", {"name": "BalInc", "type": "checking", "currency": "USD"}, headers=h)
        acct_id = acct_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h)
        cat_id = cat_resp.json()["id"]

        api_post("/transactions", {
            "type": "income", "amount": 1000.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)

        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 1000.00

    def test_expense_decreases_balance(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        acct_resp = api_post("/accounts", {"name": "BalExp", "type": "checking", "currency": "USD"}, headers=h)
        acct_id = acct_resp.json()["id"]
        inc_cat = api_post("/categories", {"name": "Inc", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "income", "amount": 1000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 300.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-03-02", "time": "10:00:00",
        }, headers=h)

        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 700.00

    def test_transfer_moves_money(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        src_resp = api_post("/accounts", {"name": "Src", "type": "checking", "currency": "USD"}, headers=h)
        src_id = src_resp.json()["id"]
        dst_resp = api_post("/accounts", {"name": "Dst", "type": "savings", "currency": "USD"}, headers=h)
        dst_id = dst_resp.json()["id"]

        inc_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Transfer", "type": "transfer"}, headers=h).json()["id"]

        # Add income to source
        api_post("/transactions", {
            "type": "income", "amount": 1000.00, "accountId": src_id,
            "categoryId": inc_cat, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)

        # Transfer from src to dst
        api_post("/transactions", {
            "type": "transfer", "amount": 400.00, "accountId": src_id,
            "categoryId": xfer_cat, "destinationAccountId": dst_id,
            "date": "2024-03-02", "time": "10:00:00",
        }, headers=h)

        src = api_get(f"/accounts/{src_id}", headers=h).json()
        dst = api_get(f"/accounts/{dst_id}", headers=h).json()
        assert src["balance"] == 600.00
        assert dst["balance"] == 400.00

    def test_delete_transaction_updates_balance(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        acct_resp = api_post("/accounts", {"name": "BalDel", "type": "checking", "currency": "USD"}, headers=h)
        acct_id = acct_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": "Inc", "type": "income"}, headers=h)
        cat_id = cat_resp.json()["id"]

        txn_resp = api_post("/transactions", {
            "type": "income", "amount": 500.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)
        txn_id = txn_resp.json()["id"]

        # Balance should be 500
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 500.00

        # Delete the transaction
        api_delete(f"/transactions/{txn_id}", headers=h)

        # Balance should be 0 again
        acct = api_get(f"/accounts/{acct_id}", headers=h).json()
        assert acct["balance"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 8: Statistics
# ════════════════════════════════════════════════════════════════════


class TestStatistics:

    def _setup_stats_user(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "Stats", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Salary", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        xfer_cat = api_post("/categories", {"name": "Xfer", "type": "transfer"}, headers=h).json()["id"]
        return h, acct_id, inc_cat, exp_cat, xfer_cat

    def test_monthly_statistics(self):
        h, acct_id, inc_cat, exp_cat, xfer_cat = self._setup_stats_user()

        # January: income 3000, expense 500
        api_post("/transactions", {
            "type": "income", "amount": 3000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-01-15", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 500.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-01-20", "time": "12:00:00",
        }, headers=h)

        # February: income 3000, expense 800
        api_post("/transactions", {
            "type": "income", "amount": 3000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-02-15", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 800.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-02-20", "time": "12:00:00",
        }, headers=h)

        resp = api_get("/statistics/monthly", params={"startMonth": "2024-01", "endMonth": "2024-02"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        jan = next(m for m in data if m["month"] == "2024-01")
        assert jan["totalIncome"] == 3000.00
        assert jan["totalExpense"] == 500.00
        assert jan["net"] == 2500.00

        feb = next(m for m in data if m["month"] == "2024-02")
        assert feb["totalIncome"] == 3000.00
        assert feb["totalExpense"] == 800.00
        assert feb["net"] == 2200.00

    def test_monthly_statistics_excludes_transfers(self):
        h, acct_id, inc_cat, exp_cat, xfer_cat = self._setup_stats_user()

        acct2_id = api_post("/accounts", {"name": "Savings", "type": "savings", "currency": "USD"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "income", "amount": 1000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-03-01", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "transfer", "amount": 200.00, "accountId": acct_id,
            "categoryId": xfer_cat, "destinationAccountId": acct2_id,
            "date": "2024-03-05", "time": "10:00:00",
        }, headers=h)

        resp = api_get("/statistics/monthly", params={"startMonth": "2024-03", "endMonth": "2024-03"}, headers=h)
        data = resp.json()
        assert len(data) == 1
        mar = data[0]
        assert mar["totalIncome"] == 1000.00
        assert mar["totalExpense"] == 0  # transfer not counted as expense
        assert mar["net"] == 1000.00

    def test_category_breakdown(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "CatBrk", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        food_cat = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        transport_cat = api_post("/categories", {"name": "Transport", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 100.00, "accountId": acct_id,
            "categoryId": food_cat, "date": "2024-04-10", "time": "12:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 50.00, "accountId": acct_id,
            "categoryId": food_cat, "date": "2024-04-15", "time": "12:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_id,
            "categoryId": transport_cat, "date": "2024-04-12", "time": "08:00:00",
        }, headers=h)

        resp = api_get("/statistics/category", params={"month": "2024-04", "type": "expense"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        food_entry = next((x for x in data if x["categoryId"] == food_cat), None)
        assert food_entry is not None
        assert food_entry["amount"] == 150.00
        assert food_entry["categoryName"] == "Food"

        transport_entry = next((x for x in data if x["categoryId"] == transport_cat), None)
        assert transport_entry is not None
        assert transport_entry["amount"] == 30.00

    def test_trends(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "Trends", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        inc_cat = api_post("/categories", {"name": "Inc", "type": "income"}, headers=h).json()["id"]
        exp_cat = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "income", "amount": 2000.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-05-01", "time": "09:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 500.00, "accountId": acct_id,
            "categoryId": exp_cat, "date": "2024-05-10", "time": "12:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "income", "amount": 2500.00, "accountId": acct_id,
            "categoryId": inc_cat, "date": "2024-06-01", "time": "09:00:00",
        }, headers=h)

        resp = api_get("/statistics/trends", params={"startMonth": "2024-05", "endMonth": "2024-06"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        may = next(m for m in data if m["month"] == "2024-05")
        assert may["totalIncome"] == 2000.00
        assert may["totalExpense"] == 500.00

        jun = next(m for m in data if m["month"] == "2024-06")
        assert jun["totalIncome"] == 2500.00
        assert jun["totalExpense"] == 0

    def test_statistics_empty_months_included(self):
        """Months with no transactions should still appear with zeros."""
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        resp = api_get("/statistics/monthly", params={"startMonth": "2024-07", "endMonth": "2024-09"}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for entry in data:
            assert entry["totalIncome"] == 0
            assert entry["totalExpense"] == 0
            assert entry["net"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 9: Exchange Rates
# ════════════════════════════════════════════════════════════════════


class TestExchangeRates:

    def test_get_exchange_rates_default(self):
        resp = api_get("/exchange-rates")
        assert resp.status_code == 200
        data = resp.json()
        assert "base" in data
        assert "rates" in data
        assert data["base"] == "USD"
        assert isinstance(data["rates"], dict)
        assert len(data["rates"]) > 0

    def test_get_exchange_rates_custom_base(self):
        resp = api_get("/exchange-rates", params={"base": "EUR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["base"] == "EUR"
        assert isinstance(data["rates"], dict)


# ════════════════════════════════════════════════════════════════════
# PART 10: CSV Export
# ════════════════════════════════════════════════════════════════════


class TestCSVExport:

    def test_export_csv(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "Export", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Food", "type": "expense"}, headers=h).json()["id"]
        tag_id = api_post("/tags", {"name": "lunch"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 25.50, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag_id],
            "date": "2024-04-15", "time": "12:30:00", "comment": "Business lunch",
        }, headers=h)

        resp = requests.get(f"{BASE_URL}/transactions/export", headers=h, timeout=30)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

        content = resp.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Header row
        header = rows[0]
        assert header == ["date", "type", "category", "account", "amount", "comment", "tags"]

        # Data row
        assert len(rows) >= 2
        data_row = rows[1]
        assert data_row[0] == "2024-04-15"
        assert data_row[1] == "expense"
        assert data_row[2] == "Food"
        assert data_row[3] == "Export"
        assert float(data_row[4]) == 25.50
        assert data_row[5] == "Business lunch"
        assert data_row[6] == "lunch"

    def test_export_csv_multiple_tags(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "Export2", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Food2", "type": "expense"}, headers=h).json()["id"]
        tag1_id = api_post("/tags", {"name": "alpha"}, headers=h).json()["id"]
        tag2_id = api_post("/tags", {"name": "beta"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag1_id, tag2_id],
            "date": "2024-04-15", "time": "12:00:00", "comment": "",
        }, headers=h)

        resp = requests.get(f"{BASE_URL}/transactions/export", headers=h, timeout=30)
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        data_row = rows[1]
        # Tags should be semicolon-separated
        tags = set(data_row[6].split(";"))
        assert tags == {"alpha", "beta"}

    def test_export_csv_empty(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}

        resp = requests.get(f"{BASE_URL}/transactions/export", headers=h, timeout=30)
        assert resp.status_code == 200
        content = resp.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        # Should have header row only
        assert len(rows) == 1
        assert rows[0] == ["date", "type", "category", "account", "amount", "comment", "tags"]

    def test_export_csv_filter_by_account(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct1 = api_post("/accounts", {"name": "Exp-A1", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        acct2 = api_post("/accounts", {"name": "Exp-A2", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Misc", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct1,
            "categoryId": cat_id, "date": "2024-04-15", "time": "12:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct2,
            "categoryId": cat_id, "date": "2024-04-16", "time": "12:00:00",
        }, headers=h)

        resp = requests.get(f"{BASE_URL}/transactions/export", params={"accountId": acct1}, headers=h, timeout=30)
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 data row
        assert rows[1][3] == "Exp-A1"


# ════════════════════════════════════════════════════════════════════
# PART 11: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_account_isolation(self):
        """User A's accounts are not visible to User B."""
        name = f"IsoAcct-{UNIQUE}"
        api_post("/accounts", {"name": name, "type": "cash", "currency": "USD"}, headers=HEADERS)

        resp = api_get("/accounts", headers=HEADERS2)
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert name not in names

    def test_category_isolation(self):
        """User A's categories are not visible to User B."""
        name = f"IsoCat-{UNIQUE}"
        api_post("/categories", {"name": name, "type": "expense"}, headers=HEADERS)

        resp = api_get("/categories", headers=HEADERS2)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert name not in names

    def test_tag_isolation(self):
        """User A's tags are not visible to User B."""
        name = f"IsoTag-{UNIQUE}"
        api_post("/tags", {"name": name}, headers=HEADERS)

        resp = api_get("/tags", headers=HEADERS2)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert name not in names

    def test_transaction_isolation(self):
        """User A's transactions are not visible to User B."""
        uid_a = str(uuid.uuid4())
        uid_b = str(uuid.uuid4())
        h_a = {"X-User-Id": uid_a, "Content-Type": "application/json"}
        h_b = {"X-User-Id": uid_b, "Content-Type": "application/json"}

        acct_id = api_post("/accounts", {"name": "IsoTxn", "type": "cash", "currency": "USD"}, headers=h_a).json()["id"]
        cat_id = api_post("/categories", {"name": "IsoExpense", "type": "expense"}, headers=h_a).json()["id"]
        api_post("/transactions", {
            "type": "expense", "amount": 99.99, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h_a)

        resp = api_get("/transactions", headers=h_b)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_cannot_access_other_users_account(self):
        """User B cannot GET User A's account by ID."""
        acct_resp = api_post("/accounts", {"name": f"ProtAcct-{UNIQUE}", "type": "cash", "currency": "USD"}, headers=HEADERS)
        acct_id = acct_resp.json()["id"]

        resp = api_get(f"/accounts/{acct_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_cannot_delete_other_users_account(self):
        """User B cannot DELETE User A's account."""
        acct_resp = api_post("/accounts", {"name": f"ProtDel-{UNIQUE}", "type": "cash", "currency": "USD"}, headers=HEADERS)
        acct_id = acct_resp.json()["id"]

        resp = api_delete(f"/accounts/{acct_id}", headers=HEADERS2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade & Deletion Rules
# ════════════════════════════════════════════════════════════════════


class TestDeletionRules:

    def test_cannot_delete_account_with_transactions(self):
        """Rule 10: Account with transactions cannot be deleted."""
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "HasTxn", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)

        resp = api_delete(f"/accounts/{acct_id}", headers=h)
        assert resp.status_code == 400

    def test_cannot_delete_account_used_as_destination(self):
        """Account used as destinationAccountId cannot be deleted."""
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        src = api_post("/accounts", {"name": "Src", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        dst = api_post("/accounts", {"name": "Dst", "type": "savings", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Xfer", "type": "transfer"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "transfer", "amount": 100.00, "accountId": src,
            "categoryId": cat_id, "destinationAccountId": dst,
            "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)

        resp = api_delete(f"/accounts/{dst}", headers=h)
        assert resp.status_code == 400

    def test_cannot_delete_category_with_transactions(self):
        """Rule 11: Category with transactions cannot be deleted."""
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "CatDel", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "UsedCat", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)

        resp = api_delete(f"/categories/{cat_id}", headers=h)
        assert resp.status_code == 400

    def test_delete_tag_removes_from_transactions(self):
        """Rule 12: Deleting a tag removes it from transactions but keeps the transaction."""
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "TagDel", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]
        tag_id = api_post("/tags", {"name": "removeme"}, headers=h).json()["id"]

        txn_resp = api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag_id],
            "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)
        txn_id = txn_resp.json()["id"]

        # Delete the tag
        api_delete(f"/tags/{tag_id}", headers=h)

        # Transaction should still exist but without the tag
        txn = api_get(f"/transactions/{txn_id}", headers=h).json()
        assert txn_id == txn["id"]
        assert tag_id not in txn["tagIds"]


# ════════════════════════════════════════════════════════════════════
# PART 13: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_accounts_list(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        resp = api_get("/accounts", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_categories_list(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        resp = api_get("/categories", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_tags_list(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        resp = api_get("/tags", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_transactions_list(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        resp = api_get("/transactions", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["transactions"] == []
        assert data["total"] == 0

    def test_transaction_with_nonexistent_account(self):
        cat_id = api_post("/categories", {"name": f"NoAcct-{UNIQUE}-{uuid.uuid4().hex[:4]}", "type": "expense"}).json()["id"]
        fake_acct = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": fake_acct,
            "categoryId": cat_id, "date": "2024-03-15", "time": "10:00:00",
        })
        assert resp.status_code == 400

    def test_transaction_with_nonexistent_category(self):
        acct_id = api_post("/accounts", {
            "name": f"NoCat-{UNIQUE}-{uuid.uuid4().hex[:4]}", "type": "cash", "currency": "USD"
        }).json()["id"]
        fake_cat = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": fake_cat, "date": "2024-03-15", "time": "10:00:00",
        })
        assert resp.status_code == 400

    def test_list_transactions_ordered_by_date_desc(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "Order", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]

        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-01-01", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-06-15", "time": "10:00:00",
        }, headers=h)
        api_post("/transactions", {
            "type": "expense", "amount": 30.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-10", "time": "10:00:00",
        }, headers=h)

        resp = api_get("/transactions", headers=h)
        txns = resp.json()["transactions"]
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True), f"Transactions not in date DESC order: {dates}"

    def test_filter_transactions_by_tag(self):
        uid = str(uuid.uuid4())
        h = {"X-User-Id": uid, "Content-Type": "application/json"}
        acct_id = api_post("/accounts", {"name": "TagFilter", "type": "checking", "currency": "USD"}, headers=h).json()["id"]
        cat_id = api_post("/categories", {"name": "Exp", "type": "expense"}, headers=h).json()["id"]
        tag_id = api_post("/tags", {"name": "special"}, headers=h).json()["id"]

        # With tag
        api_post("/transactions", {
            "type": "expense", "amount": 10.00, "accountId": acct_id,
            "categoryId": cat_id, "tagIds": [tag_id], "date": "2024-03-15", "time": "10:00:00",
        }, headers=h)
        # Without tag
        api_post("/transactions", {
            "type": "expense", "amount": 20.00, "accountId": acct_id,
            "categoryId": cat_id, "date": "2024-03-16", "time": "10:00:00",
        }, headers=h)

        resp = api_get("/transactions", params={"tagId": tag_id}, headers=h)
        data = resp.json()
        assert data["total"] == 1
        assert tag_id in data["transactions"][0]["tagIds"]
