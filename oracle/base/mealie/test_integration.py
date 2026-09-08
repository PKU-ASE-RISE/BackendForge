"""
BackendForge — L2 Integration Tests for Mealie Task

Adversarial tests targeting common LLM coding agent bugs:
- camelCase vs snake_case field names
- Nested data roundtrip
- Pagination with correct envelope
- Shopping list merge logic
- Status codes
- Sorting/filtering actually applied

"""

import os
import uuid
import datetime

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
GROUP_ID = "00000000-0000-0000-0000-100000000001"
HOUSEHOLD_ID = "00000000-0000-0000-0000-100000000002"
USER_ID = "00000000-0000-0000-0000-100000000003"
USER_ID_2 = "00000000-0000-0000-0000-100000000004"

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

U = uuid.uuid4().hex[:6]


def _reset_test_context():
    """Give every test fresh group, household, and user identities."""
    global GROUP_ID, HOUSEHOLD_ID, USER_ID, USER_ID_2
    global HEADERS, HEADERS_USER2, U

    GROUP_ID = str(uuid.uuid4())
    HOUSEHOLD_ID = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    USER_ID_2 = str(uuid.uuid4())
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
    U = uuid.uuid4().hex[:6]


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
    """Create recipe, return slug."""
    r = post("/api/recipes", {"name": name})
    assert r.status_code == 201, f"Create recipe failed: {r.status_code} {r.text}"
    result = r.json()
    return result if isinstance(result, str) else result.get("slug", result.get("id", str(result)))


def get_recipe(slug):
    r = get(f"/api/recipes/{slug}")
    assert r.status_code == 200, f"Get recipe failed: {r.status_code}"
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
# L2 Tests — Integration (20-30 tests)
# ════════════════════════════════════════════════════════════════════


class TestRecipeCamelCaseFields:
    """Pattern 1: Verify response uses camelCase field names, not snake_case."""

    def test_recipe_detail_has_camel_case_keys(self):
        """GET recipe must return camelCase keys per OpenAPI spec."""
        slug = make_recipe(f"CamelCase-{U}-1")
        recipe = get_recipe(slug)

        # These MUST be camelCase — not snake_case
        assert "recipeIngredient" in recipe, f"Missing 'recipeIngredient', keys: {list(recipe.keys())}"
        assert "recipeInstructions" in recipe, f"Missing 'recipeInstructions', keys: {list(recipe.keys())}"
        assert "lastMade" in recipe or recipe.get("lastMade") is None, \
            f"'lastMade' key missing (maybe 'last_made'?), keys: {list(recipe.keys())}"
        assert "dateAdded" in recipe, f"Missing 'dateAdded', keys: {list(recipe.keys())}"
        assert "createdAt" in recipe, f"Missing 'createdAt', keys: {list(recipe.keys())}"

        # Negative checks: snake_case variants must NOT be present
        assert "recipe_ingredient" not in recipe, "Should use 'recipeIngredient' not 'recipe_ingredient'"
        assert "recipe_instructions" not in recipe, "Should use 'recipeInstructions' not 'recipe_instructions'"
        assert "last_made" not in recipe, "Should use 'lastMade' not 'last_made'"
        assert "date_added" not in recipe, "Should use 'dateAdded' not 'date_added'"
        assert "created_at" not in recipe, "Should use 'createdAt' not 'created_at'"

    def test_recipe_summary_in_list_has_camel_case(self):
        """GET /api/recipes list items must use camelCase."""
        make_recipe(f"ListCamel-{U}")
        r = get("/api/recipes", params={"perPage": 5})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) >= 1
        item = items[0]

        # Must have camelCase keys
        assert "recipeCategory" in item or "tags" in item, f"Keys: {list(item.keys())}"
        assert "recipe_category" not in item, "Should use 'recipeCategory' not 'recipe_category'"
        assert "group_id" not in item, "Should use 'groupId' not 'group_id'"


