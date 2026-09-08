import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"drp-doc-content-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_document_create_requires_content():
    h = headers()
    title = f"missing-content-{uuid.uuid4().hex}"

    resp = requests.post(
        f"{BASE_URL}/api/documents/",
        json={"title": title},
        headers=h,
        timeout=30,
    )

    assert resp.status_code == 400, resp.text

    listed = requests.get(
        f"{BASE_URL}/api/documents/",
        params={"title__icontains": title},
        headers=h,
        timeout=30,
    )
    assert listed.status_code == 200
    assert all(doc["title"] != title for doc in listed.json()["results"])
