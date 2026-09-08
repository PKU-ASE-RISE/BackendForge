"""
BackendForge — Comprehensive Correctness Tests for Mealie Task

Tests ALL 10 business rules and ALL endpoint groups.
"""

import os
import uuid
import datetime

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
GROUP_ID = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000003"
USER_ID_2 = "00000000-0000-0000-0000-000000000004"  # Second user for rating tests
GROUP_ID_2 = "00000000-0000-0000-0000-000000000011"  # Second group for isolation tests
HOUSEHOLD_ID_2 = "00000000-0000-0000-0000-000000000012"  # Second household for isolation tests

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

HEADERS_GROUP2 = {
    "X-Group-Id": GROUP_ID_2,
    "X-User-Id": USER_ID_2,
    "X-Household-Id": HOUSEHOLD_ID_2,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


def _reset_test_context():
    """Give every test fresh group, household, and user identities."""
    global GROUP_ID, HOUSEHOLD_ID, USER_ID, USER_ID_2, GROUP_ID_2, HOUSEHOLD_ID_2
    global HEADERS, HEADERS_USER2, HEADERS_GROUP2, UNIQUE

    GROUP_ID = str(uuid.uuid4())
    HOUSEHOLD_ID = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    USER_ID_2 = str(uuid.uuid4())
    GROUP_ID_2 = str(uuid.uuid4())
    HOUSEHOLD_ID_2 = str(uuid.uuid4())
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
    HEADERS_GROUP2 = {
        "X-Group-Id": GROUP_ID_2,
        "X-User-Id": USER_ID_2,
        "X-Household-Id": HOUSEHOLD_ID_2,
        "Content-Type": "application/json",
    }
    UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def _utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date()


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


def api_patch(path, json_data=None, headers=None):
    return requests.patch(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, params=None, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ── Domain Helpers ──

def create_recipe(name):
    """POST /api/recipes → returns slug (string)."""
    resp = api_post("/api/recipes", {"name": name})
    assert resp.status_code == 201, f"Create recipe failed: {resp.status_code} {resp.text}"
    result = resp.json()
    if isinstance(result, str):
        return result
    return result.get("slug") or result.get("id") or str(result)


def get_recipe(slug_or_id):
    """GET /api/recipes/{slug} → full Recipe object."""
    resp = api_get(f"/api/recipes/{slug_or_id}")
    assert resp.status_code == 200, f"Get recipe failed: {resp.status_code} {resp.text}"
    return resp.json()


def update_recipe(slug, data):
    """PUT /api/recipes/{slug}."""
    resp = api_put(f"/api/recipes/{slug}", data)
    assert resp.status_code == 200, f"Update recipe failed: {resp.status_code} {resp.text}"
    return resp


def create_food(name):
    """POST /api/foods → IngredientFood."""
    resp = api_post("/api/foods", {"name": name})
    assert resp.status_code == 201, f"Create food failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_unit(name, abbreviation=""):
    """POST /api/units → IngredientUnit."""
    resp = api_post("/api/units", {"name": name, "abbreviation": abbreviation})
    assert resp.status_code == 201, f"Create unit failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_shopping_list(name):
    """POST /api/households/shopping/lists → ShoppingListOut."""
    resp = api_post("/api/households/shopping/lists", {"name": name})
    assert resp.status_code == 201, f"Create shopping list failed: {resp.status_code} {resp.text}"
    return resp.json()


def get_shopping_list(list_id):
    """GET /api/households/shopping/lists/{id} → ShoppingListOut."""
    resp = api_get(f"/api/households/shopping/lists/{list_id}")
    assert resp.status_code == 200, f"Get shopping list failed: {resp.status_code} {resp.text}"
    return resp.json()


def add_shopping_item(shopping_list_id, food_id=None, unit_id=None, quantity=1, note="", checked=False):
    """POST /api/households/shopping/items → ShoppingListItemsCollectionOut."""
    data = {
        "shoppingListId": shopping_list_id,
        "quantity": quantity,
        "note": note,
        "checked": checked,
    }
    if food_id:
        data["foodId"] = food_id
    if unit_id:
        data["unitId"] = unit_id
    resp = api_post("/api/households/shopping/items", data)
    assert resp.status_code == 201, f"Create shopping item failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_tag(name):
    """POST /api/organizers/tags and return the tag object with id."""
    resp = api_post("/api/organizers/tags", {"name": name})
    assert resp.status_code == 201, f"Create tag failed: {resp.status_code} {resp.text}"
    tag = resp.json()
    if tag and tag.get("id"):
        return tag
    # Fallback: look it up via list
    resp2 = api_get("/api/organizers/tags", params={"search": name, "perPage": 100})
    if resp2.status_code == 200:
        for t in resp2.json().get("items", []):
            if t.get("name") == name:
                return t
    return tag


def create_category(name):
    """POST /api/organizers/categories and return the category object with id."""
    resp = api_post("/api/organizers/categories", {"name": name})
    assert resp.status_code == 201, f"Create category failed: {resp.status_code} {resp.text}"
    cat = resp.json()
    if cat and cat.get("id"):
        return cat
    # Fallback: look it up
    resp2 = api_get("/api/organizers/categories", params={"search": name, "perPage": 100})
    if resp2.status_code == 200:
        for c in resp2.json().get("items", []):
            if c.get("name") == name:
                return c
    return cat


def next_weekday(day_name):
    """Return the ISO date string of the next occurrence of a weekday."""
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}
    target = days[day_name]
    today = _utc_today()
    days_ahead = target - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).isoformat()


# ════════════════════════════════════════════════════════════════════
# PART 1: Basic CRUD for All Endpoint Groups (~20 tests)
# ════════════════════════════════════════════════════════════════════


class TestRecipeCRUD:
    """Create → read by slug → update → verify → delete → verify 404."""

    def test_recipe_lifecycle(self):
        name = f"CRUD Recipe {UNIQUE}"
        slug = create_recipe(name)

        # Read by slug
        recipe = get_recipe(slug)
        assert recipe["name"] == name
        recipe_id = recipe["id"]

        # Update description (keep name to preserve slug)
        update_recipe(slug, {**recipe, "description": "Updated description"})
        recipe = get_recipe(slug)
        assert recipe.get("description") == "Updated description"

        # Delete
        resp = api_delete(f"/api/recipes/{slug}")
        assert resp.status_code == 200

        # Verify 404
        resp = api_get(f"/api/recipes/{slug}")
        assert resp.status_code == 404

    def test_recipe_with_ingredients_and_instructions(self):
        """Create recipe, add structured ingredients and instructions, read them back."""
        slug = create_recipe(f"Structured {UNIQUE}")
        recipe = get_recipe(slug)

        food = create_food(f"butter-{UNIQUE}-rcrud")
        unit = create_unit(f"tbsp-{UNIQUE}-rcrud", abbreviation="tbsp")

        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 2,
                    "note": "softened",
                },
            ],
            "recipeInstructions": [
                {"text": "Melt butter."},
                {"text": "Stir until golden."},
            ],
        })

        recipe = get_recipe(slug)
        assert len(recipe.get("recipeIngredient", [])) == 1
        assert len(recipe.get("recipeInstructions", [])) == 2
        assert recipe["recipeIngredient"][0]["quantity"] == 2


