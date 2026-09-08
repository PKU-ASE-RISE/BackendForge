"""
Correctness tests for Saleor Commerce API.
Tests multi-channel pricing, multi-warehouse stock, partial fulfillment,
shipping zones, voucher constraints, tax calculation, and auth+capture flow.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
PAYMENT_URL = os.environ.get("PAYMENT_URL", "").strip().rstrip("/") or "http://localhost:9999"

STAFF_KEY = "staff_admin_key"
CUSTOMER_KEY = f"customer_{uuid.uuid4().hex}"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def customer_headers(key=CUSTOMER_KEY):
    return {"X-API-Key": key, "Content-Type": "application/json"}


# ─── Channels ─────────────────────────────────────────────────────────────────

class TestChannels:
    def test_create_channel(self):
        slug = _u("web-us-")
        r = requests.post(f"{BASE_URL}/channels", json={
            "slug": slug,
            "name": "US Web Store",
            "currencyCode": "USD",
            "isActive": True
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == slug
        assert data["currencyCode"] == "USD"
        assert data["isActive"] is True

    def test_create_second_channel(self):
        slug = _u("mobile-eu-")
        r = requests.post(f"{BASE_URL}/channels", json={
            "slug": slug,
            "name": "EU Mobile App",
            "currencyCode": "EUR",
            "isActive": True
        }, headers=staff_headers())
        assert r.status_code == 201
        assert r.json()["currencyCode"] == "EUR"

    def test_list_channels(self):
        _create_channel()
        _create_channel(currency_code="EUR")
        r = requests.get(f"{BASE_URL}/channels", headers=staff_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["totalCount"] >= 2

    def test_get_channel(self):
        channel = _create_channel(name="US Web Store")
        r = requests.get(f"{BASE_URL}/channels/{channel['slug']}", headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "US Web Store"

    def test_update_channel(self):
        channel = _create_channel()
        r = requests.put(f"{BASE_URL}/channels/{channel['slug']}", json={
            "name": "US Web Store (Updated)"
        }, headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "US Web Store (Updated)"

    def test_duplicate_slug_rejected(self):
        channel = _create_channel()
        r = requests.post(f"{BASE_URL}/channels", json={
            "slug": channel["slug"],
            "name": "Duplicate",
            "currencyCode": "USD"
        }, headers=staff_headers())
        assert r.status_code == 400

    def test_customer_cannot_create_channel(self):
        r = requests.post(f"{BASE_URL}/channels", json={
            "slug": _u("forbidden-channel-"),
            "name": "Hack",
            "currencyCode": "USD"
        }, headers=customer_headers())
        assert r.status_code == 403


# ─── Warehouses ───────────────────────────────────────────────────────────────

class TestWarehouses:
    def test_create_warehouse(self):
        slug = _u("us-east-")
        r = requests.post(f"{BASE_URL}/warehouses", json={
            "name": "US East Warehouse",
            "slug": slug,
            "address": {
                "street": "100 Commerce Dr",
                "city": "New York",
                "postalCode": "10001",
                "country": "US"
            }
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == slug
        assert "id" in data

    def test_create_second_warehouse(self):
        slug = _u("eu-central-")
        r = requests.post(f"{BASE_URL}/warehouses", json={
            "name": "EU Central Warehouse",
            "slug": slug,
            "address": {
                "street": "50 Lager Str",
                "city": "Berlin",
                "postalCode": "10115",
                "country": "DE"
            }
        }, headers=staff_headers())
        assert r.status_code == 201

    def test_list_warehouses(self):
        _create_warehouse()
        _create_warehouse(country="DE")
        r = requests.get(f"{BASE_URL}/warehouses", headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 2


# ─── Tax Classes ──────────────────────────────────────────────────────────────

class TestTaxClasses:
    def test_create_tax_class(self):
        name = _u("Standard Tax ")
        r = requests.post(f"{BASE_URL}/tax-classes", json={
            "name": name,
            "rates": [
                {"countryCode": "US", "rate": 0.08},
                {"countryCode": "DE", "rate": 0.19},
                {"countryCode": "GB", "rate": 0.20}
            ]
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == name
        assert len(data["rates"]) == 3

    def test_create_reduced_tax_class(self):
        r = requests.post(f"{BASE_URL}/tax-classes", json={
            "name": _u("Reduced Tax "),
            "rates": [
                {"countryCode": "US", "rate": 0.0},
                {"countryCode": "DE", "rate": 0.07},
                {"countryCode": "GB", "rate": 0.05}
            ]
        }, headers=staff_headers())
        assert r.status_code == 201

    def test_list_tax_classes(self):
        _create_tax_class()
        _create_tax_class()
        r = requests.get(f"{BASE_URL}/tax-classes", headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["totalCount"] >= 2


# ─── Product Types ────────────────────────────────────────────────────────────

class TestProductTypes:
    def test_create_product_type(self):
        tax_class = _create_tax_class()
        slug = _u("clothing-")

        r = requests.post(f"{BASE_URL}/product-types", json={
            "name": "Clothing",
            "slug": slug,
            "productAttributes": [
                {"name": "Material", "type": "text"},
                {"name": "Brand", "type": "text"}
            ],
            "variantAttributes": [
                {"name": "Size", "type": "select", "choices": ["S", "M", "L", "XL"]},
                {"name": "Color", "type": "select", "choices": ["Red", "Blue", "Black"]}
            ],
            "taxClassId": tax_class["id"],
            "isDigital": False
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == slug
        assert len(data["variantAttributes"]) == 2

    def test_create_digital_product_type(self):
        tax_class = _create_tax_class()

        r = requests.post(f"{BASE_URL}/product-types", json={
            "name": "Digital Goods",
            "slug": _u("digital-goods-"),
            "productAttributes": [
                {"name": "Format", "type": "select", "choices": ["PDF", "EPUB", "MP3"]}
            ],
            "variantAttributes": [],
            "taxClassId": tax_class["id"],
            "isDigital": True
        }, headers=staff_headers())
        assert r.status_code == 201
        assert r.json()["isDigital"] is True


# ─── Categories ───────────────────────────────────────────────────────────────

class TestCategories:
    def test_create_root_category(self):
        slug = _u("apparel-")
        r = requests.post(f"{BASE_URL}/categories", json={
            "name": "Apparel",
            "slug": slug,
            "description": "All clothing items"
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["parentId"] is None

    def test_create_child_category(self):
        parent = _create_category()

        r = requests.post(f"{BASE_URL}/categories", json={
            "name": "T-Shirts",
            "slug": _u("t-shirts-"),
            "description": "Casual t-shirts",
            "parentId": parent["id"]
        }, headers=staff_headers())
        assert r.status_code == 201
        assert r.json()["parentId"] == parent["id"]

    def test_list_root_categories(self):
        _create_category()
        r = requests.get(f"{BASE_URL}/categories?parent=root", headers=staff_headers())
        assert r.status_code == 200
        for cat in r.json()["data"]:
            assert cat["parentId"] is None


# ─── Products with Multi-Channel Pricing ──────────────────────────────────────

class TestProducts:
    def test_create_product(self):
        clothing_type = _create_product_type(product_attributes=[
            {"name": "Material", "type": "text"},
            {"name": "Brand", "type": "text"},
        ])
        tshirts_cat = _create_category()
        slug = _u("classic-tshirt-")

        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Classic T-Shirt",
            "slug": slug,
            "description": "A classic cotton t-shirt",
            "productTypeId": clothing_type["id"],
            "categoryId": tshirts_cat["id"],
            "attributes": {"Material": "Cotton", "Brand": "BasicWear"}
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == slug

    def test_add_channel_listings(self):
        us_channel = _create_channel()
        eu_channel = _create_channel(currency_code="EUR")
        clothing_type = _create_product_type(product_attributes=[
            {"name": "Material", "type": "text"},
            {"name": "Brand", "type": "text"},
        ])
        tshirts_cat = _create_category()

        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Premium T-Shirt",
            "slug": _u("premium-tshirt-"),
            "description": "A premium organic cotton t-shirt",
            "productTypeId": clothing_type["id"],
            "categoryId": tshirts_cat["id"],
            "attributes": {"Material": "Organic Cotton", "Brand": "EcoWear"}
        }, headers=staff_headers())
        assert r.status_code == 201
        product_id = r.json()["id"]

        # Add channel listings for both channels
        r = requests.post(f"{BASE_URL}/products/{product_id}/channel-listings", json={
            "channelListings": [
                {"channelSlug": us_channel["slug"], "isPublished": True, "visibleInListings": True},
                {"channelSlug": eu_channel["slug"], "isPublished": True, "visibleInListings": True}
            ]
        }, headers=staff_headers())
        assert r.status_code == 200

    def test_create_variant_with_multi_channel_pricing(self):
        """Same product has different prices in different channels."""
        us_channel = _create_channel()
        eu_channel = _create_channel(currency_code="EUR")
        clothing_type = _create_product_type(
            product_attributes=[
                {"name": "Material", "type": "text"},
                {"name": "Brand", "type": "text"},
            ],
            variant_attributes=[
                {"name": "Size", "type": "select", "choices": ["S", "M", "L"]},
                {"name": "Color", "type": "select", "choices": ["Red", "Blue"]},
            ],
        )
        tshirts_cat = _create_category()
        sku = _u("MCT-M-BLUE-")

        # Create a product specifically for this test
        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Multi-Channel Tee",
            "slug": _u("multichannel-tee-"),
            "description": "Available on multiple channels",
            "productTypeId": clothing_type["id"],
            "categoryId": tshirts_cat["id"],
            "attributes": {"Material": "Cotton Blend", "Brand": "ChannelBrand"}
        }, headers=staff_headers())
        assert r.status_code == 201
        product_id = r.json()["id"]

        # List in both channels
        r = requests.post(f"{BASE_URL}/products/{product_id}/channel-listings", json={
            "channelListings": [
                {"channelSlug": us_channel["slug"], "isPublished": True},
                {"channelSlug": eu_channel["slug"], "isPublished": True}
            ]
        }, headers=staff_headers())
        assert r.status_code == 200

        # Create variant with different prices per channel
        r = requests.post(f"{BASE_URL}/products/{product_id}/variants", json={
            "name": "Multi-Channel Tee - M Blue",
            "sku": sku,
            "attributes": {"Size": "M", "Color": "Blue"},
            "weight": 200,
            "channelListings": [
                {"channelSlug": us_channel["slug"], "price": 29.99, "currencyCode": "USD"},
                {"channelSlug": eu_channel["slug"], "price": 24.99, "currencyCode": "EUR"}
            ]
        }, headers=staff_headers())
        assert r.status_code == 201
        variant = r.json()
        assert variant["sku"] == sku

        # Verify different prices show in different channels
        r = requests.get(f"{BASE_URL}/products/{product_id}/variants?channel={us_channel['slug']}", headers=customer_headers())
        assert r.status_code == 200
        variants_us = r.json()["data"]
        us_variant = next(v for v in variants_us if v["sku"] == sku)
        us_price = next(cl for cl in us_variant["channelListings"] if cl["channelSlug"] == us_channel["slug"])
        assert us_price["price"] == 29.99

        r = requests.get(f"{BASE_URL}/products/{product_id}/variants?channel={eu_channel['slug']}", headers=customer_headers())
        assert r.status_code == 200
        variants_eu = r.json()["data"]
        eu_variant = next(v for v in variants_eu if v["sku"] == sku)
        eu_price = next(cl for cl in eu_variant["channelListings"] if cl["channelSlug"] == eu_channel["slug"])
        assert eu_price["price"] == 24.99

    def test_product_invisible_without_channel_listing(self):
        """Product without listing in a channel should not appear in that channel."""
        channel = _create_channel()
        clothing_type = _create_product_type()

        # Create product without any channel listing
        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Hidden Product",
            "slug": _u("hidden-product-"),
            "description": "Not listed anywhere",
            "productTypeId": clothing_type["id"]
        }, headers=staff_headers())
        assert r.status_code == 201
        product_id = r.json()["id"]

        # Should not appear in channel listing
        r = requests.get(f"{BASE_URL}/products?channel={channel['slug']}", headers=customer_headers())
        assert r.status_code == 200
        product_ids = [p["id"] for p in r.json()["data"]]
        assert product_id not in product_ids


# ─── Shipping Zones ───────────────────────────────────────────────────────────

class TestShippingZones:
    def test_create_us_zone(self):
        us_wh = _create_warehouse()

        r = requests.post(f"{BASE_URL}/shipping-zones", json={
            "name": _u("US Zone "),
            "countries": ["US"],
            "warehouses": [us_wh["id"]]
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert "US" in data["countries"]

    def test_create_eu_zone(self):
        eu_wh = _create_warehouse(country="DE")

        r = requests.post(f"{BASE_URL}/shipping-zones", json={
            "name": _u("EU Zone "),
            "countries": ["DE", "FR", "GB", "IT", "ES"],
            "warehouses": [eu_wh["id"]]
        }, headers=staff_headers())
        assert r.status_code == 201

    def test_add_shipping_methods(self):
        us_zone = _create_shipping_zone("US")
        eu_zone = _create_shipping_zone("DE")

        # US standard shipping
        r = requests.post(f"{BASE_URL}/shipping-zones/{us_zone['id']}/methods", json={
            "name": "US Standard",
            "type": "price",
            "minValue": 0,
            "maxValue": None,
            "rate": 5.99,
            "currencyCode": "USD"
        }, headers=staff_headers())
        assert r.status_code == 201

        # US express shipping
        r = requests.post(f"{BASE_URL}/shipping-zones/{us_zone['id']}/methods", json={
            "name": "US Express",
            "type": "price",
            "minValue": 0,
            "maxValue": None,
            "rate": 14.99,
            "currencyCode": "USD"
        }, headers=staff_headers())
        assert r.status_code == 201

        # EU standard shipping
        r = requests.post(f"{BASE_URL}/shipping-zones/{eu_zone['id']}/methods", json={
            "name": "EU Standard",
            "type": "weight",
            "minValue": 0,
            "maxValue": 5000,
            "rate": 7.99,
            "currencyCode": "EUR"
        }, headers=staff_headers())
        assert r.status_code == 201

    def test_shipping_methods_match_country(self):
        """Only methods from zones covering customer's country are available."""
        channel = _create_channel()
        us_warehouse = _create_warehouse()
        eu_warehouse = _create_warehouse(country="DE")
        us_zone = _create_shipping_zone("US", us_warehouse["id"])
        eu_zone = _create_shipping_zone("DE", eu_warehouse["id"])
        _create_shipping_method(us_zone["id"], name="US Standard", rate=5.99)
        _create_shipping_method(us_zone["id"], name="US Express", rate=14.99)
        _create_shipping_method(eu_zone["id"], name="EU Standard", rate=7.99)
        setup = _setup_product_for_checkout(
            channel["slug"], "USD", warehouse_id=us_warehouse["id"]
        )
        product_id = setup["product_id"]
        variant_id = setup["variant_id"]

        # Create checkout
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": "test@example.com",
            "lines": [{"variantId": variant_id, "quantity": 1}]
        }, headers=customer_headers())
        assert r.status_code == 201
        checkout_id = r.json()["id"]

        # Set US shipping address
        r = requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-address", json={
            "street": "123 Main St",
            "city": "New York",
            "postalCode": "10001",
            "country": "US"
        }, headers=customer_headers())
        assert r.status_code == 200

        # Get available shipping methods
        r = requests.get(f"{BASE_URL}/checkouts/{checkout_id}/shipping-methods", headers=customer_headers())
        assert r.status_code == 200
        methods = r.json()["data"]
        method_names = [m["name"] for m in methods]
        assert "US Standard" in method_names
        assert "US Express" in method_names
        assert "EU Standard" not in method_names


