import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def api_get(path, api_key, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers(api_key), params=params, timeout=30)


def api_post(path, api_key, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers(api_key), json=json_data, timeout=30)


def test_websites_list_owned_only_excludes_team_shared():
    unique = uuid.uuid4().hex
    owner_key = f"owner-list-{unique}"
    member_key = f"member-list-{unique}"

    owner_site = api_post(
        "/api/websites",
        owner_key,
        {"name": f"owner-shared-{unique}", "domain": f"owner-shared-{unique}.example"},
    )
    assert owner_site.status_code == 201
    owner_site_id = owner_site.json()["id"]

    member_site = api_post(
        "/api/websites",
        member_key,
        {"name": f"member-owned-{unique}", "domain": f"member-owned-{unique}.example"},
    )
    assert member_site.status_code == 201
    member_site_id = member_site.json()["id"]

    member_me = api_get("/api/me", member_key)
    assert member_me.status_code == 200
    member_id = member_me.json()["id"]

    team = api_post("/api/teams", owner_key, {"name": f"team-list-{unique}"})
    assert team.status_code == 201
    team_id = team.json()["id"]

    add_member = api_post(f"/api/teams/{team_id}/members", owner_key, {"userId": member_id})
    assert add_member.status_code == 201

    share_site = api_post(f"/api/teams/{team_id}/websites", owner_key, {"websiteId": owner_site_id})
    assert share_site.status_code == 201

    listed = api_get("/api/websites", member_key)
    assert listed.status_code == 200
    website_ids = {item["id"] for item in listed.json()}

    assert member_site_id in website_ids
    assert owner_site_id not in website_ids
