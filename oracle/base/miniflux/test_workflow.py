"""
BackendForge - L3 Workflow Tests for Miniflux Task
Complex multi-step workflows covering 3+ entity types with side-effect verification.

Each test: 6-12 steps, 12-20 assertions, covers 2+ bug patterns.
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
        key = f"l3-user-{uuid.uuid4().hex[:8]}"
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
# L3 Workflow 1: Full feed lifecycle with counter verification
# Patterns: 2 (nested data), 5 (computed values), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestFeedLifecycleWorkflow:

    def test_feed_subscribe_read_unsubscribe_lifecycle(self):
        """
        Full lifecycle: create category → subscribe feed → add entries →
        read some → verify counters → unsubscribe → verify cascade.
        Patterns: 2+5+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Create category
        cat_resp = api_post("/v1/categories", {"title": f"Lifecycle-{suffix}"})
        assert cat_resp.status_code == 201
        cat = cat_resp.json()
        assert "id" in cat
        cat_id = cat["id"]

        # Step 2: Subscribe to feed
        feed_resp = api_post("/v1/feeds", {
            "feed_url": f"https://blog.example.com/feed-{suffix}.xml",
            "category_id": cat_id,
            "title": "Tech Blog"
        })
        assert feed_resp.status_code == 201
        assert "feed_id" in feed_resp.json()
        feed_id = feed_resp.json()["feed_id"]

        # Step 3: Verify feed has nested category
        feed = api_get(f"/v1/feeds/{feed_id}").json()
        assert feed["category"]["id"] == cat_id
        assert feed["category"]["title"] == f"Lifecycle-{suffix}"

        # Step 4: Add multiple entries
        entry_ids = []
        for i in range(5):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Article {i}: Tech Topic",
                "url": f"https://blog.example.com/post-{suffix}-{i}",
                "content": f"<p>Content for article {i}</p>",
                "author": "Blogger"
            })
            assert r.status_code == 201
            entry_ids.append(r.json()["id"])

        # Step 5: Verify counters show 5 unread
        counters = api_get("/v1/feeds/counters").json()
        assert "reads" in counters
        assert "unreads" in counters
        fid_str = str(feed_id)
        assert counters["unreads"][fid_str] == 5
        assert counters["reads"].get(fid_str, 0) == 0

        # Step 6: Read 3 entries
        api_put("/v1/entries", {"entry_ids": entry_ids[:3], "status": "read"})

        # Step 7: Verify counters updated
        counters2 = api_get("/v1/feeds/counters").json()
        assert counters2["reads"][fid_str] == 3
        assert counters2["unreads"][fid_str] == 2

        # Step 8: Delete feed (unsubscribe)
        del_resp = api_delete(f"/v1/feeds/{feed_id}")
        assert del_resp.status_code == 204

        # Step 9: Verify cascade - all entries gone
        for eid in entry_ids:
            r = api_get(f"/v1/entries/{eid}")
            assert r.status_code == 404, f"Entry {eid} should be deleted with feed"

        # Step 10: Verify feed gone from counters
        counters3 = api_get("/v1/feeds/counters").json()
        assert fid_str not in counters3.get("unreads", {}), \
            "Deleted feed should not appear in counters"

        # Step 11: Category still exists (feed deletion doesn't cascade to category)
        cat_check = api_get("/v1/categories")
        cat_ids = [c["id"] for c in cat_check.json()]
        assert cat_id in cat_ids

    def test_multi_feed_category_with_mark_all_read(self):
        """
        Multiple feeds in one category → mark category as read → verify all affected.
        Patterns: 5+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Create category with 2 feeds
        cat = api_post("/v1/categories", {"title": f"MultiFeed-{suffix}"}).json()
        cat_id = cat["id"]

        feed1 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/mf1-{suffix}.xml",
            "category_id": cat_id, "title": "Feed One"
        }).json()["feed_id"]

        feed2 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/mf2-{suffix}.xml",
            "category_id": cat_id, "title": "Feed Two"
        }).json()["feed_id"]

        # Step 2: Add entries to both feeds
        for i in range(3):
            api_post(f"/v1/feeds/{feed1}/entries", {
                "title": f"Feed1 Art {i}",
                "url": f"https://example.com/mf1-{suffix}-{i}",
            })
        for i in range(2):
            api_post(f"/v1/feeds/{feed2}/entries", {
                "title": f"Feed2 Art {i}",
                "url": f"https://example.com/mf2-{suffix}-{i}",
            })

        # Step 3: Verify total unread in category
        cat_entries = api_get(f"/v1/categories/{cat_id}/entries",
                             params={"status": "unread"}).json()
        assert cat_entries["total"] == 5

        # Step 4: Mark entire category as read
        mark_resp = api_put(f"/v1/categories/{cat_id}/mark-all-as-read")
        assert mark_resp.status_code == 204

        # Step 5: Verify ALL entries in both feeds are now read
        cat_entries_after = api_get(f"/v1/categories/{cat_id}/entries",
                                   params={"status": "unread"}).json()
        assert cat_entries_after["total"] == 0

        # Step 6: Verify counters updated for both feeds
        counters = api_get("/v1/feeds/counters").json()
        assert counters["unreads"].get(str(feed1), 0) == 0
        assert counters["unreads"].get(str(feed2), 0) == 0
        assert counters["reads"][str(feed1)] == 3
        assert counters["reads"][str(feed2)] == 2


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 2: User data isolation end-to-end
# Patterns: 6 (isolation), 4 (status codes), 1 (field names)
# ════════════════════════════════════════════════════════════════════


class TestMultiUserIsolationWorkflow:

    def test_complete_data_isolation_between_two_users(self):
        """
        Two users create independent data → verify complete isolation.
        Patterns: 1+6
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        user_a_headers = _user_headers(f"user-a-{suffix}")
        user_b_headers = _user_headers(f"user-b-{suffix}")

        # Step 1: User A creates category + feed + entries
        cat_a = api_post("/v1/categories", {"title": "News"}, headers=user_a_headers).json()
        feed_a = api_post("/v1/feeds", {
            "feed_url": f"https://news.example.com/feed-{suffix}.xml",
            "category_id": cat_a["id"],
            "title": "Daily News"
        }, headers=user_a_headers).json()
        entry_a = api_post(f"/v1/feeds/{feed_a['feed_id']}/entries", {
            "title": "Breaking News",
            "url": f"https://news.example.com/breaking-{suffix}",
        }, headers=user_a_headers).json()

        # Step 2: User B creates their own data with SAME category title
        cat_b = api_post("/v1/categories", {"title": "News"}, headers=user_b_headers).json()
        assert cat_b["id"] != cat_a["id"], "Different users should get different category IDs"

        feed_b = api_post("/v1/feeds", {
            "feed_url": f"https://news.example.com/feed-{suffix}.xml",
            "category_id": cat_b["id"],
            "title": "Daily News"
        }, headers=user_b_headers).json()
        # Same feed URL is OK for different users
        assert feed_b["feed_id"] != feed_a["feed_id"]

        # Step 3: User A sees only their data
        a_feeds = api_get("/v1/feeds", headers=user_a_headers).json()
        assert len(a_feeds) == 1
        assert a_feeds[0]["id"] == feed_a["feed_id"]

        a_entries = api_get("/v1/entries", headers=user_a_headers).json()
        assert a_entries["total"] == 1
        assert a_entries["entries"][0]["id"] == entry_a["id"]

        # Step 4: User B cannot see User A's specific entry
        resp = api_get(f"/v1/entries/{entry_a['id']}", headers=user_b_headers)
        assert resp.status_code == 404

        # Step 5: User B cannot access User A's feed
        resp = api_get(f"/v1/feeds/{feed_a['feed_id']}", headers=user_b_headers)
        assert resp.status_code == 404

        # Step 6: User B's categories don't include User A's
        b_cats = api_get("/v1/categories", headers=user_b_headers).json()
        b_cat_ids = [c["id"] for c in b_cats]
        assert cat_a["id"] not in b_cat_ids

    def test_admin_user_management_with_cascade_delete(self):
        """
        User auto-creates via token → creates data → admin deletes user → data gone.
        Patterns: 4+6+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Auto-create user via token (this is how auth works)
        user_token = f"doomed-user-{suffix}"
        user_headers = {"X-Auth-Token": user_token, "Content-Type": "application/json"}

        # Auto-create triggers on first request
        me_resp = api_get("/v1/me", headers=user_headers)
        assert me_resp.status_code == 200
        new_user = me_resp.json()
        assert new_user["username"] == user_token
        assert new_user["is_admin"] is False
        user_id = new_user["id"]

        # Step 2: User creates data
        cat = api_post("/v1/categories", {"title": "Doomed Cat"}, headers=user_headers).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/doomed-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Doomed Feed"
        }, headers=user_headers).json()
        entry = api_post(f"/v1/feeds/{feed['feed_id']}/entries", {
            "title": "Doomed Entry",
            "url": f"https://example.com/doomed-{suffix}",
        }, headers=user_headers).json()

        # Step 3: Verify user sees their data
        user_entries = api_get("/v1/entries", headers=user_headers).json()
        assert user_entries["total"] == 1

        # Step 4: Non-admin cannot delete users
        other_user_headers = _user_headers()
        del_resp = api_delete(f"/v1/users/{user_id}", headers=other_user_headers)
        assert del_resp.status_code == 403

        # Step 5: Admin deletes the user
        del_resp = api_delete(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert del_resp.status_code == 204

        # Step 6: Verify user is gone
        get_resp = api_get(f"/v1/users/{user_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 3: Entry reading workflow with starred/filter interaction
# Patterns: 3 (filtering), 5 (computed), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestReadingWorkflow:

    def test_reading_workflow_with_stars_and_filters(self):
        """
        Subscribe → receive entries → star some → read some → filter various ways.
        Patterns: 3+5+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Setup
        cat = api_post("/v1/categories", {"title": f"Reading-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/reading-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Reading Feed"
        }).json()
        feed_id = feed["feed_id"]

        # Step 2: Create 6 entries
        ids = []
        for i in range(6):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Article {i}: {suffix}",
                "url": f"https://example.com/reading-{suffix}-{i}",
                "content": f"Content for article {i}"
            })
            ids.append(r.json()["id"])

        # Step 3: Star entries 0 and 1
        api_put(f"/v1/entries/{ids[0]}/bookmark")
        api_put(f"/v1/entries/{ids[1]}/bookmark")

        # Step 4: Mark entries 0, 2, 3 as read
        api_put("/v1/entries", {"entry_ids": [ids[0], ids[2], ids[3]], "status": "read"})

        # Step 5: Filter by starred=true — should get entries 0 and 1
        starred_resp = api_get("/v1/entries", params={
            "starred": "true", "feed_id": feed_id
        }).json()
        assert starred_resp["total"] == 2
        starred_ids = {e["id"] for e in starred_resp["entries"]}
        assert ids[0] in starred_ids
        assert ids[1] in starred_ids

        # Step 6: Verify starring is independent of read status
        # Entry 0 is starred AND read
        e0 = api_get(f"/v1/entries/{ids[0]}").json()
        assert e0["starred"] is True
        assert e0["status"] == "read"
        # Entry 1 is starred AND unread
        e1 = api_get(f"/v1/entries/{ids[1]}").json()
        assert e1["starred"] is True
        assert e1["status"] == "unread"

        # Step 7: Filter unread — should get 1, 4, 5
        unread_resp = api_get("/v1/entries", params={
            "status": "unread", "feed_id": feed_id
        }).json()
        assert unread_resp["total"] == 3
        unread_ids = {e["id"] for e in unread_resp["entries"]}
        assert ids[1] in unread_ids
        assert ids[4] in unread_ids
        assert ids[5] in unread_ids

        # Step 8: Filter starred + unread combo
        starred_unread = api_get("/v1/entries", params={
            "starred": "true", "status": "unread", "feed_id": feed_id
        }).json()
        assert starred_unread["total"] == 1
        assert starred_unread["entries"][0]["id"] == ids[1]

        # Step 9: Verify counters
        counters = api_get("/v1/feeds/counters").json()
        assert counters["reads"][str(feed_id)] == 3
        assert counters["unreads"][str(feed_id)] == 3

    def test_search_across_entries_with_pagination(self):
        """
        Create entries with specific content → search → paginate results.
        Patterns: 3+5
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        search_keyword = f"quantum{suffix}"

        cat = api_post("/v1/categories", {"title": f"Search-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/search-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Search Feed"
        }).json()
        feed_id = feed["feed_id"]

        # Step 1: Create entries — 4 with keyword, 2 without
        for i in range(4):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Article about {search_keyword} physics {i}",
                "url": f"https://example.com/search-{suffix}-match-{i}",
            })
        for i in range(2):
            api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"Unrelated article {i}",
                "url": f"https://example.com/search-{suffix}-nomatch-{i}",
            })

        # Step 2: Search for keyword — should find 4
        search_resp = api_get("/v1/entries", params={
            "search": search_keyword, "feed_id": feed_id
        }).json()
        assert search_resp["total"] == 4

        # Step 3: Paginate search results
        page1 = api_get("/v1/entries", params={
            "search": search_keyword, "feed_id": feed_id, "limit": 2, "offset": 0,
            "order": "id", "direction": "asc",
        }).json()
        assert len(page1["entries"]) == 2
        assert page1["total"] == 4  # Total is still full count

        page2 = api_get("/v1/entries", params={
            "search": search_keyword, "feed_id": feed_id, "limit": 2, "offset": 2,
            "order": "id", "direction": "asc",
        }).json()
        assert len(page2["entries"]) == 2

        # Step 4: Pages don't overlap
        page1_ids = {e["id"] for e in page1["entries"]}
        page2_ids = {e["id"] for e in page2["entries"]}
        assert page1_ids.isdisjoint(page2_ids)


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 4: OPML import/export round-trip
# Patterns: 2 (nested data), 5 (business logic), 8 (order/uniqueness)
# ════════════════════════════════════════════════════════════════════


class TestOPMLWorkflow:

    def test_opml_export_import_roundtrip(self):
        """
        Create feeds → export OPML → import to new user → verify structure.
        Patterns: 2+5+8
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        user_b_headers = _user_headers(f"opml-user-{suffix}")

        # Step 1: Admin creates categorized feeds
        cat1 = api_post("/v1/categories", {"title": f"Tech-{suffix}"}).json()
        cat2 = api_post("/v1/categories", {"title": f"Science-{suffix}"}).json()

        api_post("/v1/feeds", {
            "feed_url": f"https://tech.example.com/feed-{suffix}.xml",
            "category_id": cat1["id"],
            "title": "Tech Blog"
        })
        api_post("/v1/feeds", {
            "feed_url": f"https://science.example.com/feed-{suffix}.xml",
            "category_id": cat2["id"],
            "title": "Science Daily"
        })

        # Step 2: Export OPML
        export_resp = api_get("/v1/export")
        assert export_resp.status_code == 200
        opml_xml = export_resp.text
        assert "opml" in opml_xml.lower()
        assert f"https://tech.example.com/feed-{suffix}.xml" in opml_xml
        assert f"https://science.example.com/feed-{suffix}.xml" in opml_xml

        # Step 3: Import to User B
        import_resp = api_post("/v1/import", opml_xml, headers=user_b_headers,
                              content_type="application/xml")
        assert import_resp.status_code == 201
        assert "message" in import_resp.json()

        # Step 4: Verify User B has the categories
        b_cats = api_get("/v1/categories", headers=user_b_headers).json()
        b_cat_titles = [c["title"] for c in b_cats]
        assert f"Tech-{suffix}" in b_cat_titles
        assert f"Science-{suffix}" in b_cat_titles

        # Step 5: Verify User B has the feeds with correct categories
        b_feeds = api_get("/v1/feeds", headers=user_b_headers).json()
        b_feed_urls = [f["feed_url"] for f in b_feeds]
        assert f"https://tech.example.com/feed-{suffix}.xml" in b_feed_urls
        assert f"https://science.example.com/feed-{suffix}.xml" in b_feed_urls

        # Step 6: Feeds should have nested category objects
        for feed in b_feeds:
            assert "category" in feed
            assert "id" in feed["category"]
            assert "title" in feed["category"]

    def test_opml_import_deduplication(self):
        """
        Import same OPML twice → categories and feeds not duplicated.
        Patterns: 5+8
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        user_headers = _user_headers(f"dedup-user-{suffix}")

        opml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Subs</title></head>
  <body>
    <outline text="DedupCat-{suffix}" title="DedupCat-{suffix}">
      <outline type="rss" text="Dedup Feed" title="Dedup Feed"
               xmlUrl="https://dedup.example.com/feed-{suffix}.xml"
               htmlUrl="https://dedup.example.com"/>
    </outline>
  </body>
</opml>"""

        # Step 1: First import
        resp1 = api_post("/v1/import", opml_xml, headers=user_headers,
                        content_type="application/xml")
        assert resp1.status_code == 201

        # Step 2: Second import (same content)
        resp2 = api_post("/v1/import", opml_xml, headers=user_headers,
                        content_type="application/xml")
        assert resp2.status_code == 201

        # Step 3: Verify no duplicates in categories
        cats = api_get("/v1/categories", headers=user_headers).json()
        matching_cats = [c for c in cats if c["title"] == f"DedupCat-{suffix}"]
        assert len(matching_cats) == 1, f"Expected 1 category, got {len(matching_cats)}"

        # Step 4: Verify no duplicates in feeds
        feeds = api_get("/v1/feeds", headers=user_headers).json()
        matching_feeds = [f for f in feeds
                         if f["feed_url"] == f"https://dedup.example.com/feed-{suffix}.xml"]
        assert len(matching_feeds) == 1, f"Expected 1 feed, got {len(matching_feeds)}"


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 5: Category management with feed reorganization
# Patterns: 2 (nested), 4 (status codes), 7 (cascade), 8 (constraints)
# ════════════════════════════════════════════════════════════════════


