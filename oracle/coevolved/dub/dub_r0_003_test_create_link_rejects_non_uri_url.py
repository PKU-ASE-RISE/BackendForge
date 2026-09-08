import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def test_create_link_rejects_non_uri_url():
    response = requests.post(
        f"{BASE_URL}/links",
        headers={"X-API-Key": ADMIN_KEY},
        json={"url": "not-a-valid-uri", "slug": f"bad-url-{uuid.uuid4().hex[:10]}"},
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 422
