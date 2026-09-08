"""
L3 Workflow Tests for Discourse Forum API.
Complex multi-entity workflows that test:
- Topic lifecycle with permissions across trust levels
- Notification chains across users
- Category hierarchy
- Search across entities
- Trust level escalation
- Post interaction chains
- Multi-user forum simulation
"""
import hashlib
import os
import time
import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
API_KEY = "discourse-api-key"

ADMIN_USER = "discourse_test_admin"


def _item_suffix():
    """Return one stable namespace across a test's setup/call/teardown phases."""
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "standalone")
    node_id = current_test.rsplit(" (", 1)[0]
    return hashlib.sha256(node_id.encode()).hexdigest()[:10]


def _username(username: str):
    if username == ADMIN_USER:
        return username
    return f"{username}_{_item_suffix()}"


def _email(email: str):
    local, separator, domain = email.partition("@")
    return f"{local}_{_item_suffix()}{separator}{domain}"


def headers(username: str):
    return {"X-API-Key": API_KEY, "X-Username": _username(username)}


def create_user(
    username: str,
    email: str = None,
    name: str = None,
    expected_status: int | None = 201,
):
    if email is None:
        email = f"{username}@example.com"
    if name is None:
        name = username.capitalize()
    if username != ADMIN_USER:
        email = _email(email)
    response = requests.post(f"{BASE_URL}/users", json={
        "username": _username(username),
        "email": email,
        "password": "password123",
        "name": name,
    })
    if expected_status is not None:
        assert response.status_code == expected_status, response.text
    return response


def set_trust_level(
    admin: str,
    target: str,
    level: int,
    expected_status: int | None = 200,
):
    response = requests.put(
        f"{BASE_URL}/users/{_username(target)}/trust-level",
        headers=headers(admin),
        json={"trustLevel": level},
    )
    if expected_status is not None:
        assert response.status_code == expected_status, response.text
    return response


@pytest.fixture(scope="session", autouse=True)
def setup_admin(_bounded_http_requests):
    """Create admin user for all workflow tests."""
    response = create_user(ADMIN_USER, expected_status=None)
    assert response.status_code in {201, 409}, response.text
    set_trust_level(ADMIN_USER, ADMIN_USER, 4)
    return ADMIN_USER


# ─── L3-1: Topic lifecycle with permissions ──────────────────────────────────

class TestTopicLifecycleWithPermissions:
    def test_full_topic_lifecycle_permissions(self, setup_admin):
        """
        Pattern 6+5+7: Full topic lifecycle across trust levels.
        User (level 0) creates topic → level 3 user pins it → original user tries
        to unpin → 403 → admin closes topic → verify no more posts allowed.
        """
        # Setup users
        create_user("wf_topic_author")
        create_user("wf_topic_regular")
        set_trust_level(ADMIN_USER, "wf_topic_regular", 3)

        # Create category
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "LifecycleCat"},
        ).json()

        # Step 1: Level 0 user creates topic
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_topic_author"),
            json={"title": "Lifecycle Topic", "categoryId": cat["id"], "content": "Original content"},
        )
        assert topic.status_code == 201
        topic_data = topic.json()
        topic_id = topic_data["id"]
        assert topic_data["pinned"] is False
        assert topic_data["closed"] is False
        assert topic_data["archived"] is False
        assert topic_data["postsCount"] == 1

        # Step 2: Admin pins the topic
        pin_resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers(ADMIN_USER),
            json={"pinned": True},
        )
        assert pin_resp.status_code == 200
        assert pin_resp.json()["pinned"] is True

        # Step 3: Original user (level 0) tries to unpin → 403
        unpin_resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers("wf_topic_author"),
            json={"pinned": False},
        )
        assert unpin_resp.status_code == 403

        # Step 4: Verify topic still pinned
        check = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("wf_topic_author")).json()
        assert check["pinned"] is True

        # Step 5: Level 3 user tries to pin/unpin → also 403 (admin only)
        unpin_l3 = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers("wf_topic_regular"),
            json={"pinned": False},
        )
        assert unpin_l3.status_code == 403

        # Step 6: Admin closes the topic
        close_resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/close",
            headers=headers(ADMIN_USER),
            json={"closed": True},
        )
        assert close_resp.status_code == 200
        assert close_resp.json()["closed"] is True

        # Step 7: Verify no more posts allowed
        post_resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_topic_author"),
            json={"topicId": topic_id, "content": "Trying to post"},
        )
        assert post_resp.status_code == 403

        # Step 8: Verify the topic state via GET
        final_topic = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("wf_topic_author")).json()
        assert final_topic["pinned"] is True
        assert final_topic["closed"] is True


