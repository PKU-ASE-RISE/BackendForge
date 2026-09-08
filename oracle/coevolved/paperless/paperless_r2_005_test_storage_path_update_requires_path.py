import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": f"drp-storage-put-required-{uuid.uuid4().hex}",
    "Content-Type": "application/json",
}


def post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def put(path, payload):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_storage_path_update_requires_path():
    original = {
        "name": f"storage-{uuid.uuid4().hex}",
        "path": "Archive/{created_year}/{title}",
    }
    created = post("/api/storage_paths/", original)
    assert created.status_code == 201, created.text
    storage_id = created.json()["id"]

    attempted_name = f"renamed-{uuid.uuid4().hex}"
    updated = put(f"/api/storage_paths/{storage_id}/", {"name": attempted_name})
    assert updated.status_code == 400, updated.text

    reloaded = get(f"/api/storage_paths/{storage_id}/")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["name"] == original["name"]
    assert reloaded.json()["path"] == original["path"]
