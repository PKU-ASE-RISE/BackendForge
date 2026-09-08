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


def test_mark_topic_read_unknown_topic_returns_404():
    user, email = create_user("topic-reader")
    stream_name = f"topic-read-{uuid.uuid4().hex}"
    stream_response = request(
        "post",
        f"{BASE_URL}/api/streams",
        headers=auth(email),
        json={"name": stream_name, "description": "topic read test"},
    )
    assert stream_response.status_code == 201, stream_response.text
    stream_id = stream_response.json()["id"]

    missing_topic = f"missing-{uuid.uuid4().hex}"
    response = request(
        "post",
        f"{BASE_URL}/api/mark-read/stream/{stream_id}/topic/{missing_topic}",
        headers=auth(email),
    )

    assert response.status_code == 404