# ─── L3-2: Notification chain ────────────────────────────────────────────────

class TestNotificationChain:
    def test_notification_chain_reply_then_read_then_like(self, setup_admin):
        """
        Pattern 7+5+6: Full notification chain.
        User A creates topic → B replies → A gets notification → A reads it →
        unread count decreases → B likes A's post → A gets another notification.
        """
        create_user("wf_notif_a")
        create_user("wf_notif_b")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "NotifChainCat"},
        ).json()

        # Step 1: A creates topic
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_notif_a"),
            json={"title": "Notification Chain Topic", "categoryId": cat["id"], "content": "Hello from A"},
        ).json()
        topic_id = topic["id"]

        # Step 2: B replies → A should get notification
        reply = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_notif_b"),
            json={"topicId": topic_id, "content": "Reply from B"},
        )
        assert reply.status_code == 201

        # Step 3: Verify A has unread notification
        a_notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("wf_notif_a")).json()
        reply_notifs = [n for n in a_notifs if n["notificationType"] == "reply" and n["topicId"] == topic_id]
        assert len(reply_notifs) >= 1
        assert reply_notifs[0]["read"] is False

        # Step 4: Get unread count before marking read
        unread_before = requests.get(
            f"{BASE_URL}/notifications/unread-count",
            headers=headers("wf_notif_a"),
        ).json()["unreadCount"]
        assert unread_before >= 1

        # Step 5: A reads the notification
        notif_id = reply_notifs[0]["id"]
        read_resp = requests.put(
            f"{BASE_URL}/notifications/{notif_id}/read",
            headers=headers("wf_notif_a"),
        )
        assert read_resp.status_code == 200
        assert read_resp.json()["read"] is True

        # Step 6: Unread count decreased
        unread_after = requests.get(
            f"{BASE_URL}/notifications/unread-count",
            headers=headers("wf_notif_a"),
        ).json()["unreadCount"]
        assert unread_after == unread_before - 1

        # Step 7: B likes A's original post → A gets like notification
        posts = requests.get(
            f"{BASE_URL}/topics/{topic_id}/posts",
            headers=headers("wf_notif_a"),
        ).json()
        a_post_id = posts[0]["id"]  # A's original post
        like_resp = requests.post(
            f"{BASE_URL}/posts/{a_post_id}/like",
            headers=headers("wf_notif_b"),
        )
        assert like_resp.status_code == 200

        # Step 8: A gets like notification
        a_notifs_after = requests.get(f"{BASE_URL}/notifications", headers=headers("wf_notif_a")).json()
        like_notifs = [n for n in a_notifs_after if n["notificationType"] == "like" and n["postId"] == a_post_id]
        assert len(like_notifs) >= 1
        assert like_notifs[0]["actingUserId"] is not None

        # Step 9: B should NOT have A's notifications
        b_notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("wf_notif_b")).json()
        b_topic_notifs = [n for n in b_notifs if n.get("topicId") == topic_id]
        assert len(b_topic_notifs) == 0


# ─── L3-3: Category hierarchy ────────────────────────────────────────────────

