"""
BackendForge — L3 Workflow Tests for Mealie Task

Multi-step adversarial workflows that cross multiple entity types.
Each test targets 2+ LLM bug patterns and includes side-effect verification.

"""

import os
import uuid
import datetime

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
GROUP_ID = "00000000-0000-0000-0000-200000000001"
HOUSEHOLD_ID = "00000000-0000-0000-0000-200000000002"
USER_ID = "00000000-0000-0000-0000-200000000003"
USER_ID_2 = "00000000-0000-0000-0000-200000000004"
USER_ID_3 = "00000000-0000-0000-0000-200000000005"

HEADERS = {
    "X-Group-Id": GROUP_ID,
    "X-User-Id": USER_ID,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-Group-Id": GROUP_ID,
    "X-User-Id": USER_ID_2,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

HEADERS_USER3 = {
    "X-Group-Id": GROUP_ID,
    "X-User-Id": USER_ID_3,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

W = uuid.uuid4().hex[:6]


def _reset_test_context():
    """Give every test fresh group, household, and user identities."""
    global GROUP_ID, HOUSEHOLD_ID, USER_ID, USER_ID_2, USER_ID_3
    global HEADERS, HEADERS_USER2, HEADERS_USER3, W

    GROUP_ID = str(uuid.uuid4())
    HOUSEHOLD_ID = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    USER_ID_2 = str(uuid.uuid4())
    USER_ID_3 = str(uuid.uuid4())
    HEADERS = {
        "X-Group-Id": GROUP_ID,
        "X-User-Id": USER_ID,
        "X-Household-Id": HOUSEHOLD_ID,
        "Content-Type": "application/json",
    }
    HEADERS_USER2 = {
        "X-Group-Id": GROUP_ID,
        "X-User-Id": USER_ID_2,
        "X-Household-Id": HOUSEHOLD_ID,
        "Content-Type": "application/json",
    }
    HEADERS_USER3 = {
        "X-Group-Id": GROUP_ID,
        "X-User-Id": USER_ID_3,
        "X-Household-Id": HOUSEHOLD_ID,
        "Content-Type": "application/json",
    }
    W = uuid.uuid4().hex[:6]


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def _utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date()


# ── HTTP Helpers ──

def get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def patch(path, json_data=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def delete(path, params=None, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ── Domain Helpers ──

def make_recipe(name):
    r = post("/api/recipes", {"name": name})
    assert r.status_code == 201, f"Create recipe failed: {r.status_code} {r.text}"
    result = r.json()
    return result if isinstance(result, str) else result.get("slug", result.get("id", str(result)))


def get_recipe(slug):
    r = get(f"/api/recipes/{slug}")
    assert r.status_code == 200
    return r.json()


def make_food(name):
    r = post("/api/foods", {"name": name})
    assert r.status_code == 201
    return r.json()


def make_unit(name, abbreviation=""):
    r = post("/api/units", {"name": name, "abbreviation": abbreviation})
    assert r.status_code == 201
    return r.json()


def make_shopping_list(name):
    r = post("/api/households/shopping/lists", {"name": name})
    assert r.status_code == 201
    return r.json()


def get_shopping_list(list_id):
    r = get(f"/api/households/shopping/lists/{list_id}")
    assert r.status_code == 200
    return r.json()


# ════════════════════════════════════════════════════════════════════
# L3 Tests — Multi-step Workflows (10-15 tests)
# ════════════════════════════════════════════════════════════════════


class TestShoppingMergeWorkflow:
    """
    Full shopping list merge workflow.
    Patterns: 1 (camelCase), 5 (merge logic), 10 (checked items).
    """

    def test_shopping_merge_full_lifecycle(self):
        """
        1. Create shopping list
        2. Add item A (food=flour, unit=cups, qty=2)
        3. Add item B (food=flour, unit=cups, qty=3) → merged into A (qty=5)
        4. Add item C (food=sugar, qty=1)
        5. Verify: 2 items total (flour=5, sugar=1)
        6. Check the flour item
        7. Add item D (food=flour, unit=cups, qty=1) → NEW item (checked doesn't merge)
        8. Verify: 3 items total (flour-checked=5, flour-unchecked=1, sugar=1)
        """
        food_flour = make_food(f"flour-{W}-smw")
        food_sugar = make_food(f"sugar-{W}-smw")
        unit_cups = make_unit(f"cups-{W}-smw")
        sl = make_shopping_list(f"MergeWF-{W}")

        # Step 2: Add flour qty=2
        r = post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food_flour["id"],
            "unitId": unit_cups["id"], "quantity": 2, "checked": False,
        })
        assert r.status_code == 201

        # Step 3: Add flour qty=3 → should merge
        r = post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food_flour["id"],
            "unitId": unit_cups["id"], "quantity": 3, "checked": False,
        })
        assert r.status_code == 201
        data = r.json()
        # Should be an update (merge), not a new creation
        assert len(data.get("updatedItems", [])) >= 1 or len(data.get("createdItems", [])) == 0, \
            "Second add should merge (update), not create new"

        # Step 4: Add sugar
        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food_sugar["id"],
            "quantity": 1, "checked": False,
        })

        # Step 5: Verify state
        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        flour_items = [i for i in items if i.get("foodId") == food_flour["id"]]
        sugar_items = [i for i in items if i.get("foodId") == food_sugar["id"]]

        assert len(flour_items) == 1, f"Flour should be merged into 1, got {len(flour_items)}"
        assert flour_items[0]["quantity"] == 5
        assert len(sugar_items) == 1
        assert sugar_items[0]["quantity"] == 1

        # Step 6: Check the flour item
        flour_item_id = flour_items[0]["id"]
        r = put(f"/api/households/shopping/items/{flour_item_id}", {
            **flour_items[0], "checked": True, "shoppingListId": sl["id"],
        })
        assert r.status_code == 200

        # Step 7: Add MORE flour (same food+unit) → should NOT merge with checked
        r = post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food_flour["id"],
            "unitId": unit_cups["id"], "quantity": 1, "checked": False,
        })
        assert r.status_code == 201

        # Step 8: Verify final state
        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        flour_items = [i for i in items if i.get("foodId") == food_flour["id"]]

        assert len(flour_items) == 2, \
            f"Should have 2 flour items (1 checked + 1 unchecked), got {len(flour_items)}"
        checked_flour = [i for i in flour_items if i.get("checked")]
        unchecked_flour = [i for i in flour_items if not i.get("checked")]
        assert len(checked_flour) == 1
        assert checked_flour[0]["quantity"] == 5
        assert len(unchecked_flour) == 1
        assert unchecked_flour[0]["quantity"] == 1


