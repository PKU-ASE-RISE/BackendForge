import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


ADDRESS = {
    "firstName": "Katherine",
    "lastName": "Johnson",
    "address1": "3 Orbit St",
    "city": "Hampton",
    "state": "VA",
    "zipCode": "23666",
    "country": "US",
    "phone": "555-0102",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api(method, path, token, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers(token), **kwargs)


def make_tokens():
    store = f"s{uuid.uuid4().hex[:10]}"
    return f"admin_{store}_admin", f"{store}_owner", f"{store}_other"


def create_order_in_payment_state(admin_token, owner_token):
    suffix = uuid.uuid4().hex
    product = api(
        "post",
        "/api/v1/products",
        admin_token,
        json={"name": f"Capture Product {suffix}", "price": 25.0, "currency": "USD", "available": True},
    )
    assert product.status_code == 201, product.text

    variant = api(
        "post",
        f"/api/v1/products/{product.json()['id']}/variants",
        admin_token,
        json={"sku": f"CAP-{suffix}", "price": 25.0, "currency": "USD"},
    )
    assert variant.status_code == 201, variant.text

    loc = api("post", "/api/v1/stock-locations", admin_token, json={"name": f"Capture Location {suffix}", "active": True})
    assert loc.status_code == 201, loc.text

    stock = api(
        "post",
        f"/api/v1/stock-locations/{loc.json()['id']}/stock-items",
        admin_token,
        json={"variantId": variant.json()["id"], "countOnHand": 5, "backorderable": False},
    )
    assert stock.status_code == 201, stock.text

    shipping_method = api("post", "/api/v1/shipping-methods", admin_token, json={"name": f"Capture Ship {suffix}", "cost": 4.0})
    assert shipping_method.status_code == 201, shipping_method.text

    order = api("post", "/api/v1/orders", owner_token, json={})
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    line_item = api(
        "post",
        f"/api/v1/orders/{order_id}/line-items",
        owner_token,
        json={"variantId": variant.json()["id"], "quantity": 1},
    )
    assert line_item.status_code == 201, line_item.text

    assert api("post", f"/api/v1/orders/{order_id}/next", owner_token, json={}).status_code == 200
    assert api(
        "put",
        f"/api/v1/orders/{order_id}/addresses",
        owner_token,
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
    ).status_code == 200
    assert api("post", f"/api/v1/orders/{order_id}/next", owner_token, json={}).status_code == 200

    shipment = api(
        "post",
        f"/api/v1/orders/{order_id}/shipments",
        owner_token,
        json={"shippingMethodId": shipping_method.json()["id"], "stockLocationId": loc.json()["id"]},
    )
    assert shipment.status_code == 200, shipment.text

    payment_state = api("post", f"/api/v1/orders/{order_id}/next", owner_token, json={})
    assert payment_state.status_code == 200, payment_state.text
    assert payment_state.json()["state"] == "payment"
    return order_id


def test_other_customer_cannot_capture_order_payment():
    admin_token, owner_token, other_token = make_tokens()
    order_id = create_order_in_payment_state(admin_token, owner_token)

    payment_method = api(
        "post",
        "/api/v1/payment-methods",
        admin_token,
        json={"name": f"Capture Card {uuid.uuid4().hex}", "type": "gateway", "active": True},
    )
    assert payment_method.status_code == 201, payment_method.text

    order = api("get", f"/api/v1/orders/{order_id}", owner_token)
    assert order.status_code == 200, order.text
    amount = order.json()["total"]

    payment = api(
        "post",
        f"/api/v1/orders/{order_id}/payments",
        owner_token,
        json={"paymentMethodId": payment_method.json()["id"], "amount": amount},
    )
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["id"]
    assert payment.json()["state"] == "authorized"

    capture = api("post", f"/api/v1/orders/{order_id}/payments/{payment_id}/capture", other_token, json={})
    assert capture.status_code in (403, 404), capture.text

    owner_order = api("get", f"/api/v1/orders/{order_id}", owner_token)
    assert owner_order.status_code == 200, owner_order.text
    payment_states = {p["id"]: p["state"] for p in owner_order.json()["payments"]}
    assert payment_states[payment_id] == "authorized"
