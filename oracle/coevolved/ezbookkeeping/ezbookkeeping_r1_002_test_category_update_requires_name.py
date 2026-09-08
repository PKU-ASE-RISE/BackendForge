import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_category_update_requires_name():
    headers = _headers()
    suffix = uuid.uuid4().hex

    create_resp = requests.post(
        f"{BASE_URL}/categories",
        json={
            "name": f"category-required-{suffix}",
            "type": "expense",
            "icon": "cart",
            "color": "#123456",
            "displayOrder": 7,
        },
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 201, create_resp.text
    category = create_resp.json()

    partial_update_resp = requests.put(
        f"{BASE_URL}/categories/{category['id']}",
        json={"color": "#654321", "displayOrder": 1},
        headers=headers,
        timeout=30,
    )

    fetched_resp = requests.get(
        f"{BASE_URL}/categories/{category['id']}",
        headers=headers,
        timeout=30,
    )
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()

    assert partial_update_resp.status_code == 400, partial_update_resp.text
    assert fetched["name"] == category["name"]
    assert fetched["color"] == "#123456"
    assert fetched["displayOrder"] == 7
