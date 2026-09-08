import base64
import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def _register_and_login(prefix):
    email = f"{prefix}-{uuid.uuid4().hex}@example.com"
    password = "MasterPass123!"
    reg = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": prefix},
    )
    assert reg.status_code == 201, reg.text
    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": email, "masterPasswordHash": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _create_login_cipher(headers, label):
    resp = requests.post(
        f"{BASE_URL}/api/ciphers",
        headers=headers,
        json={
            "type": 1,
            "name": base64.b64encode(label.encode()).decode(),
            "login": {"uri": "https://example.com", "username": label, "password": "pw"},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_attachment_download_requires_matching_cipher():
    owner_headers = _register_and_login("attachment-owner")
    other_headers = _register_and_login("attachment-other")
    owner_cipher = _create_login_cipher(owner_headers, f"owner-{uuid.uuid4().hex}")
    other_cipher = _create_login_cipher(other_headers, f"other-{uuid.uuid4().hex}")

    secret_bytes = b"attachment-data-that-belongs-to-owner"
    upload_resp = requests.post(
        f"{BASE_URL}/api/ciphers/{owner_cipher['id']}/attachment",
        headers=owner_headers,
        files={"file": ("owner-secret.txt", secret_bytes, "text/plain")},
    )
    assert upload_resp.status_code == 201, upload_resp.text
    attachment = upload_resp.json()["attachments"][0]

    cross_download = requests.get(
        f"{BASE_URL}/api/ciphers/{other_cipher['id']}/attachment/{attachment['id']}",
        headers=other_headers,
    )

    assert cross_download.status_code == 404, cross_download.text