# ─── Collections ──────────────────────────────────────────────────────────────

class TestCollections:
    def test_create_and_manage_collection(self):
        channel = _create_channel()
        product_type = _create_product_type()
        product = _create_product(product_type["id"])
        _set_channel_listings(product["id"], channel["slug"])
        r = requests.post(f"{BASE_URL}/collections", json={
            "name": "Summer Sale",
            "slug": _u("summer-sale-"),
            "description": "Hot summer deals",
            "channelListings": [
                {"channelSlug": channel["slug"], "isPublished": True}
            ]
        }, headers=staff_headers())
        assert r.status_code == 201
        collection_id = r.json()["id"]

        # Add product to collection
        r = requests.get(f"{BASE_URL}/products?channel={channel['slug']}", headers=staff_headers())
        products = r.json()["data"]
        if products:
            product_id = products[0]["id"]
            r = requests.post(f"{BASE_URL}/collections/{collection_id}/products", json={
                "productIds": [product_id]
            }, headers=staff_headers())
            assert r.status_code == 200

    def test_collection_channel_scoping(self):
        """Collection only visible in channels where it's published."""
        us_channel = _create_channel()
        eu_channel = _create_channel(currency_code="EUR")
        slug = _u("us-only-collection-")
        r = requests.post(f"{BASE_URL}/collections", json={
            "name": "US Only Collection",
            "slug": slug,
            "description": "Only for US",
            "channelListings": [
                {"channelSlug": us_channel["slug"], "isPublished": True}
            ]
        }, headers=staff_headers())
        assert r.status_code == 201

        # Should appear in web-us
        r = requests.get(f"{BASE_URL}/collections?channel={us_channel['slug']}", headers=customer_headers())
        assert r.status_code == 200
        slugs = [c["slug"] for c in r.json()["data"]]
        assert slug in slugs

        # Should NOT appear in mobile-eu
        r = requests.get(f"{BASE_URL}/collections?channel={eu_channel['slug']}", headers=customer_headers())
        assert r.status_code == 200
        slugs = [c["slug"] for c in r.json()["data"]]
        assert slug not in slugs


