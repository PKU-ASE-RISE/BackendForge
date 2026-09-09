import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers_for(user_id, space_id):
    return {
        "X-User-Id": user_id,
        "X-Space-Id": space_id,
        "Content-Type": "application/json",
    }


def test_add_recipe_to_shopping_list_rejects_cross_space_recipe():
    user_id = str(uuid.uuid4())
    headers_a = headers_for(user_id, str(uuid.uuid4()))
    headers_b = headers_for(user_id, str(uuid.uuid4()))
    suffix = uuid.uuid4().hex

    food = requests.post(
        f"{BASE_URL}/api/foods",
        headers=headers_b,
        json={"name": f"foreign-food-{suffix}"},
        timeout=30,
    )
    assert food.status_code == 201, food.text
    unit = requests.post(
        f"{BASE_URL}/api/units",
        headers=headers_b,
        json={"name": f"foreign-unit-{suffix}"},
        timeout=30,
    )
    assert unit.status_code == 201, unit.text

    recipe = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=headers_b,
        json={
            "name": f"foreign-recipe-{suffix}",
            "servings": 2,
            "steps": [
                {
                    "order": 1,
                    "instruction": "mix",
                    "ingredients": [
                        {
                            "food_id": food.json()["id"],
                            "unit_id": unit.json()["id"],
                            "amount": 10,
                        }
                    ],
                }
            ],
        },
        timeout=30,
    )
    assert recipe.status_code == 201, recipe.text
    foreign_recipe_id = recipe.json()["id"]

    shopping_list = requests.post(
        f"{BASE_URL}/api/shopping-lists",
        headers=headers_a,
        json={"name": f"local-list-{suffix}"},
        timeout=30,
    )
    assert shopping_list.status_code == 201, shopping_list.text
    shopping_list_id = shopping_list.json()["id"]

    added = requests.post(
        f"{BASE_URL}/api/shopping-lists/{shopping_list_id}/add-recipe",
        headers=headers_a,
        json={"recipe_id": foreign_recipe_id, "servings": 2},
        timeout=30,
    )

    assert added.status_code in (400, 404), added.text

    reloaded = requests.get(
        f"{BASE_URL}/api/shopping-lists/{shopping_list_id}",
        headers=headers_a,
        timeout=30,
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json().get("entries", []) == []
