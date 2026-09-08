"""
BackendForge — L3 Workflow Tests for Forem Developer Community Platform
Complex multi-step workflows that cross multiple entity types.
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


class TestArticleLifecycleWorkflow:
    """Pattern 2+5+7: Full article lifecycle with computed fields, reactions, and comments."""

    def test_article_publish_react_comment_score(self):
        h_author = headers()
        h_reader1 = headers()
        h_reader2 = headers()

        # 1. Create draft article
        body_text = " ".join(["word"] * 600)
        art = post("/articles", {
            "title": f"Lifecycle-{unique()}",
            "body_markdown": body_text,
            "published": False,
            "tags": ["python", "tutorial"]
        }, h_author).json()
        assert art["published"] is False
        assert art["published_at"] is None
        assert art["reading_time"] == math.ceil(600 / 200)  # 3

        # 2. Verify not in public list
        r = get("/articles", params={"tag": "python"})
        ids = [a["id"] for a in r.json()["data"]]
        assert art["id"] not in ids

        # 3. Publish
        pub = put(f"/articles/{art['id']}", {"published": True}, h_author).json()
        assert pub["published"] is True
        assert pub["published_at"] is not None

        # 4. Now in public list
        r2 = get("/articles", params={"tag": "python"})
        ids2 = [a["id"] for a in r2.json()["data"]]
        assert art["id"] in ids2

        # 5. Readers react
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h_reader1)
        post(f"/articles/{art['id']}/reactions", {"category": "unicorn"}, h_reader1)
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h_reader2)

        # 6. Reader comments
        c1 = post(f"/articles/{art['id']}/comments", {"body": "Great post!"}, h_reader1).json()
        c2 = post(f"/articles/{art['id']}/comments", {"body": "Thanks!", "parent_id": c1["id"]}, h_author).json()
        assert c2["parent_id"] == c1["id"]

        # 7. Verify score
        art2 = get(f"/articles/{art['id']}", h_author).json()
        assert art2["reactions_count"] == 3
        assert art2["comments_count"] == 2
        assert art2["score"] == (3 * 2) + (2 * 3)  # 12

        # 8. Verify reading_time preserved
        assert art2["reading_time"] == 3


class TestFollowFeedWorkflow:
    """Pattern 3+5: Feed algorithm with follows."""

    def test_feed_includes_followed_user_articles(self):
        h_follower = headers()
        h_author = headers()
        author = get("/users/me", h_author).json()

        # 1. Author creates published article
        art = post("/articles", {"title": f"FeedArt-{unique()}", "body_markdown": "feed content", "published": True}, h_author).json()

        # 2. Follower follows author
        r = post(f"/follows/users/{author['id']}", None, h_follower)
        assert r.status_code == 201

        # 3. Follower's feed should include the article
        feed = get("/articles/feed", h_follower).json()
        feed_ids = [a["id"] for a in feed["data"]]
        assert art["id"] in feed_ids

        # 4. Unfollow
        delete(f"/follows/users/{author['id']}", h_follower)

        # 5. Feed should no longer include (unless backfill)
        feed2 = get("/articles/feed", h_follower).json()
        feed_ids2 = [a["id"] for a in feed2["data"]]
        # Article might still be there via backfill, but at least unfollow worked
        followed = get("/follows/users", h_follower).json()["data"]
        assert author["id"] not in [u["id"] for u in followed]

    def test_feed_includes_followed_tag_articles(self):
        h_follower = headers()
        h_author = headers()
        tag_name = f"feedtag{unique()}"

        # 1. Create tag and follow it
        tag = post("/tags", {"name": tag_name}, h_follower).json()
        post(f"/follows/tags/{tag['id']}", None, h_follower)

        # 2. Another user creates article with that tag
        art = post("/articles", {"title": f"TagFeed-{unique()}", "body_markdown": "content", "published": True, "tags": [tag_name]}, h_author).json()

        # 3. Feed should include it
        feed = get("/articles/feed", h_follower).json()
        feed_ids = [a["id"] for a in feed["data"]]
        assert art["id"] in feed_ids


class TestOrganizationWorkflow:
    """Pattern 5+6+7: Organization creation, membership, and articles."""

    def test_org_lifecycle_with_members_and_articles(self):
        h1 = headers()
        h2 = headers()
        h3 = headers()
        u1 = get("/users/me", h1).json()
        u2 = get("/users/me", h2).json()

        # 1. Create organization
        slug = f"devteam-{unique()}"
        org = post("/organizations", {"name": f"Dev Team {unique()}", "slug": slug, "description": "A dev org"}, h1).json()
        assert org["slug"] == slug
        assert "id" in org

        # 2. Verify creator is a member
        members = get(f"/organizations/{slug}/members").json()["data"]
        member_ids = [m["id"] for m in members]
        assert u1["id"] in member_ids

        # 3. Add user2 as member
        r = post(f"/organizations/{slug}/members", {"username": u2["username"]}, h1)
        assert r.status_code == 201

        # 4. Non-member cannot add members
        r2 = post(f"/organizations/{slug}/members", {"username": "someone"}, h3)
        assert r2.status_code == 403

        # 5. User2 creates published article (org article)
        art = post("/articles", {"title": f"OrgArt-{unique()}", "body_markdown": "org content", "published": True}, h2).json()

        # 6. Org articles endpoint shows member articles
        org_arts = get(f"/organizations/{slug}/articles").json()["data"]
        art_ids = [a["id"] for a in org_arts]
        assert art["id"] in art_ids

        # 7. Non-member cannot update org
        r3 = put(f"/organizations/{slug}", {"name": "Hacked"}, h3)
        assert r3.status_code == 403

        # 8. Member can update
        r4 = put(f"/organizations/{slug}", {"description": "Updated desc"}, h2)
        assert r4.status_code == 200

        # 9. Cannot remove last member after removing first
        delete(f"/organizations/{slug}/members/{u1['username']}", h2)
        r5 = delete(f"/organizations/{slug}/members/{u2['username']}", h2)
        assert r5.status_code == 400


class TestCommentThreadingWorkflow:
    """Pattern 2+7: Comment threading with soft delete."""

    def test_threaded_comments_with_soft_delete(self):
        h1 = headers()
        h2 = headers()
        h3 = headers()

        # 1. Create article
        art = post("/articles", {"title": f"Threaded-{unique()}", "body_markdown": "x", "published": True}, h1).json()

        # 2. First comment
        c1 = post(f"/articles/{art['id']}/comments", {"body": "First comment!"}, h2).json()
        assert c1["parent_id"] is None

        # 3. Reply to first comment
        c2 = post(f"/articles/{art['id']}/comments", {"body": "Reply to first", "parent_id": c1["id"]}, h3).json()
        assert c2["parent_id"] == c1["id"]

        # 4. Reply to reply
        c3 = post(f"/articles/{art['id']}/comments", {"body": "Nested reply", "parent_id": c2["id"]}, h1).json()
        assert c3["parent_id"] == c2["id"]

        # 5. Soft-delete the middle comment
        r = delete(f"/comments/{c2['id']}", h3)
        assert r.status_code == 200
        deleted = r.json()
        assert deleted["body"] == "[deleted]"
        assert deleted["user_id"] is None

        # 6. Child comment still exists and references deleted parent
        c3_fetched = get(f"/comments/{c3['id']}").json()
        assert c3_fetched["parent_id"] == c2["id"]
        assert c3_fetched["body"] == "Nested reply"

        # 7. Comments list still contains all comments
        comments = get(f"/articles/{art['id']}/comments").json()["data"]
        comment_ids = [c["id"] for c in comments]
        assert c1["id"] in comment_ids
        assert c2["id"] in comment_ids
        assert c3["id"] in comment_ids

        # 8. Article comments_count should be at least 2 (soft-deleted may or may not count)
        art2 = get(f"/articles/{art['id']}", h1).json()
        assert art2["comments_count"] >= 2


class TestReactionReadingListWorkflow:
    """Pattern 5+6: Reactions, reading list, and user-specific state."""

    def test_reading_list_via_reactions(self):
        h_author = headers()
        h_reader = headers()

        # 1. Create multiple articles
        art1 = post("/articles", {"title": f"RL1-{unique()}", "body_markdown": "x", "published": True}, h_author).json()
        art2 = post("/articles", {"title": f"RL2-{unique()}", "body_markdown": "y", "published": True}, h_author).json()
        art3 = post("/articles", {"title": f"RL3-{unique()}", "body_markdown": "z", "published": True}, h_author).json()

        # 2. Reader adds art1 and art2 to reading list
        r1 = post(f"/articles/{art1['id']}/reactions", {"category": "readinglist"}, h_reader)
        assert r1.json()["result"] == "created"
        r2 = post(f"/articles/{art2['id']}/reactions", {"category": "readinglist"}, h_reader)
        assert r2.json()["result"] == "created"

        # 3. Reading list has both
        rl = get("/readinglist", h_reader).json()["data"]
        rl_ids = [a["id"] for a in rl]
        assert art1["id"] in rl_ids
        assert art2["id"] in rl_ids
        assert art3["id"] not in rl_ids

        # 4. Remove art1 from reading list (toggle)
        r3 = post(f"/articles/{art1['id']}/reactions", {"category": "readinglist"}, h_reader)
        assert r3.json()["result"] == "removed"

        # 5. Verify reading list updated
        rl2 = get("/readinglist", h_reader).json()["data"]
        rl2_ids = [a["id"] for a in rl2]
        assert art1["id"] not in rl2_ids
        assert art2["id"] in rl2_ids

        # 6. Liking an article doesn't add to reading list
        post(f"/articles/{art3['id']}/reactions", {"category": "like"}, h_reader)
        rl3 = get("/readinglist", h_reader).json()["data"]
        rl3_ids = [a["id"] for a in rl3]
        assert art3["id"] not in rl3_ids

        # 7. Verify user_reactions in GET reactions
        rx = get(f"/articles/{art2['id']}/reactions", h_reader).json()
        assert "readinglist" in rx.get("user_reactions", [])


class TestArticleDeleteCascade:
    """Pattern 7: Deleting article removes comments and reactions."""

    def test_delete_article_removes_from_listings(self):
        h1 = headers()
        h2 = headers()

        # 1. Create article
        art = post("/articles", {"title": f"DelCasc-{unique()}", "body_markdown": "body", "published": True}, h1).json()

        # 2. Add comments and reactions
        post(f"/articles/{art['id']}/comments", {"body": "comment"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h2)
        post(f"/articles/{art['id']}/reactions", {"category": "readinglist"}, h2)

        # 3. Verify they exist
        comments = get(f"/articles/{art['id']}/comments").json()["data"]
        assert len(comments) >= 1
        rl = get("/readinglist", h2).json()["data"]
        assert art["id"] in [a["id"] for a in rl]

        # 4. Delete article
        r = delete(f"/articles/{art['id']}", h1)
        assert r.status_code == 204

        # 5. Article gone
        assert get(f"/articles/{art['id']}", h1).status_code == 404

        # 6. Reading list should not include deleted article
        rl2 = get("/readinglist", h2).json()["data"]
        assert art["id"] not in [a["id"] for a in rl2]


class TestUserProfileWorkflow:
    """Pattern 1+5: Auto-provisioning and computed fields on user profile."""

    def test_user_auto_provision_and_articles_count(self):
        h = headers()
        uid = h["X-User-Id"]

        # 1. First request auto-creates user
        me = get("/users/me", h).json()
        assert me["id"] == uid
        assert me["username"] == f"user_{uid[:8]}"
        assert "joined_at" in me
        assert me["articles_count"] == 0

        # 2. Create published article
        post("/articles", {"title": f"UAP1-{unique()}", "body_markdown": "x", "published": True}, h)
        post("/articles", {"title": f"UAP2-{unique()}", "body_markdown": "y", "published": True}, h)
        post("/articles", {"title": f"UAPDraft-{unique()}", "body_markdown": "z", "published": False}, h)

        # 3. articles_count counts only published
        me2 = get(f"/users/{me['username']}").json()
        assert me2["articles_count"] == 2

        # 4. Followers endpoint works
        r = get(f"/users/{me['username']}/followers")
        assert r.status_code == 200
        assert "data" in r.json()


class TestSlugUniqueness:
    """Pattern 8: Slug uniqueness handling."""

    def test_duplicate_title_gets_unique_slug(self):
        h = headers()
        title = f"Same Title {unique()}"
        art1 = post("/articles", {"title": title, "body_markdown": "a", "published": True}, h).json()
        art2 = post("/articles", {"title": title, "body_markdown": "b", "published": True}, h).json()

        assert art1["slug"] != art2["slug"]
        assert art1["id"] != art2["id"]


class TestMultiUserReactionIsolation:
    """Pattern 6: Each user's reactions are independent."""

    def test_reactions_isolated_per_user(self):
        h_author = headers()
        h_user1 = headers()
        h_user2 = headers()

        art = post("/articles", {"title": f"IsoReact-{unique()}", "body_markdown": "x", "published": True}, h_author).json()

        # 1. User1 likes
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h_user1)

        # 2. User2 likes and unicorns
        post(f"/articles/{art['id']}/reactions", {"category": "like"}, h_user2)
        post(f"/articles/{art['id']}/reactions", {"category": "unicorn"}, h_user2)

        # 3. Check user1's reactions
        rx1 = get(f"/articles/{art['id']}/reactions", h_user1).json()
        assert "like" in rx1.get("user_reactions", [])
        assert "unicorn" not in rx1.get("user_reactions", [])

        # 4. Check user2's reactions
        rx2 = get(f"/articles/{art['id']}/reactions", h_user2).json()
        assert "like" in rx2.get("user_reactions", [])
        assert "unicorn" in rx2.get("user_reactions", [])

        # 5. Total counts are combined
        like_count = next((r["count"] for r in rx1["reactions"] if r["category"] == "like"), 0)
        assert like_count == 2


class TestFollowersListWorkflow:
    """Pattern 2+5: Followers list shows correct data."""

    def test_followers_list_after_follows(self):
        h_target = headers()
        h_f1 = headers()
        h_f2 = headers()
        target = get("/users/me", h_target).json()
        get("/users/me", h_f1)  # ensure exists
        get("/users/me", h_f2)  # ensure exists

        # 1. Two users follow target
        post(f"/follows/users/{target['id']}", None, h_f1)
        post(f"/follows/users/{target['id']}", None, h_f2)

        # 2. Check followers list
        r = get(f"/users/{target['username']}/followers")
        assert r.status_code == 200
        followers = r.json()["data"]
        follower_ids = [f["id"] for f in followers]
        assert h_f1["X-User-Id"] in follower_ids
        assert h_f2["X-User-Id"] in follower_ids

        # 3. Unfollow
        delete(f"/follows/users/{target['id']}", h_f1)

        # 4. Verify updated
        r2 = get(f"/users/{target['username']}/followers")
        follower_ids2 = [f["id"] for f in r2.json()["data"]]
        assert h_f1["X-User-Id"] not in follower_ids2
        assert h_f2["X-User-Id"] in follower_ids2
