"""Comprehensive test suite for Medusa headless e-commerce API."""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin_testkey123"
CUSTOMER_KEY = "customer_testkey456"
CUSTOMER_KEY_2 = "customer_other789"


def url(path):
    return f"{BASE_URL}{path}"


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def customer_headers(key=CUSTOMER_KEY):
    return {"X-API-Key": key, "Content-Type": "application/json"}


def item_suffix(request):
    return request.node.name.removeprefix("test_").replace("_", "-")


# ============================================================
# Authentication Tests
# ============================================================
class TestAuth:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(url("/store/products"))
        assert resp.status_code == 401

    def test_admin_endpoint_with_customer_key_returns_403(self):
        resp = requests.post(
            url("/admin/products"),
            headers=customer_headers(),
            json={"title": "Test", "handle": "test"},
        )
        assert resp.status_code == 403

    def test_admin_endpoint_with_admin_key_succeeds(self):
        resp = requests.get(url("/admin/regions"), headers=admin_headers())
        assert resp.status_code == 200


# ============================================================
# Region Tests
# ============================================================
class TestRegions:
    def test_create_region(self):
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "US", "currency": "usd", "taxRate": 0.08},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "US"
        assert data["currency"] == "usd"
        assert data["taxRate"] == 0.08
        assert "id" in data

    def test_list_regions(self):
        resp = requests.get(url("/admin/regions"), headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "regions" in data

    def test_update_region(self):
        # Create
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "EU", "currency": "eur", "taxRate": 0.2},
        )
        region_id = resp.json()["id"]
        # Update
        resp = requests.put(
            url(f"/admin/regions/{region_id}"),
            headers=admin_headers(),
            json={"name": "Europe", "currency": "eur", "taxRate": 0.19},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Europe"
        assert resp.json()["taxRate"] == 0.19

    def test_delete_region(self):
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "Temp", "currency": "gbp", "taxRate": 0.15},
        )
        region_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/regions/{region_id}"), headers=admin_headers())
        assert resp.status_code == 204

    def test_store_list_regions(self):
        resp = requests.get(url("/store/regions"), headers=customer_headers())
        assert resp.status_code == 200
        assert "regions" in resp.json()


# ============================================================
# Shipping Method Tests
# ============================================================
class TestShippingMethods:
    @pytest.fixture(autouse=True)
    def setup_region(self):
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "ShipRegion", "currency": "usd", "taxRate": 0.1},
        )
        self.region_id = resp.json()["id"]

    def test_create_shipping_method(self):
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "Standard", "price": 500},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Standard"
        assert data["price"] == 500
        assert data["regionId"] == self.region_id

    def test_list_shipping_methods(self):
        requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "Express", "price": 1500},
        )
        resp = requests.get(url("/admin/shipping-methods"), headers=admin_headers())
        assert resp.status_code == 200
        assert "shippingMethods" in resp.json()

    def test_update_shipping_method(self):
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "Old", "price": 300},
        )
        sm_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/shipping-methods/{sm_id}"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "Updated", "price": 700},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["price"] == 700

    def test_delete_shipping_method(self):
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "ToDelete", "price": 100},
        )
        sm_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/shipping-methods/{sm_id}"), headers=admin_headers())
        assert resp.status_code == 204

    def test_store_region_shipping_methods(self):
        requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "StoreVisible", "price": 800},
        )
        resp = requests.get(
            url(f"/store/regions/{self.region_id}/shipping-methods"),
            headers=customer_headers(),
        )
        assert resp.status_code == 200
        assert "shippingMethods" in resp.json()


# ============================================================
# Category Tests
# ============================================================
class TestCategories:
    def test_create_category(self):
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Clothing", "handle": "clothing"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Clothing"
        assert data["handle"] == "clothing"

    def test_list_categories(self):
        resp = requests.get(url("/admin/categories"), headers=admin_headers())
        assert resp.status_code == 200
        assert "categories" in resp.json()

    def test_update_category(self):
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Shoes", "handle": "shoes"},
        )
        cat_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/categories/{cat_id}"),
            headers=admin_headers(),
            json={"name": "Footwear", "handle": "footwear"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Footwear"

    def test_delete_category(self):
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Temp", "handle": "temp-cat"},
        )
        cat_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/categories/{cat_id}"), headers=admin_headers())
        assert resp.status_code == 204


