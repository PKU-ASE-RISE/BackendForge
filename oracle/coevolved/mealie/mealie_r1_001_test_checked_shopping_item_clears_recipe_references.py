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


def create_recipe_with_food(headers, marker):
    food = requests.post(
        f"{BASE_URL}/api/foods",
        headers=headers,
        json={"name": f"checked-ref-food-{marker}"},
        timeout=30,
    )
    assert food.status_code == 201, food.text
    food_data = food.json()

    created = requests.post(
        f"{BASE_URL}/api/recipes",
        headers=headers,
        json={"name": f"checked-ref-recipe-{marker}"},
        timeout=30,
    )
    assert created.status_code == 201, created.text
    slug = created.json()
    detail = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert detail.status_code == 200, detail.text
    recipe = detail.json()

    update = requests.put(
        f"{BASE_URL}/api/recipes/{recipe['slug']}",
        headers=headers,
        json={
            "id": recipe["id"],
            "name": recipe["name"],
            "recipeIngredient": [
                {
                    "quantity": 2,
                    "food": {"id": food_data["id"], "name": food_data["name"]},
                    "display": food_data["name"],
                    "referenceId": uuid.uuid4().hex,
                }
            ],
        },
        timeout=30,
    )
    assert update.status_code == 200, update.text
    refreshed = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert refreshed.status_code == 200, refreshed.text
    return refreshed.json()


def test_checked_shopping_item_clears_recipe_references():
    headers = auth_headers()
    marker = uuid.uuid4().hex
    recipe = create_recipe_with_food(headers, marker)

    shopping_list = requests.post(
        f"{BASE_URL}/api/households/shopping/lists",
        headers=headers,
        json={"name": f"checked-ref-list-{marker}"},
        timeout=30,
    )
    assert shopping_list.status_code == 201, shopping_list.text
    shopping_list_id = shopping_list.json()["id"]

    add_recipe = requests.post(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}/recipe/{recipe['id']}",
        headers=headers,
        json={"recipeId": recipe["id"], "recipeIncrementQuantity": 1},
        timeout=30,
    )
    assert add_recipe.status_code == 200, add_recipe.text
    item = next(
        item for item in add_recipe.json().get("listItems", []) if item.get("recipeReferences")
    )

    update = requests.put(
        f"{BASE_URL}/api/households/shopping/items/{item['id']}",
        headers=headers,
        json={
            "shoppingListId": shopping_list_id,
            "quantity": item["quantity"],
            "foodId": item.get("foodId"),
            "unitId": item.get("unitId"),
            "note": item.get("note"),
            "checked": True,
        },
        timeout=30,
    )
    assert update.status_code == 200, update.text

    detail = requests.get(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}",
        headers=headers,
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    checked_item = next(
        reloaded for reloaded in detail.json().get("listItems", []) if reloaded["id"] == item["id"]
    )

    assert checked_item["checked"] is True
    assert checked_item.get("recipeReferences") == [], (
        "Checked shopping items must not retain recipeReferences."
    )
