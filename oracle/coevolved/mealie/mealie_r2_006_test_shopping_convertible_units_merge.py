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


def create_unit(headers, payload):
    response = requests.post(f"{BASE_URL}/api/units", json=payload, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def create_list(headers, name):
    response = requests.post(f"{BASE_URL}/api/households/shopping/lists", json={"name": name}, headers=headers, timeout=30)
    assert response.status_code == 201, response.text
    return response.json()


def add_item(headers, list_id, food_id, unit_id, quantity):
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
    return response.json()


def test_shopping_convertible_units_merge():
    token = uuid.uuid4().hex
    headers = auth_headers()
    food = create_food(headers, f"convertible-food-{token}")
    cup = create_unit(
        headers,
        {
            "name": f"cup-{token}",
            "abbreviation": "cup",
            "standardQuantity": 240,
            "standardUnit": "ml",
        },
    )
    milliliter = create_unit(
        headers,
        {
            "name": f"milliliter-{token}",
            "abbreviation": "ml",
            "standardQuantity": 1,
            "standardUnit": "ml",
        },
    )
    shopping_list = create_list(headers, f"convertible-list-{token}")

    add_item(headers, shopping_list["id"], food["id"], cup["id"], 1)
    add_item(headers, shopping_list["id"], food["id"], milliliter["id"], 120)

    detail = requests.get(f"{BASE_URL}/api/households/shopping/lists/{shopping_list['id']}", headers=headers, timeout=30)
    assert detail.status_code == 200, detail.text
    food_items = [
        item
        for item in detail.json().get("listItems", [])
        if item.get("foodId") == food["id"] and not item.get("checked")
    ]
    assert len(food_items) == 1
