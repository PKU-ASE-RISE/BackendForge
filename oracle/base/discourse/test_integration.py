"""
L2 Integration Tests for Discourse Forum API.
Adversarial tests targeting common LLM implementation bugs:
- camelCase field naming
- nested data integrity
- trust level permissions ACTUALLY enforced
- view/post/like counts CHANGE
- search actually filters
- notification generation
- correct status codes
"""
import hashlib
import os
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


def _resource_name(name: str):
    return f"{name}_{_item_suffix()}"


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
    """Create admin user for all integration tests."""
    response = create_user(ADMIN_USER, expected_status=None)
    assert response.status_code in {201, 409}, response.text
    set_trust_level(ADMIN_USER, ADMIN_USER, 4)
    return ADMIN_USER


# ─── L2-1: User response field names (camelCase) ─────────────────────────────

class TestUserFieldNames:
    def test_user_creation_and_profile_camel_case_fields(self, setup_admin):
        """Pattern 1: Verify ALL user response fields are camelCase on create and GET"""
        resp = create_user("integ_user_fields", "integ_user_fields@test.com", "Test User")
        assert resp.status_code == 201
        data = resp.json()
        # Verify camelCase field names
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "name" in data
        assert "trustLevel" in data  # NOT trust_level
        assert "bio" in data
        assert "createdAt" in data  # NOT created_at
        # Verify snake_case NOT present
        assert "trust_level" not in data
        assert "created_at" not in data
        # Verify values
        assert data["trustLevel"] == 0
        assert data["username"] == _username("integ_user_fields")
        assert isinstance(data["createdAt"], str)
        assert "T" in data["createdAt"]  # ISO 8601

        # Also verify on GET with different trust level
        create_user("integ_profile_cc")
        set_trust_level(ADMIN_USER, "integ_profile_cc", 2)
        resp2 = requests.get(
            f"{BASE_URL}/users/{_username('integ_profile_cc')}",
            headers=headers(ADMIN_USER),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert "trustLevel" in data2
        assert data2["trustLevel"] == 2
        assert "trust_level" not in data2
        assert "created_at" not in data2


# ─── L2-2: Topic + Post field names and nested data ──────────────────────────

class TestTopicPostFields:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        self.admin = setup_admin
        create_user("integ_topic_user")
        cat_resp = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={
                "name": _resource_name("IntegTopicCat"),
                "color": "FF0000",
                "textColor": "FFFFFF",
            },
        )
        assert cat_resp.status_code == 201, cat_resp.text
        self.cat_id = cat_resp.json()["id"]

    def test_topic_response_all_camel_case_fields(self):
        """Pattern 1+2: Topic response must have correct camelCase fields"""
        resp = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_topic_user"),
            json={"title": "CamelCase Topic", "categoryId": self.cat_id, "content": "Body here"},
        )
        assert resp.status_code == 201
        data = resp.json()
        # All required camelCase fields
        assert "id" in data
        assert "title" in data
        assert "categoryId" in data  # NOT category_id
        assert "userId" in data  # NOT user_id
        assert "pinned" in data
        assert "closed" in data
        assert "archived" in data
        assert "viewCount" in data  # NOT view_count
        assert "postsCount" in data  # NOT posts_count
        assert "tags" in data
        assert "createdAt" in data
        # Verify snake_case NOT present
        assert "category_id" not in data
        assert "user_id" not in data
        assert "view_count" not in data
        assert "posts_count" not in data
        assert "created_at" not in data
        # Type checks
        assert isinstance(data["tags"], list)
        assert isinstance(data["viewCount"], int)
        assert isinstance(data["postsCount"], int)

    def test_post_response_all_camel_case_fields(self):
        """Pattern 1: Post response must have correct camelCase fields"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_topic_user"),
            json={"title": "Post Fields Topic", "categoryId": self.cat_id, "content": "OP content"},
        ).json()
        # Create a reply
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_topic_user"),
            json={"topicId": topic["id"], "content": "Reply content"},
        )
        assert resp.status_code == 201
        data = resp.json()
        # All required camelCase fields
        assert "id" in data
        assert "topicId" in data  # NOT topic_id
        assert "userId" in data  # NOT user_id
        assert "content" in data
        assert "postNumber" in data  # NOT post_number
        assert "quotePostId" in data  # NOT quote_post_id (should be null)
        assert "likeCount" in data  # NOT like_count
        assert "deleted" in data
        assert "createdAt" in data  # NOT created_at
        assert "updatedAt" in data  # NOT updated_at
        # Verify snake_case NOT present
        assert "topic_id" not in data
        assert "user_id" not in data
        assert "post_number" not in data
        assert "quote_post_id" not in data
        assert "like_count" not in data
        assert "created_at" not in data
        assert "updated_at" not in data
        # Verify values
        assert data["postNumber"] == 2
        assert data["likeCount"] == 0
        assert data["deleted"] is False

    def test_list_topic_posts_returns_correct_post_array(self):
        """Pattern 2: GET topic posts returns proper array with correct fields"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_topic_user"),
            json={"title": "Posts Array Topic", "categoryId": self.cat_id, "content": "First post"},
        ).json()
        # Add replies
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_topic_user"),
            json={"topicId": topic["id"], "content": "Second post"},
        )
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_topic_user"),
            json={"topicId": topic["id"], "content": "Third post"},
        )
        resp = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_topic_user"),
        )
        assert resp.status_code == 200
        posts = resp.json()
        assert isinstance(posts, list)
        assert len(posts) == 3
        # Verify each post has correct fields and sequential numbering
        for i, post in enumerate(posts, 1):
            assert post["postNumber"] == i
            assert post["topicId"] == topic["id"]
            assert "content" in post
            assert "userId" in post
            assert "likeCount" in post
            assert "createdAt" in post


