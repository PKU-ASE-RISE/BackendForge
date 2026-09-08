import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def test_channel_rejects_non_boolean_is_active():
    slug = f"ch-invalid-active-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/channels",
        json={
            "slug": slug,
            "name": "Invalid Active Flag Channel",
            "currencyCode": "USD",
            "isActive": "true",
        },
        headers=staff_headers(),
        timeout=30,
    )

    assert response.status_code == 400, response.text

    get_response = requests.get(
        f"{BASE_URL}/channels/{slug}",
        headers=staff_headers(),
        timeout=30,
    )
    assert get_response.status_code == 404
