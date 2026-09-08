import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def make_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Space-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def post(path, h, payload):
    response = requests.post(f"{BASE_URL}{path}", headers=h, json=payload, timeout=30)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_no_amount_recipe_entry_merges_with_existing_unchecked():
    h = make_headers()
    food = post("/api/foods", h, {"name": f"salt-merge-{uuid.uuid4().hex}"})
    unit = post("/api/units", h, {"name": f"pinch-merge-{uuid.uuid4().hex}"})
    shopping_list = post("/api/shopping-lists", h, {"name": f"list-{uuid.uuid4().hex}"})

    post(
        f"/api/shopping-lists/{shopping_list['id']}/entries",
        h,
        {"food_id": food["id"], "unit_id": unit["id"], "amount": 5, "checked": False},
    )
    recipe = post(
        "/api/recipes",
        h,
        {
            "name": f"no-amount-merge-{uuid.uuid4().hex}",
            "servings": 1,
            "steps": [
                {
                    "order": 1,
                    "instruction": "Season to taste.",
                    "ingredients": [
                        {
                            "food_id": food["id"],
                            "unit_id": unit["id"],
                            "amount": 0,
                            "no_amount": True,
                        }
                    ],
                }
            ],
        },
    )

    updated = requests.post(
        f"{BASE_URL}/api/shopping-lists/{shopping_list['id']}/add-recipe",
        headers=h,
        json={"recipe_id": recipe["id"], "servings": 1},
        timeout=30,
    )
    assert updated.status_code == 200, updated.text

    matching = [
        entry
        for entry in updated.json()["entries"]
        if entry["food_id"] == food["id"] and entry["unit_id"] == unit["id"]
    ]
    assert len(matching) == 1
    assert matching[0]["checked"] is False
    assert matching[0]["amount"] == 5
