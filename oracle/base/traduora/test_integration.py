"""
BackendForge — L2 Integration Tests for Traduora Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase field names + data wrapper
- Pattern 2: Nested/related data (labels in terms)
- Pattern 3: Search/filter actually implemented
- Pattern 4: Exact status codes (201/204/400/403/404)
- Pattern 5: Business logic (stats, import merge counters)
- Pattern 6: Project membership isolation
- Pattern 7: Cascade/side-effect correctness
- Pattern 8: Uniqueness constraints
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

USER1_KEY = f"l2-user1-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"l2-user2-{uuid.uuid4().hex[:8]}"
USER3_KEY = f"l2-user3-{uuid.uuid4().hex[:8]}"

H1 = {"X-Api-Key": USER1_KEY, "Content-Type": "application/json"}
H2 = {"X-Api-Key": USER2_KEY, "Content-Type": "application/json"}
H3 = {"X-Api-Key": USER3_KEY, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _isolate_test_users():
    global USER1_KEY, USER2_KEY, USER3_KEY

    USER1_KEY = f"l2-user1-{uuid.uuid4().hex}"
    USER2_KEY = f"l2-user2-{uuid.uuid4().hex}"
    USER3_KEY = f"l2-user3-{uuid.uuid4().hex}"
    H1["X-Api-Key"] = USER1_KEY
    H2["X-Api-Key"] = USER2_KEY
    H3["X-Api-Key"] = USER3_KEY


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or H1, timeout=30)


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or H1, timeout=30)


def patch(path, json=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json, headers=headers or H1, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or H1, timeout=30)


def make_project(name=None, headers=None):
    name = name or f"proj-{uuid.uuid4().hex[:8]}"
    r = post("/api/v1/projects", {"name": name, "description": "test"}, headers=headers)
    assert r.status_code == 201
    return r.json()["data"]


class TestDataWrapper:
    """Pattern 1: All responses use {"data": ...} wrapper."""

    def test_list_projects_has_data_wrapper(self):
        make_project()
        r = get("/api/v1/projects")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_create_project_has_data_wrapper(self):
        r = post("/api/v1/projects", {"name": f"wrap-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201
        body = r.json()
        assert "data" in body
        assert "id" in body["data"]

    def test_get_project_has_data_wrapper(self):
        p = make_project()
        r = get(f"/api/v1/projects/{p['id']}")
        assert r.status_code == 200
        assert "data" in r.json()
        assert r.json()["data"]["id"] == p["id"]

    def test_list_terms_has_data_wrapper(self):
        p = make_project()
        r = get(f"/api/v1/projects/{p['id']}/terms")
        assert r.status_code == 200
        assert "data" in r.json()
        assert isinstance(r.json()["data"], list)

    def test_stats_has_data_wrapper(self):
        p = make_project()
        post(f"/api/v1/projects/{p['id']}/locales", {"code": "en"})
        r = get(f"/api/v1/projects/{p['id']}/stats")
        assert r.status_code == 200
        assert "data" in r.json()


class TestProjectFields:
    """Pattern 1: Verify camelCase project fields."""

    def test_project_response_fields(self):
        r = post("/api/v1/projects", {"name": "FieldCheck", "description": "Desc"})
        assert r.status_code == 201
        p = r.json()["data"]
        assert p["name"] == "FieldCheck"
        assert p["description"] == "Desc"
        assert "id" in p
        assert "createdAt" in p
        assert "updatedAt" in p
        # Verify NOT snake_case
        assert "created_at" not in p
        assert "updated_at" not in p


class TestTermFieldsAndLabels:
    """Pattern 1+2: Term response includes labels array."""

    def test_term_includes_labels_array(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/terms", {"value": "test.key", "description": "Desc"})
        assert r.status_code == 201
        term = r.json()["data"]
        assert "id" in term
        assert "value" in term
        assert term["value"] == "test.key"
        assert "description" in term
        assert term["description"] == "Desc"
        assert "labels" in term
        assert isinstance(term["labels"], list)
        assert term["labels"] == []
        assert "createdAt" in term
        assert "updatedAt" in term

    def test_term_with_attached_label_includes_full_label(self):
        """After attaching a label, GET term should include full label objects."""
        p = make_project()
        pid = p["id"]
        lr = post(f"/api/v1/projects/{pid}/labels", {"value": "ui", "color": "#ff0000"})
        lid = lr.json()["data"]["id"]
        tr = post(f"/api/v1/projects/{pid}/terms", {"value": "labeled.term"})
        tid = tr.json()["data"]["id"]

        post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": lid})

        r = get(f"/api/v1/projects/{pid}/terms/{tid}")
        assert r.status_code == 200
        term = r.json()["data"]
        assert len(term["labels"]) == 1
        lbl = term["labels"][0]
        assert lbl["id"] == lid
        assert lbl["value"] == "ui"
        assert lbl["color"] == "#ff0000"


class TestExactStatusCodes:
    """Pattern 4: Verify exact HTTP status codes."""

    def test_create_project_201(self):
        r = post("/api/v1/projects", {"name": f"s-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_term_201(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/terms", {"value": f"t-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_locale_201(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "en"})
        assert r.status_code == 201

    def test_create_label_201(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/labels", {"value": f"l-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_add_member_201(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/members", {"userId": USER2_KEY, "role": "viewer"})
        assert r.status_code == 201

    def test_delete_project_204(self):
        p = make_project()
        r = delete(f"/api/v1/projects/{p['id']}")
        assert r.status_code == 204

    def test_delete_term_204(self):
        p = make_project()
        tr = post(f"/api/v1/projects/{p['id']}/terms", {"value": "del.me"})
        r = delete(f"/api/v1/projects/{p['id']}/terms/{tr.json()['data']['id']}")
        assert r.status_code == 204

    def test_delete_locale_204(self):
        p = make_project()
        post(f"/api/v1/projects/{p['id']}/locales", {"code": "fr"})
        r = delete(f"/api/v1/projects/{p['id']}/locales/fr")
        assert r.status_code == 204

    def test_delete_label_204(self):
        p = make_project()
        lr = post(f"/api/v1/projects/{p['id']}/labels", {"value": "del"})
        r = delete(f"/api/v1/projects/{p['id']}/labels/{lr.json()['data']['id']}")
        assert r.status_code == 204

    def test_remove_member_204(self):
        p = make_project()
        post(f"/api/v1/projects/{p['id']}/members", {"userId": USER2_KEY, "role": "editor"})
        r = delete(f"/api/v1/projects/{p['id']}/members/{USER2_KEY}")
        assert r.status_code == 204

    def test_nonexistent_project_404(self):
        r = get(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_duplicate_term_400(self):
        p = make_project()
        post(f"/api/v1/projects/{p['id']}/terms", {"value": "dup"})
        r = post(f"/api/v1/projects/{p['id']}/terms", {"value": "dup"})
        assert r.status_code == 400

    def test_invalid_locale_400(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "INVALID"})
        assert r.status_code == 400


class TestSearchFilter:
    """Pattern 3: Search query param actually filters terms."""

    def test_search_returns_only_matching(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/terms", {"value": "nav.home"})
        post(f"/api/v1/projects/{pid}/terms", {"value": "nav.about"})
        post(f"/api/v1/projects/{pid}/terms", {"value": "footer.copyright"})

        r = get(f"/api/v1/projects/{pid}/terms", params={"search": "nav"})
        assert r.status_code == 200
        terms = r.json()["data"]
        assert len(terms) == 2
        values = [t["value"] for t in terms]
        assert "nav.home" in values
        assert "nav.about" in values
        assert "footer.copyright" not in values

    def test_search_case_insensitive(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/terms", {"value": "HomeScreen.title"})
        post(f"/api/v1/projects/{pid}/terms", {"value": "other.key"})

        r = get(f"/api/v1/projects/{pid}/terms", params={"search": "homescreen"})
        assert r.status_code == 200
        terms = r.json()["data"]
        assert len(terms) == 1
        assert terms[0]["value"] == "HomeScreen.title"


class TestStatisticsCalculation:
    """Pattern 5: Stats computed correctly with multiple inputs."""

    def test_stats_progress_calculation(self):
        """3 terms, 2 translated in en → progress=66.7."""
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        t1 = post(f"/api/v1/projects/{pid}/terms", {"value": "k1"}).json()["data"]["id"]
        t2 = post(f"/api/v1/projects/{pid}/terms", {"value": "k2"}).json()["data"]["id"]
        post(f"/api/v1/projects/{pid}/terms", {"value": "k3"})

        patch(f"/api/v1/projects/{pid}/translations/en/{t1}", {"value": "V1"})
        patch(f"/api/v1/projects/{pid}/translations/en/{t2}", {"value": "V2"})

        r = get(f"/api/v1/projects/{pid}/stats")
        assert r.status_code == 200
        stats = r.json()["data"]
        en = next(s for s in stats if s["locale"] == "en")
        assert en["totalCount"] == 3
        assert en["translatedCount"] == 2
        assert en["progress"] == pytest.approx(66.7, abs=0.1)

    def test_stats_fields_present(self):
        """Each stat entry has locale, totalCount, translatedCount, progress."""
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "de"})
        post(f"/api/v1/projects/{pid}/terms", {"value": "x"})

        r = get(f"/api/v1/projects/{pid}/stats")
        stat = r.json()["data"][0]
        assert "locale" in stat
        assert "totalCount" in stat
        assert "translatedCount" in stat
        assert "progress" in stat


class TestImportMergeLogic:
    """Pattern 5: Import counters computed correctly."""

    def test_import_creates_new_terms_and_translations(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"key1": "Val1", "key2": "Val2", "key3": "Val3"}
        })
        assert r.status_code == 200
        result = r.json()["data"]
        assert result["termsCreated"] == 3
        assert result["translationsCreated"] == 3
        assert result["translationsUpdated"] == 0

    def test_import_updates_existing_translations(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        # First import
        post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"hello": "Hello", "bye": "Bye"}
        })

        # Second import with updated value
        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"hello": "Hi there"}
        })
        assert r.status_code == 200
        result = r.json()["data"]
        assert result["termsCreated"] == 0
        assert result["translationsCreated"] == 0
        assert result["translationsUpdated"] == 1

    def test_import_same_value_not_counted(self):
        """If import value is same as existing, translationsUpdated should not increment."""
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"unchanged": "Same"}
        })

        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"unchanged": "Same"}
        })
        result = r.json()["data"]
        assert result["termsCreated"] == 0
        assert result["translationsCreated"] == 0
        assert result["translationsUpdated"] == 0


class TestProjectMembershipIsolation:
    """Pattern 6: Non-members can't access projects."""

    def test_non_member_gets_404(self):
        p = make_project(headers=H1)
        r = get(f"/api/v1/projects/{p['id']}", headers=H2)
        assert r.status_code == 404

    def test_non_member_cannot_list_terms(self):
        p = make_project(headers=H1)
        r = get(f"/api/v1/projects/{p['id']}/terms", headers=H2)
        assert r.status_code == 404

    def test_removed_member_loses_access(self):
        p = make_project(headers=H1)
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "viewer"})
        # Verify access
        assert get(f"/api/v1/projects/{pid}", headers=H2).status_code == 200
        # Remove
        delete(f"/api/v1/projects/{pid}/members/{USER2_KEY}")
        # No longer accessible
        assert get(f"/api/v1/projects/{pid}", headers=H2).status_code == 404