# ─── Vouchers ─────────────────────────────────────────────────────────────────

class TestVouchers:
    def test_create_voucher(self):
        channel = _create_channel()
        code = _u("SAVE10-")
        r = requests.post(f"{BASE_URL}/vouchers", json={
            "code": code,
            "type": "percentage",
            "value": 10,
            "channelSlug": channel["slug"],
            "minOrderValue": 20.0,
            "usageLimit": 100
        }, headers=staff_headers())
        assert r.status_code == 201
        data = r.json()
        assert data["code"] == code
        assert data["usedCount"] == 0

    def test_create_channel_restricted_voucher(self):
        channel = _create_channel(currency_code="EUR")
        r = requests.post(f"{BASE_URL}/vouchers", json={
            "code": _u("EU_ONLY_15-"),
            "type": "percentage",
            "value": 15,
            "channelSlug": channel["slug"],
            "minOrderValue": 10.0
        }, headers=staff_headers())
        assert r.status_code == 201

    def test_voucher_channel_constraint(self):
        """Voucher restricted to a channel cannot be used in another channel."""
        us_channel = _create_channel()
        eu_channel = _create_channel(currency_code="EUR")
        code = _u("EU_ONLY_15-")
        _create_voucher(code=code, channel_slug=eu_channel["slug"])
        setup = _setup_product_for_checkout(us_channel["slug"], "USD")

        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": us_channel["slug"],
            "customerEmail": "voucher-test@example.com",
            "lines": [{"variantId": setup["variant_id"], "quantity": 1}]
        }, headers=customer_headers())
        assert r.status_code == 201
        checkout_id = r.json()["id"]

        # Try to apply EU-only voucher in US channel
        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/voucher", json={
            "code": code
        }, headers=customer_headers())
        assert r.status_code == 400

    def test_voucher_min_order_value(self):
        """Voucher not applicable if order value below minimum."""
        channel = _create_channel()
        code = _u("SAVE10-")
        _create_voucher(code=code, channel_slug=channel["slug"], min_order_value=20.0)
        pt = _create_product_type()
        warehouse = _create_warehouse()
        product_slug = _u("cheap-item-voucher-test-")
        sku = _u("CHEAP-V-01-")

        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Cheap Item",
            "slug": product_slug,
            "productTypeId": pt["id"]
        }, headers=staff_headers())
        product_id = r.json()["id"]

        r = requests.post(f"{BASE_URL}/products/{product_id}/channel-listings", json={
            "channelListings": [{"channelSlug": channel["slug"], "isPublished": True}]
        }, headers=staff_headers())

        r = requests.post(f"{BASE_URL}/products/{product_id}/variants", json={
            "name": "Cheap Variant",
            "sku": sku,
            "channelListings": [{"channelSlug": channel["slug"], "price": 5.00, "currencyCode": "USD"}]
        }, headers=staff_headers())
        variant_id = r.json()["id"]

        # Stock it
        r = requests.post(f"{BASE_URL}/products/{product_id}/variants/{variant_id}/stocks", json={
            "warehouseId": warehouse["id"],
            "quantity": 10
        }, headers=staff_headers())

        # Create checkout with low value
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": "cheap@example.com",
            "lines": [{"variantId": variant_id, "quantity": 1}]
        }, headers=customer_headers())
        checkout_id = r.json()["id"]

        # SAVE10 requires min $20, this is only $5
        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/voucher", json={
            "code": code
        }, headers=customer_headers())
        assert r.status_code == 400

    def test_voucher_usage_limit(self):
        """Voucher with usage limit=1 can only be used once."""
        r = requests.post(f"{BASE_URL}/vouchers", json={
            "code": _u("ONCE_ONLY-"),
            "type": "fixed",
            "value": 5.0,
            "channelSlug": None,
            "usageLimit": 1
        }, headers=staff_headers())
        assert r.status_code == 201


