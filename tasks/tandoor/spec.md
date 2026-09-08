# Tandoor Recipes — Backend Implementation Spec

## Overview

Tandoor Recipes is a **recipe management application** with meal planning, shopping lists, and nutritional tracking (based on [TandoorRecipes](https://github.com/TandoorRecipes/recipes), 8.3K stars). Users organize recipes with hierarchical keywords, plan meals, and auto-generate shopping lists with ingredient merging and servings scaling.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth with space isolation:

- `X-User-Id`: UUID identifying the user
- `X-Space-Id`: UUID identifying the space (data namespace)

Rules:
- Both headers are required on ALL endpoints.
- If either header is missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup needed. If a user/space hasn't been seen before, treat it as a new context (data scoped to that space).
- **Data scoping**: All data is scoped to the space (`X-Space-Id`). Users in the same space share data. Different spaces cannot see each other's data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 paths, 47 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Keywords — hierarchical tags (5 endpoints)

Keywords have optional parent-child relationships forming a tree structure.

- `GET /api/keywords` — List keywords (supports `search` query, `parent_id` filter, `root_only` flag)
- `POST /api/keywords` — Create a keyword (body: `name`, optional `parent_id`, `description`)
- `GET /api/keywords/{id}` — Get a single keyword
- `PUT /api/keywords/{id}` — Update a keyword
- `DELETE /api/keywords/{id}` — Delete a keyword (cascades: removes from recipes, deletes children keywords)

### 2. Foods — ingredient foods (5 endpoints)

Foods represent ingredient items. They can have nutritional data and optionally link to a recipe (sub-recipe).

- `GET /api/foods` — List foods (supports `search` query)
- `POST /api/foods` — Create a food
- `GET /api/foods/{id}` — Get a single food
- `PUT /api/foods/{id}` — Update a food
- `DELETE /api/foods/{id}` — Delete a food

### 3. Units — measurement units (5 endpoints)

Units for ingredient measurements (e.g., grams, cups, tablespoons).

- `GET /api/units` — List units (supports `search` query)
- `POST /api/units` — Create a unit
- `GET /api/units/{id}` — Get a single unit
- `PUT /api/units/{id}` — Update a unit
- `DELETE /api/units/{id}` — Delete a unit

### 4. Recipes — the core entity (6 endpoints)

Recipes contain steps, each with ingredients. They link to keywords.

- `GET /api/recipes` — List recipes (supports `search`, `keywords` filter including hierarchy, pagination)
- `POST /api/recipes` — Create a recipe (with inline steps and ingredients)
- `GET /api/recipes/{id}` — Get full recipe detail (includes steps, ingredients, keywords)
- `PUT /api/recipes/{id}` — Update a recipe (replaces steps/ingredients)
- `DELETE /api/recipes/{id}` — Delete a recipe
- `GET /api/recipes/{id}/nutrition` — Compute nutritional info for the recipe

### 5. Meal Plans — meal scheduling (5 endpoints)

Plan meals with date, meal type, and recipe reference.

- `GET /api/meal-plans` — List meal plans (supports `from_date`, `to_date` filter)
- `POST /api/meal-plans` — Create a meal plan
- `GET /api/meal-plans/{id}` — Get a single meal plan
- `PUT /api/meal-plans/{id}` — Update a meal plan
- `DELETE /api/meal-plans/{id}` — Delete a meal plan

### 6. Shopping Lists — with entries and recipe integration (9 endpoints)

Shopping lists contain entries (food + amount + unit). Can auto-import from recipes with scaling.

- `GET /api/shopping-lists` — List shopping lists
- `POST /api/shopping-lists` — Create a shopping list
- `GET /api/shopping-lists/{id}` — Get a shopping list with entries
- `PUT /api/shopping-lists/{id}` — Update shopping list name/supermarket
- `DELETE /api/shopping-lists/{id}` — Delete a shopping list
- `POST /api/shopping-lists/{id}/entries` — Add an entry manually
- `PUT /api/shopping-lists/{id}/entries/{entry_id}` — Update an entry (e.g., check/uncheck)
- `DELETE /api/shopping-lists/{id}/entries/{entry_id}` — Remove an entry
- `POST /api/shopping-lists/{id}/add-recipe` — Add all ingredients from a recipe (with servings scaling + merging)

### 7. Supermarkets — store organization (5 endpoints)

Supermarkets with category ordering for organized shopping.

- `GET /api/supermarkets` — List supermarkets
- `POST /api/supermarkets` — Create a supermarket
- `GET /api/supermarkets/{id}` — Get a supermarket (with category ordering)
- `PUT /api/supermarkets/{id}` — Update a supermarket
- `DELETE /api/supermarkets/{id}` — Delete a supermarket

### 8. Supermarket Categories — food categorization (5 endpoints)

Categories for organizing foods in supermarket aisles.

- `GET /api/supermarket-categories` — List categories
- `POST /api/supermarket-categories` — Create a category
- `GET /api/supermarket-categories/{id}` — Get a category
- `PUT /api/supermarket-categories/{id}` — Update a category
- `DELETE /api/supermarket-categories/{id}` — Delete a category

### 9. Import/Export — recipe interchange (2 endpoints)

- `POST /api/import/url` — Import a recipe from URL (mock: always returns a preset recipe)
- `GET /api/recipes/{id}/export` — Export a recipe as structured JSON

---

**Totals: 35 paths, 47 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 35 paths / 47 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Keyword hierarchy search**: When filtering recipes by a keyword, also include recipes tagged with any descendant keyword. Example: filtering by "Italian" also returns recipes tagged "Pasta" if "Pasta" is a child of "Italian".

2. **Keyword cascade delete**: Deleting a keyword also deletes all its descendant keywords (children, grandchildren, etc.) and removes all those keywords from any recipes.

3. **Keyword circular reference prevention**: A keyword's parent cannot be itself or any of its descendants. Return `400 Bad Request` if attempted.

4. **Shopping list ingredient merging**: When adding a recipe to a shopping list, if an entry with the same `food_id` AND same `unit_id` already exists and is not checked, merge by adding the amounts together instead of creating a duplicate entry.

5. **Servings scaling**: When adding a recipe to a shopping list via `POST /api/shopping-lists/{id}/add-recipe`, the `servings` field specifies desired servings. Ingredient amounts are scaled by `(desired_servings / recipe.servings)`. Example: recipe has 4 servings with 200g flour. Adding with servings=2 adds 100g flour.

6. **Nutritional computation**: `GET /api/recipes/{id}/nutrition` computes per-serving nutrition by: summing `(ingredient.amount × food.calories_per_unit)` etc. for all ingredients across all steps, then dividing by `recipe.servings`. If a food has no nutrition data (all values null), it contributes 0. If ingredient has `no_amount=true`, it contributes 0.

7. **Food-recipe link**: A food can have a `recipe_id` field pointing to another recipe. This is informational only (used for sub-recipe display). The linked recipe must exist and belong to the same space. Setting an invalid `recipe_id` returns `400 Bad Request`.

8. **Ingredient headers**: An ingredient with `is_header=true` is a section divider (e.g., "For the sauce"). It has no food/unit/amount and is excluded from shopping list generation and nutrition calculations.

9. **No-amount ingredients**: An ingredient with `no_amount=true` (e.g., "salt to taste") has amount=0 and is excluded from nutrition calculations and gets amount=0 when added to shopping lists.

10. **Recipe steps ordering**: Steps have an `order` field. They are always returned sorted by `order` ascending. Each step contains an `ingredients` array.

11. **Data isolation by space**: All data is scoped to `X-Space-Id`. A user in space A cannot see or modify data created in space B, even if it's the same user.

12. **Import URL (mock)**: The `POST /api/import/url` endpoint accepts a `url` field. Since we cannot fetch real URLs, it always creates a recipe with: name="Imported Recipe", servings=4, working_time=30, waiting_time=0, with one step containing instruction "Imported from {url}" and no ingredients. Returns the created recipe.

13. **Export format**: `GET /api/recipes/{id}/export` returns the full recipe data including all steps and ingredients, in the same schema as `GET /api/recipes/{id}` but wrapped in an `export` envelope with `version` and `exported_at` fields.

14. **Unique constraints**: Keyword names must be unique within the same parent (siblings cannot have the same name). Food names must be unique within a space. Unit names must be unique within a space. Return `400 Bad Request` on duplicates.

15. **Shopping list entries — checked status**: Entries have a `checked` boolean. Checked entries are excluded from merging (a new unchecked entry is created even if a checked entry with same food+unit exists).
