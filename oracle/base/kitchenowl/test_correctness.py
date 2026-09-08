"""
BackendForge — Comprehensive Correctness Tests for KitchenOwl Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def scoped_uuid(node_id, role):
    seed = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"backendforge:kitchenowl:L1:{node_id}:{role}",
    )
    return uuid.UUID(hex=seed.hex, version=4)

# Household and user IDs
HOUSEHOLD_ID = str(scoped_uuid("module", "household"))
USER_ID = str(scoped_uuid("module", "user-1"))
USER2_ID = str(scoped_uuid("module", "user-2"))
USER3_ID = str(scoped_uuid("module", "user-3"))

# Another household for isolation tests
OTHER_HOUSEHOLD_ID = str(scoped_uuid("module", "other-household"))
OTHER_USER_ID = str(scoped_uuid("module", "other-user"))

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

HEADERS_USER2 = {
    "X-User-Id": USER2_ID,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

HEADERS_USER3 = {
    "X-User-Id": USER3_ID,
    "X-Household-Id": HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

HEADERS_OTHER = {
    "X-User-Id": OTHER_USER_ID,
    "X-Household-Id": OTHER_HOUSEHOLD_ID,
    "Content-Type": "application/json",
}

UNIQUE = scoped_uuid("module", "marker").hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_state(request):
    """Give every test its own reproducible household namespace."""
    global HOUSEHOLD_ID, USER_ID, USER2_ID, USER3_ID
    global OTHER_HOUSEHOLD_ID, OTHER_USER_ID, UNIQUE

    node_id = request.node.nodeid
    HOUSEHOLD_ID = str(scoped_uuid(node_id, "household"))
    USER_ID = str(scoped_uuid(node_id, "user-1"))
    USER2_ID = str(scoped_uuid(node_id, "user-2"))
    USER3_ID = str(scoped_uuid(node_id, "user-3"))
    OTHER_HOUSEHOLD_ID = str(scoped_uuid(node_id, "other-household"))
    OTHER_USER_ID = str(scoped_uuid(node_id, "other-user"))
    UNIQUE = scoped_uuid(node_id, "marker").hex[:8]

    HEADERS.update({"X-User-Id": USER_ID, "X-Household-Id": HOUSEHOLD_ID})
    HEADERS_USER2.update({"X-User-Id": USER2_ID, "X-Household-Id": HOUSEHOLD_ID})
    HEADERS_USER3.update({"X-User-Id": USER3_ID, "X-Household-Id": HOUSEHOLD_ID})
    HEADERS_OTHER.update(
        {"X-User-Id": OTHER_USER_ID, "X-Household-Id": OTHER_HOUSEHOLD_ID}
    )


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


def successful_json(response):
    response.raise_for_status()
    return response.json()


# ── Setup: ensure memberships exist ──

def ensure_membership(headers=None):
    """Make a request to ensure the user+household membership is auto-created."""
    response = api_get("/api/households", headers=headers or HEADERS)
    response.raise_for_status()


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication & Authorization
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_both_headers_returns_401(self):
        """Requests without auth headers should return 401."""
        resp = requests.get(f"{BASE_URL}/api/households", timeout=30)
        assert resp.status_code == 401

    def test_missing_user_id_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/api/households",
            headers={"X-Household-Id": HOUSEHOLD_ID},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_missing_household_id_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/api/households",
            headers={"X-User-Id": USER_ID},
            timeout=30,
        )
        assert resp.status_code == 401

    def test_missing_headers_on_items(self):
        resp = requests.get(f"{BASE_URL}/api/items", timeout=30)
        assert resp.status_code == 401

    def test_missing_headers_on_recipes(self):
        resp = requests.get(f"{BASE_URL}/api/recipes", timeout=30)
        assert resp.status_code == 401

    def test_missing_headers_on_shopping_lists(self):
        resp = requests.get(f"{BASE_URL}/api/shopping-lists", timeout=30)
        assert resp.status_code == 401

    def test_missing_headers_on_expenses(self):
        resp = requests.get(f"{BASE_URL}/api/expenses", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_membership(self):
        """First request with new user+household should auto-create membership."""
        new_user = str(uuid.uuid4())
        new_household = str(uuid.uuid4())
        headers = {
            "X-User-Id": new_user,
            "X-Household-Id": new_household,
            "Content-Type": "application/json",
        }
        resp = api_get("/api/households", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == new_household
        assert data["name"] == "My Household"

    def test_household_isolation(self):
        """Data from one household is not visible in another household."""
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        # Create an item in HOUSEHOLD
        api_post("/api/items", {"name": f"IsolationTest-{UNIQUE}"})
        # OTHER_USER in OTHER_HOUSEHOLD should not see it
        resp = api_get("/api/items", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()]
        assert f"IsolationTest-{UNIQUE}" not in names


# ════════════════════════════════════════════════════════════════════
# PART 2: Households
# ════════════════════════════════════════════════════════════════════


class TestHouseholds:

    def test_get_household(self):
        ensure_membership()
        resp = api_get("/api/households")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == HOUSEHOLD_ID
        assert "name" in data

    def test_update_household_name(self):
        ensure_membership()
        resp = api_put("/api/households", {"name": f"My Kitchen {UNIQUE}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == f"My Kitchen {UNIQUE}"
        assert data["id"] == HOUSEHOLD_ID

    def test_get_household_members(self):
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        resp = api_get("/api/households/members")
        assert resp.status_code == 200
        members = resp.json()
        assert isinstance(members, list)
        user_ids = [m["userId"] for m in members]
        assert USER_ID in user_ids
        assert USER2_ID in user_ids


# ════════════════════════════════════════════════════════════════════
# PART 3: Categories CRUD
# ════════════════════════════════════════════════════════════════════


class TestCategories:

    def test_create_category(self):
        ensure_membership()
        resp = api_post("/api/categories", {"name": f"Dairy-{UNIQUE}", "ordering": 1})
        assert resp.status_code == 201
        cat = resp.json()
        assert cat["name"] == f"Dairy-{UNIQUE}"
        assert cat["ordering"] == 1
        assert "id" in cat
        assert cat["householdId"] == HOUSEHOLD_ID

    def test_create_category_default_ordering(self):
        ensure_membership()
        resp = api_post("/api/categories", {"name": f"Frozen-{UNIQUE}"})
        assert resp.status_code == 201
        cat = resp.json()
        assert cat["ordering"] == 0

    def test_list_categories_ordered(self):
        ensure_membership()
        # Create categories with specific ordering
        api_post("/api/categories", {"name": f"Cat-C-{UNIQUE}", "ordering": 3})
        api_post("/api/categories", {"name": f"Cat-A-{UNIQUE}", "ordering": 1})
        api_post("/api/categories", {"name": f"Cat-B-{UNIQUE}", "ordering": 2})
        resp = api_get("/api/categories")
        assert resp.status_code == 200
        cats = resp.json()
        assert isinstance(cats, list)
        # Verify ordering
        orderings = [c["ordering"] for c in cats]
        assert orderings == sorted(orderings)

    def test_get_category(self):
        ensure_membership()
        create_resp = api_post("/api/categories", {"name": f"GetCat-{UNIQUE}", "ordering": 5})
        cat_id = successful_json(create_resp)["id"]
        resp = api_get(f"/api/categories/{cat_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"GetCat-{UNIQUE}"

    def test_update_category(self):
        ensure_membership()
        create_resp = api_post("/api/categories", {"name": f"UpdCat-{UNIQUE}", "ordering": 1})
        cat_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/categories/{cat_id}", {"name": f"Updated-{UNIQUE}", "ordering": 10})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated-{UNIQUE}"
        assert resp.json()["ordering"] == 10

    def test_delete_category(self):
        ensure_membership()
        create_resp = api_post("/api/categories", {"name": f"DelCat-{UNIQUE}", "ordering": 1})
        cat_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/categories/{cat_id}")
        assert resp.status_code == 204
        # Verify gone
        get_resp = api_get(f"/api/categories/{cat_id}")
        assert get_resp.status_code == 404

    def test_delete_category_nullifies_items(self):
        """Deleting a category should set items' category to null."""
        ensure_membership()
        cat_resp = api_post("/api/categories", {"name": f"NullCat-{UNIQUE}", "ordering": 1})
        cat_id = successful_json(cat_resp)["id"]
        # Create item with that category
        item_resp = api_post("/api/items", {"name": f"NullItem-{UNIQUE}", "category": cat_id})
        item_id = successful_json(item_resp)["id"]
        # Delete category
        api_delete(f"/api/categories/{cat_id}").raise_for_status()
        # Check item
        items_resp = api_get("/api/items")
        items = successful_json(items_resp)
        matching = [i for i in items if i["id"] == item_id]
        assert len(matching) == 1
        assert matching[0]["category"] is None

    def test_get_nonexistent_category(self):
        ensure_membership()
        resp = api_get("/api/categories/999999")
        assert resp.status_code == 404

    def test_update_nonexistent_category(self):
        ensure_membership()
        resp = api_put("/api/categories/999999", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_nonexistent_category(self):
        ensure_membership()
        resp = api_delete("/api/categories/999999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Items CRUD
# ════════════════════════════════════════════════════════════════════


class TestItems:

    def test_create_item(self):
        ensure_membership()
        resp = api_post("/api/items", {
            "name": f"Milk-{UNIQUE}",
            "defaultUnit": "liters",
        })
        assert resp.status_code == 201
        item = resp.json()
        assert item["name"] == f"Milk-{UNIQUE}"
        assert item["defaultUnit"] == "liters"
        assert "id" in item
        assert item["householdId"] == HOUSEHOLD_ID

    def test_create_item_with_category(self):
        ensure_membership()
        cat_resp = api_post("/api/categories", {"name": f"ItemCat-{UNIQUE}", "ordering": 1})
        cat_id = successful_json(cat_resp)["id"]
        resp = api_post("/api/items", {"name": f"Cheese-{UNIQUE}", "category": cat_id})
        assert resp.status_code == 201
        assert resp.json()["category"] == cat_id

    def test_list_items(self):
        ensure_membership()
        api_post("/api/items", {"name": f"ListItem-{UNIQUE}"}).raise_for_status()
        resp = api_get("/api/items")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        names = [i["name"] for i in items]
        assert f"ListItem-{UNIQUE}" in names

    def test_search_items(self):
        ensure_membership()
        api_post("/api/items", {"name": f"Avocado-{UNIQUE}"}).raise_for_status()
        api_post("/api/items", {"name": f"Banana-{UNIQUE}"}).raise_for_status()
        resp = api_get("/api/items", params={"search": "avocado"})
        assert resp.status_code == 200
        items = resp.json()
        names = [i["name"] for i in items]
        assert f"Avocado-{UNIQUE}" in names
        assert f"Banana-{UNIQUE}" not in names

    def test_search_items_case_insensitive(self):
        ensure_membership()
        api_post("/api/items", {"name": f"UPPERCASE-{UNIQUE}"}).raise_for_status()
        resp = api_get("/api/items", params={"search": "uppercase"})
        assert resp.status_code == 200
        items = resp.json()
        names = [i["name"] for i in items]
        assert f"UPPERCASE-{UNIQUE}" in names

    def test_update_item(self):
        ensure_membership()
        create_resp = api_post("/api/items", {"name": f"UpdItem-{UNIQUE}"})
        item_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/items/{item_id}", {"name": f"Renamed-{UNIQUE}", "defaultUnit": "kg"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Renamed-{UNIQUE}"
        assert resp.json()["defaultUnit"] == "kg"

    def test_delete_item(self):
        ensure_membership()
        create_resp = api_post("/api/items", {"name": f"DelItem-{UNIQUE}"})
        item_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/items/{item_id}")
        assert resp.status_code == 204
        # Verify gone
        items_resp = api_get("/api/items")
        ids = [i["id"] for i in successful_json(items_resp)]
        assert item_id not in ids

    def test_delete_nonexistent_item(self):
        ensure_membership()
        resp = api_delete("/api/items/999999")
        assert resp.status_code == 404

    def test_update_nonexistent_item(self):
        ensure_membership()
        resp = api_put("/api/items/999999", {"name": "Ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        ensure_membership()
        resp = api_post("/api/tags", {"name": f"Vegan-{UNIQUE}"})
        assert resp.status_code == 201
        tag = resp.json()
        assert tag["name"] == f"Vegan-{UNIQUE}"
        assert "id" in tag
        assert tag["householdId"] == HOUSEHOLD_ID

    def test_list_tags(self):
        ensure_membership()
        api_post("/api/tags", {"name": f"ListTag-{UNIQUE}"}).raise_for_status()
        resp = api_get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] for t in tags]
        assert f"ListTag-{UNIQUE}" in names

    def test_update_tag(self):
        ensure_membership()
        create_resp = api_post("/api/tags", {"name": f"UpdTag-{UNIQUE}"})
        tag_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/tags/{tag_id}", {"name": f"RenamedTag-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"RenamedTag-{UNIQUE}"

    def test_delete_tag(self):
        ensure_membership()
        create_resp = api_post("/api/tags", {"name": f"DelTag-{UNIQUE}"})
        tag_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/tags/{tag_id}")
        assert resp.status_code == 204
        # Verify gone
        tags_resp = api_get("/api/tags")
        ids = [t["id"] for t in successful_json(tags_resp)]
        assert tag_id not in ids

    def test_delete_nonexistent_tag(self):
        ensure_membership()
        resp = api_delete("/api/tags/999999")
        assert resp.status_code == 404

    def test_update_nonexistent_tag(self):
        ensure_membership()
        resp = api_put("/api/tags/999999", {"name": "Ghost"})
        assert resp.status_code == 404

    def test_delete_tag_removes_from_recipes(self):
        """Deleting a tag should remove it from recipes' tag lists."""
        ensure_membership()
        tag_resp = api_post("/api/tags", {"name": f"RemTag-{UNIQUE}"})
        tag_id = successful_json(tag_resp)["id"]
        # Create recipe with that tag
        recipe_resp = api_post("/api/recipes", {
            "name": f"TagRecipe-{UNIQUE}",
            "tags": [tag_id],
            "items": [],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        # Delete tag
        api_delete(f"/api/tags/{tag_id}").raise_for_status()
        # Check recipe
        get_resp = api_get(f"/api/recipes/{recipe_id}")
        recipe = successful_json(get_resp)
        tag_ids = [t["id"] for t in recipe.get("tags", [])]
        assert tag_id not in tag_ids


# ════════════════════════════════════════════════════════════════════
# PART 6: Recipes CRUD
# ════════════════════════════════════════════════════════════════════


class TestRecipes:

    def test_create_recipe(self):
        ensure_membership()
        resp = api_post("/api/recipes", {
            "name": f"Pancakes-{UNIQUE}",
            "description": "Fluffy pancakes",
            "servings": 4,
            "time": 30,
            "sourceUrl": "https://example.com/pancakes",
            "tags": [],
            "items": [
                {"name": "Flour", "amount": 200, "unit": "g"},
                {"name": "Eggs", "amount": 2, "unit": None},
                {"name": "Milk", "amount": 300, "unit": "ml"},
            ],
        })
        assert resp.status_code == 201
        recipe = resp.json()
        assert recipe["name"] == f"Pancakes-{UNIQUE}"
        assert recipe["description"] == "Fluffy pancakes"
        assert recipe["servings"] == 4
        assert recipe["time"] == 30
        assert recipe["sourceUrl"] == "https://example.com/pancakes"
        assert "id" in recipe
        assert recipe["householdId"] == HOUSEHOLD_ID
        assert len(recipe["items"]) == 3

    def test_create_recipe_minimal(self):
        ensure_membership()
        resp = api_post("/api/recipes", {"name": f"Simple-{UNIQUE}", "items": []})
        assert resp.status_code == 201
        recipe = resp.json()
        assert recipe["name"] == f"Simple-{UNIQUE}"
        assert recipe.get("items") == []

    def test_create_recipe_with_tags(self):
        ensure_membership()
        tag_resp = api_post("/api/tags", {"name": f"RecipeTag-{UNIQUE}"})
        tag_id = successful_json(tag_resp)["id"]
        resp = api_post("/api/recipes", {
            "name": f"TaggedRecipe-{UNIQUE}",
            "tags": [tag_id],
            "items": [],
        })
        assert resp.status_code == 201
        recipe = resp.json()
        assert len(recipe["tags"]) == 1
        assert recipe["tags"][0]["id"] == tag_id
        assert recipe["tags"][0]["name"] == f"RecipeTag-{UNIQUE}"

    def test_get_recipe(self):
        ensure_membership()
        create_resp = api_post("/api/recipes", {
            "name": f"GetRecipe-{UNIQUE}",
            "items": [{"name": "Salt", "amount": 1, "unit": "tsp"}],
        })
        recipe_id = successful_json(create_resp)["id"]
        resp = api_get(f"/api/recipes/{recipe_id}")
        assert resp.status_code == 200
        recipe = resp.json()
        assert recipe["name"] == f"GetRecipe-{UNIQUE}"
        assert len(recipe["items"]) == 1
        assert recipe["items"][0]["name"] == "Salt"

    def test_list_recipes(self):
        ensure_membership()
        api_post("/api/recipes", {"name": f"ListRecipe-{UNIQUE}", "items": []}).raise_for_status()
        resp = api_get("/api/recipes")
        assert resp.status_code == 200
        recipes = resp.json()
        assert isinstance(recipes, list)
        names = [r["name"] for r in recipes]
        assert f"ListRecipe-{UNIQUE}" in names

    def test_search_recipes(self):
        ensure_membership()
        api_post("/api/recipes", {"name": f"Spaghetti-{UNIQUE}", "items": []}).raise_for_status()
        api_post("/api/recipes", {"name": f"Salad-{UNIQUE}", "items": []}).raise_for_status()
        resp = api_get("/api/recipes", params={"search": "spaghetti"})
        assert resp.status_code == 200
        recipes = resp.json()
        names = [r["name"] for r in recipes]
        assert f"Spaghetti-{UNIQUE}" in names
        assert f"Salad-{UNIQUE}" not in names

    def test_update_recipe(self):
        ensure_membership()
        create_resp = api_post("/api/recipes", {
            "name": f"UpdRecipe-{UNIQUE}",
            "servings": 2,
            "items": [{"name": "Butter", "amount": 50, "unit": "g"}],
        })
        recipe_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/recipes/{recipe_id}", {
            "name": f"UpdatedRecipe-{UNIQUE}",
            "servings": 6,
            "items": [{"name": "Butter", "amount": 100, "unit": "g"}],
        })
        assert resp.status_code == 200
        recipe = resp.json()
        assert recipe["name"] == f"UpdatedRecipe-{UNIQUE}"
        assert recipe["servings"] == 6
        assert recipe["items"][0]["amount"] == 100

    def test_delete_recipe(self):
        ensure_membership()
        create_resp = api_post("/api/recipes", {"name": f"DelRecipe-{UNIQUE}", "items": []})
        recipe_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/recipes/{recipe_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/recipes/{recipe_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_recipe(self):
        ensure_membership()
        resp = api_get("/api/recipes/999999")
        assert resp.status_code == 404

    def test_delete_nonexistent_recipe(self):
        ensure_membership()
        resp = api_delete("/api/recipes/999999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Shopping Lists CRUD
# ════════════════════════════════════════════════════════════════════


class TestShoppingLists:

    def test_create_shopping_list(self):
        ensure_membership()
        resp = api_post("/api/shopping-lists", {"name": f"Weekly-{UNIQUE}"})
        assert resp.status_code == 201
        sl = resp.json()
        assert sl["name"] == f"Weekly-{UNIQUE}"
        assert "id" in sl
        assert sl["householdId"] == HOUSEHOLD_ID

    def test_list_shopping_lists(self):
        ensure_membership()
        api_post("/api/shopping-lists", {"name": f"ListSL-{UNIQUE}"}).raise_for_status()
        resp = api_get("/api/shopping-lists")
        assert resp.status_code == 200
        lists = resp.json()
        assert isinstance(lists, list)
        names = [sl["name"] for sl in lists]
        assert f"ListSL-{UNIQUE}" in names

    def test_get_shopping_list_with_items(self):
        ensure_membership()
        create_resp = api_post("/api/shopping-lists", {"name": f"GetSL-{UNIQUE}"})
        sl_id = successful_json(create_resp)["id"]
        # Add an item
        api_post(
            f"/api/shopping-lists/{sl_id}/items", {"name": "Bread", "amount": 1}
        ).raise_for_status()
        resp = api_get(f"/api/shopping-lists/{sl_id}")
        assert resp.status_code == 200
        sl = resp.json()
        assert sl["name"] == f"GetSL-{UNIQUE}"
        assert "items" in sl
        assert len(sl["items"]) >= 1

    def test_update_shopping_list(self):
        ensure_membership()
        create_resp = api_post("/api/shopping-lists", {"name": f"UpdSL-{UNIQUE}"})
        sl_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/shopping-lists/{sl_id}", {"name": f"RenamedSL-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"RenamedSL-{UNIQUE}"

    def test_delete_shopping_list(self):
        ensure_membership()
        create_resp = api_post("/api/shopping-lists", {"name": f"DelSL-{UNIQUE}"})
        sl_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/shopping-lists/{sl_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/shopping-lists/{sl_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_shopping_list(self):
        ensure_membership()
        resp = api_get("/api/shopping-lists/999999")
        assert resp.status_code == 404

    def test_delete_nonexistent_shopping_list(self):
        ensure_membership()
        resp = api_delete("/api/shopping-lists/999999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Shopping List Items
# ════════════════════════════════════════════════════════════════════


class TestShoppingListItems:

    def test_add_item_to_shopping_list(self):
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"ItemSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {
            "name": "Apples",
            "amount": 5,
        })
        assert resp.status_code == 200
        item = resp.json()
        assert item["name"] == "Apples"
        assert item["amount"] == 5
        assert item["done"] is False
        assert "id" in item

    def test_update_shopping_list_item(self):
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"UpdItemSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        item_resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "Bananas", "amount": 3})
        item_id = successful_json(item_resp)["id"]
        resp = api_put(f"/api/shopping-lists/{sl_id}/items/{item_id}", {
            "amount": 6,
            "done": True,
        })
        assert resp.status_code == 200
        item = resp.json()
        assert item["amount"] == 6
        assert item["done"] is True

    def test_done_items_persist(self):
        """Marking an item as done keeps it in the list."""
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"DoneSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        item_resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "Oranges", "amount": 2})
        item_id = successful_json(item_resp)["id"]
        # Mark as done
        api_put(
            f"/api/shopping-lists/{sl_id}/items/{item_id}", {"done": True}
        ).raise_for_status()
        # Should still be visible
        sl = successful_json(api_get(f"/api/shopping-lists/{sl_id}"))
        item_ids = [i["id"] for i in sl["items"]]
        assert item_id in item_ids

    def test_delete_shopping_list_item(self):
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"DelItemSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        item_resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "Grapes", "amount": 1})
        item_id = successful_json(item_resp)["id"]
        resp = api_delete(f"/api/shopping-lists/{sl_id}/items/{item_id}")
        assert resp.status_code == 204
        # Verify gone
        sl = successful_json(api_get(f"/api/shopping-lists/{sl_id}"))
        item_ids = [i["id"] for i in sl["items"]]
        assert item_id not in item_ids

    def test_delete_nonexistent_item(self):
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"DelNoneSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_delete(f"/api/shopping-lists/{sl_id}/items/999999")
        assert resp.status_code == 404

    def test_merge_same_item_by_name(self):
        """Adding same item name (case-insensitive) should merge amounts."""
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"MergeSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        # Add "Milk" with amount 2
        api_post(
            f"/api/shopping-lists/{sl_id}/items", {"name": "Milk", "amount": 2}
        ).raise_for_status()
        # Add "milk" (lowercase) with amount 3 — should merge
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "milk", "amount": 3})
        assert resp.status_code == 200
        item = resp.json()
        assert item["amount"] == 5  # 2 + 3 = 5

        # Verify only one item on list
        sl = successful_json(api_get(f"/api/shopping-lists/{sl_id}"))
        milk_items = [i for i in sl["items"] if i["name"].lower() == "milk"]
        assert len(milk_items) == 1

    def test_merge_no_amount_items(self):
        """Merging items with no amounts: null + null = 2."""
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"MergeNullSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "Pepper"}).raise_for_status()
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "pepper"})
        assert resp.status_code == 200
        item = resp.json()
        assert item["amount"] == 2  # null + null → 2

    def test_merge_one_has_amount(self):
        """Merging items: 3 + null → 4 (null treated as 1)."""
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"MergeOneSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        api_post(
            f"/api/shopping-lists/{sl_id}/items", {"name": "Sugar", "amount": 3}
        ).raise_for_status()
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "sugar"})
        assert resp.status_code == 200
        item = resp.json()
        assert item["amount"] == 4  # 3 + 1 (null treated as 1) = 4

    def test_no_merge_with_done_items(self):
        """Done items should not be merged with new items."""
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"NoMergeDoneSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        # Add and mark as done
        item_resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "Butter", "amount": 1})
        item_id = successful_json(item_resp)["id"]
        api_put(
            f"/api/shopping-lists/{sl_id}/items/{item_id}", {"done": True}
        ).raise_for_status()
        # Add same name again — should create new item (not merge with done one)
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {"name": "butter", "amount": 2})
        assert resp.status_code == 200
        new_item = resp.json()
        assert new_item["id"] != item_id  # Different item
        assert new_item["amount"] == 2
        assert new_item["done"] is False


