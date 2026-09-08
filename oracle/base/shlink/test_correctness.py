"""
BackendForge — Comprehensive Correctness Tests for Shlink Task

Tests all business rules and endpoint groups for the Shlink URL shortener.
"""

import os
import uuid
import datetime
from datetime import timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-12345"

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


# ── Domain Helpers ──

def create_short_url(long_url, **kwargs):
    """POST /rest/v3/short-urls → returns ShortUrl dict."""
    data = {"longUrl": long_url, **kwargs}
    resp = api_post("/rest/v3/short-urls", data)
    assert resp.status_code == 200, f"Create short URL failed: {resp.status_code} {resp.text}"
    return resp.json()


def get_short_url(short_code, domain=None):
    """GET /rest/v3/short-urls/{shortCode} → ShortUrl dict."""
    params = {"domain": domain} if domain else None
    resp = api_get(f"/rest/v3/short-urls/{short_code}", params=params)
    assert resp.status_code == 200, f"Get short URL failed: {resp.status_code} {resp.text}"
    return resp.json()


def visit_short_url(short_code, user_agent="Mozilla/5.0", referer="https://example.com"):
    """GET /{shortCode} — perform redirect (no auth)."""
    resp = requests.get(
        f"{BASE_URL}/{short_code}",
        headers={"User-Agent": user_agent, "Referer": referer},
        allow_redirects=False,
        timeout=30,
    )
    return resp


# ════════════════════════════════════════════════════════════════════
# PART 1: Health + Authentication
# ════════════════════════════════════════════════════════════════════


