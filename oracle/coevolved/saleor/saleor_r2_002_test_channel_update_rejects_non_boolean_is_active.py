import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def test_channel_update_rejects_non_boolean_is_active():
    slug = f"drp-ch-upd-bool-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/channels",
        json={
            "slug": slug,
            "name": "Boolean Update Probe",
            "currencyCode": "USD",
            "isActive": True,
        },
        headers=staff_headers(),
        timeout=30,
    )
    assert created.status_code == 201
    assert created.json()["isActive"] is True

    updated = requests.put(
        f"{BASE_URL}/channels/{slug}",
        json={"isActive": "false"},
        headers=staff_headers(),
        timeout=30,
    )
    assert updated.status_code == 400
    assert "error" in updated.json()

    reloaded = requests.get(
        f"{BASE_URL}/channels/{slug}",
        headers=staff_headers(),
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["isActive"] is True
