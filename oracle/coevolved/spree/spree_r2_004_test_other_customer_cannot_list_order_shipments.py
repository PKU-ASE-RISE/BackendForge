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
    "phone": "555-0101",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api(method, path, token, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers(token), **kwargs)


def make_tokens():
    store = f"s{uuid.uuid4().hex[:10]}"
    return f"admin_{store}_admin", f"{store}_owner", f"{store}_other"


def create_order_ready_for_delivery(admin_token, owner_token):
    suffix = uuid.uuid4().hex
    product = api(
        "post",
        "/api/v1/products",
        admin_token,
        json={"name": f"Shipment List Product {suffix}", "price": 20.0, "currency": "USD", "available": True},
    )
    assert product.status_code == 201, product.text

    variant = api(
        "post",
        f"/api/v1/products/{product.json()['id']}/variants",
        admin_token,
        json={"sku": f"SHIP-LIST-{suffix}", "price": 20.0, "currency": "USD"},
    )
    assert variant.status_code == 201, variant.text

    loc = api(
        "post",
        "/api/v1/stock-locations",
        admin_token,
        json={"name": f"Shipment List Location {suffix}", "active": True},
    )
    assert loc.status_code == 201, loc.text

    stock = api(
        "post",
        f"/api/v1/stock-locations/{loc.json()['id']}/stock-items",
        admin_token,
        json={"variantId": variant.json()["id"], "countOnHand": 3, "backorderable": False},
    )
    assert stock.status_code == 201, stock.text

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
    addresses = api(
        "put",
        f"/api/v1/orders/{order_id}/addresses",
        owner_token,
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
    )
    assert addresses.status_code == 200, addresses.text
    advance = api("post", f"/api/v1/orders/{order_id}/next", owner_token, json={})
    assert advance.status_code == 200, advance.text
    assert advance.json()["state"] == "delivery"

    shipping_method = api(
        "post",
        "/api/v1/shipping-methods",
        admin_token,
        json={"name": f"Shipment List Method {suffix}", "cost": 6.0},
    )
    assert shipping_method.status_code == 201, shipping_method.text

    shipment = api(
        "post",
        f"/api/v1/orders/{order_id}/shipments",
        owner_token,
        json={"shippingMethodId": shipping_method.json()["id"], "stockLocationId": loc.json()["id"]},
    )
    assert shipment.status_code == 200, shipment.text
    return order_id


def test_other_customer_cannot_list_order_shipments():
    admin_token, owner_token, other_token = make_tokens()
    order_id = create_order_ready_for_delivery(admin_token, owner_token)

    response = api("get", f"/api/v1/orders/{order_id}/shipments", other_token)
    assert response.status_code in (403, 404), response.text
