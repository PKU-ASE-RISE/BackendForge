import os
import time
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(key):
    return {"X-Api-Key": key, "Content-Type": "application/json"}


def test_url_metrics_count_pageview_events_not_sessions():
    user_key = f"url-metrics-owner-{uuid.uuid4().hex}"
    h = headers(user_key)
    unique = uuid.uuid4().hex

    site_resp = requests.post(
        f"{BASE_URL}/api/websites",
        json={"name": f"URL Metrics {unique}", "domain": f"url-{unique}.example"},
        headers=h,
        timeout=30,
    )
    assert site_resp.status_code == 201
    website_id = site_resp.json()["id"]

    payload = {
        "websiteId": website_id,
        "url": f"/repeat-{unique}",
        "ip": "203.0.113.10",
        "userAgent": f"RepeatAgent/{unique}",
    }

    first = requests.post(f"{BASE_URL}/api/collect", json=payload, timeout=30)
    second = requests.post(f"{BASE_URL}/api/collect", json=payload, timeout=30)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["sessionId"] == second.json()["sessionId"]

    now_ms = int(time.time() * 1000)
    params = {
        "startAt": now_ms - 24 * 60 * 60 * 1000,
        "endAt": now_ms + 24 * 60 * 60 * 1000,
    }

    stats = requests.get(
        f"{BASE_URL}/api/websites/{website_id}/stats",
        params=params,
        headers=h,
        timeout=30,
    )
    assert stats.status_code == 200
    assert stats.json()["pageviews"] == 2

    metrics = requests.get(
        f"{BASE_URL}/api/websites/{website_id}/metrics",
        params={**params, "type": "url"},
        headers=h,
        timeout=30,
    )
    assert metrics.status_code == 200
    by_name = {item["name"]: item["count"] for item in metrics.json()}
    assert by_name[payload["url"]] == 2
