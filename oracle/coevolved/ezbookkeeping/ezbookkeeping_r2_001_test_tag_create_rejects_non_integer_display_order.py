import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_tag_create_rejects_non_integer_display_order():
    headers = _headers()
    tag_name = f"bad-order-{uuid.uuid4().hex}"

    create_resp = requests.post(
        f"{BASE_URL}/tags",
        json={"name": tag_name, "displayOrder": "not-an-integer"},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 400, create_resp.text
    assert "error" in create_resp.json()

    list_resp = requests.get(f"{BASE_URL}/tags", headers=headers, timeout=30)
    assert list_resp.status_code == 200, list_resp.text
    assert all(tag["name"] != tag_name for tag in list_resp.json())
