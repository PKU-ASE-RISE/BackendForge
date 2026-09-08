import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"drp-explicit-tags-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def test_explicit_tags_prevent_auto_matching():
    h = headers()
    match_word = f"automatchtag{uuid.uuid4().hex}"
    manual_tag = post("/api/tags/", {"name": f"manual-{uuid.uuid4().hex}"}, h)
    assert manual_tag.status_code == 201, manual_tag.text
    auto_tag = post(
        "/api/tags/",
        {
            "name": f"auto-{uuid.uuid4().hex}",
            "match": match_word,
            "matching_algorithm": 1,
        },
        h,
    )
    assert auto_tag.status_code == 201, auto_tag.text

    created = post(
        "/api/documents/",
        {
            "title": f"document mentions {match_word}",
            "content": "explicit tags should take precedence",
            "tags": [manual_tag.json()["id"]],
        },
        h,
    )
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]

    reloaded = requests.get(f"{BASE_URL}/api/documents/{doc_id}/", headers=h, timeout=30)
    assert reloaded.status_code == 200
    assert set(reloaded.json()["tags"]) == {manual_tag.json()["id"]}
    assert auto_tag.json()["id"] not in reloaded.json()["tags"]
