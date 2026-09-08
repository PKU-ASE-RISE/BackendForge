import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {
        "X-Auth-Token": f"direct-probe-dup-entry-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def _post(path, headers, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def _create_feed(headers, suffix):
    category_resp = _post("/v1/categories", headers, {"title": f"dup-entry-cat-{suffix}"})
    assert category_resp.status_code == 201, category_resp.text
    category_id = category_resp.json()["id"]

    feed_resp = _post(
        "/v1/feeds",
        headers,
        {
            "feed_url": f"https://example.com/direct-probe/dup-entry-{suffix}.xml",
            "category_id": category_id,
            "title": f"Duplicate Entry Feed {suffix}",
        },
    )
    assert feed_resp.status_code == 201, feed_resp.text
    return feed_resp.json()["feed_id"]


def test_duplicate_entry_url_returns_existing():
    headers = _headers()
    suffix = uuid.uuid4().hex
    feed_id = _create_feed(headers, suffix)
    entry_url = f"https://example.com/articles/{suffix}"

    first_resp = _post(
        f"/v1/feeds/{feed_id}/entries",
        headers,
        {
            "title": f"Original duplicate candidate {suffix}",
            "url": entry_url,
            "content": "original content",
            "author": "direct-reference-prober",
        },
    )
    assert first_resp.status_code == 201, first_resp.text
    first_entry = first_resp.json()
    assert first_entry["url"] == entry_url
    assert first_entry["title"] == f"Original duplicate candidate {suffix}"

    duplicate_resp = _post(
        f"/v1/feeds/{feed_id}/entries",
        headers,
        {
            "title": f"Replacement should be ignored {suffix}",
            "url": entry_url,
            "content": "replacement content should not create a second row",
            "author": "direct-reference-prober",
        },
    )
    assert duplicate_resp.status_code == 201, duplicate_resp.text
    duplicate_entry = duplicate_resp.json()
    assert duplicate_entry["id"] == first_entry["id"]
    assert duplicate_entry["url"] == entry_url

    reloaded_resp = _get(f"/v1/entries/{first_entry['id']}", headers)
    assert reloaded_resp.status_code == 200, reloaded_resp.text
    reloaded_entry = reloaded_resp.json()
    assert reloaded_entry["id"] == first_entry["id"]
    assert reloaded_entry["title"] == f"Original duplicate candidate {suffix}"
    assert reloaded_entry["content"] == "original content"

    feed_entries_resp = _get(f"/v1/feeds/{feed_id}/entries", headers)
    assert feed_entries_resp.status_code == 200, feed_entries_resp.text
    feed_entries = feed_entries_resp.json()
    assert feed_entries["total"] == 1
    assert [entry["id"] for entry in feed_entries["entries"]] == [first_entry["id"]]