class TestRecipeNestedDataRoundtrip:
    """Pattern 2: Create recipe with nested data → GET → verify data preserved."""

    def test_recipe_ingredients_roundtrip(self):
        """Create with recipeIngredient → GET → verify all fields present."""
        food = make_food(f"butter-{U}-rt")
        unit = make_unit(f"tbsp-{U}-rt")

        slug = make_recipe(f"Roundtrip-{U}")
        recipe = get_recipe(slug)

        # Update with ingredients
        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 3.5,
                    "note": "melted",
                },
                {
                    "food": {"id": food["id"], "name": food["name"]},
                    "unit": {"id": unit["id"], "name": unit["name"]},
                    "quantity": 1,
                    "note": "cold",
                },
            ],
            "recipeInstructions": [
                {"text": "Melt butter in pan."},
                {"text": "Add cold butter at end."},
                {"text": "Serve immediately."},
            ],
        })

        # Retrieve and verify
        updated = get_recipe(slug)
        ingredients = updated.get("recipeIngredient", [])
        instructions = updated.get("recipeInstructions", [])

        assert len(ingredients) == 2, f"Expected 2 ingredients, got {len(ingredients)}"
        assert len(instructions) == 3, f"Expected 3 instructions, got {len(instructions)}"

        # Verify ingredient fields
        assert ingredients[0]["quantity"] == 3.5
        assert ingredients[0]["note"] == "melted"
        # Verify food reference is preserved
        assert ingredients[0].get("food") is not None, "Ingredient food should not be None"
        assert ingredients[0]["food"]["id"] == food["id"]

    def test_recipe_with_tags_and_categories_roundtrip(self):
        """Create recipe with tags + categories → verify attached after GET."""
        slug = make_recipe(f"TagCat-{U}")
        recipe = get_recipe(slug)

        tag_name = f"Healthy-{U}-rt"
        cat_name = f"Salads-{U}-rt"

        put(f"/api/recipes/{slug}", {
            **recipe,
            "tags": [{"name": tag_name}],
            "recipeCategory": [{"name": cat_name}],
        })

        updated = get_recipe(slug)
        tags = updated.get("tags", [])
        categories = updated.get("recipeCategory", [])

        assert len(tags) >= 1, f"Expected at least 1 tag, got {len(tags)}"
        assert any(t["name"] == tag_name for t in tags), f"Tag '{tag_name}' not found in {tags}"
        assert len(categories) >= 1, f"Expected at least 1 category, got {len(categories)}"
        assert any(c["name"] == cat_name for c in categories), f"Category '{cat_name}' not found"


class TestRecipeDuplicateStatusCode:
    """Pattern 4: Duplicate returns 201, not 200."""

    def test_duplicate_returns_201(self):
        """POST /api/recipes/{slug}/duplicate must return 201."""
        slug = make_recipe(f"DupStatus-{U}")
        r = post(f"/api/recipes/{slug}/duplicate", {"name": f"DupStatus Copy {U}"})
        assert r.status_code == 201, f"Duplicate should return 201, got {r.status_code}"

    def test_duplicate_preserves_nested_data(self):
        """Duplicate recipe preserves ingredients and instructions."""
        food = make_food(f"egg-{U}-dup")
        slug = make_recipe(f"DupNested-{U}")
        recipe = get_recipe(slug)

        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [
                {"food": {"id": food["id"], "name": food["name"]}, "quantity": 3, "note": "beaten"},
            ],
            "recipeInstructions": [
                {"text": "Beat eggs."},
                {"text": "Cook on low heat."},
            ],
        })

        r = post(f"/api/recipes/{slug}/duplicate", {"name": f"DupNested Copy {U}"})
        assert r.status_code == 201
        dup = r.json()
        dup_slug = dup["slug"] if isinstance(dup, dict) else dup

        dup_detail = get_recipe(dup_slug)
        assert len(dup_detail.get("recipeIngredient", [])) == 1, "Duplicate should have ingredients"
        assert len(dup_detail.get("recipeInstructions", [])) == 2, "Duplicate should have instructions"


class TestLastMadeCamelCase:
    """Pattern 1: lastMade field uses camelCase."""

    def test_last_made_field_name(self):
        """PATCH last-made → GET → verify 'lastMade' key (not 'last_made')."""
        slug = make_recipe(f"LastMade-{U}")
        ts = "2026-03-15T10:00:00Z"

        r = patch(f"/api/recipes/{slug}/last-made", {"timestamp": ts})
        assert r.status_code == 200

        recipe = get_recipe(slug)
        # Must use camelCase key
        assert "lastMade" in recipe, f"Missing 'lastMade' key. Keys: {list(recipe.keys())}"
        assert recipe["lastMade"] is not None, "lastMade should not be None after PATCH"
        assert "last_made" not in recipe, "Should be 'lastMade' not 'last_made'"


