"""Correctness tests for Spree e-commerce API."""
import os
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def api_request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)

# Token conventions:
# Admin token: admin_{store_id}_{anything} -> admin of store {store_id}
# Customer token: {store_id}_{customer_id} -> customer of store {store_id}

ADMIN_TOKEN_STORE1 = "admin_store1_user1"
ADMIN_TOKEN_STORE2 = "admin_store2_user1"
CUSTOMER_TOKEN_STORE1 = "store1_customer1"
CUSTOMER_TOKEN_STORE1_B = "store1_customer2"
CUSTOMER_TOKEN_STORE2 = "store2_customer1"


def admin_headers(token=ADMIN_TOKEN_STORE1):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def customer_headers(token=CUSTOMER_TOKEN_STORE1):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


# ============ AUTH TESTS ============

class TestAuth:
    def test_missing_token_returns_401(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/products")
        assert resp.status_code == 401

    def test_empty_token_returns_401(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/products", headers={"X-Store-Token": ""})
        assert resp.status_code == 401

    def test_valid_token_returns_200(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/products", headers=customer_headers())
        assert resp.status_code == 200

    def test_customer_cannot_create_product(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=customer_headers(),
            json={"name": "Test", "price": 10.0, "currency": "USD"}
        )
        assert resp.status_code == 403


# ============ STORE TESTS ============

class TestStore:
    def test_get_store_info(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/store", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    def test_update_store(self):
        resp = api_request("put",
            f"{BASE_URL}/api/v1/store",
            headers=admin_headers(),
            json={"name": "My Spree Store", "defaultCurrency": "USD"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Spree Store"

    def test_customer_cannot_update_store(self):
        resp = api_request("put",
            f"{BASE_URL}/api/v1/store",
            headers=customer_headers(),
            json={"name": "Hacked"}
        )
        assert resp.status_code == 403


# ============ OPTION TYPES TESTS ============

class TestOptionTypes:
    def test_create_option_type(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/option-types",
            headers=admin_headers(),
            json={
                "name": "color",
                "presentation": "Color",
                "optionValues": [
                    {"name": "red", "presentation": "Red"},
                    {"name": "blue", "presentation": "Blue"}
                ]
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "color"
        assert len(data["optionValues"]) == 2

    def test_list_option_types(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/option-types", headers=admin_headers())
        assert resp.status_code == 200

    def test_get_option_type(self):
        # Create first
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/option-types",
            headers=admin_headers(),
            json={"name": "size", "presentation": "Size", "optionValues": [{"name": "s", "presentation": "S"}]}
        )
        ot_id = create_resp.json()["id"]
        resp = api_request("get", f"{BASE_URL}/api/v1/option-types/{ot_id}", headers=admin_headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "size"

    def test_delete_option_type(self):
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/option-types",
            headers=admin_headers(),
            json={"name": "material", "presentation": "Material"}
        )
        ot_id = create_resp.json()["id"]
        resp = api_request("delete", f"{BASE_URL}/api/v1/option-types/{ot_id}", headers=admin_headers())
        assert resp.status_code == 204
        resp = api_request("get", f"{BASE_URL}/api/v1/option-types/{ot_id}", headers=admin_headers())
        assert resp.status_code == 404


# ============ PRODUCT TESTS ============

class TestProducts:
    def test_create_product(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={
                "name": "T-Shirt",
                "description": "A nice t-shirt",
                "price": 29.99,
                "currency": "USD",
                "available": True,
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "T-Shirt"
        assert data["price"] == 29.99
        assert "id" in data

    def test_list_products(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/products", headers=customer_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data

    def test_get_product(self):
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Pants", "price": 49.99, "currency": "USD"}
        )
        pid = create_resp.json()["id"]
        resp = api_request("get", f"{BASE_URL}/api/v1/products/{pid}", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Pants"

    def test_update_product(self):
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Jacket", "price": 99.99, "currency": "USD"}
        )
        pid = create_resp.json()["id"]
        resp = api_request("put",
            f"{BASE_URL}/api/v1/products/{pid}",
            headers=admin_headers(),
            json={"name": "Winter Jacket", "price": 119.99}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Winter Jacket"

    def test_delete_product(self):
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Delete Me", "price": 5.0, "currency": "USD"}
        )
        pid = create_resp.json()["id"]
        resp = api_request("delete", f"{BASE_URL}/api/v1/products/{pid}", headers=admin_headers())
        assert resp.status_code == 204
        resp = api_request("get", f"{BASE_URL}/api/v1/products/{pid}", headers=admin_headers())
        assert resp.status_code == 404

    def test_product_not_found(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/products/nonexistent", headers=customer_headers())
        assert resp.status_code == 404

    def test_product_with_properties(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={
                "name": "Silk Shirt",
                "price": 79.99,
                "currency": "USD",
                "properties": [
                    {"name": "material", "value": "silk"},
                    {"name": "brand", "value": "Luxury Co"}
                ]
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["properties"]) == 2


# ============ VARIANT TESTS ============

class TestVariants:
    def _create_product(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Variant Product", "price": 30.0, "currency": "USD"}
        )
        return resp.json()["id"]

    def test_create_variant(self):
        pid = self._create_product()
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "VP-RED-L", "price": 32.0, "optionValues": []}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sku"] == "VP-RED-L"
        assert data["price"] == 32.0

    def test_list_variants(self):
        pid = self._create_product()
        api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "VP-001", "price": 30.0}
        )
        resp = api_request("get", f"{BASE_URL}/api/v1/products/{pid}/variants", headers=customer_headers())
        assert resp.status_code == 200

    def test_update_variant(self):
        pid = self._create_product()
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "VP-UPD", "price": 30.0}
        )
        vid = create_resp.json()["id"]
        resp = api_request("put",
            f"{BASE_URL}/api/v1/products/{pid}/variants/{vid}",
            headers=admin_headers(),
            json={"price": 35.0}
        )
        assert resp.status_code == 200
        assert resp.json()["price"] == 35.0

    def test_delete_variant(self):
        pid = self._create_product()
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "VP-DEL", "price": 30.0}
        )
        vid = create_resp.json()["id"]
        resp = api_request("delete", f"{BASE_URL}/api/v1/products/{pid}/variants/{vid}", headers=admin_headers())
        assert resp.status_code == 204


# ============ TAXON TESTS ============

class TestTaxons:
    def test_create_taxon(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Clothing", "permalink": "clothing"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Clothing"
        assert data["parentId"] is None

    def test_create_child_taxon(self):
        parent_resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Electronics", "permalink": "electronics"}
        )
        parent_id = parent_resp.json()["id"]
        child_resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Phones", "permalink": "electronics/phones", "parentId": parent_id}
        )
        assert child_resp.status_code == 201
        assert child_resp.json()["parentId"] == parent_id

    def test_get_taxon_with_children(self):
        parent_resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Home", "permalink": "home"}
        )
        parent_id = parent_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Kitchen", "permalink": "home/kitchen", "parentId": parent_id}
        )
        resp = api_request("get", f"{BASE_URL}/api/v1/taxons/{parent_id}", headers=customer_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["children"]) >= 1

    def test_products_in_child_taxon_findable_via_parent(self):
        # Create parent taxon
        parent_resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Apparel", "permalink": "apparel"}
        )
        parent_id = parent_resp.json()["id"]

        # Create child taxon
        child_resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Men", "permalink": "apparel/men", "parentId": parent_id}
        )
        child_id = child_resp.json()["id"]

        # Create product in child taxon
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Men Shirt", "price": 25.0, "currency": "USD", "taxonIds": [child_id]}
        )
        assert prod_resp.status_code == 201

        # Query products by parent taxon should include child's products
        resp = api_request("get",
            f"{BASE_URL}/api/v1/products",
            headers=customer_headers(),
            params={"taxonId": parent_id}
        )
        assert resp.status_code == 200
        products = resp.json()["data"]
        product_names = [p["name"] for p in products]
        assert "Men Shirt" in product_names

    def test_delete_taxon(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/taxons",
            headers=admin_headers(),
            json={"name": "Temp", "permalink": "temp"}
        )
        tid = resp.json()["id"]
        del_resp = api_request("delete", f"{BASE_URL}/api/v1/taxons/{tid}", headers=admin_headers())
        assert del_resp.status_code == 204


