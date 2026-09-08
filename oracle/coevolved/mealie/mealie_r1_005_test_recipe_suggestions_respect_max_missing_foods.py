import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    suffix = uuid.uuid4().hex
    return {
        "X-Group-Id": str(uuid.uuid4()),
        "X-Household-Id": str(uuid.uuid4()),
        "X-User-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "X-Test-Suffix": suffix,
    }


def create_food(headers, name):
    response = requests.post(
        f"{BASE_URL}/api/foods",
        headers=headers,
        json={"name": name},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_recipe(headers, name):
    response = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=headers,
        json={"name": name},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    return response.json()


def get_recipe(headers, slug):
    response = requests.get(
        f"{BASE_URL}/api/recipes/{slug}",
        headers=headers,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()


def set_recipe_food(headers, recipe, food):
    response = requests.put(
        f"{BASE_URL}/api/recipes/{recipe['slug']}",
        headers=headers,
        json={
            "id": recipe["id"],
            "name": recipe["name"],
            "recipeIngredient": [
                {
                    "quantity": 1,
                    "food": {"id": food["id"], "name": food["name"]},
                    "note": "",
                    "display": food["name"],
                    "referenceId": uuid.uuid4().hex,
                }
            ],
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text


def test_recipe_suggestions_respect_max_missing_foods():
    headers = auth_headers()
    marker = uuid.uuid4().hex
    available_food = create_food(headers, f"available-{marker}")
    unavailable_food = create_food(headers, f"unavailable-{marker}")

    available_slug = create_recipe(headers, f"suggest-available-{marker}")
    missing_slug = create_recipe(headers, f"suggest-missing-{marker}")
    available_recipe = get_recipe(headers, available_slug)
    missing_recipe = get_recipe(headers, missing_slug)

    set_recipe_food(headers, available_recipe, available_food)
    set_recipe_food(headers, missing_recipe, unavailable_food)

    response = requests.get(
        f"{BASE_URL}/api/recipes/suggestions",
        headers=headers,
        params=[
            ("foods", available_food["id"]),
            ("maxMissingFoods", "0"),
            ("maxMissingTools", "0"),
            ("limit", "25"),
        ],
        timeout=30,
    )
    assert response.status_code == 200, response.text
    items = response.json().get("items", [])
    recipe_ids = {item.get("recipe", {}).get("id") for item in items}

    assert available_recipe["id"] in recipe_ids
    assert missing_recipe["id"] not in recipe_ids, (
        "Recipe suggestions must not include a recipe whose ingredient food is "
        "missing when maxMissingFoods=0."
    )
