import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def _create_short_url_with_tag(tag):
    response = requests.post(
        f"{BASE_URL}/rest/v3/short-urls",
        headers=HEADERS,
        json={
            "longUrl": f"https://example.com/tag-dedup/{uuid.uuid4().hex}",
            "tags": [tag],
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_case_insensitive_tag_deduplication():
    suffix = uuid.uuid4().hex[:10]
    first_spelling = f"CaseProbe-{suffix}"
    second_spelling = first_spelling.lower()

    _create_short_url_with_tag(first_spelling)
    _create_short_url_with_tag(second_spelling)

    response = requests.get(
        f"{BASE_URL}/rest/v3/tags/stats",
        headers=HEADERS,
        params={"itemsPerPage": 1000},
        timeout=30,
    )
    assert response.status_code == 200, response.text

    tag_infos = response.json()["tags"]["data"]
    matching = [
        item for item in tag_infos if item.get("tag", "").lower() == second_spelling
    ]

    assert len(matching) == 1, matching
    assert matching[0]["tag"] == first_spelling
    assert matching[0]["shortUrlsCount"] == 2
