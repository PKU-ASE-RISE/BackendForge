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


def test_unconfirmed_manager_cannot_create_collection():
    _, owner_headers = _register_and_login("owner")
    invited_email, invited_headers = _register_and_login("invited-manager")

    org_resp = requests.post(
        f"{BASE_URL}/api/organizations",
        headers=owner_headers,
        json={"name": f"org-{uuid.uuid4().hex}"},
    )
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    invite_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/invite",
        headers=owner_headers,
        json={"email": invited_email, "role": 2},
    )
    assert invite_resp.status_code == 200, invite_resp.text
    assert invite_resp.json()["status"] == 0

    create_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/collections",
        headers=invited_headers,
        json={"name": f"premature-{uuid.uuid4().hex}"},
    )

    assert create_resp.status_code == 403, create_resp.text
