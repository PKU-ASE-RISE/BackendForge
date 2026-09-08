import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_article_update_rejects_non_string_tags_without_mutating():
    headers = auth_headers()
    token = uuid.uuid4().hex

    created_response = requests.post(
        f"{BASE_URL}/articles",
        json={
            "title": f"Update Non String Tags {token}",
            "body_markdown": "body",
            "published": True,
            "tags": ["python", "testing"],
        },
        headers=headers,
        timeout=30,
    )
    assert created_response.status_code == 201
    article = created_response.json()
    assert article["tags"] == ["python", "testing"]

    update_response = requests.put(
        f"{BASE_URL}/articles/{article['id']}",
        json={"tags": ["python", {"bad": "tag"}]},
        headers=headers,
        timeout=30,
    )
    assert update_response.status_code in (400, 422)

    reload_response = requests.get(
        f"{BASE_URL}/articles/{article['id']}",
        timeout=30,
    )
    assert reload_response.status_code == 200
    assert reload_response.json()["tags"] == ["python", "testing"]
