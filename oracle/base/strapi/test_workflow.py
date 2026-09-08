"""
L3 Workflow Tests for Strapi Headless CMS API.
Multi-step adversarial tests targeting complex interactions:
- Content type lifecycle with fields, entries, relations
- Role-based access across full workflows
- Localization roundtrips
- Component embedding in entries
- Cascade deletion effects
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
# L3 TESTS — Workflow
# =============================================================================


class TestContentTypeLifecycle:
    """Full lifecycle: create type -> add fields -> create entries -> query -> delete."""

    def test_full_content_type_lifecycle(self):
        """
        Pattern 2+3+7: Create type, add fields, create entries,
        filter/sort them, then delete type and verify cascade.
        """
        # 1. Create content type
        ct_name = unique_name()
        ct = create_content_type(name=ct_name, display_name="Blog Post")
        ct_id = ct["id"]
        assert ct["name"] == ct_name
        assert ct["displayName"] == "Blog Post"

        # 2. Add fields
        title_field = add_field(ct_id, "title", "text", required=True)
        add_field(ct_id, "views", "number")
        add_field(ct_id, "published", "boolean")

        # 3. Verify fields in content type
        resp = requests.get(f"{BASE_URL}/content-types/{ct_id}", headers=h(), timeout=REQUEST_TIMEOUT)
        fields = resp.json()["data"]["fields"]
        field_names = [f["name"] for f in fields]
        assert "title" in field_names
        assert "views" in field_names
        assert "published" in field_names

        # 4. Create entries
        e1 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"title": "First Post", "views": 100, "published": True},
                           headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        e2 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"title": "Second Post", "views": 50, "published": False},
                           headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        e3 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"title": "Third Post", "views": 200, "published": True},
                           headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]

        # 5. Sort by views descending
        resp = requests.get(f"{BASE_URL}/content/{ct_name}",
                            params={"sort": "views:desc"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        views_list = [e["views"] for e in entries]
        assert views_list == sorted(views_list, reverse=True)

        # 6. Filter published only
        resp = requests.get(f"{BASE_URL}/content/{ct_name}",
                            params={"filters[published][eq]": "True"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        assert len(entries) == 2
        for e in entries:
            assert e["published"] is True

        # 7. Delete content type
        resp = requests.delete(f"{BASE_URL}/content-types/{ct_id}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204

        # 8. Entries should be gone (content type doesn't exist)
        resp = requests.get(f"{BASE_URL}/content/{ct_name}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 404


class TestRelationsWorkflow:
    """Relations between content types with population."""

    def test_one_to_many_relation_populated(self):
        """
        Pattern 2+5: Create category -> articles with relation ->
        verify population returns full objects.
        """
        # 1. Create category content type
        cat_name = unique_name()
        cat_ct = create_content_type(name=cat_name)
        add_field(cat_ct["id"], "label", "text")

        # 2. Create article content type with relation
        art_name = unique_name()
        art_ct = create_content_type(name=art_name)
        add_field(art_ct["id"], "headline", "text")
        add_field(art_ct["id"], "categories", "relation",
                  target=cat_name, relationType="oneToMany")

        # 3. Create categories
        c1 = requests.post(f"{BASE_URL}/content/{cat_name}",
                           json={"label": "Tech"}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        c2 = requests.post(f"{BASE_URL}/content/{cat_name}",
                           json={"label": "Science"}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]

        # 4. Create article referencing both categories
        art = requests.post(f"{BASE_URL}/content/{art_name}", json={
            "headline": "AI Breakthrough",
            "categories": [c1["id"], c2["id"]]
        }, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]

        # 5. GET article - relations should be populated
        resp = requests.get(f"{BASE_URL}/content/{art_name}/{art['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        article = resp.json()["data"]
        assert article["headline"] == "AI Breakthrough"
        assert isinstance(article["categories"], list)
        assert len(article["categories"]) == 2
        labels = [c["label"] for c in article["categories"]]
        assert "Tech" in labels
        assert "Science" in labels


class TestLocalizationWorkflow:
    """Localization with locale filtering."""

    def test_create_localized_entries_and_filter(self):
        """
        Pattern 3+5: Create localized content type, add entries in different locales,
        filter by locale parameter.
        """
        # 1. Create content type with localization enabled
        ct_name = unique_name()
        ct = create_content_type(name=ct_name,
                                 settings={"localization": True, "draftAndPublish": False})
        add_field(ct["id"], "title", "text")
        add_field(ct["id"], "body", "text")

        # 2. Create English entry
        en_entry = requests.post(f"{BASE_URL}/content/{ct_name}", json={
            "title": "Hello World", "body": "English content"
        }, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        assert en_entry["locale"] == "en"

        # 3. Create French localization
        resp = requests.post(
            f"{BASE_URL}/content/{ct_name}/{en_entry['id']}/localizations",
            json={"locale": "fr", "title": "Bonjour le Monde", "body": "Contenu francais"},
            headers=h(),
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201
        fr_entry = resp.json()["data"]
        assert fr_entry["locale"] == "fr"
        assert fr_entry["title"] == "Bonjour le Monde"

        # 4. Filter by locale=fr
        resp = requests.get(f"{BASE_URL}/content/{ct_name}",
                            params={"locale": "fr"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        assert len(entries) >= 1
        assert all(e["locale"] == "fr" for e in entries)

        # 5. Filter by locale=en
        resp = requests.get(f"{BASE_URL}/content/{ct_name}",
                            params={"locale": "en"}, headers=h(), timeout=REQUEST_TIMEOUT)
        entries = resp.json()["data"]
        assert len(entries) >= 1
        assert all(e["locale"] == "en" for e in entries)


class TestAuthorIsolationWorkflow:
    """Author can only manage own entries."""

    def test_author_crud_isolation(self):
        """
        Pattern 6: Author 1 creates entries, Author 2 cannot modify them.
        Editor can modify any.
        """
        # 1. Admin creates content type and field
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "note", "text")

        # 2. Author 1 creates entry
        e1 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"note": "Author 1's note"},
                           headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT).json()["data"]
        assert e1["createdBy"] == "3"

        # 3. Author 2 creates entry
        e2 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"note": "Author 2's note"},
                           headers=h(AUTHOR_TOKEN_2), timeout=REQUEST_TIMEOUT).json()["data"]
        assert e2["createdBy"] == "4"

        # 4. Author 1 cannot update Author 2's entry
        resp = requests.put(f"{BASE_URL}/content/{ct_name}/{e2['id']}",
                            json={"note": "Hacked"}, headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 403

        # 5. Author 2 cannot delete Author 1's entry
        resp = requests.delete(f"{BASE_URL}/content/{ct_name}/{e1['id']}",
                               headers=h(AUTHOR_TOKEN_2), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 403

        # 6. Editor can update Author 1's entry
        resp = requests.put(f"{BASE_URL}/content/{ct_name}/{e1['id']}",
                            json={"note": "Edited by editor"}, headers=h(EDITOR_TOKEN), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["data"]["note"] == "Edited by editor"

        # 7. Author 1 can still update own entry
        resp = requests.put(f"{BASE_URL}/content/{ct_name}/{e1['id']}",
                            json={"note": "Back to mine"}, headers=h(AUTHOR_TOKEN_1), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200


class TestComponentWorkflow:
    """Components embedded in content types."""

    def test_component_crud_in_entries(self):
        """
        Pattern 2+5: Create component, use it in content type,
        verify data roundtrips correctly.
        """
        # 1. Create component
        comp_name = unique_name()
        resp = requests.post(f"{BASE_URL}/components", json={
            "name": comp_name,
            "displayName": "Address",
            "fields": [
                {"name": "street", "type": "text"},
                {"name": "city", "type": "text"},
                {"name": "zip", "type": "text"}
            ]
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        comp = resp.json()["data"]
        assert comp["name"] == comp_name
        assert len(comp["fields"]) == 3

        # 2. Create content type with component field
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "name", "text")
        add_field(ct["id"], "address", "component", component=comp_name)

        # 3. Create entry with component data
        resp = requests.post(f"{BASE_URL}/content/{ct_name}", json={
            "name": "Office",
            "address": {"street": "123 Main St", "city": "Springfield", "zip": "62701"}
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        entry = resp.json()["data"]
        assert entry["address"]["street"] == "123 Main St"
        assert entry["address"]["city"] == "Springfield"
        assert entry["address"]["zip"] == "62701"

        # 4. Update component data
        resp = requests.put(f"{BASE_URL}/content/{ct_name}/{entry['id']}", json={
            "address": {"street": "456 Oak Ave", "city": "Shelbyville", "zip": "62702"}
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        updated = resp.json()["data"]
        assert updated["address"]["street"] == "456 Oak Ave"
        assert updated["address"]["city"] == "Shelbyville"


class TestMediaWorkflow:
    """Media upload and attachment to entries."""

    def test_media_upload_and_use_in_entry(self):
        """
        Pattern 2+4: Upload media, attach to entry via media field,
        verify it's returned.
        """
        # 1. Upload a file
        resp = requests.post(f"{BASE_URL}/media",
                             files={"file": ("photo.png", b"PNG data", "image/png")},
                             headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        media = resp.json()["data"]
        assert "id" in media
        assert media["name"] == "photo.png"
        assert "url" in media
        assert "mimeType" in media

        # 2. Create content type with media field
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "title", "text")
        add_field(ct["id"], "cover", "media")

        # 3. Create entry with media reference
        resp = requests.post(f"{BASE_URL}/content/{ct_name}", json={
            "title": "With Image",
            "cover": media["id"]
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        entry = resp.json()["data"]

        # 4. GET entry - media should be populated
        resp = requests.get(f"{BASE_URL}/content/{ct_name}/{entry['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        data = resp.json()["data"]
        assert data["title"] == "With Image"
        assert isinstance(data["cover"], dict)
        assert data["cover"]["id"] == media["id"]
        assert data["cover"]["name"] == "photo.png"


class TestWebhookWorkflow:
    """Webhook registration."""

    def test_webhook_crud(self):
        """Pattern 1+4: Create, list, delete webhooks with correct fields."""
        # 1. Create webhook
        resp = requests.post(f"{BASE_URL}/webhooks", json={
            "name": "Deploy Hook",
            "url": "https://hooks.example.com/deploy",
            "events": ["entry.create", "entry.update"],
            "enabled": True
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 201
        wh = resp.json()["data"]
        assert wh["name"] == "Deploy Hook"
        assert wh["url"] == "https://hooks.example.com/deploy"
        assert set(wh["events"]) == {"entry.create", "entry.update"}
        assert wh["enabled"] is True
        assert "id" in wh
        assert "createdAt" in wh

        # 2. List webhooks
        resp = requests.get(f"{BASE_URL}/webhooks", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        webhooks = resp.json()["data"]
        assert any(w["id"] == wh["id"] for w in webhooks)

        # 3. Delete webhook
        resp = requests.delete(f"{BASE_URL}/webhooks/{wh['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204


class TestFieldManagement:
    """Field add/update/delete with impact on entries."""

    def test_add_field_and_use_in_entry(self):
        """
        Pattern 5+8: Add fields progressively, existing entries
        should still work, new entries can use new fields.
        """
        # 1. Create content type with one field
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "name", "text")

        # 2. Create entry with just name
        e1 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"name": "First"}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        assert e1["name"] == "First"

        # 3. Add another field
        add_field(ct["id"], "age", "number")

        # 4. Create entry with both fields
        e2 = requests.post(f"{BASE_URL}/content/{ct_name}",
                           json={"name": "Second", "age": 25}, headers=h(), timeout=REQUEST_TIMEOUT).json()["data"]
        assert e2["name"] == "Second"
        assert e2["age"] == 25

        # 5. First entry should still be retrievable
        resp = requests.get(f"{BASE_URL}/content/{ct_name}/{e1['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200

        # 6. Delete the age field
        fields_resp = requests.get(f"{BASE_URL}/content-types/{ct['id']}/fields", headers=h(), timeout=REQUEST_TIMEOUT)
        age_field = next(f for f in fields_resp.json()["data"] if f["name"] == "age")
        resp = requests.delete(
            f"{BASE_URL}/content-types/{ct['id']}/fields/{age_field['id']}", headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 204


class TestFilteringSortingCombined:
    """Complex queries combining filters, sorting, and pagination."""

    def test_combined_filter_sort_paginate(self):
        """
        Pattern 3+5: Apply filter + sort + pagination simultaneously.
        """
        ct_name = unique_name()
        ct = create_content_type(name=ct_name)
        add_field(ct["id"], "category", "text")
        add_field(ct["id"], "score", "number")

        # Create entries
        entries_data = [
            {"category": "A", "score": 10},
            {"category": "A", "score": 30},
            {"category": "B", "score": 20},
            {"category": "A", "score": 50},
            {"category": "B", "score": 40},
            {"category": "A", "score": 70},
        ]
        for ed in entries_data:
            requests.post(f"{BASE_URL}/content/{ct_name}", json=ed, headers=h(), timeout=REQUEST_TIMEOUT)

        # Filter category=A, sort by score desc, page 1 size 2
        resp = requests.get(f"{BASE_URL}/content/{ct_name}", params={
            "filters[category][eq]": "A",
            "sort": "score:desc",
            "page": 1,
            "pageSize": 2
        }, headers=h(), timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        entries = body["data"]
        meta = body["meta"]["pagination"]

        # Should be 4 total A entries, page 1 has 2
        assert meta["total"] == 4
        assert meta["pageSize"] == 2
        assert meta["page"] == 1
        assert len(entries) == 2
        # First should be highest score (70)
        assert entries[0]["score"] == 70
        assert entries[1]["score"] == 50
        # All should be category A
        for e in entries:
            assert e["category"] == "A"
