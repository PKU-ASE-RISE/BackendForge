import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(token):
    return {"X-Auth-Token": token, "Content-Type": "application/json"}


def _post(path, headers, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=payload, timeout=30)


def _get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_duplicate_entry_url_returns_existing_entry():
    suffix = uuid.uuid4().hex
    headers = _headers(f"duplicate-entry-user-{suffix}")

    assert _get("/v1/me", headers).status_code == 200
    category = _post("/v1/categories", headers, {"title": f"duplicate-entry-{suffix}"})
    assert category.status_code == 201
    feed = _post(
        "/v1/feeds",
        headers,
        {
            "feed_url": f"https://example.com/duplicate-entry-{suffix}.xml",
            "category_id": category.json()["id"],
            "title": "Duplicate Entry Feed",
        },
    )
    assert feed.status_code == 201
    feed_id = feed.json()["feed_id"]

    entry_url = f"https://example.com/articles/duplicate-{suffix}"
    first_resp = _post(
        f"/v1/feeds/{feed_id}/entries",
        headers,
        {
            "title": "Original Entry",
            "url": entry_url,
            "content": "original body",
            "author": "author one",
        },
    )
    assert first_resp.status_code == 201
    first = first_resp.json()
    assert first["url"] == entry_url

    duplicate_resp = _post(
        f"/v1/feeds/{feed_id}/entries",
        headers,
        {
            "title": "Duplicate Attempt Should Be Ignored",
            "url": entry_url,
            "content": "mutating body should not replace original",
            "author": "author two",
        },
    )
    assert duplicate_resp.status_code == 201
    duplicate = duplicate_resp.json()
    assert duplicate["id"] == first["id"]
    assert duplicate["title"] == first["title"]
    assert duplicate["content"] == first["content"]
    assert duplicate["author"] == first["author"]

    listing = _get(f"/v1/feeds/{feed_id}/entries", headers)
    assert listing.status_code == 200
    entries_with_url = [entry for entry in listing.json()["entries"] if entry["url"] == entry_url]
    assert len(entries_with_url) == 1
    assert entries_with_url[0]["id"] == first["id"]