# ============ STOCK TESTS ============

class TestStock:
    def _create_product_and_variant(self):
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Stock Test Product", "price": 20.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "STP-001", "price": 20.0}
        )
        vid = var_resp.json()["id"]
        return pid, vid

    def _create_stock_location(self, name="Warehouse A"):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": name, "address1": "123 Main St", "city": "NYC", "state": "NY", "country": "US", "active": True}
        )
        return resp.json()["id"]

    def test_create_stock_location(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "Main Warehouse", "active": True}
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Main Warehouse"

    def test_create_stock_item(self):
        _, vid = self._create_product_and_variant()
        loc_id = self._create_stock_location("Stock Item Warehouse")
        resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 50, "backorderable": False}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["countOnHand"] == 50
        assert data["backorderable"] is False

    def test_update_stock_item(self):
        _, vid = self._create_product_and_variant()
        loc_id = self._create_stock_location("Update Stock Warehouse")
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 10, "backorderable": False}
        )
        si_id = create_resp.json()["id"]
        resp = api_request("put",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items/{si_id}",
            headers=admin_headers(),
            json={"countOnHand": 25, "backorderable": True}
        )
        assert resp.status_code == 200
        assert resp.json()["countOnHand"] == 25
        assert resp.json()["backorderable"] is True


# ============ SHIPPING METHOD TESTS ============

