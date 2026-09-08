"""L2 Integration Tests for Medusa Headless E-Commerce API.

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase field name verification
- Pattern 2: Nested/related data completeness
- Pattern 3: Filtering/pagination actually implemented
- Pattern 4: Correct HTTP status codes
- Pattern 5: Business logic calculations (not echoed/hardcoded)
"""
import os
import requests
import uuid

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin_l2test"
CUSTOMER_KEY = f"cust_l2_{uuid.uuid4().hex[:8]}"


def url(path):
    return f"{BASE_URL}{path}"


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def customer_headers(key=None):
    return {"X-API-Key": key or CUSTOMER_KEY, "Content-Type": "application/json"}


def unique(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


# ============================================================
# Test 1: Product creation returns correct camelCase fields
# ============================================================
class TestProductFieldNames:
    def test_product_create_returns_camel_case_fields_and_201(self):
        """Pattern 1+4: Verify camelCase field names and 201 status on product creation."""
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={
                "title": "Field Test Shirt",
                "description": "Testing fields",
                "handle": unique("field-test-"),
                "status": "published",
            },
        )
        assert resp.status_code == 201, f"Expected 201 got {resp.status_code}"
        data = resp.json()
        # Verify all required camelCase keys exist
        assert "id" in data
        assert "title" in data
        assert "handle" in data
        assert "status" in data
        assert "createdAt" in data, "Missing camelCase field 'createdAt'"
        assert "updatedAt" in data, "Missing camelCase field 'updatedAt'"
        assert "categoryId" in data or data.get("categoryId") is None
        assert "collectionId" in data or data.get("collectionId") is None
        # Verify snake_case NOT present
        assert "created_at" not in data, "Should use camelCase 'createdAt' not snake_case"
        assert "updated_at" not in data, "Should use camelCase 'updatedAt' not snake_case"
        assert "category_id" not in data, "Should use camelCase 'categoryId'"
        assert "collection_id" not in data, "Should use camelCase 'collectionId'"
        # Verify values
        assert data["title"] == "Field Test Shirt"
        assert data["status"] == "published"
        # Verify timestamps are ISO 8601
        assert "T" in data["createdAt"]

    def test_product_variant_camel_case_fields(self):
        """Pattern 1: Verify variant returns camelCase fields."""
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Variant Fields", "handle": unique("vf-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={
                "title": "Medium Blue",
                "sku": unique("SKU-"),
                "price": 4500,
                "inventoryQuantity": 25,
                "options": {"Size": "Medium", "Color": "Blue"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "productId" in data, "Missing 'productId' (camelCase)"
        assert "product_id" not in data, "Should NOT use snake_case 'product_id'"
        assert "inventoryQuantity" in data, "Missing 'inventoryQuantity' (camelCase)"
        assert "inventory_quantity" not in data, "Should NOT use snake_case"
        assert "unitPrice" not in data  # unitPrice is cart item field, not variant
        assert data["productId"] == prod_id
        assert data["price"] == 4500
        assert data["inventoryQuantity"] == 25
        assert data["options"]["Size"] == "Medium"


# ============================================================
# Test 2: Product with nested data retrieved completely
# ============================================================
class TestProductNestedData:
    def test_product_get_includes_variants_options_images(self):
        """Pattern 2: GET product returns complete nested arrays."""
        # Create product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Nested Test", "handle": unique("nested-"), "status": "published"},
        )
        prod_id = resp.json()["id"]

        # Add 2 variants
        for i in range(2):
            requests.post(
                url(f"/admin/products/{prod_id}/variants"),
                headers=admin_headers(),
                json={
                    "title": f"Variant {i}",
                    "sku": unique(f"NT-{i}-"),
                    "price": 1000 * (i + 1),
                    "inventoryQuantity": 10 * (i + 1),
                },
            )

        # Add 2 options
        for opt_title in ["Size", "Color"]:
            requests.post(
                url(f"/admin/products/{prod_id}/options"),
                headers=admin_headers(),
                json={"title": opt_title},
            )

        # Add 2 images
        for i in range(2):
            requests.post(
                url(f"/admin/products/{prod_id}/images"),
                headers=admin_headers(),
                json={"url": f"https://img.test/{i}.jpg", "sortOrder": i},
            )

        # Retrieve via store endpoint
        resp = requests.get(url(f"/store/products/{prod_id}"), headers=customer_headers())
        assert resp.status_code == 200
        product = resp.json()

        # Verify variants array
        assert "variants" in product, "Product missing 'variants' array"
        assert isinstance(product["variants"], list)
        assert len(product["variants"]) == 2
        for v in product["variants"]:
            assert "id" in v
            assert "productId" in v
            assert "title" in v
            assert "sku" in v
            assert "price" in v
            assert "inventoryQuantity" in v

        # Verify options array
        assert "options" in product, "Product missing 'options' array"
        assert len(product["options"]) == 2
        for o in product["options"]:
            assert "id" in o
            assert "productId" in o
            assert "title" in o

        # Verify images array
        assert "images" in product, "Product missing 'images' array"
        assert len(product["images"]) == 2
        for img in product["images"]:
            assert "id" in img
            assert "productId" in img
            assert "url" in img
            assert "sortOrder" in img
            assert "sort_order" not in img, "Should be 'sortOrder' not 'sort_order'"


# ============================================================
# Test 3: Cart totals are CALCULATED, not echoed/hardcoded
# ============================================================
class TestCartCalculations:
    def _setup_product_and_cart(self, price, qty, tax_rate=0.1, cust_key=None):
        """Helper to create region, product, variant, customer, cart, and add item."""
        key = cust_key or f"cust_{uuid.uuid4().hex[:8]}"
        # Register customer
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@calc.test", "firstName": "Calc", "lastName": "Test"},
        )
        # Create region
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("CalcReg-"), "currency": "usd", "taxRate": tax_rate},
        )
        region_id = resp.json()["id"]
        # Product + variant
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "CalcProd", "handle": unique("calc-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("CP-"), "price": price, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]
        # Cart
        requests.post(
            url("/store/carts"),
            headers=customer_headers(key),
            json={"regionId": region_id},
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": qty},
        )
        return key, region_id, variant_id

    def test_subtotal_is_price_times_quantity_not_hardcoded(self):
        """Pattern 5: Verify subtotal = unitPrice * qty with different inputs."""
        # Test case 1: price=3000, qty=3 → subtotal=9000
        key1, _, _ = self._setup_product_and_cart(3000, 3, tax_rate=0.0)
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key1))
        assert resp.status_code == 200
        cart = resp.json()
        assert cart["subtotal"] == 9000, f"Expected 9000, got {cart['subtotal']}"

        # Test case 2: price=7777, qty=2 → subtotal=15554
        key2, _, _ = self._setup_product_and_cart(7777, 2, tax_rate=0.0)
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key2))
        cart2 = resp.json()
        assert cart2["subtotal"] == 15554, f"Expected 15554, got {cart2['subtotal']}"

    def test_tax_calculation_with_different_rates(self):
        """Pattern 5: Verify tax = (subtotal - discount) * taxRate with multiple rates."""
        # 10% tax on 5000 subtotal
        key1, _, _ = self._setup_product_and_cart(5000, 1, tax_rate=0.1)
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key1))
        cart1 = resp.json()
        assert cart1["tax"] == 500, f"Expected tax=500, got {cart1['tax']}"
        assert cart1["total"] == 5500, f"Expected total=5500, got {cart1['total']}"

        # 20% tax on 8000 subtotal
        key2, _, _ = self._setup_product_and_cart(4000, 2, tax_rate=0.2)
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key2))
        cart2 = resp.json()
        assert cart2["tax"] == 1600, f"Expected tax=1600, got {cart2['tax']}"
        assert cart2["total"] == 9600, f"Expected total=9600, got {cart2['total']}"

    def test_cart_total_formula_subtotal_minus_discount_plus_tax_plus_shipping(self):
        """Pattern 5: Verify total = subtotal - discount + tax + shipping."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@formula.test", "firstName": "F", "lastName": "T"},
        )
        # Region with 5% tax
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("FormReg-"), "currency": "usd", "taxRate": 0.05},
        )
        region_id = resp.json()["id"]
        # Shipping method 800
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": "FormShip", "price": 800},
        )
        ship_id = resp.json()["id"]
        # Discount 10%
        disc_code = unique("FORM")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": disc_code, "type": "percentage", "value": 10},
        )
        # Product price=20000, qty=1
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "FormProd", "handle": unique("fp-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("FP-"), "price": 20000, "inventoryQuantity": 50},
        )
        variant_id = resp.json()["id"]
        # Cart
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 1},
        )
        # Apply discount
        requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": disc_code},
        )
        # Set shipping
        requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(key),
            json={"shippingMethodId": ship_id},
        )
        # Verify: subtotal=20000, discount=2000, tax=(20000-2000)*0.05=900, shipping=800
        # total=20000-2000+900+800=19700
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        assert cart["subtotal"] == 20000
        assert cart["discount"] == 2000
        assert cart["tax"] == 900
        assert cart["shipping"] == 800
        assert cart["total"] == 19700


# ============================================================
# Test 4: Status codes strictly match spec
# ============================================================
class TestStatusCodes:
    def test_post_creates_return_201(self):
        """Pattern 4: All POST creation endpoints return 201."""
        # Region
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("R-"), "currency": "usd", "taxRate": 0.1},
        )
        assert resp.status_code == 201, f"POST /admin/regions: expected 201 got {resp.status_code}"

        # Category
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": unique("Cat-"), "handle": unique("cat-")},
        )
        assert resp.status_code == 201, f"POST /admin/categories: expected 201 got {resp.status_code}"

        # Collection
        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": unique("Col-"), "handle": unique("col-")},
        )
        assert resp.status_code == 201, f"POST /admin/collections: expected 201 got {resp.status_code}"

        # Shipping method
        region_id = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("SR-"), "currency": "eur", "taxRate": 0.2},
        ).json()["id"]
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": unique("Ship-"), "price": 500},
        )
        assert resp.status_code == 201, f"POST /admin/shipping-methods: expected 201 got {resp.status_code}"

        # Discount
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": unique("DISC"), "type": "fixed", "value": 100},
        )
        assert resp.status_code == 201, f"POST /admin/discounts: expected 201 got {resp.status_code}"

    def test_delete_returns_204_no_body(self):
        """Pattern 4: All DELETE endpoints return 204."""
        # Create then delete a region
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("Del-"), "currency": "gbp", "taxRate": 0.15},
        )
        region_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/regions/{region_id}"), headers=admin_headers())
        assert resp.status_code == 204, f"DELETE region: expected 204 got {resp.status_code}"

        # Create then delete product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "DelProd", "handle": unique("del-prod-")},
        )
        prod_id = resp.json()["id"]
        resp = requests.delete(url(f"/admin/products/{prod_id}"), headers=admin_headers())
        assert resp.status_code == 204, f"DELETE product: expected 204 got {resp.status_code}"

    def test_not_found_returns_404(self):
        """Pattern 4: Non-existent resources return 404."""
        fake_id = "nonexistent-id-12345"
        resp = requests.get(url(f"/store/products/{fake_id}"), headers=customer_headers())
        assert resp.status_code == 404

        resp = requests.put(
            url(f"/admin/products/{fake_id}"),
            headers=admin_headers(),
            json={"title": "X"},
        )
        assert resp.status_code == 404

        resp = requests.delete(url(f"/admin/products/{fake_id}"), headers=admin_headers())
        assert resp.status_code == 404


# ============================================================
# Test 5: Pagination and filtering actually work
# ============================================================
class TestPaginationAndFiltering:
    def test_product_pagination_limit_offset(self):
        """Pattern 3: Verify limit/offset actually restricts results."""
        # Create 5 products
        for i in range(5):
            requests.post(
                url("/admin/products"),
                headers=admin_headers(),
                json={"title": f"PagProd {i}", "handle": unique(f"pag-{i}-"), "status": "published"},
            )
        # Request with limit=2
        resp = requests.get(url("/store/products?limit=2&offset=0"), headers=customer_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["products"]) <= 2, f"Limit=2 but got {len(data['products'])} products"
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Request with offset
        resp2 = requests.get(url("/store/products?limit=2&offset=2"), headers=customer_headers())
        data2 = resp2.json()
        assert data2["offset"] == 2
        # Products should be different from first page
        ids_page1 = {p["id"] for p in data["products"]}
        ids_page2 = {p["id"] for p in data2["products"]}
        assert ids_page1.isdisjoint(ids_page2), "Pagination returned same items on different pages"

    def test_product_filter_by_category_excludes_others(self):
        """Pattern 3: categoryId filter ONLY returns matching products."""
        # Create two categories
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "CatA", "handle": unique("cata-")},
        )
        cat_a_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "CatB", "handle": unique("catb-")},
        )
        cat_b_id = resp.json()["id"]
        # Create products in each
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "InCatA", "handle": unique("inca-"), "status": "published", "categoryId": cat_a_id},
        )
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "InCatB", "handle": unique("incb-"), "status": "published", "categoryId": cat_b_id},
        )
        # Filter by CatA
        resp = requests.get(url(f"/store/products?categoryId={cat_a_id}"), headers=customer_headers())
        products = resp.json()["products"]
        assert len(products) >= 1
        for p in products:
            assert p["categoryId"] == cat_a_id, f"Filter returned product with categoryId={p.get('categoryId')}"

    def test_product_filter_by_collection(self):
        """Pattern 3: collectionId filter works correctly."""
        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": "FilterCol", "handle": unique("filtcol-")},
        )
        col_id = resp.json()["id"]
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "InCol", "handle": unique("incol-"), "status": "published", "collectionId": col_id},
        )
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "NoCol", "handle": unique("nocol-"), "status": "published"},
        )
        resp = requests.get(url(f"/store/products?collectionId={col_id}"), headers=customer_headers())
        products = resp.json()["products"]
        assert len(products) >= 1
        for p in products:
            assert p["collectionId"] == col_id

    def test_product_title_search(self):
        """Pattern 3: Title search returns partial matches."""
        unique_word = unique("XYZZY")
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": f"Special {unique_word} Product", "handle": unique("srch-"), "status": "published"},
        )
        resp = requests.get(url(f"/store/products?title={unique_word}"), headers=customer_headers())
        products = resp.json()["products"]
        assert len(products) >= 1
        assert unique_word in products[0]["title"]

    def test_store_only_shows_published_not_draft(self):
        """Pattern 3: Store listing excludes draft products."""
        unique_title = unique("DraftCheck")
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": f"{unique_title} Draft", "handle": unique("dc-d-"), "status": "draft"},
        )
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": f"{unique_title} Published", "handle": unique("dc-p-"), "status": "published"},
        )
        resp = requests.get(url(f"/store/products?title={unique_title}"), headers=customer_headers())
        products = resp.json()["products"]
        for p in products:
            assert p["status"] == "published", "Draft product leaked to store listing"


# ============================================================
# Test 6: Cart item fields verification
# ============================================================
class TestCartItemFields:
    def test_cart_item_has_correct_camel_case_fields(self):
        """Pattern 1: Cart items use camelCase (cartId, variantId, unitPrice)."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@item.test", "firstName": "I", "lastName": "T"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("IR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ItemProd", "handle": unique("ip-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("IP-"), "price": 3500, "inventoryQuantity": 20},
        )
        variant_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 2},
        )
        assert resp.status_code == 201
        cart = resp.json()
        item = cart["items"][0]
        # Verify camelCase
        assert "cartId" in item, "Missing 'cartId'"
        assert "variantId" in item, "Missing 'variantId'"
        assert "unitPrice" in item, "Missing 'unitPrice'"
        assert "cart_id" not in item, "Should be 'cartId' not 'cart_id'"
        assert "variant_id" not in item, "Should be 'variantId' not 'variant_id'"
        assert "unit_price" not in item, "Should be 'unitPrice' not 'unit_price'"
        # Verify values
        assert item["variantId"] == variant_id
        assert item["quantity"] == 2
        assert item["unitPrice"] == 3500


