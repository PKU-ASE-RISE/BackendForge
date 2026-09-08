import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-page-invalid-chapter-update",
    "X-User-Id": "1",
    "Content-Type": "application/json",
}


def api_get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def api_put(path, payload):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def created_json(response, entity_type):
    assert response.status_code == 200, f"Failed to create {entity_type}: {response.text}"
    return response.json()


def unknown_chapter_id():
    response = api_get("/api/chapters")
    assert response.status_code == 200
    used_ids = {item["id"] for item in response.json()["data"]}

    for _ in range(10):
        candidate = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
        if candidate in used_ids:
            continue
        if api_get(f"/api/chapters/{candidate}").status_code == 404:
            return candidate
    raise AssertionError("Could not find an unused chapter ID")


def test_update_page_rejects_unknown_chapter_without_side_effects():
    uid = uuid.uuid4().hex
    book = created_json(
        api_post("/api/books", {"name": f"Invalid Chapter Page Book {uid}"}),
        "book",
    )
    chapter = created_json(
        api_post(
            "/api/chapters",
            {"name": f"Invalid Chapter Page Parent {uid}", "book_id": book["id"]},
        ),
        "chapter",
    )
    page = created_json(
        api_post(
            "/api/pages",
            {"name": f"Invalid Chapter Page {uid}", "chapter_id": chapter["id"], "html": "<p>original</p>"},
        ),
        "page",
    )

    missing_chapter = unknown_chapter_id()
    update_response = api_put(
        f"/api/pages/{page['id']}",
        {"chapter_id": missing_chapter, "html": "<p>mutated despite invalid parent</p>"},
    )
    assert update_response.status_code == 422
    body = update_response.json()
    assert body["error"] == "Validation failed"
    assert "chapter_id" in body["details"]

    reloaded_page = api_get(f"/api/pages/{page['id']}")
    assert reloaded_page.status_code == 200
    page_detail = reloaded_page.json()
    assert page_detail["chapter_id"] == chapter["id"]
    assert page_detail["book_id"] == book["id"]
    assert page_detail["html"] == "<p>original</p>"

    revisions = api_get(f"/api/pages/{page['id']}/revisions")
    assert revisions.status_code == 200
    assert revisions.json()["total"] == 0
