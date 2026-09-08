"""
BookStack — L3 Workflow Tests (Adversarial)

Multi-step workflows crossing 3+ entity types, verifying side effects,
cascade behaviors, and data consistency.

Targets LLM bug patterns:
- Pattern 2: Nested data returned correctly after complex operations
- Pattern 5: Business logic actually computed (revisions, search ranking)
- Pattern 7: Cascade deletes/restores maintain consistency
- Pattern 8: Sequence-sensitive operations

"""

import os
import uuid

import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

API_KEY = "test-api-key-workflow"
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


# ═══════════════════════════════════════════════════
# L3 Tests — 6-12 steps, 12-20 assertions each
# ═══════════════════════════════════════════════════


class TestFullContentHierarchyLifecycle:
    """Pattern 2+7: Build full hierarchy then verify cascade and restore."""

    def test_build_hierarchy_delete_book_verify_cascade_restore(self):
        """
        Build: Shelf -> Book -> Chapter -> Page
        Delete book -> verify chapter/page gone -> restore -> verify all back.
        """
        uid = unique()

        # 1. Create hierarchy
        book = api_post("/api/books", {"name": f"WfBook-{uid}", "description": "workflow book"}).json()
        ch = api_post("/api/chapters", {
            "name": f"WfChapter-{uid}", "book_id": book["id"], "priority": 1
        }).json()
        page = api_post("/api/pages", {
            "name": f"WfPage-{uid}", "chapter_id": ch["id"], "html": "<p>Workflow content</p>"
        }).json()
        shelf = api_post("/api/shelves", {
            "name": f"WfShelf-{uid}", "books": [book["id"]]
        }).json()

        # 2. Verify hierarchy accessible
        book_detail = api_get(f"/api/books/{book['id']}").json()
        assert len(book_detail["contents"]) >= 1
        ch_detail = api_get(f"/api/chapters/{ch['id']}").json()
        assert len(ch_detail["pages"]) == 1
        assert ch_detail["pages"][0]["id"] == page["id"]

        # 3. Delete book — cascades to chapter and page
        r = api_delete(f"/api/books/{book['id']}")
        assert r.status_code == 200

        # 4. Verify chapter and page are now 404
        assert api_get(f"/api/chapters/{ch['id']}").status_code == 404
        assert api_get(f"/api/pages/{page['id']}").status_code == 404

        # 5. Shelf still exists (delete shelf doesn't cascade, delete book doesn't delete shelf)
        shelf_detail = api_get(f"/api/shelves/{shelf['id']}").json()
        assert shelf_detail["id"] == shelf["id"]

        # 6. Find book in recycle bin
        bin_items = api_get("/api/recycle-bin").json()["data"]
        bin_book = [i for i in bin_items if i["entity_type"] == "book" and i["entity_id"] == book["id"]]
        assert len(bin_book) == 1
        assert bin_book[0]["entity_name"] == f"WfBook-{uid}"

        # 7. Restore book
        r = api_put(f"/api/recycle-bin/{bin_book[0]['id']}/restore")
        assert r.status_code == 200

        # 8. Verify book, chapter, and page all accessible again
        assert api_get(f"/api/books/{book['id']}").status_code == 200
        assert api_get(f"/api/chapters/{ch['id']}").status_code == 200
        pg_detail = api_get(f"/api/pages/{page['id']}").json()
        assert pg_detail["html"] == "<p>Workflow content</p>"
        assert pg_detail["chapter_id"] == ch["id"]
        assert pg_detail["book_id"] == book["id"]

    def test_delete_chapter_cascades_pages_but_not_book(self):
        """
        Delete chapter -> its pages disappear -> book remains with other content.
        Restore chapter -> pages come back.
        """
        uid = unique()

        # Setup
        book = api_post("/api/books", {"name": f"ChCascBook-{uid}"}).json()
        ch1 = api_post("/api/chapters", {"name": f"ChCasc1-{uid}", "book_id": book["id"]}).json()
        ch2 = api_post("/api/chapters", {"name": f"ChCasc2-{uid}", "book_id": book["id"]}).json()
        p1 = api_post("/api/pages", {"name": f"ChCascP1-{uid}", "chapter_id": ch1["id"]}).json()
        p2 = api_post("/api/pages", {"name": f"ChCascP2-{uid}", "chapter_id": ch1["id"]}).json()
        p3 = api_post("/api/pages", {"name": f"ChCascP3-{uid}", "chapter_id": ch2["id"]}).json()

        # Delete ch1
        api_delete(f"/api/chapters/{ch1['id']}")

        # ch1's pages are gone
        assert api_get(f"/api/pages/{p1['id']}").status_code == 404
        assert api_get(f"/api/pages/{p2['id']}").status_code == 404

        # ch2 and its page unaffected
        assert api_get(f"/api/chapters/{ch2['id']}").status_code == 200
        assert api_get(f"/api/pages/{p3['id']}").status_code == 200

        # Book still exists
        assert api_get(f"/api/books/{book['id']}").status_code == 200

        # Restore ch1
        bin_items = api_get("/api/recycle-bin").json()["data"]
        bin_ch = [i for i in bin_items if i["entity_type"] == "chapter" and i["entity_id"] == ch1["id"]]
        assert len(bin_ch) == 1
        api_put(f"/api/recycle-bin/{bin_ch[0]['id']}/restore")

        # Pages restored
        assert api_get(f"/api/pages/{p1['id']}").status_code == 200
        assert api_get(f"/api/pages/{p2['id']}").status_code == 200