class TestShoppingItemCamelCase:
    """Pattern 1: Shopping item creation with camelCase request → camelCase response."""

    def test_shopping_item_camel_case_request_and_response(self):
        """POST item with camelCase body → response uses camelCase field names."""
        sl = make_shopping_list(f"CamelSL-{U}")
        food = make_food(f"rice-{U}-si")

        r = post("/api/households/shopping/items", {
            "shoppingListId": sl["id"],
            "foodId": food["id"],
            "quantity": 2,
            "note": "basmati",
            "checked": False,
        })
        assert r.status_code == 201, f"Create shopping item failed: {r.status_code} {r.text}"

        data = r.json()
        # Response should be collection format
        assert "createdItems" in data or "updatedItems" in data, \
            f"Response should have createdItems/updatedItems. Keys: {list(data.keys())}"

        # Get the item and verify field names
        created = data.get("createdItems", []) + data.get("updatedItems", [])
        assert len(created) >= 1
        item = created[0]

        assert "shoppingListId" in item, f"Missing 'shoppingListId'. Keys: {list(item.keys())}"
        assert "foodId" in item, f"Missing 'foodId'. Keys: {list(item.keys())}"
        assert "shopping_list_id" not in item, "Should be 'shoppingListId' not 'shopping_list_id'"
        assert "food_id" not in item, "Should be 'foodId' not 'food_id'"
        assert item["shoppingListId"] == sl["id"]
        assert item["foodId"] == food["id"]
        assert item["quantity"] == 2


class TestShoppingListMergeLogic:
    """Pattern 5: Shopping list merge — same food+unit → merge quantities."""

    def test_merge_same_food_same_unit_unchecked(self):
        """Two unchecked items same food+unit → merged into one with summed qty."""
        food = make_food(f"flour-{U}-merge")
        unit = make_unit(f"cups-{U}-merge")
        sl = make_shopping_list(f"MergeList-{U}")

        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "unitId": unit["id"], "quantity": 2, "checked": False,
        })
        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "unitId": unit["id"], "quantity": 3, "checked": False,
        })

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        matching = [i for i in items if i.get("foodId") == food["id"] and not i.get("checked")]

        assert len(matching) == 1, f"Should merge into 1 item, got {len(matching)}"
        assert matching[0]["quantity"] == 5, f"Expected qty 5 (2+3), got {matching[0]['quantity']}"

    def test_checked_item_does_not_merge(self):
        """Checked item with same food does NOT merge with new unchecked item."""
        food = make_food(f"eggs-{U}-nomerge")
        sl = make_shopping_list(f"NoMerge-{U}")

        # Create checked item first
        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "quantity": 6, "checked": True,
        })
        # Create unchecked item with same food
        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "quantity": 3, "checked": False,
        })

        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 2, f"Checked+unchecked should NOT merge, got {len(items)}"

    def test_different_units_no_merge(self):
        """Same food but different units → separate items (no merge)."""
        food = make_food(f"milk-{U}-units")
        unit_a = make_unit(f"cups-{U}-a")
        unit_b = make_unit(f"liters-{U}-b")
        sl = make_shopping_list(f"DiffUnit-{U}")

        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "unitId": unit_a["id"], "quantity": 2, "checked": False,
        })
        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"], "foodId": food["id"],
            "unitId": unit_b["id"], "quantity": 1, "checked": False,
        })

        detail = get_shopping_list(sl["id"])
        items = [i for i in detail.get("listItems", []) if i.get("foodId") == food["id"]]
        assert len(items) == 2, f"Different units should NOT merge, got {len(items)}"


