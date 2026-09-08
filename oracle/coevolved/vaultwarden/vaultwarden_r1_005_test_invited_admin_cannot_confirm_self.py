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


def test_invited_admin_cannot_confirm_self():
    _, owner_headers = _register_and_login("owner")
    invited_email, invited_headers = _register_and_login("invited-admin")

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
        json={"email": invited_email, "role": 1},
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invited_member = invite_resp.json()
    assert invited_member["status"] == 0

    self_confirm = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/{invited_member['id']}/confirm",
        headers=invited_headers,
    )

    assert self_confirm.status_code == 403, self_confirm.text

    owner_confirm = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/members/{invited_member['id']}/confirm",
        headers=owner_headers,
    )
    assert owner_confirm.status_code == 200, owner_confirm.text
    assert owner_confirm.json()["status"] == 1
