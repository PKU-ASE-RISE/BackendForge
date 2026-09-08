import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_workout_create_rejects_date_only_workout_date():
    headers = headers_for()
    title = f"date-only-create-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        json={
            "sport_id": 5,
            "duration": 1800,
            "distance": 4.2,
            "workout_date": "2024-10-31",
            "title": title,
        },
        timeout=30,
    )

    assert response.status_code == 400, response.text

    listed = requests.get(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        params={"title": title, "per_page": 50},
        timeout=30,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["workouts"] == []