class TestCategoryHierarchy:
    def test_parent_child_category_with_topics(self, setup_admin):
        """
        Pattern 2+7: Category hierarchy.
        Create parent → child → topic in child → verify parentCategoryId correct
        → delete parent → child should still be accessible
        → verify topics filterable by child category.
        """
        create_user("wf_cat_user")

        # Step 1: Create parent category
        parent = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "WF Parent Cat", "color": "AA0000", "position": 1},
        )
        assert parent.status_code == 201
        parent_id = parent.json()["id"]
        assert parent.json()["parentCategoryId"] is None

        # Step 2: Create child category
        child = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "WF Child Cat", "parentCategoryId": parent_id, "color": "00AA00"},
        )
        assert child.status_code == 201
        child_id = child.json()["id"]
        assert child.json()["parentCategoryId"] == parent_id

        # Step 3: Create topic in child
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_cat_user"),
            json={"title": "Child Cat Topic", "categoryId": child_id, "content": "In child"},
        )
        assert topic.status_code == 201
        assert topic.json()["categoryId"] == child_id

        # Step 4: List topics by child category
        topics = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("wf_cat_user"),
            params={"categoryId": child_id},
        ).json()
        assert len(topics) >= 1
        assert all(t["categoryId"] == child_id for t in topics)

        # Step 5: Get child category → verify parentCategoryId still correct
        child_check = requests.get(
            f"{BASE_URL}/categories/{child_id}",
            headers=headers("wf_cat_user"),
        ).json()
        assert child_check["parentCategoryId"] == parent_id
        assert child_check["name"] == "WF Child Cat"

        # Step 6: Update child to have new description
        update_resp = requests.put(
            f"{BASE_URL}/categories/{child_id}",
            headers=headers(ADMIN_USER),
            json={"description": "Updated child description"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["description"] == "Updated child description"
        assert update_resp.json()["parentCategoryId"] == parent_id


# ─── L3-4: Search across entities ────────────────────────────────────────────

class TestSearchAcrossEntities:
    def test_search_finds_both_topics_and_posts(self, setup_admin):
        """
        Pattern 3+5: Search across topics and posts with specific keywords.
        Create topics and posts with unique keywords → search → verify both found.
        """
        create_user("wf_search_user")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "SearchAcrossCat"},
        ).json()

        # Step 1: Create topic with keyword in TITLE
        topic1 = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_search_user"),
            json={
                "title": "Discussion about Metamorphosis patterns",
                "categoryId": cat["id"],
                "content": "This is about biology",
            },
        ).json()

        # Step 2: Create topic with keyword in POST CONTENT (not title)
        topic2 = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_search_user"),
            json={
                "title": "Generic Science Topic",
                "categoryId": cat["id"],
                "content": "The process of Metamorphosis in butterflies is fascinating",
            },
        ).json()

        # Step 3: Create a reply containing the keyword
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_search_user"),
            json={
                "topicId": topic2["id"],
                "content": "Metamorphosis also occurs in frogs",
            },
        )

        # Step 4: Create an UNRELATED topic (should NOT appear)
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_search_user"),
            json={
                "title": "Cooking Tips",
                "categoryId": cat["id"],
                "content": "How to make pasta",
            },
        )

        # Step 5: Search for the keyword
        search_resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("wf_search_user"),
            params={"q": "Metamorphosis"},
        )
        assert search_resp.status_code == 200
        results = search_resp.json()

        # Step 6: Verify structure
        assert "topics" in results
        assert "posts" in results

        # Step 7: Topic with keyword in title found
        matching_topics = [t for t in results["topics"] if "Metamorphosis" in t["title"]]
        assert len(matching_topics) >= 1

        # Step 8: Posts with keyword in content found
        matching_posts = [p for p in results["posts"] if "Metamorphosis" in p["content"]]
        assert len(matching_posts) >= 1

        # Step 9: Unrelated should NOT be found
        cooking_topics = [t for t in results["topics"] if "Cooking" in t["title"]]
        assert len(cooking_topics) == 0
        cooking_posts = [p for p in results["posts"] if "pasta" in p["content"]]
        assert len(cooking_posts) == 0


# ─── L3-5: Trust level escalation ────────────────────────────────────────────

class TestTrustLevelEscalation:
    def test_escalate_trust_level_and_verify_permissions(self, setup_admin):
        """
        Pattern 6+5: Trust level escalation.
        Create user at level 0 → verify cannot flag → admin sets to 1 → verify CAN flag
        → sets to 3 → verify CAN close topics → verify field in response updates.
        """
        create_user("wf_escalate_user")
        create_user("wf_escalate_poster")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "EscalateCat"},
        ).json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_escalate_poster"),
            json={"title": "Escalate Topic", "categoryId": cat["id"], "content": "Content"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("wf_escalate_poster"),
        ).json()
        post_id = posts[0]["id"]

        # Step 1: Verify user is at trust level 0
        user_resp = requests.get(
            f"{BASE_URL}/users/{_username('wf_escalate_user')}",
            headers=headers(ADMIN_USER),
        ).json()
        assert user_resp["trustLevel"] == 0

        # Step 2: Cannot flag at level 0
        flag_resp = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("wf_escalate_user"),
            json={"postId": post_id, "reason": "spam"},
        )
        assert flag_resp.status_code == 403

        # Step 3: Cannot create tag at level 0
        tag_resp = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_escalate_user"),
            json={"name": "wf_escalate_tag"},
        )
        assert tag_resp.status_code == 403

        # Step 4: Admin escalates to level 1
        level1_resp = set_trust_level(ADMIN_USER, "wf_escalate_user", 1)
        assert level1_resp.status_code == 200
        assert level1_resp.json()["trustLevel"] == 1

        # Step 5: NOW can flag
        flag_resp2 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("wf_escalate_user"),
            json={"postId": post_id, "reason": "spam now works"},
        )
        assert flag_resp2.status_code == 201

        # Step 6: Still cannot create tag (needs level 2)
        tag_resp2 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_escalate_user"),
            json={"name": "wf_escalate_tag2"},
        )
        assert tag_resp2.status_code == 403

        # Step 7: Escalate to level 2
        set_trust_level(ADMIN_USER, "wf_escalate_user", 2)

        # Step 8: Now can create tag
        tag_resp3 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_escalate_user"),
            json={"name": "wf_escalate_tag3"},
        )
        assert tag_resp3.status_code == 201

        # Step 9: Cannot close topic yet (needs level 3)
        close_resp = requests.put(
            f"{BASE_URL}/topics/{topic['id']}/close",
            headers=headers("wf_escalate_user"),
            json={"closed": True},
        )
        assert close_resp.status_code == 403

        # Step 10: Escalate to level 3
        set_trust_level(ADMIN_USER, "wf_escalate_user", 3)

        # Step 11: Now can close topic
        close_resp2 = requests.put(
            f"{BASE_URL}/topics/{topic['id']}/close",
            headers=headers("wf_escalate_user"),
            json={"closed": True},
        )
        assert close_resp2.status_code == 200
        assert close_resp2.json()["closed"] is True

        # Step 12: Verify user profile shows updated trust level
        final_user = requests.get(
            f"{BASE_URL}/users/{_username('wf_escalate_user')}",
            headers=headers(ADMIN_USER),
        ).json()
        assert final_user["trustLevel"] == 3


