"""
Correctness tests for Discourse Forum API.
Tests cover CRUD for all entities, permission enforcement, topic lifecycle,
post interactions, search, notifications, bookmarks, and flags.
"""
import hashlib
import os
import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
API_KEY = "discourse-api-key"

# Global admin user for test setup
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
    resp = requests.post(f"{BASE_URL}/users", json={
        "username": _username(username),
        "email": email,
        "password": "password123",
        "name": name,
    })
    if expected_status is not None:
        assert resp.status_code == expected_status, resp.text
    return resp


def set_trust_level(
    admin_username: str,
    target_username: str,
    level: int,
    expected_status: int | None = 200,
):
    resp = requests.put(
        f"{BASE_URL}/users/{_username(target_username)}/trust-level",
        headers=headers(admin_username),
        json={"trustLevel": level},
    )
    if expected_status is not None:
        assert resp.status_code == expected_status, resp.text
    return resp


@pytest.fixture(scope="session", autouse=True)
def global_admin(_bounded_http_requests):
    """Create a global admin user that all tests can use for bootstrapping."""
    resp = create_user(
        ADMIN_USER,
        f"{ADMIN_USER}@example.com",
        "Global Admin",
        expected_status=None,
    )
    assert resp.status_code in {201, 409}, resp.text
    # Bootstrap: set trust level (should work since no admin exists yet)
    set_trust_level(ADMIN_USER, ADMIN_USER, 4)
    return ADMIN_USER


# ─── Authentication Tests ──────────────────────────────────────────────────────


class TestAuthentication:
    def test_missing_api_key(self, global_admin):
        resp = requests.get(f"{BASE_URL}/categories", headers={"X-Username": global_admin})
        assert resp.status_code == 401

    def test_missing_username(self):
        resp = requests.get(f"{BASE_URL}/categories", headers={"X-API-Key": API_KEY})
        assert resp.status_code == 401

    def test_missing_both_headers(self):
        resp = requests.get(f"{BASE_URL}/categories")
        assert resp.status_code == 401

    def test_invalid_username(self):
        resp = requests.get(
            f"{BASE_URL}/categories",
            headers={"X-API-Key": API_KEY, "X-Username": "nonexistent_user_xyz"},
        )
        assert resp.status_code == 401


# ─── User Tests ────────────────────────────────────────────────────────────────


