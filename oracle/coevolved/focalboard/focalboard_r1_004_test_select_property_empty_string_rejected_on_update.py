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


def _put(path, json, headers):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers, timeout=30)


def _get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_select_property_empty_string_rejected_on_update():
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

    card_resp = _post(
        f"/boards/{board_id}/cards",
        {"title": _unique("card-"), "properties": {property_id: option_id}},
        headers,
    )
    assert card_resp.status_code == 201
    card_id = card_resp.json()["id"]
    assert card_resp.json()["properties"][property_id] == option_id

    update_resp = _put(
        f"/boards/{board_id}/cards/{card_id}",
        {"properties": {property_id: ""}},
        headers,
    )
    assert update_resp.status_code == 400

    reloaded = _get(f"/boards/{board_id}/cards/{card_id}", headers)
    assert reloaded.status_code == 200
    assert reloaded.json()["properties"][property_id] == option_id
