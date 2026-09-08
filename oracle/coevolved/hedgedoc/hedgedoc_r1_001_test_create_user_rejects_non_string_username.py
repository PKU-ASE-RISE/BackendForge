import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def test_create_user_rejects_non_string_username():
    bad_username = ["user", uuid.uuid4().hex]

    resp = requests.post(
        f"{API}/users",
        json={
            "username": bad_username,
            "displayName": "Malformed Username",
            "password": "testpass123",
        },
    )

    assert resp.status_code == 400
