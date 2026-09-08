import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": f"drp-doc-put-required-{uuid.uuid4().hex}",
    "Content-Type": "application/json",
}


def post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def put(path, payload):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_document_update_requires_title_and_content():
    original_title = f"original-{uuid.uuid4().hex}"
    original_content = f"content-{uuid.uuid4().hex}"
    created = post("/api/documents/", {"title": original_title, "content": original_content})
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]

    updated = put(f"/api/documents/{doc_id}/", {"title": f"missing-content-{uuid.uuid4().hex}"})
    assert updated.status_code == 400, updated.text

    reloaded = get(f"/api/documents/{doc_id}/")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["title"] == original_title
    assert reloaded.json()["content"] == original_content
