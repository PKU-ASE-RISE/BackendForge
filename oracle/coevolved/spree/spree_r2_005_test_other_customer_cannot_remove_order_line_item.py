import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


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
    product_resp = api(
        "post",
        "/api/v1/products",
        admin_token,
        json={"name": f"Owner Delete Product {suffix}", "price": 12.5, "currency": "USD", "available": True},
    )
    assert product_resp.status_code == 201, product_resp.text
    product = product_resp.json()

    variant_resp = api(
        "post",
        f"/api/v1/products/{product['id']}/variants",
        admin_token,
        json={"sku": f"OD-{suffix}", "price": 12.5, "currency": "USD"},
    )
    assert variant_resp.status_code == 201, variant_resp.text
    variant = variant_resp.json()

    loc_resp = api(
        "post",
        "/api/v1/stock-locations",
        admin_token,
        json={"name": f"Owner Delete Location {suffix}", "active": True},
    )
    assert loc_resp.status_code == 201, loc_resp.text
    loc = loc_resp.json()

    stock_resp = api(
        "post",
        f"/api/v1/stock-locations/{loc['id']}/stock-items",
        admin_token,
        json={"variantId": variant["id"], "countOnHand": 5, "backorderable": False},
    )
    assert stock_resp.status_code == 201, stock_resp.text
    return variant


def test_other_customer_cannot_remove_order_line_item():
    admin_token, owner_token, other_token = make_tokens()
    variant = create_variant_with_stock(admin_token)

    order_resp = api("post", "/api/v1/orders", owner_token, json={})
    assert order_resp.status_code == 201, order_resp.text
    order_id = order_resp.json()["id"]

    line_resp = api(
        "post",
        f"/api/v1/orders/{order_id}/line-items",
        owner_token,
        json={"variantId": variant["id"], "quantity": 1},
    )
    assert line_resp.status_code == 201, line_resp.text
    line_item_id = line_resp.json()["id"]

    delete_resp = api("delete", f"/api/v1/orders/{order_id}/line-items/{line_item_id}", other_token)
    assert delete_resp.status_code in (403, 404), delete_resp.text

    owner_order_resp = api("get", f"/api/v1/orders/{order_id}", owner_token)
    assert owner_order_resp.status_code == 200, owner_order_resp.text
    line_item_ids = {item["id"] for item in owner_order_resp.json()["lineItems"]}
    assert line_item_id in line_item_ids
