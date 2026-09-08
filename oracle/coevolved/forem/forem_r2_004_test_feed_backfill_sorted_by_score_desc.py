import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def create_published_article(headers, title):
    response = requests.post(
        f"{BASE_URL}/articles",
        json={"title": title, "body_markdown": "feed body", "published": True},
        headers=headers,
        timeout=30,
    )
    assert response.status_code == 201
    return response.json()


def test_feed_backfill_sorted_by_score_desc():
    author_headers = auth_headers()
    reactor_one_headers = auth_headers()
    reactor_two_headers = auth_headers()
    reader_headers = auth_headers()
    token = uuid.uuid4().hex

    high_score_article = create_published_article(
        author_headers,
        f"High Score Backfill {token}",
    )
    for reactor_headers in (reactor_one_headers, reactor_two_headers):
        reaction_response = requests.post(
            f"{BASE_URL}/articles/{high_score_article['id']}/reactions",
            json={"category": "like"},
            headers=reactor_headers,
            timeout=30,
        )
        assert reaction_response.status_code == 200
    comment_response = requests.post(
        f"{BASE_URL}/articles/{high_score_article['id']}/comments",
        json={"body": f"score comment {token}"},
        headers=reactor_one_headers,
        timeout=30,
    )
    assert comment_response.status_code == 201

    low_score_article = create_published_article(
        author_headers,
        f"Low Score Newer Backfill {token}",
    )

    high_reload = requests.get(
        f"{BASE_URL}/articles/{high_score_article['id']}",
        timeout=30,
    )
    assert high_reload.status_code == 200
    assert high_reload.json()["score"] > low_score_article["score"]

    feed_response = requests.get(
        f"{BASE_URL}/articles/feed",
        params={"page": 1, "per_page": 100},
        headers=reader_headers,
        timeout=30,
    )
    assert feed_response.status_code == 200
    feed_ids = [item["id"] for item in feed_response.json()["data"]]

    assert high_score_article["id"] in feed_ids
    assert low_score_article["id"] in feed_ids
    assert feed_ids.index(high_score_article["id"]) < feed_ids.index(low_score_article["id"])
