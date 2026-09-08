"""
L2 Integration Tests for Dub — Link Management Platform.
Adversarial tests targeting common LLM implementation bugs:
- camelCase field naming (ogTitle, folderId, expiresAt, etc.)
- Filtering/pagination actually working
- Correct status codes (201/204/404/409/410)
- Click counter increments
- Workspace isolation
- Role-based access control
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
# L2 TESTS
# =============================================================================


class TestLinkFieldCasing:
    """Pattern 1: Verify exact camelCase field names in link responses."""

    def test_create_link_returns_all_camelcase_fields(self):
        slug = unique_slug()
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        resp = api("post", "/links", json={
            "url": "https://example.com/camel",
            "slug": slug,
            "title": "Camel Test",
            "description": "Testing casing",
            "expiresAt": expires,
            "ios": "https://ios.example.com",
            "android": "https://android.example.com",
            "ogTitle": "OG T",
            "ogDescription": "OG D",
            "ogImage": "https://img.com/og.png",
        })
        assert resp.status_code == 201
        data = resp.json()
        # Verify camelCase fields
        assert "id" in data
        assert "slug" in data and data["slug"] == slug
        assert "url" in data and data["url"] == "https://example.com/camel"
        assert "title" in data and data["title"] == "Camel Test"
        assert "description" in data
        assert "domain" in data
        assert "folderId" in data
        assert "expiresAt" in data
        assert "ios" in data and data["ios"] == "https://ios.example.com"
        assert "android" in data and data["android"] == "https://android.example.com"
        assert "ogTitle" in data and data["ogTitle"] == "OG T"
        assert "ogDescription" in data and data["ogDescription"] == "OG D"
        assert "ogImage" in data and data["ogImage"] == "https://img.com/og.png"
        assert "archived" in data and data["archived"] is False
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "userId" in data
        assert "clicks" in data and data["clicks"] == 0
        # Verify snake_case NOT present
        assert "folder_id" not in data
        assert "expires_at" not in data
        assert "created_at" not in data
        assert "og_title" not in data

    def test_get_link_returns_camelcase(self):
        resp = api("post", "/links", json={"url": "https://get-camel.com"})
        assert resp.status_code == 201
        link_id = resp.json()["id"]

        resp = api("get", f"/links/{link_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "userId" in data
        assert "folderId" in data


class TestLinkFiltering:
    """Pattern 3: Verify filters actually filter results."""

    def test_filter_by_tag_id(self):
        # Create a tag
        tag_resp = api("post", "/tags", json={"name": unique_slug(), "color": "#FF0000"})
        assert tag_resp.status_code == 201
        tag_id = tag_resp.json()["id"]

        # Create links with and without tag
        slug_tagged = unique_slug()
        slug_untagged = unique_slug()
        api("post", "/links", json={"url": "https://tagged.com", "slug": slug_tagged, "tags": [tag_id]})
        api("post", "/links", json={"url": "https://untagged.com", "slug": slug_untagged})

        # Filter by tag
        resp = api("get", "/links", params={"tagId": tag_id})
        assert resp.status_code == 200
        slugs = [l["slug"] for l in resp.json()]
        assert slug_tagged in slugs
        assert slug_untagged not in slugs

    def test_filter_by_folder_id(self):
        # Create folder
        folder_resp = api("post", "/folders", json={"name": unique_slug()})
        assert folder_resp.status_code == 201
        folder_id = folder_resp.json()["id"]

        # Create links in/out of folder
        slug_in = unique_slug()
        slug_out = unique_slug()
        api("post", "/links", json={"url": "https://infolder.com", "slug": slug_in, "folderId": folder_id})
        api("post", "/links", json={"url": "https://nofolder.com", "slug": slug_out})

        # Filter
        resp = api("get", "/links", params={"folderId": folder_id})
        assert resp.status_code == 200
        slugs = [l["slug"] for l in resp.json()]
        assert slug_in in slugs
        assert slug_out not in slugs

    def test_filter_archived(self):
        slug_archived = unique_slug()
        slug_active = unique_slug()
        api("post", "/links", json={"url": "https://archived.com", "slug": slug_archived, "archived": True})
        api("post", "/links", json={"url": "https://active.com", "slug": slug_active, "archived": False})

        # Filter archived=true
        resp = api("get", "/links", params={"archived": "true"})
        assert resp.status_code == 200
        slugs = [l["slug"] for l in resp.json()]
        assert slug_archived in slugs
        assert slug_active not in slugs

    def test_search_filter_matches_slug_or_url(self):
        search_term = unique_slug()
        slug = f"link-{search_term}"
        api("post", "/links", json={"url": f"https://{search_term}.com", "slug": slug})

        resp = api("get", "/links", params={"search": search_term})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert any(search_term in l["slug"] or search_term in l["url"] for l in resp.json())

    def test_link_count_with_filter(self):
        tag_resp = api("post", "/tags", json={"name": unique_slug(), "color": "#00FF00"})
        tag_id = tag_resp.json()["id"]

        api("post", "/links", json={"url": "https://c1.com", "slug": unique_slug(), "tags": [tag_id]})
        api("post", "/links", json={"url": "https://c2.com", "slug": unique_slug(), "tags": [tag_id]})
        api("post", "/links", json={"url": "https://c3.com", "slug": unique_slug()})

        resp = api("get", "/links/count", params={"tagId": tag_id})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


class TestPagination:
    """Pattern 3: Pagination parameters actually limit results."""

    def test_pagination_limits_results(self):
        # Create several links
        for _ in range(5):
            api("post", "/links", json={"url": "https://page.com", "slug": unique_slug()})

        resp = api("get", "/links", params={"page": 1, "pageSize": 2})
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_pagination_page_2_different_from_page_1(self):
        slugs_created = []
        for _ in range(4):
            s = unique_slug()
            api("post", "/links", json={"url": "https://paginate.com", "slug": s})
            slugs_created.append(s)

        resp1 = api("get", "/links", params={"page": 1, "pageSize": 2})
        resp2 = api("get", "/links", params={"page": 2, "pageSize": 2})
        ids1 = [l["id"] for l in resp1.json()]
        ids2 = [l["id"] for l in resp2.json()]
        # Pages should not overlap
        assert set(ids1).isdisjoint(set(ids2))


class TestClickTracking:
    """Pattern 5: Click counter actually increments, not just hardcoded."""

    def test_redirect_increments_click_count(self):
        slug = unique_slug()
        resp = api("post", "/links", json={"url": "https://click-test.com", "slug": slug})
        assert resp.status_code == 201
        link_id = resp.json()["id"]

        # Click the link 3 times
        for _ in range(3):
            api("get", f"/r/{slug}", key=None, allow_redirects=False)

        # Verify clicks = 3
        resp = api("get", f"/links/{link_id}")
        assert resp.json()["clicks"] == 3

    def test_redirect_returns_302(self):
        slug = unique_slug()
        api("post", "/links", json={"url": "https://redirect-target.com", "slug": slug})

        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://redirect-target.com"

    def test_redirect_nonexistent_slug_returns_404(self):
        resp = api("get", f"/r/missing-{uuid.uuid4().hex}", key=None,
                   allow_redirects=False)
        assert resp.status_code == 404

    def test_redirect_expired_link_returns_410(self):
        slug = unique_slug()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        api("post", "/links", json={"url": "https://expired.com", "slug": slug, "expiresAt": past})

        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 410

    def test_redirect_password_protected_without_password_returns_401(self):
        slug = unique_slug()
        api("post", "/links", json={"url": "https://secret.com", "slug": slug, "password": "mypass"})

        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 401

    def test_redirect_password_protected_with_correct_password(self):
        slug = unique_slug()
        api("post", "/links", json={"url": "https://secretok.com", "slug": slug, "password": "pass123"})

        resp = api("get", f"/r/{slug}", key=None, params={"password": "pass123"},
                   allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://secretok.com"


class TestDeviceRedirects:
    """Pattern 5: iOS/Android redirects based on User-Agent."""

    def test_ios_redirect(self):
        slug = unique_slug()
        api("post", "/links", json={
            "url": "https://default.com",
            "slug": slug,
            "ios": "https://ios-app.com"
        })

        resp = api("get", f"/r/{slug}", key=None,
                   headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS)"},
                   allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://ios-app.com"

    def test_android_redirect(self):
        slug = unique_slug()
        api("post", "/links", json={
            "url": "https://default.com",
            "slug": slug,
            "android": "https://android-app.com"
        })

        resp = api("get", f"/r/{slug}", key=None,
                   headers={"User-Agent": "Mozilla/5.0 (Linux; Android 12)"},
                   allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://android-app.com"

    def test_desktop_gets_default_url(self):
        slug = unique_slug()
        api("post", "/links", json={
            "url": "https://desktop.com",
            "slug": slug,
            "ios": "https://ios.com",
            "android": "https://android.com"
        })

        resp = api("get", f"/r/{slug}", key=None,
                   headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                   allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://desktop.com"


class TestDomainTagFolderFields:
    """Pattern 1+4: Correct status codes and field names for domain/tag/folder."""

    def test_domain_create_returns_201_with_fields(self):
        slug = f"{unique_slug()}.link"
        resp = api("post", "/domains", json={"slug": slug})
        assert resp.status_code == 201
        d = resp.json()
        assert d["slug"] == slug
        assert "id" in d
        assert "verified" in d
        assert "primary" in d
        assert "createdAt" in d

    def test_tag_create_returns_201_with_fields(self):
        name = unique_slug()
        resp = api("post", "/tags", json={"name": name, "color": "#AABBCC"})
        assert resp.status_code == 201
        t = resp.json()
        assert t["name"] == name
        assert t["color"] == "#AABBCC"
        assert "id" in t
        assert "createdAt" in t

    def test_folder_create_returns_201_with_fields(self):
        name = unique_slug()
        resp = api("post", "/folders", json={"name": name})
        assert resp.status_code == 201
        f = resp.json()
        assert f["name"] == name
        assert "id" in f
        assert "parentId" in f
        assert "createdAt" in f

    def test_delete_domain_returns_204(self):
        slug = f"{unique_slug()}.io"
        d = api("post", "/domains", json={"slug": slug}).json()
        resp = api("delete", f"/domains/{d['id']}")
        assert resp.status_code == 204

    def test_delete_tag_returns_204(self):
        t = api("post", "/tags", json={"name": unique_slug(), "color": "#000"}).json()
        resp = api("delete", f"/tags/{t['id']}")
        assert resp.status_code == 204

    def test_delete_folder_returns_204(self):
        f = api("post", "/folders", json={"name": unique_slug()}).json()
        resp = api("delete", f"/folders/{f['id']}")
        assert resp.status_code == 204


class TestWorkspaceIsolation:
    """Pattern 6: Different workspaces cannot see each other's data."""

    def test_link_not_visible_in_other_workspace(self):
        slug = unique_slug()
        api("post", "/links", json={"url": "https://ws1only.com", "slug": slug}, key=ADMIN_KEY)

        resp = api("get", "/links", key=OTHER_WS_KEY)
        assert resp.status_code == 200
        slugs = [l["slug"] for l in resp.json()]
        assert slug not in slugs

    def test_tag_not_visible_in_other_workspace(self):
        name = unique_slug()
        api("post", "/tags", json={"name": name, "color": "#123"}, key=ADMIN_KEY)

        resp = api("get", "/tags", key=OTHER_WS_KEY)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert name not in names

    def test_folder_not_visible_in_other_workspace(self):
        name = unique_slug()
        api("post", "/folders", json={"name": name}, key=ADMIN_KEY)

        resp = api("get", "/folders", key=OTHER_WS_KEY)
        assert resp.status_code == 200
        names = [f["name"] for f in resp.json()]
        assert name not in names


