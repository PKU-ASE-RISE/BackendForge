import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers(user_id=None):
    return {
        "X-User-Id": user_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def get_current_user(headers):
    response = requests.get(f"{BASE_URL}/users/me", headers=headers, timeout=30)
    assert response.status_code == 200
    return response.json()


def test_org_members_list_honors_page_and_per_page():
    owner_headers = auth_headers()
    second_headers = auth_headers()
    owner_user = get_current_user(owner_headers)
    second_user = get_current_user(second_headers)
    token = uuid.uuid4().hex
    slug = f"members-page-{token}"

    org_response = requests.post(
        f"{BASE_URL}/organizations",
        json={"name": f"Members Page {token}", "slug": slug},
        headers=owner_headers,
        timeout=30,
    )
    assert org_response.status_code == 201

    add_response = requests.post(
        f"{BASE_URL}/organizations/{slug}/members",
        json={"username": second_user["username"]},
        headers=owner_headers,
        timeout=30,
    )
    assert add_response.status_code == 201

    page_response = requests.get(
        f"{BASE_URL}/organizations/{slug}/members",
        params={"page": 2, "per_page": 1},
        timeout=30,
    )
    assert page_response.status_code == 200
    payload = page_response.json()

    assert payload["meta"]["total"] == 2
    assert payload["meta"]["page"] == 2
    assert payload["meta"]["per_page"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["id"] in {owner_user["id"], second_user["id"]}
