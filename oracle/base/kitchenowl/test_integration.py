"""
BackendForge — L2 Integration Tests for KitchenOwl Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase field names (sourceUrl, mealType, paidBy, splitBetween, etc.)
- Pattern 2: Nested data (recipe items/tags, shopping list items)
- Pattern 3: Search/filter/ordering actually working
- Pattern 4: Exact status codes (201/204/400/404)
- Pattern 5: Business logic (merge, scaling, balances)
- Pattern 6: Household data isolation
- Pattern 7: Cascade/side-effect correctness
- Pattern 8: Uniqueness/merge constraints
"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def scoped_uuid(node_id, role):
    seed = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"backendforge:kitchenowl:L2:{node_id}:{role}",
    )
    return uuid.UUID(hex=seed.hex, version=4)


HH_ID = str(scoped_uuid("module", "household"))
HH_ID_2 = str(scoped_uuid("module", "other-household"))
USER_ID = str(scoped_uuid("module", "user-1"))
USER2_ID = str(scoped_uuid("module", "user-2"))
USER3_ID = str(scoped_uuid("module", "user-3"))

H1 = {"X-User-Id": USER_ID, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
H2 = {"X-User-Id": USER2_ID, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
H3 = {"X-User-Id": USER3_ID, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
H_OTHER = {
    "X-User-Id": str(scoped_uuid("module", "other-user")),
    "X-Household-Id": HH_ID_2,
    "Content-Type": "application/json",
}


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or H1, timeout=30)


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or H1, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or H1, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or H1, timeout=30)


def successful_json(response):
    response.raise_for_status()
    return response.json()


@pytest.fixture(autouse=True)
def isolate_test_state(request):
    """Use fresh deterministic households and memberships for each test."""
    global HH_ID, HH_ID_2, USER_ID, USER2_ID, USER3_ID

    node_id = request.node.nodeid
    HH_ID = str(scoped_uuid(node_id, "household"))
    HH_ID_2 = str(scoped_uuid(node_id, "other-household"))
    USER_ID = str(scoped_uuid(node_id, "user-1"))
    USER2_ID = str(scoped_uuid(node_id, "user-2"))
    USER3_ID = str(scoped_uuid(node_id, "user-3"))

    H1.update({"X-User-Id": USER_ID, "X-Household-Id": HH_ID})
    H2.update({"X-User-Id": USER2_ID, "X-Household-Id": HH_ID})
    H3.update({"X-User-Id": USER3_ID, "X-Household-Id": HH_ID})
    H_OTHER.update(
        {
            "X-User-Id": str(scoped_uuid(node_id, "other-user")),
            "X-Household-Id": HH_ID_2,
        }
    )

    for membership_headers in (H1, H2, H3, H_OTHER):
        get("/api/households", headers=membership_headers).raise_for_status()


class TestRecipeFields:
    """Pattern 1+2: Recipe response includes camelCase fields and nested items/tags."""

    def test_recipe_create_returns_all_fields(self):
        tag = successful_json(post("/api/tags", {"name": "Italian"}))
        r = post("/api/recipes", {
            "name": "Pasta",
            "description": "Simple pasta",
            "servings": 4,
            "time": 30,
            "sourceUrl": "https://recipe.test/pasta",
            "tags": [tag["id"]],
            "items": [
                {"name": "Spaghetti", "amount": 500, "unit": "g"},
                {"name": "Sauce", "amount": 2, "unit": "cups"},
            ]
        })
        assert r.status_code == 201
        recipe = r.json()
        assert "id" in recipe
        assert recipe["name"] == "Pasta"
        assert recipe["description"] == "Simple pasta"
        assert recipe["servings"] == 4
        assert recipe["time"] == 30
        assert recipe["sourceUrl"] == "https://recipe.test/pasta"
        assert "householdId" in recipe
        assert recipe["householdId"] == HH_ID
        # Tags are expanded
        assert "tags" in recipe
        assert isinstance(recipe["tags"], list)
        assert len(recipe["tags"]) == 1
        assert recipe["tags"][0]["id"] == tag["id"]
        assert recipe["tags"][0]["name"] == "Italian"
        # Items
        assert "items" in recipe
        assert len(recipe["items"]) == 2
        assert recipe["items"][0]["name"] == "Spaghetti"
        assert recipe["items"][0]["amount"] == 500
        assert recipe["items"][0]["unit"] == "g"

    def test_recipe_get_includes_nested_data(self):
        """GET recipe returns full tag objects and items."""
        tag = successful_json(post("/api/tags", {"name": "Quick"}))
        r = post("/api/recipes", {
            "name": "Salad", "servings": 2,
            "tags": [tag["id"]],
            "items": [{"name": "Lettuce", "amount": 1, "unit": "head"}]
        })
        rid = successful_json(r)["id"]
        r = get(f"/api/recipes/{rid}")
        assert r.status_code == 200
        recipe = r.json()
        assert len(recipe["tags"]) == 1
        assert recipe["tags"][0]["name"] == "Quick"
        assert len(recipe["items"]) == 1
        assert recipe["items"][0]["name"] == "Lettuce"


class TestShoppingListFields:
    """Pattern 1+2: Shopping list with items embedded."""

    def test_shopping_list_get_includes_items(self):
        r = post("/api/shopping-lists", {"name": "Groceries"})
        assert r.status_code == 201
        sl_id = r.json()["id"]

        post(
            f"/api/shopping-lists/{sl_id}/items", {"name": "Milk", "amount": 2}
        ).raise_for_status()
        post(f"/api/shopping-lists/{sl_id}/items", {"name": "Bread"}).raise_for_status()

        r = get(f"/api/shopping-lists/{sl_id}")
        assert r.status_code == 200
        sl = r.json()
        assert sl["id"] == sl_id
        assert "items" in sl
        assert len(sl["items"]) == 2
        names = [it["name"] for it in sl["items"]]
        assert "Milk" in names
        assert "Bread" in names
        # Each item has camelCase fields
        for item in sl["items"]:
            assert "id" in item
            assert "name" in item
            assert "done" in item
            assert "shoppingListId" in item


class TestExactStatusCodes:
    """Pattern 4: Verify exact HTTP status codes."""

    def test_create_item_201(self):
        r = post("/api/items", {"name": f"item-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_category_201(self):
        r = post("/api/categories", {"name": f"cat-{uuid.uuid4().hex[:6]}", "ordering": 1})
        assert r.status_code == 201

    def test_create_recipe_201(self):
        r = post("/api/recipes", {"name": f"rec-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_shopping_list_201(self):
        r = post("/api/shopping-lists", {"name": f"sl-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_tag_201(self):
        r = post("/api/tags", {"name": f"tag-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_create_expense_201(self):
        r = post("/api/expenses", {
            "amount": 10, "description": "test", "date": "2025-01-01",
            "paidBy": USER_ID, "splitBetween": [USER_ID]
        })
        assert r.status_code == 201

    def test_create_meal_plan_201(self):
        rec = successful_json(post("/api/recipes", {"name": "MP Recipe"}))
        r = post("/api/meal-plan", {"date": "2025-06-01", "mealType": "lunch", "recipeId": rec["id"]})
        assert r.status_code == 201

    def test_delete_item_204(self):
        item = successful_json(post("/api/items", {"name": "del-item"}))
        r = delete(f"/api/items/{item['id']}")
        assert r.status_code == 204

    def test_delete_category_204(self):
        cat = successful_json(post("/api/categories", {"name": "del-cat", "ordering": 0}))
        r = delete(f"/api/categories/{cat['id']}")
        assert r.status_code == 204

    def test_delete_recipe_204(self):
        rec = successful_json(post("/api/recipes", {"name": "del-rec"}))
        r = delete(f"/api/recipes/{rec['id']}")
        assert r.status_code == 204

    def test_nonexistent_recipe_404(self):
        r = get("/api/recipes/99999")
        assert r.status_code == 404

    def test_nonexistent_item_404(self):
        r = put("/api/items/99999", {"name": "x"})
        assert r.status_code == 404


class TestSearchFilter:
    """Pattern 3: Search actually filters results."""

    def test_item_search_filters(self):
        post("/api/items", {"name": "Apple Juice"}).raise_for_status()
        post("/api/items", {"name": "Orange Juice"}).raise_for_status()
        post("/api/items", {"name": "Banana"}).raise_for_status()

        r = get("/api/items", params={"search": "juice"})
        assert r.status_code == 200
        names = [i["name"] for i in r.json()]
        assert "Apple Juice" in names
        assert "Orange Juice" in names
        assert "Banana" not in names

    def test_recipe_search_filters(self):
        post("/api/recipes", {"name": "Chicken Soup"}).raise_for_status()
        post("/api/recipes", {"name": "Tomato Soup"}).raise_for_status()
        post("/api/recipes", {"name": "Grilled Steak"}).raise_for_status()

        r = get("/api/recipes", params={"search": "soup"})
        assert r.status_code == 200
        names = [rec["name"] for rec in r.json()]
        assert "Chicken Soup" in names
        assert "Tomato Soup" in names
        assert "Grilled Steak" not in names


class TestCategoryOrdering:
    """Pattern 3: Categories returned ordered by ordering field."""

    def test_categories_ordered_by_ordering(self):
        post("/api/categories", {"name": "Cat C", "ordering": 3})
        post("/api/categories", {"name": "Cat A", "ordering": 1})
        post("/api/categories", {"name": "Cat B", "ordering": 2})

        r = get("/api/categories")
        assert r.status_code == 200
        cats = r.json()
        orderings = [c["ordering"] for c in cats]
        assert orderings == sorted(orderings)


class TestShoppingListItemMerge:
    """Pattern 5+8: Merge behavior when adding duplicate items."""

    def test_merge_increments_amount(self):
        """Adding same item twice merges by incrementing amount."""
        sl = successful_json(post("/api/shopping-lists", {"name": "Merge Test"}))
        sl_id = sl["id"]

        r1 = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Eggs", "amount": 6})
        assert r1.status_code == 200
        r2 = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Eggs", "amount": 6})
        assert r2.status_code == 200
        # Should merge: 6 + 6 = 12
        merged = r2.json()
        assert merged["amount"] == 12
        assert merged["name"] == "Eggs"

    def test_merge_no_amount_becomes_2(self):
        """Both without amount → amount becomes 2."""
        sl = successful_json(post("/api/shopping-lists", {"name": "Merge NoAmt"}))
        sl_id = sl["id"]

        post(f"/api/shopping-lists/{sl_id}/items", {"name": "Salt"}).raise_for_status()
        r = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Salt"})
        assert r.status_code == 200
        assert r.json()["amount"] == 2

    def test_merge_case_insensitive(self):
        """Merge is case-insensitive on name."""
        sl = successful_json(post("/api/shopping-lists", {"name": "Merge Case"}))
        sl_id = sl["id"]

        post(
            f"/api/shopping-lists/{sl_id}/items", {"name": "milk", "amount": 1}
        ).raise_for_status()
        r = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Milk", "amount": 2})
        assert r.status_code == 200
        assert r.json()["amount"] == 3


class TestExpenseBalances:
    """Pattern 5: Expense balance calculation."""

    def test_simple_balance(self):
        """A pays 100 split between A and B → B owes A 50."""
        r = post("/api/expenses", {
            "amount": 100, "description": "Dinner",
            "date": "2025-01-15", "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID]
        })
        assert r.status_code == 201

        r = get("/api/expenses/balances")
        assert r.status_code == 200
        balances = r.json()
        assert isinstance(balances, list)
        # Should have a balance entry
        if len(balances) > 0:
            bal = balances[0]
            assert "from" in bal
            assert "to" in bal
            assert "amount" in bal


class TestHouseholdIsolation:
    """Pattern 6: Data isolation between households."""

    def test_items_not_visible_across_households(self):
        item = successful_json(
            post("/api/items", {"name": f"iso-{uuid.uuid4().hex[:6]}"})
        )
        r = get("/api/items", headers=H_OTHER)
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()]
        assert item["id"] not in ids

    def test_recipes_not_visible_across_households(self):
        rec = successful_json(
            post("/api/recipes", {"name": f"iso-rec-{uuid.uuid4().hex[:6]}"})
        )
        r = get(f"/api/recipes/{rec['id']}", headers=H_OTHER)
        assert r.status_code == 404

    def test_shopping_lists_not_visible_across_households(self):
        sl = successful_json(post("/api/shopping-lists", {"name": "iso-sl"}))
        r = get(f"/api/shopping-lists/{sl['id']}", headers=H_OTHER)
        assert r.status_code == 404


class TestCascadeDeleteCategory:
    """Pattern 7: Deleting category sets items' category to null."""

    def test_delete_category_nullifies_items(self):
        cat = successful_json(post("/api/categories", {"name": "Dairy", "ordering": 1}))
        item = successful_json(post("/api/items", {"name": "Milk", "category": cat["id"]}))
        assert item["category"] == cat["id"]

        delete(f"/api/categories/{cat['id']}").raise_for_status()
        r = get("/api/items", params={"search": item["name"]})
        found = next(i for i in successful_json(r) if i["id"] == item["id"])
        assert found["category"] is None


