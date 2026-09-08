import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"seg-missing-{uuid.uuid4().hex}", "Content-Type": "application/json"}


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


def test_segment_override_rejects_unknown_segment():
    api_headers = headers()
    project = create_project(api_headers)
    environment = create_environment(api_headers, project["id"])
    feature = create_feature(api_headers, project["id"])
    missing_segment_id = 9_000_000_000_000 + int(uuid.uuid4().hex[:6], 16)

    response = request(
        "POST",
        f"/api/environments/{environment['id']}/segment-overrides",
        api_headers,
        json={
            "featureId": feature["id"],
            "segmentId": missing_segment_id,
            "enabled": True,
            "value": "should-not-exist",
            "priority": 1,
        },
    )

    overrides_response = request("GET", f"/api/environments/{environment['id']}/segment-overrides", api_headers)
    assert overrides_response.status_code == 200, overrides_response.text

    assert response.status_code == 404, response.text
    assert all(item["segmentId"] != missing_segment_id for item in overrides_response.json())
