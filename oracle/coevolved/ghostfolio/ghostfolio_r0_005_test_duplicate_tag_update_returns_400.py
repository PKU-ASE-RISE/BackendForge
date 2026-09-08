import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_duplicate_tag_update_returns_400():
    user_headers = headers()
    first_name = f"tag-a-{uuid.uuid4().hex}"
    second_name = f"tag-b-{uuid.uuid4().hex}"

    first_response = requests.post(
        f"{BASE_URL}/api/tags",
        json={"name": first_name},
        headers=user_headers,
        timeout=30,
    )
    assert first_response.status_code == 201
    second_response = requests.post(
        f"{BASE_URL}/api/tags",
        json={"name": second_name},
        headers=user_headers,
        timeout=30,
    )
    assert second_response.status_code == 201
    second_id = second_response.json()["id"]

    response = requests.put(
        f"{BASE_URL}/api/tags/{second_id}",
        json={"name": first_name},
        headers=user_headers,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    tags_response = requests.get(f"{BASE_URL}/api/tags", headers=user_headers, timeout=30)
    assert tags_response.status_code == 200
    names = [tag["name"] for tag in tags_response.json()]
    assert names.count(first_name) == 1
    assert second_name in names