class TestCascadeDeletes:
    """Pattern 7: Cascade delete verification."""

    def test_delete_locale_removes_translations(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "es"})
        t = post(f"/api/v1/projects/{pid}/terms", {"value": "cascade.loc"}).json()["data"]["id"]
        patch(f"/api/v1/projects/{pid}/translations/es/{t}", {"value": "Hola"})

        delete(f"/api/v1/projects/{pid}/locales/es")

        # Re-add locale, translation should be gone
        post(f"/api/v1/projects/{pid}/locales", {"code": "es"})
        r = get(f"/api/v1/projects/{pid}/translations/es/{t}")
        assert r.status_code == 200
        assert r.json()["data"]["value"] == ""

    def test_delete_term_removes_label_associations(self):
        p = make_project()
        pid = p["id"]
        lr = post(f"/api/v1/projects/{pid}/labels", {"value": "cascade"})
        lid = lr.json()["data"]["id"]
        tr = post(f"/api/v1/projects/{pid}/terms", {"value": "del.with.label"})
        tid = tr.json()["data"]["id"]
        post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": lid})

        delete(f"/api/v1/projects/{pid}/terms/{tid}")

        # Label still exists
        r = get(f"/api/v1/projects/{pid}/labels/{lid}")
        assert r.status_code == 200


