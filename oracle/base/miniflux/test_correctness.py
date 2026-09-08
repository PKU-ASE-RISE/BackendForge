"""
BackendForge - Comprehensive Correctness Tests for Miniflux Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# API keys - the key IS the username (auto-created on first request)
ADMIN_KEY = "admin-user-first"  # First user auto-created becomes admin
USER_KEY = f"regular-user-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"another-user-{uuid.uuid4().hex[:8]}"

ADMIN_HEADERS = {
    "X-Auth-Token": ADMIN_KEY,
    "Content-Type": "application/json",
}

USER_HEADERS = {
    "X-Auth-Token": USER_KEY,
    "Content-Type": "application/json",
}

USER2_HEADERS = {
    "X-Auth-Token": USER2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None, content_type=None):
    h = dict(headers or ADMIN_HEADERS)
    if content_type:
        h["Content-Type"] = content_type
    if content_type and "xml" in content_type:
        return requests.post(f"{BASE_URL}{path}", data=json_data, headers=h, timeout=30)
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=h, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or ADMIN_HEADERS, timeout=30)


def api_delete(path, params=None, headers=None):
    return requests.delete(f"{BASE_URL}{path}", params=params, headers=headers or ADMIN_HEADERS, timeout=30)


# ── Setup: ensure admin user is created first ──

def ensure_admin():
    """Make a request with ADMIN_KEY to ensure the admin user is auto-created first."""
    api_get("/v1/me", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════
# PART 1: Health & Version (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealthAndVersion:

    def test_healthcheck_endpoint(self):
        resp = requests.get(f"{BASE_URL}/healthcheck", timeout=30)
        assert resp.status_code == 200

    def test_healthcheck_no_auth_required(self):
        """Healthcheck should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/healthcheck", timeout=30)
        assert resp.status_code == 200

    def test_version_endpoint(self):
        ensure_admin()
        resp = api_get("/v1/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Auth-Token should return 401."""
        resp = requests.get(f"{BASE_URL}/v1/feeds", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_categories(self):
        resp = requests.get(f"{BASE_URL}/v1/categories", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_entries(self):
        resp = requests.get(f"{BASE_URL}/v1/entries", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_user(self):
        """A new key should auto-create a user."""
        ensure_admin()
        new_key = f"new-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Auth-Token": new_key, "Content-Type": "application/json"}
        resp = api_get("/v1/me", headers=headers)
        assert resp.status_code == 200
        user = resp.json()
        assert user["username"] == new_key
        assert user["id"] is not None

    def test_first_user_is_admin(self):
        """The first auto-created user (ADMIN_KEY) should be admin."""
        ensure_admin()
        resp = api_get("/v1/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["is_admin"] is True

    def test_subsequent_user_is_not_admin(self):
        """Users created after the first should not be admin."""
        ensure_admin()
        resp = api_get("/v1/me", headers=USER_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert user["is_admin"] is False


# ════════════════════════════════════════════════════════════════════
# PART 3: Category CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategoryCRUD:

    def test_create_category(self):
        ensure_admin()
        resp = api_post("/v1/categories", {"title": f"Tech-{UNIQUE}"})
        assert resp.status_code == 201
        cat = resp.json()
        assert cat["title"] == f"Tech-{UNIQUE}"
        assert "id" in cat
        assert "user_id" in cat

    def test_list_categories(self):
        ensure_admin()
        # Create a category first
        api_post("/v1/categories", {"title": f"ListCat-{UNIQUE}"})
        resp = api_get("/v1/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        titles = [c["title"] for c in cats]
        assert f"ListCat-{UNIQUE}" in titles

    def test_update_category(self):
        ensure_admin()
        create_resp = api_post("/v1/categories", {"title": f"OldCat-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_put(f"/v1/categories/{cat_id}", {"title": f"NewCat-{UNIQUE}"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == f"NewCat-{UNIQUE}"

    def test_delete_category_empty(self):
        ensure_admin()
        create_resp = api_post("/v1/categories", {"title": f"EmptyCat-{UNIQUE}"})
        cat_id = create_resp.json()["id"]

        resp = api_delete(f"/v1/categories/{cat_id}")
        assert resp.status_code == 204

    def test_delete_category_with_feeds_fails(self):
        """Category with feeds cannot be deleted."""
        ensure_admin()
        create_cat = api_post("/v1/categories", {"title": f"BusyCat-{UNIQUE}"})
        cat_id = create_cat.json()["id"]

        # Create a feed in this category
        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/busy-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Busy Feed"
        })

        resp = api_delete(f"/v1/categories/{cat_id}")
        assert resp.status_code == 400

    def test_delete_nonexistent_category(self):
        ensure_admin()
        resp = api_delete("/v1/categories/999999")
        assert resp.status_code == 404

    def test_duplicate_category_title(self):
        """Same user cannot have two categories with the same title."""
        ensure_admin()
        title = f"DupCat-{UNIQUE}"
        resp1 = api_post("/v1/categories", {"title": title})
        assert resp1.status_code == 201
        resp2 = api_post("/v1/categories", {"title": title})
        assert resp2.status_code == 409

    def test_categories_with_counts(self):
        """When counts=true, include total_unread and total_read."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"CountCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        # Create a feed and entry
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/count-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Count Feed"
        })
        feed_id = feed_resp.json()["feed_id"]
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Count Entry",
            "url": f"https://example.com/count-entry-{UNIQUE}"
        })

        resp = api_get("/v1/categories", params={"counts": "true"})
        assert resp.status_code == 200
        cats = resp.json()
        # Find our category
        our_cat = next((c for c in cats if c["id"] == cat_id), None)
        assert our_cat is not None
        assert "total_unread" in our_cat


# ════════════════════════════════════════════════════════════════════
# PART 4: Feed CRUD
# ════════════════════════════════════════════════════════════════════


class TestFeedCRUD:

    def test_create_feed(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"FeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/feed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "My Test Feed",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "feed_id" in data
        assert isinstance(data["feed_id"], int)

    def test_get_feed(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"GetFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/getfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Get Feed Test",
        })
        feed_id = create_resp.json()["feed_id"]

        resp = api_get(f"/v1/feeds/{feed_id}")
        assert resp.status_code == 200
        feed = resp.json()
        assert feed["id"] == feed_id
        assert feed["feed_url"] == f"https://example.com/getfeed-{UNIQUE}.xml"
        assert feed["title"] == "Get Feed Test"
        assert "category" in feed
        assert feed["category"]["id"] == cat_id

    def test_list_feeds(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"ListFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/listfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "List Feed"
        })

        resp = api_get("/v1/feeds")
        assert resp.status_code == 200
        feeds = resp.json()
        assert isinstance(feeds, list)
        assert len(feeds) >= 1
        urls = [f["feed_url"] for f in feeds]
        assert f"https://example.com/listfeed-{UNIQUE}.xml" in urls

    def test_update_feed(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"UpdFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/updfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Original Title"
        })
        feed_id = create_resp.json()["feed_id"]

        resp = api_put(f"/v1/feeds/{feed_id}", {"title": "Updated Title"})
        assert resp.status_code == 200
        feed = resp.json()
        assert feed["title"] == "Updated Title"

    def test_delete_feed(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DelFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/delfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "To Delete"
        })
        feed_id = create_resp.json()["feed_id"]

        resp = api_delete(f"/v1/feeds/{feed_id}")
        assert resp.status_code == 204

        # Should not be found anymore
        get_resp = api_get(f"/v1/feeds/{feed_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_feed(self):
        ensure_admin()
        resp = api_delete("/v1/feeds/999999")
        assert resp.status_code == 404

    def test_duplicate_feed_url(self):
        """Same user cannot subscribe to the same URL twice."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DupFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        url = f"https://example.com/dupfeed-{UNIQUE}.xml"
        resp1 = api_post("/v1/feeds", {"feed_url": url, "category_id": cat_id, "title": "F1"})
        assert resp1.status_code == 201
        resp2 = api_post("/v1/feeds", {"feed_url": url, "category_id": cat_id, "title": "F2"})
        assert resp2.status_code == 409

    def test_get_category_feeds(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"CatFeeds-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/catfeed1-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Cat Feed 1"
        })

        resp = api_get(f"/v1/categories/{cat_id}/feeds")
        assert resp.status_code == 200
        feeds = resp.json()
        assert isinstance(feeds, list)
        assert len(feeds) >= 1
        for f in feeds:
            assert f["category"]["id"] == cat_id

    def test_refresh_feed(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"RefreshCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        create_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/refresh-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Refresh Feed"
        })
        feed_id = create_resp.json()["feed_id"]

        resp = api_put(f"/v1/feeds/{feed_id}/refresh")
        assert resp.status_code == 204

    def test_refresh_all_feeds(self):
        ensure_admin()
        resp = api_put("/v1/feeds/refresh")
        assert resp.status_code == 204

    def test_refresh_nonexistent_feed(self):
        ensure_admin()
        resp = api_put("/v1/feeds/999999/refresh")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Entry CRUD
# ════════════════════════════════════════════════════════════════════


class TestEntryCRUD:

    def test_create_entry(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"EntryCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Entry Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": f"Article {UNIQUE}",
            "url": f"https://example.com/article-{UNIQUE}",
            "content": "<p>Hello world</p>",
            "author": "Test Author"
        })
        assert resp.status_code == 201
        entry = resp.json()
        assert entry["title"] == f"Article {UNIQUE}"
        assert entry["url"] == f"https://example.com/article-{UNIQUE}"
        assert entry["status"] == "unread"
        assert entry["starred"] is False
        assert entry["feed_id"] == feed_id
        assert "id" in entry
        assert "published_at" in entry

    def test_get_entry(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"GetEntryCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/getentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Get Entry Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        create_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Get This Entry",
            "url": f"https://example.com/getthis-{UNIQUE}",
        })
        entry_id = create_resp.json()["id"]

        resp = api_get(f"/v1/entries/{entry_id}")
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["id"] == entry_id
        assert entry["title"] == "Get This Entry"

    def test_get_entry_not_found(self):
        ensure_admin()
        resp = api_get("/v1/entries/999999")
        assert resp.status_code == 404

    def test_list_entries(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"ListEntryCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/listentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "List Entry Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        for i in range(3):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Entry {i} {UNIQUE}",
                "url": f"https://example.com/listentry-{UNIQUE}-{i}",
            })

        resp = api_get("/v1/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert data["total"] >= 3

    def test_list_entries_result_set_structure(self):
        """Verify EntryResultSet has total and entries fields."""
        ensure_admin()
        resp = api_get("/v1/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["entries"], list)

    def test_update_entry(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"UpdEntryCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/updentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Upd Entry Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        create_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Original Title",
            "url": f"https://example.com/updentry-{UNIQUE}",
            "content": "Original content"
        })
        entry_id = create_resp.json()["id"]

        resp = api_put(f"/v1/entries/{entry_id}", {
            "title": "Updated Title",
            "content": "Updated content"
        })
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["title"] == "Updated Title"
        assert entry["content"] == "Updated content"

    def test_create_entry_in_nonexistent_feed(self):
        ensure_admin()
        resp = api_post("/v1/feeds/999999/entries", {
            "title": "Ghost Entry",
            "url": "https://example.com/ghost"
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Entry Status & Bookmarks
# ════════════════════════════════════════════════════════════════════


class TestEntryStatusAndBookmarks:

    def _create_entry(self, suffix=""):
        """Helper to create a feed + entry."""
        cat_resp = api_post("/v1/categories", {"title": f"StatusCat-{UNIQUE}-{suffix}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/status-{UNIQUE}-{suffix}.xml",
            "category_id": cat_id,
            "title": f"Status Feed {suffix}"
        })
        feed_id = feed_resp.json()["feed_id"]
        entry_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": f"Status Entry {suffix}",
            "url": f"https://example.com/status-{UNIQUE}-{suffix}",
        })
        return entry_resp.json()["id"], feed_id

    def test_toggle_bookmark(self):
        ensure_admin()
        entry_id, _ = self._create_entry("bookmark")

        # Initially not starred
        entry = api_get(f"/v1/entries/{entry_id}").json()
        assert entry["starred"] is False

        # Toggle on
        resp = api_put(f"/v1/entries/{entry_id}/bookmark")
        assert resp.status_code == 204

        entry = api_get(f"/v1/entries/{entry_id}").json()
        assert entry["starred"] is True

        # Toggle off
        resp = api_put(f"/v1/entries/{entry_id}/bookmark")
        assert resp.status_code == 204

        entry = api_get(f"/v1/entries/{entry_id}").json()
        assert entry["starred"] is False

    def test_bookmark_nonexistent_entry(self):
        ensure_admin()
        resp = api_put("/v1/entries/999999/bookmark")
        assert resp.status_code == 404

    def test_bulk_update_status(self):
        """PUT /v1/entries should update status for multiple entries."""
        ensure_admin()
        entry_id1, _ = self._create_entry("bulk1")
        entry_id2, _ = self._create_entry("bulk2")

        resp = api_put("/v1/entries", {
            "entry_ids": [entry_id1, entry_id2],
            "status": "read"
        })
        assert resp.status_code == 204

        # Verify both are now read
        e1 = api_get(f"/v1/entries/{entry_id1}").json()
        e2 = api_get(f"/v1/entries/{entry_id2}").json()
        assert e1["status"] == "read"
        assert e2["status"] == "read"

    def test_bulk_update_to_removed(self):
        ensure_admin()
        entry_id, _ = self._create_entry("remove")

        resp = api_put("/v1/entries", {
            "entry_ids": [entry_id],
            "status": "removed"
        })
        assert resp.status_code == 204

        entry = api_get(f"/v1/entries/{entry_id}").json()
        assert entry["status"] == "removed"

    def test_starring_independent_of_status(self):
        """Starring should not change read status."""
        ensure_admin()
        entry_id, _ = self._create_entry("indep")

        # Mark as read
        api_put("/v1/entries", {"entry_ids": [entry_id], "status": "read"})

        # Toggle bookmark
        api_put(f"/v1/entries/{entry_id}/bookmark")

        # Should still be read
        entry = api_get(f"/v1/entries/{entry_id}").json()
        assert entry["status"] == "read"
        assert entry["starred"] is True


# ════════════════════════════════════════════════════════════════════
# PART 7: Mark All As Read
# ════════════════════════════════════════════════════════════════════


class TestMarkAllAsRead:

    def test_mark_feed_entries_as_read(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"MarkFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/markfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Mark Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        # Create unread entries
        for i in range(3):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Mark Entry {i}",
                "url": f"https://example.com/mark-{UNIQUE}-{i}",
            })

        resp = api_put(f"/v1/feeds/{feed_id}/mark-all-as-read")
        assert resp.status_code == 204

        # All should be read now
        entries_resp = api_get(f"/v1/feeds/{feed_id}/entries", params={"status": "unread"})
        assert entries_resp.json()["total"] == 0

    def test_mark_category_entries_as_read(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"MarkCatCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/markcat-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Mark Cat Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        for i in range(3):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Cat Mark Entry {i}",
                "url": f"https://example.com/markcat-{UNIQUE}-{i}",
            })

        resp = api_put(f"/v1/categories/{cat_id}/mark-all-as-read")
        assert resp.status_code == 204

        entries_resp = api_get(f"/v1/categories/{cat_id}/entries", params={"status": "unread"})
        assert entries_resp.json()["total"] == 0

    def test_mark_nonexistent_feed_as_read(self):
        ensure_admin()
        resp = api_put("/v1/feeds/999999/mark-all-as-read")
        assert resp.status_code == 404

    def test_mark_nonexistent_category_as_read(self):
        ensure_admin()
        resp = api_put("/v1/categories/999999/mark-all-as-read")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Entry Filtering & Pagination
