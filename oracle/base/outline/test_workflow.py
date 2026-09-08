"""
BackendForge — L3 Workflow Tests for Outline
Multi-step, multi-entity adversarial tests.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_KEY = "admin-user-key"  # Must be the first request to become admin
MEMBER_KEY = f"member-wf-{uuid.uuid4().hex[:8]}"
VIEWER_KEY = f"viewer-wf-{uuid.uuid4().hex[:8]}"
MEMBER2_KEY = f"member2-wf-{uuid.uuid4().hex[:8]}"

ADMIN_H = {"X-Api-Key": ADMIN_KEY, "Content-Type": "application/json"}
MEMBER_H = {"X-Api-Key": MEMBER_KEY, "Content-Type": "application/json"}
VIEWER_H = {"X-Api-Key": VIEWER_KEY, "Content-Type": "application/json"}
MEMBER2_H = {"X-Api-Key": MEMBER2_KEY, "Content-Type": "application/json"}


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def api(path, json=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json is None else json,
        headers=ADMIN_H if headers is None else headers,
        timeout=30,
    )


def api_no_auth(path, json=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if json is None else json,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


def setup_module(module):
    """Ensure admin first, then other users. Set viewer role."""
    admin = api("/teams.info")
    assert admin.status_code == 200, admin.text
    member = api("/teams.info", headers=MEMBER_H)
    assert member.status_code == 200, member.text
    viewer_response = api("/teams.info", headers=VIEWER_H)
    assert viewer_response.status_code == 200, viewer_response.text
    member2 = api("/teams.info", headers=MEMBER2_H)
    assert member2.status_code == 200, member2.text
    # Set viewer role
    resp = api("/users.list", {"limit": 100})
    assert resp.status_code == 200, resp.text
    viewer = next((u for u in resp.json()["data"] if u["name"] == VIEWER_KEY), None)
    assert viewer is not None, f"Viewer user {VIEWER_KEY!r} was not returned by users.list"
    if viewer["role"] != "viewer":
        updated = api("/users.update", {"id": viewer["id"], "role": "viewer"})
        assert updated.status_code == 200, updated.text


# ═══════════════════════════════════════════════════════════
# L3 Tests — Workflows (10-15 tests)
# ═══════════════════════════════════════════════════════════


class TestDocumentLifecycleWorkflow:
    """Full document lifecycle: create → update → revisions → share → archive → delete."""

    def test_document_full_lifecycle(self):
        """Pattern 2+5+7: Document lifecycle with revisions and shares."""
        # 1. Create collection
        r = api("/collections.create", {"name": _u("lifecycle-col-"), "permission": "read_write"})
        assert r.status_code == 200
        col_id = r.json()["data"]["id"]

        # 2. Create draft document
        r = api("/documents.create", {
            "title": "Draft Title",
            "text": "Draft content v1",
            "collectionId": col_id,
            "publish": False,
        })
        assert r.status_code == 200
        doc = r.json()["data"]
        doc_id = doc["id"]
        assert doc["publishedAt"] is None
        assert doc["collectionId"] == col_id

        # 3. Doc in drafts, not in list
        r = api("/documents.drafts")
        assert doc_id in [d["id"] for d in r.json()["data"]]
        r = api("/documents.list", {"collectionId": col_id})
        assert doc_id not in [d["id"] for d in r.json()["data"]]

        # 4. Update and publish
        r = api("/documents.update", {"id": doc_id, "title": "Published Title", "text": "Content v2", "publish": True})
        assert r.status_code == 200
        assert r.json()["data"]["publishedAt"] is not None
        assert r.json()["data"]["title"] == "Published Title"

        # 5. Now in list, not in drafts
        r = api("/documents.list", {"collectionId": col_id})
        assert doc_id in [d["id"] for d in r.json()["data"]]
        r = api("/documents.drafts")
        assert doc_id not in [d["id"] for d in r.json()["data"]]

        # 6. Update again → creates revisions
        api("/documents.update", {"id": doc_id, "title": "Final Title", "text": "Content v3"})

        # 7. Check revisions
        r = api("/revisions.list", {"documentId": doc_id})
        revs = r.json()["data"]
        assert len(revs) >= 2
        # Latest revision stores previous content
        assert revs[0]["title"] == "Published Title"
        assert revs[0]["text"] == "Content v2"

        # 8. Create share link
        r = api("/shares.create", {"documentId": doc_id})
        assert r.status_code == 200
        share = r.json()["data"]
        url_id = share["urlId"]

        # 9. Public access works
        r = api_no_auth("/shares.info", {"urlId": url_id})
        assert r.status_code == 200
        assert r.json()["data"]["document"]["title"] == "Final Title"

        # 10. Archive document
        r = api("/documents.archive", {"id": doc_id})
        assert r.status_code == 200
        assert r.json()["data"]["archivedAt"] is not None

        # 11. Archived doc not in list
        r = api("/documents.list", {"collectionId": col_id})
        assert doc_id not in [d["id"] for d in r.json()["data"]]

        # 12. Still accessible via info
        r = api("/documents.info", {"id": doc_id})
        assert r.status_code == 200


class TestDocumentHierarchyWorkflow:
    """Document parent-child hierarchy and move operations."""

    def test_hierarchy_and_move(self):
        """Pattern 2+7: Create hierarchy → move → verify children follow."""
        # 1. Create two collections
        r = api("/collections.create", {"name": _u("col-a-")})
        col_a = r.json()["data"]["id"]
        r = api("/collections.create", {"name": _u("col-b-")})
        col_b = r.json()["data"]["id"]

        # 2. Create parent doc in col A
        r = api("/documents.create", {"title": "Parent", "text": "parent text", "collectionId": col_a, "publish": True})
        parent = r.json()["data"]
        parent_id = parent["id"]

        # 3. Create child doc
        r = api("/documents.create", {
            "title": "Child",
            "text": "child text",
            "collectionId": col_a,
            "parentDocumentId": parent_id,
            "publish": True,
        })
        child = r.json()["data"]
        child_id = child["id"]
        assert child["parentDocumentId"] == parent_id
        assert child["collectionId"] == col_a

        # 4. Create grandchild
        r = api("/documents.create", {
            "title": "Grandchild",
            "text": "gc text",
            "collectionId": col_a,
            "parentDocumentId": child_id,
            "publish": True,
        })
        gc_id = r.json()["data"]["id"]

        # 5. Move parent to col B
        r = api("/documents.move", {"id": parent_id, "collectionId": col_b})
        assert r.status_code == 200
        assert r.json()["data"]["collectionId"] == col_b

        # 6. Child should also move to col B
        r = api("/documents.info", {"id": child_id})
        assert r.json()["data"]["collectionId"] == col_b

        # 7. Grandchild also moved
        r = api("/documents.info", {"id": gc_id})
        assert r.json()["data"]["collectionId"] == col_b

        # 8. Col A should have no docs
        r = api("/documents.list", {"collectionId": col_a})
        assert len(r.json()["data"]) == 0

        # 9. Col B should have all 3
        r = api("/documents.list", {"collectionId": col_b})
        ids = [d["id"] for d in r.json()["data"]]
        assert parent_id in ids
        assert child_id in ids
        assert gc_id in ids


class TestArchiveCascadeWorkflow:
    """Archiving cascades to children."""

    def test_archive_cascades_to_children(self):
        """Pattern 7: Archiving parent also archives children."""
        r = api("/collections.create", {"name": _u("arch-col-")})
        col_id = r.json()["data"]["id"]

        # Create parent and children
        r = api("/documents.create", {"title": "ArchParent", "collectionId": col_id, "publish": True})
        parent_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "ArchChild1", "collectionId": col_id, "parentDocumentId": parent_id, "publish": True})
        child1_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "ArchChild2", "collectionId": col_id, "parentDocumentId": parent_id, "publish": True})
        child2_id = r.json()["data"]["id"]

        # Archive parent
        r = api("/documents.archive", {"id": parent_id})
        assert r.status_code == 200

        # Children also archived
        r = api("/documents.info", {"id": child1_id})
        assert r.json()["data"]["archivedAt"] is not None

        r = api("/documents.info", {"id": child2_id})
        assert r.json()["data"]["archivedAt"] is not None

        # None appear in list
        r = api("/documents.list", {"collectionId": col_id})
        ids = [d["id"] for d in r.json()["data"]]
        assert parent_id not in ids
        assert child1_id not in ids
        assert child2_id not in ids


class TestSoftDeleteCascadeWorkflow:
    """Soft delete cascades to children."""

    def test_delete_cascades_to_children(self):
        """Pattern 7: Deleting parent also soft-deletes children."""
        r = api("/collections.create", {"name": _u("del-col-")})
        col_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "DelParent", "collectionId": col_id, "publish": True})
        parent_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "DelChild", "collectionId": col_id, "parentDocumentId": parent_id, "publish": True})
        child_id = r.json()["data"]["id"]

        # Delete parent
        r = api("/documents.delete", {"id": parent_id})
        assert r.status_code == 200
        assert r.json()["success"] is True

        # Both disappear from list
        r = api("/documents.list", {"collectionId": col_id})
        ids = [d["id"] for d in r.json()["data"]]
        assert parent_id not in ids
        assert child_id not in ids


class TestCollectionDeleteCascade:
    """Deleting collection removes all its documents."""

    def test_collection_delete_removes_documents(self):
        """Pattern 7: Deleting collection cascades to all documents."""
        r = api("/collections.create", {"name": _u("cascade-col-")})
        col_id = r.json()["data"]["id"]

        # Create several docs
        doc1 = api("/documents.create", {"title": "D1", "collectionId": col_id, "publish": True}).json()["data"]
        doc2 = api("/documents.create", {"title": "D2", "collectionId": col_id, "publish": True}).json()["data"]

        # Delete collection
        r = api("/collections.delete", {"id": col_id})
        assert r.status_code == 200
        assert r.json()["success"] is True

        # Collection gone
        r = api("/collections.info", {"id": col_id})
        assert r.status_code == 404

        # Documents gone
        r = api("/documents.info", {"id": doc1["id"]})
        assert r.status_code == 404
        r = api("/documents.info", {"id": doc2["id"]})
        assert r.status_code == 404


class TestShareWithChildDocuments:
    """Share with includeChildDocuments."""

    def test_share_includes_children(self):
        """Pattern 2+5: Share with children returns parent + child docs."""
        r = api("/collections.create", {"name": _u("share-col-")})
        col_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "ShareParent", "text": "parent text", "collectionId": col_id, "publish": True})
        parent_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "ShareChild", "text": "child text", "collectionId": col_id, "parentDocumentId": parent_id, "publish": True})
        child_id = r.json()["data"]["id"]

        # Create share with includeChildDocuments
        r = api("/shares.create", {"documentId": parent_id, "includeChildDocuments": True})
        assert r.status_code == 200
        url_id = r.json()["data"]["urlId"]

        # Access shared content
        r = api_no_auth("/shares.info", {"urlId": url_id})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["document"]["id"] == parent_id
        assert data["childDocuments"] is not None
        child_ids = [c["id"] for c in data["childDocuments"]]
        assert child_id in child_ids


class TestRoleBasedAccessWorkflow:
    """Multi-user role workflow."""

    def test_viewer_cannot_create_or_edit(self):
        """Pattern 6: Viewer can read but not write."""
        # Create collection as admin
        r = api("/collections.create", {"name": _u("viewer-col-")})
        col_id = r.json()["data"]["id"]

        # Create a doc as admin
        r = api("/documents.create", {"title": "AdminDoc", "collectionId": col_id, "publish": True})
        doc_id = r.json()["data"]["id"]

        # Viewer can read
        r = api("/documents.info", {"id": doc_id}, headers=VIEWER_H)
        assert r.status_code == 200

        # Viewer cannot create
        r = api("/documents.create", {"title": "ViewerDoc", "collectionId": col_id}, headers=VIEWER_H)
        assert r.status_code == 403

        # Viewer cannot update
        r = api("/documents.update", {"id": doc_id, "title": "Changed"}, headers=VIEWER_H)
        assert r.status_code == 403

    def test_member_in_read_write_collection(self):
        """Pattern 6: Member can create/edit in read_write collections."""
        r = api("/collections.create", {"name": _u("rw-col-"), "permission": "read_write"})
        col_id = r.json()["data"]["id"]

        # Member creates doc
        r = api("/documents.create", {"title": _u("mem-doc-"), "collectionId": col_id, "publish": True}, headers=MEMBER_H)
        assert r.status_code == 200
        doc_id = r.json()["data"]["id"]

        # Member updates doc
        r = api("/documents.update", {"id": doc_id, "text": "updated"}, headers=MEMBER_H)
        assert r.status_code == 200


class TestCommentsWorkflow:
    """Comments lifecycle with multiple users."""

    def test_comments_multi_user_workflow(self):
        """Pattern 6+5: Multiple users comment, resolve, ownership check."""
        r = api("/collections.create", {"name": _u("cmt-col-")})
        col_id = r.json()["data"]["id"]
        r = api("/documents.create", {"title": "CommentDoc", "collectionId": col_id, "publish": True})
        doc_id = r.json()["data"]["id"]

        # Admin creates comment
        r = api("/comments.create", {"documentId": doc_id, "text": "Admin says hello"})
        assert r.status_code == 200
        admin_cmt = r.json()["data"]
        assert admin_cmt["resolved"] is False

        # Member creates comment
        r = api("/comments.create", {"documentId": doc_id, "text": "Member question"}, headers=MEMBER_H)
        assert r.status_code == 200
        member_cmt = r.json()["data"]

        # List comments
        r = api("/comments.list", {"documentId": doc_id})
        assert len(r.json()["data"]) >= 2

        # Member cannot update admin's comment
        r = api("/comments.update", {"id": admin_cmt["id"], "resolved": True}, headers=MEMBER_H)
        assert r.status_code == 403

        # Member can update own comment
        r = api("/comments.update", {"id": member_cmt["id"], "text": "Updated question", "resolved": True}, headers=MEMBER_H)
        assert r.status_code == 200
        assert r.json()["data"]["resolved"] is True
        assert r.json()["data"]["text"] == "Updated question"

        # Admin can update anyone's
        r = api("/comments.update", {"id": member_cmt["id"], "resolved": False})
        assert r.status_code == 200

        # Member cannot delete admin's comment
        r = api("/comments.delete", {"id": admin_cmt["id"]}, headers=MEMBER_H)
        assert r.status_code == 403

        # Admin can delete member's comment
        r = api("/comments.delete", {"id": member_cmt["id"]})
        assert r.status_code == 200


class TestStarsAndPinsWorkflow:
    """Stars and pins lifecycle."""

    def test_stars_pins_full_workflow(self):
        """Pattern 5+8: Stars and pins CRUD with duplicate prevention."""
        r = api("/collections.create", {"name": _u("sp-col-")})
        col_id = r.json()["data"]["id"]

        r = api("/documents.create", {"title": "StarDoc", "collectionId": col_id, "publish": True})
        doc_id = r.json()["data"]["id"]

        # Star the doc
        r = api("/stars.create", {"documentId": doc_id})
        assert r.status_code == 200
        star_id = r.json()["data"]["id"]

        # Star appears in list
        r = api("/stars.list")
        star_ids = [s["id"] for s in r.json()["data"]]
        assert star_id in star_ids

        # Duplicate star fails
        r = api("/stars.create", {"documentId": doc_id})
        assert r.status_code == 400

        # Pin the doc
        r = api("/pins.create", {"documentId": doc_id, "collectionId": col_id, "index": 1})
        assert r.status_code == 200
        pin_id = r.json()["data"]["id"]
        assert r.json()["data"]["index"] == 1

        # Pin appears in list
        r = api("/pins.list", {"collectionId": col_id})
        pin_ids = [p["id"] for p in r.json()["data"]]
        assert pin_id in pin_ids

        # Duplicate pin fails
        r = api("/pins.create", {"documentId": doc_id, "collectionId": col_id})
        assert r.status_code == 400

        # Delete star
        r = api("/stars.delete", {"id": star_id})
        assert r.status_code == 200

        # Star gone from list
        r = api("/stars.list")
        assert star_id not in [s["id"] for s in r.json()["data"]]

        # Delete pin
        r = api("/pins.delete", {"id": pin_id})
        assert r.status_code == 200


class TestGroupsWorkflow:
    """Groups and memberships workflow."""

    def test_groups_and_memberships(self):
        """Pattern 5+8: Group CRUD with membership management."""
        # Create group
        grp_name = _u("team-")
        r = api("/groups.create", {"name": grp_name})
        assert r.status_code == 200
        grp = r.json()["data"]
        grp_id = grp["id"]
        assert grp["name"] == grp_name
        assert grp["memberCount"] == 0

        # Duplicate name
        r = api("/groups.create", {"name": grp_name})
        assert r.status_code == 400

        # Get users
        r = api("/users.list")
        users = r.json()["data"]
        u1_id = users[0]["id"]
        u2_id = users[1]["id"] if len(users) > 1 else None

        # Add member
        r = api("/group_memberships.create", {"groupId": grp_id, "userId": u1_id})
        assert r.status_code == 200
        assert r.json()["data"]["groupId"] == grp_id
        assert r.json()["data"]["userId"] == u1_id

        # Duplicate membership
        r = api("/group_memberships.create", {"groupId": grp_id, "userId": u1_id})
        assert r.status_code == 400

        # Add second member
        if u2_id:
            r = api("/group_memberships.create", {"groupId": grp_id, "userId": u2_id})
            assert r.status_code == 200

        # List memberships
        r = api("/group_memberships.list", {"groupId": grp_id})
        assert r.status_code == 200
        members = r.json()["data"]
        assert len(members) >= 1

        # Remove member
        r = api("/group_memberships.delete", {"groupId": grp_id, "userId": u1_id})
        assert r.status_code == 200

        # Verify removed
        r = api("/group_memberships.list", {"groupId": grp_id})
        user_ids = [m["userId"] for m in r.json()["data"]]
        assert u1_id not in user_ids

        # Delete group
        r = api("/groups.delete", {"id": grp_id})
        assert r.status_code == 200

        # Group gone
        r = api("/groups.list")
        grp_ids = [g["id"] for g in r.json()["data"]]
        assert grp_id not in grp_ids


class TestTeamAndUsersWorkflow:
    """Team info and user management."""

    def test_team_info_and_member_count(self):
        """Pattern 1+5: Team memberCount is computed, not static."""
        r = api("/teams.info")
        assert r.status_code == 200
        team = r.json()["data"]
        assert "id" in team
        assert "name" in team
        assert "memberCount" in team
        assert team["memberCount"] >= 3  # admin + member + viewer at least
        assert "createdAt" in team
        assert "updatedAt" in team

    def test_admin_can_manage_users(self):
        """Pattern 6: Admin can list and update user roles."""
        r = api("/users.list")
        assert r.status_code == 200
        users = r.json()["data"]
        assert len(users) >= 1

        # Member cannot list users
        r = api("/users.list", headers=MEMBER_H)
        assert r.status_code == 403

        original_name = api("/teams.info").json()["data"]["name"]
        try:
            # Admin updates team
            new_name = _u("team-")
            r = api("/teams.update", {"name": new_name})
            assert r.status_code == 200
            assert r.json()["data"]["name"] == new_name

            # Member cannot update team
            r = api("/teams.update", {"name": "hacked"}, headers=MEMBER_H)
            assert r.status_code == 403
        finally:
            api("/teams.update", {"name": original_name})
