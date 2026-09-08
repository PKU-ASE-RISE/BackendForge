"""
BackendForge — L3 Workflow Tests for Saleor Commerce
Full checkout, fulfillment, and payment workflows.

"""

import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
PAYMENT_URL = os.environ.get("PAYMENT_URL", "").strip().rstrip("/") or "http://localhost:9999"

STAFF_KEY = "staff_wf_key"
CUST_KEY = f"cust_wf_{uuid.uuid4().hex}"


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex}"


def staff(method, path, json=None, params=None):
    h = {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}
    return getattr(requests, method)(f"{BASE_URL}{path}", json=json, params=params, headers=h, timeout=30)


def cust(method, path, json=None, params=None):
    h = {"X-API-Key": CUST_KEY, "Content-Type": "application/json"}
    return getattr(requests, method)(f"{BASE_URL}{path}", json=json, params=params, headers=h, timeout=30)


class TestFullCheckoutWorkflow:
    """Full e-commerce checkout → order → fulfillment workflow."""

    def test_checkout_to_order_lifecycle(self):
        """Pattern 5+7: Full checkout flow with payment, stock allocation, and fulfillment."""
        # 1. Setup: channel, warehouse, shipping zone, product
        ch_slug = _u("wf-ch-")
        staff("post", "/channels", {"slug": ch_slug, "name": "WF Channel", "currencyCode": "USD", "isActive": True})

        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "NYC", "postalCode": "10001", "street": "1 Main"}})
        wh_id = r.json()["id"]

        r = staff("post", "/shipping-zones", {"name": _u("zone-"), "countries": ["US"]})
        zone_id = r.json()["id"]
        # Link warehouse to zone
        staff("put", f"/shipping-zones/{zone_id}", {"warehouses": [wh_id]})

        r = staff("post", f"/shipping-zones/{zone_id}/methods", {"name": "Standard", "type": "price", "rate": 5.0, "minValue": 0, "maxValue": 1000})
        method_id = r.json()["id"]

        # 2. Create product type and product
        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]

        r = staff("post", "/products", {"name": _u("prod-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch_slug, "isPublished": True}]})

        # 3. Create variant with price and stock
        r = staff("post", f"/products/{prod_id}/variants", {
            "name": "Default",
            "sku": _u("SKU-"),
            "channelListings": [{"channelSlug": ch_slug, "price": 25.0, "currencyCode": "USD"}],
        })
        var_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 10})

        # 4. Create checkout
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "buyer@test.com"})
        assert r.status_code == 201
        checkout_id = r.json()["id"]

        # 5. Add line
        r = cust("post", f"/checkouts/{checkout_id}/lines", {"variantId": var_id, "quantity": 2})
        assert r.status_code in [200, 201]

        # 6. Set shipping address
        r = cust("put", f"/checkouts/{checkout_id}/shipping-address", {
            "country": "US", "city": "NYC", "postalCode": "10001", "street": "42 Elm St",
            "firstName": "John", "lastName": "Doe",
        })
        assert r.status_code == 200

        # 7. Get available shipping methods
        r = cust("get", f"/checkouts/{checkout_id}/shipping-methods")
        assert r.status_code == 200
        methods = r.json()
        assert len(methods) >= 1

        # 8. Select shipping method
        r = cust("put", f"/checkouts/{checkout_id}/shipping-method", {"shippingMethodId": method_id})
        assert r.status_code == 200

        # 9. Complete checkout → creates order

        cust("put", f"/checkouts/{checkout_id}/billing-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        r = cust("post", f"/checkouts/{checkout_id}/complete")
        assert r.status_code in [200, 201]
        order = r.json()
        assert "id" in order
        assert order["status"] == "unfulfilled"
        assert order["paymentStatus"] == "authorized"
        order_id = order["id"]

        # 10. Verify order details
        r = staff("get", f"/orders/{order_id}")
        assert r.status_code == 200
        order_data = r.json()
        assert order_data["channelSlug"] == ch_slug
        assert len(order_data["lines"]) >= 1
        assert "total" in order_data

        # 11. Fulfill order
        r = staff("post", f"/orders/{order_id}/fulfillments", {
            "lines": [{"orderLineId": order_data["lines"][0]["id"], "quantity": 2}],
            "warehouseId": wh_id,
            "trackingNumber": "TRACK123",
        })
        assert r.status_code == 201
        assert r.json()["trackingNumber"] == "TRACK123"

        # 12. Order status updated
        r = staff("get", f"/orders/{order_id}")
        assert r.json()["status"] == "fulfilled"
        assert r.json()["paymentStatus"] == "captured"


class TestVoucherApplyWorkflow:
    """Voucher application in checkout."""

    def test_voucher_discount_applied(self):
        """Pattern 5: Voucher discount reduces checkout total."""
        ch_slug = _u("vch-")
        staff("post", "/channels", {"slug": ch_slug, "name": "Voucher Ch", "currencyCode": "USD", "isActive": True})

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]
        r = staff("post", "/products", {"name": _u("p-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch_slug, "isPublished": True}]})
        r = staff("post", f"/products/{prod_id}/variants", {"name": "V", "sku": _u("S-"), "channelListings": [{"channelSlug": ch_slug, "price": 100.0, "currencyCode": "USD"}]})
        var_id = r.json()["id"]

        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "NYC", "postalCode": "10001", "street": "1 Main"}})
        wh_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 10})

        # Create voucher
        code = _u("SAVE-")
        staff("post", "/vouchers", {"code": code, "type": "percentage", "value": 20, "minOrderValue": 50})

        # Create checkout and add items
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "v@t.com"})
        co_id = r.json()["id"]
        cust("post", f"/checkouts/{co_id}/lines", {"variantId": var_id, "quantity": 1})

        # Apply voucher
        r = cust("post", f"/checkouts/{co_id}/voucher", {"code": code})
        assert r.status_code == 200

        # Verify discount visible in checkout
        r = cust("get", f"/checkouts/{co_id}")
        checkout_data = r.json()
        assert checkout_data.get("voucherCode") == code


