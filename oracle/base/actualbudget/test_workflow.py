"""
Actual Budget — L3 Workflow Tests (Adversarial)

Multi-step workflows crossing 3+ entity types.
Targets: computed values, cascade, transfers, rules, schedules, reports.

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


class TestBudgetEnvelopeWorkflow:
    """Pattern 5+7: Full budget envelope lifecycle with computed values."""

    def test_budget_lifecycle_with_spending(self):
        """
        Create group -> category -> account -> set budget -> spend
        -> verify available computed correctly -> add more spending
        -> verify cumulative.
        """
        uid = unique()
        grp = api_post("/category-groups", {"name": f"WfGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"WfCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"WfAcct-{uid}", "type": "checking"}).json()

        # Set budget: $500
        r = api_put(f"/budgets/2024-05/categories/{cat['id']}", {"amount": 50000})
        assert r.status_code == 200
        assert r.json()["budgeted"] == 50000
        assert r.json()["spent"] == 0
        assert r.json()["available"] == 50000

        # Spend $100
        api_post("/transactions", {
            "date": "2024-05-05", "amount": -10000, "accountId": acct["id"], "categoryId": cat["id"]
        })

        detail = api_get(f"/budgets/2024-05/categories/{cat['id']}").json()
        assert detail["budgeted"] == 50000
        assert detail["spent"] == 10000
        assert detail["available"] == 40000

        # Spend another $150
        api_post("/transactions", {
            "date": "2024-05-15", "amount": -15000, "accountId": acct["id"], "categoryId": cat["id"]
        })

        detail2 = api_get(f"/budgets/2024-05/categories/{cat['id']}").json()
        assert detail2["spent"] == 25000
        assert detail2["available"] == 25000

        # Verify in month summary
        month = api_get("/budgets/2024-05").json()
        cat_entry = [c for c in month["categories"] if c["categoryId"] == cat["id"]]
        assert len(cat_entry) == 1
        assert cat_entry[0]["available"] == 25000


class TestTransferWorkflow:
    """Pattern 5+7: Transfer between accounts verifies both balances."""

    def test_transfer_updates_both_account_balances(self):
        """
        Create 2 accounts with initial deposits -> transfer between them
        -> verify both balances change -> delete transfer -> balances revert.
        """
        uid = unique()
        checking = api_post("/accounts", {"name": f"TrfChk-{uid}", "type": "checking"}).json()
        savings = api_post("/accounts", {"name": f"TrfSav-{uid}", "type": "savings"}).json()

        # Initial deposits
        api_post("/transactions", {"date": "2024-01-01", "amount": 100000, "accountId": checking["id"]})
        api_post("/transactions", {"date": "2024-01-01", "amount": 50000, "accountId": savings["id"]})

        assert api_get(f"/accounts/{checking['id']}").json()["balance"] == 100000
        assert api_get(f"/accounts/{savings['id']}").json()["balance"] == 50000

        # Transfer $200 from checking to savings
        transfer = api_post("/transactions", {
            "date": "2024-01-15",
            "amount": -20000,
            "accountId": checking["id"],
            "transferAccountId": savings["id"]
        }).json()

        assert api_get(f"/accounts/{checking['id']}").json()["balance"] == 80000
        assert api_get(f"/accounts/{savings['id']}").json()["balance"] == 70000

        # Verify mirror exists
        mirror_id = transfer["transferTransactionId"]
        mirror = api_get(f"/transactions/{mirror_id}").json()
        assert mirror["amount"] == 20000
        assert mirror["accountId"] == savings["id"]

        # Delete transfer — both balances revert
        api_delete(f"/transactions/{transfer['id']}")
        assert api_get(f"/accounts/{checking['id']}").json()["balance"] == 100000
        assert api_get(f"/accounts/{savings['id']}").json()["balance"] == 50000
        assert api_get(f"/transactions/{mirror_id}").status_code == 404


class TestRuleWithPayeeWorkflow:
    """Pattern 5: Rules take precedence over payee default category."""

    def test_rule_overrides_payee_default_category(self):
        """
        Create payee with default category -> create rule with different category
        -> transaction should use rule category (not payee default).
        """
        uid = unique()
        grp = api_post("/category-groups", {"name": f"RlPyGrp-{uid}"}).json()
        default_cat = api_post("/categories", {"name": f"Default-{uid}", "groupId": grp["id"]}).json()
        rule_cat = api_post("/categories", {"name": f"RuleCat-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"RlPyAcct-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {
            "name": f"Supermarket {uid}",
            "categoryId": default_cat["id"]
        }).json()

        # Rule: payee contains "Supermarket" -> set rule_cat
        api_post("/rules", {
            "conditions": [{"field": "payee", "op": "contains", "value": "Supermarket"}],
            "actions": [{"field": "category", "value": rule_cat["id"]}]
        })

        # Create transaction with the payee
        t = api_post("/transactions", {
            "date": "2024-08-01", "amount": -5000,
            "accountId": acct["id"], "payeeId": payee["id"]
        }).json()

        # Rule should win over payee default
        assert t["categoryId"] == rule_cat["id"]

    def test_rule_with_amount_condition(self):
        """Rule with amount > threshold correctly filters."""
        uid = unique()
        grp = api_post("/category-groups", {"name": f"AmtGrp-{uid}"}).json()
        big_cat = api_post("/categories", {"name": f"BigPurch-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"AmtAcct-{uid}", "type": "checking"}).json()
        payee = api_post("/payees", {"name": f"AmtPayee-{uid}"}).json()

        # Rule: amount < -10000 (i.e., spending > $100) -> set big_cat
        api_post("/rules", {
            "conditions": [{"field": "amount", "op": "lt", "value": "-10000"}],
            "actions": [{"field": "category", "value": big_cat["id"]}]
        })

        # Small purchase — should NOT match
        t1 = api_post("/transactions", {
            "date": "2024-08-05", "amount": -5000, "accountId": acct["id"], "payeeId": payee["id"]
        }).json()
        assert t1.get("categoryId") is None

        # Big purchase — SHOULD match
        t2 = api_post("/transactions", {
            "date": "2024-08-06", "amount": -20000, "accountId": acct["id"], "payeeId": payee["id"]
        }).json()
        assert t2["categoryId"] == big_cat["id"]


class TestSchedulePostTransaction:
    """Pattern 5+8: Schedule posting creates transaction and advances nextDate."""

    def test_post_monthly_schedule_advances_date(self):
        """
        Create monthly schedule -> post transaction -> verify transaction created
        and nextDate advanced by 1 month.
        """
        uid = unique()
        acct = api_post("/accounts", {"name": f"SchPost-{uid}", "type": "checking"}).json()
        grp = api_post("/category-groups", {"name": f"SchPGrp-{uid}"}).json()
        cat = api_post("/categories", {"name": f"SchPCat-{uid}", "groupId": grp["id"]}).json()

        sched = api_post("/schedules", {
            "name": f"Monthly Rent-{uid}",
            "frequency": "monthly",
            "nextDate": "2024-01-15",
            "amount": -150000,
            "accountId": acct["id"],
            "categoryId": cat["id"]
        }).json()

        # Post first transaction
        r = api_post(f"/schedules/{sched['id']}/post-transaction")
        assert r.status_code == 201
        t = r.json()
        assert t["date"] == "2024-01-15"
        assert t["amount"] == -150000
        assert t["accountId"] == acct["id"]
        assert t["categoryId"] == cat["id"]

        # Schedule nextDate should advance to 2024-02-15
        updated_sched = api_get(f"/schedules/{sched['id']}").json()
        assert updated_sched["nextDate"] == "2024-02-15"

        # Post again
        r2 = api_post(f"/schedules/{sched['id']}/post-transaction")
        assert r2.status_code == 201
        assert r2.json()["date"] == "2024-02-15"

        # Now nextDate should be 2024-03-15
        assert api_get(f"/schedules/{sched['id']}").json()["nextDate"] == "2024-03-15"

    def test_post_weekly_schedule_advances_7_days(self):
        uid = unique()
        acct = api_post("/accounts", {"name": f"SchWk-{uid}", "type": "checking"}).json()

        sched = api_post("/schedules", {
            "name": f"Weekly-{uid}",
            "frequency": "weekly",
            "nextDate": "2024-03-01",
            "amount": -5000,
            "accountId": acct["id"]
        }).json()

        api_post(f"/schedules/{sched['id']}/post-transaction")
        updated = api_get(f"/schedules/{sched['id']}").json()
        assert updated["nextDate"] == "2024-03-08"


class TestIncomeVsExpensesReport:
    """Pattern 5: Report computes income/expenses correctly by category type."""

    def test_income_vs_expenses_computed(self):
        """
        Create income category + expense category -> add transactions
        -> verify report separates correctly.
        Use a fresh user to avoid shared state from other tests.
        """
        uid = unique()
        fresh_headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        inc_grp = api_post("/category-groups", {"name": f"IncGrp-{uid}", "isIncome": True}, headers=fresh_headers).json()
        exp_grp = api_post("/category-groups", {"name": f"ExpGrp-{uid}"}, headers=fresh_headers).json()
        inc_cat = api_post("/categories", {
            "name": f"Salary-{uid}", "groupId": inc_grp["id"], "isIncome": True
        }, headers=fresh_headers).json()
        exp_cat = api_post("/categories", {
            "name": f"Food-{uid}", "groupId": exp_grp["id"]
        }, headers=fresh_headers).json()
        acct = api_post("/accounts", {"name": f"IvEAcct-{uid}", "type": "checking"}, headers=fresh_headers).json()

        # Income in March
        api_post("/transactions", {
            "date": "2024-03-01", "amount": 500000, "accountId": acct["id"], "categoryId": inc_cat["id"]
        }, headers=fresh_headers)
        # Expenses in March
        api_post("/transactions", {
            "date": "2024-03-10", "amount": -30000, "accountId": acct["id"], "categoryId": exp_cat["id"]
        }, headers=fresh_headers)
        api_post("/transactions", {
            "date": "2024-03-20", "amount": -20000, "accountId": acct["id"], "categoryId": exp_cat["id"]
        }, headers=fresh_headers)

        r = api_get("/reports/income-vs-expenses", params={
            "startMonth": "2024-03", "endMonth": "2024-03"
        }, headers=fresh_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["startMonth"] == "2024-03"
        assert body["endMonth"] == "2024-03"
        assert "data" in body
        assert len(body["data"]) >= 1
        march = [d for d in body["data"] if d["month"] == "2024-03"]
        assert len(march) == 1
        assert march[0]["income"] == 500000
        assert march[0]["expenses"] == 50000


class TestNetWorthReport:
    """Pattern 5: Net worth computed correctly over time."""

    def test_net_worth_reflects_cumulative_transactions(self):
        """
        Create transactions in different months -> net worth report should
        show cumulative totals. Use fresh user to avoid shared state.
        """
        uid = unique()
        fresh_headers = {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}
        acct = api_post("/accounts", {"name": f"NwAcct-{uid}", "type": "checking"}, headers=fresh_headers).json()

        # January: +$1000
        api_post("/transactions", {"date": "2024-01-15", "amount": 100000, "accountId": acct["id"]}, headers=fresh_headers)
        # February: -$200
        api_post("/transactions", {"date": "2024-02-15", "amount": -20000, "accountId": acct["id"]}, headers=fresh_headers)
        # March: +$500
        api_post("/transactions", {"date": "2024-03-15", "amount": 50000, "accountId": acct["id"]}, headers=fresh_headers)

        r = api_get("/reports/net-worth", params={
            "startMonth": "2024-01", "endMonth": "2024-03"
        }, headers=fresh_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["startMonth"] == "2024-01"
        assert body["endMonth"] == "2024-03"
        assert len(body["data"]) == 3

        months = {d["month"]: d["netWorth"] for d in body["data"]}
        assert months["2024-01"] == 100000  # $1000 cumulative end of Jan
        assert months["2024-02"] == 80000   # $1000 - $200 = $800 end of Feb
        assert months["2024-03"] == 130000  # $800 + $500 = $1300 end of Mar


class TestSpendingByCategoryReport:
    """Pattern 5: Spending by category computed correctly."""

    def test_spending_by_category_multiple_categories(self):
        uid = unique()
        grp = api_post("/category-groups", {"name": f"SpGrp-{uid}"}).json()
        food = api_post("/categories", {"name": f"Food-{uid}", "groupId": grp["id"]}).json()
        transport = api_post("/categories", {"name": f"Transport-{uid}", "groupId": grp["id"]}).json()
        acct = api_post("/accounts", {"name": f"SpAcct-{uid}", "type": "checking"}).json()

        # Food spending
        api_post("/transactions", {
            "date": "2024-04-05", "amount": -8000, "accountId": acct["id"], "categoryId": food["id"]
        })
        api_post("/transactions", {
            "date": "2024-04-15", "amount": -12000, "accountId": acct["id"], "categoryId": food["id"]
        })
        # Transport spending
        api_post("/transactions", {
            "date": "2024-04-10", "amount": -5000, "accountId": acct["id"], "categoryId": transport["id"]
        })

        r = api_get("/reports/spending-by-category", params={
            "startDate": "2024-04-01", "endDate": "2024-04-30"
        })
        assert r.status_code == 200
        body = r.json()
        categories = {c["categoryId"]: c for c in body["categories"]}

        assert food["id"] in categories
        assert categories[food["id"]]["spent"] == 20000
        assert categories[food["id"]]["name"] == f"Food-{uid}"

        assert transport["id"] in categories
        assert categories[transport["id"]]["spent"] == 5000


class TestAccountDeleteCascadesTransferMirror:
    """Pattern 7: Deleting account removes transfer mirror transactions."""

    def test_account_delete_removes_transfer_mirrors(self):
        """
        Create transfer -> delete source account -> mirror in target also gone.
        """
        uid = unique()
        a1 = api_post("/accounts", {"name": f"CascA1-{uid}", "type": "checking"}).json()
        a2 = api_post("/accounts", {"name": f"CascA2-{uid}", "type": "savings"}).json()

        # Regular deposit into a2
        api_post("/transactions", {"date": "2024-05-01", "amount": 50000, "accountId": a2["id"]})

        # Transfer from a1 to a2
        transfer = api_post("/transactions", {
            "date": "2024-05-10", "amount": -10000,
            "accountId": a1["id"], "transferAccountId": a2["id"]
        }).json()
        mirror_id = transfer["transferTransactionId"]

        # Verify mirror exists in a2
        assert api_get(f"/transactions/{mirror_id}").status_code == 200

        # Delete a1 -> all a1 transactions deleted, including the transfer
        api_delete(f"/accounts/{a1['id']}")

        # The mirror in a2 should also be deleted
        assert api_get(f"/transactions/{mirror_id}").status_code == 404

        # a2 balance should only reflect the deposit (mirror gone)
        a2_balance = api_get(f"/accounts/{a2['id']}").json()["balance"]
        assert a2_balance == 50000


class TestFullUserIsolationWorkflow:
    """Pattern 6: Complete data isolation between users."""

    def test_users_fully_isolated(self):
        """
        User1 creates full budget setup. User2 sees nothing from User1.
        User2 can create same-named entities without conflict.
        """
        uid = unique()

        # User 1 setup
        acct1 = api_post("/accounts", {"name": f"SharedName-{uid}", "type": "checking"}).json()
        grp1 = api_post("/category-groups", {"name": f"SharedGrp-{uid}"}).json()
        cat1 = api_post("/categories", {"name": f"SharedCat-{uid}", "groupId": grp1["id"]}).json()
        payee1 = api_post("/payees", {"name": f"SharedPayee-{uid}"}).json()

        # User 2 sees empty lists
        assert len(api_get("/accounts", headers=HEADERS_USER2).json()) == 0
        assert len(api_get("/category-groups", headers=HEADERS_USER2).json()) == 0
        assert len(api_get("/categories", headers=HEADERS_USER2).json()) == 0
        assert len(api_get("/payees", headers=HEADERS_USER2).json()) == 0

        # User 2 can create same names (unique per user, not globally)
        r = api_post("/accounts", {"name": f"SharedName-{uid}", "type": "savings"}, headers=HEADERS_USER2)
        assert r.status_code == 201

        r = api_post("/category-groups", {"name": f"SharedGrp-{uid}"}, headers=HEADERS_USER2)
        assert r.status_code == 201
