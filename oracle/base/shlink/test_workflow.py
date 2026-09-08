"""
BackendForge — L3 Workflow Tests for Shlink Task

Multi-step workflow tests that cross entity boundaries and verify
complex interactions, side effects, and business logic integrity.

Bug patterns targeted:
- Pattern 2: Nested/related data not returned
- Pattern 3: Parameters declared but not implemented
- Pattern 5: Business logic "exists but behavior empty"
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Uniqueness/ordering sensitivity

"""

import os
import uuid
import time
import datetime
from datetime import timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-workflow"

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None, allow_redirects=False):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
        allow_redirects=allow_redirects,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_patch(path, json_data=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, params=None, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ════════════════════════════════════════════════════════════════════
# L3-1: Full URL lifecycle with visits and analytics
# ════════════════════════════════════════════════════════════════════


class TestFullUrlLifecycle:
    """Pattern 5+7: Create URL → visit → verify analytics → delete → verify cascade."""

    def test_create_visit_analyze_delete_workflow(self):
        """Complete lifecycle: create, visit, check analytics, delete, verify cleanup."""
        # Step 1: Create short URL with tags
        tag = f"lifecycle-{UNIQUE}"
        create_resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/lifecycle-{UNIQUE}",
            "tags": [tag],
            "title": "Lifecycle Test",
            "customSlug": f"life-{UNIQUE}",
        })
        assert create_resp.status_code == 200
        url_data = create_resp.json()
        short_code = url_data["shortCode"]
        assert short_code == f"life-{UNIQUE}"
        assert url_data["title"] == "Lifecycle Test"
        assert url_data["visitsSummary"]["total"] == 0

        # Step 2: Visit the URL 3 times (2 human, 1 bot)
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://google.com"},
            allow_redirects=False, timeout=30,
        )
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Mozilla/5.0 Safari"},
            allow_redirects=False, timeout=30,
        )
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Googlebot/2.1"},
            allow_redirects=False, timeout=30,
        )

        # Step 3: Verify visit counts on the short URL
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.status_code == 200
        summary = get_resp.json()["visitsSummary"]
        assert summary["total"] == 3
        assert summary["nonBots"] == 2
        assert summary["bots"] == 1

        # Step 4: Verify visit records exist
        visits_resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert visits_resp.status_code == 200
        visits = visits_resp.json()["visits"]["data"]
        assert len(visits) == 3

        # Step 5: Verify tag visits
        tag_visits_resp = api_get(f"/rest/v3/tags/{tag}/visits")
        assert tag_visits_resp.status_code == 200
        tag_visits = tag_visits_resp.json()["visits"]["data"]
        assert len(tag_visits) == 3

        # Step 6: Delete the short URL
        del_resp = api_delete(f"/rest/v3/short-urls/{short_code}")
        assert del_resp.status_code == 204

        # Step 7: Verify it's gone
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.status_code == 404

        # Step 8: Verify redirect no longer works
        redir_resp = requests.get(
            f"{BASE_URL}/{short_code}",
            allow_redirects=False, timeout=30,
        )
        assert redir_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L3-2: Max visits enforcement workflow
# ════════════════════════════════════════════════════════════════════


class TestMaxVisitsWorkflow:
    """Pattern 5+7: maxVisits enforced correctly through full workflow."""

    def test_max_visits_enforcement_and_api_visibility(self):
        """URL with maxVisits: redirect stops at limit but API still shows URL."""
        # Step 1: Create URL with maxVisits=3
        create_resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/maxv-{UNIQUE}",
            "maxVisits": 3,
        })
        assert create_resp.status_code == 200
        short_code = create_resp.json()["shortCode"]
        assert create_resp.json()["meta"]["maxVisits"] == 3

        # Step 2: Visit 3 times successfully
        for i in range(3):
            resp = requests.get(
                f"{BASE_URL}/{short_code}",
                allow_redirects=False, timeout=30,
            )
            assert resp.status_code == 302, f"Visit {i+1} should succeed"

        # Step 3: 4th visit should fail with 404
        resp = requests.get(
            f"{BASE_URL}/{short_code}",
            allow_redirects=False, timeout=30,
        )
        assert resp.status_code == 404, "Visit after maxVisits should return 404"

        # Step 4: URL still visible via API
        api_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert api_resp.status_code == 200
        assert api_resp.json()["meta"]["maxVisits"] == 3
        assert api_resp.json()["visitsSummary"]["total"] == 3

        # Step 5: Visits endpoint still shows the 3 visits
        visits_resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert visits_resp.status_code == 200
        assert len(visits_resp.json()["visits"]["data"]) == 3

        # Step 6: URL still appears in listing
        list_resp = api_get("/rest/v3/short-urls", params={
            "searchTerm": short_code,
        })
        assert list_resp.status_code == 200
        found = [u for u in list_resp.json()["shortUrls"]["data"] if u["shortCode"] == short_code]
        assert len(found) == 1


