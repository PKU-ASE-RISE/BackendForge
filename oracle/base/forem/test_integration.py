"""
BackendForge — L2 Integration Tests for Forem Developer Community Platform
Adversarial tests targeting common LLM implementation bugs.
"""

import os
import uuid
import math
import time

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def unique():
    return uuid.uuid4().hex[:8]


def headers(user_id=None):
    uid = user_id or str(uuid.uuid4())
    return {"X-User-Id": uid, "Content-Type": "application/json"}


def post(path, json_data, h):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=h, timeout=30)


def get(path, h=None, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=h or {}, timeout=30)


def put(path, json_data, h):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=h, timeout=30)


def delete(path, h):
    return requests.delete(f"{BASE_URL}{path}", headers=h, timeout=30)


class TestArticleFieldsAndComputedValues:
    """Pattern 1+5: Verify all article fields and computed values."""

    def test_article_create_returns_all_required_fields(self):
        h = headers()
        uid = h["X-User-Id"]
        title = f"My Article {unique()}"
        body = "This is the body with exactly ten words for reading time"
        r = post("/articles", {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": ["python", "webdev"],
            "description": "A test article"
        }, h)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == title
        assert data["body_markdown"] == body
        assert data["published"] is True
        assert "python" in data["tags"]
        assert "webdev" in data["tags"]
        assert data["description"] == "A test article"
        assert data["user_id"] == uid
        assert "id" in data
        assert "slug" in data
        assert "created_at" in data
        assert "reading_time" in data
        assert "reactions_count" in data
        assert "comments_count" in data
        assert "score" in data
        assert data["reactions_count"] == 0
        assert data["comments_count"] == 0
        assert data["score"] == 0
        assert data["published_at"] is not None

    def test_reading_time_computed_correctly(self):
        """reading_time = ceil(word_count / 200), min 1."""
        h = headers()
        # 400 words -> reading_time = 2
        body_400 = " ".join(["word"] * 400)
        r = post("/articles", {"title": f"RT400-{unique()}", "body_markdown": body_400, "published": True}, h)
        assert r.status_code == 201
        assert r.json()["reading_time"] == 2

        # 1 word -> reading_time = 1 (minimum)
        r2 = post("/articles", {"title": f"RT1-{unique()}", "body_markdown": "hello", "published": True}, h)
        assert r2.status_code == 201
        assert r2.json()["reading_time"] == 1

        # 201 words -> reading_time = 2
        body_201 = " ".join(["word"] * 201)
        r3 = post("/articles", {"title": f"RT201-{unique()}", "body_markdown": body_201, "published": True}, h)
        assert r3.status_code == 201
        assert r3.json()["reading_time"] == math.ceil(201 / 200)

    def test_article_score_computed_from_reactions_and_comments(self):
        """score = (reactions_count * 2) + (comments_count * 3)."""
        h = headers()
        h2 = headers()
        art = post("/articles", {"title": f"Score-{unique()}", "body_markdown": "body content", "published": True}, h).json()

        # Add reactions
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "unicorn"}, h2)

        # Add comment
        post(f"/articles/{art['id']}/comments", {"body": "great!"}, h2)

        # Check score
        art2 = get(f"/articles/{art['id']}", h).json()
        assert art2["reactions_count"] == 2
        assert art2["comments_count"] == 1
        assert art2["score"] == (2 * 2) + (1 * 3)  # 7

    def test_slug_generated_from_title(self):
        h = headers()
        r = post("/articles", {"title": "Hello World Test!", "body_markdown": "body", "published": True}, h)
        assert r.status_code == 201
        slug = r.json()["slug"]
        assert "hello" in slug.lower()
        assert "world" in slug.lower()
        # No special characters
        assert "!" not in slug


class TestArticleVisibility:
    """Pattern 3+6: Published vs unpublished visibility rules."""

    def test_unpublished_not_in_public_list(self):
        h = headers()
        title = f"Draft-{unique()}"
        art = post("/articles", {"title": title, "body_markdown": "draft body", "published": False}, h).json()

        # Public list should NOT include draft
        r = get("/articles")
        articles = r.json()["data"]
        ids = [a["id"] for a in articles]
        assert art["id"] not in ids

    def test_unpublished_visible_to_author_via_me(self):
        h = headers()
        title = f"MyDraft-{unique()}"
        art = post("/articles", {"title": title, "body_markdown": "private", "published": False}, h).json()

        r = get("/articles/me", h)
        assert r.status_code == 200
        articles = r.json()["data"]
        ids = [a["id"] for a in articles]
        assert art["id"] in ids

    def test_unpublished_not_visible_to_other_user(self):
        h1 = headers()
        h2 = headers()
        art = post("/articles", {"title": f"Secret-{unique()}", "body_markdown": "x", "published": False}, h1).json()

        r = get(f"/articles/{art['id']}", h2)
        assert r.status_code == 404

    def test_published_at_set_on_first_publish(self):
        h = headers()
        # Create unpublished
        art = post("/articles", {"title": f"Later-{unique()}", "body_markdown": "body", "published": False}, h).json()
        assert art.get("published_at") is None

        # Publish it
        r = put(f"/articles/{art['id']}", {"published": True}, h)
        assert r.status_code == 200
        assert r.json()["published_at"] is not None


