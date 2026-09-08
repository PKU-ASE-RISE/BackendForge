import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


ADDRESS = {
    "firstName": "Ada",
    "lastName": "Lovelace",
    "address1": "1 Computation Way",
    "city": "London",
    "state": "LDN",
    "zipCode": "12345",
    "country": "GB",
    "phone": "555-0100",
}


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api(method, path, token, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers(token), **kwargs)


def make_tokens():
    store = f"s{uuid.uuid4().hex[:10]}"
    return f"admin_{store}_admin", f"{store}_owner", f"{store}_other"


def create_variant_with_stock(admin_token):
    suffix = uuid.uuid4().hex
    product = api(
        "post",
        "/api/v1/products",
        admin_token,
        json={"name": f"Address Product {suffix}", "price": 15.0, "currency": "USD", "available": True},
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]

    variant = api(
        "post",
        f"/api/v1/products/{product_id}/variants",
        admin_token,
        json={"sku": f"ADDR-{suffix}", "price": 15.0, "currency": "USD"},
    )
    assert variant.status_code == 201, variant.text

    loc = api(
        "post",
        "/api/v1/stock-locations",
        admin_token,
        json={"name": f"Address Location {suffix}", "active": True},
    )
    assert loc.status_code == 201, loc.text

    stock = api(
        "post",
        f"/api/v1/stock-locations/{loc.json()['id']}/stock-items",
        admin_token,
        json={"variantId": variant.json()["id"], "countOnHand": 4, "backorderable": False},
    )
    assert stock.status_code == 201, stock.text
    return variant.json()


def test_other_customer_cannot_set_order_addresses():
    admin_token, owner_token, other_token = make_tokens()
    variant = create_variant_with_stock(admin_token)

    order = api("post", "/api/v1/orders", owner_token, json={})
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    line_item = api(
        "post",
        f"/api/v1/orders/{order_id}/line-items",
        owner_token,
        json={"variantId": variant["id"], "quantity": 1},
    )
    assert line_item.status_code == 201, line_item.text

    advance = api("post", f"/api/v1/orders/{order_id}/next", owner_token, json={})
    assert advance.status_code == 200, advance.text
    assert advance.json()["state"] == "address"

    update = api(
        "put",
        f"/api/v1/orders/{order_id}/addresses",
        other_token,
        json={"billingAddress": ADDRESS, "shippingAddress": ADDRESS},
    )
    assert update.status_code in (403, 404), update.text

    owner_order = api("get", f"/api/v1/orders/{order_id}", owner_token)
    assert owner_order.status_code == 200, owner_order.text
    data = owner_order.json()
    assert data["billingAddress"] is None
    assert data["shippingAddress"] is None
