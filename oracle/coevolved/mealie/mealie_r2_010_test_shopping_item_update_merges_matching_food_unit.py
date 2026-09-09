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


def create_unit(headers, name):
    response = requests.post(f"{BASE_URL}/api/units", json={"name": name}, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def create_list(headers, name):
    response = requests.post(f"{BASE_URL}/api/households/shopping/lists", json={"name": name}, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def create_item(headers, list_id, food_id, unit_id, quantity):
    response = requests.post(
        f"{BASE_URL}/api/households/shopping/items",
        json={
            "shoppingListId": list_id,
            "foodId": food_id,
            "unitId": unit_id,
            "quantity": quantity,
            "checked": False,
        },
        headers=headers,
        timeout=30,
    )
    assert response.status_code == 201, response.text
    created = response.json().get("createdItems", [])
    assert created, response.text
    return created[0]


def get_list(headers, list_id):
    response = requests.get(f"{BASE_URL}/api/households/shopping/lists/{list_id}", headers=headers, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


def test_shopping_item_update_merges_matching_food_unit():
    token = uuid.uuid4().hex
    headers = auth_headers()
    food_target = create_food(headers, f"merge-update-target-food-{token}")
    food_other = create_food(headers, f"merge-update-other-food-{token}")
    unit = create_unit(headers, f"merge-update-unit-{token}")
    shopping_list = create_list(headers, f"merge-update-list-{token}")
    create_item(headers, shopping_list["id"], food_target["id"], unit["id"], 2)
    item_to_update = create_item(headers, shopping_list["id"], food_other["id"], unit["id"], 3)

    update_response = requests.put(
        f"{BASE_URL}/api/households/shopping/items/{item_to_update['id']}",
        json={
            # Send writable IDs only; nested food/unit from GET may conflict.
            "shoppingListId": shopping_list["id"],
            "foodId": food_target["id"],
            "unitId": unit["id"],
            "quantity": 3,
            "checked": False,
        },
        headers=headers,
        timeout=30,
    )
    assert update_response.status_code == 200, update_response.text

    detail = get_list(headers, shopping_list["id"])
    matching = [
        item
        for item in detail.get("listItems", [])
        if item.get("foodId") == food_target["id"] and item.get("unitId") == unit["id"] and not item.get("checked")
    ]
    assert len(matching) == 1
    assert matching[0].get("quantity") == 5
