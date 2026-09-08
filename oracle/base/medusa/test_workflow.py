"""L3 Workflow Tests for Medusa Headless E-Commerce API.

End-to-end multi-entity workflows targeting:
- Complete purchase flows with side-effect verification
- Payment integration (success and failure)
- Discount usage tracking and limits
- Inventory management across orders
- Order status state machine
- Multi-variant product handling
- Data isolation between customers
"""
import os
import requests
import uuid

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin_l3test"


def url(path):
    return f"{BASE_URL}{path}"


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def customer_headers(key):
    return {"X-API-Key": key, "Content-Type": "application/json"}


def unique(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def setup_customer(key):
    """Register a customer and add a shipping address."""
    requests.post(
        url("/store/customers"),
        headers=customer_headers(key),
        json={"email": f"{key}@workflow.test", "firstName": "WF", "lastName": "User"},
    )
    resp = requests.post(
        url("/store/customers/me/addresses"),
        headers=customer_headers(key),
        json={
            "firstName": "WF", "lastName": "User",
            "address1": "100 Workflow Ave", "city": "Portland",
            "province": "OR", "postalCode": "97201", "countryCode": "US",
        },
    )
    return resp.json()["id"]


# ============================================================
# Test 1: Complete Purchase Workflow with Inventory Verification
# ============================================================
class TestCompletePurchaseWorkflow:
    def test_full_purchase_decrements_stock(self):
        """
        Pattern 5+7: Complete purchase flow verifies:
        1. Product created with stock=10
        2. Cart created, item added (qty=3)
        3. Cart totals calculated correctly
        4. Order created (payment succeeds)
        5. Inventory decremented to 7
        6. Cart no longer active
        7. Order has correct totals and status
        """
        key = f"cust_{uuid.uuid4().hex[:8]}"
        addr_id = setup_customer(key)

        # 1. Create region and product with stock=10
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("PurchR-"), "currency": "usd", "taxRate": 0.08},
        )
        region_id = resp.json()["id"]

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Purchase Test", "handle": unique("purch-"), "status": "published"},
        )
        prod_id = resp.json()["id"]

        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "Default", "sku": unique("PT-"), "price": 5000, "inventoryQuantity": 10},
        )
        variant_id = resp.json()["id"]
        assert resp.json()["inventoryQuantity"] == 10

        # 2. Create cart and add 3 items
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
        cart = resp.json()
        assert cart["items"][0]["quantity"] == 3
        assert cart["items"][0]["unitPrice"] == 5000

        # 3. Verify cart totals: subtotal=15000, tax=15000*0.08=1200, total=16200
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        assert cart["subtotal"] == 15000
        assert cart["tax"] == 1200
        assert cart["total"] == 16200

        # 4. Create order
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["status"] == "pending"
        assert order["subtotal"] == 15000
        assert order["tax"] == 1200
        assert order["total"] == 16200
        assert order["paymentId"] is not None

        # 5. Verify inventory decreased (try to add 8 items - should fail since only 7 left)
        key2 = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key2)
        requests.post(url("/store/carts"), headers=customer_headers(key2), json={"regionId": region_id})
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": variant_id, "quantity": 8},
        )
        assert resp.status_code == 409, "Should fail: only 7 inventory remaining after purchase of 3"

        # Verify adding 7 succeeds
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": variant_id, "quantity": 7},
        )
        assert resp.status_code == 201, "Should succeed: exactly 7 remaining"

        # 6. Verify original customer's cart is gone
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        assert resp.status_code == 404, "Cart should be deactivated after order"


# ============================================================
# Test 2: Payment Failure Handling
# ============================================================
class TestPaymentFailureHandling:
    def test_payment_failure_does_not_create_order_or_decrement_stock(self):
        """
        Pattern 5+7: When payment fails (amount > 999999):
        1. Order is NOT created (422 response)
        2. Inventory is NOT decremented
        3. Cart remains active
        """
        key = f"cust_{uuid.uuid4().hex[:8]}"
        addr_id = setup_customer(key)

        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("FailR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]

        # Expensive product: 500000 * 3 = 1500000 > 999999
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Expensive", "handle": unique("exp-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("EXP-"), "price": 500000, "inventoryQuantity": 5},
        )
        variant_id = resp.json()["id"]

        # Cart with qty=3 → total = 1500000 > 999999
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 3},
        )

        # Attempt checkout - should fail
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 422, f"Expected 422 for payment failure, got {resp.status_code}"

        # Verify cart still active
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        assert resp.status_code == 200, "Cart should still be active after payment failure"

        # Verify inventory NOT decremented (another customer can still buy 5)
        key2 = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key2)
        requests.post(url("/store/carts"), headers=customer_headers(key2), json={"regionId": region_id})
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": variant_id, "quantity": 5},
        )
        assert resp.status_code == 201, "Inventory should not have been decremented on payment failure"


