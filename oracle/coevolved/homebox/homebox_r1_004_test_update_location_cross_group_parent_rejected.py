import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30


def make_headers(group_id=None, user_id=None):
    return {
        "X-User-Id": user_id or str(uuid.uuid4()),
        "X-Group-Id": group_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_update_location_cross_group_parent_rejected():
    group_a = str(uuid.uuid4())
    group_b = str(uuid.uuid4())
    h_a = make_headers(group_a)
    h_b = make_headers(group_b)
    suffix = uuid.uuid4().hex

    child = requests.post(
        f"{BASE_URL}/locations",
        json={"name": f"ChildRoot-{suffix}"},
        headers=h_a,
        timeout=REQUEST_TIMEOUT,
    )
    assert child.status_code == 201, child.text
    child_id = child.json()["id"]
    assert child.json()["parentId"] is None

    foreign_parent = requests.post(
        f"{BASE_URL}/locations",
        json={"name": f"ForeignParent-{suffix}"},
        headers=h_b,
        timeout=REQUEST_TIMEOUT,
    )
    assert foreign_parent.status_code == 201, foreign_parent.text
    foreign_parent_id = foreign_parent.json()["id"]

    update = requests.put(
        f"{BASE_URL}/locations/{child_id}",
        json={"name": f"ChildRoot-{suffix}", "parentId": foreign_parent_id},
        headers=h_a,
        timeout=REQUEST_TIMEOUT,
    )
    assert update.status_code in (400, 404), update.text
    assert "error" in update.json()

    reloaded = requests.get(
        f"{BASE_URL}/locations/{child_id}", headers=h_a, timeout=REQUEST_TIMEOUT
    )
    assert reloaded.status_code == 200, reloaded.text
    data = reloaded.json()
    assert data["id"] == child_id
    assert data["name"] == f"ChildRoot-{suffix}"
    assert data["parentId"] is None
    assert data["parentId"] != foreign_parent_id
