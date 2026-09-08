import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_opportunity_update_rejects_invalid_close_date_format():
    h = headers()
    title = f"invalid-close-date-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/opportunities",
        json={"title": title, "stage": "prospecting", "value": 1000, "probability": 25},
        headers=h,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    opportunity = created.json()
    assert opportunity.get("close_date") is None

    updated = requests.put(
        f"{BASE_URL}/opportunities/{opportunity['id']}",
        json={"close_date": "not-a-date"},
        headers=h,
        timeout=30,
    )
    assert updated.status_code == 422, updated.text

    reloaded = requests.get(
        f"{BASE_URL}/opportunities/{opportunity['id']}",
        headers=h,
        timeout=30,
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json().get("close_date") is None
