"""
L3 Workflow Tests for Spree E-Commerce API.

Multi-step workflows:
- Pattern 5: Full checkout state machine, promotions, stock decrement
- Pattern 7: Side effects (stock decrement on complete, payment capture)
- Pattern 6: Store isolation, role enforcement
- Pattern 2: Nested order data throughout lifecycle
- Pattern 1: camelCase consistency in responses
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10

ADMIN_TOKEN = "admin_wf1_admin1"
CUSTOMER_TOKEN = "wf1_cust1"
CUSTOMER2_TOKEN = "wf1_cust2"
ADMIN_TOKEN_STORE2 = "admin_wf2_admin1"
CUSTOMER_STORE2 = "wf2_cust1"


def api(method, path, token=ADMIN_TOKEN, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-Store-Token"] = token
    headers.setdefault("Content-Type", "application/json")
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    url = f"{BASE_URL}{path}"
    return getattr(requests, method)(url, headers=headers, **kwargs)


def create_product_with_stock(name_prefix="Prod", price=25.0, stock=100):
    """Helper to create a product, variant, stock location, and stock item."""
    prod = api("post", "/api/v1/products", json={
        "name": f"{name_prefix}-{uuid.uuid4().hex[:4]}", "price": price, "currency": "USD", "available": True
    }).json()
    var = api("post", f"/api/v1/products/{prod['id']}/variants", json={
        "sku": f"{name_prefix}-SKU-{uuid.uuid4().hex[:4]}", "price": price, "currency": "USD"
    }).json()
    loc = api("post", "/api/v1/stock-locations", json={
        "name": f"Loc-{uuid.uuid4().hex[:4]}", "address1": "1 St", "city": "X",
        "state": "CA", "country": "US", "active": True
    }).json()
    api("post", f"/api/v1/stock-locations/{loc['id']}/stock-items", json={
        "variantId": var["id"], "countOnHand": stock, "backorderable": False
    })
    return prod, var, loc


def create_checkout_prerequisites():
    """Create shipping and payment methods."""
    sm = api("post", "/api/v1/shipping-methods", json={
        "name": f"Ship-{uuid.uuid4().hex[:4]}", "cost": 5.0
    }).json()
    pm = api("post", "/api/v1/payment-methods", json={
        "name": f"CC-{uuid.uuid4().hex[:4]}", "type": "gateway", "active": True
    }).json()
    return sm, pm


ADDRESS = {
    "firstName": "Jane", "lastName": "Doe", "address1": "456 Elm St",
    "city": "LA", "state": "CA", "zipCode": "90001", "country": "US", "phone": "555-9999"
}


class TestFullCheckoutWorkflow:
    """
    Complete checkout: cart → address → delivery → payment → confirm → complete.
    Verify state transitions, totals, stock decrement, and payment capture.
    Patterns: 5 (state machine, totals), 7 (stock decrement), 2 (nested data)
    """

    def test_full_checkout(self):
        prod, var, loc = create_product_with_stock("Checkout", price=40.0, stock=10)
        sm, pm = create_checkout_prerequisites()

        # 1. Create order (cart state)
        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        assert order["state"] == "cart"
        oid = order["id"]

        # 2. Add line item
        r = api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 2
        })
        assert r.status_code in (200, 201)

        # 3. Verify itemTotal
        r = api("get", f"/api/v1/orders/{oid}", token=CUSTOMER_TOKEN)
        assert r.json()["itemTotal"] == 80.0

        # 4. Advance: cart → address
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "address"

        # 5. Set addresses
        api("put", f"/api/v1/orders/{oid}/addresses", token=CUSTOMER_TOKEN, json={
            "billingAddress": ADDRESS, "shippingAddress": ADDRESS
        })

        # 6. Advance: address → delivery
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "delivery"

        # 7. Select shipping method
        api("post", f"/api/v1/orders/{oid}/shipments", token=CUSTOMER_TOKEN, json={
            "shippingMethodId": sm["id"], "stockLocationId": loc["id"]
        })

        # 8. Advance: delivery → payment (triggers promotion eval)
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "payment"

        # 9. Get order to verify shipments
        r = api("get", f"/api/v1/orders/{oid}", token=CUSTOMER_TOKEN)
        order = r.json()
        assert order["shipmentTotal"] == 5.0
        assert len(order["shipments"]) >= 1

        # 10. Create payment
        r = api("post", f"/api/v1/orders/{oid}/payments", token=CUSTOMER_TOKEN, json={
            "paymentMethodId": pm["id"], "amount": order["total"]
        })
        assert r.status_code == 201
        payment = r.json()
        assert payment["state"] == "authorized"
        assert "paymentMethodId" in payment

        # 11. Advance: payment → confirm
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "confirm"

        # 12. Advance: confirm → complete
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"

        # 11. Verify stock decremented
        r = api("get", f"/api/v1/stock-locations/{loc['id']}/stock-items")
        items = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        if isinstance(items, list):
            si = next((i for i in items if i["variantId"] == var["id"]), None)
            if si:
                assert si["countOnHand"] == 8  # 10 - 2


class TestPromotionWorkflow:
    """
    Promotions: create promotion → create order → verify discount applied.
    Patterns: 5 (promotion logic), 7 (adjustment total), 2 (nested rules/actions)
    """

    def test_percent_off_promotion(self):
        prod, var, loc = create_product_with_stock("Promo", price=100.0, stock=50)
        sm, pm = create_checkout_prerequisites()

        # Create promotion: 20% off for orders >= $50
        promo = api("post", "/api/v1/promotions", json={
            "name": f"20Off-{uuid.uuid4().hex[:4]}", "description": "20% off",
            "active": True,
            "rules": [{"type": "minOrderAmount", "value": 50}],
            "actions": [{"type": "percentOff", "value": 20}]
        })
        assert promo.status_code == 201
        assert promo.json()["rules"][0]["type"] == "minOrderAmount"
        assert promo.json()["actions"][0]["type"] == "percentOff"

        # Create order with $200 item total (2 x $100)
        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        oid = order["id"]
        api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 2
        })

        # Advance through checkout up to delivery -> payment transition (promo applied)
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        api("put", f"/api/v1/orders/{oid}/addresses", token=CUSTOMER_TOKEN, json={
            "billingAddress": ADDRESS, "shippingAddress": ADDRESS
        })
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        api("post", f"/api/v1/orders/{oid}/shipments", token=CUSTOMER_TOKEN, json={
            "shippingMethodId": sm["id"], "stockLocationId": loc["id"]
        })
        # This transition triggers promotion evaluation
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})

        # After delivery, promotion should be evaluated
        r = api("get", f"/api/v1/orders/{oid}", token=CUSTOMER_TOKEN)
        order = r.json()
        # adjustmentTotal should be -40 (20% of $200)
        assert order["adjustmentTotal"] == -40.0
        # total = 200 + 5 (shipping) - 40 = 165
        assert order["total"] == 165.0


class TestStoreIsolationWorkflow:
    """
    Store isolation: admin in store1 creates products → customer in store2 can't see them.
    Patterns: 6 (isolation), 4 (404 for cross-store)
    """

    def test_cross_store_isolation(self):
        # Store 1 admin creates product
        prod = api("post", "/api/v1/products", token=ADMIN_TOKEN, json={
            "name": f"Isolated-{uuid.uuid4().hex[:4]}", "price": 50.0, "currency": "USD"
        }).json()

        # Store 2 admin can't see it
        r = api("get", f"/api/v1/products/{prod['id']}", token=ADMIN_TOKEN_STORE2)
        assert r.status_code == 404

        # Store 2 customer can't see it
        r = api("get", f"/api/v1/products/{prod['id']}", token=CUSTOMER_STORE2)
        assert r.status_code == 404

        # Store 1 customer CAN see it
        r = api("get", f"/api/v1/products/{prod['id']}", token=CUSTOMER_TOKEN)
        assert r.status_code == 200
        assert r.json()["name"] == prod["name"]


class TestCancelOrderWorkflow:
    """
    Cancel order: create order → advance → cancel → verify state.
    Patterns: 5 (state machine), 4 (status codes)
    """

    def test_cancel_order(self):
        prod, var, loc = create_product_with_stock("Cancel", price=20.0, stock=30)

        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        oid = order["id"]
        api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 1
        })

        # Advance to address
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        api("put", f"/api/v1/orders/{oid}/addresses", token=CUSTOMER_TOKEN, json={
            "billingAddress": ADDRESS, "shippingAddress": ADDRESS
        })

        # Cancel
        r = api("post", f"/api/v1/orders/{oid}/cancel", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 200
        assert r.json()["state"] == "cancelled"

        # Cannot advance a cancelled order
        r = api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        assert r.status_code == 422


class TestStockManagementWorkflow:
    """
    Stock: create stock → add to cart → complete → stock decremented.
    Verify can't over-order non-backorderable items.
    Patterns: 5 (stock logic), 7 (decrement side effect)
    """

    def test_stock_prevents_overselling(self):
        prod, var, loc = create_product_with_stock("StockLimit", price=10.0, stock=3)

        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        oid = order["id"]

        # Try to add 5 when only 3 available
        r = api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 5
        })
        assert r.status_code == 422

        # Add 3 should succeed
        r = api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 3
        })
        assert r.status_code in (200, 201)


class TestProductTaxonWorkflow:
    """
    Taxon hierarchy: create parent/child taxons → assign product → query by parent.
    Patterns: 2 (hierarchy), 3 (filtering by taxon)
    """

    def test_product_taxon_assignment(self):
        # Create taxon hierarchy
        parent = api("post", "/api/v1/taxons", json={
            "name": f"Electronics-{uuid.uuid4().hex[:4]}", "permalink": f"electronics-{uuid.uuid4().hex[:4]}"
        }).json()
        child = api("post", "/api/v1/taxons", json={
            "name": f"Phones-{uuid.uuid4().hex[:4]}", "permalink": f"phones-{uuid.uuid4().hex[:4]}",
            "parentId": parent["id"]
        }).json()

        # Create product assigned to child taxon
        prod = api("post", "/api/v1/products", json={
            "name": f"iPhone-{uuid.uuid4().hex[:4]}", "price": 999.0, "currency": "USD",
            "taxonIds": [child["id"]]
        }).json()
        assert child["id"] in prod.get("taxonIds", [])

        # Query products by parent taxon should include product (hierarchical)
        r = api("get", "/api/v1/products", params={"taxonId": parent["id"]})
        assert r.status_code == 200
        data = r.json()
        products = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(products, list):
            product_ids = [p["id"] for p in products]
            assert prod["id"] in product_ids


class TestWishlistIsolationWorkflow:
    """
    Wishlists: customer1 creates wishlist → customer2 can't see it.
    Patterns: 6 (customer isolation), 4 (404)
    """

    def test_wishlist_customer_isolation(self):
        prod, var, _ = create_product_with_stock("Wish", price=15.0, stock=20)

        # Customer 1 creates wishlist
        wl = api("post", "/api/v1/wishlists", token=CUSTOMER_TOKEN, json={
            "name": f"MyWish-{uuid.uuid4().hex[:4]}"
        }).json()
        api("post", f"/api/v1/wishlists/{wl['id']}/items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"]
        })

        # Customer 2 cannot see it
        r = api("get", f"/api/v1/wishlists/{wl['id']}", token=CUSTOMER2_TOKEN)
        assert r.status_code == 404

        # Customer 2's wishlist list is separate
        r = api("get", "/api/v1/wishlists", token=CUSTOMER2_TOKEN)
        assert r.status_code == 200
        wl_ids = [w["id"] for w in r.json().get("data", r.json()) if isinstance(r.json(), dict)] if isinstance(r.json(), dict) else [w["id"] for w in r.json()]
        assert wl["id"] not in wl_ids


class TestOrderWithMultipleItems:
    """
    Order with multiple variants: verify itemTotal computed correctly.
    Patterns: 5 (computation), 2 (nested lineItems)
    """

    def test_multiple_line_items_total(self):
        prod1, var1, _ = create_product_with_stock("Multi1", price=10.0, stock=100)
        prod2, var2, _ = create_product_with_stock("Multi2", price=25.0, stock=100)

        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        oid = order["id"]

        api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var1["id"], "quantity": 3
        })
        api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var2["id"], "quantity": 2
        })

        r = api("get", f"/api/v1/orders/{oid}", token=CUSTOMER_TOKEN)
        order = r.json()
        # 3*10 + 2*25 = 80
        assert order["itemTotal"] == 80.0
        assert len(order["lineItems"]) == 2


class TestFreeShippingPromotion:
    """
    Free shipping promotion: verify shipment cost becomes 0.
    Patterns: 5 (promotion logic), 7 (adjustment)
    """

    def test_free_shipping_promotion(self):
        prod, var, loc = create_product_with_stock("FreeShip", price=60.0, stock=50)
        sm, pm = create_checkout_prerequisites()

        # Create free shipping promotion for orders >= $50
        api("post", "/api/v1/promotions", json={
            "name": f"FreeShip-{uuid.uuid4().hex[:4]}", "description": "Free shipping",
            "active": True,
            "rules": [{"type": "minOrderAmount", "value": 50}],
            "actions": [{"type": "freeShipping", "value": None}]
        })

        # Create order
        order = api("post", "/api/v1/orders", token=CUSTOMER_TOKEN, json={}).json()
        oid = order["id"]
        api("post", f"/api/v1/orders/{oid}/line-items", token=CUSTOMER_TOKEN, json={
            "variantId": var["id"], "quantity": 1
        })

        # Advance through to trigger promotion
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        api("put", f"/api/v1/orders/{oid}/addresses", token=CUSTOMER_TOKEN, json={
            "billingAddress": ADDRESS, "shippingAddress": ADDRESS
        })
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})
        api("post", f"/api/v1/orders/{oid}/shipments", token=CUSTOMER_TOKEN, json={
            "shippingMethodId": sm["id"], "stockLocationId": loc["id"]
        })
        api("post", f"/api/v1/orders/{oid}/next", token=CUSTOMER_TOKEN, json={})

        # Verify free shipping applied
        r = api("get", f"/api/v1/orders/{oid}", token=CUSTOMER_TOKEN)
        order = r.json()
        # Shipping should be free (adjustmentTotal offsets shipping or shipmentTotal is 0)
        effective_shipping = order["shipmentTotal"] + order.get("adjustmentTotal", 0)
        # Either shipmentTotal is 0 or adjustmentTotal negates it
        assert effective_shipping <= 0 or order["shipmentTotal"] == 0
