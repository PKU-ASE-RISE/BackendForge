"""
BackendForge — L2 Integration Tests for Saleor Commerce
Adversarial tests targeting common LLM implementation bugs.

"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
PAYMENT_URL = os.environ.get("PAYMENT_URL", "").strip().rstrip("/") or "http://localhost:9999"

STAFF_KEY = "staff_integ_key"
CUST_KEY = f"cust_{uuid.uuid4().hex}"


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex}"


def staff(method, path, json=None, params=None):
    h = {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}
    return getattr(requests, method)(f"{BASE_URL}{path}", json=json, params=params, headers=h, timeout=30)


def cust(method, path, json=None, params=None):
    h = {"X-API-Key": CUST_KEY, "Content-Type": "application/json"}
    return getattr(requests, method)(f"{BASE_URL}{path}", json=json, params=params, headers=h, timeout=30)


# ═══════════════════════════════════════════════════════════
# L2 Tests — Integration (20-30 tests)
# ═══════════════════════════════════════════════════════════


class TestChannelFields:
    """Pattern 1+4: Channel response fields and status codes."""

    def test_channel_create_returns_correct_fields(self):
        slug = _u("ch-")
        r = staff("post", "/channels", {"slug": slug, "name": "Test Channel", "currencyCode": "USD", "isActive": True})
        assert r.status_code == 201
        d = r.json()
        assert d["slug"] == slug
        assert d["name"] == "Test Channel"
        assert d["currencyCode"] == "USD"
        assert d["isActive"] is True
        assert "currency_code" not in d
        assert "is_active" not in d

    def test_channel_get_by_slug(self):
        slug = _u("chg-")
        staff("post", "/channels", {"slug": slug, "name": "GetCh", "currencyCode": "EUR", "isActive": True})
        r = staff("get", f"/channels/{slug}")
        assert r.status_code == 200
        assert r.json()["slug"] == slug
        assert r.json()["currencyCode"] == "EUR"


class TestWarehouseFields:
    """Pattern 1: Warehouse response fields."""

    def test_warehouse_create_and_get(self):
        slug = _u("wh-")
        r = staff("post", "/warehouses", {
            "name": "Main Warehouse",
            "slug": slug,
            "address": {"country": "US", "city": "NYC", "postalCode": "10001", "street": "123 Main St"},
        })
        assert r.status_code == 201
        d = r.json()
        assert d["name"] == "Main Warehouse"
        assert d["slug"] == slug
        assert d["address"]["country"] == "US"
        assert d["address"]["city"] == "NYC"
        assert "id" in d
        wh_id = d["id"]

        r = staff("get", f"/warehouses/{wh_id}")
        assert r.status_code == 200
        assert r.json()["slug"] == slug


class TestProductTypeFields:
    """Pattern 1+2: Product type with nested attributes."""

    def test_product_type_with_attributes(self):
        r = staff("post", "/product-types", {
            "name": _u("pt-"),
            "slug": _u("pts-"),
            "productAttributes": [
                {"name": "Material", "type": "text"},
                {"name": "Weight", "type": "numeric"},
            ],
            "variantAttributes": [
                {"name": "Size", "type": "select", "choices": ["S", "M", "L"]},
            ],
            "isDigital": False,
        })
        assert r.status_code == 201
        d = r.json()
        assert len(d["productAttributes"]) == 2
        assert d["productAttributes"][0]["name"] == "Material"
        assert d["variantAttributes"][0]["name"] == "Size"
        assert "S" in d["variantAttributes"][0]["choices"]
        assert d["isDigital"] is False


class TestCategoryHierarchy:
    """Pattern 2: Category parent-child hierarchy."""

    def test_category_with_parent(self):
        r = staff("post", "/categories", {"name": _u("root-"), "slug": _u("root-")})
        assert r.status_code == 201
        root_id = r.json()["id"]

        r = staff("post", "/categories", {"name": _u("child-"), "slug": _u("child-"), "parentId": root_id})
        assert r.status_code == 201
        assert r.json()["parentId"] == root_id

    def test_category_list_by_parent(self):
        r = staff("post", "/categories", {"name": _u("p-"), "slug": _u("p-")})
        parent_id = r.json()["id"]
        staff("post", "/categories", {"name": _u("c1-"), "slug": _u("c1-"), "parentId": parent_id})
        staff("post", "/categories", {"name": _u("c2-"), "slug": _u("c2-"), "parentId": parent_id})

        r = staff("get", "/categories", params={"parent": parent_id})
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 2


class TestProductChannelListing:
    """Pattern 3+6: Channel scoping actually filters products."""

    def test_product_only_visible_in_listed_channel(self):
        # Create 2 channels
        ch1 = _u("chp1-")
        ch2 = _u("chp2-")
        staff("post", "/channels", {"slug": ch1, "name": "Ch1", "currencyCode": "USD", "isActive": True})
        staff("post", "/channels", {"slug": ch2, "name": "Ch2", "currencyCode": "EUR", "isActive": True})

        # Create product type and product
        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]

        r = staff("post", "/products", {"name": _u("prod-"), "slug": _u("prods-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]

        # List in ch1 only
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch1, "isPublished": True}]})

        # Product visible in ch1
        r = staff("get", "/products", params={"channel": ch1})
        prod_ids = [p["id"] for p in r.json()["data"]]
        assert prod_id in prod_ids

        # Product NOT visible in ch2
        r = staff("get", "/products", params={"channel": ch2})
        prod_ids = [p["id"] for p in r.json()["data"]]
        assert prod_id not in prod_ids


class TestVariantStocks:
    """Pattern 2+5: Variant stocks and channel listings nested data."""

    def test_variant_with_stocks_and_prices(self):
        ch = _u("chv-")
        staff("post", "/channels", {"slug": ch, "name": "VCh", "currencyCode": "USD", "isActive": True})

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]

        r = staff("post", "/products", {"name": _u("prod-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        staff("post", f"/products/{prod_id}/channel-listings", {"channelListings": [{"channelSlug": ch, "isPublished": True}]})

        # Create variant
        r = staff("post", f"/products/{prod_id}/variants", {
            "name": "Default",
            "sku": _u("SKU-"),
            "channelListings": [{"channelSlug": ch, "price": 29.99, "costPrice": 15.0, "currencyCode": "USD"}],
        })
        assert r.status_code == 201
        variant = r.json()
        assert variant["name"] == "Default"
        assert "id" in variant
        assert len(variant["channelListings"]) == 1
        assert variant["channelListings"][0]["price"] == 29.99
        assert variant["channelListings"][0]["channelSlug"] == ch

    def test_variant_stock_creation(self):
        ch = _u("chs-")
        staff("post", "/channels", {"slug": ch, "name": "SCh", "currencyCode": "USD", "isActive": True})
        r = staff("post", "/warehouses", {"name": _u("wh-"), "slug": _u("whs-"), "address": {"country": "US", "city": "NYC", "postalCode": "10001", "street": "1 St"}})
        wh_id = r.json()["id"]
        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]
        r = staff("post", "/products", {"name": _u("p-"), "slug": _u("ps-"), "productTypeId": pt_id})
        prod_id = r.json()["id"]
        r = staff("post", f"/products/{prod_id}/variants", {"name": "V1", "sku": _u("S-"), "channelListings": [{"channelSlug": ch, "price": 10, "currencyCode": "USD"}]})
        var_id = r.json()["id"]

        r = staff("post", f"/products/{prod_id}/variants/{var_id}/stocks", {"warehouseId": wh_id, "quantity": 50})
        assert r.status_code in [200, 201]
        stock = r.json()
        assert stock["quantity"] == 50
        assert stock["warehouseId"] == wh_id


class TestShippingZone:
    """Pattern 2: Shipping zone with nested methods."""

    def test_shipping_zone_with_methods(self):
        r = staff("post", "/shipping-zones", {"name": _u("zone-"), "countries": ["US", "CA"]})
        assert r.status_code == 201
        zone_id = r.json()["id"]
        assert "US" in r.json()["countries"]

        r = staff("post", f"/shipping-zones/{zone_id}/methods", {
            "name": "Standard",
            "type": "price",
            "rate": 5.99,
            "minOrderValue": 0,
            "maxOrderValue": 100,
        })
        assert r.status_code == 201
        method = r.json()
        assert method["name"] == "Standard"
        assert method["rate"] == 5.99
        assert "id" in method


class TestVoucherFields:
    """Pattern 1+5: Voucher fields and constraints."""

    def test_voucher_create_with_constraints(self):
        code = _u("DISC-")
        r = staff("post", "/vouchers", {
            "code": code,
            "type": "percentage",
            "value": 10,
            "minOrderValue": 50,
            "usageLimit": 100,
        })
        assert r.status_code == 201
        d = r.json()
        assert d["code"] == code
        assert d["type"] == "percentage"
        assert d["value"] == 10
        assert d["minOrderValue"] == 50
        assert d["usageLimit"] == 100
        assert d["usedCount"] == 0
        assert "id" in d


class TestCustomerFields:
    """Pattern 1: Customer response fields."""

    def test_customer_create_and_get(self):
        r = staff("post", "/customers", {"email": f"{_u()}@test.com", "firstName": "Alice", "lastName": "Smith"})
        assert r.status_code == 201
        d = r.json()
        assert d["firstName"] == "Alice"
        assert d["lastName"] == "Smith"
        assert "id" in d
        assert "first_name" not in d
        assert "last_name" not in d

        cid = d["id"]
        r = staff("get", f"/customers/{cid}")
        assert r.status_code == 200
        assert r.json()["firstName"] == "Alice"


class TestTaxClasses:
    """Pattern 1+2: Tax class with nested rates."""

    def test_tax_class_with_rates(self):
        r = staff("post", "/tax-classes", {
            "name": _u("tax-"),
            "rates": [
                {"countryCode": "US", "rate": 0.08},
                {"countryCode": "DE", "rate": 0.19},
            ],
        })
        assert r.status_code == 201
        d = r.json()
        assert len(d["rates"]) == 2
        rates_by_country = {rate["countryCode"]: rate["rate"] for rate in d["rates"]}
        assert rates_by_country["US"] == 0.08
        assert rates_by_country["DE"] == 0.19


class TestListPagination:
    """Pattern 3: List endpoints return totalCount."""

    def test_channels_list_has_total_count(self):
        staff("post", "/channels", {"slug": _u("pch-"), "name": "P", "currencyCode": "USD", "isActive": True})
        r = staff("get", "/channels")
        assert r.status_code == 200
        assert "totalCount" in r.json()
        assert "data" in r.json()
        assert r.json()["totalCount"] >= 1

    def test_products_list_has_total_count(self):
        ch = _u("plch-")
        staff("post", "/channels", {"slug": ch, "name": "PL", "currencyCode": "USD", "isActive": True})
        r = staff("get", "/products", params={"channel": ch})
        assert r.status_code == 200
        assert "totalCount" in r.json()
        assert "data" in r.json()


class TestStatusCodes:
    """Pattern 4: Exact status codes."""

    def test_create_201_get_200_notfound_404(self):
        r = staff("post", "/channels", {"slug": _u("sc-"), "name": "SC", "currencyCode": "USD", "isActive": True})
        assert r.status_code == 201

        r = staff("get", f"/channels/{r.json()['slug']}")
        assert r.status_code == 200

        r = staff("get", f"/channels/{_u('nonexistent-slug-')}")
        assert r.status_code == 404

    def test_customer_cannot_create_channel(self):
        r = cust("post", "/channels", {"slug": _u("hack-"), "name": "H", "currencyCode": "USD"})
        assert r.status_code in [401, 403]

    def test_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/channels", timeout=30)
        assert r.status_code == 401


class TestCollectionProducts:
    """Pattern 5+7: Collection product management."""

    def test_add_and_list_products_in_collection(self):
        ch = _u("colch-")
        staff("post", "/channels", {"slug": ch, "name": "CC", "currencyCode": "USD", "isActive": True})

        r = staff("post", "/product-types", {"name": _u("pt-"), "slug": _u("pts-"), "productAttributes": [], "variantAttributes": [], "isDigital": False})
        pt_id = r.json()["id"]

        r = staff("post", "/products", {"name": _u("p1-"), "slug": _u("ps1-"), "productTypeId": pt_id})
        p1_id = r.json()["id"]
        staff("post", f"/products/{p1_id}/channel-listings", {"channelListings": [{"channelSlug": ch, "isPublished": True}]})

        r = staff("post", "/collections", {"name": _u("col-"), "slug": _u("cols-")})
        assert r.status_code == 201
        col_id = r.json()["id"]

        r = staff("post", f"/collections/{col_id}/products", {"productIds": [p1_id]})
        assert r.status_code in [200, 201]
