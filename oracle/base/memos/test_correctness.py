"""
BackendForge — Correctness Tests for Memos Task

Tests cover: CRUD, visibility rules, tag extraction, pinned ordering,
reactions uniqueness, memo relations, resource ownership, search, pagination.

"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# User IDs (will be registered via POST /api/users)
HOST_USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())

UNIQUE = uuid.uuid4().hex[:8]
TIMESTAMP_RESOLUTION_DELAY = 1.1


# ── HTTP Helpers ──

def headers_for(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


HOST_HEADERS = None  # Will be set after user creation
USER2_HEADERS = None
USER3_HEADERS = None


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ── Setup: Create users ──

@pytest.fixture(scope="session", autouse=True)
def setup_users(base_users):
    """Expose the shared session users through this module's legacy globals."""
    global HOST_HEADERS, USER2_HEADERS, USER3_HEADERS

    host_data = base_users["host"]
    user2_data = base_users["user_a"]
    user3_data = base_users["user_b"]

    assert host_data["role"] == "HOST", f"First user should be HOST, got {host_data['role']}"
    assert user2_data["role"] == "USER"

    HOST_HEADERS = base_users["host_headers"]
    USER2_HEADERS = base_users["user_a_headers"]
    USER3_HEADERS = base_users["user_b_headers"]

    return {"host": host_data, "user2": user2_data, "user3": user3_data}


def get_host_id():
    resp = api_get("/api/users", headers=HOST_HEADERS)
    users = resp.json()
    for u in users:
        if u["role"] == "HOST":
            return u["id"]
    return None


def get_user2_id():
    return USER2_HEADERS["X-User-Id"]


def get_user3_id():
    return USER3_HEADERS["X-User-Id"]


# ════════════════════════════════════════════════════════════════════
# PART 1: User CRUD & Auth
# ════════════════════════════════════════════════════════════════════


