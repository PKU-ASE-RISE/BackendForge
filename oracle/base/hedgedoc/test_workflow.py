"""
L3 Workflow Tests for HedgeDoc API.
Multi-step adversarial tests targeting complex interactions:
- Cross-entity workflows (notes + permissions + groups + revisions)
- Cascade deletion side effects
- Data isolation between users
- Permission inheritance through groups
- Business logic verification with multiple inputs
"""
import os
import uuid
import time
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
# L3 TESTS — Workflow (10-15 tests)
# =============================================================================


class TestNoteLifecycleWorkflow:
    """Full lifecycle: create, edit, revision tracking, alias management, export, delete."""

    def test_note_deletion_cascades_media_and_history(self):
        """
        Pattern 7: Deleting a note should remove associated media and history entries.
        """
        _, _, headers = create_user()

        # 1. Create note
        note = create_note(headers, content="# Media Note\nWith attachments")
        note_id = note["id"]

        # 2. Upload media
        files = {"file": (f"{unique('f')}.png", b"image data", "image/png")}
        media_resp = requests.post(f"{API}/notes/{note_id}/media", files=files, headers=headers)
        assert media_resp.status_code == 201
        media_id = media_resp.json()["id"]

        # 3. Access note (adds to history)
        requests.get(f"{API}/notes/{note_id}", headers=headers)
        resp = requests.get(f"{API}/me/history", headers=headers)
        note_ids_in_history = [h["noteId"] for h in resp.json()]
        assert note_id in note_ids_in_history

        # 4. Delete note
        resp = requests.delete(f"{API}/notes/{note_id}", headers=headers)
        assert resp.status_code == 204

        # 5. Verify media is gone (delete by mediaId should 404)
        resp = requests.delete(f"{API}/media/{media_id}", headers=headers)
        assert resp.status_code == 404

        # 6. Verify history entry is gone
        resp = requests.get(f"{API}/me/history", headers=headers)
        note_ids_in_history = [h["noteId"] for h in resp.json()]
        assert note_id not in note_ids_in_history


