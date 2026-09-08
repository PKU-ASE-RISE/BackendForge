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


def test_invited_member_cannot_access_org_until_confirmed():
    owner_email, owner_headers = _register_and_login("owner")
    invited_email, invited_headers = _register_and_login("invited")

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

    invite_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/invite",
        headers=owner_headers,
        json={"email": invited_email, "role": 3},
    )
    assert invite_resp.status_code == 200, invite_resp.text
    assert invite_resp.json()["status"] == 0

    org_get = requests.get(f"{BASE_URL}/api/organizations/{org_id}", headers=invited_headers)
    members_get = requests.get(
        f"{BASE_URL}/api/organizations/{org_id}/members", headers=invited_headers
    )
    collections_get = requests.get(
        f"{BASE_URL}/api/organizations/{org_id}/collections", headers=invited_headers
    )

    assert org_get.status_code == 403, org_get.text
    assert members_get.status_code == 403, members_get.text
    assert collections_get.status_code == 403, collections_get.text
