"""
BackendForge — L2 Integration Tests for Outline
Adversarial tests targeting common LLM implementation bugs.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_KEY = "admin-user-key"  # Must be the first request to become admin
MEMBER_KEY = f"member-integ-{uuid.uuid4().hex[:8]}"
VIEWER_KEY = f"viewer-integ-{uuid.uuid4().hex[:8]}"

ADMIN_H = {"X-Api-Key": ADMIN_KEY, "Content-Type": "application/json"}
MEMBER_H = {"X-Api-Key": MEMBER_KEY, "Content-Type": "application/json"}
VIEWER_H = {"X-Api-Key": VIEWER_KEY, "Content-Type": "application/json"}


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def api(path, json=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json is None else json,
        headers=ADMIN_H if headers is None else headers,
        timeout=30,
    )


def api_no_auth(path, json=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json is None else json,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


def setup_module(module):
    """Ensure admin is first user, then member, then set viewer role."""
    admin = api("/teams.info")  # admin auto-created first
    assert admin.status_code == 200, admin.text
    member = api("/teams.info", headers=MEMBER_H)  # member auto-created
    assert member.status_code == 200, member.text
    viewer_response = api("/teams.info", headers=VIEWER_H)  # viewer auto-created
    assert viewer_response.status_code == 200, viewer_response.text
    # Set viewer role
    resp = api("/users.list", {"limit": 100})
    assert resp.status_code == 200, resp.text
    viewer = next((u for u in resp.json()["data"] if u["name"] == VIEWER_KEY), None)
    assert viewer is not None, f"Viewer user {VIEWER_KEY!r} was not returned by users.list"
    if viewer["role"] != "viewer":
        updated = api("/users.update", {"id": viewer["id"], "role": "viewer"})
        assert updated.status_code == 200, updated.text


def _create_collection(name=None, **kw):
    r = api("/collections.create", {"name": name or _u("col-"), **kw})
    assert r.status_code == 200
    return r.json()["data"]


def _create_doc(col_id, title=None, text="", publish=True, **kw):
    r = api("/documents.create", {"title": title or _u("doc-"), "text": text, "collectionId": col_id, "publish": publish, **kw})
    assert r.status_code == 200
    return r.json()["data"]


# ═══════════════════════════════════════════════════════════
# L2 Tests — Integration (20-30 tests)
# ═══════════════════════════════════════════════════════════


class TestDocumentFieldNames:
    """Pattern 1+4: Verify exact camelCase field names in responses."""

    def test_document_response_has_correct_fields(self):
        """Document must have id, title, text, collectionId, createdBy, createdAt, etc."""
        col = _create_collection()
        title = _u("doc-fields-")
        r = api("/documents.create", {"title": title, "text": "content here", "collectionId": col["id"], "publish": True})
        assert r.status_code == 200
        doc = r.json()["data"]
        # Required camelCase fields
        assert doc["title"] == title
        assert doc["text"] == "content here"
        assert doc["collectionId"] == col["id"]
        assert "id" in doc
        assert "createdBy" in doc
        assert "createdAt" in doc
        assert "updatedAt" in doc
        assert "publishedAt" in doc
        assert doc["publishedAt"] is not None  # published=True
        assert doc["template"] is False
        assert "revision" in doc
        # No snake_case
        assert "collection_id" not in doc
        assert "created_by" not in doc
        assert "parent_document_id" not in doc

    def test_document_wrapped_in_data_field(self):
        """Response must be wrapped in {data: ...} object."""
        col = _create_collection()
        r = api("/documents.create", {"title": _u(), "collectionId": col["id"], "publish": True})
        assert "data" in r.json()
        assert isinstance(r.json()["data"], dict)

    def test_draft_document_has_null_publishedAt(self):
        """Unpublished doc has publishedAt = null."""
        col = _create_collection()
        r = api("/documents.create", {"title": _u("draft-"), "collectionId": col["id"], "publish": False})
        doc = r.json()["data"]
        assert doc["publishedAt"] is None


class TestCollectionFields:
    """Pattern 1+2: Collection nested sort object preserved."""

    def test_collection_response_fields(self):
        """Collection must have id, name, description, color, permission, sort, createdAt, updatedAt."""
        name = _u("col-test-")
        r = api("/collections.create", {
            "name": name,
            "description": "A test collection",
            "color": "#FF0000",
            "permission": "read_write",
            "sort": {"field": "title", "direction": "desc"},
        })
        assert r.status_code == 200
        col = r.json()["data"]
        assert col["name"] == name
        assert col["description"] == "A test collection"
        assert col["color"] == "#FF0000"
        assert col["permission"] == "read_write"
        assert col["sort"]["field"] == "title"
        assert col["sort"]["direction"] == "desc"
        assert "id" in col
        assert "createdAt" in col
        assert "updatedAt" in col

    def test_collection_sort_roundtrip(self):
        """Sort config preserved on get."""
        r = api("/collections.create", {"name": _u("sort-rt-"), "sort": {"field": "created_at", "direction": "asc"}})
        col_id = r.json()["data"]["id"]

        r = api("/collections.info", {"id": col_id})
        assert r.json()["data"]["sort"]["field"] == "created_at"
        assert r.json()["data"]["sort"]["direction"] == "asc"


class TestPaginationResponse:
    """Pattern 3: Pagination actually works, not just accepted."""

    def test_documents_list_pagination_object(self):
        """Response must include pagination with offset, limit, total."""
        col = _create_collection()
        _create_doc(col["id"])
        _create_doc(col["id"])
        _create_doc(col["id"])

        r = api("/documents.list", {"collectionId": col["id"], "offset": 0, "limit": 2})
        assert r.status_code == 200
        assert "pagination" in r.json()
        pag = r.json()["pagination"]
        assert pag["offset"] == 0
        assert pag["limit"] == 2
        assert pag["total"] >= 3
        assert len(r.json()["data"]) == 2

    def test_pagination_offset_skips_items(self):
        """offset=1 should skip the first item."""
        col = _create_collection()
        _create_doc(col["id"], title="First")
        _create_doc(col["id"], title="Second")
        _create_doc(col["id"], title="Third")

        r = api("/documents.list", {"collectionId": col["id"], "offset": 0, "limit": 100})
        all_ids = [d["id"] for d in r.json()["data"]]

        r = api("/documents.list", {"collectionId": col["id"], "offset": 1, "limit": 100})
        offset_ids = [d["id"] for d in r.json()["data"]]
        assert len(offset_ids) == len(all_ids) - 1
        assert all_ids[0] not in offset_ids

    def test_collections_list_pagination(self):
        """Collections list returns pagination object."""
        _create_collection()
        r = api("/collections.list", {"offset": 0, "limit": 5})
        assert "pagination" in r.json()
        assert "data" in r.json()
        assert r.json()["pagination"]["total"] >= 1


class TestDocumentDraftsAndPublish:
    """Pattern 5: Draft/publish logic truly works, not just accepted."""

    def test_draft_not_in_list_published_in_list(self):
        """Draft docs don't show in documents.list; published ones do."""
        col = _create_collection()
        draft = _create_doc(col["id"], title=_u("draft-"), publish=False)
        pub = _create_doc(col["id"], title=_u("pub-"), publish=True)

        r = api("/documents.list", {"collectionId": col["id"]})
        listed_ids = [d["id"] for d in r.json()["data"]]
        assert pub["id"] in listed_ids
        assert draft["id"] not in listed_ids

    def test_draft_appears_in_drafts_endpoint(self):
        """Draft doc appears in documents.drafts for its creator."""
        col = _create_collection()
        draft = _create_doc(col["id"], title=_u("my-draft-"), publish=False)

        r = api("/documents.drafts")
        draft_ids = [d["id"] for d in r.json()["data"]]
        assert draft["id"] in draft_ids

    def test_publish_via_update_moves_to_list(self):
        """Publishing a draft via update makes it appear in documents.list."""
        col = _create_collection()
        draft = _create_doc(col["id"], publish=False)

        # Not in list
        r = api("/documents.list", {"collectionId": col["id"]})
        assert draft["id"] not in [d["id"] for d in r.json()["data"]]

        # Publish it
        r = api("/documents.update", {"id": draft["id"], "publish": True})
        assert r.status_code == 200
        assert r.json()["data"]["publishedAt"] is not None

        # Now in list
        r = api("/documents.list", {"collectionId": col["id"]})
        assert draft["id"] in [d["id"] for d in r.json()["data"]]


