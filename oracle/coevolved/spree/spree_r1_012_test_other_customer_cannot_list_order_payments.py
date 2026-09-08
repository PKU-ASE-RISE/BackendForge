import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def headers(token):
    return {"X-Store-Token": token, "Content-Type": "application/json"}


def test_other_customer_cannot_list_order_payments():
    store = f"r1paylist{uuid.uuid4().hex[:12]}"
    owner = f"{store}_customer1"
    other = f"{store}_customer2"
    order_response = requests.post(f"{BASE_URL}/api/v1/orders", headers=headers(owner), json={}, timeout=10)
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]

    response = requests.get(f"{BASE_URL}/api/v1/orders/{order_id}/payments", headers=headers(other), timeout=10)

    assert response.status_code in (403, 404)