class TestPageRevisionWorkflow:
    """Pattern 5+7: Revision lifecycle with content verification."""

    def test_edit_restore_edit_verify_revision_chain(self):
        """
        Create page -> edit 3 times -> verify revision chain ->
        restore oldest -> verify content + new revision created.
        """
        uid = unique()
        book = api_post("/api/books", {"name": f"RevWfBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"RevWfPage-{uid}",
            "book_id": book["id"],
            "html": "<p>Version 1</p>"
        }).json()

        # Edit 3 times
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 2</p>", "name": f"RevWfPage-{uid}-v2"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 3</p>", "name": f"RevWfPage-{uid}-v3"})
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Version 4</p>", "name": f"RevWfPage-{uid}-v4"})

        # Check revisions: should be 3 (one per edit)
        revs = api_get(f"/api/pages/{page['id']}/revisions").json()
        assert revs["total"] >= 3
        rev_data = revs["data"]

        # Revisions newest first
        assert rev_data[0]["revision_number"] > rev_data[-1]["revision_number"]

        # Find oldest revision (has V1 content)
        oldest = rev_data[-1]
        assert oldest["html"] == "<p>Version 1</p>"
        assert oldest["name"] == f"RevWfPage-{uid}"

        # Restore oldest
        r = api_put(f"/api/pages/{page['id']}/revisions/{oldest['id']}/restore")
        assert r.status_code == 200
        restored = r.json()
        assert restored["html"] == "<p>Version 1</p>"
        assert restored["name"] == f"RevWfPage-{uid}"

        # Verify page content updated
        current = api_get(f"/api/pages/{page['id']}").json()
        assert current["html"] == "<p>Version 1</p>"

        # Verify new revision created (storing V4 that was replaced)
        new_revs = api_get(f"/api/pages/{page['id']}/revisions").json()
        assert new_revs["total"] > revs["total"]
        # Newest revision stores what was just replaced (V4)
        newest_rev = new_revs["data"][0]
        assert newest_rev["html"] == "<p>Version 4</p>"


class TestSearchAcrossEntityTypes:
    """Pattern 3+5: Search truly finds across all entity types with ranking."""

    def test_search_finds_all_types_and_ranks_correctly(self):
        """
        Create entities of all types with same keyword.
        Search should find all, with name matches ranked higher.
        """
        uid = unique()
        keyword = f"universal{uid}"

        # Create one of each type with keyword in different places
        shelf = api_post("/api/shelves", {"name": keyword, "description": "a shelf"}).json()
        book = api_post("/api/books", {"name": f"Book-{uid}", "description": keyword}).json()
        ch = api_post("/api/chapters", {
            "name": f"Ch-{keyword}", "book_id": book["id"], "description": "chapter"
        }).json()
        page = api_post("/api/pages", {
            "name": f"Page-{uid}", "book_id": book["id"], "html": f"<p>{keyword} in content</p>"
        }).json()

        # Search
        r = api_get("/api/search", params={"query": keyword})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 4  # All 4 entity types

        types_found = {x["type"] for x in data["data"]}
        assert "shelf" in types_found
        assert "book" in types_found
        assert "chapter" in types_found
        assert "page" in types_found

        # Name match (shelf) should score higher than content match
        shelf_result = [x for x in data["data"] if x["type"] == "shelf" and x["id"] == shelf["id"]]
        book_result = [x for x in data["data"] if x["type"] == "book" and x["id"] == book["id"]]
        assert len(shelf_result) == 1
        assert len(book_result) == 1
        assert shelf_result[0]["score"] >= book_result[0]["score"]