class TestRecipeToShoppingListWorkflow:
    """
    Recipe → Shopping list integration workflow.
    Patterns: 2 (nested data), 5 (merge logic), 7 (cascade/side-effects).
    """

    def test_recipe_to_shopping_list_full_flow(self):
        """
        1. Create recipe with 3 ingredients
        2. Create shopping list
        3. Add recipe to shopping list → 3 items created
        4. Verify each item has recipeReference
        5. Verify quantities match recipe ingredient quantities
        6. Remove recipe → items at qty 0 should be deleted
        7. Verify list is empty after full removal
        """
        foods = [make_food(f"food-{W}-rsl-{i}") for i in range(3)]
        unit = make_unit(f"unit-{W}-rsl")

        slug = make_recipe(f"RSLRecipe-{W}")
        recipe = get_recipe(slug)
        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": f["id"], "name": f["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": (i + 1) * 2,  # 2, 4, 6
                    "note": f"ingredient {i}",
                }
                for i, f in enumerate(foods)
            ],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = make_shopping_list(f"RSL-{W}")

        # Step 3: Add recipe
        r = post(f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
                 {"recipeId": recipe_id})
        assert r.status_code == 200

        # Step 4: Verify items and references
        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        assert len(items) >= 3, f"Expected 3+ items from recipe, got {len(items)}"

        for item in items:
            refs = item.get("recipeReferences", [])
            ref_recipe_ids = [ref.get("recipeId") for ref in refs]
            assert recipe_id in ref_recipe_ids, \
                f"Item {item['id']} missing recipe reference"

        # Step 5: Verify quantities
        for i, food in enumerate(foods):
            food_items = [it for it in items if it.get("foodId") == food["id"]]
            assert len(food_items) == 1
            expected_qty = (i + 1) * 2
            assert food_items[0]["quantity"] == expected_qty, \
                f"Food {i} qty should be {expected_qty}, got {food_items[0]['quantity']}"

        # Step 6: Remove recipe → items should be deleted
        r = post(f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}/delete",
                 {"recipeDecrementQuantity": 1})
        assert r.status_code == 200

        # Step 7: Verify all items removed (qty hit 0, no other refs)
        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        remaining = [i for i in items if i.get("foodId") in [f["id"] for f in foods]]
        assert len(remaining) == 0, \
            f"All items should be deleted after removal, got {len(remaining)}"


