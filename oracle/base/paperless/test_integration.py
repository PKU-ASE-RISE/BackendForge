"""
BackendForge — L2 Integration Tests for Paperless-ngx
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
USER_A = f"l2user-{RUN_ID[:8]}"
USER_B = f"l2other-{RUN_ID[:8]}"
HEADERS_A = {"X-Api-Key": USER_A, "Content-Type": "application/json"}
HEADERS_B = {"X-Api-Key": USER_B, "Content-Type": "application/json"}
U = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_users(request):
    """Give every item fresh user namespaces so state cannot leak between tests."""
    global USER_A, USER_B, HEADERS_A, HEADERS_B, U

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_A = f"l2user-{item_id}"
    USER_B = f"l2other-{item_id}"
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


class TestDocumentFieldsAndStatusCodes:
    """Pattern 1+4: Verify exact field names and status codes."""

    def test_document_create_returns_201_with_all_fields(self):
        """Verify POST returns 201 and all schema fields."""
        r = post("/api/documents/", {
            "title": f"Doc-{U}-{uuid.uuid4().hex[:4]}",
            "content": "test content body",
        })
        assert r.status_code == 201
        doc = r.json()
        assert "id" in doc
        assert "title" in doc
        assert "content" in doc
        assert "created_date" in doc
        assert "added_date" in doc
        assert "correspondent" in doc
        assert "document_type" in doc
        assert "storage_path" in doc
        assert "tags" in doc
        assert "archive_serial_number" in doc
        assert "custom_fields" in doc
        assert isinstance(doc["tags"], list)
        assert isinstance(doc["custom_fields"], list)
        assert doc["correspondent"] is None
        assert doc["document_type"] is None
        assert doc["storage_path"] is None

    def test_document_delete_returns_204(self):
        """DELETE must return 204, not 200."""
        doc = post("/api/documents/", {"title": f"Del-{U}", "content": "x"}).json()
        r = delete(f"/api/documents/{doc['id']}/")
        assert r.status_code == 204

    def test_nonexistent_document_returns_404(self):
        r = get("/api/documents/999999/")
        assert r.status_code == 404


class TestCorrespondentFields:
    """Pattern 1+2: Verify correspondent field names and document_count."""

    def test_correspondent_create_has_all_fields(self):
        name = f"Corr-{U}-{uuid.uuid4().hex[:4]}"
        r = post("/api/correspondents/", {"name": name, "match": "test", "matching_algorithm": 3})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert "match" in data
        assert "matching_algorithm" in data
        assert "document_count" in data  # computed field
        assert data["name"] == name
        assert data["match"] == "test"
        assert data["matching_algorithm"] == 3
        assert data["document_count"] == 0

    def test_correspondent_document_count_computed(self):
        """document_count must reflect actual documents, not be hardcoded 0."""
        name = f"CntCorr-{U}-{uuid.uuid4().hex[:4]}"
        corr = post("/api/correspondents/", {"name": name}).json()

        # Create 2 documents with this correspondent
        post("/api/documents/", {"title": "d1", "content": "c1", "correspondent": corr["id"]})
        post("/api/documents/", {"title": "d2", "content": "c2", "correspondent": corr["id"]})

        # Verify count
        resp = get(f"/api/correspondents/{corr['id']}/")
        assert resp.json()["document_count"] == 2


class TestTagFields:
    """Pattern 1: Verify tag field names including is_inbox_tag and color."""

    def test_tag_create_returns_all_fields(self):
        name = f"Tag-{U}-{uuid.uuid4().hex[:4]}"
        r = post("/api/tags/", {
            "name": name,
            "color": "#ff5733",
            "is_inbox_tag": True,
            "match": "urgent",
            "matching_algorithm": 1,
        })
        assert r.status_code == 201
        tag = r.json()
        assert "id" in tag
        assert "name" in tag
        assert "color" in tag
        assert "match" in tag
        assert "matching_algorithm" in tag
        assert "is_inbox_tag" in tag
        assert "document_count" in tag
        assert tag["name"] == name
        assert tag["color"] == "#ff5733"
        assert tag["is_inbox_tag"] is True
        assert tag["document_count"] == 0


class TestPaginationStructure:
    """Pattern 3: Verify pagination response has count, next, previous, results."""

    def test_all_list_endpoints_return_pagination_fields(self):
        endpoints = [
            "/api/documents/",
            "/api/correspondents/",
            "/api/document_types/",
            "/api/tags/",
            "/api/storage_paths/",
            "/api/custom_fields/",
            "/api/saved_views/",
        ]
        for ep in endpoints:
            r = get(ep)
            assert r.status_code == 200, f"Failed for {ep}"
            data = r.json()
            assert "count" in data, f"Missing 'count' in {ep}"
            assert "next" in data, f"Missing 'next' in {ep}"
            assert "previous" in data, f"Missing 'previous' in {ep}"
            assert "results" in data, f"Missing 'results' in {ep}"

    def test_pagination_actually_limits(self):
        """page_size=2 must limit results to 2."""
        for i in range(4):
            post("/api/tags/", {"name": f"PagTag-{U}-{uuid.uuid4().hex[:4]}-{i}"})
        r = get("/api/tags/", params={"page_size": 2})
        data = r.json()
        assert len(data["results"]) <= 2
        assert data["count"] >= 4

    def test_pagination_page2_different_from_page1(self):
        """Page 2 must return different items than page 1."""
        for i in range(4):
            post("/api/correspondents/", {"name": f"PgCorr-{U}-{uuid.uuid4().hex[:4]}-{i}"})

        r1 = get("/api/correspondents/", params={"page": 1, "page_size": 2})
        r2 = get("/api/correspondents/", params={"page": 2, "page_size": 2})
        ids1 = {c["id"] for c in r1.json()["results"]}
        ids2 = {c["id"] for c in r2.json()["results"]}
        assert ids1.isdisjoint(ids2)  # No overlap


class TestFilteringActuallyWorks:
    """Pattern 3: Verify document filters actually filter."""

    def test_filter_by_correspondent_excludes_others(self):
        c1 = post("/api/correspondents/", {"name": f"FC1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        c2 = post("/api/correspondents/", {"name": f"FC2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        d1 = post("/api/documents/", {"title": "in-c1", "content": "x", "correspondent": c1["id"]}).json()
        d2 = post("/api/documents/", {"title": "in-c2", "content": "x", "correspondent": c2["id"]}).json()

        r = get("/api/documents/", params={"correspondent__id": c1["id"]})
        ids = [d["id"] for d in r.json()["results"]]
        assert d1["id"] in ids
        assert d2["id"] not in ids

    def test_filter_by_document_type(self):
        dt = post("/api/document_types/", {"name": f"FDT-{U}-{uuid.uuid4().hex[:4]}"}).json()
        d1 = post("/api/documents/", {"title": "typed", "content": "x", "document_type": dt["id"]}).json()
        d2 = post("/api/documents/", {"title": "untyped", "content": "x"}).json()

        r = get("/api/documents/", params={"document_type__id": dt["id"]})
        ids = [d["id"] for d in r.json()["results"]]
        assert d1["id"] in ids
        assert d2["id"] not in ids

    def test_filter_tags_id_all(self):
        """tags__id__all: document must have ALL listed tags."""
        t1 = post("/api/tags/", {"name": f"FTA1-{U}-{uuid.uuid4().hex[:4]}"}).json()
        t2 = post("/api/tags/", {"name": f"FTA2-{U}-{uuid.uuid4().hex[:4]}"}).json()
        d_both = post("/api/documents/", {"title": "both", "content": "x", "tags": [t1["id"], t2["id"]]}).json()
        d_one = post("/api/documents/", {"title": "one", "content": "x", "tags": [t1["id"]]}).json()

        r = get("/api/documents/", params={"tags__id__all": f"{t1['id']},{t2['id']}"})
        ids = [d["id"] for d in r.json()["results"]]
        assert d_both["id"] in ids
        assert d_one["id"] not in ids

    def test_filter_title_icontains(self):
        """title__icontains is case-insensitive substring match."""
        unique_str = f"xyzzy{uuid.uuid4().hex[:6]}"
        d = post("/api/documents/", {"title": f"Hello {unique_str} World", "content": "x"}).json()
        other = post("/api/documents/", {"title": "unrelated doc", "content": "x"}).json()

        r = get("/api/documents/", params={"title__icontains": unique_str.upper()})
        ids = [d["id"] for d in r.json()["results"]]
        assert d["id"] in ids
        assert other["id"] not in ids

    def test_ordering_descending(self):
        """Ordering with - prefix should reverse order."""
        d1 = post("/api/documents/", {"title": "aaa", "content": "x"}).json()
        d2 = post("/api/documents/", {"title": "zzz", "content": "x"}).json()

        r = get("/api/documents/", params={"ordering": "-title"})
        titles = [d["title"] for d in r.json()["results"]]
        # zzz should come before aaa
        if "zzz" in titles and "aaa" in titles:
            assert titles.index("zzz") < titles.index("aaa")


class TestDataIsolation:
    """Pattern 6: Verify user A cannot see user B's data."""

    def test_documents_isolated_between_users(self):
        """User A's documents invisible to user B."""
        doc = post("/api/documents/", {"title": f"private-{U}", "content": "secret"}).json()

        # User B shouldn't see it
        r = get("/api/documents/", h=HEADERS_B)
        ids = [d["id"] for d in r.json()["results"]]
        assert doc["id"] not in ids

    def test_correspondent_isolated_between_users(self):
        corr = post("/api/correspondents/", {"name": f"IsoCorr-{U}-{uuid.uuid4().hex[:4]}"}).json()
        r = get(f"/api/correspondents/{corr['id']}/", h=HEADERS_B)
        assert r.status_code == 404

    def test_tags_isolated_between_users(self):
        tag = post("/api/tags/", {"name": f"IsoTag-{U}-{uuid.uuid4().hex[:4]}"}).json()
        r = get(f"/api/tags/{tag['id']}/", h=HEADERS_B)
        assert r.status_code == 404

    def test_cannot_assign_other_users_correspondent(self):
        """Assigning another user's correspondent should fail."""
        corr_b = post("/api/correspondents/", {"name": f"CorrB-{U}-{uuid.uuid4().hex[:4]}"}, h=HEADERS_B).json()
        r = post("/api/documents/", {"title": "steal", "content": "x", "correspondent": corr_b["id"]})
        assert r.status_code == 400


