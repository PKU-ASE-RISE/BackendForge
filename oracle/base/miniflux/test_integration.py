"""
BackendForge - L2 Integration Tests for Miniflux Task
Adversarial tests targeting common LLM implementation bugs.

Each test: 3-5 steps, 8-12 assertions, covers 1-2 bug patterns.
"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

ADMIN_KEY = "admin-user-first"
UNIQUE = uuid.uuid4().hex[:8]

ADMIN_HEADERS = {
    "X-Auth-Token": ADMIN_KEY,
    "Content-Type": "application/json",
}


def _user_headers(key=None):
    if key is None:
        key = f"l2-user-{uuid.uuid4().hex[:8]}"
    return {"X-Auth-Token": key, "Content-Type": "application/json"}


def ensure_admin():
    requests.get(f"{BASE_URL}/v1/me", headers=ADMIN_HEADERS, timeout=30)


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


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or ADMIN_HEADERS, timeout=30)


# ════════════════════════════════════════════════════════════════════
# Pattern 1+2: Field names + Nested data in Feed response
# ════════════════════════════════════════════════════════════════════


class TestFeedResponseStructure:
    """Verify feed responses have correct field names and nested category."""

    def test_feed_creation_returns_feed_id_field(self):
        """Pattern 1+4: POST /v1/feeds returns {feed_id: int} with 201 status."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"FeedStruct1-{UNIQUE}"}).json()
        cat_id = cat["id"]

        resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/struct1-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Structure Test Feed"
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
        data = resp.json()
        # Must have feed_id field (not "id", not "feedId")
        assert "feed_id" in data, f"Response keys: {list(data.keys())}"
        assert isinstance(data["feed_id"], int)
        # Should NOT have extra unexpected fields in creation response
        # The creation response is just {feed_id: int}

    def test_get_feed_includes_all_required_fields(self):
        """Pattern 1+2: GET feed has correct field names and nested category object."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"FeedStruct2-{UNIQUE}"}).json()
        cat_id = cat["id"]
        cat_title = cat["title"]

        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/struct2-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Full Fields Feed",
            "crawler": True,
            "user_agent": "TestBot/1.0"
        })
        feed_id = feed_resp.json()["feed_id"]

        resp = api_get(f"/v1/feeds/{feed_id}")
        assert resp.status_code == 200
        feed = resp.json()

        # Required fields per OpenAPI schema
        assert feed["id"] == feed_id
        assert "user_id" in feed
        assert isinstance(feed["user_id"], int)
        assert feed["feed_url"] == f"https://example.com/struct2-{UNIQUE}.xml"
        assert feed["title"] == "Full Fields Feed"

        # Nested category object (Pattern 2 - relationships)
        assert "category" in feed, "Feed must include nested 'category' object"
        assert isinstance(feed["category"], dict)
        assert feed["category"]["id"] == cat_id
        assert feed["category"]["title"] == cat_title
        assert "user_id" in feed["category"]

    def test_list_feeds_each_has_nested_category(self):
        """Pattern 2: Each feed in list must include full category object."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"FeedStruct3-{UNIQUE}"}).json()
        cat_id = cat["id"]

        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/struct3a-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Feed A"
        })
        api_post("/v1/feeds", {
            "feed_url": f"https://example.com/struct3b-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Feed B"
        })

        resp = api_get("/v1/feeds")
        assert resp.status_code == 200
        feeds = resp.json()
        assert isinstance(feeds, list)
        assert len(feeds) >= 2

        # Every feed must have a nested category
        for feed in feeds:
            assert "category" in feed, f"Feed {feed.get('id')} missing 'category'"
            assert "id" in feed["category"]
            assert "title" in feed["category"]


# ════════════════════════════════════════════════════════════════════
# Pattern 1+2: Entry response structure
# ════════════════════════════════════════════════════════════════════


