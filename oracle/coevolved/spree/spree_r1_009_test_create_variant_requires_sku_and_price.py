import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def test_create_variant_requires_sku_and_price():
    store = f"r1var{uuid.uuid4().hex[:12]}"
    headers = {"X-Store-Token": f"admin_{store}_admin", "Content-Type": "application/json"}
    product_response = requests.post(
        f"{BASE_URL}/api/v1/products",
        headers=headers,
        json={"name": f"VariantHost-{uuid.uuid4().hex}", "price": 19.5, "currency": "USD"},
        timeout=10,
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/api/v1/products/{product_id}/variants",
        headers=headers,
        json={},
        timeout=10,
    )

    assert response.status_code == 422
    assert "error" in response.json()
