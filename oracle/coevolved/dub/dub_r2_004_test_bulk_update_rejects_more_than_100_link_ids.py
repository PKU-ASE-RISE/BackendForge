import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["X-API-Key"] = ADMIN_KEY
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_bulk_update_rejects_more_than_100_link_ids():
    marker = uuid.uuid4().hex
    link_ids = []
    for i in range(101):
        created = api(
            "post",
            "/links",
            json={
                "url": f"https://example.com/bulk-update-max/{marker}/{i}",
                "slug": f"bu{marker[:8]}{i:03d}",
                "title": "before",
            },
        )
        assert created.status_code == 201
        link_ids.append(created.json()["id"])

    resp = api("patch", "/links/bulk", json={"linkIds": link_ids, "data": {"title": "after"}})

    assert resp.status_code in (400, 422)
    body = resp.json()
    assert "error" in body

    for link_id in link_ids[:3]:
        reloaded = api("get", f"/links/{link_id}")
        assert reloaded.status_code == 200
        assert reloaded.json()["title"] == "before"