# ============================================================
# Collection Tests
# ============================================================
class TestCollections:
    def test_create_collection(self):
        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": "Summer Sale", "handle": "summer-sale"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Summer Sale"
        assert data["handle"] == "summer-sale"

    def test_list_collections(self):
        resp = requests.get(url("/admin/collections"), headers=admin_headers())
        assert resp.status_code == 200
        assert "collections" in resp.json()

    def test_update_collection(self):
        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": "Old", "handle": "old-col"},
        )
        col_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/collections/{col_id}"),
            headers=admin_headers(),
            json={"title": "New", "handle": "new-col"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_delete_collection(self):
        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": "Temp", "handle": "temp-col"},
        )
        col_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/collections/{col_id}"), headers=admin_headers())
        assert resp.status_code == 204


# ============================================================
# Product Tests
# ============================================================
class TestProducts:
    def test_create_product(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={
                "title": "T-Shirt",
                "description": "A nice t-shirt",
                "handle": "t-shirt",
                "status": "published",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "T-Shirt"
        assert data["status"] == "published"
        assert "id" in data

    def test_update_product(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "OldTitle", "handle": "old-product"},
        )
        prod_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/products/{prod_id}"),
            headers=admin_headers(),
            json={"title": "NewTitle", "status": "published"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "NewTitle"
        assert resp.json()["status"] == "published"

    def test_delete_product(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ToDelete", "handle": "to-delete"},
        )
        prod_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/products/{prod_id}"), headers=admin_headers())
        assert resp.status_code == 204

    def test_store_list_only_published_products(self):
        # Create draft
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Draft Product", "handle": "draft-prod", "status": "draft"},
        )
        # Create published
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Published Product", "handle": "pub-prod", "status": "published"},
        )
        resp = requests.get(url("/store/products"), headers=customer_headers())
        assert resp.status_code == 200
        products = resp.json()["products"]
        for p in products:
            assert p["status"] == "published"

    def test_store_get_product_with_details(self):
        # Create product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Detailed", "handle": "detailed-prod", "status": "published"},
        )
        prod_id = resp.json()["id"]
        # Add variant
        requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "Small", "sku": "DET-S", "price": 2000, "inventoryQuantity": 10},
        )
        # Add option
        requests.post(
            url(f"/admin/products/{prod_id}/options"),
            headers=admin_headers(),
            json={"title": "Size"},
        )
        # Add image
        requests.post(
            url(f"/admin/products/{prod_id}/images"),
            headers=admin_headers(),
            json={"url": "https://example.com/img.jpg", "sortOrder": 1},
        )
        # Get from store
        resp = requests.get(url(f"/store/products/{prod_id}"), headers=customer_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["variants"]) >= 1
        assert len(data["options"]) >= 1
        assert len(data["images"]) >= 1

    def test_store_filter_by_category(self):
        # Create category
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "FilterCat", "handle": "filter-cat"},
        )
        cat_id = resp.json()["id"]
        # Create product in category
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={
                "title": "CatProduct",
                "handle": "cat-product",
                "status": "published",
                "categoryId": cat_id,
            },
        )
        resp = requests.get(
            url(f"/store/products?categoryId={cat_id}"), headers=customer_headers()
        )
        assert resp.status_code == 200
        products = resp.json()["products"]
        assert len(products) >= 1
        for p in products:
            assert p["categoryId"] == cat_id


