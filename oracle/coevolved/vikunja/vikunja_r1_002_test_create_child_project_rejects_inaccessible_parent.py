import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_create_child_project_rejects_inaccessible_parent():
    unique = uuid.uuid4().hex
    parent_owner_id = str(uuid.uuid4())
    outsider_id = str(uuid.uuid4())
    parent_headers = _headers(parent_owner_id)
    outsider_headers = _headers(outsider_id)

    parent = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=parent_headers,
        json={"title": f"private-parent-{unique}"},
        timeout=30,
    )
    assert parent.status_code == 201
    parent_id = parent.json()["id"]

    attempted_title = f"unauthorized-child-{unique}"
    create_child = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=outsider_headers,
        json={"title": attempted_title, "parent_project_id": parent_id},
        timeout=30,
    )
    assert create_child.status_code in {400, 403, 404}

    parent_owner_projects = requests.get(
        f"{BASE_URL}/api/v1/projects",
        headers=parent_headers,
        timeout=30,
    )
    assert parent_owner_projects.status_code == 200
    titles = {project["title"] for project in parent_owner_projects.json()}
    assert attempted_title not in titles
