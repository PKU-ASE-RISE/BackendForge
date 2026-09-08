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
    return requests.post(f"{BASE_URL}{path}", headers=h, json=payload, timeout=30)


def test_no_amount_ingredient_amount_is_zero():
    h = make_headers()
    food = post("/api/foods", h, {"name": f"salt-{uuid.uuid4().hex}"}).json()
    unit = post("/api/units", h, {"name": f"pinch-{uuid.uuid4().hex}"}).json()

    created = post(
        "/api/recipes",
        h,
        {
            "name": f"no-amount-{uuid.uuid4().hex}",
            "steps": [
                {
                    "order": 1,
                    "instruction": "Season.",
                    "ingredients": [
                        {
                            "food_id": food["id"],
                            "unit_id": unit["id"],
                            "amount": 7,
                            "no_amount": True,
                            "order": 1,
                        }
                    ],
                }
            ],
        },
    )

    if created.status_code == 400:
        return
    assert created.status_code == 201, created.text

    recipe_id = created.json()["id"]
    loaded = requests.get(f"{BASE_URL}/api/recipes/{recipe_id}", headers=h, timeout=30)
    assert loaded.status_code == 200, loaded.text
    ingredient = loaded.json()["steps"][0]["ingredients"][0]
    assert ingredient["no_amount"] is True
    assert ingredient["amount"] == 0
