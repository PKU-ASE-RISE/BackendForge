"""
BackendForge — Comprehensive Correctness Tests for Ghostfolio Task

Tests ALL business rules and ALL endpoint groups.
Focus: portfolio calculations, gain/loss computation, buy/sell quantity tracking.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")

# User IDs — auto-created on first request
USER1_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())

USER1_HEADERS = {
    "X-User-Id": USER1_ID,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
    "X-User-Id": USER2_ID,
    "Content-Type": "application/json",
}


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication & User
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_auth_header_returns_401(self):
        """Endpoints requiring auth should return 401 without header."""
        resp = requests.get(f"{BASE_URL}/api/user", timeout=30)
        assert resp.status_code == 401

    def test_missing_auth_on_accounts(self):
        resp = requests.get(f"{BASE_URL}/api/accounts", timeout=30)
        assert resp.status_code == 401

    def test_missing_auth_on_activities(self):
        resp = requests.get(f"{BASE_URL}/api/activities", timeout=30)
        assert resp.status_code == 401

    def test_missing_auth_on_portfolio(self):
        resp = requests.get(f"{BASE_URL}/api/portfolio/summary", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_user(self):
        """First request with a new user ID auto-creates the user."""
        new_user_id = str(uuid.uuid4())
        resp = requests.get(
            f"{BASE_URL}/api/user",
            headers={"X-User-Id": new_user_id, "Content-Type": "application/json"},
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == new_user_id
        assert data["baseCurrency"] == "USD"
        assert "dateCreated" in data


class TestUser:

    def test_get_user_profile(self):
        resp = api_get("/api/user")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == USER1_ID
        assert data["baseCurrency"] == "USD"
        assert "dateCreated" in data

    def test_update_user_base_currency(self):
        resp = api_put("/api/user", {"baseCurrency": "EUR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["baseCurrency"] == "EUR"

        # Reset to USD for other tests
        api_put("/api/user", {"baseCurrency": "USD"})

    def test_user_data_isolation(self):
        """User 2 cannot see user 1's data."""
        resp = api_get("/api/user", headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == USER2_ID


# ════════════════════════════════════════════════════════════════════
# PART 3: Accounts CRUD
# ════════════════════════════════════════════════════════════════════


class TestAccounts:

    def test_create_securities_account(self):
        resp = api_post("/api/accounts", {
            "name": "Brokerage Account",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Brokerage Account"
        assert data["accountType"] == "SECURITIES"
        assert data["currency"] == "USD"
        assert data["balance"] == 0
        assert "id" in data

    def test_create_cash_account(self):
        resp = api_post("/api/accounts", {
            "name": "Cash Reserve",
            "accountType": "CASH",
            "currency": "USD",
            "balance": 10000.0
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Cash Reserve"
        assert data["accountType"] == "CASH"
        assert data["balance"] == 10000.0

    def test_list_accounts(self):
        for name, account_type, balance in (
            ("Brokerage Account", "SECURITIES", 0),
            ("Cash Reserve", "CASH", 10000.0),
        ):
            api_post("/api/accounts", {
                "name": name,
                "accountType": account_type,
                "currency": "USD",
                "balance": balance,
            }).json()["id"]

        resp = api_get("/api/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least the two we just created

    def test_get_single_account(self):
        # Create, then get
        create_resp = api_post("/api/accounts", {
            "name": "Get Test Account",
            "accountType": "DEPOSIT",
            "currency": "EUR",
            "balance": 5000.0
        })
        assert create_resp.status_code == 201
        account_id = create_resp.json()["id"]

        resp = api_get(f"/api/accounts/{account_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == account_id
        assert data["name"] == "Get Test Account"
        assert "transactionCount" in data

    def test_update_account(self):
        create_resp = api_post("/api/accounts", {
            "name": "Update Me",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0
        })
        account_id = create_resp.json()["id"]

        resp = api_put(f"/api/accounts/{account_id}", {
            "name": "Updated Name",
            "balance": 500.0
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["balance"] == 500.0

    def test_delete_account_no_activities(self):
        create_resp = api_post("/api/accounts", {
            "name": "Delete Me",
            "accountType": "CASH",
            "currency": "USD",
            "balance": 0
        })
        account_id = create_resp.json()["id"]

        resp = api_delete(f"/api/accounts/{account_id}")
        assert resp.status_code == 204

        # Verify gone
        resp = api_get(f"/api/accounts/{account_id}")
        assert resp.status_code == 404

    def test_delete_account_with_activities_fails(self):
        # Create account and activity
        acc_resp = api_post("/api/accounts", {
            "name": "Has Activities",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0
        })
        account_id = acc_resp.json()["id"]

        api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-01-15T10:00:00Z",
            "quantity": 10,
            "unitPrice": 150.0,
            "fee": 5.0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id
        })

        # Try to delete account — should fail
        resp = api_delete(f"/api/accounts/{account_id}")
        assert resp.status_code == 400

    def test_account_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_account_data_isolation(self):
        """User 2 cannot see user 1's accounts."""
        api_post("/api/accounts", {
            "name": "Isolation Source",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        }).json()["id"]

        resp = api_get("/api/accounts", headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        # User 2 has no accounts
        for acc in data:
            assert acc.get("userId") != USER1_ID


# ════════════════════════════════════════════════════════════════════
# PART 4: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        resp = api_post("/api/tags", {"name": "Tech Stocks"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Tech Stocks"
        assert "id" in data

    def test_list_tags(self):
        api_post("/api/tags", {"name": "Tech Stocks"}).json()["id"]

        resp = api_get("/api/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(t["name"] == "Tech Stocks" for t in data)

    def test_get_single_tag(self):
        create_resp = api_post("/api/tags", {"name": "Dividends Tag"})
        tag_id = create_resp.json()["id"]

        resp = api_get(f"/api/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Dividends Tag"

    def test_update_tag(self):
        create_resp = api_post("/api/tags", {"name": "Old Name"})
        tag_id = create_resp.json()["id"]

        resp = api_put(f"/api/tags/{tag_id}", {"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_tag(self):
        create_resp = api_post("/api/tags", {"name": "To Delete"})
        tag_id = create_resp.json()["id"]

        resp = api_delete(f"/api/tags/{tag_id}")
        assert resp.status_code == 204

        resp = api_get(f"/api/tags/{tag_id}")
        assert resp.status_code == 404

    def test_duplicate_tag_name_fails(self):
        unique_name = f"UniqueTag-{uuid.uuid4().hex[:8]}"
        api_post("/api/tags", {"name": unique_name})
        resp = api_post("/api/tags", {"name": unique_name})
        assert resp.status_code == 400

    def test_tag_not_found(self):
        resp = api_get(f"/api/tags/{str(uuid.uuid4())}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Activities CRUD
# ════════════════════════════════════════════════════════════════════


class TestActivities:

    def _get_or_create_account(self):
        """Get an existing SECURITIES account or create one."""
        resp = api_get("/api/accounts")
        accounts = resp.json()
        for acc in accounts:
            if acc["accountType"] == "SECURITIES":
                return acc["id"]
        # Create one
        resp = api_post("/api/accounts", {
            "name": "Activities Test Account",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0
        })
        return resp.json()["id"]

    def _create_list_activity(self, date):
        account_id = self._get_or_create_account()
        return api_post("/api/activities", {
            "type": "BUY",
            "date": date,
            "quantity": 1,
            "unitPrice": 190.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "JPM",
            "accountId": account_id,
        }).json()["id"]

    def test_create_buy_activity(self):
        account_id = self._get_or_create_account()
        resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-03-01T10:00:00Z",
            "quantity": 5,
            "unitPrice": 140.0,
            "fee": 10.0,
            "currency": "USD",
            "symbol": "GOOGL",
            "accountId": account_id
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "BUY"
        assert data["quantity"] == 5
        assert data["unitPrice"] == 140.0
        assert data["fee"] == 10.0
        assert data["symbol"] == "GOOGL"
        assert data["accountId"] == account_id
        assert "id" in data
        assert "tags" in data
        assert isinstance(data["tags"], list)

    def test_create_sell_activity(self):
        account_id = self._get_or_create_account()
        # First buy some
        api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-01-01T10:00:00Z",
            "quantity": 20,
            "unitPrice": 100.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "MSFT",
            "accountId": account_id
        })
        # Then sell some
        resp = api_post("/api/activities", {
            "type": "SELL",
            "date": "2024-03-15T10:00:00Z",
            "quantity": 5,
            "unitPrice": 410.0,
            "fee": 5.0,
            "currency": "USD",
            "symbol": "MSFT",
            "accountId": account_id
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "SELL"
        assert data["quantity"] == 5

    def test_sell_more_than_owned_fails(self):
        account_id = self._get_or_create_account()
        # Try to sell 1000 NVDA without buying any
        resp = api_post("/api/activities", {
            "type": "SELL",
            "date": "2024-03-15T10:00:00Z",
            "quantity": 1000,
            "unitPrice": 800.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "NVDA",
            "accountId": account_id
        })
        assert resp.status_code == 400

    def test_create_dividend_activity(self):
        account_id = self._get_or_create_account()
        resp = api_post("/api/activities", {
            "type": "DIVIDEND",
            "date": "2024-06-01T10:00:00Z",
            "quantity": 10,
            "unitPrice": 0.82,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "DIVIDEND"

    def test_create_fee_activity(self):
        account_id = self._get_or_create_account()
        resp = api_post("/api/activities", {
            "type": "FEE",
            "date": "2024-06-15T10:00:00Z",
            "quantity": 1,
            "unitPrice": 25.0,
            "fee": 0,
            "currency": "USD",
            "symbol": None,
            "accountId": account_id
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "FEE"

    def test_create_interest_activity(self):
        account_id = self._get_or_create_account()
        resp = api_post("/api/activities", {
            "type": "INTEREST",
            "date": "2024-07-01T10:00:00Z",
            "quantity": 1,
            "unitPrice": 50.0,
            "fee": 0,
            "currency": "USD",
            "symbol": None,
            "accountId": account_id
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "INTEREST"

    def test_create_item_activity(self):
        account_id = self._get_or_create_account()
        resp = api_post("/api/activities", {
            "type": "ITEM",
            "date": "2024-01-01T10:00:00Z",
            "quantity": 1,
            "unitPrice": 50000.0,
            "fee": 0,
            "currency": "USD",
            "symbol": None,
            "accountId": account_id
        })
        assert resp.status_code == 201
        assert resp.json()["type"] == "ITEM"

    def test_list_activities(self):
        self._create_list_activity("2024-02-01T10:00:00Z")

        resp = api_get("/api/activities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_single_activity(self):
        account_id = self._get_or_create_account()
        create_resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-08-01T10:00:00Z",
            "quantity": 2,
            "unitPrice": 220.0,
            "fee": 1.0,
            "currency": "USD",
            "symbol": "VTI",
            "accountId": account_id
        })
        activity_id = create_resp.json()["id"]

        resp = api_get(f"/api/activities/{activity_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == activity_id
        assert data["symbol"] == "VTI"

    def test_update_activity(self):
        account_id = self._get_or_create_account()
        create_resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-09-01T10:00:00Z",
            "quantity": 3,
            "unitPrice": 100.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "GLD",
            "accountId": account_id
        })
        activity_id = create_resp.json()["id"]

        resp = api_put(f"/api/activities/{activity_id}", {
            "quantity": 5,
            "unitPrice": 185.0,
            "fee": 2.0
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 5
        assert data["unitPrice"] == 185.0
        assert data["fee"] == 2.0

    def test_delete_activity(self):
        account_id = self._get_or_create_account()
        create_resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-10-01T10:00:00Z",
            "quantity": 1,
            "unitPrice": 75.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "BND",
            "accountId": account_id
        })
        activity_id = create_resp.json()["id"]

        resp = api_delete(f"/api/activities/{activity_id}")
        assert resp.status_code == 204

        resp = api_get(f"/api/activities/{activity_id}")
        assert resp.status_code == 404

    def test_activity_not_found(self):
        resp = api_get(f"/api/activities/{str(uuid.uuid4())}")
        assert resp.status_code == 404

    def test_activity_with_tags(self):
        account_id = self._get_or_create_account()
        # Create a tag
        tag_resp = api_post("/api/tags", {"name": f"ActivityTag-{uuid.uuid4().hex[:8]}"})
        tag_id = tag_resp.json()["id"]

        resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-04-01T10:00:00Z",
            "quantity": 3,
            "unitPrice": 180.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "AMZN",
            "accountId": account_id,
            "tagIds": [tag_id]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "tags" in data
        assert len(data["tags"]) == 1
        assert data["tags"][0]["id"] == tag_id

    def test_activity_sorting_by_date_desc(self):
        """Default sort is by date descending."""
        self._create_list_activity("2024-01-01T10:00:00Z")
        self._create_list_activity("2024-12-01T10:00:00Z")

        resp = api_get("/api/activities", params={"sortBy": "date", "sortDirection": "desc"})
        assert resp.status_code == 200
        data = resp.json()
        if len(data) >= 2:
            # Verify descending date order
            for i in range(len(data) - 1):
                assert data[i]["date"] >= data[i + 1]["date"]

    def test_activity_sorting_by_date_asc(self):
        self._create_list_activity("2024-01-01T10:00:00Z")
        self._create_list_activity("2024-12-01T10:00:00Z")

        resp = api_get("/api/activities", params={"sortBy": "date", "sortDirection": "asc"})
        assert resp.status_code == 200
        data = resp.json()
        if len(data) >= 2:
            for i in range(len(data) - 1):
                assert data[i]["date"] <= data[i + 1]["date"]

    def test_activity_data_isolation(self):
        """User 2 cannot see user 1's activities."""
        self._create_list_activity("2024-02-01T10:00:00Z")

        resp = api_get("/api/activities", headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        for act in data:
            assert act.get("userId") != USER1_ID

    def test_activity_invalid_account_fails(self):
        """Activity with non-existent account should fail."""
        resp = api_post("/api/activities", {
            "type": "BUY",
            "date": "2024-01-01T10:00:00Z",
            "quantity": 1,
            "unitPrice": 100.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": str(uuid.uuid4())
        })
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 6: Symbols
# ════════════════════════════════════════════════════════════════════


class TestSymbols:

    def test_list_all_symbols(self):
        resp = api_get("/api/symbols")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 10
        # Check structure
        sym = data[0]
        assert "symbol" in sym
        assert "name" in sym
        assert "currency" in sym
        assert "price" in sym
        assert "sector" in sym

    def test_search_symbols_by_name(self):
        resp = api_get("/api/symbols", params={"query": "apple"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(s["symbol"] == "AAPL" for s in data)

    def test_search_symbols_by_symbol(self):
        resp = api_get("/api/symbols", params={"query": "MSFT"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(s["symbol"] == "MSFT" for s in data)

    def test_search_symbols_case_insensitive(self):
        resp = api_get("/api/symbols", params={"query": "nvda"})
        assert resp.status_code == 200
        data = resp.json()
        assert any(s["symbol"] == "NVDA" for s in data)

    def test_get_symbol_details(self):
        resp = api_get("/api/symbols/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["currency"] == "USD"
        assert data["price"] == 150.0
        assert data["sector"] == "Technology"

    def test_get_symbol_not_found(self):
        resp = api_get("/api/symbols/FAKESYMBOL")
        assert resp.status_code == 404

    def test_known_symbol_prices(self):
        """Verify all mock symbol prices."""
        expected = {
            "AAPL": 150.0,
            "GOOGL": 140.0,
            "MSFT": 400.0,
            "AMZN": 180.0,
            "TSLA": 250.0,
            "NVDA": 800.0,
            "JPM": 190.0,
            "VTI": 220.0,
            "BND": 75.0,
            "GLD": 185.0
        }
        for symbol, price in expected.items():
            resp = api_get(f"/api/symbols/{symbol}")
            assert resp.status_code == 200
            assert resp.json()["price"] == price, f"{symbol} price mismatch"


# ════════════════════════════════════════════════════════════════════
# PART 7: Portfolio Calculations (the core business logic)
# ════════════════════════════════════════════════════════════════════


class TestPortfolioCalculations:
    """
    These tests use a fresh user to have full control over portfolio state.
    """

    @pytest.fixture(autouse=True)
    def setup_portfolio_user(self):
        """Create a fresh user and set up a known portfolio state."""
        self.user_id = str(uuid.uuid4())
        self.headers = {
            "X-User-Id": self.user_id,
            "Content-Type": "application/json",
        }
        # Create a securities account
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "Main Brokerage",
                "accountType": "SECURITIES",
                "currency": "USD",
                "balance": 0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.securities_account_id = resp.json()["id"]

        # Create a cash account
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "Cash Account",
                "accountType": "CASH",
                "currency": "USD",
                "balance": 5000.0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.cash_account_id = resp.json()["id"]

    def _buy(self, symbol, quantity, unit_price, fee=0):
        resp = requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-15T10:00:00Z",
                "quantity": quantity,
                "unitPrice": unit_price,
                "fee": fee,
                "currency": "USD",
                "symbol": symbol,
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        return resp.json()

    def _sell(self, symbol, quantity, unit_price, fee=0):
        resp = requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "SELL",
                "date": "2024-06-15T10:00:00Z",
                "quantity": quantity,
                "unitPrice": unit_price,
                "fee": fee,
                "currency": "USD",
                "symbol": symbol,
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        return resp.json()

    def test_single_buy_holding(self):
        """Buy 10 AAPL at $100, current price $150."""
        self._buy("AAPL", 10, 100.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        holdings = resp.json()
        aapl = next((h for h in holdings if h["symbol"] == "AAPL"), None)
        assert aapl is not None
        assert aapl["quantity"] == 10
        assert aapl["marketPrice"] == 150.0
        assert aapl["marketValue"] == 1500.0  # 10 * 150
        assert aapl["averageCost"] == 100.0  # 1000 / 10
        assert aapl["totalCost"] == 1000.0  # 10 * 100
        assert aapl["unrealizedGain"] == 500.0  # (150 - 100) * 10
        assert abs(aapl["unrealizedGainPercent"] - 50.0) < 0.01  # (150-100)/100 * 100

    def test_multiple_buys_average_cost(self):
        """Buy 10 AAPL at $100, then 10 more at $200. Average cost = (1000+2000)/20 = $150."""
        self._buy("AAPL", 10, 100.0)
        self._buy("AAPL", 10, 200.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        aapl = next((h for h in holdings if h["symbol"] == "AAPL"), None)
        assert aapl is not None
        assert aapl["quantity"] == 20
        assert aapl["averageCost"] == 150.0  # (1000 + 2000) / 20
        assert aapl["totalCost"] == 3000.0
        assert aapl["marketPrice"] == 150.0
        assert aapl["marketValue"] == 3000.0  # 20 * 150
        assert abs(aapl["unrealizedGain"]) < 0.01  # (150 - 150) * 20 = 0
        assert abs(aapl["unrealizedGainPercent"]) < 0.01

    def test_buy_then_sell_reduces_quantity(self):
        """Buy 20 MSFT, sell 5. Holding should show 15."""
        self._buy("MSFT", 20, 350.0)
        self._sell("MSFT", 5, 400.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        msft = next((h for h in holdings if h["symbol"] == "MSFT"), None)
        assert msft is not None
        assert msft["quantity"] == 15
        # Average cost is still based on buys only: 350
        assert msft["averageCost"] == 350.0
        assert msft["marketPrice"] == 400.0
        assert msft["marketValue"] == 6000.0  # 15 * 400
        assert msft["unrealizedGain"] == 750.0  # (400 - 350) * 15
        assert abs(msft["unrealizedGainPercent"] - (50.0 / 350.0 * 100)) < 0.01

    def test_sell_all_removes_from_holdings(self):
        """Buy 10 then sell 10 — holding should not appear."""
        self._buy("TSLA", 10, 200.0)
        self._sell("TSLA", 10, 250.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        tsla = next((h for h in holdings if h["symbol"] == "TSLA"), None)
        assert tsla is None  # Should not appear

    def test_holding_detail_with_activities(self):
        """Get detailed holding info including activities."""
        self._buy("GOOGL", 5, 120.0)
        self._buy("GOOGL", 3, 130.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings/GOOGL",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "GOOGL"
        assert data["quantity"] == 8
        # averageCost = (5*120 + 3*130) / 8 = (600 + 390) / 8 = 123.75
        assert abs(data["averageCost"] - 123.75) < 0.01
        assert data["marketPrice"] == 140.0
        assert data["marketValue"] == 1120.0  # 8 * 140
        # unrealizedGain = (140 - 123.75) * 8 = 16.25 * 8 = 130
        assert abs(data["unrealizedGain"] - 130.0) < 0.01
        assert "activities" in data
        assert len(data["activities"]) == 2

    def test_holding_detail_not_found(self):
        """Holding for symbol with no position returns 404."""
        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings/FAKESYM",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 404

    def test_portfolio_summary_basic(self):
        """Test portfolio summary with a simple buy."""
        self._buy("AAPL", 10, 100.0, fee=10.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()

        # totalInvested = 10 * 100 = 1000
        assert data["totalInvested"] == 1000.0
        # currentValue = 10 * 150 (AAPL market price) + 5000 (cash)
        assert data["currentValue"] == 6500.0
        # totalGain = (holdingsValue - totalInvested) + dividends + interest - fees
        # = (1500 - 1000) + 0 + 0 - 10 = 490
        assert data["totalGain"] == 490.0
        assert data["totalFees"] == 10.0
        assert data["cashPositions"] == 5000.0
        assert data["holdings"] == 1

    def test_portfolio_summary_with_dividends(self):
        """Dividends add to totalDividends but don't change holdings."""
        self._buy("AAPL", 10, 100.0)

        # Record dividend
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "DIVIDEND",
                "date": "2024-06-01T10:00:00Z",
                "quantity": 10,
                "unitPrice": 1.50,
                "fee": 0,
                "currency": "USD",
                "symbol": "AAPL",
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        assert data["totalDividends"] == 15.0  # 10 * 1.50
        # Holdings quantity unchanged
        hold_resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = hold_resp.json()
        aapl = next((h for h in holdings if h["symbol"] == "AAPL"), None)
        assert aapl["quantity"] == 10  # Unchanged by dividend

    def test_portfolio_summary_with_interest(self):
        """Interest adds to totalInterest."""
        self._buy("AAPL", 5, 100.0)

        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "INTEREST",
                "date": "2024-07-01T10:00:00Z",
                "quantity": 1,
                "unitPrice": 25.0,
                "fee": 0,
                "currency": "USD",
                "symbol": None,
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        assert data["totalInterest"] == 25.0

    def test_portfolio_summary_with_fees(self):
        """Fees add to totalFees and reduce gain."""
        self._buy("AAPL", 10, 100.0, fee=0)

        # Standalone fee activity
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "FEE",
                "date": "2024-07-15T10:00:00Z",
                "quantity": 1,
                "unitPrice": 50.0,
                "fee": 0,
                "currency": "USD",
                "symbol": None,
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        assert data["totalFees"] == 50.0
        # totalGain = (holdingsValue - totalInvested) + dividends + interest - fees
        # = (10*150 - 1000) + 0 + 0 - 50 = 500 - 50 = 450
        assert data["totalGain"] == 450.0

    def test_portfolio_summary_empty(self):
        """Empty portfolio (no activities)."""
        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInvested"] == 0
        assert data["currentValue"] == 5000.0  # Only cash account
        assert data["totalGain"] == 0
        assert data["totalGainPercent"] == 0
        assert data["holdings"] == 0
        assert data["cashPositions"] == 5000.0

    def test_portfolio_performance(self):
        """Performance endpoint returns same core metrics as summary."""
        self._buy("AAPL", 10, 100.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/performance",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "totalInvested" in data
        assert "currentValue" in data
        assert "totalGain" in data
        assert "totalGainPercent" in data
        assert data["totalInvested"] == 1000.0
        assert data["currentValue"] == 6500.0  # 10*150 + 5000 cash
        # totalGain = (1500 - 1000) + 0 + 0 - 0 = 500
        assert data["totalGain"] == 500.0

    def test_gain_percent_calculation(self):
        """totalGainPercent = totalGain / totalInvested * 100"""
        self._buy("AAPL", 10, 100.0)  # invest 1000, worth 1500

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        # totalGain = (1500 - 1000) + 0 + 0 - 0 = 500
        # totalGainPercent = 500 / 1000 * 100 = 50
        assert abs(data["totalGainPercent"] - 50.0) < 0.01

    def test_fees_on_buy_activities(self):
        """Fees on BUY activities are included in totalFees."""
        self._buy("AAPL", 10, 100.0, fee=20.0)

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        assert data["totalFees"] == 20.0

    def test_item_type_in_portfolio(self):
        """ITEM activities contribute to portfolio value."""
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "ITEM",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 1,
                "unitPrice": 100000.0,
                "fee": 0,
                "currency": "USD",
                "symbol": None,
                "accountId": self.securities_account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        # ITEM with unitPrice 100000 adds to both totalInvested and currentValue (holdings)
        assert data["totalInvested"] == 100000.0
        # currentValue = item value (100000) + cash (5000)
        assert data["currentValue"] == 105000.0
        # totalGain = (holdingsValue - totalInvested) = (100000 - 100000) = 0
        assert data["totalGain"] == 0

    def test_multiple_holdings_portfolio(self):
        """Portfolio with multiple holdings."""
        self._buy("AAPL", 10, 100.0)   # worth 10*150 = 1500
        self._buy("GOOGL", 5, 130.0)   # worth 5*140 = 700
        self._buy("MSFT", 2, 380.0)    # worth 2*400 = 800

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        symbols = [h["symbol"] for h in holdings]
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "MSFT" in symbols

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        # totalInvested = 10*100 + 5*130 + 2*380 = 1000 + 650 + 760 = 2410
        assert data["totalInvested"] == 2410.0
        # currentValue = 1500 + 700 + 800 + 5000 (cash) = 8000
        assert data["currentValue"] == 8000.0
        assert data["holdings"] == 3
        # totalGain = (3000 - 2410) + 0 + 0 - 0 = 590
        assert data["totalGain"] == 590.0


# ════════════════════════════════════════════════════════════════════
# PART 8: Import/Export
# ════════════════════════════════════════════════════════════════════


class TestImportExport:

    @pytest.fixture(autouse=True)
    def setup_import_user(self):
        """Create a fresh user for import/export tests."""
        self.user_id = str(uuid.uuid4())
        self.headers = {
            "X-User-Id": self.user_id,
            "Content-Type": "application/json",
        }
        # Create account
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "Import Account",
                "accountType": "SECURITIES",
                "currency": "USD",
                "balance": 0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.account_id = resp.json()["id"]

    def test_import_activities(self):
        resp = requests.post(
            f"{BASE_URL}/api/import",
            json={
                "activities": [
                    {
                        "type": "BUY",
                        "date": "2024-01-01T10:00:00Z",
                        "quantity": 10,
                        "unitPrice": 150.0,
                        "fee": 5.0,
                        "currency": "USD",
                        "symbol": "AAPL",
                        "accountId": self.account_id
                    },
                    {
                        "type": "BUY",
                        "date": "2024-02-01T10:00:00Z",
                        "quantity": 5,
                        "unitPrice": 140.0,
                        "fee": 3.0,
                        "currency": "USD",
                        "symbol": "GOOGL",
                        "accountId": self.account_id
                    }
                ]
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 2

    def test_import_invalid_activity_fails_atomically(self):
        """If any activity is invalid, none are imported."""
        resp = requests.post(
            f"{BASE_URL}/api/import",
            json={
                "activities": [
                    {
                        "type": "BUY",
                        "date": "2024-01-01T10:00:00Z",
                        "quantity": 10,
                        "unitPrice": 150.0,
                        "fee": 0,
                        "currency": "USD",
                        "symbol": "AAPL",
                        "accountId": self.account_id
                    },
                    {
                        "type": "SELL",
                        "date": "2024-01-02T10:00:00Z",
                        "quantity": 9999,
                        "unitPrice": 150.0,
                        "fee": 0,
                        "currency": "USD",
                        "symbol": "TSLA",
                        "accountId": self.account_id
                    }
                ]
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 400

        # Nothing should have been imported
        activities_resp = requests.get(
            f"{BASE_URL}/api/activities",
            headers=self.headers,
            timeout=30
        )
        assert len(activities_resp.json()) == 0

    def test_export_activities(self):
        # First import some
        requests.post(
            f"{BASE_URL}/api/import",
            json={
                "activities": [
                    {
                        "type": "BUY",
                        "date": "2024-01-01T10:00:00Z",
                        "quantity": 10,
                        "unitPrice": 150.0,
                        "fee": 0,
                        "currency": "USD",
                        "symbol": "AAPL",
                        "accountId": self.account_id
                    }
                ]
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/export",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "activities" in data
        assert len(data["activities"]) >= 1
        act = data["activities"][0]
        assert "type" in act
        assert "date" in act
        assert "quantity" in act
        assert "unitPrice" in act

    def test_export_empty(self):
        """Export with no activities returns empty array."""
        resp = requests.get(
            f"{BASE_URL}/api/export",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["activities"] == []


# ════════════════════════════════════════════════════════════════════
# PART 9: Currency Conversion
# ════════════════════════════════════════════════════════════════════


class TestCurrencyConversion:
    """Test that portfolio values are converted to user's base currency."""

    @pytest.fixture(autouse=True)
    def setup_currency_user(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {
            "X-User-Id": self.user_id,
            "Content-Type": "application/json",
        }
        # Set user base currency to USD (default)
        requests.get(f"{BASE_URL}/api/user", headers=self.headers, timeout=30)

        # Create EUR account
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "EU Brokerage",
                "accountType": "SECURITIES",
                "currency": "EUR",
                "balance": 0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.eur_account_id = resp.json()["id"]

        # Create USD account
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "US Brokerage",
                "accountType": "SECURITIES",
                "currency": "USD",
                "balance": 0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.usd_account_id = resp.json()["id"]

    def test_eur_activity_converted_to_usd(self):
        """Buy in EUR, portfolio shows USD values (base currency)."""
        # Buy 10 AAPL at 100 EUR each. EUR->USD rate is 1.08
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-15T10:00:00Z",
                "quantity": 10,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "EUR",
                "symbol": "AAPL",
                "accountId": self.eur_account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        aapl = next((h for h in holdings if h["symbol"] == "AAPL"), None)
        assert aapl is not None
        assert aapl["quantity"] == 10
        # averageCost in USD = 100 EUR * 1.08 = 108 USD
        assert abs(aapl["averageCost"] - 108.0) < 0.01
        # marketPrice is always in the symbol's native currency (USD for AAPL) = 150
        assert aapl["marketPrice"] == 150.0
        # marketValue = 10 * 150 = 1500 USD
        assert abs(aapl["marketValue"] - 1500.0) < 0.01

    def test_cash_account_eur_converted(self):
        """EUR cash account balance is converted to USD in portfolio summary."""
        # Create EUR cash account with 1000 EUR
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "EUR Cash",
                "accountType": "CASH",
                "currency": "EUR",
                "balance": 1000.0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/summary",
            headers=self.headers,
            timeout=30
        )
        data = resp.json()
        # 1000 EUR * 1.08 = 1080 USD
        assert abs(data["cashPositions"] - 1080.0) < 0.01


# ════════════════════════════════════════════════════════════════════
# PART 10: Edge Cases & Validation
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    @pytest.fixture(autouse=True)
    def setup_edge_user(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {
            "X-User-Id": self.user_id,
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{BASE_URL}/api/accounts",
            json={
                "name": "Edge Account",
                "accountType": "SECURITIES",
                "currency": "USD",
                "balance": 0
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201
        self.account_id = resp.json()["id"]

    def test_sell_exactly_what_you_own(self):
        """Selling exactly the owned quantity should succeed."""
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 10,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "AAPL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "SELL",
                "date": "2024-06-01T10:00:00Z",
                "quantity": 10,
                "unitPrice": 150.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "AAPL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 201

    def test_sell_one_more_than_owned_fails(self):
        """Selling one more than owned should fail."""
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 5,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "GOOGL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "SELL",
                "date": "2024-06-01T10:00:00Z",
                "quantity": 6,
                "unitPrice": 140.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "GOOGL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 400

    def test_buy_with_fee_affects_average_cost(self):
        """Fee is included in average cost calculation."""
        # Buy 10 at $100 with $50 fee → total cost = 1000 + 50 = 1050, avg = 105
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 10,
                "unitPrice": 100.0,
                "fee": 50.0,
                "currency": "USD",
                "symbol": "NVDA",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=self.headers,
            timeout=30
        )
        holdings = resp.json()
        nvda = next((h for h in holdings if h["symbol"] == "NVDA"), None)
        assert nvda is not None
        # averageCost = (10*100 + 50) / 10 = 105
        assert abs(nvda["averageCost"] - 105.0) < 0.01
        assert nvda["totalCost"] == 1050.0

    def test_portfolio_isolation_between_users(self):
        """Different users have separate portfolios."""
        other_user_id = str(uuid.uuid4())
        other_headers = {
            "X-User-Id": other_user_id,
            "Content-Type": "application/json",
        }

        resp = requests.get(
            f"{BASE_URL}/api/portfolio/holdings",
            headers=other_headers,
            timeout=30
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_transaction_count_on_account(self):
        """Account should show transactionCount."""
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 1,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "AAPL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )
        requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-02-01T10:00:00Z",
                "quantity": 1,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "GOOGL",
                "accountId": self.account_id
            },
            headers=self.headers,
            timeout=30
        )

        resp = requests.get(
            f"{BASE_URL}/api/accounts/{self.account_id}",
            headers=self.headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transactionCount"] == 2

    def test_delete_tag_doesnt_delete_activities(self):
        """Deleting a tag removes it from activities but doesn't delete them."""
        # Create tag
        tag_resp = requests.post(
            f"{BASE_URL}/api/tags",
            json={"name": f"DeleteMe-{uuid.uuid4().hex[:6]}"},
            headers=self.headers,
            timeout=30
        )
        tag_id = tag_resp.json()["id"]

        # Create activity with tag
        act_resp = requests.post(
            f"{BASE_URL}/api/activities",
            json={
                "type": "BUY",
                "date": "2024-01-01T10:00:00Z",
                "quantity": 1,
                "unitPrice": 100.0,
                "fee": 0,
                "currency": "USD",
                "symbol": "AAPL",
                "accountId": self.account_id,
                "tagIds": [tag_id]
            },
            headers=self.headers,
            timeout=30
        )
        activity_id = act_resp.json()["id"]

        # Delete the tag
        requests.delete(f"{BASE_URL}/api/tags/{tag_id}", headers=self.headers, timeout=30)

        # Activity should still exist but without the tag
        act = requests.get(
            f"{BASE_URL}/api/activities/{activity_id}",
            headers=self.headers,
            timeout=30
        )
        assert act.status_code == 200
        assert len(act.json()["tags"]) == 0
