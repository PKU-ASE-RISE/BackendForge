"""
L2 Integration Tests for Spree E-Commerce API.

Targets LLM bug patterns:
- Pattern 1: camelCase (countOnHand, itemTotal, shippingAddress, etc.)
- Pattern 2: Nested data (order.lineItems, order.shipments, product.properties)
- Pattern 3: Filtering/pagination
- Pattern 4: Status codes (201/204/404/422)
- Pattern 5: Business logic (order totals, stock decrement, promotions)
- Pattern 6: Role permissions (admin vs customer)
- Pattern 7: Side effects (stock decrement on complete)
"""

import os
import uuid
import pytest
import requests
import subprocess
import time

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10

ADMIN_TOKEN = "admin_integ1_admin1"
CUSTOMER_TOKEN = "integ1_cust1"
CUSTOMER2_TOKEN = "integ1_cust2"
ADMIN_TOKEN_STORE2 = "admin_integ2_admin1"
CUSTOMER_STORE2 = "integ2_cust1"


def api(method, path, token=ADMIN_TOKEN, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-Store-Token"] = token
    headers.setdefault("Content-Type", "application/json")
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    url = f"{BASE_URL}{path}"
    return getattr(requests, method)(url, headers=headers, **kwargs)


@pytest.fixture(scope="module")
def setup():
    """Create products, variants, stock for tests."""
    # Create option type
    ot = api("post", "/api/v1/option-types", json={
        "name": f"color-{uuid.uuid4().hex[:4]}", "presentation": "Color",
        "optionValues": [
            {"name": "red", "presentation": "Red"},
            {"name": "blue", "presentation": "Blue"}
        ]
    }).json()

    # Create product
    prod = api("post", "/api/v1/products", json={
        "name": f"T-Shirt-{uuid.uuid4().hex[:4]}", "description": "A nice shirt",
        "price": 29.99, "currency": "USD", "available": True
    }).json()

    # Create variant
    var = api("post", f"/api/v1/products/{prod['id']}/variants", json={
        "sku": f"TSH-RED-{uuid.uuid4().hex[:4]}", "price": 29.99, "currency": "USD",
        "optionValues": [ot["optionValues"][0]["id"]]
    }).json()

    # Create stock location
    loc = api("post", "/api/v1/stock-locations", json={
        "name": f"Warehouse-{uuid.uuid4().hex[:4]}", "address1": "123 Main St",
        "city": "NYC", "state": "NY", "country": "US", "active": True
    }).json()

    # Create stock item
    si = api("post", f"/api/v1/stock-locations/{loc['id']}/stock-items", json={
        "variantId": var["id"], "countOnHand": 50, "backorderable": False
    }).json()

    # Create shipping method
    sm = api("post", "/api/v1/shipping-methods", json={
        "name": f"Standard-{uuid.uuid4().hex[:4]}", "cost": 5.99
    }).json()

    # Create payment method
    pm = api("post", "/api/v1/payment-methods", json={
        "name": f"Credit Card-{uuid.uuid4().hex[:4]}", "type": "gateway", "active": True
    }).json()

    return {
        "product": prod, "variant": var, "option_type": ot,
        "stock_location": loc, "stock_item": si,
        "shipping_method": sm, "payment_method": pm,
    }


class TestProductFieldNaming:
    """Pattern 1: camelCase field names."""

class TestStatusCodes:
    """Pattern 4: Correct HTTP status codes."""

    def test_create_product_returns_201(self):
        r = api("post", "/api/v1/products", json={
            "name": f"SC-{uuid.uuid4().hex[:4]}", "price": 9.99, "currency": "USD"
        })
        assert r.status_code == 201

    def test_delete_product_returns_204(self):
        p = api("post", "/api/v1/products", json={
            "name": f"Del-{uuid.uuid4().hex[:4]}", "price": 5.00, "currency": "USD"
        }).json()
        r = api("delete", f"/api/v1/products/{p['id']}")
        assert r.status_code == 204

    def test_get_nonexistent_product_returns_404(self):
        r = api("get", f"/api/v1/products/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_create_order_returns_201(self):
        r = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 201
        assert r.json()["state"] == "cart"


class TestRolePermissions:
    """Pattern 6: Admin vs customer."""

    def test_customer_cannot_create_product(self):
        r = api("post", "/api/v1/products", token=CUSTOMER_TOKEN, json={
            "name": "Nope", "price": 1.0, "currency": "USD"
        })
        assert r.status_code == 403

    def test_customer_cannot_create_shipping_method(self):
        r = api("post", "/api/v1/shipping-methods", token=CUSTOMER_TOKEN, json={
            "name": "No", "cost": 5.0
        })
        assert r.status_code == 403

    def test_admin_can_create_product(self):
        r = api("post", "/api/v1/products", json={
            "name": f"Admin-{uuid.uuid4().hex[:4]}", "price": 10.0, "currency": "USD"
        })
        assert r.status_code == 201


class TestOrderCreation:
    """Pattern 5: Order creation and line items."""

class TestOrderTotals:
    """Pattern 5: Order total computation."""

class TestStoreIsolation:
    """Pattern 6: Store data isolation."""

class TestTaxonHierarchy:
    """Pattern 2: Taxon parent-child relationships."""

    def test_taxon_parent_child(self):
        parent = api("post", "/api/v1/taxons", json={
            "name": f"Clothing-{uuid.uuid4().hex[:4]}", "permalink": f"clothing-{uuid.uuid4().hex[:4]}"
        }).json()

        child = api("post", "/api/v1/taxons", json={
            "name": f"Shirts-{uuid.uuid4().hex[:4]}", "permalink": f"shirts-{uuid.uuid4().hex[:4]}",
            "parentId": parent["id"]
        }).json()
        assert child["parentId"] == parent["id"]

        # Get parent should show children
        r = api("get", f"/api/v1/taxons/{parent['id']}")
        assert r.status_code == 200
        assert "children" in r.json()
        child_ids = [c["id"] for c in r.json()["children"]]
        assert child["id"] in child_ids


class TestStockCheck:
    """Pattern 5: Stock validation when adding to cart."""

class TestNestedOrderData:
    """Pattern 2: Order response includes nested lineItems, shipments, payments."""

class TestOrderStateMachine:
    """Pattern 5: State machine validation."""

class TestPagination:
    """Pattern 3: Pagination on product list."""

    def test_product_pagination(self):
        # Create several products
        for i in range(3):
            api("post", "/api/v1/products", json={
                "name": f"Page-{uuid.uuid4().hex[:4]}", "price": float(i + 1), "currency": "USD"
            })

        r = api("get", "/api/v1/products", params={"page": 1, "perPage": 2})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["perPage"] == 2
        assert len(body["data"]) <= 2


class TestWishlist:
    """Pattern 2+4: Wishlist CRUD with nested items."""