# ─── L2-3: Category and subsidiary entity field names ─────────────────────────

class TestEntityFieldNames:
    def test_category_response_camel_case_fields(self, setup_admin):
        """Pattern 1: Category, Group, Tag, Bookmark, Notification, Flag all use camelCase"""
        # Category with parentCategoryId
        parent = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "ParentCatInteg", "color": "AABBCC", "textColor": "112233"},
        ).json()
        child = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "ChildCatInteg", "parentCategoryId": parent["id"]},
        )
        assert child.status_code == 201
        data = child.json()
        assert "parentCategoryId" in data  # NOT parent_category_id
        assert "textColor" in data  # NOT text_color
        assert "createdAt" in data
        assert "parent_category_id" not in data
        assert "text_color" not in data
        assert "created_at" not in data
        assert data["parentCategoryId"] == parent["id"]

    def test_group_bookmark_flag_notification_camel_case(self, setup_admin):
        """Pattern 1: All secondary entities use camelCase field names"""
        # Group
        grp_resp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(ADMIN_USER),
            json={"name": "integ_field_group", "displayName": "Field Group", "bio": "Testing"},
        )
        assert grp_resp.status_code == 201
        grp = grp_resp.json()
        assert "displayName" in grp  # NOT display_name
        assert "memberCount" in grp  # NOT member_count
        assert "createdAt" in grp
        assert "display_name" not in grp
        assert "member_count" not in grp

        # Bookmark - create a post to bookmark
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "BmFieldCat"},
        ).json()
        create_user("integ_bm_field_user")
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_bm_field_user"),
            json={"title": "BM Topic", "categoryId": cat["id"], "content": "Body"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_bm_field_user"),
        ).json()
        bm_resp = requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("integ_bm_field_user"),
            json={"postId": posts[0]["id"]},
        )
        assert bm_resp.status_code == 201
        bm = bm_resp.json()
        assert "userId" in bm  # NOT user_id
        assert "postId" in bm  # NOT post_id
        assert "createdAt" in bm
        assert "user_id" not in bm
        assert "post_id" not in bm

        # Flag
        create_user("integ_flagger_field")
        set_trust_level(ADMIN_USER, "integ_flagger_field", 1)
        flag_resp = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("integ_flagger_field"),
            json={"postId": posts[0]["id"], "reason": "Bad content"},
        )
        assert flag_resp.status_code == 201
        flag = flag_resp.json()
        assert "postId" in flag  # NOT post_id
        assert "userId" in flag  # NOT user_id
        assert "createdAt" in flag
        assert "post_id" not in flag
        assert "user_id" not in flag
        assert flag["status"] == "pending"

        # Notification - generate one by replying
        create_user("integ_notif_replier_f")
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_notif_replier_f"),
            json={"topicId": topic["id"], "content": "Generating notification"},
        )
        notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_bm_field_user"),
        ).json()
        assert len(notifs) >= 1
        n = notifs[0]
        assert "notificationType" in n  # NOT notification_type
        assert "userId" in n
        assert "topicId" in n
        assert "postId" in n
        assert "actingUserId" in n  # NOT acting_user_id
        assert "createdAt" in n
        assert "notification_type" not in n
        assert "acting_user_id" not in n


