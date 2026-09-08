import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin-user"


def headers_for(key):
    return {"X-Gotify-Key": key, "Content-Type": "application/json"}


def ensure_admin():
    requests.get(f"{BASE_URL}/current/user", headers=headers_for(ADMIN_KEY), timeout=30)


def api_get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)


def api_post(path, headers, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def assert_bad_request(response):
    assert response.status_code == 400
    data = response.json()
    assert data["errorCode"] == 400
    assert isinstance(data["error"], str)
    assert isinstance(data["errorDescription"], str)


def create_application(headers):
    name = f"pagination-bounds-{uuid.uuid4().hex}"
    response = api_post("/applications", headers=headers, json_data={"name": name})
    assert response.status_code == 200
    return response.json()


def test_message_pagination_query_bounds():
    ensure_admin()
    headers = headers_for(f"bounds-{uuid.uuid4().hex}")
    app = create_application(headers)

    paths = ["/messages", f"/applications/{app['id']}/messages"]
    invalid_params = [{"limit": 0}, {"limit": 201}, {"since": -1}]
    for path in paths:
        for params in invalid_params:
            response = api_get(path, headers=headers, params=params)
            assert_bad_request(response)
