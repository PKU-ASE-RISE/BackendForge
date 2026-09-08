"""
L2 Integration Tests for Strapi Headless CMS API.
Adversarial tests targeting common LLM implementation bugs:
- camelCase field names (displayName, contentType, createdAt, pageSize, etc.)
- Nested data (fields array in content types, populated relations)
- Filtering/sorting/pagination actually working
- Correct status codes (201/204/404/409)
- Role enforcement (admin/editor/author)
- Pagination meta object structure
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)

ADMIN_TOKEN = "admin_1"
EDITOR_TOKEN = "editor_2"
AUTHOR_TOKEN_1 = "author_3"
AUTHOR_TOKEN_2 = "author_4"


def h(token=ADMIN_TOKEN):
    return {"X-API-Key": token}


def unique_name():
    return f"ct_{uuid.uuid4().hex[:8]}"


def create_content_type(name=None, display_name=None, settings=None):
    name = name or unique_name()
    display_name = display_name or f"Display {name}"
    payload = {"name": name, "displayName": display_name}
    if settings:
        payload["settings"] = settings
    resp = requests.post(f"{BASE_URL}/content-types", json=payload, headers=h(), timeout=REQUEST_TIMEOUT)
    assert resp.status_code == 201
    return resp.json()["data"]


def add_field(ct_id, name, field_type, **kwargs):
    payload = {"name": name, "type": field_type, **kwargs}
    resp = requests.post(f"{BASE_URL}/content-types/{ct_id}/fields", json=payload, headers=h(), timeout=REQUEST_TIMEOUT)
    assert resp.status_code == 201
    return resp.json()["data"]


# =============================================================================
# L2 TESTS
# =============================================================================


class TestContentTypeFieldCasing:
    """Pattern 1: Verify exact camelCase field names."""

    def test_content_type_response_camelcase(self):
        ct = create_content_type()
        assert "id" in ct
        assert "name" in ct
        assert "displayName" in ct
        assert "createdAt" in ct
        assert "updatedAt" in ct
        assert "fields" in ct
        assert "settings" in ct
        assert isinstance(ct["fields"], list)
        # Verify snake_case NOT present
        assert "display_name" not in ct
        assert "created_at" not in ct

    def test_field_response_camelcase(self):
        ct = create_content_type()
        field = add_field(ct["id"], "title", "text", required=True)
        assert "id" in field
        assert "name" in field and field["name"] == "title"
        assert "type" in field and field["type"] == "text"
        assert "required" in field and field["required"] is True
        assert "unique" in field

    def test_entry_response_has_camelcase_system_fields(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "title", "text")

        resp = requests.post(f"{BASE_URL}/content/{name}", json={"title": "Test"},
                             headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        entry = resp.json()["data"]
        assert "id" in entry
        assert "createdBy" in entry
        assert "createdAt" in entry
        assert "updatedAt" in entry
        assert "locale" in entry
        assert entry["title"] == "Test"
        # Verify snake_case NOT present
        assert "created_by" not in entry
        assert "created_at" not in entry


class TestPaginationMeta:
    """Pattern 3: Pagination meta object must have correct structure."""

    def test_list_entries_returns_pagination_meta(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "val", "number")

        # Create 5 entries
        for i in range(5):
            requests.post(f"{BASE_URL}/content/{name}", json={"val": i}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}", params={"page": 1, "pageSize": 2},
                            headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert "pagination" in body["meta"]
        pag = body["meta"]["pagination"]
        assert pag["page"] == 1
        assert pag["pageSize"] == 2
        assert pag["total"] == 5
        assert pag["pageCount"] == 3
        assert len(body["data"]) == 2

    def test_pagination_page_2(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "n", "number")

        for i in range(5):
            requests.post(f"{BASE_URL}/content/{name}", json={"n": i}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp1 = requests.get(f"{BASE_URL}/content/{name}", params={"page": 1, "pageSize": 3},
                             headers=h(), timeout=REQUEST_TIMEOUT)
        resp2 = requests.get(f"{BASE_URL}/content/{name}", params={"page": 2, "pageSize": 3},
                             headers=h(), timeout=REQUEST_TIMEOUT)
        ids1 = [e["id"] for e in resp1.json()["data"]]
        ids2 = [e["id"] for e in resp2.json()["data"]]
        assert len(ids1) == 3
        assert len(ids2) == 2
        assert set(ids1).isdisjoint(set(ids2))


class TestFiltering:
    """Pattern 3: Filters must actually filter results."""

    def test_filter_eq(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "status", "text")

        requests.post(f"{BASE_URL}/content/{name}", json={"status": "active"}, headers=h(), timeout=REQUEST_TIMEOUT)
        requests.post(f"{BASE_URL}/content/{name}", json={"status": "inactive"}, headers=h(), timeout=REQUEST_TIMEOUT)
        requests.post(f"{BASE_URL}/content/{name}", json={"status": "active"}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}",
                            params={"filters[status][eq]": "active"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        entries = resp.json()["data"]
        assert len(entries) == 2
        for e in entries:
            assert e["status"] == "active"

    def test_filter_contains(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "title", "text")

        requests.post(f"{BASE_URL}/content/{name}", json={"title": "Hello World"}, headers=h(), timeout=REQUEST_TIMEOUT)
        requests.post(f"{BASE_URL}/content/{name}", json={"title": "Goodbye"}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}",
                            params={"filters[title][contains]": "World"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        entries = resp.json()["data"]
        assert len(entries) == 1
        assert "World" in entries[0]["title"]

    def test_filter_gt_lt_numbers(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "score", "number")

        for s in [10, 20, 30, 40, 50]:
            requests.post(f"{BASE_URL}/content/{name}", json={"score": s}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}",
                            params={"filters[score][gt]": "25"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        assert len(entries) == 3
        for e in entries:
            assert e["score"] > 25


class TestSorting:
    """Pattern 3: Sort parameter must actually sort results."""

    def test_sort_asc(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "priority", "number")

        for p in [30, 10, 20]:
            requests.post(f"{BASE_URL}/content/{name}", json={"priority": p}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}",
                            params={"sort": "priority:asc"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        priorities = [e["priority"] for e in entries]
        assert priorities == sorted(priorities)

    def test_sort_desc(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "rank", "number")

        for r in [5, 15, 10]:
            requests.post(f"{BASE_URL}/content/{name}", json={"rank": r}, headers=h(), timeout=REQUEST_TIMEOUT)

        resp = requests.get(f"{BASE_URL}/content/{name}",
                            params={"sort": "rank:desc"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        ranks = [e["rank"] for e in entries]
        assert ranks == sorted(ranks, reverse=True)


class TestRelationPopulation:
    """Pattern 2: Relations must be populated (return objects, not just IDs)."""

    def test_one_to_one_relation_populated(self):
        # Create author content type
        author_name = unique_name()
        author_ct = create_content_type(name=author_name)
        add_field(author_ct["id"], "full_name", "text")

        # Create article content type with relation to author
        article_name = unique_name()
        article_ct = create_content_type(name=article_name)
        add_field(article_ct["id"], "title", "text")
        add_field(article_ct["id"], "author", "relation",
                  target=author_name, relationType="oneToOne")

        # Create author entry
        author_entry = requests.post(f"{BASE_URL}/content/{author_name}",
                                     json={"full_name": "John Doe"}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]

        # Create article with author relation
        article_entry = requests.post(f"{BASE_URL}/content/{article_name}",
                                      json={"title": "My Article", "author": author_entry["id"]},
                                      headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]

        # GET article should populate the relation
        resp = requests.get(f"{BASE_URL}/content/{article_name}/{article_entry['id']}",
                            headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        article = resp.json()["data"]
        assert article["title"] == "My Article"
        # Relation should be populated as an object
        assert isinstance(article["author"], dict)
        assert article["author"]["full_name"] == "John Doe"
        assert article["author"]["id"] == author_entry["id"]


class TestRoleEnforcement:
    """Pattern 6: Role permissions enforced."""

    def test_editor_cannot_create_content_type(self):
        resp = requests.post(f"{BASE_URL}/content-types",
                             json={"name": unique_name(), "displayName": "X"},
                             headers=h(EDITOR_TOKEN), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 403

    def test_author_cannot_create_content_type(self):
        resp = requests.post(f"{BASE_URL}/content-types",
                             json={"name": unique_name(), "displayName": "X"},
                             headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 403

    def test_author_cannot_update_others_entry(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "body", "text")

        # Author 1 creates entry
        entry = requests.post(f"{BASE_URL}/content/{name}",
                              json={"body": "Author 1's"},
                              headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT).json()["data"]

        # Author 2 tries to update
        resp = requests.put(f"{BASE_URL}/content/{name}/{entry['id']}",
                            json={"body": "Hacked"}, headers=h(AUTHOR_TOKEN_2), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 403

    def test_editor_can_update_any_entry(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "text", "text")

        entry = requests.post(f"{BASE_URL}/content/{name}",
                              json={"text": "Original"},
                              headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT).json()["data"]

        resp = requests.put(f"{BASE_URL}/content/{name}/{entry['id']}",
                            json={"text": "Edited by editor"}, headers=h(EDITOR_TOKEN), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["data"]["text"] == "Edited by editor"


class TestStatusCodes:
    """Pattern 4: Verify exact status codes."""

    def test_create_content_type_returns_201(self):
        resp = requests.post(f"{BASE_URL}/content-types",
                             json={"name": unique_name(), "displayName": "D"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201

    def test_create_entry_returns_201(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "x", "text")
        resp = requests.post(f"{BASE_URL}/content/{name}", json={"x": "v"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201

    def test_delete_content_type_returns_204(self):
        ct = create_content_type()
        resp = requests.delete(f"{BASE_URL}/content-types/{ct['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204

    def test_delete_entry_returns_204(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "x", "text")
        entry = requests.post(f"{BASE_URL}/content/{name}", json={"x": "v"}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        resp = requests.delete(f"{BASE_URL}/content/{name}/{entry['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204

    def test_get_nonexistent_content_type_returns_404(self):
        resp = requests.get(f"{BASE_URL}/content-types/99999", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 404

    def test_get_nonexistent_entry_returns_404(self):
        name = unique_name()
        create_content_type(name=name)
        resp = requests.get(f"{BASE_URL}/content/{name}/99999", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 404

    def test_duplicate_content_type_name_returns_409(self):
        name = unique_name()
        create_content_type(name=name)
        resp = requests.post(f"{BASE_URL}/content-types",
                             json={"name": name, "displayName": "Dup"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 409


class TestFieldValidation:
    """Pattern 5: Required/unique field validation actually works."""

    def test_required_field_missing_returns_400(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "required_field", "text", required=True)

        resp = requests.post(f"{BASE_URL}/content/{name}", json={}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 400

    def test_unique_field_violation_returns_409(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "code", "text", unique=True)

        requests.post(f"{BASE_URL}/content/{name}", json={"code": "ABC"}, headers=h(), timeout=REQUEST_TIMEOUT)
        resp = requests.post(f"{BASE_URL}/content/{name}", json={"code": "ABC"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 409

    def test_enum_field_invalid_value_returns_400(self):
        name = unique_name()
        ct = create_content_type(name=name)
        add_field(ct["id"], "status", "enum", enumValues=["draft", "published"])

        resp = requests.post(f"{BASE_URL}/content/{name}", json={"status": "invalid"}, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 400


class TestComponentEmbedding:
    """Pattern 2: Components embedded in entries."""

    def test_component_data_roundtrip(self):
        # Create component
        comp_name = unique_name()
        resp = requests.post(f"{BASE_URL}/components", json={
            "name": comp_name,
            "displayName": "SEO",
            "fields": [
                {"name": "meta_title", "type": "text"},
                {"name": "meta_desc", "type": "text"}
            ]
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201

        # Create content type with component field
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "seo", "component", component=comp_name)

        # Create entry with component data
        resp = requests.post(f"{BASE_URL}/content/{ct_name}", json={
            "seo": {"meta_title": "My Page", "meta_desc": "Description here"}
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        entry = resp.json()["data"]
        assert entry["seo"]["meta_title"] == "My Page"
        assert entry["seo"]["meta_desc"] == "Description here"

        # GET should also return component data
        resp = requests.get(f"{BASE_URL}/content/{ct_name}/{entry['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        data = resp.json()["data"]
        assert data["seo"]["meta_title"] == "My Page"
