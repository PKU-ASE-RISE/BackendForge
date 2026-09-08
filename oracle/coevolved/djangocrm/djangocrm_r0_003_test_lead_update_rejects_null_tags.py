import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_lead_update_rejects_null_tags():
    headers = _headers()
    tag_name = f"lead-tag-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/leads",
        json={"source": "web", "tags": [tag_name]},
        headers=headers,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    lead_id = created.json()["id"]

    response = requests.put(
        f"{BASE_URL}/leads/{lead_id}",
        json={"tags": None},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 422

    reloaded = requests.get(
        f"{BASE_URL}/leads/{lead_id}",
        headers=headers,
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["tags"] == [tag_name]
