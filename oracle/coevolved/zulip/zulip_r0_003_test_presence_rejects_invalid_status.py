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


def create_user():
    email = f"presence-{uuid.uuid4().hex}@example.com"
    response = request(
        "post",
        f"{BASE_URL}/api/users",
        json={
            "email": email,
            "fullName": "Presence User",
            "password": "password123",
            "role": "member",
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    user["email"] = email
    return user


def test_presence_rejects_invalid_status():
    user = create_user()

    initial_response = request(
        "post",
        f"{BASE_URL}/api/users/{user['id']}/presence",
        headers=auth_headers(user["email"]),
        json={"status": "online"},
    )
    assert initial_response.status_code == 200, initial_response.text
    assert initial_response.json()["status"] == "online"

    invalid_status = f"busy-{uuid.uuid4().hex}"
    invalid_response = request(
        "post",
        f"{BASE_URL}/api/users/{user['id']}/presence",
        headers=auth_headers(user["email"]),
        json={"status": invalid_status},
    )
    assert invalid_response.status_code == 400, invalid_response.text

    reload_response = request(
        "get",
        f"{BASE_URL}/api/users/{user['id']}/presence",
        headers=auth_headers(user["email"]),
    )
    assert reload_response.status_code == 200, reload_response.text
    assert reload_response.json()["status"] == "online"
