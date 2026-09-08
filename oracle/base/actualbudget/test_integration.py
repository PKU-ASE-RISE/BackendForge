"""
Actual Budget — L2 Integration Tests (Adversarial)

Targets LLM bug patterns:
- Pattern 1: camelCase field names (offBudget, groupId, categoryId, payeeId, etc.)
- Pattern 2: Nested data (category groups with categories array)
- Pattern 3: Filtering/pagination actually implemented
- Pattern 4: Exact status codes (201 for create, 204 for delete, 404 for not found)
- Pattern 5: Computed values (balance, budget available)
- Pattern 6: Data isolation between users
- Pattern 7: Cascade deletes

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-User-Id": USER2_ID,
    "Content-Type": "application/json",
}


def unique():
    return uuid.uuid4().hex[:8]


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


class TestAccountFieldIntegrity:
    """Pattern 1+4: camelCase fields and status codes."""

    def test_create_account_201_with_all_fields(self):
        uid = unique()
        r = api_post("/accounts", {"name": f"Acct-{uid}", "type": "checking", "offBudget": True})
        assert r.status_code == 201
        acct = r.json()
        assert "id" in acct
        assert acct["name"] == f"Acct-{uid}"
        assert acct["type"] == "checking"
        assert acct["offBudget"] is True
        assert acct["closed"] is False
        assert acct["balance"] == 0
        assert isinstance(acct["id"], str)

    def test_delete_account_returns_204(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"Del-{uid}", "type": "savings"}).json()
        r = api_delete(f"/accounts/{acct['id']}")
        assert r.status_code == 204

    def test_get_nonexistent_account_returns_404(self):
        r = api_get(f"/accounts/{uuid.uuid4()}")
        assert r.status_code == 404
        body = r.json()
        assert "error" in body


class TestAccountBalanceComputed:
    """Pattern 5: Balance is computed from transactions, not stored."""

    def test_balance_reflects_multiple_transactions(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"Bal-{uid}", "type": "checking"}).json()
        aid = acct["id"]

        api_post("/transactions", {"date": "2024-03-01", "amount": 10000, "accountId": aid})
        api_post("/transactions", {"date": "2024-03-02", "amount": -3000, "accountId": aid})
        api_post("/transactions", {"date": "2024-03-03", "amount": -2000, "accountId": aid})

        r = api_get(f"/accounts/{aid}")
        assert r.status_code == 200
        assert r.json()["balance"] == 5000

    def test_balance_updates_after_transaction_delete(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"BalDel-{uid}", "type": "checking"}).json()
        aid = acct["id"]

        t1 = api_post("/transactions", {"date": "2024-04-01", "amount": 8000, "accountId": aid}).json()
        api_post("/transactions", {"date": "2024-04-02", "amount": -3000, "accountId": aid})

        assert api_get(f"/accounts/{aid}").json()["balance"] == 5000

        api_delete(f"/transactions/{t1['id']}")
        assert api_get(f"/accounts/{aid}").json()["balance"] == -3000


class TestCategoryGroupNested:
    """Pattern 2: Category group must include nested categories array."""

    def test_group_list_includes_categories(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"Grp-{uid}"}).json()
        cat1 = api_post("/categories", {"name": f"Cat1-{uid}", "groupId": grp["id"]}).json()
        cat2 = api_post("/categories", {"name": f"Cat2-{uid}", "groupId": grp["id"]}).json()

        # GET single group
        r = api_get(f"/category-groups/{grp['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert "categories" in detail
        assert len(detail["categories"]) == 2
        cat_ids = [c["id"] for c in detail["categories"]]
        assert cat1["id"] in cat_ids
        assert cat2["id"] in cat_ids

        # List all groups also includes categories
        groups = api_get("/category-groups").json()
        our_grp = [g for g in groups if g["id"] == grp["id"]]
        assert len(our_grp) == 1
        assert len(our_grp[0]["categories"]) == 2

    def test_category_fields_in_group(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"CatFields-{uid}"}).json()
        cat = api_post("/categories", {
            "name": f"CF-{uid}", "groupId": grp["id"], "isIncome": True, "sortOrder": 5
        }).json()

        detail = api_get(f"/category-groups/{grp['id']}").json()
        nested_cat = detail["categories"][0]
        assert nested_cat["id"] == cat["id"]
        assert nested_cat["name"] == f"CF-{uid}"
        assert nested_cat["groupId"] == grp["id"]
        assert nested_cat["isIncome"] is True
        assert nested_cat["sortOrder"] == 5


class TestTransactionFiltering:
    """Pattern 3: Filtering actually works (not just declared)."""

    def test_filter_by_account_id(self):
        uid = unique()
        a1 = api_post("/accounts", {"name": f"FA1-{uid}", "type": "checking"}).json()
        a2 = api_post("/accounts", {"name": f"FA2-{uid}", "type": "savings"}).json()

        api_post("/transactions", {"date": "2024-05-01", "amount": 1000, "accountId": a1["id"]})
        api_post("/transactions", {"date": "2024-05-01", "amount": 2000, "accountId": a1["id"]})
        api_post("/transactions", {"date": "2024-05-01", "amount": 3000, "accountId": a2["id"]})

        r = api_get("/transactions", params={"accountId": a1["id"]})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        for t in data["data"]:
            assert t["accountId"] == a1["id"]

    def test_filter_by_date_range(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"FD-{uid}", "type": "checking"}).json()
        aid = acct["id"]

        api_post("/transactions", {"date": "2024-01-15", "amount": 100, "accountId": aid})
        api_post("/transactions", {"date": "2024-02-15", "amount": 200, "accountId": aid})
        api_post("/transactions", {"date": "2024-03-15", "amount": 300, "accountId": aid})

        r = api_get("/transactions", params={
            "accountId": aid, "startDate": "2024-02-01", "endDate": "2024-02-28"
        })
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["data"][0]["amount"] == 200

    def test_pagination_limit_offset(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"PG-{uid}", "type": "checking"}).json()
        aid = acct["id"]

        for i in range(5):
            api_post("/transactions", {"date": "2024-06-01", "amount": (i + 1) * 100, "accountId": aid})

        r1 = api_get("/transactions", params={"accountId": aid, "limit": 2, "offset": 0})
        assert r1.status_code == 200
        d1 = r1.json()
        assert len(d1["data"]) == 2
        assert d1["total"] == 5
        assert d1["limit"] == 2
        assert d1["offset"] == 0

        r2 = api_get("/transactions", params={"accountId": aid, "limit": 2, "offset": 2})
        d2 = r2.json()
        assert len(d2["data"]) == 2
        assert d2["offset"] == 2
        # Different transactions than first page
        ids1 = {t["id"] for t in d1["data"]}
        ids2 = {t["id"] for t in d2["data"]}
        assert ids1.isdisjoint(ids2)


class TestTransferMirrorTransaction:
    """Pattern 5+7: Transfers create mirror, deletion cascades."""

    def test_transfer_creates_mirror_with_negated_amount(self):
        uid = unique()
        a1 = api_post("/accounts", {"name": f"TrA1-{uid}", "type": "checking"}).json()
        a2 = api_post("/accounts", {"name": f"TrA2-{uid}", "type": "savings"}).json()

        r = api_post("/transactions", {
            "date": "2024-07-01",
            "amount": -5000,
            "accountId": a1["id"],
            "transferAccountId": a2["id"]
        })
        assert r.status_code == 201
        t1 = r.json()
        assert t1["transferAccountId"] == a2["id"]
        assert t1["transferTransactionId"] is not None

        # Get the mirror transaction
        mirror_id = t1["transferTransactionId"]
        mirror = api_get(f"/transactions/{mirror_id}").json()
        assert mirror["amount"] == 5000  # Negated
        assert mirror["accountId"] == a2["id"]
        assert mirror["transferAccountId"] == a1["id"]
        assert mirror["transferTransactionId"] == t1["id"]

    def test_delete_transfer_deletes_mirror(self):
        uid = unique()
        a1 = api_post("/accounts", {"name": f"TrDel1-{uid}", "type": "checking"}).json()
        a2 = api_post("/accounts", {"name": f"TrDel2-{uid}", "type": "savings"}).json()

        t1 = api_post("/transactions", {
            "date": "2024-07-15",
            "amount": -2000,
            "accountId": a1["id"],
            "transferAccountId": a2["id"]
        }).json()
        mirror_id = t1["transferTransactionId"]

        # Delete original
        r = api_delete(f"/transactions/{t1['id']}")
        assert r.status_code == 204

        # Mirror should also be gone
        assert api_get(f"/transactions/{mirror_id}").status_code == 404


class TestBudgetComputation:
    """Pattern 5: Budget available = budgeted - spent (computed correctly)."""

    def test_budget_available_computed(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"BdgGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"BdgCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"BdgAcct-{uid}", "type": "checking"}).json()

        # Set budget
        r = api_put(f"/budgets/2024-03/categories/{cat['id']}", {"amount": 50000})
        assert r.status_code == 200
        assert r.json()["budgeted"] == 50000

        # Create spending transactions in March
        api_post("/transactions", {
            "date": "2024-03-10", "amount": -15000, "accountId": acct["id"], "categoryId": cat["id"]
        })
        api_post("/transactions", {
            "date": "2024-03-20", "amount": -10000, "accountId": acct["id"], "categoryId": cat["id"]
        })

        # Check budget detail
        r = api_get(f"/budgets/2024-03/categories/{cat['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["categoryId"] == cat["id"]
        assert detail["budgeted"] == 50000
        assert detail["spent"] == 25000  # |(-15000) + (-10000)| = 25000
        assert detail["available"] == 25000  # 50000 - 25000

    def test_budget_month_all_categories(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"BdgMGrp-{uid}"}).json()
        c1 = api_post("/categories", {"name": f"BdgMC1-{uid}", "groupId": grp["id"]}).json()
        c2 = api_post("/categories", {"name": f"BdgMC2-{uid}", "groupId": grp["id"]}).json()

        api_put(f"/budgets/2024-04/categories/{c1['id']}", {"amount": 30000})
        api_put(f"/budgets/2024-04/categories/{c2['id']}", {"amount": 20000})

        r = api_get("/budgets/2024-04")
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == "2024-04"
        assert "categories" in data
        cat_ids = [c["categoryId"] for c in data["categories"]]
        assert c1["id"] in cat_ids
        assert c2["id"] in cat_ids


class TestDataIsolation:
    """Pattern 6: Users cannot see each other's data."""

    def test_accounts_isolated(self):
        uid = unique()
        # User 1 creates account
        acct = api_post("/accounts", {"name": f"Iso-{uid}", "type": "checking"}).json()

        # User 2 cannot see it
        r = api_get("/accounts", headers=HEADERS_USER2)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert acct["id"] not in ids

        # User 2 cannot GET it
        r2 = api_get(f"/accounts/{acct['id']}", headers=HEADERS_USER2)
        assert r2.status_code == 404

    def test_transactions_isolated(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"TrIso-{uid}", "type": "checking"}).json()
        t = api_post("/transactions", {"date": "2024-08-01", "amount": 5000, "accountId": acct["id"]}).json()

        # User 2 cannot see it
        r = api_get(f"/transactions/{t['id']}", headers=HEADERS_USER2)
        assert r.status_code == 404

    def test_categories_isolated(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"CatIso-{uid}"}).json()
        cat = api_post("/categories", {"name": f"CatIsoC-{uid}", "groupId": grp["id"]}).json()

        r = api_get(f"/categories/{cat['id']}", headers=HEADERS_USER2)
        assert r.status_code == 404


