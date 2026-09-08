import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def api_request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def create_variant(admin_token, price=9.0):
    product_response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={
            "name": f"Foreign Variant Product {uuid.uuid4().hex}",
            "price": price,
            "currency": "USD",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    variant_response = api_request("post",
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers(admin_token),
        json={"sku": f"FV-{uuid.uuid4().hex}", "price": price, "currency": "USD"},
    )
    assert variant_response.status_code == 201, variant_response.text
    return variant_response.json()["id"]


def test_stock_item_rejects_foreign_variant():
    store_a = f"drpfa{uuid.uuid4().hex[:8]}"
    store_b = f"drpfb{uuid.uuid4().hex[:8]}"
    admin_a = f"admin_{store_a}_admin"
    admin_b = f"admin_{store_b}_admin"

    foreign_variant_id = create_variant(admin_a)

    location_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin_b),
        json={"name": f"Store B Location {uuid.uuid4().hex}", "active": True},
    )
    assert location_response.status_code == 201, location_response.text
    location_id = location_response.json()["id"]

    stock_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations/{location_id}/stock-items",
        headers=headers(admin_b),
        json={
            "variantId": foreign_variant_id,
            "countOnHand": 3,
            "backorderable": False,
        },
    )
    assert stock_response.status_code in (404, 422), stock_response.text

    listed_response = api_request("get",
        f"{BASE_URL}/api/v1/stock-locations/{location_id}/stock-items",
        headers=headers(admin_b),
    )
    assert listed_response.status_code == 200, listed_response.text
    assert all(item.get("variantId") != foreign_variant_id for item in listed_response.json())