class TestRoleEnforcement:
    """Pattern 6: Role permissions enforced correctly."""

    def test_member_cannot_create_domain(self):
        resp = api("post", "/domains", json={"slug": f"{unique_slug()}.com"}, key=MEMBER_KEY)
        assert resp.status_code == 403

    def test_member_cannot_create_tag(self):
        resp = api("post", "/tags", json={"name": unique_slug(), "color": "#FFF"}, key=MEMBER_KEY)
        assert resp.status_code == 403

    def test_member_cannot_delete_others_link(self):
        slug = unique_slug()
        link = api("post", "/links", json={"url": "https://admin-link.com", "slug": slug}, key=ADMIN_KEY).json()

        resp = api("delete", f"/links/{link['id']}", key=MEMBER_KEY)
        assert resp.status_code == 403

    def test_member_can_create_own_link(self):
        resp = api("post", "/links", json={"url": "https://member.com", "slug": unique_slug()}, key=MEMBER_KEY)
        assert resp.status_code == 201
        assert resp.json()["userId"] == "user3"


class TestConflicts:
    """Pattern 8: Uniqueness constraints enforced."""

    def test_duplicate_tag_name_returns_409(self):
        name = unique_slug()
        api("post", "/tags", json={"name": name, "color": "#111"})
        resp = api("post", "/tags", json={"name": name, "color": "#222"})
        assert resp.status_code == 409

    def test_duplicate_domain_slug_returns_409(self):
        slug = f"{unique_slug()}.dev"
        api("post", "/domains", json={"slug": slug})
        resp = api("post", "/domains", json={"slug": slug})
        assert resp.status_code == 409

    def test_duplicate_folder_name_same_parent_returns_409(self):
        name = unique_slug()
        api("post", "/folders", json={"name": name})
        resp = api("post", "/folders", json={"name": name})
        assert resp.status_code == 409