class TestMultiUserRatingAggregation:
    """
    Multi-user rating aggregation workflow.
    Patterns: 1 (camelCase), 5 (business logic - average calculation).
    """

    def test_multi_user_rating_lifecycle(self):
        """
        1. Create recipe
        2. User1 rates 4.0 → recipe.rating = 4.0
        3. User2 rates 2.0 → recipe.rating = 3.0
        4. User3 rates 3.0 → recipe.rating = 3.0
        5. User1 changes to 5.0 → recipe.rating = (5+2+3)/3 = 3.333
        6. User2 changes to 5.0 → recipe.rating = (5+5+3)/3 = 4.333
        7. Verify via self ratings endpoint (camelCase)
        """
        slug = make_recipe(f"MultiRate-{W}")

        # Step 2: User1 rates 4.0
        r = post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 4.0})
        assert r.status_code == 200
        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(4.0, abs=0.1)

        # Step 3: User2 rates 2.0
        r = post(f"/api/users/{USER_ID_2}/ratings/{slug}", {"rating": 2.0}, headers=HEADERS_USER2)
        assert r.status_code == 200
        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(3.0, abs=0.1), \
            f"Expected (4+2)/2=3.0, got {recipe.get('rating')}"

        # Step 4: User3 rates 3.0
        r = post(f"/api/users/{USER_ID_3}/ratings/{slug}", {"rating": 3.0}, headers=HEADERS_USER3)
        assert r.status_code == 200
        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(3.0, abs=0.1), \
            f"Expected (4+2+3)/3=3.0, got {recipe.get('rating')}"

        # Step 5: User1 changes to 5.0
        r = post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 5.0})
        assert r.status_code == 200
        recipe = get_recipe(slug)
        expected = (5.0 + 2.0 + 3.0) / 3
        assert recipe.get("rating") == pytest.approx(expected, abs=0.1), \
            f"Expected {expected:.2f}, got {recipe.get('rating')}"

        # Step 6: User2 changes to 5.0
        r = post(f"/api/users/{USER_ID_2}/ratings/{slug}", {"rating": 5.0}, headers=HEADERS_USER2)
        assert r.status_code == 200
        recipe = get_recipe(slug)
        expected = (5.0 + 5.0 + 3.0) / 3
        assert recipe.get("rating") == pytest.approx(expected, abs=0.1), \
            f"Expected {expected:.2f}, got {recipe.get('rating')}"

        # Step 7: Verify self rating (camelCase check)
        r = get(f"/api/users/self/ratings/{recipe['id']}")
        assert r.status_code == 200
        data = r.json()
        assert "recipeId" in data, f"Self rating must have 'recipeId'. Keys: {list(data.keys())}"
        assert data["rating"] == pytest.approx(5.0, abs=0.1)