# ════════════════════════════════════════════════════════════════════
# L3-3: Tag sharing and cross-URL analytics
# ════════════════════════════════════════════════════════════════════


class TestTagSharingWorkflow:
    """Pattern 2+5: Tags shared across URLs, stats computed correctly."""

    def test_shared_tag_aggregates_visits_across_urls(self):
        """Tag visits aggregate visits from ALL URLs with that tag."""
        shared_tag = f"shared-{UNIQUE}"

        # Step 1: Create URL A with shared tag
        resp_a = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/shared-a-{UNIQUE}",
            "tags": [shared_tag],
        })
        code_a = resp_a.json()["shortCode"]

        # Step 2: Create URL B with shared tag
        resp_b = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/shared-b-{UNIQUE}",
            "tags": [shared_tag],
        })
        code_b = resp_b.json()["shortCode"]

        # Step 3: Visit URL A twice
        for _ in range(2):
            requests.get(f"{BASE_URL}/{code_a}", allow_redirects=False, timeout=30)

        # Step 4: Visit URL B once
        requests.get(f"{BASE_URL}/{code_b}", allow_redirects=False, timeout=30)

        # Step 5: Tag visits should have ALL 3 visits
        tag_visits_resp = api_get(f"/rest/v3/tags/{shared_tag}/visits")
        assert tag_visits_resp.status_code == 200
        tag_visits = tag_visits_resp.json()["visits"]["data"]
        assert len(tag_visits) == 3, (
            f"Tag should aggregate visits from both URLs: expected 3, got {len(tag_visits)}"
        )

        # Step 6: Tag stats should show 2 short URLs
        stats_resp = api_get("/rest/v3/tags/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()["tags"]["data"]
        tag_stat = [s for s in stats if s["tag"] == shared_tag]
        assert len(tag_stat) == 1
        assert tag_stat[0]["shortUrlsCount"] == 2
        assert tag_stat[0]["visitsSummary"]["total"] == 3

        # Step 7: Verify each URL has its own correct visit count
        url_a = api_get(f"/rest/v3/short-urls/{code_a}").json()
        url_b = api_get(f"/rest/v3/short-urls/{code_b}").json()
        assert url_a["visitsSummary"]["total"] == 2
        assert url_b["visitsSummary"]["total"] == 1


# ════════════════════════════════════════════════════════════════════
# L3-4: Orphan visits and global stats consistency
# ════════════════════════════════════════════════════════════════════


class TestOrphanVisitsWorkflow:
    """Pattern 5+7: Orphan visits tracked correctly in global stats."""

    def test_orphan_and_non_orphan_visits_tracked_separately(self):
        """Valid and invalid visits tracked in different categories."""
        # Step 1: Get initial global stats
        initial = api_get("/rest/v3/visits").json()["visits"]
        initial_non_orphan = initial["nonOrphanVisits"]["total"]
        initial_orphan = initial["orphanVisits"]["total"]

        # Step 2: Create a valid short URL
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/orphan-wf-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Step 3: Visit valid URL (non-orphan)
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Step 4: Visit invalid URL (orphan)
        requests.get(
            f"{BASE_URL}/invalid-orphan-{UNIQUE}",
            allow_redirects=False, timeout=30,
        )

        # Step 5: Verify global stats updated correctly
        after = api_get("/rest/v3/visits").json()["visits"]
        assert after["nonOrphanVisits"]["total"] == initial_non_orphan + 1
        assert after["orphanVisits"]["total"] == initial_orphan + 1

        # Step 6: Verify orphan visits list has our visit
        orphan_resp = api_get("/rest/v3/visits/orphan")
        orphan_visits = orphan_resp.json()["visits"]["data"]
        orphan_urls = [v.get("visitedUrl", "") for v in orphan_visits]
        matching = [u for u in orphan_urls if f"invalid-orphan-{UNIQUE}" in (u or "")]
        assert len(matching) >= 1, "Orphan visit should be recorded"

        # Step 7: Verify non-orphan visits list has our valid visit
        non_orphan_resp = api_get("/rest/v3/visits/non-orphan")
        non_orphan_visits = non_orphan_resp.json()["visits"]["data"]
        assert len(non_orphan_visits) >= 1

        # Step 8: Verify orphan visit has type field
        orphan_typed = [v for v in orphan_visits if v.get("type") == "invalid_short_url"]
        assert len(orphan_typed) >= 1


# ════════════════════════════════════════════════════════════════════
# L3-5: Tag rename propagation workflow
# ════════════════════════════════════════════════════════════════════


class TestTagRenameWorkflow:
    """Pattern 7: Tag rename propagates to all short URLs using it."""

    def test_rename_tag_updates_all_urls(self):
        """Renaming a tag should update it across all short URLs."""
        old_tag = f"old-rename-{UNIQUE}"
        new_tag = f"new-rename-{UNIQUE}"
        other_tag = f"other-keep-{UNIQUE}"

        # Step 1: Create URL A with old_tag
        resp_a = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/rename-a-{UNIQUE}",
            "tags": [old_tag, other_tag],
        })
        code_a = resp_a.json()["shortCode"]

        # Step 2: Create URL B with old_tag
        resp_b = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/rename-b-{UNIQUE}",
            "tags": [old_tag],
        })
        code_b = resp_b.json()["shortCode"]

        # Step 3: Rename the tag
        rename_resp = api_put("/rest/v3/tags", {
            "oldName": old_tag,
            "newName": new_tag,
        })
        assert rename_resp.status_code == 204

        # Step 4: Verify URL A has new tag and other_tag still
        url_a = api_get(f"/rest/v3/short-urls/{code_a}").json()
        assert new_tag in url_a["tags"]
        assert old_tag not in url_a["tags"]
        assert other_tag in url_a["tags"]

        # Step 5: Verify URL B has new tag
        url_b = api_get(f"/rest/v3/short-urls/{code_b}").json()
        assert new_tag in url_b["tags"]
        assert old_tag not in url_b["tags"]

        # Step 6: Old tag should not exist in tags list
        tags_resp = api_get("/rest/v3/tags")
        tags = tags_resp.json()["tags"]["data"]
        assert old_tag not in tags
        assert new_tag in tags

        # Step 7: Renaming non-existent tag returns error
        resp = api_put("/rest/v3/tags", {
            "oldName": f"nonexistent-{UNIQUE}",
            "newName": "something",
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L3-6: findIfExists deduplication workflow
# ════════════════════════════════════════════════════════════════════


class TestFindIfExistsWorkflow:
    """Pattern 5+8: findIfExists returns existing URL correctly."""

    def test_find_if_exists_returns_same_url_preserves_visits(self):
        """findIfExists returns existing URL with up-to-date visit count."""
        long_url = f"https://example.com/find-exists-{UNIQUE}"

        # Step 1: Create initial URL
        first = api_post("/rest/v3/short-urls", {
            "longUrl": long_url,
            "tags": [f"find-tag-{UNIQUE}"],
        })
        assert first.status_code == 200
        first_code = first.json()["shortCode"]

        # Step 2: Visit the URL
        requests.get(f"{BASE_URL}/{first_code}", allow_redirects=False, timeout=30)

        # Step 3: Create again with findIfExists=true
        second = api_post("/rest/v3/short-urls", {
            "longUrl": long_url,
            "findIfExists": True,
        })
        assert second.status_code == 200
        second_code = second.json()["shortCode"]

        # Step 4: Should return the SAME short code
        assert first_code == second_code, (
            f"findIfExists should return existing URL: got {second_code}, expected {first_code}"
        )

        # Step 5: Visit summary should reflect the visit
        assert second.json()["visitsSummary"]["total"] >= 1

        # Step 6: Without findIfExists, creates a new URL
        third = api_post("/rest/v3/short-urls", {
            "longUrl": long_url,
        })
        assert third.status_code == 200
        third_code = third.json()["shortCode"]
        assert third_code != first_code, "Without findIfExists should create new URL"


# ════════════════════════════════════════════════════════════════════
# L3-7: Update URL and verify redirect changes
# ════════════════════════════════════════════════════════════════════


class TestUpdateUrlWorkflow:
    """Pattern 5+7: Update URL fields and verify behavior changes."""

    def test_update_long_url_changes_redirect_target(self):
        """Changing longUrl via PATCH changes where redirect goes."""
        original_url = f"https://example.com/original-{UNIQUE}"
        updated_url = f"https://example.com/updated-{UNIQUE}"

        # Step 1: Create with original URL
        create_resp = api_post("/rest/v3/short-urls", {
            "longUrl": original_url,
        })
        short_code = create_resp.json()["shortCode"]

        # Step 2: Redirect goes to original
        redir = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir.status_code == 302
        assert redir.headers["Location"] == original_url

        # Step 3: Update the long URL
        patch_resp = api_patch(f"/rest/v3/short-urls/{short_code}", {
            "longUrl": updated_url,
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["longUrl"] == updated_url

        # Step 4: Redirect now goes to updated URL
        redir2 = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir2.status_code == 302
        assert redir2.headers["Location"] == updated_url

        # Step 5: Visit count should be 2 (both visits counted)
        url_data = api_get(f"/rest/v3/short-urls/{short_code}").json()
        assert url_data["visitsSummary"]["total"] == 2

        # Step 6: Verify all visits are in the visit list
        visits = api_get(f"/rest/v3/short-urls/{short_code}/visits").json()["visits"]["data"]
        assert len(visits) == 2


# ════════════════════════════════════════════════════════════════════
# L3-8: Valid date range workflow
# ════════════════════════════════════════════════════════════════════


class TestValidDateRangeWorkflow:
    """Pattern 5: Date range enforcement works dynamically."""

    def test_valid_until_past_blocks_redirect_api_still_works(self):
        """URL with expired validUntil: redirect blocked, API accessible."""
        past = (datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # Step 1: Create URL that's already expired
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/expired-{UNIQUE}",
            "validUntil": past,
            "customSlug": f"expired-{UNIQUE}",
        })
        assert resp.status_code == 200
        short_code = resp.json()["shortCode"]

        # Step 2: Redirect should return 404
        redir = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir.status_code == 404

        # Step 3: API still shows the URL
        api_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert api_resp.status_code == 200
        assert api_resp.json()["meta"]["validUntil"] is not None

        # Step 4: URL appears in listing
        list_resp = api_get("/rest/v3/short-urls", params={
            "searchTerm": short_code,
        })
        items = list_resp.json()["shortUrls"]["data"]
        assert any(u["shortCode"] == short_code for u in items)

        # Step 5: Update to remove validUntil (set future date)
        future = (datetime.datetime.now(timezone.utc) + datetime.timedelta(days=365)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        patch_resp = api_patch(f"/rest/v3/short-urls/{short_code}", {
            "validUntil": future,
        })
        assert patch_resp.status_code == 200

        # Step 6: Redirect should now work
        redir2 = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir2.status_code == 302


# ════════════════════════════════════════════════════════════════════
# L3-9: Domain visits workflow
# ════════════════════════════════════════════════════════════════════


class TestDomainVisitsWorkflow:
    """Pattern 2+5: Domain visits aggregate correctly."""

    def test_default_domain_visits_track_all_default_urls(self):
        """Visits to URLs on the default domain appear in domain visits."""
        # Step 1: Create URLs on default domain
        resp_a = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/domain-a-{UNIQUE}",
        })
        code_a = resp_a.json()["shortCode"]

        resp_b = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/domain-b-{UNIQUE}",
        })
        code_b = resp_b.json()["shortCode"]

        # Step 2: Visit both URLs
        requests.get(f"{BASE_URL}/{code_a}", allow_redirects=False, timeout=30)
        requests.get(f"{BASE_URL}/{code_b}", allow_redirects=False, timeout=30)
        requests.get(f"{BASE_URL}/{code_b}", allow_redirects=False, timeout=30)

        # Step 3: Check domain visits for DEFAULT
        domain_visits_resp = api_get("/rest/v3/domains/DEFAULT/visits")
        assert domain_visits_resp.status_code == 200
        domain_visits = domain_visits_resp.json()["visits"]["data"]

        # Should have at least 3 visits (from our URLs)
        assert len(domain_visits) >= 3

        # Step 4: Verify pagination structure
        pagination = domain_visits_resp.json()["visits"]["pagination"]
        assert "currentPage" in pagination
        assert "totalItems" in pagination
        assert pagination["totalItems"] >= 3


