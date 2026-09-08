import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def test_create_wishlist_requires_name():
    store = f"r1wlname{uuid.uuid4().hex[:12]}"
    headers = {"X-Store-Token": f"{store}_customer1", "Content-Type": "application/json"}

    response = requests.post(f"{BASE_URL}/api/v1/wishlists", headers=headers, json={}, timeout=10)

    assert response.status_code == 422
    assert "error" in response.json()