class TestCookbookRecipeFilterWorkflow:
    """
    Cookbook + recipe category filtering workflow.
    Patterns: 3 (filter params applied), 5 (business logic).
    """

    def test_cookbook_filter_lifecycle(self):
        """
        1. Create 2 categories
        2. Create 3 recipes: A→cat1, B→cat2, C→no category
        3. Create cookbook filtering cat1
        4. Query via cookbook → only recipe A
        5. Update cookbook to filter cat2
        6. Query via cookbook → only recipe B
        7. Verify recipe C never appears
        """
        cat1_name = f"Italian-{W}-cbw"
        cat2_name = f"Mexican-{W}-cbw"

        r = post("/api/organizers/categories", {"name": cat1_name})
        assert r.status_code == 201
        cat1 = r.json()
        r = post("/api/organizers/categories", {"name": cat2_name})
        assert r.status_code == 201
        cat2 = r.json()

        # Create recipes with categories
        slug_a = make_recipe(f"ItalianDish-{W}")
        recipe_a = get_recipe(slug_a)
        put(f"/api/recipes/{slug_a}", {**recipe_a, "recipeCategory": [{"id": cat1["id"], "name": cat1_name}]})

        slug_b = make_recipe(f"MexicanDish-{W}")
        recipe_b = get_recipe(slug_b)
        put(f"/api/recipes/{slug_b}", {**recipe_b, "recipeCategory": [{"id": cat2["id"], "name": cat2_name}]})

        slug_c = make_recipe(f"PlainDish-{W}")

        # Step 3: Create cookbook with cat1 filter
        cb_id = str(uuid.uuid4())
        r = post("/api/households/cookbooks", {
            "name": f"ItalianCB-{W}",
            "id": cb_id,
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat1["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat1["id"]],
                }]
            },
        })
        assert r.status_code == 201
        cb = r.json()

        # Step 4: Query via cookbook
        r = get("/api/recipes", params={"cookbook": cb["id"], "perPage": 100})
        assert r.status_code == 200
        slugs = [item["slug"] for item in r.json().get("items", [])]
        assert slug_a in slugs, f"Recipe A (cat1) should appear. Got: {slugs}"
        assert slug_b not in slugs, "Recipe B (cat2) should NOT appear"
        assert slug_c not in slugs, "Recipe C (no cat) should NOT appear"

        # Step 5: Update cookbook to cat2
        r = put(f"/api/households/cookbooks/{cb['id']}", {
            **cb,
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat2["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat2["id"]],
                }]
            },
        })
        assert r.status_code == 200

        # Step 6: Query again
        r = get("/api/recipes", params={"cookbook": cb["id"], "perPage": 100})
        slugs = [item["slug"] for item in r.json().get("items", [])]
        assert slug_b in slugs, f"After update, recipe B should appear. Got: {slugs}"
        assert slug_a not in slugs, "After update, recipe A should NOT appear"
        assert slug_c not in slugs, "Recipe C should still NOT appear"


