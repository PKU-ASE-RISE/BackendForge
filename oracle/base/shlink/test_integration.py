"""
BackendForge — L2 Integration Tests for Shlink Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned correctly
- Pattern 3: Parameters declared but not implemented (filtering, ordering)
- Pattern 4: Wrong status codes
- Pattern 5: Business logic "exists but empty" (analytics, counters)
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Uniqueness constraints missing

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
API_KEY = "test-api-key-integration"

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
# L2-1: camelCase field names on CREATE response
# ════════════════════════════════════════════════════════════════════


class TestCamelCaseFields:
    """Pattern 1: Verify camelCase field names in all responses."""

    def test_create_response_has_camel_case_fields(self):
        """All required fields in create response must be camelCase."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/camel-{UNIQUE}",
            "tags": ["test-tag"],
            "title": "Test Title",
        })
        assert resp.status_code == 200
        data = resp.json()

        # Verify all required camelCase fields exist
        required_fields = [
            "shortCode", "shortUrl", "longUrl", "dateCreated",
            "visitsSummary", "tags", "meta", "domain", "title",
            "crawlable", "forwardQuery",
        ]
        for field in required_fields:
            assert field in data, f"Missing camelCase field '{field}' in response"

        # Verify snake_case variants are NOT present
        snake_case_traps = [
            "short_code", "short_url", "long_url", "date_created",
            "visits_summary", "forward_query", "visits_count",
        ]
        for field in snake_case_traps:
            assert field not in data, f"Found snake_case field '{field}' — must be camelCase"

    def test_visits_summary_has_camel_case_fields(self):
        """visitsSummary nested object must have camelCase fields."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/vs-camel-{UNIQUE}",
        })
        assert resp.status_code == 200
        summary = resp.json()["visitsSummary"]

        assert "total" in summary
        assert "nonBots" in summary, "Should be 'nonBots' not 'non_bots'"
        assert "bots" in summary

        # Check snake_case NOT present
        assert "non_bots" not in summary
        assert "total_visits" not in summary

    def test_meta_has_camel_case_fields(self):
        """meta nested object must have camelCase fields."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/meta-camel-{UNIQUE}",
            "maxVisits": 10,
            "validSince": "2020-01-01T00:00:00Z",
            "validUntil": "2099-12-31T23:59:59Z",
        })
        assert resp.status_code == 200
        meta = resp.json()["meta"]

        assert "validSince" in meta, "Should be 'validSince' not 'valid_since'"
        assert "validUntil" in meta, "Should be 'validUntil' not 'valid_until'"
        assert "maxVisits" in meta, "Should be 'maxVisits' not 'max_visits'"

        # Values should be preserved
        assert meta["maxVisits"] == 10
        assert meta["validSince"] is not None
        assert meta["validUntil"] is not None

    def test_get_response_has_same_camel_case_fields(self):
        """GET response must have same camelCase structure as POST response."""
        create_resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/get-camel-{UNIQUE}",
            "title": "Get Test",
        })
        assert create_resp.status_code == 200
        short_code = create_resp.json()["shortCode"]

        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.status_code == 200
        data = get_resp.json()

        # Same fields required
        assert "shortCode" in data
        assert "longUrl" in data
        assert "dateCreated" in data
        assert "visitsSummary" in data
        assert "meta" in data
        assert "forwardQuery" in data
        assert data["shortCode"] == short_code
        assert data["title"] == "Get Test"


# ════════════════════════════════════════════════════════════════════
# L2-2: Visit counter increment verification
# ════════════════════════════════════════════════════════════════════


