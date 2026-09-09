"""
BackendForge — L2 Integration Tests for Memos Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned correctly
- Pattern 3: Filter/sort/pagination params declared but not implemented
- Pattern 4: Wrong status codes (200 vs 201/204)
- Pattern 5: Business logic exists but behavior is empty
- Pattern 6: Data isolation / visibility enforcement gaps
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Ordering/uniqueness constraints

"""

import time
from datetime import datetime, timedelta, timezone
import os
import uuid

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


def shifted_iso_timestamp(value, *, days):
    normalized = f"{value[:-1]}+00:00" if value.endswith(("Z", "z")) else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    shifted = parsed.astimezone(timezone.utc) + timedelta(days=days)
    return shifted.isoformat().replace("+00:00", "Z")


# ── Fixtures ──


@pytest.fixture(scope="session")
def users(base_users):
    """Use shared users from conftest."""
    return base_users


# ════════════════════════════════════════════════════════════════════
# L2 Tests: 3-5 steps, 8-12 assertions each
# ════════════════════════════════════════════════════════════════════


class TestCamelCaseFields:
    """Pattern 1: Verify camelCase field names in all response types."""

    def test_memo_response_uses_camel_case(self, users):
        """Memo creation and retrieval must use camelCase field names."""
        # Step 1: Create memo
        resp = api_post("/api/memos", {
            "content": f"camelCase test #hello {UNIQUE}",
            "visibility": "PUBLIC",
            "pinned": True
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        memo = resp.json()

        # Step 2: Verify all camelCase fields exist (NOT snake_case)
        assert "id" in memo
        assert "creatorId" in memo, f"Expected 'creatorId', got keys: {list(memo.keys())}"
        assert "creator_id" not in memo, "Should NOT have snake_case 'creator_id'"
        assert "createdAt" in memo, f"Expected 'createdAt', got keys: {list(memo.keys())}"
        assert "created_at" not in memo, "Should NOT have snake_case 'created_at'"
        assert "updatedAt" in memo, f"Expected 'updatedAt', got keys: {list(memo.keys())}"
        assert "updated_at" not in memo, "Should NOT have snake_case 'updated_at'"

        # Step 3: Verify field values
        assert memo["creatorId"] == users["host"]["id"]
        assert memo["visibility"] == "PUBLIC"
        assert memo["pinned"] is True
        assert isinstance(memo["tags"], list)
        assert "hello" in memo["tags"]

        # Step 4: GET the memo and verify same camelCase
        resp = api_get(f"/api/memos/{memo['id']}", headers=users["host_headers"])
        assert resp.status_code == 200
        fetched = resp.json()
        assert "creatorId" in fetched
        assert "createdAt" in fetched
        assert "updatedAt" in fetched
        assert fetched["creatorId"] == users["host"]["id"]

    def test_user_response_uses_camel_case(self, users):
        """User response must have camelCase fields."""
        # Step 1: Get user by ID
        resp = api_get(f"/api/users/{users['user_a']['id']}", headers=users["host_headers"])
        assert resp.status_code == 200
        user = resp.json()

        # Step 2: Verify camelCase field names
        assert "id" in user
        assert "username" in user
        assert "nickname" in user
        assert "avatarUrl" in user, f"Expected 'avatarUrl', got keys: {list(user.keys())}"
        assert "avatar_url" not in user, "Should NOT have snake_case 'avatar_url'"
        assert "createdAt" in user, f"Expected 'createdAt', got keys: {list(user.keys())}"
        assert "created_at" not in user
        assert "updatedAt" in user
        assert "updated_at" not in user
        assert "role" in user

        # Step 3: Verify values are correct
        assert user["role"] == "USER"
        assert isinstance(user["username"], str) and len(user["username"]) > 0
        assert user["nickname"] == "User A"

        # Step 4: List users and verify same format
        resp = api_get("/api/users", headers=users["host_headers"])
        assert resp.status_code == 200
        user_list = resp.json()
        assert isinstance(user_list, list)
        for u in user_list:
            assert "createdAt" in u, f"List user missing camelCase: {list(u.keys())}"
            assert "avatarUrl" in u

    def test_resource_response_uses_camel_case(self, users):
        """Resource response must have camelCase fields."""
        # Step 1: Create a memo to link
        resp = api_post("/api/memos", {
            "content": f"Resource link target {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        memo_id = resp.json()["id"]

        # Step 2: Create resource linked to memo
        resp = api_post("/api/resources", {
            "filename": f"camel_res_{UNIQUE}.png",
            "type": "image/png",
            "size": 4096,
            "memoId": memo_id
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        resource = resp.json()

        # Step 3: Verify camelCase fields
        assert "id" in resource
        assert "creatorId" in resource, f"Expected 'creatorId', got keys: {list(resource.keys())}"
        assert "creator_id" not in resource
        assert "memoId" in resource, f"Expected 'memoId', got keys: {list(resource.keys())}"
        assert "memo_id" not in resource
        assert "createdAt" in resource
        assert "created_at" not in resource
        assert "updatedAt" in resource
        assert "updated_at" not in resource

        # Step 4: Verify values
        assert resource["creatorId"] == users["user_a"]["id"]
        assert resource["memoId"] == memo_id
        assert resource["filename"] == f"camel_res_{UNIQUE}.png"
        assert resource["type"] == "image/png"
        assert resource["size"] == 4096

    def test_reaction_response_uses_camel_case(self, users):
        """Reaction response must have camelCase fields."""
        # Step 1: Create memo
        resp = api_post("/api/memos", {
            "content": f"Reaction camel test {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        memo_id = resp.json()["id"]

        # Step 2: Add reaction
        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "heart"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        reaction = resp.json()

        # Step 3: Verify camelCase fields
        assert "id" in reaction
        assert "creatorId" in reaction, f"Expected 'creatorId', got keys: {list(reaction.keys())}"
        assert "creator_id" not in reaction
        assert "memoId" in reaction, f"Expected 'memoId', got keys: {list(reaction.keys())}"
        assert "memo_id" not in reaction
        assert "reactionType" in reaction, f"Expected 'reactionType', got keys: {list(reaction.keys())}"
        assert "reaction_type" not in reaction
        assert "createdAt" in reaction
        assert "created_at" not in reaction

        # Step 4: Verify values
        assert reaction["creatorId"] == users["user_a"]["id"]
        assert reaction["memoId"] == memo_id
        assert reaction["reactionType"] == "heart"

    def test_memo_relation_response_uses_camel_case(self, users):
        """Memo relation response must have camelCase fields."""
        # Step 1: Create two memos
        resp = api_post("/api/memos", {
            "content": f"Relation src {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        src_id = resp.json()["id"]

        resp = api_post("/api/memos", {
            "content": f"Relation tgt {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        tgt_id = resp.json()["id"]

        # Step 2: Create relation
        resp = api_post(f"/api/memos/{src_id}/relations", {
            "relatedMemoId": tgt_id,
            "type": "REFERENCE"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        relation = resp.json()

        # Step 3: Verify camelCase fields
        assert "memoId" in relation, f"Expected 'memoId', got keys: {list(relation.keys())}"
        assert "memo_id" not in relation
        assert "relatedMemoId" in relation, f"Expected 'relatedMemoId', got keys: {list(relation.keys())}"
        assert "related_memo_id" not in relation
        assert "type" in relation

        # Step 4: Verify values
        assert relation["memoId"] == src_id
        assert relation["relatedMemoId"] == tgt_id
        assert relation["type"] == "REFERENCE"


class TestTagExtraction:
    """Pattern 2+5: Tag extraction actually works, not just empty arrays."""

    def test_multiple_tags_extracted_correctly(self, users):
        """Multiple different tags in content are all extracted."""
        # Step 1: Create memo with multiple tags
        resp = api_post("/api/memos", {
            "content": f"Working on #project-x and #coding with #2024goals {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo = resp.json()

        # Step 2: Verify tags are populated (not empty)
        assert isinstance(memo["tags"], list)
        assert len(memo["tags"]) == 3, f"Expected 3 tags, got {len(memo['tags'])}: {memo['tags']}"

        # Step 3: Verify specific tags
        assert "project-x" in memo["tags"]
        assert "coding" in memo["tags"]
        assert "2024goals" in memo["tags"]

        # Step 4: GET the memo and verify tags persist
        resp = api_get(f"/api/memos/{memo['id']}", headers=users["user_a_headers"])
        fetched = resp.json()
        assert set(fetched["tags"]) == {"project-x", "coding", "2024goals"}

    def test_duplicate_tags_deduplicated(self, users):
        """Same tag appearing multiple times results in single entry."""
        # Step 1: Create memo with duplicate tags
        resp = api_post("/api/memos", {
            "content": f"#dup #dup #dup #other {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        memo = resp.json()

        # Step 2: Verify deduplication
        assert "dup" in memo["tags"]
        assert "other" in memo["tags"]
        tag_counts = {}
        for t in memo["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        assert tag_counts.get("dup", 0) == 1, f"Tag 'dup' should appear once, got {tag_counts}"

    def test_tags_update_on_content_change(self, users):
        """When content is updated, tags are recalculated from scratch."""
        # Step 1: Create with tag A
        resp = api_post("/api/memos", {
            "content": f"#alpha initial {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        memo_id = resp.json()["id"]
        assert "alpha" in resp.json()["tags"]

        # Step 2: Update content to have tag B only
        resp = api_patch(f"/api/memos/{memo_id}", {
            "content": f"#beta replacement {UNIQUE}"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 200
        memo = resp.json()

        # Step 3: Verify tag A is gone, tag B is present
        assert "beta" in memo["tags"], f"New tag should be present: {memo['tags']}"
        assert "alpha" not in memo["tags"], f"Old tag should be gone: {memo['tags']}"

        # Step 4: Verify GET also reflects the change
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_a_headers"])
        assert "beta" in resp.json()["tags"]
        assert "alpha" not in resp.json()["tags"]

    def test_tag_count_reflects_actual_memo_count(self, users):
        """GET /api/tags returns accurate memo counts per tag."""
        tag = f"counttest{UNIQUE}"

        # Step 1: Create 3 memos with the tag
        for i in range(3):
            resp = api_post("/api/memos", {
                "content": f"#{tag} memo {i}",
                "visibility": "PRIVATE"
            }, headers=users["user_b_headers"])
            assert resp.status_code == 201

        # Step 2: Get tags
        resp = api_get("/api/tags", headers=users["user_b_headers"])
        assert resp.status_code == 200
        tags = resp.json()

        # Step 3: Verify format and count
        matching = [t for t in tags if t["tag"] == tag]
        assert len(matching) == 1, f"Expected one entry for tag '{tag}': {tags}"
        assert "tag" in matching[0]
        assert "count" in matching[0]
        assert matching[0]["count"] == 3, f"Expected count=3, got {matching[0]['count']}"


class TestVisibilityEnforcement:
    """Pattern 6: Data isolation between users."""

    def test_private_memo_not_in_list_for_others(self, users):
        """PRIVATE memos should not appear in other users' list results."""
        # Step 1: User A creates PRIVATE memo
        resp = api_post("/api/memos", {
            "content": f"Super secret {UNIQUE} vis_list_priv",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        private_id = resp.json()["id"]

        # Step 2: User A creates PUBLIC memo (control)
        resp = api_post("/api/memos", {
            "content": f"Open to all {UNIQUE} vis_list_priv",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        public_id = resp.json()["id"]

        # Step 3: User B lists User A's memos
        resp = api_get("/api/memos", params={
            "creatorId": users["user_a"]["id"],
            "search": f"{UNIQUE} vis_list_priv"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 200
        memo_ids = [m["id"] for m in resp.json()["memos"]]

        # Step 4: Verify isolation
        assert public_id in memo_ids, "PUBLIC memo should be visible to others"
        assert private_id not in memo_ids, "PRIVATE memo should NOT be visible to others"

    def test_private_memo_direct_access_returns_404(self, users):
        """GET /api/memos/{id} for a PRIVATE memo by non-owner returns 404."""
        # Step 1: User A creates PRIVATE memo
        resp = api_post("/api/memos", {
            "content": f"Direct access test {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["user_a_headers"])
        memo_id = resp.json()["id"]

        # Step 2: User B tries to access directly
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 404, f"PRIVATE memo should return 404, got {resp.status_code}"

        # Step 3: Owner can still access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200

        # Step 4: Verify it's the correct memo
        assert resp.json()["id"] == memo_id
        assert resp.json()["visibility"] == "PRIVATE"

    def test_protected_memo_visible_to_all_authenticated(self, users):
        """PROTECTED memos are visible to all authenticated users."""
        # Step 1: Host creates PROTECTED memo
        resp = api_post("/api/memos", {
            "content": f"Protected content {UNIQUE} prot_vis",
            "visibility": "PROTECTED"
        }, headers=users["host_headers"])
        memo_id = resp.json()["id"]

        # Step 2: User A can access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "PROTECTED"

        # Step 3: User B can also access
        resp = api_get(f"/api/memos/{memo_id}", headers=users["user_b_headers"])
        assert resp.status_code == 200

        # Step 4: Listed for User B when filtering by host
        resp = api_get("/api/memos", params={
            "creatorId": users["host"]["id"],
            "search": f"{UNIQUE} prot_vis"
        }, headers=users["user_b_headers"])
        assert resp.status_code == 200
        memo_ids = [m["id"] for m in resp.json()["memos"]]
        assert memo_id in memo_ids

    def test_resource_isolation_between_users(self, users):
        """Users cannot see each other's resources (returns 404, not 403)."""
        # Step 1: User A creates a resource
        resp = api_post("/api/resources", {
            "filename": f"secret_doc_{UNIQUE}.pdf",
            "type": "application/pdf",
            "size": 9999
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201
        res_id = resp.json()["id"]

        # Step 2: User B tries to GET it
        resp = api_get(f"/api/resources/{res_id}", headers=users["user_b_headers"])
        assert resp.status_code == 404, f"Other user's resource should be 404, got {resp.status_code}"

        # Step 3: User B lists resources — should NOT see User A's
        resp = api_get("/api/resources", headers=users["user_b_headers"])
        assert resp.status_code == 200
        res_ids = [r["id"] for r in resp.json()]
        assert res_id not in res_ids, "User B should not see User A's resources in list"

        # Step 4: Owner can access
        resp = api_get(f"/api/resources/{res_id}", headers=users["user_a_headers"])
        assert resp.status_code == 200
        assert resp.json()["id"] == res_id


class TestPaginationAndFiltering:
    """Pattern 3: Pagination/filtering params declared but not actually implemented."""

    def test_pagination_limit_actually_limits(self, users):
        """Limit param actually reduces result count (not just accepted and ignored)."""
        tag = f"pagelim{UNIQUE}"
        # Step 1: Create 5 memos
        for i in range(5):
            api_post("/api/memos", {
                "content": f"#{tag} page limit test {i}",
                "visibility": "PRIVATE"
            }, headers=users["host_headers"])

        # Step 2: Request with limit=2
        resp = api_get("/api/memos", params={
            "tag": tag, "limit": 2
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        data = resp.json()

        # Step 3: Verify limit is respected
        assert "memos" in data
        assert "total" in data
        assert len(data["memos"]) == 2, f"Limit=2 but got {len(data['memos'])} results"
        assert data["total"] == 5, f"Total should be 5, got {data['total']}"

    def test_pagination_offset_skips_correctly(self, users):
        """Offset param actually skips results (not just accepted and ignored)."""
        tag = f"pageoff{UNIQUE}"
        # Step 1: Create 4 memos
        for i in range(4):
            api_post("/api/memos", {
                "content": f"#{tag} offset test {i}",
                "visibility": "PRIVATE"
            }, headers=users["host_headers"])
            if i < 3:
                time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        # Step 2: Get page 1
        resp1 = api_get("/api/memos", params={
            "tag": tag, "limit": 2, "offset": 0
        }, headers=users["host_headers"])
        page1_ids = [m["id"] for m in resp1.json()["memos"]]

        # Step 3: Get page 2
        resp2 = api_get("/api/memos", params={
            "tag": tag, "limit": 2, "offset": 2
        }, headers=users["host_headers"])
        page2_ids = [m["id"] for m in resp2.json()["memos"]]

        # Step 4: Verify no overlap
        assert len(page1_ids) == 2
        assert len(page2_ids) == 2
        overlap = set(page1_ids) & set(page2_ids)
        assert not overlap, f"Pages should not overlap: {overlap}"

    def test_filter_by_tag_actually_filters(self, users):
        """Tag filter returns only matching memos, not all memos."""
        tag_a = f"filta{UNIQUE}"
        tag_b = f"filtb{UNIQUE}"

        # Step 1: Create memo with tag A
        resp = api_post("/api/memos", {
            "content": f"#{tag_a} memo",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        id_a = resp.json()["id"]

        # Step 2: Create memo with tag B
        resp = api_post("/api/memos", {
            "content": f"#{tag_b} memo",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        id_b = resp.json()["id"]

        # Step 3: Filter by tag A
        resp = api_get("/api/memos", params={"tag": tag_a}, headers=users["host_headers"])
        assert resp.status_code == 200
        memo_ids = [m["id"] for m in resp.json()["memos"]]

        # Step 4: Verify only tag A memo returned
        assert id_a in memo_ids, "Memo with matching tag should be returned"
        assert id_b not in memo_ids, "Memo without matching tag should NOT be returned"

    def test_filter_by_visibility_actually_filters(self, users):
        """Visibility filter works — returns only memos with matching visibility."""
        # Step 1: Create PUBLIC memo
        resp = api_post("/api/memos", {
            "content": f"Public filtvis {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        pub_id = resp.json()["id"]

        # Step 2: Create PRIVATE memo
        resp = api_post("/api/memos", {
            "content": f"Private filtvis {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        priv_id = resp.json()["id"]

        # Step 3: Filter by PUBLIC
        resp = api_get("/api/memos", params={
            "visibility": "PUBLIC",
            "search": f"filtvis {UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        memos = resp.json()["memos"]

        # Step 4: Verify filter works
        memo_ids = [m["id"] for m in memos]
        assert pub_id in memo_ids
        assert priv_id not in memo_ids
        for m in memos:
            assert m["visibility"] == "PUBLIC"

    def test_filter_by_pinned_actually_filters(self, users):
        """Pinned filter works — returns only pinned or unpinned memos."""
        # Step 1: Create pinned memo
        resp = api_post("/api/memos", {
            "content": f"Pinned filtpin {UNIQUE}",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=users["host_headers"])
        pinned_id = resp.json()["id"]

        # Step 2: Create unpinned memo
        resp = api_post("/api/memos", {
            "content": f"Unpinned filtpin {UNIQUE}",
            "visibility": "PRIVATE",
            "pinned": False
        }, headers=users["host_headers"])
        unpinned_id = resp.json()["id"]

        # Step 3: Filter pinned=true
        resp = api_get("/api/memos", params={
            "pinned": "true",
            "search": f"filtpin {UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        memo_ids = [m["id"] for m in resp.json()["memos"]]

        # Step 4: Verify
        assert pinned_id in memo_ids
        assert unpinned_id not in memo_ids

    def test_search_is_case_insensitive_substring(self, users):
        """Search is case-insensitive and substring-based."""
        # Step 1: Create memo with mixed case
        unique_word = f"XyZaBc{UNIQUE}"
        resp = api_post("/api/memos", {
            "content": f"Contains {unique_word} inside",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        memo_id = resp.json()["id"]

        # Step 2: Search with lowercase
        resp = api_get("/api/memos", params={
            "search": unique_word.lower()
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        found_ids = [m["id"] for m in resp.json()["memos"]]
        assert memo_id in found_ids, "Case-insensitive search should find the memo"

        # Step 3: Search with uppercase
        resp = api_get("/api/memos", params={
            "search": unique_word.upper()
        }, headers=users["host_headers"])
        found_ids = [m["id"] for m in resp.json()["memos"]]
        assert memo_id in found_ids, "Uppercase search should also find the memo"

    def test_total_count_ignores_pagination(self, users):
        """Total field in response reflects full filtered count, not paginated count."""
        tag = f"totalcnt{UNIQUE}"
        # Step 1: Create 6 memos
        for i in range(6):
            api_post("/api/memos", {
                "content": f"#{tag} total count {i}",
                "visibility": "PRIVATE"
            }, headers=users["host_headers"])

        # Step 2: Request with limit=2
        resp = api_get("/api/memos", params={
            "tag": tag, "limit": 2, "offset": 0
        }, headers=users["host_headers"])
        data = resp.json()

        # Step 3: Verify total is 6 even though we got 2
        assert len(data["memos"]) == 2
        assert data["total"] == 6, f"Total should be 6 (full count), got {data['total']}"

    def test_filter_by_creator_id(self, users):
        """creatorId filter returns only that user's memos."""
        # Step 1: User A creates a memo
        resp = api_post("/api/memos", {
            "content": f"User A creator filt {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_a_headers"])
        a_memo_id = resp.json()["id"]

        # Step 2: User B creates a memo
        resp = api_post("/api/memos", {
            "content": f"User B creator filt {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["user_b_headers"])
        b_memo_id = resp.json()["id"]

        # Step 3: Filter by User A's ID
        resp = api_get("/api/memos", params={
            "creatorId": users["user_a"]["id"],
            "search": f"creator filt {UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        memo_ids = [m["id"] for m in resp.json()["memos"]]

        # Step 4: Verify only User A's memo
        assert a_memo_id in memo_ids
        assert b_memo_id not in memo_ids


class TestPinnedOrdering:
    """Pattern 3+5: Pinned ordering actually works."""

    def test_pinned_always_before_unpinned(self, users):
        """Pinned memos ALWAYS appear before unpinned regardless of creation time."""
        tag = f"pinord{UNIQUE}"

        # Step 1: Create unpinned memo (older)
        resp = api_post("/api/memos", {
            "content": f"#{tag} unpinned first",
            "visibility": "PRIVATE",
            "pinned": False
        }, headers=users["user_b_headers"])
        unpinned_id = resp.json()["id"]
        time.sleep(TIMESTAMP_RESOLUTION_DELAY)

        # Step 2: Create pinned memo (newer)
        resp = api_post("/api/memos", {
            "content": f"#{tag} pinned second",
            "visibility": "PRIVATE",
            "pinned": True
        }, headers=users["user_b_headers"])
        pinned_id = resp.json()["id"]

        # Step 3: List memos
        resp = api_get("/api/memos", params={
            "tag": tag
        }, headers=users["user_b_headers"])
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["memos"]]

        # Step 4: Verify pinned comes first
        assert pinned_id in ids
        assert unpinned_id in ids
        assert ids.index(pinned_id) < ids.index(unpinned_id), \
            "Pinned memo must appear before unpinned"


class TestStatusCodes:
    """Pattern 4: Correct HTTP status codes."""

    def test_create_memo_returns_201(self, users):
        """POST /api/memos returns 201 (not 200)."""
        resp = api_post("/api/memos", {
            "content": f"Status test {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        assert resp.status_code == 201, f"Create should return 201, got {resp.status_code}"

    def test_create_resource_returns_201(self, users):
        """POST /api/resources returns 201 (not 200)."""
        resp = api_post("/api/resources", {
            "filename": f"status_{UNIQUE}.txt",
            "type": "text/plain",
            "size": 100
        }, headers=users["host_headers"])
        assert resp.status_code == 201, f"Create resource should return 201, got {resp.status_code}"

    def test_create_reaction_returns_201(self, users):
        """POST /api/memos/{id}/reactions returns 201 (not 200)."""
        resp = api_post("/api/memos", {
            "content": f"Status react {UNIQUE}",
            "visibility": "PUBLIC"
        }, headers=users["host_headers"])
        memo_id = resp.json()["id"]

        resp = api_post(f"/api/memos/{memo_id}/reactions", {
            "reactionType": "fire"
        }, headers=users["user_a_headers"])
        assert resp.status_code == 201, f"Create reaction should return 201, got {resp.status_code}"

    def test_delete_memo_returns_204(self, users):
        """DELETE /api/memos/{id} returns 204 (not 200)."""
        resp = api_post("/api/memos", {
            "content": f"Del status {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        memo_id = resp.json()["id"]

        resp = api_delete(f"/api/memos/{memo_id}", headers=users["host_headers"])
        assert resp.status_code == 204, f"Delete memo should return 204, got {resp.status_code}"

    def test_delete_resource_returns_204(self, users):
        """DELETE /api/resources/{id} returns 204 (not 200)."""
        resp = api_post("/api/resources", {
            "filename": f"del_status_{UNIQUE}.txt",
            "type": "text/plain",
            "size": 10
        }, headers=users["host_headers"])
        res_id = resp.json()["id"]

        resp = api_delete(f"/api/resources/{res_id}", headers=users["host_headers"])
        assert resp.status_code == 204, f"Delete resource should return 204, got {resp.status_code}"

    def test_delete_tag_returns_204(self, users):
        """DELETE /api/tags/{tag} returns 204 (not 200)."""
        tag = f"delstatustag{UNIQUE}"
        api_post("/api/memos", {
            "content": f"#{tag} test",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])

        resp = api_delete(f"/api/tags/{tag}", headers=users["host_headers"])
        assert resp.status_code == 204, f"Delete tag should return 204, got {resp.status_code}"

    def test_nonexistent_memo_returns_404_not_empty(self, users):
        """GET for nonexistent memo returns 404 (not 200 with empty/null)."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/memos/{fake_id}", headers=users["host_headers"])
        assert resp.status_code == 404, f"Nonexistent memo should be 404, got {resp.status_code}"

    def test_missing_auth_header_returns_401(self, users):
        """Request without X-User-Id returns 401."""
        resp = requests.get(f"{BASE_URL}/api/memos", timeout=30)
        assert resp.status_code == 401, f"Missing auth should be 401, got {resp.status_code}"

    def test_unregistered_user_cannot_create_memo(self, users):
        """Writes require an existing user; reads trust the header."""
        fake_headers = headers_for(str(uuid.uuid4()))
        resp = api_post("/api/memos", {"content": "Unknown user write", "visibility": "PRIVATE"}, headers=fake_headers)
        assert resp.status_code == 401, f"Unregistered user should be 401, got {resp.status_code}"


class TestMemoListResponseStructure:
    """Pattern 2: Response structure matches spec (memos array + total)."""

    def test_list_memos_has_correct_structure(self, users):
        """GET /api/memos response has 'memos' array and 'total' integer."""
        # Step 1: Create a memo
        api_post("/api/memos", {
            "content": f"Structure test {UNIQUE}",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])

        # Step 2: List memos
        resp = api_get("/api/memos", headers=users["host_headers"])
        assert resp.status_code == 200
        data = resp.json()

        # Step 3: Verify top-level structure
        assert "memos" in data, f"Response must have 'memos' key, got: {list(data.keys())}"
        assert "total" in data, f"Response must have 'total' key, got: {list(data.keys())}"
        assert isinstance(data["memos"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 1

        # Step 4: Verify each memo in list has correct fields
        for memo in data["memos"]:
            assert "id" in memo
            assert "creatorId" in memo
            assert "content" in memo
            assert "visibility" in memo
            assert "pinned" in memo
            assert "tags" in memo
            assert "createdAt" in memo
            assert "updatedAt" in memo
            assert isinstance(memo["tags"], list)
            assert isinstance(memo["pinned"], bool)


class TestDateFiltering:
    """Pattern 3: Date filtering params actually work."""

    def test_created_after_filter(self, users):
        """createdAfter filter excludes older memos."""
        # Step 1: Create memo
        resp = api_post("/api/memos", {
            "content": f"Date filter test {UNIQUE} dateaft",
            "visibility": "PRIVATE"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        memo = resp.json()
        created_at = memo["createdAt"]
        future_boundary = shifted_iso_timestamp(created_at, days=1)
        past_boundary = shifted_iso_timestamp(created_at, days=-1)

        # Step 2: Query with createdAfter set to far future
        resp = api_get("/api/memos", params={
            "createdAfter": future_boundary,
            "search": f"dateaft"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        assert len(resp.json()["memos"]) == 0, "Future date should exclude all memos"

        # Step 3: Query with createdAfter set to past
        resp = api_get("/api/memos", params={
            "createdAfter": past_boundary,
            "search": f"{UNIQUE} dateaft"
        }, headers=users["host_headers"])
        assert resp.status_code == 200
        assert len(resp.json()["memos"]) >= 1, "Past date should include memo"


class TestDefaultValues:
    """Pattern 5: Default values applied correctly."""

    def test_memo_default_visibility_is_private(self, users):
        """Memo without visibility defaults to PRIVATE."""
        resp = api_post("/api/memos", {
            "content": f"No vis specified {UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        assert resp.json()["visibility"] == "PRIVATE", \
            f"Default visibility should be PRIVATE, got {resp.json()['visibility']}"

    def test_memo_default_pinned_is_false(self, users):
        """Memo without pinned defaults to false."""
        resp = api_post("/api/memos", {
            "content": f"No pin specified {UNIQUE}"
        }, headers=users["host_headers"])
        assert resp.status_code == 201
        assert resp.json()["pinned"] is False, \
            f"Default pinned should be False, got {resp.json()['pinned']}"