class TestCascadeDeletes:
    """Pattern 7: Account delete removes transactions, group delete removes categories."""

    def test_delete_account_cascades_transactions(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"CascAcct-{uid}", "type": "checking"}).json()
        t1 = api_post("/transactions", {"date": "2024-09-01", "amount": 1000, "accountId": acct["id"]}).json()
        t2 = api_post("/transactions", {"date": "2024-09-02", "amount": 2000, "accountId": acct["id"]}).json()

        api_delete(f"/accounts/{acct['id']}")

        assert api_get(f"/transactions/{t1['id']}").status_code == 404
        assert api_get(f"/transactions/{t2['id']}").status_code == 404

    def test_delete_category_group_cascades_categories(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"CascGrp-{uid}"}).json()
        c1 = api_post("/categories", {"name": f"CascC1-{uid}", "groupId": grp["id"]}).json()
        c2 = api_post("/categories", {"name": f"CascC2-{uid}", "groupId": grp["id"]}).json()

        api_delete(f"/category-groups/{grp['id']}")

        assert api_get(f"/categories/{c1['id']}").status_code == 404
        assert api_get(f"/categories/{c2['id']}").status_code == 404


class TestRuleAutoApply:
    """Pattern 5: Rules auto-apply on transaction creation."""

    def test_rule_sets_category_on_matching_transaction(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"RuleGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"RuleCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"RuleAcct-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {"name": f"Grocery Store {uid}"}).json()

        # Create rule: if payee contains "Grocery", set category
        rule = api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Grocery"}],
            "actions": [{"field": "category", "value": cat["id"]}]
        }).json()
        assert rule["id"] is not None

        # Create transaction with that payee
        t = api_post("/transactions", {
            "date": "2024-10-01",
            "amount": -5000,
            "accountId": acct["id"],
            "payeeId": payee["id"]
        }).json()

        # Category should be auto-applied
        assert t["categoryId"] == cat["id"]

    def test_rule_does_not_apply_on_update(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"RuleNoUp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"RuleNoUpC-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"RuleNoUpA-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {"name": f"Target {uid}"}).json()

        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Target"}],
            "actions": [{"field": "category", "value": cat["id"]}]
        })

        # Create transaction WITHOUT the matching payee
        t = api_post("/transactions", {
            "date": "2024-10-05", "amount": -1000, "accountId": acct["id"]
        }).json()
        assert t.get("categoryId") is None

        # Update to add the matching payee — rule should NOT auto-apply
        updated = api_put(f"/transactions/{t['id']}", {"payeeId": payee["id"]}).json()
        assert updated.get("categoryId") is None


