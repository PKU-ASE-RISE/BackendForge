import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_duplicate_topic_key_preserves_uniqueness():
    """A duplicate may be rejected or upserted; the business key stays unique."""
    business_key = "duplicate-" + uuid.uuid4().hex
    payload = {"key": business_key, "name": "Original topic"}
    first = requests.post(f"{BASE_URL}/v1/topics", headers=HEADERS, json=payload, timeout=30)
    assert first.status_code == 201, first.text
    second = requests.post(f"{BASE_URL}/v1/topics", headers=HEADERS, json=payload, timeout=30)
    assert second.status_code in (201, 422), second.text
    current = requests.get(f"{BASE_URL}/v1/topics/{business_key}", headers=HEADERS, timeout=30)
    assert current.status_code == 200
    assert current.json()["key"] == business_key
    assert current.json()["name"] == payload["name"]
    assert current.json()["id"] == first.json()["id"]
    # Enumerate every page so uniqueness is checked independently of GET-by-key.
    matches = []
    page = 0
    while True:
        listing = requests.get(f"{BASE_URL}/v1/topics", headers=HEADERS,
                               params={"page": page, "limit": 100}, timeout=30)
        assert listing.status_code == 200
        data = listing.json()
        matches.extend(item for item in data["data"] if item["key"] == business_key)
        if (page + 1) * data["limit"] >= data["total"]:
            break
        page += 1
        assert page < 1000, "Pagination did not terminate"
    assert len(matches) == 1