class TestSearchActuallyWorks:
    """Pattern 3+5: Search returns relevant results with context."""

    def test_search_finds_document_by_title(self):
        """Search by title term returns the matching document."""
        col = _create_collection()
        unique_word = _u("xyzzy")
        doc = _create_doc(col["id"], title=f"Project {unique_word}", text="content body")

        r = api("/documents.search", {"query": unique_word})
        assert r.status_code == 200
        results = r.json()["data"]
        doc_ids = [sr["document"]["id"] for sr in results]
        assert doc["id"] in doc_ids

    def test_search_returns_context_field(self):
        """Search results include a 'context' string."""
        col = _create_collection()
        unique = _u("unique")
        _create_doc(col["id"], title="Normal", text=f"This doc contains {unique} word in it")

        r = api("/documents.search", {"query": unique})
        results = r.json()["data"]
        assert len(results) >= 1
        assert "context" in results[0]
        assert isinstance(results[0]["context"], str)
        assert len(results[0]["context"]) > 0

    def test_search_excludes_deleted_docs(self):
        """Deleted docs don't appear in search."""
        col = _create_collection()
        unique1 = _u("srch1")
        doc1 = _create_doc(col["id"], title=unique1, text=unique1)

        # Delete doc1
        api("/documents.delete", {"id": doc1["id"]})

        r = api("/documents.search", {"query": unique1})
        assert doc1["id"] not in [sr["document"]["id"] for sr in r.json()["data"]]


