import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth(group_id, household_id):
    return {
        "X-Group-Id": group_id,
        "X-Household-Id": household_id,
        "X-User-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def create_recipe(headers, name):
    response = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=headers,
        json={"name": name},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_recipe_households_filter_limits_results():
    marker = uuid.uuid4().hex
    group_id = str(uuid.uuid4())
    household_a = str(uuid.uuid4())
    household_b = str(uuid.uuid4())
    headers_a = auth(group_id, household_a)
    headers_b = auth(group_id, household_b)
    name_a = f"household-a-{marker}"
    name_b = f"household-b-{marker}"

    create_recipe(headers_a, name_a)
    create_recipe(headers_b, name_b)

    response = requests.get(
        f"{BASE_URL}/api/recipes",
        headers=headers_a,
        params=[("households", household_a), ("perPage", "50")],
        timeout=30,
    )
    assert response.status_code == 200, response.text
    names = {item.get("name") for item in response.json().get("items", [])}

    assert name_a in names
    assert name_b not in names, "households filter must exclude recipes from other households."