class TestShippingMethods:
    def test_create_shipping_method(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "Standard Shipping", "cost": 5.99}
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Standard Shipping"
        assert resp.json()["cost"] == 5.99

    def test_list_shipping_methods(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/shipping-methods", headers=customer_headers())
        assert resp.status_code == 200

    def test_delete_shipping_method(self):
        create_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "Express", "cost": 15.99}
        )
        sm_id = create_resp.json()["id"]
        resp = api_request("delete", f"{BASE_URL}/api/v1/shipping-methods/{sm_id}", headers=admin_headers())
        assert resp.status_code == 204


# ============ PAYMENT METHOD TESTS ============

class TestPaymentMethods:
    def test_create_payment_method(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/payment-methods",
            headers=admin_headers(),
            json={"name": "Credit Card", "type": "gateway", "active": True}
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Credit Card"

    def test_list_payment_methods(self):
        resp = api_request("get", f"{BASE_URL}/api/v1/payment-methods", headers=customer_headers())
        assert resp.status_code == 200


# ============ ORDER & CHECKOUT TESTS ============

class TestOrders:
    def _setup_product_with_stock(self):
        """Create a product, variant, stock location, and stock item."""
        # Product
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Order Test Product", "price": 50.0, "currency": "USD", "available": True}
        )
        pid = prod_resp.json()["id"]
        # Variant
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "OTP-001", "price": 50.0}
        )
        vid = var_resp.json()["id"]
        # Stock location
        loc_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "Order Warehouse", "active": True}
        )
        loc_id = loc_resp.json()["id"]
        # Stock item
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 100, "backorderable": False}
        )
        # Shipping method
        sm_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "Order Test Shipping", "cost": 10.0}
        )
        sm_id = sm_resp.json()["id"]
        # Payment method
        pm_resp = api_request("post",
            f"{BASE_URL}/api/v1/payment-methods",
            headers=admin_headers(),
            json={"name": "Order Test Payment", "type": "gateway", "active": True}
        )
        pm_id = pm_resp.json()["id"]
        return vid, loc_id, sm_id, pm_id

    def test_create_order(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={"email": "test@example.com"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["state"] == "cart"
        assert "id" in data

    def test_add_line_item(self):
        vid, _, _, _ = self._setup_product_with_stock()
        # Create order
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        # Add line item
        resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 2}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["variantId"] == vid
        assert data["quantity"] == 2

    def test_update_line_item_quantity(self):
        vid, _, _, _ = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        li_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        li_id = li_resp.json()["id"]
        resp = api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items/{li_id}",
            headers=customer_headers(),
            json={"quantity": 3}
        )
        assert resp.status_code == 200
        assert resp.json()["quantity"] == 3

    def test_remove_line_item(self):
        vid, _, _, _ = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        li_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        li_id = li_resp.json()["id"]
        resp = api_request("delete",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items/{li_id}",
            headers=customer_headers()
        )
        assert resp.status_code == 204

    def test_full_checkout_flow(self):
        """Test the complete checkout: cart → address → delivery → payment → confirm → complete."""
        vid, loc_id, sm_id, pm_id = self._setup_product_with_stock()

        # Create order
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={"email": "checkout@example.com"}
        )
        order_id = order_resp.json()["id"]
        assert order_resp.json()["state"] == "cart"

        # Add line item
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 2}
        )

        # Advance to address
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "address"

        # Set addresses
        address = {
            "firstName": "John",
            "lastName": "Doe",
            "address1": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zipCode": "10001",
            "country": "US",
            "phone": "555-1234"
        }
        addr_resp = api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        assert addr_resp.status_code == 200

        # Advance to delivery
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "delivery"

        # Set shipment
        ship_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        assert ship_resp.status_code == 200

        # Advance to payment
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "payment"

        # Get order to know total
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=customer_headers()).json()
        total = order_detail["total"]

        # Create payment
        pay_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": total, "paymentMethodId": pm_id}
        )
        assert pay_resp.status_code == 201
        assert pay_resp.json()["state"] == "authorized"

        # Advance to confirm
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "confirm"

        # Advance to complete
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "complete"

    def test_cannot_advance_without_line_items(self):
        """Cart with no items cannot advance."""
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 422

    def test_cannot_advance_without_address(self):
        """Cannot go from address to delivery without setting addresses."""
        vid, _, _, _ = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        # Advance to address
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        # Try to advance without setting address
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 422

    def test_cannot_advance_without_shipment(self):
        """Cannot go from delivery to payment without selecting shipping."""
        vid, loc_id, sm_id, _ = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        # Now in delivery state, try to advance without shipment
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 422

    def test_cannot_advance_without_payment(self):
        """Cannot go from payment to confirm without authorizing payment."""
        vid, loc_id, sm_id, _ = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        # Now in payment state, try to advance without payment
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 422

    def test_cancel_order(self):
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/cancel", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "cancelled"

    def test_cannot_cancel_complete_order(self):
        """Completed orders cannot be cancelled."""
        vid, loc_id, sm_id, pm_id = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={"email": "complete@example.com"}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=customer_headers()).json()
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": order_detail["total"], "paymentMethodId": pm_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        # Now complete, try to cancel
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/cancel", headers=customer_headers())
        assert resp.status_code == 422

    def test_order_total_calculation(self):
        """Order total = item_total + shipment_total + adjustment_total."""
        vid, loc_id, sm_id, pm_id = self._setup_product_with_stock()
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        # Add 2 items at 50.0 each = 100.0 item total
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 2}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        # Shipping cost is 10.0
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=customer_headers()).json()
        assert order_detail["itemTotal"] == 100.0
        assert order_detail["shipmentTotal"] == 10.0
        assert order_detail["total"] == 110.0  # 100 + 10 + 0 adjustments


