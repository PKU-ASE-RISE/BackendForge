import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_workout_create_rejects_invalid_workout_date():
    headers = headers_for()
    marker = f"invalid-date-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        json={
            "sport_id": 5,
            "duration": 1800,
            "distance": 4.2,
            "workout_date": f"not-a-date-{marker}",
            "title": marker,
        },
        timeout=30,
    )

    assert response.status_code == 400, response.text

    list_response = requests.get(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        params={"title": marker, "per_page": 10},
        timeout=30,
    )
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["data"]["workouts"] == []