# ============================================================
# Product Variant Tests
# ============================================================
class TestProductVariants:
    @pytest.fixture(autouse=True)
    def setup_product(self, request):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "VarProduct", "handle": f"var-product-{item_suffix(request)}", "status": "published"},
        )
        self.product_id = resp.json()["id"]

    def test_create_variant(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/variants"),
            headers=admin_headers(),
            json={
                "title": "Large / Red",
                "sku": "VP-LR",
                "price": 3000,
                "inventoryQuantity": 50,
                "options": {"Size": "Large", "Color": "Red"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Large / Red"
        assert data["price"] == 3000
        assert data["inventoryQuantity"] == 50

    def test_update_variant(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/variants"),
            headers=admin_headers(),
            json={"title": "Old", "sku": "VP-OLD", "price": 1000, "inventoryQuantity": 5},
        )
        var_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/products/{self.product_id}/variants/{var_id}"),
            headers=admin_headers(),
            json={"title": "Updated", "sku": "VP-UPD", "price": 1500, "inventoryQuantity": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"
        assert resp.json()["price"] == 1500

    def test_delete_variant(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/variants"),
            headers=admin_headers(),
            json={"title": "ToDelete", "sku": "VP-DEL", "price": 500, "inventoryQuantity": 1},
        )
        var_id = resp.json()["id"]
        resp = requests.delete(
            url(f"/admin/products/{self.product_id}/variants/{var_id}"),
            headers=admin_headers(),
        )
        assert resp.status_code == 204


# ============================================================
# Product Options Tests
# ============================================================
class TestProductOptions:
    @pytest.fixture(autouse=True)
    def setup_product(self, request):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "OptProduct", "handle": f"opt-product-{item_suffix(request)}"},
        )
        self.product_id = resp.json()["id"]

    def test_create_option(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/options"),
            headers=admin_headers(),
            json={"title": "Color"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Color"

    def test_delete_option(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/options"),
            headers=admin_headers(),
            json={"title": "Material"},
        )
        opt_id = resp.json()["id"]
        resp = requests.delete(
            url(f"/admin/products/{self.product_id}/options/{opt_id}"),
            headers=admin_headers(),
        )
        assert resp.status_code == 204


# ============================================================
# Product Images Tests
# ============================================================
class TestProductImages:
    @pytest.fixture(autouse=True)
    def setup_product(self, request):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ImgProduct", "handle": f"img-product-{item_suffix(request)}"},
        )
        self.product_id = resp.json()["id"]

    def test_create_image(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/images"),
            headers=admin_headers(),
            json={"url": "https://example.com/photo.jpg", "sortOrder": 0},
        )
        assert resp.status_code == 201
        assert resp.json()["url"] == "https://example.com/photo.jpg"

    def test_delete_image(self):
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/images"),
            headers=admin_headers(),
            json={"url": "https://example.com/del.jpg", "sortOrder": 1},
        )
        img_id = resp.json()["id"]
        resp = requests.delete(
            url(f"/admin/products/{self.product_id}/images/{img_id}"),
            headers=admin_headers(),
        )
        assert resp.status_code == 204


# ============================================================
# Customer Tests
# ============================================================
class TestCustomers:
    def test_register_customer(self):
        key = f"cust_{os.urandom(4).hex()}"
        resp = requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "test@example.com", "firstName": "John", "lastName": "Doe"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["firstName"] == "John"

    def test_get_own_profile(self):
        key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "me@example.com", "firstName": "Jane", "lastName": "Doe"},
        )
        resp = requests.get(url("/store/customers/me"), headers=customer_headers(key))
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    def test_update_profile(self):
        key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "upd@example.com", "firstName": "Original", "lastName": "Name"},
        )
        resp = requests.put(
            url("/store/customers/me"),
            headers=customer_headers(key),
            json={"firstName": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["firstName"] == "Updated"

    def test_duplicate_registration_returns_409(self):
        key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "dup@example.com", "firstName": "A", "lastName": "B"},
        )
        resp = requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "dup2@example.com", "firstName": "C", "lastName": "D"},
        )
        assert resp.status_code == 409

    def test_get_profile_not_registered_returns_404(self):
        key = f"cust_{os.urandom(4).hex()}"
        resp = requests.get(url("/store/customers/me"), headers=customer_headers(key))
        assert resp.status_code == 404


