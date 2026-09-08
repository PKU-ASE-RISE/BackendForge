import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers(user_id, household_id):
    return {
        "X-User-Id": user_id,
        "X-Household-Id": household_id,
        "Content-Type": "application/json",
    }


def get(path, headers_, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers_, params=params, timeout=30)


def post(path, headers_, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers_, json=payload, timeout=30)


def test_recipe_create_cannot_attach_foreign_tag():
    unique = uuid.uuid4().hex
    household_a = str(uuid.uuid4())
    household_b = str(uuid.uuid4())
    h_a = headers(str(uuid.uuid4()), household_a)
    h_b = headers(str(uuid.uuid4()), household_b)

    assert get("/api/households", h_a).status_code == 200
    assert get("/api/households", h_b).status_code == 200

    foreign_tag_resp = post("/api/tags", h_b, {"name": f"foreign-tag-{unique}"})
    assert foreign_tag_resp.status_code == 201
    foreign_tag = foreign_tag_resp.json()

    invisible_tags = get("/api/tags", h_a)
    assert invisible_tags.status_code == 200
    assert foreign_tag["id"] not in {tag["id"] for tag in invisible_tags.json()}

    recipe_resp = post(
        "/api/recipes",
        h_a,
        {
            "name": f"recipe-{unique}",
            "tags": [foreign_tag["id"]],
            "items": [{"name": f"ingredient-{unique}", "amount": 1, "unit": "unit"}],
        },
    )

    assert recipe_resp.status_code in (201, 400, 404)
    if recipe_resp.status_code != 201:
        return

    recipe = recipe_resp.json()
    assert recipe["householdId"] == household_a
    assert foreign_tag["id"] not in {tag["id"] for tag in recipe.get("tags", [])}
    assert all(tag.get("householdId") == household_a for tag in recipe.get("tags", []))

    reloaded_resp = get(f"/api/recipes/{recipe['id']}", h_a)
    assert reloaded_resp.status_code == 200
    reloaded = reloaded_resp.json()
    assert foreign_tag["id"] not in {tag["id"] for tag in reloaded.get("tags", [])}
    assert all(tag.get("householdId") == household_a for tag in reloaded.get("tags", []))