# ════════════════════════════════════════════════════════════════════
# L3-10: Bot detection across multiple endpoints
# ════════════════════════════════════════════════════════════════════


class TestBotDetectionWorkflow:
    """Pattern 5: Bot detection works consistently across all analytics."""

    def test_bot_detection_consistent_across_endpoints(self):
        """Bot visits detected consistently in all visit-related endpoints."""
        tag = f"bottest-{UNIQUE}"

        # Step 1: Create URL with tag
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/bot-wf-{UNIQUE}",
            "tags": [tag],
        })
        short_code = resp.json()["shortCode"]

        # Step 2: Visit as bot (spider keyword)
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "WebSpider/3.0"},
            allow_redirects=False, timeout=30,
        )

        # Step 3: Visit as human
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0"},
            allow_redirects=False, timeout=30,
        )

        # Step 4: Check short URL visitsSummary
        url_data = api_get(f"/rest/v3/short-urls/{short_code}").json()
        assert url_data["visitsSummary"]["total"] == 2
        assert url_data["visitsSummary"]["bots"] == 1
        assert url_data["visitsSummary"]["nonBots"] == 1

        # Step 5: Check visit records for potentialBot field
        visits = api_get(f"/rest/v3/short-urls/{short_code}/visits").json()["visits"]["data"]
        bot_visits = [v for v in visits if v["potentialBot"] is True]
        human_visits = [v for v in visits if v["potentialBot"] is False]
        assert len(bot_visits) == 1
        assert len(human_visits) == 1

        # Step 6: excludeBots filter on short URL visits
        filtered = api_get(
            f"/rest/v3/short-urls/{short_code}/visits",
            params={"excludeBots": "true"},
        ).json()["visits"]["data"]
        assert len(filtered) == 1
        assert filtered[0]["potentialBot"] is False

        # Step 7: Tag stats should show correct bot breakdown
        stats = api_get("/rest/v3/tags/stats").json()["tags"]["data"]
        tag_stat = [s for s in stats if s["tag"] == tag]
        assert len(tag_stat) == 1
        assert tag_stat[0]["visitsSummary"]["total"] == 2
        assert tag_stat[0]["visitsSummary"]["bots"] == 1
        assert tag_stat[0]["visitsSummary"]["nonBots"] == 1


