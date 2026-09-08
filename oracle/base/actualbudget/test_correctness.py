"""
BackendForge — Comprehensive Correctness Tests for Actual Budget Task

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

HEADERS = {
    "X-User-Id": USER_ID,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
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

    def test_missing_header_returns_401_payees(self):
        resp = requests.get(f"{BASE_URL}/payees", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_rules(self):
        resp = requests.get(f"{BASE_URL}/rules", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_schedules(self):
        resp = requests.get(f"{BASE_URL}/schedules", timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        resp = requests.get(f"{BASE_URL}/accounts", headers={"X-User-Id": ""}, timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 2: Account CRUD
# ════════════════════════════════════════════════════════════════════


class TestAccountCRUD:

    def test_create_account(self):
        resp = api_post("/accounts", {"name": f"Checking-{UNIQUE}", "type": "checking"})
        assert resp.status_code == 201
        acct = resp.json()
        assert acct["name"] == f"Checking-{UNIQUE}"
        assert acct["type"] == "checking"
        assert acct["balance"] == 0
        assert acct["offBudget"] is False
        assert acct["closed"] is False
        assert "id" in acct

    def test_create_account_with_options(self):
        resp = api_post("/accounts", {
            "name": f"Investment-{UNIQUE}",
            "type": "investment",
            "offBudget": True,
        })
        assert resp.status_code == 201
        acct = resp.json()
        assert acct["type"] == "investment"
        assert acct["offBudget"] is True

    def test_create_account_invalid_type(self):
        resp = api_post("/accounts", {"name": f"Bad-{UNIQUE}", "type": "invalid_type"})
        assert resp.status_code == 400

    def test_list_accounts(self):
        name = f"ListAcct-{UNIQUE}"
        api_post("/accounts", {"name": name, "type": "savings"})
        resp = api_get("/accounts")
        assert resp.status_code == 200
        accounts = resp.json()
        assert isinstance(accounts, list)
        names = [a["name"] for a in accounts]
        assert name in names

    def test_get_account(self):
        create_resp = api_post("/accounts", {"name": f"GetAcct-{UNIQUE}", "type": "cash"})
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
        create_resp = api_post("/accounts", {"name": f"UpdAcct-{UNIQUE}", "type": "checking"})
        acct_id = create_resp.json()["id"]

        resp = api_put(f"/accounts/{acct_id}", {
            "name": f"UpdatedAcct-{UNIQUE}",
            "closed": True,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedAcct-{UNIQUE}"
        assert resp.json()["closed"] is True

    def test_update_account_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_put(f"/accounts/{fake_id}", {"name": "ghost"})
        assert resp.status_code == 404

    def test_delete_account(self):
        create_resp = api_post("/accounts", {"name": f"DelAcct-{UNIQUE}", "type": "checking"})
        acct_id = create_resp.json()["id"]

        resp = api_delete(f"/accounts/{acct_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/accounts/{acct_id}")
        assert get_resp.status_code == 404

    def test_delete_account_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_duplicate_account_name(self):
        name = f"DupAcct-{UNIQUE}"
        resp1 = api_post("/accounts", {"name": name, "type": "checking"})
        assert resp1.status_code == 201
        resp2 = api_post("/accounts", {"name": name, "type": "savings"})
        assert resp2.status_code == 400

    def test_account_balance_computed_from_transactions(self):
        """Balance should be the sum of all transactions."""
        acct_resp = api_post("/accounts", {"name": f"BalAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        # Create transactions
        api_post("/transactions", {"date": "2024-01-15", "amount": 5000, "accountId": acct_id})
        api_post("/transactions", {"date": "2024-01-16", "amount": -1500, "accountId": acct_id})

        resp = api_get(f"/accounts/{acct_id}")
        assert resp.status_code == 200
        assert resp.json()["balance"] == 3500


# ════════════════════════════════════════════════════════════════════
# PART 3: Category Group CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryGroupCRUD:

    def test_create_category_group(self):
        resp = api_post("/category-groups", {"name": f"Bills-{UNIQUE}"})
        assert resp.status_code == 201
        group = resp.json()
        assert group["name"] == f"Bills-{UNIQUE}"
        assert group["isIncome"] is False
        assert group["sortOrder"] == 0
        assert group["categories"] == []
        assert "id" in group

    def test_create_income_group(self):
        resp = api_post("/category-groups", {
            "name": f"Income-{UNIQUE}",
            "isIncome": True,
            "sortOrder": 1,
        })
        assert resp.status_code == 201
        group = resp.json()
        assert group["isIncome"] is True
        assert group["sortOrder"] == 1

    def test_list_category_groups(self):
        name = f"ListGrp-{UNIQUE}"
        api_post("/category-groups", {"name": name})
        resp = api_get("/category-groups")
        assert resp.status_code == 200
        groups = resp.json()
        assert isinstance(groups, list)
        names = [g["name"] for g in groups]
        assert name in names

    def test_get_category_group(self):
        create_resp = api_post("/category-groups", {"name": f"GetGrp-{UNIQUE}"})
        group_id = create_resp.json()["id"]

        resp = api_get(f"/category-groups/{group_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == group_id

    def test_get_category_group_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/category-groups/{fake_id}")
        assert resp.status_code == 404

    def test_update_category_group(self):
        create_resp = api_post("/category-groups", {"name": f"UpdGrp-{UNIQUE}"})
        group_id = create_resp.json()["id"]

        resp = api_put(f"/category-groups/{group_id}", {
            "name": f"UpdatedGrp-{UNIQUE}",
            "sortOrder": 5,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedGrp-{UNIQUE}"
        assert resp.json()["sortOrder"] == 5

    def test_delete_category_group(self):
        create_resp = api_post("/category-groups", {"name": f"DelGrp-{UNIQUE}"})
        group_id = create_resp.json()["id"]

        resp = api_delete(f"/category-groups/{group_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/category-groups/{group_id}")
        assert get_resp.status_code == 404

    def test_duplicate_group_name(self):
        name = f"DupGrp-{UNIQUE}"
        resp1 = api_post("/category-groups", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/category-groups", {"name": name})
        assert resp2.status_code == 400

    def test_category_group_includes_categories(self):
        """Category groups should include nested categories."""
        group_resp = api_post("/category-groups", {"name": f"NestGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]

        api_post("/categories", {"name": f"NestCat-{UNIQUE}", "groupId": group_id})

        resp = api_get(f"/category-groups/{group_id}")
        assert resp.status_code == 200
        group = resp.json()
        assert len(group["categories"]) >= 1
        cat_names = [c["name"] for c in group["categories"]]
        assert f"NestCat-{UNIQUE}" in cat_names


# ════════════════════════════════════════════════════════════════════
# PART 4: Category CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryCRUD:

    def test_create_category(self):
        group_resp = api_post("/category-groups", {"name": f"CatGrp-{UNIQUE}-create"})
        group_id = group_resp.json()["id"]

        resp = api_post("/categories", {
            "name": f"Groceries-{UNIQUE}",
            "groupId": group_id,
        })
        assert resp.status_code == 201
        cat = resp.json()
        assert cat["name"] == f"Groceries-{UNIQUE}"
        assert cat["groupId"] == group_id
        assert cat["isIncome"] is False
        assert "id" in cat

    def test_create_income_category(self):
        group_resp = api_post("/category-groups", {"name": f"IncGrp-{UNIQUE}-cat", "isIncome": True})
        group_id = group_resp.json()["id"]

        resp = api_post("/categories", {
            "name": f"Salary-{UNIQUE}",
            "groupId": group_id,
            "isIncome": True,
        })
        assert resp.status_code == 201
        assert resp.json()["isIncome"] is True

    def test_list_categories(self):
        group_resp = api_post("/category-groups", {"name": f"ListCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        api_post("/categories", {"name": f"ListCat-{UNIQUE}", "groupId": group_id})

        resp = api_get("/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        names = [c["name"] for c in cats]
        assert f"ListCat-{UNIQUE}" in names

    def test_get_category(self):
        group_resp = api_post("/category-groups", {"name": f"GetCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        create_resp = api_post("/categories", {"name": f"GetCat-{UNIQUE}", "groupId": group_id})
        cat_id = create_resp.json()["id"]

        resp = api_get(f"/categories/{cat_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cat_id

    def test_get_category_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/categories/{fake_id}")
        assert resp.status_code == 404

    def test_update_category(self):
        group_resp = api_post("/category-groups", {"name": f"UpdCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        create_resp = api_post("/categories", {"name": f"UpdCat-{UNIQUE}", "groupId": group_id})
        cat_id = create_resp.json()["id"]

        resp = api_put(f"/categories/{cat_id}", {
            "name": f"UpdatedCat-{UNIQUE}",
            "sortOrder": 3,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedCat-{UNIQUE}"
        assert resp.json()["sortOrder"] == 3

    def test_delete_category(self):
        group_resp = api_post("/category-groups", {"name": f"DelCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        create_resp = api_post("/categories", {"name": f"DelCat-{UNIQUE}", "groupId": group_id})
        cat_id = create_resp.json()["id"]

        resp = api_delete(f"/categories/{cat_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/categories/{cat_id}")
        assert get_resp.status_code == 404

    def test_duplicate_category_name_in_group(self):
        group_resp = api_post("/category-groups", {"name": f"DupCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        name = f"DupCat-{UNIQUE}"
        resp1 = api_post("/categories", {"name": name, "groupId": group_id})
        assert resp1.status_code == 201
        resp2 = api_post("/categories", {"name": name, "groupId": group_id})
        assert resp2.status_code == 400

    def test_cascade_delete_group_deletes_categories(self):
        group_resp = api_post("/category-groups", {"name": f"CascGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"CascCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        api_delete(f"/category-groups/{group_id}")

        get_resp = api_get(f"/categories/{cat_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Payee CRUD
# ════════════════════════════════════════════════════════════════════


class TestPayeeCRUD:

    def test_create_payee(self):
        resp = api_post("/payees", {"name": f"Uber-{UNIQUE}"})
        assert resp.status_code == 201
        payee = resp.json()
        assert payee["name"] == f"Uber-{UNIQUE}"
        assert "id" in payee

    def test_create_payee_with_category(self):
        group_resp = api_post("/category-groups", {"name": f"PayeeCatGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"PayeeCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/payees", {"name": f"UberCat-{UNIQUE}", "categoryId": cat_id})
        assert resp.status_code == 201
        assert resp.json()["categoryId"] == cat_id

    def test_list_payees(self):
        name = f"ListPayee-{UNIQUE}"
        api_post("/payees", {"name": name})
        resp = api_get("/payees")
        assert resp.status_code == 200
        payees = resp.json()
        assert isinstance(payees, list)
        names = [p["name"] for p in payees]
        assert name in names

    def test_get_payee(self):
        create_resp = api_post("/payees", {"name": f"GetPayee-{UNIQUE}"})
        payee_id = create_resp.json()["id"]

        resp = api_get(f"/payees/{payee_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == payee_id

    def test_get_payee_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/payees/{fake_id}")
        assert resp.status_code == 404

    def test_update_payee(self):
        create_resp = api_post("/payees", {"name": f"UpdPayee-{UNIQUE}"})
        payee_id = create_resp.json()["id"]

        resp = api_put(f"/payees/{payee_id}", {"name": f"UpdatedPayee-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedPayee-{UNIQUE}"

    def test_delete_payee(self):
        create_resp = api_post("/payees", {"name": f"DelPayee-{UNIQUE}"})
        payee_id = create_resp.json()["id"]

        resp = api_delete(f"/payees/{payee_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/payees/{payee_id}")
        assert get_resp.status_code == 404

    def test_duplicate_payee_name(self):
        name = f"DupPayee-{UNIQUE}"
        resp1 = api_post("/payees", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/payees", {"name": name})
        assert resp2.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 6: Transaction CRUD
# ════════════════════════════════════════════════════════════════════


class TestTransactionCRUD:

    def test_create_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"TxAcct-{UNIQUE}-create", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -2500,
            "accountId": acct_id,
            "notes": "Lunch",
        })
        assert resp.status_code == 201
        tx = resp.json()
        assert tx["date"] == "2024-03-15"
        assert tx["amount"] == -2500
        assert tx["accountId"] == acct_id
        assert tx["notes"] == "Lunch"
        assert tx["cleared"] is False
        assert "id" in tx

    def test_create_transaction_invalid_account(self):
        fake_id = str(uuid.uuid4())
        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -1000,
            "accountId": fake_id,
        })
        assert resp.status_code == 400

    def test_list_transactions(self):
        acct_resp = api_post("/accounts", {"name": f"TxAcct-{UNIQUE}-list", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        api_post("/transactions", {"date": "2024-03-15", "amount": -500, "accountId": acct_id})

        resp = api_get("/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["data"], list)

    def test_get_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"TxAcct-{UNIQUE}-get", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"date": "2024-03-15", "amount": -800, "accountId": acct_id})
        tx_id = create_resp.json()["id"]

        resp = api_get(f"/transactions/{tx_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tx_id

    def test_get_transaction_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/transactions/{fake_id}")
        assert resp.status_code == 404

    def test_update_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"TxAcct-{UNIQUE}-upd", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"date": "2024-03-15", "amount": -800, "accountId": acct_id})
        tx_id = create_resp.json()["id"]

        resp = api_put(f"/transactions/{tx_id}", {
            "amount": -900,
            "cleared": True,
            "notes": "Updated note",
        })
        assert resp.status_code == 200
        assert resp.json()["amount"] == -900
        assert resp.json()["cleared"] is True
        assert resp.json()["notes"] == "Updated note"

    def test_delete_transaction(self):
        acct_resp = api_post("/accounts", {"name": f"TxAcct-{UNIQUE}-del", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/transactions", {"date": "2024-03-15", "amount": -800, "accountId": acct_id})
        tx_id = create_resp.json()["id"]

        resp = api_delete(f"/transactions/{tx_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/transactions/{tx_id}")
        assert get_resp.status_code == 404

    def test_delete_transaction_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_delete(f"/transactions/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Transaction Filtering & Pagination
# ════════════════════════════════════════════════════════════════════


class TestTransactionFiltering:

    def test_filter_by_account(self):
        acct1_resp = api_post("/accounts", {"name": f"FilterAcct1-{UNIQUE}", "type": "checking"})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"FilterAcct2-{UNIQUE}", "type": "savings"})
        acct2_id = acct2_resp.json()["id"]

        api_post("/transactions", {"date": "2024-04-01", "amount": -100, "accountId": acct1_id})
        api_post("/transactions", {"date": "2024-04-01", "amount": -200, "accountId": acct2_id})

        resp = api_get("/transactions", params={"accountId": acct1_id})
        assert resp.status_code == 200
        data = resp.json()
        for tx in data["data"]:
            assert tx["accountId"] == acct1_id

    def test_filter_by_date_range(self):
        acct_resp = api_post("/accounts", {"name": f"DateAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        api_post("/transactions", {"date": "2024-01-15", "amount": -100, "accountId": acct_id})
        api_post("/transactions", {"date": "2024-03-15", "amount": -200, "accountId": acct_id})
        api_post("/transactions", {"date": "2024-06-15", "amount": -300, "accountId": acct_id})

        resp = api_get("/transactions", params={
            "accountId": acct_id,
            "startDate": "2024-02-01",
            "endDate": "2024-04-30",
        })
        assert resp.status_code == 200
        data = resp.json()
        for tx in data["data"]:
            assert "2024-02-01" <= tx["date"] <= "2024-04-30"

    def test_pagination_limit_offset(self):
        acct_resp = api_post("/accounts", {"name": f"PagAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        for i in range(5):
            api_post("/transactions", {"date": f"2024-05-{10+i:02d}", "amount": -(i+1)*100, "accountId": acct_id})

        resp = api_get("/transactions", params={"accountId": acct_id, "limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert data["total"] >= 5

    def test_pagination_offset(self):
        acct_resp = api_post("/accounts", {"name": f"OffAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        for i in range(5):
            api_post("/transactions", {"date": f"2024-06-{10+i:02d}", "amount": -(i+1)*100, "accountId": acct_id})

        resp1 = api_get("/transactions", params={"accountId": acct_id, "limit": 3, "offset": 0})
        resp2 = api_get("/transactions", params={"accountId": acct_id, "limit": 3, "offset": 3})
        data1 = resp1.json()
        data2 = resp2.json()
        ids1 = [tx["id"] for tx in data1["data"]]
        ids2 = [tx["id"] for tx in data2["data"]]
        # No overlap
        assert not set(ids1).intersection(set(ids2))


# ════════════════════════════════════════════════════════════════════
# PART 8: Transfers
# ════════════════════════════════════════════════════════════════════


class TestTransfers:

    def test_create_transfer(self):
        """Creating a transfer should create a mirror transaction."""
        acct1_resp = api_post("/accounts", {"name": f"TransAcct1-{UNIQUE}", "type": "checking"})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"TransAcct2-{UNIQUE}", "type": "savings"})
        acct2_id = acct2_resp.json()["id"]

        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -5000,
            "accountId": acct1_id,
            "transferAccountId": acct2_id,
        })
        assert resp.status_code == 201
        tx = resp.json()
        assert tx["transferAccountId"] == acct2_id
        assert tx["transferTransactionId"] is not None

        # Mirror transaction should exist
        mirror_id = tx["transferTransactionId"]
        mirror_resp = api_get(f"/transactions/{mirror_id}")
        assert mirror_resp.status_code == 200
        mirror = mirror_resp.json()
        assert mirror["amount"] == 5000  # negated
        assert mirror["accountId"] == acct2_id
        assert mirror["transferAccountId"] == acct1_id
        assert mirror["transferTransactionId"] == tx["id"]

    def test_transfer_affects_both_balances(self):
        """Transfer should affect balances of both accounts."""
        acct1_resp = api_post("/accounts", {"name": f"BalTrans1-{UNIQUE}", "type": "checking"})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"BalTrans2-{UNIQUE}", "type": "savings"})
        acct2_id = acct2_resp.json()["id"]

        # Add initial balance
        api_post("/transactions", {"date": "2024-01-01", "amount": 10000, "accountId": acct1_id})

        # Transfer 3000 from checking to savings
        api_post("/transactions", {
            "date": "2024-01-15",
            "amount": -3000,
            "accountId": acct1_id,
            "transferAccountId": acct2_id,
        })

        acct1 = api_get(f"/accounts/{acct1_id}").json()
        acct2 = api_get(f"/accounts/{acct2_id}").json()
        assert acct1["balance"] == 7000
        assert acct2["balance"] == 3000

    def test_delete_transfer_deletes_mirror(self):
        """Deleting a transfer should also delete the mirror transaction."""
        acct1_resp = api_post("/accounts", {"name": f"DelTrans1-{UNIQUE}", "type": "checking"})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"DelTrans2-{UNIQUE}", "type": "savings"})
        acct2_id = acct2_resp.json()["id"]

        tx_resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -2000,
            "accountId": acct1_id,
            "transferAccountId": acct2_id,
        })
        tx_id = tx_resp.json()["id"]
        mirror_id = tx_resp.json()["transferTransactionId"]

        # Delete original
        api_delete(f"/transactions/{tx_id}")

        # Mirror should be gone too
        mirror_resp = api_get(f"/transactions/{mirror_id}")
        assert mirror_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Budgets
# ════════════════════════════════════════════════════════════════════


class TestBudgets:

    def test_set_and_get_budget(self):
        group_resp = api_post("/category-groups", {"name": f"BudGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"BudCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        # Set budget
        resp = api_put(f"/budgets/2024-03/categories/{cat_id}", {"amount": 50000})
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["categoryId"] == cat_id
        assert detail["budgeted"] == 50000

        # Get budget
        resp = api_get(f"/budgets/2024-03/categories/{cat_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["budgeted"] == 50000

    def test_budget_available_calculation(self):
        """available = budgeted - spent"""
        group_resp = api_post("/category-groups", {"name": f"AvailGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"AvailCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"AvailAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        # Set budget to 30000 cents ($300)
        api_put(f"/budgets/2024-04/categories/{cat_id}", {"amount": 30000})

        # Spend 10000 cents ($100) and 5000 cents ($50)
        api_post("/transactions", {
            "date": "2024-04-10",
            "amount": -10000,
            "accountId": acct_id,
            "categoryId": cat_id,
        })
        api_post("/transactions", {
            "date": "2024-04-15",
            "amount": -5000,
            "accountId": acct_id,
            "categoryId": cat_id,
        })

        resp = api_get(f"/budgets/2024-04/categories/{cat_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["budgeted"] == 30000
        assert detail["spent"] == 15000  # absolute value of sum of negatives
        assert detail["available"] == 15000  # 30000 - 15000

    def test_get_budget_month(self):
        """GET /budgets/{month} returns all categories with budget info."""
        group_resp = api_post("/category-groups", {"name": f"MonthGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"MonthCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        api_put(f"/budgets/2024-05/categories/{cat_id}", {"amount": 20000})

        resp = api_get("/budgets/2024-05")
        assert resp.status_code == 200
        data = resp.json()
        assert data["month"] == "2024-05"
        assert isinstance(data["categories"], list)
        cat_ids = [c["categoryId"] for c in data["categories"]]
        assert cat_id in cat_ids

    def test_budget_nonexistent_category(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/budgets/2024-03/categories/{fake_id}")
        assert resp.status_code == 404

    def test_budget_only_counts_negative_transactions(self):
        """Spent should only count negative transactions."""
        group_resp = api_post("/category-groups", {"name": f"NegGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"NegCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"NegAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        api_put(f"/budgets/2024-07/categories/{cat_id}", {"amount": 10000})

        # One negative, one positive
        api_post("/transactions", {"date": "2024-07-05", "amount": -3000, "accountId": acct_id, "categoryId": cat_id})
        api_post("/transactions", {"date": "2024-07-10", "amount": 1000, "accountId": acct_id, "categoryId": cat_id})

        resp = api_get(f"/budgets/2024-07/categories/{cat_id}")
        detail = resp.json()
        assert detail["spent"] == 3000  # only counts the negative
        assert detail["available"] == 7000  # 10000 - 3000


# ════════════════════════════════════════════════════════════════════
# PART 10: Rules
# ════════════════════════════════════════════════════════════════════


class TestRules:

    def test_create_rule(self):
        group_resp = api_post("/category-groups", {"name": f"RuleGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"Transport-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Uber"}],
            "actions": [{"field": "category", "value": cat_id}],
        })
        assert resp.status_code == 201
        rule = resp.json()
        assert "id" in rule
        assert len(rule["conditions"]) == 1
        assert rule["conditions"][0]["field"] == "payee"
        assert rule["conditions"][0]["op"] == "contains"
        assert rule["conditions"][0]["value"] == "Uber"
        assert len(rule["actions"]) == 1
        assert rule["actions"][0]["field"] == "category"
        assert rule["actions"][0]["value"] == cat_id

    def test_list_rules(self):
        group_resp = api_post("/category-groups", {"name": f"ListRuleGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"ListRuleCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "is", "value": "Netflix"}],
            "actions": [{"field": "category", "value": cat_id}],
        })

        resp = api_get("/rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert isinstance(rules, list)
        assert len(rules) >= 1

    def test_get_rule(self):
        group_resp = api_post("/category-groups", {"name": f"GetRuleGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"GetRuleCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/rules", {
            "conditions": [{"field": "notes", "op": "contains", "value": "test"}],
            "actions": [{"field": "category", "value": cat_id}],
        })
        rule_id = create_resp.json()["id"]

        resp = api_get(f"/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rule_id

    def test_get_rule_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/rules/{fake_id}")
        assert resp.status_code == 404

    def test_update_rule(self):
        group_resp = api_post("/category-groups", {"name": f"UpdRuleGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"UpdRuleCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/rules", {
            "conditions": [{"field": "payee", "op": "is", "value": "old"}],
            "actions": [{"field": "category", "value": cat_id}],
        })
        rule_id = create_resp.json()["id"]

        resp = api_put(f"/rules/{rule_id}", {
            "conditions": [{"field": "payee", "op": "contains", "value": "new"}],
            "actions": [{"field": "category", "value": cat_id}],
        })
        assert resp.status_code == 200
        assert resp.json()["conditions"][0]["value"] == "new"

    def test_delete_rule(self):
        group_resp = api_post("/category-groups", {"name": f"DelRuleGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"DelRuleCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/rules", {
            "conditions": [{"field": "payee", "op": "is", "value": "x"}],
            "actions": [{"field": "category", "value": cat_id}],
        })
        rule_id = create_resp.json()["id"]

        resp = api_delete(f"/rules/{rule_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/rules/{rule_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Rule Auto-Apply on Transaction Creation
# ════════════════════════════════════════════════════════════════════


class TestRuleAutoApply:

    def test_rule_sets_category_on_create(self):
        """When creating a transaction matching a rule, category should be auto-set."""
        # Use a fresh user to avoid interference from rules created by other tests
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"AutoGrp-{UNIQUE}"}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"AutoCat-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"AutoAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]
        payee_resp = api_post("/payees", {"name": f"Uber Rides {UNIQUE}"}, headers=iso_headers)
        payee_id = payee_resp.json()["id"]

        # Create rule: if payee contains "Uber" -> set category
        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Uber"}],
            "actions": [{"field": "category", "value": cat_id}],
        }, headers=iso_headers)

        # Create transaction without category
        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -2500,
            "accountId": acct_id,
            "payeeId": payee_id,
        }, headers=iso_headers)
        assert resp.status_code == 201
        tx = resp.json()
        assert tx["categoryId"] == cat_id

    def test_rule_does_not_apply_on_update(self):
        """Rules should only fire on creation, not on update."""
        # Use a fresh user to avoid interference
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"NoUpdGrp-{UNIQUE}"}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"NoUpdCat-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"NoUpdAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]
        payee_resp = api_post("/payees", {"name": f"Lyft {UNIQUE}"}, headers=iso_headers)
        payee_id = payee_resp.json()["id"]

        # Create rule: if payee contains "Lyft" -> set category
        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Lyft"}],
            "actions": [{"field": "category", "value": cat_id}],
        }, headers=iso_headers)

        # Create transaction without the payee (no rule match)
        other_payee_resp = api_post("/payees", {"name": f"Grocers {UNIQUE}"}, headers=iso_headers)
        other_payee_id = other_payee_resp.json()["id"]
        tx_resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -1500,
            "accountId": acct_id,
            "payeeId": other_payee_id,
        }, headers=iso_headers)
        tx_id = tx_resp.json()["id"]

        # Update to change payee to Lyft — rule should NOT fire
        api_put(f"/transactions/{tx_id}", {"payeeId": payee_id}, headers=iso_headers)
        updated = api_get(f"/transactions/{tx_id}", headers=iso_headers).json()
        # categoryId should still be None (rule did not fire on update)
        assert updated.get("categoryId") is None

    def test_rule_conditions_all_must_match(self):
        """All conditions in a rule must match (AND logic)."""
        # Use a fresh user to avoid interference
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"AndGrp-{UNIQUE}"}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"AndCat-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"AndAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]
        payee_resp = api_post("/payees", {"name": f"Amazon {UNIQUE}"}, headers=iso_headers)
        payee_id = payee_resp.json()["id"]

        # Rule: payee contains "Amazon" AND amount < -5000
        api_post("/rules", {
            "conditions": [
                {"field": "payee", "op": "contains", "value": "Amazon"},
                {"field": "amount", "op": "lt", "value": "-5000"},
            ],
            "actions": [{"field": "category", "value": cat_id}],
        }, headers=iso_headers)

        # Small Amazon purchase — should NOT match (amount > -5000)
        resp1 = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -2000,
            "accountId": acct_id,
            "payeeId": payee_id,
        }, headers=iso_headers)
        assert resp1.json().get("categoryId") is None

        # Large Amazon purchase — should match
        resp2 = api_post("/transactions", {
            "date": "2024-03-16",
            "amount": -10000,
            "accountId": acct_id,
            "payeeId": payee_id,
        }, headers=iso_headers)
        assert resp2.json()["categoryId"] == cat_id

    def test_payee_default_category(self):
        """If payee has default category and no rule matches, use payee's category."""
        # Use a fresh user to avoid interference from rules
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"DefCatGrp-{UNIQUE}"}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"DefCatCat-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"DefCatAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]
        payee_resp = api_post("/payees", {"name": f"Starbucks {UNIQUE}", "categoryId": cat_id}, headers=iso_headers)
        payee_id = payee_resp.json()["id"]

        # No matching rule exists; should use payee's default category
        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -500,
            "accountId": acct_id,
            "payeeId": payee_id,
        }, headers=iso_headers)
        assert resp.status_code == 201
        assert resp.json()["categoryId"] == cat_id

    def test_rule_takes_precedence_over_payee_default(self):
        """Rules should override payee default category."""
        # Use a fresh user to avoid interference
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"PrecGrp-{UNIQUE}"}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        cat1_resp = api_post("/categories", {"name": f"PrecCat1-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat1_id = cat1_resp.json()["id"]
        cat2_resp = api_post("/categories", {"name": f"PrecCat2-{UNIQUE}", "groupId": group_id}, headers=iso_headers)
        cat2_id = cat2_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"PrecAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]

        # Payee with default category cat1
        payee_resp = api_post("/payees", {"name": f"RulePayee {UNIQUE}", "categoryId": cat1_id}, headers=iso_headers)
        payee_id = payee_resp.json()["id"]

        # Rule: payee contains "RulePayee" -> set category cat2
        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "RulePayee"}],
            "actions": [{"field": "category", "value": cat2_id}],
        }, headers=iso_headers)

        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -500,
            "accountId": acct_id,
            "payeeId": payee_id,
        }, headers=iso_headers)
        assert resp.status_code == 201
        assert resp.json()["categoryId"] == cat2_id  # rule wins


