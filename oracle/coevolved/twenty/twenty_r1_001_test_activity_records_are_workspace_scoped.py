import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def test_activity_records_are_workspace_scoped():
    unique = uuid.uuid4().hex
    workspace_a = f"member_activity_a_{unique}"
    workspace_b = f"member_activity_b_{unique}"
    title = f"Scoped activity {unique}"

    create_resp = request(
        "post",
        f"{BASE_URL}/activities",
        headers=headers(workspace_a),
        json={"type": "call", "title": title, "body": "Workspace A only"},
    )
    assert create_resp.status_code == 201
    activity_id = create_resp.json()["id"]

    own_get = request("get", f"{BASE_URL}/activities/{activity_id}", headers=headers(workspace_a))
    assert own_get.status_code == 200
    assert own_get.json()["id"] == activity_id

    other_get = request("get", f"{BASE_URL}/activities/{activity_id}", headers=headers(workspace_b))
    assert other_get.status_code == 404

    other_list = request(
        "get",
        f"{BASE_URL}/activities",
        headers=headers(workspace_b),
        params={"type": "call", "limit": 100, "offset": 0},
    )
    assert other_list.status_code == 200
    leaked_ids = {activity["id"] for activity in other_list.json()["data"]}
    assert activity_id not in leaked_ids
