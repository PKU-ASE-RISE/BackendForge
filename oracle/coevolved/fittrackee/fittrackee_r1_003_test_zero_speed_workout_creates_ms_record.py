import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_zero_speed_workout_creates_ms_record():
    headers = headers_for()

    create_response = requests.post(
        f"{BASE_URL}/api/workouts",
        headers=headers,
        json={
            "sport_id": 6,
            "duration": 0,
            "distance": 5.0,
            "workout_date": "2024-09-03 06:45:00",
            "title": f"zero-speed-{uuid.uuid4().hex}",
        },
        timeout=30,
    )
    assert create_response.status_code == 201, create_response.text
    workout = create_response.json()["data"]["workouts"][0]
    assert workout["ave_speed"] == 0
    assert workout["max_speed"] == 0

    records_response = requests.get(f"{BASE_URL}/api/records", headers=headers, timeout=30)
    assert records_response.status_code == 200, records_response.text

    records = [
        record
        for record in records_response.json()["data"]["records"]
        if record["sport_id"] == 6 and record["workout_id"] == workout["id"]
    ]
    records_by_type = {record["record_type"]: record for record in records}

    assert "FD" in records_by_type
    assert "LD" in records_by_type
    assert "MS" in records_by_type
    assert records_by_type["MS"]["value"] == 0
