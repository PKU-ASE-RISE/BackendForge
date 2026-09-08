import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_check_update_rejects_overlong_subject():
    api_key = f"bf-probe-overlong-subject-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    created = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": f"subject-check-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    check_id = created.json()["id"]

    initial_subject = f"subject-{uuid.uuid4().hex}"
    initial_update = requests.post(
        f"{BASE_URL}/api/v1/checks/{check_id}",
        json={"subject": initial_subject},
        headers=headers,
        timeout=30,
    )
    assert initial_update.status_code == 200, initial_update.text
    assert initial_update.json()["subject"] == initial_subject

    too_long_subject = "s" * 201
    rejected = requests.post(
        f"{BASE_URL}/api/v1/checks/{check_id}",
        json={"subject": too_long_subject},
        headers=headers,
        timeout=30,
    )
    assert rejected.status_code == 400, rejected.text

    fetched = requests.get(f"{BASE_URL}/api/v1/checks/{check_id}", headers=headers, timeout=30)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["subject"] == initial_subject
