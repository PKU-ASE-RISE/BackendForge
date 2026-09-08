import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_auto_provision_prefix_collision():
    prefix = uuid.uuid4().hex[:8]
    first_user_id = f"{prefix}-0000-4000-8000-000000000001"
    second_user_id = f"{prefix}-0000-4000-8000-000000000002"

    first = requests.get(
        f"{BASE_URL}/users/me",
        headers={"X-User-Id": first_user_id},
        timeout=30,
    )
    assert first.status_code == 200
    assert first.json()["id"] == first_user_id

    second = requests.get(
        f"{BASE_URL}/users/me",
        headers={"X-User-Id": second_user_id},
        timeout=30,
    )
    assert second.status_code == 200
    assert second.json()["id"] == second_user_id
