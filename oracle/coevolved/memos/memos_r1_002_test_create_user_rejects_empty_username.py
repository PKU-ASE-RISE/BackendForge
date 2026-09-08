import os
import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def create_host(first_user_response):
    resp = first_user_response
    assert resp.status_code == 201, resp.text
    host = resp.json()
    assert host["role"] == "HOST"
    return host, headers_for(host["id"])


def test_create_user_rejects_empty_username(first_user_response):
    _, host_headers = create_host(first_user_response)

    resp = api_post(
        "/api/users",
        {"username": "", "nickname": "Should Not Exist"},
        headers=host_headers,
    )

    assert resp.status_code in (400, 422), (
        f"empty username must be rejected by the CreateUserRequest minLength contract, "
        f"got {resp.status_code}: {resp.text}"
    )

    users_resp = api_get("/api/users", headers=host_headers)
    assert users_resp.status_code == 200, users_resp.text
    usernames = [user["username"] for user in users_resp.json()]
    assert "" not in usernames
