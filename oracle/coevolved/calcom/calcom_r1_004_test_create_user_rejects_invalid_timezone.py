import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def test_create_user_rejects_invalid_timezone():
    resp = requests.post(
        f"{BASE_URL}/v1/users",
        json={
            "name": unique("user-"),
            "email": f"{unique('u-')}@example.com",
            "timezone": "Not/A_Real_Zone",
        },
        timeout=30,
    )
    assert resp.status_code == 400, resp.text
