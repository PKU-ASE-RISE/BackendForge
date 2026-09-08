import os

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-required-search",
    "X-User-Id": "1",
}


def test_search_query_required():
    response = requests.get(f"{BASE_URL}/api/search", headers=HEADERS, timeout=30)

    assert response.status_code == 422
    body = response.json()
    assert body.get("error") == "Validation failed"