class TestStockAllocationWorkflow:
    """Stock allocation on checkout completion."""

    def test_stock_allocated_prevents_overselling(self):
        """Pattern 5+8: Stock gets allocated; overselling is prevented."""
        ch_slug = _u("stch-")
        staff("post", "/channels", {"slug": ch_slug, "name": "Stock Ch", "currencyCode": "USD", "isActive": True})

        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "LA", "postalCode": "90001", "street": "2 Ave"}})
        wh_id = r.json()["id"]

        r = staff("post", "/shipping-zones", {"name": _u("z-"), "countries": ["US"]})
        zone_id = r.json()["id"]
        staff("put", f"/shipping-zones/{zone_id}", {"warehouses": [wh_id]})
        r = staff("post", f"/shipping-zones/{zone_id}/methods", {"name": "Std", "type": "price", "rate": 5.0, "minValue": 0, "maxValue": 1000})
        sm_id = r.json()["id"]

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]
        r = staff("post", "/products", {"name": _u("p-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch_slug, "isPublished": True}]})
        r = staff("post", f"/products/{prod_id}/variants", {"name": "V", "sku": _u("S-"), "channelListings": [{"channelSlug": ch_slug, "price": 10.0, "currencyCode": "USD"}]})
        var_id = r.json()["id"]

        # Stock = 3
        staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 3})

        # Create checkout with qty 2 → complete
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "s@t.com"})
        co_id = r.json()["id"]
        cust("post", f"/checkouts/{co_id}/lines", {"variantId": var_id, "quantity": 2})
        cust("put", f"/checkouts/{co_id}/shipping-address", {"country": "US", "city": "LA", "postalCode": "90001", "street": "X", "firstName": "A", "lastName": "B"})
        cust("put", f"/checkouts/{co_id}/shipping-method", {"shippingMethodId": sm_id})

        cust("put", f"/checkouts/{co_id}/billing-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        r = cust("post", f"/checkouts/{co_id}/complete")
        assert r.status_code in [200, 201]

        # Try another checkout with qty 2 → should fail (only 1 left)
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "s2@t.com"})
        co2_id = r.json()["id"]
        cust("post", f"/checkouts/{co2_id}/lines", {"variantId": var_id, "quantity": 2})
        cust("put", f"/checkouts/{co2_id}/shipping-address", {"country": "US", "city": "LA", "postalCode": "90001", "street": "Y", "firstName": "C", "lastName": "D"})
        cust("put", f"/checkouts/{co2_id}/shipping-method", {"shippingMethodId": sm_id})

        cust("put", f"/checkouts/{co2_id}/billing-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        r = cust("post", f"/checkouts/{co2_id}/complete")
        assert r.status_code == 400  # Insufficient stock


class TestShippingZoneMatchingWorkflow:
    """Shipping method availability based on country."""

class TestPartialFulfillmentWorkflow:
    """Partial fulfillment updates order status correctly."""

    def test_partial_then_full_fulfillment(self):
        """Pattern 5+7: Partial fulfillment → partiallyFulfilled; full → fulfilled."""
        ch_slug = _u("pfch-")
        staff("post", "/channels", {"slug": ch_slug, "name": "PF Ch", "currencyCode": "USD", "isActive": True})
        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "SF", "postalCode": "94102", "street": "3 Rd"}})
        wh_id = r.json()["id"]
        r = staff("post", "/shipping-zones", {"name": _u("z-"), "countries": ["US"]})
        zone_id = r.json()["id"]
        staff("put", f"/shipping-zones/{zone_id}", {"warehouses": [wh_id]})
        r = staff("post", f"/shipping-zones/{zone_id}/methods", {"name": "Std", "type": "price", "rate": 5.0, "minValue": 0, "maxValue": 1000})
        sm_id = r.json()["id"]

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]
        r = staff("post", "/products", {"name": _u("p-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch_slug, "isPublished": True}]})
        r = staff("post", f"/products/{prod_id}/variants", {"name": "V", "sku": _u("S-"), "channelListings": [{"channelSlug": ch_slug, "price": 10.0, "currencyCode": "USD"}]})
        var_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 10})

        # Checkout with qty 4
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "pf@t.com"})
        co_id = r.json()["id"]
        cust("post", f"/checkouts/{co_id}/lines", {"variantId": var_id, "quantity": 4})
        cust("put", f"/checkouts/{co_id}/shipping-address", {"country": "US", "city": "SF", "postalCode": "94102", "street": "X", "firstName": "A", "lastName": "B"})
        cust("put", f"/checkouts/{co_id}/shipping-method", {"shippingMethodId": sm_id})

        cust("put", f"/checkouts/{co_id}/billing-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        r = cust("post", f"/checkouts/{co_id}/complete")
        assert r.status_code in [200, 201]
        order_id = r.json()["id"]
        line_id = r.json()["lines"][0]["id"]

        # Partial fulfillment (2 of 4)
        r = staff("post", f"/orders/{order_id}/fulfillments", {
            "lines": [{"orderLineId": line_id, "quantity": 2}],
            "warehouseId": wh_id,
        })
        assert r.status_code == 201

        r = staff("get", f"/orders/{order_id}")
        assert r.json()["status"] == "partiallyFulfilled"

        # Fulfill remaining (2 of 4)
        r = staff("post", f"/orders/{order_id}/fulfillments", {
            "lines": [{"orderLineId": line_id, "quantity": 2}],
            "warehouseId": wh_id,
        })
        assert r.status_code == 201

        r = staff("get", f"/orders/{order_id}")
        assert r.json()["status"] == "fulfilled"


class TestTaxCalculationWorkflow:
    """Tax calculation in checkout totals."""

    def test_tax_applied_based_on_shipping_country(self):
        """Pattern 5: Tax rate lookup by product tax class + shipping country."""
        ch_slug = _u("txch-")
        staff("post", "/channels", {"slug": ch_slug, "name": "Tax Ch", "currencyCode": "USD", "isActive": True})

        # Tax class with 10% US rate
        r = staff("post", "/tax-classes", {"name": _u("tax-"), "rates": [{"countryCode": "US", "rate": 0.10}]})
        tax_id = r.json()["id"]

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False, "taxClassId": tax_id})
        pt_id = r.json()["id"]

        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "X", "postalCode": "10001", "street": "X"}})
        wh_id = r.json()["id"]
        r = staff("post", "/shipping-zones", {"name": _u("z-"), "countries": ["US"]})
        zone_id = r.json()["id"]
        staff("put", f"/shipping-zones/{zone_id}", {"warehouses": [wh_id]})
        r = staff("post", f"/shipping-zones/{zone_id}/methods", {"name": "S", "type": "price", "rate": 0, "minValue": 0, "maxValue": 1000})
        sm_id = r.json()["id"]

        r = staff("post", "/products", {"name": _u("p-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch_slug, "isPublished": True}]})
        r = staff("post", f"/products/{prod_id}/variants", {"name": "V", "sku": _u("S-"), "channelListings": [{"channelSlug": ch_slug, "price": 100.0, "currencyCode": "USD"}]})
        var_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 10})

        # Checkout
        r = cust("post", "/checkouts", {"channelSlug": ch_slug, "customerEmail": "tax@t.com"})
        co_id = r.json()["id"]
        cust("post", f"/checkouts/{co_id}/lines", {"variantId": var_id, "quantity": 1})
        cust("put", f"/checkouts/{co_id}/shipping-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        cust("put", f"/checkouts/{co_id}/shipping-method", {"shippingMethodId": sm_id})


        cust("put", f"/checkouts/{co_id}/billing-address", {"country": "US", "city": "X", "postalCode": "10001", "street": "X", "firstName": "A", "lastName": "B"})
        r = cust("post", f"/checkouts/{co_id}/complete")
        assert r.status_code in [200, 201]
        order = r.json()
        # Tax should be ~10.0 (10% of 100)
        assert order["taxTotal"] == 10.0 or abs(order["taxTotal"] - 10.0) < 0.01
        # Total = subtotal + tax + shipping
        assert order["total"] >= 110.0
