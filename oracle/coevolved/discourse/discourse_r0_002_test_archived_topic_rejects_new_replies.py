import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
API_KEY = "discourse-api-key"
ADMIN_USER = "discourse_test_admin"


def headers(username):
    return {"X-API-Key": API_KEY, "X-Username": username}


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def create_user(username, email=None, name=None, expected_status=201):
    response = requests.post(
        f"{BASE_URL}/users",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": "password123",
            "name": name or username,
        },
    )
    if expected_status is not None:
        assert response.status_code == expected_status, response.text
    return response


def ensure_admin():
    created = create_user(
        ADMIN_USER,
        f"{ADMIN_USER}@example.com",
        "Direct Reference Admin",
        expected_status=None,
    )
    assert created.status_code in {201, 409}, created.text
    promote = requests.put(
        f"{BASE_URL}/users/{ADMIN_USER}/trust-level",
        headers=headers(ADMIN_USER),
        json={"trustLevel": 4},
    )
    assert promote.status_code == 200, promote.text
    return ADMIN_USER


def test_archived_topic_rejects_new_replies():
    admin = ensure_admin()
    author = unique("drp_archive_author")
    create_user(author)

    category = requests.post(
        f"{BASE_URL}/categories",
        headers=headers(admin),
        json={"name": unique("Archive Category")},
    )
    assert category.status_code == 201, category.text

    topic = requests.post(
        f"{BASE_URL}/topics",
        headers=headers(author),
        json={
            "title": f"Archived topic {uuid.uuid4().hex}",
            "categoryId": category.json()["id"],
            "content": "Original archived-topic post",
        },
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["id"]

    archived = requests.put(
        f"{BASE_URL}/topics/{topic_id}/archive",
        headers=headers(admin),
        json={"archived": True},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True

    blocked_content = f"reply should not persist {uuid.uuid4().hex}"
    reply = requests.post(
        f"{BASE_URL}/posts",
        headers=headers(author),
        json={"topicId": topic_id, "content": blocked_content},
    )

    posts = requests.get(f"{BASE_URL}/topics/{topic_id}/posts", headers=headers(author))
    assert posts.status_code == 200, posts.text
    assert all(post["content"] != blocked_content for post in posts.json())
    assert reply.status_code == 403, reply.text
