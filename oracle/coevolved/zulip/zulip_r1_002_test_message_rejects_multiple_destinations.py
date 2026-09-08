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


def create_user(prefix="user", role="member"):
    email = unique_email(prefix)
    response = api(
        "post",
        "/api/users",
        json={
            "email": email,
            "fullName": f"{prefix.title()} User",
            "password": "password123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return email, response.json()


def test_message_rejects_multiple_destinations():
    sender_email, sender = create_user("sender")
    recipient_email, recipient = create_user("recipient")

    stream_response = api(
        "post",
        "/api/streams",
        email=sender_email,
        json={"name": f"multi-destination-{uuid.uuid4().hex}", "description": "destination validation"},
    )
    assert stream_response.status_code == 201, stream_response.text
    stream = stream_response.json()

    subscribe_response = api(
        "post",
        f"/api/streams/{stream['id']}/subscribers",
        email=sender_email,
        json={"userIds": [sender["id"], recipient["id"]]},
    )
    assert subscribe_response.status_code == 200, subscribe_response.text

    dm_response = api(
        "post",
        "/api/dm-conversations",
        email=sender_email,
        json={"participantIds": [sender["id"], recipient["id"]]},
    )
    assert dm_response.status_code == 201, dm_response.text
    conversation = dm_response.json()

    response = api(
        "post",
        "/api/messages",
        email=sender_email,
        json={
            "content": f"ambiguous destination {uuid.uuid4().hex}",
            "streamId": stream["id"],
            "topic": f"topic-{uuid.uuid4().hex}",
            "dmConversationId": conversation["id"],
        },
    )
    assert response.status_code == 400, response.text
