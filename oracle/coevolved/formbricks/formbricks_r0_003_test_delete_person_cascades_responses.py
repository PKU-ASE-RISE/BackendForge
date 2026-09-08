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


def test_delete_person_cascades_responses():
    user_id = str(uuid.uuid4())
    env_id = str(uuid.uuid4())
    hdrs = headers(env_id, user_id)
    token = uuid.uuid4().hex

    person = requests.post(
        f"{BASE_URL}/api/people",
        json={"email": f"cascade-{token}@example.com", "attributes": {"plan": "pro"}},
        headers=hdrs,
        timeout=30,
    )
    assert person.status_code == 201, person.text
    person_id = person.json()["id"]

    survey = requests.post(
        f"{BASE_URL}/api/surveys",
        json={"name": f"Person cascade {token}"},
        headers=hdrs,
        timeout=30,
    )
    assert survey.status_code == 201, survey.text
    survey_id = survey.json()["id"]

    question = requests.post(
        f"{BASE_URL}/api/surveys/{survey_id}/questions",
        json={"type": "openText", "headline": "Comment"},
        headers=hdrs,
        timeout=30,
    )
    assert question.status_code == 201, question.text
    question_id = question.json()["id"]

    activate = requests.patch(
        f"{BASE_URL}/api/surveys/{survey_id}/status",
        json={"status": "active"},
        headers=hdrs,
        timeout=30,
    )
    assert activate.status_code == 200, activate.text

    response = requests.post(
        f"{BASE_URL}/api/surveys/{survey_id}/responses",
        json={"personId": person_id, "finished": True, "data": {question_id: "linked"}},
        headers=hdrs,
        timeout=30,
    )
    assert response.status_code == 201, response.text
    response_id = response.json()["id"]

    deleted = requests.delete(
        f"{BASE_URL}/api/people/{person_id}",
        headers=hdrs,
        timeout=30,
    )
    assert deleted.status_code == 200, deleted.text

    survey_after_delete = requests.get(
        f"{BASE_URL}/api/surveys/{survey_id}",
        headers=hdrs,
        timeout=30,
    )
    assert survey_after_delete.status_code == 200, survey_after_delete.text

    listed = requests.get(
        f"{BASE_URL}/api/surveys/{survey_id}/responses",
        headers=hdrs,
        timeout=30,
    )
    assert listed.status_code == 200, listed.text
    assert response_id not in {item["id"] for item in listed.json()}
    assert person_id not in {item.get("personId") for item in listed.json()}

    fetched = requests.get(
        f"{BASE_URL}/api/surveys/{survey_id}/responses/{response_id}",
        headers=hdrs,
        timeout=30,
    )
    assert fetched.status_code == 404, fetched.text