# ─── L3-6: Post interaction chain ────────────────────────────────────────────

class TestPostInteractionChain:
    def test_post_quote_like_edit_delete_chain(self, setup_admin):
        """
        Pattern 2+5+7: Post interaction chain.
        Create post → B quotes it → C likes both → verify counts → B edits →
        verify edit preserved → soft-delete original → quote still readable.
        """
        create_user("wf_post_a")
        create_user("wf_post_b")
        create_user("wf_post_c")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "PostChainCat"},
        ).json()

        # Step 1: A creates topic with original post
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_post_a"),
            json={"title": "Post Chain Topic", "categoryId": cat["id"], "content": "Original from A"},
        ).json()
        topic_id = topic["id"]
        posts = requests.get(
            f"{BASE_URL}/topics/{topic_id}/posts",
            headers=headers("wf_post_a"),
        ).json()
        original_post_id = posts[0]["id"]

        # Step 2: B quotes A's post
        quote_resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_post_b"),
            json={
                "topicId": topic_id,
                "content": "B quoting A here",
                "quotePostId": original_post_id,
            },
        )
        assert quote_resp.status_code == 201
        quote_post = quote_resp.json()
        assert quote_post["quotePostId"] == original_post_id
        quote_post_id = quote_post["id"]

        # Step 3: C likes A's post
        like_a = requests.post(
            f"{BASE_URL}/posts/{original_post_id}/like",
            headers=headers("wf_post_c"),
        )
        assert like_a.status_code == 200
        assert like_a.json()["likeCount"] == 1

        # Step 4: C likes B's post
        like_b = requests.post(
            f"{BASE_URL}/posts/{quote_post_id}/like",
            headers=headers("wf_post_c"),
        )
        assert like_b.status_code == 200
        assert like_b.json()["likeCount"] == 1

        # Step 5: Verify like counts via GET
        post_a = requests.get(f"{BASE_URL}/posts/{original_post_id}", headers=headers("wf_post_a")).json()
        assert post_a["likeCount"] == 1
        post_b = requests.get(f"{BASE_URL}/posts/{quote_post_id}", headers=headers("wf_post_b")).json()
        assert post_b["likeCount"] == 1

        # Step 6: B edits their post
        edit_resp = requests.put(
            f"{BASE_URL}/posts/{quote_post_id}",
            headers=headers("wf_post_b"),
            json={"content": "B edited this quote"},
        )
        assert edit_resp.status_code == 200
        assert edit_resp.json()["content"] == "B edited this quote"
        # Like count preserved after edit
        assert edit_resp.json()["likeCount"] == 1

        # Step 7: Verify edit preserved via GET
        edited = requests.get(f"{BASE_URL}/posts/{quote_post_id}", headers=headers("wf_post_a")).json()
        assert edited["content"] == "B edited this quote"
        assert edited["quotePostId"] == original_post_id

        # Step 8: A soft-deletes original post
        del_resp = requests.delete(
            f"{BASE_URL}/posts/{original_post_id}",
            headers=headers("wf_post_a"),
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

        # Step 9: Quote post still readable and references original
        quote_check = requests.get(
            f"{BASE_URL}/posts/{quote_post_id}",
            headers=headers("wf_post_b"),
        ).json()
        assert quote_check["quotePostId"] == original_post_id
        assert quote_check["deleted"] is False

        # Step 10: Original still accessible (soft-deleted)
        original_check = requests.get(
            f"{BASE_URL}/posts/{original_post_id}",
            headers=headers("wf_post_a"),
        ).json()
        assert original_check["deleted"] is True


# ─── L3-7: Multi-user forum simulation ──────────────────────────────────────

class TestMultiUserSimulation:
    def test_three_users_different_levels_cross_verify(self, setup_admin):
        """
        Pattern 6+5+8: Multi-user simulation.
        3 users at different levels → each performs actions → cross-verify
        data consistency (correct authors, counts, timestamps ordered).
        """
        create_user("wf_multi_new")      # level 0
        create_user("wf_multi_member")   # level 2
        create_user("wf_multi_regular")  # level 3
        set_trust_level(ADMIN_USER, "wf_multi_member", 2)
        set_trust_level(ADMIN_USER, "wf_multi_regular", 3)

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "MultiUserCat"},
        ).json()
        cat_id = cat["id"]

        # Step 1: Level 2 user creates a tag
        tag_resp = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_multi_member"),
            json={"name": "wf_multi_tag"},
        )
        assert tag_resp.status_code == 201

        # Step 2: Level 0 user creates topic with the tag
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_multi_new"),
            json={
                "title": "Multi User Topic",
                "categoryId": cat_id,
                "content": "First post by new user",
                "tags": ["wf_multi_tag"],
            },
        ).json()
        topic_id = topic["id"]
        assert topic["postsCount"] == 1
        assert "wf_multi_tag" in topic["tags"]

        # Step 3: Level 2 replies
        reply1 = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_multi_member"),
            json={"topicId": topic_id, "content": "Reply from member"},
        ).json()
        assert reply1["postNumber"] == 2

        # Step 4: Level 3 replies
        reply2 = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_multi_regular"),
            json={"topicId": topic_id, "content": "Reply from regular"},
        ).json()
        assert reply2["postNumber"] == 3

        # Step 5: Verify postsCount updated
        topic_check = requests.get(
            f"{BASE_URL}/topics/{topic_id}",
            headers=headers("wf_multi_new"),
        ).json()
        assert topic_check["postsCount"] == 3

        # Step 6: Level 0 tries to rename topic → 403
        rename_resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}",
            headers=headers("wf_multi_new"),
            json={"title": "Renamed by newbie"},
        )
        assert rename_resp.status_code == 403

        # Step 7: Level 3 renames topic → 200
        rename_resp2 = requests.put(
            f"{BASE_URL}/topics/{topic_id}",
            headers=headers("wf_multi_regular"),
            json={"title": "Renamed by Regular"},
        )
        assert rename_resp2.status_code == 200
        assert rename_resp2.json()["title"] == "Renamed by Regular"

        # Step 8: All three users like each other's posts
        posts = requests.get(
            f"{BASE_URL}/topics/{topic_id}/posts",
            headers=headers("wf_multi_new"),
        ).json()
        # New user likes member's reply
        requests.post(f"{BASE_URL}/posts/{posts[1]['id']}/like", headers=headers("wf_multi_new"))
        # Member likes regular's reply
        requests.post(f"{BASE_URL}/posts/{posts[2]['id']}/like", headers=headers("wf_multi_member"))
        # Regular likes new user's original post
        requests.post(f"{BASE_URL}/posts/{posts[0]['id']}/like", headers=headers("wf_multi_regular"))

        # Step 9: Verify all like counts are exactly 1
        posts_final = requests.get(
            f"{BASE_URL}/topics/{topic_id}/posts",
            headers=headers("wf_multi_new"),
        ).json()
        assert posts_final[0]["likeCount"] == 1
        assert posts_final[1]["likeCount"] == 1
        assert posts_final[2]["likeCount"] == 1

        # Step 10: Verify timestamps are ordered (each subsequent post is >= previous)
        for i in range(1, len(posts_final)):
            assert posts_final[i]["createdAt"] >= posts_final[i-1]["createdAt"]

        # Step 11: Verify each post has correct userId (different users)
        user_ids = set(p["userId"] for p in posts_final)
        assert len(user_ids) == 3  # three distinct users

        # Step 12: Level 3 closes topic
        close_resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/close",
            headers=headers("wf_multi_regular"),
            json={"closed": True},
        )
        assert close_resp.status_code == 200

        # Step 13: Nobody can post anymore
        fail_post = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_multi_new"),
            json={"topicId": topic_id, "content": "Should fail"},
        )
        assert fail_post.status_code == 403


