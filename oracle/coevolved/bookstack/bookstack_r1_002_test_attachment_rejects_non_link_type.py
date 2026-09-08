import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-attachment-type",
    "X-User-Id": "1",
    "Content-Type": "application/json",
}


def api_get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def created_json(response, entity_type):
    assert response.status_code == 200, f"Failed to create {entity_type}: {response.text}"
    return response.json()


def test_attachment_rejects_non_link_type():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Attachment Type Book {uid}"}),
        "book",
    )
    page = created_json(
        api_post(
            "/api/pages",
            {"name": f"Attachment Type Page {uid}", "book_id": book["id"], "html": "<p>content</p>"},
        ),
        "page",
    )

    invalid_name = f"Invalid File Attachment {uid}"
    response = api_post(
        "/api/attachments",
        {
            "name": invalid_name,
            "uploaded_to": page["id"],
            "type": "file",
            "link_url": "https://example.invalid/file.bin",
        },
    )

    assert response.status_code == 422
    listing = api_get("/api/attachments")
    assert listing.status_code == 200
    names = [item["name"] for item in listing.json()["data"]]
    assert invalid_name not in names
