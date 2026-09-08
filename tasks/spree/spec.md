# Spree — Multi-Store E-Commerce Platform

## Overview

Build a backend API for **Spree**, a multi-store e-commerce platform that supports multiple currencies, hierarchical product categories (taxons), a cart-based checkout flow with strict state machine transitions, promotions engine, stock management with split shipments, and payment processing via an external gateway.

A payment gateway is available through the `PAYMENT_GATEWAY_URL` environment variable. The evaluator sets this variable to the reachable service URL; use `http://localhost:9999` as the local-development fallback.

## Authentication & Authorization

All API requests require an `X-Store-Token` header. Missing or empty token returns `401 Unauthorized`.

- **Admin tokens**: tokens starting with `"admin_"` have full access to manage products, promotions, stock, shipping methods, and view all orders within the store.
- **Customer tokens**: all other tokens represent customers who can browse products, manage their own orders and wishlists.

Each token is scoped to a **store**. The store is identified by the token itself (all tokens with the same prefix up to the first `_` after `admin_` or the full token for customers belong to the same store context). For simplicity:
- Admin tokens: `admin_{store_id}_{anything}` → belongs to store `{store_id}`
- Customer tokens: `{store_id}_{customer_id}` → belongs to store `{store_id}`, identifies customer `{customer_id}`

Data is **store-isolated**: a token for store A cannot access data from store B.

## Core Concepts

### Stores
Each store has its own products, orders, currencies, and configuration. Store is implicitly determined by the token.

### Products & Variants
- A **Product** is a master record with name, description, price, and properties.
- Each product can have **Variants** with different option values (e.g., color: Red, size: L) and their own price/SKU.
- **Option Types** define the axes of variation (e.g., "Color", "Size") with possible values.
- **Properties** are key-value metadata on products (e.g., material: cotton, brand: Nike).

### Taxons (Categories)
- Hierarchical category tree. Each taxon has a name, optional `parentId`, and `permalink`.
- Products can be assigned to taxons.
- Querying a parent taxon returns products in all its descendants.

### Orders & Checkout State Machine
Orders follow a strict state machine:
```
cart → address → delivery → payment → confirm → complete
```
- **cart**: initial state, line items can be added/removed
- **address**: billing and shipping addresses must be set
- **delivery**: shipping method must be selected
- **payment**: payment must be authorized
- **confirm**: order is ready, advance to complete
- **complete**: order is fulfilled, stock is decremented

An order can be **cancelled** from any state except `complete`.

Advancing state (`POST /api/v1/orders/{id}/next`) validates requirements for the current state before transitioning.

### Line Items
Items in an order. Each has a `variantId`, `quantity`, and computed `price` (from variant price * quantity).

### Stock Management
- **Stock Locations**: warehouses/stores that hold inventory.
- **Stock Items**: per-variant, per-location inventory with `countOnHand` and `backorderable` flag.
- Adding to cart checks availability: if total stock across all locations < requested quantity and item is not backorderable, return 422.
- On order completion, `countOnHand` is decremented.
- If `backorderable` is true, items can be purchased even when `countOnHand` is 0.

### Shipments & Split Shipments
- Each order has one or more **Shipments** based on which stock locations can fulfill the items.
- If items come from different stock locations, the order has multiple shipments.
- Each shipment has a `shippingMethod` and `cost`.
- Shipping methods are configured with a name and flat cost.

### Payments
- Orders can have multiple payments (partial payments).
- Payments interact with the external payment gateway configured by `PAYMENT_GATEWAY_URL`.
- Payment flow: authorize → capture (on order complete) or void (on cancel).
- Payment states: `pending` → `authorized` → `captured` or `voided`.

### Promotions
- Admin-configured rules + actions.
- **Rules** (all must match for promotion to apply):
  - `minOrderAmount`: order item_total must be >= amount
  - `specificProducts`: order must contain at least one of listed product IDs
  - `firstOrder`: customer must have no previous completed orders
- **Actions**:
  - `percentOff`: percentage discount on item_total
  - `flatOff`: fixed amount discount
  - `freeShipping`: shipping cost becomes 0
- Promotions are auto-evaluated when advancing from `delivery` to `payment` state.
- Only the best single promotion applies (highest discount value).
- Adjustments are stored on the order.

### Order Totals
```
total = itemTotal + shipmentTotal + taxTotal + adjustmentTotal
```
- `itemTotal`: sum of line item prices
- `shipmentTotal`: sum of shipment costs
- `taxTotal`: simplified as 0 (tax calculation not required for this spec)
- `adjustmentTotal`: sum of promotion adjustments (negative values = discounts)

### Wishlists
- Customers can create named wishlists and add variants to them.
- Each customer can have multiple wishlists.

## Technical Requirements

- Storage starts empty — no seed data.
- All IDs are server-generated (string or integer).
- All field names use **camelCase**.
- List endpoints support pagination via `page` and `perPage` query params (default: page=1, perPage=25).
- Standard error responses: `{"error": "message"}`.
- 201 for successful creation, 200 for updates/gets, 204 for deletes, 422 for validation errors, 404 for not found, 401 for unauthorized, 403 for forbidden.
