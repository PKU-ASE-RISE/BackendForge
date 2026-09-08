"""
BackendForge — L3 Workflow Tests for Linkwarden
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-a"))
USER_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-b"))
USER_C = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-c"))
HA = {"X-User-Id": USER_A, "Content-Type": "application/json"}
HB = {"X-User-Id": USER_B, "Content-Type": "application/json"}
HC = {"X-User-Id": USER_C, "Content-Type": "application/json"}
U = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent user namespaces."""
    global USER_A, USER_B, USER_C, HA, HB, HC, U

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-a"))
    USER_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-b"))
    USER_C = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-c"))
    HA = {"X-User-Id": USER_A, "Content-Type": "application/json"}
    HB = {"X-User-Id": USER_B, "Content-Type": "application/json"}
    HC = {"X-User-Id": USER_C, "Content-Type": "application/json"}
    U = item_id[:8]


def get(p, params=None, h=None):
    return requests.get(f"{BASE_URL}{p}", params=params, headers=HA if h is None else h, timeout=30)


def post(p, json=None, h=None):
    return requests.post(f"{BASE_URL}{p}", json=json, headers=HA if h is None else h, timeout=30)


def put(p, json=None, h=None):
    return requests.put(f"{BASE_URL}{p}", json=json, headers=HA if h is None else h, timeout=30)


def delete(p, params=None, h=None):
    return requests.delete(f"{BASE_URL}{p}", params=params, headers=HA if h is None else h, timeout=30)


class TestCollectionSharingWorkflow:
    """Pattern 5+6: Collection sharing with role-based access."""

    def test_share_collection_and_member_access(self):
        """Owner shares collection, member can view links but not delete collection."""
        # 1. User A creates collection and link
        coll = post("/api/collections", {"name": f"Shared-{U}"}).json()
        link = post("/api/links", {"url": "https://shared-link.com", "collectionId": coll["id"]}).json()

        # 2. Ensure User B exists
        get("/api/links", h=HB)

        # 3. Add User B as viewer
        r = post(f"/api/collections/{coll['id']}/members", {"userId": USER_B, "role": "viewer"})
        assert r.status_code == 201
        assert r.json()["role"] == "viewer"

        # 4. User B can see the collection
        r = get(f"/api/collections/{coll['id']}", h=HB)
        assert r.status_code == 200

        # 5. User B can see the link
        r = get(f"/api/links/{link['id']}", h=HB)
        assert r.status_code == 200

        # 6. User B cannot delete the link (viewer)
        r = delete(f"/api/links/{link['id']}", h=HB)
        assert r.status_code == 403

        # 7. User B cannot delete the collection
        r = delete(f"/api/collections/{coll['id']}", h=HB)
        assert r.status_code == 403

    def test_contributor_can_add_but_only_delete_own_links(self):
        """Contributor can add links but only delete their own."""
        coll = post("/api/collections", {"name": f"Contrib-{U}"}).json()
        get("/api/links", h=HB)  # ensure B exists
        post(f"/api/collections/{coll['id']}/members", {"userId": USER_B, "role": "contributor"})

        # Owner creates a link
        owner_link = post("/api/links", {"url": "https://owner-link.com", "collectionId": coll["id"]}).json()

        # Contributor creates a link
        contrib_link = post("/api/links", {"url": "https://contrib-link.com", "collectionId": coll["id"]}, h=HB).json()
        assert contrib_link["createdBy"] == USER_B

        # Contributor can delete own link
        r = delete(f"/api/links/{contrib_link['id']}", h=HB)
        assert r.status_code == 200

        # Contributor cannot delete owner's link
        r = delete(f"/api/links/{owner_link['id']}", h=HB)
        assert r.status_code == 403


class TestCollectionDeletionCascade:
    """Pattern 7: Collection deletion with and without deleteChildren."""

    def test_delete_with_children_cascades(self):
        """deleteChildren=true removes child collections recursively."""
        parent = post("/api/collections", {"name": f"Parent-{U}"}).json()
        child = post("/api/collections", {"name": f"Child-{U}", "parentId": parent["id"]}).json()
        grandchild = post("/api/collections", {"name": f"GChild-{U}", "parentId": child["id"]}).json()

        # Delete parent with cascade
        r = delete(f"/api/collections/{parent['id']}", params={"deleteChildren": "true"})
        assert r.status_code == 200

        # Child and grandchild collections gone
        assert get(f"/api/collections/{child['id']}").status_code == 404
        assert get(f"/api/collections/{grandchild['id']}").status_code == 404

    def test_delete_without_children_moves_to_root(self):
        """Without deleteChildren, children get parentId=null."""
        parent = post("/api/collections", {"name": f"Par2-{U}"}).json()
        child = post("/api/collections", {"name": f"Ch2-{U}", "parentId": parent["id"]}).json()

        # Delete parent without cascade
        r = delete(f"/api/collections/{parent['id']}", params={"deleteChildren": "false"})
        assert r.status_code == 200

        # Child still exists with parentId = null
        child_resp = get(f"/api/collections/{child['id']}").json()
        assert child_resp["parentId"] is None