class TestCommentCRUD:
    """Create comment → read → update text → delete."""

    def test_comment_lifecycle(self):
        slug = create_recipe(f"CommentRecipe {UNIQUE}")
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        # Create comment via POST /api/comments
        resp = api_post("/api/comments", {"recipeId": recipe_id, "text": f"Great recipe {UNIQUE}"})
        assert resp.status_code == 201
        comment = resp.json()
        comment_id = comment["id"]
        assert comment["text"] == f"Great recipe {UNIQUE}"

        # Read
        resp = api_get(f"/api/comments/{comment_id}")
        assert resp.status_code == 200
        assert resp.json()["text"] == f"Great recipe {UNIQUE}"

        # Update
        resp = api_put(f"/api/comments/{comment_id}", {"id": comment_id, "text": "Updated comment"})
        assert resp.status_code == 200
        assert resp.json()["text"] == "Updated comment"

        # Delete
        resp = api_delete(f"/api/comments/{comment_id}")
        assert resp.status_code == 200


class TestFoodCRUD:
    """Create food → read → update name → delete."""

    def test_food_lifecycle(self):
        name = f"Paprika {UNIQUE}"
        food = create_food(name)
        food_id = food["id"]
        assert food["name"] == name

        # Read
        resp = api_get(f"/api/foods/{food_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name

        # Update
        resp = api_put(f"/api/foods/{food_id}", {**food, "name": f"Smoked Paprika {UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Smoked Paprika {UNIQUE}"

        # Delete
        resp = api_delete(f"/api/foods/{food_id}")
        assert resp.status_code == 200


class TestUnitCRUD:
    """Create unit → read → update → delete."""

    def test_unit_lifecycle(self):
        name = f"Gallons {UNIQUE}"
        unit = create_unit(name, abbreviation="gal")
        unit_id = unit["id"]
        assert unit["name"] == name

        # Read
        resp = api_get(f"/api/units/{unit_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name

        # Update
        resp = api_put(f"/api/units/{unit_id}", {**unit, "name": f"Imperial Gallons {UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Imperial Gallons {UNIQUE}"

        # Delete
        resp = api_delete(f"/api/units/{unit_id}")
        assert resp.status_code == 200


class TestCategoryCRUD:
    """Create → read → slug lookup → update → delete."""

    def test_category_lifecycle(self):
        name = f"Appetizers {UNIQUE}"
        cat = create_category(name)
        cat_id = cat["id"]

        # Read by id
        resp = api_get(f"/api/organizers/categories/{cat_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name

        # Slug lookup
        slug = cat.get("slug", name.lower().replace(" ", "-"))
        resp = api_get(f"/api/organizers/categories/slug/{slug}")
        assert resp.status_code == 200

        # Update
        new_name = f"Starters {UNIQUE}"
        resp = api_put(f"/api/organizers/categories/{cat_id}", {"name": new_name})
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/organizers/categories/{cat_id}")
        assert resp.status_code == 200


class TestTagCRUD:
    """Create → read → slug lookup → update → delete."""

    def test_tag_lifecycle(self):
        name = f"Vegan {UNIQUE}"
        tag = create_tag(name)
        tag_id = tag["id"]

        # Read by id
        resp = api_get(f"/api/organizers/tags/{tag_id}")
        assert resp.status_code == 200

        # Slug lookup
        slug = tag.get("slug", name.lower().replace(" ", "-"))
        resp = api_get(f"/api/organizers/tags/slug/{slug}")
        assert resp.status_code == 200

        # Update
        resp = api_put(f"/api/organizers/tags/{tag_id}", {"name": f"Raw Vegan {UNIQUE}"})
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/organizers/tags/{tag_id}")
        assert resp.status_code == 200


class TestToolCRUD:
    """Create → read → slug lookup → update → delete."""

    def test_tool_lifecycle(self):
        name = f"Blender {UNIQUE}"
        resp = api_post("/api/organizers/tools", {"name": name, "slug": f"blender-{UNIQUE}"})
        assert resp.status_code == 201
        tool = resp.json()
        tool_id = tool["id"]

        # Read
        resp = api_get(f"/api/organizers/tools/{tool_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name

        # Slug lookup
        slug = tool.get("slug", f"blender-{UNIQUE}")
        resp = api_get(f"/api/organizers/tools/slug/{slug}")
        assert resp.status_code == 200

        # Update
        resp = api_put(f"/api/organizers/tools/{tool_id}", {**tool, "name": f"Immersion Blender {UNIQUE}"})
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/organizers/tools/{tool_id}")
        assert resp.status_code == 200


class TestCookbookCRUD:
    """Create → read → update → delete."""

    def test_cookbook_lifecycle(self):
        name = f"Weeknight Dinners {UNIQUE}"
        data = {
            "name": name,
            "description": "Quick meals",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
        }
        resp = api_post("/api/households/cookbooks", data)
        assert resp.status_code == 201
        cookbook = resp.json()
        cookbook_id = cookbook["id"]

        # Read
        resp = api_get(f"/api/households/cookbooks/{cookbook_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == name

        # Update
        resp = api_put(f"/api/households/cookbooks/{cookbook_id}", {
            **cookbook, "name": f"Quick Weeknight {UNIQUE}"
        })
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/households/cookbooks/{cookbook_id}")
        assert resp.status_code == 200


class TestMealPlanCRUD:
    """Create → read → update → delete."""

    def test_mealplan_lifecycle(self):
        date = _utc_today().isoformat()
        resp = api_post("/api/households/mealplans", {
            "date": date,
            "entryType": "lunch",
            "title": f"Lunch Plan {UNIQUE}",
            "text": "Some notes",
        })
        assert resp.status_code == 201
        plan = resp.json()
        plan_id = plan["id"]

        # Read
        resp = api_get(f"/api/households/mealplans/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == f"Lunch Plan {UNIQUE}"

        # Update
        resp = api_put(f"/api/households/mealplans/{plan_id}", {
            **plan, "title": f"Updated Lunch {UNIQUE}"
        })
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/households/mealplans/{plan_id}")
        assert resp.status_code == 200


class TestMealPlanRuleCRUD:
    """Create → read → update → delete."""

    def test_rule_lifecycle(self):
        data = {
            "day": "friday",
            "entryType": "dinner",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
        }
        resp = api_post("/api/households/mealplans/rules", data)
        assert resp.status_code == 201
        rule = resp.json()
        rule_id = rule["id"]

        # Read
        resp = api_get(f"/api/households/mealplans/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["day"] == "friday"

        # Update
        resp = api_put(f"/api/households/mealplans/rules/{rule_id}", {
            **rule, "day": "saturday"
        })
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/households/mealplans/rules/{rule_id}")
        assert resp.status_code == 200


class TestShoppingListCRUD:
    """Create → read → update → delete."""

    def test_shopping_list_lifecycle(self):
        name = f"Groceries {UNIQUE}"
        sl = create_shopping_list(name)
        sl_id = sl["id"]

        # Read
        detail = get_shopping_list(sl_id)
        assert detail.get("name") == name

        # Update
        resp = api_put(f"/api/households/shopping/lists/{sl_id}", {
            **detail, "name": f"Updated Groceries {UNIQUE}",
            "groupId": GROUP_ID, "userId": USER_ID, "id": sl_id,
        })
        assert resp.status_code == 200
        assert resp.json().get("name") == f"Updated Groceries {UNIQUE}"

        # Delete
        resp = api_delete(f"/api/households/shopping/lists/{sl_id}")
        assert resp.status_code == 200


class TestShoppingItemCRUD:
    """Create → read → update → delete."""

    def test_shopping_item_lifecycle(self):
        sl = create_shopping_list(f"ItemTest {UNIQUE}")
        food = create_food(f"Eggs {UNIQUE} si")

        # Create
        result = add_shopping_item(sl["id"], food_id=food["id"], quantity=12, note="dozen")
        created = result.get("createdItems", [])
        assert len(created) >= 1, f"Expected at least 1 created item, got {created}"
        item = created[0]
        item_id = item["id"]

        # Read
        resp = api_get(f"/api/households/shopping/items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["quantity"] == 12

        # Update via PUT on the item
        resp = api_put(f"/api/households/shopping/items/{item_id}", {
            **item, "quantity": 24, "shoppingListId": sl["id"],
        })
        assert resp.status_code == 200

        # Delete
        resp = api_delete(f"/api/households/shopping/items/{item_id}")
        assert resp.status_code == 200


class TestUserSelf:
    """Read self → update."""

    def test_user_self(self):
        resp = api_get("/api/users/self")
        assert resp.status_code == 200
        user = resp.json()
        assert user["id"] == USER_ID

    def test_user_update(self):
        resp = api_put(f"/api/users/{USER_ID}", {
            "id": USER_ID,
            "fullName": f"Test User {UNIQUE}",
            "admin": False,
        })
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Business Rule Tests — THE HARD ONES (~24 tests)
# ════════════════════════════════════════════════════════════════════


class TestRule1ShoppingListMerging:
    """Rule 1: Same food on unchecked list → merge quantities."""

    def test_b1a_same_food_same_unit_merges(self):
        """Add two unchecked items with same food+unit → ONE item with summed qty."""
        food = create_food(f"flour-{UNIQUE}-b1a")
        unit = create_unit(f"cups-{UNIQUE}-b1a")
        sl = create_shopping_list(f"List-{UNIQUE}-b1a")

        add_shopping_item(sl["id"], food_id=food["id"], unit_id=unit["id"], quantity=2)
        add_shopping_item(sl["id"], food_id=food["id"], unit_id=unit["id"], quantity=3)

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        matching = [i for i in items
                    if i.get("foodId") == food["id"] and not i.get("checked")]
        assert len(matching) == 1, (
            f"Expected 1 merged item for food {food['id']}, got {len(matching)}: "
            f"{[(i.get('foodId'), i.get('quantity')) for i in items]}"
        )
        assert matching[0]["quantity"] == 5, (
            f"Expected merged qty 5 (2+3), got {matching[0]['quantity']}"
        )

    def test_b1b_different_units_no_merge(self):
        """Same food but different (non-convertible) units → separate items."""
        food = create_food(f"milk-{UNIQUE}-b1b")
        unit_a = create_unit(f"cups-{UNIQUE}-b1b")
        unit_b = create_unit(f"liters-{UNIQUE}-b1b")
        sl = create_shopping_list(f"List-{UNIQUE}-b1b")

        add_shopping_item(sl["id"], food_id=food["id"], unit_id=unit_a["id"], quantity=2)
        add_shopping_item(sl["id"], food_id=food["id"], unit_id=unit_b["id"], quantity=1)

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        matching = [i for i in items if i.get("foodId") == food["id"]]
        assert len(matching) == 2, (
            f"Different units should NOT merge, expected 2 items, got {len(matching)}"
        )

    def test_b1c_checked_item_no_merge(self):
        """Checked item with same food should NOT merge with unchecked."""
        food = create_food(f"eggs-{UNIQUE}-b1c")
        sl = create_shopping_list(f"List-{UNIQUE}-b1c")

        add_shopping_item(sl["id"], food_id=food["id"], quantity=6, checked=True)
        add_shopping_item(sl["id"], food_id=food["id"], quantity=6, checked=False)

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        matching = [i for i in items if i.get("foodId") == food["id"]]
        assert len(matching) == 2, (
            f"Checked+unchecked should NOT merge, expected 2 items, got {len(matching)}"
        )


class TestRule2RecipeToShoppingList:
    """Rule 2: Adding a recipe to a shopping list extracts ingredients as items."""

    def test_b2a_recipe_adds_items_with_references(self):
        """Add recipe with 3 ingredients → list gets 3 items with recipeReferences."""
        foods = [create_food(f"food-{UNIQUE}-b2a-{i}") for i in range(3)]
        unit = create_unit(f"unit-{UNIQUE}-b2a")

        slug = create_recipe(f"Recipe-{UNIQUE}-b2a")
        recipe = get_recipe(slug)

        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": f["id"], "name": f["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": i + 1,
                    "note": f"ingredient {i}",
                }
                for i, f in enumerate(foods)
            ],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = create_shopping_list(f"List-{UNIQUE}-b2a")
        resp = api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
            {"recipeId": recipe_id},
        )
        assert resp.status_code == 200

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        assert len(items) >= 3, f"Expected ≥3 items from recipe, got {len(items)}"

        # Each item should reference the recipe
        for item in items:
            refs = item.get("recipeReferences", [])
            ref_recipe_ids = [r.get("recipeId") for r in refs]
            assert recipe_id in ref_recipe_ids, (
                f"Item {item.get('id')} missing recipeReference to {recipe_id}, "
                f"has refs: {ref_recipe_ids}"
            )

    def test_b2b_add_same_recipe_twice_doubles_qty(self):
        """Adding the same recipe twice should double quantities, not duplicate items."""
        food = create_food(f"food-{UNIQUE}-b2b")
        unit = create_unit(f"unit-{UNIQUE}-b2b")

        slug = create_recipe(f"Recipe-{UNIQUE}-b2b")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 2,
                    "note": "test",
                }
            ],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = create_shopping_list(f"List-{UNIQUE}-b2b")

        # Add recipe once
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
            {"recipeId": recipe_id},
        )
        # Add same recipe again
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
            {"recipeId": recipe_id},
        )

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        food_items = [i for i in items if i.get("foodId") == food["id"]]
        assert len(food_items) == 1, (
            f"Same recipe twice should merge, expected 1 item, got {len(food_items)}"
        )
        assert food_items[0]["quantity"] == 4, (
            f"Expected qty 4 (2+2), got {food_items[0]['quantity']}"
        )

    def test_b2c_recipe_increment_quantity_scales(self):
        """recipeIncrementQuantity=2 should double all ingredient quantities."""
        food = create_food(f"food-{UNIQUE}-b2c")
        unit = create_unit(f"unit-{UNIQUE}-b2c")

        slug = create_recipe(f"Recipe-{UNIQUE}-b2c")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 3,
                    "note": "test",
                }
            ],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = create_shopping_list(f"List-{UNIQUE}-b2c")
        resp = api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
            {"recipeId": recipe_id, "recipeIncrementQuantity": 2},
        )
        assert resp.status_code == 200

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        food_items = [i for i in items if i.get("foodId") == food["id"]]
        assert len(food_items) == 1
        assert food_items[0]["quantity"] == 6, (
            f"Expected qty 6 (3 × scale 2), got {food_items[0]['quantity']}"
        )


class TestRule3RemoveRecipeFromShoppingList:
    """Rule 3: Removing recipe decrements quantities; 0-qty items are deleted."""

    def test_b3a_remove_recipe_deletes_zero_qty_items(self):
        """Add recipe → remove it → items at qty 0 should vanish."""
        food = create_food(f"food-{UNIQUE}-b3a")
        unit = create_unit(f"unit-{UNIQUE}-b3a")

        slug = create_recipe(f"Recipe-{UNIQUE}-b3a")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 5,
                    "note": "test",
                }
            ],
        })
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        sl = create_shopping_list(f"List-{UNIQUE}-b3a")
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}",
            {"recipeId": recipe_id},
        )

        # Verify item exists
        detail = get_shopping_list(sl["id"])
        items_before = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items_before) >= 1, "Item should exist after adding recipe"

        # Remove recipe
        resp = api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_id}/delete",
            {"recipeDecrementQuantity": 1},
        )
        assert resp.status_code == 200

        # Items should be gone (qty hit 0, no other recipe references)
        detail = get_shopping_list(sl["id"])
        items_after = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items_after) == 0, (
            f"Items at qty 0 with no other references should be deleted, "
            f"got {len(items_after)} remaining"
        )

    def test_b3b_remove_one_recipe_preserves_other(self):
        """Two recipes share a food → remove one → item persists with other's qty."""
        food = create_food(f"shared-{UNIQUE}-b3b")
        unit = create_unit(f"unit-{UNIQUE}-b3b")

        # Recipe A: qty 2
        slug_a = create_recipe(f"RecipeA-{UNIQUE}-b3b")
        recipe_a = get_recipe(slug_a)
        update_recipe(slug_a, {
            **recipe_a,
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 2, "note": "a",
            }],
        })
        recipe_a = get_recipe(slug_a)

        # Recipe B: qty 3
        slug_b = create_recipe(f"RecipeB-{UNIQUE}-b3b")
        recipe_b = get_recipe(slug_b)
        update_recipe(slug_b, {
            **recipe_b,
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 3, "note": "b",
            }],
        })
        recipe_b = get_recipe(slug_b)

        sl = create_shopping_list(f"List-{UNIQUE}-b3b")

        # Add both recipes
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_a['id']}",
            {"recipeId": recipe_a["id"]},
        )
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_b['id']}",
            {"recipeId": recipe_b["id"]},
        )

        # Should be merged: qty 5
        detail = get_shopping_list(sl["id"])
        food_items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(food_items) == 1, f"Both recipes' items should merge, got {len(food_items)}"
        assert food_items[0]["quantity"] == 5, f"Expected 5, got {food_items[0]['quantity']}"

        # Remove recipe A
        api_post(
            f"/api/households/shopping/lists/{sl['id']}/recipe/{recipe_a['id']}/delete",
            {"recipeDecrementQuantity": 1},
        )

        # Item should still exist with qty 3 (recipe B's contribution)
        detail = get_shopping_list(sl["id"])
        food_items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(food_items) == 1, (
            f"Item should still exist after removing only recipe A, got {len(food_items)}"
        )
        assert food_items[0]["quantity"] == 3, (
            f"Expected qty 3 after removing A's contribution (2), got {food_items[0]['quantity']}"
        )


