import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": f"drp-saved-view-filter-{uuid.uuid4().hex}",
    "Content-Type": "application/json",
}


def post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_saved_view_filter_rule_requires_rule_type_and_value():
    name = f"bad-filter-view-{uuid.uuid4().hex}"
    created = post(
        "/api/saved_views/",
        {
            "name": name,
            "filter_rules": [{"rule_type": 19}],
        },
    )
    assert created.status_code == 400, created.text

    listed = get("/api/saved_views/")
    assert listed.status_code == 200, listed.text
    assert all(view["name"] != name for view in listed.json()["results"])