# ════════════════════════════════════════════════════════════════════
# PART 9: Recipe → Shopping List
# ════════════════════════════════════════════════════════════════════


class TestRecipeToShoppingList:

    def test_add_recipe_to_shopping_list(self):
        """Basic recipe → shopping list conversion."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"AddRecipeSL-{UNIQUE}",
            "servings": 4,
            "items": [
                {"name": "Flour", "amount": 200, "unit": "g"},
                {"name": "Sugar", "amount": 100, "unit": "g"},
            ],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"RecipeSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]

        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": recipe_id,
            "servings": 4,  # Same as recipe, no scaling
        })
        assert resp.status_code == 200
        sl = resp.json()
        assert "items" in sl
        item_names = [i["name"] for i in sl["items"]]
        assert "Flour" in item_names
        assert "Sugar" in item_names
        flour_item = next(i for i in sl["items"] if i["name"] == "Flour")
        assert flour_item["amount"] == 200

    def test_recipe_scaling_half(self):
        """Recipe with 4 servings, want 2 → halve amounts."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"ScaleRecipe-{UNIQUE}",
            "servings": 4,
            "items": [
                {"name": f"ScaleFlour-{UNIQUE}", "amount": 200, "unit": "g"},
                {"name": f"ScaleEggs-{UNIQUE}", "amount": 4, "unit": None},
            ],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"ScaleSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]

        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": recipe_id,
            "servings": 2,  # Half the recipe servings
        })
        assert resp.status_code == 200
        sl = resp.json()
        flour_item = next(i for i in sl["items"] if i["name"] == f"ScaleFlour-{UNIQUE}")
        eggs_item = next(i for i in sl["items"] if i["name"] == f"ScaleEggs-{UNIQUE}")
        assert flour_item["amount"] == 100  # 200 * (2/4) = 100
        assert eggs_item["amount"] == 2  # 4 * (2/4) = 2

    def test_recipe_scaling_double(self):
        """Recipe with 2 servings, want 4 → double amounts."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"DoubleRecipe-{UNIQUE}",
            "servings": 2,
            "items": [
                {"name": f"DoubleButter-{UNIQUE}", "amount": 50, "unit": "g"},
            ],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"DoubleSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]

        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": recipe_id,
            "servings": 4,
        })
        assert resp.status_code == 200
        sl = resp.json()
        butter = next(i for i in sl["items"] if i["name"] == f"DoubleButter-{UNIQUE}")
        assert butter["amount"] == 100  # 50 * (4/2) = 100

    def test_recipe_merge_with_existing_items(self):
        """Recipe items should merge with existing shopping list items."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"MergeRecipe-{UNIQUE}",
            "servings": 1,
            "items": [
                {"name": f"MergeMilk-{UNIQUE}", "amount": 2, "unit": "liters"},
            ],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"MergeRecipeSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        # Pre-add milk to shopping list
        api_post(
            f"/api/shopping-lists/{sl_id}/items",
            {"name": f"MergeMilk-{UNIQUE}", "amount": 1},
        ).raise_for_status()

        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": recipe_id,
            "servings": 1,
        })
        assert resp.status_code == 200
        sl = resp.json()
        milk_items = [i for i in sl["items"] if i["name"].lower() == f"mergemilk-{UNIQUE}".lower()]
        assert len(milk_items) == 1
        assert milk_items[0]["amount"] == 3  # 1 + 2 = 3

    def test_recipe_not_found(self):
        ensure_membership()
        sl_resp = api_post("/api/shopping-lists", {"name": f"NotFoundSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": 999999,
            "servings": 2,
        })
        assert resp.status_code == 404

    def test_shopping_list_not_found(self):
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"SLNotFound-{UNIQUE}",
            "servings": 1,
            "items": [],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        resp = api_post("/api/shopping-lists/999999/add-recipe", {
            "recipeId": recipe_id,
            "servings": 2,
        })
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Expenses CRUD
# ════════════════════════════════════════════════════════════════════


