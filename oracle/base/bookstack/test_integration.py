"""
BookStack — L2 Integration Tests (Adversarial)

Targets LLM bug patterns:
- Pattern 1: Field name casing verification
- Pattern 2: Nested/related data completeness
- Pattern 3: Parameters actually implemented (sorting, filtering)
- Pattern 4: Exact status codes
- Pattern 5: Business logic truly computed
- Pattern 7: Cascade/side-effect correctness
- Pattern 8: Ordering/sequence sensitivity

"""

import os
import uuid

import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

API_KEY = "test-api-key-integration"
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


def unique():
    return uuid.uuid4().hex


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


# ═══════════════════════════════════════════════════
# L2 Tests — 3-5 steps, 8-12 assertions each
# ═══════════════════════════════════════════════════


class TestBookFieldIntegrity:
    """Pattern 1+2: Verify all response fields present with correct casing and types."""

    def test_book_create_returns_all_fields(self):
        """All expected fields must be present in create response."""
        uid = unique()
        r = api_post("/api/books", {"name": f"FieldBook-{uid}", "description": "Desc here"})
        assert r.status_code == 200
        book = r.json()
        # Verify all required fields exist
        assert "id" in book
        assert "name" in book
        assert "slug" in book
        assert "description" in book
        assert "created_by" in book
        assert "updated_by" in book
        assert "created_at" in book
        assert "updated_at" in book
        # Verify types
        assert isinstance(book["id"], int)
        assert book["name"] == f"FieldBook-{uid}"
        assert book["description"] == "Desc here"
        assert isinstance(book["created_by"], int)
        assert book["created_by"] == 1
        # Verify detail fields
        assert "contents" in book
        assert isinstance(book["contents"], list)
        assert "tags" in book
        assert isinstance(book["tags"], list)

    def test_chapter_create_returns_all_fields_with_book_id(self):
        """Chapter create must include book_id and nested pages array."""
        uid = unique()
        book = api_post("/api/books", {"name": f"ChFieldBook-{uid}"}).json()
        r = api_post("/api/chapters", {
            "name": f"ChField-{uid}",
            "book_id": book["id"],
            "description": "Chapter desc",
            "priority": 3
        })
        assert r.status_code == 200
        ch = r.json()
        assert ch["name"] == f"ChField-{uid}"
        assert ch["book_id"] == book["id"]
        assert ch["description"] == "Chapter desc"
        assert ch["priority"] == 3
        assert "id" in ch
        assert "slug" in ch
        assert "created_by" in ch
        assert "updated_by" in ch
        assert "created_at" in ch
        assert "updated_at" in ch
        assert "pages" in ch
        assert isinstance(ch["pages"], list)
        assert "tags" in ch

    def test_page_create_has_html_and_correct_parent_ids(self):
        """Page must have html field, correct book_id derived from chapter."""
        uid = unique()
        book = api_post("/api/books", {"name": f"PgFieldBook-{uid}"}).json()
        ch = api_post("/api/chapters", {"name": f"PgFieldCh-{uid}", "book_id": book["id"]}).json()
        r = api_post("/api/pages", {
            "name": f"PgField-{uid}",
            "chapter_id": ch["id"],
            "html": "<p>Content here</p>",
            "priority": 7
        })
        assert r.status_code == 200
        page = r.json()
        assert page["name"] == f"PgField-{uid}"
        assert page["chapter_id"] == ch["id"]
        assert page["book_id"] == book["id"]  # Derived from chapter
        assert page["html"] == "<p>Content here</p>"
        assert page["priority"] == 7
        assert "id" in page
        assert "slug" in page
        assert "created_by" in page
        assert "tags" in page
        assert isinstance(page["tags"], list)