# ════════════════════════════════════════════════════════════════════


class TestEntryFiltering:

    _setup_counter = 0

    def _setup_entries(self):
        """Create feed with entries for filtering tests."""
        TestEntryFiltering._setup_counter += 1
        suffix = f"{UNIQUE}-{TestEntryFiltering._setup_counter}"

        cat_resp = api_post("/v1/categories", {"title": f"FilterCat-{suffix}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/filter-{suffix}.xml",
            "category_id": cat_id,
            "title": "Filter Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        entry_ids = []
        for i in range(5):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Filter Entry {i} {suffix}",
                "url": f"https://example.com/filter-{suffix}-{i}",
                "content": f"Content for entry {i}"
            })
            entry_ids.append(r.json()["id"])

        return feed_id, cat_id, entry_ids

    def test_filter_by_status(self):
        ensure_admin()
        feed_id, cat_id, entry_ids = self._setup_entries()

        # Mark first two as read
        api_put("/v1/entries", {"entry_ids": entry_ids[:2], "status": "read"})

        resp = api_get("/v1/entries", params={"status": "unread", "feed_id": feed_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for e in data["entries"]:
            assert e["status"] == "unread"

    def test_filter_by_starred(self):
        ensure_admin()
        feed_id, cat_id, entry_ids = self._setup_entries()

        # Star one entry
        api_put(f"/v1/entries/{entry_ids[0]}/bookmark")

        resp = api_get("/v1/entries", params={"starred": "true", "feed_id": feed_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for e in data["entries"]:
            assert e["starred"] is True

    def test_filter_by_search(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"SearchCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/search-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Search Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        search_term = f"UniqueSearchTerm{UNIQUE}"
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": f"Has {search_term} in title",
            "url": f"https://example.com/search-{UNIQUE}-found",
        })
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "No match here",
            "url": f"https://example.com/search-{UNIQUE}-notfound",
        })

        resp = api_get("/v1/entries", params={"search": search_term, "feed_id": feed_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for e in data["entries"]:
            assert search_term.lower() in e["title"].lower() or search_term.lower() in (e.get("content") or "").lower()

    def test_limit_parameter(self):
        ensure_admin()
        feed_id, _, entry_ids = self._setup_entries()

        resp = api_get("/v1/entries", params={"limit": 2, "feed_id": feed_id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) <= 2
        # Total should still reflect all matching entries
        assert data["total"] >= 5

    def test_offset_parameter(self):
        ensure_admin()
        feed_id, _, entry_ids = self._setup_entries()

        # Get first page
        resp1 = api_get("/v1/entries", params={
            "limit": 2, "offset": 0, "feed_id": feed_id,
            "order": "id", "direction": "asc",
        })
        # Get second page
        resp2 = api_get("/v1/entries", params={
            "limit": 2, "offset": 2, "feed_id": feed_id,
            "order": "id", "direction": "asc",
        })

        ids1 = [e["id"] for e in resp1.json()["entries"]]
        ids2 = [e["id"] for e in resp2.json()["entries"]]
        # Pages should not overlap
        assert set(ids1).isdisjoint(set(ids2))

    def test_direction_asc(self):
        ensure_admin()
        feed_id, _, _ = self._setup_entries()

        resp = api_get("/v1/entries", params={"order": "id", "direction": "asc", "feed_id": feed_id})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        if len(entries) >= 2:
            ids = [e["id"] for e in entries]
            assert ids == sorted(ids)

    def test_direction_desc(self):
        ensure_admin()
        feed_id, _, _ = self._setup_entries()

        resp = api_get("/v1/entries", params={"order": "id", "direction": "desc", "feed_id": feed_id})
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        if len(entries) >= 2:
            ids = [e["id"] for e in entries]
            assert ids == sorted(ids, reverse=True)

    def test_feed_entries_endpoint(self):
        """GET /v1/feeds/{id}/entries should return entries for that feed only."""
        ensure_admin()
        feed_id, _, _ = self._setup_entries()

        resp = api_get(f"/v1/feeds/{feed_id}/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        for e in data["entries"]:
            assert e["feed_id"] == feed_id

    def test_category_entries_endpoint(self):
        """GET /v1/categories/{id}/entries should return entries for that category."""
        ensure_admin()
        _, cat_id, _ = self._setup_entries()

        resp = api_get(f"/v1/categories/{cat_id}/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert data["total"] >= 1

    def test_feed_entry_endpoint(self):
        """GET /v1/feeds/{id}/entries/{entry_id} should return specific entry."""
        ensure_admin()
        feed_id, _, entry_ids = self._setup_entries()

        resp = api_get(f"/v1/feeds/{feed_id}/entries/{entry_ids[0]}")
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["id"] == entry_ids[0]
        assert entry["feed_id"] == feed_id


# ════════════════════════════════════════════════════════════════════
# PART 9: Feed Counters
# ════════════════════════════════════════════════════════════════════


class TestFeedCounters:

    def test_feed_counters_structure(self):
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"CounterCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/counter-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Counter Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        # Create entries
        entry_ids = []
        for i in range(4):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Counter Entry {i}",
                "url": f"https://example.com/counter-{UNIQUE}-{i}",
            })
            entry_ids.append(r.json()["id"])

        # Mark 2 as read
        api_put("/v1/entries", {"entry_ids": entry_ids[:2], "status": "read"})

        resp = api_get("/v1/feeds/counters")
        assert resp.status_code == 200
        data = resp.json()
        assert "reads" in data
        assert "unreads" in data

        # Feed ID should be string key in maps
        feed_id_str = str(feed_id)
        assert feed_id_str in data["reads"]
        assert feed_id_str in data["unreads"]
        assert data["reads"][feed_id_str] == 2
        assert data["unreads"][feed_id_str] == 2


# ════════════════════════════════════════════════════════════════════
# PART 10: User Management (Admin)
# ════════════════════════════════════════════════════════════════════


class TestUserManagement:

    def test_get_current_user(self):
        ensure_admin()
        resp = api_get("/v1/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert "id" in user
        assert "username" in user
        assert "is_admin" in user

    def test_list_users_as_admin(self):
        ensure_admin()
        resp = api_get("/v1/users", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 1

    def test_list_users_as_non_admin(self):
        """Non-admin should get 403."""
        ensure_admin()
        api_get("/v1/me", headers=USER_HEADERS)  # ensure user exists
        resp = api_get("/v1/users", headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_create_user_as_admin(self):
        ensure_admin()
        username = f"created-user-{UNIQUE}"
        resp = api_post("/v1/users", {
            "username": username,
            "password": "secret123",
            "is_admin": False,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 201
        user = resp.json()
        assert user["username"] == username
        assert user["is_admin"] is False
        assert "id" in user

    def test_create_user_as_non_admin(self):
        """Non-admin should get 403."""
        ensure_admin()
        api_get("/v1/me", headers=USER_HEADERS)
        resp = api_post("/v1/users", {
            "username": f"hacker-{UNIQUE}",
            "password": "hack",
            "is_admin": True,
        }, headers=USER_HEADERS)
        assert resp.status_code == 403

    def test_get_user_by_id(self):
        ensure_admin()
        create_resp = api_post("/v1/users", {
            "username": f"getuser-{UNIQUE}",
            "password": "pass",
            "is_admin": False,
        }, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_get(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["username"] == f"getuser-{UNIQUE}"

    def test_get_nonexistent_user(self):
        ensure_admin()
        resp = api_get("/v1/users/999999", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_update_user(self):
        ensure_admin()
        create_resp = api_post("/v1/users", {
            "username": f"upduser-{UNIQUE}",
            "password": "pass",
            "is_admin": False,
        }, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_put(f"/v1/users/{user_id}", {
            "username": f"upduser-new-{UNIQUE}",
            "is_admin": True,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["username"] == f"upduser-new-{UNIQUE}"
        assert updated["is_admin"] is True

    def test_delete_user(self):
        ensure_admin()
        create_resp = api_post("/v1/users", {
            "username": f"deluser-{UNIQUE}",
            "password": "pass",
            "is_admin": False,
        }, headers=ADMIN_HEADERS)
        user_id = create_resp.json()["id"]

        resp = api_delete(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 204

        # Should be gone
        get_resp = api_get(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_cannot_delete_self(self):
        """Admin cannot delete their own account."""
        ensure_admin()
        me = api_get("/v1/me", headers=ADMIN_HEADERS).json()
        my_id = me["id"]

        resp = api_delete(f"/v1/users/{my_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_mark_user_entries_as_read(self):
        """PUT /v1/users/{id}/mark-all-as-read marks all user's entries as read."""
        ensure_admin()
        me = api_get("/v1/me", headers=ADMIN_HEADERS).json()
        my_id = me["id"]

        # Create some content
        cat_resp = api_post("/v1/categories", {"title": f"UserMarkCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/usermark-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "User Mark Feed"
        })
        feed_id = feed_resp.json()["feed_id"]
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "User Mark Entry",
            "url": f"https://example.com/usermark-{UNIQUE}-entry",
        })

        resp = api_put(f"/v1/users/{my_id}/mark-all-as-read")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 11: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_feed_isolation(self):
        """User A's feeds are not visible to User B."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"IsoFeedCat-{UNIQUE}"}, headers=ADMIN_HEADERS)
        cat_id = cat_resp.json()["id"]

        feed_url = f"https://example.com/iso-{UNIQUE}.xml"
        api_post("/v1/feeds", {
            "feed_url": feed_url,
            "category_id": cat_id,
            "title": "Isolated Feed"
        }, headers=ADMIN_HEADERS)

        # User2 should not see it
        resp = api_get("/v1/feeds", headers=USER2_HEADERS)
        assert resp.status_code == 200
        urls = [f["feed_url"] for f in resp.json()]
        assert feed_url not in urls

    def test_category_isolation(self):
        """User A's categories are not visible to User B."""
        ensure_admin()
        title = f"IsoCat-{UNIQUE}"
        api_post("/v1/categories", {"title": title}, headers=ADMIN_HEADERS)

        resp = api_get("/v1/categories", headers=USER2_HEADERS)
        assert resp.status_code == 200
        titles = [c["title"] for c in resp.json()]
        assert title not in titles

    def test_entry_isolation(self):
        """User A's entries are not visible to User B."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"IsoEntryCat-{UNIQUE}"}, headers=ADMIN_HEADERS)
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/isoentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Iso Entry Feed"
        }, headers=ADMIN_HEADERS)
        feed_id = feed_resp.json()["feed_id"]

        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": f"Secret-{UNIQUE}",
            "url": f"https://example.com/secret-{UNIQUE}",
        }, headers=ADMIN_HEADERS)

        # User2 should not see it
        resp = api_get("/v1/entries", headers=USER2_HEADERS)
        assert resp.status_code == 200
        titles = [e["title"] for e in resp.json()["entries"]]
        assert f"Secret-{UNIQUE}" not in titles

    def test_cannot_access_other_users_feed(self):
        """User B cannot GET User A's feed (returns 404)."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"OtherFeedCat-{UNIQUE}"}, headers=ADMIN_HEADERS)
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/otherfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Other Feed"
        }, headers=ADMIN_HEADERS)
        feed_id = feed_resp.json()["feed_id"]

        resp = api_get(f"/v1/feeds/{feed_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_cannot_access_other_users_entry(self):
        """User B cannot GET User A's entry (returns 404)."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"OtherEntryCat-{UNIQUE}"}, headers=ADMIN_HEADERS)
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/otherentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Other Entry Feed"
        }, headers=ADMIN_HEADERS)
        feed_id = feed_resp.json()["feed_id"]

        entry_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Other Entry",
            "url": f"https://example.com/otherentry-{UNIQUE}",
        }, headers=ADMIN_HEADERS)
        entry_id = entry_resp.json()["id"]

        resp = api_get(f"/v1/entries/{entry_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_feed_deletes_entries(self):
        """Deleting a feed should delete all its entries."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"CascFeedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/cascfeed-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Cascade Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        entry_ids = []
        for i in range(3):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Cascade Entry {i}",
                "url": f"https://example.com/cascentry-{UNIQUE}-{i}",
            })
            entry_ids.append(r.json()["id"])

        # Delete the feed
        resp = api_delete(f"/v1/feeds/{feed_id}")
        assert resp.status_code == 204

        # Entries should be gone
        for eid in entry_ids:
            r = api_get(f"/v1/entries/{eid}")
            assert r.status_code == 404

    def test_delete_user_cascade(self):
        """Deleting a user should delete all their data."""
        ensure_admin()
        # Use a unique key that auto-creates a user with data
        username = f"cascade-del-{UNIQUE}"
        user_headers = {"X-Auth-Token": username, "Content-Type": "application/json"}

        # Create category, feed as that user (auto-creates user)
        cat_resp = api_post("/v1/categories", {"title": "UserCat"}, headers=user_headers)
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": "https://example.com/userdata.xml",
            "category_id": cat_id,
            "title": "User Feed"
        }, headers=user_headers)
        feed_id = feed_resp.json()["feed_id"]

        # Get the user ID
        me_resp = api_get("/v1/me", headers=user_headers)
        user_id = me_resp.json()["id"]

        # Delete the user (as admin)
        resp = api_delete(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert resp.status_code == 204

        # User should be gone
        get_resp = api_get(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: OPML Import/Export
# ════════════════════════════════════════════════════════════════════


class TestOPML:

    def test_export_opml(self):
        """Export should return valid OPML XML."""
        ensure_admin()
        # Create a category and feed first
        cat_resp = api_post("/v1/categories", {"title": f"OPMLCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/opml-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "OPML Feed"
        })

        resp = api_get("/v1/export")
        assert resp.status_code == 200
        content = resp.text
        assert "opml" in content.lower()
        assert f"https://example.com/opml-{UNIQUE}.xml" in content

    def test_import_opml(self):
        """Import should create categories and feeds from OPML XML."""
        ensure_admin()
        opml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Subscriptions</title></head>
  <body>
    <outline text="ImportCat-{UNIQUE}" title="ImportCat-{UNIQUE}">
      <outline type="rss" text="Import Feed" title="Import Feed"
               xmlUrl="https://example.com/import-{UNIQUE}.xml"
               htmlUrl="https://example.com/import"/>
    </outline>
  </body>
</opml>"""

        headers = dict(ADMIN_HEADERS)
        headers["Content-Type"] = "application/xml"
        resp = requests.post(f"{BASE_URL}/v1/import", data=opml_xml, headers=headers, timeout=30)
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data

        # Verify category was created
        cats_resp = api_get("/v1/categories")
        titles = [c["title"] for c in cats_resp.json()]
        assert f"ImportCat-{UNIQUE}" in titles

        # Verify feed was created
        feeds_resp = api_get("/v1/feeds")
        urls = [f["feed_url"] for f in feeds_resp.json()]
        assert f"https://example.com/import-{UNIQUE}.xml" in urls

    def test_import_opml_reuses_existing_category(self):
        """Import should reuse existing category by title."""
        ensure_admin()
        # Create category first
        cat_title = f"ReuseCat-{UNIQUE}"
        api_post("/v1/categories", {"title": cat_title})

        opml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Subs</title></head>
  <body>
    <outline text="{cat_title}" title="{cat_title}">
      <outline type="rss" text="Reuse Feed" title="Reuse Feed"
               xmlUrl="https://example.com/reuse-{UNIQUE}.xml"
               htmlUrl="https://example.com/reuse"/>
    </outline>
  </body>
</opml>"""

        headers = dict(ADMIN_HEADERS)
        headers["Content-Type"] = "application/xml"
        resp = requests.post(f"{BASE_URL}/v1/import", data=opml_xml, headers=headers, timeout=30)
        assert resp.status_code == 201

        # Should not create duplicate category
        cats_resp = api_get("/v1/categories")
        matching = [c for c in cats_resp.json() if c["title"] == cat_title]
        assert len(matching) == 1

    def test_import_opml_skips_duplicate_feed(self):
        """Import should skip feeds with duplicate URLs."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DupImportCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        feed_url = f"https://example.com/dupimport-{UNIQUE}.xml"
        api_post("/v1/feeds", {
            "feed_url": feed_url,
            "category_id": cat_id,
            "title": "Existing Feed"
        })

        opml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Subs</title></head>
  <body>
    <outline text="DupImportCat-{UNIQUE}" title="DupImportCat-{UNIQUE}">
      <outline type="rss" text="Dup Feed" title="Dup Feed"
               xmlUrl="{feed_url}" htmlUrl="https://example.com/dup"/>
    </outline>
  </body>
</opml>"""

        headers = dict(ADMIN_HEADERS)
        headers["Content-Type"] = "application/xml"
        resp = requests.post(f"{BASE_URL}/v1/import", data=opml_xml, headers=headers, timeout=30)
        assert resp.status_code == 201

        # Should not create duplicate feed
        feeds_resp = api_get("/v1/feeds")
        matching = [f for f in feeds_resp.json() if f["feed_url"] == feed_url]
        assert len(matching) == 1


# ════════════════════════════════════════════════════════════════════
# PART 14: Discover
# ════════════════════════════════════════════════════════════════════


class TestDiscover:

    def test_discover_feeds(self):
        ensure_admin()
        resp = api_post("/v1/discover", {"url": "https://example.com/blog"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["url"] == "https://example.com/blog"
        assert "title" in data[0]

    def test_discover_missing_url(self):
        ensure_admin()
        resp = api_post("/v1/discover", {})
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 15: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_entry_default_status_unread(self):
        """New entries should have status 'unread'."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DefStatCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/defstat-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Default Status Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        entry_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Default Status",
            "url": f"https://example.com/defstat-{UNIQUE}",
        })
        assert entry_resp.status_code == 201
        assert entry_resp.json()["status"] == "unread"

    def test_entry_default_starred_false(self):
        """New entries should not be starred."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DefStarCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/defstar-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Default Star Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        entry_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Default Star",
            "url": f"https://example.com/defstar-{UNIQUE}",
        })
        assert entry_resp.json()["starred"] is False

    def test_feed_includes_category_object(self):
        """Feed response should include nested category object."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"NestedCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]

        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/nested-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Nested Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        resp = api_get(f"/v1/feeds/{feed_id}")
        feed = resp.json()
        assert "category" in feed
        assert feed["category"]["id"] == cat_id
        assert feed["category"]["title"] == f"NestedCat-{UNIQUE}"

    def test_empty_feeds_list(self):
        """New user should have empty feeds list."""
        ensure_admin()
        key = f"empty-feeds-{uuid.uuid4().hex[:8]}"
        headers = {"X-Auth-Token": key, "Content-Type": "application/json"}
        resp = api_get("/v1/feeds", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_entries_list(self):
        """New user should have empty entries list."""
        ensure_admin()
        key = f"empty-entries-{uuid.uuid4().hex[:8]}"
        headers = {"X-Auth-Token": key, "Content-Type": "application/json"}
        resp = api_get("/v1/entries", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["entries"] == []

    def test_entry_duplicate_url_in_feed(self):
        """Creating entry with duplicate URL in same feed should return existing entry."""
        ensure_admin()
        cat_resp = api_post("/v1/categories", {"title": f"DupEntryCat-{UNIQUE}"})
        cat_id = cat_resp.json()["id"]
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/dupentry-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Dup Entry Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        url = f"https://example.com/dupentry-{UNIQUE}-same"
        resp1 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "First",
            "url": url,
        })
        assert resp1.status_code == 201

        resp2 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Second",
            "url": url,
        })
        # Should return 200 (existing) not error
        assert resp2.status_code in (200, 201)

        # Should only have one entry with that URL
        entries_resp = api_get(f"/v1/feeds/{feed_id}/entries")
        matching = [e for e in entries_resp.json()["entries"] if e["url"] == url]
        assert len(matching) == 1

    def test_update_feed_category(self):
        """Should be able to move a feed to a different category."""
        ensure_admin()
        cat1_resp = api_post("/v1/categories", {"title": f"MoveCat1-{UNIQUE}"})
        cat1_id = cat1_resp.json()["id"]
        cat2_resp = api_post("/v1/categories", {"title": f"MoveCat2-{UNIQUE}"})
        cat2_id = cat2_resp.json()["id"]

        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/move-{UNIQUE}.xml",
            "category_id": cat1_id,
            "title": "Movable Feed"
        })
        feed_id = feed_resp.json()["feed_id"]

        # Move to cat2
        resp = api_put(f"/v1/feeds/{feed_id}", {"category_id": cat2_id})
        assert resp.status_code == 200
        assert resp.json()["category"]["id"] == cat2_id
