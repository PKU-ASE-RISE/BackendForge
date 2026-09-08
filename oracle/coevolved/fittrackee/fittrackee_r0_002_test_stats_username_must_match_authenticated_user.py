import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def api_post(path, json_data, headers):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data, headers):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def set_username(headers, username):
    resp = api_patch("/api/auth/profile", {"username": username}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == username


def create_workout(headers, sport_id, distance):
    resp = api_post(
        "/api/workouts",
        {
            "sport_id": sport_id,
            "duration": 3600,
            "distance": distance,
            "workout_date": "2024-10-05 08:00:00",
            "title": f"scope-{uuid.uuid4().hex}",
        },
        headers=headers,
    )
    assert resp.status_code == 201


def test_stats_username_must_match_authenticated_user_for_both_stats_endpoints():
    owner_headers = headers_for()
    intruder_headers = headers_for()
    suffix = uuid.uuid4().hex
    owner_username = f"owner_{suffix}"
    intruder_username = f"intruder_{suffix}"

    set_username(owner_headers, owner_username)
    set_username(intruder_headers, intruder_username)
    create_workout(owner_headers, sport_id=5, distance=12.5)
    create_workout(intruder_headers, sport_id=1, distance=40.0)

    own_stats = api_get(f"/api/stats/{intruder_username}/by_sport", headers=intruder_headers)
    assert own_stats.status_code == 200

    by_sport = api_get(f"/api/stats/{owner_username}/by_sport", headers=intruder_headers)
    assert by_sport.status_code == 404

    by_time = api_get(
        f"/api/stats/{owner_username}/by_time",
        params={"time": "month"},
        headers=intruder_headers,
    )
    assert by_time.status_code == 404