class TestExpenses:

    def test_create_expense(self):
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        resp = api_post("/api/expenses", {
            "amount": 50.0,
            "description": f"Groceries-{UNIQUE}",
            "date": "2024-03-15",
            "category": "Food",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        })
        assert resp.status_code == 201
        expense = resp.json()
        assert expense["amount"] == 50.0
        assert expense["description"] == f"Groceries-{UNIQUE}"
        assert expense["date"] == "2024-03-15"
        assert expense["category"] == "Food"
        assert expense["paidBy"] == USER_ID
        assert set(expense["splitBetween"]) == {USER_ID, USER2_ID}
        assert "id" in expense
        assert expense["householdId"] == HOUSEHOLD_ID

    def test_list_expenses(self):
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        api_post("/api/expenses", {
            "amount": 20.0,
            "description": f"ListExp-{UNIQUE}",
            "date": "2024-03-16",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        }).raise_for_status()
        resp = api_get("/api/expenses")
        assert resp.status_code == 200
        expenses = resp.json()
        assert isinstance(expenses, list)
        descs = [e["description"] for e in expenses]
        assert f"ListExp-{UNIQUE}" in descs

    def test_update_expense(self):
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        create_resp = api_post("/api/expenses", {
            "amount": 30.0,
            "description": f"UpdExp-{UNIQUE}",
            "date": "2024-03-17",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        })
        expense_id = successful_json(create_resp)["id"]
        resp = api_put(f"/api/expenses/{expense_id}", {
            "amount": 45.0,
            "description": f"UpdatedExp-{UNIQUE}",
        })
        assert resp.status_code == 200
        assert resp.json()["amount"] == 45.0
        assert resp.json()["description"] == f"UpdatedExp-{UNIQUE}"

    def test_delete_expense(self):
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        create_resp = api_post("/api/expenses", {
            "amount": 10.0,
            "description": f"DelExp-{UNIQUE}",
            "date": "2024-03-18",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        })
        expense_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/expenses/{expense_id}")
        assert resp.status_code == 204
        # Verify gone
        expenses = successful_json(api_get("/api/expenses"))
        ids = [e["id"] for e in expenses]
        assert expense_id not in ids

    def test_delete_nonexistent_expense(self):
        ensure_membership()
        resp = api_delete("/api/expenses/999999")
        assert resp.status_code == 404

    def test_expense_invalid_paid_by(self):
        """paidBy must be a household member."""
        ensure_membership()
        non_member = str(uuid.uuid4())
        resp = api_post("/api/expenses", {
            "amount": 10.0,
            "description": "Bad payer",
            "date": "2024-03-19",
            "paidBy": non_member,
            "splitBetween": [USER_ID],
        })
        assert resp.status_code == 400

    def test_expense_invalid_split_between(self):
        """splitBetween users must all be household members."""
        ensure_membership()
        non_member = str(uuid.uuid4())
        resp = api_post("/api/expenses", {
            "amount": 10.0,
            "description": "Bad split",
            "date": "2024-03-19",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, non_member],
        })
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 11: Expense Balances
# ════════════════════════════════════════════════════════════════════


