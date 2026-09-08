import base64
import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def _register_and_login():
    email = f"sync_since_{uuid.uuid4().hex}@example.com"
    password = "MasterPass123!"
    register = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": "Sync Since"},
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


def test_sync_since_filters_organizations_and_collections():
    token = _register_and_login()

    org_resp = requests.post(
        f"{BASE_URL}/api/organizations",
        headers=_auth(token),
        json={"name": f"sync-org-{uuid.uuid4().hex}"},
    )
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    collection_resp = requests.post(
        f"{BASE_URL}/api/organizations/{org_id}/collections",
        headers=_auth(token),
        json={"name": _b64("sync-collection")},
    )
    assert collection_resp.status_code == 201, collection_resp.text

    future_since = "2100-01-01T00:00:00+00:00"
    sync_resp = requests.get(
        f"{BASE_URL}/api/sync",
        headers=_auth(token),
        params={"since": future_since},
    )
    assert sync_resp.status_code == 200, sync_resp.text
    data = sync_resp.json()

    assert data["ciphers"] == []
    assert data["folders"] == []
    assert data["collections"] == []
    assert data["organizations"] == []