class TestPaginationEnvelope:
    """Pattern 3: Pagination envelope has correct fields and behavior."""

    def test_pagination_envelope_fields(self):
        """Response envelope must have: page, per_page, total, total_pages, items."""
        # Create some recipes to ensure we have data
        for i in range(3):
            make_recipe(f"PagEnv-{U}-{i}")

        r = get("/api/recipes", params={"page": 1, "perPage": 2})
        assert r.status_code == 200
        data = r.json()

        assert "page" in data, f"Missing 'page'. Keys: {list(data.keys())}"
        assert "per_page" in data, f"Missing 'per_page'. Keys: {list(data.keys())}"
        assert "total" in data, f"Missing 'total'. Keys: {list(data.keys())}"
        assert "total_pages" in data, f"Missing 'total_pages'. Keys: {list(data.keys())}"
        assert "items" in data, f"Missing 'items'. Keys: {list(data.keys())}"

        assert data["page"] == 1
        assert data["per_page"] == 2
        assert len(data["items"]) <= 2
        assert data["total"] >= 3

    def test_pagination_limit_respected(self):
        """perPage=2 → at most 2 items returned."""
        for i in range(4):
            make_recipe(f"PagLimit-{U}-{i}")

        r = get("/api/recipes", params={"page": 1, "perPage": 2})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) <= 2, f"perPage=2 but got {len(items)} items"

    def test_pagination_offset_works(self):
        """Page 1 and page 2 return different items."""
        for i in range(5):
            make_recipe(f"PagOffset-{U}-{i}")

        r1 = get("/api/recipes", params={"page": 1, "perPage": 3})
        r2 = get("/api/recipes", params={"page": 2, "perPage": 3})
        ids1 = {item["id"] for item in r1.json().get("items", [])}
        ids2 = {item["id"] for item in r2.json().get("items", [])}

        overlap = ids1 & ids2
        assert not overlap, f"Page 1 and 2 overlap: {overlap}"


class TestSortingApplied:
    """Pattern 3: Sorting parameters must actually be applied."""

    def test_order_by_name_asc(self):
        """orderBy=name&orderDirection=asc → results sorted alphabetically."""
        names = [f"AAA-Sort-{U}", f"MMM-Sort-{U}", f"ZZZ-Sort-{U}"]
        for n in names:
            make_recipe(n)

        r = get("/api/recipes", params={
            "orderBy": "name", "orderDirection": "asc", "perPage": 100,
            "search": f"Sort-{U}",
        })
        assert r.status_code == 200
        items = r.json().get("items", [])
        result_names = [item["name"] for item in items]
        assert result_names == sorted(result_names, key=str.lower), \
            f"Not sorted asc: {result_names}"

    def test_order_by_name_desc(self):
        """orderBy=name&orderDirection=desc → results sorted reverse."""
        names = [f"AAA-Desc-{U}", f"MMM-Desc-{U}", f"ZZZ-Desc-{U}"]
        for n in names:
            make_recipe(n)

        r = get("/api/recipes", params={
            "orderBy": "name", "orderDirection": "desc", "perPage": 100,
            "search": f"Desc-{U}",
        })
        assert r.status_code == 200
        items = r.json().get("items", [])
        result_names = [item["name"] for item in items]
        assert result_names == sorted(result_names, key=str.lower, reverse=True), \
            f"Not sorted desc: {result_names}"


class TestMealPlanCamelCase:
    """Pattern 1: Meal plan response uses camelCase."""

    def test_meal_plan_response_fields(self):
        """POST mealplan → response has recipeId and entryType (camelCase)."""
        slug = make_recipe(f"MPRecipe-{U}")
        recipe = get_recipe(slug)

        r = post("/api/households/mealplans", {
            "date": _utc_today().isoformat(),
            "entryType": "dinner",
            "title": f"MP Test {U}",
            "recipeId": recipe["id"],
        })
        assert r.status_code == 201
        plan = r.json()

        # Must be camelCase
        assert "recipeId" in plan, f"Missing 'recipeId'. Keys: {list(plan.keys())}"
        assert "entryType" in plan, f"Missing 'entryType'. Keys: {list(plan.keys())}"
        assert "recipe_id" not in plan, "Should be 'recipeId' not 'recipe_id'"
        assert "entry_type" not in plan, "Should be 'entryType' not 'entry_type'"
        assert plan["recipeId"] == recipe["id"]
        assert plan["entryType"] == "dinner"


