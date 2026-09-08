# KitchenOwl — Backend Implementation Spec

## Overview

KitchenOwl is a **grocery list and recipe manager with expense tracking** (based on [KitchenOwl](https://github.com/TomBurworthy/kitchenowl), 1.3K stars). Households share shopping lists, recipes, and expense tracking. It supports multi-user households, recipe-to-shopping-list conversion with servings scaling, and simplified debt calculation.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID identifying the user
- `X-Household-Id`: UUID identifying the household

Rules:
- Both headers are required on **all** endpoints.
- If either header is missing, return `401 Unauthorized`.
- Trust header values directly — no database validation of the user/household relationship is needed beyond auto-creation.
- On first request with a new `X-User-Id` + `X-Household-Id` combination, auto-create the membership (the user becomes a member of that household). If the household doesn't exist yet, auto-create it with a default name "My Household".
- **Data scoping**: All data is scoped to the household (`X-Household-Id`). Members of the same household share all data. Different households have completely separate data — items, recipes, etc. created under one household are invisible to other households.
- **Membership**: A user can be a member of multiple households. A household can have multiple members. Any user can join any household by sending requests with that household's ID.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (38 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Households — household management (3 endpoints)

- `GET /api/households` — Get the current household info
- `PUT /api/households` — Update household name
- `GET /api/households/members` — List all members of the current household

### 2. Items — pantry/ingredient items (4 endpoints)

Items are the master list of ingredients/products for a household.

- `GET /api/items` — List all items (supports `search` query param)
- `POST /api/items` — Create an item (name, category, defaultUnit)
- `PUT /api/items/{id}` — Update an item
- `DELETE /api/items/{id}` — Delete an item

### 3. Categories — for grouping items (5 endpoints)

Categories organize items and determine shopping list display order.

- `GET /api/categories` — List all categories (ordered by `ordering` field)
- `POST /api/categories` — Create a category (name, ordering)
- `GET /api/categories/{id}` — Get a single category
- `PUT /api/categories/{id}` — Update a category
- `DELETE /api/categories/{id}` — Delete a category (sets items' category to null)

### 4. Recipes — recipe management (5 endpoints)

- `GET /api/recipes` — List all recipes (supports `search` query param)
- `POST /api/recipes` — Create a recipe (name, description, servings, time, sourceUrl, tags, items)
- `GET /api/recipes/{id}` — Get a single recipe with full details
- `PUT /api/recipes/{id}` — Update a recipe
- `DELETE /api/recipes/{id}` — Delete a recipe

### 5. Shopping Lists — shared shopping lists (6 endpoints)

- `GET /api/shopping-lists` — List all shopping lists for the household
- `POST /api/shopping-lists` — Create a shopping list (name)
- `GET /api/shopping-lists/{id}` — Get a shopping list with its items
- `PUT /api/shopping-lists/{id}` — Update shopping list name
- `DELETE /api/shopping-lists/{id}` — Delete a shopping list and its items
- `POST /api/shopping-lists/{id}/add-recipe` — Add recipe ingredients to shopping list (with servings scaling)

### 6. Shopping List Items — items within a shopping list (3 endpoints)

- `POST /api/shopping-lists/{id}/items` — Add item to shopping list
- `PUT /api/shopping-lists/{listId}/items/{itemId}` — Update a shopping list item (amount, done)
- `DELETE /api/shopping-lists/{listId}/items/{itemId}` — Remove item from shopping list

### 7. Tags — recipe tags (4 endpoints)

- `GET /api/tags` — List all tags
- `POST /api/tags` — Create a tag (name)
- `PUT /api/tags/{id}` — Update a tag
- `DELETE /api/tags/{id}` — Delete a tag

### 8. Expenses — expense tracking (4 endpoints)

- `GET /api/expenses` — List all expenses for the household
- `POST /api/expenses` — Create an expense (amount, description, date, category, paidBy, splitBetween)
- `PUT /api/expenses/{id}` — Update an expense
- `DELETE /api/expenses/{id}` — Delete an expense

### 9. Expense Balances — computed balances (1 endpoint)

- `GET /api/expenses/balances` — Get simplified debt balances for the household

### 10. Meal Planner — meal planning (3 endpoints)

- `GET /api/meal-plan` — Get meal plan entries (supports `from` and `to` date filters)
- `POST /api/meal-plan` — Create a meal plan entry (date, mealType, recipeId)
- `DELETE /api/meal-plan/{id}` — Delete a meal plan entry

---

**Totals: 38 endpoints across 10 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 38 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create membership**: When a request comes in with `X-User-Id` and `X-Household-Id`, if that user is not yet a member of that household, auto-create the membership. If the household doesn't exist yet, create it with name "My Household".

2. **Household data isolation**: All resources (items, categories, recipes, shopping lists, expenses, meal plans, tags) belong to a household. Data is scoped by household ID — resources created in one household are completely invisible to requests made with a different household ID.

3. **Shopping list item merge**: When adding an item to a shopping list and an item with the same name (case-insensitive) already exists on that list (and is not done), increment the existing item's amount instead of creating a duplicate. If the existing item has no amount set and the new item has no amount, set amount to 2. If one has an amount and the other doesn't, treat the missing amount as 1.

4. **Recipe → shopping list scaling**: When adding a recipe to a shopping list via `POST /api/shopping-lists/{id}/add-recipe`, the `servings` parameter in the request body determines scaling. Scale factor = request.servings / recipe.servings. Each recipe item's amount is multiplied by this factor. If recipe.servings is 0 or null, no scaling is applied (use amounts as-is). The merge rule (rule 3) also applies here.

5. **Expense balances calculation**: For each expense, each person in `splitBetween` owes `amount / len(splitBetween)`. The person who paid (`paidBy`) is owed by the others. Balance for a user = sum(amounts they paid) - sum(shares they owe). The `/api/expenses/balances` endpoint returns simplified debts — minimize the number of transactions needed to settle all debts within the household.

6. **Debt simplification algorithm**: Calculate net balance for each member. Those with positive balance are creditors, negative are debtors. Match largest debtor with largest creditor, transfer the minimum of their absolute values, repeat until settled.

7. **Categories ordering**: Categories have an `ordering` integer field. `GET /api/categories` returns them sorted by `ordering` ascending, then by `id` ascending as tiebreaker.

8. **Done items persist**: Marking a shopping list item as `done: true` keeps it in the list (for purchase history). It is NOT deleted. Done items are still returned in `GET /api/shopping-lists/{id}`.

9. **Recipe items structure**: A recipe's `items` is an array of objects, each with `name`, `amount` (number, nullable), and `unit` (string, nullable). These represent ingredients.

10. **Tags on recipes**: Recipes have a `tags` array of tag IDs. When retrieving a recipe, `tags` should be expanded to full tag objects (id + name).

11. **Cascade deletes**:
    - Deleting a category sets items' category to null (does NOT delete items).
    - Deleting a shopping list deletes all its shopping list items.
    - Deleting a recipe removes it from any meal plan entries (deletes those entries).
    - Deleting a tag removes it from all recipes' tag lists.

12. **Meal plan entry**: Each entry has a `date` (YYYY-MM-DD string), `mealType` (one of "breakfast", "lunch", "dinner"), and `recipeId` referencing a recipe.

13. **Search**: The `search` query parameter on `GET /api/items` and `GET /api/recipes` performs case-insensitive substring matching on the `name` field.

14. **Expense splitBetween**: This is an array of user IDs (UUIDs). The `paidBy` field is a single user ID. Both must be members of the current household. If a referenced user is not a member, return `400 Bad Request`.
