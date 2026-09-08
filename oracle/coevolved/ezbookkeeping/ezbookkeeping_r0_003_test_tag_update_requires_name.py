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


def test_tag_update_requires_name():
    headers = make_headers()
    unique = uuid.uuid4().hex
    created_resp = api_post(
        "/tags",
        {"name": f"tag-required-{unique}", "displayOrder": 5},
        headers,
    )
    assert created_resp.status_code == 201, created_resp.text
    tag_id = created_resp.json()["id"]

    update_resp = api_put(f"/tags/{tag_id}", {"displayOrder": 77}, headers)
    assert update_resp.status_code == 400, update_resp.text

    fetched_resp = api_get(f"/tags/{tag_id}", headers)
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()
    assert fetched["name"] == f"tag-required-{unique}"
    assert fetched["displayOrder"] == 5