class TestMealPlanRuleCamelCase:
    """Pattern 1: Meal plan rule response uses camelCase."""

    def test_rule_response_fields(self):
        """POST rule → response has 'day' (string), 'entryType', 'queryFilterString'."""
        rule_id = str(uuid.uuid4())
        r = post("/api/households/mealplans/rules", {
            "day": "monday",
            "entryType": "lunch",
            "id": rule_id,
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
        })
        assert r.status_code == 201
        rule = r.json()

        assert "day" in rule, f"Missing 'day'. Keys: {list(rule.keys())}"
        assert "entryType" in rule, f"Missing 'entryType'. Keys: {list(rule.keys())}"
        assert rule["day"] == "monday"
        assert rule["entryType"] == "lunch"
        # Should NOT be snake_case
        assert "entry_type" not in rule, "Should be 'entryType' not 'entry_type'"
        assert "day_of_week" not in rule, "Should be 'day' not 'day_of_week'"


class TestFoodUnitCRUDCamelCase:
    """Pattern 1: Food/Unit responses use camelCase."""

    def test_food_response_camel_case(self):
        """POST food → response has camelCase keys."""
        r = post("/api/foods", {
            "name": f"Avocado-{U}",
            "pluralName": f"Avocados-{U}",
        })
        assert r.status_code == 201
        food = r.json()

        assert "id" in food
        assert "name" in food
        # Check for snake_case violations
        assert "plural_name" not in food, "Should use 'pluralName' not 'plural_name'"
        assert "label_id" not in food, "Should use 'labelId' not 'label_id'"
        assert "created_at" not in food, "Should use 'createdAt' not 'created_at'"

    def test_unit_response_camel_case(self):
        """POST unit → response has camelCase keys."""
        r = post("/api/units", {
            "name": f"Tablespoon-{U}",
            "abbreviation": "tbsp",
            "useAbbreviation": True,
        })
        assert r.status_code == 201
        unit = r.json()

        assert "id" in unit
        assert "name" in unit
        assert "use_abbreviation" not in unit, "Should use 'useAbbreviation' not 'use_abbreviation'"
        assert "plural_name" not in unit, "Should use 'pluralName' not 'plural_name'"
        assert "standard_quantity" not in unit, "Should use 'standardQuantity' not 'standard_quantity'"


class TestRatingAggregation:
    """Pattern 5: Rating aggregation must compute the actual average."""

    def test_single_user_rating(self):
        """One user rates → recipe.rating equals that rating."""
        slug = make_recipe(f"Rate1-{U}")

        r = post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 4.5})
        assert r.status_code == 200

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(4.5, abs=0.1), \
            f"Expected rating 4.5, got {recipe.get('rating')}"

    def test_two_user_rating_average(self):
        """Two users rate → recipe.rating is the average."""
        slug = make_recipe(f"Rate2-{U}")

        post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 5.0})
        post(f"/api/users/{USER_ID_2}/ratings/{slug}", {"rating": 3.0}, headers=HEADERS_USER2)

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(4.0, abs=0.1), \
            f"Expected avg 4.0 (5+3)/2, got {recipe.get('rating')}"

    def test_rating_update_recalculates(self):
        """Changing a rating recalculates the average."""
        slug = make_recipe(f"RateUpd-{U}")

        post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 2.0})
        post(f"/api/users/{USER_ID_2}/ratings/{slug}", {"rating": 4.0}, headers=HEADERS_USER2)

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(3.0, abs=0.1)

        # User1 changes to 4.0 → new avg (4+4)/2 = 4.0
        post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 4.0})

        recipe = get_recipe(slug)
        assert recipe.get("rating") == pytest.approx(4.0, abs=0.1), \
            f"Expected updated avg 4.0, got {recipe.get('rating')}"


