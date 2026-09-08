"""
BackendForge — L3 Workflow Tests for Tandoor Recipes Task

Multi-step adversarial workflow tests: keyword hierarchy, shopping list merging/scaling,
nutrition computation, import/export, cascade deletes.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def make_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Space-Id": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }


def api(method, path, headers, json=None, params=None):
    return getattr(requests, method)(
        f"{BASE_URL}{path}", json=json, params=params, headers=headers, timeout=30
    )


class TestShoppingListServingsScaling:
    """Pattern 5+7: Add recipe to shopping list with scaling and verify amounts."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_add_recipe_scales_ingredients(self):
        """Recipe with 4 servings, add with 2 servings → amounts halved."""
        food1 = api("post", "/api/foods", self.h, json={"name": f"Flour-{uuid.uuid4().hex[:6]}"}).json()
        food2 = api("post", "/api/foods", self.h, json={"name": f"Sugar-{uuid.uuid4().hex[:6]}"}).json()
        unit = api("post", "/api/units", self.h, json={"name": f"g-{uuid.uuid4().hex[:6]}"}).json()

        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"Scale-{uuid.uuid4().hex[:6]}",
            "servings": 4,
            "steps": [{"order": 1, "instruction": "Mix", "ingredients": [
                {"food_id": food1["id"], "unit_id": unit["id"], "amount": 200, "order": 0},
                {"food_id": food2["id"], "unit_id": unit["id"], "amount": 100, "order": 1},
            ]}]
        }).json()

        sl = api("post", "/api/shopping-lists", self.h, json={"name": f"ScaleSL-{uuid.uuid4().hex[:6]}"}).json()

        # Add recipe with 2 servings (half of 4)
        r = api("post", f"/api/shopping-lists/{sl['id']}/add-recipe", self.h, json={
            "recipe_id": recipe["id"], "servings": 2
        })
        assert r.status_code == 200
        entries = r.json()["entries"]
        assert len(entries) == 2

        # Find flour and sugar entries
        flour_entry = next(e for e in entries if e["food_id"] == food1["id"])
        sugar_entry = next(e for e in entries if e["food_id"] == food2["id"])
        # 200 * (2/4) = 100
        assert abs(flour_entry["amount"] - 100.0) < 0.01
        # 100 * (2/4) = 50
        assert abs(sugar_entry["amount"] - 50.0) < 0.01


class TestShoppingListMerging:
    """Pattern 5: Same food+unit unchecked entries merge amounts."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_same_food_unit_merges(self):
        """Adding same food+unit twice merges into one entry with summed amount."""
        food = api("post", "/api/foods", self.h, json={"name": f"Mrg-{uuid.uuid4().hex[:6]}"}).json()
        unit = api("post", "/api/units", self.h, json={"name": f"MU-{uuid.uuid4().hex[:6]}"}).json()
        sl = api("post", "/api/shopping-lists", self.h, json={"name": f"MrgSL-{uuid.uuid4().hex[:6]}"}).json()

        # Add manually
        api("post", f"/api/shopping-lists/{sl['id']}/entries", self.h, json={
            "food_id": food["id"], "unit_id": unit["id"], "amount": 100
        })

        # Create recipe with same food+unit
        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"MrgR-{uuid.uuid4().hex[:6]}", "servings": 1,
            "steps": [{"order": 1, "instruction": "x", "ingredients": [
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 50}
            ]}]
        }).json()

        # Add recipe → should merge
        r = api("post", f"/api/shopping-lists/{sl['id']}/add-recipe", self.h, json={
            "recipe_id": recipe["id"], "servings": 1
        })
        assert r.status_code == 200
        entries = r.json()["entries"]
        # Should have just 1 entry with merged amount
        food_entries = [e for e in entries if e["food_id"] == food["id"]]
        assert len(food_entries) == 1
        assert abs(food_entries[0]["amount"] - 150.0) < 0.01

    def test_checked_entry_does_not_merge(self):
        """Checked entries should not be merged; new unchecked entry created."""
        food = api("post", "/api/foods", self.h, json={"name": f"Chk-{uuid.uuid4().hex[:6]}"}).json()
        unit = api("post", "/api/units", self.h, json={"name": f"CU-{uuid.uuid4().hex[:6]}"}).json()
        sl = api("post", "/api/shopping-lists", self.h, json={"name": f"ChkSL-{uuid.uuid4().hex[:6]}"}).json()

        # Add entry and check it
        entry = api("post", f"/api/shopping-lists/{sl['id']}/entries", self.h, json={
            "food_id": food["id"], "unit_id": unit["id"], "amount": 100
        }).json()
        api("put", f"/api/shopping-lists/{sl['id']}/entries/{entry['id']}", self.h, json={
            "checked": True
        })

        # Add recipe with same food+unit
        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"ChkR-{uuid.uuid4().hex[:6]}", "servings": 1,
            "steps": [{"order": 1, "instruction": "x", "ingredients": [
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 50}
            ]}]
        }).json()
        r = api("post", f"/api/shopping-lists/{sl['id']}/add-recipe", self.h, json={
            "recipe_id": recipe["id"], "servings": 1
        })
        entries = r.json()["entries"]
        # Should have 2 entries: one checked (100), one unchecked (50)
        food_entries = [e for e in entries if e["food_id"] == food["id"]]
        assert len(food_entries) == 2


class TestKeywordCascadeDelete:
    """Pattern 7: Deleting parent keyword cascades to children and removes from recipes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_delete_parent_cascades_children(self):
        """Delete parent → children and grandchildren also deleted."""
        parent = api("post", "/api/keywords", self.h, json={"name": f"GP-{uuid.uuid4().hex[:6]}"}).json()
        child = api("post", "/api/keywords", self.h, json={
            "name": f"GC-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]
        }).json()
        grandchild = api("post", "/api/keywords", self.h, json={
            "name": f"GGC-{uuid.uuid4().hex[:6]}", "parent_id": child["id"]
        }).json()

        # Create recipe with grandchild keyword
        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"GR-{uuid.uuid4().hex[:6]}", "servings": 1, "keyword_ids": [grandchild["id"]]
        }).json()
        assert len(recipe["keywords"]) == 1

        # Delete parent
        r = api("delete", f"/api/keywords/{parent['id']}", self.h)
        assert r.status_code == 204

        # Children should be gone
        assert api("get", f"/api/keywords/{child['id']}", self.h).status_code == 404
        assert api("get", f"/api/keywords/{grandchild['id']}", self.h).status_code == 404

        # Recipe should still exist but without the keyword
        recipe_now = api("get", f"/api/recipes/{recipe['id']}", self.h).json()
        assert len(recipe_now["keywords"]) == 0


