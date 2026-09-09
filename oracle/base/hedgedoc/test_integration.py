"""
L2 Integration Tests for HedgeDoc API.
Adversarial tests targeting common LLM implementation bugs:
- camelCase field naming
- Nested/related data completeness
- Filtering/pagination actually working
- Correct status codes (201/204/404)
- Computed values verified with multiple inputs
"""
import os
import uuid
import requests
import pytest

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user(username=None, display_name=None):
    username = username or unique("user")
    display_name = display_name or f"Display {username}"
    resp = requests.post(f"{API}/users", json={
        "username": username,
        "displayName": display_name,
        "password": "testpass123"
    })
    assert resp.status_code == 201
    data = resp.json()
    return data, data["apiKey"], {"X-API-Key": data["apiKey"]}


def create_note(headers, content="# Test\nHello", alias=None, permission="private", tags=None):
    body = {"content": content, "permission": permission}
    if alias:
        body["alias"] = alias
    if tags:
        body["tags"] = tags
    resp = requests.post(f"{API}/notes", json=body, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# =============================================================================
# L2 TESTS — Integration (20-30 tests)
# =============================================================================


class TestNoteFieldCasing:
    """Pattern 1: Verify exact camelCase field names in note responses."""

    def test_create_note_returns_all_camelcase_fields(self):
        """Verify note creation returns all expected camelCase fields."""
        _, _, headers = create_user()
        alias = unique("alias")
        resp = requests.post(f"{API}/notes", json={
            "content": "# My Note\nBody here",
            "alias": alias,
            "tags": ["tag1", "tag2"],
            "permission": "public"
        }, headers=headers)
        assert resp.status_code == 201
        note = resp.json()
        # Verify exact camelCase fields exist
        assert "id" in note
        assert "title" in note
        assert "content" in note
        assert "tags" in note
        assert "permission" in note
        assert "ownerId" in note
        assert "primaryAlias" in note
        assert "createdAt" in note
        assert "updatedAt" in note
        # Verify values
        assert note["title"] == "My Note"
        assert note["content"] == "# My Note\nBody here"
        assert set(note["tags"]) == {"tag1", "tag2"}
        assert note["permission"] == "public"
        assert note["primaryAlias"] == alias

    def test_get_note_preserves_camelcase_fields(self):
        """Pattern 1: GET response must use camelCase, not snake_case."""
        user, _, headers = create_user()
        alias = unique("get_alias")
        note = create_note(headers, content="# Retrieve Me\nContent",
                           alias=alias, tags=["x"], permission="public")
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Exact casing from openapi
        assert data["ownerId"] == user["id"]
        assert data["primaryAlias"] == alias
        assert data["createdAt"] is not None
        assert data["updatedAt"] is not None
        assert isinstance(data["tags"], list)
        assert "x" in data["tags"]

    def test_user_response_camelcase(self):
        """Pattern 1: User response must use displayName and photoUrl."""
        user, _, headers = create_user(display_name="CamelTest")
        resp = requests.get(f"{API}/users/{user['id']}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "displayName" in data
        assert "photoUrl" in data or data.get("photoUrl") is None
        assert "createdAt" in data
        assert data["displayName"] == "CamelTest"
        # Verify snake_case keys NOT present
        assert "display_name" not in data
        assert "photo_url" not in data
        assert "created_at" not in data


class TestTitleExtraction:
    """Pattern 5: Title extraction logic must actually work with different inputs."""

    def test_title_from_first_h1_with_spaces(self):
        _, _, headers = create_user()
        note = create_note(headers, content="#   Spaced Title  \nBody")
        # Title should be trimmed from first # heading
        assert note["title"].strip() == "Spaced Title"

    def test_title_untitled_when_no_h1(self):
        _, _, headers = create_user()
        note = create_note(headers, content="## Only H2\nNo H1 here")
        assert note["title"] == "Untitled"

    def test_title_updates_on_content_change(self):
        """When content is updated, title should reflect new first H1."""
        _, _, headers = create_user()
        note = create_note(headers, content="# Original Title\nBody")
        assert note["title"] == "Original Title"

        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Updated Title\nNew body"
        }, headers=headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated Title"

    def test_title_becomes_untitled_after_h1_removed(self):
        """If content update removes H1, title becomes Untitled."""
        _, _, headers = create_user()
        note = create_note(headers, content="# Has Title\nBody")
        assert note["title"] == "Has Title"

        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "No more heading\nJust text"
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Untitled"


class TestFilteringAndListing:
    """Pattern 3: Filtering/tag query actually filters results."""

    def test_tag_filter_excludes_non_matching(self):
        """Create notes with different tags, filter should only return matching."""
        _, _, headers = create_user()
        tag_unique = unique("tag")
        create_note(headers, content="# A\nA", tags=[tag_unique, "common"])
        create_note(headers, content="# B\nB", tags=[tag_unique])
        create_note(headers, content="# C\nC", tags=["other_only"])

        resp = requests.get(f"{API}/notes", params={"tag": tag_unique}, headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        # Should find exactly 2 notes with our unique tag
        assert len(notes) == 2
        for n in notes:
            assert tag_unique in n["tags"]

    def test_tag_filter_returns_empty_for_nonexistent_tag(self):
        _, _, headers = create_user()
        create_note(headers, content="# A\nBody", tags=["exists"])
        resp = requests.get(f"{API}/notes", params={"tag": "nonexistent_xyz_999"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_notes_only_shows_accessible(self):
        """Pattern 6: User B should not see User A's private notes in list."""
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        priv_note = create_note(headers_a, content="# Private\nSecret", permission="private")
        pub_note = create_note(headers_a, content="# Public\nOpen", permission="public")

        resp = requests.get(f"{API}/notes", headers=headers_b)
        assert resp.status_code == 200
        note_ids = [n["id"] for n in resp.json()]
        assert pub_note["id"] in note_ids
        assert priv_note["id"] not in note_ids

    def test_tags_endpoint_only_from_accessible_notes(self):
        """Pattern 6: Tags endpoint should only include tags from accessible notes."""
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        secret_tag = unique("secret_tag")
        public_tag = unique("public_tag")
        create_note(headers_a, content="# S\nS", tags=[secret_tag], permission="private")
        create_note(headers_a, content="# P\nP", tags=[public_tag], permission="public")

        resp = requests.get(f"{API}/tags", headers=headers_b)
        assert resp.status_code == 200
        tags = resp.json()
        assert public_tag in tags
        assert secret_tag not in tags


class TestRevisionIntegrity:
    """Pattern 2+5: Revisions must contain actual content, not empty stubs."""

    def test_revision_content_matches_historical_state(self):
        """Each revision must contain the actual content at that point in time."""
        _, _, headers = create_user()
        note = create_note(headers, content="# V1\nFirst version content")
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V2\nSecond version content"
        }, headers=headers)
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V3\nThird version content"
        }, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
        assert resp.status_code == 200
        revisions = resp.json()
        assert len(revisions) >= 2
        assert {"# V1\nFirst version content", "# V2\nSecond version content"} <= {rev["content"] for rev in revisions}

        # Verify each revision has required fields
        for rev in revisions:
            assert "id" in rev
            assert "content" in rev
            assert "title" in rev
            assert "authorId" in rev
            assert "createdAt" in rev
            assert rev["content"] is not None
            assert len(rev["content"]) > 0

    def test_revision_author_id_correct_for_different_users(self):
        """Revisions by different users should record correct authorId."""
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, content="# Init\nOriginal", permission="limited")

        # Grant B write access
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"], "level": "write"
        }, headers=headers_a)

        # B edits the note
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edited\nBy user B"
        }, headers=headers_b)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers_a)
        revisions = resp.json()
        # Last revision should be from user B
        last_rev = revisions[-1]
        assert last_rev["authorId"] == user_b["id"]