class TestRoleEnforcement:
    """Pattern 6: RBAC verification."""

    def test_viewer_cannot_create_term(self):
        p = make_project(headers=H1)
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "viewer"})
        r = post(f"/api/v1/projects/{pid}/terms", {"value": "nope"}, headers=H2)
        assert r.status_code == 403

    def test_editor_cannot_add_locale(self):
        p = make_project(headers=H1)
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "editor"})
        r = post(f"/api/v1/projects/{pid}/locales", {"code": "it"}, headers=H2)
        assert r.status_code == 403

    def test_editor_cannot_delete_project(self):
        p = make_project(headers=H1)
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "editor"})
        r = delete(f"/api/v1/projects/{pid}", headers=H2)
        assert r.status_code == 403


class TestLocaleValidation:
    """Pattern 8: Locale code validation."""

    def test_valid_two_letter(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "ja"})
        assert r.status_code == 201

    def test_valid_with_region(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "pt_BR"})
        assert r.status_code == 201

    def test_invalid_three_letter(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "eng"})
        assert r.status_code == 400

    def test_invalid_uppercase(self):
        p = make_project()
        r = post(f"/api/v1/projects/{p['id']}/locales", {"code": "EN"})
        assert r.status_code == 400

    def test_duplicate_locale_400(self):
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "ko"})
        r = post(f"/api/v1/projects/{pid}/locales", {"code": "ko"})
        assert r.status_code == 400