class TestPaginationMetadata:
    """Pattern 3: Verify pagination actually works (not just echoing params)."""

    def test_articles_list_pagination_meta(self):
        h = headers()
        # Create 3 articles
        for i in range(3):
            post("/articles", {"title": f"PgArt{i}-{unique()}", "body_markdown": "body", "published": True}, h)

        r = get("/articles", params={"per_page": 2, "page": 1})
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["page"] == 1
        assert data["meta"]["per_page"] == 2
        assert data["meta"]["total"] >= 3
        assert len(data["data"]) <= 2

    def test_pagination_page_2_different_from_page_1(self):
        h = headers()
        titles = []
        for i in range(5):
            t = f"PgTest{i}-{unique()}"
            titles.append(t)
            post("/articles", {"title": t, "body_markdown": "body", "published": True}, h)

        r1 = get("/articles", params={"per_page": 2, "page": 1})
        r2 = get("/articles", params={"per_page": 2, "page": 2})
        ids1 = {a["id"] for a in r1.json()["data"]}
        ids2 = {a["id"] for a in r2.json()["data"]}
        # Pages should have different articles
        assert ids1.isdisjoint(ids2)


class TestTagFilterActuallyWorks:
    """Pattern 3: Verify tag filter isn't just declared but never used."""

    def test_tag_filter_on_articles(self):
        h = headers()
        tag_name = f"specialtag{unique()}"
        other_tag = f"othertag{unique()}"
        art1 = post("/articles", {"title": f"Tagged-{unique()}", "body_markdown": "body", "published": True, "tags": [tag_name]}, h).json()
        art2 = post("/articles", {"title": f"Other-{unique()}", "body_markdown": "body", "published": True, "tags": [other_tag]}, h).json()

        r = get("/articles", params={"tag": tag_name})
        articles = r.json()["data"]
        ids = [a["id"] for a in articles]
        assert art1["id"] in ids
        assert art2["id"] not in ids

    def test_max_4_tags_enforced(self):
        h = headers()
        r = post("/articles", {
            "title": f"TooMany-{unique()}",
            "body_markdown": "body",
            "tags": ["a", "b", "c", "d", "e"]
        }, h)
        assert r.status_code == 400


class TestCommentsIntegrity:
    """Pattern 1+2: Comment fields and threading."""

    def test_comment_create_returns_all_fields(self):
        h = headers()
        uid = h["X-User-Id"]
        art = post("/articles", {"title": f"ComArt-{unique()}", "body_markdown": "body", "published": True}, h).json()
        r = post(f"/articles/{art['id']}/comments", {"body": "Great article!"}, h)
        assert r.status_code == 201
        com = r.json()
        assert com["body"] == "Great article!"
        assert com["article_id"] == art["id"]
        assert com["user_id"] == uid
        assert "id" in com
        assert "created_at" in com
        assert com["parent_id"] is None

    def test_threaded_comment_has_parent_id(self):
        h = headers()
        art = post("/articles", {"title": f"Thread-{unique()}", "body_markdown": "body", "published": True}, h).json()
        parent = post(f"/articles/{art['id']}/comments", {"body": "parent"}, h).json()
        child = post(f"/articles/{art['id']}/comments", {"body": "reply", "parent_id": parent["id"]}, h).json()
        assert child["parent_id"] == parent["id"]

    def test_soft_delete_comment(self):
        h = headers()
        art = post("/articles", {"title": f"SDel-{unique()}", "body_markdown": "body", "published": True}, h).json()
        com = post(f"/articles/{art['id']}/comments", {"body": "will be deleted"}, h).json()
        r = delete(f"/comments/{com['id']}", h)
        assert r.status_code == 200
        deleted = r.json()
        assert deleted["body"] == "[deleted]"
        assert deleted["user_id"] is None

    def test_comments_count_updates_on_article(self):
        h = headers()
        art = post("/articles", {"title": f"CCount-{unique()}", "body_markdown": "body", "published": True}, h).json()
        assert art["comments_count"] == 0
        post(f"/articles/{art['id']}/comments", {"body": "c1"}, h)
        post(f"/articles/{art['id']}/comments", {"body": "c2"}, h)
        art2 = get(f"/articles/{art['id']}", h).json()
        assert art2["comments_count"] == 2