class TestCategoryReorganizationWorkflow:

    def test_move_feed_between_categories_updates_entries(self):
        """
        Move feed to new category → verify entries reflect new category context.
        Patterns: 2+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Create two categories
        cat_a = api_post("/v1/categories", {"title": f"CatA-{suffix}"}).json()
        cat_b = api_post("/v1/categories", {"title": f"CatB-{suffix}"}).json()

        # Step 2: Create feed in Cat A
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/movable-{suffix}.xml",
            "category_id": cat_a["id"],
            "title": "Movable Feed"
        }).json()
        feed_id = feed["feed_id"]

        # Step 3: Add entries
        entry = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Entry in Feed",
            "url": f"https://example.com/movable-{suffix}-entry",
        }).json()

        # Step 4: Verify entry shows up in category A entries
        cat_a_entries = api_get(f"/v1/categories/{cat_a['id']}/entries").json()
        assert cat_a_entries["total"] >= 1
        entry_ids_in_a = [e["id"] for e in cat_a_entries["entries"]]
        assert entry["id"] in entry_ids_in_a

        # Step 5: Move feed to Cat B
        update_resp = api_put(f"/v1/feeds/{feed_id}", {"category_id": cat_b["id"]})
        assert update_resp.status_code == 200
        assert update_resp.json()["category"]["id"] == cat_b["id"]

        # Step 6: Entry should now appear in category B entries
        cat_b_entries = api_get(f"/v1/categories/{cat_b['id']}/entries").json()
        entry_ids_in_b = [e["id"] for e in cat_b_entries["entries"]]
        assert entry["id"] in entry_ids_in_b

        # Step 7: Entry should NOT appear in category A entries anymore
        cat_a_entries2 = api_get(f"/v1/categories/{cat_a['id']}/entries").json()
        entry_ids_in_a2 = [e["id"] for e in cat_a_entries2["entries"]]
        assert entry["id"] not in entry_ids_in_a2

        # Step 8: Category A (now empty) can be deleted
        # First remove feed from cat A by verifying it's gone
        cat_a_feeds = api_get(f"/v1/categories/{cat_a['id']}/feeds").json()
        assert len(cat_a_feeds) == 0
        del_resp = api_delete(f"/v1/categories/{cat_a['id']}")
        assert del_resp.status_code == 204

    def test_cannot_delete_category_with_feeds(self):
        """
        Try to delete category that has feeds → fail → remove feeds → succeed.
        Patterns: 4+8
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Create category with a feed
        cat = api_post("/v1/categories", {"title": f"Protected-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/protected-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Blocking Feed"
        }).json()

        # Step 2: Try to delete category → should fail with 400
        del_resp = api_delete(f"/v1/categories/{cat['id']}")
        assert del_resp.status_code == 400, \
            f"Expected 400 (category has feeds), got {del_resp.status_code}"

        # Step 3: Delete the feed first
        api_delete(f"/v1/feeds/{feed['feed_id']}")

        # Step 4: Now category can be deleted
        del_resp2 = api_delete(f"/v1/categories/{cat['id']}")
        assert del_resp2.status_code == 204


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 6: Discovery + Subscribe + Read workflow
# Patterns: 1 (field names), 4 (status codes), 5 (business logic)
# ════════════════════════════════════════════════════════════════════