class TestUsers:
    def test_create_user(self):
        resp = create_user("alice", "alice@example.com", "Alice Smith")
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == _username("alice")
        assert data["email"] == _email("alice@example.com")
        assert data["name"] == "Alice Smith"
        assert data["trustLevel"] == 0

    def test_create_user_duplicate_username(self):
        create_user("bob_dup", "bob1@example.com", "Bob")
        resp = create_user(
            "bob_dup", "bob2@example.com", "Bob2", expected_status=None
        )
        assert resp.status_code == 409

    def test_create_user_duplicate_email(self):
        create_user("charlie1", "charlie_dup@example.com", "Charlie")
        resp = create_user(
            "charlie2",
            "charlie_dup@example.com",
            "Charlie2",
            expected_status=None,
        )
        assert resp.status_code == 409

    def test_list_users(self, global_admin):
        resp = requests.get(f"{BASE_URL}/users", headers=headers(global_admin))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_user_profile(self, global_admin):
        create_user("profileuser")
        resp = requests.get(
            f"{BASE_URL}/users/{_username('profileuser')}",
            headers=headers(global_admin),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == _username("profileuser")

    def test_get_user_not_found(self, global_admin):
        resp = requests.get(f"{BASE_URL}/users/nobody999", headers=headers(global_admin))
        assert resp.status_code == 404

    def test_update_own_profile(self):
        create_user("editable_user")
        resp = requests.put(
            f"{BASE_URL}/users/{_username('editable_user')}",
            headers=headers("editable_user"),
            json={"name": "New Name", "bio": "Hello world"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["bio"] == "Hello world"

    def test_update_other_user_forbidden(self):
        create_user("user_a")
        create_user("user_b")
        resp = requests.put(
            f"{BASE_URL}/users/{_username('user_b')}",
            headers=headers("user_a"),
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_admin_can_update_other_user(self, global_admin):
        create_user("target_user")
        resp = requests.put(
            f"{BASE_URL}/users/{_username('target_user')}",
            headers=headers(global_admin),
            json={"bio": "Updated by admin"},
        )
        assert resp.status_code == 200

    def test_set_trust_level(self, global_admin):
        create_user("trust_target")
        resp = set_trust_level(global_admin, "trust_target", 3)
        assert resp.status_code == 200
        assert resp.json()["trustLevel"] == 3

    def test_set_trust_level_non_admin_forbidden(self):
        create_user("nonadmin_tl")
        create_user("victim_tl")
        resp = set_trust_level(
            "nonadmin_tl", "victim_tl", 2, expected_status=None
        )
        assert resp.status_code == 403


# ─── Category Tests ────────────────────────────────────────────────────────────


class TestCategories:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("cat_user")

    def test_create_category(self):
        resp = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "General", "slug": "general", "color": "0088CC", "description": "General discussion"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "General"
        assert data["slug"] == "general"
        assert data["color"] == "0088CC"

    def test_create_category_non_admin_forbidden(self):
        resp = requests.post(
            f"{BASE_URL}/categories",
            headers=headers("cat_user"),
            json={"name": "Hacker Category"},
        )
        assert resp.status_code == 403

    def test_list_categories(self):
        requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "ListCat1"},
        )
        resp = requests.get(f"{BASE_URL}/categories", headers=headers("cat_user"))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_category(self):
        cr = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "GetCat"},
        )
        cat_id = cr.json()["id"]
        resp = requests.get(f"{BASE_URL}/categories/{cat_id}", headers=headers("cat_user"))
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetCat"

    def test_get_category_not_found(self):
        resp = requests.get(f"{BASE_URL}/categories/99999", headers=headers("cat_user"))
        assert resp.status_code == 404

    def test_update_category(self):
        cr = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "UpdateCat"},
        )
        cat_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/categories/{cat_id}",
            headers=headers(self.admin),
            json={"name": "UpdatedCat", "color": "FF0000"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "UpdatedCat"
        assert resp.json()["color"] == "FF0000"

    def test_delete_category(self):
        cr = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "DeleteCat"},
        )
        cat_id = cr.json()["id"]
        resp = requests.delete(f"{BASE_URL}/categories/{cat_id}", headers=headers(self.admin))
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = requests.get(f"{BASE_URL}/categories/{cat_id}", headers=headers(self.admin))
        assert resp2.status_code == 404

    def test_subcategory(self):
        parent = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "ParentCat"},
        ).json()
        child = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": "ChildCat", "parentCategoryId": parent["id"]},
        )
        assert child.status_code == 201
        assert child.json()["parentCategoryId"] == parent["id"]


# ─── Topic Tests ───────────────────────────────────────────────────────────────


