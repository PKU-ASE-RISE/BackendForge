import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USER_ID = str(uuid.uuid4())
ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())
HEADERS_A = {"X-User-Id": USER_ID, "X-Org-Id": ORG_A, "Content-Type": "application/json"}
HEADERS_B = {"X-User-Id": USER_ID, "X-Org-Id": ORG_B, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS_A, timeout=30)


def post(path, json_data, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS_A, timeout=30)


def put(path, json_data, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS_A, timeout=30)


def test_project_update_rejects_other_org_client():
    suffix = uuid.uuid4().hex
    project = post("/projects", {"name": f"project-org-a-{suffix}"}, headers=HEADERS_A).json()
    other_org_client = post(
        "/clients",
        {"name": f"client-org-b-{suffix}"},
        headers=HEADERS_B,
    ).json()

    response = put(
        f"/projects/{project['id']}",
        {"client_id": other_org_client["id"]},
        headers=HEADERS_A,
    )

    assert response.status_code == 404, response.text
    reloaded = get(f"/projects/{project['id']}", headers=HEADERS_A).json()
    assert reloaded["client_id"] is None
