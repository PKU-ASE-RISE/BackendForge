"""
Correctness tests for HedgeDoc collaborative markdown editor API.
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user(username=None, display_name=None):
    """Helper to register a user and return (user_data, api_key, headers)."""
    username = username or unique("user")
    display_name = display_name or f"Display {username}"
    resp = requests.post(f"{API}/users", json={
        "username": username,
        "displayName": display_name,
        "password": "testpass123"
    })
    assert resp.status_code == 201, f"Failed to create user: {resp.text}"
    data = resp.json()
    api_key = data["apiKey"]
    headers = {"X-API-Key": api_key}
    return data, api_key, headers


def create_note(headers, content="# Test\nHello", alias=None, permission="private", tags=None):
    """Helper to create a note."""
    body = {"content": content, "permission": permission}
    if alias:
        body["alias"] = alias
    if tags:
        body["tags"] = tags
    resp = requests.post(f"{API}/notes", json=body, headers=headers)
    assert resp.status_code == 201, f"Failed to create note: {resp.text}"
    return resp.json()


# =============================================================================
# AUTH TESTS
# =============================================================================


class TestAuth:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{API}/notes")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self):
        resp = requests.get(f"{API}/notes", headers={"X-API-Key": "invalid-key"})
        assert resp.status_code == 401

    def test_valid_api_key_succeeds(self):
        _, _, headers = create_user()
        resp = requests.get(f"{API}/notes", headers=headers)
        assert resp.status_code == 200


# =============================================================================
# USER TESTS
# =============================================================================


class TestUsers:
    def test_create_user(self):
        data, api_key, _ = create_user()
        assert "id" in data
        assert "apiKey" in data
        assert data["username"] is not None

    def test_create_duplicate_username_409(self):
        username = unique("dup")
        create_user(username=username)
        resp = requests.post(f"{API}/users", json={
            "username": username,
            "displayName": "Dup",
            "password": "pass123"
        })
        assert resp.status_code == 409

    def test_get_user_profile(self):
        data, _, headers = create_user()
        resp = requests.get(f"{API}/users/{data['id']}", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["username"] == data["username"]
        assert profile["displayName"] == data["displayName"]

    def test_update_user_profile(self):
        data, _, headers = create_user()
        resp = requests.put(f"{API}/users/{data['id']}", json={
            "displayName": "New Name",
            "photoUrl": "https://example.com/photo.jpg"
        }, headers=headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["displayName"] == "New Name"
        assert updated["photoUrl"] == "https://example.com/photo.jpg"

    def test_cannot_update_other_user(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        resp = requests.put(f"{API}/users/{user_a['id']}", json={
            "displayName": "Hacked"
        }, headers=headers_b)
        assert resp.status_code == 403

    def test_delete_user(self):
        data, _, headers = create_user()
        resp = requests.delete(f"{API}/users/{data['id']}", headers=headers)
        assert resp.status_code == 204
        # Verify user no longer exists
        resp2 = requests.get(f"{API}/users/{data['id']}", headers=headers)
        assert resp2.status_code in [401, 404]


# =============================================================================
# NOTE CRUD TESTS
# =============================================================================


class TestNoteCRUD:
    def test_create_note_with_title_extraction(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# My Title\nSome content")
        assert note["title"] == "My Title"
        assert note["content"] == "# My Title\nSome content"
        assert "id" in note

    def test_create_note_untitled(self):
        _, _, headers = create_user()
        note = create_note(headers, content="No heading here")
        assert note["title"] == "Untitled"

    def test_create_note_title_from_first_h1(self):
        _, _, headers = create_user()
        content = "Some intro\n# Actual Title\n## Sub heading\nBody"
        note = create_note(headers, content=content)
        assert note["title"] == "Actual Title"

    def test_create_note_with_alias(self):
        _, _, headers = create_user()
        alias = unique("slug")
        note = create_note(headers, alias=alias)
        assert note["primaryAlias"] == alias

    def test_get_note_by_id(self):
        _, _, headers = create_user()
        note = create_note(headers)
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note["id"]

    def test_get_note_by_alias(self):
        _, _, headers = create_user()
        alias = unique("alias")
        note = create_note(headers, alias=alias)
        resp = requests.get(f"{API}/notes/{alias}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note["id"]

    def test_update_note_content(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# Old\nOld content")
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# New Title\nNew content"
        }, headers=headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "New Title"
        assert updated["content"] == "# New Title\nNew content"

    def test_update_note_metadata(self):
        _, _, headers = create_user()
        note = create_note(headers, tags=["old"])
        resp = requests.patch(f"{API}/notes/{note['id']}", json={
            "tags": ["new", "updated"],
            "permission": "public"
        }, headers=headers)
        assert resp.status_code == 200
        updated = resp.json()
        assert set(updated["tags"]) == {"new", "updated"}
        assert updated["permission"] == "public"

    def test_delete_note(self):
        _, _, headers = create_user()
        note = create_note(headers)
        resp = requests.delete(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.status_code == 204
        resp2 = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp2.status_code == 404

    def test_list_notes(self):
        _, _, headers = create_user()
        create_note(headers, content="# A\nNote A", permission="private")
        create_note(headers, content="# B\nNote B", permission="private")
        resp = requests.get(f"{API}/notes", headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 2

    def test_list_notes_filter_by_tag(self):
        _, _, headers = create_user()
        create_note(headers, content="# Tagged\nContent", tags=["python", "api"])
        create_note(headers, content="# Other\nContent", tags=["java"])
        resp = requests.get(f"{API}/notes", params={"tag": "python"}, headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 1
        assert all("python" in n["tags"] for n in notes)


# =============================================================================
# PERMISSION TESTS
# =============================================================================


class TestPermissions:
    def test_private_note_not_accessible_by_others(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="private")
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

    def test_public_note_readable_by_others(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="public")
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

    def test_public_note_not_writable_by_others(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="public")
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Hacked\nHacked content"
        }, headers=headers_b)
        assert resp.status_code == 403

    def test_limited_note_grant_read(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, permission="limited")

        # B cannot read initially
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

        # Grant read to B
        resp = requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"],
            "level": "read"
        }, headers=headers_a)
        assert resp.status_code == 200

        # B can now read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

        # B still cannot write
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edit\nEdit"
        }, headers=headers_b)
        assert resp.status_code == 403

    def test_limited_note_grant_write(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, permission="limited")

        # Grant write to B
        resp = requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"],
            "level": "write"
        }, headers=headers_a)
        assert resp.status_code == 200

        # B can read and write
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edited by B\nContent"
        }, headers=headers_b)
        assert resp.status_code == 200

    def test_revoke_user_permission(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, permission="limited")

        # Grant then revoke
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"],
            "level": "read"
        }, headers=headers_a)
        resp = requests.delete(
            f"{API}/notes/{note['id']}/permissions/users/{user_b['id']}",
            headers=headers_a
        )
        assert resp.status_code == 200

        # B cannot read anymore
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

    def test_change_permission_private_to_public(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="private")

        # B cannot read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

        # Change to public
        resp = requests.put(f"{API}/notes/{note['id']}/permissions", json={
            "permission": "public"
        }, headers=headers_a)
        assert resp.status_code == 200

        # B can now read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

    def test_get_permission_info(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, permission="limited")

        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"],
            "level": "write"
        }, headers=headers_a)

        resp = requests.get(f"{API}/notes/{note['id']}/permissions", headers=headers_a)
        assert resp.status_code == 200
        perm = resp.json()
        assert perm["permission"] == "limited"
        assert perm["ownerId"] == user_a["id"]
        assert any(up["userId"] == user_b["id"] and up["level"] == "write"
                   for up in perm["userPermissions"])

    def test_only_owner_can_change_permissions(self):
        _, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        note = create_note(headers_a, permission="public")

        resp = requests.put(f"{API}/notes/{note['id']}/permissions", json={
            "permission": "private"
        }, headers=headers_b)
        assert resp.status_code == 403

    def test_only_owner_can_delete_note(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="public")

        resp = requests.delete(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403


# =============================================================================
# GROUP PERMISSION TESTS
# =============================================================================


class TestGroupPermissions:
    def test_create_group(self):
        user_a, _, headers_a = create_user()
        name = unique("grp")
        resp = requests.post(f"{API}/groups", json={
            "name": name,
            "displayName": "My Group"
        }, headers=headers_a)
        assert resp.status_code == 201
        group = resp.json()
        assert group["name"] == name
        assert group["ownerId"] == user_a["id"]

    def test_add_member_to_group(self):
        _, _, headers_a = create_user()
        user_b, _, _ = create_user()
        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()

        resp = requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)
        assert resp.status_code == 200
        assert user_b["id"] in resp.json()["members"]

    def test_group_permission_grants_access(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        # Create group, add B
        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        # Create limited note, grant group write
        note = create_note(headers_a, permission="limited")
        resp = requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"],
            "level": "write"
        }, headers=headers_a)
        assert resp.status_code == 200

        # B (group member) can read and write
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Group edit\nEdited by group member"
        }, headers=headers_b)
        assert resp.status_code == 200

    def test_group_read_permission(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        note = create_note(headers_a, permission="limited")
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"],
            "level": "read"
        }, headers=headers_a)

        # B can read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

        # B cannot write
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Nope\n"
        }, headers=headers_b)
        assert resp.status_code == 403

    def test_revoke_group_permission(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        note = create_note(headers_a, permission="limited")
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"],
            "level": "read"
        }, headers=headers_a)

        # Revoke
        resp = requests.delete(
            f"{API}/notes/{note['id']}/permissions/groups/{grp['id']}",
            headers=headers_a
        )
        assert resp.status_code == 200

        # B cannot read anymore
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

    def test_remove_member_from_group(self):
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        note = create_note(headers_a, permission="limited")
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"],
            "level": "read"
        }, headers=headers_a)

        # B can read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

        # Remove B from group
        resp = requests.delete(
            f"{API}/groups/{grp['id']}/members/{user_b['id']}",
            headers=headers_a
        )
        assert resp.status_code == 200

        # B can no longer read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

    def test_list_groups(self):
        user_a, _, headers_a = create_user()
        name = unique("grp")
        requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a)
        resp = requests.get(f"{API}/groups", headers=headers_a)
        assert resp.status_code == 200
        groups = resp.json()
        assert any(g["name"] == name for g in groups)

    def test_delete_group(self):
        _, _, headers_a = create_user()
        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        resp = requests.delete(f"{API}/groups/{grp['id']}", headers=headers_a)
        assert resp.status_code == 204

    def test_non_owner_cannot_delete_group(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        name = unique("grp")
        grp = requests.post(f"{API}/groups", json={
            "name": name, "displayName": "G"
        }, headers=headers_a).json()
        resp = requests.delete(f"{API}/groups/{grp['id']}", headers=headers_b)
        assert resp.status_code == 403


# =============================================================================
# REVISION TESTS
# =============================================================================


class TestRevisions:
    def test_revision_created_on_update(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# V1\nFirst version")
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V2\nSecond version"
        }, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
        assert resp.status_code == 200
        revisions = resp.json()
        # PUT stores previous content; POST need not create a revision.
        assert len(revisions) >= 1
        assert "# V1\nFirst version" in {rev["content"] for rev in revisions}

    def test_get_specific_revision(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# V1\nFirst")
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V2\nSecond"
        }, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
        revisions = resp.json()
        rev_id = revisions[0]["id"]

        resp = requests.get(
            f"{API}/notes/{note['id']}/revisions/{rev_id}", headers=headers
        )
        assert resp.status_code == 200
        rev = resp.json()
        assert rev["id"] == rev_id
        assert "content" in rev

    def test_revision_diff(self):
        _, _, headers = create_user()
        note = create_note(headers, content="# V1\nFirst")
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V2\nSecond"
        }, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
        revisions = resp.json()
        # Get the last revision (most recent)
        last_rev = revisions[-1]

        resp = requests.get(
            f"{API}/notes/{note['id']}/revisions/{last_rev['id']}/diff",
            headers=headers
        )
        assert resp.status_code == 200
        diff = resp.json()
        assert "currentContent" in diff
        assert "currentTitle" in diff

    def test_revision_stores_author(self):
        user_a, _, headers_a = create_user()
        note = create_note(headers_a, content="# V1\nFirst")
        requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# V2\nSecond"
        }, headers=headers_a)

        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers_a)
        revisions = resp.json()
        for rev in revisions:
            assert rev["authorId"] == user_a["id"]


# =============================================================================
# ALIAS TESTS
# =============================================================================


class TestAliases:
    def test_create_alias(self):
        _, _, headers = create_user()
        note = create_note(headers)
        new_alias = unique("newalias")
        resp = requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": new_alias
        }, headers=headers)
        assert resp.status_code == 201
        alias_data = resp.json()
        assert alias_data["alias"] == new_alias
        assert alias_data["noteId"] == note["id"]

    def test_access_note_by_new_alias(self):
        _, _, headers = create_user()
        alias1 = unique("a1")
        note = create_note(headers, alias=alias1)
        alias2 = unique("a2")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": alias2
        }, headers=headers)

        # Access by second alias
        resp = requests.get(f"{API}/notes/{alias2}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == note["id"]

    def test_duplicate_alias_409(self):
        _, _, headers = create_user()
        alias = unique("dup_alias")
        create_note(headers, alias=alias)
        # Try creating another note with same alias
        resp = requests.post(f"{API}/notes", json={
            "content": "# Another\nNote",
            "alias": alias
        }, headers=headers)
        assert resp.status_code == 409

    def test_list_aliases(self):
        _, _, headers = create_user()
        alias1 = unique("la1")
        note = create_note(headers, alias=alias1)
        alias2 = unique("la2")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": alias2
        }, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
        assert resp.status_code == 200
        aliases = resp.json()
        alias_names = [a["alias"] for a in aliases]
        assert alias1 in alias_names
        assert alias2 in alias_names

    def test_set_primary_alias(self):
        _, _, headers = create_user()
        alias1 = unique("p1")
        note = create_note(headers, alias=alias1)
        alias2 = unique("p2")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": alias2
        }, headers=headers)

        # Set alias2 as primary
        resp = requests.put(f"{API}/aliases/{alias2}", json={
            "isPrimary": True
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["isPrimary"] is True

        # Verify note's primaryAlias changed
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.json()["primaryAlias"] == alias2

    def test_delete_alias(self):
        _, _, headers = create_user()
        alias1 = unique("d1")
        note = create_note(headers, alias=alias1)
        alias2 = unique("d2")
        requests.post(f"{API}/notes/{note['id']}/aliases", json={
            "alias": alias2
        }, headers=headers)

        # Delete alias2
        resp = requests.delete(f"{API}/aliases/{alias2}", headers=headers)
        assert resp.status_code == 204

        # Cannot access by alias2 anymore
        resp = requests.get(f"{API}/notes/{alias2}", headers=headers)
        assert resp.status_code == 404

    def test_cannot_delete_only_alias(self):
        _, _, headers = create_user()
        alias = unique("only")
        note = create_note(headers, alias=alias)

        resp = requests.delete(f"{API}/aliases/{alias}", headers=headers)
        assert resp.status_code == 400


# =============================================================================
# MEDIA TESTS
# =============================================================================


class TestMedia:
    def test_upload_media(self):
        _, _, headers = create_user()
        note = create_note(headers)
        files = {"file": ("test.png", b"fake image data", "image/png")}
        resp = requests.post(
            f"{API}/notes/{note['id']}/media",
            files=files,
            headers=headers
        )
        assert resp.status_code == 201
        media = resp.json()
        assert media["noteId"] == note["id"]
        assert media["fileName"] == "test.png"
        assert "url" in media
        assert "id" in media

    def test_list_media(self):
        _, _, headers = create_user()
        note = create_note(headers)
        files = {"file": ("img1.png", b"data1", "image/png")}
        requests.post(f"{API}/notes/{note['id']}/media", files=files, headers=headers)
        files = {"file": ("img2.jpg", b"data2", "image/jpeg")}
        requests.post(f"{API}/notes/{note['id']}/media", files=files, headers=headers)

        resp = requests.get(f"{API}/notes/{note['id']}/media", headers=headers)
        assert resp.status_code == 200
        media_list = resp.json()
        assert len(media_list) == 2

    def test_delete_media(self):
        _, _, headers = create_user()
        note = create_note(headers)
        files = {"file": ("del.png", b"data", "image/png")}
        media = requests.post(
            f"{API}/notes/{note['id']}/media", files=files, headers=headers
        ).json()

        resp = requests.delete(f"{API}/media/{media['id']}", headers=headers)
        assert resp.status_code == 204

        # Verify deleted
        resp = requests.get(f"{API}/notes/{note['id']}/media", headers=headers)
        assert len(resp.json()) == 0

    def test_cannot_upload_without_write_access(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="public")

        files = {"file": ("hack.png", b"data", "image/png")}
        resp = requests.post(
            f"{API}/notes/{note['id']}/media", files=files, headers=headers_b
        )
        assert resp.status_code == 403


# =============================================================================
# HISTORY TESTS
# =============================================================================


class TestHistory:
    def test_get_note_adds_to_history(self):
        _, _, headers = create_user()
        note = create_note(headers)

        # Access the note
        requests.get(f"{API}/notes/{note['id']}", headers=headers)

        # Check history
        resp = requests.get(f"{API}/me/history", headers=headers)
        assert resp.status_code == 200
        history = resp.json()
        note_ids = [h["noteId"] for h in history]
        assert note["id"] in note_ids

    def test_pin_note_in_history(self):
        _, _, headers = create_user()
        note = create_note(headers)
        requests.get(f"{API}/notes/{note['id']}", headers=headers)

        resp = requests.put(f"{API}/me/history/{note['id']}", json={
            "pinned": True
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["pinned"] is True

    def test_unpin_note_in_history(self):
        _, _, headers = create_user()
        note = create_note(headers)
        requests.get(f"{API}/notes/{note['id']}", headers=headers)
        requests.put(f"{API}/me/history/{note['id']}", json={
            "pinned": True
        }, headers=headers)

        resp = requests.put(f"{API}/me/history/{note['id']}", json={
            "pinned": False
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["pinned"] is False

    def test_delete_history_entry(self):
        _, _, headers = create_user()
        note = create_note(headers)
        requests.get(f"{API}/notes/{note['id']}", headers=headers)

        resp = requests.delete(f"{API}/me/history/{note['id']}", headers=headers)
        assert resp.status_code == 204

        # Verify removed
        resp = requests.get(f"{API}/me/history", headers=headers)
        note_ids = [h["noteId"] for h in resp.json()]
        assert note["id"] not in note_ids

    def test_clear_history(self):
        _, _, headers = create_user()
        note1 = create_note(headers)
        note2 = create_note(headers)
        requests.get(f"{API}/notes/{note1['id']}", headers=headers)
        requests.get(f"{API}/notes/{note2['id']}", headers=headers)

        resp = requests.delete(f"{API}/me/history", headers=headers)
        assert resp.status_code == 204

        resp = requests.get(f"{API}/me/history", headers=headers)
        assert resp.json() == []

    def test_history_updates_on_repeat_access(self):
        _, _, headers = create_user()
        note = create_note(headers)

        requests.get(f"{API}/notes/{note['id']}", headers=headers)
        resp = requests.get(f"{API}/me/history", headers=headers)
        first_access = None
        for h in resp.json():
            if h["noteId"] == note["id"]:
                first_access = h["updatedAt"]
                break
        assert first_access is not None

        # Access again
        import time
        time.sleep(0.1)
        requests.get(f"{API}/notes/{note['id']}", headers=headers)
        resp = requests.get(f"{API}/me/history", headers=headers)
        for h in resp.json():
            if h["noteId"] == note["id"]:
                assert h["updatedAt"] >= first_access
                break


# =============================================================================
# TAG TESTS
# =============================================================================


class TestTags:
    def test_list_tags(self):
        _, _, headers = create_user()
        create_note(headers, content="# A\nA", tags=["python", "api"])
        create_note(headers, content="# B\nB", tags=["python", "web"])

        resp = requests.get(f"{API}/tags", headers=headers)
        assert resp.status_code == 200
        tags = resp.json()
        assert "python" in tags
        assert "api" in tags
        assert "web" in tags

    def test_filter_notes_by_tag(self):
        _, _, headers = create_user()
        note_a = create_note(headers, content="# A\nA", tags=["unique_tag_xyz"])
        create_note(headers, content="# B\nB", tags=["other"])

        resp = requests.get(f"{API}/notes", params={"tag": "unique_tag_xyz"}, headers=headers)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 1
        assert all("unique_tag_xyz" in n["tags"] for n in notes)


# =============================================================================
# IMPORT/EXPORT TESTS
# =============================================================================


class TestImportExport:
    def test_import_markdown(self):
        _, _, headers = create_user()
        content = "# Imported Note\nThis was imported."
        alias = unique("imp")
        resp = requests.post(f"{API}/notes/import", json={
            "content": content,
            "alias": alias,
            "tags": ["imported"]
        }, headers=headers)
        assert resp.status_code == 201
        note = resp.json()
        assert note["title"] == "Imported Note"
        assert note["content"] == content
        assert note["primaryAlias"] == alias

    def test_export_markdown(self):
        _, _, headers = create_user()
        content = "# Export Test\nExport this content."
        note = create_note(headers, content=content)

        resp = requests.get(
            f"{API}/notes/{note['id']}/export/markdown", headers=headers
        )
        assert resp.status_code == 200
        assert content in resp.text

    def test_export_respects_permissions(self):
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()
        note = create_note(headers_a, permission="private")

        resp = requests.get(
            f"{API}/notes/{note['id']}/export/markdown", headers=headers_b
        )
        assert resp.status_code == 403


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    def test_note_not_found(self):
        _, _, headers = create_user()
        resp = requests.get(f"{API}/notes/nonexistent-id-12345", headers=headers)
        assert resp.status_code == 404

    def test_create_note_missing_content(self):
        _, _, headers = create_user()
        resp = requests.post(f"{API}/notes", json={}, headers=headers)
        assert resp.status_code == 400

    def test_title_extraction_multiple_h1s(self):
        """Title should be first H1 only."""
        _, _, headers = create_user()
        note = create_note(headers, content="# First\n# Second\nBody")
        assert note["title"] == "First"

    def test_title_extraction_h1_not_first_line(self):
        """H1 can appear on any line."""
        _, _, headers = create_user()
        note = create_note(headers, content="intro\n\n# Deep Title\nbody")
        assert note["title"] == "Deep Title"

    def test_owner_always_has_access(self):
        """Owner can always read/write regardless of permission level."""
        _, _, headers = create_user()
        note = create_note(headers, permission="private")
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.status_code == 200
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Updated\nBy owner"
        }, headers=headers)
        assert resp.status_code == 200

    def test_alias_globally_unique_across_notes(self):
        """Alias from one note cannot be used by another."""
        _, _, headers = create_user()
        alias = unique("global")
        create_note(headers, alias=alias)

        # Create second note, try adding same alias
        note2 = create_note(headers)
        resp = requests.post(f"{API}/notes/{note2['id']}/aliases", json={
            "alias": alias
        }, headers=headers)
        assert resp.status_code == 409
