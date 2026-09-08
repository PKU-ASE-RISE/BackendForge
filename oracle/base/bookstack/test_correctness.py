"""
BackendForge — Comprehensive Correctness Tests for BookStack Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

# Auth headers — trusted directly, no DB lookup
API_KEY = "test-api-key-12345"
USER_ID = "1"
USER2_ID = "2"

HEADERS = {
    "X-Api-Key": API_KEY,
    "X-User-Id": USER_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-Api-Key": API_KEY,
    "X-User-Id": USER2_ID,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


def missing_entity_id(resource):
    """Return an unused, runtime-verified ID for an entity collection."""
    response = api_get(f"/api/{resource}")
    assert response.status_code == 200, f"Failed to list {resource}: {response.text}"
    used_ids = {item["id"] for item in response.json()["data"]}

    for _ in range(10):
        candidate = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
        if candidate in used_ids:
            continue
        probe = api_get(f"/api/{resource}/{candidate}")
        if probe.status_code == 404:
            return candidate
    raise AssertionError(f"Could not find an unused {resource} ID")


def missing_recycle_bin_id():
    """Return an ID not present in the complete recycle-bin listing."""
    response = api_get("/api/recycle-bin")
    assert response.status_code == 200, f"Failed to list recycle bin: {response.text}"
    used_ids = {item["id"] for item in response.json()["data"]}

    for _ in range(10):
        candidate = 1_000_000_000 + uuid.uuid4().int % 1_000_000_000
        if candidate not in used_ids:
            return candidate
    raise AssertionError("Could not find an unused recycle-bin ID")


# ── Helpers to create test entities ──

def create_book(name=None, description="", tags=None):
    name = name or f"Book-{uuid.uuid4().hex}"
    payload = {"name": name, "description": description}
    if tags:
        payload["tags"] = tags
    resp = api_post("/api/books", payload)
    assert resp.status_code == 200, f"Failed to create book: {resp.text}"
    return resp.json()


def create_chapter(book_id, name=None, priority=0, description="", tags=None):
    name = name or f"Chapter-{uuid.uuid4().hex}"
    payload = {"name": name, "book_id": book_id, "priority": priority, "description": description}
    if tags:
        payload["tags"] = tags
    resp = api_post("/api/chapters", payload)
    assert resp.status_code == 200, f"Failed to create chapter: {resp.text}"
    return resp.json()


def create_page(name=None, book_id=None, chapter_id=None, html="", priority=0, tags=None):
    name = name or f"Page-{uuid.uuid4().hex}"
    payload = {"name": name, "html": html, "priority": priority}
    if chapter_id:
        payload["chapter_id"] = chapter_id
    elif book_id:
        payload["book_id"] = book_id
    if tags:
        payload["tags"] = tags
    resp = api_post("/api/pages", payload)
    assert resp.status_code == 200, f"Failed to create page: {resp.text}"
    return resp.json()


def create_shelf(name=None, description="", books=None, tags=None):
    name = name or f"Shelf-{uuid.uuid4().hex}"
    payload = {"name": name, "description": description}
    if books is not None:
        payload["books"] = books
    if tags:
        payload["tags"] = tags
    resp = api_post("/api/shelves", payload)
    assert resp.status_code == 200, f"Failed to create shelf: {resp.text}"
    return resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/books", headers={"X-User-Id": "1"}, timeout=30)
        assert resp.status_code == 401

    def test_missing_user_id_returns_401(self):
        """Requests without X-User-Id should return 401."""
        resp = requests.get(f"{BASE_URL}/api/books", headers={"X-Api-Key": "key"}, timeout=30)
        assert resp.status_code == 401

    def test_no_headers_returns_401(self):
        """Requests without any auth headers should return 401."""
        resp = requests.get(f"{BASE_URL}/api/books", timeout=30)
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        """Empty X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/books", headers={"X-Api-Key": "", "X-User-Id": "1"}, timeout=30)
        assert resp.status_code == 401

    def test_valid_auth_returns_200(self):
        """Valid auth headers should work."""
        resp = api_get("/api/books")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Shelves CRUD
# ════════════════════════════════════════════════════════════════════