class TestAliasIntegrity:
    """Pattern 1+4: Alias operations return correct fields and status codes."""

    def test_alias_create_returns_201_with_correct_fields(self):
        _, _, headers = create_user()
        note = create_note(headers, alias=unique("first"))
        new_alias = unique("second")
        resp = requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": new_alias
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["alias"] == new_alias
        assert data["noteId"] == note["id"]
        assert "isPrimary" in data
        assert data["isPrimary"] is False  # New alias is not primary by default

    def test_alias_primary_switch_demotes_old_primary(self):
        """When setting new primary, old primary should become non-primary."""
        _, _, headers = create_user()
        alias1 = unique("pri1")
        note = create_note(headers, alias=alias1)
        alias2 = unique("pri2")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={"alias": alias2}, headers=headers)

        # Set alias2 as primary
        resp = requests.put(f"{API}/aliases/{alias2}", json={"isPrimary": True}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["isPrimary"] is True

        # Verify alias1 is no longer primary
        resp = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
        aliases = resp.json()
        for a in aliases:
            if a["alias"] == alias1:
                assert a["isPrimary"] is False
            elif a["alias"] == alias2:
                assert a["isPrimary"] is True

    def test_delete_alias_returns_204(self):
        """Pattern 4: DELETE alias must return 204, not 200."""
        _, _, headers = create_user()
        alias1 = unique("keep")
        note = create_note(headers, alias=alias1)
        alias2 = unique("del")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={"alias": alias2}, headers=headers)

        resp = requests.delete(f"{API}/aliases/{alias2}", headers=headers)
        assert resp.status_code == 204


