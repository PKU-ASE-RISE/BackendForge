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


def test_category_parent_can_be_cleared_with_null():
    admin = ensure_admin()

    parent = requests.post(
        f"{BASE_URL}/categories",
        headers=headers(admin),
        json={"name": unique("Parent Category")},
    )
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]

    child = requests.post(
        f"{BASE_URL}/categories",
        headers=headers(admin),
        json={"name": unique("Child Category"), "parentCategoryId": parent_id},
    )
    assert child.status_code == 201, child.text
    child_id = child.json()["id"]
    assert child.json()["parentCategoryId"] == parent_id

    cleared = requests.put(
        f"{BASE_URL}/categories/{child_id}",
        headers=headers(admin),
        json={"parentCategoryId": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["parentCategoryId"] is None

    reloaded = requests.get(f"{BASE_URL}/categories/{child_id}", headers=headers(admin))
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["parentCategoryId"] is None
