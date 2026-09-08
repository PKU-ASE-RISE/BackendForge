"""
BackendForge — L3 Workflow Tests for Memos Task

Multi-step workflow tests spanning 3+ entity types, 6-12 steps each,
targeting adversarial bug patterns that LLM coding agents commonly produce.

"""

import os
import uuid
import time

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
UNIQUE = uuid.uuid4().hex[:8]
TIMESTAMP_RESOLUTION_DELAY = 1.1


# ── HTTP Helpers ──


def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ── Fixtures ──


@pytest.fixture(scope="session")
def users(base_users):
    """Use shared users from conftest."""
    return base_users


# ════════════════════════════════════════════════════════════════════
# L3 Tests: 6-12 steps, 12-20 assertions, cross-entity workflows
# ════════════════════════════════════════════════════════════════════


class TestFullMemoLifecycle:
    """Pattern 1+2+4+7: Complete memo lifecycle with tags, reactions, relations."""

    def test_memo_create_react_relate_delete(self, users):
        """Full lifecycle: create memo → add reactions → add relations → delete → verify cascade."""
        # Step 1: Create two memos
        resp = api_post("/api/memos", {
            "content": f"#lifecycle Source memo {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        src = resp.json()
        assert "creatorId" in src
        assert src["creatorId"] == users["user_a"]["id"]
        assert "lifecycle" in src["tags"]

        resp = api_post("/api/memos", {
            "content": f"#lifecycle Target memo {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        tgt = resp.json()

        # Step 2: User B adds reaction to source memo
        resp = api_post(f"/api/memos/{src['id']}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 201
        reaction = resp.json()
        assert reaction["memoId"] == src["id"]
        assert reaction["reactionType"] == "thumbs_up"
        assert reaction["creatorId"] == users["user_b"]["id"]

        # Step 3: Create relation between memos
        resp = api_post(f"/api/memos/{src['id']}/relations", {
            "relatedMemoId": tgt["id"],
            "type": "REFERENCE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        rel = resp.json()
        assert rel["memoId"] == src["id"]
        assert rel["relatedMemoId"] == tgt["id"]

        # Step 4: Verify relations listed
        resp = api_get(f"/api/memos/{src['id']}/relations", headers=users["user_a_headers"])
        assert resp.status_code == 200
        relations = resp.json()
        assert len(relations) >= 1

        # Step 5: Verify reactions listed
        resp = api_get(f"/api/memos/{src['id']}/reactions", headers=users["user_a_headers"])
        assert resp.status_code == 200
        reactions = resp.json()
        assert len(reactions) >= 1
        assert reactions[0]["reactionType"] == "thumbs_up"

        # Step 6: Delete source memo (owner)
        resp = api_delete(f"/api/memos/{src['id']}", headers=users["user_a_headers"])
        assert resp.status_code == 204

        # Step 7: Verify memo is gone
        resp = api_get(f"/api/memos/{src['id']}", headers=users["user_a_headers"])
        assert resp.status_code == 404

        # Step 8: Verify target memo still exists (no improper cascade)
        resp = api_get(f"/api/memos/{tgt['id']}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["id"] == tgt["id"]


class TestTagManagementWorkflow:
    """Pattern 5+7: Tag operations actually modify memo content and recalculate tags."""

    def test_tag_rename_across_multiple_memos(self, users):
        """Rename tag → all memos' content and tags updated; other users unaffected."""
        old_tag = f"oldwf{UNIQUE}"
        new_tag = f"newwf{UNIQUE}"
        other_tag = f"otherwf{UNIQUE}"

        # Step 1: User A creates memos with old tag
        resp = api_post("/api/memos", {
            "content": f"#{old_tag} first memo",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo1_id = resp.json()["id"]

        resp = api_post("/api/memos", {
            "content": f"#{old_tag} second memo with #{other_tag}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo2_id = resp.json()["id"]

        # Step 2: User B creates memo with same tag name (should NOT be affected)
        resp = api_post("/api/memos", {
            "content": f"#{old_tag} userB memo",
            "visibility": "PRIVATE"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 201
        memo_b_id = resp.json()["id"]

        # Step 3: User A renames the tag
        resp = api_post("/api/tags/rename", {
            "oldName": old_tag,
            "newName": new_tag
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["oldName"] == old_tag
        assert resp.json()["newName"] == new_tag

        # Step 4: Verify memo1 content updated
        resp = api_get(f"/api/memos/{memo1_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        m1 = resp.json()
        assert f"#{new_tag}" in m1["content"], f"Content should have new tag: {m1['content']}"
        assert f"#{old_tag}" not in m1["content"], f"Old tag should be gone: {m1['content']}"
        assert new_tag in m1["tags"]
        assert old_tag not in m1["tags"]

        # Step 5: Verify memo2 content updated, other tag preserved
        resp = api_get(f"/api/memos/{memo2_id}", headers=users["user_a_headers"])
        m2 = resp.json()
        assert f"#{new_tag}" in m2["content"]
        assert f"#{old_tag}" not in m2["content"]
        assert new_tag in m2["tags"]
        assert other_tag in m2["tags"], f"Other tag should be preserved: {m2['tags']}"

        # Step 6: Verify User B's memo is NOT affected
        resp = api_get(f"/api/memos/{memo_b_id}", headers=users["user_b_headers"])
        mb = resp.json()
        assert f"#{old_tag}" in mb["content"], f"User B's memo should be unchanged: {mb['content']}"
        assert old_tag in mb["tags"]

        # Step 7: Verify User A's tag list reflects change
        resp = api_get("/api/tags", headers=users["user_a_headers"])
        a_tags = [t["tag"] for t in resp.json()]
        assert new_tag in a_tags, f"New tag should appear in list: {a_tags}"
        assert old_tag not in a_tags, f"Old tag should be gone from list: {a_tags}"

    def test_tag_delete_removes_from_content_and_tag_list(self, users):
        """Delete tag → removed from memo content AND from tags array AND from GET /api/tags."""
        tag_to_delete = f"delmulti{UNIQUE}"
        keep_tag = f"keeptag{UNIQUE}"

        # Step 1: Create memos with mixed tags
        resp = api_post("/api/memos", {
            "content": f"#{tag_to_delete} #{keep_tag} first",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo1_id = resp.json()["id"]

        resp = api_post("/api/memos", {
            "content": f"#{tag_to_delete} only this tag",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        memo2_id = resp.json()["id"]

        # Step 2: Verify tag exists in tag list
        resp = api_get("/api/tags", headers=users["user_a_headers"])
        tags = [t["tag"] for t in resp.json()]
        assert tag_to_delete in tags

        # Step 3: Delete the tag
        resp = api_delete(f"/api/tags/{tag_to_delete}", headers=users["user_a_headers"])
        assert resp.status_code == 204

        # Step 4: Verify memo1 content no longer has the tag
        resp = api_get(f"/api/memos/{memo1_id}", headers=users["user_a_headers"])
        m1 = resp.json()
        assert f"#{tag_to_delete}" not in m1["content"]
        assert tag_to_delete not in m1["tags"]
        assert keep_tag in m1["tags"], "Other tags should be preserved"

        # Step 5: Verify memo2 tag removed
        resp = api_get(f"/api/memos/{memo2_id}", headers=users["user_a_headers"])
        m2 = resp.json()
        assert f"#{tag_to_delete}" not in m2["content"]
        assert tag_to_delete not in m2["tags"]

        # Step 6: Verify tag gone from tag list
        resp = api_get("/api/tags", headers=users["user_a_headers"])
        tags = [t["tag"] for t in resp.json()]
        assert tag_to_delete not in tags, f"Deleted tag should be gone from list: {tags}"
        assert keep_tag in tags, "Unrelated tags should remain"


class TestMultiUserVisibilityWorkflow:
    """Pattern 6+1+3: Multi-user data isolation with visibility & filtering."""

    def test_cross_user_visibility_and_filtering(self, users):
        """Multi-user scenario: visibility rules + filtering across users."""
        tag = f"crossuser{UNIQUE}"

        # Step 1: User A creates PRIVATE memo
        resp = api_post("/api/memos", {
            "content": f"#{tag} private from A",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        a_private_id = resp.json()["id"]

        # Step 2: User A creates PUBLIC memo
        resp = api_post("/api/memos", {
            "content": f"#{tag} public from A",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        a_public_id = resp.json()["id"]

        # Step 3: User B creates PROTECTED memo
        resp = api_post("/api/memos", {
            "content": f"#{tag} protected from B",
            "visibility": "PROTECTED"
        }, headers=users["user_b_headers"])
        b_protected_id = resp.json()["id"]

        # Step 4: User B queries all memos with tag filter
        resp = api_get("/api/memos", params={"tag": tag}, headers=users["user_b_headers"])
        assert resp.status_code == 200
        b_sees = [m["id"] for m in resp.json()["memos"]]

        # Step 5: User B should see A's PUBLIC and B's PROTECTED, NOT A's PRIVATE
        assert a_public_id in b_sees, "B should see A's PUBLIC memo"
        assert b_protected_id in b_sees, "B should see own PROTECTED memo"
        assert a_private_id not in b_sees, "B should NOT see A's PRIVATE memo"

        # Step 6: User A queries with creatorId=B — sees PROTECTED
        resp = api_get("/api/memos", params={
            "creatorId": users["user_b"]["id"],
            "tag": tag
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        a_sees_b = [m["id"] for m in resp.json()["memos"]]
        assert b_protected_id in a_sees_b, "A should see B's PROTECTED memo"

        # Step 7: User A can still see own PRIVATE
        resp = api_get(f"/api/memos/{a_private_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PRIVATE"

        # Step 8: User B direct access to A's PRIVATE → 404
        resp = api_get(f"/api/memos/{a_private_id}", headers=users["user_b_headers"])
        assert resp.status_code == 404

        # Step 9: Verify total count respects visibility
        resp = api_get("/api/memos", params={
            "creatorId": users["user_a"]["id"],
            "tag": tag
        }, headers=users["user_b_headers"])
        data = resp.json()
        # B should only see A's PUBLIC (not PRIVATE)
        assert data["total"] == 1, f"B should see 1 of A's memos, got {data['total']}"


class TestMemoResourceWorkflow:
    """Pattern 2+6+7: Memo + Resource linking and ownership."""

    def test_resource_linked_to_memo_lifecycle(self, users):
        """Create memo → link resource → update resource → delete memo → resource survives."""
        # Step 1: Create memo
        resp = api_post("/api/memos", {
            "content": f"Memo with attachment {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo = resp.json()
        memo_id = memo["id"]

        # Step 2: Create resource linked to memo
        resp = api_post("/api/resources", {
            "filename": f"attachment_{UNIQUE}.png",
            "type": "image/png",
            "size": 5000,
            "memoId": memo_id
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        resource = resp.json()
        res_id = resource["id"]
        assert resource["memoId"] == memo_id
        assert resource["creatorId"] == users["user_a"]["id"]
        assert resource["filename"] == f"attachment_{UNIQUE}.png"

        # Step 3: Verify resource listed for user
        resp = api_get("/api/resources", headers=users["user_a_headers"])
        assert resp.status_code == 200
        res_ids = [r["id"] for r in resp.json()]
        assert res_id in res_ids

        # Step 4: User B cannot see User A's resource
        resp = api_get(f"/api/resources/{res_id}", headers=users["user_b_headers"])
        assert resp.status_code == 404

        # Step 5: Update resource filename
        resp = api_patch(f"/api/resources/{res_id}", {
            "filename": f"renamed_{UNIQUE}.png"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["filename"] == f"renamed_{UNIQUE}.png"
        assert resp.json()["memoId"] == memo_id  # link preserved

        # Step 6: Delete the memo
        resp = api_delete(f"/api/memos/{memo_id}", headers=users["user_a_headers"])
        assert resp.status_code == 204

        # Step 7: Resource should still exist (memoId becomes null due to ON DELETE SET NULL)
        resp = api_get(f"/api/resources/{res_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        resource = resp.json()
        assert resource["id"] == res_id
        assert resource["memoId"] is None, f"memoId should be null after memo deleted, got {resource['memoId']}"

        # Step 8: Clean up
        resp = api_delete(f"/api/resources/{res_id}", headers=users["user_a_headers"])
        assert resp.status_code == 204


class TestReactionWorkflow:
    """Pattern 4+6+8: Reactions with uniqueness, ownership, and cross-user access."""

    def test_reaction_uniqueness_and_ownership(self, users):
        """Multiple users react → duplicates rejected → only reactor can delete."""
        # Step 1: Create a public memo
        resp = api_post("/api/memos", {
            "content": f"React workflow {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        memo_id = resp.json()["id"]

        # Step 2: User A reacts with thumbs_up
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        reaction_a = resp.json()
        assert reaction_a["creatorId"] == users["user_a"]["id"]
        assert reaction_a["reactionType"] == "thumbs_up"

        # Step 3: User B reacts with same type (allowed — different user)
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 201
        reaction_b = resp.json()
        assert reaction_b["creatorId"] == users["user_b"]["id"]

        # Step 4: User A tries same reaction again → 409
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 409

        # Step 5: User A adds different type (allowed)
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "heart"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201

        # Step 6: List reactions — should have 3 total
        resp = api_get(f"/api/memos/{memo_id}/reactions", headers=users["host_headers"])
        assert resp.status_code == 200
        reactions = resp.json()
        assert len(reactions) == 3, f"Expected 3 reactions, got {len(reactions)}"

        # Step 7: User B tries to delete User A's reaction → 403
        resp = api_delete(f"/api/reactions/{reaction_a['id']}", headers=users["user_b_headers"])
        assert resp.status_code == 403

        # Step 8: User A deletes own reaction → 204
        resp = api_delete(f"/api/reactions/{reaction_a['id']}", headers=users["user_a_headers"])
        assert resp.status_code == 204

        # Step 9: Verify reaction count decreased
        resp = api_get(f"/api/memos/{memo_id}/reactions", headers=users["host_headers"])
        assert len(resp.json()) == 2

        # Step 10: User A can now re-add the same reaction type
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201


class TestMemoRelationWorkflow:
    """Pattern 7+8: Relations with constraints and bidirectional visibility."""

    def test_relation_constraints_and_visibility(self, users):
        """Create relations → verify constraints → check bidirectional listing."""
        # Step 1: Create 3 memos
        resp = api_post("/api/memos", {
            "content": f"Memo Alpha {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        alpha_id = resp.json()["id"]

        resp = api_post("/api/memos", {
            "content": f"Memo Beta {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        beta_id = resp.json()["id"]

        resp = api_post("/api/memos", {
            "content": f"Memo Gamma {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        gamma_id = resp.json()["id"]

        # Step 2: Self-reference rejected
        resp = api_post(f"/api/memos/{alpha_id}/relations", {
            "relatedMemoId": alpha_id,
            "type": "REFERENCE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 400

        # Step 3: Create Alpha → Beta relation
        resp = api_post(f"/api/memos/{alpha_id}/relations", {
            "relatedMemoId": beta_id,
            "type": "REFERENCE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        assert resp.json()["memoId"] == alpha_id
        assert resp.json()["relatedMemoId"] == beta_id

        # Step 4: Duplicate relation → 409
        resp = api_post(f"/api/memos/{alpha_id}/relations", {
            "relatedMemoId": beta_id,
            "type": "REFERENCE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 409

        # Step 5: Create Alpha → Gamma relation
        resp = api_post(f"/api/memos/{alpha_id}/relations", {
            "relatedMemoId": gamma_id,
            "type": "REFERENCE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201

        # Step 6: List relations for Alpha — should have 2 outgoing
        resp = api_get(f"/api/memos/{alpha_id}/relations", headers=users["user_a_headers"])
        assert resp.status_code == 200
        alpha_rels = resp.json()
        assert len(alpha_rels) >= 2

        # Step 7: List relations for Beta — should show incoming from Alpha
        resp = api_get(f"/api/memos/{beta_id}/relations", headers=users["user_a_headers"])
        assert resp.status_code == 200
        beta_rels = resp.json()
        assert len(beta_rels) >= 1
        found = any(r["memoId"] == alpha_id and r["relatedMemoId"] == beta_id for r in beta_rels)
        assert found, "Beta should show incoming relation from Alpha"

        # Step 8: Delete Alpha → Beta relation
        resp = api_delete(f"/api/memos/{alpha_id}/relations/{beta_id}",
                          headers=users["user_a_headers"])
        assert resp.status_code == 204

        # Step 9: Verify relation gone from Alpha's list
        resp = api_get(f"/api/memos/{alpha_id}/relations", headers=users["user_a_headers"])
        remaining = resp.json()
        remaining_targets = [r["relatedMemoId"] for r in remaining if r["memoId"] == alpha_id]
        assert beta_id not in remaining_targets

        # Step 10: Alpha → Gamma still exists
        assert gamma_id in remaining_targets


class TestHostPrivilegesWorkflow:
    """Pattern 6+4: HOST can manage other users' data; regular users cannot."""

    def test_host_delete_others_memo_and_manage_users(self, users):
        """HOST manages users and deletes others' memos; regular users restricted."""
        # Step 1: User A creates a PRIVATE memo
        resp = api_post("/api/memos", {
            "content": f"User A private memo {UNIQUE} hostpriv",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        a_memo_id = resp.json()["id"]

        # Step 2: User B tries to delete User A's memo → 403
        resp = api_delete(f"/api/memos/{a_memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 403

        # Step 3: User B tries to update User A's memo → 403
        resp = api_patch(f"/api/memos/{a_memo_id}", {
            "content": "Hacked!"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 403

        # Step 4: HOST can delete User A's memo
        resp = api_delete(f"/api/memos/{a_memo_id}", headers=users["host_headers"])
        assert resp.status_code == 204

        # Step 5: Verify it's gone
        resp = api_get(f"/api/memos/{a_memo_id}", headers=users["user_a_headers"])
        assert resp.status_code == 404

        # Step 6: HOST can update User A's profile
        resp = api_patch(f"/api/users/{users['user_a']['id']}", {
            "nickname": f"Host-Edited-{UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        assert resp.json()["nickname"] == f"Host-Edited-{UNIQUE}"

        # Step 7: User B cannot update User A's profile
        resp = api_patch(f"/api/users/{users['user_a']['id']}", {
            "nickname": "Hacked!"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 403

        # Step 8: User B cannot create new users
        resp = api_post("/api/users", {
            "username": f"illegal_{UNIQUE}"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 403

        # Step 9: HOST can create new users
        resp = api_post("/api/users", {
            "username": f"newuser_{UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        assert resp.json()["role"] == "USER"


class TestPinnedMemoWorkflow:
    """Pattern 3+5: Pin/unpin with correct ordering and filter interaction."""

    def test_pin_unpin_ordering_and_filter(self, users):
        """Create memos → pin → verify order → unpin → verify order changes."""
        tag = f"pinwf{UNIQUE}"

        # Step 1: Create 3 unpinned memos in order
        ids = []
        for i in range(3):
            resp = api_post("/api/memos", {
                "content": f"#{tag} memo {i}",
                "visibility": "PRIVATE",
                "pinned": False
            }, headers=users["user_a_headers"])
            assert resp.status_code == 201
            ids.append(resp.json()["id"])
            if i < 2:
                time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        # ids[0]=oldest, ids[2]=newest

        # Step 2: Verify initial order (newest first for unpinned)
        resp = api_get("/api/memos", params={"tag": tag}, headers=users["user_a_headers"])
        listed_ids = [m["id"] for m in resp.json()["memos"]]
        assert listed_ids.index(ids[2]) < listed_ids.index(ids[0]), \
            "Newest unpinned should come first"

        # Step 3: Pin the oldest memo
        resp = api_patch(f"/api/memos/{ids[0]}", {
            "pinned": True
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["pinned"] is True

        # Step 4: Now oldest (pinned) should be FIRST
        resp = api_get("/api/memos", params={"tag": tag}, headers=users["user_a_headers"])
        listed_ids = [m["id"] for m in resp.json()["memos"]]
        assert listed_ids[0] == ids[0], "Pinned memo should be first regardless of creation time"

        # Step 5: Filter by pinned=true returns only the pinned one
        resp = api_get("/api/memos", params={
            "tag": tag, "pinned": "true"
        }, headers=users["user_a_headers"])
        pinned_memos = resp.json()["memos"]
        assert len(pinned_memos) == 1
        assert pinned_memos[0]["id"] == ids[0]
        assert pinned_memos[0]["pinned"] is True

        # Step 6: Unpin it
        resp = api_patch(f"/api/memos/{ids[0]}", {
            "pinned": False
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["pinned"] is False

        # Step 7: Back to normal order (newest first)
        resp = api_get("/api/memos", params={"tag": tag}, headers=users["user_a_headers"])
        listed_ids = [m["id"] for m in resp.json()["memos"]]
        assert listed_ids.index(ids[2]) < listed_ids.index(ids[0]), \
            "After unpin, newest should be first again"


class TestSearchAndPaginationWorkflow:
    """Pattern 3+5: Search + pagination working together correctly."""

    def test_search_with_pagination_and_total(self, users):
        """Create multiple memos → search → paginate → verify correctness."""
        search_term = f"searchable{UNIQUE}"

        # Step 1: Create 5 matching memos and 2 non-matching
        matching_ids = []
        for i in range(5):
            resp = api_post("/api/memos", {
                "content": f"This is {search_term} item {i}",
                "visibility": "PRIVATE"
            }, headers=users["user_a_headers"])
            assert resp.status_code == 201
            matching_ids.append(resp.json()["id"])
            if i < 4:
                time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        for i in range(2):
            api_post("/api/memos", {
                "content": f"Unrelated content {UNIQUE} {i}",
                "visibility": "PRIVATE"
            }, headers=users["user_a_headers"])

        # Step 2: Search with full term — should find 5
        resp = api_get("/api/memos", params={
            "search": search_term
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5, f"Expected 5 matches, got {data['total']}"

        # Step 3: Paginate page 1 (limit=2)
        resp = api_get("/api/memos", params={
            "search": search_term, "limit": 2, "offset": 0
        }, headers=users["user_a_headers"])
        page1 = resp.json()
        assert len(page1["memos"]) == 2
        assert page1["total"] == 5  # Total unchanged by pagination

        # Step 4: Paginate page 2
        resp = api_get("/api/memos", params={
            "search": search_term, "limit": 2, "offset": 2
        }, headers=users["user_a_headers"])
        page2 = resp.json()
        assert len(page2["memos"]) == 2
        assert page2["total"] == 5

        # Step 5: Paginate page 3 (only 1 remaining)
        resp = api_get("/api/memos", params={
            "search": search_term, "limit": 2, "offset": 4
        }, headers=users["user_a_headers"])
        page3 = resp.json()
        assert len(page3["memos"]) == 1
        assert page3["total"] == 5

        # Step 6: Verify no overlap between pages
        all_page_ids = (
            [m["id"] for m in page1["memos"]] +
            [m["id"] for m in page2["memos"]] +
            [m["id"] for m in page3["memos"]]
        )
        assert len(all_page_ids) == len(set(all_page_ids)), "Pages should not overlap"
        assert set(all_page_ids) == set(matching_ids), "All pages combined should cover all matches"


class TestUserCreationAndRoles:
    """Pattern 6+4: First user = HOST, subsequent = USER, role enforcement."""

    def test_first_user_host_subsequent_user(self, users):
        """Verify HOST/USER role assignment and access control."""
        # Step 1: The host should have HOST role
        resp = api_get(f"/api/users/{users['host']['id']}", headers=users["host_headers"])
        assert resp.status_code == 200
        assert resp.json()["role"] == "HOST"

        # Step 2: Regular users have USER role
        resp = api_get(f"/api/users/{users['user_a']['id']}", headers=users["host_headers"])
        assert resp.status_code == 200
        assert resp.json()["role"] == "USER"

        resp = api_get(f"/api/users/{users['user_b']['id']}", headers=users["host_headers"])
        assert resp.status_code == 200
        assert resp.json()["role"] == "USER"

        # Step 3: List all users
        resp = api_get("/api/users", headers=users["host_headers"])
        assert resp.status_code == 200
        all_users = resp.json()
        assert isinstance(all_users, list)
        assert len(all_users) >= 3

        # Step 4: Each user has required fields
        for u in all_users:
            assert "id" in u
            assert "username" in u
            assert "role" in u
            assert "createdAt" in u
            assert "updatedAt" in u
            assert u["role"] in ("HOST", "USER")

        # Step 5: User A cannot create users
        resp = api_post("/api/users", {
            "username": f"fail_{UNIQUE}"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 403

        # Step 6: Request without auth header → 401
        resp = requests.get(f"{BASE_URL}/api/users", timeout=30)
        assert resp.status_code == 401


class TestMemoUpdateVisibilityTransition:
    """Pattern 5+6: Changing visibility dynamically affects access."""

    def test_visibility_change_affects_access(self, users):
        """Change memo from PUBLIC to PRIVATE → others lose access."""
        # Step 1: User A creates PUBLIC memo
        resp = api_post("/api/memos", {
            "content": f"Visibility transition {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo_id = resp.json()["id"]

        # Step 2: User B can access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 200

        # Step 3: User A changes to PRIVATE
        resp = api_patch(f"/api/memos/{memo_id}", {
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PRIVATE"

        # Step 4: User B can no longer access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 404

        # Step 5: User A still can access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PRIVATE"

        # Step 6: Change back to PROTECTED
        resp = api_patch(f"/api/memos/{memo_id}", {
            "visibility": "PROTECTED"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200

        # Step 7: User B can access again
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PROTECTED"