class TestShelvesCRUD:

    def test_create_shelf(self):
        shelf = create_shelf(name=f"TestShelf-{UNIQUE}", description="A test shelf")
        assert shelf["name"] == f"TestShelf-{UNIQUE}"
        assert shelf["description"] == "A test shelf"
        assert "id" in shelf
        assert "slug" in shelf
        assert "created_at" in shelf
        assert "updated_at" in shelf
        assert shelf["created_by"] == int(USER_ID)

    def test_create_shelf_name_required(self):
        resp = api_post("/api/shelves", {"description": "no name"})
        assert resp.status_code == 422

    def test_list_shelves(self):
        create_shelf(name=f"ListShelf-{UNIQUE}")
        resp = api_get("/api/shelves")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        assert data["total"] >= 1
        names = [s["name"] for s in data["data"]]
        assert f"ListShelf-{UNIQUE}" in names

    def test_get_shelf(self):
        shelf = create_shelf(name=f"GetShelf-{UNIQUE}")
        resp = api_get(f"/api/shelves/{shelf['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == shelf["id"]
        assert detail["name"] == f"GetShelf-{UNIQUE}"
        assert "books" in detail
        assert isinstance(detail["books"], list)

    def test_update_shelf(self):
        shelf = create_shelf(name=f"UpdShelf-{UNIQUE}")
        resp = api_put(f"/api/shelves/{shelf['id']}", {
            "name": f"UpdShelfNew-{UNIQUE}",
            "description": "Updated desc"
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdShelfNew-{UNIQUE}"
        assert updated["description"] == "Updated desc"

    def test_delete_shelf(self):
        shelf = create_shelf(name=f"DelShelf-{UNIQUE}")
        resp = api_delete(f"/api/shelves/{shelf['id']}")
        assert resp.status_code == 200

        # Should no longer appear in list
        list_resp = api_get("/api/shelves")
        ids = [s["id"] for s in list_resp.json()["data"]]
        assert shelf["id"] not in ids

    def test_get_deleted_shelf_returns_404(self):
        shelf = create_shelf(name=f"Del404Shelf-{UNIQUE}")
        api_delete(f"/api/shelves/{shelf['id']}")
        resp = api_get(f"/api/shelves/{shelf['id']}")
        assert resp.status_code == 404

    def test_get_nonexistent_shelf_returns_404(self):
        missing_id = missing_entity_id("shelves")
        resp = api_get(f"/api/shelves/{missing_id}")
        assert resp.status_code == 404

    def test_shelf_with_books(self):
        """Shelf can reference books in order."""
        book1 = create_book(name=f"ShelfBook1-{UNIQUE}")
        book2 = create_book(name=f"ShelfBook2-{UNIQUE}")
        shelf = create_shelf(name=f"BookShelf-{UNIQUE}", books=[book2["id"], book1["id"]])

        resp = api_get(f"/api/shelves/{shelf['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert len(detail["books"]) == 2
        assert detail["books"][0]["id"] == book2["id"]
        assert detail["books"][1]["id"] == book1["id"]


# ════════════════════════════════════════════════════════════════════
# PART 3: Books CRUD
# ════════════════════════════════════════════════════════════════════


class TestBooksCRUD:

    def test_create_book(self):
        book = create_book(name=f"TestBook-{UNIQUE}", description="A test book")
        assert book["name"] == f"TestBook-{UNIQUE}"
        assert book["description"] == "A test book"
        assert "id" in book
        assert "slug" in book
        assert "created_at" in book
        assert book["created_by"] == int(USER_ID)

    def test_create_book_name_required(self):
        resp = api_post("/api/books", {"description": "no name"})
        assert resp.status_code == 422

    def test_list_books(self):
        create_book(name=f"ListBook-{UNIQUE}")
        resp = api_get("/api/books")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_book(self):
        book = create_book(name=f"GetBook-{UNIQUE}")
        resp = api_get(f"/api/books/{book['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == book["id"]
        assert "contents" in detail
        assert isinstance(detail["contents"], list)

    def test_get_book_contents_include_chapters_and_pages(self):
        """Book detail should show chapters and direct pages."""
        book = create_book(name=f"ContBook-{UNIQUE}")
        ch = create_chapter(book["id"], name=f"ContChap-{UNIQUE}")
        page = create_page(name=f"DirectPage-{UNIQUE}", book_id=book["id"])

        resp = api_get(f"/api/books/{book['id']}")
        detail = resp.json()
        contents = detail["contents"]
        types = [c["type"] for c in contents]
        assert "chapter" in types
        assert "page" in types

    def test_update_book(self):
        book = create_book(name=f"UpdBook-{UNIQUE}")
        resp = api_put(f"/api/books/{book['id']}", {
            "name": f"UpdBookNew-{UNIQUE}",
            "description": "New desc"
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdBookNew-{UNIQUE}"
        assert updated["description"] == "New desc"

    def test_delete_book(self):
        book = create_book(name=f"DelBook-{UNIQUE}")
        resp = api_delete(f"/api/books/{book['id']}")
        assert resp.status_code == 200

        # Should not appear in list
        list_resp = api_get("/api/books")
        ids = [b["id"] for b in list_resp.json()["data"]]
        assert book["id"] not in ids

    def test_get_nonexistent_book_returns_404(self):
        missing_id = missing_entity_id("books")
        resp = api_get(f"/api/books/{missing_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Chapters CRUD
# ════════════════════════════════════════════════════════════════════


class TestChaptersCRUD:

    def test_create_chapter(self):
        book = create_book(name=f"ChBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"TestChapter-{UNIQUE}", description="Ch desc")
        assert chapter["name"] == f"TestChapter-{UNIQUE}"
        assert chapter["description"] == "Ch desc"
        assert chapter["book_id"] == book["id"]
        assert "id" in chapter
        assert "slug" in chapter

    def test_create_chapter_requires_book_id(self):
        resp = api_post("/api/chapters", {"name": "No book"})
        assert resp.status_code == 422

    def test_create_chapter_invalid_book_id(self):
        missing_book_id = missing_entity_id("books")
        resp = api_post("/api/chapters", {"name": "Bad book", "book_id": missing_book_id})
        assert resp.status_code == 422

    def test_list_chapters(self):
        book = create_book(name=f"ChListBook-{UNIQUE}")
        create_chapter(book["id"], name=f"ListChap-{UNIQUE}")
        resp = api_get("/api/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_chapter(self):
        book = create_book(name=f"ChGetBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"GetChap-{UNIQUE}")
        resp = api_get(f"/api/chapters/{chapter['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == chapter["id"]
        assert "pages" in detail
        assert isinstance(detail["pages"], list)

    def test_update_chapter(self):
        book = create_book(name=f"ChUpdBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"UpdChap-{UNIQUE}")
        resp = api_put(f"/api/chapters/{chapter['id']}", {
            "name": f"UpdChapNew-{UNIQUE}",
            "description": "Updated ch"
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdChapNew-{UNIQUE}"
        assert updated["description"] == "Updated ch"

    def test_delete_chapter(self):
        book = create_book(name=f"ChDelBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"DelChap-{UNIQUE}")
        resp = api_delete(f"/api/chapters/{chapter['id']}")
        assert resp.status_code == 200

        # Should not appear in list
        list_resp = api_get("/api/chapters")
        ids = [c["id"] for c in list_resp.json()["data"]]
        assert chapter["id"] not in ids

    def test_get_nonexistent_chapter_returns_404(self):
        missing_id = missing_entity_id("chapters")
        resp = api_get(f"/api/chapters/{missing_id}")
        assert resp.status_code == 404

    def test_chapter_priority(self):
        """Chapters can have priority for ordering."""
        book = create_book(name=f"PriBook-{UNIQUE}")
        ch1 = create_chapter(book["id"], name=f"PriChap1-{UNIQUE}", priority=10)
        ch2 = create_chapter(book["id"], name=f"PriChap2-{UNIQUE}", priority=5)

        resp = api_get(f"/api/books/{book['id']}")
        contents = resp.json()["contents"]
        chapters = [c for c in contents if c["type"] == "chapter"]
        # Priority 5 should come before 10
        assert len(chapters) >= 2
        priorities = [c["priority"] for c in chapters]
        assert priorities == sorted(priorities)


# ════════════════════════════════════════════════════════════════════
# PART 5: Pages CRUD
# ════════════════════════════════════════════════════════════════════


class TestPagesCRUD:

    def test_create_page_in_chapter(self):
        book = create_book(name=f"PgBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"PgChap-{UNIQUE}")
        page = create_page(name=f"TestPage-{UNIQUE}", chapter_id=chapter["id"], html="<p>Hello</p>")
        assert page["name"] == f"TestPage-{UNIQUE}"
        assert page["html"] == "<p>Hello</p>"
        assert page["chapter_id"] == chapter["id"]
        assert page["book_id"] == book["id"]
        assert "id" in page
        assert "slug" in page

    def test_create_page_in_book_directly(self):
        book = create_book(name=f"DirectPgBook-{UNIQUE}")
        page = create_page(name=f"DirectPage-{UNIQUE}", book_id=book["id"], html="<p>Direct</p>")
        assert page["book_id"] == book["id"]
        assert page.get("chapter_id") is None or page.get("chapter_id") == 0

    def test_create_page_requires_parent(self):
        """Page must have either book_id or chapter_id."""
        resp = api_post("/api/pages", {"name": "Orphan page", "html": "<p>X</p>"})
        assert resp.status_code == 422

    def test_create_page_name_required(self):
        book = create_book(name=f"NmBook-{UNIQUE}")
        resp = api_post("/api/pages", {"book_id": book["id"], "html": "<p>X</p>"})
        assert resp.status_code == 422

    def test_list_pages(self):
        book = create_book(name=f"PgListBook-{UNIQUE}")
        create_page(name=f"ListPage-{UNIQUE}", book_id=book["id"])
        resp = api_get("/api/pages")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_page(self):
        book = create_book(name=f"PgGetBook-{UNIQUE}")
        page = create_page(name=f"GetPage-{UNIQUE}", book_id=book["id"], html="<p>Content</p>")
        resp = api_get(f"/api/pages/{page['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == page["id"]
        assert detail["html"] == "<p>Content</p>"
        assert "tags" in detail

    def test_update_page(self):
        book = create_book(name=f"PgUpdBook-{UNIQUE}")
        page = create_page(name=f"UpdPage-{UNIQUE}", book_id=book["id"], html="<p>Old</p>")
        resp = api_put(f"/api/pages/{page['id']}", {
            "name": f"UpdPageNew-{UNIQUE}",
            "html": "<p>New content</p>"
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdPageNew-{UNIQUE}"
        assert updated["html"] == "<p>New content</p>"

    def test_delete_page(self):
        book = create_book(name=f"PgDelBook-{UNIQUE}")
        page = create_page(name=f"DelPage-{UNIQUE}", book_id=book["id"])
        resp = api_delete(f"/api/pages/{page['id']}")
        assert resp.status_code == 200

        # Should not appear in list
        list_resp = api_get("/api/pages")
        ids = [p["id"] for p in list_resp.json()["data"]]
        assert page["id"] not in ids

    def test_get_nonexistent_page_returns_404(self):
        missing_id = missing_entity_id("pages")
        resp = api_get(f"/api/pages/{missing_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Slugs
# ════════════════════════════════════════════════════════════════════


class TestSlugs:

    def test_slug_generated_from_name(self):
        """Slug should be auto-generated from name."""
        unique_name = f"My Test Book {UNIQUE}"
        book = create_book(name=unique_name)
        expected_slug = f"my-test-book-{UNIQUE}"
        assert book["slug"] == expected_slug

    def test_slug_handles_special_chars(self):
        """Slug should strip special characters."""
        book = create_book(name="Hello World! @#$%")
        assert "hello-world" in book["slug"]
        assert "@" not in book["slug"]
        assert "#" not in book["slug"]

    def test_slug_uniqueness(self):
        """Duplicate names should generate unique slugs with suffix."""
        book1 = create_book(name=f"DupSlug-{UNIQUE}")
        book2 = create_book(name=f"DupSlug-{UNIQUE}")
        assert book1["slug"] != book2["slug"]
        # Second should have a suffix
        assert book2["slug"].startswith(book1["slug"])


# ════════════════════════════════════════════════════════════════════
# PART 7: Tags
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_with_tags(self):
        """Entities can be created with tags."""
        tags = [{"name": "status", "value": "draft"}, {"name": "priority", "value": "high"}]
        book = create_book(name=f"TagBook-{UNIQUE}", tags=tags)
        resp = api_get(f"/api/books/{book['id']}")
        detail = resp.json()
        assert "tags" in detail
        assert len(detail["tags"]) == 2
        tag_names = [t["name"] for t in detail["tags"]]
        assert "status" in tag_names
        assert "priority" in tag_names

    def test_update_replaces_tags(self):
        """Updating tags replaces all existing tags."""
        tags = [{"name": "old", "value": "tag"}]
        book = create_book(name=f"TagUpd-{UNIQUE}", tags=tags)

        new_tags = [{"name": "new", "value": "tag"}]
        api_put(f"/api/books/{book['id']}", {"tags": new_tags})

        resp = api_get(f"/api/books/{book['id']}")
        detail = resp.json()
        assert len(detail["tags"]) == 1
        assert detail["tags"][0]["name"] == "new"
        assert detail["tags"][0]["value"] == "tag"

    def test_tags_on_pages(self):
        book = create_book(name=f"PgTagBook-{UNIQUE}")
        tags = [{"name": "status", "value": "published"}]
        page = create_page(name=f"TagPage-{UNIQUE}", book_id=book["id"], tags=tags)
        resp = api_get(f"/api/pages/{page['id']}")
        detail = resp.json()
        assert len(detail["tags"]) == 1
        assert detail["tags"][0]["name"] == "status"

    def test_tags_on_shelves(self):
        tags = [{"name": "category", "value": "science"}]
        shelf = create_shelf(name=f"TagShelf-{UNIQUE}", tags=tags)
        resp = api_get(f"/api/shelves/{shelf['id']}")
        detail = resp.json()
        assert len(detail["tags"]) == 1
        assert detail["tags"][0]["name"] == "category"

    def test_tags_on_chapters(self):
        book = create_book(name=f"ChTagBook-{UNIQUE}")
        tags = [{"name": "level", "value": "beginner"}]
        chapter = create_chapter(book["id"], name=f"TagChap-{UNIQUE}", tags=tags)
        resp = api_get(f"/api/chapters/{chapter['id']}")
        detail = resp.json()
        assert len(detail["tags"]) == 1
        assert detail["tags"][0]["name"] == "level"


# ════════════════════════════════════════════════════════════════════
# PART 8: Page Revisions
# ════════════════════════════════════════════════════════════════════


class TestRevisions:

    def test_update_creates_revision(self):
        """Updating a page should create a revision."""
        book = create_book(name=f"RevBook-{UNIQUE}")
        page = create_page(name=f"RevPage-{UNIQUE}", book_id=book["id"], html="<p>Version 1</p>")

        # Update the page
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 2</p>"})

        # Check revisions
        resp = api_get(f"/api/pages/{page['id']}/revisions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_revision_stores_previous_content(self):
        """Revision should store the content BEFORE the update."""
        book = create_book(name=f"RevPrev-{UNIQUE}")
        page = create_page(name=f"RevPrevPage-{UNIQUE}", book_id=book["id"], html="<p>Original</p>")

        # Update
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Updated</p>"})

        # Get revisions
        resp = api_get(f"/api/pages/{page['id']}/revisions")
        revisions = resp.json()["data"]
        assert len(revisions) >= 1
        # The revision should have the original content
        rev = revisions[0]
        assert rev["html"] == "<p>Original</p>"

    def test_get_specific_revision(self):
        """Can get a specific revision by ID."""
        book = create_book(name=f"RevSpec-{UNIQUE}")
        page = create_page(name=f"RevSpecPage-{UNIQUE}", book_id=book["id"], html="<p>First</p>")
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Second</p>"})

        revisions_resp = api_get(f"/api/pages/{page['id']}/revisions")
        revisions = revisions_resp.json()["data"]
        rev_id = revisions[0]["id"]

        resp = api_get(f"/api/pages/{page['id']}/revisions/{rev_id}")
        assert resp.status_code == 200
        rev = resp.json()
        assert rev["id"] == rev_id
        assert "html" in rev
        assert "name" in rev

    def test_restore_revision(self):
        """Restoring a revision replaces current page content."""
        book = create_book(name=f"RevRest-{UNIQUE}")
        page = create_page(name=f"RestorePage-{UNIQUE}", book_id=book["id"], html="<p>Original</p>")

        # Update twice
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 2</p>"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 3</p>"})

        # Get revision with original content
        revisions_resp = api_get(f"/api/pages/{page['id']}/revisions")
        revisions = revisions_resp.json()["data"]
        # Find revision with original content (should be earliest)
        original_rev = None
        for rev in revisions:
            if rev["html"] == "<p>Original</p>":
                original_rev = rev
                break
        assert original_rev is not None, f"Could not find original revision. Revisions: {revisions}"

        # Restore it
        resp = api_put(f"/api/pages/{page['id']}/revisions/{original_rev['id']}/restore")
        assert resp.status_code == 200

        # Page should now have original content
        page_resp = api_get(f"/api/pages/{page['id']}")
        assert page_resp.json()["html"] == "<p>Original</p>"

    def test_restore_creates_new_revision(self):
        """Restoring creates a new revision (of what was replaced)."""
        book = create_book(name=f"RevRestNew-{UNIQUE}")
        page = create_page(name=f"RestNewPage-{UNIQUE}", book_id=book["id"], html="<p>V1</p>")
        api_put(f"/api/pages/{page['id']}", {"html": "<p>V2</p>"})

        # Get count before restore
        revisions_before = api_get(f"/api/pages/{page['id']}/revisions").json()["total"]

        # Get the first revision and restore
        revisions = api_get(f"/api/pages/{page['id']}/revisions").json()["data"]
        rev_id = revisions[0]["id"]
        api_put(f"/api/pages/{page['id']}/revisions/{rev_id}/restore")

        # Count should increase
        revisions_after = api_get(f"/api/pages/{page['id']}/revisions").json()["total"]
        assert revisions_after > revisions_before

    def test_revisions_newest_first(self):
        """Revisions should be listed newest first."""
        book = create_book(name=f"RevOrd-{UNIQUE}")
        page = create_page(name=f"RevOrdPage-{UNIQUE}", book_id=book["id"], html="<p>V1</p>")
        api_put(f"/api/pages/{page['id']}", {"html": "<p>V2</p>"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>V3</p>"})

        resp = api_get(f"/api/pages/{page['id']}/revisions")
        revisions = resp.json()["data"]
        assert len(revisions) >= 2
        # Newest first means higher revision_number comes first
        for i in range(len(revisions) - 1):
            assert revisions[i]["revision_number"] >= revisions[i+1]["revision_number"]

    def test_revision_nonexistent_page_404(self):
        missing_page_id = missing_entity_id("pages")
        resp = api_get(f"/api/pages/{missing_page_id}/revisions")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Recycle Bin
# ════════════════════════════════════════════════════════════════════


class TestRecycleBin:

    def test_deleted_item_appears_in_bin(self):
        """Deleted items should appear in the recycle bin."""
        book = create_book(name=f"BinBook-{UNIQUE}")
        api_delete(f"/api/books/{book['id']}")

        resp = api_get("/api/recycle-bin")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        # Find our deleted book
        found = any(
            item["entity_type"] == "book" and item["entity_id"] == book["id"]
            for item in data["data"]
        )
        assert found, f"Deleted book not found in recycle bin"

    def test_restore_from_bin(self):
        """Restoring brings item back."""
        book = create_book(name=f"RestoreBin-{UNIQUE}")
        api_delete(f"/api/books/{book['id']}")

        # Find in recycle bin
        bin_resp = api_get("/api/recycle-bin")
        bin_item = None
        for item in bin_resp.json()["data"]:
            if item["entity_type"] == "book" and item["entity_id"] == book["id"]:
                bin_item = item
                break
        assert bin_item is not None

        # Restore
        resp = api_put(f"/api/recycle-bin/{bin_item['id']}/restore")
        assert resp.status_code == 200

        # Book should be accessible again
        book_resp = api_get(f"/api/books/{book['id']}")
        assert book_resp.status_code == 200
        assert book_resp.json()["name"] == f"RestoreBin-{UNIQUE}"

    def test_permanent_delete_from_bin(self):
        """Permanently deleting removes item completely."""
        book = create_book(name=f"PermDel-{UNIQUE}")
        api_delete(f"/api/books/{book['id']}")

        # Find in recycle bin
        bin_resp = api_get("/api/recycle-bin")
        bin_item = None
        for item in bin_resp.json()["data"]:
            if item["entity_type"] == "book" and item["entity_id"] == book["id"]:
                bin_item = item
                break
        assert bin_item is not None

        # Permanently delete
        resp = api_delete(f"/api/recycle-bin/{bin_item['id']}")
        assert resp.status_code == 200

        # Should no longer be in recycle bin
        bin_resp2 = api_get("/api/recycle-bin")
        ids = [item["id"] for item in bin_resp2.json()["data"]]
        assert bin_item["id"] not in ids

        # Should not be accessible
        book_resp = api_get(f"/api/books/{book['id']}")
        assert book_resp.status_code == 404

    def test_recycle_bin_nonexistent_item_404(self):
        missing_id = missing_recycle_bin_id()
        resp = api_put(f"/api/recycle-bin/{missing_id}/restore")
        assert resp.status_code == 404

    def test_recycle_bin_has_metadata(self):
        """Recycle bin items should have entity metadata."""
        book = create_book(name=f"BinMeta-{UNIQUE}")
        api_delete(f"/api/books/{book['id']}")

        bin_resp = api_get("/api/recycle-bin")
        bin_item = None
        for item in bin_resp.json()["data"]:
            if item["entity_type"] == "book" and item["entity_id"] == book["id"]:
                bin_item = item
                break
        assert bin_item is not None
        assert "deleted_by" in bin_item
        assert "deleted_at" in bin_item
        assert bin_item["entity_name"] == f"BinMeta-{UNIQUE}"


# ════════════════════════════════════════════════════════════════════
# PART 10: Cascade Deletes and Restores
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_book_cascades_to_chapters_and_pages(self):
        """Deleting a book should soft-delete its chapters and pages."""
        book = create_book(name=f"CascBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"CascChap-{UNIQUE}")
        page = create_page(name=f"CascPage-{UNIQUE}", chapter_id=chapter["id"])

        api_delete(f"/api/books/{book['id']}")

        # Chapter should not be listable
        ch_resp = api_get(f"/api/chapters/{chapter['id']}")
        assert ch_resp.status_code == 404

        # Page should not be listable
        pg_resp = api_get(f"/api/pages/{page['id']}")
        assert pg_resp.status_code == 404

    def test_delete_chapter_cascades_to_pages(self):
        """Deleting a chapter should soft-delete its pages."""
        book = create_book(name=f"CascChBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"CascChChap-{UNIQUE}")
        page = create_page(name=f"CascChPage-{UNIQUE}", chapter_id=chapter["id"])

        api_delete(f"/api/chapters/{chapter['id']}")

        # Page should not be listable
        pg_resp = api_get(f"/api/pages/{page['id']}")
        assert pg_resp.status_code == 404

    def test_delete_shelf_does_not_delete_books(self):
        """Deleting a shelf should NOT delete its books."""
        book = create_book(name=f"ShelfNoCasc-{UNIQUE}")
        shelf = create_shelf(name=f"NoCascShelf-{UNIQUE}", books=[book["id"]])

        api_delete(f"/api/shelves/{shelf['id']}")

        # Book should still be accessible
        book_resp = api_get(f"/api/books/{book['id']}")
        assert book_resp.status_code == 200

    def test_restore_book_restores_children(self):
        """Restoring a book should restore cascade-deleted chapters and pages."""
        book = create_book(name=f"RestCascBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"RestCascChap-{UNIQUE}")
        page = create_page(name=f"RestCascPage-{UNIQUE}", chapter_id=chapter["id"])

        api_delete(f"/api/books/{book['id']}")

        # Find book in recycle bin
        bin_resp = api_get("/api/recycle-bin")
        bin_item = None
        for item in bin_resp.json()["data"]:
            if item["entity_type"] == "book" and item["entity_id"] == book["id"]:
                bin_item = item
                break
        assert bin_item is not None

        # Restore
        api_put(f"/api/recycle-bin/{bin_item['id']}/restore")

        # Chapter and page should be accessible again
        ch_resp = api_get(f"/api/chapters/{chapter['id']}")
        assert ch_resp.status_code == 200

        pg_resp = api_get(f"/api/pages/{page['id']}")
        assert pg_resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 11: Search
# ════════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_finds_pages_by_name(self):
        """Search should find pages by name."""
        book = create_book(name=f"SrchBook-{UNIQUE}")
        page = create_page(name=f"Findable-{UNIQUE}", book_id=book["id"], html="<p>nothing special</p>")

        resp = api_get("/api/search", params={"query": f"Findable-{UNIQUE}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        found = any(r["name"] == f"Findable-{UNIQUE}" for r in data["data"])
        assert found, f"Page not found in search results: {data}"

    def test_search_finds_pages_by_content(self):
        """Search should find pages by HTML content."""
        book = create_book(name=f"SrchContBook-{UNIQUE}")
        unique_content = f"uniquecontent{UNIQUE}"
        create_page(name=f"ContentPage-{UNIQUE}", book_id=book["id"], html=f"<p>{unique_content}</p>")

        resp = api_get("/api/search", params={"query": unique_content})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_finds_books(self):
        """Search should find books by name."""
        unique_name = f"SearchableBook-{UNIQUE}"
        create_book(name=unique_name)

        resp = api_get("/api/search", params={"query": unique_name})
        assert resp.status_code == 200
        data = resp.json()
        found = any(r["type"] == "book" and r["name"] == unique_name for r in data["data"])
        assert found

    def test_search_finds_chapters(self):
        """Search should find chapters."""
        book = create_book(name=f"SrchChBook-{UNIQUE}")
        unique_name = f"SearchableChapter-{UNIQUE}"
        create_chapter(book["id"], name=unique_name)

        resp = api_get("/api/search", params={"query": unique_name})
        assert resp.status_code == 200
        data = resp.json()
        found = any(r["type"] == "chapter" and r["name"] == unique_name for r in data["data"])
        assert found

    def test_search_finds_shelves(self):
        """Search should find shelves."""
        unique_name = f"SearchableShelf-{UNIQUE}"
        create_shelf(name=unique_name)

        resp = api_get("/api/search", params={"query": unique_name})
        assert resp.status_code == 200
        data = resp.json()
        found = any(r["type"] == "shelf" and r["name"] == unique_name for r in data["data"])
        assert found

    def test_search_results_have_score(self):
        """Search results should include a score field."""
        book = create_book(name=f"ScoreBook-{UNIQUE}")
        create_page(name=f"ScorePage-{UNIQUE}", book_id=book["id"])

        resp = api_get("/api/search", params={"query": f"ScorePage-{UNIQUE}"})
        data = resp.json()
        if data["total"] > 0:
            for result in data["data"]:
                assert "score" in result
                assert "type" in result
                assert "id" in result
                assert "name" in result

    def test_search_name_match_ranks_higher(self):
        """Title matches should rank higher than content matches."""
        book = create_book(name=f"RankBook-{UNIQUE}")
        keyword = f"rankkeyword{UNIQUE}"
        # Page with keyword in name
        create_page(name=keyword, book_id=book["id"], html="<p>Unrelated content</p>")
        # Page with keyword in content only
        create_page(name=f"OtherPage-{UNIQUE}", book_id=book["id"], html=f"<p>{keyword}</p>")

        resp = api_get("/api/search", params={"query": keyword})
        data = resp.json()
        assert data["total"] >= 2
        # First result should be the title match (higher score)
        assert data["data"][0]["name"] == keyword

    def test_search_empty_query_returns_empty(self):
        """Empty search query should return empty results or error."""
        resp = api_get("/api/search", params={"query": ""})
        # Either return empty results or 422
        assert resp.status_code in [200, 422]
        if resp.status_code == 200:
            assert resp.json()["total"] == 0

    def test_search_no_match(self):
        """Search for non-existent content returns empty."""
        query = f"zzz-nonexistent-{uuid.uuid4().hex}"
        resp = api_get("/api/search", params={"query": query})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 12: Attachments
# ════════════════════════════════════════════════════════════════════


class TestAttachments:

    def test_create_link_attachment(self):
        book = create_book(name=f"AttBook-{UNIQUE}")
        page = create_page(name=f"AttPage-{UNIQUE}", book_id=book["id"])

        resp = api_post("/api/attachments", {
            "name": f"TestAttach-{UNIQUE}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com"
        })
        assert resp.status_code == 200
        att = resp.json()
        assert att["name"] == f"TestAttach-{UNIQUE}"
        assert att["uploaded_to"] == page["id"]
        assert att["type"] == "link"
        assert att["link_url"] == "https://example.com"
        assert "id" in att

    def test_create_attachment_requires_name(self):
        book = create_book(name=f"AttReqBook-{UNIQUE}")
        page = create_page(name=f"AttReqPage-{UNIQUE}", book_id=book["id"])
        resp = api_post("/api/attachments", {
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com"
        })
        assert resp.status_code == 422

    def test_create_attachment_requires_uploaded_to(self):
        resp = api_post("/api/attachments", {
            "name": "NoPage",
            "type": "link",
            "link_url": "https://example.com"
        })
        assert resp.status_code == 422

    def test_list_attachments(self):
        book = create_book(name=f"AttListBook-{UNIQUE}")
        page = create_page(name=f"AttListPage-{UNIQUE}", book_id=book["id"])
        api_post("/api/attachments", {
            "name": f"ListAtt-{UNIQUE}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com"
        })

        resp = api_get("/api/attachments")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_attachment(self):
        book = create_book(name=f"AttGetBook-{UNIQUE}")
        page = create_page(name=f"AttGetPage-{UNIQUE}", book_id=book["id"])
        create_resp = api_post("/api/attachments", {
            "name": f"GetAtt-{UNIQUE}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com/doc"
        })
        att = create_resp.json()

        resp = api_get(f"/api/attachments/{att['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == att["id"]
        assert detail["link_url"] == "https://example.com/doc"

    def test_update_attachment(self):
        book = create_book(name=f"AttUpdBook-{UNIQUE}")
        page = create_page(name=f"AttUpdPage-{UNIQUE}", book_id=book["id"])
        create_resp = api_post("/api/attachments", {
            "name": f"UpdAtt-{UNIQUE}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://old.com"
        })
        att = create_resp.json()

        resp = api_put(f"/api/attachments/{att['id']}", {
            "name": f"UpdAttNew-{UNIQUE}",
            "link_url": "https://new.com"
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"UpdAttNew-{UNIQUE}"
        assert updated["link_url"] == "https://new.com"

    def test_delete_attachment(self):
        book = create_book(name=f"AttDelBook-{UNIQUE}")
        page = create_page(name=f"AttDelPage-{UNIQUE}", book_id=book["id"])
        create_resp = api_post("/api/attachments", {
            "name": f"DelAtt-{UNIQUE}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://todelete.com"
        })
        att = create_resp.json()

        resp = api_delete(f"/api/attachments/{att['id']}")
        assert resp.status_code == 200

        # Should not be accessible
        get_resp = api_get(f"/api/attachments/{att['id']}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_attachment_404(self):
        missing_id = missing_entity_id("attachments")
        resp = api_get(f"/api/attachments/{missing_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Page Export
# ════════════════════════════════════════════════════════════════════


class TestPageExport:

    def test_export_html(self):
        book = create_book(name=f"ExpBook-{UNIQUE}")
        page = create_page(name=f"ExpPage-{UNIQUE}", book_id=book["id"], html="<h1>Title</h1><p>Body</p>")

        resp = api_get(f"/api/pages/{page['id']}/export/html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "<h1>Title</h1>" in resp.text
        assert "<p>Body</p>" in resp.text

    def test_export_plaintext(self):
        book = create_book(name=f"ExpTxtBook-{UNIQUE}")
        page = create_page(name=f"ExpTxtPage-{UNIQUE}", book_id=book["id"], html="<h1>Title</h1><p>Body text</p>")

        resp = api_get(f"/api/pages/{page['id']}/export/plaintext")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        # Should not contain HTML tags
        assert "<h1>" not in resp.text
        assert "<p>" not in resp.text
        assert "Title" in resp.text
        assert "Body text" in resp.text

    def test_export_markdown(self):
        book = create_book(name=f"ExpMdBook-{UNIQUE}")
        page = create_page(name=f"ExpMdPage-{UNIQUE}", book_id=book["id"], html="<h1>Title</h1><p>Body</p>")

        resp = api_get(f"/api/pages/{page['id']}/export/markdown")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")
        # Should contain text content
        assert "Title" in resp.text
        assert "Body" in resp.text

    def test_export_nonexistent_page_404(self):
        missing_page_id = missing_entity_id("pages")
        resp = api_get(f"/api/pages/{missing_page_id}/export/html")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Page Move
# ════════════════════════════════════════════════════════════════════


class TestPageMove:

    def test_move_page_to_different_chapter(self):
        """Moving a page to a different chapter."""
        book = create_book(name=f"MoveBook-{UNIQUE}")
        ch1 = create_chapter(book["id"], name=f"MoveCh1-{UNIQUE}")
        ch2 = create_chapter(book["id"], name=f"MoveCh2-{UNIQUE}")
        page = create_page(name=f"MovePage-{UNIQUE}", chapter_id=ch1["id"])

        resp = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": ch2["id"]})
        assert resp.status_code == 200
        moved = resp.json()
        assert moved["chapter_id"] == ch2["id"]

        # Verify via GET
        get_resp = api_get(f"/api/pages/{page['id']}")
        assert get_resp.json()["chapter_id"] == ch2["id"]

    def test_move_page_to_book_directly(self):
        """Moving a page from chapter to direct book child."""
        book = create_book(name=f"MoveBookDirect-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"MoveChDirect-{UNIQUE}")
        page = create_page(name=f"MovePageDirect-{UNIQUE}", chapter_id=chapter["id"])

        resp = api_put(f"/api/pages/{page['id']}/move", {"book_id": book["id"]})
        assert resp.status_code == 200
        moved = resp.json()
        assert moved["book_id"] == book["id"]
        assert moved.get("chapter_id") is None or moved.get("chapter_id") == 0

    def test_move_page_to_different_book(self):
        """Moving a page to a chapter in a different book."""
        book1 = create_book(name=f"MoveBook1-{UNIQUE}")
        book2 = create_book(name=f"MoveBook2-{UNIQUE}")
        ch1 = create_chapter(book1["id"], name=f"MoveChB1-{UNIQUE}")
        ch2 = create_chapter(book2["id"], name=f"MoveChB2-{UNIQUE}")
        page = create_page(name=f"MovePageB-{UNIQUE}", chapter_id=ch1["id"])

        resp = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": ch2["id"]})
        assert resp.status_code == 200
        moved = resp.json()
        assert moved["chapter_id"] == ch2["id"]
        assert moved["book_id"] == book2["id"]

    def test_move_nonexistent_page_404(self):
        book = create_book(name=f"MoveMissingBook-{UNIQUE}")
        missing_page_id = missing_entity_id("pages")
        resp = api_put(f"/api/pages/{missing_page_id}/move", {"book_id": book["id"]})
        assert resp.status_code == 404

    def test_move_page_invalid_target_422(self):
        """Moving to a non-existent chapter should fail."""
        book = create_book(name=f"MoveInvBook-{UNIQUE}")
        page = create_page(name=f"MoveInvPage-{UNIQUE}", book_id=book["id"])
        missing_chapter_id = missing_entity_id("chapters")
        resp = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": missing_chapter_id})
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 15: Ordering / Priority
# ════════════════════════════════════════════════════════════════════


class TestOrdering:

    def test_pages_ordered_by_priority_in_chapter(self):
        """Pages within a chapter are sorted by priority."""
        book = create_book(name=f"OrdBook-{UNIQUE}")
        chapter = create_chapter(book["id"], name=f"OrdChap-{UNIQUE}")
        p1 = create_page(name=f"OrdP1-{UNIQUE}", chapter_id=chapter["id"], priority=20)
        p2 = create_page(name=f"OrdP2-{UNIQUE}", chapter_id=chapter["id"], priority=5)
        p3 = create_page(name=f"OrdP3-{UNIQUE}", chapter_id=chapter["id"], priority=10)

        resp = api_get(f"/api/chapters/{chapter['id']}")
        pages = resp.json()["pages"]
        priorities = [p["priority"] for p in pages]
        assert priorities == sorted(priorities), f"Pages not sorted by priority: {priorities}"

    def test_book_contents_ordered_by_priority(self):
        """Book contents (chapters + direct pages) sorted by priority."""
        book = create_book(name=f"OrdContBook-{UNIQUE}")
        ch1 = create_chapter(book["id"], name=f"OrdContCh1-{UNIQUE}", priority=10)
        ch2 = create_chapter(book["id"], name=f"OrdContCh2-{UNIQUE}", priority=1)
        p1 = create_page(name=f"OrdContP1-{UNIQUE}", book_id=book["id"], priority=5)

        resp = api_get(f"/api/books/{book['id']}")
        contents = resp.json()["contents"]
        priorities = [c["priority"] for c in contents]
        assert priorities == sorted(priorities), f"Contents not sorted by priority: {priorities}"


# ════════════════════════════════════════════════════════════════════
# PART 16: Single-tenant (no data isolation)
# ════════════════════════════════════════════════════════════════════


class TestSingleTenant:

    def test_different_users_see_same_content(self):
        """All users see all content (no data isolation)."""
        book = create_book(name=f"SharedBook-{UNIQUE}")

        # User 2 should see the book
        resp = api_get("/api/books", headers=HEADERS_USER2)
        assert resp.status_code == 200
        names = [b["name"] for b in resp.json()["data"]]
        assert f"SharedBook-{UNIQUE}" in names

    def test_created_by_tracked(self):
        """created_by should reflect the creating user."""
        book = create_book(name=f"TrackBook-{UNIQUE}")
        assert book["created_by"] == int(USER_ID)

    def test_updated_by_tracked(self):
        """updated_by should reflect the updating user."""
        book = create_book(name=f"TrackUpdBook-{UNIQUE}")

        resp = api_put(f"/api/books/{book['id']}", {"description": "Updated"}, headers=HEADERS_USER2)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["updated_by"] == int(USER2_ID)


# ════════════════════════════════════════════════════════════════════
# PART 17: List Response Format
# ════════════════════════════════════════════════════════════════════


class TestListFormat:

    def test_books_list_format(self):
        resp = api_get("/api/books")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["total"], int)

    def test_chapters_list_format(self):
        resp = api_get("/api/chapters")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_pages_list_format(self):
        resp = api_get("/api/pages")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_shelves_list_format(self):
        resp = api_get("/api/shelves")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_attachments_list_format(self):
        resp = api_get("/api/attachments")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data


# ════════════════════════════════════════════════════════════════════
# PART 18: Timestamps
# ════════════════════════════════════════════════════════════════════


class TestTimestamps:

    def test_created_at_set_on_create(self):
        book = create_book(name=f"TSBook-{UNIQUE}")
        assert "created_at" in book
        assert book["created_at"] is not None
        # Should be ISO 8601 format
        assert "T" in book["created_at"]

    def test_updated_at_changes_on_update(self):
        book = create_book(name=f"TSUpdBook-{UNIQUE}")
        original_updated = book["updated_at"]

        import time
        time.sleep(0.1)  # Ensure time difference

        resp = api_put(f"/api/books/{book['id']}", {"description": "Updated"})
        updated = resp.json()
        assert updated["updated_at"] >= original_updated