# ════════════════════════════════════════════════════════════════════
# L3-11: Search and ordering combined workflow
# ════════════════════════════════════════════════════════════════════


class TestSearchAndOrderWorkflow:
    """Pattern 3: Search + ordering work together correctly."""

    def test_search_with_ordering_returns_filtered_sorted_results(self):
        """searchTerm filters results AND orderBy sorts them correctly."""
        search_term = f"searchord-{UNIQUE}"

        # Step 1: Create 3 URLs with the search term, different slugs for ordering
        slugs = [f"ccc-{search_term}", f"aaa-{search_term}", f"bbb-{search_term}"]
        for slug in slugs:
            api_post("/rest/v3/short-urls", {
                "longUrl": f"https://example.com/{slug}",
                "customSlug": slug,
            })

        # Create one URL WITHOUT the search term (should be excluded)
        api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/no-match-{UNIQUE}",
            "customSlug": f"no-match-{UNIQUE}",
        })

        # Step 2: Search + order by shortCode-ASC
        resp = api_get("/rest/v3/short-urls", params={
            "searchTerm": search_term,
            "orderBy": "shortCode-ASC",
        })
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]

        # Step 3: Should only have items matching search term
        assert len(items) == 3
        for item in items:
            assert search_term in item["shortCode"] or search_term in item["longUrl"]

        # Step 4: Should be in ASC order
        codes = [item["shortCode"] for item in items]
        assert codes == sorted(codes), f"Expected ASC order, got {codes}"

        # Step 5: Verify non-matching URL is excluded
        all_codes = [item["shortCode"] for item in items]
        assert f"no-match-{UNIQUE}" not in all_codes


