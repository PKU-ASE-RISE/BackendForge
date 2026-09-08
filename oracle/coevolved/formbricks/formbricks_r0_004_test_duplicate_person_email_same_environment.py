import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(env_id, user_id):
    return {
        "X-User-Id": user_id,
        "X-Environment-Id": env_id,
        "Content-Type": "application/json",
    }


def test_duplicate_person_email_same_environment():
    user_id = str(uuid.uuid4())
    env_id = str(uuid.uuid4())
    other_env_id = str(uuid.uuid4())
    email = f"dup-{uuid.uuid4().hex}@example.com"

    first = requests.post(
        f"{BASE_URL}/api/people",
        json={"email": email, "userId": f"user-{uuid.uuid4().hex}"},
        headers=headers(env_id, user_id),
        timeout=30,
    )
    assert first.status_code == 201, first.text

    isolated = requests.post(
        f"{BASE_URL}/api/people",
        json={"email": email, "userId": f"user-{uuid.uuid4().hex}"},
        headers=headers(other_env_id, user_id),
        timeout=30,
    )
    assert isolated.status_code == 201, isolated.text

    duplicate = requests.post(
        f"{BASE_URL}/api/people",
        json={"email": email, "userId": f"user-{uuid.uuid4().hex}"},
        headers=headers(env_id, user_id),
        timeout=30,
    )
    assert duplicate.status_code == 409, duplicate.text

    listed = requests.get(
        f"{BASE_URL}/api/people",
        headers=headers(env_id, user_id),
        timeout=30,
    )
    assert listed.status_code == 200, listed.text
    matching = [person for person in listed.json() if person.get("email") == email]
    assert len(matching) == 1
