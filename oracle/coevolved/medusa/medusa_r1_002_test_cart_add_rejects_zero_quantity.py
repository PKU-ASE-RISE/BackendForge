import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin_direct_probe"


def url(path):
    return f"{BASE_URL}{path}"


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def customer_headers(key):
    return {"X-API-Key": key, "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def test_cart_add_rejects_zero_quantity():
    customer_key = unique("cust_zero_qty_")
    requests.post(
        url("/store/customers"),
        headers=customer_headers(customer_key),
        json={
            "email": f"{customer_key}@example.test",
            "firstName": "Zero",
            "lastName": "Quantity",
        },
    )

    region_resp = requests.post(
        url("/admin/regions"),
        headers=admin_headers(),
        json={"name": unique("ZeroQtyRegion-"), "currency": "usd", "taxRate": 0.0},
    )
    assert region_resp.status_code == 201
    region_id = region_resp.json()["id"]

    product_resp = requests.post(
        url("/admin/products"),
        headers=admin_headers(),
        json={"title": "Zero Quantity Product", "handle": unique("zero-qty-"), "status": "published"},
    )
    assert product_resp.status_code == 201
    product_id = product_resp.json()["id"]

    variant_resp = requests.post(
        url(f"/admin/products/{product_id}/variants"),
        headers=admin_headers(),
        json={
            "title": "Default",
            "sku": unique("ZQ-"),
            "price": 1200,
            "inventoryQuantity": 5,
        },
    )
    assert variant_resp.status_code == 201
    variant_id = variant_resp.json()["id"]

    cart_resp = requests.post(
        url("/store/carts"),
        headers=customer_headers(customer_key),
        json={"regionId": region_id},
    )
    assert cart_resp.status_code == 201

    bad_add = requests.post(
        url("/store/carts/mine/items"),
        headers=customer_headers(customer_key),
        json={"variantId": variant_id, "quantity": 0},
    )
    assert 400 <= bad_add.status_code < 500, bad_add.text

    cart_after = requests.get(url("/store/carts/mine"), headers=customer_headers(customer_key))
    assert cart_after.status_code == 200
    assert cart_after.json()["items"] == []
