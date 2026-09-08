import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def test_missing_link_url_validation_error_shape():
    response = requests.post(
        f"{BASE_URL}/links",
        headers={"X-API-Key": ADMIN_KEY},
        json={"slug": f"missing-url-{uuid.uuid4().hex[:10]}"},
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    assert "detail" not in body
    assert body["error"]["code"] == "unprocessable_entity"
    assert isinstance(body["error"].get("message"), str)