class TestPermissionWorkflow:
    """Complex permission scenarios with users and groups."""

    def test_group_permission_inheritance_and_revocation(self):
        """
        Pattern 5+6+7: Group permission grants access to all members,
        removing a member revokes their access.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        user_c, _, headers_c = create_user()

        # 1. Create group, add B and C
        grp = requests.post(f"{API}/groups", json={
            "name": unique("grp"), "displayName": "Team"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={"userId": user_b["id"]}, headers=headers_a)
        requests.post(f"{API}/groups/{grp['id']}/members", json={"userId": user_c["id"]}, headers=headers_a)

        # 2. Create limited note
        note = create_note(headers_a, content="# Team Doc\nShared content", permission="limited")

        # 3. Neither B nor C can access yet
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_c)
        assert resp.status_code == 403

        # 4. Grant group write permission
        resp = requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"], "level": "write"
        }, headers=headers_a)
        assert resp.status_code == 200

        # 5. Both B and C can now read AND write
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edited by B\nB's edit"
        }, headers=headers_b)
        assert resp.status_code == 200

        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_c)
        assert resp.status_code == 200

        # 6. Remove C from group
        resp = requests.delete(f"{API}/groups/{grp['id']}/members/{user_c['id']}", headers=headers_a)
        assert resp.status_code == 200

        # 7. C can no longer access, B still can
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_c)
        assert resp.status_code == 403
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

    def test_permission_level_change_affects_access(self):
        """
        Pattern 5+6: Changing permission level from private to public to limited.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        # 1. Create private note
        note = create_note(headers_a, content="# Secret\nContent", permission="private")

        # 2. B cannot read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

        # 3. Change to public
        resp = requests.put(f"{API}/notes/{note['id']}/permissions", json={
            "permission": "public"
        }, headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["permission"] == "public"

        # 4. B can now read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

        # 5. B still cannot write (public = read only for non-owner)
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Hacked\nNope"
        }, headers=headers_b)
        assert resp.status_code == 403

        # 6. Change to limited
        resp = requests.put(f"{API}/notes/{note['id']}/permissions", json={
            "permission": "limited"
        }, headers=headers_a)
        assert resp.status_code == 200

        # 7. B cannot read anymore (limited with no explicit grant)
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

        # 8. Grant B read
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"], "level": "read"
        }, headers=headers_a)

        # 9. B can read again
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

    def test_user_and_group_permissions_combined(self):
        """
        Pattern 5+6: User has individual read, group gives write.
        User should have write access through group membership.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        # 1. Create group and add B
        grp = requests.post(f"{API}/groups", json={
            "name": unique("combo"), "displayName": "Combo"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={"userId": user_b["id"]}, headers=headers_a)

        # 2. Create limited note
        note = create_note(headers_a, content="# Combined\nPerm test", permission="limited")

        # 3. Grant B individual read
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"], "level": "read"
        }, headers=headers_a)

        # 4. B can read but not write
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Attempt\nWrite"
        }, headers=headers_b)
        assert resp.status_code == 403

        # 5. Grant group write
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"], "level": "write"
        }, headers=headers_a)

        # 6. B can now write through group
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Success\nWritten via group"
        }, headers=headers_b)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Success"


class TestCollaborativeEditingWorkflow:
    """Multi-user editing with revision tracking."""

    def test_multi_user_editing_creates_correct_revisions(self):
        """
        Pattern 2+5: Multiple users edit same note, each revision
        records correct authorId and content.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()
        user_c, _, headers_c = create_user()

        # 1. Create note, grant B and C write
        note = create_note(headers_a, content="# Draft\nInitial by A", permission="limited")
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_b["id"], "level": "write"
        }, headers=headers_a)
        requests.post(f"{API}/notes/{note['id']}/permissions/users", json={
            "userId": user_c["id"], "level": "write"
        }, headers=headers_a)

        # 2. B edits
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edit by B\nB was here"
        }, headers=headers_b)
        assert resp.status_code == 200

        # 3. C edits
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Edit by C\nC was here"
        }, headers=headers_c)
        assert resp.status_code == 200

        # 4. A edits
        resp = requests.put(f"{API}/notes/{note['id']}", json={
            "content": "# Final by A\nA finalized"
        }, headers=headers_a)
        assert resp.status_code == 200

        # 5. Check revisions
        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers_a)
        revisions = resp.json()
        assert len(revisions) >= 3  # One previous-state revision per PUT.
        assert {"# Draft\nInitial by A", "# Edit by B\nB was here", "# Edit by C\nC was here"} <= {rev["content"] for rev in revisions}

        # 6. Verify different authors appear
        author_ids = set(r["authorId"] for r in revisions)
        assert user_a["id"] in author_ids
        assert user_b["id"] in author_ids
        assert user_c["id"] in author_ids

        # 7. Current note state should be A's final edit
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_a)
        assert resp.json()["title"] == "Final by A"
        assert resp.json()["content"] == "# Final by A\nA finalized"