class TestRule4RatingAggregation:
    """Rule 4: recipe.rating = average of all user ratings, recalculated on change."""

    def test_b4a_average_of_two_users(self):
        """User1 rates 4.0, User2 rates 2.0 → recipe.rating = 3.0."""
        slug = create_recipe(f"RateMe-{UNIQUE}-b4a")
        get_recipe(slug)  # ensure exists

        resp = api_post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 4.0})
        assert resp.status_code == 200

        resp = api_post(f"/api/users/{USER_ID_2}/ratings/{slug}",
                        {"rating": 2.0}, headers=HEADERS_USER2)
        assert resp.status_code == 200

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(3.0, abs=0.1), (
            f"Expected average 3.0, got {recipe.get('rating')}"
        )

    def test_b4b_update_rating_changes_average(self):
        """Change one user's rating → average updates."""
        slug = create_recipe(f"RateMe-{UNIQUE}-b4b")

        api_post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 4.0})
        api_post(f"/api/users/{USER_ID_2}/ratings/{slug}",
                 {"rating": 2.0}, headers=HEADERS_USER2)

        # Average = 3.0
        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(3.0, abs=0.1)

        # User2 changes to 4.0 → new average = 4.0
        api_post(f"/api/users/{USER_ID_2}/ratings/{slug}",
                 {"rating": 4.0}, headers=HEADERS_USER2)

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(4.0, abs=0.1), (
            f"Expected updated average 4.0, got {recipe.get('rating')}"
        )

    def test_b4c_rating_is_per_recipe(self):
        """Each recipe has its own independent rating."""
        slug_a = create_recipe(f"RecipeA-{UNIQUE}-b4c")
        slug_b = create_recipe(f"RecipeB-{UNIQUE}-b4c")

        api_post(f"/api/users/{USER_ID}/ratings/{slug_a}", {"rating": 5.0})
        api_post(f"/api/users/{USER_ID}/ratings/{slug_b}", {"rating": 1.0})

        recipe_a = get_recipe(slug_a)
        recipe_b = get_recipe(slug_b)
        assert recipe_a.get("rating") == pytest.approx(5.0, abs=0.1), (
            f"Recipe A rating should be 5.0, got {recipe_a.get('rating')}"
        )
        assert recipe_b.get("rating") == pytest.approx(1.0, abs=0.1), (
            f"Recipe B rating should be 1.0, got {recipe_b.get('rating')}"
        )


