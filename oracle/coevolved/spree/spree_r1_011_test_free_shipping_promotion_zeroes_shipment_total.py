import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


ADDRESS = {
    "firstName": "Grace",
    "lastName": "Hopper",
    "address1": "10 Compiler Way",
    "city": "Arlington",
    "state": "VA",
    "zipCode": "22201",
    "country": "US",
    "phone": "555-0199",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def test_free_shipping_promotion_zeroes_shipment_total():
    store = f"r1free{uuid.uuid4().hex[:12]}"
    admin = f"admin_{store}_admin"
    customer = f"{store}_customer1"
    product = requests.post(
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin),
        json={"name": f"FreeShip-{uuid.uuid4().hex}", "price": 30.0, "currency": "USD"},
        timeout=10,
    ).json()
    variant = requests.post(
        f"{BASE_URL}/api/v1/products/{product['id']}/variants",
        headers=headers(admin),
        json={"sku": f"FREE-{uuid.uuid4().hex}", "price": 30.0, "currency": "USD"},
        timeout=10,
    ).json()
    location = requests.post(
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin),
        json={"name": f"FreeLoc-{uuid.uuid4().hex}", "active": True},
        timeout=10,
    ).json()
    requests.post(
        f"{BASE_URL}/api/v1/stock-locations/{location['id']}/stock-items",
        headers=headers(admin),
        json={"variantId": variant["id"], "countOnHand": 3, "backorderable": False},
        timeout=10,
    )
    shipping_method = requests.post(
        f"{BASE_URL}/api/v1/shipping-methods",
        headers=headers(admin),
        json={"name": f"FreeShipMethod-{uuid.uuid4().hex}", "cost": 12.5},
        timeout=10,
    ).json()
    promotion_response = requests.post(
        f"{BASE_URL}/api/v1/promotions",
        headers=headers(admin),
        json={
            "name": f"FreeShipping-{uuid.uuid4().hex}",
            "rules": [{"type": "minOrderAmount", "value": 1}],
            "actions": [{"type": "freeShipping", "value": 0}],
            "active": True,
        },
        timeout=10,
    )
    assert promotion_response.status_code == 201
    order = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers(customer), json={}, timeout=10).json()
    order_id = order["id"]
    assert requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(customer),
        json={"variantId": variant["id"], "quantity": 1},
        timeout=10,
    ).status_code == 201
    assert requests.post(f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=headers(customer), json={}, timeout=10).status_code == 200
    assert requests.put(
        f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
        headers=headers(customer),
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
        timeout=10,
    ).status_code == 200
    assert requests.post(f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=headers(customer), json={}, timeout=10).status_code == 200
    assert requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
        headers=headers(customer),
        json={"shippingMethodId": shipping_method["id"], "stockLocationId": location["id"]},
        timeout=10,
    ).status_code == 200

    payment_state_response = requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/next",
        headers=headers(customer),
        json={},
        timeout=10,
    )

    assert payment_state_response.status_code == 200
    order_after = payment_state_response.json()
    assert order_after["state"] == "payment"
    assert order_after["shipmentTotal"] == 0