# ============ STOCK AVAILABILITY TESTS ============

class TestStockAvailability:
    def _setup(self):
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Limited Item", "price": 10.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "LTD-001", "price": 10.0}
        )
        vid = var_resp.json()["id"]
        loc_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "Limited Warehouse", "active": True}
        )
        loc_id = loc_resp.json()["id"]
        return pid, vid, loc_id

    def test_insufficient_stock_rejects_add_to_cart(self):
        """Cannot add to cart if stock is insufficient and not backorderable."""
        _, vid, loc_id = self._setup()
        # Set stock to 2
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 2, "backorderable": False}
        )
        # Create order
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        # Try to add 5 items (only 2 in stock)
        resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 5}
        )
        assert resp.status_code == 422

    def test_backorderable_allows_oversell(self):
        """Backorderable items can be added even with 0 stock."""
        _, vid, loc_id = self._setup()
        # Set stock to 0 but backorderable
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 0, "backorderable": True}
        )
        # Create order
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        # Add 3 items (stock is 0 but backorderable)
        resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 3}
        )
        assert resp.status_code == 201

    def test_stock_decrements_on_complete(self):
        """Completing an order decrements stock count_on_hand."""
        _, vid, loc_id = self._setup()
        # Stock item
        si_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 20, "backorderable": False}
        )
        si_id = si_resp.json()["id"]
        # Shipping & payment methods
        sm_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "Stock Test Ship", "cost": 5.0}
        )
        sm_id = sm_resp.json()["id"]
        pm_resp = api_request("post",
            f"{BASE_URL}/api/v1/payment-methods",
            headers=admin_headers(),
            json={"name": "Stock Test Pay", "type": "gateway", "active": True}
        )
        pm_id = pm_resp.json()["id"]

        # Complete checkout
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={"email": "stock@test.com"}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 3}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=customer_headers()).json()
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": order_detail["total"], "paymentMethodId": pm_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())

        # Check stock was decremented
        stock_resp = api_request("get",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers()
        )
        stock_items = stock_resp.json()
        # Find our stock item
        if isinstance(stock_items, dict) and "data" in stock_items:
            stock_items = stock_items["data"]
        our_item = next((si for si in stock_items if si["id"] == si_id), None)
        assert our_item is not None
        assert our_item["countOnHand"] == 17  # 20 - 3


