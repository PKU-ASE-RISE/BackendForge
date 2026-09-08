"""
BackendForge — L3 Workflow Tests for Ghostfolio Task

Multi-step adversarial workflow tests covering portfolio calculations,
import/export, currency conversion, and complex scenarios.

"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api(method, path, headers, json=None, params=None):
    return getattr(requests, method)(
        f"{BASE_URL}{path}", json=json, params=params, headers=headers, timeout=30
    )


class TestPortfolioLifecycle:
    """Pattern 2+5+7: Full portfolio lifecycle with computed values verification."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "Main", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]
        cash = api("post", "/api/accounts", self.headers, json={
            "name": "Cash", "accountType": "CASH", "currency": "USD", "balance": 10000.0
        }).json()
        self.cash_id = cash["id"]

    def test_buy_dividend_fee_portfolio_summary(self):
        """
        Buy 10 AAPL @100, receive dividend $2/share, pay $30 fee.
        Verify all summary fields computed correctly.
        """
        # Buy
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-15T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 10.0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        })
        # Dividend
        api("post", "/api/activities", self.headers, json={
            "type": "DIVIDEND", "date": "2024-04-01T10:00:00Z",
            "quantity": 10, "unitPrice": 2.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        })
        # Fee
        api("post", "/api/activities", self.headers, json={
            "type": "FEE", "date": "2024-05-01T10:00:00Z",
            "quantity": 1, "unitPrice": 30.0, "fee": 0,
            "currency": "USD", "symbol": None, "accountId": self.acct_id
        })
        # Interest
        api("post", "/api/activities", self.headers, json={
            "type": "INTEREST", "date": "2024-06-01T10:00:00Z",
            "quantity": 1, "unitPrice": 15.0, "fee": 0,
            "currency": "USD", "symbol": None, "accountId": self.acct_id
        })

        # Verify holdings
        r = api("get", "/api/portfolio/holdings", self.headers)
        holdings = r.json()
        aapl = next(h for h in holdings if h["symbol"] == "AAPL")
        assert aapl["quantity"] == 10
        assert aapl["marketPrice"] == 150.0
        assert aapl["marketValue"] == 1500.0

        # Verify summary
        r = api("get", "/api/portfolio/summary", self.headers)
        s = r.json()
        assert s["totalInvested"] == 1000.0  # 10*100
        assert s["currentValue"] == 11500.0  # 10*150 + 10000 cash
        assert s["totalDividends"] == 20.0  # 10*2
        assert s["totalInterest"] == 15.0
        assert s["totalFees"] == 40.0  # 10 (buy fee) + 30 (standalone)
        # totalGain = (1500-1000) + 20 + 15 - 40 = 495
        assert abs(s["totalGain"] - 495.0) < 0.01
        assert s["cashPositions"] == 10000.0
        assert s["holdings"] == 1