class TestRevisionsCreated:
    """Pattern 5+7: Revisions auto-created on updates."""

    def test_update_creates_revision(self):
        """Each update to title/text creates a new revision."""
        col = _create_collection()
        doc = _create_doc(col["id"], title="V1", text="Version 1 text")

        # Update once
        api("/documents.update", {"id": doc["id"], "title": "V2", "text": "Version 2 text"})
        # Update again
        api("/documents.update", {"id": doc["id"], "title": "V3", "text": "Version 3 text"})

        r = api("/revisions.list", {"documentId": doc["id"]})
        assert r.status_code == 200
        revs = r.json()["data"]
        assert len(revs) >= 2  # At least 2 revisions from updates

    def test_revision_stores_previous_content(self):
        """Revision contains the old title and text."""
        col = _create_collection()
        doc = _create_doc(col["id"], title="Original Title", text="Original text")

        api("/documents.update", {"id": doc["id"], "title": "New Title", "text": "New text"})

        r = api("/revisions.list", {"documentId": doc["id"]})
        revs = r.json()["data"]
        assert len(revs) >= 1
        # Most recent revision stores previous state
        rev = revs[0]
        assert rev["title"] == "Original Title"
        assert rev["text"] == "Original text"
        assert "id" in rev
        assert "documentId" in rev
        assert "createdAt" in rev


class TestSharePublicAccess:
    """Pattern 5: Share links work without auth."""

    def test_share_creates_urlId_and_public_access(self):
        """Create share → access via urlId without auth."""
        col = _create_collection()
        doc = _create_doc(col["id"], title=_u("shared-"), text="Public content")

        r = api("/shares.create", {"documentId": doc["id"]})
        assert r.status_code == 200
        share = r.json()["data"]
        assert "urlId" in share
        assert "id" in share
        assert share["documentId"] == doc["id"]
        url_id = share["urlId"]

        # Public access without auth
        r = api_no_auth("/shares.info", {"urlId": url_id})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["document"]["id"] == doc["id"]
        assert data["document"]["title"] == doc["title"]

    def test_revoked_share_returns_404(self):
        """After revoking, share.info returns 404."""
        col = _create_collection()
        doc = _create_doc(col["id"])
        r = api("/shares.create", {"documentId": doc["id"]})
        share = r.json()["data"]

        api("/shares.revoke", {"id": share["id"]})

        r = api_no_auth("/shares.info", {"urlId": share["urlId"]})
        assert r.status_code == 404


class TestStarsDuplicatePrevention:
    """Pattern 8: Duplicate star returns 400."""

    def test_star_document_then_duplicate_fails(self):
        """Starring same doc twice returns 400."""
        col = _create_collection()
        doc = _create_doc(col["id"])

        r = api("/stars.create", {"documentId": doc["id"]})
        assert r.status_code == 200
        star = r.json()["data"]
        assert star["documentId"] == doc["id"]
        assert "id" in star
        assert "createdAt" in star

        # Duplicate
        r = api("/stars.create", {"documentId": doc["id"]})
        assert r.status_code == 400

    def test_star_collection(self):
        """Can star a collection; fields correct."""
        col = _create_collection()
        r = api("/stars.create", {"collectionId": col["id"]})
        assert r.status_code == 200
        star = r.json()["data"]
        assert star["collectionId"] == col["id"]


class TestPinDuplicatePrevention:
    """Pattern 8: Duplicate pin returns 400."""

    def test_pin_document_then_duplicate_fails(self):
        """Pinning same doc in same collection twice returns 400."""
        col = _create_collection()
        doc = _create_doc(col["id"])

        r = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"], "index": 0})
        assert r.status_code == 200
        pin = r.json()["data"]
        assert pin["documentId"] == doc["id"]
        assert pin["collectionId"] == col["id"]
        assert "id" in pin

        # Duplicate
        r = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]})
        assert r.status_code == 400