# ============ PROMOTION TESTS ============

class TestPromotions:
    """Each promotion test uses a unique store to avoid cross-test interference."""

    def _setup_for_promotion(self, store_suffix):
        """Setup a complete checkout-ready environment in an isolated store."""
        adm = {"X-Store-Token": f"admin_{store_suffix}_u1", "Content-Type": "application/json"}
        cust = {"X-Store-Token": f"{store_suffix}_cust1", "Content-Type": "application/json"}

        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=adm,
            json={"name": "Promo Product", "price": 100.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=adm,
            json={"sku": "PROMO-001", "price": 100.0}
        )
        vid = var_resp.json()["id"]
        loc_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=adm,
            json={"name": "Promo Warehouse", "active": True}
        )
        loc_id = loc_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=adm,
            json={"variantId": vid, "countOnHand": 100, "backorderable": False}
        )
        sm_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=adm,
            json={"name": "Promo Ship", "cost": 10.0}
        )
        sm_id = sm_resp.json()["id"]
        pm_resp = api_request("post",
            f"{BASE_URL}/api/v1/payment-methods",
            headers=adm,
            json={"name": "Promo Pay", "type": "gateway", "active": True}
        )
        pm_id = pm_resp.json()["id"]
        return pid, vid, loc_id, sm_id, pm_id, adm, cust

    def test_create_promotion(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/promotions",
            headers=admin_headers(),
            json={
                "name": "10% Off Over $50",
                "description": "10% discount for orders over $50",
                "active": True,
                "rules": [{"type": "minOrderAmount", "value": 50.0}],
                "actions": [{"type": "percentOff", "value": 10.0}]
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "10% Off Over $50"
        assert len(data["rules"]) == 1
        assert len(data["actions"]) == 1

    def test_promotion_applied_when_rules_met(self):
        """Promotion applies when minimum order amount is met."""
        pid, vid, loc_id, sm_id, pm_id, adm, cust = self._setup_for_promotion("promostore1")

        # Create promotion: 20% off for orders >= $80
        api_request("post",
            f"{BASE_URL}/api/v1/promotions",
            headers=adm,
            json={
                "name": "20% Off 80+",
                "active": True,
                "rules": [{"type": "minOrderAmount", "value": 80.0}],
                "actions": [{"type": "percentOff", "value": 20.0}]
            }
        )

        # Create order with item_total = 100 (1 x $100)
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=cust,
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=cust,
            json={"variantId": vid, "quantity": 1}
        )
        # Advance through checkout
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=cust,
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=cust,
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        # Advance to payment - this is when promotions are evaluated
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)

        # Check order has adjustment
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=cust).json()
        # 20% off $100 = -$20 adjustment
        assert order_detail["adjustmentTotal"] == -20.0
        # Total: 100 (items) + 10 (shipping) - 20 (promo) = 90
        assert order_detail["total"] == 90.0

    def test_promotion_not_applied_when_rules_not_met(self):
        """Promotion does NOT apply when min order amount is not met."""
        pid, vid, loc_id, sm_id, pm_id, adm, cust = self._setup_for_promotion("promostore2")

        # Create promotion: $50 off for orders >= $500
        api_request("post",
            f"{BASE_URL}/api/v1/promotions",
            headers=adm,
            json={
                "name": "Big Spender",
                "active": True,
                "rules": [{"type": "minOrderAmount", "value": 500.0}],
                "actions": [{"type": "flatOff", "value": 50.0}]
            }
        )

        # Create order with item_total = 100 (not >= 500)
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=cust,
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=cust,
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=cust,
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=cust,
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)

        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=cust).json()
        # No promotion applied
        assert order_detail["adjustmentTotal"] == 0.0
        assert order_detail["total"] == 110.0  # 100 + 10 shipping

    def test_free_shipping_promotion(self):
        """Free shipping promotion zeroes out shipping cost."""
        pid, vid, loc_id, sm_id, pm_id, adm, cust = self._setup_for_promotion("promostore3")

        # Create free shipping promotion for orders >= $50
        api_request("post",
            f"{BASE_URL}/api/v1/promotions",
            headers=adm,
            json={
                "name": "Free Shipping",
                "active": True,
                "rules": [{"type": "minOrderAmount", "value": 50.0}],
                "actions": [{"type": "freeShipping", "value": 0}]
            }
        )

        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=cust,
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=cust,
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=cust,
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=cust,
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=cust)

        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=cust).json()
        # Free shipping means shipment cost adjustment = -10
        # Total = 100 (items) + 10 (shipping) - 10 (free shipping) = 100
        assert order_detail["total"] == 100.0

    def test_first_order_promotion(self):
        """First order promotion only applies to customer's first order."""
        pid, vid, loc_id, sm_id, pm_id, adm, cust = self._setup_for_promotion("promostore4")

        # Create first-order promotion
        api_request("post",
            f"{BASE_URL}/api/v1/promotions",
            headers=adm,
            json={
                "name": "Welcome Discount",
                "active": True,
                "rules": [{"type": "firstOrder"}],
                "actions": [{"type": "flatOff", "value": 15.0}]
            }
        )

        # Use a fresh customer token (same store as the promo)
        fresh_customer = "promostore4_freshcust1"
        fresh_headers = {"X-Store-Token": fresh_customer, "Content-Type": "application/json"}

        # First order should get promo
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=fresh_headers,
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=fresh_headers,
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=fresh_headers)
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=fresh_headers,
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=fresh_headers)
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=fresh_headers,
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=fresh_headers)
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=fresh_headers).json()
        # $15 off
        assert order_detail["adjustmentTotal"] == -15.0

        # Complete first order
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=fresh_headers,
            json={"amount": order_detail["total"], "paymentMethodId": pm_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=fresh_headers)
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=fresh_headers)

        # Second order should NOT get the promo
        order_resp2 = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=fresh_headers,
            json={}
        )
        order_id2 = order_resp2.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id2}/line-items",
            headers=fresh_headers,
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id2}/next", headers=fresh_headers)
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id2}/addresses",
            headers=fresh_headers,
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id2}/next", headers=fresh_headers)
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id2}/shipments",
            headers=fresh_headers,
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id2}/next", headers=fresh_headers)
        order_detail2 = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id2}", headers=fresh_headers).json()
        assert order_detail2["adjustmentTotal"] == 0.0


