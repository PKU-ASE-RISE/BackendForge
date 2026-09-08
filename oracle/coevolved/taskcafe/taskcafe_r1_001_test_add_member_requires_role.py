import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, user_id):
    return requests.get(f"{BASE_URL}{path}", headers=headers(user_id), timeout=30)


def api_post(path, user_id, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers(user_id), json=json_data, timeout=30)


def test_add_member_requires_role():
    suffix = uuid.uuid4().hex
    owner_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    project_response = api_post("/projects", owner_id, {"name": f"required-role-{suffix}"})
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    response = api_post(f"/projects/{project['id']}/members", owner_id, {"userId": target_id})
    assert response.status_code != 201, response.text

    members_response = api_get(f"/projects/{project['id']}/members", owner_id)
    assert members_response.status_code == 200, members_response.text
    member_ids = {member["userId"] for member in members_response.json()}
    assert target_id not in member_ids
