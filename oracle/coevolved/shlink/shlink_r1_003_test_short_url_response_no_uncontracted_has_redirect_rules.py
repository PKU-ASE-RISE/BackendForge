import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def test_short_url_response_no_uncontracted_has_redirect_rules():
    slug = f"schema-{uuid.uuid4().hex[:12]}"
    payload = {
        "longUrl": f"https://example.com/{slug}",
        "customSlug": slug,
    }

    create_resp = requests.post(
        f"{BASE_URL}/rest/v3/short-urls",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()

    assert "hasRedirectRules" not in created

    get_resp = requests.get(
        f"{BASE_URL}/rest/v3/short-urls/{slug}",
        headers=HEADERS,
        timeout=30,
    )
    assert get_resp.status_code == 200, get_resp.text
    reloaded = get_resp.json()

    assert "hasRedirectRules" not in reloaded
