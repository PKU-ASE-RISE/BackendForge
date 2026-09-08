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


def test_get_product_includes_created_variants():
    store = f"drpvar{uuid.uuid4().hex[:8]}"
    admin_token = f"admin_{store}_admin"

    product_response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={
            "name": f"Variant Detail Product {uuid.uuid4().hex}",
            "price": 19.5,
            "currency": "USD",
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    variant_response = api_request("post",
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers(admin_token),
        json={
            "sku": f"SKU-{uuid.uuid4().hex}",
            "price": 21.0,
            "currency": "USD",
        },
    )
    assert variant_response.status_code == 201, variant_response.text
    variant_id = variant_response.json()["id"]

    detail_response = api_request("get",
        f"{BASE_URL}/api/v1/products/{product_id}",
        headers=headers(admin_token),
    )
    assert detail_response.status_code == 200, detail_response.text
    product = detail_response.json()

    assert "variants" in product
    assert any(variant.get("id") == variant_id for variant in product["variants"])
