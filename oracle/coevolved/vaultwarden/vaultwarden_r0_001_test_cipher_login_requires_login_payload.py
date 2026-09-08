import base64
import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def _auth_headers():
    email = f"login-payload-{uuid.uuid4().hex}@example.com"
    password = f"MasterPass-{uuid.uuid4().hex}"
    register = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": "Login Payload"},
    )
    assert register.status_code == 201
    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": email, "masterPasswordHash": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_cipher_login_requires_login_payload():
    headers = _auth_headers()
    cipher_name = base64.b64encode(f"missing-login-{uuid.uuid4().hex}".encode()).decode()

    resp = requests.post(
        f"{BASE_URL}/api/ciphers",
        headers=headers,
        json={"type": 1, "name": cipher_name},
    )

    assert resp.status_code == 400

    listed = requests.get(f"{BASE_URL}/api/ciphers", headers=headers)
    assert listed.status_code == 200
    assert all(item.get("name") != cipher_name for item in listed.json().get("data", []))