class TestRule5TagCategoryFoodDedup:
    """Rule 5: Tags/categories/foods are deduplicated by name within a group."""

    def test_b5a_tag_dedup_across_recipes(self):
        """Two recipes with tag 'Italian' → only ONE 'Italian' tag in the system."""
        tag_name = f"Italian-{UNIQUE}-b5a"

        slug_a = create_recipe(f"RecipeA-{UNIQUE}-b5a")
        recipe_a = get_recipe(slug_a)
        update_recipe(slug_a, {**recipe_a, "tags": [{"name": tag_name}]})

        slug_b = create_recipe(f"RecipeB-{UNIQUE}-b5b")
        recipe_b = get_recipe(slug_b)
        update_recipe(slug_b, {**recipe_b, "tags": [{"name": tag_name}]})

        # Both recipes should have the tag
        recipe_a = get_recipe(slug_a)
        recipe_b = get_recipe(slug_b)
        a_tags = [t["name"] for t in (recipe_a.get("tags") or [])]
        b_tags = [t["name"] for t in (recipe_b.get("tags") or [])]
        assert tag_name in a_tags, f"Recipe A missing tag: {a_tags}"
        assert tag_name in b_tags, f"Recipe B missing tag: {b_tags}"

        # But there should be exactly ONE tag with this name globally
        resp = api_get("/api/organizers/tags", params={"search": tag_name, "perPage": 100})
        assert resp.status_code == 200
        all_tags = resp.json().get("items", [])
        matching = [t for t in all_tags if t.get("name") == tag_name]
        assert len(matching) == 1, (
            f"Expected exactly 1 '{tag_name}' tag, got {len(matching)}: "
            f"{[t.get('id') for t in matching]}"
        )

        # Both recipes should reference the SAME tag id
        a_tag_ids = [t["id"] for t in (recipe_a.get("tags") or []) if t["name"] == tag_name]
        b_tag_ids = [t["id"] for t in (recipe_b.get("tags") or []) if t["name"] == tag_name]
        assert a_tag_ids == b_tag_ids, (
            f"Both recipes should share the same tag id: A={a_tag_ids}, B={b_tag_ids}"
        )

    def test_b5b_category_dedup_across_recipes(self):
        """Two recipes with category 'Desserts' → only ONE category."""
        cat_name = f"Desserts-{UNIQUE}-b5b"

        slug_a = create_recipe(f"RecipeA-{UNIQUE}-b5b")
        recipe_a = get_recipe(slug_a)
        update_recipe(slug_a, {**recipe_a, "recipeCategory": [{"name": cat_name}]})

        slug_b = create_recipe(f"RecipeB-{UNIQUE}-b5b")
        recipe_b = get_recipe(slug_b)
        update_recipe(slug_b, {**recipe_b, "recipeCategory": [{"name": cat_name}]})

        resp = api_get("/api/organizers/categories", params={"search": cat_name, "perPage": 100})
        assert resp.status_code == 200
        all_cats = resp.json().get("items", [])
        matching = [c for c in all_cats if c.get("name") == cat_name]
        assert len(matching) == 1, (
            f"Expected 1 '{cat_name}' category, got {len(matching)}"
        )

    def test_b5c_food_dedup_via_recipe_ingredient(self):
        """Create food 'flour', then recipe with ingredient food 'flour' → reuses it."""
        food_name = f"flour-{UNIQUE}-b5c"
        food = create_food(food_name)

        slug = create_recipe(f"Recipe-{UNIQUE}-b5c")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [
                {"food": {"name": food_name}, "quantity": 1, "note": "test"}
            ],
        })

        # Should still be only one food with this name
        resp = api_get("/api/foods", params={"search": food_name, "perPage": 100})
        assert resp.status_code == 200
        all_foods = resp.json().get("items", [])
        matching = [f for f in all_foods if f.get("name") == food_name]
        assert len(matching) == 1, (
            f"Expected 1 '{food_name}' food, got {len(matching)}"
        )