class TestShelfLifecycleWithBooks:
    """Pattern 2+7: Shelf operations don't cascade-delete books."""

    def test_shelf_lifecycle_books_persist(self):
        """
        Create books -> put on shelf -> update shelf books -> delete shelf
        -> verify books still exist and accessible.
        """
        uid = unique()
        b1 = api_post("/api/books", {"name": f"ShLfB1-{uid}"}).json()
        b2 = api_post("/api/books", {"name": f"ShLfB2-{uid}"}).json()
        b3 = api_post("/api/books", {"name": f"ShLfB3-{uid}"}).json()

        # Create shelf with b1, b2
        shelf = api_post("/api/shelves", {
            "name": f"ShLfShelf-{uid}",
            "books": [b1["id"], b2["id"]],
            "tags": [{"name": "type", "value": "reference"}]
        }).json()
        assert len(shelf["books"]) == 2
        assert shelf["tags"][0]["name"] == "type"

        # Update shelf to have b2, b3 (remove b1, add b3)
        r = api_put(f"/api/shelves/{shelf['id']}", {"books": [b2["id"], b3["id"]]})
        assert r.status_code == 200
        updated = r.json()
        assert len(updated["books"]) == 2
        assert updated["books"][0]["id"] == b2["id"]
        assert updated["books"][1]["id"] == b3["id"]

        # b1 still exists (just removed from shelf)
        assert api_get(f"/api/books/{b1['id']}").status_code == 200

        # Delete shelf
        api_delete(f"/api/shelves/{shelf['id']}")

        # ALL books still exist
        assert api_get(f"/api/books/{b1['id']}").status_code == 200
        assert api_get(f"/api/books/{b2['id']}").status_code == 200
        assert api_get(f"/api/books/{b3['id']}").status_code == 200


class TestPageMoveWithRevisions:
    """Pattern 5+7: Moving pages preserves content and revision history."""

    def test_move_page_preserves_revisions_and_content(self):
        """
        Create page with revisions -> move to different book/chapter
        -> verify content intact and revisions still accessible.
        """
        uid = unique()
        book1 = api_post("/api/books", {"name": f"MvRevBk1-{uid}"}).json()
        book2 = api_post("/api/books", {"name": f"MvRevBk2-{uid}"}).json()
        ch1 = api_post("/api/chapters", {"name": f"MvRevCh1-{uid}", "book_id": book1["id"]}).json()
        ch2 = api_post("/api/chapters", {"name": f"MvRevCh2-{uid}", "book_id": book2["id"]}).json()

        # Create page and edit to create revisions
        page = api_post("/api/pages", {
            "name": f"MvRevPg-{uid}",
            "chapter_id": ch1["id"],
            "html": "<p>Original</p>"
        }).json()
        api_put(f"/api/pages/{page['id']}", {"html": "<p>Edited</p>"})

        # Verify revision exists
        revs_before = api_get(f"/api/pages/{page['id']}/revisions").json()
        assert revs_before["total"] >= 1

        # Move page to ch2 (different book)
        r = api_put(f"/api/pages/{page['id']}/move", {"chapter_id": ch2["id"]})
        assert r.status_code == 200
        assert r.json()["book_id"] == book2["id"]
        assert r.json()["chapter_id"] == ch2["id"]
        assert r.json()["html"] == "<p>Edited</p>"

        # Revisions still accessible
        revs_after = api_get(f"/api/pages/{page['id']}/revisions").json()
        assert revs_after["total"] == revs_before["total"]

        # Page no longer in book1's contents
        bk1_contents = api_get(f"/api/books/{book1['id']}").json()["contents"]
        page_ids = [c["id"] for c in bk1_contents if c["type"] == "page"]
        assert page["id"] not in page_ids

        # Page appears in book2's contents via ch2
        ch2_detail = api_get(f"/api/chapters/{ch2['id']}").json()
        pg_ids = [p["id"] for p in ch2_detail["pages"]]
        assert page["id"] in pg_ids