class TestGroupOperations:
    """Pattern 1+2: Group responses have correct field names and members list."""

    def test_group_create_returns_correct_fields(self):
        user, _, headers = create_user()
        name = unique("grp")
        resp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "My Group"
        }, headers=headers)
        assert resp.status_code == 201
        grp = resp.json()
        assert "id" in grp
        assert grp["name"] == name
        assert grp["displayName"] == "My Group"
        assert grp["ownerId"] == user["id"]
        assert "members" in grp
        assert isinstance(grp["members"], list)

    def test_group_members_list_updates_correctly(self):
        """Pattern 2: members array must actually contain added users."""
        _, _, headers_a = create_user()
        user_b, _, _ = create_user()
        user_c, _, _ = create_user()

        grp = requests.post(f"{API}/groups", json={
            "name": unique("grp"), "displayName": "G"
        }, headers=headers_a).json()

        # Add B
        resp = requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)
        assert resp.status_code == 200
        assert user_b["id"] in resp.json()["members"]

        # Add C
        resp = requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_c["id"]
        }, headers=headers_a)
        assert resp.status_code == 200
        members = resp.json()["members"]
        assert user_b["id"] in members
        assert user_c["id"] in members

    def test_group_member_removal_reflected(self):
        """After removal, member should not appear in group members list."""
        _, _, headers_a = create_user()
        user_b, _, _ = create_user()

        grp = requests.post(f"{API}/groups", json={
            "name": unique("grp"), "displayName": "G"
        }, headers=headers_a).json()

        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        resp = requests.delete(
            f"{API}/groups/{grp['id']}/members/{user_b['id']}", headers=headers_a
        )
        assert resp.status_code == 200
        assert user_b["id"] not in resp.json()["members"]

    def test_list_groups_only_shows_user_groups(self):
        """Pattern 6: User should only see groups they belong to."""
        _, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        grp_name_a = unique("grp_a")
        requests.post(f"{API}/groups", json={
            "name": grp_name_a, "displayName": "A's Group"
        }, headers=headers_a)

        grp_name_b = unique("grp_b")
        requests.post(f"{API}/groups", json={
            "name": grp_name_b, "displayName": "B's Group"
        }, headers=headers_b)

        # B should see their own group but not A's
        resp = requests.get(f"{API}/groups", headers=headers_b)
        assert resp.status_code == 200
        group_names = [g["name"] for g in resp.json()]
        assert grp_name_b in group_names
        assert grp_name_a not in group_names