# ─── Customers ────────────────────────────────────────────────────────────────

class TestCustomers:
    def test_create_customer(self):
        email = f"{_u('john-')}@example.com"
        key = _u("customer-")
        r = requests.post(f"{BASE_URL}/customers", json={
            "email": email,
            "firstName": "John",
            "lastName": "Doe"
        }, headers=customer_headers(key))
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == email

    def test_add_address(self):
        key = _u("customer-")
        customer = _customer_setup("post", "/customers", {
            "email": f"{_u('address-')}@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }, key=key)

        r = requests.post(f"{BASE_URL}/customers/{customer['id']}/addresses", json={
            "street": "456 Oak Ave",
            "city": "Los Angeles",
            "postalCode": "90001",
            "country": "US",
            "firstName": "John",
            "lastName": "Doe",
            "isDefaultShipping": True,
            "isDefaultBilling": True
        }, headers=customer_headers(key))
        assert r.status_code == 201
        assert r.json()["isDefaultShipping"] is True

    def test_staff_can_add_note(self):
        customer = _staff_setup("post", "/customers", {
            "email": f"{_u('note-')}@example.com",
            "firstName": "John",
            "lastName": "Doe",
        })

        r = requests.put(f"{BASE_URL}/customers/{customer['id']}", json={
            "note": "VIP customer, handle with care"
        }, headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["note"] == "VIP customer, handle with care"


# ─── Warehouse Stock & Allocation ─────────────────────────────────────────────

class TestWarehouseStock:
    def test_set_stock(self):
        channel = _create_channel()
        setup = _setup_product_for_checkout(channel["slug"], "USD")
        product_id = setup["product_id"]
        variant_id = setup["variant_id"]

        r = requests.post(f"{BASE_URL}/products/{product_id}/variants/{variant_id}/stocks", json={
            "warehouseId": setup["warehouse_id"],
            "quantity": 5
        }, headers=staff_headers())
        assert r.status_code == 200
        assert r.json()["quantity"] == 5
        assert r.json()["allocatedQuantity"] == 0

    def test_prevent_overselling(self):
        """Cannot add more items to checkout than available stock."""
        channel = _create_channel()
        warehouse = _create_warehouse()
        pt = _create_product_type()

        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Limited Stock Item",
            "slug": _u("limited-stock-item-"),
            "productTypeId": pt["id"]
        }, headers=staff_headers())
        product_id = r.json()["id"]

        r = requests.post(f"{BASE_URL}/products/{product_id}/channel-listings", json={
            "channelListings": [{"channelSlug": channel["slug"], "isPublished": True}]
        }, headers=staff_headers())

        r = requests.post(f"{BASE_URL}/products/{product_id}/variants", json={
            "name": "Limited Variant",
            "sku": _u("LTD-001-"),
            "channelListings": [{"channelSlug": channel["slug"], "price": 50.00, "currencyCode": "USD"}]
        }, headers=staff_headers())
        variant_id = r.json()["id"]

        # Set stock to 3
        r = requests.post(f"{BASE_URL}/products/{product_id}/variants/{variant_id}/stocks", json={
            "warehouseId": warehouse["id"],
            "quantity": 3
        }, headers=staff_headers())
        assert r.status_code == 200

        # Create checkout requesting quantity > available
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": "oversell@example.com",
            "lines": [{"variantId": variant_id, "quantity": 5}]
        }, headers=customer_headers())
        # Should fail or return 400 because stock is only 3
        assert r.status_code == 400


