"""
BackendForge — Comprehensive Correctness Tests for Tandoor Recipes Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex

# Auth headers — trusted directly, data scoped to space
USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user"))
SPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:space"))
OTHER_SPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:other-space"))

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Space-Id": SPACE_ID,
    "Content-Type": "application/json",
}

OTHER_SPACE_HEADERS = {
    "X-User-Id": USER_ID,
    "X-Space-Id": OTHER_SPACE_ID,
    "Content-Type": "application/json",
}

UNIQUE = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_space(request):
    """Give every item fresh space namespaces so state cannot leak across tests."""
    global USER_ID, SPACE_ID, OTHER_SPACE_ID, HEADERS, OTHER_SPACE_HEADERS, UNIQUE

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user"))
    SPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:space"))
    OTHER_SPACE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:other-space"))
    HEADERS = {
        "X-User-Id": USER_ID,
        "X-Space-Id": SPACE_ID,
        "Content-Type": "application/json",
    }
    OTHER_SPACE_HEADERS = {
        "X-User-Id": USER_ID,
        "X-Space-Id": OTHER_SPACE_ID,
        "Content-Type": "application/json",
    }
    UNIQUE = item_id[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_user_id_header(self):
        """Missing X-User-Id should return 401."""
        resp = requests.get(f"{BASE_URL}/api/keywords",
                            headers={"X-Space-Id": SPACE_ID, "Content-Type": "application/json"}, timeout=30)
        assert resp.status_code == 401

    def test_missing_space_id_header(self):
        """Missing X-Space-Id should return 401."""
        resp = requests.get(f"{BASE_URL}/api/keywords",
                            headers={"X-User-Id": USER_ID, "Content-Type": "application/json"}, timeout=30)
        assert resp.status_code == 401

    def test_no_headers_at_all(self):
        """No auth headers should return 401."""
        resp = requests.get(f"{BASE_URL}/api/keywords",
                            headers={"Content-Type": "application/json"}, timeout=30)
        assert resp.status_code == 401

    def test_valid_headers_work(self):
        """Valid headers should return 200."""
        resp = api_get("/api/keywords")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Units CRUD
# ════════════════════════════════════════════════════════════════════


class TestUnitsCRUD:

    def test_create_unit(self):
        resp = api_post("/api/units", {"name": f"gram-{UNIQUE}", "plural_name": "grams", "description": "metric weight"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"gram-{UNIQUE}"
        assert data["plural_name"] == "grams"
        assert data["description"] == "metric weight"
        assert "id" in data

    def test_list_units(self):
        api_post("/api/units", {"name": f"list-unit-{UNIQUE}"})
        resp = api_get("/api/units")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_unit(self):
        # Create, then get
        create_resp = api_post("/api/units", {"name": f"cup-{UNIQUE}"})
        unit_id = create_resp.json()["id"]
        resp = api_get(f"/api/units/{unit_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"cup-{UNIQUE}"

    def test_update_unit(self):
        create_resp = api_post("/api/units", {"name": f"tbsp-{UNIQUE}"})
        unit_id = create_resp.json()["id"]
        resp = api_put(f"/api/units/{unit_id}", {"name": f"tablespoon-{UNIQUE}", "plural_name": "tablespoons"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"tablespoon-{UNIQUE}"

    def test_delete_unit(self):
        create_resp = api_post("/api/units", {"name": f"tsp-del-{UNIQUE}"})
        unit_id = create_resp.json()["id"]
        resp = api_delete(f"/api/units/{unit_id}")
        assert resp.status_code == 204
        # Verify gone
        resp = api_get(f"/api/units/{unit_id}")
        assert resp.status_code == 404

    def test_duplicate_unit_name(self):
        name = f"dup-unit-{UNIQUE}"
        api_post("/api/units", {"name": name})
        resp = api_post("/api/units", {"name": name})
        assert resp.status_code == 400

    def test_search_units(self):
        unique_name = f"milliliter-{uuid.uuid4().hex[:8]}"
        api_post("/api/units", {"name": unique_name})
        resp = api_get("/api/units", params={"search": unique_name})
        assert resp.status_code == 200
        results = resp.json()
        assert any(u["name"] == unique_name for u in results)

    def test_unit_not_found(self):
        resp = api_get("/api/units/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Foods CRUD
# ════════════════════════════════════════════════════════════════════


class TestFoodsCRUD:

    def test_create_food(self):
        resp = api_post("/api/foods", {
            "name": f"flour-{UNIQUE}",
            "calories_per_unit": 3.64,
            "protein_per_unit": 0.10,
            "fat_per_unit": 0.01,
            "carbs_per_unit": 0.76
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"flour-{UNIQUE}"
        assert data["calories_per_unit"] == pytest.approx(3.64)
        assert "id" in data

    def test_list_foods(self):
        resp = api_get("/api/foods")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_food(self):
        create_resp = api_post("/api/foods", {"name": f"sugar-{UNIQUE}"})
        food_id = create_resp.json()["id"]
        resp = api_get(f"/api/foods/{food_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"sugar-{UNIQUE}"

    def test_update_food(self):
        create_resp = api_post("/api/foods", {"name": f"butter-{UNIQUE}"})
        food_id = create_resp.json()["id"]
        resp = api_put(f"/api/foods/{food_id}", {"name": f"butter-updated-{UNIQUE}", "calories_per_unit": 7.17})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"butter-updated-{UNIQUE}"
        assert resp.json()["calories_per_unit"] == pytest.approx(7.17)

    def test_delete_food(self):
        create_resp = api_post("/api/foods", {"name": f"salt-del-{UNIQUE}"})
        food_id = create_resp.json()["id"]
        resp = api_delete(f"/api/foods/{food_id}")
        assert resp.status_code == 204
        resp = api_get(f"/api/foods/{food_id}")
        assert resp.status_code == 404

    def test_duplicate_food_name(self):
        name = f"dup-food-{UNIQUE}"
        api_post("/api/foods", {"name": name})
        resp = api_post("/api/foods", {"name": name})
        assert resp.status_code == 400

    def test_food_with_invalid_recipe_link(self):
        resp = api_post("/api/foods", {"name": f"linked-food-{UNIQUE}", "recipe_id": 99999})
        assert resp.status_code == 400

    def test_search_foods(self):
        unique_name = f"paprika-{uuid.uuid4().hex[:8]}"
        api_post("/api/foods", {"name": unique_name})
        resp = api_get("/api/foods", params={"search": unique_name})
        assert resp.status_code == 200
        results = resp.json()
        assert any(f["name"] == unique_name for f in results)


# ════════════════════════════════════════════════════════════════════
# PART 4: Keywords CRUD and Hierarchy
# ════════════════════════════════════════════════════════════════════


class TestKeywordsCRUD:

    def test_create_keyword(self):
        resp = api_post("/api/keywords", {"name": f"Italian-{UNIQUE}", "description": "Italian cuisine"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Italian-{UNIQUE}"
        assert data["description"] == "Italian cuisine"
        assert "id" in data
        assert data["parent_id"] is None

    def test_create_child_keyword(self):
        parent_resp = api_post("/api/keywords", {"name": f"Asian-{UNIQUE}"})
        parent_id = parent_resp.json()["id"]
        resp = api_post("/api/keywords", {"name": f"Chinese-{UNIQUE}", "parent_id": parent_id})
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == parent_id

    def test_list_keywords(self):
        resp = api_get("/api/keywords")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_root_only_keywords(self):
        parent_resp = api_post("/api/keywords", {"name": f"Root-{uuid.uuid4().hex[:8]}"})
        parent_id = parent_resp.json()["id"]
        api_post("/api/keywords", {"name": f"Child-{uuid.uuid4().hex[:8]}", "parent_id": parent_id})
        resp = api_get("/api/keywords", params={"root_only": "true"})
        assert resp.status_code == 200
        results = resp.json()
        # All returned keywords should have no parent
        for kw in results:
            assert kw["parent_id"] is None

    def test_list_keywords_by_parent(self):
        parent_resp = api_post("/api/keywords", {"name": f"ParentFilter-{uuid.uuid4().hex[:8]}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/keywords", {"name": f"ChildFilter-{uuid.uuid4().hex[:8]}", "parent_id": parent_id})
        child_id = child_resp.json()["id"]
        resp = api_get("/api/keywords", params={"parent_id": parent_id})
        assert resp.status_code == 200
        results = resp.json()
        assert any(k["id"] == child_id for k in results)
        for k in results:
            assert k["parent_id"] == parent_id

    def test_get_keyword(self):
        create_resp = api_post("/api/keywords", {"name": f"GetKw-{UNIQUE}"})
        kw_id = create_resp.json()["id"]
        resp = api_get(f"/api/keywords/{kw_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == kw_id

    def test_update_keyword(self):
        create_resp = api_post("/api/keywords", {"name": f"UpdKw-{UNIQUE}"})
        kw_id = create_resp.json()["id"]
        resp = api_put(f"/api/keywords/{kw_id}", {"name": f"UpdatedKw-{UNIQUE}", "description": "updated"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedKw-{UNIQUE}"
        assert resp.json()["description"] == "updated"

    def test_delete_keyword(self):
        create_resp = api_post("/api/keywords", {"name": f"DelKw-{UNIQUE}"})
        kw_id = create_resp.json()["id"]
        resp = api_delete(f"/api/keywords/{kw_id}")
        assert resp.status_code == 204
        resp = api_get(f"/api/keywords/{kw_id}")
        assert resp.status_code == 404

    def test_delete_keyword_cascades_to_children(self):
        """Deleting a parent keyword also deletes its children."""
        parent_resp = api_post("/api/keywords", {"name": f"CascParent-{uuid.uuid4().hex[:8]}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/keywords", {"name": f"CascChild-{uuid.uuid4().hex[:8]}", "parent_id": parent_id})
        child_id = child_resp.json()["id"]
        grandchild_resp = api_post("/api/keywords", {"name": f"CascGrand-{uuid.uuid4().hex[:8]}", "parent_id": child_id})
        grandchild_id = grandchild_resp.json()["id"]

        # Delete parent
        resp = api_delete(f"/api/keywords/{parent_id}")
        assert resp.status_code == 204

        # Children should also be gone
        assert api_get(f"/api/keywords/{child_id}").status_code == 404
        assert api_get(f"/api/keywords/{grandchild_id}").status_code == 404

    def test_keyword_circular_reference_prevention(self):
        """Cannot set a keyword's parent to itself or its descendant."""
        parent_resp = api_post("/api/keywords", {"name": f"CircP-{uuid.uuid4().hex[:8]}"})
        parent_id = parent_resp.json()["id"]
        child_resp = api_post("/api/keywords", {"name": f"CircC-{uuid.uuid4().hex[:8]}", "parent_id": parent_id})
        child_id = child_resp.json()["id"]

        # Try to make parent's parent be the child → circular
        resp = api_put(f"/api/keywords/{parent_id}", {"name": f"CircP-{uuid.uuid4().hex[:8]}", "parent_id": child_id})
        assert resp.status_code == 400

    def test_keyword_self_reference_prevention(self):
        """Cannot set a keyword's parent to itself."""
        resp = api_post("/api/keywords", {"name": f"SelfRef-{uuid.uuid4().hex[:8]}"})
        kw_id = resp.json()["id"]
        resp = api_put(f"/api/keywords/{kw_id}", {"name": f"SelfRef-{uuid.uuid4().hex[:8]}", "parent_id": kw_id})
        assert resp.status_code == 400

    def test_duplicate_keyword_name_same_parent(self):
        """Siblings cannot have the same name."""
        name = f"SibDup-{uuid.uuid4().hex[:8]}"
        api_post("/api/keywords", {"name": name})
        resp = api_post("/api/keywords", {"name": name})
        assert resp.status_code == 400

    def test_same_name_different_parent_allowed(self):
        """Same name under different parents should be allowed."""
        parent1 = api_post("/api/keywords", {"name": f"P1-{uuid.uuid4().hex[:8]}"}).json()
        parent2 = api_post("/api/keywords", {"name": f"P2-{uuid.uuid4().hex[:8]}"}).json()
        name = f"SharedName-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/api/keywords", {"name": name, "parent_id": parent1["id"]})
        assert resp1.status_code == 201
        resp2 = api_post("/api/keywords", {"name": name, "parent_id": parent2["id"]})
        assert resp2.status_code == 201


