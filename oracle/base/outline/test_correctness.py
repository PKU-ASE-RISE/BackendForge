"""
BackendForge — Comprehensive Correctness Tests for Outline Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# API keys — the key IS the user identifier (auto-created on first request)
ADMIN_KEY = "admin-user-key"  # First user auto-created becomes admin
MEMBER_KEY = f"member-user-{uuid.uuid4().hex[:8]}"
VIEWER_KEY = f"viewer-user-{uuid.uuid4().hex[:8]}"

ADMIN_HEADERS = {"X-Api-Key": ADMIN_KEY, "Content-Type": "application/json"}
MEMBER_HEADERS = {"X-Api-Key": MEMBER_KEY, "Content-Type": "application/json"}
VIEWER_HEADERS = {"X-Api-Key": VIEWER_KEY, "Content-Type": "application/json"}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api(path, json_data=None, headers=None):
    """All Outline API calls are POST."""
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json_data is None else json_data,
        headers=ADMIN_HEADERS if headers is None else headers,
        timeout=30,
    )


def api_no_auth(path, json_data=None):
    """POST without auth header."""
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json_data is None else json_data,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


# ── Setup helpers ──

def ensure_admin():
    """Make a request with ADMIN_KEY to ensure the admin user is auto-created first."""
    response = api("/teams.info", headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text


def ensure_member():
    """Ensure member user exists (created after admin)."""
    ensure_admin()
    response = api("/teams.info", headers=MEMBER_HEADERS)
    assert response.status_code == 200, response.text


def ensure_viewer():
    """Ensure viewer user exists then set role to viewer."""
    ensure_admin()
    # Trigger auto-create
    response = api("/teams.info", headers=VIEWER_HEADERS)
    assert response.status_code == 200, response.text
    # Get user list to find viewer's id
    resp = api("/users.list", {"limit": 100}, headers=ADMIN_HEADERS)
    assert resp.status_code == 200, resp.text
    users = resp.json()["data"]
    viewer = None
    for u in users:
        if u["name"] == VIEWER_KEY:
            viewer = u
            break
    assert viewer is not None, f"Viewer user {VIEWER_KEY!r} was not returned by users.list"
    if viewer["role"] != "viewer":
        response = api(
            "/users.update",
            {"id": viewer["id"], "role": "viewer"},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 200, response.text


def create_member_user(prefix):
    """Create a disposable member and return its API representation."""
    ensure_admin()
    user_key = f"{prefix}-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": user_key, "Content-Type": "application/json"}
    response = api("/teams.info", headers=headers)
    assert response.status_code == 200, response.text

    response = api("/users.list", {"limit": 100}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    user = next((item for item in response.json()["data"] if item["name"] == user_key), None)
    assert user is not None, f"Member user {user_key!r} was not returned by users.list"
    return user


def create_collection(name=None, headers=None, **kwargs):
    """Helper to create a collection."""
    name = name or f"Collection-{uuid.uuid4().hex[:8]}"
    body = {"name": name, **kwargs}
    resp = api(
        "/collections.create",
        body,
        headers=ADMIN_HEADERS if headers is None else headers,
    )
    assert resp.status_code == 200, f"Failed to create collection: {resp.text}"
    return resp.json()["data"]


def create_document(collection_id, title=None, text="", publish=True, headers=None, **kwargs):
    """Helper to create a document."""
    title = title or f"Doc-{uuid.uuid4().hex[:8]}"
    body = {"title": title, "text": text, "collectionId": collection_id, "publish": publish, **kwargs}
    resp = api(
        "/documents.create",
        body,
        headers=ADMIN_HEADERS if headers is None else headers,
    )
    assert resp.status_code == 200, f"Failed to create document: {resp.text}"
    return resp.json()["data"]


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401_collections(self):
        resp = api_no_auth("/collections.list")
        assert resp.status_code == 401

    def test_missing_header_returns_401_documents(self):
        resp = api_no_auth("/documents.list")
        assert resp.status_code == 401

    def test_missing_header_returns_401_users(self):
        resp = api_no_auth("/users.list")
        assert resp.status_code == 401

    def test_auto_create_first_user_as_admin(self):
        ensure_admin()
        resp = api("/users.list", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()["data"]
        admin = next((u for u in users if u["name"] == ADMIN_KEY), None)
        assert admin is not None
        assert admin["role"] == "admin"

    def test_subsequent_user_is_member(self):
        ensure_member()
        resp = api("/users.list", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()["data"]
        member = next((u for u in users if u["name"] == MEMBER_KEY), None)
        assert member is not None
        assert member["role"] == "member"

    def test_shares_info_no_auth_required(self):
        """shares.info is the only endpoint that doesn't require auth."""
        resp = api_no_auth("/shares.info", {"urlId": "nonexistent"})
        # Should be 404 (not found), not 401
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 2: Teams
# ════════════════════════════════════════════════════════════════════


