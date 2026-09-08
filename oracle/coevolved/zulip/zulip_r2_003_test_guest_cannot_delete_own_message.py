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


def test_guest_cannot_delete_own_message():
    creator, creator_email = create_user("delete-creator", "member")
    guest, guest_email = create_user("delete-guest", "guest")
    stream_response = request(
        "post",
        f"{BASE_URL}/api/streams",
        headers=auth(creator_email),
        json={"name": f"delete-{uuid.uuid4().hex}", "description": "delete role test"},
    )
    assert stream_response.status_code == 201, stream_response.text
    stream_id = stream_response.json()["id"]
    subscribe_response = request(
        "post",
        f"{BASE_URL}/api/streams/{stream_id}/subscribers",
        headers=auth(creator_email),
        json={"userIds": [guest["id"]]},
    )
    assert subscribe_response.status_code == 200, subscribe_response.text

    message_response = request(
        "post",
        f"{BASE_URL}/api/messages",
        headers=auth(guest_email),
        json={"streamId": stream_id, "topic": "guest-delete", "content": "guest message"},
    )
    assert message_response.status_code == 201, message_response.text
    message_id = message_response.json()["id"]

    delete_response = request(
        "delete",
        f"{BASE_URL}/api/messages/{message_id}",
        headers=auth(guest_email),
    )
    assert delete_response.status_code == 403

    reload_response = request(
        "get",
        f"{BASE_URL}/api/messages/{message_id}",
        headers=auth(creator_email),
    )
    assert reload_response.status_code == 200
