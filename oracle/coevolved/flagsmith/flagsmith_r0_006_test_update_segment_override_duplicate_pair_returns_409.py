import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"seg-dup-update-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def request(method, path, api_headers, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", headers=api_headers, timeout=30, **kwargs)


def create_project(api_headers):
    response = request("POST", "/api/projects", api_headers, json={"name": f"project-{uuid.uuid4().hex}"})
    assert response.status_code == 201, response.text
    return response.json()


def create_environment(api_headers, project_id):
    response = request("POST", f"/api/projects/{project_id}/environments", api_headers, json={"name": f"env-{uuid.uuid4().hex}"})
    assert response.status_code == 201, response.text
    return response.json()


def create_feature(api_headers, project_id):
    response = request(
        "POST",
        f"/api/projects/{project_id}/features",
        api_headers,
        json={"name": f"feature-{uuid.uuid4().hex}", "type": "FLAG", "defaultEnabled": False, "initialValue": ""},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_segment(api_headers, project_id):
    response = request(
        "POST",
        f"/api/projects/{project_id}/segments",
        api_headers,
        json={"name": f"segment-{uuid.uuid4().hex}", "matchType": "ALL", "rules": []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_override(api_headers, environment_id, feature_id, segment_id, value):
    response = request(
        "POST",
        f"/api/environments/{environment_id}/segment-overrides",
        api_headers,
        json={"featureId": feature_id, "segmentId": segment_id, "enabled": True, "value": value, "priority": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_update_segment_override_duplicate_pair_returns_409():
    api_headers = headers()
    project = create_project(api_headers)
    environment = create_environment(api_headers, project["id"])
    feature_one = create_feature(api_headers, project["id"])
    feature_two = create_feature(api_headers, project["id"])
    segment_one = create_segment(api_headers, project["id"])
    segment_two = create_segment(api_headers, project["id"])
    override_one = create_override(api_headers, environment["id"], feature_one["id"], segment_one["id"], "first")
    override_two = create_override(api_headers, environment["id"], feature_two["id"], segment_two["id"], "second")

    response = request(
        "PUT",
        f"/api/environments/{environment['id']}/segment-overrides/{override_two['id']}",
        api_headers,
        json={
            "featureId": feature_one["id"],
            "segmentId": segment_one["id"],
            "enabled": True,
            "value": "duplicate",
            "priority": 99,
        },
    )

    overrides_response = request("GET", f"/api/environments/{environment['id']}/segment-overrides", api_headers)
    assert overrides_response.status_code == 200, overrides_response.text
    overrides_by_id = {item["id"]: item for item in overrides_response.json()}

    assert response.status_code == 409, response.text
    assert overrides_by_id[override_one["id"]]["featureId"] == feature_one["id"]
    assert overrides_by_id[override_one["id"]]["segmentId"] == segment_one["id"]
    assert overrides_by_id[override_two["id"]]["featureId"] == feature_two["id"]
    assert overrides_by_id[override_two["id"]]["segmentId"] == segment_two["id"]