class TestFoodMergeWorkflow:
    """
    Food merge → recipe ingredient references updated.
    Patterns: 2 (nested data), 7 (cascade/side-effects).
    """

    def test_food_merge_updates_all_references(self):
        """
        1. Create food_a and food_b
        2. Create recipe1 with ingredient referencing food_a
        3. Create recipe2 with ingredient referencing food_a
        4. Merge food_a → food_b
        5. Verify recipe1 now references food_b
        6. Verify recipe2 now references food_b
        7. Verify food_a is deleted (404)
        8. Verify food_b still exists
        """
        food_a = make_food(f"foodA-{W}-fm")
        food_b = make_food(f"foodB-{W}-fm")
        unit = make_unit(f"unit-{W}-fm")

        # Recipe 1 with food_a
        slug1 = make_recipe(f"FoodMergeR1-{W}")
        recipe1 = get_recipe(slug1)
        put(f"/api/recipes/{slug1}", {
            **recipe1,
            "recipeIngredient": [{
                "food": {"id": food_a["id"], "name": food_a["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 2, "note": "recipe1",
            }],
        })

        # Recipe 2 with food_a
        slug2 = make_recipe(f"FoodMergeR2-{W}")
        recipe2 = get_recipe(slug2)
        put(f"/api/recipes/{slug2}", {
            **recipe2,
            "recipeIngredient": [{
                "food": {"id": food_a["id"], "name": food_a["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 5, "note": "recipe2",
            }],
        })

        # Verify both reference food_a
        r1 = get_recipe(slug1)
        r2 = get_recipe(slug2)
        assert r1["recipeIngredient"][0]["food"]["id"] == food_a["id"]
        assert r2["recipeIngredient"][0]["food"]["id"] == food_a["id"]

        # Step 4: Merge food_a → food_b
        r = put("/api/foods/merge", {"fromFood": food_a["id"], "toFood": food_b["id"]})
        assert r.status_code == 200

        # Step 5-6: Both recipes now reference food_b
        r1 = get_recipe(slug1)
        r2 = get_recipe(slug2)

        r1_food_ids = [ing.get("food", {}).get("id") for ing in r1.get("recipeIngredient", []) if ing.get("food")]
        r2_food_ids = [ing.get("food", {}).get("id") for ing in r2.get("recipeIngredient", []) if ing.get("food")]

        assert food_b["id"] in r1_food_ids, f"Recipe1 should reference food_b after merge"
        assert food_a["id"] not in r1_food_ids, f"Recipe1 should NOT reference food_a after merge"
        assert food_b["id"] in r2_food_ids, f"Recipe2 should reference food_b after merge"
        assert food_a["id"] not in r2_food_ids

        # Step 7: food_a deleted
        r = get(f"/api/foods/{food_a['id']}")
        assert r.status_code == 404, f"food_a should be 404 after merge, got {r.status_code}"

        # Step 8: food_b still exists
        r = get(f"/api/foods/{food_b['id']}")
        assert r.status_code == 200


class TestFullRecipeLifecycle:
    """
    Full recipe lifecycle with nested data.
    Patterns: 1 (camelCase), 2 (nested data), 4 (status codes), 7 (side-effects).
    """

    def test_create_update_duplicate_verify_isolation(self):
        """
        1. Create recipe
        2. Add ingredients + tags + categories
        3. Verify all nested data present
        4. Duplicate recipe → 201
        5. Verify clone has ALL nested data
        6. Update clone (change description)
        7. Verify ORIGINAL is unchanged
        """
        food = make_food(f"chicken-{W}-lc")
        unit = make_unit(f"pounds-{W}-lc")
        tag_name = f"Dinner-{W}-lc"
        cat_name = f"Poultry-{W}-lc"

        # Step 1-2
        slug = make_recipe(f"Lifecycle-{W}")
        recipe = get_recipe(slug)
        put(f"/api/recipes/{slug}", {
            **recipe,
            "description": "Original description",
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 2, "note": "boneless",
            }],
            "recipeInstructions": [
                {"text": "Season chicken."},
                {"text": "Grill for 8 minutes."},
            ],
            "tags": [{"name": tag_name}],
            "recipeCategory": [{"name": cat_name}],
        })

        # Step 3: Verify nested data
        recipe = get_recipe(slug)
        assert len(recipe.get("recipeIngredient", [])) == 1
        assert len(recipe.get("recipeInstructions", [])) == 2
        assert len(recipe.get("tags", [])) >= 1
        assert len(recipe.get("recipeCategory", [])) >= 1
        assert recipe["description"] == "Original description"

        # Step 4: Duplicate
        r = post(f"/api/recipes/{slug}/duplicate", {"name": f"Clone-{W}"})
        assert r.status_code == 201, f"Duplicate should return 201, got {r.status_code}"
        dup = r.json()
        dup_slug = dup["slug"] if isinstance(dup, dict) else dup

        # Step 5: Clone has all nested data
        clone = get_recipe(dup_slug)
        assert len(clone.get("recipeIngredient", [])) == 1, \
            f"Clone should have 1 ingredient, got {len(clone.get('recipeIngredient', []))}"
        assert len(clone.get("recipeInstructions", [])) == 2, \
            f"Clone should have 2 instructions"
        assert len(clone.get("tags", [])) >= 1, "Clone should have tags"
        assert len(clone.get("recipeCategory", [])) >= 1, "Clone should have categories"

        # Step 6: Update clone
        put(f"/api/recipes/{dup_slug}", {**clone, "description": "Updated clone description"})
        clone = get_recipe(dup_slug)
        assert clone["description"] == "Updated clone description"

        # Step 7: Original unchanged
        original = get_recipe(slug)
        assert original["description"] == "Original description", \
            f"Original description changed! Got: {original['description']}"


class TestUnitMergeWorkflow:
    """
    Unit merge → recipe ingredient references updated.
    Patterns: 7 (cascade), 5 (business logic).
    """

    def test_unit_merge_updates_recipe_references(self):
        """
        1. Create unit_a and unit_b
        2. Create recipe with ingredient using unit_a
        3. Merge unit_a → unit_b
        4. Verify recipe now uses unit_b
        5. Verify unit_a is 404
        """
        unit_a = make_unit(f"unitA-{W}-um")
        unit_b = make_unit(f"unitB-{W}-um")
        food = make_food(f"food-{W}-um")

        slug = make_recipe(f"UnitMerge-{W}")
        recipe = get_recipe(slug)
        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit_a["id"], "name": unit_a["name"]},
                "quantity": 3, "note": "test",
            }],
        })

        # Verify uses unit_a
        recipe = get_recipe(slug)
        assert recipe["recipeIngredient"][0]["unit"]["id"] == unit_a["id"]

        # Merge
        r = put("/api/units/merge", {"fromUnit": unit_a["id"], "toUnit": unit_b["id"]})
        assert r.status_code == 200

        # Verify uses unit_b
        recipe = get_recipe(slug)
        unit_ids = [ing.get("unit", {}).get("id") for ing in recipe.get("recipeIngredient", []) if ing.get("unit")]
        assert unit_b["id"] in unit_ids, f"After merge, should use unit_b. Got: {unit_ids}"
        assert unit_a["id"] not in unit_ids

        # unit_a is deleted
        r = get(f"/api/units/{unit_a['id']}")
        assert r.status_code == 404


