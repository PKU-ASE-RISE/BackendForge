import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Space-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_create_recipe_rejects_invalid_step_type():
    h = headers()
    recipe_name = f"bad-step-type-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=h,
        json={
            "name": recipe_name,
            "steps": [
                {
                    "order": 1,
                    "instruction": "This uses an invalid OpenAPI enum value.",
                    "step_type": "video",
                }
            ],
        },
        timeout=30,
    )

    assert response.status_code == 400, response.text

    listed = requests.get(
        f"{BASE_URL}/api/recipes",
        headers=h,
        params={"search": recipe_name},
        timeout=30,
    )
    assert listed.status_code == 200, listed.text
    assert all(item["name"] != recipe_name for item in listed.json()["results"])