class TestRule6FoodUnitMerge:
    """Rule 6: Merging food/unit A→B updates all references, then deletes A."""

    def test_b6a_food_merge_updates_recipe_references(self):
        """Merge food A → B: recipe ingredients pointing to A now point to B."""
        food_a = create_food(f"foodA-{UNIQUE}-b6a")
        food_b = create_food(f"foodB-{UNIQUE}-b6a")
        unit = create_unit(f"unit-{UNIQUE}-b6a")

        slug = create_recipe(f"Recipe-{UNIQUE}-b6a")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [{
                "food": {"id": food_a["id"], "name": food_a["name"]},
                "unit": {"id": unit["id"], "name": unit["name"]},
                "quantity": 1, "note": "before merge",
            }],
        })

        # Verify recipe uses food A
        recipe = get_recipe(slug)
        ing_food_ids = [
            i.get("food", {}).get("id")
            for i in recipe.get("recipeIngredient", [])
            if i.get("food")
        ]
        assert food_a["id"] in ing_food_ids, "Recipe should use food A before merge"

        # Merge A → B
        resp = api_put("/api/foods/merge", {"fromFood": food_a["id"], "toFood": food_b["id"]})
        assert resp.status_code == 200

        # Recipe should now reference food B
        recipe = get_recipe(slug)
        ing_food_ids = [
            i.get("food", {}).get("id")
            for i in recipe.get("recipeIngredient", [])
            if i.get("food")
        ]
        assert food_b["id"] in ing_food_ids, (
            f"After merge, recipe should reference food B ({food_b['id']}), "
            f"got: {ing_food_ids}"
        )
        assert food_a["id"] not in ing_food_ids, (
            f"After merge, food A ({food_a['id']}) should be gone from recipe"
        )

        # Food A should be deleted
        resp = api_get(f"/api/foods/{food_a['id']}")
        assert resp.status_code == 404, (
            f"Food A should be deleted after merge, got {resp.status_code}"
        )

    def test_b6b_unit_merge_updates_recipe_references(self):
        """Merge unit A → B: recipe ingredients using unit A now use unit B."""
        unit_a = create_unit(f"unitA-{UNIQUE}-b6b")
        unit_b = create_unit(f"unitB-{UNIQUE}-b6b")
        food = create_food(f"food-{UNIQUE}-b6b")

        slug = create_recipe(f"Recipe-{UNIQUE}-b6b")
        recipe = get_recipe(slug)
        update_recipe(slug, {
            **recipe,
            "recipeIngredient": [{
                "food": {"id": food["id"], "name": food["name"]},
                "unit": {"id": unit_a["id"], "name": unit_a["name"]},
                "quantity": 1, "note": "before merge",
            }],
        })

        # Merge A → B
        resp = api_put("/api/units/merge", {"fromUnit": unit_a["id"], "toUnit": unit_b["id"]})
        assert resp.status_code == 200

        # Recipe should now use unit B
        recipe = get_recipe(slug)
        ing_unit_ids = [
            i.get("unit", {}).get("id")
            for i in recipe.get("recipeIngredient", [])
            if i.get("unit")
        ]
        assert unit_b["id"] in ing_unit_ids, (
            f"After merge, recipe should use unit B, got: {ing_unit_ids}"
        )
        assert unit_a["id"] not in ing_unit_ids

        # Unit A should be deleted
        resp = api_get(f"/api/units/{unit_a['id']}")
        assert resp.status_code == 404


class TestRule7SlugUniqueness:
    """Rule 7: Recipe slugs must be unique within a group; handle collisions."""

    def test_b7a_duplicate_name_gets_different_slug(self):
        """Two recipes with identical name → both succeed with different slugs."""
        name = f"Same Name {UNIQUE} B7A"
        slug1 = create_recipe(name)
        slug2 = create_recipe(name)

        assert slug1 != slug2, (
            f"Two recipes named '{name}' got the same slug: {slug1}"
        )

        # Both should be independently accessible
        r1 = get_recipe(slug1)
        r2 = get_recipe(slug2)
        assert r1["id"] != r2["id"], "Recipes with same name should have different IDs"

    def test_b7b_slug_is_url_safe(self):
        """Slug should be lowercase, URL-safe, and derived from name."""
        name = f"My Fancy Recipe {UNIQUE}"
        slug = create_recipe(name)
        assert " " not in slug, f"Slug should not contain spaces: '{slug}'"
        assert slug == slug.lower() or slug.replace("-", "").isalnum(), (
            f"Slug should be URL-safe: '{slug}'"
        )


class TestRule8MealPlanRandom:
    """Rule 8: Random meal plan respects rules (day + entryType → filter)."""

    def test_b8a_random_respects_tag_rule(self):
        """Rule for 'tuesday dinner' requires tag X → random returns recipe with tag X."""
        tag_name = f"QuickMeal-{UNIQUE}-b8a"
        tag = create_tag(tag_name)
        tag_id = tag["id"]

        # Create recipe WITH the tag
        slug_match = create_recipe(f"Matching-{UNIQUE}-b8a")
        recipe_match = get_recipe(slug_match)
        update_recipe(slug_match, {
            **recipe_match, "tags": [{"id": tag_id, "name": tag_name}]
        })
        recipe_match = get_recipe(slug_match)

        # Create recipe WITHOUT the tag
        create_recipe(f"NoTag-{UNIQUE}-b8a")

        # Create rule: tuesday + dinner → require the tag
        rule_data = {
            "day": "tuesday",
            "entryType": "dinner",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
            "queryFilterString": f'tags.id CONTAINS_ANY ["{tag_id}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "tags.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [tag_id],
                }]
            },
        }
        resp = api_post("/api/households/mealplans/rules", rule_data)
        assert resp.status_code == 201

        # Request random for next Tuesday dinner
        tuesday = next_weekday("tuesday")
        resp = api_post("/api/households/mealplans/random",
                        {"date": tuesday, "entryType": "dinner"})
        assert resp.status_code == 200
        plan = resp.json()

        # Should pick the matching recipe
        plan_recipe_id = plan.get("recipeId")
        assert plan_recipe_id == recipe_match["id"], (
            f"Random should pick the tagged recipe ({recipe_match['id']}), "
            f"got {plan_recipe_id}"
        )

    def test_b8b_random_returns_valid_recipe(self):
        """Random meal plan should return a plan entry with a recipe."""
        slug = create_recipe(f"AnyRecipe-{UNIQUE}-b8b")
        recipe = get_recipe(slug)

        date = _utc_today().isoformat()
        resp = api_post("/api/households/mealplans/random",
                        {"date": date, "entryType": "dinner"})
        assert resp.status_code == 200
        plan = resp.json()
        assert plan.get("recipeId") is not None or plan.get("recipe") is not None, (
            "Random meal plan should include a recipe reference"
        )


