import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 10
ADMIN_TOKEN = "system_admin"


def headers(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_org():
    name = unique("org")
    response = requests.post(
        f"{BASE_URL}/organizations",
        json={"name": name, "domain": f"{name}.example.com"},
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_action_enabled_must_be_boolean():
    org = create_org()
    action_name = unique("action")

    response = requests.post(
        f"{BASE_URL}/organizations/{org['id']}/actions",
        json={
            "name": action_name,
            "eventType": "pre.login",
            "script": "console.log('pre')",
            "enabled": "yes",
        },
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 400, response.text

    actions = requests.get(
        f"{BASE_URL}/organizations/{org['id']}/actions",
        headers=headers(),
        timeout=REQUEST_TIMEOUT,
    )
    assert actions.status_code == 200, actions.text
    assert all(item["name"] != action_name for item in actions.json()["items"])
