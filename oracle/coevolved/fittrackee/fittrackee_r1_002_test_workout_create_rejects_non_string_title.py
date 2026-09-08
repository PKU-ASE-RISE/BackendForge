import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_workout_create_rejects_non_string_title():
    headers = headers_for()

    response = requests.post(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        json={
            "sport_id": 5,
            "duration": 1200,
            "distance": 3.0,
            "workout_date": "2024-08-15 07:30:00",
            "title": {"not": "a string"},
        },
        timeout=30,
    )

    assert response.status_code == 400, response.text
