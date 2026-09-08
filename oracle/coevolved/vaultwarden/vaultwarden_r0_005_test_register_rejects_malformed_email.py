import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def test_register_rejects_malformed_email():
    malformed_email = f"not-an-email-{uuid.uuid4().hex}"
    password = f"MasterPass-{uuid.uuid4().hex}"

    resp = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={
            "email": malformed_email,
            "masterPasswordHash": password,
            "name": "Malformed Email",
        },
    )

    assert resp.status_code == 400

    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": malformed_email, "masterPasswordHash": password},
    )
    assert login.status_code == 401
