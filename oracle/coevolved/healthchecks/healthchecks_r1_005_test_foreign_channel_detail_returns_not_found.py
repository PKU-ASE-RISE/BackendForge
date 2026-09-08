import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def test_foreign_channel_detail_returns_not_found():
    owner_key = f"bf-probe-channel-owner-{uuid.uuid4().hex}"
    other_key = f"bf-probe-channel-other-{uuid.uuid4().hex}"
    owner_headers = _headers(owner_key)
    other_headers = _headers(other_key)

    created = requests.post(
        f"{BASE_URL}/api/v1/channels/",
        json={
            "kind": "email",
            "name": f"foreign-channel-{uuid.uuid4().hex}",
            "email": f"{uuid.uuid4().hex}@example.com",
        },
        headers=owner_headers,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    channel_id = created.json()["id"]

    foreign_get = requests.get(f"{BASE_URL}/api/v1/channels/{channel_id}", headers=other_headers, timeout=30)
    assert foreign_get.status_code == 404, foreign_get.text

    other_list = requests.get(f"{BASE_URL}/api/v1/channels/", headers=other_headers, timeout=30)
    assert other_list.status_code == 200, other_list.text
    assert channel_id not in {channel["id"] for channel in other_list.json()["channels"]}

    owner_get = requests.get(f"{BASE_URL}/api/v1/channels/{channel_id}", headers=owner_headers, timeout=30)
    assert owner_get.status_code == 200, owner_get.text
    assert owner_get.json()["id"] == channel_id