class TestTagLifecycleWorkflow:
    """Pattern 5+7: Tag dedup on link creation and cleanup on tag deletion."""

    def test_link_with_tags_creates_and_reuses_tags(self):
        """Creating links with same tag name reuses existing tag."""
        tag_name = f"reuse-{uuid.uuid4().hex[:6]}"
        l1 = post("/api/links", {"url": "https://t1.com", "tags": [{"name": tag_name}]}).json()
        l2 = post("/api/links", {"url": "https://t2.com", "tags": [{"name": tag_name}]}).json()

        # Both links should have the same tag id
        assert l1["tags"][0]["id"] == l2["tags"][0]["id"]

    def test_delete_tag_removes_from_links(self):
        """Deleting a tag removes it from all associated links."""
        tag_name = f"deltag-{uuid.uuid4().hex[:6]}"
        link = post("/api/links", {"url": "https://dt.com", "tags": [{"name": tag_name}]}).json()
        tag_id = link["tags"][0]["id"]

        # Delete the tag
        r = delete(f"/api/tags/{tag_id}")
        assert r.status_code == 200

        # Link should no longer have the tag
        link_resp = get(f"/api/links/{link['id']}").json()
        tag_ids = [t["id"] for t in link_resp["tags"]]
        assert tag_id not in tag_ids


class TestHighlightWorkflow:
    """Pattern 2+7: Highlight CRUD on links."""

    def test_highlight_full_lifecycle(self):
        """Create, list, update, delete highlight."""
        link = post("/api/links", {"url": "https://hl-wf.com"}).json()

        # Create
        hl = post(f"/api/links/{link['id']}/highlights", {"text": "original", "color": "#ff0000"}).json()
        assert hl["text"] == "original"

        # Update
        r = put(f"/api/highlights/{hl['id']}", {"text": "updated", "note": "added note"})
        assert r.status_code == 200
        assert r.json()["text"] == "updated"
        assert r.json()["note"] == "added note"

        # List
        r = get(f"/api/links/{link['id']}/highlights")
        assert len(r.json()["highlights"]) == 1

        # Delete
        r = delete(f"/api/highlights/{hl['id']}")
        assert r.status_code == 200

        # Gone
        r = get(f"/api/links/{link['id']}/highlights")
        assert len(r.json()["highlights"]) == 0


class TestPublicCollectionWorkflow:
    """Pattern 6: Public vs private collection access."""

    def test_toggle_public_affects_access(self):
        """Making a collection public exposes it; making private hides it."""
        coll = post("/api/collections", {"name": f"Toggle-{U}", "isPublic": True}).json()
        post("/api/links", {"url": "https://toggle.com", "collectionId": coll["id"]})

        # Public accessible
        r = requests.get(f"{BASE_URL}/api/public/collections/{coll['id']}", timeout=30)
        assert r.status_code == 200

        # Make private
        put(f"/api/collections/{coll['id']}", {"name": f"Toggle-{U}", "isPublic": False})

        # Now 404
        r = requests.get(f"{BASE_URL}/api/public/collections/{coll['id']}", timeout=30)
        assert r.status_code == 404


class TestDashboardAccuracy:
    """Pattern 5: Dashboard stats reflect actual data."""

    def test_dashboard_counts_match_reality(self):
        """Dashboard totalLinks matches actual link count."""
        # Get baseline
        base = get("/api/dashboard").json()

        # Create entities
        post("/api/links", {"url": f"https://dash-{uuid.uuid4().hex[:6]}.com"})
        post("/api/collections", {"name": f"DashColl-{uuid.uuid4().hex[:6]}"})
        post("/api/tags", {"name": f"DashTag-{uuid.uuid4().hex[:6]}"})

        # Verify counts increased
        after = get("/api/dashboard").json()
        assert after["totalLinks"] == base["totalLinks"] + 1
        assert after["totalCollections"] == base["totalCollections"] + 1
        assert after["totalTags"] == base["totalTags"] + 1


class TestSearchIsolation:
    """Pattern 3+6: Search only returns accessible links."""

    def test_search_excludes_other_users_links(self):
        """User B's links not in User A's search results."""
        unique = f"isolsrch{uuid.uuid4().hex[:6]}"
        post("/api/links", {"url": f"https://{unique}.com", "name": unique}, h=HB)

        r = get("/api/search", params={"q": unique})
        assert r.json()["total"] == 0


class TestMemberRoleManagement:
    """Pattern 5+8: Role updates and removals."""

    def test_owner_can_change_member_role(self):
        """Owner can promote/demote members."""
        coll = post("/api/collections", {"name": f"Role-{U}"}).json()
        get("/api/links", h=HB)  # ensure B exists
        member = post(f"/api/collections/{coll['id']}/members", {"userId": USER_B, "role": "viewer"}).json()

        # Promote to contributor
        r = put(f"/api/collections/{coll['id']}/members/{member['id']}", {"role": "contributor"})
        assert r.status_code == 200
        assert r.json()["role"] == "contributor"

        # Demote to viewer
        r = put(f"/api/collections/{coll['id']}/members/{member['id']}", {"role": "viewer"})
        assert r.status_code == 200
        assert r.json()["role"] == "viewer"


class TestUnorganizedCollectionProtection:
    """Pattern 8: Unorganized collection cannot be deleted."""

    def test_cannot_delete_unorganized_collection(self):
        """The default Unorganized collection cannot be deleted."""
        # Trigger creation of Unorganized collection
        link = post("/api/links", {"url": "https://unorg-test.com"}).json()
        unorg_id = link["collectionId"]

        # Try to delete → should fail
        r = delete(f"/api/collections/{unorg_id}")
        assert r.status_code in (400, 403)

        # Still exists
        assert get(f"/api/collections/{unorg_id}").status_code == 200
