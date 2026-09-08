"""
BackendForge — Correctness Tests for Forem Developer Community Platform

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid
import time

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# User IDs (UUIDs)
USER1_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
USER3_ID = str(uuid.uuid4())

USER1_HEADERS = {"X-User-Id": USER1_ID, "Content-Type": "application/json"}
USER2_HEADERS = {"X-User-Id": USER2_ID, "Content-Type": "application/json"}
USER3_HEADERS = {"X-User-Id": USER3_ID, "Content-Type": "application/json"}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_auth_articles_create(self):
        """POST /articles without X-User-Id returns 401."""
        resp = api_post("/articles", {"title": "t", "body_markdown": "b"}, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401

    def test_missing_auth_users_me(self):
        """GET /users/me without X-User-Id returns 401."""
        resp = api_get("/users/me", headers={})
        assert resp.status_code == 401

    def test_missing_auth_readinglist(self):
        """GET /readinglist without X-User-Id returns 401."""
        resp = api_get("/readinglist", headers={})
        assert resp.status_code == 401

    def test_missing_auth_feed(self):
        """GET /articles/feed without X-User-Id returns 401."""
        resp = api_get("/articles/feed", headers={})
        assert resp.status_code == 401

    def test_missing_auth_follows(self):
        """GET /follows/users without X-User-Id returns 401."""
        resp = api_get("/follows/users", headers={})
        assert resp.status_code == 401

    def test_auto_provision_user(self):
        """First request with new X-User-Id auto-creates user."""
        new_id = str(uuid.uuid4())
        resp = api_get("/users/me", headers={"X-User-Id": new_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == new_id
        assert data["username"] == f"user_{new_id[:8]}"
        assert "joined_at" in data


# ════════════════════════════════════════════════════════════════════
# PART 2: Users
# ════════════════════════════════════════════════════════════════════


class TestUsers:

    def test_get_me(self):
        """GET /users/me returns current user profile."""
        resp = api_get("/users/me", headers=USER1_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == USER1_ID
        assert "username" in data
        assert "joined_at" in data
        assert "articles_count" in data

    def test_get_user_by_username(self):
        """GET /users/{username} returns public profile."""
        # First get the username
        me = api_get("/users/me", headers=USER1_HEADERS).json()
        username = me["username"]

        resp = api_get(f"/users/{username}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == USER1_ID
        assert data["username"] == username

    def test_get_user_not_found(self):
        """GET /users/{username} with non-existent username returns 404."""
        resp = api_get("/users/nonexistent_user_xyz")
        assert resp.status_code == 404

    def test_articles_count_computed(self):
        """articles_count reflects only published articles."""
        resp = api_get("/users/me", headers=USER1_HEADERS)
        data = resp.json()
        assert isinstance(data["articles_count"], int)


# ════════════════════════════════════════════════════════════════════
# PART 3: Tags
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        """POST /tags creates a tag."""
        tag_name = f"python-{UNIQUE}"
        resp = api_post("/tags", {
            "name": tag_name,
            "bg_color": "#306998",
            "text_color": "#FFD43B",
            "description": "Python programming language",
            "rules_markdown": "Be nice"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == tag_name
        assert data["bg_color"] == "#306998"
        assert data["text_color"] == "#FFD43B"
        assert data["description"] == "Python programming language"
        assert "id" in data
        assert "created_at" in data

    def test_create_tag_requires_auth(self):
        """POST /tags without auth returns 401."""
        resp = api_post("/tags", {"name": "no-auth"}, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401

    def test_create_tag_duplicate_name(self):
        """POST /tags with duplicate name returns 400."""
        name = f"dup-tag-{UNIQUE}"
        api_post("/tags", {"name": name}, headers=USER1_HEADERS)
        resp = api_post("/tags", {"name": name}, headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_list_tags(self):
        """GET /tags returns paginated tags."""
        resp = api_get("/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        assert "total" in data["meta"]
        assert "page" in data["meta"]
        assert "per_page" in data["meta"]

    def test_get_tag(self):
        """GET /tags/{id} returns single tag."""
        # Create a tag first
        tag_name = f"get-tag-{UNIQUE}"
        created = api_post("/tags", {"name": tag_name}, headers=USER1_HEADERS).json()
        tag_id = created["id"]

        resp = api_get(f"/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == tag_name

    def test_update_tag(self):
        """PUT /tags/{id} updates tag."""
        tag_name = f"upd-tag-{UNIQUE}"
        created = api_post("/tags", {"name": tag_name}, headers=USER1_HEADERS).json()
        tag_id = created["id"]

        resp = api_put(f"/tags/{tag_id}", {"description": "Updated!"}, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated!"

    def test_delete_tag(self):
        """DELETE /tags/{id} removes tag."""
        tag_name = f"del-tag-{UNIQUE}"
        created = api_post("/tags", {"name": tag_name}, headers=USER1_HEADERS).json()
        tag_id = created["id"]

        resp = api_delete(f"/tags/{tag_id}", headers=USER1_HEADERS)
        assert resp.status_code == 204

        resp = api_get(f"/tags/{tag_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Articles
# ════════════════════════════════════════════════════════════════════


class TestArticles:

    def test_create_article_unpublished(self):
        """POST /articles creates unpublished article by default."""
        resp = api_post("/articles", {
            "title": f"My First Article {UNIQUE}",
            "body_markdown": "This is the body of my article with some words to test reading time calculation.",
            "tags": ["python", "tutorial"]
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"My First Article {UNIQUE}"
        assert data["published"] is False
        assert data["published_at"] is None
        assert data["tags"] == ["python", "tutorial"]
        assert data["user_id"] == USER1_ID
        assert "id" in data
        assert "slug" in data
        assert "reading_time" in data
        assert "reactions_count" in data
        assert "comments_count" in data
        assert "score" in data
        assert "created_at" in data

    def test_create_article_published(self):
        """POST /articles with published=true sets published_at."""
        resp = api_post("/articles", {
            "title": f"Published Article {UNIQUE}",
            "body_markdown": "Body content here",
            "published": True,
            "tags": ["news"]
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["published"] is True
        assert data["published_at"] is not None

    def test_create_article_max_4_tags(self):
        """POST /articles with >4 tags returns 400."""
        resp = api_post("/articles", {
            "title": "Too many tags",
            "body_markdown": "body",
            "tags": ["a", "b", "c", "d", "e"]
        }, headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_reading_time_computation(self):
        """Reading time is ceil(word_count / 200), min 1."""
        # 400 words → 2 minutes
        body = " ".join(["word"] * 400)
        resp = api_post("/articles", {
            "title": f"Reading Time Test {UNIQUE}",
            "body_markdown": body,
            "published": True
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["reading_time"] == 2

    def test_reading_time_minimum(self):
        """Reading time minimum is 1 minute."""
        resp = api_post("/articles", {
            "title": f"Short Article {UNIQUE}",
            "body_markdown": "hello",
            "published": True
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["reading_time"] == 1

    def test_slug_generation(self):
        """Slug is generated from title."""
        resp = api_post("/articles", {
            "title": f"Hello World Test {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        slug = resp.json()["slug"]
        assert "hello-world-test" in slug
        # Should be lowercase and hyphenated
        assert slug == slug.lower()
        assert " " not in slug

    def test_unpublished_not_in_list(self):
        """Unpublished articles don't appear in GET /articles."""
        # Create unpublished
        resp = api_post("/articles", {
            "title": f"Hidden Article {UNIQUE}",
            "body_markdown": "secret",
            "published": False
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        article_id = resp.json()["id"]

        # List articles - should not include unpublished
        resp = api_get("/articles")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["data"]]
        assert article_id not in ids

    def test_unpublished_visible_to_author(self):
        """Author can see their own unpublished article."""
        resp = api_post("/articles", {
            "title": f"My Private {UNIQUE}",
            "body_markdown": "private",
            "published": False
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_get(f"/articles/{article_id}", headers=USER1_HEADERS)
        assert resp.status_code == 200

    def test_unpublished_not_visible_to_others(self):
        """Others cannot see unpublished articles."""
        resp = api_post("/articles", {
            "title": f"Other Private {UNIQUE}",
            "body_markdown": "private",
            "published": False
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_get(f"/articles/{article_id}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_list_my_articles_includes_unpublished(self):
        """GET /articles/me includes unpublished articles."""
        # Create one unpublished
        resp = api_post("/articles", {
            "title": f"My Draft {UNIQUE}",
            "body_markdown": "draft",
            "published": False
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201
        draft_id = resp.json()["id"]

        resp = api_get("/articles/me", headers=USER2_HEADERS)
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["data"]]
        assert draft_id in ids

    def test_update_article(self):
        """PUT /articles/{id} updates article."""
        resp = api_post("/articles", {
            "title": f"To Update {UNIQUE}",
            "body_markdown": "original",
            "published": True
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_put(f"/articles/{article_id}", {
            "body_markdown": "updated body"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["body_markdown"] == "updated body"

    def test_update_article_forbidden(self):
        """PUT /articles/{id} by non-author returns 403."""
        resp = api_post("/articles", {
            "title": f"Auth Test {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_put(f"/articles/{article_id}", {"title": "hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_publish_sets_published_at(self):
        """Updating published from false to true sets published_at."""
        resp = api_post("/articles", {
            "title": f"Will Publish {UNIQUE}",
            "body_markdown": "body",
            "published": False
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]
        assert resp.json()["published_at"] is None

        resp = api_put(f"/articles/{article_id}", {"published": True}, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["published_at"] is not None

    def test_delete_article(self):
        """DELETE /articles/{id} removes article."""
        resp = api_post("/articles", {
            "title": f"To Delete {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_delete(f"/articles/{article_id}", headers=USER1_HEADERS)
        assert resp.status_code == 204

        resp = api_get(f"/articles/{article_id}", headers=USER1_HEADERS)
        assert resp.status_code == 404

    def test_delete_article_forbidden(self):
        """DELETE /articles/{id} by non-author returns 403."""
        resp = api_post("/articles", {
            "title": f"No Delete {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        article_id = resp.json()["id"]

        resp = api_delete(f"/articles/{article_id}", headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_list_articles_pagination(self):
        """GET /articles supports pagination."""
        # Create several articles
        for i in range(3):
            api_post("/articles", {
                "title": f"Paginate {UNIQUE} {i}",
                "body_markdown": "body",
                "published": True
            }, headers=USER1_HEADERS)

        resp = api_get("/articles", params={"per_page": 2, "page": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 2
        assert data["meta"]["per_page"] == 2
        assert data["meta"]["page"] == 1

    def test_list_articles_filter_by_tag(self):
        """GET /articles?tag=X filters by tag."""
        tag_name = f"filter-{UNIQUE}"
        api_post("/articles", {
            "title": f"Tagged Article {UNIQUE}",
            "body_markdown": "body",
            "published": True,
            "tags": [tag_name]
        }, headers=USER1_HEADERS)

        resp = api_get("/articles", params={"tag": tag_name})
        assert resp.status_code == 200
        articles = resp.json()["data"]
        assert len(articles) >= 1
        for a in articles:
            assert tag_name in a["tags"]

    def test_article_includes_user(self):
        """Article response includes user object."""
        resp = api_post("/articles", {
            "title": f"With User {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        data = resp.json()
        assert "user" in data
        assert data["user"]["id"] == USER1_ID
        assert "username" in data["user"]

    def test_article_score_computation(self):
        """Score = (reactions_count * 2) + (comments_count * 3)."""
        resp = api_post("/articles", {
            "title": f"Score Test {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)
        data = resp.json()
        # Initially 0 reactions and 0 comments
        assert data["score"] == 0
        assert data["reactions_count"] == 0
        assert data["comments_count"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 5: Comments
# ════════════════════════════════════════════════════════════════════


class TestComments:

    def _create_published_article(self, headers=None):
        """Helper to create a published article."""
        headers = headers or USER1_HEADERS
        resp = api_post("/articles", {
            "title": f"Comment Article {uuid.uuid4().hex[:6]}",
            "body_markdown": "Article for comments",
            "published": True
        }, headers=headers)
        return resp.json()["id"]

    def test_create_comment(self):
        """POST /articles/{id}/comments creates comment."""
        article_id = self._create_published_article()
        resp = api_post(f"/articles/{article_id}/comments", {
            "body": "Great article!"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["body"] == "Great article!"
        assert data["article_id"] == article_id
        assert data["user_id"] == USER2_ID
        assert data["parent_id"] is None
        assert "id" in data
        assert "created_at" in data

    def test_create_comment_requires_auth(self):
        """POST /articles/{id}/comments without auth returns 401."""
        article_id = self._create_published_article()
        resp = api_post(f"/articles/{article_id}/comments", {
            "body": "no auth"
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401

    def test_create_threaded_comment(self):
        """POST /articles/{id}/comments with parent_id creates threaded reply."""
        article_id = self._create_published_article()
        # Create parent comment
        parent = api_post(f"/articles/{article_id}/comments", {
            "body": "Parent comment"
        }, headers=USER1_HEADERS).json()

        # Create child comment
        resp = api_post(f"/articles/{article_id}/comments", {
            "body": "Reply to parent",
            "parent_id": parent["id"]
        }, headers=USER2_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_id"] == parent["id"]

    def test_list_comments(self):
        """GET /articles/{id}/comments returns comments sorted by creation."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/comments", {"body": "First"}, headers=USER1_HEADERS)
        api_post(f"/articles/{article_id}/comments", {"body": "Second"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        comments = data["data"]
        assert len(comments) >= 2
        # Verify ascending order
        bodies = [c["body"] for c in comments]
        assert bodies.index("First") < bodies.index("Second")

    def test_get_comment(self):
        """GET /comments/{id} returns single comment."""
        article_id = self._create_published_article()
        created = api_post(f"/articles/{article_id}/comments", {
            "body": "Find me"
        }, headers=USER1_HEADERS).json()

        resp = api_get(f"/comments/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["body"] == "Find me"

    def test_update_comment(self):
        """PUT /comments/{id} updates comment body."""
        article_id = self._create_published_article()
        created = api_post(f"/articles/{article_id}/comments", {
            "body": "Original"
        }, headers=USER1_HEADERS).json()

        resp = api_put(f"/comments/{created['id']}", {"body": "Edited"}, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["body"] == "Edited"

    def test_update_comment_forbidden(self):
        """PUT /comments/{id} by non-author returns 403."""
        article_id = self._create_published_article()
        created = api_post(f"/articles/{article_id}/comments", {
            "body": "Mine"
        }, headers=USER1_HEADERS).json()

        resp = api_put(f"/comments/{created['id']}", {"body": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_delete_comment_soft_delete(self):
        """DELETE /comments/{id} soft-deletes: body=[deleted], user_id=null."""
        article_id = self._create_published_article()
        created = api_post(f"/articles/{article_id}/comments", {
            "body": "Will be deleted"
        }, headers=USER1_HEADERS).json()

        resp = api_delete(f"/comments/{created['id']}", headers=USER1_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["body"] == "[deleted]"
        assert data["user_id"] is None

    def test_delete_comment_children_remain(self):
        """Deleting parent comment preserves child comments."""
        article_id = self._create_published_article()
        parent = api_post(f"/articles/{article_id}/comments", {
            "body": "Parent"
        }, headers=USER1_HEADERS).json()

        child = api_post(f"/articles/{article_id}/comments", {
            "body": "Child",
            "parent_id": parent["id"]
        }, headers=USER2_HEADERS).json()

        # Delete parent
        api_delete(f"/comments/{parent['id']}", headers=USER1_HEADERS)

        # Child should still exist
        resp = api_get(f"/comments/{child['id']}")
        assert resp.status_code == 200
        assert resp.json()["body"] == "Child"
        assert resp.json()["parent_id"] == parent["id"]

    def test_comment_on_nonexistent_article(self):
        """POST /articles/{id}/comments on non-existent article returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/articles/{fake_id}/comments", {
            "body": "no article"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 404

    def test_comments_count_updated(self):
        """Article's comments_count reflects actual comments."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/comments", {"body": "c1"}, headers=USER1_HEADERS)
        api_post(f"/articles/{article_id}/comments", {"body": "c2"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}", headers=USER1_HEADERS)
        assert resp.json()["comments_count"] == 2


# ════════════════════════════════════════════════════════════════════
# PART 6: Reactions
# ════════════════════════════════════════════════════════════════════


class TestReactions:

    def _create_published_article(self, headers=None):
        headers = headers or USER1_HEADERS
        resp = api_post("/articles", {
            "title": f"React Article {uuid.uuid4().hex[:6]}",
            "body_markdown": "Article for reactions",
            "published": True
        }, headers=headers)
        return resp.json()["id"]

    def test_toggle_reaction_on(self):
        """POST reaction creates it (toggle on)."""
        article_id = self._create_published_article()
        resp = api_post(f"/articles/{article_id}/reactions", {
            "category": "like"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "created"
        # Check counts
        like_count = next(r for r in data["reactions"] if r["category"] == "like")["count"]
        assert like_count == 1
        assert "like" in data["user_reactions"]

    def test_toggle_reaction_off(self):
        """POST same reaction again removes it (toggle off)."""
        article_id = self._create_published_article()
        # Toggle on
        api_post(f"/articles/{article_id}/reactions", {"category": "unicorn"}, headers=USER2_HEADERS)
        # Toggle off
        resp = api_post(f"/articles/{article_id}/reactions", {"category": "unicorn"}, headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "removed"
        unicorn_count = next(r for r in data["reactions"] if r["category"] == "unicorn")["count"]
        assert unicorn_count == 0
        assert "unicorn" not in data["user_reactions"]

    def test_multiple_reaction_categories(self):
        """User can react with multiple categories on same article."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)
        resp = api_post(f"/articles/{article_id}/reactions", {"category": "unicorn"}, headers=USER2_HEADERS)
        data = resp.json()
        assert "like" in data["user_reactions"]
        assert "unicorn" in data["user_reactions"]

    def test_reaction_uniqueness_per_user(self):
        """Each user can only have one reaction per category per article."""
        article_id = self._create_published_article()
        # User2 likes
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)
        # User3 likes
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER3_HEADERS)

        resp = api_get(f"/articles/{article_id}/reactions")
        data = resp.json()
        like_count = next(r for r in data["reactions"] if r["category"] == "like")["count"]
        assert like_count == 2

    def test_get_reactions(self):
        """GET /articles/{id}/reactions returns reaction summary."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}/reactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "reactions" in data
        categories = [r["category"] for r in data["reactions"]]
        assert "like" in categories
        assert "unicorn" in categories
        assert "readinglist" in categories

    def test_get_reactions_with_user_context(self):
        """GET /articles/{id}/reactions with auth shows user's reactions."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}/reactions", headers=USER2_HEADERS)
        data = resp.json()
        assert "like" in data["user_reactions"]

    def test_reaction_requires_auth(self):
        """POST reaction without auth returns 401."""
        article_id = self._create_published_article()
        resp = api_post(f"/articles/{article_id}/reactions", {
            "category": "like"
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401

    def test_reaction_nonexistent_article(self):
        """POST reaction on non-existent article returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/articles/{fake_id}/reactions", {
            "category": "like"
        }, headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_reactions_count_on_article(self):
        """Article's reactions_count reflects total reactions."""
        article_id = self._create_published_article()
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)
        api_post(f"/articles/{article_id}/reactions", {"category": "unicorn"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}", headers=USER1_HEADERS)
        assert resp.json()["reactions_count"] == 2

    def test_article_score_with_reactions_and_comments(self):
        """Score = (reactions_count * 2) + (comments_count * 3)."""
        article_id = self._create_published_article()
        # 2 reactions
        api_post(f"/articles/{article_id}/reactions", {"category": "like"}, headers=USER2_HEADERS)
        api_post(f"/articles/{article_id}/reactions", {"category": "unicorn"}, headers=USER3_HEADERS)
        # 1 comment
        api_post(f"/articles/{article_id}/comments", {"body": "Nice"}, headers=USER2_HEADERS)

        resp = api_get(f"/articles/{article_id}", headers=USER1_HEADERS)
        data = resp.json()
        assert data["reactions_count"] == 2
        assert data["comments_count"] == 1
        assert data["score"] == (2 * 2) + (1 * 3)  # 7


# ════════════════════════════════════════════════════════════════════
# PART 7: Follows
# ════════════════════════════════════════════════════════════════════


class TestFollows:

    def test_follow_user(self):
        """POST /follows/users/{id} follows a user."""
        # Ensure user2 exists
        api_get("/users/me", headers=USER2_HEADERS)

        resp = api_post(f"/follows/users/{USER2_ID}", headers=USER1_HEADERS)
        assert resp.status_code == 201

    def test_follow_self_rejected(self):
        """Cannot follow yourself."""
        resp = api_post(f"/follows/users/{USER1_ID}", headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_follow_already_following(self):
        """Following same user twice returns 400."""
        # Ensure user3 exists
        api_get("/users/me", headers=USER3_HEADERS)
        api_post(f"/follows/users/{USER3_ID}", headers=USER1_HEADERS)
        resp = api_post(f"/follows/users/{USER3_ID}", headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_list_followed_users(self):
        """GET /follows/users lists followed users."""
        follower_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        follower_headers = {"X-User-Id": follower_id, "Content-Type": "application/json"}
        target_headers = {"X-User-Id": target_id, "Content-Type": "application/json"}

        target = api_get("/users/me", headers=target_headers)
        assert target.status_code == 200
        follower = api_get("/users/me", headers=follower_headers)
        assert follower.status_code == 200
        followed = api_post(f"/follows/users/{target_id}", headers=follower_headers)
        assert followed.status_code == 201

        resp = api_get("/follows/users", headers=follower_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        ids = [u["id"] for u in data["data"]]
        assert target_id in ids

    def test_unfollow_user(self):
        """DELETE /follows/users/{id} unfollows a user."""
        # Follow user3 first (may already be followed)
        api_get("/users/me", headers=USER3_HEADERS)
        api_post(f"/follows/users/{USER3_ID}", headers=USER2_HEADERS)

        resp = api_delete(f"/follows/users/{USER3_ID}", headers=USER2_HEADERS)
        assert resp.status_code == 204

        # Verify unfollowed
        resp = api_get("/follows/users", headers=USER2_HEADERS)
        ids = [u["id"] for u in resp.json()["data"]]
        assert USER3_ID not in ids

    def test_unfollow_not_following(self):
        """DELETE /follows/users/{id} when not following returns 404."""
        random_id = str(uuid.uuid4())
        resp = api_delete(f"/follows/users/{random_id}", headers=USER1_HEADERS)
        assert resp.status_code == 404

    def test_follow_tag(self):
        """POST /follows/tags/{id} follows a tag."""
        tag = api_post("/tags", {"name": f"follow-tag-{UNIQUE}"}, headers=USER1_HEADERS).json()
        resp = api_post(f"/follows/tags/{tag['id']}", headers=USER1_HEADERS)
        assert resp.status_code == 201

    def test_follow_tag_already_following(self):
        """Following same tag twice returns 400."""
        tag = api_post("/tags", {"name": f"dup-follow-{UNIQUE}"}, headers=USER1_HEADERS).json()
        api_post(f"/follows/tags/{tag['id']}", headers=USER1_HEADERS)
        resp = api_post(f"/follows/tags/{tag['id']}", headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_list_followed_tags(self):
        """GET /follows/tags lists followed tags."""
        resp = api_get("/follows/tags", headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_unfollow_tag(self):
        """DELETE /follows/tags/{id} unfollows tag."""
        tag = api_post("/tags", {"name": f"unfollow-tag-{UNIQUE}"}, headers=USER2_HEADERS).json()
        api_post(f"/follows/tags/{tag['id']}", headers=USER2_HEADERS)
        resp = api_delete(f"/follows/tags/{tag['id']}", headers=USER2_HEADERS)
        assert resp.status_code == 204

    def test_list_user_followers(self):
        """GET /users/{username}/followers lists followers."""
        follower_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())
        follower_headers = {"X-User-Id": follower_id, "Content-Type": "application/json"}
        target_headers = {"X-User-Id": target_id, "Content-Type": "application/json"}

        target = api_get("/users/me", headers=target_headers)
        assert target.status_code == 200
        follower = api_get("/users/me", headers=follower_headers)
        assert follower.status_code == 200
        followed = api_post(f"/follows/users/{target_id}", headers=follower_headers)
        assert followed.status_code == 201

        resp = api_get(f"/users/{target.json()['username']}/followers")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        ids = [u["id"] for u in data["data"]]
        assert follower_id in ids

    def test_follow_nonexistent_user(self):
        """Following non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/follows/users/{fake_id}", headers=USER1_HEADERS)
        assert resp.status_code == 404

    def test_follow_nonexistent_tag(self):
        """Following non-existent tag returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/follows/tags/{fake_id}", headers=USER1_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Listings
# ════════════════════════════════════════════════════════════════════


class TestListings:

    def test_create_listing(self):
        """POST /listings creates a listing."""
        resp = api_post("/listings", {
            "title": f"Job Posting {UNIQUE}",
            "body": "We are hiring!",
            "category": "jobs",
            "contact_via": "email@test.com"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == f"Job Posting {UNIQUE}"
        assert data["category"] == "jobs"
        assert data["published"] is True
        assert data["contact_via"] == "email@test.com"
        assert "id" in data
        assert "created_at" in data

    def test_create_listing_invalid_category(self):
        """POST /listings with invalid category returns 400."""
        resp = api_post("/listings", {
            "title": "Bad Cat",
            "body": "body",
            "category": "invalid"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_create_listing_requires_auth(self):
        """POST /listings without auth returns 401."""
        resp = api_post("/listings", {
            "title": "No Auth",
            "body": "body",
            "category": "misc"
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 401

    def test_list_listings(self):
        """GET /listings returns published listings."""
        resp = api_get("/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_list_listings_filter_category(self):
        """GET /listings?category=jobs filters by category."""
        api_post("/listings", {
            "title": f"Event {UNIQUE}",
            "body": "body",
            "category": "events"
        }, headers=USER1_HEADERS)

        resp = api_get("/listings", params={"category": "events"})
        data = resp.json()
        for listing in data["data"]:
            assert listing["category"] == "events"

    def test_get_listing(self):
        """GET /listings/{id} returns single listing."""
        created = api_post("/listings", {
            "title": f"Get Me {UNIQUE}",
            "body": "body",
            "category": "misc"
        }, headers=USER1_HEADERS).json()

        resp = api_get(f"/listings/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == f"Get Me {UNIQUE}"

    def test_update_listing(self):
        """PUT /listings/{id} updates listing."""
        created = api_post("/listings", {
            "title": f"Update Me {UNIQUE}",
            "body": "body",
            "category": "misc"
        }, headers=USER1_HEADERS).json()

        resp = api_put(f"/listings/{created['id']}", {
            "title": "Updated Title"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_listing_forbidden(self):
        """PUT /listings/{id} by non-author returns 403."""
        created = api_post("/listings", {
            "title": f"Protected {UNIQUE}",
            "body": "body",
            "category": "misc"
        }, headers=USER1_HEADERS).json()

        resp = api_put(f"/listings/{created['id']}", {"title": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_delete_listing(self):
        """DELETE /listings/{id} removes listing."""
        created = api_post("/listings", {
            "title": f"Delete Me {UNIQUE}",
            "body": "body",
            "category": "misc"
        }, headers=USER1_HEADERS).json()

        resp = api_delete(f"/listings/{created['id']}", headers=USER1_HEADERS)
        assert resp.status_code == 204

        resp = api_get(f"/listings/{created['id']}")
        assert resp.status_code == 404

    def test_delete_listing_forbidden(self):
        """DELETE /listings/{id} by non-author returns 403."""
        created = api_post("/listings", {
            "title": f"No Delete {UNIQUE}",
            "body": "body",
            "category": "misc"
        }, headers=USER1_HEADERS).json()

        resp = api_delete(f"/listings/{created['id']}", headers=USER2_HEADERS)
        assert resp.status_code == 403


# ════════════════════════════════════════════════════════════════════
# PART 9: Organizations
# ════════════════════════════════════════════════════════════════════


class TestOrganizations:

    def test_create_organization(self):
        """POST /organizations creates org with creator as member."""
        resp = api_post("/organizations", {
            "name": f"Dev Corp {UNIQUE}",
            "slug": f"dev-corp-{UNIQUE}",
            "description": "A dev organization"
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Dev Corp {UNIQUE}"
        assert data["slug"] == f"dev-corp-{UNIQUE}"
        assert data["members_count"] == 1
        assert "id" in data

    def test_create_org_duplicate_slug(self):
        """POST /organizations with duplicate slug returns 400."""
        slug = f"dup-org-{UNIQUE}"
        api_post("/organizations", {"name": "Org1", "slug": slug}, headers=USER1_HEADERS)
        resp = api_post("/organizations", {"name": "Org2", "slug": slug}, headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_list_organizations(self):
        """GET /organizations returns orgs with pagination."""
        resp = api_get("/organizations")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_get_organization(self):
        """GET /organizations/{slug} returns org."""
        slug = f"get-org-{UNIQUE}"
        api_post("/organizations", {"name": "Get Org", "slug": slug}, headers=USER1_HEADERS)
        resp = api_get(f"/organizations/{slug}")
        assert resp.status_code == 200
        assert resp.json()["slug"] == slug

    def test_update_organization(self):
        """PUT /organizations/{slug} updates org (members only)."""
        slug = f"upd-org-{UNIQUE}"
        api_post("/organizations", {"name": "To Update", "slug": slug}, headers=USER1_HEADERS)
        resp = api_put(f"/organizations/{slug}", {"name": "Updated Name"}, headers=USER1_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_organization_forbidden(self):
        """PUT /organizations/{slug} by non-member returns 403."""
        slug = f"noupd-org-{UNIQUE}"
        api_post("/organizations", {"name": "No Update", "slug": slug}, headers=USER1_HEADERS)
        resp = api_put(f"/organizations/{slug}", {"name": "Hacked"}, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_add_member(self):
        """POST /organizations/{slug}/members adds member."""
        slug = f"add-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        # Get user2's username
        user2 = api_get("/users/me", headers=USER2_HEADERS).json()
        resp = api_post(f"/organizations/{slug}/members", {
            "username": user2["username"]
        }, headers=USER1_HEADERS)
        assert resp.status_code == 201

    def test_add_member_already_member(self):
        """Adding existing member returns 400."""
        slug = f"dup-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        user2 = api_get("/users/me", headers=USER2_HEADERS).json()
        api_post(f"/organizations/{slug}/members", {"username": user2["username"]}, headers=USER1_HEADERS)
        resp = api_post(f"/organizations/{slug}/members", {"username": user2["username"]}, headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_add_member_forbidden(self):
        """Non-member cannot add members."""
        slug = f"forbid-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        user3 = api_get("/users/me", headers=USER3_HEADERS).json()
        resp = api_post(f"/organizations/{slug}/members", {
            "username": user3["username"]
        }, headers=USER2_HEADERS)
        assert resp.status_code == 403

    def test_list_members(self):
        """GET /organizations/{slug}/members lists members."""
        slug = f"list-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        resp = api_get(f"/organizations/{slug}/members")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) >= 1

    def test_remove_member(self):
        """DELETE /organizations/{slug}/members/{username} removes member."""
        slug = f"rm-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        user2 = api_get("/users/me", headers=USER2_HEADERS).json()
        api_post(f"/organizations/{slug}/members", {"username": user2["username"]}, headers=USER1_HEADERS)

        resp = api_delete(f"/organizations/{slug}/members/{user2['username']}", headers=USER1_HEADERS)
        assert resp.status_code == 204

    def test_cannot_remove_last_member(self):
        """Cannot remove the last member."""
        slug = f"last-mem-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)
        user1 = api_get("/users/me", headers=USER1_HEADERS).json()

        resp = api_delete(f"/organizations/{slug}/members/{user1['username']}", headers=USER1_HEADERS)
        assert resp.status_code == 400

    def test_delete_organization(self):
        """DELETE /organizations/{slug} removes org."""
        slug = f"del-org-{UNIQUE}"
        api_post("/organizations", {"name": "To Delete", "slug": slug}, headers=USER1_HEADERS)
        resp = api_delete(f"/organizations/{slug}", headers=USER1_HEADERS)
        assert resp.status_code == 204

        resp = api_get(f"/organizations/{slug}")
        assert resp.status_code == 404

    def test_org_articles(self):
        """GET /organizations/{slug}/articles returns articles by members."""
        slug = f"art-org-{UNIQUE}"
        api_post("/organizations", {"name": "Org", "slug": slug}, headers=USER1_HEADERS)

        # Create article as member
        api_post("/articles", {
            "title": f"Org Article {UNIQUE}",
            "body_markdown": "body",
            "published": True
        }, headers=USER1_HEADERS)

        resp = api_get(f"/organizations/{slug}/articles")
        assert resp.status_code == 200
        assert "data" in resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 10: Search
# ════════════════════════════════════════════════════════════════════


class TestSearch:

    def test_search_articles_by_title(self):
        """GET /search/articles?q=X searches by title."""
        unique_word = f"xyzzy{UNIQUE}"
        api_post("/articles", {
            "title": f"Article with {unique_word}",
            "body_markdown": "plain body",
            "published": True
        }, headers=USER1_HEADERS)

        resp = api_get("/search/articles", params={"q": unique_word})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1
        assert any(unique_word in a["title"] for a in data["data"])

    def test_search_articles_by_body(self):
        """GET /search/articles?q=X searches body."""
        unique_word = f"qwerty{UNIQUE}"
        api_post("/articles", {
            "title": "Normal Title",
            "body_markdown": f"This contains {unique_word} in body",
            "published": True
        }, headers=USER1_HEADERS)

        resp = api_get("/search/articles", params={"q": unique_word})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_search_missing_query(self):
        """GET /search/articles without q returns 400."""
        resp = api_get("/search/articles")
        assert resp.status_code == 400

    def test_search_only_published(self):
        """Search does not return unpublished articles."""
        unique_word = f"secret{UNIQUE}"
        api_post("/articles", {
            "title": f"Unpublished {unique_word}",
            "body_markdown": "secret",
            "published": False
        }, headers=USER1_HEADERS)

        resp = api_get("/search/articles", params={"q": unique_word})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    def test_search_pagination(self):
        """Search supports pagination."""
        resp = api_get("/search/articles", params={"q": "article", "per_page": 5, "page": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["per_page"] == 5
        assert data["meta"]["page"] == 1


# ════════════════════════════════════════════════════════════════════
# PART 11: Reading List
# ════════════════════════════════════════════════════════════════════


class TestReadingList:

    def test_reading_list_empty(self):
        """GET /readinglist returns empty list initially."""
        new_user = str(uuid.uuid4())
        resp = api_get("/readinglist", headers={"X-User-Id": new_user})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    def test_reading_list_after_bookmark(self):
        """Bookmarking (readinglist reaction) adds to reading list."""
        # Create article
        article = api_post("/articles", {
            "title": f"Bookmark Me {UNIQUE}",
            "body_markdown": "Great content",
            "published": True
        }, headers=USER1_HEADERS).json()

        # Bookmark (readinglist reaction) by user2
        api_post(f"/articles/{article['id']}/reactions", {
            "category": "readinglist"
        }, headers=USER2_HEADERS)

        # Check reading list
        resp = api_get("/readinglist", headers=USER2_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        ids = [a["id"] for a in data["data"]]
        assert article["id"] in ids

    def test_reading_list_remove_bookmark(self):
        """Removing readinglist reaction removes from reading list."""
        article = api_post("/articles", {
            "title": f"Unbookmark Me {UNIQUE}",
            "body_markdown": "content",
            "published": True
        }, headers=USER1_HEADERS).json()

        # Add to reading list
        api_post(f"/articles/{article['id']}/reactions", {"category": "readinglist"}, headers=USER2_HEADERS)
        # Remove from reading list (toggle off)
        api_post(f"/articles/{article['id']}/reactions", {"category": "readinglist"}, headers=USER2_HEADERS)

        resp = api_get("/readinglist", headers=USER2_HEADERS)
        ids = [a["id"] for a in resp.json()["data"]]
        assert article["id"] not in ids

    def test_reading_list_requires_auth(self):
        """GET /readinglist without auth returns 401."""
        resp = api_get("/readinglist", headers={})
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 12: Feed
# ════════════════════════════════════════════════════════════════════


class TestFeed:

    def test_feed_requires_auth(self):
        """GET /articles/feed without auth returns 401."""
        resp = api_get("/articles/feed", headers={})
        assert resp.status_code == 401

    def test_feed_returns_followed_user_articles(self):
        """Feed includes articles from followed users."""
        # User3 creates article
        article = api_post("/articles", {
            "title": f"Feed User Article {UNIQUE}",
            "body_markdown": "body for feed",
            "published": True
        }, headers=USER3_HEADERS).json()

        # User2 follows User3
        api_get("/users/me", headers=USER3_HEADERS)  # ensure exists
        api_post(f"/follows/users/{USER3_ID}", headers=USER2_HEADERS)

        # User2's feed should include the article
        resp = api_get("/articles/feed", headers=USER2_HEADERS)
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["data"]]
        assert article["id"] in ids

    def test_feed_returns_followed_tag_articles(self):
        """Feed includes articles tagged with followed tags."""
        tag_name = f"feedtag-{UNIQUE}"
        tag = api_post("/tags", {"name": tag_name}, headers=USER1_HEADERS).json()

        # Create article with this tag
        article = api_post("/articles", {
            "title": f"Feed Tag Article {UNIQUE}",
            "body_markdown": "body",
            "published": True,
            "tags": [tag_name]
        }, headers=USER1_HEADERS).json()

        # User3 follows the tag
        api_post(f"/follows/tags/{tag['id']}", headers=USER3_HEADERS)

        # User3's feed should include the article
        resp = api_get("/articles/feed", headers=USER3_HEADERS)
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["data"]]
        assert article["id"] in ids

    def test_feed_pagination(self):
        """Feed supports pagination."""
        resp = api_get("/articles/feed", params={"per_page": 5, "page": 1}, headers=USER1_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["per_page"] == 5
        assert data["meta"]["page"] == 1

    def test_feed_structure(self):
        """Feed response has correct structure."""
        resp = api_get("/articles/feed", headers=USER1_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)


# ════════════════════════════════════════════════════════════════════
# PART 13: Edge Cases and Business Rules
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_article_not_found(self):
        """GET /articles/{id} with non-existent ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/articles/{fake_id}")
        assert resp.status_code == 404

    def test_tag_not_found(self):
        """GET /tags/{id} with non-existent ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/tags/{fake_id}")
        assert resp.status_code == 404

    def test_comment_not_found(self):
        """GET /comments/{id} with non-existent ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/comments/{fake_id}")
        assert resp.status_code == 404

    def test_listing_not_found(self):
        """GET /listings/{id} with non-existent ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/listings/{fake_id}")
        assert resp.status_code == 404

    def test_org_not_found(self):
        """GET /organizations/{slug} with non-existent slug returns 404."""
        resp = api_get("/organizations/nonexistent-org-xyz")
        assert resp.status_code == 404

    def test_articles_count_only_published(self):
        """articles_count counts only published articles."""
        new_user_id = str(uuid.uuid4())
        headers = {"X-User-Id": new_user_id, "Content-Type": "application/json"}

        # Create 2 published, 1 unpublished
        api_post("/articles", {"title": "Pub1", "body_markdown": "b", "published": True}, headers=headers)
        api_post("/articles", {"title": "Pub2", "body_markdown": "b", "published": True}, headers=headers)
        api_post("/articles", {"title": "Draft", "body_markdown": "b", "published": False}, headers=headers)

        resp = api_get("/users/me", headers=headers)
        assert resp.json()["articles_count"] == 2

    def test_slug_uniqueness(self):
        """Two articles with same title get unique slugs."""
        title = f"Same Title {UNIQUE}"
        a1 = api_post("/articles", {
            "title": title,
            "body_markdown": "body1",
            "published": True
        }, headers=USER1_HEADERS).json()

        a2 = api_post("/articles", {
            "title": title,
            "body_markdown": "body2",
            "published": True
        }, headers=USER1_HEADERS).json()

        assert a1["slug"] != a2["slug"]

    def test_reading_time_ceil(self):
        """Reading time rounds up: 201 words = 2 minutes."""
        body = " ".join(["word"] * 201)
        resp = api_post("/articles", {
            "title": f"Ceil Test {UNIQUE}",
            "body_markdown": body,
            "published": True
        }, headers=USER1_HEADERS)
        assert resp.json()["reading_time"] == 2

    def test_reading_time_exact_200(self):
        """200 words = exactly 1 minute."""
        body = " ".join(["word"] * 200)
        resp = api_post("/articles", {
            "title": f"Exact 200 {UNIQUE}",
            "body_markdown": body,
            "published": True
        }, headers=USER1_HEADERS)
        assert resp.json()["reading_time"] == 1

    def test_public_endpoints_no_auth_needed(self):
        """Public endpoints work without auth."""
        # GET /articles
        resp = api_get("/articles")
        assert resp.status_code == 200

        # GET /tags
        resp = api_get("/tags")
        assert resp.status_code == 200

        # GET /listings
        resp = api_get("/listings")
        assert resp.status_code == 200

        # GET /organizations
        resp = api_get("/organizations")
        assert resp.status_code == 200
