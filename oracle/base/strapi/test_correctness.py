"""
Test suite for Strapi Headless CMS API.
Tests cover content types, dynamic entries, field validation, relations,
components, localization, filtering, sorting, pagination, role enforcement,
media upload, and webhooks.
"""

import os

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)

ADMIN_TOKEN = "admin_1"
EDITOR_TOKEN = "editor_2"
AUTHOR_TOKEN_1 = "author_3"
AUTHOR_TOKEN_2 = "author_4"


def headers(token=ADMIN_TOKEN):
    return {"X-API-Key": token}


def json_headers(token=ADMIN_TOKEN):
    return {"X-API-Key": token, "Content-Type": "application/json"}


def isolated_name(prefix, test_name):
    return f"{prefix}_{test_name.removeprefix('test_').lower()}"


# ─── Authentication ─────────────────────────────────────────────────────────


class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/content-types", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/content-types", headers={"X-API-Key": "invalid"},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        resp = requests.get(f"{BASE_URL}/content-types", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200


# ─── Content Types CRUD ─────────────────────────────────────────────────────


class TestContentTypes:
    def test_list_content_types_empty(self):
        resp = requests.get(f"{BASE_URL}/content-types", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_create_content_type(self):
        payload = {
            "name": "article",
            "displayName": "Article",
            "description": "Blog articles",
            "settings": {"draftAndPublish": True, "localization": True},
        }
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "article"
        assert data["displayName"] == "Article"
        assert data["id"] is not None
        assert data["settings"]["localization"] is True

    def test_create_duplicate_content_type_returns_409(self):
        payload = {
            "name": "duplicate_article_conflict_probe",
            "displayName": "Article Dup",
        }
        requests.post(
            f"{BASE_URL}/content-types",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 409

    def test_create_content_type_missing_name_returns_400(self):
        payload = {"displayName": "No Name"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400

    def test_get_content_type(self):
        # First create one
        payload = {"name": "category", "displayName": "Category"}
        create_resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        ct_id = create_resp.json()["data"]["id"]

        resp = requests.get(
            f"{BASE_URL}/content-types/{ct_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "category"

    def test_get_nonexistent_content_type_returns_404(self):
        resp = requests.get(f"{BASE_URL}/content-types/9999", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 404

    def test_update_content_type(self):
        payload = {"name": "tag", "displayName": "Tag"}
        create_resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        ct_id = create_resp.json()["data"]["id"]

        update_payload = {"displayName": "Tags", "description": "Content tags"}
        resp = requests.put(
            f"{BASE_URL}/content-types/{ct_id}",
            json=update_payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["displayName"] == "Tags"
        assert resp.json()["data"]["description"] == "Content tags"

    def test_delete_content_type(self):
        payload = {"name": "temp_type", "displayName": "Temp"}
        create_resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        ct_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/content-types/{ct_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204

        resp = requests.get(
            f"{BASE_URL}/content-types/{ct_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 404


# ─── Fields ─────────────────────────────────────────────────────────────────


class TestFields:
    @pytest.fixture(autouse=True)
    def setup_content_type(self, request):
        payload = {
            "name": isolated_name("post", request.node.name),
            "displayName": "Post",
        }
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            self.ct_id = resp.json()["data"]["id"]
        else:
            # Already exists, find it
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == payload["name"]:
                    self.ct_id = ct["id"]
                    break

    def test_add_text_field(self):
        payload = {"name": "title", "type": "text", "required": True, "unique": True}
        resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "title"
        assert data["type"] == "text"
        assert data["required"] is True
        assert data["unique"] is True

    def test_add_number_field(self):
        payload = {"name": "views", "type": "number", "default": 0}
        resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["type"] == "number"

    def test_add_enum_field(self):
        payload = {
            "name": "status",
            "type": "enum",
            "enumValues": ["draft", "published", "archived"],
        }
        resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["enumValues"] == ["draft", "published", "archived"]

    def test_add_duplicate_field_returns_409(self):
        payload = {"name": "title", "type": "text"}
        resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        # Add once if needed, then submit the duplicate.
        if resp.status_code == 201:
            resp = requests.post(
                f"{BASE_URL}/content-types/{self.ct_id}/fields",
                json=payload,
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )
        assert resp.status_code == 409

    def test_add_field_missing_type_returns_400(self):
        payload = {"name": "nofield"}
        resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400

    def test_list_fields(self):
        resp = requests.get(
            f"{BASE_URL}/content-types/{self.ct_id}/fields", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_update_field(self):
        # Add a field
        payload = {"name": "body_field", "type": "text"}
        create_resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if create_resp.status_code == 201:
            field_id = create_resp.json()["data"]["id"]
        else:
            # Find it
            list_resp = requests.get(
                f"{BASE_URL}/content-types/{self.ct_id}/fields", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            field_id = None
            for f in list_resp.json()["data"]:
                if f["name"] == "body_field":
                    field_id = f["id"]
                    break
            assert field_id is not None

        update_payload = {"required": True}
        resp = requests.put(
            f"{BASE_URL}/content-types/{self.ct_id}/fields/{field_id}",
            json=update_payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["required"] is True

    def test_delete_field(self):
        payload = {"name": "temp_field", "type": "boolean"}
        create_resp = requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        field_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/content-types/{self.ct_id}/fields/{field_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204


# ─── Dynamic Entries CRUD ────────────────────────────────────────────────────


class TestEntries:
    @pytest.fixture(autouse=True)
    def setup_article_type(self, request):
        """Create 'blog' content type with fields for testing entries."""
        self.content_type = isolated_name("blog", request.node.name)
        payload = {
            "name": self.content_type,
            "displayName": "Blog",
            "settings": {"localization": True},
        }
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            self.ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == self.content_type:
                    self.ct_id = ct["id"]
                    break

        # Add fields (ignore 409 if already exists)
        fields = [
            {"name": "title", "type": "text", "required": True, "unique": True},
            {"name": "body", "type": "text"},
            {"name": "views", "type": "number", "default": 0},
            {"name": "published", "type": "boolean", "default": False},
            {
                "name": "status",
                "type": "enum",
                "enumValues": ["draft", "published", "archived"],
            },
        ]
        for field in fields:
            requests.post(
                f"{BASE_URL}/content-types/{self.ct_id}/fields",
                json=field,
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )

    def test_create_entry(self):
        payload = {
            "title": "First Blog Post",
            "body": "Hello world",
            "views": 10,
            "published": True,
            "status": "published",
        }
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["title"] == "First Blog Post"
        assert data["views"] == 10
        assert data["id"] is not None
        assert "createdAt" in data
        assert "createdBy" in data

    def test_create_entry_missing_required_field_returns_400(self):
        payload = {"body": "No title"}
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400

    def test_create_entry_invalid_enum_returns_400(self):
        payload = {"title": "Enum Test", "status": "invalid_status"}
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400

    def test_create_entry_unique_violation_returns_409(self):
        payload = {"title": "Unique Title Test"}
        requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 409

    def test_list_entries(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert "pagination" in body["meta"]

    def test_get_entry(self):
        payload = {"title": "Get Test Entry"}
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "Get Test Entry"

    def test_get_nonexistent_entry_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}/99999",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 404

    def test_update_entry(self):
        payload = {"title": "Update Test Entry"}
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        update_payload = {"body": "Updated body", "views": 42}
        resp = requests.put(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            json=update_payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["body"] == "Updated body"
        assert resp.json()["data"]["views"] == 42

    def test_delete_entry(self):
        payload = {"title": "Delete Test Entry"}
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204

        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 404

    def test_nonexistent_content_type_returns_404(self):
        resp = requests.get(
            f"{BASE_URL}/content/nonexistent", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 404

    def test_default_values_applied(self):
        payload = {"title": "Default Values Test"}
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["views"] == 0
        assert data["published"] is False


# ─── Filtering, Sorting, Pagination ─────────────────────────────────────────


class TestFilteringSortingPagination:
    @pytest.fixture(autouse=True)
    def setup_data(self, request):
        """Create 'product' content type and some entries."""
        self.content_type = isolated_name("product", request.node.name)
        payload = {"name": self.content_type, "displayName": "Product"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201, resp.text
        ct_id = resp.json()["data"]["id"]

        # Add fields
        fields = [
            {"name": "name", "type": "text", "required": True},
            {"name": "price", "type": "number"},
            {"name": "category", "type": "text"},
        ]
        for field in fields:
            requests.post(
                f"{BASE_URL}/content-types/{ct_id}/fields",
                json=field,
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )

        # Create test products
        products = [
            {"name": "Apple", "price": 1, "category": "fruit"},
            {"name": "Banana", "price": 2, "category": "fruit"},
            {"name": "Carrot", "price": 3, "category": "vegetable"},
            {"name": "Date", "price": 5, "category": "fruit"},
            {"name": "Eggplant", "price": 4, "category": "vegetable"},
        ]
        for p in products:
            requests.post(
                f"{BASE_URL}/content/{self.content_type}",
                json=p,
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )

    def test_pagination_metadata(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}?page=1&pageSize=2",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        pagination = body["meta"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["pageSize"] == 2
        assert pagination["total"] >= 5
        assert pagination["pageCount"] >= 3

    def test_pagination_second_page(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}?page=2&pageSize=2",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_sort_ascending(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}?sort=price:asc&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        prices = [d["price"] for d in data if "price" in d]
        assert prices == sorted(prices)

    def test_sort_descending(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}?sort=price:desc&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        prices = [d["price"] for d in data if "price" in d]
        assert prices == sorted(prices, reverse=True)

    def test_filter_eq(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}"
            "?filters[category][eq]=fruit&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(d["category"] == "fruit" for d in data)
        assert len(data) >= 3

    def test_filter_gt(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}"
            "?filters[price][gt]=3&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(d["price"] > 3 for d in data)

    def test_filter_contains(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}"
            "?filters[name][contains]=an&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all("an" in d["name"].lower() for d in data)

    def test_filter_startsWith(self):
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}"
            "?filters[name][startsWith]=A&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(d["name"].startswith("A") for d in data)
        assert len(data) >= 1


# ─── Relations ───────────────────────────────────────────────────────────────


class TestRelations:
    @pytest.fixture(autouse=True)
    def setup_related_types(self, request):
        """Create 'author_profile' and 'book' content types with a relation."""
        self.test_name = request.node.name
        # Create author_profile type
        self.author_type = isolated_name("author_profile", self.test_name)
        payload = {"name": self.author_type, "displayName": "Author Profile"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            self.author_ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == self.author_type:
                    self.author_ct_id = ct["id"]
                    break

        # Add name field to author_profile
        requests.post(
            f"{BASE_URL}/content-types/{self.author_ct_id}/fields",
            json={"name": "name", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Create book type
        self.book_type = isolated_name("book", self.test_name)
        payload = {"name": self.book_type, "displayName": "Book"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            self.book_ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == self.book_type:
                    self.book_ct_id = ct["id"]
                    break

        # Add fields to book
        requests.post(
            f"{BASE_URL}/content-types/{self.book_ct_id}/fields",
            json={"name": "title", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        requests.post(
            f"{BASE_URL}/content-types/{self.book_ct_id}/fields",
            json={
                "name": "author",
                "type": "relation",
                "target": self.author_type,
                "relationType": "oneToOne",
            },
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

    def test_create_entry_with_relation(self):
        # Create an author
        author_resp = requests.post(
            f"{BASE_URL}/content/{self.author_type}",
            json={"name": "J.K. Rowling"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert author_resp.status_code == 201
        author_id = author_resp.json()["data"]["id"]

        # Create a book with relation to the author
        book_resp = requests.post(
            f"{BASE_URL}/content/{self.book_type}",
            json={"title": "Harry Potter", "author": author_id},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert book_resp.status_code == 201
        book_id = book_resp.json()["data"]["id"]

        # GET the book should populate the relation
        get_resp = requests.get(
            f"{BASE_URL}/content/{self.book_type}/{book_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert get_resp.status_code == 200
        data = get_resp.json()["data"]
        assert isinstance(data["author"], dict)
        assert data["author"]["name"] == "J.K. Rowling"
        assert data["author"]["id"] == author_id

    def test_one_to_many_relation(self):
        # Create a publisher content type
        publisher_type = isolated_name("publisher", self.test_name)
        payload = {"name": publisher_type, "displayName": "Publisher"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            pub_ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == publisher_type:
                    pub_ct_id = ct["id"]
                    break

        requests.post(
            f"{BASE_URL}/content-types/{pub_ct_id}/fields",
            json={"name": "name", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Create a magazine type with oneToMany relation to publisher
        magazine_type = isolated_name("magazine", self.test_name)
        payload = {"name": magazine_type, "displayName": "Magazine"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            mag_ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == magazine_type:
                    mag_ct_id = ct["id"]
                    break

        requests.post(
            f"{BASE_URL}/content-types/{mag_ct_id}/fields",
            json={"name": "title", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        requests.post(
            f"{BASE_URL}/content-types/{mag_ct_id}/fields",
            json={
                "name": "publishers",
                "type": "relation",
                "target": publisher_type,
                "relationType": "oneToMany",
            },
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Create publishers
        pub1 = requests.post(
            f"{BASE_URL}/content/{publisher_type}",
            json={"name": "Pub A"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()["data"]["id"]
        pub2 = requests.post(
            f"{BASE_URL}/content/{publisher_type}",
            json={"name": "Pub B"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        ).json()["data"]["id"]

        # Create magazine with multiple publishers
        mag_resp = requests.post(
            f"{BASE_URL}/content/{magazine_type}",
            json={"title": "Tech Weekly", "publishers": [pub1, pub2]},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert mag_resp.status_code == 201
        mag_id = mag_resp.json()["data"]["id"]

        # GET should have populated publishers
        get_resp = requests.get(
            f"{BASE_URL}/content/{magazine_type}/{mag_id}",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        data = get_resp.json()["data"]
        assert isinstance(data["publishers"], list)
        assert len(data["publishers"]) == 2
        assert data["publishers"][0]["name"] in ["Pub A", "Pub B"]


# ─── Components ──────────────────────────────────────────────────────────────


class TestComponents:
    def test_create_component(self):
        payload = {
            "name": "seo",
            "displayName": "SEO",
            "description": "SEO metadata",
            "fields": [
                {"name": "metaTitle", "type": "text", "required": True},
                {"name": "metaDescription", "type": "text"},
            ],
        }
        resp = requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "seo"
        assert len(data["fields"]) == 2

    def test_create_duplicate_component_returns_409(self):
        payload = {
            "name": "duplicate_component_conflict_probe",
            "displayName": "SEO Dup",
        }
        requests.post(
            f"{BASE_URL}/components",
            json=payload,
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        resp = requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 409

    def test_list_components(self):
        resp = requests.get(f"{BASE_URL}/components", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_component(self):
        # Create a component
        payload = {
            "name": "address",
            "displayName": "Address",
            "fields": [
                {"name": "street", "type": "text"},
                {"name": "city", "type": "text"},
            ],
        }
        create_resp = requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if create_resp.status_code == 201:
            comp_id = create_resp.json()["data"]["id"]
        else:
            list_resp = requests.get(f"{BASE_URL}/components", headers=headers(), timeout=REQUEST_TIMEOUT)
            for c in list_resp.json()["data"]:
                if c["name"] == "address":
                    comp_id = c["id"]
                    break

        resp = requests.get(f"{BASE_URL}/components/{comp_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "address"

    def test_use_component_in_content_type(self):
        """Create a content type with a component field and verify data is nested."""
        # Ensure seo component exists
        payload = {
            "name": "seo_comp",
            "displayName": "SEO Comp",
            "fields": [
                {"name": "metaTitle", "type": "text"},
                {"name": "metaDescription", "type": "text"},
            ],
        }
        requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Create a page content type
        ct_payload = {"name": "page", "displayName": "Page"}
        ct_resp = requests.post(
            f"{BASE_URL}/content-types", json=ct_payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if ct_resp.status_code == 201:
            ct_id = ct_resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == "page":
                    ct_id = ct["id"]
                    break

        # Add fields
        requests.post(
            f"{BASE_URL}/content-types/{ct_id}/fields",
            json={"name": "title", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        requests.post(
            f"{BASE_URL}/content-types/{ct_id}/fields",
            json={"name": "seo", "type": "component", "component": "seo_comp"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Create an entry with component data
        entry_payload = {
            "title": "Homepage",
            "seo": {"metaTitle": "Home", "metaDescription": "Welcome to our site"},
        }
        entry_resp = requests.post(
            f"{BASE_URL}/content/page", json=entry_payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert entry_resp.status_code == 201
        entry_id = entry_resp.json()["data"]["id"]

        # GET the entry and verify component data is nested
        get_resp = requests.get(
            f"{BASE_URL}/content/page/{entry_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        data = get_resp.json()["data"]
        assert isinstance(data["seo"], dict)
        assert data["seo"]["metaTitle"] == "Home"
        assert data["seo"]["metaDescription"] == "Welcome to our site"

    def test_add_field_to_component(self):
        # Create component
        payload = {
            "name": "social",
            "displayName": "Social",
            "fields": [{"name": "twitter", "type": "text"}],
        }
        resp = requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            comp_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(f"{BASE_URL}/components", headers=headers(), timeout=REQUEST_TIMEOUT)
            for c in list_resp.json()["data"]:
                if c["name"] == "social":
                    comp_id = c["id"]
                    break

        # Add a field
        field_resp = requests.post(
            f"{BASE_URL}/components/{comp_id}/fields",
            json={"name": "facebook", "type": "text"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert field_resp.status_code == 201

    def test_delete_component(self):
        payload = {"name": "temp_comp", "displayName": "Temp"}
        create_resp = requests.post(
            f"{BASE_URL}/components", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        comp_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/components/{comp_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204


# ─── Localization ────────────────────────────────────────────────────────────


class TestLocalization:
    @pytest.fixture(autouse=True)
    def setup_localized_type(self, request):
        """Create a localized content type."""
        self.content_type = isolated_name("news", request.node.name)
        payload = {
            "name": self.content_type,
            "displayName": "News",
            "settings": {"localization": True},
        }
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            self.ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == self.content_type:
                    self.ct_id = ct["id"]
                    break

        requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json={"name": "headline", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        requests.post(
            f"{BASE_URL}/content-types/{self.ct_id}/fields",
            json={"name": "content", "type": "text"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Ensure French locale exists
        requests.post(
            f"{BASE_URL}/locales",
            json={"code": "fr", "name": "French"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

    def test_create_locale(self):
        resp = requests.post(
            f"{BASE_URL}/locales",
            json={"code": "de", "name": "German"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code in [201, 409]  # 409 if already exists

    def test_list_locales(self):
        resp = requests.get(f"{BASE_URL}/locales", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_create_localized_entry(self):
        # Create entry in default locale
        entry_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"headline": "Breaking News", "content": "Something happened"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert entry_resp.status_code == 201
        entry_id = entry_resp.json()["data"]["id"]
        assert entry_resp.json()["data"]["locale"] == "en"

        # Create French localization
        loc_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}/localizations",
            json={
                "locale": "fr",
                "headline": "Nouvelles",
                "content": "Quelque chose",
            },
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert loc_resp.status_code == 201
        assert loc_resp.json()["data"]["locale"] == "fr"
        assert loc_resp.json()["data"]["headline"] == "Nouvelles"

    def test_filter_entries_by_locale(self):
        # Create entries in different locales
        entry_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"headline": "English News for Locale"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if entry_resp.status_code == 201:
            entry_id = entry_resp.json()["data"]["id"]
            requests.post(
                f"{BASE_URL}/content/{self.content_type}/{entry_id}/localizations",
                json={"locale": "fr", "headline": "Actualites pour Locale"},
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )

        # Query French locale
        resp = requests.get(
            f"{BASE_URL}/content/{self.content_type}?locale=fr&pageSize=100",
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert all(d["locale"] == "fr" for d in data)

    def test_duplicate_locale_on_entry_returns_400(self):
        entry_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"headline": "Dup Locale Test"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = entry_resp.json()["data"]["id"]

        # Create French version
        requests.post(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}/localizations",
            json={"locale": "fr", "headline": "FR Version"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        # Try to create another French version → 400
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}/localizations",
            json={"locale": "fr", "headline": "FR Version Again"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400


# ─── Role-Based Access Control ───────────────────────────────────────────────


class TestRBAC:
    @pytest.fixture(autouse=True)
    def setup_rbac_type(self, request):
        """Create content type for RBAC testing."""
        self.content_type = isolated_name("note", request.node.name)
        payload = {"name": self.content_type, "displayName": "Note"}
        resp = requests.post(
            f"{BASE_URL}/content-types", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            ct_id = resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == self.content_type:
                    ct_id = ct["id"]
                    break
            else:
                ct_id = None

        if ct_id:
            requests.post(
                f"{BASE_URL}/content-types/{ct_id}/fields",
                json={"name": "text", "type": "text", "required": True},
                headers=json_headers(),
                timeout=REQUEST_TIMEOUT,
            )

    def test_editor_cannot_create_content_type(self):
        payload = {"name": "editor_type", "displayName": "Editor Type"}
        resp = requests.post(
            f"{BASE_URL}/content-types",
            json=payload,
            headers=json_headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_author_cannot_create_content_type(self):
        payload = {"name": "author_type", "displayName": "Author Type"}
        resp = requests.post(
            f"{BASE_URL}/content-types",
            json=payload,
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_editor_can_create_entry(self):
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "Editor note"},
            headers=json_headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201

    def test_author_can_create_entry(self):
        resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "Author note"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201

    def test_author_cannot_update_others_entry(self):
        # Author 1 creates an entry
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "Author1 private note"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        # Author 2 tries to update it
        resp = requests.put(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            json={"text": "Hacked"},
            headers=json_headers(AUTHOR_TOKEN_2),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_author_cannot_delete_others_entry(self):
        # Author 1 creates an entry
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "Author1 another note"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        # Author 2 tries to delete it
        resp = requests.delete(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            headers=json_headers(AUTHOR_TOKEN_2),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_author_can_update_own_entry(self):
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "My own note"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        resp = requests.put(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            json={"text": "Updated my own note"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_editor_can_update_any_entry(self):
        # Author creates entry
        create_resp = requests.post(
            f"{BASE_URL}/content/{self.content_type}",
            json={"text": "Author note for editor"},
            headers=json_headers(AUTHOR_TOKEN_1),
            timeout=REQUEST_TIMEOUT,
        )
        entry_id = create_resp.json()["data"]["id"]

        # Editor updates it
        resp = requests.put(
            f"{BASE_URL}/content/{self.content_type}/{entry_id}",
            json={"text": "Edited by editor"},
            headers=json_headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200

    def test_editor_cannot_delete_content_type(self):
        # Get a content type
        list_resp = requests.get(
            f"{BASE_URL}/content-types", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if list_resp.json()["data"]:
            ct_id = list_resp.json()["data"][0]["id"]
            resp = requests.delete(
                f"{BASE_URL}/content-types/{ct_id}",
                headers=headers(EDITOR_TOKEN),
                timeout=REQUEST_TIMEOUT,
            )
            assert resp.status_code == 403


# ─── Media ───────────────────────────────────────────────────────────────────


class TestMedia:
    def test_upload_media(self):
        files = {"file": ("test.txt", b"Hello World", "text/plain")}
        resp = requests.post(
            f"{BASE_URL}/media",
            files=files,
            headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "test.txt"
        assert data["mimeType"] == "text/plain"
        assert data["size"] > 0
        assert data["id"] is not None

    def test_list_media(self):
        resp = requests.get(f"{BASE_URL}/media", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_media(self):
        files = {"file": ("get_test.png", b"\x89PNG\r\n", "image/png")}
        create_resp = requests.post(
            f"{BASE_URL}/media", files=files, headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        media_id = create_resp.json()["data"]["id"]

        resp = requests.get(f"{BASE_URL}/media/{media_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "get_test.png"

    def test_delete_media(self):
        files = {"file": ("del_test.txt", b"delete me", "text/plain")}
        create_resp = requests.post(
            f"{BASE_URL}/media", files=files, headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        media_id = create_resp.json()["data"]["id"]

        resp = requests.delete(f"{BASE_URL}/media/{media_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204

        resp = requests.get(f"{BASE_URL}/media/{media_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 404

    def test_create_media_folder(self):
        resp = requests.post(
            f"{BASE_URL}/media/folders",
            json={"name": "images"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code in [201, 409]

    def test_list_media_folders(self):
        resp = requests.get(f"{BASE_URL}/media/folders", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_upload_to_folder(self):
        # Ensure folder exists
        requests.post(
            f"{BASE_URL}/media/folders",
            json={"name": "documents"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        files = {"file": ("doc.pdf", b"%PDF", "application/pdf")}
        data = {"folder": "documents"}
        resp = requests.post(
            f"{BASE_URL}/media", files=files, data=data, headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["folder"] == "documents"

    def test_media_attachment_to_entry(self):
        """Upload a media file and attach it to an entry via a media field."""
        # Create content type with media field
        ct_payload = {"name": "gallery", "displayName": "Gallery"}
        ct_resp = requests.post(
            f"{BASE_URL}/content-types", json=ct_payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if ct_resp.status_code == 201:
            ct_id = ct_resp.json()["data"]["id"]
        else:
            list_resp = requests.get(
                f"{BASE_URL}/content-types", headers=headers(),
                timeout=REQUEST_TIMEOUT,
            )
            for ct in list_resp.json()["data"]:
                if ct["name"] == "gallery":
                    ct_id = ct["id"]
                    break

        requests.post(
            f"{BASE_URL}/content-types/{ct_id}/fields",
            json={"name": "caption", "type": "text", "required": True},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        requests.post(
            f"{BASE_URL}/content-types/{ct_id}/fields",
            json={"name": "image", "type": "media"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        # Upload media
        files = {"file": ("photo.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")}
        media_resp = requests.post(
            f"{BASE_URL}/media", files=files, headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        media_id = media_resp.json()["data"]["id"]

        # Create entry with media attachment
        entry_resp = requests.post(
            f"{BASE_URL}/content/gallery",
            json={"caption": "Beautiful sunset", "image": media_id},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert entry_resp.status_code == 201
        entry_id = entry_resp.json()["data"]["id"]

        # Get entry - media should be populated
        get_resp = requests.get(
            f"{BASE_URL}/content/gallery/{entry_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        data = get_resp.json()["data"]
        assert isinstance(data["image"], dict)
        assert data["image"]["id"] == media_id
        assert data["image"]["name"] == "photo.jpg"


# ─── Webhooks ────────────────────────────────────────────────────────────────


class TestWebhooks:
    def test_create_webhook(self):
        payload = {
            "name": "Entry Created Hook",
            "url": "https://example.com/hook",
            "events": ["entry.create", "entry.update"],
            "enabled": True,
            "contentTypes": ["blog"],
        }
        resp = requests.post(
            f"{BASE_URL}/webhooks", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Entry Created Hook"
        assert data["url"] == "https://example.com/hook"
        assert "entry.create" in data["events"]
        assert data["enabled"] is True

    def test_list_webhooks(self):
        resp = requests.get(f"{BASE_URL}/webhooks", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_webhook(self):
        payload = {
            "name": "Get Hook",
            "url": "https://example.com/get-hook",
            "events": ["entry.delete"],
        }
        create_resp = requests.post(
            f"{BASE_URL}/webhooks", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        hook_id = create_resp.json()["data"]["id"]

        resp = requests.get(f"{BASE_URL}/webhooks/{hook_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Get Hook"

    def test_update_webhook(self):
        payload = {
            "name": "Update Hook",
            "url": "https://example.com/update",
            "events": ["entry.create"],
        }
        create_resp = requests.post(
            f"{BASE_URL}/webhooks", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        hook_id = create_resp.json()["data"]["id"]

        resp = requests.put(
            f"{BASE_URL}/webhooks/{hook_id}",
            json={"enabled": False, "name": "Updated Hook"},
            headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["enabled"] is False
        assert resp.json()["data"]["name"] == "Updated Hook"

    def test_delete_webhook(self):
        payload = {
            "name": "Delete Hook",
            "url": "https://example.com/del",
            "events": ["entry.create"],
        }
        create_resp = requests.post(
            f"{BASE_URL}/webhooks", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        hook_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/webhooks/{hook_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204

    def test_webhook_missing_url_returns_400(self):
        payload = {"name": "Bad Hook", "events": ["entry.create"]}
        resp = requests.post(
            f"{BASE_URL}/webhooks", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 400

    def test_editor_cannot_manage_webhooks(self):
        payload = {
            "name": "Editor Hook",
            "url": "https://example.com/editor",
            "events": ["entry.create"],
        }
        resp = requests.post(
            f"{BASE_URL}/webhooks",
            json=payload,
            headers=json_headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403


# ─── Users & API Tokens ─────────────────────────────────────────────────────


class TestUsersAndTokens:
    def test_create_user(self):
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "role": "editor",
        }
        resp = requests.post(
            f"{BASE_URL}/users", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code in [201, 409]
        if resp.status_code == 201:
            data = resp.json()["data"]
            assert data["username"] == "testuser"
            assert data["role"] == "editor"

    def test_list_users(self):
        resp = requests.get(f"{BASE_URL}/users", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_get_user(self):
        payload = {
            "username": "getuser",
            "email": "getuser@example.com",
            "role": "author",
        }
        create_resp = requests.post(
            f"{BASE_URL}/users", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if create_resp.status_code == 201:
            user_id = create_resp.json()["data"]["id"]
        else:
            list_resp = requests.get(f"{BASE_URL}/users", headers=headers(), timeout=REQUEST_TIMEOUT)
            for u in list_resp.json()["data"]:
                if u["username"] == "getuser":
                    user_id = u["id"]
                    break

        resp = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200

    def test_editor_cannot_manage_users(self):
        resp = requests.get(
            f"{BASE_URL}/users", headers=headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_create_api_token(self):
        payload = {"name": "Read Token", "type": "read-only"}
        resp = requests.post(
            f"{BASE_URL}/api-tokens", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Read Token"
        assert data["type"] == "read-only"
        assert "token" in data

    def test_list_api_tokens(self):
        resp = requests.get(f"{BASE_URL}/api-tokens", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_delete_api_token(self):
        payload = {"name": "Delete Token", "type": "full-access"}
        create_resp = requests.post(
            f"{BASE_URL}/api-tokens", json=payload, headers=json_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        token_id = create_resp.json()["data"]["id"]

        resp = requests.delete(
            f"{BASE_URL}/api-tokens/{token_id}", headers=headers(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 204

    def test_editor_cannot_manage_tokens(self):
        resp = requests.get(
            f"{BASE_URL}/api-tokens", headers=headers(EDITOR_TOKEN),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 403

    def test_list_roles(self):
        resp = requests.get(f"{BASE_URL}/roles", headers=headers(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        role_names = [r["name"] for r in data]
        assert "admin" in role_names
        assert "editor" in role_names
        assert "author" in role_names
