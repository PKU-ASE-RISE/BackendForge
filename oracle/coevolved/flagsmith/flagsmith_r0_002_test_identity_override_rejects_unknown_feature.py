import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"identity-missing-{uuid.uuid4().hex}", "Content-Type": "application/json"}


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


def create_identity(api_headers, environment_id):
    response = request(
        "POST",
        f"/api/environments/{environment_id}/identities",
        api_headers,
        json={"identifier": f"user-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_identity_override_rejects_unknown_feature():
    api_headers = headers()
    project = create_project(api_headers)
    environment = create_environment(api_headers, project["id"])
    identity = create_identity(api_headers, environment["id"])
    missing_feature_id = 9_000_000_000_000 + int(uuid.uuid4().hex[:6], 16)

    response = request(
        "POST",
        f"/api/environments/{environment['id']}/identities/{identity['id']}/overrides",
        api_headers,
        json={"featureId": missing_feature_id, "enabled": True, "value": "should-not-exist"},
    )

    overrides_response = request("GET", f"/api/environments/{environment['id']}/identities/{identity['id']}/overrides", api_headers)
    assert overrides_response.status_code == 200, overrides_response.text

    assert response.status_code == 404, response.text
    assert all(item["featureId"] != missing_feature_id for item in overrides_response.json())
