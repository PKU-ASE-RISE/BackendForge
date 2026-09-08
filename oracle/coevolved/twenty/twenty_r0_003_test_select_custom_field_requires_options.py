import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10
ADMIN_KEY = "admin_select_custom_field_requires_options"


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def test_select_custom_field_requires_options():
    unique = uuid.uuid4().hex
    response = request(
        "post",
        f"{BASE_URL}/custom-fields",
        headers=headers(),
        json={
            "name": f"selectField{unique[:10]}",
            "label": f"Select Field {unique[:10]}",
            "objectType": "people",
            "type": "select",
        },
    )

    assert response.status_code == 400, response.text
    body = response.json()
    assert "error" in body