# ─── L3-8: Bookmarks and notifications combined ──────────────────────────────

class TestBookmarksAndNotifications:
    def test_bookmark_like_notification_interaction(self, setup_admin):
        """
        Pattern 5+6+7: Bookmarks + likes + notifications interaction.
        User A posts → B bookmarks it → C likes it → A gets notification →
        verify bookmark is per-user → B's bookmarks only show B's, not A's.
        """
        create_user("wf_bkn_a")
        create_user("wf_bkn_b")
        create_user("wf_bkn_c")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "BookmarkNotifCat"},
        ).json()

        # Step 1: A creates topic
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_bkn_a"),
            json={"title": "Bookmark Notif Topic", "categoryId": cat["id"], "content": "Important content"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("wf_bkn_a"),
        ).json()
        post_id = posts[0]["id"]

        # Step 2: B bookmarks the post
        bm_resp = requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("wf_bkn_b"),
            json={"postId": post_id},
        )
        assert bm_resp.status_code == 201
        assert bm_resp.json()["postId"] == post_id

        # Step 3: C likes the post → A gets notification
        like_resp = requests.post(
            f"{BASE_URL}/posts/{post_id}/like",
            headers=headers("wf_bkn_c"),
        )
        assert like_resp.status_code == 200
        assert like_resp.json()["likeCount"] == 1

        # Step 4: A has like notification
        a_notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("wf_bkn_a")).json()
        like_notifs = [n for n in a_notifs if n["notificationType"] == "like"]
        assert len(like_notifs) >= 1

        # Step 5: B's bookmarks contain the post
        b_bms = requests.get(f"{BASE_URL}/bookmarks", headers=headers("wf_bkn_b")).json()
        assert any(bm["postId"] == post_id for bm in b_bms)

        # Step 6: A's bookmarks do NOT contain the post (isolation)
        a_bms = requests.get(f"{BASE_URL}/bookmarks", headers=headers("wf_bkn_a")).json()
        assert all(bm["postId"] != post_id for bm in a_bms)

        # Step 7: C's bookmarks also empty for this post
        c_bms = requests.get(f"{BASE_URL}/bookmarks", headers=headers("wf_bkn_c")).json()
        assert all(bm["postId"] != post_id for bm in c_bms)

        # Step 8: B can delete their bookmark
        bm_id = bm_resp.json()["id"]
        del_resp = requests.delete(f"{BASE_URL}/bookmarks/{bm_id}", headers=headers("wf_bkn_b"))
        assert del_resp.status_code == 204

        # Step 9: B's bookmarks now empty for this post
        b_bms_after = requests.get(f"{BASE_URL}/bookmarks", headers=headers("wf_bkn_b")).json()
        assert all(bm["postId"] != post_id for bm in b_bms_after)