# ════════════════════════════════════════════════════════════════════
# PART 12: Schedules
# ════════════════════════════════════════════════════════════════════


class TestSchedules:

    def test_create_schedule(self):
        acct_resp = api_post("/accounts", {"name": f"SchedAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        resp = api_post("/schedules", {
            "name": f"Rent-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-04-01",
            "amount": -150000,
            "accountId": acct_id,
        })
        assert resp.status_code == 201
        sched = resp.json()
        assert sched["name"] == f"Rent-{UNIQUE}"
        assert sched["frequency"] == "monthly"
        assert sched["nextDate"] == "2024-04-01"
        assert sched["amount"] == -150000
        assert sched["accountId"] == acct_id
        assert "id" in sched

    def test_list_schedules(self):
        acct_resp = api_post("/accounts", {"name": f"SchedList-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        api_post("/schedules", {
            "name": f"ListSched-{UNIQUE}",
            "frequency": "weekly",
            "nextDate": "2024-04-01",
            "amount": -5000,
            "accountId": acct_id,
        })

        resp = api_get("/schedules")
        assert resp.status_code == 200
        schedules = resp.json()
        assert isinstance(schedules, list)
        names = [s["name"] for s in schedules]
        assert f"ListSched-{UNIQUE}" in names

    def test_get_schedule(self):
        acct_resp = api_post("/accounts", {"name": f"SchedGet-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"GetSched-{UNIQUE}",
            "frequency": "yearly",
            "nextDate": "2024-12-25",
            "amount": -20000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        resp = api_get(f"/schedules/{sched_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sched_id

    def test_get_schedule_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/schedules/{fake_id}")
        assert resp.status_code == 404

    def test_update_schedule(self):
        acct_resp = api_post("/accounts", {"name": f"SchedUpd-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"UpdSched-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-04-01",
            "amount": -5000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        resp = api_put(f"/schedules/{sched_id}", {
            "amount": -6000,
            "frequency": "weekly",
        })
        assert resp.status_code == 200
        assert resp.json()["amount"] == -6000
        assert resp.json()["frequency"] == "weekly"

    def test_delete_schedule(self):
        acct_resp = api_post("/accounts", {"name": f"SchedDel-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"DelSched-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-04-01",
            "amount": -5000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        resp = api_delete(f"/schedules/{sched_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/schedules/{sched_id}")
        assert get_resp.status_code == 404

    def test_post_transaction_monthly(self):
        """Posting a schedule should create a transaction and advance nextDate."""
        acct_resp = api_post("/accounts", {"name": f"PostSched-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"PostMon-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-03-15",
            "amount": -10000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        resp = api_post(f"/schedules/{sched_id}/post-transaction")
        assert resp.status_code == 201
        tx = resp.json()
        assert tx["date"] == "2024-03-15"
        assert tx["amount"] == -10000
        assert tx["accountId"] == acct_id

        # Schedule nextDate should advance to 2024-04-15
        sched = api_get(f"/schedules/{sched_id}").json()
        assert sched["nextDate"] == "2024-04-15"

    def test_post_transaction_weekly(self):
        acct_resp = api_post("/accounts", {"name": f"PostWeek-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"PostWk-{UNIQUE}",
            "frequency": "weekly",
            "nextDate": "2024-03-11",
            "amount": -3000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        api_post(f"/schedules/{sched_id}/post-transaction")

        sched = api_get(f"/schedules/{sched_id}").json()
        assert sched["nextDate"] == "2024-03-18"  # +7 days

    def test_post_transaction_yearly(self):
        acct_resp = api_post("/accounts", {"name": f"PostYear-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"PostYr-{UNIQUE}",
            "frequency": "yearly",
            "nextDate": "2024-06-01",
            "amount": -100000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        api_post(f"/schedules/{sched_id}/post-transaction")

        sched = api_get(f"/schedules/{sched_id}").json()
        assert sched["nextDate"] == "2025-06-01"  # +1 year

    def test_post_transaction_month_end_handling(self):
        """Jan 31 + 1 month = Feb 28 (or 29 in leap year)."""
        acct_resp = api_post("/accounts", {"name": f"PostEnd-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        create_resp = api_post("/schedules", {
            "name": f"PostEndM-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-01-31",
            "amount": -5000,
            "accountId": acct_id,
        })
        sched_id = create_resp.json()["id"]

        api_post(f"/schedules/{sched_id}/post-transaction")

        sched = api_get(f"/schedules/{sched_id}").json()
        # 2024 is a leap year, so Feb has 29 days
        assert sched["nextDate"] == "2024-02-29"


# ════════════════════════════════════════════════════════════════════
# PART 13: Reports
# ════════════════════════════════════════════════════════════════════


class TestReports:

    def test_spending_by_category(self):
        group_resp = api_post("/category-groups", {"name": f"RptGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"RptCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"RptAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        api_post("/transactions", {
            "date": "2024-03-10",
            "amount": -5000,
            "accountId": acct_id,
            "categoryId": cat_id,
        })
        api_post("/transactions", {
            "date": "2024-03-20",
            "amount": -3000,
            "accountId": acct_id,
            "categoryId": cat_id,
        })

        resp = api_get("/reports/spending-by-category", params={
            "startDate": "2024-03-01",
            "endDate": "2024-03-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["startDate"] == "2024-03-01"
        assert data["endDate"] == "2024-03-31"
        assert isinstance(data["categories"], list)

        # Find our category
        found = [c for c in data["categories"] if c["categoryId"] == cat_id]
        assert len(found) == 1
        assert found[0]["spent"] == 8000  # abs(-5000 + -3000)

    def test_net_worth_report(self):
        acct_resp = api_post("/accounts", {"name": f"NwAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        api_post("/transactions", {"date": "2024-01-15", "amount": 100000, "accountId": acct_id})
        api_post("/transactions", {"date": "2024-02-15", "amount": -20000, "accountId": acct_id})

        resp = api_get("/reports/net-worth", params={
            "startMonth": "2024-01",
            "endMonth": "2024-03",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["startMonth"] == "2024-01"
        assert data["endMonth"] == "2024-03"
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

        # Each data point has month and netWorth
        for point in data["data"]:
            assert "month" in point
            assert "netWorth" in point

    def test_income_vs_expenses_report(self):
        # Use a fresh user to avoid interference from other tests' transactions
        iso_user = str(uuid.uuid4())
        iso_headers = {"X-User-Id": iso_user, "Content-Type": "application/json"}

        group_resp = api_post("/category-groups", {"name": f"IvEGrp-{UNIQUE}", "isIncome": True}, headers=iso_headers)
        group_id = group_resp.json()["id"]
        inc_cat_resp = api_post("/categories", {
            "name": f"IvEInc-{UNIQUE}", "groupId": group_id, "isIncome": True,
        }, headers=iso_headers)
        inc_cat_id = inc_cat_resp.json()["id"]

        exp_grp_resp = api_post("/category-groups", {"name": f"IvEExpGrp-{UNIQUE}"}, headers=iso_headers)
        exp_grp_id = exp_grp_resp.json()["id"]
        exp_cat_resp = api_post("/categories", {"name": f"IvEExp-{UNIQUE}", "groupId": exp_grp_id}, headers=iso_headers)
        exp_cat_id = exp_cat_resp.json()["id"]

        acct_resp = api_post("/accounts", {"name": f"IvEAcct-{UNIQUE}", "type": "checking"}, headers=iso_headers)
        acct_id = acct_resp.json()["id"]

        # Income transaction
        api_post("/transactions", {
            "date": "2024-03-01",
            "amount": 500000,
            "accountId": acct_id,
            "categoryId": inc_cat_id,
        }, headers=iso_headers)
        # Expense transaction
        api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -80000,
            "accountId": acct_id,
            "categoryId": exp_cat_id,
        }, headers=iso_headers)

        resp = api_get("/reports/income-vs-expenses", params={
            "startMonth": "2024-03",
            "endMonth": "2024-03",
        }, headers=iso_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["startMonth"] == "2024-03"
        assert data["endMonth"] == "2024-03"
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

        march = [d for d in data["data"] if d["month"] == "2024-03"]
        assert len(march) == 1
        assert march[0]["income"] == 500000
        assert march[0]["expenses"] == 80000  # absolute value


# ════════════════════════════════════════════════════════════════════
# PART 14: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_account_isolation(self):
        """User A's accounts are not visible to User B."""
        name = f"IsoAcct-{UNIQUE}"
        api_post("/accounts", {"name": name, "type": "checking"}, headers=HEADERS)

        resp = api_get("/accounts", headers=USER2_HEADERS)
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert name not in names

    def test_transaction_isolation(self):
        """User A's transactions are not visible to User B."""
        acct_resp = api_post("/accounts", {"name": f"IsoTxAcct-{UNIQUE}", "type": "checking"}, headers=HEADERS)
        acct_id = acct_resp.json()["id"]
        tx_resp = api_post("/transactions", {
            "date": "2024-03-15", "amount": -999, "accountId": acct_id,
        }, headers=HEADERS)
        tx_id = tx_resp.json()["id"]

        # User 2 should not see it
        resp = api_get(f"/transactions/{tx_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_category_isolation(self):
        """User A's categories are not visible to User B."""
        grp_resp = api_post("/category-groups", {"name": f"IsoCatGrp-{UNIQUE}"}, headers=HEADERS)
        grp_id = grp_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"IsoCat-{UNIQUE}", "groupId": grp_id}, headers=HEADERS)
        cat_id = cat_resp.json()["id"]

        resp = api_get(f"/categories/{cat_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_payee_isolation(self):
        """User A's payees are not visible to User B."""
        payee_resp = api_post("/payees", {"name": f"IsoPayee-{UNIQUE}"}, headers=HEADERS)
        payee_id = payee_resp.json()["id"]

        resp = api_get(f"/payees/{payee_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_rule_isolation(self):
        """User A's rules are not visible to User B."""
        grp_resp = api_post("/category-groups", {"name": f"IsoRuleGrp-{UNIQUE}"}, headers=HEADERS)
        grp_id = grp_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"IsoRuleCat-{UNIQUE}", "groupId": grp_id}, headers=HEADERS)
        cat_id = cat_resp.json()["id"]

        rule_resp = api_post("/rules", {
            "conditions": [{"field": "payee", "op": "is", "value": "x"}],
            "actions": [{"field": "category", "value": cat_id}],
        }, headers=HEADERS)
        rule_id = rule_resp.json()["id"]

        resp = api_get(f"/rules/{rule_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_schedule_isolation(self):
        """User A's schedules are not visible to User B."""
        acct_resp = api_post("/accounts", {"name": f"IsoSchedAcct-{UNIQUE}", "type": "checking"}, headers=HEADERS)
        acct_id = acct_resp.json()["id"]
        sched_resp = api_post("/schedules", {
            "name": f"IsoSched-{UNIQUE}",
            "frequency": "monthly",
            "nextDate": "2024-04-01",
            "amount": -5000,
            "accountId": acct_id,
        }, headers=HEADERS)
        sched_id = sched_resp.json()["id"]

        resp = api_get(f"/schedules/{sched_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_account_deletes_transactions(self):
        """Deleting an account should delete all its transactions."""
        acct_resp = api_post("/accounts", {"name": f"CascAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]

        tx_resp = api_post("/transactions", {"date": "2024-03-15", "amount": -1000, "accountId": acct_id})
        tx_id = tx_resp.json()["id"]

        api_delete(f"/accounts/{acct_id}")

        get_resp = api_get(f"/transactions/{tx_id}")
        assert get_resp.status_code == 404

    def test_delete_account_deletes_transfer_mirror(self):
        """Deleting an account with transfers should also delete mirror transactions."""
        acct1_resp = api_post("/accounts", {"name": f"CascTr1-{UNIQUE}", "type": "checking"})
        acct1_id = acct1_resp.json()["id"]
        acct2_resp = api_post("/accounts", {"name": f"CascTr2-{UNIQUE}", "type": "savings"})
        acct2_id = acct2_resp.json()["id"]

        tx_resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -3000,
            "accountId": acct1_id,
            "transferAccountId": acct2_id,
        })
        mirror_id = tx_resp.json()["transferTransactionId"]

        # Delete account 1
        api_delete(f"/accounts/{acct1_id}")

        # Mirror in account 2 should also be gone
        get_resp = api_get(f"/transactions/{mirror_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 16: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_accounts_list(self):
        """New user should have empty accounts list."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}
        resp = api_get("/accounts", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_transactions_list(self):
        """New user should have empty transactions."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}
        resp = api_get("/transactions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["total"] == 0

    def test_budget_zero_when_not_set(self):
        """Budget for a category that hasn't been set should be 0."""
        group_resp = api_post("/category-groups", {"name": f"ZeroBudGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"ZeroBudCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]

        resp = api_get(f"/budgets/2024-08/categories/{cat_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["budgeted"] == 0
        assert detail["spent"] == 0
        assert detail["available"] == 0

    def test_account_all_types_valid(self):
        """All valid account types should work."""
        valid_types = ["checking", "savings", "credit_card", "investment", "cash"]
        for i, t in enumerate(valid_types):
            resp = api_post("/accounts", {"name": f"Type{t}-{UNIQUE}-{i}", "type": t})
            assert resp.status_code == 201, f"Type {t} should be valid"
            assert resp.json()["type"] == t

    def test_transaction_with_category_and_payee(self):
        """Full transaction with all optional fields."""
        group_resp = api_post("/category-groups", {"name": f"FullGrp-{UNIQUE}"})
        group_id = group_resp.json()["id"]
        cat_resp = api_post("/categories", {"name": f"FullCat-{UNIQUE}", "groupId": group_id})
        cat_id = cat_resp.json()["id"]
        acct_resp = api_post("/accounts", {"name": f"FullAcct-{UNIQUE}", "type": "checking"})
        acct_id = acct_resp.json()["id"]
        payee_resp = api_post("/payees", {"name": f"FullPayee-{UNIQUE}"})
        payee_id = payee_resp.json()["id"]

        resp = api_post("/transactions", {
            "date": "2024-03-15",
            "amount": -4200,
            "accountId": acct_id,
            "categoryId": cat_id,
            "payeeId": payee_id,
            "notes": "Full test",
            "cleared": True,
        })
        assert resp.status_code == 201
        tx = resp.json()
        assert tx["categoryId"] == cat_id
        assert tx["payeeId"] == payee_id
        assert tx["notes"] == "Full test"
        assert tx["cleared"] is True