# ============ MULTI-PAYMENT TESTS ============

class TestMultiPayment:
    def _setup_order_in_payment_state(self):
        """Create order and advance to payment state."""
        # Product + variant + stock
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Multi-Pay Product", "price": 200.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "MP-001", "price": 200.0}
        )
        vid = var_resp.json()["id"]
        loc_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "Multi-Pay Warehouse", "active": True}
        )
        loc_id = loc_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid, "countOnHand": 50, "backorderable": False}
        )
        sm_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "MP Shipping", "cost": 10.0}
        )
        sm_id = sm_resp.json()["id"]
        pm_resp = api_request("post",
            f"{BASE_URL}/api/v1/payment-methods",
            headers=admin_headers(),
            json={"name": "MP Payment", "type": "gateway", "active": True}
        )
        pm_id = pm_resp.json()["id"]

        # Create order
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid, "quantity": 1}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc_id}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        return order_id, pm_id

    def test_partial_payments(self):
        """Multiple payments can cover the order total."""
        order_id, pm_id = self._setup_order_in_payment_state()
        order_detail = api_request("get", f"{BASE_URL}/api/v1/orders/{order_id}", headers=customer_headers()).json()
        total = order_detail["total"]  # Should be 210.0

        # First partial payment
        pay1_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": 100.0, "paymentMethodId": pm_id}
        )
        assert pay1_resp.status_code == 201
        assert pay1_resp.json()["state"] == "authorized"

        # Second payment for remainder
        pay2_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": total - 100.0, "paymentMethodId": pm_id}
        )
        assert pay2_resp.status_code == 201
        assert pay2_resp.json()["state"] == "authorized"

        # Should be able to advance now
        resp = api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        assert resp.status_code == 200
        assert resp.json()["state"] == "confirm"

    def test_void_payment(self):
        """Can void an authorized payment."""
        order_id, pm_id = self._setup_order_in_payment_state()
        pay_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments",
            headers=customer_headers(),
            json={"amount": 50.0, "paymentMethodId": pm_id}
        )
        pay_id = pay_resp.json()["id"]
        void_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/payments/{pay_id}/void",
            headers=customer_headers()
        )
        assert void_resp.status_code == 200
        assert void_resp.json()["state"] == "voided"