class TestTopics:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("topic_user")
        create_user("topic_regular")
        set_trust_level(self.admin, "topic_regular", 3)
        # Create a category
        resp = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("TopicTestCat")},
        )
        assert resp.status_code == 201, resp.text
        self.category_id = resp.json()["id"]

    def test_create_topic(self):
        resp = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={
                "title": "My First Topic",
                "categoryId": self.category_id,
                "content": "This is the body of the topic.",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My First Topic"
        assert data["categoryId"] == self.category_id
        assert data["pinned"] is False
        assert data["closed"] is False
        assert data["archived"] is False
        assert data["postsCount"] == 1

    def test_create_topic_invalid_category(self):
        resp = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={
                "title": "Bad Category",
                "categoryId": 99999,
                "content": "Body",
            },
        )
        assert resp.status_code == 404

    def test_list_topics(self):
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "ListTopic", "categoryId": self.category_id, "content": "Body"},
        )
        resp = requests.get(f"{BASE_URL}/topics", headers=headers("topic_user"))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_topics_by_category(self):
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "FilteredTopic", "categoryId": self.category_id, "content": "Body"},
        )
        resp = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            params={"categoryId": self.category_id},
        )
        assert resp.status_code == 200
        for topic in resp.json():
            assert topic["categoryId"] == self.category_id

    def test_get_topic_increments_view_count(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "ViewCountTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        # First view
        r1 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("topic_user"))
        vc1 = r1.json()["viewCount"]
        # Second view
        r2 = requests.get(f"{BASE_URL}/topics/{topic_id}", headers=headers("topic_user"))
        vc2 = r2.json()["viewCount"]
        assert vc2 == vc1 + 1

    def test_get_topic_not_found(self):
        resp = requests.get(f"{BASE_URL}/topics/99999", headers=headers("topic_user"))
        assert resp.status_code == 404

    def test_update_topic_title_requires_trust_level_3(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "RenameTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        # topic_user has trust level 0, should fail
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}",
            headers=headers("topic_user"),
            json={"title": "New Title"},
        )
        assert resp.status_code == 403

    def test_update_topic_by_regular(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "RenameByRegular", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}",
            headers=headers("topic_regular"),
            json={"title": "Renamed By Regular"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed By Regular"

    def test_pin_topic(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "PinTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers(self.admin),
            json={"pinned": True},
        )
        assert resp.status_code == 200
        assert resp.json()["pinned"] is True

    def test_pin_topic_non_admin_forbidden(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "PinForbidden", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers("topic_user"),
            json={"pinned": True},
        )
        assert resp.status_code == 403

    def test_close_topic(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "CloseTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/close",
            headers=headers("topic_regular"),
            json={"closed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["closed"] is True

    def test_close_topic_insufficient_level(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "CloseNoLevel", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/close",
            headers=headers("topic_user"),
            json={"closed": True},
        )
        assert resp.status_code == 403

    def test_archive_topic(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "ArchiveTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/archive",
            headers=headers(self.admin),
            json={"archived": True},
        )
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

    def test_archive_topic_non_admin(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "ArchiveNoAdmin", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/topics/{topic_id}/archive",
            headers=headers("topic_regular"),
            json={"archived": True},
        )
        assert resp.status_code == 403

    def test_delete_topic(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "DeleteTopic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.delete(f"{BASE_URL}/topics/{topic_id}", headers=headers(self.admin))
        assert resp.status_code == 204

    def test_delete_topic_non_admin(self):
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "DeleteNoAdmin", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        resp = requests.delete(f"{BASE_URL}/topics/{topic_id}", headers=headers("topic_user"))
        assert resp.status_code == 403

    def test_topic_with_tags(self):
        # Create tags first
        create_user("tag_maker_t")
        set_trust_level(self.admin, "tag_maker_t", 2)
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_maker_t"), json={"name": "python"})
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_maker_t"), json={"name": "help"})

        resp = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={
                "title": "Tagged Topic",
                "categoryId": self.category_id,
                "content": "Body",
                "tags": ["python", "help"],
            },
        )
        assert resp.status_code == 201
        assert set(resp.json()["tags"]) == {"python", "help"}

    def test_filter_topics_by_tag(self):
        create_user("tag_maker_t2")
        set_trust_level(self.admin, "tag_maker_t2", 2)
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_maker_t2"), json={"name": "unique_tag_filter"})
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={
                "title": "Tagged Filter Topic",
                "categoryId": self.category_id,
                "content": "Body",
                "tags": ["unique_tag_filter"],
            },
        )
        resp = requests.get(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            params={"tag": "unique_tag_filter"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        for t in resp.json():
            assert "unique_tag_filter" in t["tags"]

    def test_topic_lifecycle(self):
        """Test full lifecycle: create -> pin -> close -> archive"""
        cr = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("topic_user"),
            json={"title": "Lifecycle Topic", "categoryId": self.category_id, "content": "Body"},
        )
        topic_id = cr.json()["id"]
        assert cr.json()["pinned"] is False
        assert cr.json()["closed"] is False
        assert cr.json()["archived"] is False

        # Pin
        r1 = requests.put(
            f"{BASE_URL}/topics/{topic_id}/pin",
            headers=headers(self.admin),
            json={"pinned": True},
        )
        assert r1.json()["pinned"] is True

        # Close
        r2 = requests.put(
            f"{BASE_URL}/topics/{topic_id}/close",
            headers=headers("topic_regular"),
            json={"closed": True},
        )
        assert r2.json()["closed"] is True

        # Archive
        r3 = requests.put(
            f"{BASE_URL}/topics/{topic_id}/archive",
            headers=headers(self.admin),
            json={"archived": True},
        )
        assert r3.json()["archived"] is True


# ─── Post Tests ────────────────────────────────────────────────────────────────


class TestPosts:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("post_user")
        create_user("post_other")
        # Create category and topic
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("PostTestCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.category_id = cat["id"]
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("post_user"),
            json={"title": "PostTestTopic", "categoryId": self.category_id, "content": "Original post"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        self.topic_id = topic["id"]

    def test_create_post_reply(self):
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_other"),
            json={"topicId": self.topic_id, "content": "This is a reply"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["topicId"] == self.topic_id
        assert data["content"] == "This is a reply"
        assert data["postNumber"] == 2  # First post is #1 (the OP)

    def test_create_post_with_quote(self):
        # Get the first post
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        first_post_id = posts[0]["id"]

        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_other"),
            json={
                "topicId": self.topic_id,
                "content": "Quoting you here",
                "quotePostId": first_post_id,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["quotePostId"] == first_post_id

    def test_create_post_in_closed_topic(self):
        # Close the topic
        create_user("closer_post")
        set_trust_level(self.admin, "closer_post", 3)
        requests.put(
            f"{BASE_URL}/topics/{self.topic_id}/close",
            headers=headers("closer_post"),
            json={"closed": True},
        )
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_other"),
            json={"topicId": self.topic_id, "content": "Trying to post"},
        )
        assert resp.status_code == 403

    def test_create_post_topic_not_found(self):
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_user"),
            json={"topicId": 99999, "content": "No topic"},
        )
        assert resp.status_code == 404

    def test_get_post(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        resp = requests.get(f"{BASE_URL}/posts/{post_id}", headers=headers("post_user"))
        assert resp.status_code == 200
        assert resp.json()["id"] == post_id

    def test_list_topic_posts(self):
        # Add a reply
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_other"),
            json={"topicId": self.topic_id, "content": "A reply"},
        )
        resp = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_edit_own_post(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        resp = requests.put(
            f"{BASE_URL}/posts/{post_id}",
            headers=headers("post_user"),
            json={"content": "Edited content"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Edited content"

    def test_edit_other_user_post_forbidden(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        resp = requests.put(
            f"{BASE_URL}/posts/{post_id}",
            headers=headers("post_other"),
            json={"content": "Hacked"},
        )
        assert resp.status_code == 403

    def test_admin_can_edit_any_post(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        resp = requests.put(
            f"{BASE_URL}/posts/{post_id}",
            headers=headers(self.admin),
            json={"content": "Admin edit"},
        )
        assert resp.status_code == 200

    def test_delete_post_soft(self):
        reply = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_user"),
            json={"topicId": self.topic_id, "content": "Delete me"},
        ).json()
        resp = requests.delete(f"{BASE_URL}/posts/{reply['id']}", headers=headers("post_user"))
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_other_post_forbidden(self):
        reply = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_user"),
            json={"topicId": self.topic_id, "content": "Dont delete me"},
        ).json()
        resp = requests.delete(f"{BASE_URL}/posts/{reply['id']}", headers=headers("post_other"))
        assert resp.status_code == 403

    def test_like_post(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        resp = requests.post(f"{BASE_URL}/posts/{post_id}/like", headers=headers("post_other"))
        assert resp.status_code == 200
        assert resp.json()["likeCount"] >= 1

    def test_like_post_duplicate(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        create_user("liker_dup")
        requests.post(f"{BASE_URL}/posts/{post_id}/like", headers=headers("liker_dup"))
        resp = requests.post(f"{BASE_URL}/posts/{post_id}/like", headers=headers("liker_dup"))
        assert resp.status_code == 409

    def test_unlike_post(self):
        reply = requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_user"),
            json={"topicId": self.topic_id, "content": "Like then unlike"},
        ).json()
        create_user("unliker")
        requests.post(f"{BASE_URL}/posts/{reply['id']}/like", headers=headers("unliker"))
        resp = requests.delete(f"{BASE_URL}/posts/{reply['id']}/like", headers=headers("unliker"))
        assert resp.status_code == 200
        assert resp.json()["likeCount"] == 0

    def test_unlike_not_liked(self):
        posts = requests.get(
            f"{BASE_URL}/topics/{self.topic_id}/posts",
            headers=headers("post_user"),
        ).json()
        post_id = posts[0]["id"]
        create_user("never_liked")
        resp = requests.delete(f"{BASE_URL}/posts/{post_id}/like", headers=headers("never_liked"))
        assert resp.status_code == 404

    def test_posts_count_updated(self):
        """Topic's postsCount should reflect reply additions"""
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("post_other"),
            json={"topicId": self.topic_id, "content": "Counting reply"},
        )
        topic = requests.get(f"{BASE_URL}/topics/{self.topic_id}", headers=headers("post_user")).json()
        assert topic["postsCount"] >= 2


# ─── Group Tests ───────────────────────────────────────────────────────────────


class TestGroups:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("grp_user")

    def test_create_group(self):
        resp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "moderators", "displayName": "Moderators", "bio": "The mod team"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "moderators"
        assert data["memberCount"] == 0

    def test_create_group_non_admin(self):
        resp = requests.post(
            f"{BASE_URL}/groups",
            headers=headers("grp_user"),
            json={"name": "hacker_group"},
        )
        assert resp.status_code == 403

    def test_list_groups(self):
        requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "list_group"},
        )
        resp = requests.get(f"{BASE_URL}/groups", headers=headers("grp_user"))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_group(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "get_group"},
        ).json()
        resp = requests.get(f"{BASE_URL}/groups/{cr['id']}", headers=headers("grp_user"))
        assert resp.status_code == 200
        assert resp.json()["name"] == "get_group"

    def test_update_group(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "update_group"},
        ).json()
        resp = requests.put(
            f"{BASE_URL}/groups/{cr['id']}",
            headers=headers(self.admin),
            json={"displayName": "Updated Display"},
        )
        assert resp.status_code == 200
        assert resp.json()["displayName"] == "Updated Display"

    def test_delete_group(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "delete_group"},
        ).json()
        resp = requests.delete(f"{BASE_URL}/groups/{cr['id']}", headers=headers(self.admin))
        assert resp.status_code == 204

    def test_add_member(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "member_group"},
        ).json()
        resp = requests.post(
            f"{BASE_URL}/groups/{cr['id']}/members",
            headers=headers(self.admin),
            json={"username": _username("grp_user")},
        )
        assert resp.status_code == 200
        assert resp.json()["memberCount"] == 1

    def test_list_members(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "list_member_group"},
        ).json()
        requests.post(
            f"{BASE_URL}/groups/{cr['id']}/members",
            headers=headers(self.admin),
            json={"username": _username("grp_user")},
        )
        resp = requests.get(f"{BASE_URL}/groups/{cr['id']}/members", headers=headers("grp_user"))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["username"] == _username("grp_user")

    def test_remove_member(self):
        cr = requests.post(
            f"{BASE_URL}/groups",
            headers=headers(self.admin),
            json={"name": "remove_member_group"},
        ).json()
        requests.post(
            f"{BASE_URL}/groups/{cr['id']}/members",
            headers=headers(self.admin),
            json={"username": _username("grp_user")},
        )
        resp = requests.delete(
            f"{BASE_URL}/groups/{cr['id']}/members",
            headers=headers(self.admin),
            json={"username": _username("grp_user")},
        )
        assert resp.status_code == 200
        assert resp.json()["memberCount"] == 0


# ─── Tag Tests ─────────────────────────────────────────────────────────────────


class TestTags:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("tag_member")
        set_trust_level(self.admin, "tag_member", 2)
        create_user("tag_newbie")

    def test_create_tag(self):
        resp = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("tag_member"),
            json={"name": "javascript"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "javascript"
        assert resp.json()["topicCount"] == 0

    def test_create_tag_low_trust_level(self):
        resp = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("tag_newbie"),
            json={"name": "hacker_tag"},
        )
        assert resp.status_code == 403

    def test_create_tag_duplicate(self):
        requests.post(
            f"{BASE_URL}/tags",
            headers=headers("tag_member"),
            json={"name": "dup_tag"},
        )
        resp = requests.post(
            f"{BASE_URL}/tags",
            headers=headers("tag_member"),
            json={"name": "dup_tag"},
        )
        assert resp.status_code == 409

    def test_list_tags(self):
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "list_tag"})
        resp = requests.get(f"{BASE_URL}/tags", headers=headers("tag_newbie"))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_tag(self):
        cr = requests.post(
            f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "get_tag"}
        ).json()
        resp = requests.get(f"{BASE_URL}/tags/{cr['id']}", headers=headers("tag_newbie"))
        assert resp.status_code == 200
        assert resp.json()["name"] == "get_tag"

    def test_delete_tag(self):
        cr = requests.post(
            f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "del_tag"}
        ).json()
        resp = requests.delete(f"{BASE_URL}/tags/{cr['id']}", headers=headers(self.admin))
        assert resp.status_code == 204

    def test_delete_tag_non_admin(self):
        cr = requests.post(
            f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "nodelete_tag"}
        ).json()
        resp = requests.delete(f"{BASE_URL}/tags/{cr['id']}", headers=headers("tag_member"))
        assert resp.status_code == 403

    def test_create_tag_group(self):
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "tg_tag1"})
        requests.post(f"{BASE_URL}/tags", headers=headers("tag_member"), json={"name": "tg_tag2"})
        resp = requests.post(
            f"{BASE_URL}/tag-groups",
            headers=headers(self.admin),
            json={"name": "Programming", "tags": ["tg_tag1", "tg_tag2"]},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Programming"
        assert set(resp.json()["tags"]) == {"tg_tag1", "tg_tag2"}

    def test_create_tag_group_non_admin(self):
        resp = requests.post(
            f"{BASE_URL}/tag-groups",
            headers=headers("tag_member"),
            json={"name": "Hacker Group", "tags": []},
        )
        assert resp.status_code == 403

    def test_list_tag_groups(self):
        resp = requests.get(f"{BASE_URL}/tag-groups", headers=headers("tag_newbie"))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ─── Search Tests ──────────────────────────────────────────────────────────────


class TestSearch:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("search_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("SearchCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.category_id = cat["id"]

    def test_search_topics(self):
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("search_user"),
            json={
                "title": "Unique Elephant Discussion",
                "categoryId": self.category_id,
                "content": "Let us talk about elephants",
            },
        )
        resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("search_user"),
            params={"q": "Elephant"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert len(data["topics"]) >= 1
        assert any("Elephant" in t["title"] for t in data["topics"])

    def test_search_posts(self):
        requests.post(
            f"{BASE_URL}/topics",
            headers=headers("search_user"),
            json={
                "title": "Random Topic",
                "categoryId": self.category_id,
                "content": "This post contains the word xylophone uniquely",
            },
        )
        resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("search_user"),
            params={"q": "xylophone"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "posts" in data
        assert len(data["posts"]) >= 1

    def test_search_no_results(self):
        resp = requests.get(
            f"{BASE_URL}/search",
            headers=headers("search_user"),
            params={"q": "zzznonexistenttermzzz"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["topics"]) == 0
        assert len(data["posts"]) == 0


# ─── Notification Tests ────────────────────────────────────────────────────────


class TestNotifications:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("notif_author")
        create_user("notif_replier")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("NotifCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        self.category_id = cat["id"]

    def test_reply_generates_notification(self):
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("notif_author"),
            json={"title": "Notify Topic", "categoryId": self.category_id, "content": "Hello"},
        ).json()
        # Reply to topic — should notify the author
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("notif_replier"),
            json={"topicId": topic["id"], "content": "Nice post!"},
        )
        # Check author's notifications
        resp = requests.get(f"{BASE_URL}/notifications", headers=headers("notif_author"))
        assert resp.status_code == 200
        notifs = resp.json()
        assert len(notifs) >= 1
        assert any(n["notificationType"] == "reply" for n in notifs)

    def test_unread_count(self):
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("notif_author"),
            json={"title": "Unread Topic", "categoryId": self.category_id, "content": "Hello"},
        ).json()
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("notif_replier"),
            json={"topicId": topic["id"], "content": "Reply here"},
        )
        resp = requests.get(f"{BASE_URL}/notifications/unread-count", headers=headers("notif_author"))
        assert resp.status_code == 200
        assert resp.json()["unreadCount"] >= 1

    def test_mark_notification_read(self):
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("notif_author"),
            json={"title": "MarkRead Topic", "categoryId": self.category_id, "content": "Hello"},
        ).json()
        requests.post(
            f"{BASE_URL}/posts",
            headers=headers("notif_replier"),
            json={"topicId": topic["id"], "content": "Reply for read"},
        )
        notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("notif_author")).json()
        unread = [n for n in notifs if not n["read"]]
        assert len(unread) >= 1
        notif_id = unread[0]["id"]

        resp = requests.put(
            f"{BASE_URL}/notifications/{notif_id}/read",
            headers=headers("notif_author"),
        )
        assert resp.status_code == 200
        assert resp.json()["read"] is True

    def test_like_generates_notification(self):
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("notif_author"),
            json={"title": "Like Notif Topic", "categoryId": self.category_id, "content": "Like me"},
        ).json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("notif_author"),
        ).json()
        post_id = posts[0]["id"]
        # Like the post
        requests.post(f"{BASE_URL}/posts/{post_id}/like", headers=headers("notif_replier"))
        # Check notifications
        notifs = requests.get(f"{BASE_URL}/notifications", headers=headers("notif_author")).json()
        assert any(n["notificationType"] == "like" for n in notifs)