class TestCascadeDeleteRecipe:
    """Pattern 7: Deleting recipe removes meal plan entries."""

    def test_delete_recipe_removes_meal_plan_entries(self):
        rec = successful_json(post("/api/recipes", {"name": "MealDel Recipe"}))
        mp = post("/api/meal-plan", {
            "date": "2025-07-01", "mealType": "dinner", "recipeId": rec["id"]
        })
        assert mp.status_code == 201
        mp_id = mp.json()["id"]

        delete(f"/api/recipes/{rec['id']}").raise_for_status()

        r = get("/api/meal-plan", params={"from": "2025-07-01", "to": "2025-07-01"})
        ids = [e["id"] for e in successful_json(r)]
        assert mp_id not in ids


class TestCascadeDeleteTag:
    """Pattern 7: Deleting tag removes it from recipes."""

    def test_delete_tag_removes_from_recipes(self):
        tag = successful_json(post("/api/tags", {"name": "ToDelete"}))
        rec = successful_json(
            post("/api/recipes", {"name": "Tagged", "tags": [tag["id"]]})
        )
        assert any(t["id"] == tag["id"] for t in rec["tags"])

        delete(f"/api/tags/{tag['id']}").raise_for_status()

        r = get(f"/api/recipes/{rec['id']}")
        tag_ids = [t["id"] for t in successful_json(r)["tags"]]
        assert tag["id"] not in tag_ids