class TestDiscoveryToReadWorkflow:

    def test_discover_subscribe_read_workflow(self):
        """
        Discover feeds → subscribe → add entries → read → verify state.
        Patterns: 1+4+5
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        blog_url = f"https://newblog-{suffix}.example.com"

        # Step 1: Discover feeds
        discover_resp = api_post("/v1/discover", {"url": blog_url})
        assert discover_resp.status_code == 200
        discovered = discover_resp.json()
        assert isinstance(discovered, list)
        assert len(discovered) >= 1
        assert "url" in discovered[0]
        assert "title" in discovered[0]
        assert discovered[0]["url"] == blog_url

        # Step 2: Create category for subscription
        cat = api_post("/v1/categories", {"title": f"Discovered-{suffix}"})
        assert cat.status_code == 201
        cat_id = cat.json()["id"]

        # Step 3: Subscribe to discovered feed
        feed_resp = api_post("/v1/feeds", {
            "feed_url": discovered[0]["url"],
            "category_id": cat_id,
            "title": discovered[0]["title"]
        })
        assert feed_resp.status_code == 201
        feed_id = feed_resp.json()["feed_id"]

        # Step 4: Simulate entries arriving
        entry1 = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Welcome Post",
            "url": f"{blog_url}/welcome",
            "content": "<p>First post</p>"
        })
        assert entry1.status_code == 201
        entry1_data = entry1.json()
        assert entry1_data["status"] == "unread"
        assert entry1_data["starred"] is False
        assert entry1_data["feed_id"] == feed_id

        # Step 5: Verify via /v1/me that user context works
        me = api_get("/v1/me").json()
        assert "id" in me
        assert "username" in me
        assert "is_admin" in me

        # Step 6: Mark entry as read via batch
        batch_resp = api_put("/v1/entries", {
            "entry_ids": [entry1_data["id"]],
            "status": "read"
        })
        assert batch_resp.status_code == 204

        # Step 7: Verify the entry is now read
        entry_check = api_get(f"/v1/entries/{entry1_data['id']}").json()
        assert entry_check["status"] == "read"


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 7: Feed update propagation
# Patterns: 1 (field names), 2 (nested data), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestFeedUpdateWorkflow:

    def test_update_feed_properties_reflected_everywhere(self):
        """
        Update feed title → verify reflected in feed list, category feeds,
        and nested in entry responses.
        Patterns: 1+2+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        # Step 1: Setup
        cat = api_post("/v1/categories", {"title": f"FeedUpd-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/feedupd-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Original Title"
        }).json()
        feed_id = feed["feed_id"]

        entry = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Test Article",
            "url": f"https://example.com/feedupd-{suffix}-article",
        }).json()
        entry_id = entry["id"]

        # Step 2: Update feed title
        update_resp = api_put(f"/v1/feeds/{feed_id}", {"title": "Updated Title"})
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated Title"
        # Must still have nested category
        assert "category" in update_resp.json()
        assert update_resp.json()["category"]["id"] == cat["id"]

        # Step 3: Verify in feed list
        feeds = api_get("/v1/feeds").json()
        our_feed = next(f for f in feeds if f["id"] == feed_id)
        assert our_feed["title"] == "Updated Title"

        # Step 4: Verify in category feeds
        cat_feeds = api_get(f"/v1/categories/{cat['id']}/feeds").json()
        cat_feed = next(f for f in cat_feeds if f["id"] == feed_id)
        assert cat_feed["title"] == "Updated Title"

        # Step 5: Verify nested feed in entry response reflects update
        entry_resp = api_get(f"/v1/entries/{entry_id}").json()
        assert "feed" in entry_resp
        assert entry_resp["feed"]["title"] == "Updated Title"
        assert entry_resp["feed"]["id"] == feed_id


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 8: Admin mark-all-as-read for a user across multiple feeds/categories
# Patterns: 5 (computed), 6 (authorization), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestUserMarkAllReadWorkflow:

    def test_user_mark_all_as_read_spans_all_feeds(self):
        """
        User has entries across multiple feeds/categories →
        non-admin self call is forbidden → admin mark-all-as-read for user →
        all become read.
        Patterns: 5+6+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]
        user_headers = _user_headers(f"markall-{suffix}")

        # Step 1: Get user ID
        me = api_get("/v1/me", headers=user_headers).json()
        user_id = me["id"]

        # Step 2: Create 2 categories, each with a feed and entries
        cat1 = api_post("/v1/categories", {"title": f"MarkAll1-{suffix}"},
                       headers=user_headers).json()
        cat2 = api_post("/v1/categories", {"title": f"MarkAll2-{suffix}"},
                       headers=user_headers).json()

        feed1 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/markall1-{suffix}.xml",
            "category_id": cat1["id"],
            "title": "Feed1"
        }, headers=user_headers).json()["feed_id"]

        feed2 = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/markall2-{suffix}.xml",
            "category_id": cat2["id"],
            "title": "Feed2"
        }, headers=user_headers).json()["feed_id"]

        for i in range(3):
            api_post(f"/v1/feeds/{feed1}/entries", {
                "title": f"F1 Entry {i}",
                "url": f"https://example.com/markall1-{suffix}-{i}",
            }, headers=user_headers)
        for i in range(2):
            api_post(f"/v1/feeds/{feed2}/entries", {
                "title": f"F2 Entry {i}",
                "url": f"https://example.com/markall2-{suffix}-{i}",
            }, headers=user_headers)

        # Step 3: Verify 5 unread total
        entries = api_get("/v1/entries", params={"status": "unread"},
                         headers=user_headers).json()
        assert entries["total"] == 5

        # Step 4: Non-admin user-management call is forbidden and has no side effect
        forbidden_resp = api_put(f"/v1/users/{user_id}/mark-all-as-read",
                                headers=user_headers)
        assert forbidden_resp.status_code == 403
        still_unread = api_get("/v1/entries", params={"status": "unread"},
                              headers=user_headers).json()
        assert still_unread["total"] == 5

        # Step 5: Admin marks all user entries as read
        mark_resp = api_put(f"/v1/users/{user_id}/mark-all-as-read")
        assert mark_resp.status_code == 204

        # Step 6: Verify zero unread
        entries_after = api_get("/v1/entries", params={"status": "unread"},
                               headers=user_headers).json()
        assert entries_after["total"] == 0

        # Step 7: Verify all are read
        all_entries = api_get("/v1/entries", headers=user_headers).json()
        assert all_entries["total"] == 5
        for e in all_entries["entries"]:
            assert e["status"] == "read"

        # Step 8: Verify counters reflect this
        counters = api_get("/v1/feeds/counters", headers=user_headers).json()
        assert counters["unreads"].get(str(feed1), 0) == 0
        assert counters["unreads"].get(str(feed2), 0) == 0
        assert counters["reads"][str(feed1)] == 3
        assert counters["reads"][str(feed2)] == 2


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 9: Entry update and bookmark interaction
# Patterns: 1 (fields), 5 (business logic), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestEntryModificationWorkflow:

    def test_entry_update_preserves_status_and_bookmark(self):
        """
        Create entry → mark read → star → update title/content →
        verify status and star preserved.
        Patterns: 1+5+7
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        cat = api_post("/v1/categories", {"title": f"EntryMod-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/entrymod-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Entry Mod Feed"
        }).json()
        feed_id = feed["feed_id"]

        # Step 1: Create entry
        entry = api_post(f"/v1/feeds/{feed_id}/entries", {
            "title": "Original Title",
            "url": f"https://example.com/entrymod-{suffix}",
            "content": "Original content"
        }).json()
        entry_id = entry["id"]
        assert entry["status"] == "unread"
        assert entry["starred"] is False

        # Step 2: Mark as read
        api_put("/v1/entries", {"entry_ids": [entry_id], "status": "read"})

        # Step 3: Star it
        api_put(f"/v1/entries/{entry_id}/bookmark")

        # Step 4: Verify state
        e = api_get(f"/v1/entries/{entry_id}").json()
        assert e["status"] == "read"
        assert e["starred"] is True

        # Step 5: Update title and content
        update_resp = api_put(f"/v1/entries/{entry_id}", {
            "title": "Updated Title",
            "content": "Updated content"
        })
        assert update_resp.status_code == 200
        updated = update_resp.json()

        # Step 6: Verify update applied
        assert updated["title"] == "Updated Title"
        assert updated["content"] == "Updated content"

        # Step 7: Verify status and star preserved
        assert updated["status"] == "read", "Update should not reset status"
        assert updated["starred"] is True, "Update should not reset bookmark"

        # Step 8: Verify via GET
        final = api_get(f"/v1/entries/{entry_id}").json()
        assert final["title"] == "Updated Title"
        assert final["content"] == "Updated content"
        assert final["status"] == "read"
        assert final["starred"] is True


