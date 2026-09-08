import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-shelf-association-delete",
    "X-User-Id": "1",
    "Content-Type": "application/json",
}


def api_get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def api_put(path, payload=None):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def api_delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def created_json(response, entity_type):
    assert response.status_code == 200, f"Failed to create {entity_type}: {response.text}"
    return response.json()


def test_shelf_delete_removes_book_associations_on_restore():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Shelf Association Book {uid}"}),
        "book",
    )
    shelf = created_json(
        api_post(
            "/api/shelves",
            {"name": f"Shelf Association Container {uid}", "books": [book["id"]]},
        ),
        "shelf",
    )
    assert [item["id"] for item in shelf["books"]] == [book["id"]]

    delete_response = api_delete(f"/api/shelves/{shelf['id']}")
    assert delete_response.status_code == 200
    assert api_get(f"/api/shelves/{shelf['id']}").status_code == 404
    assert api_get(f"/api/books/{book['id']}").status_code == 200

    recycle_response = api_get("/api/recycle-bin")
    assert recycle_response.status_code == 200
    matching_bins = [
        item for item in recycle_response.json()["data"]
        if item["entity_type"] == "shelf" and item["entity_id"] == shelf["id"]
    ]
    assert len(matching_bins) == 1

    restore_response = api_put(f"/api/recycle-bin/{matching_bins[0]['id']}/restore")
    assert restore_response.status_code == 200

    restored_shelf = api_get(f"/api/shelves/{shelf['id']}")
    assert restored_shelf.status_code == 200
    assert restored_shelf.json()["books"] == []
    assert api_get(f"/api/books/{book['id']}").status_code == 200