class TestGroupUniqueness:
    """Pattern 8: Duplicate group name returns 400."""

    def test_duplicate_group_name_rejected(self):
        """Creating two groups with same name returns 400."""
        name = _u("grp-")
        r = api("/groups.create", {"name": name})
        assert r.status_code == 200
        assert r.json()["data"]["name"] == name
        assert "memberCount" in r.json()["data"]

        r = api("/groups.create", {"name": name})
        assert r.status_code == 400


class TestGroupMembershipDuplicate:
    """Pattern 8: Adding user to same group twice returns 400."""

    def test_duplicate_membership_rejected(self):
        """Adding same user to group twice returns 400."""
        r = api("/groups.create", {"name": _u("gm-grp-")})
        grp_id = r.json()["data"]["id"]

        # Get admin user id
        r = api("/users.list")
        admin_id = r.json()["data"][0]["id"]

        r = api("/group_memberships.create", {"groupId": grp_id, "userId": admin_id})
        assert r.status_code == 200
        assert r.json()["data"]["groupId"] == grp_id
        assert r.json()["data"]["userId"] == admin_id

        r = api("/group_memberships.create", {"groupId": grp_id, "userId": admin_id})
        assert r.status_code == 400


class TestCommentOwnership:
    """Pattern 6: Only comment author or admin can update/delete."""

    def test_member_cannot_update_others_comment(self):
        """Member cannot update admin's comment."""
        col = _create_collection()
        doc = _create_doc(col["id"])

        # Admin creates comment
        r = api("/comments.create", {"documentId": doc["id"], "text": "Admin's comment"})
        cmt_id = r.json()["data"]["id"]

        # Member tries to update
        r = api("/comments.update", {"id": cmt_id, "text": "hacked"}, headers=MEMBER_H)
        assert r.status_code == 403

    def test_comment_fields_correct(self):
        """Comment has id, documentId, text, resolved, createdBy, createdAt, updatedAt."""
        col = _create_collection()
        doc = _create_doc(col["id"])

        r = api("/comments.create", {"documentId": doc["id"], "text": "Great doc!"})
        assert r.status_code == 200
        cmt = r.json()["data"]
        assert cmt["text"] == "Great doc!"
        assert cmt["documentId"] == doc["id"]
        assert cmt["resolved"] is False
        assert "id" in cmt
        assert "createdBy" in cmt
        assert "createdAt" in cmt
        assert "updatedAt" in cmt


class TestSoftDelete:
    """Pattern 7: Soft delete removes from listings but doc still retrievable via info."""

    def test_deleted_doc_not_in_list(self):
        """Deleted doc disappears from documents.list."""
        col = _create_collection()
        doc = _create_doc(col["id"], title=_u("del-"))

        r = api("/documents.list", {"collectionId": col["id"]})
        assert doc["id"] in [d["id"] for d in r.json()["data"]]

        api("/documents.delete", {"id": doc["id"]})

        r = api("/documents.list", {"collectionId": col["id"]})
        assert doc["id"] not in [d["id"] for d in r.json()["data"]]


class TestCollectionPermissions:
    """Pattern 6: Read-only collections prevent member edits."""

    def test_member_cannot_create_in_read_collection(self):
        """Member cannot create docs in read-only collection."""
        col = _create_collection(permission="read")

        r = api("/documents.create", {"title": "Blocked", "collectionId": col["id"], "publish": True}, headers=MEMBER_H)
        assert r.status_code == 403

    def test_admin_can_create_in_read_collection(self):
        """Admin can always create docs regardless of permission."""
        col = _create_collection(permission="read")
        r = api("/documents.create", {"title": _u("admin-doc-"), "collectionId": col["id"], "publish": True})
        assert r.status_code == 200


class TestTemplateExclusion:
    """Pattern 5: Templates don't appear in list/search."""

    def test_template_not_in_list(self):
        """Template docs don't appear in documents.list."""
        col = _create_collection()
        tmpl = _create_doc(col["id"], title=_u("tmpl-"), template=True)
        normal = _create_doc(col["id"], title=_u("normal-"))

        r = api("/documents.list", {"collectionId": col["id"]})
        ids = [d["id"] for d in r.json()["data"]]
        assert normal["id"] in ids
        assert tmpl["id"] not in ids

    def test_template_accessible_via_info(self):
        """Template can still be retrieved by ID."""
        col = _create_collection()
        tmpl = _create_doc(col["id"], title=_u("tmpl-info-"), template=True)

        r = api("/documents.info", {"id": tmpl["id"]})
        assert r.status_code == 200
        assert r.json()["data"]["template"] is True