# ============================================================
# Test 7: Discount application and calculation
# ============================================================
class TestDiscountCalculations:
    def test_percentage_discount_calculated_correctly(self):
        """Pattern 5: Percentage discount = value% of subtotal (not hardcoded)."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@pct.test", "firstName": "P", "lastName": "D"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("PR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        # Discount 25%
        code = unique("PCT25")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 25},
        )
        # Product price=12000
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "PctProd", "handle": unique("pct-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("PP-"), "price": 12000, "inventoryQuantity": 50},
        )
        variant_id = resp.json()["id"]
        # Cart with qty=2 → subtotal=24000
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 2},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        # 25% of 24000 = 6000
        assert cart["subtotal"] == 24000
        assert cart["discount"] == 6000, f"Expected discount=6000, got {cart['discount']}"
        assert cart["total"] == 18000

    def test_fixed_discount_capped_at_subtotal(self):
        """Pattern 5: Fixed discount cannot exceed subtotal."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@fix.test", "firstName": "F", "lastName": "D"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("FR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        # Fixed discount of 50000 (more than subtotal)
        code = unique("BIG")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "fixed", "value": 50000},
        )
        # Product price=3000
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "CheapProd", "handle": unique("cheap-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("CH-"), "price": 3000, "inventoryQuantity": 50},
        )
        variant_id = resp.json()["id"]
        # Cart qty=1 → subtotal=3000
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        # Discount capped at subtotal=3000
        assert cart["discount"] == 3000, f"Expected discount capped at 3000, got {cart['discount']}"
        assert cart["total"] == 0


