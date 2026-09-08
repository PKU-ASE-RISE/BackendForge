import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def _auth_headers():
    email = f"generator-length-{uuid.uuid4().hex}@example.com"
    password = "MasterPass123!"
    reg = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": "Generator"},
    )
    assert reg.status_code == 201, reg.text
    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": email, "masterPasswordHash": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_generator_respects_requested_length_with_multiple_classes():
    resp = requests.post(
        f"{BASE_URL}/api/generator/password",
        headers=_auth_headers(),
        json={
            "length": 2,
            "uppercase": True,
            "lowercase": True,
            "numbers": True,
            "special": False,
        },
    )

    if resp.status_code == 400:
        return

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["password"]) == 2
