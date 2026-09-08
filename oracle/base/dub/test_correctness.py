"""
Correctness tests for Dub — Link Management Platform.
Tests cover: links CRUD, click tracking, password protection, expiration,
device-specific redirects, analytics, domains, tags, folders, bulk operations,
workspace isolation, and role enforcement.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30

# API Keys for different roles/workspaces
OWNER_KEY = "owner_ws1_user1"
ADMIN_KEY = "admin_ws1_user2"
MEMBER_KEY = "member_ws1_user3"
MEMBER2_KEY = "member_ws1_user4"
OTHER_WS_KEY = "admin_ws2_user5"


def api(method, path, key=ADMIN_KEY, **kwargs):
    """Helper to make API requests."""
    headers = dict(kwargs.pop("headers", {}) or {})
    if key:
        headers["X-API-Key"] = key
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


# ============================================================
# Authentication Tests
# ============================================================


class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        resp = api("get", "/links", key=None)
        assert resp.status_code == 401

    def test_invalid_api_key_format_returns_401(self):
        resp = api("get", "/links", key="invalidkey")
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        resp = api("get", "/links", key=ADMIN_KEY)
        assert resp.status_code == 200


# ============================================================
# Link CRUD Tests
# ============================================================


class TestLinkCRUD:
    def test_create_link_with_custom_slug(self):
        slug = f"test-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={
            "url": "https://example.com",
            "slug": slug,
            "title": "Test Link",
            "description": "A test link"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == slug
        assert data["url"] == "https://example.com"
        assert data["title"] == "Test Link"
        assert data["description"] == "A test link"
        assert "id" in data
        assert "createdAt" in data
        assert data["clicks"] == 0

    def test_create_link_auto_generates_slug(self):
        resp = api("post", "/links", json={
            "url": "https://example.com/auto"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["slug"]) == 7
        assert data["slug"].isalnum()

    def test_create_link_duplicate_slug_returns_409(self):
        slug = f"dup-{uuid.uuid4().hex[:8]}"
        resp1 = api("post", "/links", json={"url": "https://a.com", "slug": slug})
        assert resp1.status_code == 201
        resp2 = api("post", "/links", json={"url": "https://b.com", "slug": slug})
        assert resp2.status_code == 409

    def test_create_link_missing_url_returns_422(self):
        resp = api("post", "/links", json={"slug": f"no-url-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 422

    def test_get_link_by_id(self):
        resp = api("post", "/links", json={"url": "https://get-test.com"})
        link_id = resp.json()["id"]
        resp2 = api("get", f"/links/{link_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == link_id

    def test_get_nonexistent_link_returns_404(self):
        resp = api("get", f"/links/missing-{uuid.uuid4().hex}")
        assert resp.status_code == 404

    def test_update_link(self):
        resp = api("post", "/links", json={"url": "https://original.com"})
        link_id = resp.json()["id"]
        resp2 = api("put", f"/links/{link_id}", json={
            "url": "https://updated.com",
            "title": "Updated"
        })
        assert resp2.status_code == 200
        assert resp2.json()["url"] == "https://updated.com"
        assert resp2.json()["title"] == "Updated"

    def test_delete_link(self):
        resp = api("post", "/links", json={"url": "https://delete-me.com"})
        link_id = resp.json()["id"]
        resp2 = api("delete", f"/links/{link_id}")
        assert resp2.status_code == 204
        resp3 = api("get", f"/links/{link_id}")
        assert resp3.status_code == 404

    def test_list_links(self):
        slug = f"list-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={"url": "https://list-test.com", "slug": slug})
        resp = api("get", "/links")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        slugs = [l["slug"] for l in data]
        assert slug in slugs

    def test_list_links_search_filter(self):
        slug = f"searchable-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={"url": "https://search.com", "slug": slug})
        resp = api("get", "/links", params={"search": slug})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(l["slug"] == slug for l in data)

    def test_get_link_count(self):
        resp = api("get", "/links/count")
        assert resp.status_code == 200
        assert "count" in resp.json()
        assert isinstance(resp.json()["count"], int)

    def test_get_link_info_by_domain_slug(self):
        slug = f"info-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://info.com", "slug": slug})
        domain = resp.json()["domain"]
        resp2 = api("get", "/links/info", params={"domain": domain, "slug": slug})
        assert resp2.status_code == 200
        assert resp2.json()["slug"] == slug

    def test_create_link_with_all_optional_fields(self):
        slug = f"full-{uuid.uuid4().hex[:8]}"
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        resp = api("post", "/links", json={
            "url": "https://full.com",
            "slug": slug,
            "title": "Full Link",
            "description": "All fields",
            "expiresAt": expires,
            "password": "secret123",
            "ios": "https://ios.full.com",
            "android": "https://android.full.com",
            "ogTitle": "OG Title",
            "ogDescription": "OG Desc",
            "ogImage": "https://img.com/og.png"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ios"] == "https://ios.full.com"
        assert data["android"] == "https://android.full.com"
        assert data["ogTitle"] == "OG Title"
        assert data["ogDescription"] == "OG Desc"
        assert data["ogImage"] == "https://img.com/og.png"


# ============================================================
# Redirect & Click Tracking Tests
# ============================================================


class TestRedirect:
    def test_redirect_returns_302(self):
        slug = f"redir-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={"url": "https://destination.com", "slug": slug})
        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://destination.com"

    def test_redirect_nonexistent_slug_returns_404(self):
        resp = api("get", f"/r/missing-{uuid.uuid4().hex}", key=None, allow_redirects=False)
        assert resp.status_code == 404

    def test_redirect_increments_click_count(self):
        slug = f"click-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://clicks.com", "slug": slug})
        link_id = resp.json()["id"]

        # Make 3 clicks
        for _ in range(3):
            api("get", f"/r/{slug}", key=None, allow_redirects=False)

        resp2 = api("get", f"/links/{link_id}")
        assert resp2.json()["clicks"] == 3

    def test_redirect_with_custom_domain(self):
        # Create domain first
        domain_slug = f"d-{uuid.uuid4().hex[:6]}.link"
        api("post", "/domains", json={"slug": domain_slug})
        slug = f"cdom-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://custom-domain.com",
            "slug": slug,
            "domain": domain_slug
        })
        resp = api("get", f"/r/{domain_slug}/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://custom-domain.com"

    def test_password_protected_link_no_password_returns_401(self):
        slug = f"pwd-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://secret.com",
            "slug": slug,
            "password": "mypassword"
        })
        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 401

    def test_password_protected_link_wrong_password_returns_401(self):
        slug = f"pwd2-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://secret2.com",
            "slug": slug,
            "password": "correct"
        })
        resp = api("get", f"/r/{slug}", key=None, params={"password": "wrong"}, allow_redirects=False)
        assert resp.status_code == 401

    def test_password_protected_link_correct_password_redirects(self):
        slug = f"pwd3-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://secret3.com",
            "slug": slug,
            "password": "correct"
        })
        resp = api("get", f"/r/{slug}", key=None, params={"password": "correct"}, allow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://secret3.com"

    def test_expired_link_returns_410(self):
        slug = f"exp-{uuid.uuid4().hex[:8]}"
        expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        api("post", "/links", json={
            "url": "https://expired.com",
            "slug": slug,
            "expiresAt": expired
        })
        resp = api("get", f"/r/{slug}", key=None, allow_redirects=False)
        assert resp.status_code == 410

    def test_ios_redirect(self):
        slug = f"ios-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://default.com",
            "slug": slug,
            "ios": "https://ios-app.com"
        })
        resp = api(
            "get",
            f"/r/{slug}",
            key=None,
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
            allow_redirects=False
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://ios-app.com"

    def test_android_redirect(self):
        slug = f"android-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://default.com",
            "slug": slug,
            "android": "https://android-app.com"
        })
        resp = api(
            "get",
            f"/r/{slug}",
            key=None,
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7)"},
            allow_redirects=False
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://android-app.com"

    def test_desktop_uses_default_url(self):
        slug = f"desk-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://desktop.com",
            "slug": slug,
            "ios": "https://ios.com",
            "android": "https://android.com"
        })
        resp = api(
            "get",
            f"/r/{slug}",
            key=None,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=False
        )
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://desktop.com"


# ============================================================
# Analytics Tests
# ============================================================


class TestAnalytics:
    def _create_link_with_clicks(self, num_clicks=5, country="US", user_agent=None):
        slug = f"analytics-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://analytics.com", "slug": slug})
        link_id = resp.json()["id"]

        ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        for _ in range(num_clicks):
            api(
                "get",
                f"/r/{slug}",
                key=None,
                headers={
                    "User-Agent": ua,
                    "X-Forwarded-Country": country,
                    "Referer": "https://google.com"
                },
                allow_redirects=False
            )
        return link_id, slug

    def test_analytics_countries(self):
        link_id, _ = self._create_link_with_clicks(3, country="US")
        resp = api("get", "/analytics/countries", params={"linkId": link_id})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        us_entry = next((d for d in data if d["country"] == "US"), None)
        assert us_entry is not None
        assert us_entry["clicks"] >= 3

    def test_analytics_devices(self):
        link_id, _ = self._create_link_with_clicks(
            2, user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        )
        resp = api("get", "/analytics/devices", params={"linkId": link_id})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        mobile_entry = next((d for d in data if d["device"] == "Mobile"), None)
        assert mobile_entry is not None
        assert mobile_entry["clicks"] >= 2

    def test_analytics_browsers(self):
        link_id, _ = self._create_link_with_clicks(2)
        resp = api("get", "/analytics/browsers", params={"linkId": link_id})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert all("browser" in d and "clicks" in d for d in data)

    def test_analytics_os(self):
        link_id, _ = self._create_link_with_clicks(2)
        resp = api("get", "/analytics/os", params={"linkId": link_id})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert all("os" in d and "clicks" in d for d in data)

    def test_analytics_referers(self):
        link_id, _ = self._create_link_with_clicks(2)
        resp = api("get", "/analytics/referers", params={"linkId": link_id})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        google_entry = next((d for d in data if "google" in d["referer"].lower()), None)
        assert google_entry is not None
        assert google_entry["clicks"] >= 2

    def test_analytics_timeseries(self):
        link_id, _ = self._create_link_with_clicks(3)
        resp = api("get", "/analytics/timeseries", params={
            "linkId": link_id,
            "interval": "24h"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        total_clicks = sum(d["clicks"] for d in data)
        assert total_clicks >= 3

    def test_analytics_requires_auth(self):
        resp = api("get", "/analytics/countries", key=None)
        assert resp.status_code == 401


# ============================================================
# Events Tests
# ============================================================


class TestEvents:
    def test_get_events(self):
        slug = f"evt-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://events.com", "slug": slug})
        link_id = resp.json()["id"]

        api(
            "get",
            f"/r/{slug}",
            key=None,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "X-Forwarded-Country": "GB",
                "Referer": "https://twitter.com"
            },
            allow_redirects=False
        )

        resp2 = api("get", "/events", params={"linkId": link_id})
        assert resp2.status_code == 200
        data = resp2.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        event = data[0]
        assert event["linkId"] == link_id
        assert "timestamp" in event
        assert event["country"] == "GB"

    def test_events_requires_auth(self):
        resp = api("get", "/events", key=None)
        assert resp.status_code == 401


# ============================================================
# Domain Tests
# ============================================================


class TestDomains:
    def test_create_domain(self):
        slug = f"dom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug})
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == slug
        assert data["verified"] is False
        assert "id" in data

    def test_create_duplicate_domain_returns_409(self):
        slug = f"dupdom-{uuid.uuid4().hex[:6]}.link"
        api("post", "/domains", json={"slug": slug})
        resp = api("post", "/domains", json={"slug": slug})
        assert resp.status_code == 409

    def test_list_domains(self):
        slug = f"listdom-{uuid.uuid4().hex[:6]}.link"
        api("post", "/domains", json={"slug": slug})
        resp = api("get", "/domains")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert any(d["slug"] == slug for d in resp.json())

    def test_get_domain(self):
        slug = f"getdom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug})
        domain_id = resp.json()["id"]
        resp2 = api("get", f"/domains/{domain_id}")
        assert resp2.status_code == 200
        assert resp2.json()["slug"] == slug

    def test_update_domain_verify(self):
        slug = f"verdom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug})
        domain_id = resp.json()["id"]
        resp2 = api("patch", f"/domains/{domain_id}", json={"verified": True})
        assert resp2.status_code == 200
        assert resp2.json()["verified"] is True

    def test_delete_domain(self):
        slug = f"deldom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug})
        domain_id = resp.json()["id"]
        resp2 = api("delete", f"/domains/{domain_id}")
        assert resp2.status_code == 204
        resp3 = api("get", f"/domains/{domain_id}")
        assert resp3.status_code == 404

    def test_set_primary_domain(self):
        slug = f"pridom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug, "primary": True})
        assert resp.status_code == 201
        domain = resp.json()
        try:
            assert domain["primary"] is True
        finally:
            api("delete", f"/domains/{domain['id']}")

    def test_member_cannot_create_domain(self):
        slug = f"memdom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug}, key=MEMBER_KEY)
        assert resp.status_code == 403


# ============================================================
# Tag Tests
# ============================================================


class TestTags:
    def test_create_tag(self):
        name = f"tag-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/tags", json={"name": name, "color": "#FF0000"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["color"] == "#FF0000"

    def test_create_duplicate_tag_returns_409(self):
        name = f"dup-tag-{uuid.uuid4().hex[:8]}"
        api("post", "/tags", json={"name": name, "color": "#00FF00"})
        resp = api("post", "/tags", json={"name": name, "color": "#0000FF"})
        assert resp.status_code == 409

    def test_list_tags(self):
        name = f"list-tag-{uuid.uuid4().hex[:8]}"
        api("post", "/tags", json={"name": name, "color": "#123456"})
        resp = api("get", "/tags")
        assert resp.status_code == 200
        assert any(t["name"] == name for t in resp.json())

    def test_update_tag(self):
        name = f"upd-tag-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/tags", json={"name": name, "color": "#111111"})
        tag_id = resp.json()["id"]
        resp2 = api("patch", f"/tags/{tag_id}", json={"color": "#999999"})
        assert resp2.status_code == 200
        assert resp2.json()["color"] == "#999999"

    def test_delete_tag(self):
        name = f"del-tag-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/tags", json={"name": name, "color": "#AAAAAA"})
        tag_id = resp.json()["id"]
        resp2 = api("delete", f"/tags/{tag_id}")
        assert resp2.status_code == 204
        resp3 = api("get", f"/tags/{tag_id}")
        assert resp3.status_code == 404

    def test_filter_links_by_tag(self):
        tag_name = f"filter-tag-{uuid.uuid4().hex[:8]}"
        tag_resp = api("post", "/tags", json={"name": tag_name, "color": "#BBBBBB"})
        tag_id = tag_resp.json()["id"]

        slug = f"tagged-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={
            "url": "https://tagged.com",
            "slug": slug,
            "tags": [tag_id]
        })

        resp = api("get", "/links", params={"tagId": tag_id})
        assert resp.status_code == 200
        assert any(l["slug"] == slug for l in resp.json())

    def test_member_cannot_create_tag(self):
        name = f"mem-tag-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/tags", json={"name": name, "color": "#CCCCCC"}, key=MEMBER_KEY)
        assert resp.status_code == 403


# ============================================================
# Folder Tests
# ============================================================


class TestFolders:
    def test_create_folder(self):
        name = f"folder-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": name})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["parentId"] is None

    def test_create_nested_folder(self):
        parent_name = f"parent-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": parent_name})
        parent_id = resp.json()["id"]

        child_name = f"child-{uuid.uuid4().hex[:8]}"
        resp2 = api("post", "/folders", json={"name": child_name, "parentId": parent_id})
        assert resp2.status_code == 201
        assert resp2.json()["parentId"] == parent_id

    def test_duplicate_folder_name_same_parent_returns_409(self):
        name = f"dupfolder-{uuid.uuid4().hex[:8]}"
        api("post", "/folders", json={"name": name})
        resp = api("post", "/folders", json={"name": name})
        assert resp.status_code == 409

    def test_same_name_different_parents_allowed(self):
        parent1 = api("post", "/folders", json={"name": f"p1-{uuid.uuid4().hex[:8]}"}).json()["id"]
        parent2 = api("post", "/folders", json={"name": f"p2-{uuid.uuid4().hex[:8]}"}).json()["id"]

        name = f"samename-{uuid.uuid4().hex[:8]}"
        resp1 = api("post", "/folders", json={"name": name, "parentId": parent1})
        resp2 = api("post", "/folders", json={"name": name, "parentId": parent2})
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    def test_list_folders(self):
        name = f"listfolder-{uuid.uuid4().hex[:8]}"
        api("post", "/folders", json={"name": name})
        resp = api("get", "/folders")
        assert resp.status_code == 200
        assert any(f["name"] == name for f in resp.json())

    def test_update_folder(self):
        name = f"updfolder-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": name})
        folder_id = resp.json()["id"]
        new_name = f"updated-{uuid.uuid4().hex[:8]}"
        resp2 = api("patch", f"/folders/{folder_id}", json={"name": new_name})
        assert resp2.status_code == 200
        assert resp2.json()["name"] == new_name

    def test_delete_folder(self):
        name = f"delfolder-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": name})
        folder_id = resp.json()["id"]
        resp2 = api("delete", f"/folders/{folder_id}")
        assert resp2.status_code == 204
        resp3 = api("get", f"/folders/{folder_id}")
        assert resp3.status_code == 404

    def test_link_in_folder(self):
        folder_name = f"linkfolder-{uuid.uuid4().hex[:8]}"
        folder_resp = api("post", "/folders", json={"name": folder_name})
        folder_id = folder_resp.json()["id"]

        slug = f"infoldr-{uuid.uuid4().hex[:8]}"
        link_resp = api("post", "/links", json={
            "url": "https://folder-link.com",
            "slug": slug,
            "folderId": folder_id
        })
        assert link_resp.status_code == 201
        assert link_resp.json()["folderId"] == folder_id

        # Filter links by folder
        resp = api("get", "/links", params={"folderId": folder_id})
        assert resp.status_code == 200
        assert any(l["slug"] == slug for l in resp.json())

    def test_member_cannot_create_folder(self):
        name = f"memfolder-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": name}, key=MEMBER_KEY)
        assert resp.status_code == 403


# ============================================================
# Bulk Operations Tests
# ============================================================


class TestBulkOperations:
    def test_bulk_create_links(self):
        links = [
            {"url": f"https://bulk{i}.com", "slug": f"bulk-{uuid.uuid4().hex[:8]}"}
            for i in range(3)
        ]
        resp = api("post", "/links/bulk", json=links)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 3
        for i, link in enumerate(data):
            assert link["url"] == links[i]["url"]

    def test_bulk_create_fails_atomically_on_duplicate(self):
        slug = f"bulkdup-{uuid.uuid4().hex[:8]}"
        api("post", "/links", json={"url": "https://existing.com", "slug": slug})

        links = [
            {"url": "https://new1.com", "slug": f"new1-{uuid.uuid4().hex[:8]}"},
            {"url": "https://dup.com", "slug": slug},  # This will conflict
        ]
        resp = api("post", "/links/bulk", json=links)
        assert resp.status_code == 409

    def test_bulk_update_links(self):
        # Create links
        link_ids = []
        for i in range(3):
            resp = api("post", "/links", json={
                "url": f"https://bulkupd{i}.com",
                "slug": f"bulkupd-{uuid.uuid4().hex[:8]}"
            })
            link_ids.append(resp.json()["id"])

        # Bulk update
        resp = api("patch", "/links/bulk", json={
            "linkIds": link_ids,
            "data": {"title": "Bulk Updated"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(l["title"] == "Bulk Updated" for l in data)

    def test_bulk_delete_links(self):
        link_ids = []
        for i in range(3):
            resp = api("post", "/links", json={
                "url": f"https://bulkdel{i}.com",
                "slug": f"bulkdel-{uuid.uuid4().hex[:8]}"
            })
            link_ids.append(resp.json()["id"])

        resp = api("delete", "/links/bulk", json={"linkIds": link_ids})
        assert resp.status_code == 200
        assert resp.json()["deletedCount"] == 3

        # Verify deleted
        for lid in link_ids:
            resp2 = api("get", f"/links/{lid}")
            assert resp2.status_code == 404

    def test_bulk_create_exceeds_limit_returns_422(self):
        links = [{"url": f"https://over{i}.com"} for i in range(101)]
        resp = api("post", "/links/bulk", json=links)
        assert resp.status_code == 422


# ============================================================
# QR Code Tests
# ============================================================


class TestQRCode:
    def test_get_qr_code_svg(self):
        resp = api("post", "/links", json={"url": "https://qr-test.com"})
        link_id = resp.json()["id"]
        resp2 = api("get", f"/links/{link_id}/qr")
        assert resp2.status_code == 200
        assert "svg" in resp2.headers.get("Content-Type", "").lower() or "xml" in resp2.headers.get("Content-Type", "").lower()

    def test_get_qr_code_png(self):
        resp = api("post", "/links", json={"url": "https://qr-png.com"})
        link_id = resp.json()["id"]
        resp2 = api("get", f"/links/{link_id}/qr", params={"format": "png"})
        assert resp2.status_code == 200
        assert "png" in resp2.headers.get("Content-Type", "").lower()

    def test_qr_code_nonexistent_link_returns_404(self):
        resp = api("get", f"/links/missing-{uuid.uuid4().hex}/qr")
        assert resp.status_code == 404


# ============================================================
# Workspace Tests
# ============================================================


class TestWorkspaces:
    def test_get_workspace(self):
        resp = api("get", "/workspaces")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "name" in data

    def test_update_workspace_owner_only(self):
        resp = api("patch", "/workspaces", json={"name": "Updated WS"}, key=OWNER_KEY)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated WS"

    def test_update_workspace_admin_forbidden(self):
        resp = api("patch", "/workspaces", json={"name": "Nope"}, key=ADMIN_KEY)
        assert resp.status_code == 403

    def test_update_workspace_member_forbidden(self):
        resp = api("patch", "/workspaces", json={"name": "Nope"}, key=MEMBER_KEY)
        assert resp.status_code == 403


# ============================================================
# Members Tests
# ============================================================


class TestMembers:
    def test_list_members(self):
        resp = api("get", "/workspaces/members")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_invite_member_owner_only(self):
        email = f"new-{uuid.uuid4().hex[:6]}@example.com"
        resp = api("post", "/workspaces/members", json={
            "email": email,
            "name": "New User",
            "role": "member"
        }, key=OWNER_KEY)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == email
        assert data["role"] == "member"

    def test_invite_member_admin_forbidden(self):
        email = f"nope-{uuid.uuid4().hex[:6]}@example.com"
        resp = api("post", "/workspaces/members", json={
            "email": email,
            "role": "member"
        }, key=ADMIN_KEY)
        assert resp.status_code == 403

    def test_update_member_role(self):
        email = f"role-{uuid.uuid4().hex[:6]}@example.com"
        resp = api("post", "/workspaces/members", json={
            "email": email,
            "name": "Role User",
            "role": "member"
        }, key=OWNER_KEY)
        user_id = resp.json()["userId"]

        resp2 = api("patch", f"/workspaces/members/{user_id}", json={
            "role": "admin"
        }, key=OWNER_KEY)
        assert resp2.status_code == 200
        assert resp2.json()["role"] == "admin"

    def test_remove_member(self):
        email = f"remove-{uuid.uuid4().hex[:6]}@example.com"
        resp = api("post", "/workspaces/members", json={
            "email": email,
            "name": "Remove User",
            "role": "member"
        }, key=OWNER_KEY)
        user_id = resp.json()["userId"]

        resp2 = api("delete", f"/workspaces/members/{user_id}", key=OWNER_KEY)
        assert resp2.status_code == 204


# ============================================================
# Workspace Isolation Tests
# ============================================================


class TestWorkspaceIsolation:
    def test_links_isolated_between_workspaces(self):
        slug = f"iso-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://ws1.com", "slug": slug}, key=ADMIN_KEY)
        assert resp.status_code == 201
        link_id = resp.json()["id"]

        # Other workspace cannot see this link
        resp2 = api("get", f"/links/{link_id}", key=OTHER_WS_KEY)
        assert resp2.status_code == 404

    def test_tags_isolated_between_workspaces(self):
        name = f"iso-tag-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/tags", json={"name": name, "color": "#111111"}, key=ADMIN_KEY)
        assert resp.status_code == 201
        tag_id = resp.json()["id"]

        resp2 = api("get", f"/tags/{tag_id}", key=OTHER_WS_KEY)
        assert resp2.status_code == 404

    def test_domains_isolated_between_workspaces(self):
        slug = f"isodom-{uuid.uuid4().hex[:6]}.link"
        resp = api("post", "/domains", json={"slug": slug}, key=ADMIN_KEY)
        assert resp.status_code == 201
        domain_id = resp.json()["id"]

        resp2 = api("get", f"/domains/{domain_id}", key=OTHER_WS_KEY)
        assert resp2.status_code == 404


# ============================================================
# Role Enforcement Tests
# ============================================================


class TestRoleEnforcement:
    def test_member_can_create_own_link(self):
        slug = f"mem-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://member.com", "slug": slug}, key=MEMBER_KEY)
        assert resp.status_code == 201
        assert resp.json()["userId"] == "user3"

    def test_member_can_update_own_link(self):
        slug = f"memupd-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://mem-update.com", "slug": slug}, key=MEMBER_KEY)
        link_id = resp.json()["id"]
        resp2 = api("put", f"/links/{link_id}", json={"title": "My Update"}, key=MEMBER_KEY)
        assert resp2.status_code == 200

    def test_member_cannot_update_others_link(self):
        slug = f"adminlink-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://admin-link.com", "slug": slug}, key=ADMIN_KEY)
        link_id = resp.json()["id"]

        resp2 = api("put", f"/links/{link_id}", json={"title": "Hacked"}, key=MEMBER_KEY)
        assert resp2.status_code == 403

    def test_member_cannot_delete_others_link(self):
        slug = f"admindel-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://admin-del.com", "slug": slug}, key=ADMIN_KEY)
        link_id = resp.json()["id"]

        resp2 = api("delete", f"/links/{link_id}", key=MEMBER_KEY)
        assert resp2.status_code == 403

    def test_admin_can_update_any_link(self):
        slug = f"memadmin-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://mem-link.com", "slug": slug}, key=MEMBER_KEY)
        link_id = resp.json()["id"]

        resp2 = api("put", f"/links/{link_id}", json={"title": "Admin Edit"}, key=ADMIN_KEY)
        assert resp2.status_code == 200

    def test_admin_can_delete_any_link(self):
        slug = f"memdel-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/links", json={"url": "https://mem-del.com", "slug": slug}, key=MEMBER_KEY)
        link_id = resp.json()["id"]

        resp2 = api("delete", f"/links/{link_id}", key=ADMIN_KEY)
        assert resp2.status_code == 204

    def test_member_cannot_manage_tags(self):
        resp = api("post", "/tags", json={
            "name": f"forbidden-{uuid.uuid4().hex[:8]}",
            "color": "#000",
        }, key=MEMBER_KEY)
        assert resp.status_code == 403

    def test_member_cannot_manage_domains(self):
        slug = f"forbidden-{uuid.uuid4().hex[:8]}.link"
        resp = api("post", "/domains", json={"slug": slug}, key=MEMBER_KEY)
        assert resp.status_code == 403

    def test_member_cannot_manage_folders(self):
        name = f"forbidden-{uuid.uuid4().hex[:8]}"
        resp = api("post", "/folders", json={"name": name}, key=MEMBER_KEY)
        assert resp.status_code == 403
