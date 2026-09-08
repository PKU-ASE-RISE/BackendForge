import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, **kwargs)


def auth_headers(email):
    return {"X-API-Key": "test-key", "X-User-Email": email}


def create_owner():
    email = f"owner-{uuid.uuid4().hex}@example.com"
    response = request(
        "post",
        f"{BASE_URL}/api/users",
        json={
            "email": email,
            "fullName": "Owner User",
            "password": "password123",
            "role": "owner",
        },
    )
    assert response.status_code == 201, response.text
    return email


def test_create_user_rejects_invalid_email_format():
    owner_email = create_owner()
    invalid_email = f"not-an-email-{uuid.uuid4().hex}"

    response = request(
        "post",
        f"{BASE_URL}/api/users",
        json={
            "email": invalid_email,
            "fullName": "Invalid Email User",
            "password": "password123",
            "role": "member",
        },
    )

    assert response.status_code == 400, response.text

    users_response = request(
        "get",
        f"{BASE_URL}/api/users",
        headers=auth_headers(owner_email),
    )
    assert users_response.status_code == 200, users_response.text
    assert invalid_email not in {user["email"] for user in users_response.json()}
