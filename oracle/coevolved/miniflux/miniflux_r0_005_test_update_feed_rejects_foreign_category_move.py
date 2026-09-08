import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(token):
    return {"X-Auth-Token": token, "Content-Type": "application/json"}


def _post(path, headers, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=payload, timeout=30)


def _put(path, headers, payload):
    return requests.put(f"{BASE_URL}{path}", headers=headers, json=payload, timeout=30)


def _get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_update_feed_rejects_foreign_category_move():
    suffix = uuid.uuid4().hex
    owner = _headers(f"owner-update-feed-{suffix}")
    mover = _headers(f"mover-update-feed-{suffix}")

    owner_me = _get("/v1/me", owner)
    mover_me = _get("/v1/me", mover)
    assert owner_me.status_code == 200
    assert mover_me.status_code == 200
    owner_user_id = owner_me.json()["id"]
    mover_user_id = mover_me.json()["id"]
    assert owner_user_id != mover_user_id

    foreign_cat_resp = _post("/v1/categories", owner, {"title": f"foreign-move-{suffix}"})
    own_cat_resp = _post("/v1/categories", mover, {"title": f"own-move-{suffix}"})
    assert foreign_cat_resp.status_code == 201
    assert own_cat_resp.status_code == 201
    foreign_cat = foreign_cat_resp.json()
    own_cat = own_cat_resp.json()
    assert foreign_cat["user_id"] == owner_user_id
    assert own_cat["user_id"] == mover_user_id

    feed_resp = _post(
        "/v1/feeds",
        mover,
        {
            "feed_url": f"https://example.com/move-feed-{suffix}.xml",
            "category_id": own_cat["id"],
            "title": "Move Candidate",
        },
    )
    assert feed_resp.status_code == 201
    feed_id = feed_resp.json()["feed_id"]

    move_resp = _put(
        f"/v1/feeds/{feed_id}",
        mover,
        {"category_id": foreign_cat["id"], "title": "Move Candidate Updated"},
    )
    assert move_resp.status_code != 200

    reloaded_resp = _get(f"/v1/feeds/{feed_id}", mover)
    assert reloaded_resp.status_code == 200
    reloaded = reloaded_resp.json()
    assert reloaded["user_id"] == mover_user_id
    assert reloaded["category"]["id"] == own_cat["id"]
    assert reloaded["category"]["user_id"] == mover_user_id
