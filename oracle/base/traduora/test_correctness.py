"""
BackendForge — Comprehensive Correctness Tests for Traduora Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# User keys — auto-created on first request
USER_KEY = f"user-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"user2-{uuid.uuid4().hex[:8]}"
USER3_KEY = f"user3-{uuid.uuid4().hex[:8]}"

USER_HEADERS = {
    "X-Api-Key": USER_KEY,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
    "X-Api-Key": USER2_KEY,
    "Content-Type": "application/json",
}

USER3_HEADERS = {
    "X-Api-Key": USER3_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolate_test_users():
    global USER_KEY, USER2_KEY, USER3_KEY, UNIQUE

    USER_KEY = f"user-{uuid.uuid4().hex}"
    USER2_KEY = f"user2-{uuid.uuid4().hex}"
    USER3_KEY = f"user3-{uuid.uuid4().hex}"
    USER_HEADERS["X-Api-Key"] = USER_KEY
    USER2_HEADERS["X-Api-Key"] = USER2_KEY
    USER3_HEADERS["X-Api-Key"] = USER3_KEY
    UNIQUE = uuid.uuid4().hex


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or USER_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or USER_HEADERS, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers or USER_HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or USER_HEADERS, timeout=30)


def create_project(name=None, headers=None):
    """Helper to create a project and return its data."""
    name = name or f"Project-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/v1/projects", {"name": name, "description": "Test project"}, headers=headers)
    assert resp.status_code == 201, f"Failed to create project: {resp.status_code} {resp.text}"
    return resp.json()["data"]


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401_on_get(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/v1/projects", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_returns_401_on_post(self):
        resp = requests.post(f"{BASE_URL}/api/v1/projects", json={"name": "test"}, timeout=30)
        assert resp.status_code == 401

    def test_empty_header_returns_401(self):
        """Empty X-Api-Key should return 401."""
        resp = requests.get(
            f"{BASE_URL}/api/v1/projects",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_valid_key_auto_creates_user(self):
        """Any non-empty API key should work and auto-create a user."""
        new_key = f"new-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": new_key, "Content-Type": "application/json"}
        resp = api_get("/api/v1/projects", headers=headers)
        assert resp.status_code == 200
        assert "data" in resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 2: Project CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjectCRUD:

    def test_create_project_returns_201(self):
        """POST /projects should return 201 (not 200)."""
        resp = api_post("/api/v1/projects", {"name": f"MyProject-{UNIQUE}", "description": "A test project"})
        assert resp.status_code == 201
        project = resp.json()["data"]
        assert project["name"] == f"MyProject-{UNIQUE}"
        assert project["description"] == "A test project"
        assert "id" in project
        assert "createdAt" in project
        assert "updatedAt" in project

    def test_create_project_minimal(self):
        """Creating a project with only name should default description to empty."""
        resp = api_post("/api/v1/projects", {"name": f"MinProject-{UNIQUE}"})
        assert resp.status_code == 201
        project = resp.json()["data"]
        assert project["name"] == f"MinProject-{UNIQUE}"
        assert project["description"] == ""

    def test_create_project_missing_name_returns_400(self):
        resp = api_post("/api/v1/projects", {"description": "no name"})
        assert resp.status_code == 400

    def test_list_projects_returns_data_wrapper(self):
        """Response must be wrapped in {"data": [...]}."""
        create_project(f"ListProject-{UNIQUE}")
        resp = api_get("/api/v1/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        projects = body["data"]
        assert isinstance(projects, list)
        names = [p["name"] for p in projects]
        assert f"ListProject-{UNIQUE}" in names

    def test_get_project(self):
        project = create_project(f"GetProject-{UNIQUE}")
        project_id = project["id"]

        resp = api_get(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == f"GetProject-{UNIQUE}"
        assert data["id"] == project_id

    def test_get_nonexistent_project_returns_404(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/projects/{fake_id}")
        assert resp.status_code == 404

    def test_update_project(self):
        project = create_project(f"UpdateProject-{UNIQUE}")
        project_id = project["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}", {
            "name": f"UpdatedProject-{UNIQUE}",
            "description": "Updated desc",
        })
        assert resp.status_code == 200
        updated = resp.json()["data"]
        assert updated["name"] == f"UpdatedProject-{UNIQUE}"
        assert updated["description"] == "Updated desc"

    def test_delete_project_returns_204(self):
        """DELETE should return 204 (not 200)."""
        project = create_project(f"DelProject-{UNIQUE}")
        project_id = project["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 204

        # Should no longer be accessible
        get_resp = api_get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 404

    def test_project_isolation_between_users(self):
        """User A's project should not be visible to User B (unless shared)."""
        project = create_project(f"IsoProject-{UNIQUE}", headers=USER_HEADERS)
        resp = api_get("/api/v1/projects", headers=USER2_HEADERS)
        assert resp.status_code == 200
        projects = resp.json()["data"]
        project_ids = [p["id"] for p in projects]
        assert project["id"] not in project_ids