# ============================================================
# Test 8: Shipping method integration
# ============================================================
class TestShippingMethodFields:
    def test_shipping_method_camel_case_and_region_association(self):
        """Pattern 1+2: Verify shipping method fields and region filter."""
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("SMReg-"), "currency": "usd", "taxRate": 0.05},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": "Express Delivery", "price": 1500},
        )
        assert resp.status_code == 201
        sm = resp.json()
        assert "id" in sm
        assert "regionId" in sm, "Missing 'regionId' (camelCase)"
        assert "region_id" not in sm
        assert sm["regionId"] == region_id
        assert sm["name"] == "Express Delivery"
        assert sm["price"] == 1500

        # Verify store endpoint shows it under correct region
        resp = requests.get(
            url(f"/store/regions/{region_id}/shipping-methods"),
            headers=customer_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "shippingMethods" in data, "Response should have 'shippingMethods' key"
        assert "shipping_methods" not in data
        found = any(m["id"] == sm["id"] for m in data["shippingMethods"])
        assert found, "Shipping method not found under its region"


# ============================================================
# Test 9: Customer and address field verification
# ============================================================
class TestCustomerAddressFields:
    def test_customer_fields_camel_case(self):
        """Pattern 1: Customer response uses camelCase."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        resp = requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": "camel@test.com", "firstName": "Camel", "lastName": "Case"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "firstName" in data, "Missing 'firstName'"
        assert "lastName" in data, "Missing 'lastName'"
        assert "createdAt" in data, "Missing 'createdAt'"
        assert "first_name" not in data
        assert "last_name" not in data
        assert "created_at" not in data
        assert data["firstName"] == "Camel"
        assert data["lastName"] == "Case"

    def test_address_fields_camel_case(self):
        """Pattern 1: Address response uses camelCase."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@addr.test", "firstName": "A", "lastName": "B"},
        )
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(key),
            json={
                "firstName": "Ship",
                "lastName": "To",
                "address1": "100 Main St",
                "address2": "Apt 5",
                "city": "Boston",
                "province": "MA",
                "postalCode": "02101",
                "countryCode": "US",
                "phone": "555-1234",
                "isDefault": True,
            },
        )
        assert resp.status_code == 201
        addr = resp.json()
        assert "customerId" in addr, "Missing 'customerId'"
        assert "customer_id" not in addr
        assert "firstName" in addr
        assert "lastName" in addr
        assert "postalCode" in addr, "Missing 'postalCode'"
        assert "postal_code" not in addr
        assert "countryCode" in addr, "Missing 'countryCode'"
        assert "country_code" not in addr
        assert "isDefault" in addr, "Missing 'isDefault'"
        assert "is_default" not in addr
        assert addr["postalCode"] == "02101"
        assert addr["countryCode"] == "US"
        assert addr["isDefault"] is True