class TestEntryResponseStructure:
    """Verify entry responses have correct field names and nested feed."""

    def test_create_entry_response_has_all_required_fields(self):
        """Pattern 1: Entry creation response has exact field names from schema."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"EntryStruct1-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entrystruct1-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Entry Struct Feed"
        }).json()
        feed_id = feed["feed_id"]

        resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "My Article",
            "url": f"https://example.com/article-struct1-{UNIQUE}",
            "content": "<p>Body text</p>",
            "author": "Jane Doe"
        })
        assert resp.status_code == 201
        entry = resp.json()

        # Required fields per OpenAPI
        assert "id" in entry
        assert isinstance(entry["id"], int)
        assert "user_id" in entry
        assert isinstance(entry["user_id"], int)
        assert "feed_id" in entry
        assert entry["feed_id"] == feed_id
        assert entry["status"] == "unread"
        assert entry["title"] == "My Article"
        assert entry["url"] == f"https://example.com/article-struct1-{UNIQUE}"
        assert "published_at" in entry
        assert entry["starred"] is False
        assert entry["content"] == "<p>Body text</p>"
        assert entry["author"] == "Jane Doe"

    def test_get_entry_includes_nested_feed_object(self):
        """Pattern 2: GET /v1/entries/{id} should include nested feed object."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"EntryStruct2-{UNIQUE}"}).json()
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entrystruct2-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Nested Feed Check"
        })
        feed_id = feed_resp.json()["feed_id"]

        entry_resp = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Nested Check Article",
            "url": f"https://example.com/nestedcheck-{UNIQUE}",
        })
        entry_id = entry_resp.json()["id"]

        resp = api_get(f"/v1/entries/{entry_id}")
        assert resp.status_code == 200
        entry = resp.json()

        # Entry should include nested feed with its own nested category
        assert "feed" in entry, "Entry must include nested 'feed' object"
        assert isinstance(entry["feed"], dict)
        assert entry["feed"]["id"] == feed_id
        assert entry["feed"]["title"] == "Nested Feed Check"
        assert "category" in entry["feed"], "Nested feed must include category"

    def test_entry_list_result_set_structure(self):
        """Pattern 1: GET /v1/entries returns {total: int, entries: [...]}."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"EntryStruct3-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entrystruct3-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "ResultSet Feed"
        }).json()
        feed_id = feed["feed_id"]

        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "RS Entry 1",
            "url": f"https://example.com/rs1-{UNIQUE}",
        })

        resp = api_get("/v1/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data, f"Missing 'total' key. Keys: {list(data.keys())}"
        assert "entries" in data, f"Missing 'entries' key. Keys: {list(data.keys())}"
        assert isinstance(data["total"], int)
        assert isinstance(data["entries"], list)
        assert data["total"] >= 1


# ════════════════════════════════════════════════════════════════════
# Pattern 3: Filtering actually restricts results
# ════════════════════════════════════════════════════════════════════


class TestFilteringActuallyWorks:
    """Verify that filtering parameters actually restrict returned results."""

    def _setup_feed_with_entries(self, suffix):
        """Helper: create category + feed + varied entries."""
        cat = api_post("/v1/categories", {"title": f"Filter-{suffix}-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/filter-{suffix}-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": f"Filter Feed {suffix}"
        }).json()
        feed_id = feed["feed_id"]
        return cat["id"], feed_id

    def test_status_filter_excludes_non_matching(self):
        """Pattern 3: Status filter must EXCLUDE entries that don't match."""
        ensure_admin()
        cat_id, feed_id = self._setup_feed_with_entries("status")

        ids = []
        for i in range(4):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Status Entry {i}",
                "url": f"https://example.com/status-{UNIQUE}-{i}",
            })
            ids.append(r.json()["id"])

        # Mark first 2 as read
        api_put("/v1/entries", {"entry_ids": ids[:2], "status": "read"})

        # Filter for unread only
        resp = api_get("/v1/entries", params={"status": "unread", "feed_id": feed_id})
        data = resp.json()
        assert data["total"] == 2, f"Expected 2 unread, got {data['total']}"
        for e in data["entries"]:
            assert e["status"] == "unread", f"Got status={e['status']} when filtering for unread"

        # Filter for read only
        resp2 = api_get("/v1/entries", params={"status": "read", "feed_id": feed_id})
        data2 = resp2.json()
        assert data2["total"] == 2, f"Expected 2 read, got {data2['total']}"
        for e in data2["entries"]:
            assert e["status"] == "read"

    def test_starred_filter_only_returns_starred(self):
        """Pattern 3: starred=true must only return starred entries."""
        ensure_admin()
        cat_id, feed_id = self._setup_feed_with_entries("starred")

        ids = []
        for i in range(3):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Star Entry {i}",
                "url": f"https://example.com/starfilter-{UNIQUE}-{i}",
            })
            ids.append(r.json()["id"])

        # Star only the first one
        api_put(f"/v1/entries/{ids[0]}/bookmark")

        # Filter starred=true
        resp = api_get("/v1/entries", params={"starred": "true", "feed_id": feed_id})
        data = resp.json()
        assert data["total"] == 1, f"Expected 1 starred, got {data['total']}"
        assert data["entries"][0]["starred"] is True
        assert data["entries"][0]["id"] == ids[0]

    def test_limit_actually_limits_results(self):
        """Pattern 3: limit=2 must return at most 2 entries."""
        ensure_admin()
        cat_id, feed_id = self._setup_feed_with_entries("limit")

        for i in range(5):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Limit Entry {i}",
                "url": f"https://example.com/limit-{UNIQUE}-{i}",
            })

        resp = api_get("/v1/entries", params={"limit": 2, "feed_id": feed_id})
        data = resp.json()
        assert len(data["entries"]) == 2, f"Expected 2 entries, got {len(data['entries'])}"
        # But total should reflect ALL matching, not just page
        assert data["total"] == 5

    def test_offset_skips_entries(self):
        """Pattern 3: offset actually skips entries for pagination."""
        ensure_admin()
        cat_id, feed_id = self._setup_feed_with_entries("offset")

        for i in range(5):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Offset Entry {i}",
                "url": f"https://example.com/offset-{UNIQUE}-{i}",
            })

        # Get page 1 and page 2
        page1 = api_get("/v1/entries", params={
            "limit": 2, "offset": 0, "feed_id": feed_id,
            "order": "id", "direction": "asc"
        }).json()
        page2 = api_get("/v1/entries", params={
            "limit": 2, "offset": 2, "feed_id": feed_id,
            "order": "id", "direction": "asc"
        }).json()

        ids1 = {e["id"] for e in page1["entries"]}
        ids2 = {e["id"] for e in page2["entries"]}
        assert len(ids1) == 2
        assert len(ids2) == 2
        assert ids1.isdisjoint(ids2), "Pages must not overlap"

    def test_order_direction_actually_sorts(self):
        """Pattern 3: order=id + direction=asc/desc actually changes order."""
        ensure_admin()
        cat_id, feed_id = self._setup_feed_with_entries("order")

        for i in range(4):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Order Entry {i}",
                "url": f"https://example.com/order-{UNIQUE}-{i}",
            })

        # Ascending
        asc_resp = api_get("/v1/entries", params={
            "order": "id", "direction": "asc", "feed_id": feed_id
        }).json()
        asc_ids = [e["id"] for e in asc_resp["entries"]]
        assert asc_ids == sorted(asc_ids), "Ascending order not working"

        # Descending
        desc_resp = api_get("/v1/entries", params={
            "order": "id", "direction": "desc", "feed_id": feed_id
        }).json()
        desc_ids = [e["id"] for e in desc_resp["entries"]]
        assert desc_ids == sorted(desc_ids, reverse=True), "Descending order not working"

    def test_feed_id_filter_restricts_to_feed(self):
        """Pattern 3: feed_id filter must only return entries from that feed."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"FeedFilter-{UNIQUE}"}).json()

        feed1 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/feedfilter1-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Feed Filter 1"
        }).json()["feed_id"]

        feed2 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/feedfilter2-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Feed Filter 2"
        }).json()["feed_id"]

        api_post(f"/v1/feeds/{feed1}/entries", {
            "title": "Feed1 Entry",
            "url": f"https://example.com/ff1-{UNIQUE}",
        })
        api_post(f"/v1/feeds/{feed2}/entries", {
            "title": "Feed2 Entry",
            "url": f"https://example.com/ff2-{UNIQUE}",
        })

        # Filter by feed1
        resp = api_get("/v1/entries", params={"feed_id": feed1})
        data = resp.json()
        for e in data["entries"]:
            assert e["feed_id"] == feed1, f"Entry from wrong feed: {e['feed_id']}"

    def test_category_id_filter_restricts_to_category(self):
        """Pattern 3: category_id filter restricts entries to that category."""
        ensure_admin()
        cat1 = api_post("/v1/categories", {"title": f"CatFilter1-{UNIQUE}"}).json()
        cat2 = api_post("/v1/categories", {"title": f"CatFilter2-{UNIQUE}"}).json()

        feed1 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/catfilter1-{UNIQUE}.xml",
            "category_id": cat1["id"],
            "title": "CatFilter Feed1"
        }).json()["feed_id"]

        feed2 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/catfilter2-{UNIQUE}.xml",
            "category_id": cat2["id"],
            "title": "CatFilter Feed2"
        }).json()["feed_id"]

        api_post(f"/v1/feeds/{feed1}/entries", {
            "title": "Cat1 Entry",
            "url": f"https://example.com/cf1-{UNIQUE}",
        })
        api_post(f"/v1/feeds/{feed2}/entries", {
            "title": "Cat2 Entry",
            "url": f"https://example.com/cf2-{UNIQUE}",
        })

        # Filter by category1
        resp = api_get("/v1/entries", params={"category_id": cat1["id"]})
        data = resp.json()
        assert data["total"] >= 1
        # All returned entries should be from feed1 (which is in cat1)
        for e in data["entries"]:
            assert e["feed_id"] == feed1


# ════════════════════════════════════════════════════════════════════
# Pattern 4: Status codes must be precise
# ════════════════════════════════════════════════════════════════════


class TestPreciseStatusCodes:
    """Verify exact status codes (201 vs 200 vs 204)."""

    def test_create_category_returns_201(self):
        """Pattern 4: Category creation must return 201, not 200."""
        ensure_admin()
        resp = api_post("/v1/categories", {"title": f"Status201-{UNIQUE}"})
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"

    def test_create_feed_returns_201(self):
        """Pattern 4: Feed creation must return 201, not 200."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"FeedStatus-{UNIQUE}"}).json()
        resp = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/status201feed-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Status 201 Feed"
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"

    def test_create_entry_returns_201(self):
        """Pattern 4: Entry creation must return 201, not 200."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"EntryStatus-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entrystatus-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Entry Status Feed"
        }).json()

        resp = api_post(f"/v1/feeds/{feed['feed_id']}/entries", {
            "title": "Status Entry",
            "url": f"https://example.com/entrystatus-{UNIQUE}",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"

    def test_delete_operations_return_204(self):
        """Pattern 4: DELETE must return 204, not 200."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Del204-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/del204-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Del 204 Feed"
        }).json()

        resp = api_delete(f"/v1/feeds/{feed['feed_id']}")
        assert resp.status_code == 204, f"Expected 204 for feed delete, got {resp.status_code}"

        resp2 = api_delete(f"/v1/categories/{cat['id']}")
        assert resp2.status_code == 204, f"Expected 204 for category delete, got {resp2.status_code}"

    def test_mark_as_read_returns_204(self):
        """Pattern 4: Mark-all-as-read must return 204."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Mark204-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/mark204-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Mark 204 Feed"
        }).json()

        resp = api_put(f"/v1/feeds/{feed['feed_id']}/mark-all-as-read")
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"

    def test_bulk_status_update_returns_204(self):
        """Pattern 4: PUT /v1/entries (batch update) returns 204, not 200."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Bulk204-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/bulk204-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Bulk 204 Feed"
        }).json()
        entry = api_post(f"/v1/feeds/{feed['feed_id']}/entries", {
            "title": "Bulk Entry",
            "url": f"https://example.com/bulk204-{UNIQUE}",
        }).json()

        resp = api_put("/v1/entries", {
            "entry_ids": [entry["id"]],
            "status": "read"
        })
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"

    def test_bookmark_toggle_returns_204(self):
        """Pattern 4: PUT /v1/entries/{id}/bookmark returns 204."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Bkmk204-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/bkmk204-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Bkmk 204 Feed"
        }).json()
        entry = api_post(f"/v1/feeds/{feed['feed_id']}/entries", {
            "title": "Bookmark Entry",
            "url": f"https://example.com/bkmk204-{UNIQUE}",
        }).json()

        resp = api_put(f"/v1/entries/{entry['id']}/bookmark")
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# Pattern 5: Computed values verified with different inputs
# ════════════════════════════════════════════════════════════════════


class TestComputedValues:
    """Verify counters and counts are actually computed, not hardcoded."""

    def test_feed_counters_reflect_actual_state(self):
        """Pattern 5: Feed counters must match actual read/unread counts."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Counter-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/counter-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Counter Feed"
        }).json()
        feed_id = feed["feed_id"]

        # Create 5 entries (all unread)
        ids = []
        for i in range(5):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Counter Entry {i}",
                "url": f"https://example.com/counter-{UNIQUE}-{i}",
            })
            ids.append(r.json()["id"])

        # Check counters: 0 read, 5 unread
        counters = api_get("/v1/feeds/counters").json()
        fid_str = str(feed_id)
        assert fid_str in counters["unreads"]
        assert counters["unreads"][fid_str] == 5
        assert counters["reads"].get(fid_str, 0) == 0

        # Mark 3 as read
        api_put("/v1/entries", {"entry_ids": ids[:3], "status": "read"})

        # Re-check counters: 3 read, 2 unread
        counters2 = api_get("/v1/feeds/counters").json()
        assert counters2["reads"][fid_str] == 3
        assert counters2["unreads"][fid_str] == 2

    def test_category_counts_reflect_actual_state(self):
        """Pattern 5: Category counts (total_unread, total_read) must be computed."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"CatCount-{UNIQUE}"}).json()
        cat_id = cat["id"]
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/catcount-{UNIQUE}.xml",
            "category_id": cat_id,
            "title": "Cat Count Feed"
        }).json()
        feed_id = feed["feed_id"]

        ids = []
        for i in range(4):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"CatCount Entry {i}",
                "url": f"https://example.com/catcount-{UNIQUE}-{i}",
            })
            ids.append(r.json()["id"])

        # Mark 1 as read
        api_put("/v1/entries", {"entry_ids": [ids[0]], "status": "read"})

        # Check counts
        resp = api_get("/v1/categories", params={"counts": "true"})
        cats = resp.json()
        our_cat = next(c for c in cats if c["id"] == cat_id)
        assert "total_unread" in our_cat
        assert our_cat["total_unread"] == 3
        assert "total_read" in our_cat
        assert our_cat["total_read"] == 1

    def test_entry_total_in_result_set_is_full_count(self):
        """Pattern 5: 'total' must be count of ALL matching, not just page size."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Total-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/total-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Total Feed"
        }).json()
        feed_id = feed["feed_id"]

        for i in range(6):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Total Entry {i}",
                "url": f"https://example.com/total-{UNIQUE}-{i}",
            })

        # Request with limit=2, total should still be 6
        resp = api_get("/v1/entries", params={"limit": 2, "feed_id": feed_id})
        data = resp.json()
        assert len(data["entries"]) == 2
        assert data["total"] == 6, f"Total should be 6 (all matching), got {data['total']}"