class TestBuySellQuantityTracking:
    """Pattern 5+7: Buy/sell affects holdings, sell removes zero-qty holdings."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "BuySell", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]

    def test_buy_sell_partial_and_full(self):
        """
        Buy 20 MSFT, sell 5, verify holding=15. Sell remaining 15, verify gone.
        """
        # Buy 20
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 20, "unitPrice": 350.0, "fee": 0,
            "currency": "USD", "symbol": "MSFT", "accountId": self.acct_id
        })

        # Sell 5
        api("post", "/api/activities", self.headers, json={
            "type": "SELL", "date": "2024-03-01T10:00:00Z",
            "quantity": 5, "unitPrice": 400.0, "fee": 0,
            "currency": "USD", "symbol": "MSFT", "accountId": self.acct_id
        })

        # Verify 15 remaining
        r = api("get", "/api/portfolio/holdings", self.headers)
        msft = next(h for h in r.json() if h["symbol"] == "MSFT")
        assert msft["quantity"] == 15
        assert msft["averageCost"] == 350.0  # Average cost unchanged by sells
        assert msft["marketValue"] == 6000.0  # 15 * 400

        # Sell remaining 15
        api("post", "/api/activities", self.headers, json={
            "type": "SELL", "date": "2024-06-01T10:00:00Z",
            "quantity": 15, "unitPrice": 400.0, "fee": 0,
            "currency": "USD", "symbol": "MSFT", "accountId": self.acct_id
        })

        # Should be gone from holdings
        r = api("get", "/api/portfolio/holdings", self.headers)
        symbols = [h["symbol"] for h in r.json()]
        assert "MSFT" not in symbols

        # Holding detail should 404
        r = api("get", "/api/portfolio/holdings/MSFT", self.headers)
        assert r.status_code == 404


class TestImportExportRoundtrip:
    """Pattern 5+7: Import, verify via holdings, export, verify format."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "ImportExport", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]

    def test_import_verify_export_roundtrip(self):
        """Import 3 activities → verify holdings → export → check format."""
        # Import
        r = api("post", "/api/import", self.headers, json={
            "activities": [
                {"type": "BUY", "date": "2024-01-01T10:00:00Z", "quantity": 10,
                 "unitPrice": 100.0, "fee": 5.0, "currency": "USD",
                 "symbol": "AAPL", "accountId": self.acct_id},
                {"type": "BUY", "date": "2024-02-01T10:00:00Z", "quantity": 5,
                 "unitPrice": 130.0, "fee": 0, "currency": "USD",
                 "symbol": "GOOGL", "accountId": self.acct_id},
                {"type": "DIVIDEND", "date": "2024-03-01T10:00:00Z", "quantity": 10,
                 "unitPrice": 1.0, "fee": 0, "currency": "USD",
                 "symbol": "AAPL", "accountId": self.acct_id}
            ]
        })
        assert r.status_code == 201
        assert r.json()["count"] == 3

        # Verify holdings
        r = api("get", "/api/portfolio/holdings", self.headers)
        holdings = r.json()
        assert len(holdings) == 2
        aapl = next(h for h in holdings if h["symbol"] == "AAPL")
        assert aapl["quantity"] == 10  # Dividend doesn't change qty
        googl = next(h for h in holdings if h["symbol"] == "GOOGL")
        assert googl["quantity"] == 5

        # Export
        r = api("get", "/api/export", self.headers)
        assert r.status_code == 200
        export_data = r.json()
        assert "activities" in export_data
        assert len(export_data["activities"]) == 3
        # Verify export has correct fields
        for act in export_data["activities"]:
            assert "type" in act
            assert "date" in act
            assert "quantity" in act
            assert "unitPrice" in act
            assert "accountId" in act

    def test_import_atomic_failure(self):
        """If one activity invalid, nothing imported."""
        r = api("post", "/api/import", self.headers, json={
            "activities": [
                {"type": "BUY", "date": "2024-01-01T10:00:00Z", "quantity": 10,
                 "unitPrice": 100.0, "fee": 0, "currency": "USD",
                 "symbol": "AAPL", "accountId": self.acct_id},
                {"type": "SELL", "date": "2024-01-02T10:00:00Z", "quantity": 999,
                 "unitPrice": 100.0, "fee": 0, "currency": "USD",
                 "symbol": "NVDA", "accountId": self.acct_id}  # Can't sell without buying
            ]
        })
        assert r.status_code == 400

        # Nothing imported
        r = api("get", "/api/activities", self.headers)
        assert len(r.json()) == 0


