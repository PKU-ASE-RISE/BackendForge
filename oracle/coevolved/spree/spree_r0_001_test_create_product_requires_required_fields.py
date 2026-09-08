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


def test_create_product_requires_required_fields():
    store = f"drpreq{uuid.uuid4().hex[:8]}"
    admin_token = f"admin_{store}_admin"

    response = api_request("post",
        f"{BASE_URL}/api/v1/products",
        headers=headers(admin_token),
        json={"name": f"Incomplete-{uuid.uuid4().hex}"},
    )

    assert response.status_code == 422, response.text

    listed = api_request("get", f"{BASE_URL}/api/v1/products", headers=headers(admin_token))
    assert listed.status_code == 200
    names = [product.get("name") for product in listed.json().get("data", [])]
    assert not any(name and name.startswith("Incomplete-") for name in names)
