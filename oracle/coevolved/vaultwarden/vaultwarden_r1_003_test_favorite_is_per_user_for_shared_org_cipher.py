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
    return email, {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_favorite_is_per_user_for_shared_org_cipher():
    _, owner_headers = _register_and_login("owner")
    member_email, member_headers = _register_and_login("member")

    org_resp = requests.post(
        f"{BASE_URL}/api/organizations",
        headers=owner_headers,
        json={"name": f"org-{uuid.uuid4().hex}"},
    )
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    collection_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/collections",
        headers=owner_headers,
        json={"name": f"collection-{uuid.uuid4().hex}"},
    )
    assert collection_resp.status_code == 201, collection_resp.text
    collection_id = collection_resp.json()["id"]

    invite_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/invite",
        headers=owner_headers,
        json={"email": member_email, "role": 3},
    )
    assert invite_resp.status_code == 200, invite_resp.text
    confirm_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/{invite_resp.json()['id']}/confirm",
        headers=owner_headers,
    )
    assert confirm_resp.status_code == 200, confirm_resp.text

    cipher_resp = requests.post(
        f"{BASE_URL}/api/ciphers",
        headers=owner_headers,
        json={
            "type": 1,
            "name": base64.b64encode(f"shared-{uuid.uuid4().hex}".encode()).decode(),
            "organizationId": org_id,
            "collectionIds": [collection_id],
            "favorite": False,
            "login": {"uri": "https://example.com", "username": "owner", "password": "pw1"},
        },
    )
    assert cipher_resp.status_code == 201, cipher_resp.text
    cipher_id = cipher_resp.json()["id"]
    assert cipher_resp.json()["favorite"] is False

    member_favorite = requests.put(
        f"{BASE_URL}/api/ciphers/{cipher_id}/favorite",
        headers=member_headers,
        json={"favorite": True},
    )
    assert member_favorite.status_code == 200, member_favorite.text
    assert member_favorite.json()["favorite"] is True

    owner_reload = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=owner_headers)
    assert owner_reload.status_code == 200, owner_reload.text
    assert owner_reload.json()["favorite"] is False
