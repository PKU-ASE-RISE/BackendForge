import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-Api-Key": f"org-feature-update-enum-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_update_feature_rejects_invalid_type_enum():
    headers = _headers()
    project_resp = requests.post(
        f"{BASE_URL}/api/projects",
        json={"name": f"proj-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/features",
        json={"name": f"valid-feature-{uuid.uuid4().hex}", "type": "CONFIG", "defaultEnabled": True, "initialValue": "stable"},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 201
    feature = create_resp.json()

    update_resp = requests.put(
        f"{BASE_URL}/api/projects/{project_id}/features/{feature['id']}",
        json={"name": feature["name"], "type": "REMOTE", "defaultEnabled": False, "initialValue": "mutated"},
        headers=headers,
        timeout=30,
    )
    assert update_resp.status_code != 200

    reload_resp = requests.get(
        f"{BASE_URL}/api/projects/{project_id}/features/{feature['id']}",
        headers=headers,
        timeout=30,
    )
    assert reload_resp.status_code == 200
    reloaded = reload_resp.json()
    assert reloaded["type"] == "CONFIG"
    assert reloaded["defaultEnabled"] is True
    assert reloaded["initialValue"] == "stable"