class TestExpenseBalances:

    def test_balances_simple_two_users(self):
        """A pays 100, split between A and B → B owes A 50."""
        # Use fresh household for clean calculation
        h_id = str(uuid.uuid4())
        u_a = str(uuid.uuid4())
        u_b = str(uuid.uuid4())
        h_a = {"X-User-Id": u_a, "X-Household-Id": h_id, "Content-Type": "application/json"}
        h_b = {"X-User-Id": u_b, "X-Household-Id": h_id, "Content-Type": "application/json"}
        # Establish memberships
        api_get("/api/households", headers=h_a).raise_for_status()
        api_get("/api/households", headers=h_b).raise_for_status()

        api_post("/api/expenses", {
            "amount": 100.0,
            "description": "Dinner",
            "date": "2024-04-01",
            "paidBy": u_a,
            "splitBetween": [u_a, u_b],
        }, headers=h_a).raise_for_status()

        resp = api_get("/api/expenses/balances", headers=h_a)
        assert resp.status_code == 200
        balances = resp.json()
        assert isinstance(balances, list)
        assert len(balances) == 1
        b = balances[0]
        assert b["from"] == u_b  # B owes
        assert b["to"] == u_a  # A is owed
        assert b["amount"] == 50.0

    def test_balances_three_users_simplification(self):
        """
        A pays 90 split 3 ways (A,B,C) → each owes 30.
        B pays 60 split 3 ways (A,B,C) → each owes 20.

        Net: A = 90 - 30 - 20 = +40 (owed 40)
             B = 60 - 30 - 20 = +10 (owed 10)
             C = 0 - 30 - 20 = -50 (owes 50)

        Simplified: C owes A 40, C owes B 10
        """
        h_id = str(uuid.uuid4())
        u_a = str(uuid.uuid4())
        u_b = str(uuid.uuid4())
        u_c = str(uuid.uuid4())
        h_a = {"X-User-Id": u_a, "X-Household-Id": h_id, "Content-Type": "application/json"}
        h_b = {"X-User-Id": u_b, "X-Household-Id": h_id, "Content-Type": "application/json"}
        h_c = {"X-User-Id": u_c, "X-Household-Id": h_id, "Content-Type": "application/json"}
        api_get("/api/households", headers=h_a).raise_for_status()
        api_get("/api/households", headers=h_b).raise_for_status()
        api_get("/api/households", headers=h_c).raise_for_status()

        api_post("/api/expenses", {
            "amount": 90.0,
            "description": "Expense A",
            "date": "2024-04-01",
            "paidBy": u_a,
            "splitBetween": [u_a, u_b, u_c],
        }, headers=h_a).raise_for_status()

        api_post("/api/expenses", {
            "amount": 60.0,
            "description": "Expense B",
            "date": "2024-04-02",
            "paidBy": u_b,
            "splitBetween": [u_a, u_b, u_c],
        }, headers=h_a).raise_for_status()

        resp = api_get("/api/expenses/balances", headers=h_a)
        assert resp.status_code == 200
        balances = resp.json()
        # Total owed: C owes 50 total (40 to A, 10 to B)
        # Simplified should be 2 transactions
        assert len(balances) == 2
        total_from_c = sum(b["amount"] for b in balances if b["from"] == u_c)
        assert abs(total_from_c - 50.0) < 0.01
        # A should receive 40
        to_a = sum(b["amount"] for b in balances if b["to"] == u_a)
        assert abs(to_a - 40.0) < 0.01
        # B should receive 10
        to_b = sum(b["amount"] for b in balances if b["to"] == u_b)
        assert abs(to_b - 10.0) < 0.01

    def test_balances_empty(self):
        """No expenses → empty balances."""
        h_id = str(uuid.uuid4())
        u_a = str(uuid.uuid4())
        h_a = {"X-User-Id": u_a, "X-Household-Id": h_id, "Content-Type": "application/json"}
        api_get("/api/households", headers=h_a).raise_for_status()
        resp = api_get("/api/expenses/balances", headers=h_a)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_balances_all_even(self):
        """If everyone paid equally, balances should be empty."""
        h_id = str(uuid.uuid4())
        u_a = str(uuid.uuid4())
        u_b = str(uuid.uuid4())
        h_a = {"X-User-Id": u_a, "X-Household-Id": h_id, "Content-Type": "application/json"}
        h_b = {"X-User-Id": u_b, "X-Household-Id": h_id, "Content-Type": "application/json"}
        api_get("/api/households", headers=h_a)
        api_get("/api/households", headers=h_b)

        # A pays 50 split A,B → B owes 25
        api_post("/api/expenses", {
            "amount": 50.0,
            "description": "Exp1",
            "date": "2024-04-01",
            "paidBy": u_a,
            "splitBetween": [u_a, u_b],
        }, headers=h_a)
        # B pays 50 split A,B → A owes 25
        api_post("/api/expenses", {
            "amount": 50.0,
            "description": "Exp2",
            "date": "2024-04-02",
            "paidBy": u_b,
            "splitBetween": [u_a, u_b],
        }, headers=h_a)

        resp = api_get("/api/expenses/balances", headers=h_a)
        assert resp.status_code == 200
        balances = resp.json()
        assert balances == []