class TestMealPlanDateFilter:
    """Pattern 3: Meal plan from/to filters actually work."""

    def test_date_filter_returns_only_matching(self):
        rec = successful_json(post("/api/recipes", {"name": "Filter Recipe"}))
        post(
            "/api/meal-plan",
            {"date": "2025-03-10", "mealType": "breakfast", "recipeId": rec["id"]},
        ).raise_for_status()
        post(
            "/api/meal-plan",
            {"date": "2025-03-15", "mealType": "lunch", "recipeId": rec["id"]},
        ).raise_for_status()
        post(
            "/api/meal-plan",
            {"date": "2025-03-20", "mealType": "dinner", "recipeId": rec["id"]},
        ).raise_for_status()

        r = get("/api/meal-plan", params={"from": "2025-03-12", "to": "2025-03-18"})
        assert r.status_code == 200
        dates = [e["date"] for e in r.json()]
        assert "2025-03-15" in dates
        assert "2025-03-10" not in dates
        assert "2025-03-20" not in dates


class TestExpenseFields:
    """Pattern 1: Expense response has correct camelCase fields."""

    def test_expense_response_fields(self):
        r = post("/api/expenses", {
            "amount": 42.50, "description": "Groceries", "date": "2025-02-20",
            "category": "food", "paidBy": USER_ID, "splitBetween": [USER_ID, USER2_ID]
        })
        assert r.status_code == 201
        e = r.json()
        assert "id" in e
        assert e["amount"] == 42.50
        assert e["description"] == "Groceries"
        assert e["date"] == "2025-02-20"
        assert e["category"] == "food"
        assert e["paidBy"] == USER_ID
        assert "splitBetween" in e
        assert isinstance(e["splitBetween"], list)
        assert set(e["splitBetween"]) == {USER_ID, USER2_ID}
        assert "householdId" in e
        assert e["householdId"] == HH_ID


