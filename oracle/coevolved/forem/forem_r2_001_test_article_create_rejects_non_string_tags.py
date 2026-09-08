import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_article_create_rejects_non_string_tags():
    response = requests.post(
        f"{BASE_URL}/articles",
        json={
            "title": f"Non String Tags {uuid.uuid4().hex}",
            "body_markdown": "body",
            "published": True,
            "tags": ["python", 123],
        },
        headers=auth_headers(),
        timeout=30,
    )

    assert response.status_code in (400, 422)
    body = response.json()
    assert isinstance(body, dict)
    assert "id" not in body
