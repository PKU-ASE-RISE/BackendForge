import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_post(path, json_data, headers):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def api_patch(path, json_data, headers):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def test_create_workout_with_non_integer_duration_returns_400():
    headers = headers_for()
    title = f"bad-duration-{uuid.uuid4().hex}"

    resp = api_post(
        "/api/workouts",
        {
            "sport_id": 5,
            "duration": "not-seconds",
            "distance": 5.0,
            "workout_date": "2024-11-02 09:00:00",
            "title": title,
        },
        headers=headers,
    )

    assert resp.status_code == 400
    listed = api_get("/api/workouts", headers=headers)
    assert listed.status_code == 200
    assert all(w.get("title") != title for w in listed.json()["data"]["workouts"])


def test_patch_workout_with_non_numeric_distance_returns_400_and_preserves_value():
    headers = headers_for()
    create = api_post(
        "/api/workouts",
        {
            "sport_id": 5,
            "duration": 1800,
            "distance": 4.0,
            "workout_date": "2024-11-03 09:00:00",
            "title": f"valid-before-bad-patch-{uuid.uuid4().hex}",
        },
        headers=headers,
    )
    assert create.status_code == 201
    workout_id = create.json()["data"]["workouts"][0]["id"]

    patch = api_patch(f"/api/workouts/{workout_id}", {"distance": "far"}, headers=headers)
    assert patch.status_code == 400

    reloaded = api_get(f"/api/workouts/{workout_id}", headers=headers)
    assert reloaded.status_code == 200
    assert reloaded.json()["data"]["workouts"][0]["distance"] == 4.0
