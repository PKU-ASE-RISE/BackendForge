import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "test-api-key-chapter-move-page-book",
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


def test_chapter_move_updates_child_page_book_id():
    uid = uuid.uuid4().hex
    first_book = created_json(
        api_post("/api/books", {"name": f"Chapter Move Source {uid}"}),
        "source book",
    )
    second_book = created_json(
        api_post("/api/books", {"name": f"Chapter Move Target {uid}"}),
        "target book",
    )
    chapter = created_json(
        api_post(
            "/api/chapters",
            {"name": f"Chapter Move Container {uid}", "book_id": first_book["id"]},
        ),
        "chapter",
    )
    page = created_json(
        api_post(
            "/api/pages",
            {"name": f"Chapter Move Child {uid}", "chapter_id": chapter["id"], "html": "<p>child</p>"},
        ),
        "page",
    )
    assert page["book_id"] == first_book["id"]
    assert page["chapter_id"] == chapter["id"]

    move_response = api_put(f"/api/chapters/{chapter['id']}", {"book_id": second_book["id"]})
    assert move_response.status_code == 200
    moved_chapter = move_response.json()
    assert moved_chapter["book_id"] == second_book["id"]

    reloaded_page = api_get(f"/api/pages/{page['id']}")
    assert reloaded_page.status_code == 200
    page_detail = reloaded_page.json()
    assert page_detail["chapter_id"] == chapter["id"]
    assert page_detail["book_id"] == second_book["id"]

    reloaded_chapter = api_get(f"/api/chapters/{chapter['id']}")
    assert reloaded_chapter.status_code == 200
    child_pages = reloaded_chapter.json()["pages"]
    matching_pages = [item for item in child_pages if item["id"] == page["id"]]
    assert len(matching_pages) == 1
    assert matching_pages[0]["book_id"] == second_book["id"]
