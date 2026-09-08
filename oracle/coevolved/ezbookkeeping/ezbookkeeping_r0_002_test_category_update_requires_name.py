import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_put(path, payload, headers):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_category_update_requires_name():
    headers = make_headers()
    unique = uuid.uuid4().hex
    created_resp = api_post(
        "/categories",
        {
            "name": f"cat-required-{unique}",
            "type": "expense",
            "icon": "original-icon",
            "color": "#112233",
            "displayOrder": 4,
        },
        headers,
    )
    assert created_resp.status_code == 201, created_resp.text
    category_id = created_resp.json()["id"]

    update_resp = api_put(
        f"/categories/{category_id}",
        {"color": "#445566", "displayOrder": 88},
        headers,
    )
    assert update_resp.status_code == 400, update_resp.text

    fetched_resp = api_get(f"/categories/{category_id}", headers)
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()
    assert fetched["name"] == f"cat-required-{unique}"
    assert fetched["icon"] == "original-icon"
    assert fetched["color"] == "#112233"
    assert fetched["displayOrder"] == 4
