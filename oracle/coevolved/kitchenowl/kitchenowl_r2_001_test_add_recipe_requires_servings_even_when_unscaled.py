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


def test_add_recipe_requires_servings_even_when_unscaled():
    household_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    h = headers(user_id, household_id)
    ingredient = f"required-servings-{uuid.uuid4().hex}"

    membership_response = requests.get(
        f"{BASE_URL}/api/households", headers=h, timeout=30
    )
    recipe_response = requests.post(
        f"{BASE_URL}/api/recipes",
        json={
            "name": f"unscaled-recipe-{uuid.uuid4().hex}",
            "servings": None,
            "items": [{"name": ingredient, "amount": 2, "unit": "kg"}],
        },
        headers=h,
        timeout=30,
    )
    assert recipe_response.status_code == 201
    recipe_id = recipe_response.json()["id"]

    list_response = requests.post(
        f"{BASE_URL}/api/shopping-lists",
        json={"name": f"servings-list-{uuid.uuid4().hex}"},
        headers=h,
        timeout=30,
    )
    assert list_response.status_code == 201
    list_id = list_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/api/shopping-lists/{list_id}/add-recipe",
        json={"recipeId": recipe_id},
        headers=h,
        timeout=30,
    )
    list_after_response = requests.get(
        f"{BASE_URL}/api/shopping-lists/{list_id}", headers=h, timeout=30
    )
    list_after = list_after_response.json()
    item_names = {item["name"] for item in list_after["items"]}

    assert response.status_code >= 400
    assert ingredient not in item_names