class TestPayeeDefaultCategory:
    """Pattern 5: Payee categoryId used as default when no explicit category."""

    def test_payee_default_category_applied(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"PayDef-{uid}"}).json()
        cat = api_post("/categories", {"name": f"PayDefCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"PayDefAcct-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {"name": f"DefaultPayee-{uid}", "categoryId": cat["id"]}).json()

        # Create transaction with payee but no explicit category
        t = api_post("/transactions", {
            "date": "2024-11-01",
            "amount": -2000,
            "accountId": acct["id"],
            "payeeId": payee["id"]
        }).json()
        assert t["categoryId"] == cat["id"]

    def test_explicit_category_overrides_payee_default(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"PayOvr-{uid}"}).json()
        cat1 = api_post("/categories", {"name": f"PayOvrC1-{uid}", "groupId": grp["id"]}).json()
        cat2 = api_post("/categories", {"name": f"PayOvrC2-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"PayOvrA-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {"name": f"OvrPayee-{uid}", "categoryId": cat1["id"]}).json()

        # Explicit category should win over payee default
        t = api_post("/transactions", {
            "date": "2024-11-05",
            "amount": -3000,
            "accountId": acct["id"],
            "payeeId": payee["id"],
            "categoryId": cat2["id"]
        }).json()
        assert t["categoryId"] == cat2["id"]


class TestScheduleFields:
    """Pattern 1+4: Schedule CRUD with correct field names and status codes."""

    def test_create_schedule_201_with_all_fields(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"SchAcct-{uid}", "type": "checking"}).json()
        grp = api_post("/category-groups", {"name": f"SchGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"SchCat-{uid}", "groupId": grp["id"]}).json()

        r = api_post("/schedules", {
            "name": f"Monthly Rent-{uid}",
            "frequency": "monthly",
            "nextDate": "2024-12-01",
            "amount": -150000,
            "accountId": acct["id"],
            "categoryId": cat["id"]
        })
        assert r.status_code == 201
        sched = r.json()
        assert sched["name"] == f"Monthly Rent-{uid}"
        assert sched["frequency"] == "monthly"
        assert sched["nextDate"] == "2024-12-01"
        assert sched["amount"] == -150000
        assert sched["accountId"] == acct["id"]
        assert sched["categoryId"] == cat["id"]
        assert "id" in sched

    def test_delete_schedule_returns_204(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"SchDel-{uid}", "type": "checking"}).json()
        sched = api_post("/schedules", {
            "name": f"Del-{uid}", "frequency": "weekly", "nextDate": "2025-01-01",
            "amount": -1000, "accountId": acct["id"]
        }).json()
        r = api_delete(f"/schedules/{sched['id']}")
        assert r.status_code == 204


class TestTransactionListStructure:
    """Pattern 1: Transaction list response has data/total/limit/offset."""

    def test_transaction_list_response_structure(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"TLS-{uid}", "type": "checking"}).json()
        api_post("/transactions", {"date": "2024-12-01", "amount": 100, "accountId": acct["id"]})

        r = api_get("/transactions", params={"accountId": acct["id"]})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert isinstance(body["data"], list)
        assert isinstance(body["total"], int)
        assert isinstance(body["limit"], int)
        assert isinstance(body["offset"], int)

    def test_transaction_fields_complete(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"TFC-{uid}", "type": "checking"}).json()
        t = api_post("/transactions", {
            "date": "2024-12-05", "amount": -2500, "accountId": acct["id"],
            "notes": "test note", "cleared": True
        }).json()

        detail = api_get(f"/transactions/{t['id']}").json()
        assert detail["id"] == t["id"]
        assert detail["date"] == "2024-12-05"
        assert detail["amount"] == -2500
        assert detail["accountId"] == acct["id"]
        assert detail["notes"] == "test note"
        assert detail["cleared"] is True
        assert "categoryId" in detail
        assert "payeeId" in detail
        assert "transferAccountId" in detail
        assert "transferTransactionId" in detail


