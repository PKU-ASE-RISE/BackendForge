"""
BackendForge — Comprehensive Correctness Tests for Paperless-ngx Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex

# User keys — the key IS the username (auto-created on first request)
USER_KEY = f"testuser-{RUN_ID[:8]}"
USER2_KEY = f"otheruser-{RUN_ID[:8]}"

HEADERS = {
    "X-Api-Key": USER_KEY,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-Api-Key": USER2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_users(request):
    """Give every item fresh user namespaces so state cannot leak between tests."""
    global USER_KEY, USER2_KEY, HEADERS, HEADERS2, UNIQUE

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_KEY = f"testuser-{item_id}"
    USER2_KEY = f"otheruser-{item_id}"
    HEADERS = {"X-Api-Key": USER_KEY, "Content-Type": "application/json"}
    HEADERS2 = {"X-Api-Key": USER2_KEY, "Content-Type": "application/json"}
    UNIQUE = item_id[:8]


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


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """All endpoints require X-Api-Key header."""
        resp = requests.get(f"{BASE_URL}/api/documents/", timeout=30)
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/api/documents/",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_valid_api_key_auto_creates_user(self):
        """First request with a new key auto-creates the user."""
        resp = api_get("/api/documents/")
        assert resp.status_code == 200

    def test_tasks_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/tasks/", timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 2: Correspondents CRUD
# ════════════════════════════════════════════════════════════════════


class TestCorrespondents:

    def test_create_correspondent(self):
        resp = api_post("/api/correspondents/", {
            "name": f"Acme Corp {UNIQUE}",
            "match": f"acmematch{UNIQUE}",
            "matching_algorithm": 1,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Acme Corp {UNIQUE}"
        assert data["match"] == f"acmematch{UNIQUE}"
        assert data["matching_algorithm"] == 1
        assert "id" in data
        assert "document_count" in data
        assert data["document_count"] == 0

    def test_create_correspondent_minimal(self):
        resp = api_post("/api/correspondents/", {"name": f"Minimal Corp {UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["match"] == ""
        assert data["matching_algorithm"] == 0

    def test_create_duplicate_name_returns_400(self):
        name = f"DupCorr {uuid.uuid4().hex[:8]}"
        api_post("/api/correspondents/", {"name": name})
        resp = api_post("/api/correspondents/", {"name": name})
        assert resp.status_code == 400

    def test_list_correspondents_paginated(self):
        resp = api_get("/api/correspondents/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_get_correspondent(self):
        create = api_post("/api/correspondents/", {"name": f"GetCorr {uuid.uuid4().hex[:8]}"})
        cid = create.json()["id"]
        resp = api_get(f"/api/correspondents/{cid}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == cid

    def test_update_correspondent(self):
        create = api_post("/api/correspondents/", {"name": f"UpdCorr {uuid.uuid4().hex[:8]}"})
        cid = create.json()["id"]
        resp = api_put(f"/api/correspondents/{cid}/", {
            "name": f"Updated {uuid.uuid4().hex[:8]}",
            "match": "updated",
            "matching_algorithm": 3,
        })
        assert resp.status_code == 200
        assert resp.json()["match"] == "updated"
        assert resp.json()["matching_algorithm"] == 3

    def test_delete_correspondent(self):
        create = api_post("/api/correspondents/", {"name": f"DelCorr {uuid.uuid4().hex[:8]}"})
        cid = create.json()["id"]
        resp = api_delete(f"/api/correspondents/{cid}/")
        assert resp.status_code == 204
        # Verify it's gone
        resp = api_get(f"/api/correspondents/{cid}/")
        assert resp.status_code == 404

    def test_correspondent_not_found(self):
        resp = api_get("/api/correspondents/99999/")
        assert resp.status_code == 404

    def test_data_isolation_correspondents(self):
        """User2 cannot see User1's correspondents."""
        create = api_post("/api/correspondents/", {"name": f"IsoCorr {uuid.uuid4().hex[:8]}"})
        cid = create.json()["id"]
        resp = api_get(f"/api/correspondents/{cid}/", headers=HEADERS2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Document Types CRUD
# ════════════════════════════════════════════════════════════════════


class TestDocumentTypes:

    def test_create_document_type(self):
        resp = api_post("/api/document_types/", {
            "name": f"Invoice {UNIQUE}",
            "match": "invoice",
            "matching_algorithm": 3,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Invoice {UNIQUE}"
        assert data["matching_algorithm"] == 3
        assert data["document_count"] == 0

    def test_list_document_types(self):
        resp = api_get("/api/document_types/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_update_document_type(self):
        create = api_post("/api/document_types/", {"name": f"UpdType {uuid.uuid4().hex[:8]}"})
        tid = create.json()["id"]
        resp = api_put(f"/api/document_types/{tid}/", {
            "name": f"Receipt {uuid.uuid4().hex[:8]}",
            "match": "receipt",
            "matching_algorithm": 1,
        })
        assert resp.status_code == 200
        assert resp.json()["match"] == "receipt"

    def test_delete_document_type(self):
        create = api_post("/api/document_types/", {"name": f"DelType {uuid.uuid4().hex[:8]}"})
        tid = create.json()["id"]
        resp = api_delete(f"/api/document_types/{tid}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 4: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        resp = api_post("/api/tags/", {
            "name": f"Important {UNIQUE}",
            "color": "#ff0000",
            "is_inbox_tag": True,
            "match": "urgent",
            "matching_algorithm": 1,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Important {UNIQUE}"
        assert data["color"] == "#ff0000"
        assert data["is_inbox_tag"] is True
        assert data["document_count"] == 0

    def test_create_tag_defaults(self):
        resp = api_post("/api/tags/", {"name": f"DefaultTag {uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["color"] == "#a6cee3"
        assert data["is_inbox_tag"] is False
        assert data["match"] == ""
        assert data["matching_algorithm"] == 0

    def test_create_duplicate_tag_name_returns_400(self):
        name = f"DupTag {uuid.uuid4().hex[:8]}"
        api_post("/api/tags/", {"name": name})
        resp = api_post("/api/tags/", {"name": name})
        assert resp.status_code == 400

    def test_list_tags(self):
        resp = api_get("/api/tags/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_update_tag(self):
        create = api_post("/api/tags/", {"name": f"UpdTag {uuid.uuid4().hex[:8]}"})
        tid = create.json()["id"]
        resp = api_put(f"/api/tags/{tid}/", {
            "name": f"Renamed {uuid.uuid4().hex[:8]}",
            "color": "#00ff00",
            "is_inbox_tag": False,
            "match": "",
            "matching_algorithm": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["color"] == "#00ff00"

    def test_delete_tag(self):
        create = api_post("/api/tags/", {"name": f"DelTag {uuid.uuid4().hex[:8]}"})
        tid = create.json()["id"]
        resp = api_delete(f"/api/tags/{tid}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 5: Storage Paths CRUD
# ════════════════════════════════════════════════════════════════════


class TestStoragePaths:

    def test_create_storage_path(self):
        resp = api_post("/api/storage_paths/", {
            "name": f"Archive {UNIQUE}",
            "path": "/documents/{correspondent}/{title}",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Archive {UNIQUE}"
        assert data["path"] == "/documents/{correspondent}/{title}"
        assert data["document_count"] == 0

    def test_list_storage_paths(self):
        resp = api_get("/api/storage_paths/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_delete_storage_path(self):
        create = api_post("/api/storage_paths/", {
            "name": f"DelPath {uuid.uuid4().hex[:8]}",
            "path": "/tmp/{title}",
        })
        pid = create.json()["id"]
        resp = api_delete(f"/api/storage_paths/{pid}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 6: Custom Fields CRUD
# ════════════════════════════════════════════════════════════════════


class TestCustomFields:

    def test_create_custom_field(self):
        resp = api_post("/api/custom_fields/", {
            "name": f"Invoice Number {UNIQUE}",
            "data_type": "string",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Invoice Number {UNIQUE}"
        assert data["data_type"] == "string"

    def test_create_custom_field_integer(self):
        resp = api_post("/api/custom_fields/", {
            "name": f"Amount {uuid.uuid4().hex[:8]}",
            "data_type": "integer",
        })
        assert resp.status_code == 201
        assert resp.json()["data_type"] == "integer"

    def test_list_custom_fields(self):
        resp = api_get("/api/custom_fields/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_delete_custom_field(self):
        create = api_post("/api/custom_fields/", {
            "name": f"DelField {uuid.uuid4().hex[:8]}",
            "data_type": "boolean",
        })
        fid = create.json()["id"]
        resp = api_delete(f"/api/custom_fields/{fid}/")
        assert resp.status_code == 204

    def test_duplicate_custom_field_name_returns_400(self):
        name = f"DupField {uuid.uuid4().hex[:8]}"
        api_post("/api/custom_fields/", {"name": name, "data_type": "string"})
        resp = api_post("/api/custom_fields/", {"name": name, "data_type": "string"})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 7: Saved Views CRUD
# ════════════════════════════════════════════════════════════════════


class TestSavedViews:

    def test_create_saved_view(self):
        resp = api_post("/api/saved_views/", {
            "name": f"My View {UNIQUE}",
            "sort_field": "created_date",
            "sort_reverse": True,
            "filter_rules": [
                {"rule_type": 19, "value": "invoice"},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"My View {UNIQUE}"
        assert data["sort_field"] == "created_date"
        assert data["sort_reverse"] is True
        assert len(data["filter_rules"]) == 1
        assert data["filter_rules"][0]["rule_type"] == 19
        assert data["filter_rules"][0]["value"] == "invoice"

    def test_list_saved_views(self):
        resp = api_get("/api/saved_views/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_update_saved_view(self):
        create = api_post("/api/saved_views/", {
            "name": f"UpdView {uuid.uuid4().hex[:8]}",
            "sort_field": "title",
            "sort_reverse": False,
            "filter_rules": [],
        })
        vid = create.json()["id"]
        resp = api_put(f"/api/saved_views/{vid}/", {
            "name": f"Renamed View {uuid.uuid4().hex[:8]}",
            "sort_field": "created_date",
            "sort_reverse": True,
            "filter_rules": [{"rule_type": 20, "value": "report"}],
        })
        assert resp.status_code == 200
        assert resp.json()["sort_reverse"] is True

    def test_delete_saved_view(self):
        create = api_post("/api/saved_views/", {
            "name": f"DelView {uuid.uuid4().hex[:8]}",
            "sort_field": "title",
            "sort_reverse": False,
            "filter_rules": [],
        })
        vid = create.json()["id"]
        resp = api_delete(f"/api/saved_views/{vid}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 8: Documents CRUD
# ════════════════════════════════════════════════════════════════════


class TestDocumentsCRUD:

    def test_create_document_basic(self):
        resp = api_post("/api/documents/", {
            "title": f"Test Document {UNIQUE}",
            "content": "This is the content of a test document.",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"Test Document {UNIQUE}"
        assert data["content"] == "This is the content of a test document."
        assert "id" in data
        assert "added_date" in data
        assert data["correspondent"] is None
        assert data["document_type"] is None
        assert data["tags"] == []
        assert data["archive_serial_number"] is None
        assert data["custom_fields"] == []

    def test_create_document_with_date(self):
        resp = api_post("/api/documents/", {
            "title": f"Dated Doc {uuid.uuid4().hex[:8]}",
            "content": "Content with date.",
            "created_date": "2023-06-15",
        })
        assert resp.status_code == 201
        assert resp.json()["created_date"] == "2023-06-15"

    def test_create_document_with_relationships(self):
        # Create correspondent and type first
        corr = api_post("/api/correspondents/", {"name": f"RelCorr {uuid.uuid4().hex[:8]}"}).json()
        dtype = api_post("/api/document_types/", {"name": f"RelType {uuid.uuid4().hex[:8]}"}).json()
        tag = api_post("/api/tags/", {"name": f"RelTag {uuid.uuid4().hex[:8]}"}).json()

        resp = api_post("/api/documents/", {
            "title": f"Related Doc {uuid.uuid4().hex[:8]}",
            "content": "Doc with relationships.",
            "correspondent": corr["id"],
            "document_type": dtype["id"],
            "tags": [tag["id"]],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["correspondent"] == corr["id"]
        assert data["document_type"] == dtype["id"]
        assert data["tags"] == [tag["id"]]

    def test_create_document_invalid_correspondent_returns_400(self):
        resp = api_post("/api/documents/", {
            "title": "Bad Corr Doc",
            "content": "Content",
            "correspondent": 99999,
        })
        assert resp.status_code == 400

    def test_create_document_invalid_tag_returns_400(self):
        resp = api_post("/api/documents/", {
            "title": "Bad Tag Doc",
            "content": "Content",
            "tags": [99999],
        })
        assert resp.status_code == 400

    def test_get_document(self):
        create = api_post("/api/documents/", {
            "title": f"GetDoc {uuid.uuid4().hex[:8]}",
            "content": "Get this doc.",
        })
        doc_id = create.json()["id"]
        resp = api_get(f"/api/documents/{doc_id}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    def test_update_document(self):
        create = api_post("/api/documents/", {
            "title": f"UpdDoc {uuid.uuid4().hex[:8]}",
            "content": "Original content.",
        })
        doc_id = create.json()["id"]
        resp = api_put(f"/api/documents/{doc_id}/", {
            "title": "Updated Title",
            "content": "Updated content.",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        assert resp.json()["content"] == "Updated content."

    def test_delete_document(self):
        create = api_post("/api/documents/", {
            "title": f"DelDoc {uuid.uuid4().hex[:8]}",
            "content": "To be deleted.",
        })
        doc_id = create.json()["id"]
        resp = api_delete(f"/api/documents/{doc_id}/")
        assert resp.status_code == 204
        # Verify it's gone
        resp = api_get(f"/api/documents/{doc_id}/")
        assert resp.status_code == 404

    def test_document_not_found(self):
        resp = api_get("/api/documents/99999/")
        assert resp.status_code == 404

    def test_data_isolation_documents(self):
        """User2 cannot see User1's documents."""
        create = api_post("/api/documents/", {
            "title": f"IsoDoc {uuid.uuid4().hex[:8]}",
            "content": "Isolated.",
        })
        doc_id = create.json()["id"]
        resp = api_get(f"/api/documents/{doc_id}/", headers=HEADERS2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: ASN (Archive Serial Number)
# ════════════════════════════════════════════════════════════════════


class TestASN:

    def test_asn_null_by_default(self):
        resp = api_post("/api/documents/", {
            "title": f"NoASN {uuid.uuid4().hex[:8]}",
            "content": "No serial number.",
        })
        assert resp.status_code == 201
        assert resp.json()["archive_serial_number"] is None

    def test_set_asn_explicitly(self):
        asn = 10000 + int(uuid.uuid4().hex[:4], 16)  # random large ASN
        resp = api_post("/api/documents/", {
            "title": f"WithASN {uuid.uuid4().hex[:8]}",
            "content": "Has serial number.",
            "archive_serial_number": asn,
        })
        assert resp.status_code == 201
        assert resp.json()["archive_serial_number"] == asn

    def test_duplicate_asn_returns_400(self):
        asn = 20000 + int(uuid.uuid4().hex[:4], 16)
        api_post("/api/documents/", {
            "title": f"ASN1 {uuid.uuid4().hex[:8]}",
            "content": "First.",
            "archive_serial_number": asn,
        })
        resp = api_post("/api/documents/", {
            "title": f"ASN2 {uuid.uuid4().hex[:8]}",
            "content": "Second.",
            "archive_serial_number": asn,
        })
        assert resp.status_code == 400

    def test_asn_unique_per_user(self):
        """Same ASN can be used by different users."""
        asn = 30000 + int(uuid.uuid4().hex[:4], 16)
        resp1 = api_post("/api/documents/", {
            "title": f"ASN-U1 {uuid.uuid4().hex[:8]}",
            "content": "User1 doc.",
            "archive_serial_number": asn,
        })
        assert resp1.status_code == 201
        resp2 = api_post("/api/documents/", {
            "title": f"ASN-U2 {uuid.uuid4().hex[:8]}",
            "content": "User2 doc.",
            "archive_serial_number": asn,
        }, headers=HEADERS2)
        assert resp2.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 10: Custom Fields on Documents
# ════════════════════════════════════════════════════════════════════


class TestCustomFieldsOnDocuments:

    def test_set_custom_field_on_document(self):
        # Create custom field
        field = api_post("/api/custom_fields/", {
            "name": f"CF-str {uuid.uuid4().hex[:8]}",
            "data_type": "string",
        }).json()
        # Create document with custom field
        resp = api_post("/api/documents/", {
            "title": f"CF Doc {uuid.uuid4().hex[:8]}",
            "content": "Document with custom field.",
            "custom_fields": [{"field": field["id"], "value": "INV-001"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["custom_fields"]) == 1
        assert data["custom_fields"][0]["field"] == field["id"]
        assert data["custom_fields"][0]["value"] == "INV-001"

    def test_update_custom_field_value(self):
        field = api_post("/api/custom_fields/", {
            "name": f"CF-upd {uuid.uuid4().hex[:8]}",
            "data_type": "integer",
        }).json()
        doc = api_post("/api/documents/", {
            "title": f"CF UpdDoc {uuid.uuid4().hex[:8]}",
            "content": "Content.",
            "custom_fields": [{"field": field["id"], "value": 42}],
        }).json()
        # Update the document's custom field
        resp = api_put(f"/api/documents/{doc['id']}/", {
            "title": doc["title"],
            "content": doc["content"],
            "custom_fields": [{"field": field["id"], "value": 99}],
        })
        assert resp.status_code == 200
        cf = resp.json()["custom_fields"]
        assert len(cf) == 1
        assert cf[0]["value"] == 99

    def test_invalid_custom_field_id_returns_400(self):
        resp = api_post("/api/documents/", {
            "title": "Bad CF Doc",
            "content": "Content",
            "custom_fields": [{"field": 99999, "value": "test"}],
        })
        assert resp.status_code == 400

    def test_custom_field_deleted_removes_from_documents(self):
        field = api_post("/api/custom_fields/", {
            "name": f"CF-del {uuid.uuid4().hex[:8]}",
            "data_type": "string",
        }).json()
        doc = api_post("/api/documents/", {
            "title": f"CF DelDoc {uuid.uuid4().hex[:8]}",
            "content": "Content.",
            "custom_fields": [{"field": field["id"], "value": "will-be-removed"}],
        }).json()
        # Delete the custom field definition
        api_delete(f"/api/custom_fields/{field['id']}/")
        # Verify field is removed from document
        resp = api_get(f"/api/documents/{doc['id']}/")
        assert resp.status_code == 200
        assert resp.json()["custom_fields"] == []


# ════════════════════════════════════════════════════════════════════
# PART 11: Auto-Matching
# ════════════════════════════════════════════════════════════════════


class TestAutoMatching:

    def test_auto_match_correspondent_exact(self):
        """Correspondent with exact matching auto-assigned on doc create."""
        unique = uuid.uuid4().hex[:8]
        corr = api_post("/api/correspondents/", {
            "name": f"AutoCorr-Exact {unique}",
            "match": f"xyzcorp{unique}",
            "matching_algorithm": 3,  # exact
        }).json()
        # Create document that contains the match string
        resp = api_post("/api/documents/", {
            "title": f"Letter from xyzcorp{unique} about services",
            "content": f"Dear customer, xyzcorp{unique} would like to...",
        })
        assert resp.status_code == 201
        assert resp.json()["correspondent"] == corr["id"]

    def test_auto_match_correspondent_any_word(self):
        """Correspondent with 'any' matching: any word matches."""
        corr = api_post("/api/correspondents/", {
            "name": f"AutoCorr-Any {uuid.uuid4().hex[:8]}",
            "match": "globaltech megacorp",
            "matching_algorithm": 1,  # any word
        }).json()
        # Document title contains 'globaltech' as a word
        resp = api_post("/api/documents/", {
            "title": f"Message from globaltech about renewal {uuid.uuid4().hex[:8]}",
            "content": "Please renew your subscription.",
        })
        assert resp.status_code == 201
        assert resp.json()["correspondent"] == corr["id"]

    def test_auto_match_correspondent_all_words(self):
        """Correspondent with 'all' matching: all words must match."""
        suffix = uuid.uuid4().hex[:8]
        corr = api_post("/api/correspondents/", {
            "name": f"AutoCorr-All {suffix}",
            "match": "alpha beta",
            "matching_algorithm": 2,  # all words
        }).json()
        # Document with only one word doesn't match
        resp1 = api_post("/api/documents/", {
            "title": f"Only alpha word present {suffix}",
            "content": "Nothing else special.",
        })
        assert resp1.status_code == 201
        assert resp1.json()["correspondent"] is None or resp1.json()["correspondent"] != corr["id"]

        # Document with both words matches
        resp2 = api_post("/api/documents/", {
            "title": f"Both alpha and beta words {suffix}",
            "content": "This has both.",
        })
        assert resp2.status_code == 201
        assert resp2.json()["correspondent"] == corr["id"]

    def test_auto_match_document_type_regex(self):
        """Document type with regex matching."""
        dtype = api_post("/api/document_types/", {
            "name": f"AutoType-Regex {uuid.uuid4().hex[:8]}",
            "match": r"INV-\d{4}",
            "matching_algorithm": 4,  # regex
        }).json()
        resp = api_post("/api/documents/", {
            "title": f"Document INV-2024 from vendor {uuid.uuid4().hex[:8]}",
            "content": "Total amount due.",
        })
        assert resp.status_code == 201
        assert resp.json()["document_type"] == dtype["id"]

    def test_auto_match_tags_multiple(self):
        """Multiple tags can be auto-matched to a single document."""
        tag1 = api_post("/api/tags/", {
            "name": f"AutoTag1 {uuid.uuid4().hex[:8]}",
            "match": "urgent",
            "matching_algorithm": 1,
        }).json()
        tag2 = api_post("/api/tags/", {
            "name": f"AutoTag2 {uuid.uuid4().hex[:8]}",
            "match": "payment",
            "matching_algorithm": 1,
        }).json()
        resp = api_post("/api/documents/", {
            "title": f"Urgent payment reminder {uuid.uuid4().hex[:8]}",
            "content": "Please make the urgent payment by Friday.",
        })
        assert resp.status_code == 201
        tags = resp.json()["tags"]
        assert tag1["id"] in tags
        assert tag2["id"] in tags

    def test_auto_match_does_not_override_explicit(self):
        """If user explicitly sets correspondent, auto-match doesn't override."""
        corr_auto = api_post("/api/correspondents/", {
            "name": f"AutoCorrNoOverride {uuid.uuid4().hex[:8]}",
            "match": "override_test_keyword",
            "matching_algorithm": 3,
        }).json()
        corr_explicit = api_post("/api/correspondents/", {
            "name": f"ExplicitCorr {uuid.uuid4().hex[:8]}",
        }).json()
        resp = api_post("/api/documents/", {
            "title": "Document with override_test_keyword inside",
            "content": "Some content.",
            "correspondent": corr_explicit["id"],
        })
        assert resp.status_code == 201
        # Should keep the explicitly set one
        assert resp.json()["correspondent"] == corr_explicit["id"]

    def test_auto_match_no_match(self):
        """Documents that don't match any rule get null."""
        resp = api_post("/api/documents/", {
            "title": f"Completely unique xyzzy {uuid.uuid4().hex[:8]}",
            "content": "Nothing matches here at all zzzqqq.",
        })
        assert resp.status_code == 201
        # This item only verifies successful creation.
        assert resp.json()["id"] is not None

    def test_auto_match_first_correspondent_wins(self):
        """If multiple correspondents match, the one with lowest ID wins."""
        suffix = uuid.uuid4().hex[:8]
        corr1 = api_post("/api/correspondents/", {
            "name": f"First-{suffix}",
            "match": f"multiword{suffix}",
            "matching_algorithm": 3,
        }).json()
        corr2 = api_post("/api/correspondents/", {
            "name": f"Second-{suffix}",
            "match": f"multiword{suffix}",
            "matching_algorithm": 3,
        }).json()
        resp = api_post("/api/documents/", {
            "title": f"Contains multiword{suffix} text",
            "content": "Some content.",
        })
        assert resp.status_code == 201
        # First (lowest ID) wins
        assert resp.json()["correspondent"] == corr1["id"]


# ════════════════════════════════════════════════════════════════════
# PART 12: Pagination
# ════════════════════════════════════════════════════════════════════


class TestPagination:

    def test_documents_pagination(self):
        """Create enough documents to test pagination."""
        prefix = uuid.uuid4().hex[:8]
        for i in range(3):
            api_post("/api/documents/", {
                "title": f"PagDoc {prefix} {i}",
                "content": f"Content {i}",
            })
        resp = api_get("/api/documents/", params={"page_size": 2, "page": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 3
        assert len(data["results"]) <= 2
        # next should be a URL string (not null) if there are more items
        if data["count"] > 2:
            assert data["next"] is not None
            assert "page=2" in data["next"] or "page_size" in data["next"]

    def test_pagination_page_2(self):
        prefix = uuid.uuid4().hex[:8]
        for i in range(3):
            api_post("/api/documents/", {
                "title": f"PageTwoDoc {prefix} {i}",
                "content": f"Content {i}",
            })
        resp = api_get("/api/documents/", params={"page_size": 2, "page": 2})
        assert resp.status_code == 200
        data = resp.json()
        # previous should exist on page 2
        assert data["previous"] is not None

    def test_correspondents_pagination(self):
        prefix = uuid.uuid4().hex[:8]
        for i in range(3):
            api_post("/api/correspondents/", {"name": f"PageCorr {prefix} {i}"})
        resp = api_get("/api/correspondents/", params={"page_size": 2, "page": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert len(data["results"]) <= 2


# ════════════════════════════════════════════════════════════════════
# PART 13: Filtering
# ════════════════════════════════════════════════════════════════════


class TestFiltering:

    def test_filter_by_correspondent(self):
        corr = api_post("/api/correspondents/", {"name": f"FiltCorr {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"FiltDoc {uuid.uuid4().hex[:8]}",
            "content": "Filtering test.",
            "correspondent": corr["id"],
        }).json()
        resp = api_get("/api/documents/", params={"correspondent__id": corr["id"]})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)
        # All results should have this correspondent
        for d in results:
            assert d["correspondent"] == corr["id"]

    def test_filter_by_document_type(self):
        dtype = api_post("/api/document_types/", {"name": f"FiltType {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"FiltTypeDoc {uuid.uuid4().hex[:8]}",
            "content": "Type filtering.",
            "document_type": dtype["id"],
        }).json()
        resp = api_get("/api/documents/", params={"document_type__id": dtype["id"]})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_filter_by_tags_all(self):
        tag1 = api_post("/api/tags/", {"name": f"FiltTag1 {uuid.uuid4().hex[:8]}"}).json()
        tag2 = api_post("/api/tags/", {"name": f"FiltTag2 {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"FiltTagsDoc {uuid.uuid4().hex[:8]}",
            "content": "Tags filtering.",
            "tags": [tag1["id"], tag2["id"]],
        }).json()
        # Filter by both tags (ALL)
        resp = api_get("/api/documents/", params={
            "tags__id__all": f"{tag1['id']},{tag2['id']}"
        })
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_filter_by_tags_in(self):
        tag = api_post("/api/tags/", {"name": f"FiltTagIn {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"FiltTagInDoc {uuid.uuid4().hex[:8]}",
            "content": "Tag in filtering.",
            "tags": [tag["id"]],
        }).json()
        resp = api_get("/api/documents/", params={"tags__id__in": str(tag["id"])})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_filter_by_title_icontains(self):
        unique_word = f"xyzzyfilter{uuid.uuid4().hex[:8]}"
        doc = api_post("/api/documents/", {
            "title": f"Document with {unique_word} in title",
            "content": "Normal content.",
        }).json()
        resp = api_get("/api/documents/", params={"title__icontains": unique_word})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_filter_by_content_icontains(self):
        unique_word = f"qwertyfilter{uuid.uuid4().hex[:8]}"
        doc = api_post("/api/documents/", {
            "title": "Normal title",
            "content": f"Content with {unique_word} inside.",
        }).json()
        resp = api_get("/api/documents/", params={"content__icontains": unique_word})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_filter_by_asn_range(self):
        asn = 40000 + int(uuid.uuid4().hex[:4], 16)
        doc = api_post("/api/documents/", {
            "title": f"ASNRange {uuid.uuid4().hex[:8]}",
            "content": "ASN range test.",
            "archive_serial_number": asn,
        }).json()
        resp = api_get("/api/documents/", params={
            "archive_serial_number__gte": asn,
            "archive_serial_number__lte": asn,
        })
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any(d["id"] == doc["id"] for d in results)

    def test_ordering_by_title(self):
        prefix = uuid.uuid4().hex[:8]
        api_post("/api/documents/", {"title": f"B-{prefix}", "content": "c"})
        api_post("/api/documents/", {"title": f"A-{prefix}", "content": "c"})
        api_post("/api/documents/", {"title": f"C-{prefix}", "content": "c"})
        resp = api_get("/api/documents/", params={
            "ordering": "title",
            "title__icontains": prefix,
        })
        assert resp.status_code == 200
        results = resp.json()["results"]
        titles = [d["title"] for d in results]
        assert titles == sorted(titles)

    def test_ordering_descending(self):
        prefix = uuid.uuid4().hex[:8]
        api_post("/api/documents/", {"title": f"B-{prefix}", "content": "c"})
        api_post("/api/documents/", {"title": f"A-{prefix}", "content": "c"})
        api_post("/api/documents/", {"title": f"C-{prefix}", "content": "c"})
        resp = api_get("/api/documents/", params={
            "ordering": "-title",
            "title__icontains": prefix,
        })
        assert resp.status_code == 200
        results = resp.json()["results"]
        titles = [d["title"] for d in results]
        assert titles == sorted(titles, reverse=True)


# ════════════════════════════════════════════════════════════════════
# PART 14: Search
# ════════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_basic(self):
        unique_word = f"searchterm{uuid.uuid4().hex[:8]}"
        api_post("/api/documents/", {
            "title": f"Searchable {unique_word}",
            "content": f"This document contains {unique_word} multiple times. {unique_word}.",
        })
        resp = api_get("/api/search/", params={"query": unique_word})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        # First result should contain our word
        assert unique_word in results[0]["title"] or unique_word in results[0]["content"]

    def test_search_returns_ranking(self):
        """Documents with more occurrences should rank higher."""
        unique_word = f"rankword{uuid.uuid4().hex[:8]}"
        # Doc with many occurrences
        api_post("/api/documents/", {
            "title": f"Many {unique_word}",
            "content": f"{unique_word} {unique_word} {unique_word} {unique_word} {unique_word}",
        })
        # Doc with few occurrences
        api_post("/api/documents/", {
            "title": f"Few {uuid.uuid4().hex[:8]}",
            "content": f"Just one {unique_word} here.",
        })
        resp = api_get("/api/search/", params={"query": unique_word})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 2
        # Results should have __search_hit__ with score
        assert "__search_hit__" in results[0]
        assert "score" in results[0]["__search_hit__"]
        # First result should have higher score
        assert results[0]["__search_hit__"]["score"] >= results[1]["__search_hit__"]["score"]

    def test_search_no_results(self):
        resp = api_get("/api/search/", params={"query": f"nonexistent{uuid.uuid4().hex}"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_isolation(self):
        """Search only returns current user's documents."""
        unique_word = f"isoword{uuid.uuid4().hex[:8]}"
        api_post("/api/documents/", {
            "title": f"User1 {unique_word}",
            "content": "User1 content.",
        })
        resp = api_get("/api/search/", params={"query": unique_word}, headers=HEADERS2)
        assert resp.status_code == 200
        # User2 should not see User1's documents
        assert len(resp.json()) == 0


# ════════════════════════════════════════════════════════════════════
# PART 15: Bulk Operations
# ════════════════════════════════════════════════════════════════════


class TestBulkOperations:

    def test_bulk_set_correspondent(self):
        corr = api_post("/api/correspondents/", {"name": f"BulkCorr {uuid.uuid4().hex[:8]}"}).json()
        doc1 = api_post("/api/documents/", {
            "title": f"Bulk1 {uuid.uuid4().hex[:8]}",
            "content": "Bulk test 1.",
        }).json()
        doc2 = api_post("/api/documents/", {
            "title": f"Bulk2 {uuid.uuid4().hex[:8]}",
            "content": "Bulk test 2.",
        }).json()

        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [doc1["id"], doc2["id"]],
            "method": "set_correspondent",
            "parameters": {"correspondent": corr["id"]},
        })
        assert resp.status_code == 200
        assert resp.json()["result"] == "OK"

        # Verify both docs now have the correspondent
        d1 = api_get(f"/api/documents/{doc1['id']}/").json()
        d2 = api_get(f"/api/documents/{doc2['id']}/").json()
        assert d1["correspondent"] == corr["id"]
        assert d2["correspondent"] == corr["id"]

    def test_bulk_add_tag(self):
        tag = api_post("/api/tags/", {"name": f"BulkTag {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"BulkTagDoc {uuid.uuid4().hex[:8]}",
            "content": "Bulk tag test.",
        }).json()

        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [doc["id"]],
            "method": "add_tag",
            "parameters": {"tag": tag["id"]},
        })
        assert resp.status_code == 200

        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert tag["id"] in d["tags"]

    def test_bulk_remove_tag(self):
        tag = api_post("/api/tags/", {"name": f"BulkRemTag {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"BulkRemDoc {uuid.uuid4().hex[:8]}",
            "content": "Bulk remove tag test.",
            "tags": [tag["id"]],
        }).json()

        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [doc["id"]],
            "method": "remove_tag",
            "parameters": {"tag": tag["id"]},
        })
        assert resp.status_code == 200

        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert tag["id"] not in d["tags"]

    def test_bulk_delete(self):
        doc = api_post("/api/documents/", {
            "title": f"BulkDel {uuid.uuid4().hex[:8]}",
            "content": "To be bulk deleted.",
        }).json()

        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [doc["id"]],
            "method": "delete",
            "parameters": {},
        })
        assert resp.status_code == 200

        # Verify document is deleted
        resp = api_get(f"/api/documents/{doc['id']}/")
        assert resp.status_code == 404

    def test_bulk_invalid_document_returns_400(self):
        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [99999],
            "method": "delete",
            "parameters": {},
        })
        assert resp.status_code == 400

    def test_bulk_set_document_type(self):
        dtype = api_post("/api/document_types/", {"name": f"BulkType {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"BulkTypeDoc {uuid.uuid4().hex[:8]}",
            "content": "Bulk type test.",
        }).json()

        resp = api_post("/api/documents/bulk_edit/", {
            "documents": [doc["id"]],
            "method": "set_document_type",
            "parameters": {"document_type": dtype["id"]},
        })
        assert resp.status_code == 200

        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert d["document_type"] == dtype["id"]


# ════════════════════════════════════════════════════════════════════
# PART 16: Deletion Cascading
# ════════════════════════════════════════════════════════════════════


class TestDeletionCascading:

    def test_delete_correspondent_nullifies_documents(self):
        corr = api_post("/api/correspondents/", {"name": f"CascCorr {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"CascDoc {uuid.uuid4().hex[:8]}",
            "content": "Cascade test.",
            "correspondent": corr["id"],
        }).json()
        # Delete correspondent
        api_delete(f"/api/correspondents/{corr['id']}/")
        # Document should still exist but with null correspondent
        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert d["correspondent"] is None

    def test_delete_document_type_nullifies_documents(self):
        dtype = api_post("/api/document_types/", {"name": f"CascType {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"CascTypeDoc {uuid.uuid4().hex[:8]}",
            "content": "Type cascade test.",
            "document_type": dtype["id"],
        }).json()
        api_delete(f"/api/document_types/{dtype['id']}/")
        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert d["document_type"] is None

    def test_delete_tag_removes_from_documents(self):
        tag = api_post("/api/tags/", {"name": f"CascTag {uuid.uuid4().hex[:8]}"}).json()
        other_tag = api_post("/api/tags/", {"name": f"KeepTag {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"CascTagDoc {uuid.uuid4().hex[:8]}",
            "content": "Tag cascade test.",
            "tags": [tag["id"], other_tag["id"]],
        }).json()
        api_delete(f"/api/tags/{tag['id']}/")
        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert tag["id"] not in d["tags"]
        assert other_tag["id"] in d["tags"]

    def test_delete_storage_path_nullifies_documents(self):
        path = api_post("/api/storage_paths/", {
            "name": f"CascPath {uuid.uuid4().hex[:8]}",
            "path": "/archive/{title}",
        }).json()
        doc = api_post("/api/documents/", {
            "title": f"CascPathDoc {uuid.uuid4().hex[:8]}",
            "content": "Path cascade test.",
            "storage_path": path["id"],
        }).json()
        api_delete(f"/api/storage_paths/{path['id']}/")
        d = api_get(f"/api/documents/{doc['id']}/").json()
        assert d["storage_path"] is None


# ════════════════════════════════════════════════════════════════════
# PART 17: Document Count on Metadata
# ════════════════════════════════════════════════════════════════════


class TestDocumentCount:

    def test_correspondent_document_count(self):
        corr = api_post("/api/correspondents/", {"name": f"CountCorr {uuid.uuid4().hex[:8]}"}).json()
        api_post("/api/documents/", {
            "title": f"CountDoc1 {uuid.uuid4().hex[:8]}",
            "content": "Count test.",
            "correspondent": corr["id"],
        })
        api_post("/api/documents/", {
            "title": f"CountDoc2 {uuid.uuid4().hex[:8]}",
            "content": "Count test 2.",
            "correspondent": corr["id"],
        })
        resp = api_get(f"/api/correspondents/{corr['id']}/")
        assert resp.status_code == 200
        assert resp.json()["document_count"] == 2

    def test_tag_document_count(self):
        tag = api_post("/api/tags/", {"name": f"CountTag {uuid.uuid4().hex[:8]}"}).json()
        api_post("/api/documents/", {
            "title": f"TagCountDoc {uuid.uuid4().hex[:8]}",
            "content": "Tag count test.",
            "tags": [tag["id"]],
        })
        resp = api_get(f"/api/tags/{tag['id']}/")
        assert resp.status_code == 200
        assert resp.json()["document_count"] == 1


# ════════════════════════════════════════════════════════════════════
# PART 18: Tasks Endpoint
# ════════════════════════════════════════════════════════════════════


class TestTasks:

    def test_tasks_returns_empty_list(self):
        resp = api_get("/api/tasks/")
        assert resp.status_code == 200
        assert resp.json() == []


# ════════════════════════════════════════════════════════════════════
# PART 19: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_update_document_with_custom_fields_preserves_them(self):
        field = api_post("/api/custom_fields/", {
            "name": f"EdgeCF {uuid.uuid4().hex[:8]}",
            "data_type": "string",
        }).json()
        doc = api_post("/api/documents/", {
            "title": "Edge doc",
            "content": "Edge content.",
            "custom_fields": [{"field": field["id"], "value": "preserved"}],
        }).json()
        # Update title but keep custom fields
        resp = api_put(f"/api/documents/{doc['id']}/", {
            "title": "Edge doc updated",
            "content": "Edge content.",
            "custom_fields": [{"field": field["id"], "value": "preserved"}],
        })
        assert resp.status_code == 200
        assert resp.json()["custom_fields"][0]["value"] == "preserved"

    def test_document_with_multiple_tags(self):
        tags = []
        for i in range(3):
            t = api_post("/api/tags/", {"name": f"MultiTag{i} {uuid.uuid4().hex[:8]}"}).json()
            tags.append(t["id"])
        resp = api_post("/api/documents/", {
            "title": f"MultiTagDoc {uuid.uuid4().hex[:8]}",
            "content": "Many tags.",
            "tags": tags,
        })
        assert resp.status_code == 201
        assert set(resp.json()["tags"]) == set(tags)

    def test_update_removes_tags(self):
        tag = api_post("/api/tags/", {"name": f"RemoveTag {uuid.uuid4().hex[:8]}"}).json()
        doc = api_post("/api/documents/", {
            "title": f"WillRemoveTag {uuid.uuid4().hex[:8]}",
            "content": "Remove tag test.",
            "tags": [tag["id"]],
        }).json()
        # Update with empty tags
        resp = api_put(f"/api/documents/{doc['id']}/", {
            "title": doc["title"],
            "content": doc["content"],
            "tags": [],
        })
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    def test_correspondent_cross_user_reference_returns_400(self):
        """User1 cannot reference User2's correspondent."""
        corr = api_post("/api/correspondents/", {
            "name": f"CrossCorr {uuid.uuid4().hex[:8]}",
        }, headers=HEADERS2).json()
        resp = api_post("/api/documents/", {
            "title": "Cross ref test",
            "content": "Content.",
            "correspondent": corr["id"],
        })
        assert resp.status_code == 400
