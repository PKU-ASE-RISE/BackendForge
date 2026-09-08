import base64
import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def _register_and_login(prefix):
    email = f"{prefix}_{uuid.uuid4().hex}@example.com"
    password = "MasterPass123!"
    register = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": prefix},
    )
    assert register.status_code == 201, register.text
    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": email, "masterPasswordHash": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["accessToken"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _b64(value):
    return base64.b64encode(value.encode()).decode()


def test_cipher_create_rejects_foreign_folder_id():
    owner_token = _register_and_login("folder_owner")
    attacker_token = _register_and_login("folder_attacker")

    folder_resp = requests.post(
        f"{BASE_URL}/api/folders",
        headers=_auth(owner_token),
        json={"name": _b64("owner-only-folder")},
    )
    assert folder_resp.status_code == 201, folder_resp.text
    foreign_folder_id = folder_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/ciphers",
        headers=_auth(attacker_token),
        json={
            "type": 1,
            "name": _b64("foreign-folder-cipher"),
            "folderId": foreign_folder_id,
            "login": {
                "uri": "https://example.invalid",
                "username": _b64("user"),
                "password": _b64("pass"),
            },
        },
    )

    assert create_resp.status_code == 400, create_resp.text
