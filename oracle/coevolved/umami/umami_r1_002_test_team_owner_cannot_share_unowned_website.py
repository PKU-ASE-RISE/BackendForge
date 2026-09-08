import os
import time
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def api_get(path, api_key, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers(api_key), params=params, timeout=30)


def api_post(path, api_key, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers(api_key), json=json_data, timeout=30)


def test_team_owner_cannot_share_unowned_website():
    unique = uuid.uuid4().hex
    team_owner_key = f"team-owner-unowned-{unique}"
    website_owner_key = f"site-owner-unowned-{unique}"

    team = api_post("/api/teams", team_owner_key, {"name": f"unowned-share-team-{unique}"})
    assert team.status_code == 201
    team_id = team.json()["id"]

    private_site = api_post(
        "/api/websites",
        website_owner_key,
        {"name": f"private-unowned-{unique}", "domain": f"private-unowned-{unique}.example"},
    )
    assert private_site.status_code == 201
    private_site_id = private_site.json()["id"]

    denied = api_post(f"/api/teams/{team_id}/websites", team_owner_key, {"websiteId": private_site_id})
    assert denied.status_code == 404

    team_websites = api_get(f"/api/teams/{team_id}/websites", team_owner_key)
    assert team_websites.status_code == 200
    assert private_site_id not in {item["websiteId"] for item in team_websites.json()}

    now_ms = int(time.time() * 1000)
    stats = api_get(
        f"/api/websites/{private_site_id}/stats",
        team_owner_key,
        params={"startAt": now_ms - 86_400_000, "endAt": now_ms + 86_400_000},
    )
    assert stats.status_code == 404
