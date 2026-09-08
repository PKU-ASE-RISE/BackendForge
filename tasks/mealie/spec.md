# RecipeVault — Backend Implementation Spec

## Overview

RecipeVault is a **self-hosted recipe management application** (based on [Mealie](https://github.com/mealie-recipes/mealie), 12K★). Users manage recipes, organize with categories/tags, plan meals, create shopping lists from recipes, and rate/favorite recipes.

The application is deployed locally (single machine, small household). A typical power user accumulates 5,000–50,000 recipes. Performance matters.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice (SQLAlchemy, raw SQL, none, etc.)

## Authentication

Header-based auth (no JWT/OAuth):
- `X-User-Id`: UUID of the current user
- `X-Group-Id`: UUID of the user's group
- `X-Household-Id`: UUID of the user's household

Rules:
- All three headers are required on every request. If any is missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup to verify the IDs is required.
- **Data scoping**: Recipes, foods, units, tags, categories, and tools are scoped to `group_id`. Shopping lists, meal plans, and cookbooks are scoped to `household_id`. Ratings and favorites are scoped to `user_id`.
- **Isolation**: A request with group A's ID must never see or modify data belonging to group B. Same for households.

## API Contract

The full OpenAPI 3.1 spec is in **`openapi.yaml`** (51 paths, 94 endpoints, 102 schemas). Your implementation must match this contract exactly — response structure, field names, status codes.

All paginated list endpoints share the same query params: `page`, `perPage`, `orderBy`, `orderDirection`, `orderByNullPosition`, `queryFilter`, `paginationSeed`, and optionally `search`. They all return the same envelope: `{page, per_page, total, total_pages, items, next, previous}`.

---

### 1. Recipes — core CRUD + search + filter (6 paths, 12 methods)

The heart of the app. Recipes support rich filtering by categories, tags, tools, foods, and households. List endpoint supports `requireAll*` flags for AND vs OR filtering. Cookbook-based filtering via `cookbook` query param.

- `GET /api/recipes` — Paginated list; filterable by categories, tags, tools, foods, households, cookbook; searchable
- `POST /api/recipes` — Create (just name → returns slug)
- `PUT /api/recipes` — Bulk update (array of Recipe)
- `PATCH /api/recipes` — Bulk partial update (array of Recipe)
- `GET /api/recipes/{slug}` — Full detail (by slug or id)
- `PUT /api/recipes/{slug}` — Full update
- `PATCH /api/recipes/{slug}` — Partial update
- `DELETE /api/recipes/{slug}` — Delete
- `GET /api/recipes/{slug}/comments` — List comments on a recipe
- `POST /api/recipes/{slug}/duplicate` — Deep copy (all sub-entities); optional new name
- `PATCH /api/recipes/{slug}/last-made` — Track when recipe was last made (timestamp)
- `GET /api/recipes/suggestions` — Recipe suggestions based on available foods/tools; params: `foods`, `tools`, `limit`, `maxMissingFoods`, `maxMissingTools`, `includeFoodsOnHand`, `includeToolsOnHand`

### 2. Comments — independent CRUD (2 paths, 5 methods)

Top-level comment management, independent of the recipe comments sub-endpoint. Each comment belongs to a recipe (via `recipeId`) and a user.

- `GET /api/comments` — Paginated list of all comments
- `POST /api/comments` — Create comment (body: `recipeId`, `text`)
- `GET /api/comments/{item_id}` — Get single comment
- `PUT /api/comments/{item_id}` — Update comment (body: `id`, `text`)
- `DELETE /api/comments/{item_id}` — Delete comment

### 3. Foods — ingredient food library (3 paths, 6 methods)

Shared food entities referenced by recipe ingredients. Support aliases, labels, and plural names. Scoped to group.

- `GET /api/foods` — Paginated list (searchable)
- `POST /api/foods` — Create food
- `GET /api/foods/{item_id}` — Get single food
- `PUT /api/foods/{item_id}` — Update food
- `DELETE /api/foods/{item_id}` — Delete food
- `PUT /api/foods/merge` — **Merge** food A into food B (body: `fromFood`, `toFood`); updates all references then deletes A

### 4. Units — ingredient unit library (3 paths, 6 methods)

Shared unit entities referenced by recipe ingredients. Support abbreviations, aliases, fractions, and standard-unit conversions (`standardQuantity`/`standardUnit` for unit conversion).

- `GET /api/units` — Paginated list (searchable)
- `POST /api/units` — Create unit
- `GET /api/units/{item_id}` — Get single unit
- `PUT /api/units/{item_id}` — Update unit
- `DELETE /api/units/{item_id}` — Delete unit
- `PUT /api/units/merge` — **Merge** unit A into unit B (body: `fromUnit`, `toUnit`); updates all references then deletes A

### 5. Organizers — Categories (4 paths, 7 methods)

Recipe categories with slug-based lookup. Each category tracks how many recipes use it.

- `GET /api/organizers/categories` — Paginated list (searchable)
- `POST /api/organizers/categories` — Create category (body: `name`)
- `GET /api/organizers/categories/empty` — List categories with 0 recipes (returns array, not paginated)
- `GET /api/organizers/categories/slug/{category_slug}` — Lookup by slug (returns category with its recipes)
- `GET /api/organizers/categories/{item_id}` — Get by ID (returns CategorySummary)
- `PUT /api/organizers/categories/{item_id}` — Update (body: `name`)
- `DELETE /api/organizers/categories/{item_id}` — Delete

### 6. Organizers — Tags (4 paths, 7 methods)

Recipe tags. Same pattern as categories: full CRUD + empty listing + slug lookup. Slug lookup returns tag with associated recipes.

- `GET /api/organizers/tags` — Paginated list (searchable)
- `POST /api/organizers/tags` — Create tag (body: `name`)
- `GET /api/organizers/tags/empty` — List tags with 0 recipes
- `GET /api/organizers/tags/slug/{tag_slug}` — Lookup by slug (returns RecipeTagResponse with recipes)
- `GET /api/organizers/tags/{item_id}` — Get by ID (returns RecipeTagResponse)
- `PUT /api/organizers/tags/{item_id}` — Update (body: `name`)
- `DELETE /api/organizers/tags/{item_id}` — Delete

### 7. Organizers — Tools (3 paths, 6 methods)

Kitchen tools/equipment linked to recipes. Tracks which households have each tool (`householdsWithTool`). Slug lookup returns tool with associated recipes.

- `GET /api/organizers/tools` — Paginated list (searchable)
- `POST /api/organizers/tools` — Create tool
- `GET /api/organizers/tools/slug/{tool_slug}` — Lookup by slug (returns RecipeToolResponse with recipes)
- `GET /api/organizers/tools/{item_id}` — Get by ID
- `PUT /api/organizers/tools/{item_id}` — Update
- `DELETE /api/organizers/tools/{item_id}` — Delete

### 8. Cookbooks — dynamic recipe collections (2 paths, 6 methods)

A cookbook = a set of filter rules (stored as `queryFilterString` / `queryFilter`). Listing a cookbook's recipes = querying recipes with those filters. Scoped to household.

- `GET /api/households/cookbooks` — Paginated list
- `POST /api/households/cookbooks` — Create cookbook
- `PUT /api/households/cookbooks` — Bulk update (array of cookbooks; reorder via `position`)
- `GET /api/households/cookbooks/{item_id}` — Get single cookbook (by ID or slug)
- `PUT /api/households/cookbooks/{item_id}` — Update cookbook
- `DELETE /api/households/cookbooks/{item_id}` — Delete cookbook

### 9. Meal Plans — planning + rules + random (6 paths, 12 methods)

Plan meals by date + entry type (breakfast/lunch/dinner/side/snack/drink/dessert). Can link to a recipe or be free-text. Scoped to household.

- `GET /api/households/mealplans` — Paginated list; filterable by `start_date` / `end_date`
- `POST /api/households/mealplans` — Create plan entry (body: `date` required, plus `entryType`, `title`, `text`, `recipeId`)
- `GET /api/households/mealplans/today` — Get today's meal plan entries
- `GET /api/households/mealplans/{item_id}` — Get single plan entry (integer ID)
- `PUT /api/households/mealplans/{item_id}` — Update plan entry
- `DELETE /api/households/mealplans/{item_id}` — Delete plan entry
- `POST /api/households/mealplans/random` — **Generate random meal** based on rules (body: `date`, `entryType`)
- `GET /api/households/mealplans/rules` — Paginated list of rules
- `POST /api/households/mealplans/rules` — Create rule (day-of-week + entry type → query filter for eligible recipes)
- `GET /api/households/mealplans/rules/{item_id}` — Get single rule
- `PUT /api/households/mealplans/rules/{item_id}` — Update rule
- `DELETE /api/households/mealplans/rules/{item_id}` — Delete rule

### 10. Shopping Lists — list CRUD + recipe operations (6 paths, 9 methods)

Shopping lists with recipe integration. Adding a recipe extracts ingredients as list items. Removing decrements proportionally. Label settings control item ordering by label.

- `GET /api/households/shopping/lists` — Paginated list (returns ShoppingListSummary — no items)
- `POST /api/households/shopping/lists` — Create list
- `GET /api/households/shopping/lists/{item_id}` — Get full list (includes listItems, recipeReferences, labelSettings)
- `PUT /api/households/shopping/lists/{item_id}` — Update list
- `DELETE /api/households/shopping/lists/{item_id}` — Delete list
- `PUT /api/households/shopping/lists/{item_id}/label-settings` — Update label sort order (array of `{shoppingListId, labelId, position, id}`)
- `POST /api/households/shopping/lists/{item_id}/recipe` — **Add recipes to list** (bulk; body: array of `{recipeId, recipeIncrementQuantity, recipeIngredients?}`)
- `POST /api/households/shopping/lists/{item_id}/recipe/{recipe_id}` — **Add single recipe to list** (body: same params)
- `POST /api/households/shopping/lists/{item_id}/recipe/{recipe_id}/delete` — **Remove recipe from list** (body: `recipeDecrementQuantity`)

### 11. Shopping Items — independent item CRUD (3 paths, 8 methods)

Direct CRUD on shopping list items, independent of the list-level recipe operations. Items support merging logic: creating/updating items with matching food+unit on the same list merges quantities. Returns `ShoppingListItemsCollectionOut` with `createdItems`, `updatedItems`, `deletedItems`.

- `GET /api/households/shopping/items` — Paginated list of all items
- `POST /api/households/shopping/items` — Create single item (may merge → returns collection)
- `PUT /api/households/shopping/items` — Bulk update (array of items; may merge → returns collection)
- `DELETE /api/households/shopping/items` — Bulk delete (query param: `ids` array)
- `POST /api/households/shopping/items/create-bulk` — **Bulk create** (array of items; auto-merge)
- `GET /api/households/shopping/items/{item_id}` — Get single item
- `PUT /api/households/shopping/items/{item_id}` — Update single item (may merge → returns collection)
- `DELETE /api/households/shopping/items/{item_id}` — Delete single item

### 12. Users — profile, ratings, favorites (9 paths, 10 methods)

User profile + per-user recipe ratings and favorites. "Self" endpoints use the authenticated user from headers. `{id}` endpoints work on any user.

- `GET /api/users/self` — Get current user profile (UserOut)
- `PUT /api/users/{item_id}` — Update user profile (UserBase)
- `GET /api/users/self/ratings` — Current user's ratings (returns `{ratings: [UserRatingSummary]}`)
- `GET /api/users/self/ratings/{recipe_id}` — Current user's rating for a specific recipe
- `GET /api/users/{id}/ratings` — Any user's ratings (returns `{ratings: [UserRatingOut]}`)
- `POST /api/users/{id}/ratings/{slug}` — **Rate a recipe** (body: UserRatingUpdate with `rating` and/or `isFavorite`)
- `GET /api/users/self/favorites` — Current user's favorites (returns `{ratings: [UserRatingSummary]}` filtered to favorites)
- `GET /api/users/{id}/favorites` — Any user's favorites (returns `{ratings: [UserRatingOut]}`)
- `POST /api/users/{id}/favorites/{slug}` — **Add favorite**
- `DELETE /api/users/{id}/favorites/{slug}` — **Remove favorite**

---

**Totals: 51 paths, 94 methods across 12 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 51 paths / 94 methods** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Shopping list merging**: When adding items, if the same food already exists on the list (unchecked), merge quantities instead of creating duplicates. If units differ but are convertible (e.g., cups↔ml), convert and merge.

2. **Recipe → Shopping list**: Adding a recipe to a shopping list extracts all ingredients and adds them as items. If a recipe references another recipe as an ingredient, recursively expand. Track which recipe each item came from (recipe_references).

3. **Removing recipe from shopping list**: Decrement quantities proportionally by the recipe's scale. Remove items that hit 0 quantity and have no other recipe references.

4. **Rating aggregation**: A recipe's `rating` is the average of all `users_to_recipes.rating` values, not a directly-set field. Recalculate on each rating change.

5. **Tag/Category/Food deduplication**: When creating a recipe with `tags: [{name: "Italian"}]`, reuse the existing "Italian" tag (match by name within group), don't create a duplicate.

6. **Food/Unit merge**: Merging food A into food B means: update all recipe_ingredients referencing A to point to B, then delete A. Same for units.

7. **Slug uniqueness**: Recipe slugs must be unique within a group. Handle collisions.

8. **Meal plan random**: Must respect meal plan rules (day-of-week + entry type → required tags/categories). Don't return recently-used recipes.

9. **Cookbook dynamic filtering**: A cookbook stores filter criteria (categories, tags, tools, etc.). Listing a cookbook's recipes = querying with those filters.

10. **Checked items**: Checked shopping list items should not participate in merging and should not have recipe references.
