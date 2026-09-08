import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


ADDRESS = {
    "firstName": "Ada",
    "lastName": "Lovelace",
    "address1": "1 Engine Way",
    "city": "London",
    "state": "LDN",
    "zipCode": "00001",
    "country": "GB",
    "phone": "555-0100",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api_request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def create_variant_with_stock(admin_token, price=14.0, count=5):
    product_response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={
            "name": f"Foreign Location Product {uuid.uuid4().hex}",
            "price": price,
            "currency": "USD",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    variant_response = api_request("post",
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers(admin_token),
        json={"sku": f"FOREIGN-{uuid.uuid4().hex}", "price": price, "currency": "USD"},
    )
    assert variant_response.status_code == 201, variant_response.text
    variant_id = variant_response.json()["id"]

    location_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin_token),
        json={"name": f"Home Stock {uuid.uuid4().hex}", "active": True},
    )
    assert location_response.status_code == 201, location_response.text
    location_id = location_response.json()["id"]

    stock_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations/{location_id}/stock-items",
        headers=headers(admin_token),
        json={"variantId": variant_id, "countOnHand": count, "backorderable": False},
    )
    assert stock_response.status_code == 201, stock_response.text
    return variant_id


def put_order_in_delivery_state(customer_token, admin_token, variant_id):
    order_response = api_request("post",
        f"{BASE_URL}/api/v1/orders",
        headers=headers(customer_token),
        json={"email": "foreign-location@example.com"},
    )
    assert order_response.status_code == 201, order_response.text
    order_id = order_response.json()["id"]

    line_response = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(customer_token),
        json={"variantId": variant_id, "quantity": 1},
    )
    assert line_response.status_code == 201, line_response.text

    first_next = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/next",
        headers=headers(customer_token),
        json={},
    )
    assert first_next.status_code == 200, first_next.text
    assert first_next.json()["state"] == "address"

    address_response = api_request("put",
        f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
        headers=headers(customer_token),
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
    )
    assert address_response.status_code == 200, address_response.text

    second_next = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/next",
        headers=headers(customer_token),
        json={},
    )
    assert second_next.status_code == 200, second_next.text
    assert second_next.json()["state"] == "delivery"

    method_response = api_request("post",
        f"{BASE_URL}/api/v1/shipping-methods",
        headers=headers(admin_token),
        json={"name": f"Foreign Guard {uuid.uuid4().hex}", "cost": 6.0},
    )
    assert method_response.status_code == 201, method_response.text
    return order_id, method_response.json()["id"]


def test_shipment_rejects_foreign_stock_location():
    store_a = f"drpsa{uuid.uuid4().hex[:8]}"
    store_b = f"drpsb{uuid.uuid4().hex[:8]}"
    admin_a = f"admin_{store_a}_admin"
    admin_b = f"admin_{store_b}_admin"
    customer_a = f"{store_a}_customer"

    variant_id = create_variant_with_stock(admin_a)
    order_id, shipping_method_id = put_order_in_delivery_state(customer_a, admin_a, variant_id)

    foreign_location_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin_b),
        json={"name": f"Foreign Stock {uuid.uuid4().hex}", "active": True},
    )
    assert foreign_location_response.status_code == 201, foreign_location_response.text
    foreign_location_id = foreign_location_response.json()["id"]

    shipment_response = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
        headers=headers(customer_a),
        json={
            "shippingMethodId": shipping_method_id,
            "stockLocationId": foreign_location_id,
        },
    )

    assert shipment_response.status_code in (404, 422), shipment_response.text

    order_after = api_request("get",
        f"{BASE_URL}/api/v1/orders/{order_id}",
        headers=headers(customer_a),
    )
    assert order_after.status_code == 200, order_after.text
    assert all(
        shipment.get("stockLocationId") != foreign_location_id
        for shipment in order_after.json()["shipments"]
    )