class TestAttachmentPageRelationship:
    """Pattern 7+8: Attachments tied to pages, sequence matters."""

    def test_attachment_lifecycle_with_page(self):
        """
        Create page -> add attachments -> update attachment -> delete page
        -> verify attachments behavior.
        """
        uid = unique()
        book = api_post("/api/books", {"name": f"AttWfBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"AttWfPage-{uid}", "book_id": book["id"], "html": "<p>Content</p>"
        }).json()

        # Create 2 attachments
        att1 = api_post("/api/attachments", {
            "name": f"Att1-{uid}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com/1"
        }).json()
        att2 = api_post("/api/attachments", {
            "name": f"Att2-{uid}",
            "uploaded_to": page["id"],
            "type": "link",
            "link_url": "https://example.com/2"
        }).json()

        # Verify both exist in list
        all_atts = api_get("/api/attachments").json()
        att_ids = [a["id"] for a in all_atts["data"]]
        assert att1["id"] in att_ids
        assert att2["id"] in att_ids

        # Update attachment 1
        r = api_put(f"/api/attachments/{att1['id']}", {
            "name": f"Att1Updated-{uid}",
            "link_url": "https://updated.com/1"
        })
        assert r.status_code == 200
        assert r.json()["name"] == f"Att1Updated-{uid}"
        assert r.json()["link_url"] == "https://updated.com/1"
        assert r.json()["uploaded_to"] == page["id"]

        # Delete attachment 2
        r = api_delete(f"/api/attachments/{att2['id']}")
        assert r.status_code == 200
        assert api_get(f"/api/attachments/{att2['id']}").status_code == 404

        # Attachment 1 still accessible
        att1_detail = api_get(f"/api/attachments/{att1['id']}").json()
        assert att1_detail["name"] == f"Att1Updated-{uid}"
        assert att1_detail["link_url"] == "https://updated.com/1"


class TestRecycleBinPermanentDelete:
    """Pattern 7+8: Permanent delete truly removes, restore truly recovers."""

    def test_permanent_delete_vs_restore_workflow(self):
        """
        Delete 2 books -> permanently delete one -> restore other
        -> verify one is gone forever, other is back.
        """
        uid = unique()
        book1 = api_post("/api/books", {"name": f"PermBook1-{uid}"}).json()
        book2 = api_post("/api/books", {"name": f"PermBook2-{uid}"}).json()

        # Add some content to book2
        ch = api_post("/api/chapters", {"name": f"PermCh-{uid}", "book_id": book2["id"]}).json()
        pg = api_post("/api/pages", {"name": f"PermPg-{uid}", "chapter_id": ch["id"]}).json()

        # Delete both books
        api_delete(f"/api/books/{book1['id']}")
        api_delete(f"/api/books/{book2['id']}")

        # Both in recycle bin
        bin_data = api_get("/api/recycle-bin").json()["data"]
        bin1 = [i for i in bin_data if i["entity_type"] == "book" and i["entity_id"] == book1["id"]]
        bin2 = [i for i in bin_data if i["entity_type"] == "book" and i["entity_id"] == book2["id"]]
        assert len(bin1) == 1
        assert len(bin2) == 1

        # Permanently delete book1
        r = api_delete(f"/api/recycle-bin/{bin1[0]['id']}")
        assert r.status_code == 200

        # Restore book2
        r = api_put(f"/api/recycle-bin/{bin2[0]['id']}/restore")
        assert r.status_code == 200

        # book1 completely gone
        assert api_get(f"/api/books/{book1['id']}").status_code == 404
        # Not in recycle bin either
        bin_after = api_get("/api/recycle-bin").json()["data"]
        assert not any(i["entity_id"] == book1["id"] and i["entity_type"] == "book" for i in bin_after)

        # book2 fully restored with children
        assert api_get(f"/api/books/{book2['id']}").status_code == 200
        assert api_get(f"/api/chapters/{ch['id']}").status_code == 200
        assert api_get(f"/api/pages/{pg['id']}").status_code == 200


