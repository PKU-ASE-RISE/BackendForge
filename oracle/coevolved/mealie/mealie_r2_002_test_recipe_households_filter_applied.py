import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def auth_headers(group_id, household_id, user_id=None):
    return {
        "X-Group-Id": group_id,
        "X-Household-Id": household_id,
        "X-User-Id": user_id or str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def create_recipe(headers, name):
    created = requests.post(f"{BASE_URL}/api/recipes", json={"name": name}, headers=headers, timeout=30)
    assert created.status_code == 201, created.text
    slug_value = created.json()
    slug = slug_value if isinstance(slug_value, str) else slug_value.get("slug")
    detail = requests.get(f"{BASE_URL}/api/recipes/{slug}", headers=headers, timeout=30)
    assert detail.status_code == 200, detail.text
    return detail.json()


def test_recipe_households_filter_applied():
    token = uuid.uuid4().hex
    group_id = str(uuid.uuid4())
    household_a = str(uuid.uuid4())
    household_b = str(uuid.uuid4())
    headers_a = auth_headers(group_id, household_a)
    headers_b = auth_headers(group_id, household_b)

    recipe_a = create_recipe(headers_a, f"household-filter-{token}-a")
    recipe_b = create_recipe(headers_b, f"household-filter-{token}-b")

    response = requests.get(
        f"{BASE_URL}/api/recipes",
        params=[
            ("search", f"household-filter-{token}"),
            ("households", household_a),
            ("perPage", "50"),
        ],
        headers=headers_a,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    items = response.json().get("items", [])
    slugs = {item.get("slug") for item in items}

    assert recipe_a["slug"] in slugs
    assert recipe_b["slug"] not in slugs
    assert all(item.get("householdId") == household_a for item in items if item.get("slug") in {recipe_a["slug"], recipe_b["slug"]})