# ════════════════════════════════════════════════════════════════════
# PART 3: Locales
# ════════════════════════════════════════════════════════════════════


class TestLocales:

    def test_add_locale_returns_201(self):
        """POST locale should return 201."""
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        assert resp.status_code == 201
        locale = resp.json()["data"]
        assert locale["code"] == "en"
        assert "createdAt" in locale

    def test_add_locale_with_region(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en_US"})
        assert resp.status_code == 201
        locale = resp.json()["data"]
        assert locale["code"] == "en_US"

    def test_add_invalid_locale_special_chars(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/locales", {"code": "invalid!"})
        assert resp.status_code == 400

    def test_add_invalid_locale_too_long(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/locales", {"code": "english"})
        assert resp.status_code == 400

    def test_add_duplicate_locale_returns_400(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})
        resp = api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})
        assert resp.status_code == 400

    def test_list_locales(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})

        resp = api_get(f"/api/v1/projects/{project_id}/locales")
        assert resp.status_code == 200
        locales = resp.json()["data"]
        assert len(locales) == 2
        codes = [loc["code"] for loc in locales]
        assert "en" in codes
        assert "fr" in codes

    def test_remove_locale_returns_204(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "de"})
        resp = api_delete(f"/api/v1/projects/{project_id}/locales/de")
        assert resp.status_code == 204

        # Verify gone
        locales_resp = api_get(f"/api/v1/projects/{project_id}/locales")
        codes = [loc["code"] for loc in locales_resp.json()["data"]]
        assert "de" not in codes

    def test_remove_nonexistent_locale_returns_404(self):
        project = create_project()
        project_id = project["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}/locales/xx")
        assert resp.status_code == 404

    def test_remove_locale_deletes_translations(self):
        """Removing a locale should delete all translations for it."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "es"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "hello"})
        term_id = term_resp.json()["data"]["id"]
        api_patch(f"/api/v1/projects/{project_id}/translations/es/{term_id}", {"value": "hola"})

        # Remove locale
        api_delete(f"/api/v1/projects/{project_id}/locales/es")

        # Re-add locale — translation should be gone
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "es"})
        trans_resp = api_get(f"/api/v1/projects/{project_id}/translations/es/{term_id}")
        assert trans_resp.status_code == 200
        assert trans_resp.json()["data"]["value"] == ""


# ════════════════════════════════════════════════════════════════════
# PART 4: Terms
# ════════════════════════════════════════════════════════════════════


class TestTerms:

    def test_create_term_returns_201(self):
        """POST term should return 201."""
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/terms", {
            "value": "home.welcome",
            "description": "Welcome message",
        })
        assert resp.status_code == 201
        term = resp.json()["data"]
        assert term["value"] == "home.welcome"
        assert term["description"] == "Welcome message"
        assert "id" in term
        assert "labels" in term
        assert isinstance(term["labels"], list)
        assert term["labels"] == []
        assert "createdAt" in term
        assert "updatedAt" in term

    def test_create_term_minimal(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "simple.key"})
        assert resp.status_code == 201
        term = resp.json()["data"]
        assert term["value"] == "simple.key"
        assert term["description"] == ""

    def test_create_duplicate_term_returns_400(self):
        """Duplicate term value in same project returns 400."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "dup.key"})
        resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "dup.key"})
        assert resp.status_code == 400

    def test_list_terms(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.one"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.two"})

        resp = api_get(f"/api/v1/projects/{project_id}/terms")
        assert resp.status_code == 200
        terms = resp.json()["data"]
        assert len(terms) >= 2
        values = [t["value"] for t in terms]
        assert "term.one" in values
        assert "term.two" in values

    def test_search_terms_filters_correctly(self):
        """Search should filter terms by substring match."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "menu.file"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "menu.edit"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "errors.notfound"})

        resp = api_get(f"/api/v1/projects/{project_id}/terms", params={"search": "menu"})
        assert resp.status_code == 200
        terms = resp.json()["data"]
        assert len(terms) == 2
        for t in terms:
            assert "menu" in t["value"].lower()

    def test_get_term(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "get.term"})
        term_id = create_resp.json()["data"]["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/terms/{term_id}")
        assert resp.status_code == 200
        term = resp.json()["data"]
        assert term["value"] == "get.term"
        assert term["id"] == term_id

    def test_get_nonexistent_term_returns_404(self):
        project = create_project()
        project_id = project["id"]
        fake_id = str(uuid.uuid4())

        resp = api_get(f"/api/v1/projects/{project_id}/terms/{fake_id}")
        assert resp.status_code == 404

    def test_update_term(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "old.key"})
        term_id = create_resp.json()["data"]["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}/terms/{term_id}", {
            "value": "new.key",
            "description": "Updated description",
        })
        assert resp.status_code == 200
        term = resp.json()["data"]
        assert term["value"] == "new.key"
        assert term["description"] == "Updated description"

    def test_update_term_to_duplicate_value_returns_400(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "existing.key"})
        create_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "other.key"})
        term_id = create_resp.json()["data"]["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}/terms/{term_id}", {"value": "existing.key"})
        assert resp.status_code == 400

    def test_delete_term_returns_204(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "del.key"})
        term_id = create_resp.json()["data"]["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}/terms/{term_id}")
        assert resp.status_code == 204

        # Verify gone
        get_resp = api_get(f"/api/v1/projects/{project_id}/terms/{term_id}")
        assert get_resp.status_code == 404

    def test_delete_term_cascades_translations(self):
        """Deleting a term should delete all its translations."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "to.delete"})
        term_id = term_resp.json()["data"]["id"]
        api_patch(f"/api/v1/projects/{project_id}/translations/en/{term_id}", {"value": "translated"})

        # Delete term
        api_delete(f"/api/v1/projects/{project_id}/terms/{term_id}")

        # List translations for locale should not include the deleted term
        trans_resp = api_get(f"/api/v1/projects/{project_id}/translations/en")
        assert trans_resp.status_code == 200
        term_ids = [t["termId"] for t in trans_resp.json()["data"]]
        assert term_id not in term_ids


