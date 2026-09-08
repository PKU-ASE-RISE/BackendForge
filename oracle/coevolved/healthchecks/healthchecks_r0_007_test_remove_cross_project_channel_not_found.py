import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def test_remove_cross_project_channel_not_found():
    api_key_a = f"bf-probe-remove-a-{uuid.uuid4().hex}"
    api_key_b = f"bf-probe-remove-b-{uuid.uuid4().hex}"
    headers_a = _headers(api_key_a)
    headers_b = _headers(api_key_b)

    check_resp = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": f"cross-remove-check-{uuid.uuid4().hex}"},
        headers=headers_a,
        timeout=30,
    )
    assert check_resp.status_code == 201, check_resp.text
    check_id = check_resp.json()["id"]

    own_channel_resp = requests.post(
        f"{BASE_URL}/api/v1/channels/",
        json={"kind": "email", "name": f"own-channel-{uuid.uuid4().hex}", "email": f"{uuid.uuid4().hex}@example.com"},
        headers=headers_a,
        timeout=30,
    )
    assert own_channel_resp.status_code == 201, own_channel_resp.text
    own_channel_id = own_channel_resp.json()["id"]

    assign_resp = requests.post(
        f"{BASE_URL}/api/v1/checks/{check_id}/channels/{own_channel_id}",
        headers=headers_a,
        timeout=30,
    )
    assert assign_resp.status_code == 200, assign_resp.text

    other_channel_resp = requests.post(
        f"{BASE_URL}/api/v1/channels/",
        json={"kind": "email", "name": f"other-channel-{uuid.uuid4().hex}", "email": f"{uuid.uuid4().hex}@example.com"},
        headers=headers_b,
        timeout=30,
    )
    assert other_channel_resp.status_code == 201, other_channel_resp.text
    other_channel_id = other_channel_resp.json()["id"]

    remove_resp = requests.delete(
        f"{BASE_URL}/api/v1/checks/{check_id}/channels/{other_channel_id}",
        headers=headers_a,
        timeout=30,
    )

    fetched = requests.get(f"{BASE_URL}/api/v1/checks/{check_id}", headers=headers_a, timeout=30)
    assert fetched.status_code == 200, fetched.text
    channels = {value for value in fetched.json()["channels"].split(",") if value}

    assert own_channel_id in channels
    assert other_channel_id not in channels
    assert remove_resp.status_code == 404, remove_resp.text