class TestValidationErrors:
    """Pattern 4+8: Proper error status codes."""

    def test_invalid_account_type_returns_400(self):
        r = api_post("/accounts", {"name": f"BadType-{unique()}", "type": "bitcoin"})
        assert r.status_code == 400
        assert "error" in r.json()

    def test_duplicate_account_name_returns_400(self):
        uid = unique()
        name = f"DupAcct-{uid}"
        api_post("/accounts", {"name": name, "type": "checking"})
        r = api_post("/accounts", {"name": name, "type": "savings"})
        assert r.status_code == 400

    def test_duplicate_payee_name_returns_400(self):
        uid = unique()
        name = f"DupPayee-{uid}"
        api_post("/payees", {"name": name})
        r = api_post("/payees", {"name": name})
        assert r.status_code == 400

    def test_duplicate_category_group_name_returns_400(self):
        uid = unique()
        name = f"DupGrp-{uid}"
        api_post("/category-groups", {"name": name})
        r = api_post("/category-groups", {"name": name})
        assert r.status_code == 400


class TestReportFields:
    """Pattern 1+5: Report response structure and computed values."""

    def test_spending_by_category_response_structure(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"RptGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"RptCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"RptAcct-{uid}", "type": "checking"}).json()

        api_post("/transactions", {
            "date": "2024-06-15", "amount": -5000,
            "accountId": acct["id"], "categoryId": cat["id"]
        })

        r = api_get("/reports/spending-by-category", params={
            "startDate": "2024-06-01", "endDate": "2024-06-30"
        })
        assert r.status_code == 200
        body = r.json()
        assert "startDate" in body
        assert "endDate" in body
        assert "categories" in body
        found = [c for c in body["categories"] if c["categoryId"] == cat["id"]]
        assert len(found) == 1
        assert found[0]["spent"] == 5000
        assert "name" in found[0]