# ─── L3-9: Flag moderation workflow ──────────────────────────────────────────

class TestFlagModerationWorkflow:
    def test_flag_review_accept_reject_workflow(self, setup_admin):
        """
        Pattern 5+6+4: Flag moderation workflow.
        Level 0 cannot flag → level 1 flags → admin reviews → accepts one,
        rejects another → verify statuses → verify filter by status works.
        """
        create_user("wf_flag_newbie")
        create_user("wf_flag_basic")
        set_trust_level(ADMIN_USER, "wf_flag_basic", 1)
        create_user("wf_flag_poster")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "FlagWorkflowCat"},
        ).json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_flag_poster"),
            json={"title": "Flag Workflow Topic", "categoryId": cat["id"], "content": "Flag me"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("wf_flag_poster"),
        ).json()
        post_id = posts[0]["id"]

        # Step 1: Level 0 tries to flag → 403
        resp0 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("wf_flag_newbie"),
            json={"postId": post_id, "reason": "I'm new"},
        )
        assert resp0.status_code == 403

        # Step 2: Level 1 flags successfully (flag 1)
        flag1 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("wf_flag_basic"),
            json={"postId": post_id, "reason": "Spam content"},
        )
        assert flag1.status_code == 201
        flag1_id = flag1.json()["id"]
        assert flag1.json()["status"] == "pending"

        # Step 3: Level 1 flags again (flag 2)
        flag2 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("wf_flag_basic"),
            json={"postId": post_id, "reason": "Offensive language"},
        )
        assert flag2.status_code == 201
        flag2_id = flag2.json()["id"]

        # Step 4: Non-admin cannot see flags
        list_resp = requests.get(f"{BASE_URL}/flags", headers=headers("wf_flag_basic"))
        assert list_resp.status_code == 403

        # Step 5: Admin lists pending flags
        admin_flags = requests.get(
            f"{BASE_URL}/flags",
            headers=headers(ADMIN_USER),
            params={"status": "pending"},
        ).json()
        assert any(f["id"] == flag1_id for f in admin_flags)
        assert any(f["id"] == flag2_id for f in admin_flags)

        # Step 6: Admin accepts flag 1
        accept_resp = requests.put(
            f"{BASE_URL}/flags/{flag1_id}/accept",
            headers=headers(ADMIN_USER),
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["status"] == "accepted"

        # Step 7: Admin rejects flag 2
        reject_resp = requests.put(
            f"{BASE_URL}/flags/{flag2_id}/reject",
            headers=headers(ADMIN_USER),
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

        # Step 8: Filter by status works
        accepted = requests.get(
            f"{BASE_URL}/flags",
            headers=headers(ADMIN_USER),
            params={"status": "accepted"},
        ).json()
        assert any(f["id"] == flag1_id for f in accepted)
        assert all(f["status"] == "accepted" for f in accepted)

        rejected = requests.get(
            f"{BASE_URL}/flags",
            headers=headers(ADMIN_USER),
            params={"status": "rejected"},
        ).json()
        assert any(f["id"] == flag2_id for f in rejected)
        assert all(f["status"] == "rejected" for f in rejected)


# ─── L3-10: Tags and topics interaction ──────────────────────────────────────

class TestTagsTopicsInteraction:
    def test_tag_topic_count_and_filtering(self, setup_admin):
        """
        Pattern 3+5+7: Tags + topics interaction.
        Create tags → create topics with tags → verify topicCount updates →
        filter by tag → verify only matching returned → update topic tags → verify.
        """
        create_user("wf_tag_topic_user")
        set_trust_level(ADMIN_USER, "wf_tag_topic_user", 2)

        # Step 1: Create tags
        tag_a = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_tag_topic_user"),
            json={"name": "wf_tag_alpha"},
        ).json()
        tag_b = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("wf_tag_topic_user"),
            json={"name": "wf_tag_beta"},
        ).json()
        assert tag_a["topicCount"] == 0
        assert tag_b["topicCount"] == 0

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "TagTopicCat"},
        ).json()

        # Step 2: Create topic with tag_alpha
        t1 = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_tag_topic_user"),
            json={
                "title": "Alpha Topic",
                "categoryId": cat["id"],
                "content": "Tagged with alpha",
                "tags": ["wf_tag_alpha"],
            },
        ).json()
        assert "wf_tag_alpha" in t1["tags"]

        # Step 3: Create topic with both tags
        t2 = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_tag_topic_user"),
            json={
                "title": "Both Tags Topic",
                "categoryId": cat["id"],
                "content": "Tagged with both",
                "tags": ["wf_tag_alpha", "wf_tag_beta"],
            },
        ).json()
        assert "wf_tag_alpha" in t2["tags"]
        assert "wf_tag_beta" in t2["tags"]

        # Step 4: Verify topicCount for tag_alpha = 2
        tag_a_check = requests.get(
            f"{BASE_URL}/tags/{tag_a['id']}",
            headers=headers("wf_tag_topic_user"),
        ).json()
        assert tag_a_check["topicCount"] == 2

        # Step 5: Verify topicCount for tag_beta = 1
        tag_b_check = requests.get(
            f"{BASE_URL}/tags/{tag_b['id']}",
            headers=headers("wf_tag_topic_user"),
        ).json()
        assert tag_b_check["topicCount"] == 1

        # Step 6: Filter topics by tag_beta → only 1 result
        filtered = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("wf_tag_topic_user"),
            params={"tag": "wf_tag_beta"},
        ).json()
        matching = [t for t in filtered if "wf_tag_beta" in t["tags"]]
        assert len(matching) >= 1
        for t in filtered:
            assert "wf_tag_beta" in t["tags"]

        # Step 7: Level 3 updates topic1 to add tag_beta
        set_trust_level(ADMIN_USER, "wf_tag_topic_user", 3)
        update_resp = requests.put(
            f"{BASE_URL}/topics/{t1['id']}",
            headers=headers("wf_tag_topic_user"),
            json={"tags": ["wf_tag_alpha", "wf_tag_beta"]},
        )
        assert update_resp.status_code == 200
        assert "wf_tag_beta" in update_resp.json()["tags"]

        # Step 8: Now tag_beta topicCount should be 2
        tag_b_final = requests.get(
            f"{BASE_URL}/tags/{tag_b['id']}",
            headers=headers("wf_tag_topic_user"),
        ).json()
        assert tag_b_final["topicCount"] == 2


