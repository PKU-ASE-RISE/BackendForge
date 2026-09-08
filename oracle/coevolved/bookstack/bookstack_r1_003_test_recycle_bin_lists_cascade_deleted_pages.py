import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-recycle-cascade",
    "X-User-Id": "1",
    "Content-Type": "application/json",
}


def api_get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def api_delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def created_json(response, entity_type):
    assert response.status_code == 200, f"Failed to create {entity_type}: {response.text}"
    return response.json()


def test_recycle_bin_lists_cascade_deleted_pages():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Recycle Book {uid}"}),
        "book",
    )
    chapter = created_json(
        api_post(
            "/api/chapters",
            {"name": f"Recycle Chapter {uid}", "book_id": book["id"]},
        ),
        "chapter",
    )
    page = created_json(
        api_post(
            "/api/pages",
            {"name": f"Recycle Page {uid}", "chapter_id": chapter["id"], "html": "<p>deleted child</p>"},
        ),
        "page",
    )

    delete_response = api_delete(f"/api/chapters/{chapter['id']}")
    assert delete_response.status_code == 200
    assert api_get(f"/api/chapters/{chapter['id']}").status_code == 404
    assert api_get(f"/api/pages/{page['id']}").status_code == 404

    recycle_response = api_get("/api/recycle-bin")
    assert recycle_response.status_code == 200
    recycle_items = recycle_response.json()["data"]

    chapter_items = [
        item for item in recycle_items
        if item["entity_type"] == "chapter" and item["entity_id"] == chapter["id"]
    ]
    page_items = [
        item for item in recycle_items
        if item["entity_type"] == "page" and item["entity_id"] == page["id"]
    ]
    assert len(chapter_items) == 1
    assert len(page_items) == 1
    assert page_items[0]["entity_name"] == f"Recycle Page {uid}"
