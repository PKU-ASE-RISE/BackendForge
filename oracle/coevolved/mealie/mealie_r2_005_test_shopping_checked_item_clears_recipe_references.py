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


def update_recipe(headers, recipe):
    response = requests.put(f"{BASE_URL}/api/recipes/{recipe['slug']}", json=recipe, headers=headers, timeout=30)
    assert response.status_code == 200, response.text


def create_list(headers, name):
    response = requests.post(f"{BASE_URL}/api/households/shopping/lists", json={"name": name}, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def get_list(headers, list_id):
    response = requests.get(f"{BASE_URL}/api/households/shopping/lists/{list_id}", headers=headers, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


def test_shopping_checked_item_clears_recipe_references():
    token = uuid.uuid4().hex
    headers = auth_headers()
    food = create_food(headers, f"checked-ref-food-{token}")
    recipe = create_recipe(headers, f"checked-ref-recipe-{token}")
    recipe["recipeIngredient"] = [{"food": {"id": food["id"], "name": food["name"]}, "quantity": 1}]
    update_recipe(headers, recipe)
    shopping_list = create_list(headers, f"checked-ref-list-{token}")

    add_response = requests.post(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list['id']}/recipe/{recipe['id']}",
        json={"recipeId": recipe["id"], "recipeIncrementQuantity": 1},
        headers=headers,
        timeout=30,
    )
    assert add_response.status_code == 200, add_response.text
    detail = get_list(headers, shopping_list["id"])
    item = next(item for item in detail.get("listItems", []) if item.get("foodId") == food["id"])
    assert item.get("recipeReferences")

    checked_response = requests.put(
        f"{BASE_URL}/api/households/shopping/items/{item['id']}",
        json={**item, "shoppingListId": shopping_list["id"], "checked": True},
        headers=headers,
        timeout=30,
    )
    assert checked_response.status_code == 200, checked_response.text

    updated_detail = get_list(headers, shopping_list["id"])
    checked_item = next(candidate for candidate in updated_detail.get("listItems", []) if candidate.get("id") == item["id"])
    assert checked_item.get("checked") is True
    assert checked_item.get("recipeReferences") == []