class TestHistoryAndTagsWorkflow:
    """Cross-cutting: History tracking + tag aggregation."""

    def test_history_tracks_access_across_multiple_notes(self):
        """
        Pattern 5+6: History auto-updates on note access;
        history is per-user and includes correct titles.
        """
        _, _, headers = create_user()

        # 1. Create 3 notes with distinct titles
        note1 = create_note(headers, content="# Alpha\nFirst note")
        note2 = create_note(headers, content="# Beta\nSecond note")
        note3 = create_note(headers, content="# Gamma\nThird note")

        # 2. Access them in order
        requests.get(f"{API}/notes/{note1['id']}", headers=headers)
        requests.get(f"{API}/notes/{note2['id']}", headers=headers)
        requests.get(f"{API}/notes/{note3['id']}", headers=headers)

        # 3. Check history
        resp = requests.get(f"{API}/me/history", headers=headers)
        assert resp.status_code == 200
        history = resp.json()
        history_map = {h["noteId"]: h for h in history}

        assert note1["id"] in history_map
        assert note2["id"] in history_map
        assert note3["id"] in history_map
        assert history_map[note1["id"]]["title"] == "Alpha"
        assert history_map[note2["id"]]["title"] == "Beta"
        assert history_map[note3["id"]]["title"] == "Gamma"

        # 4. Pin one, verify
        requests.put(f"{API}/me/history/{note2['id']}", json={"pinned": True}, headers=headers)
        resp = requests.get(f"{API}/me/history", headers=headers)
        updated_map = {h["noteId"]: h for h in resp.json()}
        assert updated_map[note2["id"]]["pinned"] is True
        assert updated_map[note1["id"]]["pinned"] is False

        # 5. Delete one from history, verify others remain
        resp = requests.delete(f"{API}/me/history/{note1['id']}", headers=headers)
        assert resp.status_code == 204
        resp = requests.get(f"{API}/me/history", headers=headers)
        remaining_ids = [h["noteId"] for h in resp.json()]
        assert note1["id"] not in remaining_ids
        assert note2["id"] in remaining_ids
        assert note3["id"] in remaining_ids

    def test_tag_aggregation_reflects_note_changes(self):
        """
        Pattern 3+5: Tags endpoint aggregates from all accessible notes;
        changing tags on notes should update the aggregation.
        """
        _, _, headers = create_user()

        # 1. Create notes with different tags
        tag_a = unique("tag_a")
        tag_b = unique("tag_b")
        tag_c = unique("tag_c")
        note1 = create_note(headers, content="# N1\nN1", tags=[tag_a, tag_b])
        note2 = create_note(headers, content="# N2\nN2", tags=[tag_b, tag_c])

        # 2. Verify tags endpoint shows all 3
        resp = requests.get(f"{API}/tags", headers=headers)
        tags = resp.json()
        assert tag_a in tags
        assert tag_b in tags
        assert tag_c in tags

        # 3. Update note1 to remove tag_a
        resp = requests.patch(f"{API}/notes/{note1['id']}", json={
            "tags": [tag_b]
        }, headers=headers)
        assert resp.status_code == 200

        # 4. tag_a should no longer appear
        resp = requests.get(f"{API}/tags", headers=headers)
        tags = resp.json()
        assert tag_a not in tags
        assert tag_b in tags
        assert tag_c in tags

        # 5. Filter notes by tag_b should return both
        resp = requests.get(f"{API}/notes", params={"tag": tag_b}, headers=headers)
        notes = resp.json()
        note_ids = [n["id"] for n in notes]
        assert note1["id"] in note_ids
        assert note2["id"] in note_ids

        # 6. Filter by tag_c should only return note2
        resp = requests.get(f"{API}/notes", params={"tag": tag_c}, headers=headers)
        notes = resp.json()
        assert len(notes) == 1
        assert notes[0]["id"] == note2["id"]


class TestAliasWorkflow:
    """Complex alias operations: primary switching, deletion constraints."""

    def test_alias_management_workflow(self):
        """
        Pattern 1+4+8: Create note with alias, add more, switch primary,
        delete non-primary, verify constraints.
        """
        _, _, headers = create_user()

        # 1. Create note with alias
        alias1 = unique("wf_a1")
        note = create_note(headers, content="# Alias Test\nContent", alias=alias1)
        assert note["primaryAlias"] == alias1

        # 2. Add alias2 and alias3
        alias2 = unique("wf_a2")
        alias3 = unique("wf_a3")
        resp = requests.post(f"{API}/notes/{note['id']}/aliases", json={"alias": alias2}, headers=headers)
        assert resp.status_code == 201
        resp = requests.post(f"{API}/notes/{note['id']}/aliases", json={"alias": alias3}, headers=headers)
        assert resp.status_code == 201

        # 3. Verify all 3 aliases listed
        resp = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
        aliases = resp.json()
        assert len(aliases) == 3
        alias_names = [a["alias"] for a in aliases]
        assert alias1 in alias_names
        assert alias2 in alias_names
        assert alias3 in alias_names

        # 4. Switch primary to alias2
        resp = requests.put(f"{API}/aliases/{alias2}", json={"isPrimary": True}, headers=headers)
        assert resp.status_code == 200

        # 5. Verify note's primaryAlias updated
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
        assert resp.json()["primaryAlias"] == alias2

        # 6. Delete alias3 (non-primary)
        resp = requests.delete(f"{API}/aliases/{alias3}", headers=headers)
        assert resp.status_code == 204

        # 7. Accessing via alias3 should 404
        resp = requests.get(f"{API}/notes/{alias3}", headers=headers)
        assert resp.status_code == 404

        # 8. Still accessible via alias1 and alias2
        resp = requests.get(f"{API}/notes/{alias1}", headers=headers)
        assert resp.status_code == 200
        resp = requests.get(f"{API}/notes/{alias2}", headers=headers)
        assert resp.status_code == 200

        # 9. Try duplicate alias (conflict)
        _, _, headers2 = create_user()
        note2 = create_note(headers2)
        resp = requests.post(f"{API}/notes/{note2['id']}/aliases", json={"alias": alias1}, headers=headers2)
        assert resp.status_code == 409


