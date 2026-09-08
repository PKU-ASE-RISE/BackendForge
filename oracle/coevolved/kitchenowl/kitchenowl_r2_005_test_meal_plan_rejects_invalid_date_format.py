import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers(user_id, household_id):
    return {
        "X-User-Id": user_id,
        "X-Household-Id": household_id,
        "Content-Type": "application/json",
    }


def test_meal_plan_rejects_invalid_date_format():
    household_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    h = headers(user_id, household_id)
    recipe_name = f"meal-date-recipe-{uuid.uuid4().hex}"

    membership_response = requests.get(
        f"{BASE_URL}/api/households", headers=h, timeout=30
    )
    recipe_response = requests.post(
        f"{BASE_URL}/api/recipes",
        json={"name": recipe_name, "items": []},
        headers=h,
        timeout=30,
    )
    assert recipe_response.status_code == 201
    recipe_id = recipe_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/api/meal-plan",
        json={"date": "not-a-date", "mealType": "dinner", "recipeId": recipe_id},
        headers=h,
        timeout=30,
    )
    entries_after_response = requests.get(
        f"{BASE_URL}/api/meal-plan", headers=h, timeout=30
    )
    entries_after = entries_after_response.json()

    assert response.status_code == 400
    assert all(
        not (entry["recipeId"] == recipe_id and entry["date"] == "not-a-date")
        for entry in entries_after
    )
