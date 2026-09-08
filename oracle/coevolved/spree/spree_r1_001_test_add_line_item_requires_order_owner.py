import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def create_variant_with_stock(store):
    admin = f"admin_{store}_admin"
    product = requests.post(
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin),
        json={"name": f"OwnerProbe-{uuid.uuid4().hex}", "price": 11.0, "currency": "USD"},
        timeout=10,
    ).json()
    variant = requests.post(
        f"{BASE_URL}/api/v1/products/{product['id']}/variants",
        headers=headers(admin),
        json={"sku": f"OWN-{uuid.uuid4().hex}", "price": 11.0, "currency": "USD"},
        timeout=10,
    ).json()
    location = requests.post(
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin),
        json={"name": f"OwnerLoc-{uuid.uuid4().hex}", "active": True},
        timeout=10,
    ).json()
    stock_response = requests.post(
        f"{BASE_URL}/api/v1/stock-locations/{location['id']}/stock-items",
        headers=headers(admin),
        json={"variantId": variant["id"], "countOnHand": 5, "backorderable": False},
        timeout=10,
    )
    assert stock_response.status_code == 201
    return variant


def test_add_line_item_requires_order_owner():
    store = f"r1ownli{uuid.uuid4().hex[:12]}"
    owner = f"{store}_customer1"
    other = f"{store}_customer2"
    variant = create_variant_with_stock(store)
    order_response = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers(owner), json={}, timeout=10)
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(other),
        json={"variantId": variant["id"], "quantity": 1},
        timeout=10,
    )

    assert response.status_code in (403, 404)
    order_after = requests.get(f"{BASE_URL}/api/v1/orders/{order_id}", headers=headers(owner), timeout=10).json()
    assert order_after["lineItems"] == []