class TestRule9CookbookDynamicFiltering:
    """Rule 9: Cookbook stores filter criteria; listing = querying with those filters."""

    def test_b9a_cookbook_filters_by_category(self):
        """Cookbook filters for category X → only X-recipes appear."""
        cat_name = f"CookbookCat-{UNIQUE}-b9a"
        cat = create_category(cat_name)
        cat_id = cat["id"]

        # Recipe A — HAS the category
        slug_a = create_recipe(f"InCookbook-{UNIQUE}-b9a")
        recipe_a = get_recipe(slug_a)
        update_recipe(slug_a, {
            **recipe_a, "recipeCategory": [{"id": cat_id, "name": cat_name}]
        })

        # Recipe B — does NOT have the category
        slug_b = create_recipe(f"NotInCookbook-{UNIQUE}-b9a")

        # Create cookbook with category filter
        cookbook_data = {
            "name": f"Cookbook-{UNIQUE}-b9a",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat_id}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat_id],
                }]
            },
        }
        resp = api_post("/api/households/cookbooks", cookbook_data)
        assert resp.status_code == 201
        cookbook = resp.json()
        cookbook_id = cookbook["id"]

        # Query recipes through cookbook
        resp = api_get("/api/recipes", params={"cookbook": cookbook_id, "perPage": 100})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        slugs = [r.get("slug") for r in items]

        assert slug_a in slugs, (
            f"Recipe A (with category) should appear in cookbook, slugs: {slugs}"
        )
        assert slug_b not in slugs, (
            f"Recipe B (without category) should NOT appear in cookbook"
        )

    def test_b9b_update_cookbook_filter_changes_results(self):
        """Changing cookbook's filter criteria changes which recipes match."""
        cat1_name = f"CatAlpha-{UNIQUE}-b9b"
        cat2_name = f"CatBeta-{UNIQUE}-b9b"
        cat1 = create_category(cat1_name)
        cat2 = create_category(cat2_name)

        slug_a = create_recipe(f"Alpha-{UNIQUE}-b9b")
        recipe_a = get_recipe(slug_a)
        update_recipe(slug_a, {
            **recipe_a, "recipeCategory": [{"id": cat1["id"], "name": cat1_name}]
        })

        slug_b = create_recipe(f"Beta-{UNIQUE}-b9b")
        recipe_b = get_recipe(slug_b)
        update_recipe(slug_b, {
            **recipe_b, "recipeCategory": [{"id": cat2["id"], "name": cat2_name}]
        })

        # Create cookbook filtering by cat1
        cookbook_data = {
            "name": f"Cookbook-{UNIQUE}-b9b",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat1["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat1["id"]],
                }]
            },
        }
        resp = api_post("/api/households/cookbooks", cookbook_data)
        assert resp.status_code == 201
        cookbook = resp.json()
        cookbook_id = cookbook["id"]

        # Initially should have recipe A
        resp = api_get("/api/recipes", params={"cookbook": cookbook_id, "perPage": 100})
        slugs = [r.get("slug") for r in resp.json().get("items", [])]
        assert slug_a in slugs

        # Update cookbook to filter by cat2 instead
        resp = api_put(f"/api/households/cookbooks/{cookbook_id}", {
            **cookbook,
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat2["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat2["id"]],
                }]
            },
        })
        assert resp.status_code == 200

        # Now should have recipe B, not A
        resp = api_get("/api/recipes", params={"cookbook": cookbook_id, "perPage": 100})
        slugs = [r.get("slug") for r in resp.json().get("items", [])]
        assert slug_b in slugs, f"After filter update, recipe B should appear"
        assert slug_a not in slugs, f"After filter update, recipe A should NOT appear"


class TestRule10CheckedItems:
    """Rule 10: Checked items don't merge and shouldn't have recipe references."""

    def test_b10a_two_unchecked_same_food_merge(self):
        """Two unchecked items with same food → merge."""
        food = create_food(f"food-{UNIQUE}-b10a")
        sl = create_shopping_list(f"List-{UNIQUE}-b10a")

        add_shopping_item(sl["id"], food_id=food["id"], quantity=2, checked=False)
        add_shopping_item(sl["id"], food_id=food["id"], quantity=3, checked=False)

        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 1, f"Two unchecked same-food items should merge, got {len(items)}"
        assert items[0]["quantity"] == 5

    def test_b10b_checked_does_not_merge_with_unchecked(self):
        """Checked item + new unchecked item same food → should NOT merge."""
        food = create_food(f"food-{UNIQUE}-b10b")
        sl = create_shopping_list(f"List-{UNIQUE}-b10b")

        # First item: checked
        add_shopping_item(sl["id"], food_id=food["id"], quantity=2, checked=True)
        # Second item: unchecked
        add_shopping_item(sl["id"], food_id=food["id"], quantity=3, checked=False)

        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 2, (
            f"Checked + unchecked should NOT merge, expected 2, got {len(items)}"
        )
        checked = [i for i in items if i.get("checked")]
        unchecked = [i for i in items if not i.get("checked")]
        assert len(checked) == 1 and checked[0]["quantity"] == 2
        assert len(unchecked) == 1 and unchecked[0]["quantity"] == 3


# ════════════════════════════════════════════════════════════════════
# PART 3: Pagination, Search, Sort (~8 tests)
# ════════════════════════════════════════════════════════════════════


class TestPaginationAndSearch:

    def test_per_page_limit(self):
        for i in range(6):
            create_recipe(f"PageLimit-{UNIQUE}-{i}")
        resp = api_get("/api/recipes", params={"page": 1, "perPage": 5})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        assert len(items) <= 5, f"perPage=5 but got {len(items)} items"

    def test_different_pages_no_overlap(self):
        for i in range(12):
            create_recipe(f"PageSplit-{UNIQUE}-{i:02d}")
        resp1 = api_get("/api/recipes", params={"page": 1, "perPage": 10})
        resp2 = api_get("/api/recipes", params={"page": 2, "perPage": 10})
        assert resp1.status_code == 200 and resp2.status_code == 200

        ids1 = {r["id"] for r in resp1.json().get("items", [])}
        ids2 = {r["id"] for r in resp2.json().get("items", [])}
        overlap = ids1 & ids2
        assert not overlap, f"Pages 1 and 2 share {len(overlap)} recipes: {overlap}"

    def test_total_and_total_pages_consistent(self):
        for i in range(3):
            create_recipe(f"PageTotal-{UNIQUE}-{i}")
        resp = api_get("/api/recipes", params={"page": 1, "perPage": 10})
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", 0)
        total_pages = data.get("total_pages", 0)
        per_page = data.get("per_page", 10)
        if total > 0 and per_page > 0:
            expected_pages = (total + per_page - 1) // per_page
            assert total_pages == expected_pages, (
                f"total_pages={total_pages} but expected {expected_pages} "
                f"(total={total}, per_page={per_page})"
            )

    def test_search_finds_recipe(self):
        name = f"Searchable Pancakes {UNIQUE}"
        create_recipe(name)
        resp = api_get("/api/recipes", params={"search": name})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        names = [r.get("name", "") for r in items]
        assert any(UNIQUE in n for n in names), (
            f"Search for '{name}' found no matches in: {names[:5]}"
        )

    def test_search_no_results_for_garbage(self):
        resp = api_get("/api/recipes", params={"search": "zzznonexistent99999xyz"})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        assert len(items) == 0, f"Garbage search should return 0 results, got {len(items)}"

    def test_sort_by_name_asc(self):
        for name in ("Zulu", "Alpha", "Mike"):
            create_recipe(f"{name}-Sort-{UNIQUE}")
        resp = api_get("/api/recipes", params={
            "orderBy": "name", "orderDirection": "asc", "perPage": 20
        })
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        if len(items) >= 2:
            names = [r["name"].lower() for r in items]
            assert names == sorted(names), f"Not sorted by name asc: {names[:5]}"

    def test_shopping_list_pagination(self):
        # Create a few lists
        for i in range(3):
            create_shopping_list(f"PagList-{UNIQUE}-{i}")
        resp = api_get("/api/households/shopping/lists", params={"page": 1, "perPage": 2})
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        assert len(items) <= 2

    def test_food_search(self):
        fname = f"UniqueSpice-{UNIQUE}"
        create_food(fname)
        resp = api_get("/api/foods", params={"search": fname, "perPage": 10})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        assert any(f.get("name") == fname for f in items), (
            f"Food search for '{fname}' returned no match"
        )