# ============================================================
# Address Tests
# ============================================================
class TestAddresses:
    @pytest.fixture(autouse=True)
    def setup_customer(self, request):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{item_suffix(request)}@example.test", "firstName": "Addr", "lastName": "Test"},
        )

    def test_add_address(self):
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "John",
                "lastName": "Doe",
                "address1": "123 Main St",
                "city": "NYC",
                "province": "NY",
                "postalCode": "10001",
                "countryCode": "US",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["city"] == "NYC"

    def test_list_addresses(self):
        requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "A",
                "lastName": "B",
                "address1": "456 Oak",
                "city": "LA",
                "province": "CA",
                "postalCode": "90001",
                "countryCode": "US",
            },
        )
        resp = requests.get(
            url("/store/customers/me/addresses"), headers=customer_headers(self.key)
        )
        assert resp.status_code == 200
        assert "addresses" in resp.json()
        assert len(resp.json()["addresses"]) >= 1

    def test_update_address(self):
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "Old",
                "lastName": "Addr",
                "address1": "789 Elm",
                "city": "CHI",
                "province": "IL",
                "postalCode": "60601",
                "countryCode": "US",
            },
        )
        addr_id = resp.json()["id"]
        resp = requests.put(
            url(f"/store/customers/me/addresses/{addr_id}"),
            headers=customer_headers(self.key),
            json={
                "firstName": "New",
                "lastName": "Addr",
                "address1": "789 Elm Updated",
                "city": "Chicago",
                "province": "IL",
                "postalCode": "60601",
                "countryCode": "US",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["city"] == "Chicago"

    def test_delete_address(self):
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "Del",
                "lastName": "Me",
                "address1": "000 Del St",
                "city": "Del",
                "province": "DL",
                "postalCode": "00000",
                "countryCode": "US",
            },
        )
        addr_id = resp.json()["id"]
        resp = requests.delete(
            url(f"/store/customers/me/addresses/{addr_id}"),
            headers=customer_headers(self.key),
        )
        assert resp.status_code == 204


# ============================================================
# Cart Tests
# ============================================================
class TestCarts:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        # Register customer
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@example.com", "firstName": "Cart", "lastName": "User"},
        )
        # Create region
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "CartRegion", "currency": "usd", "taxRate": 0.1},
        )
        self.region_id = resp.json()["id"]
        # Create product with variant
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "CartItem", "handle": f"cart-item-{self.key}", "status": "published"},
        )
        self.product_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{self.product_id}/variants"),
            headers=admin_headers(),
            json={"title": "Default", "sku": f"CI-{self.key}", "price": 2500, "inventoryQuantity": 20},
        )
        self.variant_id = resp.json()["id"]

    def test_create_cart(self):
        resp = requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["regionId"] == self.region_id
        assert data["items"] == []

    def test_duplicate_cart_returns_409(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        assert resp.status_code == 409

    def test_add_item_to_cart(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 2},
        )
        assert resp.status_code == 201
        cart = resp.json()
        assert len(cart["items"]) == 1
        assert cart["items"][0]["quantity"] == 2
        assert cart["items"][0]["unitPrice"] == 2500

    def test_update_item_quantity(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 1},
        )
        item_id = resp.json()["items"][0]["id"]
        resp = requests.put(
            url(f"/store/carts/mine/items/{item_id}"),
            headers=customer_headers(self.key),
            json={"quantity": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["items"][0]["quantity"] == 5

    def test_remove_item_from_cart(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 1},
        )
        item_id = resp.json()["items"][0]["id"]
        resp = requests.delete(
            url(f"/store/carts/mine/items/{item_id}"),
            headers=customer_headers(self.key),
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_cart_totals_calculation(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 2},
        )
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(self.key))
        assert resp.status_code == 200
        cart = resp.json()
        # subtotal = 2500 * 2 = 5000
        assert cart["subtotal"] == 5000
        # tax = 5000 * 0.1 = 500
        assert cart["tax"] == 500
        # total = 5000 + 500 = 5500 (no discount, no shipping)
        assert cart["total"] == 5500

    def test_insufficient_inventory_returns_409(self):
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 999},
        )
        assert resp.status_code == 409

    def test_no_active_cart_returns_404(self):
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(self.key))
        assert resp.status_code == 404