class TestDataIsolation:
    """Pattern 6: Verify complete data isolation between users."""

    def test_complete_isolation_between_users(self):
        """
        Two users with their own notes, groups, media, history —
        neither should see the other's private data.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        # 1. Each creates private notes
        note_a = create_note(headers_a, content="# A Private\nA's secret", permission="private",
                             tags=["a_tag"])
        note_b = create_note(headers_b, content="# B Private\nB's secret", permission="private",
                             tags=["b_tag"])

        # 2. Each creates groups
        grp_a = requests.post(f"{API}/groups", json={
            "name": unique("grp_a"), "displayName": "A's Group"
        }, headers=headers_a).json()
        grp_b = requests.post(f"{API}/groups", json={
            "name": unique("grp_b"), "displayName": "B's Group"
        }, headers=headers_b).json()

        # 3. Each uploads media
        requests.post(f"{API}/notes/{note_a['id']}/media",
                      files={"file": ("a.png", b"A data", "image/png")}, headers=headers_a)
        requests.post(f"{API}/notes/{note_b['id']}/media",
                      files={"file": ("b.png", b"B data", "image/png")}, headers=headers_b)

        # 4. Each accesses own note (history)
        requests.get(f"{API}/notes/{note_a['id']}", headers=headers_a)
        requests.get(f"{API}/notes/{note_b['id']}", headers=headers_b)

        # 5. Verify: A cannot see B's note
        resp = requests.get(f"{API}/notes/{note_b['id']}", headers=headers_a)
        assert resp.status_code == 403

        # 6. Verify: B cannot see A's note
        resp = requests.get(f"{API}/notes/{note_a['id']}", headers=headers_b)
        assert resp.status_code == 403

        # 7. A's note list doesn't include B's note
        resp = requests.get(f"{API}/notes", headers=headers_a)
        a_note_ids = [n["id"] for n in resp.json()]
        assert note_a["id"] in a_note_ids
        assert note_b["id"] not in a_note_ids

        # 8. A's groups don't include B's group
        resp = requests.get(f"{API}/groups", headers=headers_a)
        a_grp_ids = [g["id"] for g in resp.json()]
        assert grp_a["id"] in a_grp_ids
        assert grp_b["id"] not in a_grp_ids

        # 9. A's tags don't include B's tags
        resp = requests.get(f"{API}/tags", headers=headers_a)
        assert "b_tag" not in resp.json()

        # 10. A's history doesn't include B's note
        resp = requests.get(f"{API}/me/history", headers=headers_a)
        a_hist_ids = [h["noteId"] for h in resp.json()]
        assert note_b["id"] not in a_hist_ids


class TestGroupDeletionWorkflow:
    """Pattern 7: Group deletion and its effects on permissions."""

    def test_delete_group_revokes_member_access(self):
        """
        Deleting a group should cause its members to lose access
        previously granted through that group.
        """
        user_a, _, headers_a = create_user()
        user_b, _, headers_b = create_user()

        # 1. Create group with B as member
        grp = requests.post(f"{API}/groups", json={
            "name": unique("del_grp"), "displayName": "Temp Group"
        }, headers=headers_a).json()
        requests.post(f"{API}/groups/{grp['id']}/members", json={
            "userId": user_b["id"]
        }, headers=headers_a)

        # 2. Create limited note, grant group read
        note = create_note(headers_a, content="# Group Note\nContent", permission="limited")
        requests.post(f"{API}/notes/{note['id']}/permissions/groups", json={
            "groupId": grp["id"], "level": "read"
        }, headers=headers_a)

        # 3. Verify B can read
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 200

        # 4. Delete the group
        resp = requests.delete(f"{API}/groups/{grp['id']}", headers=headers_a)
        assert resp.status_code == 204

        # 5. B should lose access
        resp = requests.get(f"{API}/notes/{note['id']}", headers=headers_b)
        assert resp.status_code == 403

        # 6. The group itself should be gone
        resp = requests.get(f"{API}/groups/{grp['id']}", headers=headers_a)
        assert resp.status_code == 404


class TestImportExportWorkflow:
    """Pattern 5+8: Import/export roundtrip with edge cases."""

    def test_import_export_roundtrip_preserves_content(self):
        """
        Import note -> modify -> export -> compare.
        Verify exact content preservation through the pipeline.
        """
        _, _, headers = create_user()

        # 1. Import with complex markdown
        original = "# Complex Note\n\n## Section 1\n\n- Item A\n- Item B\n\n```python\nprint('hello')\n```\n\n> Blockquote here"
        alias = unique("rt")
        resp = requests.post(f"{API}/notes/import", json={
            "content": original,
            "alias": alias,
            "tags": ["imported", "roundtrip"]
        }, headers=headers)
        assert resp.status_code == 201
        note = resp.json()
        assert note["title"] == "Complex Note"
        assert note["primaryAlias"] == alias
        assert set(note["tags"]) == {"imported", "roundtrip"}

        # 2. Export and verify exact match
        resp = requests.get(f"{API}/notes/{note['id']}/export/markdown", headers=headers)
        assert resp.status_code == 200
        assert resp.text == original

        # 3. Update content
        updated = "# Updated Complex\n\nNew content entirely"
        resp = requests.put(f"{API}/notes/{note['id']}", json={"content": updated}, headers=headers)
        assert resp.status_code == 200

        # 4. Export again — should be updated content
        resp = requests.get(f"{API}/notes/{note['id']}/export/markdown", headers=headers)
        assert resp.status_code == 200
        assert resp.text == updated

        # 5. Revisions should capture the change
        resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
        revisions = resp.json()
        assert len(revisions) >= 1
        # One revision should contain the original content
        contents = [r["content"] for r in revisions]
        assert original in contents


class TestConflictAndEdgeCases:
    """Pattern 8: Uniqueness constraints and error handling."""

    def test_duplicate_username_alias_group_conflicts(self):
        """
        Verify 409 Conflict for duplicate username, alias, and group name.
        """
        _, _, headers_a = create_user()
        _, _, headers_b = create_user()

        # 1. Duplicate username
        uname = unique("conflict_u")
        requests.post(f"{API}/users", json={
            "username": uname, "displayName": "First", "password": "pass"
        })
        resp = requests.post(f"{API}/users", json={
            "username": uname, "displayName": "Second", "password": "pass"
        })
        assert resp.status_code == 409

        # 2. Duplicate alias across different users
        alias = unique("conflict_alias")
        create_note(headers_a, alias=alias)
        resp = requests.post(f"{API}/notes", json={
            "content": "# Dup\nDup", "alias": alias
        }, headers=headers_b)
        assert resp.status_code == 409

        # 3. Duplicate group name
        grp_name = unique("conflict_grp")
        resp = requests.post(f"{API}/groups", json={
            "name": grp_name, "displayName": "G1"
        }, headers=headers_a)
        assert resp.status_code == 201
        resp = requests.post(f"{API}/groups", json={
            "name": grp_name, "displayName": "G2"
        }, headers=headers_b)
        assert resp.status_code == 409

    def test_operations_on_deleted_resources_return_404(self):
        """
        After deletion, all operations on the resource should return 404.
        """
        _, _, headers = create_user()

        # 1. Create and delete a note
        note = create_note(headers, content="# Gone\nSoon deleted")
        note_id = note["id"]
        requests.delete(f"{API}/notes/{note_id}", headers=headers)

        # 2. All operations should 404
        resp = requests.get(f"{API}/notes/{note_id}", headers=headers)
        assert resp.status_code == 404
        resp = requests.put(f"{API}/notes/{note_id}", json={"content": "x"}, headers=headers)
        assert resp.status_code == 404
        resp = requests.patch(f"{API}/notes/{note_id}", json={"tags": []}, headers=headers)
        assert resp.status_code == 404
        resp = requests.get(f"{API}/notes/{note_id}/revisions", headers=headers)
        assert resp.status_code == 404
        resp = requests.get(f"{API}/notes/{note_id}/aliases", headers=headers)
        assert resp.status_code == 404
        resp = requests.get(f"{API}/notes/{note_id}/media", headers=headers)
        assert resp.status_code == 404
        resp = requests.get(f"{API}/notes/{note_id}/permissions", headers=headers)
        assert resp.status_code == 404
