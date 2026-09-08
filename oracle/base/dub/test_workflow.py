"""
L3 Workflow Tests for Dub — Link Management Platform.
Multi-step adversarial tests targeting complex interactions:
- Link lifecycle with tags, folders, analytics
- Bulk operations atomicity
- Click tracking with analytics aggregation
- Role-based access across operations
- Workspace isolation end-to-end
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30

OWNER_KEY = "owner_ws1_user1"
ADMIN_KEY = "admin_ws1_user2"
MEMBER_KEY = "member_ws1_user3"
MEMBER2_KEY = "member_ws1_user4"
OTHER_WS_KEY = "admin_ws2_user5"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    if key:
        headers["X-API-Key"] = key
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def unique_slug():
    return f"s{uuid.uuid4().hex[:8]}"


# =============================================================================
# L3 TESTS — Workflow (10-15 tests)
# =============================================================================


class TestLinkLifecycleWorkflow:
    """Full lifecycle with tags, folders, click tracking."""

    def test_create_organize_click_archive_delete(self):
        """
        Pattern 2+5+7: Create link with tag+folder -> click -> verify analytics ->
        archive -> verify filtered out -> delete -> verify cascade.
        """
        # 1. Create tag and folder
        tag_name = unique_slug()
        tag = api("post", "/tags", json={"name": tag_name, "color": "#FF0000"}).json()
        folder_name = unique_slug()
        folder = api("post", "/folders", json={"name": folder_name}).json()

        # 2. Create link in folder with tag
        slug = unique_slug()
        resp = api("post", "/links", json={
            "url": "https://lifecycle.com",
            "slug": slug,
            "title": "Lifecycle Test",
            "tags": [tag["id"]],
            "folderId": folder["id"]
        })
        assert resp.status_code == 201
        link = resp.json()
        assert link["folderId"] == folder["id"]
        assert tag["id"] in link["tags"]

        # 3. Click the link
        for _ in range(3):
            api("get", f"/r/{slug}", key=None, allow_redirects=False)

        # 4. Verify click count
        resp = api("get", f"/links/{link['id']}")
        assert resp.json()["clicks"] == 3

        # 5. Archive the link
        resp = api("put", f"/links/{link['id']}", json={"archived": True})
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

        # 6. Verify archived filter excludes it from normal list
        resp = api("get", "/links", params={"archived": "false"})
        link_ids = [l["id"] for l in resp.json()]
        assert link["id"] not in link_ids

        # 7. Verify still appears in archived list
        resp = api("get", "/links", params={"archived": "true"})
        link_ids = [l["id"] for l in resp.json()]
        assert link["id"] in link_ids

        # 8. Delete the link
        resp = api("delete", f"/links/{link['id']}")
        assert resp.status_code == 204

        # 9. Verify gone
        resp = api("get", f"/links/{link['id']}")
        assert resp.status_code == 404


class TestAnalyticsWorkflow:
    """Click events produce correct analytics aggregation."""

    def test_clicks_reflected_in_analytics(self):
        """
        Pattern 5: Generate clicks with specific metadata,
        verify analytics endpoints aggregate correctly.
        """
        # 1. Create link
        slug = unique_slug()
        resp = api("post", "/links", json={"url": "https://analytics.com", "slug": slug})
        assert resp.status_code == 201
        link_id = resp.json()["id"]

        # 2. Click with different user agents and countries
        # Desktop Chrome from US
        api("get", f"/r/{slug}", key=None, allow_redirects=False, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
            "X-Forwarded-Country": "US",
            "Referer": "https://google.com"
        })
        # Mobile Safari from UK
        api("get", f"/r/{slug}", key=None, allow_redirects=False, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1",
            "X-Forwarded-Country": "UK",
            "Referer": "https://twitter.com"
        })
        # Android from DE
        api("get", f"/r/{slug}", key=None, allow_redirects=False, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120",
            "X-Forwarded-Country": "DE"
        })

        # 3. Verify click count
        resp = api("get", f"/links/{link_id}")
        assert resp.json()["clicks"] == 3

        # 4. Verify country analytics
        resp = api("get", "/analytics/countries", params={"linkId": link_id})
        assert resp.status_code == 200
        countries = resp.json()
        assert len(countries) >= 2
        country_map = {c["country"]: c["clicks"] for c in countries}
        assert "US" in country_map
        assert "UK" in country_map

        # 5. Verify device analytics
        resp = api("get", "/analytics/devices", params={"linkId": link_id})
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) >= 2
        device_names = [d["device"] for d in devices]
        assert "Desktop" in device_names or "Mobile" in device_names

        # 6. Verify events log
        resp = api("get", "/events", params={"linkId": link_id})
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 3
        for e in events:
            assert "id" in e
            assert "linkId" in e
            assert "timestamp" in e
            assert "country" in e
            assert "device" in e
            assert "browser" in e
            assert e["linkId"] == link_id


class TestBulkOperationsWorkflow:
    """Bulk CRUD with validation and atomicity."""

    def test_bulk_create_and_delete(self):
        """
        Pattern 5+7: Bulk create links, verify all created,
        bulk delete, verify all gone.
        """
        # 1. Bulk create 3 links
        slugs = [unique_slug() for _ in range(3)]
        links_data = [
            {"url": f"https://bulk{i}.com", "slug": slugs[i]}
            for i in range(3)
        ]
        resp = api("post", "/links/bulk", json=links_data)
        assert resp.status_code == 201
        created = resp.json()
        assert len(created) == 3
        link_ids = [l["id"] for l in created]

        # 2. Verify each exists
        for lid in link_ids:
            resp = api("get", f"/links/{lid}")
            assert resp.status_code == 200

        # 3. Bulk delete
        resp = api("delete", "/links/bulk", json={"linkIds": link_ids})
        assert resp.status_code == 200
        assert resp.json()["deletedCount"] == 3

        # 4. Verify all gone
        for lid in link_ids:
            resp = api("get", f"/links/{lid}")
            assert resp.status_code == 404

    def test_bulk_update_applies_to_all(self):
        """
        Pattern 5: Bulk update changes applied to all specified links.
        """
        # 1. Create links
        slugs = [unique_slug() for _ in range(3)]
        link_ids = []
        for s in slugs:
            resp = api("post", "/links", json={"url": "https://pre-update.com", "slug": s})
            link_ids.append(resp.json()["id"])

        # 2. Bulk update - archive all
        resp = api("patch", "/links/bulk", json={
            "linkIds": link_ids,
            "data": {"archived": True}
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert len(updated) == 3
        for link in updated:
            assert link["archived"] is True

        # 3. Verify each link is archived
        for lid in link_ids:
            resp = api("get", f"/links/{lid}")
            assert resp.json()["archived"] is True


class TestRoleBasedWorkflow:
    """Multi-role operations in same workspace."""

    def test_member_manages_own_links_admin_manages_all(self):
        """
        Pattern 6: Member creates link, can manage it.
        Admin can manage member's link. Member cannot manage admin's link.
        """
        # 1. Member creates a link
        member_slug = unique_slug()
        resp = api("post", "/links", json={"url": "https://member-link.com", "slug": member_slug}, key=MEMBER_KEY)
        assert resp.status_code == 201
        member_link_id = resp.json()["id"]
        assert resp.json()["userId"] == "user3"

        # 2. Member can update own link
        resp = api("put", f"/links/{member_link_id}", json={"title": "My Link"}, key=MEMBER_KEY)
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Link"

        # 3. Admin creates a link
        admin_slug = unique_slug()
        resp = api("post", "/links", json={"url": "https://admin-link.com", "slug": admin_slug}, key=ADMIN_KEY)
        assert resp.status_code == 201
        admin_link_id = resp.json()["id"]

        # 4. Member cannot delete admin's link
        resp = api("delete", f"/links/{admin_link_id}", key=MEMBER_KEY)
        assert resp.status_code == 403

        # 5. Admin can delete member's link
        resp = api("delete", f"/links/{member_link_id}", key=ADMIN_KEY)
        assert resp.status_code == 204

        # 6. Verify member's link is gone
        resp = api("get", f"/links/{member_link_id}", key=MEMBER_KEY)
        assert resp.status_code == 404


class TestMemberManagement:
    """Owner-only member operations."""

    def test_owner_manages_members(self):
        """
        Pattern 6: Only owner can invite, update role, and remove members.
        """
        # 1. Owner invites a member
        email = f"{unique_slug()}@example.com"
        resp = api("post", "/workspaces/members", json={
            "email": email, "name": "New Person", "role": "member"
        }, key=OWNER_KEY)
        assert resp.status_code == 201
        member = resp.json()
        assert member["email"] == email
        assert member["role"] == "member"
        new_user_id = member["userId"]

        # 2. Admin cannot invite members
        resp = api("post", "/workspaces/members", json={
            "email": f"{unique_slug()}@test.com", "name": "X", "role": "member"
        }, key=ADMIN_KEY)
        assert resp.status_code == 403

        # 3. Owner updates role
        resp = api("patch", f"/workspaces/members/{new_user_id}", json={
            "role": "admin"
        }, key=OWNER_KEY)
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

        # 4. Owner removes member
        resp = api("delete", f"/workspaces/members/{new_user_id}", key=OWNER_KEY)
        assert resp.status_code == 204


class TestDomainWorkflow:
    """Domain management with primary domain switching."""

    def test_domain_primary_switching(self):
        """
        Pattern 5+8: Only one domain can be primary at a time.
        """
        # 1. Create first domain as primary
        slug1 = f"{unique_slug()}.link"
        resp = api("post", "/domains", json={"slug": slug1, "primary": True})
        assert resp.status_code == 201
        d1 = resp.json()
        d2 = None
        try:
            assert d1["primary"] is True

            # 2. Create second domain as primary
            slug2 = f"{unique_slug()}.link"
            resp = api("post", "/domains", json={"slug": slug2, "primary": True})
            assert resp.status_code == 201
            d2 = resp.json()
            assert d2["primary"] is True

            # 3. First domain should no longer be primary
            resp = api("get", f"/domains/{d1['id']}")
            assert resp.json()["primary"] is False

            # 4. Second is primary
            resp = api("get", f"/domains/{d2['id']}")
            assert resp.json()["primary"] is True
        finally:
            if d2 is not None:
                api("delete", f"/domains/{d2['id']}")
            api("delete", f"/domains/{d1['id']}")

    def test_link_uses_custom_domain_for_redirect(self):
        """Create link with custom domain, redirect uses that domain path."""
        domain_slug = f"{unique_slug()}.sh"
        api("post", "/domains", json={"slug": domain_slug})

        link_slug = unique_slug()
        resp = api("post", "/links", json={
            "url": "https://custom-domain-target.com",
            "slug": link_slug,
            "domain": domain_slug
        })
        assert resp.status_code == 201
        assert resp.json()["domain"] == domain_slug

        # Redirect via domain/slug path
        resp = api("get", f"/r/{domain_slug}/{link_slug}", key=None, allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://custom-domain-target.com"


class TestFolderHierarchy:
    """Nested folders and link organization."""

    def test_nested_folders_and_link_organization(self):
        """
        Pattern 2+3: Create parent/child folders, put links in each,
        verify folder filter returns only links in that folder.
        """
        # 1. Create parent folder
        parent_name = unique_slug()
        parent = api("post", "/folders", json={"name": parent_name}).json()

        # 2. Create child folder
        child_name = unique_slug()
        child = api("post", "/folders", json={"name": child_name, "parentId": parent["id"]}).json()
        assert child["parentId"] == parent["id"]

        # 3. Create links in each folder
        slug_parent = unique_slug()
        slug_child = unique_slug()
        slug_none = unique_slug()
        api("post", "/links", json={"url": "https://p.com", "slug": slug_parent, "folderId": parent["id"]})
        api("post", "/links", json={"url": "https://c.com", "slug": slug_child, "folderId": child["id"]})
        api("post", "/links", json={"url": "https://n.com", "slug": slug_none})

        # 4. Filter by parent folder
        resp = api("get", "/links", params={"folderId": parent["id"]})
        slugs = [l["slug"] for l in resp.json()]
        assert slug_parent in slugs
        assert slug_child not in slugs
        assert slug_none not in slugs

        # 5. Filter by child folder
        resp = api("get", "/links", params={"folderId": child["id"]})
        slugs = [l["slug"] for l in resp.json()]
        assert slug_child in slugs
        assert slug_parent not in slugs


class TestWorkspaceIsolationWorkflow:
    """End-to-end workspace isolation."""

    def test_workspace_data_completely_isolated(self):
        """
        Pattern 6: Create resources in ws1, verify invisible in ws2.
        """
        # 1. Create tag in ws1
        tag_name = unique_slug()
        tag = api("post", "/tags", json={"name": tag_name, "color": "#ABC"}, key=ADMIN_KEY).json()

        # 2. Create folder in ws1
        folder_name = unique_slug()
        folder = api("post", "/folders", json={"name": folder_name}, key=ADMIN_KEY).json()

        # 3. Create link in ws1
        slug = unique_slug()
        link = api("post", "/links", json={
            "url": "https://ws1.com",
            "slug": slug,
            "tags": [tag["id"]],
            "folderId": folder["id"]
        }, key=ADMIN_KEY).json()

        # 4. ws2 cannot see the link
        resp = api("get", f"/links/{link['id']}", key=OTHER_WS_KEY)
        assert resp.status_code == 404

        # 5. ws2 cannot see the tag
        resp = api("get", f"/tags/{tag['id']}", key=OTHER_WS_KEY)
        assert resp.status_code == 404

        # 6. ws2 cannot see the folder
        resp = api("get", f"/folders/{folder['id']}", key=OTHER_WS_KEY)
        assert resp.status_code == 404

        # 7. ws2 link list is empty (or doesn't contain ws1 data)
        resp = api("get", "/links", key=OTHER_WS_KEY)
        link_ids = [l["id"] for l in resp.json()]
        assert link["id"] not in link_ids


class TestQRCodeAndLinkInfo:
    """QR code generation and link info lookup."""

    def test_qr_code_generation(self):
        """Pattern 5: QR code endpoint returns image data."""
        slug = unique_slug()
        link = api("post", "/links", json={"url": "https://qr.com", "slug": slug}).json()

        # SVG format (default)
        resp = api("get", f"/links/{link['id']}/qr")
        assert resp.status_code == 200
        assert "svg" in resp.headers.get("Content-Type", "").lower() or len(resp.content) > 0

    def test_link_info_lookup_by_domain_slug(self):
        """Pattern 5: /links/info returns the correct link by domain+slug."""
        slug = unique_slug()
        link = api("post", "/links", json={"url": "https://info-lookup.com", "slug": slug}).json()
        domain = link["domain"]

        resp = api("get", "/links/info", params={"domain": domain, "slug": slug})
        assert resp.status_code == 200
        found = resp.json()
        assert found["id"] == link["id"]
        assert found["slug"] == slug
        assert found["url"] == "https://info-lookup.com"

    def test_link_info_not_found_returns_404(self):
        marker = uuid.uuid4().hex
        resp = api("get", "/links/info", params={
            "domain": f"missing-{marker}.com",
            "slug": f"missing-{marker}",
        })
        assert resp.status_code == 404