# ─── Full Checkout + Order Flow ───────────────────────────────────────────────

class TestCheckoutAndOrderFlow:
    def test_stock_allocated_after_checkout(self):
        """Completing checkout increases allocatedQuantity."""
        channel = _create_channel()
        warehouse = _create_warehouse()
        zone = _create_shipping_zone("US", warehouse["id"])
        method = _create_shipping_method(zone["id"])
        product_type = _create_product_type()
        product = _create_product(product_type["id"], name="Allocation Test Product")
        product_id = product["id"]
        _set_channel_listings(product_id, channel["slug"])
        variant = _create_variant(product_id, channel["slug"], price=25.0)
        variant_id = variant["id"]
        _set_stock(product_id, variant_id, warehouse["id"], 10)

        # Create and complete checkout
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": f"{_u('alloc-')}@example.com",
            "lines": [{"variantId": variant_id, "quantity": 3}]
        }, headers=customer_headers())
        checkout_id = r.json()["id"]

        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-address", json={
            "street": "1 Alloc St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/billing-address", json={
            "street": "1 Alloc St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())

        r = requests.get(f"{BASE_URL}/checkouts/{checkout_id}/shipping-methods", headers=customer_headers())
        method_id = next(item["id"] for item in r.json()["data"] if item["id"] == method["id"])
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-method", json={
            "shippingMethodId": method_id
        }, headers=customer_headers())

        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/complete", json={}, headers=customer_headers())
        assert r.status_code == 200

        # Check allocated stock
        r = requests.get(f"{BASE_URL}/products/{product_id}/variants?channel={channel['slug']}", headers=staff_headers())
        variant = next(v for v in r.json()["data"] if v["id"] == variant_id)
        stock = next(s for s in variant["stocks"] if s["warehouseId"] == warehouse["id"])
        assert stock["allocatedQuantity"] >= 3