class TestReactionToggle:
    """Pattern 5: Reaction toggle actually works, not just creates."""

    def test_toggle_on_and_off(self):
        h = headers()
        art = post("/articles", {"title": f"React-{unique()}", "body_markdown": "body", "published": True}, h).json()
        h2 = headers()

        # Toggle on
        r1 = post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        assert r1.status_code == 200
        assert r1.json()["result"] == "created"

        # Toggle off
        r2 = post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        assert r2.status_code == 200
        assert r2.json()["result"] == "removed"

    def test_multiple_reaction_categories(self):
        h = headers()
        h2 = headers()
        art = post("/articles", {"title": f"Multi-{unique()}", "body_markdown": "body", "published": True}, h).json()

        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "unicorn"}, h2)

        r = get(f"/articles/{art['id']}/reactions", h2)
        assert r.status_code == 200
        reactions = r.json()["reactions"]
        like_count = next((rx["count"] for rx in reactions if rx["category"] == "like"), 0)
        unicorn_count = next((rx["count"] for rx in reactions if rx["category"] == "unicorn"), 0)
        assert like_count == 1
        assert unicorn_count == 1

    def test_reaction_affects_article_reactions_count(self):
        h = headers()
        h2 = headers()
        h3 = headers()
        art = post("/articles", {"title": f"RxCount-{unique()}", "body_markdown": "body", "published": True}, h).json()

        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h3)

        art2 = get(f"/articles/{art['id']}", h).json()
        assert art2["reactions_count"] == 2


class TestFollowSystem:
    """Pattern 5+6: Follows actually work and cannot follow self."""

    def test_follow_and_list_followed_users(self):
        h1 = headers()
        h2 = headers()
        # Ensure user2 exists
        u2 = get("/users/me", h2).json()

        r = post(f"/follows/users/{u2['id']}", None, h1)
        assert r.status_code == 201

        r2 = get("/follows/users", h1)
        assert r2.status_code == 200
        followed = r2.json()["data"]
        ids = [u["id"] for u in followed]
        assert u2["id"] in ids

    def test_cannot_follow_self(self):
        h = headers()
        me = get("/users/me", h).json()
        r = post(f"/follows/users/{me['id']}", None, h)
        assert r.status_code == 400

    def test_unfollow_user(self):
        h1 = headers()
        h2 = headers()
        u2 = get("/users/me", h2).json()
        post(f"/follows/users/{u2['id']}", None, h1)
        r = delete(f"/follows/users/{u2['id']}", h1)
        assert r.status_code == 204

    def test_follow_tag(self):
        h = headers()
        tag = post("/tags", {"name": f"followtag-{unique()}"}, h).json()
        r = post(f"/follows/tags/{tag['id']}", None, h)
        assert r.status_code == 201

        r2 = get("/follows/tags", h)
        tag_ids = [t["id"] for t in r2.json()["data"]]
        assert tag["id"] in tag_ids


class TestListingsCategory:
    """Pattern 3+4: Listing category filter and status codes."""

    def test_listing_create_and_filter_by_category(self):
        h = headers()
        l1 = post("/listings", {"title": f"Job-{unique()}", "body": "hiring", "category": "jobs"}, h).json()
        l2 = post("/listings", {"title": f"Event-{unique()}", "body": "meetup", "category": "events"}, h).json()

        r = get("/listings", params={"category": "jobs"})
        listings = r.json()["data"]
        ids = [l["id"] for l in listings]
        assert l1["id"] in ids
        assert l2["id"] not in ids

    def test_listing_author_only_update(self):
        h1 = headers()
        h2 = headers()
        listing = post("/listings", {"title": f"Mine-{unique()}", "body": "body", "category": "misc"}, h1).json()
        r = put(f"/listings/{listing['id']}", {"title": "Hacked"}, h2)
        assert r.status_code == 403

    def test_listing_delete_returns_204(self):
        h = headers()
        listing = post("/listings", {"title": f"Del-{unique()}", "body": "body", "category": "misc"}, h).json()
        r = delete(f"/listings/{listing['id']}", h)
        assert r.status_code == 204
        r2 = get(f"/listings/{listing['id']}")
        assert r2.status_code == 404