# ════════════════════════════════════════════════════════════════════
# Pattern 5+7: Side effects verified
# ════════════════════════════════════════════════════════════════════


class TestSideEffects:
    """Verify operations have correct side effects."""

    def test_mark_feed_as_read_changes_entry_status(self):
        """Pattern 7: mark-all-as-read must actually change each entry's status."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"SideEff1-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/sideeff1-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Side Effect Feed"
        }).json()
        feed_id = feed["feed_id"]

        ids = []
        for i in range(3):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"SideEff Entry {i}",
                "url": f"https://example.com/sideeff1-{UNIQUE}-{i}",
            })
            ids.append(r.json()["id"])

        # Verify all unread
        for eid in ids:
            e = api_get(f"/v1/entries/{eid}").json()
            assert e["status"] == "unread"

        # Mark all as read
        api_put(f"/v1/feeds/{feed_id}/mark-all-as-read")

        # Verify all now read
        for eid in ids:
            e = api_get(f"/v1/entries/{eid}").json()
            assert e["status"] == "read", f"Entry {eid} still {e['status']} after mark-all-as-read"

    def test_bookmark_toggle_is_idempotent_pair(self):
        """Pattern 5: Toggle twice returns to original state."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"Toggle-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/toggle-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Toggle Feed"
        }).json()
        entry = api_post(f"/v1/feeds/{feed['feed_id']}/entries", {
            "title": "Toggle Entry",
            "url": f"https://example.com/toggle-{UNIQUE}",
        }).json()
        entry_id = entry["id"]

        # Initially not starred
        assert api_get(f"/v1/entries/{entry_id}").json()["starred"] is False

        # Toggle on
        api_put(f"/v1/entries/{entry_id}/bookmark")
        assert api_get(f"/v1/entries/{entry_id}").json()["starred"] is True

        # Toggle off
        api_put(f"/v1/entries/{entry_id}/bookmark")
        assert api_get(f"/v1/entries/{entry_id}").json()["starred"] is False

    def test_mark_as_read_only_affects_unread(self):
        """Pattern 7: mark-all-as-read should not affect 'removed' status entries."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"MarkOnly-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/markonly-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "MarkOnly Feed"
        }).json()
        feed_id = feed["feed_id"]

        e1 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Will Be Removed",
            "url": f"https://example.com/markonly1-{UNIQUE}",
        }).json()
        e2 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Will Stay Unread",
            "url": f"https://example.com/markonly2-{UNIQUE}",
        }).json()

        # Set e1 to removed
        api_put("/v1/entries", {"entry_ids": [e1["id"]], "status": "removed"})

        # Mark all as read
        api_put(f"/v1/feeds/{feed_id}/mark-all-as-read")

        # e1 should remain removed (not changed to read)
        entry1 = api_get(f"/v1/entries/{e1['id']}").json()
        assert entry1["status"] == "removed", "Mark-as-read should not change 'removed' entries"

        # e2 should now be read
        entry2 = api_get(f"/v1/entries/{e2['id']}").json()
        assert entry2["status"] == "read"


# ════════════════════════════════════════════════════════════════════
# Pattern 6: Data isolation between users
# ════════════════════════════════════════════════════════════════════


class TestDataIsolationL2:
    """Verify strict data isolation between users."""

    def test_user_cannot_see_others_entries_via_feed_endpoint(self):
        """Pattern 6: User B cannot access User A's feed entries endpoint."""
        ensure_admin()
        user_b_headers = _user_headers()

        # Admin creates content
        cat = api_post("/v1/categories", {"title": f"Iso-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/iso-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Isolated Feed"
        }).json()
        feed_id = feed["feed_id"]
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Secret Entry",
            "url": f"https://example.com/iso-{UNIQUE}",
        })

        # User B tries to access admin's feed entries
        resp = api_get(f"/v1/feeds/{feed_id}/entries", headers=user_b_headers)
        assert resp.status_code == 404, "Should not be able to access other user's feed"

    def test_counters_isolated_between_users(self):
        """Pattern 6: Feed counters only show own feeds."""
        ensure_admin()
        user_b_headers = _user_headers()

        # Admin creates content
        cat = api_post("/v1/categories", {"title": f"IsoCount-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/isocount-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Iso Counter Feed"
        }).json()
        feed_id = feed["feed_id"]
        api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Iso Entry",
            "url": f"https://example.com/isocount-{UNIQUE}",
        })

        # User B's counters should not include admin's feed
        counters = api_get("/v1/feeds/counters", headers=user_b_headers).json()
        assert str(feed_id) not in counters.get("unreads", {}), \
            "User B should not see admin's feed in counters"


