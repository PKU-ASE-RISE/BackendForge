"""
BackendForge — L3 Workflow Tests for Traduora Task

Multi-step cross-entity workflows testing:
- Pattern 2+5+7: Nested data + business logic + cascades
- Pattern 3+6: Search/filter + isolation
- Pattern 1+4+8: Field names + status codes + uniqueness
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

USER1_KEY = f"l3-user1-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"l3-user2-{uuid.uuid4().hex[:8]}"
USER3_KEY = f"l3-user3-{uuid.uuid4().hex[:8]}"

H1 = {"X-Api-Key": USER1_KEY, "Content-Type": "application/json"}
H2 = {"X-Api-Key": USER2_KEY, "Content-Type": "application/json"}
H3 = {"X-Api-Key": USER3_KEY, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _isolate_test_users():
    global USER1_KEY, USER2_KEY, USER3_KEY

    USER1_KEY = f"l3-user1-{uuid.uuid4().hex}"
    USER2_KEY = f"l3-user2-{uuid.uuid4().hex}"
    USER3_KEY = f"l3-user3-{uuid.uuid4().hex}"
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


class TestFullTranslationWorkflow:
    """Pattern 2+5+7: Full translation lifecycle with stats verification."""

    def test_complete_translation_workflow(self):
        """
        1. Create project
        2. Add locales (en, fr, de)
        3. Create 4 terms
        4. Translate all 4 in en, 2 in fr, 0 in de
        5. Verify stats: en=100%, fr=50%, de=0%
        6. Export en as json — verify all 4 keys present
        7. Export fr as nested_json — verify structure
        8. Delete a locale (de) → verify stats only show 2 locales
        """
        p = make_project()
        pid = p["id"]

        # 2. Locales
        for code in ["en", "fr", "de"]:
            r = post(f"/api/v1/projects/{pid}/locales", {"code": code})
            assert r.status_code == 201

        # 3. Terms
        term_ids = []
        for val in ["nav.home", "nav.about", "footer.copy", "title"]:
            r = post(f"/api/v1/projects/{pid}/terms", {"value": val})
            assert r.status_code == 201
            term_ids.append(r.json()["data"]["id"])

        # 4. Translations
        en_vals = ["Home", "About", "Copyright", "App Title"]
        for tid, val in zip(term_ids, en_vals):
            patch(f"/api/v1/projects/{pid}/translations/en/{tid}", {"value": val})

        fr_vals = ["Accueil", "A propos"]
        for tid, val in zip(term_ids[:2], fr_vals):
            patch(f"/api/v1/projects/{pid}/translations/fr/{tid}", {"value": val})

        # 5. Stats
        r = get(f"/api/v1/projects/{pid}/stats")
        assert r.status_code == 200
        stats = {s["locale"]: s for s in r.json()["data"]}
        assert stats["en"]["totalCount"] == 4
        assert stats["en"]["translatedCount"] == 4
        assert stats["en"]["progress"] == 100.0
        assert stats["fr"]["totalCount"] == 4
        assert stats["fr"]["translatedCount"] == 2
        assert stats["fr"]["progress"] == 50.0
        assert stats["de"]["totalCount"] == 4
        assert stats["de"]["translatedCount"] == 0
        assert stats["de"]["progress"] == 0.0

        # 6. Export en
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "json"})
        assert r.status_code == 200
        exported = r.json()
        assert exported["nav.home"] == "Home"
        assert exported["nav.about"] == "About"
        assert exported["footer.copy"] == "Copyright"
        assert exported["title"] == "App Title"

        # 7. Export fr nested
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "fr", "format": "nested_json"})
        assert r.status_code == 200
        nested = r.json()
        assert nested["nav"]["home"] == "Accueil"
        assert nested["nav"]["about"] == "A propos"
        # Untranslated should be empty
        assert nested["footer"]["copy"] == ""

        # 8. Delete de
        r = delete(f"/api/v1/projects/{pid}/locales/de")
        assert r.status_code == 204
        r = get(f"/api/v1/projects/{pid}/stats")
        locales_in_stats = [s["locale"] for s in r.json()["data"]]
        assert "de" not in locales_in_stats
        assert "en" in locales_in_stats
        assert "fr" in locales_in_stats


class TestImportExportRoundtrip:
    """Pattern 5: Import/export correctness and merge semantics."""

    def test_import_export_roundtrip(self):
        """
        1. Import json data with 3 keys
        2. Export as json → verify exact roundtrip
        3. Import again with 1 updated, 1 new → verify merge counts
        4. Export → verify merged state
        5. Export nested_json → verify dot nesting
        """
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        # 1. Import
        data = {"app.title": "My App", "app.desc": "Description", "footer": "Footer"}
        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json", "data": data
        })
        assert r.status_code == 200
        res = r.json()["data"]
        assert res["termsCreated"] == 3
        assert res["translationsCreated"] == 3

        # 2. Export json
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "json"})
        assert r.status_code == 200
        exported = r.json()
        assert exported["app.title"] == "My App"
        assert exported["app.desc"] == "Description"
        assert exported["footer"] == "Footer"

        # 3. Merge import
        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "json",
            "data": {"app.title": "Updated App", "new.key": "New Value"}
        })
        res = r.json()["data"]
        assert res["termsCreated"] == 1
        assert res["translationsCreated"] == 1
        assert res["translationsUpdated"] == 1

        # 4. Export merged state
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "json"})
        exported = r.json()
        assert exported["app.title"] == "Updated App"
        assert exported["app.desc"] == "Description"  # untouched
        assert exported["footer"] == "Footer"  # untouched
        assert exported["new.key"] == "New Value"

        # 5. Nested export
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "nested_json"})
        nested = r.json()
        assert nested["app"]["title"] == "Updated App"
        assert nested["app"]["desc"] == "Description"
        assert nested["footer"] == "Footer"
        assert nested["new"]["key"] == "New Value"


class TestMemberRBACWorkflow:
    """Pattern 4+6: Full RBAC lifecycle."""

    def test_rbac_lifecycle(self):
        """
        1. User1 creates project (admin)
        2. User1 adds User2 as viewer
        3. User2 can list terms but not create
        4. User1 promotes User2 to editor
        5. User2 can now create terms
        6. User2 still can't manage locales or members
        7. User1 adds User3 as admin
        8. User3 can add locales and members
        9. User1 cannot remove themselves (owner)
        10. User3 cannot remove User1 (owner)
        """
        p = make_project(headers=H1)
        pid = p["id"]

        # 2.
        r = post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "viewer"})
        assert r.status_code == 201

        # 3. Viewer can read
        r = get(f"/api/v1/projects/{pid}/terms", headers=H2)
        assert r.status_code == 200
        # Viewer cannot create
        r = post(f"/api/v1/projects/{pid}/terms", {"value": "nope"}, headers=H2)
        assert r.status_code == 403

        # 4. Promote to editor
        r = patch(f"/api/v1/projects/{pid}/members/{USER2_KEY}", {"role": "editor"})
        assert r.status_code == 200
        assert r.json()["data"]["role"] == "editor"

        # 5. Editor can create terms
        r = post(f"/api/v1/projects/{pid}/terms", {"value": "editor.made"}, headers=H2)
        assert r.status_code == 201

        # 6. Editor can't manage locales
        r = post(f"/api/v1/projects/{pid}/locales", {"code": "it"}, headers=H2)
        assert r.status_code == 403
        # Editor can't manage members
        r = post(f"/api/v1/projects/{pid}/members", {"userId": USER3_KEY, "role": "viewer"}, headers=H2)
        assert r.status_code == 403

        # 7. Add User3 as admin
        r = post(f"/api/v1/projects/{pid}/members", {"userId": USER3_KEY, "role": "admin"})
        assert r.status_code == 201

        # 8. User3 (admin) can add locale
        r = post(f"/api/v1/projects/{pid}/locales", {"code": "ja"}, headers=H3)
        assert r.status_code == 201

        # 9. Owner cannot remove self
        r = delete(f"/api/v1/projects/{pid}/members/{USER1_KEY}")
        assert r.status_code == 400

        # 10. User3 cannot remove owner
        r = delete(f"/api/v1/projects/{pid}/members/{USER1_KEY}", headers=H3)
        assert r.status_code == 400


class TestProjectCascadeDelete:
    """Pattern 7: Full cascade on project delete."""

    def test_project_delete_cascades_all(self):
        """
        1. Create project with locales, terms, translations, labels, members
        2. Delete project
        3. Verify project gone (404)
        4. Verify member can no longer see project
        """
        p = make_project(headers=H1)
        pid = p["id"]

        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})
        t = post(f"/api/v1/projects/{pid}/terms", {"value": "cascade.key"}).json()["data"]["id"]
        patch(f"/api/v1/projects/{pid}/translations/en/{t}", {"value": "trans"})
        post(f"/api/v1/projects/{pid}/labels", {"value": "lbl"})
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "viewer"})

        # Verify accessible before
        assert get(f"/api/v1/projects/{pid}", headers=H2).status_code == 200

        # Delete
        r = delete(f"/api/v1/projects/{pid}")
        assert r.status_code == 204

        # Project gone
        assert get(f"/api/v1/projects/{pid}").status_code == 404
        # Member can't see it either
        assert get(f"/api/v1/projects/{pid}", headers=H2).status_code == 404

        # Project not in list
        r = get("/api/v1/projects")
        ids = [proj["id"] for proj in r.json()["data"]]
        assert pid not in ids


class TestTermLabelWorkflow:
    """Pattern 2+7+8: Labels on terms with cascade behavior."""

    def test_label_term_lifecycle(self):
        """
        1. Create project
        2. Create 2 labels
        3. Create term
        4. Attach both labels to term
        5. Verify term shows both labels
        6. Remove one label from term
        7. Verify only one label remains
        8. Delete the other label entirely
        9. Verify term has no labels
        10. Duplicate label attachment → 400
        """
        p = make_project()
        pid = p["id"]

        # 2. Labels
        l1 = post(f"/api/v1/projects/{pid}/labels", {"value": "ui", "color": "#ff0000"}).json()["data"]
        l2 = post(f"/api/v1/projects/{pid}/labels", {"value": "menu", "color": "#00ff00"}).json()["data"]

        # 3. Term
        t = post(f"/api/v1/projects/{pid}/terms", {"value": "nav.item"}).json()["data"]
        tid = t["id"]

        # 4. Attach both
        r = post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": l1["id"]})
        assert r.status_code == 200
        r = post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": l2["id"]})
        assert r.status_code == 200

        # 5. Both labels present
        r = get(f"/api/v1/projects/{pid}/terms/{tid}")
        labels = r.json()["data"]["labels"]
        label_ids = [l["id"] for l in labels]
        assert l1["id"] in label_ids
        assert l2["id"] in label_ids

        # 6. Remove l1
        r = delete(f"/api/v1/projects/{pid}/terms/{tid}/labels/{l1['id']}")
        assert r.status_code == 204

        # 7. Only l2 remains
        r = get(f"/api/v1/projects/{pid}/terms/{tid}")
        labels = r.json()["data"]["labels"]
        label_ids = [l["id"] for l in labels]
        assert l1["id"] not in label_ids
        assert l2["id"] in label_ids

        # 8. Delete l2 entirely
        r = delete(f"/api/v1/projects/{pid}/labels/{l2['id']}")
        assert r.status_code == 204

        # 9. Term has no labels
        r = get(f"/api/v1/projects/{pid}/terms/{tid}")
        assert r.json()["data"]["labels"] == []

        # 10. Re-create label and test duplicate
        l3 = post(f"/api/v1/projects/{pid}/labels", {"value": "dup-test"}).json()["data"]
        post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": l3["id"]})
        r = post(f"/api/v1/projects/{pid}/terms/{tid}/labels", {"labelId": l3["id"]})
        assert r.status_code == 400


class TestUntranslatedBehavior:
    """Pattern 5: Untranslated terms return empty string, not 404."""

    def test_untranslated_workflow(self):
        """
        1. Create project + locale + terms
        2. GET single untranslated → empty string
        3. GET all translations for locale → all terms present with empty
        4. Set one translation
        5. GET all → one has value, rest still empty
        6. Set to empty string explicitly → stats should not count it
        """
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        t1 = post(f"/api/v1/projects/{pid}/terms", {"value": "k1"}).json()["data"]["id"]
        t2 = post(f"/api/v1/projects/{pid}/terms", {"value": "k2"}).json()["data"]["id"]
        t3 = post(f"/api/v1/projects/{pid}/terms", {"value": "k3"}).json()["data"]["id"]

        # 2. Single untranslated
        r = get(f"/api/v1/projects/{pid}/translations/en/{t1}")
        assert r.status_code == 200
        assert r.json()["data"]["value"] == ""
        assert r.json()["data"]["termId"] == t1

        # 3. All translations
        r = get(f"/api/v1/projects/{pid}/translations/en")
        assert r.status_code == 200
        trans = r.json()["data"]
        ids = [t["termId"] for t in trans]
        assert t1 in ids and t2 in ids and t3 in ids
        for t in trans:
            assert t["value"] == ""

        # 4. Set one
        patch(f"/api/v1/projects/{pid}/translations/en/{t1}", {"value": "Hello"})

        # 5. One translated, rest empty
        r = get(f"/api/v1/projects/{pid}/translations/en")
        trans_map = {t["termId"]: t["value"] for t in r.json()["data"]}
        assert trans_map[t1] == "Hello"
        assert trans_map[t2] == ""
        assert trans_map[t3] == ""

        # 6. Set to empty explicitly → not counted in stats
        patch(f"/api/v1/projects/{pid}/translations/en/{t1}", {"value": ""})
        r = get(f"/api/v1/projects/{pid}/stats")
        stats = r.json()["data"]
        en = next(s for s in stats if s["locale"] == "en")
        assert en["translatedCount"] == 0


class TestNestedJsonImportExport:
    """Pattern 5: Nested JSON import/export."""

    def test_nested_json_roundtrip(self):
        """
        1. Import nested_json with deep nesting
        2. Verify terms created with dot notation
        3. Export as nested_json → verify structure matches input
        4. Export as flat json → verify dot notation keys
        """
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        nested_data = {
            "app": {
                "header": {"title": "Main Title", "subtitle": "Sub"},
                "footer": "Footer Text"
            },
            "common": {"ok": "OK", "cancel": "Cancel"}
        }

        # 1.
        r = post(f"/api/v1/projects/{pid}/imports", {
            "locale": "en", "format": "nested_json", "data": nested_data
        })
        assert r.status_code == 200
        assert r.json()["data"]["termsCreated"] == 5

        # 2. Verify terms
        r = get(f"/api/v1/projects/{pid}/terms")
        values = sorted([t["value"] for t in r.json()["data"]])
        assert "app.footer" in values
        assert "app.header.title" in values
        assert "app.header.subtitle" in values
        assert "common.ok" in values
        assert "common.cancel" in values

        # 3. Export nested
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "nested_json"})
        assert r.status_code == 200
        exported = r.json()
        assert exported["app"]["header"]["title"] == "Main Title"
        assert exported["app"]["header"]["subtitle"] == "Sub"
        assert exported["app"]["footer"] == "Footer Text"
        assert exported["common"]["ok"] == "OK"
        assert exported["common"]["cancel"] == "Cancel"

        # 4. Export flat
        r = get(f"/api/v1/projects/{pid}/exports", params={"locale": "en", "format": "json"})
        flat = r.json()
        assert flat["app.header.title"] == "Main Title"
        assert flat["common.ok"] == "OK"


class TestMultiUserProjectSharing:
    """Pattern 6: Project sharing and access control."""

    def test_sharing_and_access_workflow(self):
        """
        1. User1 creates project
        2. User2 cannot see project
        3. User1 adds User2 as viewer
        4. User2 can now see project and read terms
        5. User2 cannot modify terms
        6. User1 adds User3 as editor
        7. User3 can create terms
        8. User3 can set translations
        9. User3 cannot remove members
        10. Stats accessible to all members
        """
        p = make_project(headers=H1)
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})
        post(f"/api/v1/projects/{pid}/terms", {"value": "shared.key"})

        # 2. User2 can't see
        r = get(f"/api/v1/projects/{pid}", headers=H2)
        assert r.status_code == 404

        # 3. Add User2
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "viewer"})

        # 4. User2 can read
        r = get(f"/api/v1/projects/{pid}/terms", headers=H2)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1

        # 5. User2 cannot create
        r = post(f"/api/v1/projects/{pid}/terms", {"value": "viewer.attempt"}, headers=H2)
        assert r.status_code == 403

        # 6. Add User3 as editor
        post(f"/api/v1/projects/{pid}/members", {"userId": USER3_KEY, "role": "editor"})

        # 7. User3 can create
        r = post(f"/api/v1/projects/{pid}/terms", {"value": "editor.key"}, headers=H3)
        assert r.status_code == 201
        tid = r.json()["data"]["id"]

        # 8. User3 can translate
        r = patch(f"/api/v1/projects/{pid}/translations/en/{tid}", {"value": "Translated"}, headers=H3)
        assert r.status_code == 200

        # 9. User3 cannot manage members
        r = delete(f"/api/v1/projects/{pid}/members/{USER2_KEY}", headers=H3)
        assert r.status_code == 403

        # 10. Stats accessible to all
        for h in [H1, H2, H3]:
            r = get(f"/api/v1/projects/{pid}/stats", headers=h)
            assert r.status_code == 200


class TestOwnerProtection:
    """Pattern 4+8: Owner cannot be removed."""

    def test_owner_protection_workflow(self):
        """
        1. User1 creates project (becomes owner)
        2. User1 adds User2 as admin
        3. User2 tries to remove User1 → 400
        4. User1 tries to remove self → 400
        5. User2 can be removed by User1
        6. Re-add User2, User2 can't remove self
        """
        p = make_project(headers=H1)
        pid = p["id"]

        # 2.
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "admin"})

        # 3.
        r = delete(f"/api/v1/projects/{pid}/members/{USER1_KEY}", headers=H2)
        assert r.status_code == 400

        # 4.
        r = delete(f"/api/v1/projects/{pid}/members/{USER1_KEY}")
        assert r.status_code == 400

        # 5.
        r = delete(f"/api/v1/projects/{pid}/members/{USER2_KEY}")
        assert r.status_code == 204

        # 6.
        post(f"/api/v1/projects/{pid}/members", {"userId": USER2_KEY, "role": "admin"})
        r = delete(f"/api/v1/projects/{pid}/members/{USER2_KEY}", headers=H2)
        assert r.status_code == 400


class TestTranslationLocaleEntryFields:
    """Pattern 1: Verify TranslationLocaleEntry fields (termId, termValue, value)."""

    def test_translation_locale_entry_has_correct_fields(self):
        """
        1. Create terms
        2. Get translations for locale
        3. Each entry must have termId, termValue, value
        """
        p = make_project()
        pid = p["id"]
        post(f"/api/v1/projects/{pid}/locales", {"code": "en"})

        t1 = post(f"/api/v1/projects/{pid}/terms", {"value": "greet.hello"}).json()["data"]
        t2 = post(f"/api/v1/projects/{pid}/terms", {"value": "greet.bye"}).json()["data"]

        patch(f"/api/v1/projects/{pid}/translations/en/{t1['id']}", {"value": "Hello"})

        r = get(f"/api/v1/projects/{pid}/translations/en")
        assert r.status_code == 200
        entries = r.json()["data"]
        assert len(entries) >= 2

        for entry in entries:
            assert "termId" in entry
            assert "termValue" in entry
            assert "value" in entry

        # Find specific entries
        e1 = next(e for e in entries if e["termId"] == t1["id"])
        assert e1["termValue"] == "greet.hello"
        assert e1["value"] == "Hello"

        e2 = next(e for e in entries if e["termId"] == t2["id"])
        assert e2["termValue"] == "greet.bye"
        assert e2["value"] == ""
