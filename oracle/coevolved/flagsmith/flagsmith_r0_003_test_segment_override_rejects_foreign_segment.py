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


def create_feature(api_headers, project_id, initial_value):
    response = request(
        "POST",
        f"/api/projects/{project_id}/features",
        api_headers,
        json={
            "name": f"feature-{uuid.uuid4().hex}",
            "type": "CONFIG",
            "defaultEnabled": False,
            "initialValue": initial_value,
        },
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


def test_segment_override_rejects_foreign_segment():
    org_a = headers("seg-foreign-a")
    org_b = headers("seg-foreign-b")

    project_a = create_project(org_a, "project-a")
    environment_a = create_environment(org_a, project_a["id"])
    feature_a = create_feature(org_a, project_a["id"], "default-value")
    identity_a = create_identity(org_a, environment_a["id"])
    trait_response = request(
        "POST",
        f"/api/environments/{environment_a['id']}/identities/{identity_a['id']}/traits",
        org_a,
        json={"key": "plan", "value": "enterprise"},
    )
    assert trait_response.status_code == 200, trait_response.text

    project_b = create_project(org_b, "project-b")
    foreign_segment = create_segment(
        org_b,
        project_b["id"],
        [{"property": "plan", "operator": "EQUAL", "value": "enterprise"}],
    )

    response = request(
        "POST",
        f"/api/environments/{environment_a['id']}/segment-overrides",
        org_a,
        json={
            "featureId": feature_a["id"],
            "segmentId": foreign_segment["id"],
            "enabled": True,
            "value": "foreign-segment-value",
            "priority": 100,
        },
    )

    flags_response = request("GET", f"/api/environments/{environment_a['id']}/identities/{identity_a['id']}/flags", org_a)
    assert flags_response.status_code == 200, flags_response.text
    flag = next(item for item in flags_response.json() if item["featureId"] == feature_a["id"])
    overrides_response = request("GET", f"/api/environments/{environment_a['id']}/segment-overrides", org_a)
    assert overrides_response.status_code == 200, overrides_response.text

    assert response.status_code == 404, response.text
    assert flag["source"] == "DEFAULT"
    assert flag["value"] == "default-value"
    assert all(item["segmentId"] != foreign_segment["id"] for item in overrides_response.json())