class TestTagDeduplicationWorkflow:
    """
    Tag deduplication across recipes.
    Patterns: 5 (business logic), 7 (side-effects).
    """

    def test_tag_dedup_multiple_recipes(self):
        """
        1. Create recipe A with tag "QuickMeals"
        2. Create recipe B with tag "QuickMeals" (same name)
        3. Verify only ONE tag exists in the system
        4. Both recipes reference the SAME tag id
        5. Query tag by slug → both recipes listed
        """
        tag_name = f"QuickMeals-{W}"

        slug_a = make_recipe(f"TagDedupA-{W}")
        recipe_a = get_recipe(slug_a)
        put(f"/api/recipes/{slug_a}", {**recipe_a, "tags": [{"name": tag_name}]})

        slug_b = make_recipe(f"TagDedupB-{W}")
        recipe_b = get_recipe(slug_b)
        put(f"/api/recipes/{slug_b}", {**recipe_b, "tags": [{"name": tag_name}]})

        # Step 3: Only one tag
        r = get("/api/organizers/tags", params={"search": tag_name, "perPage": 100})
        assert r.status_code == 200
        tags = [t for t in r.json().get("items", []) if t.get("name") == tag_name]
        assert len(tags) == 1, f"Expected 1 tag '{tag_name}', got {len(tags)}"

        tag_id = tags[0]["id"]
        tag_slug = tags[0]["slug"]

        # Step 4: Both recipes share same tag id
        ra = get_recipe(slug_a)
        rb = get_recipe(slug_b)
        a_tag_ids = [t["id"] for t in ra.get("tags", []) if t["name"] == tag_name]
        b_tag_ids = [t["id"] for t in rb.get("tags", []) if t["name"] == tag_name]
        assert a_tag_ids == [tag_id], f"Recipe A tag id mismatch: {a_tag_ids} != [{tag_id}]"
        assert b_tag_ids == [tag_id], f"Recipe B tag id mismatch: {b_tag_ids} != [{tag_id}]"

        # Step 5: Tag slug lookup shows both recipes
        r = get(f"/api/organizers/tags/slug/{tag_slug}")
        assert r.status_code == 200
        tag_data = r.json()
        recipe_slugs = [rec.get("slug") for rec in tag_data.get("recipes", [])]
        assert slug_a in recipe_slugs, f"Tag lookup should include recipe A"
        assert slug_b in recipe_slugs, f"Tag lookup should include recipe B"