class TestVisitCounterIncrement:
    """Pattern 5: Visit counter must actually increment (not hardcoded)."""

    def test_visit_increments_total_counter(self):
        """Each redirect should increment visitsSummary.total by 1."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/inc-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Initially zero
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.json()["visitsSummary"]["total"] == 0

        # Visit once
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Should be 1
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.json()["visitsSummary"]["total"] == 1

        # Visit again
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Should be 2
        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert get_resp.json()["visitsSummary"]["total"] == 2

    def test_visit_increments_nonbots_for_regular_user_agent(self):
        """Regular user agent visit increments nonBots counter."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/nonbot-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Visit with normal UA
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"},
            allow_redirects=False, timeout=30,
        )

        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        summary = get_resp.json()["visitsSummary"]
        assert summary["total"] == 1
        assert summary["nonBots"] == 1
        assert summary["bots"] == 0

    def test_visit_increments_bots_for_bot_user_agent(self):
        """Bot user agent visit increments bots counter."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/botcount-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Visit with bot UA
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Googlebot/2.1"},
            allow_redirects=False, timeout=30,
        )

        get_resp = api_get(f"/rest/v3/short-urls/{short_code}")
        summary = get_resp.json()["visitsSummary"]
        assert summary["total"] == 1
        assert summary["bots"] == 1
        assert summary["nonBots"] == 0


# ════════════════════════════════════════════════════════════════════
# L2-3: Redirect status code verification
# ════════════════════════════════════════════════════════════════════


class TestRedirectStatusCode:
    """Pattern 4: Redirect must return 302, not 200 or 301."""

    def test_redirect_returns_302_not_301(self):
        """Redirect MUST return 302 (temporary), not 301 (permanent)."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/redir302-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        redir_resp = requests.get(
            f"{BASE_URL}/{short_code}",
            allow_redirects=False,
            timeout=30,
        )
        assert redir_resp.status_code == 302, (
            f"Expected 302 redirect, got {redir_resp.status_code}"
        )
        assert redir_resp.headers.get("Location") == f"https://example.com/redir302-{UNIQUE}"

    def test_redirect_not_found_returns_404(self):
        """Non-existent short code returns 404 on redirect."""
        resp = requests.get(
            f"{BASE_URL}/nonexistent-{UNIQUE}",
            allow_redirects=False,
            timeout=30,
        )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# L2-4: Tag filtering actually works
# ════════════════════════════════════════════════════════════════════


class TestTagFiltering:
    """Pattern 3: Tag filtering must actually filter results."""

    def test_filter_by_tag_returns_only_tagged_urls(self):
        """Filtering by tag must return ONLY URLs with that tag."""
        tag_a = f"filter-a-{UNIQUE}"
        tag_b = f"filter-b-{UNIQUE}"

        # Create URL with tag_a
        resp_a = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/tag-a-{UNIQUE}",
            "tags": [tag_a],
        })
        code_a = resp_a.json()["shortCode"]

        # Create URL with tag_b
        api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/tag-b-{UNIQUE}",
            "tags": [tag_b],
        })

        # Filter by tag_a
        resp = api_get("/rest/v3/short-urls", params={"tags[]": [tag_a]})
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]

        # All results should have tag_a
        assert len(items) >= 1
        for item in items:
            assert tag_a in item["tags"], (
                f"Filtered results should only contain URLs with tag '{tag_a}'"
            )

        # URL with tag_b should NOT appear
        codes_in_result = [item["shortCode"] for item in items]
        # Verify our tag_a URL IS in the result
        assert code_a in codes_in_result

    def test_filter_by_nonexistent_tag_returns_empty(self):
        """Filtering by a tag no URL has returns empty list."""
        resp = api_get("/rest/v3/short-urls", params={
            "tags[]": [f"nonexistent-tag-{UNIQUE}"],
        })
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]
        assert len(items) == 0


# ════════════════════════════════════════════════════════════════════
# L2-5: Date range filtering on visits
# ════════════════════════════════════════════════════════════════════