class TestAutoMatching:
    """Pattern 5: Verify matching algorithms actually work."""

    def test_matching_algorithm_any_assigns_correspondent(self):
        """Algorithm 1 (any): if any word matches, assign."""
        word = f"matchword{uuid.uuid4().hex[:6]}"
        corr = post("/api/correspondents/", {
            "name": f"AnyCorr-{U}-{uuid.uuid4().hex[:4]}",
            "match": f"{word} otherstuff",
            "matching_algorithm": 1,
        }).json()

        doc = post("/api/documents/", {
            "title": f"This has {word} in it",
            "content": "nothing special",
        }).json()
        assert doc["correspondent"] == corr["id"]

    def test_matching_algorithm_exact_substring(self):
        """Algorithm 3 (exact): match string must appear as substring."""
        phrase = f"exact phrase {uuid.uuid4().hex[:6]}"
        dt = post("/api/document_types/", {
            "name": f"ExactDT-{U}-{uuid.uuid4().hex[:4]}",
            "match": phrase,
            "matching_algorithm": 3,
        }).json()

        # Should match
        doc1 = post("/api/documents/", {
            "title": f"Contains {phrase} here",
            "content": "blah",
        }).json()
        assert doc1["document_type"] == dt["id"]

        # Should NOT match (partial)
        doc2 = post("/api/documents/", {
            "title": "no match here",
            "content": "blah",
        }).json()
        assert doc2["document_type"] is None

    def test_explicit_value_overrides_auto_match(self):
        """Explicit correspondent in POST body overrides auto-matching."""
        word = f"overrideword{uuid.uuid4().hex[:6]}"
        auto_corr = post("/api/correspondents/", {
            "name": f"AutoCorr-{U}-{uuid.uuid4().hex[:4]}",
            "match": word,
            "matching_algorithm": 1,
        }).json()
        manual_corr = post("/api/correspondents/", {
            "name": f"ManualCorr-{U}-{uuid.uuid4().hex[:4]}",
        }).json()

        doc = post("/api/documents/", {
            "title": f"Has {word} word",
            "content": "x",
            "correspondent": manual_corr["id"],
        }).json()
        assert doc["correspondent"] == manual_corr["id"]

    def test_tag_matching_adds_all_matching_tags(self):
        """All matching tags should be added."""
        w1 = f"tagmatch1{uuid.uuid4().hex[:5]}"
        w2 = f"tagmatch2{uuid.uuid4().hex[:5]}"
        t1 = post("/api/tags/", {"name": f"T1-{U}-{uuid.uuid4().hex[:4]}", "match": w1, "matching_algorithm": 1}).json()
        t2 = post("/api/tags/", {"name": f"T2-{U}-{uuid.uuid4().hex[:4]}", "match": w2, "matching_algorithm": 1}).json()

        doc = post("/api/documents/", {
            "title": f"Contains {w1} and {w2}",
            "content": "x",
        }).json()
        assert t1["id"] in doc["tags"]
        assert t2["id"] in doc["tags"]


