import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api(method, path, user_id, json_data=None, params=None):
    return requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers(user_id),
        json=json_data,
        params=params,
        timeout=30,
    )


def test_category_update_rejects_foreign_group():
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex

    own_group_resp = api(
        "POST",
        "/category-groups",
        user_id,
        {"name": f"owned-category-group-{suffix}"},
    )
    assert own_group_resp.status_code == 201, own_group_resp.text
    own_group_id = own_group_resp.json()["id"]

    category_resp = api(
        "POST",
        "/categories",
        user_id,
        {"name": f"owned-category-{suffix}", "groupId": own_group_id},
    )
    assert category_resp.status_code == 201, category_resp.text
    category_id = category_resp.json()["id"]

    foreign_group_resp = api(
        "POST",
        "/category-groups",
        other_user_id,
        {"name": f"foreign-target-group-{suffix}"},
    )
    assert foreign_group_resp.status_code == 201, foreign_group_resp.text
    foreign_group_id = foreign_group_resp.json()["id"]

    update_resp = api(
        "PUT",
        f"/categories/{category_id}",
        user_id,
        {"groupId": foreign_group_id},
    )
    assert update_resp.status_code == 400, update_resp.text

    reloaded_resp = api("GET", f"/categories/{category_id}", user_id)
    assert reloaded_resp.status_code == 200, reloaded_resp.text
    assert reloaded_resp.json()["groupId"] == own_group_id