# ─── Bookmark Tests ────────────────────────────────────────────────────────────


class TestBookmarks:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("bm_user")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("BookmarkCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("bm_user"),
            json={"title": "Bookmark Topic", "categoryId": cat["id"], "content": "Bookmark this"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("bm_user"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.post_id = posts[0]["id"]

    def test_create_bookmark(self):
        resp = requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("bm_user"),
            json={"postId": self.post_id},
        )
        assert resp.status_code == 201
        assert resp.json()["postId"] == self.post_id
        assert resp.json()["userId"] is not None

    def test_create_bookmark_duplicate(self):
        create_user("bm_dup_user")
        requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("bm_dup_user"),
            json={"postId": self.post_id},
        )
        resp = requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("bm_dup_user"),
            json={"postId": self.post_id},
        )
        assert resp.status_code == 409

    def test_list_bookmarks(self):
        create_user("bm_list_user")
        requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("bm_list_user"),
            json={"postId": self.post_id},
        )
        resp = requests.get(f"{BASE_URL}/bookmarks", headers=headers("bm_list_user"))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_bookmark(self):
        create_user("bm_del_user")
        bm = requests.post(
            f"{BASE_URL}/bookmarks",
            headers=headers("bm_del_user"),
            json={"postId": self.post_id},
        ).json()
        resp = requests.delete(f"{BASE_URL}/bookmarks/{bm['id']}", headers=headers("bm_del_user"))
        assert resp.status_code == 204
        # Verify gone
        bms = requests.get(f"{BASE_URL}/bookmarks", headers=headers("bm_del_user")).json()
        assert all(b["id"] != bm["id"] for b in bms)