class TestShelfBookRelationship:
    """Pattern 2+3: Shelf-book relationship with ordering verified."""

    def test_shelf_books_ordering_preserved(self):
        """Books on shelf must maintain specified order."""
        uid = unique()
        b1 = api_post("/api/books", {"name": f"ShB1-{uid}"}).json()
        b2 = api_post("/api/books", {"name": f"ShB2-{uid}"}).json()
        b3 = api_post("/api/books", {"name": f"ShB3-{uid}"}).json()

        # Create shelf with specific book order: b3, b1, b2
        shelf = api_post("/api/shelves", {
            "name": f"OrdShelf-{uid}",
            "books": [b3["id"], b1["id"], b2["id"]]
        }).json()

        # Retrieve and verify order
        r = api_get(f"/api/shelves/{shelf['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert len(detail["books"]) == 3
        assert detail["books"][0]["id"] == b3["id"]
        assert detail["books"][1]["id"] == b1["id"]
        assert detail["books"][2]["id"] == b2["id"]
        # Each book object has required fields
        for bk in detail["books"]:
            assert "id" in bk
            assert "name" in bk
            assert "slug" in bk

    def test_shelf_update_reorders_books(self):
        """Updating shelf books array changes the order."""
        uid = unique()
        b1 = api_post("/api/books", {"name": f"ReordB1-{uid}"}).json()
        b2 = api_post("/api/books", {"name": f"ReordB2-{uid}"}).json()
        shelf = api_post("/api/shelves", {
            "name": f"ReordShelf-{uid}",
            "books": [b1["id"], b2["id"]]
        }).json()

        # Update with reversed order
        r = api_put(f"/api/shelves/{shelf['id']}", {"books": [b2["id"], b1["id"]]})
        assert r.status_code == 200
        updated = r.json()
        assert updated["books"][0]["id"] == b2["id"]
        assert updated["books"][1]["id"] == b1["id"]

        # Confirm via separate GET
        detail = api_get(f"/api/shelves/{shelf['id']}").json()
        assert detail["books"][0]["id"] == b2["id"]
        assert detail["books"][1]["id"] == b1["id"]


class TestSlugGeneration:
    """Pattern 5: Slug business logic actually works with varying inputs."""

    def test_slug_from_complex_name(self):
        """Slug generated correctly from name with special chars."""
        uid = unique()
        book = api_post("/api/books", {"name": f"Hello World! {uid}"}).json()
        assert book["slug"] == f"hello-world-{uid}"

    def test_slug_strips_special_characters(self):
        """Slug strips non-alphanumeric except dashes."""
        uid = unique()
        book = api_post("/api/books", {"name": f"Test@Book#{uid}!"}).json()
        slug = book["slug"]
        assert "@" not in slug
        assert "#" not in slug
        assert "!" not in slug
        # Should contain the meaningful parts
        assert "test" in slug
        assert "book" in slug
        assert uid in slug

    def test_slug_collision_appends_suffix(self):
        """Duplicate slugs get -N suffix."""
        uid = unique()
        name = f"DupName-{uid}"
        b1 = api_post("/api/books", {"name": name}).json()
        b2 = api_post("/api/books", {"name": name}).json()
        b3 = api_post("/api/books", {"name": name}).json()

        assert b1["slug"] != b2["slug"]
        assert b2["slug"] != b3["slug"]
        assert b1["slug"] != b3["slug"]
        # Verify suffixes
        base_slug = b1["slug"]
        assert b2["slug"].startswith(base_slug)
        assert b3["slug"].startswith(base_slug)

    def test_slug_truncated_to_100_chars(self):
        """Slug is at most 100 characters."""
        uid = unique()
        long_name = "A" * 120 + f"-{uid}"
        book = api_post("/api/books", {"name": long_name}).json()
        assert len(book["slug"]) <= 100


class TestTagsReplaceSemantics:
    """Pattern 5+7: Tags replace (not merge) on update, and work on all entity types."""

    def test_tags_full_replace_on_update(self):
        """Updating tags replaces ALL existing tags, not merges."""
        uid = unique()
        book = api_post("/api/books", {
            "name": f"TagReplace-{uid}",
            "tags": [
                {"name": "env", "value": "prod"},
                {"name": "team", "value": "backend"}
            ]
        }).json()

        # Update with completely different tags
        r = api_put(f"/api/books/{book['id']}", {
            "tags": [{"name": "version", "value": "2.0"}]
        })
        assert r.status_code == 200
        detail = api_get(f"/api/books/{book['id']}").json()
        assert len(detail["tags"]) == 1
        assert detail["tags"][0]["name"] == "version"
        assert detail["tags"][0]["value"] == "2.0"
        # Old tags should NOT be present
        tag_names = [t["name"] for t in detail["tags"]]
        assert "env" not in tag_names
        assert "team" not in tag_names

    def test_tags_empty_array_clears_all(self):
        """Setting tags to empty array removes all tags."""
        uid = unique()
        book = api_post("/api/books", {
            "name": f"TagClear-{uid}",
            "tags": [{"name": "key", "value": "val"}]
        }).json()

        r = api_put(f"/api/books/{book['id']}", {"tags": []})
        assert r.status_code == 200
        detail = api_get(f"/api/books/{book['id']}").json()
        assert len(detail["tags"]) == 0

    def test_tags_with_same_name_different_values(self):
        """Multiple tags can have the same name."""
        uid = unique()
        tags = [
            {"name": "category", "value": "science"},
            {"name": "category", "value": "math"}
        ]
        book = api_post("/api/books", {"name": f"MultiTag-{uid}", "tags": tags}).json()
        detail = api_get(f"/api/books/{book['id']}").json()
        assert len(detail["tags"]) == 2
        values = [t["value"] for t in detail["tags"]]
        assert "science" in values
        assert "math" in values


class TestListResponseFormat:
    """Pattern 1+4: List endpoints return correct structure with data/total."""

    def test_list_books_total_reflects_actual_count(self):
        """Total field must match actual number of items."""
        uid = unique()
        # Create 3 books
        api_post("/api/books", {"name": f"ListCnt1-{uid}"})
        api_post("/api/books", {"name": f"ListCnt2-{uid}"})
        api_post("/api/books", {"name": f"ListCnt3-{uid}"})

        r = api_get("/api/books")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == len(data["data"])
        assert data["total"] >= 3

    def test_list_shelves_item_fields_complete(self):
        """Each item in list response has all required fields."""
        uid = unique()
        api_post("/api/shelves", {"name": f"ListShelf-{uid}", "description": "test"})

        r = api_get("/api/shelves")
        assert r.status_code == 200
        items = r.json()["data"]
        found = [s for s in items if s["name"] == f"ListShelf-{uid}"]
        assert len(found) == 1
        item = found[0]
        assert "id" in item
        assert "name" in item
        assert "slug" in item
        assert "description" in item
        assert "created_by" in item
        assert "updated_by" in item
        assert "created_at" in item
        assert "updated_at" in item


class TestBookContentsNested:
    """Pattern 2+3: Book detail contents correctly includes chapters and pages with type field."""

    def test_book_contents_type_field_correct(self):
        """Each item in book contents has type='chapter' or type='page'."""
        uid = unique()
        book = api_post("/api/books", {"name": f"ContType-{uid}"}).json()
        api_post("/api/chapters", {"name": f"ContTypeCh-{uid}", "book_id": book["id"], "priority": 1})
        api_post("/api/pages", {"name": f"ContTypePg-{uid}", "book_id": book["id"], "priority": 2})

        r = api_get(f"/api/books/{book['id']}")
        contents = r.json()["contents"]
        assert len(contents) >= 2
        types = {c["type"] for c in contents}
        assert "chapter" in types
        assert "page" in types
        for item in contents:
            assert "id" in item
            assert "name" in item
            assert "slug" in item
            assert "type" in item
            assert "priority" in item
            assert item["type"] in ("chapter", "page")

    def test_book_contents_priority_sorting(self):
        """Book contents sorted by priority ascending."""
        uid = unique()
        book = api_post("/api/books", {"name": f"ContSort-{uid}"}).json()
        api_post("/api/chapters", {"name": f"SortCh-{uid}", "book_id": book["id"], "priority": 20})
        api_post("/api/pages", {"name": f"SortPg1-{uid}", "book_id": book["id"], "priority": 5})
        api_post("/api/pages", {"name": f"SortPg2-{uid}", "book_id": book["id"], "priority": 15})

        r = api_get(f"/api/books/{book['id']}")
        contents = r.json()["contents"]
        priorities = [c["priority"] for c in contents]
        assert priorities == sorted(priorities), f"Not sorted by priority: {priorities}"


class TestChapterPagesNested:
    """Pattern 2: Chapter detail includes pages list with all fields."""

    def test_chapter_pages_complete(self):
        """Chapter detail includes its pages with all required fields."""
        uid = unique()
        book = api_post("/api/books", {"name": f"ChPgBook-{uid}"}).json()
        ch = api_post("/api/chapters", {"name": f"ChPg-{uid}", "book_id": book["id"]}).json()
        api_post("/api/pages", {
            "name": f"ChPgPage1-{uid}", "chapter_id": ch["id"], "html": "<p>A</p>", "priority": 5
        })
        api_post("/api/pages", {
            "name": f"ChPgPage2-{uid}", "chapter_id": ch["id"], "html": "<p>B</p>", "priority": 2
        })

        r = api_get(f"/api/chapters/{ch['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert len(detail["pages"]) == 2
        # Sorted by priority
        assert detail["pages"][0]["priority"] <= detail["pages"][1]["priority"]
        # Fields present
        for pg in detail["pages"]:
            assert "id" in pg
            assert "name" in pg
            assert "slug" in pg
            assert "book_id" in pg
            assert "priority" in pg


class TestRevisionFieldIntegrity:
    """Pattern 1+5: Revision fields correct and content stores PREVIOUS version."""

    def test_revision_has_all_required_fields(self):
        """Revision object has id, page_id, revision_number, name, html, created_by, created_at."""
        uid = unique()
        book = api_post("/api/books", {"name": f"RevFieldBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"RevFieldPage-{uid}",
            "book_id": book["id"],
            "html": "<p>Original content</p>"
        }).json()

        # Update to create revision
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Updated</p>"})

        r = api_get(f"/api/pages/{page['id']}/revisions")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        rev = data["data"][0]
        assert "id" in rev
        assert "page_id" in rev
        assert rev["page_id"] == page["id"]
        assert "revision_number" in rev
        assert isinstance(rev["revision_number"], int)
        assert "name" in rev
        assert "html" in rev
        assert "created_by" in rev
        assert "created_at" in rev
        # Content should be the PREVIOUS (pre-update) content
        assert rev["html"] == "<p>Original content</p>"
        assert rev["name"] == f"RevFieldPage-{uid}"

    def test_multiple_revisions_increment_number(self):
        """Each revision gets an incrementing revision_number."""
        uid = unique()
        book = api_post("/api/books", {"name": f"RevNumBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"RevNumPage-{uid}", "book_id": book["id"], "html": "<p>V1</p>"
        }).json()

        api_put(f"/api/pages/{page['id']}", {"html": "<p>V2</p>"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>V3</p>"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>V4</p>"})

        r = api_get(f"/api/pages/{page['id']}/revisions")
        revisions = r.json()["data"]
        assert len(revisions) >= 3
        # Newest first — so revision_numbers should be decreasing
        for i in range(len(revisions) - 1):
            assert revisions[i]["revision_number"] > revisions[i + 1]["revision_number"]


class TestPageExportContent:
    """Pattern 5: Export endpoints actually transform content."""

    def test_plaintext_export_strips_all_html_tags(self):
        """Plaintext export must not contain any HTML tags."""
        uid = unique()
        html_content = "<h1>Title</h1><p>Paragraph with <strong>bold</strong> and <em>italic</em></p>"
        book = api_post("/api/books", {"name": f"ExpBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"ExpPage-{uid}", "book_id": book["id"], "html": html_content
        }).json()

        r = api_get(f"/api/pages/{page['id']}/export/plaintext")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        text = r.text
        assert "<h1>" not in text
        assert "<p>" not in text
        assert "<strong>" not in text
        assert "<em>" not in text
        assert "Title" in text
        assert "bold" in text
        assert "italic" in text

    def test_html_export_returns_raw_html(self):
        """HTML export returns the raw html field content."""
        uid = unique()
        html_content = "<div><h2>Section</h2><ul><li>Item 1</li><li>Item 2</li></ul></div>"
        book = api_post("/api/books", {"name": f"HtmlExpBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"HtmlExpPage-{uid}", "book_id": book["id"], "html": html_content
        }).json()

        r = api_get(f"/api/pages/{page['id']}/export/html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert html_content in r.text

    def test_markdown_export_content_type(self):
        """Markdown export has correct content-type."""
        uid = unique()
        book = api_post("/api/books", {"name": f"MdExpBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"MdExpPage-{uid}", "book_id": book["id"], "html": "<p>Some text</p>"
        }).json()

        r = api_get(f"/api/pages/{page['id']}/export/markdown")
        assert r.status_code == 200
        assert "text/markdown" in r.headers.get("content-type", "")
        assert "Some text" in r.text


class TestPageMoveUpdatesParent:
    """Pattern 7: Move page actually updates parent references."""

    def test_move_page_removes_from_old_chapter(self):
        """After move, page no longer appears in old chapter's pages."""
        uid = unique()
        book = api_post("/api/books", {"name": f"MvBook-{uid}"}).json()
        ch1 = api_post("/api/chapters", {"name": f"MvCh1-{uid}", "book_id": book["id"]}).json()
        ch2 = api_post("/api/chapters", {"name": f"MvCh2-{uid}", "book_id": book["id"]}).json()
        page = api_post("/api/pages", {"name": f"MvPage-{uid}", "chapter_id": ch1["id"]}).json()

        # Move to ch2
        r = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": ch2["id"]})
        assert r.status_code == 200
        assert r.json()["chapter_id"] == ch2["id"]

        # Old chapter should not contain the page
        ch1_detail = api_get(f"/api/chapters/{ch1['id']}").json()
        page_ids = [p["id"] for p in ch1_detail["pages"]]
        assert page["id"] not in page_ids

        # New chapter should contain it
        ch2_detail = api_get(f"/api/chapters/{ch2['id']}").json()
        page_ids = [p["id"] for p in ch2_detail["pages"]]
        assert page["id"] in page_ids

    def test_move_page_updates_book_id_when_moving_to_different_book(self):
        """Moving page to chapter in different book updates book_id."""
        uid = unique()
        book1 = api_post("/api/books", {"name": f"MvBk1-{uid}"}).json()
        book2 = api_post("/api/books", {"name": f"MvBk2-{uid}"}).json()
        ch1 = api_post("/api/chapters", {"name": f"MvChBk1-{uid}", "book_id": book1["id"]}).json()
        ch2 = api_post("/api/chapters", {"name": f"MvChBk2-{uid}", "book_id": book2["id"]}).json()
        page = api_post("/api/pages", {"name": f"MvPgBk-{uid}", "chapter_id": ch1["id"]}).json()

        assert page["book_id"] == book1["id"]

        r = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": ch2["id"]})
        assert r.status_code == 200
        moved = r.json()
        assert moved["book_id"] == book2["id"]
        assert moved["chapter_id"] == ch2["id"]

        # Confirm via GET
        detail = api_get(f"/api/pages/{page['id']}").json()
        assert detail["book_id"] == book2["id"]


class TestAttachmentIntegrity:
    """Pattern 1+2: Attachment fields present and correct."""

    def test_attachment_detail_has_link_url(self):
        """GET attachment returns link_url field."""
        uid = unique()
        book = api_post("/api/books", {"name": f"AttBook-{uid}"}).json()
        page = api_post("/api/pages", {"name": f"AttPage-{uid}", "book_id": book["id"]}).json()

        att = api_post("/api/attachments", {
            "name": f"Att-{uid}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com/test"
        }).json()

        r = api_get(f"/api/attachments/{att['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["id"] == att["id"]
        assert detail["name"] == f"Att-{uid}"
        assert detail["uploaded_to"] == page["id"]
        assert detail["type"] == "link"
        assert detail["link_url"] == "https://example.com/test"
        assert "created_by" in detail
        assert "updated_by" in detail
        assert "created_at" in detail
        assert "updated_at" in detail

    def test_attachment_list_does_not_include_deleted(self):
        """Deleted attachment should not appear in list."""
        uid = unique()
        book = api_post("/api/books", {"name": f"AttDelBook-{uid}"}).json()
        page = api_post("/api/pages", {"name": f"AttDelPage-{uid}", "book_id": book["id"]}).json()

        att = api_post("/api/attachments", {
            "name": f"AttDel-{uid}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com/del"
        }).json()

        api_delete(f"/api/attachments/{att['id']}")

        r = api_get("/api/attachments")
        ids = [a["id"] for a in r.json()["data"]]
        assert att["id"] not in ids


class TestRecycleBinMetadata:
    """Pattern 1+2: Recycle bin items have correct metadata."""

    def test_recycle_bin_item_fields(self):
        """Recycle bin items must have all specified fields."""
        uid = unique()
        book = api_post("/api/books", {"name": f"BinField-{uid}"}).json()
        api_delete(f"/api/books/{book['id']}")

        r = api_get("/api/recycle-bin")
        assert r.status_code == 200
        items = r.json()["data"]
        found = [i for i in items if i["entity_type"] == "book" and i["entity_id"] == book["id"]]
        assert len(found) == 1
        item = found[0]
        assert "id" in item
        assert "deleted_by" in item
        assert item["deleted_by"] == 1
        assert "deleted_at" in item
        assert "entity_type" in item
        assert item["entity_type"] == "book"
        assert "entity_id" in item
        assert item["entity_id"] == book["id"]
        assert "entity_name" in item
        assert item["entity_name"] == f"BinField-{uid}"


class TestSearchResultFields:
    """Pattern 1+5: Search results have correct structure and scoring."""

    def test_search_result_fields_complete(self):
        """Each search result has type, id, name, slug, score."""
        uid = unique()
        keyword = f"searchable{uid}"
        book = api_post("/api/books", {"name": f"SrchBook-{uid}"}).json()
        api_post("/api/pages", {"name": keyword, "book_id": book["id"], "html": "<p>x</p>"})

        r = api_get("/api/search", params={"query": keyword})
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1
        for result in data["data"]:
            assert "type" in result
            assert result["type"] in ("shelf", "book", "chapter", "page")
            assert "id" in result
            assert isinstance(result["id"], int)
            assert "name" in result
            assert "slug" in result
            assert "score" in result
            assert isinstance(result["score"], (int, float))

    def test_search_does_not_return_deleted_items(self):
        """Soft-deleted items should NOT appear in search results."""
        uid = unique()
        keyword = f"deletesearch{uid}"
        book = api_post("/api/books", {"name": keyword}).json()

        # Verify it appears in search
        r1 = api_get("/api/search", params={"query": keyword})
        assert r1.json()["total"] >= 1

        # Delete and search again
        api_delete(f"/api/books/{book['id']}")
        r2 = api_get("/api/search", params={"query": keyword})
        found = [x for x in r2.json()["data"] if x["id"] == book["id"] and x["type"] == "book"]
        assert len(found) == 0


class TestValidationErrors:
    """Pattern 4+8: Correct status codes and error format for validation."""

    def test_create_book_no_name_returns_422(self):
        """Missing required field returns 422 with error details."""
        r = api_post("/api/books", {"description": "no name"})
        assert r.status_code == 422
        body = r.json()
        assert "error" in body

    def test_create_page_no_parent_returns_422(self):
        """Page without book_id or chapter_id returns 422."""
        r = api_post("/api/pages", {"name": "orphan"})
        assert r.status_code == 422

    def test_create_chapter_invalid_book_returns_422(self):
        """Chapter with non-existent book_id returns 422."""
        missing_book_id = missing_entity_id("books")
        r = api_post("/api/chapters", {"name": "bad", "book_id": missing_book_id})
        assert r.status_code == 422

    def test_get_nonexistent_returns_404_with_error_body(self):
        """404 responses have proper error body."""
        missing_book_id = missing_entity_id("books")
        r = api_get(f"/api/books/{missing_book_id}")
        assert r.status_code == 404
        body = r.json()
        assert "error" in body

    def test_delete_nonexistent_returns_404(self):
        """Deleting non-existent entity returns 404."""
        missing_book_id = missing_entity_id("books")
        r = api_delete(f"/api/books/{missing_book_id}")
        assert r.status_code == 404


class TestAuthenticationEnforcement:
    """Pattern 4+6: Auth checked on all endpoints."""

    def test_auth_required_on_post(self):
        """POST without auth returns 401."""
        r = requests.post(f"{BASE_URL}/api/books", json={"name": "X"}, timeout=30)
        assert r.status_code == 401

    def test_auth_required_on_put(self):
        """PUT without auth returns 401."""
        r = requests.put(f"{BASE_URL}/api/books/1", json={"name": "X"}, timeout=30)
        assert r.status_code == 401

    def test_auth_required_on_delete(self):
        """DELETE without auth returns 401."""
        r = requests.delete(f"{BASE_URL}/api/books/1", timeout=30)
        assert r.status_code == 401

    def test_auth_required_on_search(self):
        """Search without auth returns 401."""
        r = requests.get(f"{BASE_URL}/api/search", params={"query": "test"}, timeout=30)
        assert r.status_code == 401

    def test_auth_required_on_recycle_bin(self):
        """Recycle bin without auth returns 401."""
        r = requests.get(f"{BASE_URL}/api/recycle-bin", timeout=30)
        assert r.status_code == 401


class TestUpdatedByTracking:
    """Pattern 7: updated_by correctly tracks which user made the change."""

    def test_created_by_vs_updated_by_different_users(self):
        """created_by stays as creator; updated_by changes to updater."""
        uid = unique()
        book = api_post("/api/books", {"name": f"TrackBook-{uid}"}).json()
        assert book["created_by"] == 1

        # Update as user 2
        r = api_put(f"/api/books/{book['id']}", {"description": "new"}, headers=HEADERS_USER2)
        assert r.status_code == 200
        updated = r.json()
        assert updated["created_by"] == 1  # Unchanged
        assert updated["updated_by"] == 2  # Changed to user 2
