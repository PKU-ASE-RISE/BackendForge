import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth(group_id, household_id):
    return {
        "X-Group-Id": group_id,
        "X-Household-Id": household_id,
        "X-User-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def create_shopping_list(headers, name):
    response = requests.post(
        f"{BASE_URL}/api/households/shopping/lists",
        headers=headers,
        json={"name": name},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_item(headers, shopping_list_id, note):
    response = requests.post(
        f"{BASE_URL}/api/households/shopping/items",
        headers=headers,
        json={"shoppingListId": shopping_list_id, "quantity": 1, "note": note},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    created = response.json().get("createdItems", [])
    assert created, response.text
    return created[0]


def test_shopping_item_get_is_household_scoped():
    marker = uuid.uuid4().hex
    group_id = str(uuid.uuid4())
    headers_a = auth(group_id, str(uuid.uuid4()))
    headers_b = auth(group_id, str(uuid.uuid4()))
    shopping_list_b = create_shopping_list(headers_b, f"private-list-{marker}")
    item_b = create_item(headers_b, shopping_list_b["id"], f"private-note-{marker}")

    response = requests.get(
        f"{BASE_URL}/api/households/shopping/items/{item_b['id']}",
        headers=headers_a,
        timeout=30,
    )
    assert response.status_code != 200, (
        "Shopping item detail endpoint must not reveal another household's item."
    )
