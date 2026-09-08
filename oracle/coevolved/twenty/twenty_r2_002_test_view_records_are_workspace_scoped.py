import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def test_view_records_are_workspace_scoped():
    marker = uuid.uuid4().hex
    owner_a = f"owner_view_scope_a_{marker}"
    owner_b = f"owner_view_scope_b_{marker}"
    view_name = f"Scoped People View {marker}"

    created = request(
        "post",
        f"{BASE_URL}/views",
        headers=headers(owner_a),
        json={
            "name": view_name,
            "objectType": "people",
            "filters": [{"field": "firstName", "operator": "contains", "value": marker[:8]}],
            "sorts": [{"field": "createdAt", "direction": "desc"}],
        },
    )
    assert created.status_code == 201, created.text
    view = created.json()
    view_id = view["id"]

    same_workspace = request("get", f"{BASE_URL}/views/{view_id}", headers=headers(owner_a))
    assert same_workspace.status_code == 200, same_workspace.text
    assert same_workspace.json()["id"] == view_id

    other_workspace_get = request("get", f"{BASE_URL}/views/{view_id}", headers=headers(owner_b))
    assert other_workspace_get.status_code == 404, other_workspace_get.text

    other_workspace_list = request("get", f"{BASE_URL}/views", headers=headers(owner_b))
    assert other_workspace_list.status_code == 200, other_workspace_list.text
    leaked_ids = {item.get("id") for item in other_workspace_list.json().get("data", [])}
    leaked_names = {item.get("name") for item in other_workspace_list.json().get("data", [])}
    assert view_id not in leaked_ids
    assert view_name not in leaked_names
