import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def get(path, user_id, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers(user_id), params=params, timeout=30)


def post(path, user_id, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers(user_id), json=payload, timeout=30)


def test_links_list_search_matches_tag_names():
    user_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex
    tag_name = f"tagonly-{unique}"

    tagged_resp = post(
        "/api/links",
        user_id,
        {
            "url": f"https://tag-search-target-{unique}.example.com",
            "name": "tag search target",
            "description": "no matching token here",
            "tags": [{"name": tag_name}],
        },
    )
    assert tagged_resp.status_code == 201
    tagged_link = tagged_resp.json()

    decoy_resp = post(
        "/api/links",
        user_id,
        {
            "url": f"https://tag-search-decoy-{unique}.example.com",
            "name": "tag search decoy",
            "description": "also no matching token",
        },
    )
    assert decoy_resp.status_code == 201
    decoy_link = decoy_resp.json()

    search_resp = get("/api/links", user_id, params={"search": tag_name})
    assert search_resp.status_code == 200
    result_ids = {link["id"] for link in search_resp.json()["links"]}
    assert tagged_link["id"] in result_ids
    assert decoy_link["id"] not in result_ids