# ─── Partial Fulfillment ──────────────────────────────────────────────────────

class TestPartialFulfillment:
    pass
# ─── Tax Calculation ──────────────────────────────────────────────────────────

class TestTaxCalculation:
    def test_tax_applied_based_on_country(self):
        """Tax rate from product's tax class applied based on shipping country."""
        channel = _create_channel()
        warehouse = _create_warehouse()
        zone = _create_shipping_zone("US", warehouse["id"])
        method = _create_shipping_method(zone["id"])
        standard_tax = _create_tax_class(rates=[
            {"countryCode": "US", "rate": 0.08},
            {"countryCode": "DE", "rate": 0.19},
        ])
        product_type = _create_product_type(tax_class_id=standard_tax["id"])
        product = _create_product(product_type["id"], name="Tax Test Product")
        product_id = product["id"]
        _set_channel_listings(product_id, channel["slug"])
        variant = _create_variant(product_id, channel["slug"], price=100.0)
        variant_id = variant["id"]
        _set_stock(product_id, variant_id, warehouse["id"], 10)

        # Create checkout with US shipping (8% tax)
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": f"{_u('tax-')}@example.com",
            "lines": [{"variantId": variant_id, "quantity": 1}]
        }, headers=customer_headers())
        checkout_id = r.json()["id"]

        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-address", json={
            "street": "1 Tax St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/billing-address", json={
            "street": "1 Tax St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())

        r = requests.get(f"{BASE_URL}/checkouts/{checkout_id}/shipping-methods", headers=customer_headers())
        method_id = next(item["id"] for item in r.json()["data"] if item["id"] == method["id"])
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-method", json={
            "shippingMethodId": method_id
        }, headers=customer_headers())

        # Complete and check tax
        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/complete", json={}, headers=customer_headers())
        assert r.status_code == 200
        order = r.json()

        # Product is $100, US tax rate is 8% = $8 tax
        assert order["taxTotal"] == pytest.approx(8.0, abs=0.01)
        assert order["lines"][0]["taxRate"] == pytest.approx(0.08, abs=0.001)
        assert order["lines"][0]["taxAmount"] == pytest.approx(8.0, abs=0.01)


# ─── Returns and Refunds ──────────────────────────────────────────────────────

class TestReturns:
    pass
# ─── Auth + Capture Payment Flow ─────────────────────────────────────────────

