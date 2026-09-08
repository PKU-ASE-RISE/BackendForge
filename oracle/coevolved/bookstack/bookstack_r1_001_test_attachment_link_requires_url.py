import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-attachment-link-url",
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


def test_attachment_link_requires_url():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Attachment URL Book {uid}"}),
        "book",
    )
    page = created_json(
        api_post(
            "/api/pages",
            {"name": f"Attachment URL Page {uid}", "book_id": book["id"], "html": "<p>content</p>"},
        ),
        "page",
    )

    attachment_name = f"Missing Link URL Attachment {uid}"
    response = api_post(
        "/api/attachments",
        {
            "name": attachment_name,
            "uploaded_to": page["id"],
            "type": "link",
        },
    )

    assert response.status_code == 422
    listing = api_get("/api/attachments")
    assert listing.status_code == 200
    names = [item["name"] for item in listing.json()["data"]]
    assert attachment_name not in names
