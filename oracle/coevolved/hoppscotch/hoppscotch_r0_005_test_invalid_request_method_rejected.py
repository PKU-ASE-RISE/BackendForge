import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user):
    return {"X-API-Key": user, "Content-Type": "application/json"}


def test_invalid_request_method_rejected():
    user = f"user_{uuid.uuid4().hex}"
    collection = requests.post(
        f"{BASE_URL}/collections",
        json={"name": f"col_{uuid.uuid4().hex}"},
        headers=headers(user),
    )
    assert collection.status_code == 201
    collection_id = collection.json()["id"]

    request_name = f"invalid_method_{uuid.uuid4().hex}"
    resp = requests.post(
        f"{BASE_URL}/requests",
        json={
            "collectionId": collection_id,
            "name": request_name,
            "method": "TRACE",
            "url": "https://example.com/trace",
        },
        headers=headers(user),
    )

    assert resp.status_code == 400
    listed = requests.get(
        f"{BASE_URL}/requests",
        params={"collectionId": collection_id},
        headers=headers(user),
    )
    assert listed.status_code == 200
    assert all(item["name"] != request_name for item in listed.json())