# ============ WISHLIST TESTS ============

class TestWishlists:
    def _create_variant(self):
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Wishlist Product", "price": 25.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "WL-001", "price": 25.0}
        )
        return var_resp.json()["id"]

    def test_create_wishlist(self):
        resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "My Favorites", "isDefault": True}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Favorites"
        assert data["isDefault"] is True

    def test_add_item_to_wishlist(self):
        vid = self._create_variant()
        wl_resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "Gift Ideas"}
        )
        wl_id = wl_resp.json()["id"]
        resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists/{wl_id}/items",
            headers=customer_headers(),
            json={"variantId": vid}
        )
        assert resp.status_code == 201
        assert resp.json()["variantId"] == vid

    def test_remove_item_from_wishlist(self):
        vid = self._create_variant()
        wl_resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "Remove Test"}
        )
        wl_id = wl_resp.json()["id"]
        item_resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists/{wl_id}/items",
            headers=customer_headers(),
            json={"variantId": vid}
        )
        item_id = item_resp.json()["id"]
        resp = api_request("delete",
            f"{BASE_URL}/api/v1/wishlists/{wl_id}/items/{item_id}",
            headers=customer_headers()
        )
        assert resp.status_code == 204

    def test_get_wishlist_with_items(self):
        vid = self._create_variant()
        wl_resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "Full WL"}
        )
        wl_id = wl_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/wishlists/{wl_id}/items",
            headers=customer_headers(),
            json={"variantId": vid}
        )
        resp = api_request("get", f"{BASE_URL}/api/v1/wishlists/{wl_id}", headers=customer_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_delete_wishlist(self):
        wl_resp = api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "To Delete"}
        )
        wl_id = wl_resp.json()["id"]
        resp = api_request("delete", f"{BASE_URL}/api/v1/wishlists/{wl_id}", headers=customer_headers())
        assert resp.status_code == 204
        resp = api_request("get", f"{BASE_URL}/api/v1/wishlists/{wl_id}", headers=customer_headers())
        assert resp.status_code == 404

    def test_list_wishlists(self):
        api_request("post",
            f"{BASE_URL}/api/v1/wishlists",
            headers=customer_headers(),
            json={"name": "List WL Test"}
        )
        resp = api_request("get", f"{BASE_URL}/api/v1/wishlists", headers=customer_headers())
        assert resp.status_code == 200


# ============ STORE ISOLATION TESTS ============