class TestMealPlanRandomWithRules:
    """
    Meal plan random respects rules.
    Patterns: 1 (camelCase), 5 (business logic applied).
    """

    def test_random_meal_plan_uses_rules(self):
        """
        1. Create tag "Comfort"
        2. Create recipe A WITH tag
        3. Create recipe B WITHOUT tag
        4. Create rule: wednesday + dinner → require "Comfort" tag
        5. Request random for wednesday dinner
        6. Verify result has recipeId pointing to recipe A
        7. Verify response uses camelCase (recipeId, entryType)
        """
        tag_name = f"Comfort-{W}"
        r = post("/api/organizers/tags", {"name": tag_name})
        assert r.status_code == 201
        tag = r.json()

        slug_a = make_recipe(f"ComfortFood-{W}")
        recipe_a = get_recipe(slug_a)
        put(f"/api/recipes/{slug_a}", {**recipe_a, "tags": [{"id": tag["id"], "name": tag_name}]})
        recipe_a = get_recipe(slug_a)

        slug_b = make_recipe(f"NoComfort-{W}")

        # Create rule
        rule_id = str(uuid.uuid4())
        r = post("/api/households/mealplans/rules", {
            "day": "wednesday",
            "entryType": "dinner",
            "id": rule_id,
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "queryFilterString": f'tags.id CONTAINS_ANY ["{tag["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "tags.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [tag["id"]],
                }]
            },
        })
        assert r.status_code == 201

        # Find next wednesday
        today = _utc_today()
        days_ahead = 2 - today.weekday()  # 2 = wednesday
        if days_ahead <= 0:
            days_ahead += 7
        wednesday = (today + datetime.timedelta(days=days_ahead)).isoformat()

        # Request random
        r = post("/api/households/mealplans/random", {"date": wednesday, "entryType": "dinner"})
        assert r.status_code == 200
        plan = r.json()

        # camelCase check
        assert "recipeId" in plan, f"Missing 'recipeId'. Keys: {list(plan.keys())}"
        assert "entryType" in plan, f"Missing 'entryType'. Keys: {list(plan.keys())}"
        assert "recipe_id" not in plan
        assert "entry_type" not in plan

        # Should pick recipe A (the one with the tag)
        assert plan["recipeId"] == recipe_a["id"], \
            f"Random should pick recipe A ({recipe_a['id']}), got {plan['recipeId']}"


class TestRecipeSearchAndSort:
    """
    Search + sort combined workflow.
    Patterns: 3 (params actually applied).
    """

    def test_search_combined_with_sort(self):
        """
        1. Create recipes: "Zeta Soup", "Alpha Soup", "Mu Soup"
        2. Search for "Soup" with sort by name asc
        3. Verify results are sorted: Alpha, Mu, Zeta
        4. Search with sort desc
        5. Verify order reversed: Zeta, Mu, Alpha
        """
        prefix = f"SrchSort-{W}"
        names = [f"Zeta {prefix}", f"Alpha {prefix}", f"Mu {prefix}"]
        for n in names:
            make_recipe(n)

        # Sort asc
        r = get("/api/recipes", params={
            "search": prefix, "orderBy": "name", "orderDirection": "asc", "perPage": 100,
        })
        assert r.status_code == 200
        items = r.json().get("items", [])
        result_names = [item["name"] for item in items]
        assert len(result_names) >= 3, f"Expected 3+ results, got {len(result_names)}"
        assert result_names == sorted(result_names, key=str.lower), \
            f"Not sorted asc: {result_names}"

        # Sort desc
        r = get("/api/recipes", params={
            "search": prefix, "orderBy": "name", "orderDirection": "desc", "perPage": 100,
        })
        items = r.json().get("items", [])
        result_names = [item["name"] for item in items]
        assert result_names == sorted(result_names, key=str.lower, reverse=True), \
            f"Not sorted desc: {result_names}"


class TestFavoriteAndRatingWorkflow:
    """
    Favorite + rating combined workflow.
    Patterns: 1 (camelCase), 5 (business logic).
    """

    def test_favorite_and_rating_lifecycle(self):
        """
        1. Create recipe
        2. Add as favorite → verify in favorites list
        3. Rate recipe 5.0
        4. Verify self rating has isFavorite=True AND rating=5.0
        5. Remove favorite
        6. Verify removed from favorites but rating preserved
        """
        slug = make_recipe(f"FavRate-{W}")
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        # Step 2: Add favorite
        r = post(f"/api/users/{USER_ID}/favorites/{slug}", {})
        assert r.status_code == 200

        r = get(f"/api/users/{USER_ID}/favorites")
        assert r.status_code == 200
        favs = r.json()
        assert "ratings" in favs
        fav_recipe_ids = [f.get("recipeId") for f in favs["ratings"]]
        assert recipe_id in fav_recipe_ids, "Recipe should be in favorites"

        # Step 3: Rate 5.0
        r = post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 5.0})
        assert r.status_code == 200

        # Step 4: Self rating check
        r = get(f"/api/users/self/ratings/{recipe_id}")
        assert r.status_code == 200
        data = r.json()
        assert "recipeId" in data, f"Missing 'recipeId'. Keys: {list(data.keys())}"
        assert "isFavorite" in data, f"Missing 'isFavorite'. Keys: {list(data.keys())}"
        assert data["isFavorite"] == True
        assert data["rating"] == pytest.approx(5.0, abs=0.1)

        # Step 5: Remove favorite
        r = delete(f"/api/users/{USER_ID}/favorites/{slug}")
        assert r.status_code == 200

        # Step 6: Not in favorites, but rating preserved
        r = get(f"/api/users/{USER_ID}/favorites")
        fav_recipe_ids = [f.get("recipeId") for f in r.json().get("ratings", [])]
        assert recipe_id not in fav_recipe_ids, "Should be removed from favorites"

        r = get(f"/api/users/self/ratings/{recipe_id}")
        data = r.json()
        assert data.get("rating") == pytest.approx(5.0, abs=0.1), \
            "Rating should be preserved after removing favorite"


