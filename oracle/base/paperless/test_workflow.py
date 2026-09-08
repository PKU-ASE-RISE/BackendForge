"""
BackendForge — L3 Workflow Tests for Paperless-ngx
Multi-entity, multi-step adversarial tests targeting LLM implementation gaps.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
USER_A = f"l3usera-{RUN_ID[:8]}"
USER_B = f"l3userb-{RUN_ID[:8]}"
HEADERS_A = {"X-Api-Key": USER_A, "Content-Type": "application/json"}
HEADERS_B = {"X-Api-Key": USER_B, "Content-Type": "application/json"}
U = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_users(request):
    """Give every item fresh user namespaces so state cannot leak between tests."""
    global USER_A, USER_B, HEADERS_A, HEADERS_B, U

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_A = f"l3usera-{item_id}"
    USER_B = f"l3userb-{item_id}"
    HEADERS_A = {"X-Api-Key": USER_A, "Content-Type": "application/json"}
    HEADERS_B = {"X-Api-Key": USER_B, "Content-Type": "application/json"}
    U = item_id[:8]


def get(path, params=None, h=None):
    request_headers = HEADERS_A if h is None else h
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def post(path, json=None, h=None):
    request_headers = HEADERS_A if h is None else h
    return requests.post(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def put(path, json=None, h=None):
    request_headers = HEADERS_A if h is None else h
    return requests.put(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def delete(path, h=None):
    request_headers = HEADERS_A if h is None else h
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


class TestDocumentFullLifecycle:
    """Pattern 2+5+7: Document creation with auto-matching, update, cascading effects."""

    def test_document_lifecycle_with_auto_matching_and_tags(self):
        """Create matching rules, create doc, verify auto-assign, update, delete."""
        # 1. Create correspondent with matching
        match_word = f"invoiceword{uuid.uuid4().hex[:5]}"
        corr = post("/api/correspondents/", {
            "name": f"InvCorr-{U}-{uuid.uuid4().hex[:4]}",
            "match": match_word,
            "matching_algorithm": 1,
        }).json()

        # 2. Create doc type with matching
        type_phrase = f"receipt phrase {uuid.uuid4().hex[:5]}"
        dtype = post("/api/document_types/", {
            "name": f"ReceiptType-{U}-{uuid.uuid4().hex[:4]}",
            "match": type_phrase,
            "matching_algorithm": 3,
        }).json()

        # 3. Create tags with matching
        tag_word = f"tagword{uuid.uuid4().hex[:5]}"
        tag = post("/api/tags/", {
            "name": f"AutoTag-{U}-{uuid.uuid4().hex[:4]}",
            "match": tag_word,
            "matching_algorithm": 1,
        }).json()

        # 4. Create document that matches all
        doc = post("/api/documents/", {
            "title": f"Document with {match_word} and {tag_word}",
            "content": f"Contains {type_phrase} as well",
        }).json()

        assert doc["correspondent"] == corr["id"]
        assert doc["document_type"] == dtype["id"]
        assert tag["id"] in doc["tags"]

        # 5. Verify via GET
        doc_get = get(f"/api/documents/{doc['id']}/").json()
        assert doc_get["correspondent"] == corr["id"]
        assert doc_get["document_type"] == dtype["id"]
        assert tag["id"] in doc_get["tags"]

        # 6. Update document
        r = put(f"/api/documents/{doc['id']}/", {
            "title": "Updated title",
            "content": "Updated content",
            "correspondent": corr["id"],
            "document_type": None,
            "tags": [],
        })
        assert r.status_code == 200
        updated = r.json()
        assert updated["title"] == "Updated title"
        assert updated["document_type"] is None
        assert updated["tags"] == []

        # 7. Delete and verify
        assert delete(f"/api/documents/{doc['id']}/").status_code == 204
        assert get(f"/api/documents/{doc['id']}/").status_code == 404


class TestBulkEditWorkflow:
    """Pattern 5+7: Bulk operations actually modify documents."""

    def test_bulk_add_tag_and_set_correspondent(self):
        """Bulk operations should modify all specified documents."""
        # 1. Create resources
        tag = post("/api/tags/", {"name": f"BulkTag-{U}-{uuid.uuid4().hex[:4]}"}).json()
        corr = post("/api/correspondents/", {"name": f"BulkCorr-{U}-{uuid.uuid4().hex[:4]}"}).json()
        d1 = post("/api/documents/", {"title": "bulk1", "content": "x"}).json()
        d2 = post("/api/documents/", {"title": "bulk2", "content": "x"}).json()
        d3 = post("/api/documents/", {"title": "bulk3", "content": "x"}).json()

        # 2. Bulk add tag
        r = post("/api/documents/bulk_edit/", {
            "documents": [d1["id"], d2["id"]],
            "method": "add_tag",
            "parameters": {"tag": tag["id"]},
        })
        assert r.status_code == 200
        assert r.json()["result"] == "OK"

        # 3. Verify tag added to d1, d2 but NOT d3
        assert tag["id"] in get(f"/api/documents/{d1['id']}/").json()["tags"]
        assert tag["id"] in get(f"/api/documents/{d2['id']}/").json()["tags"]
        assert tag["id"] not in get(f"/api/documents/{d3['id']}/").json()["tags"]

        # 4. Bulk set correspondent
        r2 = post("/api/documents/bulk_edit/", {
            "documents": [d1["id"], d3["id"]],
            "method": "set_correspondent",
            "parameters": {"correspondent": corr["id"]},
        })
        assert r2.status_code == 200

        # 5. Verify
        assert get(f"/api/documents/{d1['id']}/").json()["correspondent"] == corr["id"]
        assert get(f"/api/documents/{d3['id']}/").json()["correspondent"] == corr["id"]
        assert get(f"/api/documents/{d2['id']}/").json()["correspondent"] is None

    def test_bulk_delete_removes_documents(self):
        """Bulk delete should remove all specified documents."""
        d1 = post("/api/documents/", {"title": "bdel1", "content": "x"}).json()
        d2 = post("/api/documents/", {"title": "bdel2", "content": "x"}).json()

        r = post("/api/documents/bulk_edit/", {
            "documents": [d1["id"], d2["id"]],
            "method": "delete",
        })
        assert r.status_code == 200

        assert get(f"/api/documents/{d1['id']}/").status_code == 404
        assert get(f"/api/documents/{d2['id']}/").status_code == 404

    def test_bulk_edit_invalid_document_returns_400(self):
        """Bulk edit with non-existent document ID should fail."""
        r = post("/api/documents/bulk_edit/", {
            "documents": [999999],
            "method": "delete",
        })
        assert r.status_code == 400


class TestDeletionCascadeEffects:
    """Pattern 7: Deleting entities has correct cascading effects on documents."""

    def test_delete_correspondent_nullifies_documents(self):
        """Deleting correspondent sets documents' correspondent to null."""
        corr = post("/api/correspondents/", {"name": f"DelCorr-{U}-{uuid.uuid4().hex[:4]}"}).json()
        d1 = post("/api/documents/", {"title": "dc1", "content": "x", "correspondent": corr["id"]}).json()
        d2 = post("/api/documents/", {"title": "dc2", "content": "x", "correspondent": corr["id"]}).json()

        # Delete correspondent
        assert delete(f"/api/correspondents/{corr['id']}/").status_code == 204

        # Documents should still exist with correspondent=null
        assert get(f"/api/documents/{d1['id']}/").json()["correspondent"] is None
        assert get(f"/api/documents/{d2['id']}/").json()["correspondent"] is None

    def test_delete_tag_removes_from_documents(self):
        """Deleting a tag removes it from all documents' tag arrays."""
        t1 = post("/api/tags/", {"name": f"DelTag1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        t2 = post("/api/tags/", {"name": f"DelTag2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        doc = post("/api/documents/", {"title": "tdel", "content": "x", "tags": [t1["id"], t2["id"]]}).json()

        # Delete t1
        assert delete(f"/api/tags/{t1['id']}/").status_code == 204

        # Document should have only t2
        doc_resp = get(f"/api/documents/{doc['id']}/").json()
        assert t1["id"] not in doc_resp["tags"]
        assert t2["id"] in doc_resp["tags"]

    def test_delete_custom_field_removes_from_documents(self):
        """Deleting a custom field removes it from all documents."""
        cf = post("/api/custom_fields/", {"name": f"DelCF-{U}-{uuid.uuid4().hex[:4]}", "data_type": "string"}).json()
        doc = post("/api/documents/", {
            "title": "cf-del",
            "content": "x",
            "custom_fields": [{"field": cf["id"], "value": "test"}],
        }).json()
        assert len(doc["custom_fields"]) == 1

        # Delete custom field
        assert delete(f"/api/custom_fields/{cf['id']}/").status_code == 204

        # Document's custom_fields should be empty
        doc_resp = get(f"/api/documents/{doc['id']}/").json()
        assert len(doc_resp["custom_fields"]) == 0


class TestDataIsolationWorkflow:
    """Pattern 6: Full isolation workflow across multiple entity types."""

    def test_full_isolation_across_all_entity_types(self):
        """User A's entire data model is invisible to User B."""
        # User A creates everything
        corr_a = post("/api/correspondents/", {"name": f"IsoCorr-{U}-{uuid.uuid4().hex[:4]}"}).json()
        dt_a = post("/api/document_types/", {"name": f"IsoDT-{U}-{uuid.uuid4().hex[:4]}"}).json()
        tag_a = post("/api/tags/", {"name": f"IsoTag-{U}-{uuid.uuid4().hex[:4]}"}).json()
        sp_a = post("/api/storage_paths/", {"name": f"IsoSP-{U}-{uuid.uuid4().hex[:4]}", "path": "/a"}).json()
        doc_a = post("/api/documents/", {
            "title": "isolated",
            "content": "secret",
            "correspondent": corr_a["id"],
            "document_type": dt_a["id"],
            "tags": [tag_a["id"]],
            "storage_path": sp_a["id"],
        }).json()

        # User B can't see any of it
        assert get(f"/api/correspondents/{corr_a['id']}/", h=HEADERS_B).status_code == 404
        assert get(f"/api/document_types/{dt_a['id']}/", h=HEADERS_B).status_code == 404
        assert get(f"/api/tags/{tag_a['id']}/", h=HEADERS_B).status_code == 404
        assert get(f"/api/storage_paths/{sp_a['id']}/", h=HEADERS_B).status_code == 404
        assert get(f"/api/documents/{doc_a['id']}/", h=HEADERS_B).status_code == 404

        # User B's lists don't include User A's data
        b_docs = get("/api/documents/", h=HEADERS_B).json()
        b_ids = [d["id"] for d in b_docs["results"]]
        assert doc_a["id"] not in b_ids

    def test_user_cannot_modify_others_documents(self):
        """User B cannot update or delete User A's documents."""
        doc = post("/api/documents/", {"title": "private", "content": "x"}).json()

        # User B tries to update
        r = put(f"/api/documents/{doc['id']}/", {"title": "hacked", "content": "y"}, h=HEADERS_B)
        assert r.status_code == 404

        # User B tries to delete
        r2 = delete(f"/api/documents/{doc['id']}/", h=HEADERS_B)
        assert r2.status_code == 404

        # Original doc untouched
        assert get(f"/api/documents/{doc['id']}/").json()["title"] == "private"


class TestMatchingAlgorithmsWorkflow:
    """Pattern 5: All matching algorithms tested together."""

    def test_algorithm_2_all_words_must_match(self):
        """Algorithm 2 (all): ALL words must be present."""
        w1 = f"word1{uuid.uuid4().hex[:5]}"
        w2 = f"word2{uuid.uuid4().hex[:5]}"
        corr = post("/api/correspondents/", {
            "name": f"AllCorr-{U}-{uuid.uuid4().hex[:4]}",
            "match": f"{w1} {w2}",
            "matching_algorithm": 2,
        }).json()

        # Has both words → match
        d1 = post("/api/documents/", {"title": f"{w1} blah {w2}", "content": "x"}).json()
        assert d1["correspondent"] == corr["id"]

        # Has only one word → no match
        d2 = post("/api/documents/", {"title": f"Only {w1} here", "content": "x"}).json()
        assert d2["correspondent"] is None

    def test_algorithm_4_regex_matching(self):
        """Algorithm 4 (regex): regex pattern match."""
        prefix = f"rx{uuid.uuid4().hex[:4]}"
        dt = post("/api/document_types/", {
            "name": f"RegexDT-{U}-{uuid.uuid4().hex[:4]}",
            "match": f"{prefix}\\d+",
            "matching_algorithm": 4,
        }).json()

        # Matches regex
        d1 = post("/api/documents/", {"title": f"Has {prefix}12345 in it", "content": "x"}).json()
        assert d1["document_type"] == dt["id"]

        # Doesn't match
        d2 = post("/api/documents/", {"title": f"Has {prefix} without digits", "content": "x"}).json()
        assert d2["document_type"] is None


class TestDocumentCustomFieldsWorkflow:
    """Pattern 2+5: Custom field lifecycle on documents."""

    def test_multiple_custom_fields_lifecycle(self):
        """Create multiple custom fields, use them on a document, update, verify."""
        cf_str = post("/api/custom_fields/", {"name": f"CFStr-{U}-{uuid.uuid4().hex[:4]}", "data_type": "string"}).json()
        cf_int = post("/api/custom_fields/", {"name": f"CFInt-{U}-{uuid.uuid4().hex[:4]}", "data_type": "integer"}).json()
        cf_bool = post("/api/custom_fields/", {"name": f"CFBool-{U}-{uuid.uuid4().hex[:4]}", "data_type": "boolean"}).json()

        # Create doc with custom fields
        doc = post("/api/documents/", {
            "title": "multi-cf",
            "content": "x",
            "custom_fields": [
                {"field": cf_str["id"], "value": "hello"},
                {"field": cf_int["id"], "value": 42},
                {"field": cf_bool["id"], "value": True},
            ],
        }).json()
        assert len(doc["custom_fields"]) == 3

        # Verify values
        cf_map = {cf["field"]: cf["value"] for cf in doc["custom_fields"]}
        assert cf_map[cf_str["id"]] == "hello"
        assert cf_map[cf_int["id"]] == 42
        assert cf_map[cf_bool["id"]] is True

        # Update document custom fields
        updated = put(f"/api/documents/{doc['id']}/", {
            "title": "multi-cf",
            "content": "x",
            "custom_fields": [
                {"field": cf_str["id"], "value": "updated"},
            ],
        }).json()
        assert len(updated["custom_fields"]) == 1
        assert updated["custom_fields"][0]["value"] == "updated"


class TestDocumentCountConsistency:
    """Pattern 5+7: document_count on entities stays consistent."""

    def test_document_count_updates_with_document_changes(self):
        """document_count should reflect reality after creates and deletes."""
        corr = post("/api/correspondents/", {"name": f"CntC-{U}-{uuid.uuid4().hex[:4]}"}).json()
        tag = post("/api/tags/", {"name": f"CntT-{U}-{uuid.uuid4().hex[:4]}"}).json()

        # Initially 0
        assert get(f"/api/correspondents/{corr['id']}/").json()["document_count"] == 0
        assert get(f"/api/tags/{tag['id']}/").json()["document_count"] == 0

        # Create documents
        d1 = post("/api/documents/", {"title": "cnt1", "content": "x", "correspondent": corr["id"], "tags": [tag["id"]]}).json()
        d2 = post("/api/documents/", {"title": "cnt2", "content": "x", "correspondent": corr["id"], "tags": [tag["id"]]}).json()

        assert get(f"/api/correspondents/{corr['id']}/").json()["document_count"] == 2
        assert get(f"/api/tags/{tag['id']}/").json()["document_count"] == 2

        # Delete one document
        delete(f"/api/documents/{d1['id']}/")

        assert get(f"/api/correspondents/{corr['id']}/").json()["document_count"] == 1
        assert get(f"/api/tags/{tag['id']}/").json()["document_count"] == 1


class TestSearchIsolation:
    """Pattern 3+6: Search only returns current user's documents."""

    def test_search_respects_user_isolation(self):
        """Search results must be scoped to the requesting user."""
        unique = f"searchiso{uuid.uuid4().hex[:8]}"
        # User A creates a doc
        post("/api/documents/", {"title": unique, "content": unique})
        # User B creates a doc with same content
        post("/api/documents/", {"title": f"other-{unique}", "content": unique}, h=HEADERS_B)

        # User A searches
        r_a = get("/api/search/", params={"query": unique})
        ids_a = [d["id"] for d in r_a.json()]

        # User B searches
        r_b = get("/api/search/", params={"query": unique}, h=HEADERS_B)
        ids_b = [d["id"] for d in r_b.json()]

        # No overlap
        assert set(ids_a).isdisjoint(set(ids_b))
        assert len(ids_a) >= 1
        assert len(ids_b) >= 1