# ============================================================
# Discount Tests
# ============================================================
class TestDiscounts:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@disc.com", "firstName": "Disc", "lastName": "User"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "DiscRegion", "currency": "usd", "taxRate": 0.1},
        )
        self.region_id = resp.json()["id"]

    def test_create_discount(self):
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": "SAVE10", "type": "percentage", "value": 10},
        )
        assert resp.status_code == 201
        assert resp.json()["code"] == "SAVE10"
        assert resp.json()["type"] == "percentage"
        assert resp.json()["value"] == 10

    def test_create_fixed_discount(self):
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": "FLAT500", "type": "fixed", "value": 500},
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "fixed"
        assert resp.json()["value"] == 500

    def test_duplicate_code_returns_409(self):
        code = f"DUP{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 5},
        )
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 10},
        )
        assert resp.status_code == 409

    def test_list_discounts(self):
        resp = requests.get(url("/admin/discounts"), headers=admin_headers())
        assert resp.status_code == 200
        assert "discounts" in resp.json()

    def test_update_discount(self):
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": f"UPD{os.urandom(3).hex()}", "type": "percentage", "value": 15},
        )
        disc_id = resp.json()["id"]
        resp = requests.put(
            url(f"/admin/discounts/{disc_id}"),
            headers=admin_headers(),
            json={"code": f"UPD{os.urandom(3).hex()}", "type": "percentage", "value": 20},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == 20

    def test_delete_discount(self):
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": f"DEL{os.urandom(3).hex()}", "type": "fixed", "value": 100},
        )
        disc_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/discounts/{disc_id}"), headers=admin_headers())
        assert resp.status_code == 204

    def test_apply_percentage_discount_to_cart(self):
        # Create discount
        code = f"PCT{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 20},
        )
        # Create product and variant
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "DiscProd", "handle": f"disc-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"DP-{self.key}", "price": 10000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        # Create cart, add item
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        # Apply discount
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        # subtotal = 10000, discount = 20% of 10000 = 2000
        assert cart["subtotal"] == 10000
        assert cart["discount"] == 2000
        # tax = (10000 - 2000) * 0.1 = 800
        assert cart["tax"] == 800
        # total = 10000 - 2000 + 800 = 8800
        assert cart["total"] == 8800

    def test_apply_fixed_discount_to_cart(self):
        code = f"FIX{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "fixed", "value": 1500},
        )
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "FixProd", "handle": f"fix-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"FP-{self.key}", "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        # subtotal = 5000, discount = 1500 (fixed)
        assert cart["subtotal"] == 5000
        assert cart["discount"] == 1500
        # tax = (5000 - 1500) * 0.1 = 350
        assert cart["tax"] == 350
        # total = 5000 - 1500 + 350 = 3850
        assert cart["total"] == 3850

    def test_expired_discount_returns_422(self):
        code = f"EXP{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={
                "code": code,
                "type": "percentage",
                "value": 10,
                "startsAt": "2020-01-01T00:00:00Z",
                "endsAt": "2020-12-31T23:59:59Z",
            },
        )
        # Create cart
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ExpProd", "handle": f"exp-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"EP-{self.key}", "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code},
        )
        assert resp.status_code == 422

    def test_usage_limit_exceeded_returns_422(self):
        code = f"LIM{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 5, "usageLimit": 0},
        )
        # Create product/variant/cart
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "LimProd", "handle": f"lim-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"LP-{self.key}", "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code},
        )
        assert resp.status_code == 422

    def test_remove_discount_from_cart(self):
        code = f"REM{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 10},
        )
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "RemProd", "handle": f"rem-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"RP-{self.key}", "price": 3000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code},
        )
        resp = requests.delete(
            url("/store/carts/mine/discount"), headers=customer_headers(self.key)
        )
        assert resp.status_code == 200
        assert resp.json()["discount"] == 0
        assert resp.json()["discountCode"] is None

    def test_discount_code_case_insensitive(self):
        code = f"CASE{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code.upper(), "type": "percentage", "value": 10},
        )
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "CaseProd", "handle": f"case-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"CP-{self.key}", "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        # Apply with lowercase
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(self.key),
            json={"code": code.lower()},
        )
        assert resp.status_code == 200
        assert resp.json()["discount"] > 0


