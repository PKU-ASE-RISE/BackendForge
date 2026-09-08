import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def api_get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)


def api_post(path, headers, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def api_put(path, headers, json_data):
    return requests.put(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def test_project_update_rejects_cross_org_client():
    h_a = fresh_headers()
    h_b = fresh_headers()
    assert api_get("/api/v1/organizations/current", headers=h_a).status_code == 200
    assert api_get("/api/v1/organizations/current", headers=h_b).status_code == 200

    token = uuid.uuid4().hex
    client_resp = api_post(
        "/api/v1/clients",
        headers=h_a,
        json_data={"name": f"client-a-{token}"},
    )
    assert client_resp.status_code == 201
    client_a = client_resp.json()

    project_resp = api_post(
        "/api/v1/projects",
        headers=h_b,
        json_data={
            "name": f"project-b-{token}",
            "color": "#445566",
            "is_billable": False,
        },
    )
    assert project_resp.status_code == 201
    project_b = project_resp.json()
    assert project_b["client_id"] is None

    update_resp = api_put(
        f"/api/v1/projects/{project_b['id']}",
        headers=h_b,
        json_data={"client_id": client_a["id"]},
    )
    assert update_resp.status_code == 422

    reload_resp = api_get(f"/api/v1/projects/{project_b['id']}", headers=h_b)
    assert reload_resp.status_code == 200
    assert reload_resp.json()["client_id"] is None