# ─── Flag Tests ────────────────────────────────────────────────────────────────


class TestFlags:
    @pytest.fixture(autouse=True)
    def setup(self, global_admin):
        self.admin = global_admin
        create_user("flag_basic")
        set_trust_level(self.admin, "flag_basic", 1)
        create_user("flag_newbie")
        create_user("flag_poster")
        cat = requests.post(
            f"{BASE_URL}/categories",
            headers=headers(self.admin),
            json={"name": _resource_name("FlagCat")},
        )
        assert cat.status_code == 201, cat.text
        cat = cat.json()
        topic = requests.post(
            f"{BASE_URL}/topics",
            headers=headers("flag_poster"),
            json={"title": "Flag Topic", "categoryId": cat["id"], "content": "Offensive content"},
        )
        assert topic.status_code == 201, topic.text
        topic = topic.json()
        posts = requests.get(
            f"{BASE_URL}/topics/{topic['id']}/posts",
            headers=headers("flag_poster"),
        )
        assert posts.status_code == 200, posts.text
        posts = posts.json()
        self.post_id = posts[0]["id"]

    def test_create_flag(self):
        resp = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "This is offensive"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"
        assert resp.json()["postId"] == self.post_id

    def test_create_flag_low_trust_level(self):
        resp = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_newbie"),
            json={"postId": self.post_id, "reason": "I disagree"},
        )
        assert resp.status_code == 403

    def test_list_flags_admin(self):
        requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "Spam"},
        )
        resp = requests.get(f"{BASE_URL}/flags", headers=headers(self.admin))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_flags_non_admin(self):
        resp = requests.get(f"{BASE_URL}/flags", headers=headers("flag_basic"))
        assert resp.status_code == 403

    def test_list_flags_filter_by_status(self):
        requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "Filter test"},
        )
        resp = requests.get(
            f"{BASE_URL}/flags",
            headers=headers(self.admin),
            params={"status": "pending"},
        )
        assert resp.status_code == 200
        for flag in resp.json():
            assert flag["status"] == "pending"

    def test_accept_flag(self):
        flag = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "Accept me"},
        ).json()
        resp = requests.put(
            f"{BASE_URL}/flags/{flag['id']}/accept",
            headers=headers(self.admin),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_reject_flag(self):
        flag = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "Reject me"},
        ).json()
        resp = requests.put(
            f"{BASE_URL}/flags/{flag['id']}/reject",
            headers=headers(self.admin),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_accept_flag_non_admin(self):
        flag = requests.post(
            f"{BASE_URL}/flags",
            headers=headers("flag_basic"),
            json={"postId": self.post_id, "reason": "No admin accept"},
        ).json()
        resp = requests.put(
            f"{BASE_URL}/flags/{flag['id']}/accept",
            headers=headers("flag_basic"),
        )
        assert resp.status_code == 403