# ============================================================
# Cart Shipping Tests
# ============================================================
class TestCartShipping:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@ship.com", "firstName": "Ship", "lastName": "User"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "ShipTestRegion", "currency": "usd", "taxRate": 0.05},
        )
        self.region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "Standard Ship", "price": 1000},
        )
        self.shipping_id = resp.json()["id"]
        # Product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ShipProd", "handle": f"ship-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"SP-{self.key}", "price": 4000, "inventoryQuantity": 10},
        )
        self.variant_id = resp.json()["id"]
        # Cart
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 1},
        )

    def test_set_shipping_method(self):
        resp = requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(self.key),
            json={"shippingMethodId": self.shipping_id},
        )
        assert resp.status_code == 200
        cart = resp.json()
        assert cart["shipping"] == 1000
        # subtotal=4000, tax=(4000)*0.05=200, shipping=1000, total=5200
        assert cart["subtotal"] == 4000
        assert cart["tax"] == 200
        assert cart["total"] == 5200

    def test_shipping_method_wrong_region_returns_422(self):
        # Create another region and shipping method
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "OtherRegion", "currency": "eur", "taxRate": 0.2},
        )
        other_region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": other_region_id, "name": "OtherShip", "price": 2000},
        )
        other_ship_id = resp.json()["id"]
        # Try to set it on cart in different region
        resp = requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(self.key),
            json={"shippingMethodId": other_ship_id},
        )
        assert resp.status_code == 422


# ============================================================
# Order & Payment Integration Tests
# ============================================================
class TestOrdersAndPayments:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@order.com", "firstName": "Order", "lastName": "User"},
        )
        # Region
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "OrderRegion", "currency": "usd", "taxRate": 0.1},
        )
        self.region_id = resp.json()["id"]
        # Shipping method
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": self.region_id, "name": "OrderShip", "price": 500},
        )
        self.shipping_id = resp.json()["id"]
        # Product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "OrderProd", "handle": f"order-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"OP-{self.key}", "price": 3000, "inventoryQuantity": 10},
        )
        self.variant_id = resp.json()["id"]
        # Address
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "Order",
                "lastName": "Addr",
                "address1": "100 Order St",
                "city": "Austin",
                "province": "TX",
                "postalCode": "73301",
                "countryCode": "US",
            },
        )
        self.address_id = resp.json()["id"]
        # Cart
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 2},
        )
        requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(self.key),
            json={"shippingMethodId": self.shipping_id},
        )

    def test_create_order_success(self):
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["status"] == "pending"
        assert order["customerId"] == self.key
        # subtotal = 3000*2 = 6000
        assert order["subtotal"] == 6000
        # tax = 6000 * 0.1 = 600
        assert order["tax"] == 600
        # shipping = 500
        assert order["shipping"] == 500
        # total = 6000 + 600 + 500 = 7100
        assert order["total"] == 7100
        assert order["paymentId"] is not None

    def test_order_decrements_inventory(self):
        requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        # Verify by trying to add more than the remaining inventory.
        # First we need a new cart
        key2 = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key2),
            json={"email": f"{key2}@inv.com", "firstName": "Inv", "lastName": "Check"},
        )
        requests.post(
            url("/store/carts"),
            headers=customer_headers(key2),
            json={"regionId": self.region_id},
        )
        # Try to add more than remaining inventory (was 10, used 2, so 8 remaining)
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": self.variant_id, "quantity": 9},
        )
        assert resp.status_code == 409

    def test_order_clears_cart(self):
        requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        # Cart should no longer be active
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(self.key))
        assert resp.status_code == 404

    def test_list_own_orders(self):
        requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        resp = requests.get(url("/store/orders"), headers=customer_headers(self.key))
        assert resp.status_code == 200
        assert len(resp.json()["orders"]) >= 1

    def test_get_order_details(self):
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        order_id = resp.json()["id"]
        resp = requests.get(url(f"/store/orders/{order_id}"), headers=customer_headers(self.key))
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id

    def test_cancel_own_order(self):
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        order_id = resp.json()["id"]
        resp = requests.post(
            url(f"/store/orders/{order_id}/cancel"), headers=customer_headers(self.key)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cannot_cancel_non_pending_order(self):
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        order_id = resp.json()["id"]
        # Admin confirms
        requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        # Customer tries to cancel
        resp = requests.post(
            url(f"/store/orders/{order_id}/cancel"), headers=customer_headers(self.key)
        )
        assert resp.status_code == 422

    def test_empty_cart_cannot_checkout(self):
        # Create new customer with empty cart
        key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@empty.com", "firstName": "E", "lastName": "C"},
        )
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(key),
            json={
                "firstName": "A",
                "lastName": "B",
                "address1": "1 St",
                "city": "C",
                "province": "P",
                "postalCode": "00000",
                "countryCode": "US",
            },
        )
        addr_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(key),
            json={"regionId": self.region_id},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 409