class TestDateRangeFiltering:
    """Pattern 3: Date filtering must actually filter visits."""

    def test_start_date_in_future_returns_no_visits(self):
        """startDate in the future should return zero visits."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/date-filter-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Create a visit now
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Query with future startDate
        future = "2099-01-01T00:00:00Z"
        visit_resp = api_get(
            f"/rest/v3/short-urls/{short_code}/visits",
            params={"startDate": future},
        )
        assert visit_resp.status_code == 200
        visits = visit_resp.json()["visits"]["data"]
        assert len(visits) == 0, "Future startDate should filter out all past visits"

    def test_end_date_in_past_returns_no_visits(self):
        """endDate in the past should return zero visits for recent visits."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/enddate-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Create a visit now
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Query with past endDate
        past = "2000-01-01T00:00:00Z"
        visit_resp = api_get(
            f"/rest/v3/short-urls/{short_code}/visits",
            params={"endDate": past},
        )
        assert visit_resp.status_code == 200
        visits = visit_resp.json()["visits"]["data"]
        assert len(visits) == 0, "Past endDate should filter out all recent visits"


# ════════════════════════════════════════════════════════════════════
# L2-6: Short code uniqueness enforcement
# ════════════════════════════════════════════════════════════════════


class TestShortCodeUniqueness:
    """Pattern 8: Duplicate short codes must be rejected."""

    def test_duplicate_custom_slug_rejected(self):
        """Creating two short URLs with the same custom slug returns 400."""
        slug = f"dup-slug-{UNIQUE}"

        # First creation succeeds
        resp1 = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/first",
            "customSlug": slug,
        })
        assert resp1.status_code == 200
        assert resp1.json()["shortCode"] == slug

        # Second creation with same slug fails
        resp2 = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/second",
            "customSlug": slug,
        })
        assert resp2.status_code == 400, (
            f"Duplicate slug should return 400, got {resp2.status_code}"
        )

    def test_auto_generated_codes_are_unique(self):
        """Multiple auto-generated short codes are all unique."""
        codes = set()
        for i in range(5):
            resp = api_post("/rest/v3/short-urls", {
                "longUrl": f"https://example.com/auto-{UNIQUE}-{i}",
            })
            assert resp.status_code == 200
            code = resp.json()["shortCode"]
            assert code not in codes, f"Generated duplicate code: {code}"
            codes.add(code)

    def test_invalid_slug_format_rejected(self):
        """Slugs with invalid characters are rejected with 400."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/bad-slug",
            "customSlug": "invalid slug!@#$%",
        })
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# L2-7: Correct status codes
# ════════════════════════════════════════════════════════════════════


class TestStatusCodes:
    """Pattern 4: Verify correct HTTP status codes for each operation."""

    def test_create_returns_200(self):
        """POST create short URL returns 200 (not 201)."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/status-{UNIQUE}",
        })
        assert resp.status_code == 200, (
            f"Create should return 200, got {resp.status_code}"
        )

    def test_delete_returns_204(self):
        """DELETE short URL returns 204 (not 200)."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/del-status-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        del_resp = api_delete(f"/rest/v3/short-urls/{short_code}")
        assert del_resp.status_code == 204, (
            f"Delete should return 204, got {del_resp.status_code}"
        )

    def test_get_nonexistent_returns_404(self):
        """GET non-existent short code returns 404 (not 200 with empty)."""
        resp = api_get(f"/rest/v3/short-urls/does-not-exist-{UNIQUE}")
        assert resp.status_code == 404, (
            f"Non-existent should return 404, got {resp.status_code}"
        )

    def test_delete_nonexistent_returns_404(self):
        """DELETE non-existent short code returns 404."""
        resp = api_delete(f"/rest/v3/short-urls/does-not-exist-{UNIQUE}")
        assert resp.status_code == 404

    def test_tag_rename_returns_204(self):
        """PUT rename tag returns 204 (not 200)."""
        tag = f"rename-status-{UNIQUE}"
        api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/tagstatus-{UNIQUE}",
            "tags": [tag],
        })

        resp = api_put("/rest/v3/tags", {
            "oldName": tag,
            "newName": f"renamed-status-{UNIQUE}",
        })
        assert resp.status_code == 204, (
            f"Tag rename should return 204, got {resp.status_code}"
        )

    def test_tag_delete_returns_204(self):
        """DELETE tags returns 204 (not 200)."""
        tag = f"delstatus-{UNIQUE}"
        api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/tagdelstatus-{UNIQUE}",
            "tags": [tag],
        })

        resp = api_delete("/rest/v3/tags", params={"tags[]": [tag]})
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# L2-8: Custom slug vs auto-generated
# ════════════════════════════════════════════════════════════════════


class TestCustomSlugVsAutoGenerated:
    """Pattern 1+8: Custom slug behavior and auto-generation."""

    def test_custom_slug_is_used_exactly(self):
        """Custom slug appears exactly as provided in the response."""
        slug = f"my-exact-slug-{UNIQUE}"
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/custom",
            "customSlug": slug,
        })
        assert resp.status_code == 200
        assert resp.json()["shortCode"] == slug

    def test_auto_generated_slug_has_valid_format(self):
        """Auto-generated slugs are alphanumeric with minimum length."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/auto-fmt-{UNIQUE}",
        })
        assert resp.status_code == 200
        code = resp.json()["shortCode"]
        assert len(code) >= 4, f"Auto-generated code too short: '{code}'"
        # Should be alphanumeric (letters + digits)
        assert code.replace("-", "").isalnum(), f"Code contains invalid chars: '{code}'"

    def test_custom_slug_with_dashes_allowed(self):
        """Custom slugs can contain dashes."""
        slug = f"slug-with-dashes-{UNIQUE}"
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/dashes",
            "customSlug": slug,
        })
        assert resp.status_code == 200
        assert resp.json()["shortCode"] == slug