# ============================================================
# Test 10: Discount field verification
# ============================================================
class TestDiscountFields:
    def test_discount_camel_case_fields(self):
        """Pattern 1: Discount response uses camelCase."""
        code = unique("FLD")
        resp = requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={
                "code": code,
                "type": "percentage",
                "value": 15,
                "usageLimit": 100,
                "startsAt": "2024-01-01T00:00:00Z",
                "endsAt": "2099-12-31T23:59:59Z",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "usageLimit" in data, "Missing 'usageLimit'"
        assert "usageCount" in data, "Missing 'usageCount'"
        assert "startsAt" in data, "Missing 'startsAt'"
        assert "endsAt" in data, "Missing 'endsAt'"
        assert "regionId" in data or data.get("regionId") is None
        assert "usage_limit" not in data
        assert "usage_count" not in data
        assert "starts_at" not in data
        assert "ends_at" not in data
        assert "region_id" not in data
        assert data["usageCount"] == 0
        assert data["usageLimit"] == 100


# ============================================================
# Test 11: Order fields and payment integration
# ============================================================
class TestOrderFields:
    def test_order_response_camel_case_fields(self):
        """Pattern 1+4: Order creation returns 201 with camelCase fields."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@order.test", "firstName": "O", "lastName": "F"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("OR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "OrdProd", "handle": unique("ord-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("OP-"), "price": 5000, "inventoryQuantity": 20},
        )
        variant_id = resp.json()["id"]
        resp = requests.post(
            url("/store/customers/me/addresses"),
            headers=customer_headers(key),
            json={
                "firstName": "O", "lastName": "F",
                "address1": "1 Order St", "city": "NYC",
                "province": "NY", "postalCode": "10001", "countryCode": "US",
            },
        )
        addr_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        # Verify camelCase fields
        assert "customerId" in order, "Missing 'customerId'"
        assert "cartId" in order, "Missing 'cartId'"
        assert "regionId" in order, "Missing 'regionId'"
        assert "paymentId" in order, "Missing 'paymentId'"
        assert "shippingMethodId" in order or order.get("shippingMethodId") is None
        assert "shippingAddress" in order or order.get("shippingAddress") is None
        assert "createdAt" in order
        assert "updatedAt" in order
        # No snake_case
        assert "customer_id" not in order
        assert "cart_id" not in order
        assert "region_id" not in order
        assert "payment_id" not in order
        assert "shipping_method_id" not in order
        assert "shipping_address" not in order
        assert "created_at" not in order
        assert "updated_at" not in order
        # Values
        assert order["status"] == "pending"
        assert order["subtotal"] == 5000
        assert order["total"] == 5000
        assert order["paymentId"] is not None


# ============================================================
# Test 12: Region field verification
# ============================================================
class TestRegionFields:
    def test_region_camel_case_fields(self):
        """Pattern 1: Region uses 'taxRate' not 'tax_rate'."""
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("RgnTest-"), "currency": "eur", "taxRate": 0.19},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "taxRate" in data, "Missing 'taxRate' (camelCase)"
        assert "tax_rate" not in data, "Should use 'taxRate' not 'tax_rate'"
        assert data["taxRate"] == 0.19
        assert data["currency"] == "eur"


# ============================================================
# Test 13: Auth and permission enforcement
# ============================================================
class TestAuthEnforcement:
    def test_admin_endpoints_reject_customer_key(self):
        """Pattern 4+6: Admin endpoints return 403 for non-admin keys."""
        cust_key = f"cust_{uuid.uuid4().hex[:8]}"
        endpoints = [
            ("POST", "/admin/products", {"title": "X", "handle": "x"}),
            ("POST", "/admin/categories", {"name": "X", "handle": "x"}),
            ("POST", "/admin/discounts", {"code": "X", "type": "fixed", "value": 1}),
            ("GET", "/admin/orders", None),
        ]
        for method, path, body in endpoints:
            if method == "POST":
                resp = requests.post(url(path), headers=customer_headers(cust_key), json=body)
            else:
                resp = requests.get(url(path), headers=customer_headers(cust_key))
            assert resp.status_code == 403, f"{method} {path} should return 403 for customer, got {resp.status_code}"

    def test_missing_api_key_returns_401(self):
        """Pattern 4: No API key → 401."""
        resp = requests.get(url("/store/products"))
        assert resp.status_code == 401
        resp = requests.get(url("/admin/regions"))
        assert resp.status_code == 401


# ============================================================
# Test 14: Cart with shipping cost included in total
# ============================================================
class TestCartShippingInTotal:
    def test_shipping_cost_adds_to_total(self):
        """Pattern 5: Shipping cost is included in final total calculation."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@ship.test", "firstName": "S", "lastName": "T"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("ShipCalc-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": "Expensive Ship", "price": 2500},
        )
        ship_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ShipCalcProd", "handle": unique("sc-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("SC-"), "price": 10000, "inventoryQuantity": 30},
        )
        variant_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 1},
        )
        # Before shipping
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        assert cart["shipping"] == 0
        assert cart["total"] == 10000

        # After adding shipping
        requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(key),
            json={"shippingMethodId": ship_id},
        )
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        assert cart["shipping"] == 2500
        assert cart["total"] == 12500, f"Expected 12500 (10000+2500), got {cart['total']}"