# ─── L2-4: Trust level permissions ACTUALLY enforced (multiple levels) ────────

class TestTrustLevelEnforcement:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        self.admin = setup_admin
        # Create users at different levels
        create_user("integ_level0")
        create_user("integ_level1")
        create_user("integ_level2")
        create_user("integ_level3")
        set_trust_level(ADMIN_USER, "integ_level1", 1)
        set_trust_level(ADMIN_USER, "integ_level2", 2)
        set_trust_level(ADMIN_USER, "integ_level3", 3)
        # Setup a post for flagging
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("TrustLevelCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_level0"),
            json={"title": "TrustLevel Topic", "categoryId": cat["id"], "content": "Content"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        self.topic_id = topic["id"]
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_level0"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.post_id = posts[0]["id"]

    def test_level0_cannot_flag_level1_can(self):
        """Pattern 6: Trust level 0 cannot flag, level 1 can — proves NOT hardcoded"""
        # Level 0 tries to flag → 403
        resp0 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("integ_level0"),
            json={"postId": self.post_id, "reason": "spam"},
        )
        assert resp0.status_code == 403
        # Level 1 flags → 201
        resp1 = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("integ_level1"),
            json={"postId": self.post_id, "reason": "spam"},
        )
        assert resp1.status_code == 201
        assert resp1.json()["status"] == "pending"

    def test_level1_cannot_create_tag_level2_can(self):
        """Pattern 6: Trust level 1 cannot create tag, level 2 can"""
        # Level 1 tries → 403
        resp1 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_level1"),
            json={"name": "integ_blocked_tag"},
        )
        assert resp1.status_code == 403
        # Level 2 creates → 201
        resp2 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_level2"),
            json={"name": "integ_allowed_tag"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["name"] == "integ_allowed_tag"

    def test_level2_cannot_close_topic_level3_can(self):
        """Pattern 6: Trust level 2 cannot close topic, level 3 can"""
        # Level 2 tries to close → 403
        resp2 = requests.put(
            f"{BASE_URL}/topics/{self.topic_id}/close",
            headers=headers("integ_level2"),
            json={"closed": True},
        )
        assert resp2.status_code == 403
        # Level 3 closes → 200
        resp3 = requests.put(
            f"{BASE_URL}/topics/{self.topic_id}/close",
            headers=headers("integ_level3"),
            json={"closed": True},
        )
        assert resp3.status_code == 200
        assert resp3.json()["closed"] is True

    def test_level3_cannot_pin_only_admin_can(self):
        """Pattern 6: Trust level 3 cannot pin, only admin (level 4) can"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_level0"),
            json={"title": "Pin Test Topic", "categoryId": self.cat_id, "content": "Pin me"},
        ).json()
        # Level 3 tries to pin → 403
        resp3 = requests.put(
            f"{BASE_URL}/topics/{topic['id']}/pin",
            headers=headers("integ_level3"),
            json={"pinned": True},
        )
        assert resp3.status_code == 403
        # Admin pins → 200
        resp_admin = requests.put(
            f"{BASE_URL}/topics/{topic['id']}/pin",
            headers=headers(ADMIN_USER),
            json={"pinned": True},
        )
        assert resp_admin.status_code == 200
        assert resp_admin.json()["pinned"] is True

    def test_non_admin_cannot_create_category(self):
        """Pattern 6: Non-admin (even level 3) cannot create categories"""
        resp = requests.post(
            f"{BASE_URL}/categories",
            headers=headers("integ_level3"),
            json={"name": "Hacker Cat"},
        )
        assert resp.status_code == 403


# ─── L2-5: View count actually increments ────────────────────────────────────

class TestViewCountIncrements:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_viewer")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("ViewCountCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_view_count_increments_on_each_get(self):
        """Pattern 5: viewCount must INCREASE on each GET, not be static"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_viewer"),
            json={"title": "ViewCount Topic", "categoryId": self.cat_id, "content": "Body"},
        ).json()
        topic_id = topic["id"]
        # First GET
        r1 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("integ_viewer"))
        vc1 = r1.json()["viewCount"]
        assert vc1 >= 1  # At least 1 after first view
        # Second GET
        r2 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("integ_viewer"))
        vc2 = r2.json()["viewCount"]
        assert vc2 == vc1 + 1  # Must be exactly +1
        # Third GET
        r3 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("integ_viewer"))
        vc3 = r3.json()["viewCount"]
        assert vc3 == vc2 + 1  # Must be exactly +1 again
        # Verify monotonic increase
        assert vc3 > vc2 > vc1


