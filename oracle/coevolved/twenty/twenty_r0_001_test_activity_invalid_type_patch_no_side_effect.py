import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10
MEMBER_KEY = "member_activity_invalid_type_side_effect"


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers():
    return {"X-API-Key": MEMBER_KEY, "Content-Type": "application/json"}


def test_activity_invalid_type_patch_no_side_effect():
    unique = uuid.uuid4().hex
    created = request(
        "post",
        f"{BASE_URL}/activities",
        headers=headers(),
        json={
            "type": "call",
            "title": f"Valid activity {unique[:8]}",
            "body": "Created with a valid enum value.",
        },
    )
    assert created.status_code == 201, created.text
    activity_id = created.json()["id"]

    invalid_update = request(
        "patch",
        f"{BASE_URL}/activities/{activity_id}",
        headers=headers(),
        json={"type": f"invalid-{unique[:8]}"},
    )
    assert invalid_update.status_code == 400, invalid_update.text

    reloaded = request("get", f"{BASE_URL}/activities/{activity_id}", headers=headers())
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["type"] == "call"