# ════════════════════════════════════════════════════════════════════
# PART 5: Recipes CRUD
# ════════════════════════════════════════════════════════════════════


class TestRecipesCRUD:

    def test_create_simple_recipe(self):
        resp = api_post("/api/recipes", {
            "name": f"Pancakes-{UNIQUE}",
            "description": "Fluffy pancakes",
            "servings": 4,
            "working_time": 15,
            "waiting_time": 5
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Pancakes-{UNIQUE}"
        assert data["servings"] == 4
        assert data["working_time"] == 15
        assert data["waiting_time"] == 5
        assert "id" in data
        assert "steps" in data
        assert "keywords" in data

    def test_create_recipe_with_steps_and_ingredients(self):
        # First create food and unit
        food_resp = api_post("/api/foods", {"name": f"egg-{uuid.uuid4().hex[:8]}"})
        food_id = food_resp.json()["id"]
        unit_resp = api_post("/api/units", {"name": f"piece-{uuid.uuid4().hex[:8]}"})
        unit_id = unit_resp.json()["id"]

        resp = api_post("/api/recipes", {
            "name": f"Omelette-{UNIQUE}",
            "servings": 2,
            "steps": [
                {
                    "instruction": "Beat eggs",
                    "order": 1,
                    "ingredients": [
                        {"food_id": food_id, "unit_id": unit_id, "amount": 3}
                    ]
                },
                {
                    "instruction": "Cook in pan",
                    "order": 2,
                    "ingredients": []
                }
            ]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["steps"]) == 2
        # Steps should be ordered
        assert data["steps"][0]["order"] <= data["steps"][1]["order"]
        assert len(data["steps"][0]["ingredients"]) == 1
        assert data["steps"][0]["ingredients"][0]["food_id"] == food_id
        assert data["steps"][0]["ingredients"][0]["amount"] == 3

    def test_create_recipe_with_keywords(self):
        kw_resp = api_post("/api/keywords", {"name": f"Breakfast-{uuid.uuid4().hex[:8]}"})
        kw_id = kw_resp.json()["id"]

        resp = api_post("/api/recipes", {
            "name": f"Toast-{uuid.uuid4().hex[:8]}",
            "keyword_ids": [kw_id]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["keywords"]) == 1
        assert data["keywords"][0]["id"] == kw_id

    def test_list_recipes(self):
        resp = api_get("/api/recipes")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_get_recipe(self):
        create_resp = api_post("/api/recipes", {"name": f"GetR-{UNIQUE}"})
        recipe_id = create_resp.json()["id"]
        resp = api_get(f"/api/recipes/{recipe_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == recipe_id
        assert "steps" in resp.json()
        assert "keywords" in resp.json()

    def test_update_recipe(self):
        create_resp = api_post("/api/recipes", {"name": f"UpdR-{UNIQUE}", "servings": 2})
        recipe_id = create_resp.json()["id"]
        resp = api_put(f"/api/recipes/{recipe_id}", {
            "name": f"UpdatedR-{UNIQUE}",
            "servings": 6,
            "steps": [{"instruction": "New step", "order": 1}]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"UpdatedR-{UNIQUE}"
        assert data["servings"] == 6
        assert len(data["steps"]) == 1

    def test_delete_recipe(self):
        create_resp = api_post("/api/recipes", {"name": f"DelR-{UNIQUE}"})
        recipe_id = create_resp.json()["id"]
        resp = api_delete(f"/api/recipes/{recipe_id}")
        assert resp.status_code == 204
        resp = api_get(f"/api/recipes/{recipe_id}")
        assert resp.status_code == 404

    def test_recipe_not_found(self):
        resp = api_get("/api/recipes/99999")
        assert resp.status_code == 404

    def test_recipe_search(self):
        unique_name = f"Searchable-{uuid.uuid4().hex[:8]}"
        api_post("/api/recipes", {"name": unique_name})
        resp = api_get("/api/recipes", params={"search": unique_name})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(r["name"] == unique_name for r in data["results"])

    def test_recipe_pagination(self):
        # Create a few recipes
        for i in range(3):
            api_post("/api/recipes", {"name": f"Page-{uuid.uuid4().hex[:8]}"})
        resp = api_get("/api/recipes", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2


# ════════════════════════════════════════════════════════════════════
# PART 6: Keyword Hierarchy Search
# ════════════════════════════════════════════════════════════════════


class TestKeywordHierarchySearch:

    def test_search_by_parent_keyword_includes_children(self):
        """Filtering recipes by parent keyword should also include recipes with child keywords."""
        # Create hierarchy: Cuisine -> Mediterranean -> Greek
        cuisine_resp = api_post("/api/keywords", {"name": f"Cuisine-{uuid.uuid4().hex[:8]}"})
        cuisine_id = cuisine_resp.json()["id"]
        med_resp = api_post("/api/keywords", {"name": f"Mediterranean-{uuid.uuid4().hex[:8]}", "parent_id": cuisine_id})
        med_id = med_resp.json()["id"]
        greek_resp = api_post("/api/keywords", {"name": f"Greek-{uuid.uuid4().hex[:8]}", "parent_id": med_id})
        greek_id = greek_resp.json()["id"]

        # Create recipes with different keywords
        api_post("/api/recipes", {"name": f"Moussaka-{uuid.uuid4().hex[:8]}", "keyword_ids": [greek_id]})
        api_post("/api/recipes", {"name": f"Hummus-{uuid.uuid4().hex[:8]}", "keyword_ids": [med_id]})
        api_post("/api/recipes", {"name": f"General-{uuid.uuid4().hex[:8]}", "keyword_ids": [cuisine_id]})

        # Search by top-level keyword should return all 3
        resp = api_get("/api/recipes", params={"keywords": str(cuisine_id)})
        assert resp.status_code == 200
        assert resp.json()["count"] >= 3

        # Search by Mediterranean should return med + greek recipes (at least 2)
        resp = api_get("/api/recipes", params={"keywords": str(med_id)})
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2

        # Search by Greek should return only Greek recipe (at least 1)
        resp = api_get("/api/recipes", params={"keywords": str(greek_id)})
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_search_by_multiple_keywords(self):
        """Comma-separated keywords should work (OR logic — recipe must have at least one)."""
        kw1_resp = api_post("/api/keywords", {"name": f"Quick-{uuid.uuid4().hex[:8]}"})
        kw1_id = kw1_resp.json()["id"]
        kw2_resp = api_post("/api/keywords", {"name": f"Vegan-{uuid.uuid4().hex[:8]}"})
        kw2_id = kw2_resp.json()["id"]

        api_post("/api/recipes", {"name": f"QuickDish-{uuid.uuid4().hex[:8]}", "keyword_ids": [kw1_id]})
        api_post("/api/recipes", {"name": f"VeganDish-{uuid.uuid4().hex[:8]}", "keyword_ids": [kw2_id]})

        resp = api_get("/api/recipes", params={"keywords": f"{kw1_id},{kw2_id}"})
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2


# ════════════════════════════════════════════════════════════════════
# PART 7: Nutritional Computation
# ════════════════════════════════════════════════════════════════════


class TestNutrition:

    def test_basic_nutrition_computation(self):
        """Nutrition = sum(ingredient.amount * food.calories_per_unit) / servings."""
        # Create foods with nutrition data
        flour = api_post("/api/foods", {
            "name": f"flour-nut-{uuid.uuid4().hex[:8]}",
            "calories_per_unit": 3.5,
            "protein_per_unit": 0.1,
            "fat_per_unit": 0.01,
            "carbs_per_unit": 0.75
        }).json()
        sugar = api_post("/api/foods", {
            "name": f"sugar-nut-{uuid.uuid4().hex[:8]}",
            "calories_per_unit": 4.0,
            "protein_per_unit": 0.0,
            "fat_per_unit": 0.0,
            "carbs_per_unit": 1.0
        }).json()

        unit = api_post("/api/units", {"name": f"g-nut-{uuid.uuid4().hex[:8]}"}).json()

        # Create recipe with 2 servings, 200g flour + 100g sugar
        recipe = api_post("/api/recipes", {
            "name": f"NutRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 2,
            "steps": [{
                "instruction": "Mix",
                "order": 1,
                "ingredients": [
                    {"food_id": flour["id"], "unit_id": unit["id"], "amount": 200},
                    {"food_id": sugar["id"], "unit_id": unit["id"], "amount": 100}
                ]
            }]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recipe_id"] == recipe["id"]
        assert data["servings"] == 2

        # Total calories = 200*3.5 + 100*4.0 = 700 + 400 = 1100
        # Per serving = 1100 / 2 = 550
        assert data["calories"] == pytest.approx(550.0, rel=1e-2)
        # Total protein = 200*0.1 + 100*0.0 = 20
        # Per serving = 10
        assert data["protein"] == pytest.approx(10.0, rel=1e-2)
        # Total fat = 200*0.01 + 100*0.0 = 2
        # Per serving = 1
        assert data["fat"] == pytest.approx(1.0, rel=1e-2)
        # Total carbs = 200*0.75 + 100*1.0 = 150 + 100 = 250
        # Per serving = 125
        assert data["carbs"] == pytest.approx(125.0, rel=1e-2)

    def test_nutrition_excludes_no_amount_ingredients(self):
        """Ingredients with no_amount=true contribute 0 to nutrition."""
        food = api_post("/api/foods", {
            "name": f"salt-noamt-{uuid.uuid4().hex[:8]}",
            "calories_per_unit": 0.0,
            "protein_per_unit": 0.0,
            "fat_per_unit": 0.0,
            "carbs_per_unit": 0.0
        }).json()
        caloric_food = api_post("/api/foods", {
            "name": f"oil-noamt-{uuid.uuid4().hex[:8]}",
            "calories_per_unit": 9.0,
            "protein_per_unit": 0.0,
            "fat_per_unit": 1.0,
            "carbs_per_unit": 0.0
        }).json()
        unit = api_post("/api/units", {"name": f"ml-noamt-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"NoAmtRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Cook",
                "order": 1,
                "ingredients": [
                    {"food_id": caloric_food["id"], "unit_id": unit["id"], "amount": 10},
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 5, "no_amount": True}
                ]
            }]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        # Only oil contributes: 10 * 9.0 = 90 calories / 1 serving = 90
        assert data["calories"] == pytest.approx(90.0, rel=1e-2)

    def test_nutrition_excludes_header_ingredients(self):
        """Ingredients with is_header=true are excluded from nutrition."""
        food = api_post("/api/foods", {
            "name": f"food-hdr-{uuid.uuid4().hex[:8]}",
            "calories_per_unit": 5.0,
            "protein_per_unit": 1.0,
            "fat_per_unit": 0.5,
            "carbs_per_unit": 2.0
        }).json()
        unit = api_post("/api/units", {"name": f"u-hdr-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"HdrRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Assemble",
                "order": 1,
                "ingredients": [
                    {"is_header": True, "note": "For the sauce"},
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 100}
                ]
            }]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        # Only the non-header ingredient contributes: 100 * 5.0 = 500
        assert data["calories"] == pytest.approx(500.0, rel=1e-2)

    def test_nutrition_food_without_nutrition_data(self):
        """Foods with null nutrition values contribute 0."""
        food = api_post("/api/foods", {
            "name": f"mystery-{uuid.uuid4().hex[:8]}"
            # No nutrition data provided
        }).json()
        unit = api_post("/api/units", {"name": f"u-mys-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"MysteryRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Add mystery ingredient",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 100}
                ]
            }]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["calories"] == pytest.approx(0.0)
        assert data["protein"] == pytest.approx(0.0)
        assert data["fat"] == pytest.approx(0.0)
        assert data["carbs"] == pytest.approx(0.0)

    def test_nutrition_recipe_not_found(self):
        resp = api_get("/api/recipes/99999/nutrition")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Meal Plans
# ════════════════════════════════════════════════════════════════════


class TestMealPlans:

    def test_create_meal_plan(self):
        recipe = api_post("/api/recipes", {"name": f"MPRecipe-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_post("/api/meal-plans", {
            "date": "2025-06-15",
            "meal_type": "dinner",
            "recipe_id": recipe["id"],
            "servings": 4,
            "title": "Family dinner",
            "note": "Make extra"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2025-06-15"
        assert data["meal_type"] == "dinner"
        assert data["recipe_id"] == recipe["id"]
        assert data["servings"] == 4
        assert data["title"] == "Family dinner"
        assert "id" in data

    def test_create_meal_plan_without_recipe(self):
        resp = api_post("/api/meal-plans", {
            "date": "2025-06-16",
            "meal_type": "lunch",
            "title": "Eat out"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["recipe_id"] is None

    def test_list_meal_plans(self):
        resp = api_get("/api/meal-plans")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_meal_plans_date_filter(self):
        api_post("/api/meal-plans", {"date": "2025-07-01", "meal_type": "breakfast"})
        api_post("/api/meal-plans", {"date": "2025-07-05", "meal_type": "lunch"})
        api_post("/api/meal-plans", {"date": "2025-07-10", "meal_type": "dinner"})

        resp = api_get("/api/meal-plans", params={"from_date": "2025-07-03", "to_date": "2025-07-07"})
        assert resp.status_code == 200
        results = resp.json()
        for mp in results:
            assert mp["date"] >= "2025-07-03"
            assert mp["date"] <= "2025-07-07"

    def test_get_meal_plan(self):
        create_resp = api_post("/api/meal-plans", {"date": "2025-08-01", "meal_type": "other"})
        mp_id = create_resp.json()["id"]
        resp = api_get(f"/api/meal-plans/{mp_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == mp_id

    def test_update_meal_plan(self):
        create_resp = api_post("/api/meal-plans", {"date": "2025-09-01", "meal_type": "breakfast"})
        mp_id = create_resp.json()["id"]
        resp = api_put(f"/api/meal-plans/{mp_id}", {
            "date": "2025-09-02",
            "meal_type": "lunch",
            "title": "Changed"
        })
        assert resp.status_code == 200
        assert resp.json()["date"] == "2025-09-02"
        assert resp.json()["meal_type"] == "lunch"
        assert resp.json()["title"] == "Changed"

    def test_delete_meal_plan(self):
        create_resp = api_post("/api/meal-plans", {"date": "2025-10-01", "meal_type": "dinner"})
        mp_id = create_resp.json()["id"]
        resp = api_delete(f"/api/meal-plans/{mp_id}")
        assert resp.status_code == 204
        resp = api_get(f"/api/meal-plans/{mp_id}")
        assert resp.status_code == 404

    def test_meal_plan_not_found(self):
        resp = api_get("/api/meal-plans/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Shopping Lists CRUD
# ════════════════════════════════════════════════════════════════════


class TestShoppingListsCRUD:

    def test_create_shopping_list(self):
        resp = api_post("/api/shopping-lists", {"name": f"Weekly-{UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Weekly-{UNIQUE}"
        assert "id" in data
        assert "entries" in data
        assert data["entries"] == []

    def test_list_shopping_lists(self):
        resp = api_get("/api/shopping-lists")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_shopping_list(self):
        create_resp = api_post("/api/shopping-lists", {"name": f"GetSL-{UNIQUE}"})
        sl_id = create_resp.json()["id"]
        resp = api_get(f"/api/shopping-lists/{sl_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sl_id
        assert "entries" in resp.json()

    def test_update_shopping_list(self):
        create_resp = api_post("/api/shopping-lists", {"name": f"UpdSL-{UNIQUE}"})
        sl_id = create_resp.json()["id"]
        resp = api_put(f"/api/shopping-lists/{sl_id}", {"name": f"UpdatedSL-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"UpdatedSL-{UNIQUE}"

    def test_delete_shopping_list(self):
        create_resp = api_post("/api/shopping-lists", {"name": f"DelSL-{UNIQUE}"})
        sl_id = create_resp.json()["id"]
        resp = api_delete(f"/api/shopping-lists/{sl_id}")
        assert resp.status_code == 204
        resp = api_get(f"/api/shopping-lists/{sl_id}")
        assert resp.status_code == 404

    def test_add_entry_to_shopping_list(self):
        food = api_post("/api/foods", {"name": f"sl-food-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"sl-unit-{uuid.uuid4().hex[:8]}"}).json()
        sl = api_post("/api/shopping-lists", {"name": f"EntrySL-{uuid.uuid4().hex[:8]}"}).json()

        resp = api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"],
            "unit_id": unit["id"],
            "amount": 500
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["food_id"] == food["id"]
        assert data["unit_id"] == unit["id"]
        assert data["amount"] == 500
        assert data["checked"] is False

    def test_update_entry(self):
        food = api_post("/api/foods", {"name": f"sl-upd-{uuid.uuid4().hex[:8]}"}).json()
        sl = api_post("/api/shopping-lists", {"name": f"UpdEntrySL-{uuid.uuid4().hex[:8]}"}).json()
        entry = api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "amount": 100
        }).json()

        resp = api_put(f"/api/shopping-lists/{sl['id']}/entries/{entry['id']}", {
            "checked": True
        })
        assert resp.status_code == 200
        assert resp.json()["checked"] is True

    def test_delete_entry(self):
        food = api_post("/api/foods", {"name": f"sl-del-{uuid.uuid4().hex[:8]}"}).json()
        sl = api_post("/api/shopping-lists", {"name": f"DelEntrySL-{uuid.uuid4().hex[:8]}"}).json()
        entry = api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "amount": 50
        }).json()

        resp = api_delete(f"/api/shopping-lists/{sl['id']}/entries/{entry['id']}")
        assert resp.status_code == 204

    def test_shopping_list_not_found(self):
        resp = api_get("/api/shopping-lists/99999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Shopping List — Add Recipe with Scaling and Merging
# ════════════════════════════════════════════════════════════════════


class TestShoppingListAddRecipe:

    def test_add_recipe_to_shopping_list_basic(self):
        """Adding a recipe should create entries for all its ingredients."""
        food1 = api_post("/api/foods", {"name": f"rice-add-{uuid.uuid4().hex[:8]}"}).json()
        food2 = api_post("/api/foods", {"name": f"chicken-add-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"g-add-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"ChickenRice-{uuid.uuid4().hex[:8]}",
            "servings": 2,
            "steps": [{
                "instruction": "Cook",
                "order": 1,
                "ingredients": [
                    {"food_id": food1["id"], "unit_id": unit["id"], "amount": 200},
                    {"food_id": food2["id"], "unit_id": unit["id"], "amount": 300}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"AddRecipeSL-{uuid.uuid4().hex[:8]}"}).json()

        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        data = resp.json()
        entries = data["entries"]
        assert len(entries) == 2

        # Check both foods are present
        food_ids = [e["food_id"] for e in entries]
        assert food1["id"] in food_ids
        assert food2["id"] in food_ids

    def test_add_recipe_with_servings_scaling(self):
        """Amounts should be scaled by desired_servings / recipe_servings."""
        food = api_post("/api/foods", {"name": f"flour-scale-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"g-scale-{uuid.uuid4().hex[:8]}"}).json()

        # Recipe has 4 servings, 200g flour
        recipe = api_post("/api/recipes", {
            "name": f"ScaleRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 4,
            "steps": [{
                "instruction": "Mix",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 200}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"ScaleSL-{uuid.uuid4().hex[:8]}"}).json()

        # Add with servings=2 → 200 * (2/4) = 100
        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"],
            "servings": 2
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        flour_entry = next(e for e in entries if e["food_id"] == food["id"])
        assert flour_entry["amount"] == pytest.approx(100.0, rel=1e-2)

    def test_add_recipe_ingredient_merging(self):
        """Same food + same unit should merge amounts."""
        food = api_post("/api/foods", {"name": f"butter-merge-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"g-merge-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"MergeRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Use butter",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 50}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"MergeSL-{uuid.uuid4().hex[:8]}"}).json()

        # Add existing entry with same food+unit
        api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "unit_id": unit["id"], "amount": 100
        })

        # Now add recipe — should merge: 100 + 50 = 150
        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        butter_entries = [e for e in entries if e["food_id"] == food["id"] and e["unit_id"] == unit["id"]]
        assert len(butter_entries) == 1
        assert butter_entries[0]["amount"] == pytest.approx(150.0, rel=1e-2)

    def test_add_recipe_no_merge_different_unit(self):
        """Different units for same food should NOT merge."""
        food = api_post("/api/foods", {"name": f"milk-nomerge-{uuid.uuid4().hex[:8]}"}).json()
        unit1 = api_post("/api/units", {"name": f"ml-nm-{uuid.uuid4().hex[:8]}"}).json()
        unit2 = api_post("/api/units", {"name": f"cup-nm-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"NoMergeRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Pour",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit2["id"], "amount": 2}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"NoMergeSL-{uuid.uuid4().hex[:8]}"}).json()

        # Add entry with unit1
        api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "unit_id": unit1["id"], "amount": 500
        })

        # Add recipe with unit2 — should create new entry
        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        milk_entries = [e for e in entries if e["food_id"] == food["id"]]
        assert len(milk_entries) == 2

    def test_add_recipe_no_merge_checked_entry(self):
        """Checked entries are not merged — a new unchecked entry is created."""
        food = api_post("/api/foods", {"name": f"egg-chk-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"pc-chk-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"ChkRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Use eggs",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 3}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"ChkSL-{uuid.uuid4().hex[:8]}"}).json()

        # Add checked entry
        entry = api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "unit_id": unit["id"], "amount": 6, "checked": True
        }).json()

        # Add recipe — should NOT merge because existing is checked
        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        egg_entries = [e for e in entries if e["food_id"] == food["id"]]
        assert len(egg_entries) == 2

    def test_add_recipe_excludes_headers(self):
        """Header ingredients should not be added to shopping list."""
        food = api_post("/api/foods", {"name": f"onion-hdr-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"pc-hdr-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"HdrRecipeSL-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Prep",
                "order": 1,
                "ingredients": [
                    {"is_header": True, "note": "Vegetables"},
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 2}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"HdrSLTest-{uuid.uuid4().hex[:8]}"}).json()

        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        # Only 1 entry (the onion), not the header
        assert len(entries) == 1
        assert entries[0]["food_id"] == food["id"]

    def test_add_recipe_no_amount_ingredient(self):
        """no_amount ingredients should be added with amount=0."""
        food = api_post("/api/foods", {"name": f"salt-noamt-sl-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"pinch-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"NoAmtSL-{uuid.uuid4().hex[:8]}",
            "servings": 1,
            "steps": [{
                "instruction": "Season",
                "order": 1,
                "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 1, "no_amount": True}
                ]
            }]
        }).json()

        sl = api_post("/api/shopping-lists", {"name": f"NoAmtSLTest-{uuid.uuid4().hex[:8]}"}).json()

        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {
            "recipe_id": recipe["id"]
        })
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["amount"] == 0

    def test_add_recipe_invalid_recipe_id(self):
        sl = api_post("/api/shopping-lists", {"name": f"BadRecipeSL-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_post(f"/api/shopping-lists/{sl['id']}/add-recipe", {"recipe_id": 99999})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Supermarkets and Categories
# ════════════════════════════════════════════════════════════════════


class TestSupermarkets:

    def test_create_supermarket_category(self):
        resp = api_post("/api/supermarket-categories", {"name": f"Dairy-{UNIQUE}"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Dairy-{UNIQUE}"
        assert "id" in data

    def test_list_supermarket_categories(self):
        resp = api_get("/api/supermarket-categories")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_supermarket_category(self):
        cat = api_post("/api/supermarket-categories", {"name": f"GetCat-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_get(f"/api/supermarket-categories/{cat['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cat["id"]

    def test_update_supermarket_category(self):
        cat = api_post("/api/supermarket-categories", {"name": f"UpdCat-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_put(f"/api/supermarket-categories/{cat['id']}", {"name": f"UpdatedCat-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200

    def test_delete_supermarket_category(self):
        cat = api_post("/api/supermarket-categories", {"name": f"DelCat-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_delete(f"/api/supermarket-categories/{cat['id']}")
        assert resp.status_code == 204
        resp = api_get(f"/api/supermarket-categories/{cat['id']}")
        assert resp.status_code == 404

    def test_create_supermarket(self):
        cat = api_post("/api/supermarket-categories", {"name": f"Produce-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_post("/api/supermarkets", {
            "name": f"Walmart-{UNIQUE}",
            "description": "Big store",
            "category_ordering": [cat["id"]]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == f"Walmart-{UNIQUE}"
        assert cat["id"] in data["category_ordering"]

    def test_list_supermarkets(self):
        resp = api_get("/api/supermarkets")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_supermarket(self):
        sm = api_post("/api/supermarkets", {"name": f"GetSM-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_get(f"/api/supermarkets/{sm['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sm["id"]

    def test_update_supermarket(self):
        sm = api_post("/api/supermarkets", {"name": f"UpdSM-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_put(f"/api/supermarkets/{sm['id']}", {"name": f"UpdatedSM-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200

    def test_delete_supermarket(self):
        sm = api_post("/api/supermarkets", {"name": f"DelSM-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_delete(f"/api/supermarkets/{sm['id']}")
        assert resp.status_code == 204
        resp = api_get(f"/api/supermarkets/{sm['id']}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Import/Export
# ════════════════════════════════════════════════════════════════════


class TestImportExport:

    def test_import_from_url(self):
        resp = api_post("/api/import/url", {"url": "https://example.com/my-recipe"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Imported Recipe"
        assert data["servings"] == 4
        assert data["working_time"] == 30
        assert data["waiting_time"] == 0
        assert len(data["steps"]) == 1
        assert "https://example.com/my-recipe" in data["steps"][0]["instruction"]

    def test_export_recipe(self):
        recipe = api_post("/api/recipes", {
            "name": f"ExportRecipe-{uuid.uuid4().hex[:8]}",
            "servings": 3,
            "steps": [{"instruction": "Do stuff", "order": 1}]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "exported_at" in data
        assert "recipe" in data
        assert data["recipe"]["id"] == recipe["id"]
        assert data["recipe"]["name"] == recipe["name"]
        assert len(data["recipe"]["steps"]) == 1

    def test_export_recipe_not_found(self):
        resp = api_get("/api/recipes/99999/export")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation by Space
# ════════════════════════════════════════════════════════════════════


class TestSpaceIsolation:

    def test_different_spaces_cannot_see_each_other_data(self):
        """Data created in one space is not visible in another."""
        # Create a keyword in the default space
        kw_resp = api_post("/api/keywords", {"name": f"IsoKw-{uuid.uuid4().hex[:8]}"})
        assert kw_resp.status_code == 201
        kw_id = kw_resp.json()["id"]

        # Try to get it from another space — should be 404
        resp = api_get(f"/api/keywords/{kw_id}", headers=OTHER_SPACE_HEADERS)
        assert resp.status_code == 404

    def test_different_spaces_lists_are_independent(self):
        """Listing in different space should not show other space's data."""
        unique_name = f"IsoFood-{uuid.uuid4().hex[:8]}"
        api_post("/api/foods", {"name": unique_name})

        # List from other space
        resp = api_get("/api/foods", params={"search": unique_name}, headers=OTHER_SPACE_HEADERS)
        assert resp.status_code == 200
        results = resp.json()
        assert not any(f["name"] == unique_name for f in results)

    def test_recipes_isolated_by_space(self):
        """Recipes from one space are not visible in another."""
        recipe = api_post("/api/recipes", {"name": f"IsoRecipe-{uuid.uuid4().hex[:8]}"}).json()
        resp = api_get(f"/api/recipes/{recipe['id']}", headers=OTHER_SPACE_HEADERS)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Edge Cases and Field Validation
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_recipe_steps_ordered(self):
        """Steps should always be returned in order."""
        food = api_post("/api/foods", {"name": f"edge-food-{uuid.uuid4().hex[:8]}"}).json()
        recipe = api_post("/api/recipes", {
            "name": f"OrderedSteps-{uuid.uuid4().hex[:8]}",
            "steps": [
                {"instruction": "Third", "order": 3},
                {"instruction": "First", "order": 1},
                {"instruction": "Second", "order": 2}
            ]
        }).json()

        resp = api_get(f"/api/recipes/{recipe['id']}")
        steps = resp.json()["steps"]
        assert steps[0]["instruction"] == "First"
        assert steps[1]["instruction"] == "Second"
        assert steps[2]["instruction"] == "Third"

    def test_recipe_default_values(self):
        """Recipe should have correct defaults."""
        recipe = api_post("/api/recipes", {"name": f"Defaults-{uuid.uuid4().hex[:8]}"}).json()
        assert recipe["servings"] == 1
        assert recipe["working_time"] == 0
        assert recipe["waiting_time"] == 0
        assert recipe["description"] == ""
        assert recipe["internal"] is False
        assert recipe["keywords"] == []
        assert recipe["steps"] == []

    def test_food_recipe_link_valid(self):
        """A food can link to an existing recipe in the same space."""
        recipe = api_post("/api/recipes", {"name": f"SubRecipe-{uuid.uuid4().hex[:8]}"}).json()
        food = api_post("/api/foods", {
            "name": f"linked-{uuid.uuid4().hex[:8]}",
            "recipe_id": recipe["id"]
        })
        assert food.status_code == 201
        assert food.json()["recipe_id"] == recipe["id"]

    def test_ingredient_with_is_header(self):
        """Header ingredients should be stored correctly."""
        recipe = api_post("/api/recipes", {
            "name": f"HeaderIng-{uuid.uuid4().hex[:8]}",
            "steps": [{
                "instruction": "Prep",
                "order": 1,
                "ingredients": [
                    {"is_header": True, "note": "For the dough", "order": 0}
                ]
            }]
        }).json()

        step = recipe["steps"][0]
        header = step["ingredients"][0]
        assert header["is_header"] is True
        assert header["note"] == "For the dough"

    def test_update_recipe_replaces_steps(self):
        """Updating a recipe with new steps should replace old steps entirely."""
        food = api_post("/api/foods", {"name": f"replace-food-{uuid.uuid4().hex[:8]}"}).json()
        unit = api_post("/api/units", {"name": f"replace-unit-{uuid.uuid4().hex[:8]}"}).json()

        recipe = api_post("/api/recipes", {
            "name": f"ReplaceSteps-{uuid.uuid4().hex[:8]}",
            "steps": [
                {"instruction": "Old step 1", "order": 1, "ingredients": [
                    {"food_id": food["id"], "unit_id": unit["id"], "amount": 100}
                ]},
                {"instruction": "Old step 2", "order": 2}
            ]
        }).json()

        # Update with completely different steps
        updated = api_put(f"/api/recipes/{recipe['id']}", {
            "name": recipe["name"],
            "steps": [{"instruction": "New single step", "order": 1}]
        }).json()

        assert len(updated["steps"]) == 1
        assert updated["steps"][0]["instruction"] == "New single step"

    def test_shopping_list_entry_with_no_unit(self):
        """Entry can have null unit_id."""
        food = api_post("/api/foods", {"name": f"nounit-{uuid.uuid4().hex[:8]}"}).json()
        sl = api_post("/api/shopping-lists", {"name": f"NoUnitSL-{uuid.uuid4().hex[:8]}"}).json()

        resp = api_post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"],
            "amount": 3
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit_id"] is None
        assert data["amount"] == 3