# ============================================================
# Order Status Workflow Tests
# ============================================================
class TestOrderStatusWorkflow:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@wf.com", "firstName": "WF", "lastName": "User"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "WFRegion", "currency": "usd", "taxRate": 0.05},
        )
        self.region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "WFProd", "handle": f"wf-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"WF-{self.key}", "price": 2000, "inventoryQuantity": 50},
        )
        self.variant_id = resp.json()["id"]
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "A",
                "lastName": "B",
                "address1": "1 St",
                "city": "C",
                "province": "P",
                "postalCode": "00000",
                "countryCode": "US",
            },
        )
        self.address_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": self.variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        self.order_id = resp.json()["id"]

    def test_pending_to_confirmed(self):
        resp = requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    def test_confirmed_to_shipped(self):
        requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        resp = requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    def test_shipped_to_delivered(self):
        requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        resp = requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    def test_invalid_transition_returns_422(self):
        # pending -> shipped (skip confirmed) should fail
        resp = requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        assert resp.status_code == 422

    def test_pending_to_cancelled(self):
        resp = requests.put(
            url(f"/admin/orders/{self.order_id}/status"),
            headers=admin_headers(),
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_admin_list_orders(self):
        resp = requests.get(url("/admin/orders"), headers=admin_headers())
        assert resp.status_code == 200
        assert "orders" in resp.json()
        assert resp.json()["count"] >= 1


# ============================================================
# Payment Integration Tests
# ============================================================
class TestPaymentIntegration:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.key = f"cust_{os.urandom(4).hex()}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(self.key),
            json={"email": f"{self.key}@pay.com", "firstName": "Pay", "lastName": "User"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "PayRegion", "currency": "usd", "taxRate": 0.0},
        )
        self.region_id = resp.json()["id"]
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(self.key),
            json={
                "firstName": "P",
                "lastName": "U",
                "address1": "1 Pay St",
                "city": "PayCity",
                "province": "PC",
                "postalCode": "11111",
                "countryCode": "US",
            },
        )
        self.address_id = resp.json()["id"]

    def test_successful_payment(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "PayProd", "handle": f"pay-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"PP-{self.key}", "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["paymentId"] is not None
        assert order["status"] == "pending"

    def test_failed_payment_large_amount(self):
        """Payment should fail if charge amount > 999999."""
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ExpProd", "handle": f"exp-pay-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        # Price is 500000 per unit, quantity 3 = 1500000 > 999999
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"EXP-{self.key}", "price": 500000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 3},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        # Payment fails -> order not created
        assert resp.status_code == 422

    def test_refund_order(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "RefProd", "handle": f"ref-prod-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"REF-{self.key}", "price": 2000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        order_id = resp.json()["id"]
        # Refund
        resp = requests.post(
            url(f"/admin/orders/{order_id}/refund"),
            headers=admin_headers(),
            json={"reason": "customer_request"},
        )
        assert resp.status_code == 200
        payment = resp.json()
        assert payment["status"] == "refunded"
        assert payment["refundId"] is not None

    def test_partial_refund(self):
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "PartRef", "handle": f"part-ref-{self.key}", "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": f"PR-{self.key}", "price": 4000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        requests.post(
            url("/store/carts"),
            headers=customer_headers(self.key),
            json={"regionId": self.region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(self.key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(self.key),
            json={"shippingAddressId": self.address_id},
        )
        order_id = resp.json()["id"]
        # Partial refund
        resp = requests.post(
            url(f"/admin/orders/{order_id}/refund"),
            headers=admin_headers(),
            json={"amount": 1000, "reason": "partial"},
        )
        assert resp.status_code == 200
        assert resp.json()["refundId"] is not None


# ============================================================
# Full Order Lifecycle Test
# ============================================================
class TestFullLifecycle:
    def test_complete_order_lifecycle(self):
        """Test full flow: register → browse → cart → discount → shipping → order → status workflow."""
        key = f"cust_{os.urandom(4).hex()}"

        # 1. Setup - Admin creates region, product, discount, shipping
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": "Lifecycle Region", "currency": "usd", "taxRate": 0.1},
        )
        region_id = resp.json()["id"]

        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": "Standard", "price": 800},
        )
        shipping_id = resp.json()["id"]

        disc_code = f"LIFE{os.urandom(3).hex()}"
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": disc_code, "type": "percentage", "value": 10, "usageLimit": 5},
        )

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={
                "title": "Lifecycle Product",
                "handle": f"lifecycle-{key}",
                "status": "published",
            },
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "Default", "sku": f"LC-{key}", "price": 5000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        # 2. Customer registers
        resp = requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@life.com", "firstName": "Life", "lastName": "Cycle"},
        )
        assert resp.status_code == 201

        # 3. Customer adds address
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(key),
            json={
                "firstName": "Life",
                "lastName": "Cycle",
                "address1": "999 Life Way",
                "city": "Seattle",
                "province": "WA",
                "postalCode": "98101",
                "countryCode": "US",
            },
        )
        address_id = resp.json()["id"]

        # 4. Customer browses products
        resp = requests.get(url("/store/products"), headers=customer_headers(key))
        assert resp.status_code == 200

        # 5. Customer creates cart and adds items
        resp = requests.post(
            url("/store/carts"),
            headers=customer_headers(key),
            json={"regionId": region_id},
        )
        assert resp.status_code == 201

        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 3},
        )
        assert resp.status_code == 201

        # 6. Apply discount
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": disc_code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        # subtotal = 5000*3 = 15000
        assert cart["subtotal"] == 15000
        # discount = 10% of 15000 = 1500
        assert cart["discount"] == 1500

        # 7. Set shipping
        resp = requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(key),
            json={"shippingMethodId": shipping_id},
        )
        assert resp.status_code == 200
        cart = resp.json()
        assert cart["shipping"] == 800
        # tax = (15000 - 1500) * 0.1 = 1350
        assert cart["tax"] == 1350
        # total = 15000 - 1500 + 1350 + 800 = 15650
        assert cart["total"] == 15650

        # 8. Create order
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": address_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        order_id = order["id"]
        assert order["status"] == "pending"
        assert order["total"] == 15650

        # 9. Admin confirms order
        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        # 10. Admin ships order
        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

        # 11. Admin delivers order
        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"
