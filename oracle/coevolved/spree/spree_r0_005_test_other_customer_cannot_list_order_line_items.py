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


def create_variant_with_stock(admin_token, price=13.0, count=5):
    product_response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={
            "name": f"Private Line Product {uuid.uuid4().hex}",
            "price": price,
            "currency": "USD",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    variant_response = api_request("post",
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers(admin_token),
        json={
            "sku": f"PRIVATE-{uuid.uuid4().hex}",
            "price": price,
            "currency": "USD",
        },
    )
    assert variant_response.status_code == 201, variant_response.text
    variant_id = variant_response.json()["id"]

    location_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations",
        headers=headers(admin_token),
        json={"name": f"Line Stock {uuid.uuid4().hex}", "active": True},
    )
    assert location_response.status_code == 201, location_response.text
    location_id = location_response.json()["id"]

    stock_response = api_request("post",
        f"{BASE_URL}/api/v1/stock-locations/{location_id}/stock-items",
        headers=headers(admin_token),
        json={"variantId": variant_id, "countOnHand": count, "backorderable": False},
    )
    assert stock_response.status_code == 201, stock_response.text
    return variant_id


def test_other_customer_cannot_list_order_line_items():
    store = f"drpown{uuid.uuid4().hex[:8]}"
    admin_token = f"admin_{store}_admin"
    owner_token = f"{store}_owner"
    other_token = f"{store}_other"
    variant_id = create_variant_with_stock(admin_token)

    order_response = api_request("post",
        f"{BASE_URL}/api/v1/orders",
        headers=headers(owner_token),
        json={"email": "owner@example.com"},
    )
    assert order_response.status_code == 201, order_response.text
    order_id = order_response.json()["id"]

    line_response = api_request("post",
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(owner_token),
        json={"variantId": variant_id, "quantity": 1},
    )
    assert line_response.status_code == 201, line_response.text

    other_response = api_request("get",
        f"{BASE_URL}/api/v1/orders/{order_id}/line-items",
        headers=headers(other_token),
    )

    assert other_response.status_code in (403, 404), other_response.text
