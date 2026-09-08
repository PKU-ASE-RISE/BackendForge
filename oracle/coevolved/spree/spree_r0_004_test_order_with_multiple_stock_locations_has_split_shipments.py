import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


ADDRESS = {
    "firstName": "Grace",
    "lastName": "Hopper",
    "address1": "2 Compiler Ave",
    "city": "Arlington",
    "state": "VA",
    "zipCode": "22201",
    "country": "US",
    "phone": "555-0200",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api_request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def create_variant_at_location(admin_token, location_name, price):
    product_response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={
            "name": f"Split Product {uuid.uuid4().hex}",
            "price": price,
            "currency": "USD",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    variant_response = api_request("post",
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers(admin_token),
        json={"sku": f"SPLIT-{uuid.uuid4().hex}", "price": price, "currency": "USD"},
    )
    assert variant_response.status_code == 201, variant_response.text
    variant_id = variant_response.json()["id"]

    location_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin_token),
        json={"name": f"{location_name}-{uuid.uuid4().hex}", "active": True},
    )
    assert location_response.status_code == 201, location_response.text
    location_id = location_response.json()["id"]

    stock_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations/{location_id}/stock-items",
        headers=headers(admin_token),
        json={"variantId": variant_id, "countOnHand": 5, "backorderable": False},
    )
    assert stock_response.status_code == 201, stock_response.text
    return variant_id, location_id


def test_order_with_multiple_stock_locations_has_split_shipments():
    store = f"drpsplit{uuid.uuid4().hex[:8]}"
    admin_token = f"admin_{store}_admin"
    customer_token = f"{store}_customer"

    variant_a, location_a = create_variant_at_location(admin_token, "East", 12.0)
    variant_b, location_b = create_variant_at_location(admin_token, "West", 15.0)
    assert location_a != location_b

    method_response = api_request("post",
        f"{BASE_URL}/api/v1/shipping-methods",
        headers=headers(admin_token),
        json={"name": f"Split Ground {uuid.uuid4().hex}", "cost": 4.0},
    )
    assert method_response.status_code == 201, method_response.text
    shipping_method_id = method_response.json()["id"]

    order_response = api_request("post",
        f"{BASE_URL}/api/v1/orders",
        headers=headers(customer_token),
        json={"email": "split@example.com"},
    )
    assert order_response.status_code == 201, order_response.text
    order_id = order_response.json()["id"]

    for variant_id in (variant_a, variant_b):
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

    shipment_response = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
        headers=headers(customer_token),
        json={"shippingMethodId": shipping_method_id},
    )
    assert shipment_response.status_code == 200, shipment_response.text

    order_after = api_request("get",
        f"{BASE_URL}/api/v1/orders/{order_id}",
        headers=headers(customer_token),
    )
    assert order_after.status_code == 200, order_after.text
    shipments = order_after.json()["shipments"]
    shipment_locations = {shipment.get("stockLocationId") for shipment in shipments}

    assert len(shipments) >= 2
    assert {location_a, location_b}.issubset(shipment_locations)