class TestASNUniqueness:
    """Pattern 8: ASN uniqueness constraint."""

    def test_duplicate_asn_returns_400(self):
        asn = 9999000 + int(uuid.uuid4().hex[:4], 16)
        post("/api/documents/", {"title": "d1", "content": "x", "archive_serial_number": asn})
        r = post("/api/documents/", {"title": "d2", "content": "x", "archive_serial_number": asn})
        assert r.status_code == 400

    def test_null_asn_allows_multiple(self):
        r1 = post("/api/documents/", {"title": "no-asn1", "content": "x"})
        r2 = post("/api/documents/", {"title": "no-asn2", "content": "x"})
        assert r1.status_code == 201
        assert r2.status_code == 201


class TestCustomFields:
    """Pattern 1+2: Custom fields on documents."""

    def test_custom_field_on_document_roundtrip(self):
        """Custom field values should persist and return correctly."""
        cf = post("/api/custom_fields/", {"name": f"CF-{U}-{uuid.uuid4().hex[:4]}", "data_type": "string"}).json()
        doc = post("/api/documents/", {
            "title": "cf-doc",
            "content": "x",
            "custom_fields": [{"field": cf["id"], "value": "hello world"}],
        }).json()
        assert len(doc["custom_fields"]) == 1
        assert doc["custom_fields"][0]["field"] == cf["id"]
        assert doc["custom_fields"][0]["value"] == "hello world"

        # GET to verify roundtrip
        resp = get(f"/api/documents/{doc['id']}/")
        assert resp.json()["custom_fields"][0]["value"] == "hello world"

    def test_custom_field_data_type_in_response(self):
        cf = post("/api/custom_fields/", {"name": f"CFdt-{U}-{uuid.uuid4().hex[:4]}", "data_type": "integer"}).json()
        assert "id" in cf
        assert "name" in cf
        assert "data_type" in cf
        assert cf["data_type"] == "integer"


