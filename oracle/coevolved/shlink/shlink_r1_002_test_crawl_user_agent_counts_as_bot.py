import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def test_crawl_user_agent_counts_as_bot():
    slug = f"crawl-{uuid.uuid4().hex[:12]}"
    create_resp = requests.post(
        f"{BASE_URL}/rest/v3/short-urls",
        json={
            "longUrl": f"https://example.com/{slug}",
            "customSlug": slug,
        },
        headers=HEADERS,
        timeout=30,
    )
    assert create_resp.status_code == 200, create_resp.text

    visit_resp = requests.get(
        f"{BASE_URL}/{slug}",
        headers={
            "User-Agent": "ExampleCrawlClient/1.0",
            "Referer": "https://referer.example/crawl",
        },
        allow_redirects=False,
        timeout=30,
    )
    assert visit_resp.status_code == 302, visit_resp.text

    visits_resp = requests.get(
        f"{BASE_URL}/rest/v3/short-urls/{slug}/visits",
        headers=HEADERS,
        timeout=30,
    )
    assert visits_resp.status_code == 200, visits_resp.text
    visits = visits_resp.json()["visits"]["data"]
    assert len(visits) == 1
    assert visits[0]["userAgent"] == "ExampleCrawlClient/1.0"
    assert visits[0]["potentialBot"] is True

    detail_resp = requests.get(
        f"{BASE_URL}/rest/v3/short-urls/{slug}",
        headers=HEADERS,
        timeout=30,
    )
    assert detail_resp.status_code == 200, detail_resp.text
    summary = detail_resp.json()["visitsSummary"]
    assert summary["bots"] == 1
    assert summary["nonBots"] == 0