class TestMediaOperations:
    """Pattern 1+4: Media upload and responses."""

    def test_media_upload_returns_201_with_all_fields(self):
        user, _, headers = create_user()
        note = create_note(headers)
        fname = f"{unique('img')}.png"
        files = {"file": (fname, b"PNG fake data here", "image/png")}
        resp = requests.post(f"{API}/notes/{note['id']}/media", files=files, headers=headers)
        assert resp.status_code == 201
        media = resp.json()
        assert "id" in media
        assert media["noteId"] == note["id"]
        assert media["fileName"] == fname
        assert "url" in media
        assert media["url"] is not None and len(media["url"]) > 0
        assert media["userId"] == user["id"]
        assert "createdAt" in media

    def test_media_delete_returns_204(self):
        """Pattern 4: DELETE media must return 204."""
        _, _, headers = create_user()
        note = create_note(headers)
        files = {"file": ("del.png", b"data", "image/png")}
        media = requests.post(
            f"{API}/notes/{note['id']}/media", files=files, headers=headers
        ).json()

        resp = requests.delete(f"{API}/media/{media['id']}", headers=headers)
        assert resp.status_code == 204

    def test_media_list_returns_correct_entries(self):
        """Pattern 2: List media should return all uploaded items with correct fields."""
        _, _, headers = create_user()
        note = create_note(headers)
        fname1 = f"{unique('f1')}.png"
        fname2 = f"{unique('f2')}.jpg"
        requests.post(f"{API}/notes/{note['id']}/media",
                      files={"file": (fname1, b"data1", "image/png")}, headers=headers)
        requests.post(f"{API}/notes/{note['id']}/media",
                      files={"file": (fname2, b"data2", "image/jpeg")}, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/media", headers=headers)
        assert resp.status_code == 200
        media_list = resp.json()
        assert len(media_list) == 2
        fnames = [m["fileName"] for m in media_list]
        assert fname1 in fnames
        assert fname2 in fnames
        for m in media_list:
            assert "id" in m
            assert "noteId" in m
            assert "url" in m
            assert "userId" in m
            assert "createdAt" in m


class TestHistoryFields:
    """Pattern 1+5: History entries have correct fields and auto-update behavior."""

    def test_history_entry_has_correct_fields(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# History Test\nBody")
        requests.get(f"{API}/notes/{note['id']}", headers=headers)

        resp = requests.get(f"{API}/me/history", headers=headers)
        assert resp.status_code == 200
        history = resp.json()
        entry = next(h for h in history if h["noteId"] == note["id"])
        assert "noteId" in entry
        assert "title" in entry
        assert "updatedAt" in entry
        assert "pinned" in entry
        assert entry["title"] == "History Test"
        assert entry["pinned"] is False

    def test_history_pin_persists(self):
        """Pin state must be retrievable after setting."""
        _, _, headers = create_user()
        note = create_note(headers, content="# Pin Me\nContent")
        requests.get(f"{API}/notes/{note['id']}", headers=headers)

        resp = requests.put(f"{API}/me/history/{note['id']}", json={"pinned": True}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["pinned"] is True

        # Verify via GET history
        resp = requests.get(f"{API}/me/history", headers=headers)
        entry = next(h for h in resp.json() if h["noteId"] == note["id"])
        assert entry["pinned"] is True

    def test_history_isolated_between_users(self):
        """Pattern 6: User A's history should not appear in User B's history."""
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, content="# Shared\nNote", permission="public")

        # Only A accesses it
        requests.get(f"{API}/notes/{note['id']}", headers=headers_a)

        # B should not have it in history
        resp = requests.get(f"{API}/me/history", headers=headers_b)
        note_ids = [h["noteId"] for h in resp.json()]
        assert note["id"] not in note_ids


class TestPermissionInfoFields:
    """Pattern 1+2: Permission info response contains all nested arrays."""

    def test_permission_info_contains_user_and_group_arrays(self):
        user_a, _, headers_a = create_user()
        user_b, _, _ = create_user()
        note = create_note(headers_a, permission="limited")

        # Grant user permission
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"], "level": "write"
        }, headers=headers_a)

        # Create group and grant
        grp = requests.post(f"{API}/groups", json={
            "name": unique("grp"), "displayName": "G"
        }, headers=headers_a).json()
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"], "level": "read"
        }, headers=headers_a)

        resp = requests.get(f"{API}/notes/{note['id']}/permissions", headers=headers_a)
        assert resp.status_code == 200
        perm = resp.json()
        assert perm["noteId"] == note["id"]
        assert perm["permission"] == "limited"
        assert perm["ownerId"] == user_a["id"]
        assert "userPermissions" in perm
        assert "groupPermissions" in perm
        assert isinstance(perm["userPermissions"], list)
        assert isinstance(perm["groupPermissions"], list)
        # Verify structure of nested objects
        up = next(u for u in perm["userPermissions"] if u["userId"] == user_b["id"])
        assert up["level"] == "write"
        gp = next(g for g in perm["groupPermissions"] if g["groupId"] == grp["id"])
        assert gp["level"] == "read"