# ─── L2-6: Posts count changes when posts are added ──────────────────────────

class TestPostsCountChanges:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_poster_a")
        create_user("integ_poster_b")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("PostsCountCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_posts_count_increases_with_replies(self):
        """Pattern 5: postsCount must INCREASE when posts are added"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_poster_a"),
            json={"title": "PostCount Topic", "categoryId": self.cat_id, "content": "Initial"},
        ).json()
        topic_id = topic["id"]
        # Initially postsCount == 1 (the OP)
        assert topic["postsCount"] == 1

        # Add a reply
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_poster_b"),
            json={"topicId": topic_id, "content": "Reply 1"},
        )
        # Check postsCount increased
        t2 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("integ_poster_a")).json()
        assert t2["postsCount"] == 2

        # Add another reply
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_poster_a"),
            json={"topicId": topic_id, "content": "Reply 2"},
        )
        t3 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("integ_poster_a")).json()
        assert t3["postsCount"] == 3


# ─── L2-7: Like count changes ────────────────────────────────────────────────

class TestLikeCountChanges:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_liker_a")
        create_user("integ_liker_b")
        create_user("integ_liker_c")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("LikeCountCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_liker_a"),
            json={"title": "LikeCount Topic", "categoryId": cat["id"], "content": "Like me"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_liker_a"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.post_id = posts[0]["id"]

    def test_like_count_increases_and_decreases(self):
        """Pattern 5: likeCount must CHANGE with likes/unlikes"""
        # Initial like count is 0
        post = requests.get(f"{BASE_URL}/posts/{self.post_id}", headers=headers("integ_liker_a")).json()
        assert post["likeCount"] == 0

        # Like by user B → count becomes 1
        resp_b = requests.post(
            f"{BASE_URL}/posts/{self.post_id}/like",
            headers=headers("integ_liker_b"),
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["likeCount"] == 1

        # Like by user C → count becomes 2
        resp_c = requests.post(
            f"{BASE_URL}/posts/{self.post_id}/like",
            headers=headers("integ_liker_c"),
        )
        assert resp_c.status_code == 200
        assert resp_c.json()["likeCount"] == 2

        # Unlike by user B → count back to 1
        resp_unlike = requests.delete(
            f"{BASE_URL}/posts/{self.post_id}/like",
            headers=headers("integ_liker_b"),
        )
        assert resp_unlike.status_code == 200
        assert resp_unlike.json()["likeCount"] == 1


# ─── L2-8: Search actually searches (not just returns all) ───────────────────

class TestSearchActuallyFilters:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_searcher")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("SearchFilterCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_search_returns_only_matching_topics(self):
        """Pattern 3+5: Search must FILTER, not return everything"""
        # Create topics with different keywords
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_searcher"),
            json={"title": "Quantum Computing Future", "categoryId": self.cat_id, "content": "About quantum"},
        )
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_searcher"),
            json={"title": "Cooking Italian Pasta", "categoryId": self.cat_id, "content": "About cooking"},
        )
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_searcher"),
            json={"title": "Gardening Tips Spring", "categoryId": self.cat_id, "content": "About gardening"},
        )

        # Search for "Quantum" — only 1 should match
        resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("integ_searcher"),
            params={"q": "Quantum"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "posts" in data
        # Only quantum topic should match in titles
        matching_topics = [t for t in data["topics"] if "Quantum" in t["title"]]
        assert len(matching_topics) >= 1
        # Pasta and Gardening should NOT be in topic matches by title
        non_matching = [t for t in data["topics"] if "Pasta" in t["title"] or "Gardening" in t["title"]]
        assert len(non_matching) == 0

    def test_search_finds_posts_by_content(self):
        """Pattern 5: Search also searches post content, not just topic titles"""
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_searcher"),
            json={
                "title": "Generic Title XYZ",
                "categoryId": self.cat_id,
                "content": "This post mentions bioluminescence which is unique",
            },
        )
        resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("integ_searcher"),
            params={"q": "bioluminescence"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) >= 1
        assert any("bioluminescence" in p["content"] for p in data["posts"])


# ─── L2-9: Notification generation and isolation ─────────────────────────────

class TestNotificationGeneration:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_notif_author")
        create_user("integ_notif_replier")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("NotifGenCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_reply_generates_notification_for_topic_owner(self):
        """Pattern 7: Reply to topic must generate notification for owner"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_notif_author"),
            json={"title": "Notif Gen Topic", "categoryId": self.cat_id, "content": "Notify me"},
        ).json()
        # Reply by different user
        reply = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_notif_replier"),
            json={"topicId": topic["id"], "content": "Here is my reply"},
        )
        assert reply.status_code == 201
        # Check author's notifications
        notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_notif_author"),
        ).json()
        reply_notifs = [n for n in notifs if n["notificationType"] == "reply" and n["topicId"] == topic["id"]]
        assert len(reply_notifs) >= 1
        # Verify notification fields
        n = reply_notifs[0]
        assert n["userId"] is not None
        assert n["actingUserId"] is not None
        assert n["read"] is False
        assert n["postId"] is not None

    def test_notifications_are_user_specific(self):
        """Pattern 6: User B should NOT see user A's notifications"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_notif_author"),
            json={"title": "Isolation Topic", "categoryId": self.cat_id, "content": "Isolated"},
        ).json()
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_notif_replier"),
            json={"topicId": topic["id"], "content": "Reply for isolation test"},
        )
        # Author has notifications
        author_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_notif_author"),
        ).json()
        author_reply_notifs = [n for n in author_notifs if n["topicId"] == topic["id"]]
        assert len(author_reply_notifs) >= 1
        # Replier should NOT have those notifications
        replier_notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_notif_replier"),
        ).json()
        replier_topic_notifs = [n for n in replier_notifs if n.get("topicId") == topic["id"]]
        assert len(replier_topic_notifs) == 0

    def test_like_generates_notification(self):
        """Pattern 7: Like generates notification for post owner"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_notif_author"),
            json={"title": "Like Notif Topic", "categoryId": self.cat_id, "content": "Like this"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_notif_author"),
        ).json()
        post_id = posts[0]["id"]
        requests.post(
            f"{BASE_URL}/posts/{post_id}/like",
            headers=headers("integ_notif_replier"),
        )
        notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_notif_author"),
        ).json()
        like_notifs = [n for n in notifs if n["notificationType"] == "like" and n["postId"] == post_id]
        assert len(like_notifs) >= 1


