import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def test_bulk_update_rejects_non_string_link_ids():
    response = requests.patch(
        f"{BASE_URL}/links/bulk",
        headers={"X-API-Key": ADMIN_KEY},
        json={"linkIds": [12345], "data": {"archived": True}},
        timeout=REQUEST_TIMEOUT,
    )

    assert response.status_code == 422
