import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


ADDRESS = {
    "firstName": "Ada",
    "lastName": "Lovelace",
    "address1": "1 Loop",
    "city": "NYC",
    "state": "NY",
    "zipCode": "10001",
    "country": "US",
    "phone": "555-0100",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def setup_order_in_payment_state(store, owner):
    admin = f"admin_{store}_admin"
    product = requests.post(
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin),
        json={"name": f"PayOwner-{uuid.uuid4().hex}", "price": 15.0, "currency": "USD"},
        timeout=10,
    ).json()
    variant = requests.post(
        f"{BASE_URL}/api/v1/products/{product['id']}/variants",
        headers=headers(admin),
        json={"sku": f"PAY-{uuid.uuid4().hex}", "price": 15.0, "currency": "USD"},
        timeout=10,
    ).json()
    location = requests.post(
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin),
        json={"name": f"PayLoc-{uuid.uuid4().hex}", "active": True},
        timeout=10,
    ).json()
    requests.post(
        f"{BASE_URL}/api/v1/stock-locations/{location['id']}/stock-items",
        headers=headers(admin),
        json={"variantId": variant["id"], "countOnHand": 5, "backorderable": False},
        timeout=10,
    )
    shipping_method = requests.post(
        f"{BASE_URL}/api/v1/shipping-methods",
        headers=headers(admin),
        json={"name": f"PayShip-{uuid.uuid4().hex}", "cost": 4.0},
        timeout=10,
    ).json()
    payment_method = requests.post(
        f"{BASE_URL}/api/v1/payment-methods",
        headers=headers(admin),
        json={"name": f"PayMethod-{uuid.uuid4().hex}", "type": "gateway", "active": True},
        timeout=10,
    ).json()
    order = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers(owner), json={}, timeout=10).json()
    order_id = order["id"]
    add_response = requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(owner),
        json={"variantId": variant["id"], "quantity": 1},
        timeout=10,
    )
    assert add_response.status_code == 201
    assert requests.post(f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=headers(owner), json={}, timeout=10).status_code == 200
    assert requests.put(
        f"{BASE_URL}/api/v1/orders/{order_id}/addresses",
        headers=headers(owner),
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
        timeout=10,
    ).status_code == 200
    assert requests.post(f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=headers(owner), json={}, timeout=10).status_code == 200
    assert requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/shipments",
        headers=headers(owner),
        json={"shippingMethodId": shipping_method["id"], "stockLocationId": location["id"]},
        timeout=10,
    ).status_code == 200
    payment_state = requests.post(f"{BASE_URL}/api/v1/orders/{order_id}/next", headers=headers(owner), json={}, timeout=10)
    assert payment_state.status_code == 200
    return payment_state.json(), payment_method


def test_create_payment_requires_order_owner():
    store = f"r1payown{uuid.uuid4().hex[:12]}"
    owner = f"{store}_customer1"
    other = f"{store}_customer2"
    order, payment_method = setup_order_in_payment_state(store, owner)

    response = requests.post(
        f"{BASE_URL}/api/v1/orders/{order['id']}/payments",
        headers=headers(other),
        json={"paymentMethodId": payment_method["id"], "amount": order["total"]},
        timeout=10,
    )

    assert response.status_code in (403, 404)
    order_after = requests.get(f"{BASE_URL}/api/v1/orders/{order['id']}", headers=headers(owner), timeout=10).json()
    assert order_after["payments"] == []