class TestCookbookDynamicFilter:
    """Pattern 5: Cookbook filter must actually filter recipes."""

    def test_cookbook_filters_by_category(self):
        """Create cookbook with category filter → only matching recipes returned."""
        # Create category and recipes
        cat_name = f"CookbookCat-{U}"
        r = post("/api/organizers/categories", {"name": cat_name})
        assert r.status_code == 201
        cat = r.json()

        slug_in = make_recipe(f"InCB-{U}")
        recipe_in = get_recipe(slug_in)
        put(f"/api/recipes/{slug_in}", {**recipe_in, "recipeCategory": [{"id": cat["id"], "name": cat_name}]})

        slug_out = make_recipe(f"OutCB-{U}")

        # Create cookbook
        cb_data = {
            "name": f"CB-{U}",
            "groupId": GROUP_ID,
            "householdId": HOUSEHOLD_ID,
            "id": str(uuid.uuid4()),
            "queryFilterString": f'recipeCategory.id CONTAINS_ANY ["{cat["id"]}"]',
            "queryFilter": {
                "parts": [{
                    "attributeName": "recipeCategory.id",
                    "relationalOperator": "CONTAINS_ANY",
                    "value": [cat["id"]],
                }]
            },
        }
        r = post("/api/households/cookbooks", cb_data)
        assert r.status_code == 201
        cb = r.json()

        # Query via cookbook
        r = get("/api/recipes", params={"cookbook": cb["id"], "perPage": 100})
        assert r.status_code == 200
        slugs = [item.get("slug") for item in r.json().get("items", [])]

        assert slug_in in slugs, f"Recipe with category should appear. Got: {slugs}"
        assert slug_out not in slugs, f"Recipe without category should NOT appear"


class TestShoppingListItemResponse:
    """Pattern 2: Shopping list detail includes full item data."""

    def test_shopping_list_detail_has_list_items(self):
        """GET shopping list detail must include 'listItems' array."""
        sl = make_shopping_list(f"DetailSL-{U}")
        food = make_food(f"bread-{U}-detail")

        post("/api/households/shopping/items", {
            "shoppingListId": sl["id"],
            "foodId": food["id"],
            "quantity": 1,
            "checked": False,
        })

        detail = get_shopping_list(sl["id"])
        assert "listItems" in detail, f"Missing 'listItems'. Keys: {list(detail.keys())}"
        assert len(detail["listItems"]) >= 1, "Should have at least 1 item"

        item = detail["listItems"][0]
        # Verify camelCase in list item
        assert "shoppingListId" in item, f"Item missing 'shoppingListId'. Keys: {list(item.keys())}"
        assert "foodId" in item, f"Item missing 'foodId'. Keys: {list(item.keys())}"
        assert "recipeReferences" in item, f"Item missing 'recipeReferences'. Keys: {list(item.keys())}"


