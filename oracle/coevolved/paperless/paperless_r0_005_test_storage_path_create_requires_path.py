import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"drp-storage-path-required-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_storage_path_create_requires_path():
    h = headers()
    name = f"missing-path-{uuid.uuid4().hex}"

    resp = requests.post(
        f"{BASE_URL}/api/storage_paths/",
        json={"name": name},
        headers=h,
        timeout=30,
    )

    assert resp.status_code == 400, resp.text

    listed = requests.get(f"{BASE_URL}/api/storage_paths/", headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(path["name"] != name for path in listed.json()["results"])
