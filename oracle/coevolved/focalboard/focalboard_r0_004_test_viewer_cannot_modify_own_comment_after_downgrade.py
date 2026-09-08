import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def _post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _put(path, payload, headers):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def _delete(path, headers):
    return requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=30)


def _setup_comment_then_downgrade_to_viewer():
    admin_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    admin_headers = _headers(admin_id)
    member_headers = _headers(member_id)

    board_resp = _post(
        "/boards",
        {"title": f"downgrade-{uuid.uuid4().hex}", "type": "board"},
        admin_headers,
    )
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    member_resp = _post(
        f"/boards/{board_id}/members",
        {"userId": member_id, "role": "commenter"},
        admin_headers,
    )
    assert member_resp.status_code == 201

    card_resp = _post(f"/boards/{board_id}/cards", {"title": "comment target"}, admin_headers)
    assert card_resp.status_code == 201
    card_id = card_resp.json()["id"]

    original_text = f"original-{uuid.uuid4().hex}"
    comment_resp = _post(
        f"/boards/{board_id}/cards/{card_id}/comments",
        {"text": original_text},
        member_headers,
    )
    assert comment_resp.status_code == 201
    comment_id = comment_resp.json()["id"]

    downgrade_resp = _put(
        f"/boards/{board_id}/members/{member_id}",
        {"role": "viewer"},
        admin_headers,
    )
    assert downgrade_resp.status_code == 200
    assert downgrade_resp.json()["role"] == "viewer"

    return board_id, card_id, comment_id, original_text, admin_headers, member_headers


def test_viewer_cannot_update_own_comment_after_downgrade():
    board_id, card_id, comment_id, original_text, admin_headers, member_headers = (
        _setup_comment_then_downgrade_to_viewer()
    )

    update_resp = _put(
        f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}",
        {"text": "viewer should not edit"},
        member_headers,
    )
    assert update_resp.status_code == 403

    comments_resp = _get(f"/boards/{board_id}/cards/{card_id}/comments", admin_headers)
    assert comments_resp.status_code == 200
    comments = {comment["id"]: comment for comment in comments_resp.json()}
    assert comments[comment_id]["text"] == original_text


def test_viewer_cannot_delete_own_comment_after_downgrade():
    board_id, card_id, comment_id, _, admin_headers, member_headers = (
        _setup_comment_then_downgrade_to_viewer()
    )

    delete_resp = _delete(
        f"/boards/{board_id}/cards/{card_id}/comments/{comment_id}",
        member_headers,
    )
    assert delete_resp.status_code == 403

    comments_resp = _get(f"/boards/{board_id}/cards/{card_id}/comments", admin_headers)
    assert comments_resp.status_code == 200
    comment_ids = {comment["id"] for comment in comments_resp.json()}
    assert comment_id in comment_ids
