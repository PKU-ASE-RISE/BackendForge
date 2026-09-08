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


def test_lead_create_rejects_invalid_source():
    headers = _headers()
    invalid_source = f"trade_show_{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/leads",
        json={"source": invalid_source, "notes": "invalid source probe"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 422

    listed = requests.get(f"{BASE_URL}/leads", headers=headers, timeout=30)
    assert listed.status_code == 200
    assert all(lead.get("source") != invalid_source for lead in listed.json())
