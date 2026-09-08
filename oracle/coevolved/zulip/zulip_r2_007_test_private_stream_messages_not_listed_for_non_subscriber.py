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


def test_private_stream_messages_not_listed_for_non_subscriber():
    owner, owner_email = create_user("private-owner", "member")
    outsider, outsider_email = create_user("private-outsider", "member")
    stream_response = request(
        "post",
        f"{BASE_URL}/api/streams",
        headers=auth(owner_email),
        json={
            "name": f"private-{uuid.uuid4().hex}",
            "description": "private message isolation",
            "isPrivate": True,
        },
    )
    assert stream_response.status_code == 201, stream_response.text
    stream_id = stream_response.json()["id"]
    secret = f"secret-{uuid.uuid4().hex}"
    message_response = request(
        "post",
        f"{BASE_URL}/api/messages",
        headers=auth(owner_email),
        json={"streamId": stream_id, "topic": "private-topic", "content": secret},
    )
    assert message_response.status_code == 201, message_response.text
    message_id = message_response.json()["id"]

    list_response = request(
        "get",
        f"{BASE_URL}/api/messages",
        headers=auth(outsider_email),
        params={"streamId": stream_id, "keyword": secret},
    )
    assert list_response.status_code == 200, list_response.text
    leaked_ids = {message["id"] for message in list_response.json()}

    assert message_id not in leaked_ids
