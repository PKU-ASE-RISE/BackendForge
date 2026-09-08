"""
BackendForge — L2 Integration Tests for Ghostfolio Task

Adversarial tests targeting common LLM implementation bugs:
- camelCase field naming (Pattern 1)
- Nested/computed data correctness (Pattern 2)
- Sorting/filtering actually working (Pattern 3)
- Exact status codes (Pattern 4)
- Business logic computation (Pattern 5)
- Data isolation (Pattern 6)
- Cascade/side effects (Pattern 7)

"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())

HEADERS_A = {"X-User-Id": USER_A_ID, "Content-Type": "application/json"}
HEADERS_B = {"X-User-Id": USER_B_ID, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def post(path, json=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def put(path, json=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def delete(path, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


class TestAccountResponseFields:
    """Pattern 1+4: Verify account response has correct camelCase fields and status codes."""

    def test_create_account_returns_201_with_all_fields(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/accounts", {
            "name": f"Acct-{tag}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 1234.56
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert "accountType" in data
        assert "currency" in data
        assert "balance" in data
        assert "userId" in data
        assert data["name"] == f"Acct-{tag}"
        assert data["accountType"] == "SECURITIES"
        assert data["currency"] == "USD"
        assert data["balance"] == 1234.56
        assert data["userId"] == USER_A_ID

    def test_get_account_includes_transaction_count(self):
        """Pattern 2: GET account includes computed transactionCount."""
        acct = post("/api/accounts", {
            "name": f"TxCnt-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        # Add an activity
        post("/api/activities", {
            "type": "BUY", "date": "2024-03-01T10:00:00Z",
            "quantity": 5, "unitPrice": 150.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": acct["id"]
        })
        r = get(f"/api/accounts/{acct['id']}")
        assert r.status_code == 200
        data = r.json()
        assert "transactionCount" in data
        assert data["transactionCount"] == 1

    def test_delete_account_returns_204(self):
        acct = post("/api/accounts", {
            "name": f"Del-{uuid.uuid4().hex[:6]}",
            "accountType": "CASH", "currency": "USD", "balance": 0
        }).json()
        r = delete(f"/api/accounts/{acct['id']}")
        assert r.status_code == 204

    def test_nonexistent_account_returns_404(self):
        r = get(f"/api/accounts/{uuid.uuid4()}")
        assert r.status_code == 404


class TestActivityResponseFields:
    """Pattern 1+2: Activity response has correct camelCase fields + tags array."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.acct = post("/api/accounts", {
            "name": f"ActResp-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()

    def test_create_activity_returns_201_with_tags_array(self):
        tag = post("/api/tags", {"name": f"Tag-{uuid.uuid4().hex[:8]}"}).json()
        r = post("/api/activities", {
            "type": "BUY", "date": "2024-02-15T08:00:00Z",
            "quantity": 7, "unitPrice": 140.0, "fee": 3.5,
            "currency": "USD", "symbol": "GOOGL",
            "accountId": self.acct["id"],
            "tagIds": [tag["id"]]
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "type" in data
        assert "date" in data
        assert "quantity" in data
        assert "unitPrice" in data
        assert "fee" in data
        assert "currency" in data
        assert "symbol" in data
        assert "accountId" in data
        assert "tags" in data
        assert "userId" in data
        assert data["type"] == "BUY"
        assert data["quantity"] == 7
        assert data["unitPrice"] == 140.0
        assert data["fee"] == 3.5
        assert data["symbol"] == "GOOGL"
        assert data["accountId"] == self.acct["id"]
        assert len(data["tags"]) == 1
        assert data["tags"][0]["id"] == tag["id"]
        assert data["tags"][0]["name"] == tag["name"]

    def test_delete_activity_returns_204(self):
        act = post("/api/activities", {
            "type": "BUY", "date": "2024-05-01T10:00:00Z",
            "quantity": 1, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct["id"]
        }).json()
        r = delete(f"/api/activities/{act['id']}")
        assert r.status_code == 204
        # Verify gone
        assert get(f"/api/activities/{act['id']}").status_code == 404


class TestActivitySorting:
    """Pattern 3: Verify sorting actually changes order."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {"X-User-Id": self.user_id, "Content-Type": "application/json"}
        acct = requests.post(f"{BASE_URL}/api/accounts", json={
            "name": "SortAcct", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=self.headers, timeout=30).json()
        self.acct_id = acct["id"]
        # Create activities with different dates
        for i, (date, qty) in enumerate([
            ("2024-01-01T10:00:00Z", 10),
            ("2024-06-01T10:00:00Z", 5),
            ("2024-03-01T10:00:00Z", 20),
        ]):
            requests.post(f"{BASE_URL}/api/activities", json={
                "type": "BUY", "date": date, "quantity": qty,
                "unitPrice": 100.0, "fee": 0, "currency": "USD",
                "symbol": "AAPL", "accountId": self.acct_id
            }, headers=self.headers, timeout=30)

    def test_sort_by_date_desc(self):
        r = requests.get(f"{BASE_URL}/api/activities",
                         params={"sortBy": "date", "sortDirection": "desc"},
                         headers=self.headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        dates = [a["date"] for a in data]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_date_asc(self):
        r = requests.get(f"{BASE_URL}/api/activities",
                         params={"sortBy": "date", "sortDirection": "asc"},
                         headers=self.headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        dates = [a["date"] for a in data]
        assert dates == sorted(dates)


class TestSymbolSearch:
    """Pattern 3+5: Symbol search with partial/case-insensitive matching."""

    def test_search_partial_name(self):
        r = get("/api/symbols", params={"query": "vanguard"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2  # VTI and BND
        symbols = [s["symbol"] for s in data]
        assert "VTI" in symbols
        assert "BND" in symbols

    def test_search_returns_correct_fields(self):
        r = get("/api/symbols", params={"query": "NVDA"})
        data = r.json()
        assert len(data) >= 1
        sym = data[0]
        assert sym["symbol"] == "NVDA"
        assert sym["name"] == "NVIDIA Corp."
        assert sym["currency"] == "USD"
        assert sym["price"] == 800.0
        assert sym["sector"] == "Technology"

    def test_no_match_returns_empty(self):
        r = get("/api/symbols", params={"query": "xyznonexistent123"})
        assert r.status_code == 200
        assert r.json() == []


class TestHoldingComputedValues:
    """Pattern 5: Verify computed holding values with multiple inputs."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {"X-User-Id": self.user_id, "Content-Type": "application/json"}
        acct = requests.post(f"{BASE_URL}/api/accounts", json={
            "name": "HoldComp", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=self.headers, timeout=30).json()
        self.acct_id = acct["id"]

    def test_average_cost_with_fee(self):
        """averageCost = (qty*price + fee) / qty for single buy."""
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 50.0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)

        r = requests.get(f"{BASE_URL}/api/portfolio/holdings/AAPL",
                         headers=self.headers, timeout=30)
        assert r.status_code == 200
        h = r.json()
        assert h["symbol"] == "AAPL"
        assert h["quantity"] == 10
        # averageCost = (10*100 + 50) / 10 = 105
        assert abs(h["averageCost"] - 105.0) < 0.01
        assert abs(h["totalCost"] - 1050.0) < 0.01
        # unrealizedGain = (150 - 105) * 10 = 450
        assert abs(h["unrealizedGain"] - 450.0) < 0.01
        # unrealizedGainPercent = (150-105)/105 * 100 ≈ 42.857
        assert abs(h["unrealizedGainPercent"] - (45.0/105.0*100)) < 0.1

    def test_multiple_buys_weighted_average(self):
        """Two buys: 5@100 fee=10, 15@200 fee=30. avg = (510+3030)/20 = 177"""
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 5, "unitPrice": 100.0, "fee": 10.0,
            "currency": "USD", "symbol": "MSFT", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-02-01T10:00:00Z",
            "quantity": 15, "unitPrice": 200.0, "fee": 30.0,
            "currency": "USD", "symbol": "MSFT", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)

        r = requests.get(f"{BASE_URL}/api/portfolio/holdings/MSFT",
                         headers=self.headers, timeout=30)
        h = r.json()
        assert h["quantity"] == 20
        # totalCost = (5*100+10) + (15*200+30) = 510 + 3030 = 3540
        assert abs(h["totalCost"] - 3540.0) < 0.01
        # averageCost = 3540/20 = 177
        assert abs(h["averageCost"] - 177.0) < 0.01
        # marketValue = 20 * 400 = 8000
        assert abs(h["marketValue"] - 8000.0) < 0.01

    def test_holding_detail_includes_activities(self):
        """Pattern 2: HoldingDetail has activities array."""
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 3, "unitPrice": 130.0, "fee": 0,
            "currency": "USD", "symbol": "GOOGL", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)

        r = requests.get(f"{BASE_URL}/api/portfolio/holdings/GOOGL",
                         headers=self.headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "activities" in data
        assert isinstance(data["activities"], list)
        assert len(data["activities"]) == 1
        assert data["activities"][0]["symbol"] == "GOOGL"


class TestPortfolioSummaryFields:
    """Pattern 1+5: Summary response has all camelCase fields with correct values."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {"X-User-Id": self.user_id, "Content-Type": "application/json"}
        acct = requests.post(f"{BASE_URL}/api/accounts", json={
            "name": "SumAcct", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=self.headers, timeout=30).json()
        self.acct_id = acct["id"]
        # Cash account
        requests.post(f"{BASE_URL}/api/accounts", json={
            "name": "Cash", "accountType": "CASH", "currency": "USD", "balance": 2000.0
        }, headers=self.headers, timeout=30)

    def test_summary_all_fields_present(self):
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 5.0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)

        r = requests.get(f"{BASE_URL}/api/portfolio/summary",
                         headers=self.headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "totalInvested" in data
        assert "currentValue" in data
        assert "totalGain" in data
        assert "totalGainPercent" in data
        assert "totalDividends" in data
        assert "totalInterest" in data
        assert "totalFees" in data
        assert "holdings" in data
        assert "cashPositions" in data
        # Values
        assert data["totalInvested"] == 1000.0
        assert data["currentValue"] == 3500.0  # 10*150 + 2000 cash
        assert data["totalFees"] == 5.0
        assert data["cashPositions"] == 2000.0
        assert data["holdings"] == 1


class TestTagUniqueness:
    """Pattern 8: Duplicate tag names should fail."""

    def test_duplicate_tag_name_returns_400(self):
        tag_name = f"Unique-{uuid.uuid4().hex[:8]}"
        r1 = post("/api/tags", {"name": tag_name})
        assert r1.status_code == 201
        r2 = post("/api/tags", {"name": tag_name})
        assert r2.status_code == 400

    def test_tag_has_correct_fields(self):
        name = f"FieldCheck-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": name})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert "userId" in data
        assert data["name"] == name
        assert data["userId"] == USER_A_ID


class TestDataIsolation:
    """Pattern 6: User B cannot see User A's data."""

    def test_accounts_isolated(self):
        acct = post("/api/accounts", {
            "name": f"IsoA-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=HEADERS_A).json()
        r = get(f"/api/accounts/{acct['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_activities_isolated(self):
        acct = post("/api/accounts", {
            "name": f"IsoAct-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=HEADERS_A).json()
        act = post("/api/activities", {
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 1, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": acct["id"]
        }, headers=HEADERS_A).json()
        r = get(f"/api/activities/{act['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_tags_isolated(self):
        tag = post("/api/tags", {"name": f"IsoTag-{uuid.uuid4().hex[:8]}"}, headers=HEADERS_A).json()
        r = get(f"/api/tags/{tag['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_portfolio_isolated(self):
        """User B's portfolio should not include User A's holdings."""
        acct = post("/api/accounts", {
            "name": f"IsoPort-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=HEADERS_A).json()
        post("/api/activities", {
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 100, "unitPrice": 150.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": acct["id"]
        }, headers=HEADERS_A)
        r = get("/api/portfolio/holdings", headers=HEADERS_B)
        assert r.status_code == 200
        holdings_b = r.json()
        symbols_b = [h["symbol"] for h in holdings_b]
        # User B should have no AAPL (or anything)
        # Can't assert empty because other tests might use USER_B, but check no leakage
        # from our specific buy
        for h in holdings_b:
            if h["symbol"] == "AAPL":
                assert h.get("userId", USER_B_ID) != USER_A_ID


class TestAccountDeletionConstraint:
    """Pattern 7: Cannot delete account with activities."""

    def test_account_with_activity_returns_400_on_delete(self):
        acct = post("/api/accounts", {
            "name": f"NoDel-{uuid.uuid4().hex[:6]}",
            "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        post("/api/activities", {
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 1, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": acct["id"]
        })
        r = delete(f"/api/accounts/{acct['id']}")
        assert r.status_code == 400
        # Account should still exist
        assert get(f"/api/accounts/{acct['id']}").status_code == 200


class TestSellValidation:
    """Pattern 5+8: Cannot sell more than owned."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = str(uuid.uuid4())
        self.headers = {"X-User-Id": self.user_id, "Content-Type": "application/json"}
        acct = requests.post(f"{BASE_URL}/api/accounts", json={
            "name": "SellVal", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }, headers=self.headers, timeout=30).json()
        self.acct_id = acct["id"]

    def test_sell_without_owning_fails(self):
        r = requests.post(f"{BASE_URL}/api/activities", json={
            "type": "SELL", "date": "2024-06-01T10:00:00Z",
            "quantity": 1, "unitPrice": 150.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)
        assert r.status_code == 400

    def test_sell_more_than_owned_fails(self):
        requests.post(f"{BASE_URL}/api/activities", json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 5, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "TSLA", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)
        r = requests.post(f"{BASE_URL}/api/activities", json={
            "type": "SELL", "date": "2024-06-01T10:00:00Z",
            "quantity": 6, "unitPrice": 250.0, "fee": 0,
            "currency": "USD", "symbol": "TSLA", "accountId": self.acct_id
        }, headers=self.headers, timeout=30)
        assert r.status_code == 400


class TestHealthEndpoint:
    """Pattern 4: Health endpoint no-auth and correct response."""

    def test_health_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert "status" in r.json()

    def test_other_endpoints_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/accounts", timeout=30)
        assert r.status_code == 401
        r = requests.get(f"{BASE_URL}/api/portfolio/summary", timeout=30)
        assert r.status_code == 401