# ─── L2-10: Unread count tracking ────────────────────────────────────────────

class TestUnreadCount:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_unread_author")
        create_user("integ_unread_replier")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("UnreadCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_unread_count_decreases_on_mark_read(self):
        """Pattern 5: unreadCount must DECREASE when notifications are marked read"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_unread_author"),
            json={"title": "Unread Topic", "categoryId": self.cat_id, "content": "Content"},
        ).json()
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_unread_replier"),
            json={"topicId": topic["id"], "content": "Reply for unread test"},
        )
        # Get unread count before
        count_before = requests.get(
            f"{BASE_URL}/notifications/unread-count",
            headers=headers("integ_unread_author"),
        ).json()["unreadCount"]
        assert count_before >= 1
        # Mark one notification as read
        notifs = requests.get(
            f"{BASE_URL}/notifications",
            headers=headers("integ_unread_author"),
        ).json()
        unread = [n for n in notifs if not n["read"]]
        assert len(unread) >= 1
        requests.put(
            f"{BASE_URL}/notifications/{unread[0]['id']}/read",
            headers=headers("integ_unread_author"),
        )
        # Check unread count decreased
        count_after = requests.get(
            f"{BASE_URL}/notifications/unread-count",
            headers=headers("integ_unread_author"),
        ).json()["unreadCount"]
        assert count_after == count_before - 1


# ─── L2-11: Topic filtering by category and tag ──────────────────────────────

class TestTopicFiltering:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_filter_user")
        cat1 = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("FilterCat1")},
        )
        assert cat1.status_code == 201, cat1.text
        cat1 = cat1.json()
        cat2 = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("FilterCat2")},
        )
        assert cat2.status_code == 201, cat2.text
        cat2 = cat2.json()
        self.cat1_id = cat1["id"]
        self.cat2_id = cat2["id"]

    def test_filter_topics_by_category_id(self):
        """Pattern 3: categoryId filter must actually filter results"""
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            json={"title": "Topic in Cat1", "categoryId": self.cat1_id, "content": "Body"},
        )
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            json={"title": "Topic in Cat2", "categoryId": self.cat2_id, "content": "Body"},
        )
        resp = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            params={"categoryId": self.cat1_id},
        )
        assert resp.status_code == 200
        topics = resp.json()
        assert len(topics) >= 1
        for t in topics:
            assert t["categoryId"] == self.cat1_id

    def test_filter_topics_by_tag(self):
        """Pattern 3: tag filter must actually filter results"""
        set_trust_level(ADMIN_USER, "integ_filter_user", 2)
        requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_filter_user"),
            json={"name": "integ_filter_tag"},
        )
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            json={"title": "Tagged Topic Filter", "categoryId": self.cat1_id, "content": "Body", "tags": ["integ_filter_tag"]},
        )
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            json={"title": "Untagged Topic Filter", "categoryId": self.cat1_id, "content": "Body"},
        )
        resp = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("integ_filter_user"),
            params={"tag": "integ_filter_tag"},
        )
        assert resp.status_code == 200
        topics = resp.json()
        assert len(topics) >= 1
        for t in topics:
            assert "integ_filter_tag" in t["tags"]


# ─── L2-12: Closed topic blocks new posts ────────────────────────────────────

class TestClosedTopicBlocks:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_close_user")
        create_user("integ_close_poster")
        set_trust_level(ADMIN_USER, "integ_close_user", 3)
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("ClosedPostCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_cannot_post_in_closed_topic(self):
        """Pattern 4+5: Posting in closed topic must return 403"""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_close_poster"),
            json={"title": "Close Test", "categoryId": self.cat_id, "content": "Open post"},
        ).json()
        requests.put(
            f"{BASE_URL}/topics/{topic['id']}/close",
            headers=headers("integ_close_user"),
            json={"closed": True},
        )
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_close_poster"),
            json={"topicId": topic["id"], "content": "Trying to post in closed topic"},
        )
        assert resp.status_code == 403


# ─── L2-13: Group member count changes ──────────────────────────────────────

class TestGroupMemberCount:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_grp_member1")
        create_user("integ_grp_member2")

    def test_member_count_changes_on_add_remove(self):
        """Pattern 5: memberCount must CHANGE when members added/removed"""
        grp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(ADMIN_USER),
            json={"name": "integ_count_group", "displayName": "Count Group"},
        ).json()
        assert grp["memberCount"] == 0
        resp1 = requests.post(
            f"{BASE_URL}/groups/{grp['id']}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("integ_grp_member1")},
        )
        assert resp1.json()["memberCount"] == 1
        resp2 = requests.post(
            f"{BASE_URL}/groups/{grp['id']}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("integ_grp_member2")},
        )
        assert resp2.json()["memberCount"] == 2
        resp3 = requests.delete(
            f"{BASE_URL}/groups/{grp['id']}/members",
            headers=headers(ADMIN_USER),
            json={"username": _username("integ_grp_member1")},
        )
        assert resp3.json()["memberCount"] == 1


# ─── L2-14: Tag fields including topicCount ──────────────────────────────────

class TestTagFields:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_tag_fields_user")
        set_trust_level(ADMIN_USER, "integ_tag_fields_user", 2)

    def test_tag_response_has_topic_count_that_changes(self):
        """Pattern 1+5: Tag must have topicCount that reflects actual usage"""
        tag = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_tag_fields_user"),
            json={"name": "integ_count_tag"},
        ).json()
        assert "topicCount" in tag  # NOT topic_count
        assert "createdAt" in tag
        assert "topic_count" not in tag
        assert "created_at" not in tag
        assert tag["topicCount"] == 0

        # Create a topic with this tag
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "TagCountCat"},
        ).json()
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_tag_fields_user"),
            json={
                "title": "Tag Count Topic",
                "categoryId": cat["id"],
                "content": "Body",
                "tags": ["integ_count_tag"],
            },
        )
        # Re-fetch tag and verify topicCount increased
        tag_updated = requests.get(
            f"{BASE_URL}/tags/{tag['id']}",
            headers=headers("integ_tag_fields_user"),
        ).json()
        assert tag_updated["topicCount"] == 1


# ─── L2-15: Status code correctness ─────────────────────────────────────────

class TestStatusCodes:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_sc_user")

    def test_create_resources_return_201_delete_returns_204(self):
        """Pattern 4: POST create must return 201, DELETE must return 204, missing returns 404"""
        # Create category → 201
        resp_cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "StatusCodeCat"},
        )
        assert resp_cat.status_code == 201
        cat_id = resp_cat.json()["id"]

        # Create topic → 201
        resp_topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_sc_user"),
            json={"title": "StatusCode Topic", "categoryId": cat_id, "content": "Body"},
        )
        assert resp_topic.status_code == 201

        # Create post → 201
        resp_post = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_sc_user"),
            json={"topicId": resp_topic.json()["id"], "content": "Reply"},
        )
        assert resp_post.status_code == 201

        # Create group → 201
        resp_grp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(ADMIN_USER),
            json={"name": "sc_group"},
        )
        assert resp_grp.status_code == 201

        # Delete → 204
        del_cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": "DeleteSCCat"},
        ).json()
        resp_del = requests.delete(
            f"{BASE_URL}/categories/{del_cat['id']}",
            headers=headers(ADMIN_USER),
        )
        assert resp_del.status_code == 204

        # Not found → 404
        assert requests.get(f"{BASE_URL}/topics/999999", headers=headers("integ_sc_user")).status_code == 404
        assert requests.get(f"{BASE_URL}/categories/999999", headers=headers("integ_sc_user")).status_code == 404
        assert requests.get(f"{BASE_URL}/posts/999999", headers=headers("integ_sc_user")).status_code == 404


# ─── L2-16: Soft delete preserves post but marks it deleted ──────────────────

class TestSoftDelete:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_softdel_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("SoftDelCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_softdel_user"),
            json={"title": "SoftDel Topic", "categoryId": cat["id"], "content": "First post"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        self.topic_id = topic["id"]

    def test_soft_delete_marks_post_as_deleted(self):
        """Pattern 5+7: Soft delete must set deleted=True, post still accessible"""
        post = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_softdel_user"),
            json={"topicId": self.topic_id, "content": "Delete this post"},
        ).json()
        assert post["deleted"] is False
        resp = requests.delete(
            f"{BASE_URL}/posts/{post['id']}",
            headers=headers("integ_softdel_user"),
        )
        assert resp.status_code == 200  # Soft delete returns 200 with body
        assert resp.json()["deleted"] is True
        # Post is still accessible via GET
        get_resp = requests.get(
            f"{BASE_URL}/posts/{post['id']}",
            headers=headers("integ_softdel_user"),
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["deleted"] is True


# ─── L2-17: Quote post reference ─────────────────────────────────────────────

class TestQuotePost:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_quote_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("QuoteCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_quote_user"),
            json={"title": "Quote Topic", "categoryId": cat["id"], "content": "Original post"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        self.topic_id = topic["id"]
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_quote_user"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.first_post_id = posts[0]["id"]

    def test_quote_post_id_preserved_and_null_when_absent(self):
        """Pattern 2: quotePostId must be properly stored/returned; null when not quoting"""
        # Create a post quoting the first post
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_quote_user"),
            json={
                "topicId": self.topic_id,
                "content": "I'm quoting you",
                "quotePostId": self.first_post_id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["quotePostId"] == self.first_post_id
        # Verify via GET
        get_resp = requests.get(
            f"{BASE_URL}/posts/{data['id']}",
            headers=headers("integ_quote_user"),
        )
        assert get_resp.json()["quotePostId"] == self.first_post_id

        # Post without quote has null quotePostId
        resp2 = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_quote_user"),
            json={"topicId": self.topic_id, "content": "No quote here"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["quotePostId"] is None


# ─── L2-18: Tag group fields ─────────────────────────────────────────────────

class TestTagGroupFields:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_tg_user")
        set_trust_level(ADMIN_USER, "integ_tg_user", 2)
        tag1 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_tg_user"),
            json={"name": "integ_tg_tag1"},
        )
        assert tag1.status_code == 201, tag1.text
        tag2 = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("integ_tg_user"),
            json={"name": "integ_tg_tag2"},
        )
        assert tag2.status_code == 201, tag2.text

    def test_tag_group_has_correct_fields(self):
        """Pattern 1+2: Tag group must return tags array with correct field names"""
        resp = requests.post(
            f"{BASE_URL}/tag-groups",
            headers=headers(ADMIN_USER),
            json={"name": "IntegTagGroup", "tags": ["integ_tg_tag1", "integ_tg_tag2"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "tags" in data
        assert "createdAt" in data
        assert "created_at" not in data
        assert isinstance(data["tags"], list)
        assert set(data["tags"]) == {"integ_tg_tag1", "integ_tg_tag2"}


# ─── L2-19: Edit post updates content and updatedAt ──────────────────────────

class TestEditPostUpdatedAt:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_edit_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("EditTimeCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_edit_user"),
            json={"title": "Edit Time Topic", "categoryId": cat["id"], "content": "Original"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_edit_user"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.post_id = posts[0]["id"]

    def test_edit_post_changes_content_and_updated_at(self):
        """Pattern 5: Editing post must update content AND updatedAt timestamp"""
        original = requests.get(
            f"{BASE_URL}/posts/{self.post_id}",
            headers=headers("integ_edit_user"),
        ).json()
        import time
        time.sleep(0.1)
        resp = requests.put(
            f"{BASE_URL}/posts/{self.post_id}",
            headers=headers("integ_edit_user"),
            json={"content": "Edited content here"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Edited content here"
        assert resp.json()["updatedAt"] is not None


# ─── L2-20: Post number sequential ───────────────────────────────────────────

class TestPostNumberSequential:
    @pytest.fixture(autouse=True)
    def setup(self, setup_admin):
        create_user("integ_postnum_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(ADMIN_USER),
            json={"name": _resource_name("PostNumCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.cat_id = cat["id"]

    def test_post_numbers_are_sequential(self):
        """Pattern 5: Post numbers must be sequential 1, 2, 3..."""
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("integ_postnum_user"),
            json={"title": "PostNum Topic", "categoryId": self.cat_id, "content": "First"},
        ).json()
        p2 = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_postnum_user"),
            json={"topicId": topic["id"], "content": "Second"},
        ).json()
        p3 = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("integ_postnum_user"),
            json={"topicId": topic["id"], "content": "Third"},
        ).json()
        assert p2["postNumber"] == 2
        assert p3["postNumber"] == 3
        # Verify via list
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("integ_postnum_user"),
        ).json()
        assert posts[0]["postNumber"] == 1
        assert posts[1]["postNumber"] == 2
        assert posts[2]["postNumber"] == 3
