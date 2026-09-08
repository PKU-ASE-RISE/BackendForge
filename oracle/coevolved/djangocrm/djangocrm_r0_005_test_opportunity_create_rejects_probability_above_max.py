import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_opportunity_create_rejects_probability_above_max():
    headers = _headers()
    title = f"Overprobable Deal {uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/opportunities",
        json={"title": title, "stage": "prospecting", "value": 1000, "probability": 101},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 422

    listed = requests.get(
        f"{BASE_URL}/opportunities",
        headers=headers,
        timeout=30,
    )
    assert listed.status_code == 200
    assert all(opp.get("title") != title for opp in listed.json())
