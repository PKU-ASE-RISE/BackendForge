import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def test_create_link_rejects_non_string_tag_ids():
    response = requests.post(
        f"{BASE_URL}/links",
        headers={"X-API-Key": ADMIN_KEY},
        json={
            "url": "https://example.com/tag-type",
            "slug": f"bad-tag-{uuid.uuid4().hex[:10]}",
            "tags": [12345],
        },
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 422