class TestRecipeCommentWorkflow:
    """
    Recipe + comment lifecycle.
    Patterns: 1 (camelCase), 2 (nested relationships).
    """

    def test_recipe_comments_workflow(self):
        """
        1. Create recipe
        2. Add 2 comments
        3. GET /api/recipes/{slug}/comments → 2 comments
        4. Verify comment fields (recipeId, text, userId)
        5. Update one comment
        6. Delete one comment
        7. Verify only 1 remains
        """
        slug = make_recipe(f"Comments-{W}")
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        # Step 2: Add comments
        r1 = post("/api/comments", {"recipeId": recipe_id, "text": f"Comment 1 {W}"})
        assert r1.status_code == 201
        comment1 = r1.json()

        r2 = post("/api/comments", {"recipeId": recipe_id, "text": f"Comment 2 {W}"})
        assert r2.status_code == 201
        comment2 = r2.json()

        # Step 3: GET recipe comments
        r = get(f"/api/recipes/{slug}/comments")
        assert r.status_code == 200
        comments = r.json()
        assert isinstance(comments, list)
        assert len(comments) >= 2

        # Step 4: Verify fields (camelCase)
        assert "recipeId" in comment1, f"Missing 'recipeId'. Keys: {list(comment1.keys())}"
        assert "recipe_id" not in comment1, "Should be 'recipeId' not 'recipe_id'"
        assert comment1["recipeId"] == recipe_id

        # Step 5: Update
        r = put(f"/api/comments/{comment1['id']}", {"id": comment1["id"], "text": "Updated text"})
        assert r.status_code == 200
        assert r.json()["text"] == "Updated text"

        # Step 6: Delete
        r = delete(f"/api/comments/{comment2['id']}")
        assert r.status_code == 200

        # Step 7: Only 1 remains
        r = get(f"/api/recipes/{slug}/comments")
        remaining = r.json()
        assert len(remaining) == 1, f"Expected 1 comment after delete, got {len(remaining)}"
        assert remaining[0]["id"] == comment1["id"]


class TestShoppingListRecipeIncrementScale:
    """
    Recipe scale (recipeIncrementQuantity) workflow.
    Patterns: 5 (business logic), 2 (nested data).
    """

    def test_recipe_scale_doubles_quantities(self):
        """
        1. Create recipe with ingredient qty=3
        2. Add to shopping list with scale=2
        3. Verify item qty = 3*2 = 6
        4. Add again with scale=3
        5. Verify item qty = 6 + 3*3 = 15 (merged)
        """
        food = make_food(f"pasta-{W}-scale")
        unit = make_unit(f"cups-{W}-scale")

        slug = make_recipe(f"ScaleRecipe-{W}")
        recipe = get_recipe(slug)
        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 3, "note": "dry",
            }],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = make_shopping_list(f"ScaleSL-{W}")

        # Step 2: Add with scale=2
        r = post(f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
                 {"recipeId": recipe_id, "recipeIncrementQuantity": 2})
        assert r.status_code == 200

        # Step 3: Verify qty = 3*2 = 6
        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 1
        assert items[0]["quantity"] == 6, f"Expected 6 (3*2), got {items[0]['quantity']}"

        # Step 4: Add again with scale=3
        r = post(f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
                 {"recipeId": recipe_id, "recipeIncrementQuantity": 3})
        assert r.status_code == 200

        # Step 5: Verify qty = 6 + 9 = 15
        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 1, "Items should merge"
        assert items[0]["quantity"] == 15, f"Expected 15 (6+9), got {items[0]['quantity']}"
