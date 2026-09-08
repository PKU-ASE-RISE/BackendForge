import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(label):
    return {"X-Api-Key": f"{label}-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def request(method, path, api_headers, **kwargs):
    return requests.request(method, f"{BASE_URL}{path}", headers=api_headers, timeout=30, **kwargs)


def create_project(api_headers, prefix):
    response = request("POST", "/api/projects", api_headers, json={"name": f"{prefix}-{uuid.uuid4().hex}"})
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


def create_identity(api_headers, environment_id):
    response = request(
        "POST",
        f"/api/environments/{environment_id}/identities",
        api_headers,
        json={"identifier": f"user-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_identity_override(api_headers, environment_id, identity_id, feature_id, value):
    response = request(
        "POST",
        f"/api/environments/{environment_id}/identities/{identity_id}/overrides",
        api_headers,
        json={"featureId": feature_id, "enabled": True, "value": value},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_update_identity_override_rejects_foreign_feature():
    org_a = headers("update-identity-a")
    org_b = headers("update-identity-b")

    project_a = create_project(org_a, "project-a")
    environment_a = create_environment(org_a, project_a["id"])
    local_feature = create_feature(org_a, project_a["id"])
    identity = create_identity(org_a, environment_a["id"])
    override = create_identity_override(org_a, environment_a["id"], identity["id"], local_feature["id"], "local")

    project_b = create_project(org_b, "project-b")
    foreign_feature = create_feature(org_b, project_b["id"])

    response = request(
        "PUT",
        f"/api/environments/{environment_a['id']}/identities/{identity['id']}/overrides/{override['id']}",
        org_a,
        json={"featureId": foreign_feature["id"], "enabled": True, "value": "foreign"},
    )

    overrides_response = request("GET", f"/api/environments/{environment_a['id']}/identities/{identity['id']}/overrides", org_a)
    assert overrides_response.status_code == 200, overrides_response.text
    current_override = next(item for item in overrides_response.json() if item["id"] == override["id"])

    assert response.status_code == 404, response.text
    assert current_override["featureId"] == local_feature["id"]
    assert current_override["value"] == "local"
