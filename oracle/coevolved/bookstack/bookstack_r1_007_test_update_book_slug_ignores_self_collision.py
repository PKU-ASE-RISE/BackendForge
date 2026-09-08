import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-book-slug-update",
    "X-User-Id": "1",
    "Content-Type": "application/json",
}


def api_get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def api_put(path, payload):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def test_update_book_slug_ignores_self_collision():
    uid = uuid.uuid4().hex
    original_name = f"Self Slug Book {uid}"
    expected_slug = f"self-slug-book-{uid}"

    created = api_post("/api/books", {"name": original_name, "description": "slug baseline"})
    assert created.status_code == 200
    book = created.json()
    assert book["slug"] == expected_slug

    updated_name = f"{original_name}!!!"
    updated = api_put(f"/api/books/{book['id']}", {"name": updated_name})
    assert updated.status_code == 200
    updated_book = updated.json()
    assert updated_book["name"] == updated_name
    assert updated_book["slug"] == expected_slug

    reloaded = api_get(f"/api/books/{book['id']}")
    assert reloaded.status_code == 200
    assert reloaded.json()["slug"] == expected_slug
