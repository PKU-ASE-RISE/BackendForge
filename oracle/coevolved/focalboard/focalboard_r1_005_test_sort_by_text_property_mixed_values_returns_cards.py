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


def test_sort_by_text_property_mixed_values_returns_cards():
    headers = _headers()
    board_resp = _post("/boards", {"title": _unique("board-"), "type": "table"}, headers)
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    prop_resp = _post(
        f"/boards/{board_id}/properties",
        {"name": _unique("rank-"), "type": "text"},
        headers,
    )
    assert prop_resp.status_code == 201
    property_id = prop_resp.json()["id"]

    numeric_title = _unique("numeric-looking-")
    alpha_title = _unique("alpha-")
    first_card = _post(
        f"/boards/{board_id}/cards",
        {"title": numeric_title, "properties": {property_id: "10"}},
        headers,
    )
    assert first_card.status_code == 201
    second_card = _post(
        f"/boards/{board_id}/cards",
        {"title": alpha_title, "properties": {property_id: "alpha"}},
        headers,
    )
    assert second_card.status_code == 201

    sorted_resp = _get(f"/boards/{board_id}/cards", headers, params={"sort_by": property_id})
    assert sorted_resp.status_code == 200
    titles = {card["title"] for card in sorted_resp.json()}
    assert {numeric_title, alpha_title}.issubset(titles)
