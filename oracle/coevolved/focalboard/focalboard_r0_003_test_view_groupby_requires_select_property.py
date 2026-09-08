import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_view_groupby_text_property_is_rejected_and_not_persisted():
    user_id = str(uuid.uuid4())
    headers = _headers(user_id)

    board_resp = requests.post(
        f"{BASE_URL}/boards",
        json={"title": f"groupby-{uuid.uuid4().hex}", "type": "board"},
        headers=headers,
        timeout=30,
    )
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    prop_resp = requests.post(
        f"{BASE_URL}/boards/{board_id}/properties",
        json={"name": "Plain text grouping is invalid", "type": "text"},
        headers=headers,
        timeout=30,
    )
    assert prop_resp.status_code == 201
    text_property_id = prop_resp.json()["id"]

    view_name = f"invalid-groupby-{uuid.uuid4().hex}"
    view_resp = requests.post(
        f"{BASE_URL}/boards/{board_id}/views",
        json={"name": view_name, "type": "board", "groupBy": text_property_id},
        headers=headers,
        timeout=30,
    )
    assert 400 <= view_resp.status_code < 500

    list_resp = requests.get(f"{BASE_URL}/boards/{board_id}/views", headers=headers, timeout=30)
    assert list_resp.status_code == 200
    assert all(view["name"] != view_name for view in list_resp.json())
