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


def test_activity_create_rejects_invalid_type():
    headers = _headers()
    subject = f"Invalid activity type {uuid.uuid4().hex}"
    invalid_type = f"fax_{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/activities",
        json={"type": invalid_type, "subject": subject},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 422

    listed = requests.get(f"{BASE_URL}/activities", headers=headers, timeout=30)
    assert listed.status_code == 200
    assert all(activity.get("subject") != subject for activity in listed.json())