# ════════════════════════════════════════════════════════════════════
# PART 4: 404 Handling (~4 tests)
# ════════════════════════════════════════════════════════════════════


class TestNotFound:

    def test_recipe_not_found(self):
        resp = api_get("/api/recipes/absolutely-nonexistent-slug-zzz")
        assert resp.status_code == 404

    def test_shopping_list_not_found(self):
        resp = api_get("/api/households/shopping/lists/00000000-0000-0000-0000-ffffffffffff")
        assert resp.status_code == 404

    def test_food_not_found(self):
        resp = api_get("/api/foods/00000000-0000-0000-0000-ffffffffffff")
        assert resp.status_code == 404

    def test_mealplan_not_found(self):
        resp = api_get("/api/households/mealplans/99999999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Missing Endpoint Coverage (~15 tests)
# ════════════════════════════════════════════════════════════════════


def create_recipe_full(name, **extra_fields):
    """Helper: POST /api/recipes returns a slug string per OpenAPI spec.
    This helper creates the recipe, then GETs the detail to return the full dict."""
    resp = api_post("/api/recipes", {"name": name})
    assert resp.status_code == 201, f"Create recipe failed: {resp.status_code} {resp.text}"
    result = resp.json()
    # POST /api/recipes returns a string (slug) per OpenAPI spec
    if isinstance(result, str):
        slug = result
    elif isinstance(result, dict):
        slug = result.get("slug", result.get("id", ""))
    else:
        slug = str(result)
    detail = api_get(f"/api/recipes/{slug}")
    assert detail.status_code == 200, f"GET recipe detail failed for slug={slug}: {detail.status_code}"
    recipe = detail.json()
    if extra_fields:
        update_recipe(slug, {**recipe, **extra_fields})
        recipe = get_recipe(slug)
    return recipe


class TestRecipeDuplicate:
    """POST /api/recipes/{slug}/duplicate"""

    def test_duplicate_creates_new_recipe(self):
        recipe = create_recipe_full(f"Dup Original {UNIQUE}")
        slug = recipe["slug"]
        # Duplicate it
        dup_resp = api_post(f"/api/recipes/{slug}/duplicate", {"name": f"Dup Copy {UNIQUE}"})
        assert dup_resp.status_code == 201
        dup = dup_resp.json()
        dup_slug = dup["slug"] if isinstance(dup, dict) else dup
        assert dup_slug != slug, "Duplicate should have a different slug"

    def test_duplicate_copies_ingredients(self):
        recipe = create_recipe_full(
            f"Dup Ingredients {UNIQUE}",
            recipeIngredient=[
                {"note": "eggs", "quantity": 3, "originalText": "3 eggs"},
                {"note": "milk", "quantity": 1, "originalText": "1 cup milk"},
            ],
        )
        slug = recipe["slug"]
        dup_resp = api_post(f"/api/recipes/{slug}/duplicate", {})
        assert dup_resp.status_code == 201
        dup = dup_resp.json()
        dup_slug = dup["slug"] if isinstance(dup, dict) else dup
        # Duplicate should have same number of ingredients
        orig_detail = api_get(f"/api/recipes/{slug}").json()
        dup_detail = api_get(f"/api/recipes/{dup_slug}").json()
        orig_count = len(orig_detail.get("recipeIngredient", []))
        dup_count = len(dup_detail.get("recipeIngredient", []))
        assert dup_count == orig_count, (
            f"Duplicate has {dup_count} ingredients, original has {orig_count}"
        )


class TestRecipeLastMade:
    """PATCH /api/recipes/{slug}/last-made"""

    def test_last_made_updates(self):
        recipe = create_recipe_full(f"LastMade {UNIQUE}")
        slug = recipe["slug"]
        ts = "2026-04-01T12:00:00Z"
        patch_resp = requests.patch(
            f"{BASE_URL}/api/recipes/{slug}/last-made",
            json={"timestamp": ts},
            headers=HEADERS,
            timeout=30,
        )
        assert patch_resp.status_code == 200
        detail = api_get(f"/api/recipes/{slug}").json()
        assert detail.get("lastMade") is not None, "lastMade should be set"


class TestRecipeComments:
    """GET /api/recipes/{slug}/comments"""

    def test_get_recipe_comments(self):
        recipe = create_recipe_full(f"CommentList {UNIQUE}")
        slug = recipe["slug"]
        recipe_id = recipe["id"]
        # Add a comment
        api_post("/api/comments", {"recipeId": recipe_id, "text": f"Comment {UNIQUE}"})
        # Get comments via recipe endpoint
        comments_resp = api_get(f"/api/recipes/{slug}/comments")
        assert comments_resp.status_code == 200
        comments = comments_resp.json()
        assert isinstance(comments, list), "Should return array of comments"
        assert len(comments) >= 1, "Should have at least 1 comment"


class TestRecipeSuggestions:
    """GET /api/recipes/suggestions"""

    def test_suggestions_returns_items(self):
        resp = api_get("/api/recipes/suggestions", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data, "Suggestions response should have 'items'"
        assert isinstance(data["items"], list)


class TestMealplanToday:
    """GET /api/households/mealplans/today"""

    def test_today_returns_data(self):
        resp = api_get("/api/households/mealplans/today")
        assert resp.status_code == 200


class TestShoppingItemsBulkCreate:
    """POST /api/households/shopping/items/create-bulk"""

    def test_bulk_create_items(self):
        # Create a shopping list first
        sl_resp = api_post("/api/households/shopping/lists", {"name": f"BulkSL {UNIQUE}"})
        assert sl_resp.status_code == 201
        sl_id = sl_resp.json()["id"]
        # Bulk create 2 items
        items = [
            {"shoppingListId": sl_id, "note": f"Bulk item A {UNIQUE}", "quantity": 1},
            {"shoppingListId": sl_id, "note": f"Bulk item B {UNIQUE}", "quantity": 2},
        ]
        resp = api_post("/api/households/shopping/items/create-bulk", items)
        assert resp.status_code == 201
        data = resp.json()
        created = data.get("createdItems", [])
        assert len(created) >= 2, f"Expected 2 created items, got {len(created)}"


class TestShoppingListLabelSettings:
    """PUT /api/households/shopping/lists/{item_id}/label-settings"""

    def test_label_settings_endpoint_exists(self):
        sl_resp = api_post("/api/households/shopping/lists", {"name": f"LabelSL {UNIQUE}"})
        assert sl_resp.status_code == 201
        sl_id = sl_resp.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/api/households/shopping/lists/{sl_id}/label-settings",
            json=[],
            headers=HEADERS,
            timeout=30,
        )
        # Endpoint should exist (200), even if no labels to update
        assert resp.status_code == 200


class TestShoppingListBulkRecipe:
    """POST /api/households/shopping/lists/{item_id}/recipe (bulk add)"""

    def test_bulk_add_recipes_to_list(self):
        # Create a shopping list
        sl_resp = api_post("/api/households/shopping/lists", {"name": f"BulkRecipeSL {UNIQUE}"})
        assert sl_resp.status_code == 201
        sl_id = sl_resp.json()["id"]
        # Create a recipe
        recipe = create_recipe_full(f"BulkAddRecipe {UNIQUE}")
        recipe_id = recipe["id"]
        # Bulk add
        resp = api_post(
            f"/api/households/shopping/lists/{sl_id}/recipe",
            [{"recipeId": recipe_id, "recipeIncrementQuantity": 1}],
        )
        assert resp.status_code == 200


class TestOrganizersEmpty:
    """GET /api/organizers/categories/empty and /api/organizers/tags/empty"""

    def test_categories_empty_returns_array(self):
        resp = api_get("/api/organizers/categories/empty")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list), "Empty categories should return array"

    def test_tags_empty_returns_data(self):
        resp = api_get("/api/organizers/tags/empty")
        assert resp.status_code == 200


