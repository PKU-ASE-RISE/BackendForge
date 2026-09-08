import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, **kwargs)


def auth(email):
    return {"X-API-Key": "test-key", "X-User-Email": email}


def create_user(prefix="user", role="member"):
    token = uuid.uuid4().hex
    email = f"{prefix}-{token}@example.com"
    response = request(
        "post",
        f"{BASE_URL}/api/users",
        json={
            "email": email,
            "fullName": f"{prefix.title()} {token[:6]}",
            "password": "password123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), email


def test_guest_cannot_self_subscribe_public_stream():
    creator, creator_email = create_user("subscribe-creator", "member")
    guest, guest_email = create_user("subscribe-guest", "guest")
    stream_response = request(
        "post",
        f"{BASE_URL}/api/streams",
        headers=auth(creator_email),
        json={"name": f"subscribe-{uuid.uuid4().hex}", "description": "public stream"},
    )
    assert stream_response.status_code == 201, stream_response.text
    stream_id = stream_response.json()["id"]

    response = request(
        "post",
        f"{BASE_URL}/api/streams/{stream_id}/subscribers",
        headers=auth(guest_email),
        json={"userIds": [guest["id"]]},
    )
    assert response.status_code == 403

    subscribers_response = request(
        "get",
        f"{BASE_URL}/api/streams/{stream_id}/subscribers",
        headers=auth(creator_email),
    )
    assert subscribers_response.status_code == 200, subscribers_response.text
    assert guest["id"] not in subscribers_response.json()
