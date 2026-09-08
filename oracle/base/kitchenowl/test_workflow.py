"""
BackendForge — L3 Workflow Tests for KitchenOwl Task

Multi-step cross-entity workflows testing:
- Pattern 2+5+7: Nested data + business logic (merge, scaling, balances) + cascades
- Pattern 3+6: Filtering + isolation
- Pattern 1+4: Field names + status codes
"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def scoped_uuid(node_id, role):
    seed = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"backendforge:kitchenowl:L3:{node_id}:{role}",
    )
    return uuid.UUID(hex=seed.hex, version=4)


HH_ID = str(scoped_uuid("module", "household"))
HH_ID_2 = str(scoped_uuid("module", "other-household"))
USER_A = str(scoped_uuid("module", "user-a"))
USER_B = str(scoped_uuid("module", "user-b"))
USER_C = str(scoped_uuid("module", "user-c"))

HA = {"X-User-Id": USER_A, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
HB = {"X-User-Id": USER_B, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
HC = {"X-User-Id": USER_C, "X-Household-Id": HH_ID, "Content-Type": "application/json"}
H_OTHER = {
    "X-User-Id": str(scoped_uuid("module", "other-user")),
    "X-Household-Id": HH_ID_2,
    "Content-Type": "application/json",
}


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or HA, timeout=30)


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HA, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or HA, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HA, timeout=30)


def successful_json(response):
    response.raise_for_status()
    return response.json()


@pytest.fixture(autouse=True)
def isolate_test_state(request):
    """Use fresh deterministic households and memberships for each workflow."""
    global HH_ID, HH_ID_2, USER_A, USER_B, USER_C

    node_id = request.node.nodeid
    HH_ID = str(scoped_uuid(node_id, "household"))
    HH_ID_2 = str(scoped_uuid(node_id, "other-household"))
    USER_A = str(scoped_uuid(node_id, "user-a"))
    USER_B = str(scoped_uuid(node_id, "user-b"))
    USER_C = str(scoped_uuid(node_id, "user-c"))

    HA.update({"X-User-Id": USER_A, "X-Household-Id": HH_ID})
    HB.update({"X-User-Id": USER_B, "X-Household-Id": HH_ID})
    HC.update({"X-User-Id": USER_C, "X-Household-Id": HH_ID})
    H_OTHER.update(
        {
            "X-User-Id": str(scoped_uuid(node_id, "other-user")),
            "X-Household-Id": HH_ID_2,
        }
    )

    for membership_headers in (HA, HB, HC, H_OTHER):
        get("/api/households", headers=membership_headers).raise_for_status()


class TestRecipeToShoppingListScaling:
    """Pattern 5: Recipe add-to-shopping-list with servings scaling."""

    def test_recipe_scaling_workflow(self):
        """
        1. Create recipe with 4 servings and 3 ingredients
        2. Create shopping list
        3. Add recipe for 8 servings (2x scaling)
        4. Verify each item amount is doubled
        5. Add same recipe again for 4 servings (1x)
        6. Verify amounts merged correctly (merge rule)
        """
        # 1. Recipe
        r = post("/api/recipes", {
            "name": "Scaling Test",
            "servings": 4,
            "items": [
                {"name": "Flour", "amount": 200, "unit": "g"},
                {"name": "Sugar", "amount": 100, "unit": "g"},
                {"name": "Eggs", "amount": 2, "unit": None},
            ]
        })
        assert r.status_code == 201
        recipe = r.json()
        rec_id = recipe["id"]

        # 2. Shopping list
        sl = successful_json(post("/api/shopping-lists", {"name": "Scale SL"}))
        sl_id = sl["id"]

        # 3. Add for 8 servings (2x)
        r = post(f"/api/shopping-lists/{sl_id}/add-recipe", {"recipeId": rec_id, "servings": 8})
        assert r.status_code == 200
        sl_data = r.json()
        items = sl_data["items"]
        flour = next(i for i in items if i["name"].lower() == "flour")
        sugar = next(i for i in items if i["name"].lower() == "sugar")
        eggs = next(i for i in items if i["name"].lower() == "eggs")
        assert flour["amount"] == 400  # 200 * 2
        assert sugar["amount"] == 200  # 100 * 2
        assert eggs["amount"] == 4  # 2 * 2

        # 5. Add again for 4 servings (1x) → merge
        r = post(f"/api/shopping-lists/{sl_id}/add-recipe", {"recipeId": rec_id, "servings": 4})
        assert r.status_code == 200
        items = r.json()["items"]
        flour = next(i for i in items if i["name"].lower() == "flour")
        sugar = next(i for i in items if i["name"].lower() == "sugar")
        eggs = next(i for i in items if i["name"].lower() == "eggs")
        # Merged: 400+200=600, 200+100=300, 4+2=6
        assert flour["amount"] == 600
        assert sugar["amount"] == 300
        assert eggs["amount"] == 6


class TestExpenseBalanceWorkflow:
    """Pattern 5: Expense balance calculation with multiple expenses."""

    def test_balance_calculation(self):
        """
        1. A pays 90 split A,B,C → each owes 30, A paid 90 so A net +60
        2. B pays 60 split A,B,C → each owes 20, B paid 60 so B net +40
        3. Check balances: A net=+60-20-20=+20, B net=+40-30-20=-10... wait
           Actually: A net = 90 - 30 - 20 = 40, B net = 60 - 30 - 20 = 10, C net = 0 - 30 - 20 = -50
           Wait let me recalculate:
           Expense 1: A pays 90 split [A,B,C]. Each share=30. A's net += 90-30=60. B owes 30. C owes 30.
           Expense 2: B pays 60 split [A,B,C]. Each share=20. B's net += 60-20=40. A owes 20. C owes 20.
           Overall: A net = +60 - 20 = +40. B net = -30 + 40 = +10. C net = -30 - 20 = -50.
           C owes 40 to A and 10 to B.
        4. Verify balances sum to zero (all from amounts = all to amounts)
        """
        # 1.
        r = post("/api/expenses", {
            "amount": 90, "description": "Dinner", "date": "2025-01-01",
            "paidBy": USER_A, "splitBetween": [USER_A, USER_B, USER_C]
        })
        assert r.status_code == 201

        # 2.
        r = post("/api/expenses", {
            "amount": 60, "description": "Groceries", "date": "2025-01-02",
            "paidBy": USER_B, "splitBetween": [USER_A, USER_B, USER_C]
        })
        assert r.status_code == 201

        # 3+4. Check balances
        r = get("/api/expenses/balances")
        assert r.status_code == 200
        balances = r.json()
        assert isinstance(balances, list)

        # All balance entries should have from, to, amount
        for bal in balances:
            assert "from" in bal
            assert "to" in bal
            assert "amount" in bal
            assert bal["amount"] > 0

        # Total owed should sum correctly (net zero)
        total_from = sum(b["amount"] for b in balances)
        # C owes 50 total, split as 40 to A and 10 to B (or equivalent simplified)
        assert total_from == pytest.approx(50, abs=0.01)


class TestCascadeDeleteWorkflow:
    """Pattern 7: Multiple cascades verified."""

    def test_full_cascade_on_recipe_delete(self):
        """
        1. Create tag
        2. Create recipe with tag and items
        3. Create meal plan entry with recipe
        4. Delete recipe
        5. Verify meal plan entry gone
        6. Verify tag still exists
        """
        tag = successful_json(post("/api/tags", {"name": "CascadeTag"}))
        rec = successful_json(post("/api/recipes", {
            "name": "Cascade Recipe",
            "tags": [tag["id"]],
            "items": [{"name": "Ing1", "amount": 1, "unit": "pcs"}]
        }))

        mp = successful_json(post("/api/meal-plan", {
            "date": "2025-09-01", "mealType": "lunch", "recipeId": rec["id"]
        }))

        # Delete recipe
        r = delete(f"/api/recipes/{rec['id']}")
        assert r.status_code == 204

        # Meal plan entry gone
        r = get("/api/meal-plan", params={"from": "2025-09-01", "to": "2025-09-01"})
        ids = [e["id"] for e in r.json()]
        assert mp["id"] not in ids

        # Tag still exists
        r = get("/api/tags")
        tag_ids = [t["id"] for t in r.json()]
        assert tag["id"] in tag_ids

    def test_shopping_list_delete_cascades_items(self):
        """
        1. Create shopping list
        2. Add items
        3. Delete shopping list
        4. Verify shopping list gone (404)
        """
        sl = successful_json(post("/api/shopping-lists", {"name": "Del SL"}))
        sl_id = sl["id"]
        post(f"/api/shopping-lists/{sl_id}/items", {"name": "Item1"})
        post(f"/api/shopping-lists/{sl_id}/items", {"name": "Item2"})

        r = delete(f"/api/shopping-lists/{sl_id}")
        assert r.status_code == 204

        r = get(f"/api/shopping-lists/{sl_id}")
        assert r.status_code == 404


class TestHouseholdIsolationWorkflow:
    """Pattern 6: Full isolation across all entity types."""

    def test_complete_household_isolation(self):
        """
        1. Create item, recipe, shopping list, tag, expense in HH1
        2. Verify all visible in HH1
        3. Verify NONE visible/accessible from HH2
        """
        item = successful_json(
            post("/api/items", {"name": f"iso-{uuid.uuid4().hex[:6]}"})
        )
        tag = successful_json(
            post("/api/tags", {"name": f"iso-tag-{uuid.uuid4().hex[:6]}"})
        )
        rec = successful_json(
            post(
                "/api/recipes",
                {"name": f"iso-rec-{uuid.uuid4().hex[:6]}", "tags": [tag["id"]]},
            )
        )
        sl = successful_json(post("/api/shopping-lists", {"name": "iso-sl"}))
        exp = successful_json(post("/api/expenses", {
            "amount": 10, "description": "iso", "date": "2025-05-01",
            "paidBy": USER_A, "splitBetween": [USER_A]
        }))

        # Verify in HH1
        assert get(f"/api/recipes/{rec['id']}").status_code == 200
        assert get(f"/api/shopping-lists/{sl['id']}").status_code == 200

        # Invisible from HH2
        assert get(f"/api/recipes/{rec['id']}", headers=H_OTHER).status_code == 404
        assert get(f"/api/shopping-lists/{sl['id']}", headers=H_OTHER).status_code == 404

        # Items list doesn't include HH1 items
        r = get("/api/items", headers=H_OTHER)
        hh2_ids = [i["id"] for i in successful_json(r)]
        assert item["id"] not in hh2_ids

        # Tags not visible
        r = get("/api/tags", headers=H_OTHER)
        hh2_tag_ids = [t["id"] for t in successful_json(r)]
        assert tag["id"] not in hh2_tag_ids


class TestShoppingListMergeWorkflow:
    """Pattern 5+8: Merge behavior with done items."""

    def test_merge_skips_done_items(self):
        """
        1. Create shopping list
        2. Add 'Milk' with amount 1
        3. Mark it as done
        4. Add 'Milk' again with amount 2
        5. Verify: TWO items now (done milk + new milk), not merged
        """
        sl = successful_json(post("/api/shopping-lists", {"name": "Done Merge"}))
        sl_id = sl["id"]

        r = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Milk", "amount": 1})
        item_id = successful_json(r)["id"]

        # Mark done
        put(
            f"/api/shopping-lists/{sl_id}/items/{item_id}", {"done": True}
        ).raise_for_status()

        # Add again
        r = post(f"/api/shopping-lists/{sl_id}/items", {"name": "Milk", "amount": 2})
        assert r.status_code == 200

        # Should have 2 items (done + new)
        r = get(f"/api/shopping-lists/{sl_id}")
        milks = [
            i for i in successful_json(r)["items"] if i["name"].lower() == "milk"
        ]
        assert len(milks) == 2
        done_milk = next(m for m in milks if m["done"])
        new_milk = next(m for m in milks if not m["done"])
        assert done_milk["amount"] == 1
        assert new_milk["amount"] == 2


class TestMealPlanWorkflow:
    """Pattern 1+3+7: Meal plan with date filtering and recipe cascade."""

    def test_meal_plan_lifecycle(self):
        """
        1. Create 2 recipes
        2. Create meal plan entries for different dates and meal types
        3. Filter by date range → verify correct entries
        4. Delete one recipe → its meal plan entries removed
        5. Other recipe's entries still exist
        """
        rec1 = successful_json(post("/api/recipes", {"name": "MP Recipe 1"}))
        rec2 = successful_json(post("/api/recipes", {"name": "MP Recipe 2"}))

        # Entries for different dates
        e1 = successful_json(post(
            "/api/meal-plan",
            {"date": "2025-04-01", "mealType": "breakfast", "recipeId": rec1["id"]},
        ))
        e2 = successful_json(post(
            "/api/meal-plan",
            {"date": "2025-04-02", "mealType": "lunch", "recipeId": rec2["id"]},
        ))
        e3 = successful_json(post(
            "/api/meal-plan",
            {"date": "2025-04-03", "mealType": "dinner", "recipeId": rec1["id"]},
        ))

        # Verify fields
        assert e1["mealType"] == "breakfast"
        assert e1["recipeId"] == rec1["id"]
        assert e2["mealType"] == "lunch"

        # Filter
        r = get("/api/meal-plan", params={"from": "2025-04-01", "to": "2025-04-02"})
        assert r.status_code == 200
        ids = [e["id"] for e in r.json()]
        assert e1["id"] in ids
        assert e2["id"] in ids
        assert e3["id"] not in ids

        # Delete rec1 → e1 and e3 gone
        delete(f"/api/recipes/{rec1['id']}").raise_for_status()
        r = get("/api/meal-plan", params={"from": "2025-04-01", "to": "2025-04-03"})
        remaining_ids = [e["id"] for e in r.json()]
        assert e1["id"] not in remaining_ids
        assert e3["id"] not in remaining_ids
        assert e2["id"] in remaining_ids


class TestCategoryItemWorkflow:
    """Pattern 7: Category and item relationship."""

    def test_category_lifecycle_with_items(self):
        """
        1. Create category with ordering
        2. Create items in that category
        3. Verify items have category set
        4. Delete category
        5. Verify items now have category=null
        6. Items themselves still exist
        """
        cat = successful_json(post("/api/categories", {"name": "Frozen", "ordering": 5}))
        assert cat["ordering"] == 5

        item1 = successful_json(
            post("/api/items", {"name": "Ice Cream", "category": cat["id"]})
        )
        item2 = successful_json(
            post("/api/items", {"name": "Frozen Pizza", "category": cat["id"]})
        )
        assert item1["category"] == cat["id"]
        assert item2["category"] == cat["id"]

        # Delete category
        r = delete(f"/api/categories/{cat['id']}")
        assert r.status_code == 204

        # Category gone
        r = get(f"/api/categories/{cat['id']}")
        assert r.status_code == 404

        # Items still exist but category is null
        r = get("/api/items", params={"search": "Ice Cream"})
        found = [i for i in r.json() if i["id"] == item1["id"]]
        assert len(found) == 1
        assert found[0]["category"] is None


class TestAutoCreateMembership:
    """Pattern 1+6: Auto-create household and membership."""

    def test_first_request_auto_creates(self):
        """First request with new user+household auto-creates both."""
        new_hh = str(uuid.uuid4())
        new_user = str(uuid.uuid4())
        headers = {"X-User-Id": new_user, "X-Household-Id": new_hh, "Content-Type": "application/json"}

        r = get("/api/households", headers=headers)
        assert r.status_code == 200
        hh = r.json()
        assert hh["id"] == new_hh
        assert hh["name"] == "My Household"

        # User is a member
        r = get("/api/households/members", headers=headers)
        assert r.status_code == 200
        members = r.json()
        user_ids = [m["userId"] for m in members]
        assert new_user in user_ids