class TestTagsOnActivitiesWorkflow:
    """Pattern 2+7: Tags attached to activities, deletion removes association."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "TagWF", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]

    def test_tag_lifecycle_on_activities(self):
        """
        Create tags → attach to activity → verify → update tag → verify name changes →
        delete tag → verify removed from activity but activity persists.
        """
        # Create two tags
        t1 = api("post", "/api/tags", self.headers, json={"name": f"T1-{uuid.uuid4().hex[:6]}"}).json()
        t2 = api("post", "/api/tags", self.headers, json={"name": f"T2-{uuid.uuid4().hex[:6]}"}).json()

        # Create activity with both tags
        act = api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 5, "unitPrice": 150.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id,
            "tagIds": [t1["id"], t2["id"]]
        }).json()
        assert len(act["tags"]) == 2
        tag_ids = [t["id"] for t in act["tags"]]
        assert t1["id"] in tag_ids
        assert t2["id"] in tag_ids

        # Update tag name
        new_name = f"Updated-{uuid.uuid4().hex[:6]}"
        api("put", f"/api/tags/{t1['id']}", self.headers, json={"name": new_name})

        # Verify tag name updated in activity response
        r = api("get", f"/api/activities/{act['id']}", self.headers)
        act_data = r.json()
        tag1_in_act = next(t for t in act_data["tags"] if t["id"] == t1["id"])
        assert tag1_in_act["name"] == new_name

        # Delete tag t2
        r = api("delete", f"/api/tags/{t2['id']}", self.headers)
        assert r.status_code == 204

        # Activity still exists with only t1
        r = api("get", f"/api/activities/{act['id']}", self.headers)
        assert r.status_code == 200
        assert len(r.json()["tags"]) == 1
        assert r.json()["tags"][0]["id"] == t1["id"]


class TestCurrencyConversionWorkflow:
    """Pattern 5: Portfolio values converted to base currency."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        # EUR account
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "EUR Broker", "accountType": "SECURITIES", "currency": "EUR", "balance": 0
        }).json()
        self.eur_acct_id = acct["id"]

    def test_eur_buy_converted_to_usd_in_portfolio(self):
        """
        Buy 10 AAPL @ 100 EUR. User base = USD. EUR→USD = 1.08.
        averageCost = 108 USD. marketValue = 10*150 = 1500 USD.
        """
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 0,
            "currency": "EUR", "symbol": "AAPL", "accountId": self.eur_acct_id
        })

        r = api("get", "/api/portfolio/holdings/AAPL", self.headers)
        assert r.status_code == 200
        h = r.json()
        assert h["quantity"] == 10
        # averageCost in USD = 100 * 1.08 = 108
        assert abs(h["averageCost"] - 108.0) < 0.01
        # totalCost = 10 * 108 = 1080
        assert abs(h["totalCost"] - 1080.0) < 0.01
        assert h["marketPrice"] == 150.0
        assert abs(h["marketValue"] - 1500.0) < 0.01
        # unrealizedGain = (150 - 108) * 10 = 420
        assert abs(h["unrealizedGain"] - 420.0) < 0.01

        # Summary
        r = api("get", "/api/portfolio/summary", self.headers)
        s = r.json()
        # totalInvested in USD = 10 * 100 * 1.08 = 1080
        assert abs(s["totalInvested"] - 1080.0) < 0.01


