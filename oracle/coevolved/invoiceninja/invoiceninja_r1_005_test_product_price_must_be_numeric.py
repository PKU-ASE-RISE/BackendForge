import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"product-price-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_product_price_must_be_numeric():
    response = requests.post(
        f"{BASE_URL}/api/products",
        json={
            "name": f"product-{uuid.uuid4().hex}",
            "price": "not-a-number",
        },
        headers=headers(),
        timeout=30,
    )

    assert response.status_code == 422
    assert "error" in response.json()