class TestKeywordCircularPrevention:
    """Pattern 8: Cannot create circular keyword references."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_cannot_set_parent_to_self(self):
        kw = api("post", "/api/keywords", self.h, json={"name": f"Self-{uuid.uuid4().hex[:6]}"}).json()
        r = api("put", f"/api/keywords/{kw['id']}", self.h, json={
            "name": kw["name"], "parent_id": kw["id"]
        })
        assert r.status_code == 400

    def test_cannot_set_parent_to_descendant(self):
        parent = api("post", "/api/keywords", self.h, json={"name": f"Circ1-{uuid.uuid4().hex[:6]}"}).json()
        child = api("post", "/api/keywords", self.h, json={
            "name": f"Circ2-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]
        }).json()
        # Try to set parent's parent to child (circular)
        r = api("put", f"/api/keywords/{parent['id']}", self.h, json={
            "name": parent["name"], "parent_id": child["id"]
        })
        assert r.status_code == 400


class TestNutritionWorkflow:
    """Pattern 5: Complex nutrition computation with multiple foods and no_amount."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_nutrition_with_multiple_steps_and_no_amount(self):
        """
        2 steps, 3 ingredients (one no_amount). Verify computation is correct.
        """
        food1 = api("post", "/api/foods", self.h, json={
            "name": f"NW1-{uuid.uuid4().hex[:6]}",
            "calories_per_unit": 5.0, "protein_per_unit": 1.0,
            "fat_per_unit": 0.5, "carbs_per_unit": 2.0
        }).json()
        food2 = api("post", "/api/foods", self.h, json={
            "name": f"NW2-{uuid.uuid4().hex[:6]}",
            "calories_per_unit": 10.0, "protein_per_unit": 3.0,
            "fat_per_unit": 2.0, "carbs_per_unit": 4.0
        }).json()
        food3 = api("post", "/api/foods", self.h, json={
            "name": f"Salt-{uuid.uuid4().hex[:6]}",
            "calories_per_unit": 0, "protein_per_unit": 0,
            "fat_per_unit": 0, "carbs_per_unit": 0
        }).json()
        unit = api("post", "/api/units", self.h, json={"name": f"nwu-{uuid.uuid4().hex[:6]}"}).json()

        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"NWR-{uuid.uuid4().hex[:6]}", "servings": 2,
            "steps": [
                {"order": 1, "instruction": "Step1", "ingredients": [
                    {"food_id": food1["id"], "unit_id": unit["id"], "amount": 100, "order": 0},
                    {"food_id": food3["id"], "unit_id": unit["id"], "amount": 0, "no_amount": True, "order": 1},
                ]},
                {"order": 2, "instruction": "Step2", "ingredients": [
                    {"food_id": food2["id"], "unit_id": unit["id"], "amount": 50, "order": 0},
                ]}
            ]
        }).json()

        n = api("get", f"/api/recipes/{recipe['id']}/nutrition", self.h).json()
        # food1: 100*5=500, food2: 50*10=500, food3 (no_amount): 0 → total cal=1000, per serving=500
        assert abs(n["calories"] - 500.0) < 0.01
        # protein: 100*1 + 50*3 = 250, /2 = 125
        assert abs(n["protein"] - 125.0) < 0.01
        # fat: 100*0.5 + 50*2 = 150, /2 = 75
        assert abs(n["fat"] - 75.0) < 0.01
        # carbs: 100*2 + 50*4 = 400, /2 = 200
        assert abs(n["carbs"] - 200.0) < 0.01