class TestMultiHoldingPortfolio:
    """Pattern 5: Multiple holdings with different symbols verified together."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "MultiH", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]
        api("post", "/api/accounts", self.headers, json={
            "name": "Cash", "accountType": "CASH", "currency": "USD", "balance": 5000.0
        })

    def test_three_holdings_portfolio_summary(self):
        """
        Buy AAPL 10@100, GOOGL 5@120, NVDA 2@700.
        Verify each holding + summary totals.
        """
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        })
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-02-01T10:00:00Z",
            "quantity": 5, "unitPrice": 120.0, "fee": 0,
            "currency": "USD", "symbol": "GOOGL", "accountId": self.acct_id
        })
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-03-01T10:00:00Z",
            "quantity": 2, "unitPrice": 700.0, "fee": 0,
            "currency": "USD", "symbol": "NVDA", "accountId": self.acct_id
        })

        # Verify individual holdings
        r = api("get", "/api/portfolio/holdings", self.headers)
        holdings = r.json()
        assert len(holdings) == 3
        aapl = next(h for h in holdings if h["symbol"] == "AAPL")
        assert aapl["quantity"] == 10
        assert aapl["marketValue"] == 1500.0  # 10*150
        googl = next(h for h in holdings if h["symbol"] == "GOOGL")
        assert googl["quantity"] == 5
        assert googl["marketValue"] == 700.0  # 5*140
        nvda = next(h for h in holdings if h["symbol"] == "NVDA")
        assert nvda["quantity"] == 2
        assert nvda["marketValue"] == 1600.0  # 2*800

        # Verify summary
        r = api("get", "/api/portfolio/summary", self.headers)
        s = r.json()
        # totalInvested = 10*100 + 5*120 + 2*700 = 1000 + 600 + 1400 = 3000
        assert s["totalInvested"] == 3000.0
        # currentValue = 1500 + 700 + 1600 + 5000 = 8800
        assert s["currentValue"] == 8800.0
        assert s["holdings"] == 3
        # totalGain = (3800 - 3000) + 0 + 0 - 0 = 800
        assert abs(s["totalGain"] - 800.0) < 0.01
        # gainPercent = 800/3000 * 100 ≈ 26.67
        assert abs(s["totalGainPercent"] - (800.0/3000.0*100)) < 0.1


class TestUserProfileWorkflow:
    """Pattern 1+5: User profile creation and update."""

    def test_auto_create_and_update_base_currency(self):
        """New user auto-created with USD, can update to EUR."""
        headers = make_headers()
        # Auto-create
        r = api("get", "/api/user", headers)
        assert r.status_code == 200
        user = r.json()
        assert user["baseCurrency"] == "USD"
        assert "id" in user
        assert "dateCreated" in user

        # Update
        r = api("put", "/api/user", headers, json={"baseCurrency": "EUR"})
        assert r.status_code == 200
        assert r.json()["baseCurrency"] == "EUR"

        # Verify persisted
        r = api("get", "/api/user", headers)
        assert r.json()["baseCurrency"] == "EUR"


class TestItemActivityInPortfolio:
    """Pattern 5: ITEM activities count in portfolio value."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "ItemAcct", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]

    def test_item_included_in_portfolio(self):
        """ITEM with unitPrice contributes to portfolio value."""
        api("post", "/api/activities", self.headers, json={
            "type": "ITEM", "date": "2024-01-01T10:00:00Z",
            "quantity": 1, "unitPrice": 50000.0, "fee": 0,
            "currency": "USD", "symbol": None, "accountId": self.acct_id
        })

        r = api("get", "/api/portfolio/summary", self.headers)
        s = r.json()
        assert s["totalInvested"] == 50000.0
        assert s["currentValue"] == 50000.0
        assert s["totalGain"] == 0
        assert s["totalGainPercent"] == 0


class TestPerformanceEndpoint:
    """Pattern 1+5: Performance endpoint returns correct structure and values."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = make_headers()
        acct = api("post", "/api/accounts", self.headers, json={
            "name": "Perf", "accountType": "SECURITIES", "currency": "USD", "balance": 0
        }).json()
        self.acct_id = acct["id"]
        api("post", "/api/accounts", self.headers, json={
            "name": "PerfCash", "accountType": "CASH", "currency": "USD", "balance": 3000.0
        })

    def test_performance_matches_summary(self):
        """Performance endpoint should have same core values as summary."""
        api("post", "/api/activities", self.headers, json={
            "type": "BUY", "date": "2024-01-01T10:00:00Z",
            "quantity": 10, "unitPrice": 100.0, "fee": 0,
            "currency": "USD", "symbol": "AAPL", "accountId": self.acct_id
        })

        perf = api("get", "/api/portfolio/performance", self.headers).json()
        summary = api("get", "/api/portfolio/summary", self.headers).json()

        assert "totalInvested" in perf
        assert "currentValue" in perf
        assert "totalGain" in perf
        assert "totalGainPercent" in perf
        assert perf["totalInvested"] == summary["totalInvested"]
        assert perf["currentValue"] == summary["currentValue"]
        assert abs(perf["totalGain"] - summary["totalGain"]) < 0.01
        assert abs(perf["totalGainPercent"] - summary["totalGainPercent"]) < 0.01
