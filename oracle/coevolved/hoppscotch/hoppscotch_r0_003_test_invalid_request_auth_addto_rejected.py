import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user):
    return {"X-API-Key": user, "Content-Type": "application/json"}


def test_invalid_request_auth_addto_rejected():
    user = f"user_{uuid.uuid4().hex}"
    collection = requests.post(
        f"{BASE_URL}/collections",
        json={"name": f"col_{uuid.uuid4().hex}"},
        headers=headers(user),
    )
    assert collection.status_code == 201

    resp = requests.post(
        f"{BASE_URL}/requests",
        json={
            "collectionId": collection.json()["id"],
            "name": f"bad_addto_{uuid.uuid4().hex}",
            "method": "GET",
            "url": "https://example.com/resource",
            "auth": {
                "type": "api-key",
                "key": "X-Test-Key",
                "value": "secret",
                "addTo": "cookie",
            },
        },
        headers=headers(user),
    )

    assert resp.status_code == 400
