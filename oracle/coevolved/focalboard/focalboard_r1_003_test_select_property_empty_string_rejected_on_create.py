import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(user_id=None):
    return {"X-User-Id": user_id or str(uuid.uuid4()), "Content-Type": "application/json"}


def _unique(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def _post(path, json, headers):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers, timeout=30)


def _get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def test_select_property_empty_string_rejected_on_create():
    headers = _headers()
    board_resp = _post("/boards", {"title": _unique("board-"), "type": "board"}, headers)
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    option_id = str(uuid.uuid4())
    prop_resp = _post(
        f"/boards/{board_id}/properties",
        {
            "name": _unique("status-"),
            "type": "select",
            "options": [{"id": option_id, "value": "Todo"}],
        },
        headers,
    )
    assert prop_resp.status_code == 201
    property_id = prop_resp.json()["id"]

    bad_title = _unique("bad-select-")
    create_resp = _post(
        f"/boards/{board_id}/cards",
        {"title": bad_title, "properties": {property_id: ""}},
        headers,
    )
    assert create_resp.status_code == 400

    cards_resp = _get(f"/boards/{board_id}/cards", headers)
    assert cards_resp.status_code == 200
    assert all(card["title"] != bad_title for card in cards_resp.json())
