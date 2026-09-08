import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def test_create_tags_persists_unused_tags():
    prefix = f"unused-tag-{uuid.uuid4().hex}"
    tag_a = f"{prefix}-a"
    tag_b = f"{prefix}-b"

    create_resp = requests.post(
        f"{BASE_URL}/rest/v3/tags",
        headers=HEADERS,
        json={"tags": [tag_a, tag_b]},
        timeout=30,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()["tags"]["data"]
    assert tag_a in created
    assert tag_b in created

    list_resp = requests.get(
        f"{BASE_URL}/rest/v3/tags",
        headers=HEADERS,
        params={"searchTerm": prefix, "itemsPerPage": 50},
        timeout=30,
    )
    assert list_resp.status_code == 200, list_resp.text
    listed = list_resp.json()["tags"]["data"]
    assert tag_a in listed
    assert tag_b in listed
