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


def post_json(headers, path, body, expected):
    response = requests.post(f"{BASE_URL}{path}", headers=headers, json=body, timeout=30)
    assert response.status_code == expected, response.text
    return response.json()


def test_shopping_item_update_merges_matching_food_unit():
    headers = auth_headers()
    marker = uuid.uuid4().hex
    food_a = post_json(headers, "/api/foods", {"name": f"merge-food-a-{marker}"}, 201)
    food_b = post_json(headers, "/api/foods", {"name": f"merge-food-b-{marker}"}, 201)
    unit = post_json(headers, "/api/units", {"name": f"merge-unit-{marker}"}, 201)
    shopping_list = post_json(
        headers,
        "/api/households/shopping/lists",
        {"name": f"merge-update-list-{marker}"},
        201,
    )

    first_collection = post_json(
        headers,
        "/api/households/shopping/items",
        {
            "shoppingListId": shopping_list["id"],
            "foodId": food_a["id"],
            "unitId": unit["id"],
            "quantity": 2,
            "checked": False,
        },
        201,
    )
    second_collection = post_json(
        headers,
        "/api/households/shopping/items",
        {
            "shoppingListId": shopping_list["id"],
            "foodId": food_b["id"],
            "unitId": unit["id"],
            "quantity": 3,
            "checked": False,
        },
        201,
    )
    assert first_collection.get("createdItems")
    second_item = second_collection["createdItems"][0]

    update_response = requests.put(
        f"{BASE_URL}/api/households/shopping/items/{second_item['id']}",
        headers=headers,
        json={
            "shoppingListId": shopping_list["id"],
            "foodId": food_a["id"],
            "unitId": unit["id"],
            "quantity": 3,
            "checked": False,
        },
        timeout=30,
    )
    assert update_response.status_code == 200, update_response.text

    detail = requests.get(
        f"{BASE_URL}/api/households/shopping/lists/{shopping_list['id']}",
        headers=headers,
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    matching = [
        item
        for item in detail.json().get("listItems", [])
        if item.get("foodId") == food_a["id"]
        and item.get("unitId") == unit["id"]
        and item.get("checked") is False
    ]

    assert len(matching) == 1, "Updating to an existing food+unit should merge, not duplicate."
    assert matching[0].get("quantity") == 5
