"""
BackendForge — L2 Integration Tests for Tandoor Recipes Task

Adversarial tests targeting: field naming, nested data, filtering/pagination,
status codes, business logic computation, data isolation, cascade deletes.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex

SPACE_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:space-a"))
SPACE_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:space-b"))
USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user"))

HEADERS_A = {"X-User-Id": USER_A, "X-Space-Id": SPACE_A, "Content-Type": "application/json"}
HEADERS_B = {"X-User-Id": USER_A, "X-Space-Id": SPACE_B, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def isolate_test_spaces(request):
    """Give every item fresh space namespaces so state cannot leak across tests."""
    global SPACE_A, SPACE_B, USER_A, HEADERS_A, HEADERS_B

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    SPACE_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:space-a"))
    SPACE_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:space-b"))
    USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user"))
    HEADERS_A = {"X-User-Id": USER_A, "X-Space-Id": SPACE_A, "Content-Type": "application/json"}
    HEADERS_B = {"X-User-Id": USER_A, "X-Space-Id": SPACE_B, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS_A if headers is None else headers,
        timeout=30,
    )


def post(path, json=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS_A if headers is None else headers,
        timeout=30,
    )


def put(path, json=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json,
        headers=HEADERS_A if headers is None else headers,
        timeout=30,
    )


def delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS_A if headers is None else headers,
        timeout=30,
    )


class TestKeywordResponseFields:
    """Pattern 1+4: Keyword response fields and status codes."""

    def test_create_keyword_returns_201_with_fields(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/keywords", {"name": f"Kw-{tag}", "description": "Test desc"})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert "description" in data
        assert "parent_id" in data
        assert "created_at" in data
        assert data["name"] == f"Kw-{tag}"
        assert data["description"] == "Test desc"
        assert data["parent_id"] is None

    def test_keyword_with_parent(self):
        parent = post("/api/keywords", {"name": f"Parent-{uuid.uuid4().hex[:6]}"}).json()
        child = post("/api/keywords", {"name": f"Child-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]})
        assert child.status_code == 201
        assert child.json()["parent_id"] == parent["id"]

    def test_delete_keyword_returns_204(self):
        kw = post("/api/keywords", {"name": f"Del-{uuid.uuid4().hex[:6]}"}).json()
        r = delete(f"/api/keywords/{kw['id']}")
        assert r.status_code == 204
        assert get(f"/api/keywords/{kw['id']}").status_code == 404

    def test_nonexistent_keyword_returns_404(self):
        assert get("/api/keywords/999999").status_code == 404


class TestFoodResponseFields:
    """Pattern 1+4: Food response fields."""

    def test_create_food_returns_201(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/foods", {
            "name": f"Food-{tag}",
            "calories_per_unit": 52.5,
            "protein_per_unit": 3.2,
            "fat_per_unit": 1.1,
            "carbs_per_unit": 9.8,
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert data["name"] == f"Food-{tag}"
        assert data["calories_per_unit"] == 52.5
        assert data["protein_per_unit"] == 3.2
        assert data["fat_per_unit"] == 1.1
        assert data["carbs_per_unit"] == 9.8

    def test_food_unique_name_constraint(self):
        name = f"UniqueFood-{uuid.uuid4().hex[:8]}"
        r1 = post("/api/foods", {"name": name})
        assert r1.status_code == 201
        r2 = post("/api/foods", {"name": name})
        assert r2.status_code == 400


class TestUnitResponseFields:
    """Pattern 1+4: Unit response fields."""

    def test_create_unit_returns_201(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/units", {"name": f"unit-{tag}", "plural_name": f"units-{tag}", "description": "desc"})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "name" in data
        assert "plural_name" in data
        assert "description" in data
        assert data["name"] == f"unit-{tag}"
        assert data["plural_name"] == f"units-{tag}"

    def test_unit_unique_name_constraint(self):
        name = f"UniqueUnit-{uuid.uuid4().hex[:8]}"
        post("/api/units", {"name": name})
        r = post("/api/units", {"name": name})
        assert r.status_code == 400


class TestRecipeResponseFields:
    """Pattern 1+2: Recipe response with nested steps and ingredients."""

    def test_create_recipe_with_steps_and_ingredients(self):
        food = post("/api/foods", {"name": f"Flour-{uuid.uuid4().hex[:6]}"}).json()
        unit = post("/api/units", {"name": f"g-{uuid.uuid4().hex[:6]}"}).json()
        kw = post("/api/keywords", {"name": f"Baking-{uuid.uuid4().hex[:6]}"}).json()

        r = post("/api/recipes", {
            "name": f"Cake-{uuid.uuid4().hex[:6]}",
            "description": "A cake recipe",
            "servings": 8,
            "working_time": 30,
            "waiting_time": 45,
            "keyword_ids": [kw["id"]],
            "steps": [{
                "instruction": "Mix ingredients",
                "order": 1,
                "time": 10,
                "ingredients": [{
                    "food_id": food["id"],
                    "unit_id": unit["id"],
                    "amount": 200,
                    "note": "sifted",
                    "order": 0
                }]
            }]
        })
        assert r.status_code == 201
        recipe = r.json()
        assert "id" in recipe
        assert "name" in recipe
        assert "steps" in recipe
        assert "keywords" in recipe
        assert "created_at" in recipe
        assert recipe["servings"] == 8
        assert recipe["working_time"] == 30
        assert recipe["waiting_time"] == 45
        # Nested steps
        assert len(recipe["steps"]) == 1
        step = recipe["steps"][0]
        assert "id" in step
        assert step["instruction"] == "Mix ingredients"
        assert step["order"] == 1
        assert "ingredients" in step
        assert len(step["ingredients"]) == 1
        ing = step["ingredients"][0]
        assert "id" in ing
        assert ing["food_id"] == food["id"]
        assert ing["unit_id"] == unit["id"]
        assert ing["amount"] == 200
        assert ing["note"] == "sifted"
        # Keywords
        assert len(recipe["keywords"]) == 1
        assert recipe["keywords"][0]["id"] == kw["id"]


class TestRecipePagination:
    """Pattern 3: Verify pagination actually works."""

    def test_pagination_limits_results(self):
        tag = uuid.uuid4().hex[:6]
        # Create 5 recipes
        for i in range(5):
            post("/api/recipes", {"name": f"Pag-{tag}-{i}", "servings": 1})
        r = get("/api/recipes", params={"page": 1, "page_size": 2})
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "results" in data
        assert len(data["results"]) <= 2
        assert data["count"] >= 5

    def test_pagination_page2_different_items(self):
        tag = uuid.uuid4().hex[:6]
        for i in range(4):
            post("/api/recipes", {"name": f"Pg2-{tag}-{i}", "servings": 1})
        r1 = get("/api/recipes", params={"page": 1, "page_size": 2})
        r2 = get("/api/recipes", params={"page": 2, "page_size": 2})
        ids1 = {r["id"] for r in r1.json()["results"]}
        ids2 = {r["id"] for r in r2.json()["results"]}
        assert ids1.isdisjoint(ids2)


class TestRecipeKeywordFilter:
    """Pattern 3+5: Keyword filter includes descendants."""

    def test_keyword_filter_includes_children(self):
        parent = post("/api/keywords", {"name": f"Italian-{uuid.uuid4().hex[:6]}"}).json()
        child = post("/api/keywords", {"name": f"Pasta-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]}).json()

        # Recipe with child keyword only
        recipe = post("/api/recipes", {
            "name": f"Spaghetti-{uuid.uuid4().hex[:6]}",
            "keyword_ids": [child["id"]],
            "servings": 2
        }).json()

        # Filter by parent should include recipe with child keyword
        r = get("/api/recipes", params={"keywords": str(parent["id"])})
        assert r.status_code == 200
        ids = [rec["id"] for rec in r.json()["results"]]
        assert recipe["id"] in ids


class TestNutritionComputation:
    """Pattern 5: Verify nutrition is computed, not hardcoded."""

    def test_nutrition_computed_per_serving(self):
        food = post("/api/foods", {
            "name": f"NutFood-{uuid.uuid4().hex[:6]}",
            "calories_per_unit": 10.0,
            "protein_per_unit": 2.0,
            "fat_per_unit": 1.0,
            "carbs_per_unit": 5.0,
        }).json()
        unit = post("/api/units", {"name": f"nut-u-{uuid.uuid4().hex[:6]}"}).json()

        recipe = post("/api/recipes", {
            "name": f"NutRecipe-{uuid.uuid4().hex[:6]}",
            "servings": 4,
            "steps": [{"order": 1, "instruction": "Cook", "ingredients": [
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 100}
            ]}]
        }).json()

        r = get(f"/api/recipes/{recipe['id']}/nutrition")
        assert r.status_code == 200
        n = r.json()
        assert n["recipe_id"] == recipe["id"]
        assert n["servings"] == 4
        # Total: 100 * 10 = 1000 cal, per serving: 250
        assert abs(n["calories"] - 250.0) < 0.01
        assert abs(n["protein"] - 50.0) < 0.01  # 100*2/4
        assert abs(n["fat"] - 25.0) < 0.01  # 100*1/4
        assert abs(n["carbs"] - 125.0) < 0.01  # 100*5/4

    def test_nutrition_excludes_header_ingredients(self):
        food = post("/api/foods", {
            "name": f"NutH-{uuid.uuid4().hex[:6]}",
            "calories_per_unit": 50.0,
            "protein_per_unit": 5.0, "fat_per_unit": 3.0, "carbs_per_unit": 10.0
        }).json()
        unit = post("/api/units", {"name": f"nh-u-{uuid.uuid4().hex[:6]}"}).json()

        recipe = post("/api/recipes", {
            "name": f"NutHR-{uuid.uuid4().hex[:6]}",
            "servings": 1,
            "steps": [{"order": 1, "instruction": "Do", "ingredients": [
                {"is_header": True, "note": "For the sauce", "order": 0},
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 10, "order": 1}
            ]}]
        }).json()

        n = get(f"/api/recipes/{recipe['id']}/nutrition").json()
        # Only the non-header ingredient: 10*50 = 500 cal / 1 serving
        assert abs(n["calories"] - 500.0) < 0.01


class TestShoppingListEntryFields:
    """Pattern 1+4: Shopping list entry response fields."""

    def test_add_entry_returns_201(self):
        food = post("/api/foods", {"name": f"SLF-{uuid.uuid4().hex[:6]}"}).json()
        unit = post("/api/units", {"name": f"SLU-{uuid.uuid4().hex[:6]}"}).json()
        sl = post("/api/shopping-lists", {"name": f"SL-{uuid.uuid4().hex[:6]}"}).json()
        r = post(f"/api/shopping-lists/{sl['id']}/entries", {
            "food_id": food["id"], "unit_id": unit["id"], "amount": 3.5
        })
        assert r.status_code == 201
        entry = r.json()
        assert "id" in entry
        assert "food_id" in entry
        assert "unit_id" in entry
        assert "amount" in entry
        assert "checked" in entry
        assert entry["food_id"] == food["id"]
        assert entry["unit_id"] == unit["id"]
        assert entry["amount"] == 3.5
        assert entry["checked"] is False


class TestShoppingListGetIncludesEntries:
    """Pattern 2: GET shopping list includes entries array."""

    def test_get_shopping_list_has_entries(self):
        food = post("/api/foods", {"name": f"SLE-{uuid.uuid4().hex[:6]}"}).json()
        sl = post("/api/shopping-lists", {"name": f"SLEnt-{uuid.uuid4().hex[:6]}"}).json()
        post(f"/api/shopping-lists/{sl['id']}/entries", {"food_id": food["id"], "amount": 2})

        r = get(f"/api/shopping-lists/{sl['id']}")
        assert r.status_code == 200
        data = r.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) == 1
        assert data["entries"][0]["food_id"] == food["id"]


class TestMealPlanDateFilter:
    """Pattern 3: Verify date filter actually works."""

    def test_from_to_date_filter(self):
        recipe = post("/api/recipes", {"name": f"MP-{uuid.uuid4().hex[:6]}", "servings": 2}).json()
        post("/api/meal-plans", {"date": "2024-06-01", "meal_type": "lunch", "recipe_id": recipe["id"]})
        post("/api/meal-plans", {"date": "2024-06-15", "meal_type": "dinner", "recipe_id": recipe["id"]})
        post("/api/meal-plans", {"date": "2024-07-01", "meal_type": "breakfast", "recipe_id": recipe["id"]})

        r = get("/api/meal-plans", params={"from_date": "2024-06-01", "to_date": "2024-06-30"})
        assert r.status_code == 200
        plans = r.json()
        for p in plans:
            assert "2024-06" in p["date"]


class TestDataIsolationBySpace:
    """Pattern 6: Different spaces cannot see each other's data."""

    def test_keyword_isolated(self):
        kw = post("/api/keywords", {"name": f"IsoKw-{uuid.uuid4().hex[:6]}"}, headers=HEADERS_A).json()
        r = get(f"/api/keywords/{kw['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_recipe_isolated(self):
        recipe = post("/api/recipes", {"name": f"IsoR-{uuid.uuid4().hex[:6]}", "servings": 1}, headers=HEADERS_A).json()
        r = get(f"/api/recipes/{recipe['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_food_isolated(self):
        food = post("/api/foods", {"name": f"IsoF-{uuid.uuid4().hex[:6]}"}, headers=HEADERS_A).json()
        r = get(f"/api/foods/{food['id']}", headers=HEADERS_B)
        assert r.status_code == 404


class TestKeywordSearch:
    """Pattern 3: Search actually filters results."""

    def test_search_filters_keywords(self):
        tag = uuid.uuid4().hex[:8]
        post("/api/keywords", {"name": f"Searchable-{tag}"})
        post("/api/keywords", {"name": f"Other-{uuid.uuid4().hex[:6]}"})
        r = get("/api/keywords", params={"search": tag})
        assert r.status_code == 200
        names = [k["name"] for k in r.json()]
        assert any(tag in n for n in names)

    def test_root_only_filter(self):
        parent = post("/api/keywords", {"name": f"RootP-{uuid.uuid4().hex[:6]}"}).json()
        post("/api/keywords", {"name": f"ChildC-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]})
        r = get("/api/keywords", params={"root_only": "true"})
        assert r.status_code == 200
        for kw in r.json():
            assert kw["parent_id"] is None


class TestExportRecipe:
    """Pattern 2: Export has envelope with version, exported_at, recipe."""

    def test_export_structure(self):
        recipe = post("/api/recipes", {"name": f"Exp-{uuid.uuid4().hex[:6]}", "servings": 4}).json()
        r = get(f"/api/recipes/{recipe['id']}/export")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "exported_at" in data
        assert "recipe" in data
        assert data["recipe"]["id"] == recipe["id"]
        assert data["recipe"]["name"] == recipe["name"]


class TestAuthRequired:
    """Pattern 4: Missing headers return 401."""

    def test_missing_headers_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/keywords", timeout=30)
        assert r.status_code == 401

    def test_missing_space_id_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/recipes",
                         headers={"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"},
                         timeout=30)
        assert r.status_code == 401