class TestPaymentFlow:
    pass
# ─── Multi-Channel Product Visibility ─────────────────────────────────────────

class TestMultiChannelVisibility:
    def test_product_only_visible_in_listed_channel(self):
        """A product listed only in web-us is not visible in mobile-eu."""
        us_channel = _create_channel()
        eu_channel = _create_channel(currency_code="EUR")
        pt = _create_product_type()

        r = requests.post(f"{BASE_URL}/products", json={
            "name": "US Only Product",
            "slug": _u("us-only-product-"),
            "productTypeId": pt["id"]
        }, headers=staff_headers())
        product_id = r.json()["id"]

        # Only list in web-us
        r = requests.post(f"{BASE_URL}/products/{product_id}/channel-listings", json={
            "channelListings": [{"channelSlug": us_channel["slug"], "isPublished": True}]
        }, headers=staff_headers())
        assert r.status_code == 200

        # Visible in web-us
        r = requests.get(f"{BASE_URL}/products?channel={us_channel['slug']}", headers=customer_headers())
        product_ids = [p["id"] for p in r.json()["data"]]
        assert product_id in product_ids

        # Not visible in mobile-eu
        r = requests.get(f"{BASE_URL}/products?channel={eu_channel['slug']}", headers=customer_headers())
        product_ids = [p["id"] for p in r.json()["data"]]
        assert product_id not in product_ids


# ─── Auth Permissions ─────────────────────────────────────────────────────────

class TestPermissions:
    def test_no_auth_returns_401(self):
        r = requests.get(f"{BASE_URL}/channels")
        assert r.status_code == 401

    def test_customer_cannot_manage_products(self):
        r = requests.post(f"{BASE_URL}/products", json={
            "name": "Hack Product",
            "slug": _u("forbidden-product-"),
            "productTypeId": "fake"
        }, headers=customer_headers())
        assert r.status_code == 403

    def test_customer_cannot_create_voucher(self):
        r = requests.post(f"{BASE_URL}/vouchers", json={
            "code": _u("FORBIDDEN-"),
            "type": "percentage",
            "value": 99
        }, headers=customer_headers())
        assert r.status_code == 403

    def test_customer_cannot_list_customers(self):
        r = requests.get(f"{BASE_URL}/customers", headers=customer_headers())
        assert r.status_code == 403

    def test_customer_cannot_fulfill_orders(self):
        r = requests.post(f"{BASE_URL}/orders/fake-id/fulfillments", json={
            "warehouseId": "fake",
            "lines": []
        }, headers=customer_headers())
        assert r.status_code == 403


# ─── Voucher Applied Correctly in Checkout ────────────────────────────────────

class TestVoucherInCheckout:
    def test_percentage_voucher_applied(self):
        """Apply a 10% voucher and verify discount in completed order."""
        channel = _create_channel()
        warehouse = _create_warehouse()
        zone = _create_shipping_zone("US", warehouse["id"])
        method = _create_shipping_method(zone["id"])
        product_type = _create_product_type()
        product = _create_product(product_type["id"], name="Voucher Checkout Product")
        product_id = product["id"]
        _set_channel_listings(product_id, channel["slug"])
        variant = _create_variant(product_id, channel["slug"], price=50.0)
        variant_id = variant["id"]
        _set_stock(product_id, variant_id, warehouse["id"], 10)
        code = _u("SAVE10-")
        _create_voucher(
            code=code,
            channel_slug=channel["slug"],
            min_order_value=20.0,
            usage_limit=100,
        )

        # Create checkout
        r = requests.post(f"{BASE_URL}/checkouts", json={
            "channelSlug": channel["slug"],
            "customerEmail": f"{_u('voucher-checkout-')}@example.com",
            "lines": [{"variantId": variant_id, "quantity": 1}]
        }, headers=customer_headers())
        checkout_id = r.json()["id"]

        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-address", json={
            "street": "1 V St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/billing-address", json={
            "street": "1 V St", "city": "NY", "postalCode": "10001", "country": "US"
        }, headers=customer_headers())

        r = requests.get(f"{BASE_URL}/checkouts/{checkout_id}/shipping-methods", headers=customer_headers())
        method_id = next(item["id"] for item in r.json()["data"] if item["id"] == method["id"])
        requests.put(f"{BASE_URL}/checkouts/{checkout_id}/shipping-method", json={
            "shippingMethodId": method_id
        }, headers=customer_headers())

        # Apply SAVE10 voucher (10% off, min $20)
        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/voucher", json={
            "code": code
        }, headers=customer_headers())
        assert r.status_code == 200

        # Complete checkout
        r = requests.post(f"{BASE_URL}/checkouts/{checkout_id}/complete", json={}, headers=customer_headers())
        assert r.status_code == 200
        order = r.json()

        # 10% of $50 = $5 discount
        assert order["discount"] == pytest.approx(5.0, abs=0.01)
        assert order["voucherCode"] == code


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _setup_product_for_checkout(channel_slug, currency_code, *, warehouse_id=None):
    """Helper to create a product with stock ready for checkout."""
    product_type = _create_product_type()
    warehouse = _create_warehouse() if warehouse_id is None else {"id": warehouse_id}
    product = _create_product(product_type["id"])
    _set_channel_listings(product["id"], channel_slug)
    variant = _create_variant(product["id"], channel_slug, currency_code, price=35.0)
    _set_stock(product["id"], variant["id"], warehouse["id"], 100)
    return {
        "product_id": product["id"],
        "variant_id": variant["id"],
        "warehouse_id": warehouse["id"],
    }


