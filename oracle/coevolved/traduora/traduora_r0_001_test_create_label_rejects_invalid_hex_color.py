import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"probe-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def get(path, h):
    return requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)


def create_project(h):
    response = post(
        "/api/v1/projects",
        {"name": f"proj-{uuid.uuid4().hex}", "description": "probe"},
        h,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_create_label_rejects_invalid_hex_color():
    h = headers()
    project_id = create_project(h)
    label_value = f"label-{uuid.uuid4().hex}"

    response = post(
        f"/api/v1/projects/{project_id}/labels",
        {"value": label_value, "color": "not-a-hex-color"},
        h,
    )
    assert response.status_code == 400, response.text

    labels_response = get(f"/api/v1/projects/{project_id}/labels", h)
    assert labels_response.status_code == 200, labels_response.text
    values = [label["value"] for label in labels_response.json()["data"]]
    assert label_value not in values