class TestUserFavorites:
    """POST/DELETE /api/users/{id}/favorites/{slug}, GET /api/users/{id}/favorites"""

    def test_add_and_remove_favorite(self):
        # Create a recipe to favorite
        recipe = create_recipe_full(f"Fav Recipe {UNIQUE}")
        slug = recipe["slug"]
        user_id = HEADERS["X-User-Id"]
        # Add favorite
        fav_resp = api_post(f"/api/users/{user_id}/favorites/{slug}", {})
        assert fav_resp.status_code == 200
        # Get favorites
        favs = api_get(f"/api/users/{user_id}/favorites")
        assert favs.status_code == 200
        data = favs.json()
        assert "ratings" in data, "Favorites response should have 'ratings' key"
        # Remove favorite
        del_resp = requests.delete(
            f"{BASE_URL}/api/users/{user_id}/favorites/{slug}",
            headers=HEADERS,
            timeout=30,
        )
        assert del_resp.status_code == 200


class TestUserSelfEndpoints:
    """GET /api/users/self/favorites, /api/users/self/ratings, /api/users/self/ratings/{recipe_id}"""

    def test_self_favorites(self):
        resp = api_get("/api/users/self/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert "ratings" in data, "Self favorites should have 'ratings' key"

    def test_self_ratings(self):
        resp = api_get("/api/users/self/ratings")
        assert resp.status_code == 200
        data = resp.json()
        assert "ratings" in data, "Self ratings should have 'ratings' key"

    def test_self_rating_for_recipe(self):
        # Create recipe and rate it first
        recipe = create_recipe_full(f"SelfRate {UNIQUE}")
        recipe_id = recipe["id"]
        slug = recipe["slug"]
        slug = recipe["slug"]
        user_id = HEADERS["X-User-Id"]
        # Rate it
        api_post(f"/api/users/{user_id}/ratings/{slug}", {"rating": 4.0})
        # Get self rating for this recipe
        rating_resp = api_get(f"/api/users/self/ratings/{recipe_id}")
        assert rating_resp.status_code == 200
        data = rating_resp.json()
        assert "recipeId" in data, "Rating response should have 'recipeId'"


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: Authentication & Isolation Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestAuthMissingHeaders:
    """Requests with missing auth headers should return 401."""

    def test_missing_all_headers(self):
        resp = requests.get(f"{BASE_URL}/api/recipes", timeout=30)
        assert resp.status_code == 401, f"Expected 401 without headers, got {resp.status_code}"

    def test_missing_user_id(self):
        headers = {"X-Group-Id": GROUP_ID, "X-Household-Id": HOUSEHOLD_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/api/recipes", headers=headers, timeout=30)
        assert resp.status_code == 401, f"Expected 401 without X-User-Id, got {resp.status_code}"

    def test_missing_group_id(self):
        headers = {"X-User-Id": USER_ID, "X-Household-Id": HOUSEHOLD_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/api/recipes", headers=headers, timeout=30)
        assert resp.status_code == 401, f"Expected 401 without X-Group-Id, got {resp.status_code}"

    def test_missing_household_id(self):
        headers = {"X-User-Id": USER_ID, "X-Group-Id": GROUP_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/api/recipes", headers=headers, timeout=30)
        assert resp.status_code == 401, f"Expected 401 without X-Household-Id, got {resp.status_code}"


class TestGroupIsolation:
    """Data created by group A must not be visible to group B."""

    def test_recipe_isolation(self):
        """Recipe created by group A is invisible to group B."""
        name = f"IsoRecipe-{UNIQUE}"
        resp = api_post("/api/recipes", {"name": name})
        assert resp.status_code == 201, f"Create failed: {resp.status_code}"

        # Group B should not see it
        resp_b = api_get("/api/recipes", params={"search": name}, headers=HEADERS_GROUP2)
        assert resp_b.status_code == 200
        items = resp_b.json().get("items", resp_b.json() if isinstance(resp_b.json(), list) else [])
        names = [r.get("name", "") for r in items]
        assert name not in names, f"Group B should NOT see group A's recipe '{name}'"

    def test_food_isolation(self):
        """Food created by group A is invisible to group B."""
        name = f"IsoFood-{UNIQUE}"
        resp = api_post("/api/foods", {"name": name})
        assert resp.status_code == 201, f"Create failed: {resp.status_code}"

        # Group B should not see it
        resp_b = api_get("/api/foods", headers=HEADERS_GROUP2)
        assert resp_b.status_code == 200
        data = resp_b.json()
        items = data.get("items", data if isinstance(data, list) else [])
        names = [f.get("name", "") for f in items]
        assert name not in names, f"Group B should NOT see group A's food '{name}'"

    def test_tag_isolation(self):
        """Tag created by group A is invisible to group B."""
        name = f"IsoTag-{UNIQUE}"
        resp = api_post("/api/organizers/tags", {"name": name})
        assert resp.status_code == 201, f"Create failed: {resp.status_code}"

        # Group B should not see it
        resp_b = api_get("/api/organizers/tags", headers=HEADERS_GROUP2)
        assert resp_b.status_code == 200
        data = resp_b.json()
        items = data.get("items", data if isinstance(data, list) else [])
        names = [t.get("name", "") for t in items]
        assert name not in names, f"Group B should NOT see group A's tag '{name}'"


class TestHouseholdIsolation:
    """Data scoped to household A must not be visible to household B."""

    def test_shopping_list_isolation(self):
        """Shopping list created by household A is invisible to household B."""
        name = f"IsoList-{UNIQUE}"
        resp = api_post("/api/households/shopping/lists", {"name": name})
        assert resp.status_code == 201, f"Create failed: {resp.status_code}"

        # Household B (in group 2) should not see it
        resp_b = api_get("/api/households/shopping/lists", headers=HEADERS_GROUP2)
        assert resp_b.status_code == 200
        data = resp_b.json()
        items = data.get("items", data if isinstance(data, list) else [])
        names = [sl.get("name", "") for sl in items]
        assert name not in names, f"Household B should NOT see household A's shopping list '{name}'"

    def test_mealplan_isolation(self):
        """Meal plan created by household A is invisible to household B."""
        today = _utc_today().isoformat()
        resp = api_post("/api/households/mealplans", {
            "date": today,
            "entryType": "dinner",
            "title": f"IsoMeal-{UNIQUE}",
        })
        assert resp.status_code == 201, f"Create failed: {resp.status_code}"

        # Household B should not see it
        resp_b = api_get("/api/households/mealplans", headers=HEADERS_GROUP2)
        assert resp_b.status_code == 200
        data = resp_b.json()
        items = data.get("items", data if isinstance(data, list) else [])
        titles = [mp.get("title", "") for mp in items]
        assert f"IsoMeal-{UNIQUE}" not in titles, "Household B should NOT see household A's meal plan"