# ============================================================
# Test 15: Order list pagination fields
# ============================================================
class TestOrderListPagination:
    def test_order_list_returns_count_limit_offset(self):
        """Pattern 3: Order listing includes pagination metadata."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@olp.test", "firstName": "O", "lastName": "L"},
        )
        resp = requests.get(url("/store/orders?limit=5&offset=0"), headers=customer_headers(key))
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["orders"], list)
        assert isinstance(data["count"], int)


# ============================================================
# Test 16: Admin orders list with status filter
# ============================================================
class TestAdminOrderFilter:
    def test_admin_orders_filter_by_status(self):
        """Pattern 3: Status filter on admin orders endpoint works."""
        # First check that the endpoint accepts status parameter
        resp = requests.get(
            url("/admin/orders?status=pending"), headers=admin_headers()
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data
        # All returned orders should have pending status
        for order in data["orders"]:
            assert order["status"] == "pending", f"Filter returned order with status={order['status']}"


# ============================================================
# Test 17: Category with parent association
# ============================================================
class TestCategoryHierarchy:
    def test_category_parent_child_relationship(self):
        """Pattern 1+2: parentCategoryId field present and usable."""
        # Create parent
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Parent", "handle": unique("parent-")},
        )
        assert resp.status_code == 201
        parent = resp.json()
        assert "parentCategoryId" in parent or parent.get("parentCategoryId") is None
        assert "parent_category_id" not in parent
        parent_id = parent["id"]

        # Create child with parent
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Child", "handle": unique("child-"), "parentCategoryId": parent_id},
        )
        assert resp.status_code == 201
        child = resp.json()
        assert child["parentCategoryId"] == parent_id


# ============================================================
# Test 18: Product image sortOrder field
# ============================================================
class TestProductImageSortOrder:
    def test_image_sort_order_camel_case(self):
        """Pattern 1: Image uses 'sortOrder' not 'sort_order'."""
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ImgSort", "handle": unique("imgsort-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/images"),
            headers=admin_headers(),
            json={"url": "https://example.com/test.jpg", "sortOrder": 5},
        )
        assert resp.status_code == 201
        img = resp.json()
        assert "sortOrder" in img, "Missing 'sortOrder'"
        assert "sort_order" not in img, "Should be 'sortOrder' not 'sort_order'"
        assert img["sortOrder"] == 5
        assert "productId" in img
        assert "product_id" not in img


# ============================================================
# Test 19: Cart discountCode field in response
# ============================================================
class TestCartDiscountCodeField:
    def test_cart_has_discount_code_field(self):
        """Pattern 1: Cart response includes 'discountCode' field."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@dcf.test", "firstName": "D", "lastName": "C"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("DCF-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        # discountCode should be present (null when no discount applied)
        assert "discountCode" in cart, "Missing 'discountCode' field"
        assert "discount_code" not in cart
        assert cart["discountCode"] is None


# ============================================================
# Test 20: Inventory check on adding to cart
# ============================================================
class TestInventoryCheckOnAdd:
    def test_cannot_add_more_than_inventory(self):
        """Pattern 5: Inventory check is enforced on add-to-cart."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@inv.test", "firstName": "I", "lastName": "V"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("InvR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        # Product with inventory=3
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "LimitedProd", "handle": unique("ltd-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("LT-"), "price": 2000, "inventoryQuantity": 3},
        )
        variant_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        # Try to add qty=4 (exceeds inventory of 3)
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 4},
        )
        assert resp.status_code == 409, f"Expected 409 for insufficient inventory, got {resp.status_code}"

    def test_can_add_exactly_inventory_amount(self):
        """Pattern 5: Can add items up to inventory limit."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@exact.test", "firstName": "E", "lastName": "X"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("ExR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "ExactProd", "handle": unique("exact-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("EX-"), "price": 1000, "inventoryQuantity": 5},
        )
        variant_id = resp.json()["id"]
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        # Add exactly 5
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 5},
        )
        assert resp.status_code == 201