class TestHealth:
    """Health endpoint should work without auth."""

    def test_health_returns_pass(self):
        resp = requests.get(f"{BASE_URL}/rest/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pass"
        assert "version" in data
        assert "links" in data


class TestAuthentication:
    """Requests without API key should return 401."""

    def test_missing_api_key_on_short_urls(self):
        resp = requests.get(f"{BASE_URL}/rest/v3/short-urls", timeout=30)
        assert resp.status_code == 401, f"Expected 401 without API key, got {resp.status_code}"

    def test_missing_api_key_on_tags(self):
        resp = requests.get(f"{BASE_URL}/rest/v3/tags", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_on_visits(self):
        resp = requests.get(f"{BASE_URL}/rest/v3/visits", timeout=30)
        assert resp.status_code == 401

    def test_missing_api_key_on_domains(self):
        resp = requests.get(f"{BASE_URL}/rest/v3/domains", timeout=30)
        assert resp.status_code == 401

    def test_redirect_does_not_require_auth(self):
        """GET /{shortCode} is public — no auth needed (even if 404)."""
        resp = requests.get(
            f"{BASE_URL}/nonexistent-code-xyz", allow_redirects=False, timeout=30
        )
        # Should be 404 (not found), not 401 (unauthorized)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 2: Short URL CRUD
# ════════════════════════════════════════════════════════════════════


class TestShortUrlCRUD:
    """Create → read → update → delete short URLs."""

    def test_create_short_url_basic(self):
        """Create a short URL with just a long URL."""
        url = create_short_url(f"https://example.com/{UNIQUE}")
        assert url["longUrl"] == f"https://example.com/{UNIQUE}"
        assert url["shortCode"] is not None
        assert len(url["shortCode"]) >= 4
        assert url["shortUrl"] is not None
        assert url["dateCreated"] is not None
        assert url["tags"] == []
        assert url["meta"]["validSince"] is None
        assert url["meta"]["validUntil"] is None
        assert url["meta"]["maxVisits"] is None
        assert url["crawlable"] is False
        assert url["forwardQuery"] is True

    def test_create_short_url_with_custom_slug(self):
        """Create with a custom slug."""
        slug = f"my-custom-{UNIQUE}"
        url = create_short_url(f"https://example.com/custom-{UNIQUE}", customSlug=slug)
        assert url["shortCode"] == slug

    def test_create_short_url_with_tags(self):
        """Create with tags."""
        tags = [f"tag-a-{UNIQUE}", f"tag-b-{UNIQUE}"]
        url = create_short_url(f"https://example.com/tagged-{UNIQUE}", tags=tags)
        assert sorted(url["tags"]) == sorted(tags)

    def test_create_short_url_with_meta(self):
        """Create with maxVisits and valid dates."""
        url = create_short_url(
            f"https://example.com/meta-{UNIQUE}",
            maxVisits=100,
            validSince="2020-01-01T00:00:00Z",
            validUntil="2099-12-31T23:59:59Z",
            title="Test Title",
        )
        assert url["meta"]["maxVisits"] == 100
        assert url["meta"]["validSince"] is not None
        assert url["meta"]["validUntil"] is not None
        assert url["title"] == "Test Title"

    def test_get_short_url(self):
        """Read a short URL by short code."""
        created = create_short_url(f"https://example.com/get-{UNIQUE}")
        fetched = get_short_url(created["shortCode"])
        assert fetched["shortCode"] == created["shortCode"]
        assert fetched["longUrl"] == created["longUrl"]

    def test_edit_short_url(self):
        """Patch a short URL to update its metadata."""
        created = create_short_url(f"https://example.com/edit-{UNIQUE}")
        short_code = created["shortCode"]

        resp = api_patch(f"/rest/v3/short-urls/{short_code}", {
            "title": "Updated Title",
            "maxVisits": 50,
            "tags": [f"new-tag-{UNIQUE}"],
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated Title"
        assert updated["meta"]["maxVisits"] == 50
        assert f"new-tag-{UNIQUE}" in updated["tags"]

    def test_delete_short_url(self):
        """Delete a short URL."""
        created = create_short_url(f"https://example.com/delete-{UNIQUE}")
        short_code = created["shortCode"]

        resp = api_delete(f"/rest/v3/short-urls/{short_code}")
        assert resp.status_code == 204

        # Should be gone
        resp = api_get(f"/rest/v3/short-urls/{short_code}")
        assert resp.status_code == 404

    def test_get_nonexistent_returns_404(self):
        """Getting a non-existent short code returns 404."""
        resp = api_get("/rest/v3/short-urls/absolutely-nonexistent-zzz")
        assert resp.status_code == 404

    def test_visits_summary_starts_at_zero(self):
        """A new short URL should have zero visits."""
        url = create_short_url(f"https://example.com/zero-{UNIQUE}")
        assert url["visitsSummary"]["total"] == 0
        assert url["visitsSummary"]["nonBots"] == 0
        assert url["visitsSummary"]["bots"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 3: Redirect + Visit Tracking
# ════════════════════════════════════════════════════════════════════


class TestRedirectAndVisitTracking:
    """Redirect behavior and visit recording."""

    def test_redirect_returns_302(self):
        """Visiting a short URL returns 302 with Location header."""
        long_url = f"https://example.com/redirect-{UNIQUE}"
        url = create_short_url(long_url)
        resp = visit_short_url(url["shortCode"])
        assert resp.status_code == 302
        assert resp.headers.get("Location") == long_url

    def test_visit_is_recorded(self):
        """After visiting, the visit count increments."""
        url = create_short_url(f"https://example.com/visit-track-{UNIQUE}")
        short_code = url["shortCode"]

        visit_short_url(short_code)

        # Check visits
        updated = get_short_url(short_code)
        assert updated["visitsSummary"]["total"] >= 1

    def test_visit_details_recorded(self):
        """Visit records referer, userAgent, date, potentialBot."""
        url = create_short_url(f"https://example.com/visit-detail-{UNIQUE}")
        short_code = url["shortCode"]

        visit_short_url(short_code, user_agent="TestBrowser/1.0", referer="https://referrer.com")

        # Get visits
        resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        assert resp.status_code == 200
        visits_data = resp.json()["visits"]["data"]
        assert len(visits_data) >= 1

        visit = visits_data[0]
        assert visit["userAgent"] == "TestBrowser/1.0"
        assert visit["referer"] == "https://referrer.com"
        assert visit["date"] is not None
        assert visit["potentialBot"] is False

    def test_bot_detection(self):
        """Visit with bot user-agent is flagged as potentialBot."""
        url = create_short_url(f"https://example.com/bot-{UNIQUE}")
        short_code = url["shortCode"]

        visit_short_url(short_code, user_agent="Googlebot/2.1")

        resp = api_get(f"/rest/v3/short-urls/{short_code}/visits")
        visits_data = resp.json()["visits"]["data"]
        assert len(visits_data) >= 1

        bot_visits = [v for v in visits_data if v["potentialBot"] is True]
        assert len(bot_visits) >= 1, "Googlebot should be detected as potentialBot"

    def test_bot_counted_in_bots_summary(self):
        """Bot visits increment the 'bots' counter in visitsSummary."""
        url = create_short_url(f"https://example.com/bot-count-{UNIQUE}")
        short_code = url["shortCode"]

        visit_short_url(short_code, user_agent="Spider/1.0 crawler")

        updated = get_short_url(short_code)
        assert updated["visitsSummary"]["bots"] >= 1
        assert updated["visitsSummary"]["total"] >= 1

    def test_multiple_visits_counted(self):
        """Multiple visits are all counted."""
        url = create_short_url(f"https://example.com/multi-{UNIQUE}")
        short_code = url["shortCode"]

        for _ in range(3):
            visit_short_url(short_code)

        updated = get_short_url(short_code)
        assert updated["visitsSummary"]["total"] >= 3

    def test_nonexistent_short_code_returns_404(self):
        """Visiting a non-existent short code returns 404."""
        resp = requests.get(
            f"{BASE_URL}/totally-fake-{UNIQUE}",
            allow_redirects=False,
            timeout=30,
        )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Max Visits Enforcement
# ════════════════════════════════════════════════════════════════════


class TestMaxVisits:
    """Rule 4: After maxVisits is reached, redirect returns 404."""

    def test_max_visits_enforced(self):
        """Short URL with maxVisits=2: after 2 visits, 3rd returns 404."""
        url = create_short_url(
            f"https://example.com/max-{UNIQUE}",
            maxVisits=2,
        )
        short_code = url["shortCode"]

        # First 2 visits succeed
        resp1 = visit_short_url(short_code)
        assert resp1.status_code == 302, f"Visit 1 should succeed, got {resp1.status_code}"

        resp2 = visit_short_url(short_code)
        assert resp2.status_code == 302, f"Visit 2 should succeed, got {resp2.status_code}"

        # 3rd visit should fail
        resp3 = visit_short_url(short_code)
        assert resp3.status_code == 404, (
            f"Visit 3 should return 404 (max visits reached), got {resp3.status_code}"
        )

    def test_max_visits_url_still_accessible_via_api(self):
        """Even after max visits, the short URL is still visible via API."""
        url = create_short_url(
            f"https://example.com/max-api-{UNIQUE}",
            maxVisits=1,
        )
        short_code = url["shortCode"]

        visit_short_url(short_code)  # Use up the 1 visit

        # API should still return it
        fetched = get_short_url(short_code)
        assert fetched["shortCode"] == short_code
        assert fetched["meta"]["maxVisits"] == 1


# ════════════════════════════════════════════════════════════════════
# PART 5: Valid Date Range Enforcement
# ════════════════════════════════════════════════════════════════════


class TestValidDateRange:
    """Rule 5: validSince/validUntil restrict redirect availability."""

    def test_valid_since_in_future_returns_404(self):
        """Short URL with validSince in the future: redirect returns 404."""
        future = (datetime.datetime.now(timezone.utc) + datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = create_short_url(
            f"https://example.com/future-{UNIQUE}",
            validSince=future,
        )
        short_code = url["shortCode"]

        resp = visit_short_url(short_code)
        assert resp.status_code == 404, (
            f"Redirect before validSince should return 404, got {resp.status_code}"
        )

    def test_valid_until_in_past_returns_404(self):
        """Short URL with validUntil in the past: redirect returns 404."""
        past = (datetime.datetime.now(timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = create_short_url(
            f"https://example.com/past-{UNIQUE}",
            validUntil=past,
        )
        short_code = url["shortCode"]

        resp = visit_short_url(short_code)
        assert resp.status_code == 404, (
            f"Redirect after validUntil should return 404, got {resp.status_code}"
        )

    def test_valid_range_within_bounds_succeeds(self):
        """Short URL within valid range: redirect succeeds."""
        past = (datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future = (datetime.datetime.now(timezone.utc) + datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = create_short_url(
            f"https://example.com/inrange-{UNIQUE}",
            validSince=past,
            validUntil=future,
        )
        short_code = url["shortCode"]

        resp = visit_short_url(short_code)
        assert resp.status_code == 302, (
            f"Redirect within valid range should return 302, got {resp.status_code}"
        )

    def test_expired_url_still_in_api(self):
        """Even after expiry, short URL is visible via API."""
        past = (datetime.datetime.now(timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = create_short_url(
            f"https://example.com/expired-api-{UNIQUE}",
            validUntil=past,
        )
        short_code = url["shortCode"]

        fetched = get_short_url(short_code)
        assert fetched["shortCode"] == short_code


# ════════════════════════════════════════════════════════════════════
# PART 6: Custom Slug Validation
# ════════════════════════════════════════════════════════════════════


class TestCustomSlugValidation:
    """Rule 2: Custom slug validation + Rule 1: Uniqueness."""

    def test_invalid_slug_rejected(self):
        """Slug with special characters is rejected."""
        resp = api_post("/rest/v3/short-urls", {
            "longUrl": "https://example.com/bad-slug",
            "customSlug": "has spaces!@#",
        })
        assert resp.status_code == 400, (
            f"Invalid slug should return 400, got {resp.status_code}"
        )

    def test_duplicate_slug_rejected(self):
        """Creating a second short URL with the same custom slug fails."""
        slug = f"unique-slug-{UNIQUE}"
        create_short_url(f"https://example.com/first-{UNIQUE}", customSlug=slug)

        resp = api_post("/rest/v3/short-urls", {
            "longUrl": f"https://example.com/second-{UNIQUE}",
            "customSlug": slug,
        })
        assert resp.status_code == 400, (
            f"Duplicate slug should return 400, got {resp.status_code}"
        )

    def test_valid_slug_with_dashes(self):
        """Slug with alphanumeric and dashes is valid."""
        slug = f"valid-slug-123-{UNIQUE}"
        url = create_short_url(f"https://example.com/valid-{UNIQUE}", customSlug=slug)
        assert url["shortCode"] == slug

    def test_short_code_length_default(self):
        """Generated short code has reasonable default length (>= 4)."""
        url = create_short_url(
            f"https://example.com/len-{UNIQUE}",
        )
        assert len(url["shortCode"]) >= 4


# ════════════════════════════════════════════════════════════════════
# PART 7: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTagsCRUD:
    """Tag listing, renaming, and deletion."""

    def test_tags_created_via_short_url(self):
        """Tags are created when attached to short URLs."""
        tag = f"auto-tag-{UNIQUE}"
        create_short_url(f"https://example.com/tag-create-{UNIQUE}", tags=[tag])

        resp = api_get("/rest/v3/tags")
        assert resp.status_code == 200
        tags_data = resp.json()["tags"]["data"]
        assert tag in tags_data, f"Tag '{tag}' should appear in tags list"

    def test_rename_tag(self):
        """Rename a tag and verify it updates everywhere."""
        old_name = f"old-tag-{UNIQUE}"
        new_name = f"renamed-tag-{UNIQUE}"
        url = create_short_url(f"https://example.com/rename-{UNIQUE}", tags=[old_name])

        resp = api_put("/rest/v3/tags", {"oldName": old_name, "newName": new_name})
        assert resp.status_code == 204

        # Short URL should now have new tag name
        fetched = get_short_url(url["shortCode"])
        assert new_name in fetched["tags"], f"Expected '{new_name}' in tags, got {fetched['tags']}"
        assert old_name not in fetched["tags"], f"Old tag name '{old_name}' should be gone"

    def test_delete_tags(self):
        """Delete a tag removes it from all short URLs."""
        tag = f"deleteme-{UNIQUE}"
        url = create_short_url(f"https://example.com/tagdel-{UNIQUE}", tags=[tag])

        resp = api_delete("/rest/v3/tags", params={"tags[]": [tag]})
        assert resp.status_code == 204

        # Tag should be gone from the short URL
        fetched = get_short_url(url["shortCode"])
        assert tag not in fetched["tags"], f"Deleted tag '{tag}' should be removed"

    def test_tags_with_stats(self):
        """Tags stats endpoint returns shortUrlsCount and visitsSummary."""
        tag = f"stats-tag-{UNIQUE}"
        url = create_short_url(f"https://example.com/tagstat-{UNIQUE}", tags=[tag])
        visit_short_url(url["shortCode"])

        resp = api_get("/rest/v3/tags/stats")
        assert resp.status_code == 200
        tags_data = resp.json()["tags"]["data"]
        matching = [t for t in tags_data if t["tag"] == tag]
        assert len(matching) == 1, f"Tag '{tag}' should appear in stats"
        assert matching[0]["shortUrlsCount"] >= 1
        assert matching[0]["visitsSummary"]["total"] >= 1

    def test_rename_nonexistent_tag_returns_404(self):
        """Renaming a tag that doesn't exist returns 404."""
        resp = api_put("/rest/v3/tags", {
            "oldName": f"nonexistent-{UNIQUE}",
            "newName": f"something-{UNIQUE}",
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Visits Endpoints
# ════════════════════════════════════════════════════════════════════


class TestVisitsEndpoints:
    """Visit listing and filtering."""

    def test_short_url_visits_list(self):
        """GET /rest/v3/short-urls/{shortCode}/visits returns visits."""
        url = create_short_url(f"https://example.com/vlist-{UNIQUE}")
        visit_short_url(url["shortCode"])

        resp = api_get(f"/rest/v3/short-urls/{url['shortCode']}/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "data" in data["visits"]
        assert "pagination" in data["visits"]
        assert len(data["visits"]["data"]) >= 1

    def test_visits_pagination(self):
        """Visits support pagination."""
        url = create_short_url(f"https://example.com/vpag-{UNIQUE}")
        for _ in range(3):
            visit_short_url(url["shortCode"])

        resp = api_get(f"/rest/v3/short-urls/{url['shortCode']}/visits", params={
            "page": 1, "itemsPerPage": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        pagination = data["visits"]["pagination"]
        assert pagination["itemsPerPage"] == 2
        assert pagination["currentPage"] == 1
        assert len(data["visits"]["data"]) <= 2

    def test_visits_date_filter(self):
        """Visits can be filtered by date range."""
        url = create_short_url(f"https://example.com/vdate-{UNIQUE}")
        visit_short_url(url["shortCode"])

        # Filter with future startDate should return 0 visits
        future = (datetime.datetime.now(timezone.utc) + datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = api_get(f"/rest/v3/short-urls/{url['shortCode']}/visits", params={
            "startDate": future,
        })
        assert resp.status_code == 200
        assert len(resp.json()["visits"]["data"]) == 0

    def test_visits_exclude_bots(self):
        """excludeBots=true filters out bot visits."""
        url = create_short_url(f"https://example.com/vbot-{UNIQUE}")
        visit_short_url(url["shortCode"], user_agent="Googlebot/2.1")
        visit_short_url(url["shortCode"], user_agent="Mozilla/5.0 (normal)")

        resp = api_get(f"/rest/v3/short-urls/{url['shortCode']}/visits", params={
            "excludeBots": "true",
        })
        assert resp.status_code == 200
        visits = resp.json()["visits"]["data"]
        # Should exclude the bot visit
        for v in visits:
            assert v["potentialBot"] is False, "excludeBots should filter out bot visits"

    def test_global_visits_stats(self):
        """GET /rest/v3/visits returns global stats."""
        resp = api_get("/rest/v3/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "nonOrphanVisits" in data["visits"]
        assert "orphanVisits" in data["visits"]
        assert "total" in data["visits"]["nonOrphanVisits"]
        assert "nonBots" in data["visits"]["nonOrphanVisits"]
        assert "bots" in data["visits"]["nonOrphanVisits"]

    def test_non_orphan_visits_list(self):
        """GET /rest/v3/visits/non-orphan returns visit list."""
        url = create_short_url(f"https://example.com/nonorph-{UNIQUE}")
        visit_short_url(url["shortCode"])

        resp = api_get("/rest/v3/visits/non-orphan")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "data" in data["visits"]
        assert "pagination" in data["visits"]

    def test_orphan_visits_recorded(self):
        """Visiting invalid short code records an orphan visit."""
        invalid_code = f"orphan-{UNIQUE}"
        requests.get(
            f"{BASE_URL}/{invalid_code}",
            allow_redirects=False,
            timeout=30,
        )

        resp = api_get("/rest/v3/visits/orphan")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "data" in data["visits"]
        # Should have at least one orphan visit
        assert len(data["visits"]["data"]) >= 1

    def test_tag_visits(self):
        """GET /rest/v3/tags/{tag}/visits returns visits for tagged URLs."""
        tag = f"visit-tag-{UNIQUE}"
        url = create_short_url(f"https://example.com/tagvisit-{UNIQUE}", tags=[tag])
        visit_short_url(url["shortCode"])

        resp = api_get(f"/rest/v3/tags/{tag}/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert len(data["visits"]["data"]) >= 1

    def test_nonexistent_short_url_visits_returns_404(self):
        """Getting visits for non-existent short code returns 404."""
        resp = api_get("/rest/v3/short-urls/nonexistent-zzz/visits")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Domains
# ════════════════════════════════════════════════════════════════════


class TestDomains:
    """Domain listing and redirect configuration."""

    def test_list_domains(self):
        """GET /rest/v3/domains returns domain list."""
        resp = api_get("/rest/v3/domains")
        assert resp.status_code == 200
        data = resp.json()
        assert "domains" in data
        assert "data" in data["domains"]
        assert "defaultRedirects" in data["domains"]

    def test_set_domain_redirects(self):
        """PATCH /rest/v3/domains/redirects sets redirects for a domain."""
        domain = f"test-{UNIQUE}.example.com"
        resp = api_patch("/rest/v3/domains/redirects", {
            "domain": domain,
            "baseUrlRedirect": "https://example.com/home",
            "regular404Redirect": "https://example.com/404",
            "invalidShortUrlRedirect": "https://example.com/invalid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["baseUrlRedirect"] == "https://example.com/home"
        assert data["regular404Redirect"] == "https://example.com/404"
        assert data["invalidShortUrlRedirect"] == "https://example.com/invalid"

    def test_domain_visits(self):
        """GET /rest/v3/domains/{domain}/visits returns visit data."""
        resp = api_get("/rest/v3/domains/DEFAULT/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "data" in data["visits"]
        assert "pagination" in data["visits"]


# ════════════════════════════════════════════════════════════════════
# PART 11: Short URL Listing + Pagination
# ════════════════════════════════════════════════════════════════════


class TestShortUrlListing:
    """Listing, pagination, search, and ordering."""

    def test_list_short_urls_pagination(self):
        """List endpoint supports pagination."""
        # Create a few URLs
        for i in range(3):
            create_short_url(f"https://example.com/list-{UNIQUE}-{i}")

        resp = api_get("/rest/v3/short-urls", params={"page": 1, "itemsPerPage": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert "shortUrls" in data
        assert "data" in data["shortUrls"]
        assert "pagination" in data["shortUrls"]
        assert len(data["shortUrls"]["data"]) <= 2
        pagination = data["shortUrls"]["pagination"]
        assert pagination["currentPage"] == 1
        assert pagination["itemsPerPage"] == 2

    def test_pagination_fields_consistent(self):
        """Pagination totalItems and pagesCount are consistent."""
        resp = api_get("/rest/v3/short-urls", params={"page": 1, "itemsPerPage": 5})
        assert resp.status_code == 200
        pagination = resp.json()["shortUrls"]["pagination"]
        total = pagination["totalItems"]
        pages = pagination["pagesCount"]
        per_page = pagination["itemsPerPage"]
        if total > 0:
            expected_pages = (total + per_page - 1) // per_page
            assert pages == expected_pages, (
                f"pagesCount={pages} but expected {expected_pages} "
                f"(totalItems={total}, itemsPerPage={per_page})"
            )

    def test_search_term_filter(self):
        """searchTerm filters by long URL and short code."""
        unique_str = f"searchable-{UNIQUE}"
        create_short_url(f"https://example.com/{unique_str}")

        resp = api_get("/rest/v3/short-urls", params={"searchTerm": unique_str})
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]
        assert len(items) >= 1
        # All results should match the search term
        for item in items:
            found = unique_str in item["longUrl"] or unique_str in item["shortCode"]
            assert found, f"Item doesn't match search term: {item['longUrl']}, {item['shortCode']}"

    def test_filter_by_tags(self):
        """tags[] filter returns only short URLs with those tags."""
        tag = f"filter-tag-{UNIQUE}"
        create_short_url(f"https://example.com/tagged-filter-{UNIQUE}", tags=[tag])
        create_short_url(f"https://example.com/untagged-filter-{UNIQUE}")

        resp = api_get("/rest/v3/short-urls", params={"tags[]": [tag]})
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]
        assert len(items) >= 1
        for item in items:
            assert tag in item["tags"], f"Item should have tag '{tag}', has {item['tags']}"

    def test_order_by_date_created(self):
        """orderBy=dateCreated-DESC returns newest first."""
        for i in range(2):
            create_short_url(f"https://example.com/date-order-{UNIQUE}-{i}")

        resp = api_get("/rest/v3/short-urls", params={
            "orderBy": "dateCreated-DESC", "itemsPerPage": 10,
        })
        assert resp.status_code == 200
        items = resp.json()["shortUrls"]["data"]
        if len(items) >= 2:
            dates = [item["dateCreated"] for item in items]
            assert dates == sorted(dates, reverse=True), (
                f"Should be sorted by dateCreated DESC: {dates}"
            )


# ════════════════════════════════════════════════════════════════════
# PART 12: findIfExists
# ════════════════════════════════════════════════════════════════════


class TestFindIfExists:
    """Rule 10: findIfExists returns existing URL instead of creating new."""

    def test_find_if_exists_returns_existing(self):
        """With findIfExists=true and same longUrl, returns existing short URL."""
        long_url = f"https://example.com/findexist-{UNIQUE}"
        first = create_short_url(long_url)

        second = create_short_url(long_url, findIfExists=True)
        assert second["shortCode"] == first["shortCode"], (
            "findIfExists should return the existing short URL"
        )

    def test_find_if_exists_false_creates_new(self):
        """Without findIfExists (default false), a new short URL is created."""
        long_url = f"https://example.com/nofind-{UNIQUE}"
        first = create_short_url(long_url)
        second = create_short_url(long_url)
        assert second["shortCode"] != first["shortCode"], (
            "Without findIfExists, should create a new short URL"
        )


# ════════════════════════════════════════════════════════════════════
# PART 13: Tag Sharing / Reuse
# ════════════════════════════════════════════════════════════════════


class TestTagReuse:
    """Rule 8: Tags are shared across short URLs."""

    def test_same_tag_shared(self):
        """Two short URLs with same tag → tag appears once in listing."""
        tag = f"shared-{UNIQUE}"
        create_short_url(f"https://example.com/share1-{UNIQUE}", tags=[tag])
        create_short_url(f"https://example.com/share2-{UNIQUE}", tags=[tag])

        resp = api_get("/rest/v3/tags")
        tags_data = resp.json()["tags"]["data"]
        count = tags_data.count(tag)
        assert count == 1, f"Tag '{tag}' should appear exactly once, got {count}"

    def test_tag_stats_counts_multiple_urls(self):
        """Tag stats counts both short URLs that use it."""
        tag = f"multi-{UNIQUE}"
        create_short_url(f"https://example.com/multi1-{UNIQUE}", tags=[tag])
        create_short_url(f"https://example.com/multi2-{UNIQUE}", tags=[tag])

        resp = api_get("/rest/v3/tags/stats")
        tags_data = resp.json()["tags"]["data"]
        matching = [t for t in tags_data if t["tag"] == tag]
        assert len(matching) == 1
        assert matching[0]["shortUrlsCount"] >= 2


# ════════════════════════════════════════════════════════════════════
# PART 14: Orphan Visit Types
# ════════════════════════════════════════════════════════════════════


class TestOrphanVisitTypes:
    """Rule 7: Orphan visits have a type field."""

    def test_invalid_short_url_orphan_type(self):
        """Visiting invalid short code creates orphan with type=invalid_short_url."""
        code = f"invalid-{UNIQUE}"
        requests.get(f"{BASE_URL}/{code}", allow_redirects=False, timeout=30)

        resp = api_get("/rest/v3/visits/orphan")
        data = resp.json()["visits"]["data"]
        invalid_visits = [v for v in data if v.get("type") == "invalid_short_url"]
        assert len(invalid_visits) >= 1, "Should have at least one invalid_short_url orphan visit"

    def test_orphan_filter_by_type(self):
        """Orphan visits can be filtered by type."""
        code = f"typefilt-{UNIQUE}"
        requests.get(f"{BASE_URL}/{code}", allow_redirects=False, timeout=30)

        resp = api_get("/rest/v3/visits/orphan", params={"type": "invalid_short_url"})
        assert resp.status_code == 200
        data = resp.json()["visits"]["data"]
        for visit in data:
            assert visit.get("type") == "invalid_short_url", (
                f"Filtered orphan should be invalid_short_url, got {visit.get('type')}"
            )


# ════════════════════════════════════════════════════════════════════
# PART 15: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Various edge cases and error handling."""

    def test_edit_nonexistent_returns_404(self):
        """PATCH on non-existent short code returns 404."""
        resp = api_patch("/rest/v3/short-urls/nonexistent-zzz", {"title": "test"})
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self):
        """DELETE on non-existent short code returns 404."""
        resp = api_delete("/rest/v3/short-urls/nonexistent-zzz")
        assert resp.status_code == 404

    def test_create_without_long_url_fails(self):
        """Creating without longUrl returns 400."""
        resp = api_post("/rest/v3/short-urls", {"title": "no url"})
        assert resp.status_code == 400

    def test_edit_long_url(self):
        """Can change the long URL of a short URL."""
        url = create_short_url(f"https://example.com/original-{UNIQUE}")
        new_long = f"https://example.com/changed-{UNIQUE}"
        resp = api_patch(f"/rest/v3/short-urls/{url['shortCode']}", {"longUrl": new_long})
        assert resp.status_code == 200
        assert resp.json()["longUrl"] == new_long

        # Redirect should now go to new URL
        resp = visit_short_url(url["shortCode"])
        assert resp.status_code == 302
        assert resp.headers.get("Location") == new_long

    def test_crawlable_flag(self):
        """crawlable flag is stored and returned correctly."""
        url = create_short_url(
            f"https://example.com/crawl-{UNIQUE}", crawlable=True
        )
        assert url["crawlable"] is True

        fetched = get_short_url(url["shortCode"])
        assert fetched["crawlable"] is True

    def test_forward_query_default_true(self):
        """forwardQuery defaults to true."""
        url = create_short_url(f"https://example.com/fq-{UNIQUE}")
        assert url["forwardQuery"] is True

    def test_short_url_contains_short_code(self):
        """shortUrl field contains the shortCode."""
        url = create_short_url(f"https://example.com/contains-{UNIQUE}")
        assert url["shortCode"] in url["shortUrl"]

    def test_tags_search_filter(self):
        """Tag listing supports searchTerm filter."""
        tag = f"searchable-tag-{UNIQUE}"
        create_short_url(f"https://example.com/tagsearch-{UNIQUE}", tags=[tag])

        resp = api_get("/rest/v3/tags", params={"searchTerm": tag})
        assert resp.status_code == 200
        tags_data = resp.json()["tags"]["data"]
        assert tag in tags_data