class TestAuth:
    """Authentication and authorization tests."""

    def test_missing_header_returns_401(self):
        """Request without X-User-Id header should return 401."""
        resp = requests.get(f"{BASE_URL}/api/memos", timeout=30)
        assert resp.status_code == 401, f"Expected 401 without header, got {resp.status_code}"

    def test_unregistered_user_returns_401(self):
        """Request with unknown user ID should return 401."""
        fake_headers = headers_for(str(uuid.uuid4()))
        resp = api_get("/api/memos", headers=fake_headers)
        assert resp.status_code == 401, f"Expected 401 for unregistered user, got {resp.status_code}"

    def test_first_user_is_host(self):
        """First created user should have HOST role."""
        resp = api_get("/api/users", headers=HOST_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        host_users = [u for u in users if u["role"] == "HOST"]
        assert len(host_users) >= 1, "Should have at least one HOST user"

    def test_non_host_cannot_create_user(self):
        """Regular USER cannot create new users."""
        resp = api_post("/api/users", {
            "username": f"unauthorized_{UNIQUE}",
        }, headers=USER2_HEADERS)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


class TestUserCRUD:
    """User profile management."""

    def test_list_users(self):
        """GET /api/users returns all users."""
        resp = api_get("/api/users", headers=HOST_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 3, f"Expected at least 3 users, got {len(users)}"

    def test_get_user_by_id(self):
        """GET /api/users/{id} returns user details."""
        user2_id = get_user2_id()
        resp = api_get(f"/api/users/{user2_id}", headers=HOST_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["id"] == user2_id
        assert "username" in user
        assert "role" in user
        assert "createdAt" in user

    def test_get_nonexistent_user_404(self):
        """GET /api/users/{id} with fake ID returns 404."""
        resp = api_get(f"/api/users/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_user_update_own_profile(self):
        """Users can update their own profile."""
        user2_id = get_user2_id()
        resp = api_patch(f"/api/users/{user2_id}", {
            "nickname": f"Updated Nick {UNIQUE}",
            "bio": "Updated bio"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["nickname"] == f"Updated Nick {UNIQUE}"
        assert user["bio"] == "Updated bio"

    def test_user_cannot_update_others(self):
        """Regular USER cannot update another user's profile."""
        host_id = get_host_id()
        resp = api_patch(f"/api/users/{host_id}", {
            "nickname": "Hacked"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_host_can_update_others(self):
        """HOST can update any user's profile."""
        user2_id = get_user2_id()
        resp = api_patch(f"/api/users/{user2_id}", {
            "nickname": f"Host Updated {UNIQUE}"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["nickname"] == f"Host Updated {UNIQUE}"


# ════════════════════════════════════════════════════════════════════
# PART 2: Memo CRUD
# ════════════════════════════════════════════════════════════════════


class TestMemoCRUD:
    """Basic memo create, read, update, delete."""

    def test_create_memo(self):
        """POST /api/memos creates a memo and returns it."""
        resp = api_post("/api/memos", {
            "content": f"Hello world #{UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201, f"Create memo failed: {resp.status_code} {resp.text}"
        memo = resp.json()
        assert memo["content"] == f"Hello world #{UNIQUE}"
        assert memo["visibility"] == "PRIVATE"
        assert memo["pinned"] is False
        assert "id" in memo
        assert "creatorId" in memo
        assert "createdAt" in memo
        assert "updatedAt" in memo
        assert "tags" in memo

    def test_create_memo_default_visibility(self):
        """Memo without explicit visibility defaults to PRIVATE."""
        resp = api_post("/api/memos", {
            "content": f"Default vis {UNIQUE}"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["visibility"] == "PRIVATE"

    def test_get_memo_by_id(self):
        """GET /api/memos/{id} returns memo details."""
        # Create
        resp = api_post("/api/memos", {
            "content": f"Get test {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        # Get
        resp = api_get(f"/api/memos/{memo_id}", headers=HOST_HEADERS)
        assert resp.status_code == 200
        memo = resp.json()
        assert memo["id"] == memo_id
        assert memo["content"] == f"Get test {UNIQUE}"

    def test_update_memo_content(self):
        """PATCH /api/memos/{id} updates content."""
        # Create
        resp = api_post("/api/memos", {
            "content": f"Before update {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        # Update
        resp = api_patch(f"/api/memos/{memo_id}", {
            "content": f"After update {UNIQUE}"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["content"] == f"After update {UNIQUE}"

    def test_update_memo_visibility(self):
        """PATCH can change visibility."""
        resp = api_post("/api/memos", {
            "content": f"Vis change {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_patch(f"/api/memos/{memo_id}", {
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PUBLIC"

    def test_update_memo_pinned(self):
        """PATCH can change pinned status."""
        resp = api_post("/api/memos", {
            "content": f"Pin test {UNIQUE}",
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_patch(f"/api/memos/{memo_id}", {
            "pinned": True
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["pinned"] is True

    def test_delete_memo(self):
        """DELETE /api/memos/{id} removes memo."""
        resp = api_post("/api/memos", {
            "content": f"Delete me {UNIQUE}",
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_delete(f"/api/memos/{memo_id}", headers=HOST_HEADERS)
        assert resp.status_code == 204

        # Verify gone
        resp = api_get(f"/api/memos/{memo_id}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_only_owner_can_update(self):
        """Non-owner cannot update a memo."""
        resp = api_post("/api/memos", {
            "content": f"Owner only {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_patch(f"/api/memos/{memo_id}", {
            "content": "Hacked!"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_only_owner_or_host_can_delete(self):
        """Non-owner non-HOST cannot delete a memo."""
        resp = api_post("/api/memos", {
            "content": f"User2 memo {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=USER2_HEADERS)
        memo_id = resp.json()["id"]

        # User3 cannot delete User2's memo
        resp = api_delete(f"/api/memos/{memo_id}", headers=USER3_HEADERS)
        assert resp.status_code == 403

        # HOST can delete anyone's memo
        resp = api_delete(f"/api/memos/{memo_id}", headers=HOST_HEADERS)
        assert resp.status_code == 204

    def test_get_nonexistent_memo_404(self):
        """GET /api/memos/{id} with fake ID returns 404."""
        resp = api_get(f"/api/memos/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Visibility Rules
# ════════════════════════════════════════════════════════════════════


class TestVisibility:
    """Memo visibility rules."""

    def test_private_memo_invisible_to_others(self):
        """PRIVATE memo is not visible to other users."""
        resp = api_post("/api/memos", {
            "content": f"Secret {UNIQUE} vis_private",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201
        memo_id = resp.json()["id"]

        # User2 cannot see it
        resp = api_get(f"/api/memos/{memo_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404, f"PRIVATE memo should be invisible, got {resp.status_code}"

    def test_protected_memo_visible_to_authenticated(self):
        """PROTECTED memo is visible to other authenticated users."""
        resp = api_post("/api/memos", {
            "content": f"Protected {UNIQUE} vis_protected",
            "visibility": "PROTECTED"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_get(f"/api/memos/{memo_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200, f"PROTECTED memo should be visible, got {resp.status_code}"

    def test_public_memo_visible_to_authenticated(self):
        """PUBLIC memo is visible to other authenticated users."""
        resp = api_post("/api/memos", {
            "content": f"Public {UNIQUE} vis_public",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_get(f"/api/memos/{memo_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200, f"PUBLIC memo should be visible, got {resp.status_code}"

    def test_list_memos_visibility_filtering(self):
        """Listing memos respects visibility rules."""
        # Create PRIVATE memo by HOST
        resp = api_post("/api/memos", {
            "content": f"ListPriv {UNIQUE} list_vis",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        private_id = resp.json()["id"]

        # Create PUBLIC memo by HOST
        resp = api_post("/api/memos", {
            "content": f"ListPub {UNIQUE} list_vis",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        public_id = resp.json()["id"]

        # User2 lists with creatorId=HOST
        host_id = get_host_id()
        resp = api_get("/api/memos", params={
            "creatorId": host_id,
            "search": f"{UNIQUE} list_vis"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        memo_ids = [m["id"] for m in memos]

        assert public_id in memo_ids, "PUBLIC memo should be visible to user2"
        assert private_id not in memo_ids, "PRIVATE memo should NOT be visible to user2"

    def test_owner_sees_all_own_memos(self):
        """Owner sees all their own memos regardless of visibility."""
        resp = api_post("/api/memos", {
            "content": f"OwnerPriv {UNIQUE} owner_all",
            "visibility": "PRIVATE"
        }, headers=USER2_HEADERS)
        private_id = resp.json()["id"]

        user2_id = get_user2_id()
        resp = api_get("/api/memos", params={
            "creatorId": user2_id,
            "search": f"{UNIQUE} owner_all"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        memo_ids = [m["id"] for m in memos]
        assert private_id in memo_ids, "Owner should see their own PRIVATE memo"


# ════════════════════════════════════════════════════════════════════
# PART 4: Tag Extraction & Management
# ════════════════════════════════════════════════════════════════════


class TestTags:
    """Tag auto-extraction and management."""

    def test_tags_extracted_on_create(self):
        """Tags are auto-extracted from content when creating a memo."""
        resp = api_post("/api/memos", {
            "content": f"Working on #project-alpha and #coding today {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201
        memo = resp.json()
        assert "tags" in memo
        assert "project-alpha" in memo["tags"], f"Tags: {memo['tags']}"
        assert "coding" in memo["tags"], f"Tags: {memo['tags']}"

    def test_tags_extracted_on_update(self):
        """Tags are recalculated when content is updated."""
        resp = api_post("/api/memos", {
            "content": f"#oldtag {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]
        assert "oldtag" in resp.json()["tags"]

        resp = api_patch(f"/api/memos/{memo_id}", {
            "content": f"#newtag {UNIQUE}"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        memo = resp.json()
        assert "newtag" in memo["tags"], f"Tags after update: {memo['tags']}"
        assert "oldtag" not in memo["tags"], f"Old tag should be gone: {memo['tags']}"

    def test_tag_list_with_counts(self):
        """GET /api/tags returns tags with counts for the user."""
        # Create memos with specific tags
        tag_name = f"counttag{UNIQUE}"
        api_post("/api/memos", {
            "content": f"#{tag_name} first memo",
            "visibility": "PRIVATE"
        }, headers=USER2_HEADERS)
        api_post("/api/memos", {
            "content": f"#{tag_name} second memo",
            "visibility": "PRIVATE"
        }, headers=USER2_HEADERS)
        api_post("/api/memos", {
            "content": f"#{tag_name} third memo",
            "visibility": "PRIVATE"
        }, headers=USER2_HEADERS)

        resp = api_get("/api/tags", headers=USER2_HEADERS)
        assert resp.status_code == 200
        tags = resp.json()
        matching = [t for t in tags if t["tag"] == tag_name]
        assert len(matching) == 1, f"Expected 1 tag entry for '{tag_name}', got {len(matching)}"
        assert matching[0]["count"] >= 3, f"Expected count >= 3, got {matching[0]['count']}"

    def test_tags_are_per_user(self):
        """Tags from one user don't appear in another user's tag list."""
        tag_name = f"userspecific{UNIQUE}"
        api_post("/api/memos", {
            "content": f"#{tag_name} memo",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)

        # User2 should NOT see this tag
        resp = api_get("/api/tags", headers=USER2_HEADERS)
        assert resp.status_code == 200
        user2_tags = [t["tag"] for t in resp.json()]
        assert tag_name not in user2_tags, f"User2 should not see HOST's tag: {user2_tags}"

    def test_delete_tag(self):
        """DELETE /api/tags/{tag} removes the tag from all user's memos."""
        tag_name = f"deltag{UNIQUE}"
        resp = api_post("/api/memos", {
            "content": f"Has #{tag_name} in content",
            "visibility": "PRIVATE"
        }, headers=USER3_HEADERS)
        memo_id = resp.json()["id"]

        # Delete the tag
        resp = api_delete(f"/api/tags/{tag_name}", headers=USER3_HEADERS)
        assert resp.status_code == 204

        # Memo content should no longer contain #tag_name
        resp = api_get(f"/api/memos/{memo_id}", headers=USER3_HEADERS)
        assert resp.status_code == 200
        memo = resp.json()
        assert f"#{tag_name}" not in memo["content"], (
            f"Tag should be removed from content: '{memo['content']}'"
        )
        assert tag_name not in memo["tags"], f"Tag should be removed from tags: {memo['tags']}"

    def test_rename_tag(self):
        """POST /api/tags/rename renames a tag in all user's memos."""
        old_tag = f"oldname{UNIQUE}"
        new_tag = f"newname{UNIQUE}"
        resp = api_post("/api/memos", {
            "content": f"Has #{old_tag} here",
            "visibility": "PRIVATE"
        }, headers=USER3_HEADERS)
        memo_id = resp.json()["id"]

        # Rename
        resp = api_post("/api/tags/rename", {
            "oldName": old_tag,
            "newName": new_tag
        }, headers=USER3_HEADERS)
        assert resp.status_code == 200

        # Memo should now have new tag
        resp = api_get(f"/api/memos/{memo_id}", headers=USER3_HEADERS)
        memo = resp.json()
        assert f"#{new_tag}" in memo["content"], (
            f"Content should contain #{new_tag}: '{memo['content']}'"
        )
        assert new_tag in memo["tags"], f"Tags should contain new tag: {memo['tags']}"
        assert old_tag not in memo["tags"], f"Old tag should be gone: {memo['tags']}"

    def test_filter_memos_by_tag(self):
        """GET /api/memos?tag=X returns only memos with that tag."""
        tag_name = f"filtertag{UNIQUE}"
        # Create memo WITH tag
        resp = api_post("/api/memos", {
            "content": f"#{tag_name} tagged memo filter_test",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        tagged_id = resp.json()["id"]

        # Create memo WITHOUT tag
        resp = api_post("/api/memos", {
            "content": f"No tag memo filter_test {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        untagged_id = resp.json()["id"]

        # Filter by tag
        resp = api_get("/api/memos", params={"tag": tag_name}, headers=HOST_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        memo_ids = [m["id"] for m in memos]
        assert tagged_id in memo_ids, "Tagged memo should appear"
        assert untagged_id not in memo_ids, "Untagged memo should NOT appear"


# ════════════════════════════════════════════════════════════════════
# PART 5: Pinned Ordering
# ════════════════════════════════════════════════════════════════════


class TestPinnedOrdering:
    """Pinned memos appear first in list."""

    def test_pinned_before_unpinned(self):
        """Pinned memos should appear before unpinned in listing."""
        # Create unpinned memo first
        resp = api_post("/api/memos", {
            "content": f"Unpinned first {UNIQUE} pinorder",
            "visibility": "PRIVATE",
            "pinned": False
        }, headers=USER3_HEADERS)
        unpinned_id = resp.json()["id"]

        time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        # Create pinned memo second (newer)
        resp = api_post("/api/memos", {
            "content": f"Pinned second {UNIQUE} pinorder",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=USER3_HEADERS)
        pinned_id = resp.json()["id"]

        # List memos
        user3_id = get_user3_id()
        resp = api_get("/api/memos", params={
            "creatorId": user3_id,
            "search": f"{UNIQUE} pinorder"
        }, headers=USER3_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]

        # Find positions
        ids = [m["id"] for m in memos]
        assert pinned_id in ids and unpinned_id in ids, (
            f"Both memos should be in list. IDs found: {ids}"
        )
        pinned_pos = ids.index(pinned_id)
        unpinned_pos = ids.index(unpinned_id)
        assert pinned_pos < unpinned_pos, (
            f"Pinned memo should come first. Pinned at {pinned_pos}, unpinned at {unpinned_pos}"
        )

    def test_pinned_ordered_by_created_desc(self):
        """Within pinned group, newer memos come first."""
        # Create two pinned memos
        resp = api_post("/api/memos", {
            "content": f"Pinned older {UNIQUE} pin_order2",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=USER3_HEADERS)
        older_id = resp.json()["id"]

        time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        resp = api_post("/api/memos", {
            "content": f"Pinned newer {UNIQUE} pin_order2",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=USER3_HEADERS)
        newer_id = resp.json()["id"]

        user3_id = get_user3_id()
        resp = api_get("/api/memos", params={
            "creatorId": user3_id,
            "search": f"{UNIQUE} pin_order2"
        }, headers=USER3_HEADERS)
        memos = resp.json()["memos"]
        ids = [m["id"] for m in memos]
        assert newer_id in ids and older_id in ids
        assert ids.index(newer_id) < ids.index(older_id), (
            "Newer pinned memo should come before older pinned memo"
        )


# ════════════════════════════════════════════════════════════════════
# PART 6: Reactions
# ════════════════════════════════════════════════════════════════════


class TestReactions:
    """Emoji reactions on memos."""

    def test_add_reaction(self):
        """POST /api/memos/{memoId}/reactions creates a reaction."""
        # Create a PUBLIC memo
        resp = api_post("/api/memos", {
            "content": f"React to me {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        # User2 reacts
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201, f"Create reaction failed: {resp.status_code} {resp.text}"
        reaction = resp.json()
        assert reaction["reactionType"] == "thumbs_up"
        assert reaction["memoId"] == memo_id
        assert "id" in reaction
        assert "creatorId" in reaction

    def test_list_reactions(self):
        """GET /api/memos/{memoId}/reactions returns all reactions."""
        resp = api_post("/api/memos", {
            "content": f"Reactions list {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        # Two users react
        api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "heart"
        }, headers=USER2_HEADERS)
        api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "laugh"
        }, headers=USER3_HEADERS)

        resp = api_get(f"/api/memos/{memo_id}/reactions", headers=HOST_HEADERS)
        assert resp.status_code == 200
        reactions = resp.json()
        assert len(reactions) >= 2, f"Expected at least 2 reactions, got {len(reactions)}"

    def test_duplicate_reaction_type_conflict(self):
        """Same user, same reactionType on same memo returns 409."""
        resp = api_post("/api/memos", {
            "content": f"Dup react {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        # First reaction
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201

        # Same reactionType again
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 409, (
            f"Duplicate reaction should return 409, got {resp.status_code}"
        )

    def test_different_reaction_types_allowed(self):
        """Same user can have different reaction types on same memo."""
        resp = api_post("/api/memos", {
            "content": f"Multi react {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201

        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "heart"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201, (
            f"Different reaction type should succeed, got {resp.status_code}"
        )

    def test_delete_reaction(self):
        """DELETE /api/reactions/{id} removes a reaction."""
        resp = api_post("/api/memos", {
            "content": f"Del react {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        reaction_id = resp.json()["id"]

        # Delete
        resp = api_delete(f"/api/reactions/{reaction_id}", headers=USER2_HEADERS)
        assert resp.status_code == 204

    def test_only_reactor_can_delete(self):
        """Only the user who created the reaction can delete it."""
        resp = api_post("/api/memos", {
            "content": f"React auth {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "thumbs_up"
        }, headers=USER2_HEADERS)
        reaction_id = resp.json()["id"]

        # User3 cannot delete User2's reaction
        resp = api_delete(f"/api/reactions/{reaction_id}", headers=USER3_HEADERS)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 7: Memo Relations
# ════════════════════════════════════════════════════════════════════


class TestRelations:
    """Memo-to-memo relations."""

    def test_create_relation(self):
        """POST /api/memos/{memoId}/relations creates a reference."""
        resp1 = api_post("/api/memos", {
            "content": f"Source memo {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        source_id = resp1.json()["id"]

        resp2 = api_post("/api/memos", {
            "content": f"Target memo {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        target_id = resp2.json()["id"]

        resp = api_post(f"/api/memos/{source_id}/relations", {
            "relatedMemoId": target_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201, f"Create relation failed: {resp.status_code} {resp.text}"
        relation = resp.json()
        assert relation["memoId"] == source_id
        assert relation["relatedMemoId"] == target_id
        assert relation["type"] == "REFERENCE"

    def test_list_relations(self):
        """GET /api/memos/{memoId}/relations returns relations."""
        resp1 = api_post("/api/memos", {
            "content": f"Rel list source {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        source_id = resp1.json()["id"]

        resp2 = api_post("/api/memos", {
            "content": f"Rel list target {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        target_id = resp2.json()["id"]

        api_post(f"/api/memos/{source_id}/relations", {
            "relatedMemoId": target_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)

        # List relations for source
        resp = api_get(f"/api/memos/{source_id}/relations", headers=HOST_HEADERS)
        assert resp.status_code == 200
        relations = resp.json()
        assert len(relations) >= 1
        rel_targets = [r["relatedMemoId"] for r in relations if r["memoId"] == source_id]
        assert target_id in rel_targets

    def test_self_reference_rejected(self):
        """A memo cannot reference itself."""
        resp = api_post("/api/memos", {
            "content": f"Self ref {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_post(f"/api/memos/{memo_id}/relations", {
            "relatedMemoId": memo_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 400, f"Self-reference should return 400, got {resp.status_code}"

    def test_duplicate_relation_conflict(self):
        """Same relation created twice returns 409."""
        resp1 = api_post("/api/memos", {
            "content": f"Dup rel source {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        source_id = resp1.json()["id"]

        resp2 = api_post("/api/memos", {
            "content": f"Dup rel target {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        target_id = resp2.json()["id"]

        # First
        resp = api_post(f"/api/memos/{source_id}/relations", {
            "relatedMemoId": target_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201

        # Duplicate
        resp = api_post(f"/api/memos/{source_id}/relations", {
            "relatedMemoId": target_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 409, (
            f"Duplicate relation should return 409, got {resp.status_code}"
        )

    def test_delete_relation(self):
        """DELETE /api/memos/{memoId}/relations/{relatedMemoId} removes relation."""
        resp1 = api_post("/api/memos", {
            "content": f"Del rel source {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        source_id = resp1.json()["id"]

        resp2 = api_post("/api/memos", {
            "content": f"Del rel target {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        target_id = resp2.json()["id"]

        api_post(f"/api/memos/{source_id}/relations", {
            "relatedMemoId": target_id,
            "type": "REFERENCE"
        }, headers=HOST_HEADERS)

        resp = api_delete(f"/api/memos/{source_id}/relations/{target_id}", headers=HOST_HEADERS)
        assert resp.status_code == 204

        # Verify gone
        resp = api_get(f"/api/memos/{source_id}/relations", headers=HOST_HEADERS)
        relations = resp.json()
        rel_targets = [r["relatedMemoId"] for r in relations if r["memoId"] == source_id]
        assert target_id not in rel_targets



# ════════════════════════════════════════════════════════════════════
# PART 8: Resources
# ════════════════════════════════════════════════════════════════════


class TestResources:
    """Resource metadata CRUD."""

    def test_create_resource(self):
        """POST /api/resources creates resource metadata."""
        resp = api_post("/api/resources", {
            "filename": f"photo_{UNIQUE}.png",
            "type": "image/png",
            "size": 12345
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201, f"Create resource failed: {resp.status_code} {resp.text}"
        resource = resp.json()
        assert resource["filename"] == f"photo_{UNIQUE}.png"
        assert resource["type"] == "image/png"
        assert resource["size"] == 12345
        assert "id" in resource
        assert "creatorId" in resource

    def test_list_resources(self):
        """GET /api/resources lists user's resources."""
        api_post("/api/resources", {
            "filename": f"list_res_{UNIQUE}.txt",
            "type": "text/plain",
            "size": 100
        }, headers=HOST_HEADERS)

        resp = api_get("/api/resources", headers=HOST_HEADERS)
        assert resp.status_code == 200
        resources = resp.json()
        assert isinstance(resources, list)
        assert len(resources) >= 1

    def test_get_resource(self):
        """GET /api/resources/{id} returns resource details."""
        resp = api_post("/api/resources", {
            "filename": f"get_res_{UNIQUE}.pdf",
            "type": "application/pdf",
            "size": 5000
        }, headers=HOST_HEADERS)
        res_id = resp.json()["id"]

        resp = api_get(f"/api/resources/{res_id}", headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["filename"] == f"get_res_{UNIQUE}.pdf"

    def test_update_resource(self):
        """PATCH /api/resources/{id} updates resource metadata."""
        resp = api_post("/api/resources", {
            "filename": f"upd_res_{UNIQUE}.jpg",
            "type": "image/jpeg",
            "size": 8000
        }, headers=HOST_HEADERS)
        res_id = resp.json()["id"]

        resp = api_patch(f"/api/resources/{res_id}", {
            "filename": f"renamed_{UNIQUE}.jpg"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["filename"] == f"renamed_{UNIQUE}.jpg"

    def test_delete_resource(self):
        """DELETE /api/resources/{id} removes resource."""
        resp = api_post("/api/resources", {
            "filename": f"del_res_{UNIQUE}.txt",
            "type": "text/plain",
            "size": 50
        }, headers=HOST_HEADERS)
        res_id = resp.json()["id"]

        resp = api_delete(f"/api/resources/{res_id}", headers=HOST_HEADERS)
        assert resp.status_code == 204

        resp = api_get(f"/api/resources/{res_id}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_resource_ownership(self):
        """Users can only see/modify their own resources."""
        resp = api_post("/api/resources", {
            "filename": f"owner_res_{UNIQUE}.txt",
            "type": "text/plain",
            "size": 100
        }, headers=HOST_HEADERS)
        res_id = resp.json()["id"]

        # User2 cannot access HOST's resource
        resp = api_get(f"/api/resources/{res_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404, f"Expected 404 for other's resource, got {resp.status_code}"

    def test_resource_linked_to_memo(self):
        """Resources can be linked to a memo via memoId."""
        resp = api_post("/api/memos", {
            "content": f"Memo with resource {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)
        memo_id = resp.json()["id"]

        resp = api_post("/api/resources", {
            "filename": f"linked_{UNIQUE}.png",
            "type": "image/png",
            "size": 3000,
            "memoId": memo_id
        }, headers=HOST_HEADERS)
        assert resp.status_code == 201
        resource = resp.json()
        assert resource["memoId"] == memo_id


# ════════════════════════════════════════════════════════════════════
# PART 9: Search & Pagination
# ════════════════════════════════════════════════════════════════════


class TestSearchAndPagination:
    """Search and pagination tests."""

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        content = f"UniqueSearchTerm{UNIQUE}"
        api_post("/api/memos", {
            "content": content,
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)

        # Search lowercase
        resp = api_get("/api/memos", params={
            "search": content.lower()
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        found = any(content in m["content"] for m in memos)
        assert found, f"Case-insensitive search should find memo"

    def test_pagination_limit(self):
        """Limit parameter controls result count."""
        # Create several memos
        for i in range(5):
            api_post("/api/memos", {
                "content": f"Pagination test {UNIQUE} page_{i}",
                "visibility": "PRIVATE"
            }, headers=HOST_HEADERS)

        resp = api_get("/api/memos", params={
            "limit": 2,
            "search": f"Pagination test {UNIQUE}"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["memos"]) <= 2, f"Limit=2 but got {len(data['memos'])} items"
        assert data["total"] >= 5, f"Total should be >= 5, got {data['total']}"

    def test_pagination_offset(self):
        """Offset parameter skips results."""
        marker = f"Pagination offset {UNIQUE}"
        for i in range(4):
            api_post("/api/memos", {
                "content": f"{marker} page_{i}",
                "visibility": "PRIVATE"
            }, headers=HOST_HEADERS)
            if i < 3:
                time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        resp1 = api_get("/api/memos", params={
            "limit": 2,
            "offset": 0,
            "search": marker
        }, headers=HOST_HEADERS)
        resp2 = api_get("/api/memos", params={
            "limit": 2,
            "offset": 2,
            "search": marker
        }, headers=HOST_HEADERS)

        ids1 = {m["id"] for m in resp1.json()["memos"]}
        ids2 = {m["id"] for m in resp2.json()["memos"]}
        overlap = ids1 & ids2
        assert not overlap, f"Different offsets should not overlap: {overlap}"

    def test_filter_by_visibility(self):
        """Filter memos by visibility."""
        api_post("/api/memos", {
            "content": f"Vis filter PUBLIC {UNIQUE} vf",
            "visibility": "PUBLIC"
        }, headers=HOST_HEADERS)
        api_post("/api/memos", {
            "content": f"Vis filter PRIVATE {UNIQUE} vf",
            "visibility": "PRIVATE"
        }, headers=HOST_HEADERS)

        resp = api_get("/api/memos", params={
            "visibility": "PUBLIC",
            "search": f"{UNIQUE} vf"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        for m in memos:
            assert m["visibility"] == "PUBLIC", f"Got visibility {m['visibility']}"

    def test_filter_by_pinned(self):
        """Filter memos by pinned status."""
        api_post("/api/memos", {
            "content": f"Pinned filter {UNIQUE} pf",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=HOST_HEADERS)
        api_post("/api/memos", {
            "content": f"Unpinned filter {UNIQUE} pf",
            "visibility": "PRIVATE",
            "pinned": False
        }, headers=HOST_HEADERS)

        resp = api_get("/api/memos", params={
            "pinned": "true",
            "search": f"{UNIQUE} pf"
        }, headers=HOST_HEADERS)
        assert resp.status_code == 200
        memos = resp.json()["memos"]
        for m in memos:
            assert m["pinned"] is True, f"All should be pinned"


# ════════════════════════════════════════════════════════════════════
# PART 10: 404 Handling
# ════════════════════════════════════════════════════════════════════


class TestNotFound:
    """404 responses for nonexistent resources."""

    def test_memo_not_found(self):
        resp = api_get(f"/api/memos/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_resource_not_found(self):
        resp = api_get(f"/api/resources/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_user_not_found(self):
        resp = api_get(f"/api/users/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_reaction_delete_not_found(self):
        resp = api_delete(f"/api/reactions/{uuid.uuid4()}", headers=HOST_HEADERS)
        assert resp.status_code == 404

    def test_relation_delete_not_found(self):
        resp = api_delete(
            f"/api/memos/{uuid.uuid4()}/relations/{uuid.uuid4()}", headers=HOST_HEADERS
        )
        assert resp.status_code == 404
