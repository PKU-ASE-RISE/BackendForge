import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
API_KEY = "discourse-api-key"
ADMIN_USER = "discourse_test_admin"


def headers(username):
    return {"X-API-Key": API_KEY, "X-Username": username}


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def create_user(username, email=None, name=None, expected_status=201):
    response = requests.post(
        f"{BASE_URL}/users",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": "password123",
            "name": name or username,
        },
    )
    if expected_status is not None:
        assert response.status_code == expected_status, response.text
    return response


def ensure_admin():
    created = create_user(
        ADMIN_USER,
        f"{ADMIN_USER}@example.com",
        "Direct Reference Admin",
        expected_status=None,
    )
    assert created.status_code in {201, 409}, created.text
    promote = requests.put(
        f"{BASE_URL}/users/{ADMIN_USER}/trust-level",
        headers=headers(ADMIN_USER),
        json={"trustLevel": 4},
    )
    assert promote.status_code == 200, promote.text
    return ADMIN_USER


def test_trust_level_rejects_values_outside_openapi_range():
    admin = ensure_admin()

    for invalid_level in (-1, 5):
        target = unique("drp_tl_target")
        created = create_user(target)
        assert created.status_code == 201, created.text

        update = requests.put(
            f"{BASE_URL}/users/{target}/trust-level",
            headers=headers(admin),
            json={"trustLevel": invalid_level},
        )
        profile = requests.get(f"{BASE_URL}/users/{target}", headers=headers(admin))
        assert profile.status_code == 200, profile.text

        assert update.status_code >= 400, update.text
        assert profile.json()["trustLevel"] == 0
