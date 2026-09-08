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


def put_recipe(headers, recipe, ingredients):
    response = requests.put(
        f"{BASE_URL}/api/recipes/{recipe['slug']}",
        headers=headers,
        json={"id": recipe["id"], "name": recipe["name"], "recipeIngredient": ingredients},
        timeout=30,
    )
    assert response.status_code == 200, response.text


def test_shopping_recipe_add_expands_referenced_recipe_ingredients():
    headers = auth_headers()
    marker = uuid.uuid4().hex
    child_food = create_food(headers, f"child-food-{marker}")

    child_slug = create_recipe(headers, f"child-recipe-{marker}")
    child_recipe = get_recipe(headers, child_slug)
    put_recipe(
        headers,
        child_recipe,
        [
            {
                "quantity": 4,
                "food": {"id": child_food["id"], "name": child_food["name"]},
                "note": "",
                "display": child_food["name"],
                "referenceId": uuid.uuid4().hex,
            }
        ],
    )
    child_recipe = get_recipe(headers, child_slug)

    parent_slug = create_recipe(headers, f"parent-recipe-{marker}")
    parent_recipe = get_recipe(headers, parent_slug)
    put_recipe(
        headers,
        parent_recipe,
        [
            {
                "quantity": 1,
                "referencedRecipe": child_recipe,
                "note": "nested recipe",
                "display": child_recipe["name"],
                "referenceId": uuid.uuid4().hex,
            }
        ],
    )
    parent_recipe = get_recipe(headers, parent_slug)

    shopping_list = requests.post(
        f"{BASE_URL}/api/households/shopping/lists",
        headers=headers,
        json={"name": f"nested-recipe-list-{marker}"},
        timeout=30,
    )
    assert shopping_list.status_code == 201, shopping_list.text
    shopping_list_id = shopping_list.json()["id"]

    add_response = requests.post(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}/recipe/{parent_recipe['id']}",
        headers=headers,
        json={"recipeId": parent_recipe["id"], "recipeIncrementQuantity": 1},
        timeout=30,
    )
    assert add_response.status_code == 200, add_response.text

    detail = requests.get(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list_id}",
        headers=headers,
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    food_ids = {item.get("foodId") for item in detail.json().get("listItems", [])}
    assert child_food["id"] in food_ids, (
        "Adding a parent recipe must recursively add ingredient foods from its referenced recipe."
    )
