"""
BackendForge — Comprehensive Correctness Tests for Linkwarden Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# Users — UUIDs trusted directly via X-User-Id header
RUN_ID = uuid.uuid4().hex
USER1_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-1"))
USER2_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-2"))
USER3_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-3"))

USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}

UNIQUE = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent user namespaces."""
    global USER1_ID, USER2_ID, USER3_ID, USER1_HEADERS, USER2_HEADERS, USER3_HEADERS, UNIQUE

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER1_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-1"))
    USER2_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-2"))
    USER3_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-3"))
    USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
    USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
    USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}
    UNIQUE = item_id[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=USER1_HEADERS if headers is None else headers,
        timeout=30,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=USER1_HEADERS if headers is None else headers,
        timeout=30,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=USER1_HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, params=None, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        params=params,
        headers=USER1_HEADERS if headers is None else headers,
        timeout=30,
    )


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_auth_header_returns_401(self):
        """Any authenticated endpoint without X-User-Id returns 401."""
        resp = requests.get(f"{BASE_URL}/api/links", timeout=30)
        assert resp.status_code == 401

    def test_empty_auth_header_returns_401(self):
        """Empty X-User-Id header returns 401."""
        resp = requests.get(f"{BASE_URL}/api/links", headers={"X-User-Id": ""}, timeout=30)
        assert resp.status_code == 401

    def test_valid_auth_header_works(self):
        """Valid UUID in X-User-Id is accepted."""
        resp = api_get("/api/links")
        assert resp.status_code == 200

    def test_user_auto_created(self):
        """First request with a new UUID auto-creates the user."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}
        resp = api_get("/api/collections", headers=headers)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 3: Collections CRUD
# ════════════════════════════════════════════════════════════════════


class TestCollections:

    def test_create_collection(self):
        """Create a collection returns 201."""
        resp = api_post("/api/collections", {"name": f"TestCol-{UNIQUE}", "description": "Test desc", "color": "#ff0000"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"TestCol-{UNIQUE}"
        assert data["description"] == "Test desc"
        assert data["color"] == "#ff0000"
        assert data["ownerId"] == USER1_ID
        assert "id" in data
        assert "createdAt" in data

    def test_create_collection_name_required(self):
        """Creating a collection without a name returns 400."""
        resp = api_post("/api/collections", {"description": "no name"})
        assert resp.status_code == 400

    def test_list_collections(self):
        """List collections returns owned collections."""
        # Create one first
        api_post("/api/collections", {"name": f"ListTest-{UNIQUE}"})
        resp = api_get("/api/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert "collections" in data
        assert isinstance(data["collections"], list)
        names = [c["name"] for c in data["collections"]]
        assert f"ListTest-{UNIQUE}" in names

    def test_get_collection_by_id(self):
        """Get a single collection by ID."""
        create_resp = api_post("/api/collections", {"name": f"GetById-{UNIQUE}"})
        col_id = create_resp.json()["id"]
        resp = api_get(f"/api/collections/{col_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"GetById-{UNIQUE}"

    def test_get_collection_not_found(self):
        """Get non-existent collection returns 404."""
        resp = api_get("/api/collections/999999")
        assert resp.status_code == 404

    def test_update_collection(self):
        """Update a collection's name and color."""
        create_resp = api_post("/api/collections", {"name": f"UpdateMe-{UNIQUE}"})
        col_id = create_resp.json()["id"]
        resp = api_put(f"/api/collections/{col_id}", {"name": f"Updated-{UNIQUE}", "color": "#00ff00"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated-{UNIQUE}"
        assert resp.json()["color"] == "#00ff00"

    def test_update_collection_forbidden_for_non_owner(self):
        """Non-owner cannot update a collection."""
        create_resp = api_post("/api/collections", {"name": f"NotYours-{UNIQUE}"})
        col_id = create_resp.json()["id"]
        resp = api_put(f"/api/collections/{col_id}", {"name": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_delete_collection(self):
        """Delete a collection returns 200."""
        create_resp = api_post("/api/collections", {"name": f"DeleteMe-{UNIQUE}"})
        col_id = create_resp.json()["id"]
        resp = api_delete(f"/api/collections/{col_id}")
        assert resp.status_code == 200
        # Verify it's gone
        resp2 = api_get(f"/api/collections/{col_id}")
        assert resp2.status_code == 404

    def test_delete_collection_forbidden_for_non_owner(self):
        """Non-owner cannot delete a collection."""
        create_resp = api_post("/api/collections", {"name": f"CantDelete-{UNIQUE}"})
        col_id = create_resp.json()["id"]
        resp = api_delete(f"/api/collections/{col_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_collection_with_parent(self):
        """Create a nested collection with parentId."""
        parent_resp = api_post("/api/collections", {"name": f"Parent-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/collections", {"name": f"Child-{UNIQUE}", "parentId": parent_id})
        assert child_resp.status_code == 201
        assert child_resp.json()["parentId"] == parent_id

    def test_delete_collection_moves_links_to_unorganized(self):
        """Deleting a collection sets its links' collectionId to the Unorganized collection."""
        col_resp = api_post("/api/collections", {"name": f"WillDelete-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        # Create a link in that collection
        link_resp = api_post("/api/links", {"url": f"https://willdelete-{UNIQUE}.com", "collectionId": col_id})
        link_id = link_resp.json()["id"]
        # Delete collection
        api_delete(f"/api/collections/{col_id}")
        # Check link is now in Unorganized (collectionId points to Unorganized collection)
        link_resp2 = api_get(f"/api/links/{link_id}")
        assert link_resp2.status_code == 200
        # Link should still exist but in the Unorganized collection
        link_data = link_resp2.json()
        assert link_data["id"] == link_id
        # The collectionId should be the Unorganized collection (not null)
        # Verify it's not the deleted collection
        assert link_data["collectionId"] != col_id

    def test_delete_collection_with_children_cascade(self):
        """deleteChildren=true cascades to child collections."""
        parent_resp = api_post("/api/collections", {"name": f"CascadeParent-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/collections", {"name": f"CascadeChild-{UNIQUE}", "parentId": parent_id})
        child_id = child_resp.json()["id"]
        # Delete parent with cascade
        resp = api_delete(f"/api/collections/{parent_id}", params={"deleteChildren": "true"})
        assert resp.status_code == 200
        # Child should also be deleted
        resp2 = api_get(f"/api/collections/{child_id}")
        assert resp2.status_code == 404

    def test_delete_collection_without_children_flag_moves_children(self):
        """Without deleteChildren, child collections move to root."""
        parent_resp = api_post("/api/collections", {"name": f"NoCascadeParent-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/collections", {"name": f"NoCascadeChild-{UNIQUE}", "parentId": parent_id})
        child_id = child_resp.json()["id"]
        # Delete parent without cascade
        resp = api_delete(f"/api/collections/{parent_id}", params={"deleteChildren": "false"})
        assert resp.status_code == 200
        # Child should still exist with parentId = null
        resp2 = api_get(f"/api/collections/{child_id}")
        assert resp2.status_code == 200
        assert resp2.json()["parentId"] is None


# ════════════════════════════════════════════════════════════════════
# PART 4: Links CRUD
# ════════════════════════════════════════════════════════════════════


class TestLinks:

    def test_create_link(self):
        """Create a link returns 201."""
        resp = api_post("/api/links", {"url": f"https://example-{UNIQUE}.com", "name": "Example", "description": "A test link"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == f"https://example-{UNIQUE}.com"
        assert data["name"] == "Example"
        assert data["description"] == "A test link"
        assert data["createdBy"] == USER1_ID
        assert "id" in data
        assert "createdAt" in data

    def test_create_link_url_required(self):
        """Creating a link without url returns 400."""
        resp = api_post("/api/links", {"name": "No URL"})
        assert resp.status_code == 400

    def test_create_link_with_collection(self):
        """Create a link in a specific collection."""
        col_resp = api_post("/api/collections", {"name": f"LinkCol-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        link_resp = api_post("/api/links", {"url": f"https://in-col-{UNIQUE}.com", "collectionId": col_id})
        assert link_resp.status_code == 201
        assert link_resp.json()["collectionId"] == col_id

    def test_create_link_with_tags(self):
        """Create a link with tags auto-creates tags."""
        resp = api_post("/api/links", {
            "url": f"https://tagged-{UNIQUE}.com",
            "name": "Tagged link",
            "tags": [{"name": f"tag-a-{UNIQUE}"}, {"name": f"tag-b-{UNIQUE}"}]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "tags" in data
        tag_names = [t["name"] for t in data["tags"]]
        assert f"tag-a-{UNIQUE}" in tag_names
        assert f"tag-b-{UNIQUE}" in tag_names

    def test_create_link_in_unorganized_by_default(self):
        """Link without collectionId goes to the Unorganized collection."""
        resp = api_post("/api/links", {"url": f"https://unorg-{UNIQUE}.com"})
        assert resp.status_code == 201
        data = resp.json()
        # collectionId should be set (Unorganized collection)
        assert data["collectionId"] is not None

    def test_list_links(self):
        """List links returns links for the user."""
        # Create a link to ensure there's at least one
        api_post("/api/links", {"url": f"https://list-test-{UNIQUE}.com"})
        resp = api_get("/api/links")
        assert resp.status_code == 200
        data = resp.json()
        assert "links" in data
        assert "total" in data
        assert isinstance(data["links"], list)
        assert data["total"] >= 1

    def test_list_links_pagination(self):
        """List links supports limit and offset."""
        # Create a few links
        for i in range(3):
            api_post("/api/links", {"url": f"https://page-{UNIQUE}-{i}.com"})
        resp = api_get("/api/links", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["links"]) <= 2

    def test_list_links_filter_by_collection(self):
        """List links can filter by collectionId."""
        col_resp = api_post("/api/collections", {"name": f"FilterCol-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_post("/api/links", {"url": f"https://filter-me-{UNIQUE}.com", "collectionId": col_id})
        resp = api_get("/api/links", params={"collectionId": col_id})
        assert resp.status_code == 200
        data = resp.json()
        for link in data["links"]:
            assert link["collectionId"] == col_id

    def test_get_link_by_id(self):
        """Get a single link by ID."""
        create_resp = api_post("/api/links", {"url": f"https://get-by-id-{UNIQUE}.com"})
        link_id = create_resp.json()["id"]
        resp = api_get(f"/api/links/{link_id}")
        assert resp.status_code == 200
        assert resp.json()["url"] == f"https://get-by-id-{UNIQUE}.com"

    def test_get_link_not_found(self):
        """Get non-existent link returns 404."""
        resp = api_get("/api/links/999999")
        assert resp.status_code == 404

    def test_update_link(self):
        """Update a link's name and description."""
        create_resp = api_post("/api/links", {"url": f"https://update-link-{UNIQUE}.com"})
        link_id = create_resp.json()["id"]
        resp = api_put(f"/api/links/{link_id}", {"name": "Updated name", "description": "Updated desc"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated name"
        assert resp.json()["description"] == "Updated desc"

    def test_update_link_tags(self):
        """Update a link's tags."""
        create_resp = api_post("/api/links", {"url": f"https://update-tags-{UNIQUE}.com", "tags": [{"name": f"old-{UNIQUE}"}]})
        link_id = create_resp.json()["id"]
        resp = api_put(f"/api/links/{link_id}", {"tags": [{"name": f"new-{UNIQUE}"}]})
        assert resp.status_code == 200
        tag_names = [t["name"] for t in resp.json()["tags"]]
        assert f"new-{UNIQUE}" in tag_names
        assert f"old-{UNIQUE}" not in tag_names

    def test_delete_link(self):
        """Delete a link returns 200."""
        create_resp = api_post("/api/links", {"url": f"https://delete-link-{UNIQUE}.com"})
        link_id = create_resp.json()["id"]
        resp = api_delete(f"/api/links/{link_id}")
        assert resp.status_code == 200
        # Verify it's gone
        resp2 = api_get(f"/api/links/{link_id}")
        assert resp2.status_code == 404

    def test_delete_link_forbidden_for_other_user(self):
        """Another user cannot delete someone else's link (unless shared)."""
        create_resp = api_post("/api/links", {"url": f"https://nodelete-{UNIQUE}.com"})
        link_id = create_resp.json()["id"]
        resp = api_delete(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_data_isolation_links(self):
        """User2 cannot see User1's links by default."""
        api_post("/api/links", {"url": f"https://isolated-{UNIQUE}.com"})
        resp = api_get("/api/links", headers=USER2_HEADERS)
        data = resp.json()
        urls = [l["url"] for l in data["links"]]
        assert f"https://isolated-{UNIQUE}.com" not in urls


# ════════════════════════════════════════════════════════════════════
# PART 5: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        """Create a tag returns 201."""
        resp = api_post("/api/tags", {"name": f"newtag-{UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"newtag-{UNIQUE}"
        assert data["ownerId"] == USER1_ID
        assert "id" in data

    def test_create_duplicate_tag_returns_existing(self):
        """Creating a tag with the same name returns the existing tag (200)."""
        api_post("/api/tags", {"name": f"dupetag-{UNIQUE}"})
        resp = api_post("/api/tags", {"name": f"dupetag-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"dupetag-{UNIQUE}"

    def test_create_duplicate_tag_case_insensitive(self):
        """Tag deduplication is case-insensitive."""
        api_post("/api/tags", {"name": f"CaseTag-{UNIQUE}"})
        resp = api_post("/api/tags", {"name": f"casetag-{UNIQUE}"})
        assert resp.status_code == 200

    def test_list_tags(self):
        """List tags returns user's tags."""
        api_post("/api/tags", {"name": f"listtag-{UNIQUE}"})
        resp = api_get("/api/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        tag_names = [t["name"] for t in data["tags"]]
        assert f"listtag-{UNIQUE}" in tag_names

    def test_tags_per_user_isolation(self):
        """Tags are per-user: user2's tags are separate."""
        api_post("/api/tags", {"name": f"user1tag-{UNIQUE}"})
        resp = api_get("/api/tags", headers=USER2_HEADERS)
        data = resp.json()
        tag_names = [t["name"] for t in data["tags"]]
        assert f"user1tag-{UNIQUE}" not in tag_names

    def test_update_tag(self):
        """Rename a tag."""
        create_resp = api_post("/api/tags", {"name": f"rename-me-{UNIQUE}"})
        tag_id = create_resp.json()["id"]
        resp = api_put(f"/api/tags/{tag_id}", {"name": f"renamed-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"renamed-{UNIQUE}"

    def test_update_tag_not_found(self):
        """Update non-existent tag returns 404."""
        resp = api_put("/api/tags/999999", {"name": "no"})
        assert resp.status_code == 404

    def test_delete_tag(self):
        """Delete a tag."""
        create_resp = api_post("/api/tags", {"name": f"deleteme-{UNIQUE}"})
        tag_id = create_resp.json()["id"]
        resp = api_delete(f"/api/tags/{tag_id}")
        assert resp.status_code == 200

    def test_delete_tag_removes_from_links(self):
        """Deleting a tag removes it from associated links."""
        # Create a link with a tag
        tag_name = f"removelink-{UNIQUE}"
        link_resp = api_post("/api/links", {"url": f"https://tagremove-{UNIQUE}.com", "tags": [{"name": tag_name}]})
        link_id = link_resp.json()["id"]
        # Find the tag id
        tags_resp = api_get("/api/tags")
        tag_id = None
        for t in tags_resp.json()["tags"]:
            if t["name"] == tag_name:
                tag_id = t["id"]
                break
        assert tag_id is not None
        # Delete the tag
        api_delete(f"/api/tags/{tag_id}")
        # Check the link no longer has that tag
        link_resp2 = api_get(f"/api/links/{link_id}")
        tag_names = [t["name"] for t in link_resp2.json()["tags"]]
        assert tag_name not in tag_names


# ════════════════════════════════════════════════════════════════════
# PART 6: Collection Members (Sharing)
# ════════════════════════════════════════════════════════════════════


class TestCollectionMembers:

    def test_add_member(self):
        """Owner can add a member to their collection."""
        col_resp = api_post("/api/collections", {"name": f"ShareCol-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        # Ensure user2 exists by making a request
        api_get("/api/collections", headers=USER2_HEADERS)
        resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["userId"] == USER2_ID
        assert data["role"] == "viewer"
        assert data["collectionId"] == col_id

    def test_list_members(self):
        """List members of a collection."""
        col_resp = api_post("/api/collections", {"name": f"ListMem-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "admin"})
        resp = api_get(f"/api/collections/{col_id}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data
        # Should have at least owner + the added member
        assert len(data["members"]) >= 2

    def test_update_member_role(self):
        """Owner can update a member's role."""
        col_resp = api_post("/api/collections", {"name": f"RoleChange-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        add_resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        member_id = add_resp.json()["id"]
        resp = api_put(f"/api/collections/{col_id}/members/{member_id}", {"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_remove_member(self):
        """Owner can remove a member."""
        col_resp = api_post("/api/collections", {"name": f"RemoveMem-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        add_resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        member_id = add_resp.json()["id"]
        resp = api_delete(f"/api/collections/{col_id}/members/{member_id}")
        assert resp.status_code == 200

    def test_non_owner_cannot_add_member(self):
        """Non-owner/non-admin cannot add members."""
        col_resp = api_post("/api/collections", {"name": f"NoAdd-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER3_HEADERS)
        # User2 is not a member yet, try to add user3
        resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER3_ID, "role": "viewer"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_duplicate_member_returns_error(self):
        """Adding the same user twice returns an error."""
        col_resp = api_post("/api/collections", {"name": f"DupMem-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "admin"})
        # Should be conflict or bad request
        assert resp.status_code in (400, 409)

    def test_shared_collection_visible_to_member(self):
        """A shared collection appears in the member's collection list."""
        col_resp = api_post("/api/collections", {"name": f"SharedVisible-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 should see this collection
        resp = api_get("/api/collections", headers=USER2_HEADERS)
        col_ids = [c["id"] for c in resp.json()["collections"]]
        assert col_id in col_ids

    def test_viewer_cannot_add_links(self):
        """A viewer cannot create links in the shared collection."""
        col_resp = api_post("/api/collections", {"name": f"ViewerNoWrite-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 tries to add a link to this collection
        resp = api_post("/api/links", {"url": f"https://viewer-add-{UNIQUE}.com", "collectionId": col_id}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_contributor_can_add_links(self):
        """A contributor can create links in the shared collection."""
        col_resp = api_post("/api/collections", {"name": f"ContribWrite-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "contributor"})
        resp = api_post("/api/links", {"url": f"https://contrib-add-{UNIQUE}.com", "collectionId": col_id}, headers=USER2_HEADERS)
        assert resp.status_code == 201

    def test_viewer_can_read_links_in_shared_collection(self):
        """A viewer can read links in the shared collection."""
        col_resp = api_post("/api/collections", {"name": f"ViewerRead-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        # Owner adds a link
        link_resp = api_post("/api/links", {"url": f"https://viewer-read-{UNIQUE}.com", "collectionId": col_id})
        link_id = link_resp.json()["id"]
        # Add user2 as viewer
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 can read the link
        resp = api_get(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_admin_can_update_member_role(self):
        """An admin cannot update member roles; role changes are owner-only."""
        col_resp = api_post("/api/collections", {"name": f"AdminRole-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_get("/api/collections", headers=USER3_HEADERS)
        # Add user2 as admin
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "admin"})
        # Add user3 as viewer
        add_resp = api_post(f"/api/collections/{col_id}/members", {"userId": USER3_ID, "role": "viewer"})
        member3_id = add_resp.json()["id"]
        # User2 (admin) cannot update user3's role.
        resp = api_put(f"/api/collections/{col_id}/members/{member3_id}", {"role": "contributor"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

        members = api_get(f"/api/collections/{col_id}/members").json()["members"]
        member3 = next(member for member in members if member["id"] == member3_id)
        assert member3["role"] == "viewer"


# ════════════════════════════════════════════════════════════════════
# PART 7: Highlights
# ════════════════════════════════════════════════════════════════════


class TestHighlights:

    def test_create_highlight(self):
        """Create a highlight on a link."""
        link_resp = api_post("/api/links", {"url": f"https://highlight-{UNIQUE}.com"})
        link_id = link_resp.json()["id"]
        resp = api_post(f"/api/links/{link_id}/highlights", {"text": "Important text", "color": "#ffff00", "note": "My note"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Important text"
        assert data["color"] == "#ffff00"
        assert data["note"] == "My note"
        assert data["linkId"] == link_id
        assert data["createdBy"] == USER1_ID

    def test_list_highlights(self):
        """List highlights for a link."""
        link_resp = api_post("/api/links", {"url": f"https://list-hl-{UNIQUE}.com"})
        link_id = link_resp.json()["id"]
        api_post(f"/api/links/{link_id}/highlights", {"text": "Highlight 1"})
        api_post(f"/api/links/{link_id}/highlights", {"text": "Highlight 2"})
        resp = api_get(f"/api/links/{link_id}/highlights")
        assert resp.status_code == 200
        data = resp.json()
        assert "highlights" in data
        assert len(data["highlights"]) >= 2

    def test_update_highlight(self):
        """Update a highlight's text."""
        link_resp = api_post("/api/links", {"url": f"https://update-hl-{UNIQUE}.com"})
        link_id = link_resp.json()["id"]
        hl_resp = api_post(f"/api/links/{link_id}/highlights", {"text": "Original"})
        hl_id = hl_resp.json()["id"]
        resp = api_put(f"/api/highlights/{hl_id}", {"text": "Updated", "color": "#00ff00"})
        assert resp.status_code == 200
        assert resp.json()["text"] == "Updated"
        assert resp.json()["color"] == "#00ff00"

    def test_delete_highlight(self):
        """Delete a highlight."""
        link_resp = api_post("/api/links", {"url": f"https://delete-hl-{UNIQUE}.com"})
        link_id = link_resp.json()["id"]
        hl_resp = api_post(f"/api/links/{link_id}/highlights", {"text": "Delete me"})
        hl_id = hl_resp.json()["id"]
        resp = api_delete(f"/api/highlights/{hl_id}")
        assert resp.status_code == 200

    def test_highlight_on_nonexistent_link(self):
        """Creating a highlight on a non-existent link returns 404."""
        resp = api_post("/api/links/999999/highlights", {"text": "No link"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Public Collections
# ════════════════════════════════════════════════════════════════════


class TestPublicCollections:

    def test_public_collection_accessible_without_auth(self):
        """Public collections are accessible without auth."""
        col_resp = api_post("/api/collections", {"name": f"Public-{UNIQUE}", "isPublic": True})
        col_id = col_resp.json()["id"]
        # No auth header
        resp = requests.get(f"{BASE_URL}/api/public/collections/{col_id}", timeout=30)
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Public-{UNIQUE}"

    def test_private_collection_not_accessible_publicly(self):
        """Private collections return 404 on public endpoint."""
        col_resp = api_post("/api/collections", {"name": f"Private-{UNIQUE}", "isPublic": False})
        col_id = col_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/api/public/collections/{col_id}", timeout=30)
        assert resp.status_code == 404

    def test_public_collection_links_accessible(self):
        """Links in a public collection are accessible without auth."""
        col_resp = api_post("/api/collections", {"name": f"PubLinks-{UNIQUE}", "isPublic": True})
        col_id = col_resp.json()["id"]
        api_post("/api/links", {"url": f"https://public-link-{UNIQUE}.com", "collectionId": col_id})
        resp = requests.get(f"{BASE_URL}/api/public/collections/{col_id}/links", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "links" in data
        assert len(data["links"]) >= 1


# ════════════════════════════════════════════════════════════════════
# PART 9: Search
# ════════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_by_name(self):
        """Search finds links by name."""
        search_term = f"searchable-{UNIQUE}"
        api_post("/api/links", {"url": f"https://search1-{UNIQUE}.com", "name": search_term})
        resp = api_get("/api/search", params={"q": search_term})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [l["name"] for l in data["links"]]
        assert any(search_term in n for n in names)

    def test_search_by_url(self):
        """Search finds links by URL."""
        unique_url = f"https://findme-unique-url-{UNIQUE}.com"
        api_post("/api/links", {"url": unique_url, "name": "URL search test"})
        resp = api_get("/api/search", params={"q": f"findme-unique-url-{UNIQUE}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_by_description(self):
        """Search finds links by description."""
        desc = f"unique-desc-{UNIQUE}"
        api_post("/api/links", {"url": f"https://search-desc-{UNIQUE}.com", "description": desc})
        resp = api_get("/api/search", params={"q": desc})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_is_user_scoped(self):
        """Search only returns links the user has access to."""
        secret_term = f"secret-{UNIQUE}"
        api_post("/api/links", {"url": f"https://secret-{UNIQUE}.com", "name": secret_term})
        # User2 searches - should not find user1's link
        resp = api_get("/api/search", params={"q": secret_term}, headers=USER2_HEADERS)
        data = resp.json()
        names = [l["name"] for l in data["links"]]
        assert secret_term not in names

    def test_search_includes_shared_collection_links(self):
        """Search includes links from shared collections."""
        col_resp = api_post("/api/collections", {"name": f"SearchShare-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        shared_term = f"shared-search-{UNIQUE}"
        api_post("/api/links", {"url": f"https://shared-search-{UNIQUE}.com", "name": shared_term, "collectionId": col_id})
        # Share with user2
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 can find it
        resp = api_get("/api/search", params={"q": shared_term}, headers=USER2_HEADERS)
        data = resp.json()
        assert data["total"] >= 1

    def test_search_empty_query_returns_empty(self):
        """Empty search query returns empty results."""
        resp = api_get("/api/search", params={"q": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["links"] == []


# ════════════════════════════════════════════════════════════════════
# PART 10: Dashboard
# ════════════════════════════════════════════════════════════════════


class TestDashboard:

    def test_dashboard_returns_stats(self):
        """Dashboard returns the expected stat fields."""
        # Ensure user1 has some data
        api_post("/api/links", {"url": f"https://dash-{UNIQUE}.com"})
        resp = api_get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "totalLinks" in data
        assert "totalCollections" in data
        assert "totalTags" in data
        assert "linksPerDay" in data
        assert isinstance(data["linksPerDay"], list)

    def test_dashboard_links_per_day_has_7_entries(self):
        """linksPerDay has entries for the last 7 days."""
        resp = api_get("/api/dashboard")
        data = resp.json()
        assert len(data["linksPerDay"]) == 7

    def test_dashboard_links_per_day_structure(self):
        """Each entry in linksPerDay has date and count."""
        resp = api_get("/api/dashboard")
        data = resp.json()
        for entry in data["linksPerDay"]:
            assert "date" in entry
            assert "count" in entry

    def test_dashboard_requires_auth(self):
        """Dashboard requires authentication."""
        resp = requests.get(f"{BASE_URL}/api/dashboard", timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 11: Export
# ════════════════════════════════════════════════════════════════════


class TestExport:

    def test_export_returns_links(self):
        """Export returns the user's links."""
        api_post("/api/links", {"url": f"https://export-{UNIQUE}.com", "name": "Export test"})
        resp = api_get("/api/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "links" in data
        assert isinstance(data["links"], list)
        assert len(data["links"]) >= 1

    def test_export_only_own_links(self):
        """Export only includes the user's own links."""
        api_post("/api/links", {"url": f"https://export-own-{UNIQUE}.com"})
        resp = api_get("/api/export", headers=USER2_HEADERS)
        data = resp.json()
        urls = [l["url"] for l in data["links"]]
        assert f"https://export-own-{UNIQUE}.com" not in urls

    def test_export_requires_auth(self):
        """Export requires authentication."""
        resp = requests.get(f"{BASE_URL}/api/export", timeout=30)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 12: Bulk Import
# ════════════════════════════════════════════════════════════════════


class TestBulkImport:

    def test_bulk_import_links(self):
        """Bulk import creates multiple links."""
        links_data = [
            {"url": f"https://bulk1-{UNIQUE}.com", "name": "Bulk 1"},
            {"url": f"https://bulk2-{UNIQUE}.com", "name": "Bulk 2"},
            {"url": f"https://bulk3-{UNIQUE}.com", "name": "Bulk 3"},
        ]
        resp = api_post("/api/links/bulk", {"links": links_data})
        assert resp.status_code == 201
        data = resp.json()
        assert "links" in data
        assert "count" in data
        assert data["count"] == 3
        assert len(data["links"]) == 3

    def test_bulk_import_with_tags(self):
        """Bulk import with tags."""
        links_data = [
            {"url": f"https://bulk-tag-{UNIQUE}.com", "name": "Bulk tag", "tags": [{"name": f"bulk-t-{UNIQUE}"}]}
        ]
        resp = api_post("/api/links/bulk", {"links": links_data})
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["links"]) == 1
        assert len(data["links"][0]["tags"]) >= 1


# ════════════════════════════════════════════════════════════════════
# PART 13: Unorganized Collection Behavior
# ════════════════════════════════════════════════════════════════════


class TestUnorganizedCollection:

    def test_unorganized_collection_auto_created(self):
        """An Unorganized collection is auto-created for the user."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}
        resp = api_get("/api/collections", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        names = [c["name"] for c in data["collections"]]
        assert "Unorganized" in names

    def test_unorganized_collection_cannot_be_deleted(self):
        """The Unorganized collection cannot be deleted."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}
        # Trigger creation
        resp = api_get("/api/collections", headers=headers)
        data = resp.json()
        unorg_id = None
        for c in data["collections"]:
            if c["name"] == "Unorganized":
                unorg_id = c["id"]
                break
        assert unorg_id is not None
        # Try to delete it
        del_resp = api_delete(f"/api/collections/{unorg_id}", headers=headers)
        assert del_resp.status_code in (400, 403)


# ════════════════════════════════════════════════════════════════════
# PART 14: Permission Inheritance (Parent Collection)
# ════════════════════════════════════════════════════════════════════


class TestPermissionInheritance:

    def test_child_collection_inherits_parent_membership(self):
        """Members of a parent collection have access to child collections."""
        # Create parent
        parent_resp = api_post("/api/collections", {"name": f"InheritParent-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        # Create child
        child_resp = api_post("/api/collections", {"name": f"InheritChild-{UNIQUE}", "parentId": parent_id})
        child_id = child_resp.json()["id"]
        # Add user2 as viewer of parent
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{parent_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 should be able to access child collection
        resp = api_get(f"/api/collections/{child_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_child_collection_links_visible_to_parent_member(self):
        """Links in a child collection are visible to parent collection members."""
        parent_resp = api_post("/api/collections", {"name": f"InheritLinks-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/collections", {"name": f"InheritChildLinks-{UNIQUE}", "parentId": parent_id})
        child_id = child_resp.json()["id"]
        # Create a link in child
        link_resp = api_post("/api/links", {"url": f"https://inherit-link-{UNIQUE}.com", "collectionId": child_id})
        link_id = link_resp.json()["id"]
        # Add user2 as viewer of parent
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{parent_id}/members", {"userId": USER2_ID, "role": "viewer"})
        # User2 can read the link
        resp = api_get(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 15: Edge Cases and Validation
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_create_link_in_nonexistent_collection(self):
        """Creating a link with a non-existent collectionId."""
        resp = api_post("/api/links", {"url": f"https://nocol-{UNIQUE}.com", "collectionId": 999999})
        # Should fail with 404 or 400
        assert resp.status_code in (400, 404)

    def test_create_collection_with_invalid_parent(self):
        """Creating a collection with non-existent parentId."""
        resp = api_post("/api/collections", {"name": f"BadParent-{UNIQUE}", "parentId": 999999})
        assert resp.status_code in (400, 404)

    def test_contributor_cannot_delete_others_links(self):
        """A contributor can only delete their own links."""
        col_resp = api_post("/api/collections", {"name": f"ContribDel-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        # Owner creates a link
        link_resp = api_post("/api/links", {"url": f"https://owner-link-{UNIQUE}.com", "collectionId": col_id})
        link_id = link_resp.json()["id"]
        # Add user2 as contributor
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "contributor"})
        # User2 tries to delete owner's link
        resp = api_delete(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_contributor_can_delete_own_links(self):
        """A contributor can delete their own links in a shared collection."""
        col_resp = api_post("/api/collections", {"name": f"ContribOwnDel-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "contributor"})
        # User2 creates a link
        link_resp = api_post("/api/links", {"url": f"https://contrib-own-{UNIQUE}.com", "collectionId": col_id}, headers=USER2_HEADERS)
        link_id = link_resp.json()["id"]
        # User2 deletes their own link
        resp = api_delete(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_admin_can_delete_any_link_in_collection(self):
        """An admin can delete any link in the collection."""
        col_resp = api_post("/api/collections", {"name": f"AdminDel-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        # Owner creates a link
        link_resp = api_post("/api/links", {"url": f"https://admin-del-{UNIQUE}.com", "collectionId": col_id})
        link_id = link_resp.json()["id"]
        # Add user2 as admin
        api_get("/api/collections", headers=USER2_HEADERS)
        api_post(f"/api/collections/{col_id}/members", {"userId": USER2_ID, "role": "admin"})
        # User2 (admin) deletes owner's link
        resp = api_delete(f"/api/links/{link_id}", headers=USER2_HEADERS)
        assert resp.status_code == 200

    def test_search_filter_by_collection(self):
        """Search can be filtered by collectionId."""
        col_resp = api_post("/api/collections", {"name": f"SearchFilter-{UNIQUE}"})
        col_id = col_resp.json()["id"]
        api_post("/api/links", {"url": f"https://sf1-{UNIQUE}.com", "name": f"searchfilter-{UNIQUE}", "collectionId": col_id})
        api_post("/api/links", {"url": f"https://sf2-{UNIQUE}.com", "name": f"searchfilter-{UNIQUE}"})
        resp = api_get("/api/search", params={"q": f"searchfilter-{UNIQUE}", "collectionId": col_id})
        data = resp.json()
        for link in data["links"]:
            assert link["collectionId"] == col_id

    def test_list_links_filter_by_tag(self):
        """List links can filter by tagId."""
        tag_name = f"filtertag-{UNIQUE}"
        api_post("/api/links", {"url": f"https://tagfilter-{UNIQUE}.com", "tags": [{"name": tag_name}]})
        # Get tag id
        tags_resp = api_get("/api/tags")
        tag_id = None
        for t in tags_resp.json()["tags"]:
            if t["name"] == tag_name:
                tag_id = t["id"]
                break
        assert tag_id is not None
        resp = api_get("/api/links", params={"tagId": tag_id})
        assert resp.status_code == 200
        data = resp.json()
        for link in data["links"]:
            link_tag_names = [t["name"] for t in link["tags"]]
            assert tag_name in link_tag_names
