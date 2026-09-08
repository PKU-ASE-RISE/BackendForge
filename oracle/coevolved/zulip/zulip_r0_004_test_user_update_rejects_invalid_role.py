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


def create_user(prefix, role="member"):
    email = f"{prefix}-{uuid.uuid4().hex}@example.com"
    response = request(
        "post",
        f"{BASE_URL}/api/users",
        json={
            "email": email,
            "fullName": f"{prefix.title()} User",
            "password": "password123",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    user["email"] = email
    return user


def test_user_update_rejects_invalid_role():
    owner = create_user("owner", role="owner")
    target = create_user("target", role="member")
    invalid_role = f"invalid-role-{uuid.uuid4().hex}"

    response = request(
        "patch",
        f"{BASE_URL}/api/users/{target['id']}",
        headers=auth_headers(owner["email"]),
        json={"role": invalid_role},
    )

    assert response.status_code == 400, response.text

    reload_response = request(
        "get",
        f"{BASE_URL}/api/users/{target['id']}",
        headers=auth_headers(owner["email"]),
    )
    assert reload_response.status_code == 200, reload_response.text
    assert reload_response.json()["role"] == "member"
