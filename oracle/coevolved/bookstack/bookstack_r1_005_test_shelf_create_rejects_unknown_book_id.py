import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-shelf-books",
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


def unknown_book_id():
    response = api_get("/api/books")
    assert response.status_code == 200, f"Failed to list books: {response.text}"
    used_ids = {item["id"] for item in response.json()["data"]}

    for _ in range(10):
        candidate = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
        if candidate in used_ids:
            continue
        if api_get(f"/api/books/{candidate}").status_code == 404:
            return candidate
    raise AssertionError("Could not find an unused book ID")


def test_shelf_create_rejects_unknown_book_id():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Shelf Known Book {uid}"}),
        "book",
    )
    shelf_name = f"Shelf With Unknown Book {uid}"
    missing_book_id = unknown_book_id()

    response = api_post(
        "/api/shelves",
        {
            "name": shelf_name,
            "books": [book["id"], missing_book_id],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body.get("error") == "Validation failed"

    listing = api_get("/api/shelves")
    assert listing.status_code == 200
    names = [item["name"] for item in listing.json()["data"]]
    assert shelf_name not in names