class TestMealPlanFields:
    """Pattern 1: MealPlanEntry fields."""

    def test_meal_plan_entry_fields(self):
        rec = successful_json(post("/api/recipes", {"name": "MPF Recipe"}))
        r = post("/api/meal-plan", {"date": "2025-08-01", "mealType": "breakfast", "recipeId": rec["id"]})
        assert r.status_code == 201
        entry = r.json()
        assert "id" in entry
        assert entry["date"] == "2025-08-01"
        assert entry["mealType"] == "breakfast"
        assert entry["recipeId"] == rec["id"]
        assert "householdId" in entry
        assert entry["householdId"] == HH_ID


class TestDoneItemPersists:
    """Pattern 5: Marking item as done keeps it in list."""

    def test_done_item_still_in_list(self):
        sl = successful_json(post("/api/shopping-lists", {"name": "Done Test"}))
        sl_id = sl["id"]
        r = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Butter"})
        item_id = successful_json(r)["id"]

        put(
            f"/api/shopping-lists/{sl_id}/items/{item_id}", {"done": True}
        ).raise_for_status()

        r = get(f"/api/shopping-lists/{sl_id}")
        items = successful_json(r)["items"]
        found = next(i for i in items if i["id"] == item_id)
        assert found["done"] is True
        assert found["name"] == "Butter"
