import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def _project_by_id(projects, project_id):
    for project in projects:
        if project.get("id") == project_id:
            return project
    raise AssertionError(f"project {project_id} not found in list: {projects}")


def test_project_list_includes_role_info():
    unique = uuid.uuid4().hex
    owner_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    owner_headers = _headers(owner_id)
    member_headers = _headers(member_id)

    requests.get(f"{BASE_URL}/api/v1/projects", headers=member_headers, timeout=30)

    create = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=owner_headers,
        json={"title": f"role-list-{unique}"},
        timeout=30,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    add_member = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "viewer"},
        timeout=30,
    )
    assert add_member.status_code == 201
    assert add_member.json() == {"user_id": member_id, "role": "viewer"}

    owner_list = requests.get(f"{BASE_URL}/api/v1/projects", headers=owner_headers, timeout=30)
    member_list = requests.get(f"{BASE_URL}/api/v1/projects", headers=member_headers, timeout=30)
    assert owner_list.status_code == 200
    assert member_list.status_code == 200

    owner_project = _project_by_id(owner_list.json(), project_id)
    member_project = _project_by_id(member_list.json(), project_id)

    assert owner_project["title"] == f"role-list-{unique}"
    assert member_project["title"] == f"role-list-{unique}"
    assert owner_project["owner_id"] == owner_id
    assert member_project["owner_id"] == owner_id
    assert owner_project.get("role") == "owner"
    assert member_project.get("role") == "viewer"
