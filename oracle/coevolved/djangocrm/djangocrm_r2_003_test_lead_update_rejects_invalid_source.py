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


def test_lead_update_rejects_invalid_source():
    h = headers()
    marker = f"lead-source-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/leads",
        json={"source": "web", "notes": marker},
        headers=h,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    lead = created.json()

    updated = requests.put(
        f"{BASE_URL}/leads/{lead['id']}",
        json={"source": "social_media"},
        headers=h,
        timeout=30,
    )
    assert updated.status_code == 422, updated.text

    reloaded = requests.get(
        f"{BASE_URL}/leads/{lead['id']}",
        headers=h,
        timeout=30,
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["source"] == "web"