class TestSearchEndpoint:
    """Pattern 3+5: Search actually searches content."""

    def test_search_returns_matching_documents(self):
        unique_word = f"searchable{uuid.uuid4().hex[:8]}"
        doc = post("/api/documents/", {"title": "generic", "content": f"Has {unique_word} inside"}).json()
        post("/api/documents/", {"title": "other", "content": "nothing relevant"})

        r = get("/api/search/", params={"query": unique_word})
        assert r.status_code == 200
        results = r.json()
        ids = [item["id"] for item in results]
        assert doc["id"] in ids

    def test_search_includes_hit_metadata(self):
        """Search results should have __search_hit__ with score."""
        word = f"hitword{uuid.uuid4().hex[:6]}"
        post("/api/documents/", {"title": word, "content": word})

        r = get("/api/search/", params={"query": word})
        results = r.json()
        assert len(results) >= 1
        assert "__search_hit__" in results[0]
        hit = results[0]["__search_hit__"]
        assert "score" in hit
        assert "rank" in hit


class TestUniqueNames:
    """Pattern 8: Name uniqueness per user."""

    def test_duplicate_correspondent_name_returns_400(self):
        name = f"UniqueCorr-{uuid.uuid4().hex[:8]}"
        r1 = post("/api/correspondents/", {"name": name})
        assert r1.status_code == 201
        r2 = post("/api/correspondents/", {"name": name})
        assert r2.status_code == 400

    def test_same_name_different_users_ok(self):
        """Same name for different users should be allowed."""
        name = f"SharedName-{uuid.uuid4().hex[:8]}"
        r1 = post("/api/tags/", {"name": name})
        assert r1.status_code == 201
        r2 = post("/api/tags/", {"name": name}, h=HEADERS_B)
        assert r2.status_code == 201


class TestSavedViewFields:
    """Pattern 1+2: Saved view field names and nested filter_rules."""

    def test_saved_view_create_with_filter_rules(self):
        r = post("/api/saved_views/", {
            "name": f"SV-{U}-{uuid.uuid4().hex[:4]}",
            "sort_field": "title",
            "sort_reverse": True,
            "filter_rules": [{"rule_type": 19, "value": "invoice"}],
        })
        assert r.status_code == 201
        sv = r.json()
        assert "id" in sv
        assert "name" in sv
        assert "sort_field" in sv
        assert "sort_reverse" in sv
        assert "filter_rules" in sv
        assert sv["sort_field"] == "title"
        assert sv["sort_reverse"] is True
        assert len(sv["filter_rules"]) == 1
        assert sv["filter_rules"][0]["rule_type"] == 19
        assert sv["filter_rules"][0]["value"] == "invoice"


class TestStoragePathFields:
    """Pattern 1: Verify storage path has all required fields."""

    def test_storage_path_create_returns_all_fields(self):
        r = post("/api/storage_paths/", {
            "name": f"SP-{U}-{uuid.uuid4().hex[:4]}",
            "path": "/archive/{correspondent}/{title}",
        })
        assert r.status_code == 201
        sp = r.json()
        assert "id" in sp
        assert "name" in sp
        assert "path" in sp
        assert "match" in sp
        assert "matching_algorithm" in sp
        assert "document_count" in sp
        assert sp["path"] == "/archive/{correspondent}/{title}"


class TestTasksEndpoint:
    """Pattern 4: Tasks returns empty array."""

    def test_tasks_returns_empty_array(self):
        r = get("/api/tasks/")
        assert r.status_code == 200
        assert r.json() == []
