import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def test_v3_short_urls_list_endpoint():
    response = requests.get(
        f"{BASE_URL}/rest/v3/short-urls",
        headers=HEADERS,
        params={"page": 1, "itemsPerPage": 1},
        timeout=30,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "shortUrls" in payload
    assert isinstance(payload["shortUrls"].get("data"), list)
    pagination = payload["shortUrls"].get("pagination")
    assert isinstance(pagination, dict)
    for field in [
        "currentPage",
        "pagesCount",
        "itemsPerPage",
        "itemsInCurrentPage",
        "totalItems",
    ]:
        assert field in pagination