# ════════════════════════════════════════════════════════════════════
# L2-9: Analytics data computed (not hardcoded)
# ════════════════════════════════════════════════════════════════════


class TestAnalyticsComputed:
    """Pattern 5: Analytics must be computed dynamically, not hardcoded."""

    def test_global_stats_reflect_actual_visits(self):
        """Global visit stats must reflect actual visit counts."""
        # Get initial stats
        initial = api_get("/rest/v3/visits").json()["visits"]["nonOrphanVisits"]["total"]

        # Create a URL and visit it
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/globalstats-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]
        requests.get(f"{BASE_URL}/{short_code}", allow_redirects=False, timeout=30)

        # Stats should have incremented
        after = api_get("/rest/v3/visits").json()["visits"]["nonOrphanVisits"]["total"]
        assert after == initial + 1, (
            f"Global stats should increment from {initial} to {initial + 1}, got {after}"
        )

    def test_visits_list_has_actual_visit_data(self):
        """Visit records contain actual request data, not placeholder values."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/visitdata-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Visit with specific headers
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={
                "User-Agent": "SpecificTestAgent/1.0",
                "Referer": "https://specific-referrer.example.com",
            },
            allow_redirects=False, timeout=30,
        )

        # Check the visit record
        visit_resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        visits = visit_resp.json()["visits"]["data"]
        assert len(visits) >= 1

        visit = visits[0]
        assert visit["userAgent"] == "SpecificTestAgent/1.0"
        assert visit["referer"] == "https://specific-referrer.example.com"
        assert visit["date"] is not None
        assert visit["potentialBot"] is False

    def test_orphan_stats_increment_on_invalid_visit(self):
        """Orphan visit stats increment when visiting invalid short code."""
        # Get initial orphan count
        initial = api_get("/rest/v3/visits").json()["visits"]["orphanVisits"]["total"]

        # Visit non-existent code
        requests.get(
            f"{BASE_URL}/orphan-stats-{UNIQUE}",
            allow_redirects=False, timeout=30,
        )

        # Orphan stats should increment
        after = api_get("/rest/v3/visits").json()["visits"]["orphanVisits"]["total"]
        assert after == initial + 1, (
            f"Orphan stats should increment from {initial} to {initial + 1}, got {after}"
        )


# ════════════════════════════════════════════════════════════════════
# L2-10: Pagination structure
# ════════════════════════════════════════════════════════════════════


class TestPaginationStructure:
    """Pattern 1+3: Pagination fields correct and functional."""

    def test_pagination_has_all_required_fields(self):
        """Pagination object has all camelCase fields."""
        resp = api_get("/rest/v3/short-urls", params={"page": 1, "itemsPerPage": 5})
        assert resp.status_code == 200
        pagination = resp.json()["shortUrls"]["pagination"]

        required = ["currentPage", "pagesCount", "itemsPerPage", "itemsInCurrentPage", "totalItems"]
        for field in required:
            assert field in pagination, f"Missing pagination field '{field}'"

        # Check types
        assert isinstance(pagination["currentPage"], int)
        assert isinstance(pagination["pagesCount"], int)
        assert isinstance(pagination["itemsPerPage"], int)
        assert isinstance(pagination["itemsInCurrentPage"], int)
        assert isinstance(pagination["totalItems"], int)

    def test_items_per_page_respected(self):
        """itemsPerPage limits the number of results returned."""
        # Create at least 3 URLs
        for i in range(3):
            api_post("/rest/v3/short-urls", {
                "longUrl": f"https://example.com/pag-{UNIQUE}-{i}",
            })

        resp = api_get("/rest/v3/short-urls", params={"itemsPerPage": 2})
        assert resp.status_code == 200
        data = resp.json()["shortUrls"]
        assert len(data["data"]) <= 2
        assert data["pagination"]["itemsPerPage"] == 2


# ════════════════════════════════════════════════════════════════════
# L2-11: Order by actually works
# ════════════════════════════════════════════════════════════════════


class TestOrderBy:
    """Pattern 3: OrderBy parameter must actually change result order."""

    def test_order_by_short_code_asc(self):
        """orderBy=shortCode-ASC returns codes in ascending order."""
        # Create URLs with specific slugs
        slugs = [f"zzz-order-{UNIQUE}", f"aaa-order-{UNIQUE}", f"mmm-order-{UNIQUE}"]
        for slug in slugs:
            api_post("/rest/v3/short-urls", {
                "longUrl": f"https://example.com/{slug}",
                "customSlug": slug,
            })

        resp = api_get("/rest/v3/short-urls", params={
            "orderBy": "shortCode-ASC",
            "searchTerm": f"order-{UNIQUE}",
        })
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]

        codes = [item["shortCode"] for item in items]
        assert codes == sorted(codes), (
            f"Should be sorted ASC: {codes}"
        )

    def test_order_by_short_code_desc(self):
        """orderBy=shortCode-DESC returns codes in descending order."""
        slugs = [
            f"zzz-desc-order-{UNIQUE}",
            f"aaa-desc-order-{UNIQUE}",
            f"mmm-desc-order-{UNIQUE}",
        ]
        for slug in slugs:
            api_post("/rest/v3/short-urls", {
                "longUrl": f"https://example.com/{slug}",
                "customSlug": slug,
            })

        resp = api_get("/rest/v3/short-urls", params={
            "orderBy": "shortCode-DESC",
            "searchTerm": f"desc-order-{UNIQUE}",
        })
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]

        if len(items) >= 2:
            codes = [item["shortCode"] for item in items]
            assert codes == sorted(codes, reverse=True), (
                f"Should be sorted DESC: {codes}"
            )


# ════════════════════════════════════════════════════════════════════
# L2-12: Exclude bots filter
# ════════════════════════════════════════════════════════════════════


class TestExcludeBotsFilter:
    """Pattern 3: excludeBots parameter must actually filter results."""

    def test_exclude_bots_removes_bot_visits(self):
        """excludeBots=true must remove visits with potentialBot=true."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/excbot-{UNIQUE}",
        })
        short_code = resp.json()["shortCode"]

        # Visit as bot
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Googlebot/2.1 crawler"},
            allow_redirects=False, timeout=30,
        )
        # Visit as human
        requests.get(
            f"{BASE_URL}/{short_code}",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh)"},
            allow_redirects=False, timeout=30,
        )

        # Without filter: should have both
        all_visits = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert len(all_visits.json()["visits"]["data"]) == 2

        # With excludeBots: should have only human visit
        filtered = api_get(
            f"/rest/v3/short-urls/{short_code}/visits",
            params={"excludeBots": "true"},
        )
        filtered_visits = filtered.json()["visits"]["data"]
        assert len(filtered_visits) == 1
        assert filtered_visits[0]["potentialBot"] is False