class TestMultiUserEditTracking:
    """Pattern 6+7: Track created_by/updated_by across operations."""

    def test_multi_user_create_update_workflow(self):
        """
        User1 creates hierarchy -> User2 edits page -> verify tracking fields.
        """
        uid = unique()

        # User 1 creates
        book = api_post("/api/books", {"name": f"MuBook-{uid}"}).json()
        assert book["created_by"] == 1
        assert book["updated_by"] == 1

        ch = api_post("/api/chapters", {"name": f"MuCh-{uid}", "book_id": book["id"]}).json()
        page = api_post("/api/pages", {
            "name": f"MuPage-{uid}", "chapter_id": ch["id"], "html": "<p>User1 content</p>"
        }).json()
        assert page["created_by"] == 1

        # User 2 updates the page
        r = api_put(f"/api/pages/{page['id']}", {"html": "<p>User2 edit</p>"}, headers=HEADERS_USER2)
        assert r.status_code == 200
        updated = r.json()
        assert updated["created_by"] == 1  # Still user 1
        assert updated["updated_by"] == 2  # Now user 2

        # Verify via GET
        detail = api_get(f"/api/pages/{page['id']}").json()
        assert detail["created_by"] == 1
        assert detail["updated_by"] == 2
        assert detail["html"] == "<p>User2 edit</p>"

        # Revision should track who created it (user 2 triggered the edit)
        revs = api_get(f"/api/pages/{page['id']}/revisions").json()
        assert revs["total"] >= 1
        assert revs["data"][0]["created_by"] == 2


class TestComplexTagsWorkflow:
    """Pattern 2+5: Tags across multiple entity types in a workflow."""

    def test_tags_across_hierarchy(self):
        """
        Create shelf/book/chapter/page all with tags.
        Update tags selectively. Verify tag replacement semantics.
        """
        uid = unique()

        shelf = api_post("/api/shelves", {
            "name": f"TagWfShelf-{uid}",
            "tags": [{"name": "level", "value": "top"}]
        }).json()

        book = api_post("/api/books", {
            "name": f"TagWfBook-{uid}",
            "tags": [{"name": "subject", "value": "math"}, {"name": "grade", "value": "10"}]
        }).json()

        ch = api_post("/api/chapters", {
            "name": f"TagWfCh-{uid}",
            "book_id": book["id"],
            "tags": [{"name": "unit", "value": "algebra"}]
        }).json()

        page = api_post("/api/pages", {
            "name": f"TagWfPage-{uid}",
            "chapter_id": ch["id"],
            "html": "<p>Content</p>",
            "tags": [{"name": "difficulty", "value": "easy"}, {"name": "status", "value": "draft"}]
        }).json()

        # Verify all tags present
        shelf_detail = api_get(f"/api/shelves/{shelf['id']}").json()
        assert len(shelf_detail["tags"]) == 1
        assert shelf_detail["tags"][0]["value"] == "top"

        book_detail = api_get(f"/api/books/{book['id']}").json()
        assert len(book_detail["tags"]) == 2

        page_detail = api_get(f"/api/pages/{page['id']}").json()
        assert len(page_detail["tags"]) == 2

        # Update page tags — should REPLACE, not merge
        api_put(f"/api/pages/{page['id']}", {
            "tags": [{"name": "status", "value": "published"}]
        })
        page_updated = api_get(f"/api/pages/{page['id']}").json()
        assert len(page_updated["tags"]) == 1  # Only 1 tag now
        assert page_updated["tags"][0]["name"] == "status"
        assert page_updated["tags"][0]["value"] == "published"

        # Other entity tags unaffected
        book_check = api_get(f"/api/books/{book['id']}").json()
        assert len(book_check["tags"]) == 2