class TestSuggestionsResponseFormat:
    """Pattern 7 (eval report): Suggestions must return 'items' not 'suggestions'."""

    def test_suggestions_has_items_key(self):
        """GET /api/recipes/suggestions → response has 'items' key."""
        make_recipe(f"Suggest-{U}")

        r = get("/api/recipes/suggestions", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()

        assert "items" in data, f"Suggestions should have 'items' key, got keys: {list(data.keys())}"
        assert isinstance(data["items"], list)
        # Must NOT use 'suggestions'
        assert "suggestions" not in data or data.get("items") is not None, \
            "Should use 'items' not 'suggestions'"


class TestSelfRatingCamelCase:
    """Pattern 7 (eval report): Self rating response uses camelCase."""

    def test_self_rating_response(self):
        """GET /api/users/self/ratings/{recipe_id} → 'recipeId' not 'recipe_id'."""
        slug = make_recipe(f"SelfRate-{U}")
        recipe = get_recipe(slug)
        recipe_id = recipe["id"]

        # Rate it
        post(f"/api/users/{USER_ID}/ratings/{slug}", {"rating": 3.5})

        # Get self rating
        r = get(f"/api/users/self/ratings/{recipe_id}")
        assert r.status_code == 200
        data = r.json()

        assert "recipeId" in data, f"Missing 'recipeId'. Keys: {list(data.keys())}"
        assert "recipe_id" not in data, "Should be 'recipeId' not 'recipe_id'"
        # If isFavorite is present, check it's not snake_case
        if "isFavorite" in data or "is_favorite" in data:
            assert "isFavorite" in data, "Should be 'isFavorite' not 'is_favorite'"


class TestShoppingListBulkCreate:
    """Pattern 5: Bulk create respects merge logic."""

    def test_bulk_create_merges_same_food(self):
        """Bulk create 3 items, 2 with same food → end up with 2 items."""
        food_a = make_food(f"apple-{U}-bulk")
        food_b = make_food(f"banana-{U}-bulk")
        sl = make_shopping_list(f"BulkSL-{U}")

        r = post("/api/households/shopping/items/create-bulk", [
            {"shoppingListId": sl["id"], "foodId": food_a["id"], "quantity": 2},
            {"shoppingListId": sl["id"], "foodId": food_b["id"], "quantity": 1},
            {"shoppingListId": sl["id"], "foodId": food_a["id"], "quantity": 3},
        ])
        assert r.status_code == 201

        detail = get_shopping_list(sl["id"])
        items = detail.get("listItems", [])
        apple_items = [i for i in items if i.get("foodId") == food_a["id"]]
        banana_items = [i for i in items if i.get("foodId") == food_b["id"]]

        assert len(apple_items) == 1, f"Apple items should merge, got {len(apple_items)}"
        assert apple_items[0]["quantity"] == 5, f"Apple qty should be 5, got {apple_items[0]['quantity']}"
        assert len(banana_items) == 1


class TestFoodDeduplication:
    """Pattern 5: Food deduplication when used in recipes."""

    def test_food_dedup_via_recipe(self):
        """Create food explicitly, then use same name in recipe → reuses existing."""
        food_name = f"garlic-{U}-dedup"
        food = make_food(food_name)

        slug = make_recipe(f"FoodDedup-{U}")
        recipe = get_recipe(slug)
        put(f"/api/recipes/{slug}", {
            **recipe,
            "recipeIngredient": [
                {"food": {"name": food_name}, "quantity": 3, "note": "cloves"},
            ],
        })

        # Verify only one food with this name exists
        r = get("/api/foods", params={"search": food_name, "perPage": 100})
        items = r.json().get("items", [])
        matching = [f for f in items if f.get("name") == food_name]
        assert len(matching) == 1, f"Expected 1 food '{food_name}', got {len(matching)}"

        # Verify recipe ingredient references the existing food
        updated = get_recipe(slug)
        ings = updated.get("recipeIngredient", [])
        assert len(ings) == 1
        assert ings[0].get("food", {}).get("id") == food["id"]


class TestRecipeCreateReturnsSlugWith201:
    """Pattern 4: POST /api/recipes returns 201 and a slug string."""

    def test_create_returns_201(self):
        """POST /api/recipes → 201 status code."""
        r = post("/api/recipes", {"name": f"Status201-{U}"})
        assert r.status_code == 201, f"Expected 201, got {r.status_code}"

    def test_create_returns_slug_string(self):
        """POST /api/recipes → body is a slug string."""
        r = post("/api/recipes", {"name": f"SlugStr-{U}"})
        assert r.status_code == 201
        result = r.json()
        # Should be a string slug or dict with slug
        if isinstance(result, str):
            assert len(result) > 0
            assert " " not in result, f"Slug should not contain spaces: '{result}'"
        else:
            assert "slug" in result, f"If dict, should have 'slug' key"


class TestShoppingListCamelCaseInDetail:
    """Pattern 1+2: Shopping list full detail has camelCase throughout."""

    def test_shopping_list_full_detail_camel_case(self):
        """GET shopping list detail → camelCase keys everywhere."""
        sl = make_shopping_list(f"DetailCC-{U}")
        detail = get_shopping_list(sl["id"])

        # Top-level keys
        assert "groupId" in detail or "group_id" not in detail, \
            f"Should use 'groupId'. Keys: {list(detail.keys())}"
        assert "householdId" in detail, f"Missing 'householdId'. Keys: {list(detail.keys())}"
        assert "listItems" in detail, f"Missing 'listItems'. Keys: {list(detail.keys())}"
        assert "recipeReferences" in detail, f"Missing 'recipeReferences'. Keys: {list(detail.keys())}"
        assert "labelSettings" in detail, f"Missing 'labelSettings'. Keys: {list(detail.keys())}"

        # Must NOT have snake_case alternatives
        assert "group_id" not in detail
        assert "household_id" not in detail
        assert "list_items" not in detail
        assert "recipe_references" not in detail
        assert "label_settings" not in detail
