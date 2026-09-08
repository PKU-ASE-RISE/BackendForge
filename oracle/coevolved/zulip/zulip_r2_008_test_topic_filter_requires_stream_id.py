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


def test_topic_filter_requires_stream_id():
    user, email = create_user("topic-filter")
    topic_name = f"topic-only-{uuid.uuid4().hex}"

    response = request(
        "get",
        f"{BASE_URL}/api/messages",
        headers=auth(email),
        params={"topic": topic_name},
    )

    assert response.status_code == 400