class TestImportUrlWorkflow:
    """Pattern 5: Import URL creates a recipe with expected structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_import_url_creates_recipe(self):
        url = f"https://example.com/recipe-{uuid.uuid4().hex[:8]}"
        r = api("post", "/api/import/url", self.h, json={"url": url})
        assert r.status_code == 201
        recipe = r.json()
        assert recipe["name"] == "Imported Recipe"
        assert recipe["servings"] == 4
        assert recipe["working_time"] == 30
        assert recipe["waiting_time"] == 0
        assert len(recipe["steps"]) == 1
        assert url in recipe["steps"][0]["instruction"]


class TestRecipeSearchWorkflow:
    """Pattern 3: Search by name actually filters."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_search_by_name(self):
        tag = uuid.uuid4().hex[:8]
        api("post", "/api/recipes", self.h, json={"name": f"FindMe-{tag}", "servings": 1})
        api("post", "/api/recipes", self.h, json={"name": f"Other-{uuid.uuid4().hex[:6]}", "servings": 1})

        r = api("get", "/api/recipes", self.h, params={"search": tag})
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) >= 1
        assert any(tag in rec["name"] for rec in results)


class TestRecipeExportWorkflow:
    """Pattern 2: Export includes full recipe with steps and ingredients."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_export_includes_full_data(self):
        food = api("post", "/api/foods", self.h, json={"name": f"ExF-{uuid.uuid4().hex[:6]}"}).json()
        unit = api("post", "/api/units", self.h, json={"name": f"ExU-{uuid.uuid4().hex[:6]}"}).json()
        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"ExR-{uuid.uuid4().hex[:6]}", "servings": 3,
            "steps": [{"order": 1, "instruction": "Export step", "ingredients": [
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 75}
            ]}]
        }).json()

        r = api("get", f"/api/recipes/{recipe['id']}/export", self.h)
        assert r.status_code == 200
        export = r.json()
        assert "version" in export
        assert "exported_at" in export
        assert "recipe" in export
        rec = export["recipe"]
        assert rec["id"] == recipe["id"]
        assert rec["servings"] == 3
        assert len(rec["steps"]) == 1
        assert len(rec["steps"][0]["ingredients"]) == 1
        assert rec["steps"][0]["ingredients"][0]["amount"] == 75


class TestMealPlanWorkflow:
    """Pattern 1+3: Meal plan CRUD and date filtering."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_meal_plan_full_lifecycle(self):
        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"MPR-{uuid.uuid4().hex[:6]}", "servings": 2
        }).json()

        # Create
        mp = api("post", "/api/meal-plans", self.h, json={
            "date": "2024-12-25", "meal_type": "dinner",
            "recipe_id": recipe["id"], "servings": 4, "title": "Christmas Dinner"
        }).json()
        assert mp["date"] == "2024-12-25"
        assert mp["meal_type"] == "dinner"
        assert mp["recipe_id"] == recipe["id"]
        assert mp["servings"] == 4
        assert mp["title"] == "Christmas Dinner"

        # Get
        r = api("get", f"/api/meal-plans/{mp['id']}", self.h)
        assert r.status_code == 200
        assert r.json()["id"] == mp["id"]

        # Update
        r = api("put", f"/api/meal-plans/{mp['id']}", self.h, json={
            "date": "2024-12-25", "meal_type": "lunch", "servings": 6, "title": "Updated"
        })
        assert r.status_code == 200
        assert r.json()["meal_type"] == "lunch"
        assert r.json()["servings"] == 6

        # Delete
        r = api("delete", f"/api/meal-plans/{mp['id']}", self.h)
        assert r.status_code == 204
        assert api("get", f"/api/meal-plans/{mp['id']}", self.h).status_code == 404


class TestShoppingListHeaderExcluded:
    """Pattern 5: Header ingredients excluded from shopping list generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_header_ingredients_not_added_to_list(self):
        food = api("post", "/api/foods", self.h, json={"name": f"HdrF-{uuid.uuid4().hex[:6]}"}).json()
        unit = api("post", "/api/units", self.h, json={"name": f"HdrU-{uuid.uuid4().hex[:6]}"}).json()

        recipe = api("post", "/api/recipes", self.h, json={
            "name": f"HdrR-{uuid.uuid4().hex[:6]}", "servings": 1,
            "steps": [{"order": 1, "instruction": "Do", "ingredients": [
                {"is_header": True, "note": "For the sauce", "order": 0},
                {"food_id": food["id"], "unit_id": unit["id"], "amount": 100, "order": 1},
            ]}]
        }).json()

        sl = api("post", "/api/shopping-lists", self.h, json={"name": f"HdrSL-{uuid.uuid4().hex[:6]}"}).json()
        r = api("post", f"/api/shopping-lists/{sl['id']}/add-recipe", self.h, json={
            "recipe_id": recipe["id"], "servings": 1
        })
        assert r.status_code == 200
        entries = r.json()["entries"]
        # Only the non-header ingredient should be added
        assert len(entries) == 1
        assert entries[0]["food_id"] == food["id"]
        assert entries[0]["amount"] == 100