class TestTeams:

    def test_get_team_info(self):
        ensure_admin()
        resp = api("/teams.info", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        team = resp.json()["data"]
        assert "id" in team
        assert "name" in team
        assert "memberCount" in team
        assert "createdAt" in team

    def test_update_team_name(self):
        ensure_admin()
        original_name = api("/teams.info", headers=ADMIN_HEADERS).json()["data"]["name"]
        new_name = f"Team-{UNIQUE}"
        try:
            resp = api("/teams.update", {"name": new_name}, headers=ADMIN_HEADERS)
            assert resp.status_code == 200
            team = resp.json()["data"]
            assert team["name"] == new_name
        finally:
            api("/teams.update", {"name": original_name}, headers=ADMIN_HEADERS)

    def test_update_team_non_admin_forbidden(self):
        ensure_member()
        original_name = api("/teams.info", headers=ADMIN_HEADERS).json()["data"]["name"]
        try:
            resp = api("/teams.update", {"name": "Hacked"}, headers=MEMBER_HEADERS)
            assert resp.status_code == 403
        finally:
            api("/teams.update", {"name": original_name}, headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════
# PART 3: Collections CRUD
# ════════════════════════════════════════════════════════════════════


class TestCollectionsCRUD:

    def test_create_collection(self):
        ensure_admin()
        name = f"TestCol-{UNIQUE}"
        resp = api("/collections.create", {
            "name": name,
            "description": "A test collection",
            "color": "#FF0000",
        })
        assert resp.status_code == 200
        col = resp.json()["data"]
        assert col["name"] == name
        assert col["description"] == "A test collection"
        assert col["color"] == "#FF0000"
        assert col["permission"] == "read_write"  # default
        assert "id" in col
        assert "createdAt" in col

    def test_create_collection_with_sort(self):
        ensure_admin()
        resp = api("/collections.create", {
            "name": f"SortCol-{UNIQUE}",
            "sort": {"field": "title", "direction": "desc"},
        })
        assert resp.status_code == 200
        col = resp.json()["data"]
        assert col["sort"]["field"] == "title"
        assert col["sort"]["direction"] == "desc"

    def test_create_collection_read_only(self):
        ensure_admin()
        resp = api("/collections.create", {
            "name": f"ReadCol-{UNIQUE}",
            "permission": "read",
        })
        assert resp.status_code == 200
        col = resp.json()["data"]
        assert col["permission"] == "read"

    def test_get_collection(self):
        ensure_admin()
        col = create_collection(f"GetCol-{UNIQUE}")
        resp = api("/collections.info", {"id": col["id"]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == col["id"]
        assert data["name"] == col["name"]

    def test_get_nonexistent_collection(self):
        ensure_admin()
        fake_id = str(uuid.uuid4())
        resp = api("/collections.info", {"id": fake_id})
        assert resp.status_code == 404

    def test_update_collection(self):
        ensure_admin()
        col = create_collection(f"UpdCol-{UNIQUE}")
        resp = api("/collections.update", {
            "id": col["id"],
            "name": f"Updated-{UNIQUE}",
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == f"Updated-{UNIQUE}"
        assert data["description"] == "Updated desc"

    def test_delete_collection(self):
        ensure_admin()
        col = create_collection(f"DelCol-{UNIQUE}")
        resp = api("/collections.delete", {"id": col["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify gone
        info_resp = api("/collections.info", {"id": col["id"]})
        assert info_resp.status_code == 404

    def test_list_collections(self):
        ensure_admin()
        col = create_collection(f"ListCol-{UNIQUE}")
        resp = api("/collections.list", {"limit": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        names = [c["name"] for c in data["data"]]
        assert col["name"] in names

    def test_list_collections_pagination(self):
        ensure_admin()
        # Create a few collections
        for i in range(3):
            create_collection(f"PagCol-{UNIQUE}-{i}")
        resp = api("/collections.list", {"offset": 0, "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 2
        assert data["pagination"]["limit"] == 2
        assert "total" in data["pagination"]

    def test_member_cannot_create_collection(self):
        """Only admins can create collections."""
        ensure_member()
        resp = api("/collections.create", {"name": f"MemberCol-{UNIQUE}"}, headers=MEMBER_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 4: Documents CRUD
# ════════════════════════════════════════════════════════════════════


class TestDocumentsCRUD:

    def test_create_document(self):
        ensure_admin()
        col = create_collection(f"DocCol-{UNIQUE}")
        resp = api("/documents.create", {
            "title": f"TestDoc-{UNIQUE}",
            "text": "# Hello\n\nThis is a test document.",
            "collectionId": col["id"],
            "publish": True,
        })
        assert resp.status_code == 200
        doc = resp.json()["data"]
        assert doc["title"] == f"TestDoc-{UNIQUE}"
        assert doc["text"] == "# Hello\n\nThis is a test document."
        assert doc["collectionId"] == col["id"]
        assert doc["publishedAt"] is not None
        assert doc["template"] is False
        assert "id" in doc
        assert "createdAt" in doc
        assert "createdBy" in doc

    def test_create_document_as_draft(self):
        ensure_admin()
        col = create_collection(f"DraftCol-{UNIQUE}")
        resp = api("/documents.create", {
            "title": f"DraftDoc-{UNIQUE}",
            "text": "Draft content",
            "collectionId": col["id"],
            "publish": False,
        })
        assert resp.status_code == 200
        doc = resp.json()["data"]
        assert doc["publishedAt"] is None

    def test_create_document_as_template(self):
        ensure_admin()
        col = create_collection(f"TplCol-{UNIQUE}")
        resp = api("/documents.create", {
            "title": f"Template-{UNIQUE}",
            "text": "Template content",
            "collectionId": col["id"],
            "template": True,
            "publish": True,
        })
        assert resp.status_code == 200
        doc = resp.json()["data"]
        assert doc["template"] is True

    def test_get_document(self):
        ensure_admin()
        col = create_collection(f"GetDocCol-{UNIQUE}")
        doc = create_document(col["id"], f"GetDoc-{UNIQUE}")
        resp = api("/documents.info", {"id": doc["id"]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == doc["id"]
        assert data["title"] == doc["title"]

    def test_get_nonexistent_document(self):
        ensure_admin()
        resp = api("/documents.info", {"id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_update_document(self):
        ensure_admin()
        col = create_collection(f"UpdDocCol-{UNIQUE}")
        doc = create_document(col["id"], f"UpdDoc-{UNIQUE}", text="Original")
        resp = api("/documents.update", {
            "id": doc["id"],
            "title": f"Updated-{UNIQUE}",
            "text": "Updated content",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == f"Updated-{UNIQUE}"
        assert data["text"] == "Updated content"

    def test_update_publish_document(self):
        ensure_admin()
        col = create_collection(f"PubDocCol-{UNIQUE}")
        doc = create_document(col["id"], f"PubDoc-{UNIQUE}", publish=False)
        assert doc["publishedAt"] is None
        resp = api("/documents.update", {"id": doc["id"], "publish": True})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["publishedAt"] is not None

    def test_delete_document(self):
        ensure_admin()
        col = create_collection(f"DelDocCol-{UNIQUE}")
        doc = create_document(col["id"], f"DelDoc-{UNIQUE}")
        resp = api("/documents.delete", {"id": doc["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Should not appear in list
        list_resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in list_resp.json()["data"]]
        assert doc["id"] not in doc_ids

    def test_list_documents(self):
        ensure_admin()
        col = create_collection(f"ListDocCol-{UNIQUE}")
        doc = create_document(col["id"], f"ListDoc-{UNIQUE}")
        resp = api("/documents.list", {"collectionId": col["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        doc_ids = [d["id"] for d in data["data"]]
        assert doc["id"] in doc_ids

    def test_list_documents_excludes_templates(self):
        """Templates should not appear in documents.list."""
        ensure_admin()
        col = create_collection(f"TplListCol-{UNIQUE}")
        template = create_document(col["id"], f"TplDoc-{UNIQUE}", template=True)
        normal = create_document(col["id"], f"NormalDoc-{UNIQUE}")
        resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert normal["id"] in doc_ids
        assert template["id"] not in doc_ids

    def test_list_documents_excludes_archived(self):
        """Archived documents should not appear in documents.list."""
        ensure_admin()
        col = create_collection(f"ArchListCol-{UNIQUE}")
        doc = create_document(col["id"], f"ArchDoc-{UNIQUE}")
        api("/documents.archive", {"id": doc["id"]})
        resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert doc["id"] not in doc_ids

    def test_list_documents_excludes_deleted(self):
        """Deleted documents should not appear in documents.list."""
        ensure_admin()
        col = create_collection(f"DelListCol-{UNIQUE}")
        doc = create_document(col["id"], f"DelListDoc-{UNIQUE}")
        api("/documents.delete", {"id": doc["id"]})
        resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert doc["id"] not in doc_ids

    def test_list_documents_pagination(self):
        ensure_admin()
        col = create_collection(f"PagDocCol-{UNIQUE}")
        for i in range(4):
            create_document(col["id"], f"PagDoc-{UNIQUE}-{i}")
        resp = api("/documents.list", {"collectionId": col["id"], "offset": 0, "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 2
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] >= 4


# ════════════════════════════════════════════════════════════════════
# PART 5: Document Hierarchy
# ════════════════════════════════════════════════════════════════════


class TestDocumentHierarchy:

    def test_create_child_document(self):
        ensure_admin()
        col = create_collection(f"HierCol-{UNIQUE}")
        parent = create_document(col["id"], f"Parent-{UNIQUE}")
        child = create_document(col["id"], f"Child-{UNIQUE}", parentDocumentId=parent["id"])
        assert child["parentDocumentId"] == parent["id"]
        assert child["collectionId"] == col["id"]

    def test_move_document_to_different_collection(self):
        ensure_admin()
        col1 = create_collection(f"MoveCol1-{UNIQUE}")
        col2 = create_collection(f"MoveCol2-{UNIQUE}")
        doc = create_document(col1["id"], f"MoveDoc-{UNIQUE}")
        resp = api("/documents.move", {"id": doc["id"], "collectionId": col2["id"]})
        assert resp.status_code == 200
        moved = resp.json()["data"]
        assert moved["collectionId"] == col2["id"]

    def test_move_document_moves_children(self):
        """Moving a parent also moves all children to the new collection."""
        ensure_admin()
        col1 = create_collection(f"MoveChCol1-{UNIQUE}")
        col2 = create_collection(f"MoveChCol2-{UNIQUE}")
        parent = create_document(col1["id"], f"MoveParent-{UNIQUE}")
        child = create_document(col1["id"], f"MoveChild-{UNIQUE}", parentDocumentId=parent["id"])

        api("/documents.move", {"id": parent["id"], "collectionId": col2["id"]})

        # Check child also moved
        child_resp = api("/documents.info", {"id": child["id"]})
        assert child_resp.json()["data"]["collectionId"] == col2["id"]

    def test_archive_cascades_to_children(self):
        """Archiving a parent archives all children."""
        ensure_admin()
        col = create_collection(f"ArchCascCol-{UNIQUE}")
        parent = create_document(col["id"], f"ArchParent-{UNIQUE}")
        child = create_document(col["id"], f"ArchChild-{UNIQUE}", parentDocumentId=parent["id"])

        api("/documents.archive", {"id": parent["id"]})

        # Check child is archived
        child_resp = api("/documents.info", {"id": child["id"]})
        assert child_resp.json()["data"]["archivedAt"] is not None

    def test_delete_cascades_to_children(self):
        """Deleting a parent also soft-deletes all children."""
        ensure_admin()
        col = create_collection(f"DelCascCol-{UNIQUE}")
        parent = create_document(col["id"], f"DelParent-{UNIQUE}")
        child = create_document(col["id"], f"DelChild-{UNIQUE}", parentDocumentId=parent["id"])

        api("/documents.delete", {"id": parent["id"]})

        # Child should not be in list
        list_resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in list_resp.json()["data"]]
        assert child["id"] not in doc_ids


# ════════════════════════════════════════════════════════════════════
# PART 6: Drafts and Publishing
# ════════════════════════════════════════════════════════════════════


class TestDraftsAndPublishing:

    def test_drafts_list_shows_own_drafts(self):
        ensure_admin()
        col = create_collection(f"DraftListCol-{UNIQUE}")
        draft = create_document(col["id"], f"MyDraft-{UNIQUE}", publish=False)
        resp = api("/documents.drafts", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert draft["id"] in doc_ids

    def test_drafts_not_in_documents_list(self):
        """Unpublished drafts should not appear in documents.list."""
        ensure_admin()
        col = create_collection(f"DraftNotListCol-{UNIQUE}")
        draft = create_document(col["id"], f"HiddenDraft-{UNIQUE}", publish=False)
        resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert draft["id"] not in doc_ids

    def test_publish_draft_makes_it_visible(self):
        ensure_admin()
        col = create_collection(f"PubDraftCol-{UNIQUE}")
        draft = create_document(col["id"], f"PubDraft-{UNIQUE}", publish=False)
        # Publish it
        api("/documents.update", {"id": draft["id"], "publish": True})
        # Should now appear in list
        resp = api("/documents.list", {"collectionId": col["id"]})
        doc_ids = [d["id"] for d in resp.json()["data"]]
        assert draft["id"] in doc_ids


# ════════════════════════════════════════════════════════════════════
# PART 7: Search
# ════════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_basic(self):
        ensure_admin()
        col = create_collection(f"SearchCol-{UNIQUE}")
        create_document(col["id"], f"Quantum-{UNIQUE}", text="Quantum computing is fascinating")
        resp = api("/documents.search", {"query": "Quantum"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        # Should find at least one result
        assert len(data["data"]) >= 1
        # Each result has document and context
        result = data["data"][0]
        assert "document" in result
        assert "context" in result

    def test_search_title_ranks_higher(self):
        """Documents with query in title should rank higher than content-only matches."""
        ensure_admin()
        col = create_collection(f"RankCol-{UNIQUE}")
        # Doc with match only in content
        content_doc = create_document(col["id"], f"Unrelated-{UNIQUE}",
                                      text=f"This has the word Xylophone{UNIQUE} in body")
        # Doc with match in title
        title_doc = create_document(col["id"], f"Xylophone{UNIQUE}",
                                    text="Some other content here")
        resp = api("/documents.search", {"query": f"Xylophone{UNIQUE}"})
        results = resp.json()["data"]
        assert len(results) >= 2
        # First result should be the title match
        assert results[0]["document"]["id"] == title_doc["id"]

    def test_search_excludes_templates(self):
        """Templates should not appear in search results."""
        ensure_admin()
        col = create_collection(f"SearchTplCol-{UNIQUE}")
        template = create_document(col["id"], f"SearchTpl-{UNIQUE}",
                                   text=f"Searchable{UNIQUE}", template=True)
        resp = api("/documents.search", {"query": f"Searchable{UNIQUE}"})
        doc_ids = [r["document"]["id"] for r in resp.json()["data"]]
        assert template["id"] not in doc_ids

    def test_search_excludes_deleted(self):
        ensure_admin()
        col = create_collection(f"SearchDelCol-{UNIQUE}")
        doc = create_document(col["id"], f"SearchDel-{UNIQUE}",
                              text=f"Deletable{UNIQUE}")
        api("/documents.delete", {"id": doc["id"]})
        resp = api("/documents.search", {"query": f"Deletable{UNIQUE}"})
        doc_ids = [r["document"]["id"] for r in resp.json()["data"]]
        assert doc["id"] not in doc_ids

    def test_search_context_snippet(self):
        """Search results should include context with a snippet."""
        ensure_admin()
        col = create_collection(f"CtxCol-{UNIQUE}")
        create_document(col["id"], f"CtxDoc-{UNIQUE}",
                        text=f"The word Elephant{UNIQUE} appears in this sentence")
        resp = api("/documents.search", {"query": f"Elephant{UNIQUE}"})
        results = resp.json()["data"]
        assert len(results) >= 1
        context = results[0]["context"]
        assert f"Elephant{UNIQUE}" in context

    def test_search_filter_by_collection(self):
        ensure_admin()
        col1 = create_collection(f"SFCol1-{UNIQUE}")
        col2 = create_collection(f"SFCol2-{UNIQUE}")
        doc1 = create_document(col1["id"], f"SFDoc1-{UNIQUE}", text=f"Zeppelin{UNIQUE}")
        doc2 = create_document(col2["id"], f"SFDoc2-{UNIQUE}", text=f"Zeppelin{UNIQUE}")
        resp = api("/documents.search", {"query": f"Zeppelin{UNIQUE}", "collectionId": col1["id"]})
        doc_ids = [r["document"]["id"] for r in resp.json()["data"]]
        assert doc1["id"] in doc_ids
        assert doc2["id"] not in doc_ids


# ════════════════════════════════════════════════════════════════════
# PART 8: Revisions
# ════════════════════════════════════════════════════════════════════


class TestRevisions:

    def test_revision_created_on_update(self):
        ensure_admin()
        col = create_collection(f"RevCol-{UNIQUE}")
        doc = create_document(col["id"], f"RevDoc-{UNIQUE}", text="Version 1")
        # Update document
        api("/documents.update", {"id": doc["id"], "text": "Version 2"})
        # List revisions
        resp = api("/revisions.list", {"documentId": doc["id"]})
        assert resp.status_code == 200
        revisions = resp.json()["data"]
        assert len(revisions) >= 1
        # The revision should contain the old text
        assert revisions[0]["text"] == "Version 1"

    def test_multiple_revisions(self):
        ensure_admin()
        col = create_collection(f"MultiRevCol-{UNIQUE}")
        doc = create_document(col["id"], f"MultiRevDoc-{UNIQUE}", text="V1")
        api("/documents.update", {"id": doc["id"], "text": "V2"})
        api("/documents.update", {"id": doc["id"], "text": "V3"})
        resp = api("/revisions.list", {"documentId": doc["id"]})
        revisions = resp.json()["data"]
        assert len(revisions) >= 2
        # Newest first
        assert revisions[0]["text"] == "V2"
        assert revisions[1]["text"] == "V1"

    def test_get_specific_revision(self):
        ensure_admin()
        col = create_collection(f"SpecRevCol-{UNIQUE}")
        doc = create_document(col["id"], f"SpecRevDoc-{UNIQUE}", text="Original")
        api("/documents.update", {"id": doc["id"], "title": "New Title", "text": "Changed"})
        revisions = api("/revisions.list", {"documentId": doc["id"]}).json()["data"]
        rev_id = revisions[0]["id"]
        resp = api("/revisions.info", {"id": rev_id})
        assert resp.status_code == 200
        rev = resp.json()["data"]
        assert rev["id"] == rev_id
        assert rev["documentId"] == doc["id"]
        assert rev["title"] == f"SpecRevDoc-{UNIQUE}"
        assert rev["text"] == "Original"

    def test_revision_not_found(self):
        ensure_admin()
        resp = api("/revisions.info", {"id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_revisions_list_document_not_found(self):
        ensure_admin()
        resp = api("/revisions.list", {"documentId": str(uuid.uuid4())})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Shares
# ════════════════════════════════════════════════════════════════════


class TestShares:

    def test_create_share(self):
        ensure_admin()
        col = create_collection(f"ShareCol-{UNIQUE}")
        doc = create_document(col["id"], f"ShareDoc-{UNIQUE}", text="Shared content")
        resp = api("/shares.create", {"documentId": doc["id"]})
        assert resp.status_code == 200
        share = resp.json()["data"]
        assert share["documentId"] == doc["id"]
        assert "urlId" in share
        assert "id" in share
        assert len(share["urlId"]) > 0

    def test_access_share_without_auth(self):
        """shares.info works without authentication."""
        ensure_admin()
        col = create_collection(f"PubShareCol-{UNIQUE}")
        doc = create_document(col["id"], f"PubShareDoc-{UNIQUE}", text="Public content")
        share = api("/shares.create", {"documentId": doc["id"]}).json()["data"]
        # Access without auth
        resp = api_no_auth("/shares.info", {"urlId": share["urlId"]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["document"]["id"] == doc["id"]
        assert data["document"]["text"] == "Public content"

    def test_share_include_child_documents(self):
        ensure_admin()
        col = create_collection(f"ChildShareCol-{UNIQUE}")
        parent = create_document(col["id"], f"ParentShare-{UNIQUE}", text="Parent")
        child = create_document(col["id"], f"ChildShare-{UNIQUE}", text="Child",
                                parentDocumentId=parent["id"])
        share = api("/shares.create", {
            "documentId": parent["id"],
            "includeChildDocuments": True,
        }).json()["data"]
        resp = api_no_auth("/shares.info", {"urlId": share["urlId"]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["childDocuments"] is not None
        child_ids = [d["id"] for d in data["childDocuments"]]
        assert child["id"] in child_ids

    def test_share_without_children_returns_null(self):
        ensure_admin()
        col = create_collection(f"NoChildShareCol-{UNIQUE}")
        parent = create_document(col["id"], f"NoChildShare-{UNIQUE}", text="Parent only")
        child = create_document(col["id"], f"ChildNoShare-{UNIQUE}",
                                parentDocumentId=parent["id"])
        share = api("/shares.create", {
            "documentId": parent["id"],
            "includeChildDocuments": False,
        }).json()["data"]
        resp = api_no_auth("/shares.info", {"urlId": share["urlId"]})
        data = resp.json()["data"]
        assert data["childDocuments"] is None

    def test_list_shares(self):
        ensure_admin()
        col = create_collection(f"ListShareCol-{UNIQUE}")
        doc = create_document(col["id"], f"ListShareDoc-{UNIQUE}")
        share = api("/shares.create", {"documentId": doc["id"]}).json()["data"]
        resp = api("/shares.list")
        assert resp.status_code == 200
        data = resp.json()
        share_ids = [s["id"] for s in data["data"]]
        assert share["id"] in share_ids

    def test_revoke_share(self):
        ensure_admin()
        col = create_collection(f"RevokeShareCol-{UNIQUE}")
        doc = create_document(col["id"], f"RevokeShareDoc-{UNIQUE}")
        share = api("/shares.create", {"documentId": doc["id"]}).json()["data"]
        resp = api("/shares.revoke", {"id": share["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Share should no longer work
        info_resp = api_no_auth("/shares.info", {"urlId": share["urlId"]})
        assert info_resp.status_code == 404

    def test_share_nonexistent_document(self):
        ensure_admin()
        resp = api("/shares.create", {"documentId": str(uuid.uuid4())})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Stars
# ════════════════════════════════════════════════════════════════════


class TestStars:

    def test_star_document(self):
        ensure_admin()
        col = create_collection(f"StarCol-{UNIQUE}")
        doc = create_document(col["id"], f"StarDoc-{UNIQUE}")
        resp = api("/stars.create", {"documentId": doc["id"]})
        assert resp.status_code == 200
        star = resp.json()["data"]
        assert star["documentId"] == doc["id"]
        assert star["collectionId"] is None
        assert "id" in star

    def test_star_collection(self):
        ensure_admin()
        col = create_collection(f"StarredCol-{UNIQUE}")
        resp = api("/stars.create", {"collectionId": col["id"]})
        assert resp.status_code == 200
        star = resp.json()["data"]
        assert star["collectionId"] == col["id"]
        assert star["documentId"] is None

    def test_cannot_star_twice(self):
        ensure_admin()
        col = create_collection(f"DupStarCol-{UNIQUE}")
        doc = create_document(col["id"], f"DupStarDoc-{UNIQUE}")
        api("/stars.create", {"documentId": doc["id"]})
        resp = api("/stars.create", {"documentId": doc["id"]})
        assert resp.status_code == 400

    def test_list_stars(self):
        ensure_admin()
        col = create_collection(f"ListStarCol-{UNIQUE}")
        doc = create_document(col["id"], f"ListStarDoc-{UNIQUE}")
        star = api("/stars.create", {"documentId": doc["id"]}).json()["data"]
        resp = api("/stars.list")
        assert resp.status_code == 200
        star_ids = [s["id"] for s in resp.json()["data"]]
        assert star["id"] in star_ids

    def test_delete_star(self):
        ensure_admin()
        col = create_collection(f"DelStarCol-{UNIQUE}")
        doc = create_document(col["id"], f"DelStarDoc-{UNIQUE}")
        star = api("/stars.create", {"documentId": doc["id"]}).json()["data"]
        resp = api("/stars.delete", {"id": star["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify gone
        list_resp = api("/stars.list")
        star_ids = [s["id"] for s in list_resp.json()["data"]]
        assert star["id"] not in star_ids

    def test_star_nonexistent_document(self):
        ensure_admin()
        resp = api("/stars.create", {"documentId": str(uuid.uuid4())})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Comments
# ════════════════════════════════════════════════════════════════════


class TestComments:

    def test_create_comment(self):
        ensure_admin()
        col = create_collection(f"CmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"CmtDoc-{UNIQUE}")
        resp = api("/comments.create", {"documentId": doc["id"], "text": "Great doc!"})
        assert resp.status_code == 200
        comment = resp.json()["data"]
        assert comment["documentId"] == doc["id"]
        assert comment["text"] == "Great doc!"
        assert comment["resolved"] is False
        assert "id" in comment
        assert "createdBy" in comment

    def test_list_comments(self):
        ensure_admin()
        col = create_collection(f"ListCmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"ListCmtDoc-{UNIQUE}")
        cmt = api("/comments.create", {"documentId": doc["id"], "text": "Comment A"}).json()["data"]
        resp = api("/comments.list", {"documentId": doc["id"]})
        assert resp.status_code == 200
        data = resp.json()
        comment_ids = [c["id"] for c in data["data"]]
        assert cmt["id"] in comment_ids

    def test_update_comment_text(self):
        ensure_admin()
        col = create_collection(f"UpdCmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"UpdCmtDoc-{UNIQUE}")
        cmt = api("/comments.create", {"documentId": doc["id"], "text": "Old text"}).json()["data"]
        resp = api("/comments.update", {"id": cmt["id"], "text": "New text"})
        assert resp.status_code == 200
        assert resp.json()["data"]["text"] == "New text"

    def test_resolve_comment(self):
        ensure_admin()
        col = create_collection(f"ResCmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"ResCmtDoc-{UNIQUE}")
        cmt = api("/comments.create", {"documentId": doc["id"], "text": "Issue"}).json()["data"]
        resp = api("/comments.update", {"id": cmt["id"], "resolved": True})
        assert resp.status_code == 200
        assert resp.json()["data"]["resolved"] is True

    def test_delete_comment(self):
        ensure_admin()
        col = create_collection(f"DelCmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"DelCmtDoc-{UNIQUE}")
        cmt = api("/comments.create", {"documentId": doc["id"], "text": "Bye"}).json()["data"]
        resp = api("/comments.delete", {"id": cmt["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify gone
        list_resp = api("/comments.list", {"documentId": doc["id"]})
        cmt_ids = [c["id"] for c in list_resp.json()["data"]]
        assert cmt["id"] not in cmt_ids

    def test_comment_on_nonexistent_document(self):
        ensure_admin()
        resp = api("/comments.create", {"documentId": str(uuid.uuid4()), "text": "Hello"})
        assert resp.status_code == 404

    def test_non_author_cannot_update_comment(self):
        """Only comment author or admin can update."""
        ensure_member()
        col = create_collection(f"AuthCmtCol-{UNIQUE}")
        doc = create_document(col["id"], f"AuthCmtDoc-{UNIQUE}")
        # Member creates comment
        cmt = api("/comments.create", {"documentId": doc["id"], "text": "My comment"},
                  headers=MEMBER_HEADERS).json()["data"]
        # Another member key tries to update
        other_key = f"other-member-{uuid.uuid4().hex[:8]}"
        other_headers = {"X-Api-Key": other_key, "Content-Type": "application/json"}
        api("/teams.info", headers=other_headers)  # auto-create
        resp = api("/comments.update", {"id": cmt["id"], "text": "Hacked"}, headers=other_headers)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 12: Pins
# ════════════════════════════════════════════════════════════════════


class TestPins:

    def test_create_pin(self):
        ensure_admin()
        col = create_collection(f"PinCol-{UNIQUE}")
        doc = create_document(col["id"], f"PinDoc-{UNIQUE}")
        resp = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]})
        assert resp.status_code == 200
        pin = resp.json()["data"]
        assert pin["documentId"] == doc["id"]
        assert pin["collectionId"] == col["id"]
        assert "id" in pin

    def test_cannot_pin_twice(self):
        ensure_admin()
        col = create_collection(f"DupPinCol-{UNIQUE}")
        doc = create_document(col["id"], f"DupPinDoc-{UNIQUE}")
        api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]})
        resp = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]})
        assert resp.status_code == 400

    def test_list_pins(self):
        ensure_admin()
        col = create_collection(f"ListPinCol-{UNIQUE}")
        doc = create_document(col["id"], f"ListPinDoc-{UNIQUE}")
        pin = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]}).json()["data"]
        resp = api("/pins.list", {"collectionId": col["id"]})
        assert resp.status_code == 200
        pin_ids = [p["id"] for p in resp.json()["data"]]
        assert pin["id"] in pin_ids

    def test_delete_pin(self):
        ensure_admin()
        col = create_collection(f"DelPinCol-{UNIQUE}")
        doc = create_document(col["id"], f"DelPinDoc-{UNIQUE}")
        pin = api("/pins.create", {"documentId": doc["id"], "collectionId": col["id"]}).json()["data"]
        resp = api("/pins.delete", {"id": pin["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_pin_nonexistent_document(self):
        ensure_admin()
        col = create_collection(f"PinNECol-{UNIQUE}")
        resp = api("/pins.create", {"documentId": str(uuid.uuid4()), "collectionId": col["id"]})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Groups
# ════════════════════════════════════════════════════════════════════


class TestGroups:

    def test_create_group(self):
        ensure_admin()
        name = f"Group-{UNIQUE}"
        resp = api("/groups.create", {"name": name})
        assert resp.status_code == 200
        group = resp.json()["data"]
        assert group["name"] == name
        assert group["memberCount"] == 0
        assert "id" in group

    def test_duplicate_group_name(self):
        ensure_admin()
        name = f"DupGroup-{UNIQUE}"
        api("/groups.create", {"name": name})
        resp = api("/groups.create", {"name": name})
        assert resp.status_code == 400

    def test_list_groups(self):
        ensure_admin()
        name = f"ListGroup-{UNIQUE}"
        group = api("/groups.create", {"name": name}).json()["data"]
        resp = api("/groups.list")
        assert resp.status_code == 200
        group_ids = [g["id"] for g in resp.json()["data"]]
        assert group["id"] in group_ids

    def test_delete_group(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"DelGroup-{UNIQUE}"}).json()["data"]
        resp = api("/groups.delete", {"id": group["id"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify gone
        list_resp = api("/groups.list")
        group_ids = [g["id"] for g in list_resp.json()["data"]]
        assert group["id"] not in group_ids

    def test_member_cannot_create_group(self):
        ensure_member()
        resp = api("/groups.create", {"name": f"MemberGroup-{UNIQUE}"}, headers=MEMBER_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 14: Group Memberships
# ════════════════════════════════════════════════════════════════════


class TestGroupMemberships:

    def test_add_user_to_group(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"MemGroup-{UNIQUE}"}).json()["data"]
        # Get admin user id
        users = api("/users.list").json()["data"]
        admin_id = next(u["id"] for u in users if u["name"] == ADMIN_KEY)
        resp = api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        assert resp.status_code == 200
        membership = resp.json()["data"]
        assert membership["groupId"] == group["id"]
        assert membership["userId"] == admin_id

    def test_cannot_add_twice(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"DupMemGroup-{UNIQUE}"}).json()["data"]
        users = api("/users.list").json()["data"]
        admin_id = next(u["id"] for u in users if u["name"] == ADMIN_KEY)
        api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        resp = api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        assert resp.status_code == 400

    def test_list_group_members(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"ListMemGroup-{UNIQUE}"}).json()["data"]
        users = api("/users.list").json()["data"]
        admin_id = next(u["id"] for u in users if u["name"] == ADMIN_KEY)
        api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        resp = api("/group_memberships.list", {"groupId": group["id"]})
        assert resp.status_code == 200
        user_ids = [m["userId"] for m in resp.json()["data"]]
        assert admin_id in user_ids

    def test_remove_user_from_group(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"RemMemGroup-{UNIQUE}"}).json()["data"]
        users = api("/users.list").json()["data"]
        admin_id = next(u["id"] for u in users if u["name"] == ADMIN_KEY)
        api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        resp = api("/group_memberships.delete", {"groupId": group["id"], "userId": admin_id})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        # Verify removed
        list_resp = api("/group_memberships.list", {"groupId": group["id"]})
        user_ids = [m["userId"] for m in list_resp.json()["data"]]
        assert admin_id not in user_ids

    def test_group_member_count_updates(self):
        ensure_admin()
        group = api("/groups.create", {"name": f"CountGroup-{UNIQUE}"}).json()["data"]
        assert group["memberCount"] == 0
        users = api("/users.list").json()["data"]
        admin_id = next(u["id"] for u in users if u["name"] == ADMIN_KEY)
        api("/group_memberships.create", {"groupId": group["id"], "userId": admin_id})
        # Re-fetch group
        groups = api("/groups.list").json()["data"]
        updated_group = next(g for g in groups if g["id"] == group["id"])
        assert updated_group["memberCount"] == 1


# ════════════════════════════════════════════════════════════════════
# PART 15: Users Management
# ════════════════════════════════════════════════════════════════════


class TestUsers:

    def test_list_users_admin_only(self):
        ensure_member()
        resp = api("/users.list", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_list_users_as_admin(self):
        ensure_admin()
        resp = api("/users.list", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1

    def test_get_user_info(self):
        ensure_admin()
        users = api("/users.list").json()["data"]
        user_id = users[0]["id"]
        resp = api("/users.info", {"id": user_id})
        assert resp.status_code == 200
        user = resp.json()["data"]
        assert user["id"] == user_id
        assert "name" in user
        assert "role" in user
        assert "isSuspended" in user

    def test_update_user_role(self):
        member = create_member_user("role-target")
        resp = api("/users.update", {"id": member["id"], "role": "viewer"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "viewer"

    def test_suspend_user(self):
        member = create_member_user("suspension-target")
        resp = api("/users.update", {"id": member["id"], "isSuspended": True}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["isSuspended"] is True

    def test_update_user_non_admin_forbidden(self):
        ensure_member()
        target = create_member_user("managed-user")
        resp = api("/users.update", {"id": target["id"], "role": "viewer"}, headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_get_nonexistent_user(self):
        ensure_admin()
        resp = api("/users.info", {"id": str(uuid.uuid4())})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 16: Collection Permissions
# ════════════════════════════════════════════════════════════════════


class TestCollectionPermissions:

    def test_member_can_create_doc_in_read_write_collection(self):
        ensure_member()
        col = create_collection(f"RWCol-{UNIQUE}", permission="read_write")
        resp = api("/documents.create", {
            "title": f"MemberDoc-{UNIQUE}",
            "text": "Written by member",
            "collectionId": col["id"],
            "publish": True,
        }, headers=MEMBER_HEADERS)
        assert resp.status_code == 200

    def test_member_cannot_create_doc_in_read_collection(self):
        ensure_member()
        col = create_collection(f"ReadOnlyCol-{UNIQUE}", permission="read")
        resp = api("/documents.create", {
            "title": f"ForbiddenDoc-{UNIQUE}",
            "text": "Should fail",
            "collectionId": col["id"],
            "publish": True,
        }, headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_can_create_doc_in_read_collection(self):
        ensure_admin()
        col = create_collection(f"AdminReadCol-{UNIQUE}", permission="read")
        resp = api("/documents.create", {
            "title": f"AdminDoc-{UNIQUE}",
            "text": "Admin writes anywhere",
            "collectionId": col["id"],
            "publish": True,
        })
        assert resp.status_code == 200

    def test_viewer_cannot_create_document(self):
        ensure_viewer()
        col = create_collection(f"ViewerCol-{UNIQUE}", permission="read_write")
        resp = api("/documents.create", {
            "title": f"ViewerDoc-{UNIQUE}",
            "text": "Should fail",
            "collectionId": col["id"],
            "publish": True,
        }, headers=VIEWER_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 17: Delete Collection Cascade
# ════════════════════════════════════════════════════════════════════


class TestCollectionCascade:

    def test_delete_collection_deletes_documents(self):
        ensure_admin()
        col = create_collection(f"CascCol-{UNIQUE}")
        doc = create_document(col["id"], f"CascDoc-{UNIQUE}")
        api("/collections.delete", {"id": col["id"]})
        # Document should be gone
        resp = api("/documents.info", {"id": doc["id"]})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 18: Document Revision Counter
# ════════════════════════════════════════════════════════════════════


class TestDocumentRevisionCounter:

    def test_revision_increments_on_update(self):
        ensure_admin()
        col = create_collection(f"RevCntCol-{UNIQUE}")
        doc = create_document(col["id"], f"RevCntDoc-{UNIQUE}", text="V1")
        initial_rev = doc["revision"]
        api("/documents.update", {"id": doc["id"], "text": "V2"})
        updated = api("/documents.info", {"id": doc["id"]}).json()["data"]
        assert updated["revision"] == initial_rev + 1


# ════════════════════════════════════════════════════════════════════
# PART 19: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_create_document_missing_collection_id(self):
        ensure_admin()
        resp = api("/documents.create", {"title": "No collection"})
        assert resp.status_code == 400

    def test_create_document_nonexistent_collection(self):
        ensure_admin()
        resp = api("/documents.create", {
            "title": "Ghost",
            "collectionId": str(uuid.uuid4()),
        })
        assert resp.status_code == 404

    def test_move_to_nonexistent_collection(self):
        ensure_admin()
        col = create_collection(f"MoveNECol-{UNIQUE}")
        doc = create_document(col["id"], f"MoveNEDoc-{UNIQUE}")
        resp = api("/documents.move", {"id": doc["id"], "collectionId": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_archive_already_archived(self):
        """Archiving an already archived doc should still return 200."""
        ensure_admin()
        col = create_collection(f"ReArchCol-{UNIQUE}")
        doc = create_document(col["id"], f"ReArchDoc-{UNIQUE}")
        api("/documents.archive", {"id": doc["id"]})
        resp = api("/documents.archive", {"id": doc["id"]})
        assert resp.status_code == 200

    def test_delete_nonexistent_document(self):
        ensure_admin()
        resp = api("/documents.delete", {"id": str(uuid.uuid4())})
        assert resp.status_code == 404

    def test_uuid_format_ids(self):
        """IDs should be valid UUIDs."""
        ensure_admin()
        col = create_collection(f"UUIDCol-{UNIQUE}")
        # Verify collection id is a valid UUID
        try:
            uuid.UUID(col["id"])
        except ValueError:
            pytest.fail(f"Collection id is not a valid UUID: {col['id']}")

    def test_pagination_defaults(self):
        """Default pagination should be offset=0, limit=25."""
        ensure_admin()
        resp = api("/collections.list", {})
        data = resp.json()
        assert data["pagination"]["offset"] == 0
        assert data["pagination"]["limit"] == 25

    def test_pagination_limit_cap(self):
        """Limit should be capped at 100."""
        ensure_admin()
        resp = api("/collections.list", {"limit": 200})
        data = resp.json()
        assert data["pagination"]["limit"] <= 100
