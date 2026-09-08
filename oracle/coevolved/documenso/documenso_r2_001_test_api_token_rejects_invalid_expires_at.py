import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": f"drp-r2-token-expiry-{uuid.uuid4().hex}",
}


def post(path, json_data=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_api_token_rejects_invalid_expires_at():
    token_name = f"BadExpiry-{uuid.uuid4().hex}"

    response = post("/api/tokens", {"name": token_name, "expiresAt": "not-a-date-time"})

    assert response.status_code in (400, 422), response.text
    tokens_response = get("/api/tokens")
    assert tokens_response.status_code == 200, tokens_response.text
    assert all(token["name"] != token_name for token in tokens_response.json())