# ============================================================
# Test 3: Discount Usage Limit Enforcement
# ============================================================
class TestDiscountUsageLimitWorkflow:
    def test_discount_usage_count_increments_and_limits(self):
        """
        Pattern 5+7: Discount with usageLimit=1:
        1. Create discount with limit=1
        2. First customer uses it → order succeeds, usageCount=1
        3. Second customer tries to use it → 422 (limit exceeded)
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("DLimR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]

        code = unique("ONCE")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 10, "usageLimit": 1},
        )

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "DiscLimitProd", "handle": unique("dlim-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("DL-"), "price": 5000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        # Customer 1 uses the discount and checks out
        key1 = f"cust_{uuid.uuid4().hex[:8]}"
        addr1 = setup_customer(key1)
        requests.post(url("/store/carts"), headers=customer_headers(key1), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key1),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key1),
            json={"code": code},
        )
        assert resp.status_code == 200
        cart = resp.json()
        assert cart["discount"] == 500  # 10% of 5000

        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key1),
            json={"shippingAddressId": addr1},
        )
        assert resp.status_code == 201

        # Customer 2 tries to use the same discount
        key2 = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key2)
        requests.post(url("/store/carts"), headers=customer_headers(key2), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key2),
            json={"code": code},
        )
        assert resp.status_code == 422, "Discount should be rejected after usage limit reached"


# ============================================================
# Test 4: Multi-Variant Product Cart
# ============================================================
class TestMultiVariantCartWorkflow:
    def test_multiple_variants_separate_line_items_correct_totals(self):
        """
        Pattern 2+5: Product with 3 variants (S/M/L) at different prices:
        1. Add each variant to cart
        2. Verify 3 separate line items
        3. Verify each has correct unitPrice
        4. Verify subtotal sums all correctly
        """
        key = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key)

        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("MVR-"), "currency": "usd", "taxRate": 0.1},
        )
        region_id = resp.json()["id"]

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Multi-Size Shirt", "handle": unique("mv-"), "status": "published"},
        )
        prod_id = resp.json()["id"]

        # Create 3 variants with different prices
        variants = []
        prices = [2000, 2500, 3000]  # S, M, L
        for i, (size, price) in enumerate(zip(["Small", "Medium", "Large"], prices)):
            resp = requests.post(
                url(f"/admin/products/{prod_id}/variants"),
                headers=admin_headers(),
                json={
                    "title": size,
                    "sku": unique(f"MV-{size[0]}-"),
                    "price": price,
                    "inventoryQuantity": 20,
                    "options": {"Size": size},
                },
            )
            assert resp.status_code == 201
            variants.append(resp.json())

        # Cart - add each variant
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})

        for v in variants:
            resp = requests.post(
                url("/store/carts/mine/items"),
                headers=customer_headers(key),
                json={"variantId": v["id"], "quantity": 1},
            )
            assert resp.status_code == 201

        # Verify cart
        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()

        # 3 separate line items
        assert len(cart["items"]) == 3, f"Expected 3 line items, got {len(cart['items'])}"

        # Verify each item's unitPrice matches variant price
        item_prices = sorted([item["unitPrice"] for item in cart["items"]])
        assert item_prices == sorted(prices), f"Expected prices {sorted(prices)}, got {item_prices}"

        # Verify subtotal = sum of all (price * qty)
        expected_subtotal = sum(prices)  # Each qty=1
        assert cart["subtotal"] == expected_subtotal, f"Expected subtotal={expected_subtotal}, got {cart['subtotal']}"

        # Verify tax = subtotal * 0.1
        expected_tax = int(expected_subtotal * 0.1)
        assert cart["tax"] == expected_tax

        # Verify total = subtotal + tax
        assert cart["total"] == expected_subtotal + expected_tax


# ============================================================
# Test 5: Order Status Workflow (Valid and Invalid Transitions)
# ============================================================
class TestOrderStatusWorkflow:
    def test_valid_status_progression_and_invalid_transitions_rejected(self):
        """
        Pattern 4+5: Order status machine:
        1. Create order → pending
        2. pending → confirmed ✓
        3. confirmed → shipped ✓
        4. shipped → delivered ✓
        5. Try: pending → shipped ✗ (skip)
        6. Try: pending → delivered ✗ (skip)
        7. Try: confirmed → delivered ✗ (skip)
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("StR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "StatusProd", "handle": unique("st-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("ST-"), "price": 1000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        def create_order():
            k = f"cust_{uuid.uuid4().hex[:8]}"
            a = setup_customer(k)
            requests.post(url("/store/carts"), headers=customer_headers(k), json={"regionId": region_id})
            requests.post(
                url("/store/carts/mine/items"),
                headers=customer_headers(k),
                json={"variantId": variant_id, "quantity": 1},
            )
            r = requests.post(url("/store/orders"), headers=customer_headers(k), json={"shippingAddressId": a})
            return r.json()["id"]

        # Valid progression: pending → confirmed → shipped → delivered
        order_id = create_order()

        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

        resp = requests.put(
            url(f"/admin/orders/{order_id}/status"),
            headers=admin_headers(),
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

        # Invalid: pending → shipped (skipping confirmed)
        order_id2 = create_order()
        resp = requests.put(
            url(f"/admin/orders/{order_id2}/status"),
            headers=admin_headers(),
            json={"status": "shipped"},
        )
        assert resp.status_code == 422, "pending → shipped should be invalid"

        # Invalid: pending → delivered (skipping confirmed+shipped)
        order_id3 = create_order()
        resp = requests.put(
            url(f"/admin/orders/{order_id3}/status"),
            headers=admin_headers(),
            json={"status": "delivered"},
        )
        assert resp.status_code == 422, "pending → delivered should be invalid"

        # Invalid: confirmed → delivered (skipping shipped)
        order_id4 = create_order()
        requests.put(
            url(f"/admin/orders/{order_id4}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )
        resp = requests.put(
            url(f"/admin/orders/{order_id4}/status"),
            headers=admin_headers(),
            json={"status": "delivered"},
        )
        assert resp.status_code == 422, "confirmed → delivered should be invalid"


# ============================================================
# Test 6: Inventory Protection Across Customers
# ============================================================
class TestInventoryProtection:
    def test_inventory_prevents_overselling(self):
        """
        Pattern 7+8: Stock=5, customer A buys 4, customer B cannot buy 2.
        Verifies side-effect (stock decrease) is real.
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("InvP-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "LimitedStock", "handle": unique("ls-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("LS-"), "price": 2000, "inventoryQuantity": 5},
        )
        variant_id = resp.json()["id"]

        # Customer A buys 4
        key_a = f"cust_{uuid.uuid4().hex[:8]}"
        addr_a = setup_customer(key_a)
        requests.post(url("/store/carts"), headers=customer_headers(key_a), json={"regionId": region_id})
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_a),
            json={"variantId": variant_id, "quantity": 4},
        )
        assert resp.status_code == 201

        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key_a),
            json={"shippingAddressId": addr_a},
        )
        assert resp.status_code == 201

        # Customer B tries to buy 2 (only 1 left)
        key_b = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key_b)
        requests.post(url("/store/carts"), headers=customer_headers(key_b), json={"regionId": region_id})
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_b),
            json={"variantId": variant_id, "quantity": 2},
        )
        assert resp.status_code == 409, "Should fail: only 1 item in stock after A bought 4"

        # But buying 1 should succeed
        resp = requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_b),
            json={"variantId": variant_id, "quantity": 1},
        )
        assert resp.status_code == 201, "Should succeed: exactly 1 remaining"


# ============================================================
# Test 7: Discount + Shipping + Tax Full Calculation Workflow
# ============================================================
class TestFullCalculationWorkflow:
    def test_discount_shipping_tax_all_interact_correctly(self):
        """
        Pattern 5: Verify the complete formula:
        subtotal = sum(price*qty)
        discount = percentage of subtotal
        tax = (subtotal - discount) * taxRate
        shipping = flat rate
        total = subtotal - discount + tax + shipping
        """
        key = f"cust_{uuid.uuid4().hex[:8]}"
        addr_id = setup_customer(key)

        # Region: 12% tax
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("FullCalcR-"), "currency": "usd", "taxRate": 0.12},
        )
        region_id = resp.json()["id"]

        # Shipping: 1200
        resp = requests.post(
            url("/admin/shipping-methods"),
            headers=admin_headers(),
            json={"regionId": region_id, "name": "Standard", "price": 1200},
        )
        ship_id = resp.json()["id"]

        # Discount: 15%
        code = unique("FULL15")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "percentage", "value": 15},
        )

        # Product: price=10000
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "FullCalcProd", "handle": unique("fc-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("FC-"), "price": 10000, "inventoryQuantity": 50},
        )
        variant_id = resp.json()["id"]

        # Build cart: qty=2 → subtotal=20000
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 2},
        )

        # Apply discount
        resp = requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": code},
        )
        assert resp.status_code == 200

        # Set shipping
        resp = requests.put(
            url("/store/carts/mine/shipping"),
            headers=customer_headers(key),
            json={"shippingMethodId": ship_id},
        )
        assert resp.status_code == 200
        cart = resp.json()

        # Verify calculations:
        # subtotal = 10000 * 2 = 20000
        assert cart["subtotal"] == 20000
        # discount = 15% of 20000 = 3000
        assert cart["discount"] == 3000
        # tax = (20000 - 3000) * 0.12 = 17000 * 0.12 = 2040
        assert cart["tax"] == 2040
        # shipping = 1200
        assert cart["shipping"] == 1200
        # total = 20000 - 3000 + 2040 + 1200 = 20240
        assert cart["total"] == 20240

        # Create order and verify same totals
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["subtotal"] == 20000
        assert order["discount"] == 3000
        assert order["tax"] == 2040
        assert order["shipping"] == 1200
        assert order["total"] == 20240


# ============================================================
# Test 8: Order Cancellation and Data Isolation
# ============================================================
class TestOrderCancellation:
    def test_customer_can_cancel_pending_but_not_confirmed(self):
        """
        Pattern 4+6: Customer cancellation rules:
        1. Create order → pending → cancel ✓
        2. Create order → confirm → cancel ✗ (422)
        Also verify customer B cannot see customer A's orders
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("CancelR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "CancelProd", "handle": unique("canc-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("CN-"), "price": 2000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        # Customer A: order 1 (cancel while pending)
        key_a = f"cust_{uuid.uuid4().hex[:8]}"
        addr_a = setup_customer(key_a)
        requests.post(url("/store/carts"), headers=customer_headers(key_a), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_a),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key_a),
            json={"shippingAddressId": addr_a},
        )
        order1_id = resp.json()["id"]

        # Cancel while pending → success
        resp = requests.post(
            url(f"/store/orders/{order1_id}/cancel"),
            headers=customer_headers(key_a),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Customer A: order 2 (try cancel after confirmed)
        requests.post(url("/store/carts"), headers=customer_headers(key_a), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_a),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key_a),
            json={"shippingAddressId": addr_a},
        )
        order2_id = resp.json()["id"]

        # Admin confirms
        requests.put(
            url(f"/admin/orders/{order2_id}/status"),
            headers=admin_headers(),
            json={"status": "confirmed"},
        )

        # Customer tries to cancel → fail
        resp = requests.post(
            url(f"/store/orders/{order2_id}/cancel"),
            headers=customer_headers(key_a),
        )
        assert resp.status_code == 422, "Cannot cancel confirmed order"

        # Customer B cannot see A's orders
        key_b = f"cust_{uuid.uuid4().hex[:8]}"
        setup_customer(key_b)
        resp = requests.get(url("/store/orders"), headers=customer_headers(key_b))
        assert resp.status_code == 200
        orders_b = resp.json()["orders"]
        order_ids_b = [o["id"] for o in orders_b]
        assert order1_id not in order_ids_b, "Customer B should not see A's orders"
        assert order2_id not in order_ids_b, "Customer B should not see A's orders"


# ============================================================
# Test 9: Refund Workflow
# ============================================================
class TestRefundWorkflow:
    def test_refund_full_and_partial(self):
        """
        Pattern 5+7: Refund handling:
        1. Create order (amount=5000)
        2. Full refund → payment status becomes 'refunded', refundId set
        3. Second order → partial refund of 1000
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("RefR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "RefundProd", "handle": unique("ref-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("RF-"), "price": 5000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        # Order 1: full refund
        key1 = f"cust_{uuid.uuid4().hex[:8]}"
        addr1 = setup_customer(key1)
        requests.post(url("/store/carts"), headers=customer_headers(key1), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key1),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key1),
            json={"shippingAddressId": addr1},
        )
        assert resp.status_code == 201
        order1_id = resp.json()["id"]
        assert resp.json()["total"] == 5000

        # Full refund
        resp = requests.post(
            url(f"/admin/orders/{order1_id}/refund"),
            headers=admin_headers(),
            json={"reason": "full_refund"},
        )
        assert resp.status_code == 200
        payment = resp.json()
        assert payment["status"] == "refunded"
        assert payment["refundId"] is not None
        assert payment["amount"] == 5000

        # Order 2: partial refund
        key2 = f"cust_{uuid.uuid4().hex[:8]}"
        addr2 = setup_customer(key2)
        requests.post(url("/store/carts"), headers=customer_headers(key2), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key2),
            json={"variantId": variant_id, "quantity": 1},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key2),
            json={"shippingAddressId": addr2},
        )
        order2_id = resp.json()["id"]

        # Partial refund of 1000
        resp = requests.post(
            url(f"/admin/orders/{order2_id}/refund"),
            headers=admin_headers(),
            json={"amount": 1000, "reason": "partial"},
        )
        assert resp.status_code == 200
        payment2 = resp.json()
        assert payment2["refundId"] is not None


# ============================================================
# Test 10: Product Lifecycle with Category and Collection
# ============================================================
class TestProductLifecycleWorkflow:
    def test_product_with_category_and_collection_filterable(self):
        """
        Pattern 2+3: Create products with categories/collections, verify
        filtering works end-to-end from admin creation to store retrieval.
        """
        # Create category and collection
        resp = requests.post(
            url("/admin/categories"),
            headers=admin_headers(),
            json={"name": "Electronics", "handle": unique("elec-")},
        )
        cat_id = resp.json()["id"]

        resp = requests.post(
            url("/admin/collections"),
            headers=admin_headers(),
            json={"title": "Winter Sale", "handle": unique("winter-")},
        )
        col_id = resp.json()["id"]

        # Create product in both category and collection
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={
                "title": "Smart Watch",
                "handle": unique("sw-"),
                "status": "published",
                "categoryId": cat_id,
                "collectionId": col_id,
            },
        )
        assert resp.status_code == 201
        product = resp.json()
        assert product["categoryId"] == cat_id
        assert product["collectionId"] == col_id

        # Create another product NOT in this category
        requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "Other Item", "handle": unique("other-"), "status": "published"},
        )

        # Filter by category → only smart watch
        resp = requests.get(
            url(f"/store/products?categoryId={cat_id}"),
            headers=customer_headers(f"cust_{uuid.uuid4().hex[:8]}"),
        )
        products = resp.json()["products"]
        assert len(products) >= 1
        for p in products:
            assert p["categoryId"] == cat_id

        # Filter by collection
        resp = requests.get(
            url(f"/store/products?collectionId={col_id}"),
            headers=customer_headers(f"cust_{uuid.uuid4().hex[:8]}"),
        )
        products = resp.json()["products"]
        assert len(products) >= 1
        for p in products:
            assert p["collectionId"] == col_id


# ============================================================
# Test 11: Fixed Discount Workflow
# ============================================================
class TestFixedDiscountWorkflow:
    def test_fixed_discount_deducted_correctly_from_order(self):
        """
        Pattern 5: Fixed discount of 2000 on subtotal of 8000:
        - discount=2000
        - tax on (8000-2000)=6000
        - total reflects correct amount charged
        """
        key = f"cust_{uuid.uuid4().hex[:8]}"
        addr_id = setup_customer(key)

        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("FixR-"), "currency": "usd", "taxRate": 0.1},
        )
        region_id = resp.json()["id"]

        code = unique("FIX2K")
        requests.post(
            url("/admin/discounts"),
            headers=admin_headers(),
            json={"code": code, "type": "fixed", "value": 2000},
        )

        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "FixDiscProd", "handle": unique("fd-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("FD-"), "price": 4000, "inventoryQuantity": 50},
        )
        variant_id = resp.json()["id"]

        # qty=2 → subtotal=8000
        requests.post(url("/store/carts"), headers=customer_headers(key), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key),
            json={"variantId": variant_id, "quantity": 2},
        )
        requests.post(
            url("/store/carts/mine/discount"),
            headers=customer_headers(key),
            json={"code": code},
        )

        resp = requests.get(url("/store/carts/mine"), headers=customer_headers(key))
        cart = resp.json()
        # subtotal=8000, discount=2000, tax=(8000-2000)*0.1=600, total=8000-2000+600=6600
        assert cart["subtotal"] == 8000
        assert cart["discount"] == 2000
        assert cart["tax"] == 600
        assert cart["total"] == 6600

        # Create order and verify totals preserved
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key),
            json={"shippingAddressId": addr_id},
        )
        assert resp.status_code == 201
        order = resp.json()
        assert order["subtotal"] == 8000
        assert order["discount"] == 2000
        assert order["tax"] == 600
        assert order["total"] == 6600


# ============================================================
# Test 12: Customer Data Isolation
# ============================================================
class TestCustomerDataIsolation:
    def test_customers_cannot_access_each_others_carts_and_orders(self):
        """
        Pattern 6: Customer A and B have separate carts and orders.
        Each can only see their own data.
        """
        resp = requests.post(
            url("/admin/regions"),
            headers=admin_headers(),
            json={"name": unique("IsoR-"), "currency": "usd", "taxRate": 0.0},
        )
        region_id = resp.json()["id"]
        resp = requests.post(
            url("/admin/products"),
            headers=admin_headers(),
            json={"title": "IsoProd", "handle": unique("iso-"), "status": "published"},
        )
        prod_id = resp.json()["id"]
        resp = requests.post(
            url(f"/admin/products/{prod_id}/variants"),
            headers=admin_headers(),
            json={"title": "V1", "sku": unique("ISO-"), "price": 1000, "inventoryQuantity": 100},
        )
        variant_id = resp.json()["id"]

        # Customer A
        key_a = f"cust_{uuid.uuid4().hex[:8]}"
        addr_a = setup_customer(key_a)
        requests.post(url("/store/carts"), headers=customer_headers(key_a), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_a),
            json={"variantId": variant_id, "quantity": 2},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key_a),
            json={"shippingAddressId": addr_a},
        )
        order_a_id = resp.json()["id"]

        # Customer B
        key_b = f"cust_{uuid.uuid4().hex[:8]}"
        addr_b = setup_customer(key_b)
        requests.post(url("/store/carts"), headers=customer_headers(key_b), json={"regionId": region_id})
        requests.post(
            url("/store/carts/mine/items"),
            headers=customer_headers(key_b),
            json={"variantId": variant_id, "quantity": 3},
        )
        resp = requests.post(
            url("/store/orders"),
            headers=customer_headers(key_b),
            json={"shippingAddressId": addr_b},
        )
        order_b_id = resp.json()["id"]

        # A's orders don't include B's
        resp = requests.get(url("/store/orders"), headers=customer_headers(key_a))
        a_order_ids = [o["id"] for o in resp.json()["orders"]]
        assert order_a_id in a_order_ids
        assert order_b_id not in a_order_ids

        # B's orders don't include A's
        resp = requests.get(url("/store/orders"), headers=customer_headers(key_b))
        b_order_ids = [o["id"] for o in resp.json()["orders"]]
        assert order_b_id in b_order_ids
        assert order_a_id not in b_order_ids

        # A cannot get B's order directly
        resp = requests.get(url(f"/store/orders/{order_b_id}"), headers=customer_headers(key_a))
        assert resp.status_code == 404, "Customer A should not see B's order"

        # B cannot get A's order directly
        resp = requests.get(url(f"/store/orders/{order_a_id}"), headers=customer_headers(key_b))
        assert resp.status_code == 404, "Customer B should not see A's order"