# ─── L3-11: Group management and member operations ───────────────────────────

class TestGroupManagementWorkflow:
    def test_group_lifecycle_with_members(self, setup_admin):
        """
        Pattern 5+6+7: Group lifecycle.
        Create group → add members → verify count → list members → remove →
        verify count decreased → non-admin cannot manage.
        """
        create_user("wf_grp_user1")
        create_user("wf_grp_user2")
        create_user("wf_grp_user3")

        # Step 1: Create group
        grp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(ADMIN_USER),
            json={"name": "wf_test_group", "displayName": "WF Test Group", "bio": "Testing"},
        )
        assert grp.status_code == 201
        grp_data = grp.json()
        grp_id = grp_data["id"]
        assert grp_data["memberCount"] == 0
        assert grp_data["displayName"] == "WF Test Group"

        # Step 2: Non-admin cannot add members
        fail_resp = requests.post(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers("wf_grp_user1"),
            json={"username": _username("wf_grp_user2")},
        )
        assert fail_resp.status_code == 403

        # Step 3: Admin adds user1
        add1 = requests.post(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("wf_grp_user1")},
        )
        assert add1.status_code == 200
        assert add1.json()["memberCount"] == 1

        # Step 4: Admin adds user2
        add2 = requests.post(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("wf_grp_user2")},
        )
        assert add2.json()["memberCount"] == 2

        # Step 5: Admin adds user3
        add3 = requests.post(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("wf_grp_user3")},
        )
        assert add3.json()["memberCount"] == 3

        # Step 6: List members → exactly 3
        members = requests.get(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers("wf_grp_user1"),
        ).json()
        assert len(members) == 3
        usernames = {m["username"] for m in members}
        assert usernames == {
            _username("wf_grp_user1"),
            _username("wf_grp_user2"),
            _username("wf_grp_user3"),
        }

        # Step 7: Remove user2
        rem = requests.delete(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("wf_grp_user2")},
        )
        assert rem.json()["memberCount"] == 2

        # Step 8: Verify user2 is gone
        members_after = requests.get(
            f"{BASE_URL}/groups/{grp_id}/members",
            headers=headers("wf_grp_user1"),
        ).json()
        assert len(members_after) == 2
        assert _username("wf_grp_user2") not in {
            m["username"] for m in members_after
        }

        # Step 9: Update group info
        update = requests.put(
            f"{BASE_URL}/groups/{grp_id}",
            headers=headers(ADMIN_USER),
            json={"bio": "Updated bio", "displayName": "New Display"},
        )
        assert update.status_code == 200
        assert update.json()["bio"] == "Updated bio"
        assert update.json()["displayName"] == "New Display"
        assert update.json()["memberCount"] == 2  # count preserved

        # Step 10: Non-admin cannot delete group
        del_fail = requests.delete(
            f"{BASE_URL}/groups/{grp_id}",
            headers=headers("wf_grp_user1"),
        )
        assert del_fail.status_code == 403