# ════════════════════════════════════════════════════════════════════
# L3-12: Delete URL cascades to visits
# ════════════════════════════════════════════════════════════════════


class TestDeleteCascadeWorkflow:
    """Pattern 7: Deleting short URL cascades to related entities."""

    def test_delete_url_cascades_tags_and_blocks_access(self):
        """Deleting a URL: API returns 404, redirect fails, tags removed from URL."""
        tag = f"cascade-tag-{UNIQUE}"

        # Step 1: Create URL with tag and visit it
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/cascade-{UNIQUE}",
            "tags": [tag],
            "customSlug": f"cascade-{UNIQUE}",
        })
        assert resp.status_code == 200
        short_code = resp.json()["shortCode"]

        # Step 2: Visit to generate visit records
        redir = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir.status_code == 302

        # Step 3: Confirm visit was recorded
        visits_resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert visits_resp.status_code == 200
        assert len(visits_resp.json()["visits"]["data"]) == 1

        # Step 4: Delete the URL
        del_resp = api_delete(f"/rest/v3/short-urls/{short_code}")
        assert del_resp.status_code == 204

        # Step 5: API lookup returns 404
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.status_code == 404

        # Step 6: Redirect now returns 404 (records orphan visit)
        redir2 = requests.get(
            f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30,
        )
        assert redir2.status_code == 404

        # Step 7: Visits endpoint for deleted URL returns 404
        visits_resp2 = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert visits_resp2.status_code == 404

        # Step 8: Cannot delete again (already gone)
        del_again = api_delete(f"/rest/v3/short-urls/{short_code}")
        assert del_again.status_code == 404
