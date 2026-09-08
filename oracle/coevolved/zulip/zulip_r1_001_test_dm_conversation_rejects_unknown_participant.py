import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, **kwargs)


def api(method, path, email=None, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = "test-key"
    if email is not None:
        headers["X-User-Email"] = email
    return request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def test_dm_conversation_rejects_unknown_participant():
    owner_email = unique_email("dm-owner")
    create_response = api(
        "post",
        "/api/users",
        json={
            "email": owner_email,
            "fullName": "DM Owner",
            "password": "password123",
            "role": "member",
        },
    )
    assert create_response.status_code == 201, create_response.text
    owner = create_response.json()

    unknown_user_id = 0
    assert unknown_user_id != owner["id"]

    response = api(
        "post",
        "/api/dm-conversations",
        email=owner_email,
        json={"participantIds": [owner["id"], unknown_user_id]},
    )
    assert response.status_code == 400, response.text