class TestStoreIsolation:
    def test_store_a_admin_cannot_see_store_b_products(self):
        """Products created in store 2 are not visible from store 1."""
        # Create product in store 2
        resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(ADMIN_TOKEN_STORE2),
            json={"name": "Store 2 Only Product", "price": 15.0, "currency": "EUR"}
        )
        assert resp.status_code == 201
        product_id = resp.json()["id"]

        # Try to access from store 1
        resp = api_request("get",
            f"{BASE_URL}/api/v1/products/{product_id}",
            headers=admin_headers(ADMIN_TOKEN_STORE1)
        )
        assert resp.status_code == 404

    def test_store_isolation_in_listing(self):
        """Product listing only shows products from the token's store."""
        # Create product in store 2
        api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(ADMIN_TOKEN_STORE2),
            json={"name": "Isolated Product XYZ", "price": 30.0, "currency": "EUR"}
        )

        # List from store 1 should not contain it
        resp = api_request("get", f"{BASE_URL}/api/v1/products", headers=admin_headers(ADMIN_TOKEN_STORE1))
        assert resp.status_code == 200
        products = resp.json()["data"]
        names = [p["name"] for p in products]
        assert "Isolated Product XYZ" not in names

    def test_customer_store2_cannot_see_store1_orders(self):
        """Customer from store 2 cannot see store 1 orders."""
        # Create order in store 1
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(CUSTOMER_TOKEN_STORE1),
            json={}
        )
        order_id = order_resp.json()["id"]

        # Try to access from store 2
        resp = api_request("get",
            f"{BASE_URL}/api/v1/orders/{order_id}",
            headers=customer_headers(CUSTOMER_TOKEN_STORE2)
        )
        assert resp.status_code == 404


# ============ SPLIT SHIPMENT TESTS ============

class TestSplitShipments:
    def test_multiple_shipments_from_different_locations(self):
        """Items from different stock locations result in separate shipments."""
        # Create 2 variants
        prod_resp = api_request("post",
            f"{BASE_URL}/api/v1/products",
            headers=admin_headers(),
            json={"name": "Split Ship Product", "price": 40.0, "currency": "USD"}
        )
        pid = prod_resp.json()["id"]
        var1_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "SS-001", "price": 40.0}
        )
        vid1 = var1_resp.json()["id"]
        var2_resp = api_request("post",
            f"{BASE_URL}/api/v1/products/{pid}/variants",
            headers=admin_headers(),
            json={"sku": "SS-002", "price": 60.0}
        )
        vid2 = var2_resp.json()["id"]

        # Create 2 stock locations
        loc1_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "East Warehouse", "active": True}
        )
        loc1_id = loc1_resp.json()["id"]
        loc2_resp = api_request("post",
            f"{BASE_URL}/api/v1/stock-locations",
            headers=admin_headers(),
            json={"name": "West Warehouse", "active": True}
        )
        loc2_id = loc2_resp.json()["id"]

        # Stock variant 1 only in location 1
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc1_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid1, "countOnHand": 10, "backorderable": False}
        )
        # Stock variant 2 only in location 2
        api_request("post",
            f"{BASE_URL}/api/v1/stock-locations/{loc2_id}/stock-items",
            headers=admin_headers(),
            json={"variantId": vid2, "countOnHand": 10, "backorderable": False}
        )

        # Shipping method
        sm_resp = api_request("post",
            f"{BASE_URL}/api/v1/shipping-methods",
            headers=admin_headers(),
            json={"name": "Split Shipping", "cost": 5.0}
        )
        sm_id = sm_resp.json()["id"]

        # Create order with both variants
        order_resp = api_request("post",
            f"{BASE_URL}/api/v1/orders",
            headers=customer_headers(),
            json={}
        )
        order_id = order_resp.json()["id"]
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid1, "quantity": 1}
        )
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
            headers=customer_headers(),
            json={"variantId": vid2, "quantity": 1}
        )

        # Advance to delivery
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())
        address = {"firstName": "J", "lastName": "D", "address1": "1 St", "city": "C", "state": "S", "zipCode": "0", "country": "US", "phone": "0"}
        api_request("put",
            f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
            headers=customer_headers(),
            json={"billingAddress": address, "shippingAddress": address}
        )
        api_request("post", f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=customer_headers())

        # Create shipments for both locations
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc1_id}
        )
        api_request("post",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers(),
            json={"shippingMethodId": sm_id, "stockLocationId": loc2_id}
        )

        # Check order has multiple shipments
        shipments_resp = api_request("get",
            f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
            headers=customer_headers()
        )
        assert shipments_resp.status_code == 200
        shipments = shipments_resp.json()
        if isinstance(shipments, dict) and "data" in shipments:
            shipments = shipments["data"]
        assert len(shipments) >= 2
