import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_update_project_rejects_unknown_parent():
    unique = uuid.uuid4().hex
    user_id = str(uuid.uuid4())
    headers = _headers(user_id)

    create = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={"title": f"project-parent-validation-{unique}"},
        timeout=30,
    )
    assert create.status_code == 201
    project = create.json()
    assert project["parent_project_id"] is None

    unknown_parent_id = 999_000_000_000 + int(unique[:6], 16)
    update = requests.put(
        f"{BASE_URL}/api/v1/projects/{project['id']}",
        headers=headers,
        json={"title": f"should-not-apply-{unique}", "parent_project_id": unknown_parent_id},
        timeout=30,
    )
    assert update.status_code in {400, 404}

    reloaded = requests.get(
        f"{BASE_URL}/api/v1/projects/{project['id']}",
        headers=headers,
        timeout=30,
    )
    assert reloaded.status_code == 200
    data = reloaded.json()
    assert data["title"] == f"project-parent-validation-{unique}"
    assert data["parent_project_id"] is None
