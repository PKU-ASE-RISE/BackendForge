import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_comments_list_honors_page_and_per_page():
    author_headers = auth_headers()
    commenter_headers = auth_headers()
    token = uuid.uuid4().hex

    article_response = requests.post(
        f"{BASE_URL}/articles",
        json={
            "title": f"Comment Pagination {token}",
            "body_markdown": "body",
            "published": True,
        },
        headers=author_headers,
        timeout=30,
    )
    assert article_response.status_code == 201
    article = article_response.json()

    comment_ids = []
    for index in range(2):
        comment_response = requests.post(
            f"{BASE_URL}/articles/{article['id']}/comments",
            json={"body": f"comment {token} {index}"},
            headers=commenter_headers,
            timeout=30,
        )
        assert comment_response.status_code == 201
        comment_ids.append(comment_response.json()["id"])

    page_response = requests.get(
        f"{BASE_URL}/articles/{article['id']}/comments",
        params={"page": 2, "per_page": 1},
        timeout=30,
    )
    assert page_response.status_code == 200
    payload = page_response.json()

    assert payload["meta"]["total"] == 2
    assert payload["meta"]["page"] == 2
    assert payload["meta"]["per_page"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["id"] in set(comment_ids)
