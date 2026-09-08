import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def test_channel_create_rejects_non_string_slug():
    numeric_slug = int(uuid.uuid4().hex[:12], 16) + 1

    response = requests.post(
        f"{BASE_URL}/channels",
        json={
            "slug": numeric_slug,
            "name": "Non String Slug Probe",
            "currencyCode": "USD",
            "isActive": True,
        },
        headers=staff_headers(),
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    listed = requests.get(
        f"{BASE_URL}/channels",
        headers=staff_headers(),
        timeout=30,
    )
    assert listed.status_code == 200
    assert all(channel["slug"] != numeric_slug for channel in listed.json()["data"])
