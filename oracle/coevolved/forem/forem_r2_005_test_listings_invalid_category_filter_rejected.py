import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_listings_invalid_category_filter_rejected():
    token = uuid.uuid4().hex
    create_response = requests.post(
        f"{BASE_URL}/listings",
        json={
            "title": f"Valid Listing {token}",
            "body": "listing body",
            "category": "jobs",
            "published": True,
        },
        headers={"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"},
        timeout=30,
    )
    assert create_response.status_code == 201

    response = requests.get(
        f"{BASE_URL}/listings",
        params={"category": f"invalid-{token}"},
        timeout=30,
    )

    assert response.status_code in (400, 422)
    assert "data" not in response.json()