# ════════════════════════════════════════════════════════════════════
# PART 12: Meal Planner
# ════════════════════════════════════════════════════════════════════


class TestMealPlanner:

    def test_create_meal_plan_entry(self):
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"MealRecipe-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        resp = api_post("/api/meal-plan", {
            "date": "2024-04-15",
            "mealType": "dinner",
            "recipeId": recipe_id,
        })
        assert resp.status_code == 201
        entry = resp.json()
        assert entry["date"] == "2024-04-15"
        assert entry["mealType"] == "dinner"
        assert entry["recipeId"] == recipe_id
        assert "id" in entry
        assert entry["householdId"] == HOUSEHOLD_ID

    def test_list_meal_plan(self):
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"MealList-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        api_post("/api/meal-plan", {
            "date": "2024-04-16",
            "mealType": "breakfast",
            "recipeId": recipe_id,
        }).raise_for_status()
        resp = api_get("/api/meal-plan")
        assert resp.status_code == 200
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1

    def test_meal_plan_date_filter(self):
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"MealFilter-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        api_post("/api/meal-plan", {
            "date": "2024-05-01",
            "mealType": "lunch",
            "recipeId": recipe_id,
        })
        api_post("/api/meal-plan", {
            "date": "2024-06-01",
            "mealType": "dinner",
            "recipeId": recipe_id,
        })
        # Filter for May only
        resp = api_get("/api/meal-plan", params={"from": "2024-05-01", "to": "2024-05-31"})
        assert resp.status_code == 200
        entries = resp.json()
        for entry in entries:
            assert entry["date"] >= "2024-05-01"
            assert entry["date"] <= "2024-05-31"

    def test_delete_meal_plan_entry(self):
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"MealDel-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        create_resp = api_post("/api/meal-plan", {
            "date": "2024-04-20",
            "mealType": "lunch",
            "recipeId": recipe_id,
        })
        entry_id = successful_json(create_resp)["id"]
        resp = api_delete(f"/api/meal-plan/{entry_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_meal_plan(self):
        ensure_membership()
        resp = api_delete("/api/meal-plan/999999")
        assert resp.status_code == 404

    def test_meal_plan_invalid_recipe(self):
        """Creating meal plan with non-existent recipe should fail."""
        ensure_membership()
        resp = api_post("/api/meal-plan", {
            "date": "2024-04-21",
            "mealType": "breakfast",
            "recipeId": 999999,
        })
        assert resp.status_code == 400

    def test_delete_recipe_removes_meal_plans(self):
        """Deleting a recipe should remove associated meal plan entries."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"CascadeMeal-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        entry_resp = api_post("/api/meal-plan", {
            "date": "2024-04-22",
            "mealType": "dinner",
            "recipeId": recipe_id,
        })
        entry_id = successful_json(entry_resp)["id"]
        # Delete recipe
        api_delete(f"/api/recipes/{recipe_id}").raise_for_status()
        # Meal plan entry should be gone
        entries = successful_json(api_get("/api/meal-plan"))
        entry_ids = [e["id"] for e in entries]
        assert entry_id not in entry_ids


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_items_isolation(self):
        """Items from one household should not be visible in another."""
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        api_post("/api/items", {"name": f"IsoItem-{UNIQUE}"})
        resp = api_get("/api/items", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()]
        assert f"IsoItem-{UNIQUE}" not in names

    def test_recipes_isolation(self):
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        api_post("/api/recipes", {"name": f"IsoRecipe-{UNIQUE}", "items": []})
        resp = api_get("/api/recipes", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert f"IsoRecipe-{UNIQUE}" not in names

    def test_shopping_lists_isolation(self):
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        api_post("/api/shopping-lists", {"name": f"IsoSL-{UNIQUE}"})
        resp = api_get("/api/shopping-lists", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        names = [sl["name"] for sl in resp.json()]
        assert f"IsoSL-{UNIQUE}" not in names

    def test_expenses_isolation(self):
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        ensure_membership(HEADERS_USER2)
        api_post("/api/expenses", {
            "amount": 99.0,
            "description": f"IsoExp-{UNIQUE}",
            "date": "2024-04-01",
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        })
        resp = api_get("/api/expenses", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        descs = [e["description"] for e in resp.json()]
        assert f"IsoExp-{UNIQUE}" not in descs

    def test_tags_isolation(self):
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        api_post("/api/tags", {"name": f"IsoTag-{UNIQUE}"})
        resp = api_get("/api/tags", headers=HEADERS_OTHER)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert f"IsoTag-{UNIQUE}" not in names

    def test_cannot_access_other_household_shopping_list(self):
        """Trying to GET a shopping list from another household returns 404."""
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        sl_resp = api_post("/api/shopping-lists", {"name": f"ProtectedSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_get(f"/api/shopping-lists/{sl_id}", headers=HEADERS_OTHER)
        assert resp.status_code == 404

    def test_cannot_access_other_household_recipe(self):
        ensure_membership()
        ensure_membership(HEADERS_OTHER)
        recipe_resp = api_post("/api/recipes", {"name": f"ProtectedRecipe-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        resp = api_get(f"/api/recipes/{recipe_id}", headers=HEADERS_OTHER)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_shopping_list_item_category(self):
        """Shopping list items can have a category."""
        ensure_membership()
        cat_resp = api_post("/api/categories", {"name": f"EdgeCat-{UNIQUE}", "ordering": 1})
        cat_id = successful_json(cat_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"EdgeSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_post(f"/api/shopping-lists/{sl_id}/items", {
            "name": "Yogurt",
            "amount": 2,
            "category": cat_id,
        })
        assert resp.status_code == 200
        assert resp.json()["category"] == cat_id

    def test_recipe_null_servings_no_scaling(self):
        """Recipe with null servings → no scaling applied."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {
            "name": f"NullServings-{UNIQUE}",
            "servings": None,
            "items": [{"name": f"NoScale-{UNIQUE}", "amount": 10, "unit": "g"}],
        })
        recipe_id = successful_json(recipe_resp)["id"]
        sl_resp = api_post("/api/shopping-lists", {"name": f"NullServSL-{UNIQUE}"})
        sl_id = successful_json(sl_resp)["id"]
        resp = api_post(f"/api/shopping-lists/{sl_id}/add-recipe", {
            "recipeId": recipe_id,
            "servings": 5,
        })
        assert resp.status_code == 200
        sl = resp.json()
        item = next(i for i in sl["items"] if i["name"] == f"NoScale-{UNIQUE}")
        assert item["amount"] == 10  # No scaling

    def test_multiple_users_same_household(self):
        """Multiple users in same household see the same data."""
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        api_post("/api/items", {"name": f"SharedItem-{UNIQUE}"}).raise_for_status()
        # User2 should see it
        resp = api_get("/api/items", headers=HEADERS_USER2)
        names = [i["name"] for i in successful_json(resp)]
        assert f"SharedItem-{UNIQUE}" in names

    def test_expense_category_nullable(self):
        """Expense category can be null."""
        ensure_membership()
        ensure_membership(HEADERS_USER2)
        resp = api_post("/api/expenses", {
            "amount": 15.0,
            "description": f"NullCatExp-{UNIQUE}",
            "date": "2024-04-01",
            "category": None,
            "paidBy": USER_ID,
            "splitBetween": [USER_ID, USER2_ID],
        })
        assert resp.status_code == 201
        assert resp.json()["category"] is None

    def test_recipe_items_null_amount(self):
        """Recipe items can have null amount."""
        ensure_membership()
        resp = api_post("/api/recipes", {
            "name": f"NullAmtRecipe-{UNIQUE}",
            "items": [{"name": "Salt", "amount": None, "unit": "pinch"}],
        })
        assert resp.status_code == 201
        recipe = resp.json()
        assert recipe["items"][0]["amount"] is None

    def test_meal_type_validation(self):
        """Meal type must be breakfast, lunch, or dinner."""
        ensure_membership()
        recipe_resp = api_post("/api/recipes", {"name": f"MealTypeRecipe-{UNIQUE}", "items": []})
        recipe_id = successful_json(recipe_resp)["id"]
        # Valid types should work
        for meal_type in ["breakfast", "lunch", "dinner"]:
            resp = api_post("/api/meal-plan", {
                "date": "2024-04-25",
                "mealType": meal_type,
                "recipeId": recipe_id,
            })
            assert resp.status_code == 201, f"mealType '{meal_type}' should be valid"