class TestImportExportIntegration:
    """Pattern 4+5: Import/export correctness."""

    def test_import_returns_201_with_complete_note(self):
        _, _, headers = create_user()
        alias = unique("imp")
        resp = requests.post(f"{API}/notes/import", json={
            "content": "# Imported\nImported body",
            "alias": alias,
            "tags": ["imported", "test"]
        }, headers=headers)
        assert resp.status_code == 201
        note = resp.json()
        assert note["title"] == "Imported"
        assert note["content"] == "# Imported\nImported body"
        assert note["primaryAlias"] == alias
        assert set(note["tags"]) == {"imported", "test"}
        assert "id" in note
        assert "ownerId" in note
        assert "createdAt" in note

    def test_export_returns_exact_content(self):
        """Export must return the exact markdown, not modified."""
        _, _, headers = create_user()
        content = "# Export Exact\n\nParagraph with **bold** and `code`.\n\n- item1\n- item2"
        note = create_note(headers, content=content)

        resp = requests.get(f"{API}/notes/{note['id']}/export/markdown", headers=headers)
        assert resp.status_code == 200
        assert resp.text == content


class TestStatusCodes:
    """Pattern 4: Verify exact status codes throughout."""

    def test_create_user_returns_201(self):
        resp = requests.post(f"{API}/users", json={
            "username": unique("u"), "displayName": "D", "password": "p"
        })
        assert resp.status_code == 201

    def test_delete_user_returns_204(self):
        user, _, headers = create_user()
        resp = requests.delete(f"{API}/users/{user['id']}", headers=headers)
        assert resp.status_code == 204

    def test_delete_note_returns_204(self):
        _, _, headers = create_user()
        note = create_note(headers)
        resp = requests.delete(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.status_code == 204

    def test_get_nonexistent_note_returns_404(self):
        _, _, headers = create_user()
        resp = requests.get(f"{API}/notes/{uuid.uuid4().hex}", headers=headers)
        assert resp.status_code == 404

    def test_get_nonexistent_user_returns_404(self):
        _, _, headers = create_user()
        resp = requests.get(f"{API}/users/{uuid.uuid4().hex}", headers=headers)
        assert resp.status_code == 404

    def test_get_nonexistent_group_returns_404(self):
        _, _, headers = create_user()
        resp = requests.get(f"{API}/groups/{uuid.uuid4().hex}", headers=headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_history_entry_returns_404(self):
        _, _, headers = create_user()
        resp = requests.delete(f"{API}/me/history/{uuid.uuid4().hex}", headers=headers)
        assert resp.status_code == 404