class TestPageExportWorkflow:
    """Pattern 5: Export correctly transforms content after edits."""

    def test_export_reflects_latest_content_after_edits(self):
        """
        Create page -> edit content -> export all formats
        -> verify exports reflect CURRENT content, not original.
        """
        uid = unique()
        book = api_post("/api/books", {"name": f"ExpWfBook-{uid}"}).json()
        page = api_post("/api/pages", {
            "name": f"ExpWfPage-{uid}",
            "book_id": book["id"],
            "html": "<h1>Old Title</h1><p>Old body</p>"
        }).json()

        # Edit page
        api_put(f"/api/pages/{page['id']}", {
            "html": "<h1>New Title</h1><p>New body with <strong>bold</strong></p>"
        })

        # HTML export — should be the new content
        html_r = api_get(f"/api/pages/{page['id']}/export/html")
        assert html_r.status_code == 200
        assert "New Title" in html_r.text
        assert "Old Title" not in html_r.text

        # Plaintext export — should strip HTML from new content
        txt_r = api_get(f"/api/pages/{page['id']}/export/plaintext")
        assert txt_r.status_code == 200
        assert "New Title" in txt_r.text
        assert "bold" in txt_r.text
        assert "<strong>" not in txt_r.text
        assert "<h1>" not in txt_r.text

        # Markdown export
        md_r = api_get(f"/api/pages/{page['id']}/export/markdown")
        assert md_r.status_code == 200
        assert "New Title" in md_r.text

        # Verify 404 for deleted page export
        api_delete(f"/api/pages/{page['id']}")
        assert api_get(f"/api/pages/{page['id']}/export/html").status_code == 404
        assert api_get(f"/api/pages/{page['id']}/export/plaintext").status_code == 404


class TestPriorityOrderingWorkflow:
    """Pattern 3+5: Priority ordering actually works with complex scenarios."""

    def test_mixed_priorities_in_book_contents(self):
        """
        Create chapters and direct pages with various priorities.
        Verify book contents are sorted by priority correctly.
        """
        uid = unique()
        book = api_post("/api/books", {"name": f"PriWfBook-{uid}"}).json()

        # Create with deliberate out-of-order priorities
        api_post("/api/chapters", {"name": f"PriCh-Z-{uid}", "book_id": book["id"], "priority": 30})
        api_post("/api/pages", {"name": f"PriPg-A-{uid}", "book_id": book["id"], "priority": 10})
        api_post("/api/chapters", {"name": f"PriCh-M-{uid}", "book_id": book["id"], "priority": 20})
        api_post("/api/pages", {"name": f"PriPg-B-{uid}", "book_id": book["id"], "priority": 5})
        api_post("/api/chapters", {"name": f"PriCh-A-{uid}", "book_id": book["id"], "priority": 1})

        # Get book contents
        detail = api_get(f"/api/books/{book['id']}").json()
        contents = detail["contents"]
        assert len(contents) >= 5

        # Verify sorted by priority ascending
        priorities = [c["priority"] for c in contents]
        assert priorities == sorted(priorities), f"Not sorted: {priorities}"

        # Verify first item has lowest priority
        assert contents[0]["priority"] == 1
        assert contents[-1]["priority"] == 30

    def test_chapter_pages_priority_after_page_move(self):
        """
        Move a page into a chapter — verify priority ordering in new location.
        """
        uid = unique()
        book = api_post("/api/books", {"name": f"PriMvBook-{uid}"}).json()
        ch = api_post("/api/chapters", {"name": f"PriMvCh-{uid}", "book_id": book["id"]}).json()

        # Create pages in chapter with priorities
        api_post("/api/pages", {"name": f"PriMvP1-{uid}", "chapter_id": ch["id"], "priority": 10})
        api_post("/api/pages", {"name": f"PriMvP2-{uid}", "chapter_id": ch["id"], "priority": 30})

        # Create a direct page and move it into the chapter
        direct_page = api_post("/api/pages", {
            "name": f"PriMvDirect-{uid}", "book_id": book["id"], "priority": 20
        }).json()
        api_put(f"/api/pages/{direct_page['id']}/move", {"chapter_id": ch["id"]})

        # Check chapter pages ordering
        ch_detail = api_get(f"/api/chapters/{ch['id']}").json()
        pages = ch_detail["pages"]
        assert len(pages) == 3
        priorities = [p["priority"] for p in pages]
        assert priorities == sorted(priorities)
