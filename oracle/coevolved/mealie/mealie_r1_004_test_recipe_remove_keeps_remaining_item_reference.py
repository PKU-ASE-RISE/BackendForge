import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers():
    return {
        "X-Group-Id": str(uuid.uuid4()),
        "X-Household-Id": str(uuid.uuid4()),
        "X-User-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def create_recipe_with_single_food(headers, marker):
    food = requests.post(
        f"{BASE_URL}/api/foods",
        headers=headers,
        json={"name": f"partial-remove-food-{marker}"},
        timeout=30,
    )
    assert food.status_code == 201, food.text
    food_data = food.json()

    recipe_create = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=headers,
        json={"name": f"partial-remove-recipe-{marker}"},
        timeout=30,
    )
    assert recipe_create.status_code == 201, recipe_create.text
    slug = recipe_create.json()
    recipe_get = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert recipe_get.status_code == 200, recipe_get.text
    recipe = recipe_get.json()

    recipe_update = requests.put(
        f"{BASE_URL}/api/recipes/{recipe['slug']}",
        headers=headers,
        json={
            "id": recipe["id"],
            "name": recipe["name"],
            "recipeIngredient": [
                {
                    "quantity": 1,
                    "food": {"id": food_data["id"], "name": food_data["name"]},
                    "display": food_data["name"],
                    "referenceId": uuid.uuid4().hex,
                }
            ],
        },
        timeout=30,
    )
    assert recipe_update.status_code == 200, recipe_update.text
    refreshed = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert refreshed.status_code == 200, refreshed.text
    return refreshed.json(), food_data


def test_recipe_remove_keeps_remaining_item_reference():
    headers = auth_headers()
    marker = uuid.uuid4().hex
    recipe, food = create_recipe_with_single_food(headers, marker)

    shopping_list = requests.post(
        f"{BASE_URL}/api/households/shopping/lists",
        headers=headers,
        json={"name": f"partial-remove-list-{marker}"},
        timeout=30,
    )
    assert shopping_list.status_code == 201, shopping_list.text
    shopping_list_id = shopping_list.json()["id"]

    for _ in range(2):
        add_response = requests.post(
            f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}/recipe/{recipe['id']}",
            headers=headers,
            json={"recipeId": recipe["id"], "recipeIncrementQuantity": 1},
            timeout=30,
        )
        assert add_response.status_code == 200, add_response.text

    remove_response = requests.post(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}/recipe/{recipe['id']}/delete",
        headers=headers,
        json={"recipeDecrementQuantity": 1},
        timeout=30,
    )
    assert remove_response.status_code == 200, remove_response.text
    detail = requests.get(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}",
        headers=headers,
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()

    list_refs = [ref for ref in data.get("recipeReferences", []) if ref.get("recipeId") == recipe["id"]]
    assert list_refs and list_refs[0].get("recipeQuantity") == 1

    item = next(item for item in data.get("listItems", []) if item.get("foodId") == food["id"])
    assert item.get("quantity") == 1
    remaining_item_ref_qty = sum(
        ref.get("recipeQuantity") or 0
        for ref in item.get("recipeReferences", [])
        if ref.get("recipeId") == recipe["id"]
    )
    assert remaining_item_ref_qty == 1, (
        "The remaining item quantity from the recipe must retain one item-level recipe reference."
    )
