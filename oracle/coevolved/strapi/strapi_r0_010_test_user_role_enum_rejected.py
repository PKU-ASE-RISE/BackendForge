import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def test_user_role_enum_rejected():
    suffix = uuid.uuid4().hex[:10]
    resp = requests.post(
        f"{BASE_URL}/users",
        json={
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "role": "superadmin",
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