# ============================================================
# Test 21: Discount region restriction
# ============================================================
class TestDiscountRegionRestriction:
    def test_discount_with_wrong_region_returns_422(self):
        """Pattern 5: Region-restricted discount rejected for wrong region."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@drr.test", "firstName": "D", "lastName": "R"},
        )
        # Region A (for discount)
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("RegA-"), "currency": "usd", "taxRate": 0.0},
        )
        region_a_id = resp.json()["id"]
        # Region B (for cart)
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("RegB-"), "currency": "eur", "taxRate": 0.1},
        )
        region_b_id = resp.json()["id"]
        # Discount restricted to region A
        code = unique("REGA")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 10, "regionId": region_a_id},
        )
        # Product
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "RegProd", "handle": unique("rp-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("RP-"), "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        # Cart in region B
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_b_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 1},
        )
        # Try to apply discount restricted to region A
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": code},
        )
        assert resp.status_code == 422, f"Expected 422 for region mismatch, got {resp.status_code}"


# ============================================================
# Test 22: Multiple items in cart calculation
# ============================================================
class TestMultiItemCartCalculation:
    def test_cart_with_multiple_different_items(self):
        """Pattern 5: Subtotal sums ALL items, not just first."""
        key = f"cust_{uuid.uuid4().hex[:8]}"
        requests.post(
            url("/store/customers"),
            headers=customer_headers(key),
            json={"email": f"{key}@multi.test", "firstName": "M", "lastName": "I"},
        )
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("MultiR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        # Two products with different prices
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Prod1", "handle": unique("m1-"), "status": "published"},
        )
        pid1 = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{pid1}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("M1-"), "price": 2000, "inventoryQuantity": 50},
        )
        vid1 = resp.json()["id"]

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Prod2", "handle": unique("m2-"), "status": "published"},
        )
        pid2 = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{pid2}/variants"),
            headers=admin_headers(),
            json={"title": "V2", "sku": unique("M2-"), "price": 3500, "inventoryQuantity": 50},
        )
        vid2 = resp.json()["id"]

        # Cart with both items
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": vid1, "quantity": 2},  # 2000*2=4000
        )
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": vid2, "quantity": 3},  # 3500*3=10500
        )
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        assert len(cart["items"]) == 2
        # subtotal = 4000 + 10500 = 14500
        assert cart["subtotal"] == 14500, f"Expected subtotal=14500, got {cart['subtotal']}"
        assert cart["total"] == 14500