class TestOrganizationMembership:
    """Pattern 5+7: Org membership rules."""

    def test_creator_becomes_member(self):
        h = headers()
        slug = f"org-{unique()}"
        org = post("/organizations", {"name": f"Org {unique()}", "slug": slug}, h).json()
        r = get(f"/organizations/{slug}/members")
        members = r.json()["data"]
        assert len(members) >= 1

    def test_cannot_remove_last_member(self):
        h = headers()
        me = get("/users/me", h).json()
        slug = f"solo-{unique()}"
        post("/organizations", {"name": f"Solo {unique()}", "slug": slug}, h)
        r = delete(f"/organizations/{slug}/members/{me['username']}", h)
        assert r.status_code == 400

    def test_non_member_cannot_update_org(self):
        h1 = headers()
        h2 = headers()
        slug = f"priv-{unique()}"
        post("/organizations", {"name": "Private", "slug": slug}, h1)
        r = put(f"/organizations/{slug}", {"name": "Hacked"}, h2)
        assert r.status_code == 403


class TestSearchActuallySearches:
    """Pattern 3: Search isn't just returning all articles."""

    def test_search_finds_by_title(self):
        h = headers()
        keyword = f"uniqueword{unique()}"
        post("/articles", {"title": f"Article about {keyword}", "body_markdown": "content", "published": True}, h)
        post("/articles", {"title": f"Unrelated-{unique()}", "body_markdown": "other content", "published": True}, h)

        r = get("/search/articles", params={"q": keyword})
        assert r.status_code == 200
        articles = r.json()["data"]
        assert len(articles) >= 1
        assert all(keyword in a["title"] or keyword in a.get("body_markdown", "") for a in articles)

    def test_search_requires_q_param(self):
        r = get("/search/articles", params={})
        assert r.status_code == 400

    def test_search_only_published(self):
        h = headers()
        keyword = f"draftsearch{unique()}"
        post("/articles", {"title": f"Draft {keyword}", "body_markdown": "x", "published": False}, h)

        r = get("/search/articles", params={"q": keyword})
        articles = r.json()["data"]
        assert len(articles) == 0


class TestUserArticlesCount:
    """Pattern 5: articles_count is computed, not hardcoded."""

    def test_articles_count_only_published(self):
        h = headers()
        me = get("/users/me", h).json()
        initial_count = me["articles_count"]

        post("/articles", {"title": f"Pub-{unique()}", "body_markdown": "x", "published": True}, h)
        post("/articles", {"title": f"Draft-{unique()}", "body_markdown": "x", "published": False}, h)

        me2 = get(f"/users/{me['username']}").json()
        assert me2["articles_count"] == initial_count + 1  # only published counted


class TestReadingList:
    """Pattern 5: Reading list uses readinglist reactions."""

    def test_readinglist_reaction_adds_to_reading_list(self):
        h1 = headers()
        h2 = headers()
        art = post("/articles", {"title": f"ReadList-{unique()}", "body_markdown": "body", "published": True}, h1).json()

        # Add to reading list
        post(f"/articles/{art['id']}/reactions", {"category": "readinglist"}, h2)

        r = get("/readinglist", h2)
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["data"]]
        assert art["id"] in ids

    def test_readinglist_toggle_off_removes(self):
        h1 = headers()
        h2 = headers()
        art = post("/articles", {"title": f"RL2-{unique()}", "body_markdown": "body", "published": True}, h1).json()

        # Add then remove
        post(f"/articles/{art['id']}/reactions", {"category": "readinglist"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "readinglist"}, h2)

        r = get("/readinglist", h2)
        ids = [a["id"] for a in r.json()["data"]]
        assert art["id"] not in ids


class TestArticleAuthorization:
    """Pattern 6: Only author can update/delete articles."""

    def test_non_author_cannot_update_article(self):
        h1 = headers()
        h2 = headers()
        art = post("/articles", {"title": f"Auth-{unique()}", "body_markdown": "x", "published": True}, h1).json()
        r = put(f"/articles/{art['id']}", {"title": "Hacked"}, h2)
        assert r.status_code == 403

    def test_non_author_cannot_delete_article(self):
        h1 = headers()
        h2 = headers()
        art = post("/articles", {"title": f"AuthDel-{unique()}", "body_markdown": "x", "published": True}, h1).json()
        r = delete(f"/articles/{art['id']}", h2)
        assert r.status_code == 403

    def test_delete_article_returns_204(self):
        h = headers()
        art = post("/articles", {"title": f"Del204-{unique()}", "body_markdown": "x", "published": True}, h).json()
        r = delete(f"/articles/{art['id']}", h)
        assert r.status_code == 204
        r2 = get(f"/articles/{art['id']}", h)
        assert r2.status_code == 404
