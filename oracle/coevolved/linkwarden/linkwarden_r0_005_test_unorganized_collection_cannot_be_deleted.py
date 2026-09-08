import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_unorganized_collection_cannot_be_deleted():
    user_id = str(uuid.uuid4())
    h = headers(user_id)

    list_resp = requests.get(f"{BASE_URL}/api/collections", headers=h, timeout=30)
    assert list_resp.status_code == 200
    collections = list_resp.json()["collections"]
    unorganized = next(c for c in collections if c["name"] == "Unorganized")

    delete_resp = requests.delete(
        f"{BASE_URL}/api/collections/{unorganized['id']}",
        headers=h,
        timeout=30,
    )
    assert delete_resp.status_code == 403

    reload_resp = requests.get(
        f"{BASE_URL}/api/collections/{unorganized['id']}",
        headers=h,
        timeout=30,
    )
    assert reload_resp.status_code == 200
    assert reload_resp.json()["name"] == "Unorganized"