# ════════════════════════════════════════════════════════════════════
# L3 Workflow 10: Feed entries endpoint with filtering
# Patterns: 3 (filtering), 5 (computed), 7 (side effects)
# ════════════════════════════════════════════════════════════════════


class TestFeedEntriesFilterWorkflow:

    def test_feed_entries_endpoint_respects_all_filters(self):
        """
        Use GET /v1/feeds/{id}/entries with various filters and verify.
        Patterns: 3+5
        """
        ensure_admin()
        suffix = uuid.uuid4().hex[:6]

        cat = api_post("/v1/categories", {"title": f"FeedEntries-{suffix}"}).json()
        feed = api_post("/v1/feeds", {
            "feed_url": f"https://example.com/feedentries-{suffix}.xml",
            "category_id": cat["id"],
            "title": "Feed Entries Test"
        }).json()
        feed_id = feed["feed_id"]

        # Step 1: Create 6 entries
        ids = []
        for i in range(6):
            r = api_post(f"/v1/feeds/{feed_id}/entries", {
                "title": f"FE Article {i}",
                "url": f"https://example.com/fe-{suffix}-{i}",
            })
            ids.append(r.json()["id"])

        # Step 2: Mark first 3 as read, star entry 1
        api_put("/v1/entries", {"entry_ids": ids[:3], "status": "read"})
        api_put(f"/v1/entries/{ids[1]}/bookmark")

        # Step 3: Filter by status=unread via feed endpoint
        unread_resp = api_get(f"/v1/feeds/{feed_id}/entries",
                             params={"status": "unread"}).json()
        assert unread_resp["total"] == 3
        for e in unread_resp["entries"]:
            assert e["status"] == "unread"
            assert e["feed_id"] == feed_id

        # Step 4: Filter starred via feed endpoint
        starred_resp = api_get(f"/v1/feeds/{feed_id}/entries",
                              params={"starred": "true"}).json()
        assert starred_resp["total"] == 1
        assert starred_resp["entries"][0]["id"] == ids[1]

        # Step 5: Pagination via feed endpoint
        page = api_get(f"/v1/feeds/{feed_id}/entries",
                      params={"limit": 2, "order": "id", "direction": "asc"}).json()
        assert len(page["entries"]) == 2
        assert page["total"] == 6
        assert page["entries"][0]["id"] < page["entries"][1]["id"]

        # Step 6: Verify result set structure
        assert "total" in page
        assert "entries" in page
        assert isinstance(page["total"], int)
        assert isinstance(page["entries"], list)