# ════════════════════════════════════════════════════════════════════
# PART 5: Translations
# ════════════════════════════════════════════════════════════════════


class TestTranslations:

    def test_set_translation(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "greeting"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}/translations/en/{term_id}", {"value": "Hello"})
        assert resp.status_code == 200
        trans = resp.json()["data"]
        assert trans["termId"] == term_id
        assert trans["value"] == "Hello"

    def test_get_single_translation(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "farewell"})
        term_id = term_resp.json()["data"]["id"]
        api_patch(f"/api/v1/projects/{project_id}/translations/fr/{term_id}", {"value": "Au revoir"})

        resp = api_get(f"/api/v1/projects/{project_id}/translations/fr/{term_id}")
        assert resp.status_code == 200
        trans = resp.json()["data"]
        assert trans["value"] == "Au revoir"
        assert trans["termId"] == term_id

    def test_untranslated_returns_empty_string_not_404(self):
        """Untranslated term-locale pairs return empty string, not 404."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "de"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "untranslated.key"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/translations/de/{term_id}")
        assert resp.status_code == 200
        trans = resp.json()["data"]
        assert trans["value"] == ""
        assert trans["termId"] == term_id

    def test_overwrite_translation(self):
        """Updating an existing translation overwrites the value."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "update.me"})
        term_id = term_resp.json()["data"]["id"]

        api_patch(f"/api/v1/projects/{project_id}/translations/en/{term_id}", {"value": "First"})
        resp = api_patch(f"/api/v1/projects/{project_id}/translations/en/{term_id}", {"value": "Second"})
        assert resp.status_code == 200
        assert resp.json()["data"]["value"] == "Second"

    def test_get_all_translations_for_locale(self):
        """GET translations for a locale should return all terms with termId, termValue, value."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term1_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "key.one"})
        term1_id = term1_resp.json()["data"]["id"]
        term2_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "key.two"})
        term2_id = term2_resp.json()["data"]["id"]

        api_patch(f"/api/v1/projects/{project_id}/translations/en/{term1_id}", {"value": "One"})
        api_patch(f"/api/v1/projects/{project_id}/translations/en/{term2_id}", {"value": "Two"})

        resp = api_get(f"/api/v1/projects/{project_id}/translations/en")
        assert resp.status_code == 200
        translations = resp.json()["data"]
        assert len(translations) >= 2

        # Check structure — must have termId, termValue, value
        for t in translations:
            assert "termId" in t
            assert "termValue" in t
            assert "value" in t

        trans_map = {t["termId"]: t["value"] for t in translations}
        assert trans_map[term1_id] == "One"
        assert trans_map[term2_id] == "Two"

    def test_locale_translations_include_untranslated_terms(self):
        """GET translations for locale includes untranslated terms with empty value."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "no.translation"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/translations/en")
        assert resp.status_code == 200
        translations = resp.json()["data"]
        term_ids = [t["termId"] for t in translations]
        assert term_id in term_ids
        trans_map = {t["termId"]: t["value"] for t in translations}
        assert trans_map[term_id] == ""

    def test_translation_nonexistent_locale_returns_404(self):
        """Getting translation for a locale not in project should return 404."""
        project = create_project()
        project_id = project["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "some.key"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/translations/xx/{term_id}")
        assert resp.status_code == 404

    def test_translation_nonexistent_term_returns_404(self):
        """Getting translation for a nonexistent term should return 404."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        fake_id = str(uuid.uuid4())

        resp = api_get(f"/api/v1/projects/{project_id}/translations/en/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Import/Export
# ════════════════════════════════════════════════════════════════════


class TestImportExport:

    def test_import_json_creates_terms_and_translations(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})

        resp = api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {
                "welcome": "Welcome",
                "goodbye": "Goodbye",
            },
        })
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert "termsCreated" in result
        assert "translationsCreated" in result
        assert "translationsUpdated" in result
        assert result["termsCreated"] == 2
        assert result["translationsCreated"] == 2

    def test_import_merges_without_deleting(self):
        """Import should update/add but not delete existing translations."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})

        # First import
        api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {"hello": "Hello", "world": "World"},
        })

        # Second import — update "hello", add "new"
        resp = api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {"hello": "Hi", "new.key": "New"},
        })
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["termsCreated"] == 1  # "new.key"
        assert result["translationsUpdated"] == 1  # "hello" changed
        assert result["translationsCreated"] == 1  # "new.key"

        # Verify "world" is unchanged (not deleted)
        terms_resp = api_get(f"/api/v1/projects/{project_id}/terms")
        terms = terms_resp.json()["data"]
        world_term = next(t for t in terms if t["value"] == "world")
        trans_resp = api_get(f"/api/v1/projects/{project_id}/translations/en/{world_term['id']}")
        assert trans_resp.json()["data"]["value"] == "World"

    def test_import_auto_creates_terms(self):
        """Import should auto-create terms that don't exist."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})

        resp = api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "fr",
            "format": "json",
            "data": {"new.term": "Nouveau terme"},
        })
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["termsCreated"] == 1

        # Verify term exists
        terms_resp = api_get(f"/api/v1/projects/{project_id}/terms")
        values = [t["value"] for t in terms_resp.json()["data"]]
        assert "new.term" in values

    def test_import_nonexistent_locale_returns_404(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "zz",
            "format": "json",
            "data": {"key": "value"},
        })
        assert resp.status_code == 404

    def test_export_json_flat(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {"export.key1": "Value 1", "export.key2": "Value 2"},
        })

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "en", "format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["export.key1"] == "Value 1"
        assert data["export.key2"] == "Value 2"

    def test_export_nested_json(self):
        """Nested JSON export should convert dot-notation to nested objects."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {"menu.file": "File", "menu.edit": "Edit", "title": "App"},
        })

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "en", "format": "nested_json"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["menu"]["file"] == "File"
        assert data["menu"]["edit"] == "Edit"
        assert data["title"] == "App"

    def test_export_yaml(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "json",
            "data": {"yaml.key": "YAML Value"},
        })

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "en", "format": "yaml"})
        assert resp.status_code == 200
        # YAML response should contain the key and value
        text = resp.text
        assert "yaml" in text
        assert "YAML Value" in text

    def test_export_nonexistent_locale_returns_404(self):
        project = create_project()
        project_id = project["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "xx", "format": "json"})
        assert resp.status_code == 404

    def test_export_includes_untranslated_as_empty(self):
        """Export should include untranslated terms with empty string value."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "untranslated.export"})

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "en", "format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "untranslated.export" in data
        assert data["untranslated.export"] == ""

    def test_import_nested_json_format(self):
        """Import with nested_json format should flatten to dot-notation terms."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})

        resp = api_post(f"/api/v1/projects/{project_id}/imports", {
            "locale": "en",
            "format": "nested_json",
            "data": {
                "nav": {
                    "home": "Home",
                    "about": "About",
                },
                "title": "App Title",
            },
        })
        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["termsCreated"] == 3

        # Verify terms are created with dot-notation
        terms_resp = api_get(f"/api/v1/projects/{project_id}/terms")
        values = [t["value"] for t in terms_resp.json()["data"]]
        assert "nav.home" in values
        assert "nav.about" in values
        assert "title" in values


# ════════════════════════════════════════════════════════════════════
# PART 7: Project Members
# ════════════════════════════════════════════════════════════════════


class TestMembers:

    def test_creator_is_admin_member(self):
        """Project creator should be in members list as admin."""
        project = create_project()
        project_id = project["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/members")
        assert resp.status_code == 200
        members = resp.json()["data"]
        assert len(members) >= 1
        # Creator should be admin
        creator = next(m for m in members if m["userId"] == USER_KEY)
        assert creator["role"] == "admin"

    def test_add_member_returns_201(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/members", {
            "userId": USER2_KEY,
            "role": "editor",
        })
        assert resp.status_code == 201
        member = resp.json()["data"]
        assert member["userId"] == USER2_KEY
        assert member["role"] == "editor"

    def test_added_member_can_see_project(self):
        """After being added, the member should see the project in their list."""
        project = create_project(f"SharedProject-{UNIQUE}")
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/members", {
            "userId": USER2_KEY,
            "role": "viewer",
        })

        resp = api_get("/api/v1/projects", headers=USER2_HEADERS)
        assert resp.status_code == 200
        project_ids = [p["id"] for p in resp.json()["data"]]
        assert project_id in project_ids

    def test_add_duplicate_member_returns_400(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER3_KEY, "role": "viewer"})
        resp = api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER3_KEY, "role": "editor"})
        assert resp.status_code == 400

    def test_update_member_role(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_patch(f"/api/v1/projects/{project_id}/members/{USER2_KEY}", {"role": "editor"})
        assert resp.status_code == 200
        member = resp.json()["data"]
        assert member["role"] == "editor"

    def test_remove_member_returns_204(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "editor"})

        resp = api_delete(f"/api/v1/projects/{project_id}/members/{USER2_KEY}")
        assert resp.status_code == 204

        # Verify removed
        members_resp = api_get(f"/api/v1/projects/{project_id}/members")
        user_ids = [m["userId"] for m in members_resp.json()["data"]]
        assert USER2_KEY not in user_ids

    def test_cannot_remove_owner(self):
        """The project creator (owner) cannot be removed."""
        project = create_project()
        project_id = project["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}/members/{USER_KEY}")
        assert resp.status_code == 400

    def test_cannot_remove_self(self):
        """A member cannot remove themselves."""
        project = create_project()
        project_id = project["id"]

        # Add USER2 as admin
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "admin"})

        # USER2 tries to remove themselves
        resp = api_delete(f"/api/v1/projects/{project_id}/members/{USER2_KEY}", headers=USER2_HEADERS)
        assert resp.status_code == 400

    def test_remove_nonexistent_member_returns_404(self):
        project = create_project()
        project_id = project["id"]
        fake_user = f"nonexistent-{uuid.uuid4().hex[:8]}"

        resp = api_delete(f"/api/v1/projects/{project_id}/members/{fake_user}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Role Enforcement
# ════════════════════════════════════════════════════════════════════


class TestRoleEnforcement:

    def test_viewer_cannot_create_term(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "nope"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_viewer_cannot_set_translation(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "viewer.test"})
        term_id = term_resp.json()["data"]["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_patch(
            f"/api/v1/projects/{project_id}/translations/en/{term_id}",
            {"value": "Nope"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_viewer_can_read_terms(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "readable.key"})
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_get(f"/api/v1/projects/{project_id}/terms", headers=USER2_HEADERS)
        assert resp.status_code == 200
        values = [t["value"] for t in resp.json()["data"]]
        assert "readable.key" in values

    def test_viewer_can_export(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_get(
            f"/api/v1/projects/{project_id}/exports",
            params={"locale": "en", "format": "json"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 200

    def test_editor_can_create_term(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "editor"})

        resp = api_post(
            f"/api/v1/projects/{project_id}/terms",
            {"value": "editor.term"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 201

    def test_editor_cannot_add_locale(self):
        """Editors cannot manage locales (admin only)."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "editor"})

        resp = api_post(
            f"/api/v1/projects/{project_id}/locales",
            {"code": "it"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_editor_cannot_add_member(self):
        """Editors cannot manage members (admin only)."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "editor"})

        resp = api_post(
            f"/api/v1/projects/{project_id}/members",
            {"userId": USER3_KEY, "role": "viewer"},
            headers=USER2_HEADERS,
        )
        assert resp.status_code == 403

    def test_editor_cannot_delete_project(self):
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "editor"})

        resp = api_delete(f"/api/v1/projects/{project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_non_member_cannot_access_project(self):
        """Non-member gets 404 (not 403) when accessing a project."""
        project = create_project(headers=USER_HEADERS)
        project_id = project["id"]

        resp = api_get(f"/api/v1/projects/{project_id}", headers=USER3_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Labels
# ════════════════════════════════════════════════════════════════════


class TestLabels:

    def test_create_label_returns_201(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/labels", {
            "value": "menu",
            "color": "#ff0000",
        })
        assert resp.status_code == 201
        label = resp.json()["data"]
        assert label["value"] == "menu"
        assert label["color"] == "#ff0000"
        assert "id" in label
        assert "createdAt" in label
        assert "updatedAt" in label

    def test_create_label_default_color(self):
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "errors"})
        assert resp.status_code == 201
        label = resp.json()["data"]
        assert label["color"] == "#000000"

    def test_create_duplicate_label_returns_400(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/labels", {"value": "dup"})
        resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "dup"})
        assert resp.status_code == 400

    def test_list_labels(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/labels", {"value": "label1"})
        api_post(f"/api/v1/projects/{project_id}/labels", {"value": "label2"})

        resp = api_get(f"/api/v1/projects/{project_id}/labels")
        assert resp.status_code == 200
        labels = resp.json()["data"]
        assert len(labels) >= 2
        values = [lbl["value"] for lbl in labels]
        assert "label1" in values
        assert "label2" in values

    def test_get_label(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "getme"})
        label_id = create_resp.json()["data"]["id"]

        resp = api_get(f"/api/v1/projects/{project_id}/labels/{label_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["value"] == "getme"

    def test_update_label(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "oldlabel"})
        label_id = create_resp.json()["data"]["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}/labels/{label_id}", {
            "value": "newlabel",
            "color": "#00ff00",
        })
        assert resp.status_code == 200
        label = resp.json()["data"]
        assert label["value"] == "newlabel"
        assert label["color"] == "#00ff00"

    def test_delete_label_returns_204(self):
        project = create_project()
        project_id = project["id"]

        create_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "deleteme"})
        label_id = create_resp.json()["data"]["id"]

        resp = api_delete(f"/api/v1/projects/{project_id}/labels/{label_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/v1/projects/{project_id}/labels/{label_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Term Labels
# ════════════════════════════════════════════════════════════════════


class TestTermLabels:

    def test_add_label_to_term(self):
        project = create_project()
        project_id = project["id"]

        label_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "feature"})
        label_id = label_resp.json()["data"]["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.labeled"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})
        assert resp.status_code == 200
        term = resp.json()["data"]
        label_ids = [lbl["id"] for lbl in term["labels"]]
        assert label_id in label_ids

    def test_label_appears_when_getting_term(self):
        """Labels should appear in term response after attachment."""
        project = create_project()
        project_id = project["id"]

        label_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "ui"})
        label_id = label_resp.json()["data"]["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "with.label"})
        term_id = term_resp.json()["data"]["id"]

        api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})

        get_resp = api_get(f"/api/v1/projects/{project_id}/terms/{term_id}")
        term = get_resp.json()["data"]
        label_ids = [lbl["id"] for lbl in term["labels"]]
        assert label_id in label_ids

    def test_add_same_label_twice_returns_400(self):
        project = create_project()
        project_id = project["id"]

        label_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "dup_attach"})
        label_id = label_resp.json()["data"]["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.dup.label"})
        term_id = term_resp.json()["data"]["id"]

        api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})
        resp = api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})
        assert resp.status_code == 400

    def test_remove_label_from_term(self):
        project = create_project()
        project_id = project["id"]

        label_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "removable"})
        label_id = label_resp.json()["data"]["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.removelabel"})
        term_id = term_resp.json()["data"]["id"]

        api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})

        resp = api_delete(f"/api/v1/projects/{project_id}/terms/{term_id}/labels/{label_id}")
        assert resp.status_code == 204

        # Verify label is gone from term
        get_resp = api_get(f"/api/v1/projects/{project_id}/terms/{term_id}")
        term = get_resp.json()["data"]
        label_ids = [lbl["id"] for lbl in term["labels"]]
        assert label_id not in label_ids

    def test_delete_label_removes_from_all_terms(self):
        """Deleting a label should cascade-remove it from all terms."""
        project = create_project()
        project_id = project["id"]

        label_resp = api_post(f"/api/v1/projects/{project_id}/labels", {"value": "cascade_label"})
        label_id = label_resp.json()["data"]["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "term.cascade"})
        term_id = term_resp.json()["data"]["id"]

        api_post(f"/api/v1/projects/{project_id}/terms/{term_id}/labels", {"labelId": label_id})

        # Delete the label
        api_delete(f"/api/v1/projects/{project_id}/labels/{label_id}")

        # Term should no longer have the label
        get_resp = api_get(f"/api/v1/projects/{project_id}/terms/{term_id}")
        term = get_resp.json()["data"]
        assert len(term["labels"]) == 0


# ════════════════════════════════════════════════════════════════════
# PART 11: Statistics
# ════════════════════════════════════════════════════════════════════


class TestStatistics:

    def test_stats_basic_calculation(self):
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})

        t1 = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "s.one"}).json()["data"]["id"]
        t2 = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "s.two"}).json()["data"]["id"]

        # Translate both in en, only one in fr
        api_patch(f"/api/v1/projects/{project_id}/translations/en/{t1}", {"value": "One"})
        api_patch(f"/api/v1/projects/{project_id}/translations/en/{t2}", {"value": "Two"})
        api_patch(f"/api/v1/projects/{project_id}/translations/fr/{t1}", {"value": "Un"})

        resp = api_get(f"/api/v1/projects/{project_id}/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert isinstance(stats, list)
        assert len(stats) == 2

        stats_map = {s["locale"]: s for s in stats}
        en_stats = stats_map["en"]
        fr_stats = stats_map["fr"]

        assert en_stats["totalCount"] == 2
        assert en_stats["translatedCount"] == 2
        assert en_stats["progress"] == 100.0

        assert fr_stats["totalCount"] == 2
        assert fr_stats["translatedCount"] == 1
        assert fr_stats["progress"] == 50.0

    def test_stats_no_terms_returns_zero(self):
        """If there are no terms, progress should be 0."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})

        resp = api_get(f"/api/v1/projects/{project_id}/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert len(stats) == 1
        assert stats[0]["totalCount"] == 0
        assert stats[0]["translatedCount"] == 0
        assert stats[0]["progress"] == 0

    def test_stats_empty_translation_not_counted(self):
        """Setting a translation to empty string should not count as translated."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        t1 = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "stat.empty"}).json()["data"]["id"]
        api_patch(f"/api/v1/projects/{project_id}/translations/en/{t1}", {"value": ""})

        resp = api_get(f"/api/v1/projects/{project_id}/stats")
        stats = resp.json()["data"]
        en_stats = next(s for s in stats if s["locale"] == "en")
        assert en_stats["translatedCount"] == 0
        assert en_stats["progress"] == 0

    def test_stats_nonexistent_project_returns_404(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/v1/projects/{fake_id}/stats")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_project_cascades_all(self):
        """Deleting a project should delete all related data."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "cascade.term"})
        api_post(f"/api/v1/projects/{project_id}/labels", {"value": "cascade.label"})

        resp = api_delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 204

        # Verify project is completely gone
        get_resp = api_get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Edge Cases & Integration
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_export_empty_project(self):
        """Exporting from a project with no terms should return empty object."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})

        resp = api_get(f"/api/v1/projects/{project_id}/exports", params={"locale": "en", "format": "json"})
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_term_value_with_dots(self):
        """Terms can have dots in their value — used for namespacing."""
        project = create_project()
        project_id = project["id"]

        resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "a.b.c.d"})
        assert resp.status_code == 201
        assert resp.json()["data"]["value"] == "a.b.c.d"

    def test_multiple_locales_same_term(self):
        """Same term can have different translations per locale."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "fr"})

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "hello"})
        term_id = term_resp.json()["data"]["id"]

        api_patch(f"/api/v1/projects/{project_id}/translations/en/{term_id}", {"value": "Hello"})
        api_patch(f"/api/v1/projects/{project_id}/translations/fr/{term_id}", {"value": "Bonjour"})

        en_resp = api_get(f"/api/v1/projects/{project_id}/translations/en/{term_id}")
        fr_resp = api_get(f"/api/v1/projects/{project_id}/translations/fr/{term_id}")

        assert en_resp.json()["data"]["value"] == "Hello"
        assert fr_resp.json()["data"]["value"] == "Bonjour"

    def test_partial_update_project_name_only(self):
        """PATCH project with only name should not change description."""
        project = create_project()
        project_id = project["id"]
        original_desc = project["description"]

        resp = api_patch(f"/api/v1/projects/{project_id}", {"name": "NewName"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "NewName"
        assert resp.json()["data"]["description"] == original_desc

    def test_partial_update_term_description_only(self):
        """PATCH term with only description should not change value."""
        project = create_project()
        project_id = project["id"]

        term_resp = api_post(f"/api/v1/projects/{project_id}/terms", {"value": "keep.value"})
        term_id = term_resp.json()["data"]["id"]

        resp = api_patch(f"/api/v1/projects/{project_id}/terms/{term_id}", {"description": "New desc"})
        assert resp.status_code == 200
        assert resp.json()["data"]["value"] == "keep.value"
        assert resp.json()["data"]["description"] == "New desc"

    def test_search_is_case_insensitive(self):
        """Term search should be case-insensitive."""
        project = create_project()
        project_id = project["id"]

        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "HomePage.Title"})
        api_post(f"/api/v1/projects/{project_id}/terms", {"value": "other.key"})

        resp = api_get(f"/api/v1/projects/{project_id}/terms", params={"search": "homepage"})
        assert resp.status_code == 200
        terms = resp.json()["data"]
        assert len(terms) == 1
        assert terms[0]["value"] == "HomePage.Title"

    def test_removed_member_loses_access(self):
        """After removal, a member should no longer see the project."""
        project = create_project()
        project_id = project["id"]

        # Add and then remove USER2
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})
        api_delete(f"/api/v1/projects/{project_id}/members/{USER2_KEY}")

        # USER2 should no longer see the project
        resp = api_get(f"/api/v1/projects/{project_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_viewer_can_view_stats(self):
        """Viewers should be able to access stats."""
        project = create_project()
        project_id = project["id"]
        api_post(f"/api/v1/projects/{project_id}/locales", {"code": "en"})
        api_post(f"/api/v1/projects/{project_id}/members", {"userId": USER2_KEY, "role": "viewer"})

        resp = api_get(f"/api/v1/projects/{project_id}/stats", headers=USER2_HEADERS)
        assert resp.status_code == 200
