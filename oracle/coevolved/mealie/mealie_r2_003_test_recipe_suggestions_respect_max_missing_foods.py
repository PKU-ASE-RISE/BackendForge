import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers(group_id, household_id, user_id=None):
    return {
        "X-Group-Id": group_id,
        "X-Household-Id": household_id,
        "X-User-Id": user_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def create_food(headers, name):
    response = requests.post(f"{BASE_URL}/api/foods", json={"name": name}, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def create_recipe(headers, name):
    created = requests.post(f"{BASE_URL}/api/recipes", json={"name": name}, headers=headers, timeout=30)
    assert created.status_code == 201, created.text
    slug_value = created.json()
    slug = slug_value if isinstance(slug_value, str) else slug_value.get("slug")
    detail = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert detail.status_code == 200, detail.text
    return detail.json()


def update_recipe(headers, slug, recipe):
    response = requests.put(f"{BASE_URL}/api/recipes/{slug}", json=recipe, headers=headers, timeout=30)
    assert response.status_code == 200, response.text


def test_recipe_suggestions_respect_max_missing_foods():
    token = uuid.uuid4().hex
    headers = auth_headers(str(uuid.uuid4()), str(uuid.uuid4()))
    required_food = create_food(headers, f"required-suggestion-food-{token}")
    available_food = create_food(headers, f"available-suggestion-food-{token}")
    recipe = create_recipe(headers, f"suggestion-missing-food-{token}")
    recipe["recipeIngredient"] = [
        {
            "food": {"id": required_food["id"], "name": required_food["name"]},
            "quantity": 1,
            "note": "must be on hand",
        }
    ]
    update_recipe(headers, recipe["slug"], recipe)

    response = requests.get(
        f"{BASE_URL}/api/recipes/suggestions",
        params=[
            ("foods", available_food["id"]),
            ("limit", "20"),
            ("maxMissingFoods", "0"),
            ("maxMissingTools", "0"),
        ],
        headers=headers,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    suggested_slugs = {
        item.get("recipe", {}).get("slug")
        for item in response.json().get("items", [])
        if isinstance(item, dict)
    }

    assert recipe["slug"] not in suggested_slugs