# ════════════════════════════════════════════════════════════════════
# Pattern 8: Uniqueness constraints
# ════════════════════════════════════════════════════════════════════


class TestUniquenessConstraints:
    """Verify uniqueness rules are enforced."""

    def test_duplicate_category_title_returns_409(self):
        """Pattern 8: Same user, duplicate category title → 409."""
        ensure_admin()
        title = f"Unique-{UNIQUE}"
        resp1 = api_post("/v1/categories", {"title": title})
        assert resp1.status_code == 201

        resp2 = api_post("/v1/categories", {"title": title})
        assert resp2.status_code == 409, f"Expected 409 for duplicate category, got {resp2.status_code}"

    def test_duplicate_feed_url_returns_409(self):
        """Pattern 8: Same user, duplicate feed_url → 409."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"DupFeed-{UNIQUE}"}).json()
        url = f"https://example.com/dupfeed-{UNIQUE}.xml"

        resp1 = api_post("/v1/feeds", {"feed_url": url, "category_id": cat["id"], "title": "First"})
        assert resp1.status_code == 201

        resp2 = api_post("/v1/feeds", {"feed_url": url, "category_id": cat["id"], "title": "Second"})
        assert resp2.status_code == 409, f"Expected 409 for duplicate feed URL, got {resp2.status_code}"

    def test_same_category_title_different_users_is_ok(self):
        """Pattern 8: Different users CAN have same category title."""
        ensure_admin()
        user_b_headers = _user_headers()
        title = f"SharedTitle-{UNIQUE}"

        resp1 = api_post("/v1/categories", {"title": title}, headers=ADMIN_HEADERS)
        assert resp1.status_code == 201

        resp2 = api_post("/v1/categories", {"title": title}, headers=user_b_headers)
        assert resp2.status_code == 201, "Different users should be able to use same category title"

    def test_duplicate_entry_url_in_same_feed(self):
        """Pattern 8: Duplicate entry URL in same feed returns existing, not error."""
        ensure_admin()
        cat = api_post("/v1/categories", {"title": f"DupEntry-{UNIQUE}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/dupentry-{UNIQUE}.xml",
            "category_id": cat["id"],
            "title": "Dup Entry Feed"
        }).json()
        feed_id = feed["feed_id"]
        entry_url = f"https://example.com/dupentry-{UNIQUE}"

        resp1 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Original",
            "url": entry_url,
        })
        assert resp1.status_code == 201
        orig_id = resp1.json()["id"]

        resp2 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Duplicate",
            "url": entry_url,
        })
        # Should succeed but return existing entry (not create new)
        assert resp2.status_code in (200, 201)
        assert resp2.json()["id"] == orig_id, "Should return existing entry on duplicate URL"