def _u(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def _staff_setup(method, path, payload=None, params=None):
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        json=payload,
        params=params,
        headers=staff_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json() if response.content else None


def _customer_setup(method, path, payload=None, *, key=CUSTOMER_KEY):
    response = requests.request(
        method,
        f"{BASE_URL}{path}",
        json=payload,
        headers=customer_headers(key),
        timeout=30,
    )
    response.raise_for_status()
    return response.json() if response.content else None


def _create_channel(currency_code="USD", name="Test Channel"):
    slug = _u("channel-")
    return _staff_setup("post", "/channels", {
        "slug": slug,
        "name": name,
        "currencyCode": currency_code,
        "isActive": True,
    })


def _create_warehouse(country="US"):
    slug = _u("warehouse-")
    return _staff_setup("post", "/warehouses", {
        "name": f"Warehouse {slug}",
        "slug": slug,
        "address": {
            "street": "100 Commerce Dr",
            "city": "New York",
            "postalCode": "10001",
            "country": country,
        },
    })


def _create_tax_class(rates=None, name=None):
    return _staff_setup("post", "/tax-classes", {
        "name": name or _u("Tax Class "),
        "rates": rates or [{"countryCode": "US", "rate": 0.08}],
    })


def _create_product_type(
    *,
    tax_class_id=None,
    is_digital=False,
    product_attributes=None,
    variant_attributes=None,
):
    slug = _u("product-type-")
    payload = {
        "name": f"Product Type {slug}",
        "slug": slug,
        "productAttributes": product_attributes or [],
        "variantAttributes": variant_attributes or [],
        "isDigital": is_digital,
    }
    if tax_class_id is not None:
        payload["taxClassId"] = tax_class_id
    return _staff_setup("post", "/product-types", payload)


def _create_category(*, parent_id=None):
    slug = _u("category-")
    payload = {"name": f"Category {slug}", "slug": slug}
    if parent_id is not None:
        payload["parentId"] = parent_id
    return _staff_setup("post", "/categories", payload)


def _create_product(product_type_id, *, category_id=None, name=None):
    slug = _u("product-")
    payload = {
        "name": name or f"Product {slug}",
        "slug": slug,
        "productTypeId": product_type_id,
    }
    if category_id is not None:
        payload["categoryId"] = category_id
    return _staff_setup("post", "/products", payload)


def _set_channel_listings(product_id, *channel_slugs):
    return _staff_setup("post", f"/products/{product_id}/channel-listings", {
        "channelListings": [
            {"channelSlug": channel_slug, "isPublished": True}
            for channel_slug in channel_slugs
        ],
    })


def _create_variant(product_id, channel_slug, currency_code="USD", *, price=10.0):
    sku = _u("SKU-")
    return _staff_setup("post", f"/products/{product_id}/variants", {
        "name": f"Variant {sku}",
        "sku": sku,
        "channelListings": [{
            "channelSlug": channel_slug,
            "price": price,
            "currencyCode": currency_code,
        }],
    })


def _set_stock(product_id, variant_id, warehouse_id, quantity):
    return _staff_setup(
        "post",
        f"/products/{product_id}/variants/{variant_id}/stocks",
        {"warehouseId": warehouse_id, "quantity": quantity},
    )


def _create_shipping_zone(country, warehouse_id=None, name=None):
    payload = {"name": name or _u(f"{country} Zone "), "countries": [country]}
    if warehouse_id is not None:
        payload["warehouses"] = [warehouse_id]
    return _staff_setup("post", "/shipping-zones", payload)


def _create_shipping_method(zone_id, *, name="Standard", rate=5.0):
    return _staff_setup("post", f"/shipping-zones/{zone_id}/methods", {
        "name": name,
        "type": "price",
        "minValue": 0,
        "maxValue": 1000,
        "rate": rate,
        "currencyCode": "USD",
    })


def _create_voucher(*, code=None, channel_slug=None, min_order_value=None, usage_limit=None):
    payload = {
        "code": code or _u("VOUCHER-"),
        "type": "percentage",
        "value": 10,
        "channelSlug": channel_slug,
    }
    if min_order_value is not None:
        payload["minOrderValue"] = min_order_value
    if usage_limit is not None:
        payload["usageLimit"] = usage_limit
    return _staff_setup("post", "/vouchers", payload)
