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
        json={"name": f"feature-{uuid.uuid4().hex}", "type": "CONFIG", "defaultEnabled": False, "initialValue": "default"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_segment(api_headers, project_id, rules):
    response = request(
        "POST",
        f"/api/projects/{project_id}/segments",
        api_headers,
        json={"name": f"segment-{uuid.uuid4().hex}", "matchType": "ALL", "rules": rules},
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


def create_segment_override(api_headers, environment_id, feature_id, segment_id, value):
    response = request(
        "POST",
        f"/api/environments/{environment_id}/segment-overrides",
        api_headers,
        json={"featureId": feature_id, "segmentId": segment_id, "enabled": True, "value": value, "priority": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_update_segment_override_rejects_foreign_segment():
    org_a = headers("update-seg-a")
    org_b = headers("update-seg-b")

    project_a = create_project(org_a, "project-a")
    environment_a = create_environment(org_a, project_a["id"])
    feature_a = create_feature(org_a, project_a["id"])
    local_segment = create_segment(org_a, project_a["id"], [])
    override = create_segment_override(org_a, environment_a["id"], feature_a["id"], local_segment["id"], "local-value")
    identity = create_identity(org_a, environment_a["id"])

    project_b = create_project(org_b, "project-b")
    foreign_segment = create_segment(
        org_b,
        project_b["id"],
        [{"property": "tier", "operator": "EQUAL", "value": "gold"}],
    )
    trait_response = request(
        "POST",
        f"/api/environments/{environment_a['id']}/identities/{identity['id']}/traits",
        org_a,
        json={"key": "tier", "value": "gold"},
    )
    assert trait_response.status_code == 200, trait_response.text

    response = request(
        "PUT",
        f"/api/environments/{environment_a['id']}/segment-overrides/{override['id']}",
        org_a,
        json={
            "featureId": feature_a["id"],
            "segmentId": foreign_segment["id"],
            "enabled": True,
            "value": "foreign-value",
            "priority": 50,
        },
    )

    overrides_response = request("GET", f"/api/environments/{environment_a['id']}/segment-overrides", org_a)
    assert overrides_response.status_code == 200, overrides_response.text
    current_override = next(item for item in overrides_response.json() if item["id"] == override["id"])
    flags_response = request("GET", f"/api/environments/{environment_a['id']}/identities/{identity['id']}/flags", org_a)
    assert flags_response.status_code == 200, flags_response.text
    flag = next(item for item in flags_response.json() if item["featureId"] == feature_a["id"])

    assert response.status_code == 404, response.text
    assert current_override["segmentId"] == local_segment["id"]
    assert flag["source"] == "SEGMENT"
    assert flag["value"] == "local-value"
