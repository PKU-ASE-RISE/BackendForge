import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers():
    return {"X-Api-Key": f"label-newline-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def _create_project(headers):
    resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"name": f"label-newline-project-{uuid.uuid4().hex}", "description": "label newline probe"},
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def test_create_label_rejects_trailing_newline_color():
    headers = _headers()
    project_id = _create_project(headers)
    label_value = f"bad-color-{uuid.uuid4().hex}"

    create_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/labels",
        json={"value": label_value, "color": "#ff0000\n"},
        headers=headers,
        timeout=30,
    )
    list_resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}/labels", headers=headers, timeout=30)

    assert list_resp.status_code == 200, list_resp.text
    label_values = {label["value"] for label in list_resp.json()["data"]}
    assert create_resp.status_code == 400, create_resp.text
    assert label_value not in label_values