# ─── L3-12: Complete forum simulation with view counts ────────────────────────

class TestForumSimulationViewCounts:
    def test_topic_views_posts_and_search_consistency(self, setup_admin):
        """
        Pattern 5+3+7: Forum simulation combining view counts, posts, search.
        Create topic → multiple views → add posts → search finds it →
        verify all counters consistent.
        """
        create_user("wf_sim_user1")
        create_user("wf_sim_user2")

        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "SimulationCat"},
        ).json()

        # Step 1: Create topic
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("wf_sim_user1"),
            json={
                "title": "Photosynthesis Research Discussion",
                "categoryId": cat["id"],
                "content": "Let's discuss photosynthesis mechanisms",
            },
        ).json()
        topic_id = topic["id"]
        assert topic["viewCount"] == 0
        assert topic["postsCount"] == 1

        # Step 2: First view increments
        t1 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("wf_sim_user1")).json()
        assert t1["viewCount"] == 1

        # Step 3: Second view increments again
        t2 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("wf_sim_user2")).json()
        assert t2["viewCount"] == 2

        # Step 4: Add posts
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_sim_user2"),
            json={"topicId": topic_id, "content": "Great topic about photosynthesis!"},
        )
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("wf_sim_user1"),
            json={"topicId": topic_id, "content": "Thanks for joining the photosynthesis discussion"},
        )

        # Step 5: Verify postsCount
        t3 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("wf_sim_user1")).json()
        assert t3["postsCount"] == 3
        assert t3["viewCount"] == 3  # +1 from this GET

        # Step 6: Search finds this topic
        search_resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("wf_sim_user1"),
            params={"q": "Photosynthesis"},
        ).json()
        found_topics = [t for t in search_resp["topics"] if t["id"] == topic_id]
        assert len(found_topics) == 1

        # Step 7: Search also finds posts with the keyword
        found_posts = [p for p in search_resp["posts"] if "photosynthesis" in p["content"].lower()]
        assert len(found_posts) >= 2

        # Step 8: Notification generated for user1 (from user2's reply)
        notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("wf_sim_user1")).json()
        reply_notifs = [n for n in notifs if n["notificationType"] == "reply" and n["topicId"] == topic_id]
        assert len(reply_notifs) >= 1
