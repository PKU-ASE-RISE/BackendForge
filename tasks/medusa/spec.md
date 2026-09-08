# Medusa — Headless E-Commerce Platform

## Overview

Build a headless e-commerce backend API inspired by Medusa.js. The platform provides a complete suite of APIs for managing products, customers, shopping carts, orders, payments, discounts, shipping, and regions.

## Authentication

All endpoints require an `X-API-Key` header:
- Missing header → HTTP 401
- Keys starting with `admin_` are admin users (can manage products, update orders, manage discounts, manage shipping, manage regions)
- All other keys are customer identifiers (can manage their own carts, addresses, orders)

## External Services

### Payment Service

A payment gateway service is available through the `PAYMENT_SERVICE_URL` environment variable. The evaluator sets this variable to the reachable service URL; use `http://localhost:9999` as the local-development fallback. Your implementation MUST call this service for all payment operations; do not implement payment processing yourself.

**Payment Service API:**

#### POST /v1/charges
Create a new charge.

Request body:
```json
{
  "amount": 5000,
  "currency": "usd",
  "description": "Order payment",
  "metadata": {"orderId": "order_123"}
}
```

Headers:
- `Idempotency-Key` (optional): Ensures idempotent requests

Response (201):
```json
{
  "id": "ch_abc123",
  "amount": 5000,
  "currency": "usd",
  "status": "succeeded",
  "description": "Order payment",
  "metadata": {"orderId": "order_123"},
  "createdAt": "2024-01-01T00:00:00Z"
}
```

Rules:
- If amount > 999999, status will be `failed`
- Otherwise, status will be `succeeded`
- Idempotency key returns same response for duplicate requests

#### GET /v1/charges/{id}
Retrieve a charge by ID.

Response (200):
```json
{
  "id": "ch_abc123",
  "amount": 5000,
  "currency": "usd",
  "status": "succeeded",
  "description": "Order payment",
  "metadata": {},
  "createdAt": "2024-01-01T00:00:00Z"
}
```

#### POST /v1/refunds
Create a refund for a charge.

Request body:
```json
{
  "chargeId": "ch_abc123",
  "amount": 2500,
  "reason": "customer_request"
}
```

Response (201):
```json
{
  "id": "re_xyz789",
  "chargeId": "ch_abc123",
  "amount": 2500,
  "reason": "customer_request",
  "status": "succeeded",
  "createdAt": "2024-01-01T00:00:00Z"
}
```

Rules:
- Refund amount must not exceed original charge amount
- Charge must exist and have status `succeeded`

## Data Model

### Regions
- id, name, currency (3-letter code), taxRate (percentage as decimal, e.g. 0.1 for 10%)
- A region defines a market with its currency and tax configuration

### Products
- id, title, description, handle (URL-friendly slug), status (draft/published), categoryId, collectionId, createdAt, updatedAt
- A product can have multiple variants and images

### Product Options
- id, productId, title (e.g., "Size", "Color")
- Define the axes of variation for a product

### Product Variants
- id, productId, title, sku, price (integer, in smallest currency unit), inventoryQuantity, options (key-value pairs matching product options)
- Each variant represents a specific combination (e.g., "Large / Red")

### Product Images
- id, productId, url, sortOrder

### Product Categories
- id, name, handle, parentCategoryId (nullable for top-level)

### Product Collections
- id, title, handle

### Customers
- id (same as API key), email, firstName, lastName, createdAt
- Customer is identified by their API key

### Customer Addresses
- id, customerId, firstName, lastName, address1, address2, city, province, postalCode, countryCode, phone, isDefault

### Carts
- id, customerId, regionId, items[], discountCode, createdAt
- Each customer can have at most one active cart
- Cart totals are calculated dynamically: subtotal, discount, tax, shipping, total

### Cart Items
- id, cartId, variantId, quantity, unitPrice

### Discounts
- id, code (unique, case-insensitive), type (percentage/fixed), value, usageLimit, usageCount, startsAt, endsAt, regionId (nullable — if set, only applies in that region)
- Percentage: value is 0-100 representing percent off
- Fixed: value is amount off in smallest currency unit

### Orders
- id, customerId, cartId, regionId, status, subtotal, discount, tax, shipping, total, paymentId, shippingMethodId, shippingAddress, createdAt, updatedAt
- Status workflow: pending → confirmed → shipped → delivered (or pending → cancelled)

### Shipping Methods
- id, regionId, name, price (flat rate in smallest currency unit)

### Payments
- id, orderId, chargeId (from payment service), amount, currency, status, refundId, createdAt

## Core Business Logic

### Cart Calculations
- `subtotal` = sum of (item.unitPrice * item.quantity)
- `discount` = apply discount code (percentage of subtotal, or fixed amount, capped at subtotal)
- `tax` = (subtotal - discount) * region.taxRate
- `shipping` = selected shipping method price (0 if none selected)
- `total` = subtotal - discount + tax + shipping

### Inventory
- When a cart is checked out (order created), inventory is decremented
- Cannot add to cart if variant inventoryQuantity < requested quantity
- Cannot checkout if any item's variant has insufficient inventory

### Discount Validation
- Code must exist and be active (current time between startsAt and endsAt, or no time bounds)
- Usage count must be less than usage limit (if limit is set)
- If discount has a regionId, cart's region must match
- Usage count increments when order is created from cart with that discount

### Order Status Transitions
- pending → confirmed (admin only)
- confirmed → shipped (admin only)
- shipped → delivered (admin only)
- pending → cancelled (admin or customer who owns the order)
- No other transitions allowed

### Payment Flow
1. Customer creates an order from their cart (POST /store/orders)
2. System calls payment service to create a charge
3. If charge succeeds, order status is `pending` with associated payment
4. If charge fails, order is not created (return error)
5. Admin can refund an order's payment (POST /admin/orders/{id}/refund)

## API Endpoint Groups

### Store Endpoints (customer-facing)

#### Products (read-only for customers)
- GET /store/products — list published products (supports search by title, filter by categoryId, collectionId)
- GET /store/products/{id} — get product with variants, options, images

#### Customers
- POST /store/customers — register (create profile for current API key)
- GET /store/customers/me — get own profile
- PUT /store/customers/me — update own profile

#### Customer Addresses
- GET /store/customers/me/addresses — list own addresses
- POST /store/customers/me/addresses — add address
- PUT /store/customers/me/addresses/{id} — update address
- DELETE /store/customers/me/addresses/{id} — delete address

#### Carts
- POST /store/carts — create a cart (one active cart per customer)
- GET /store/carts/mine — get active cart with calculated totals
- POST /store/carts/mine/items — add item to cart
- PUT /store/carts/mine/items/{itemId} — update item quantity
- DELETE /store/carts/mine/items/{itemId} — remove item from cart
- POST /store/carts/mine/discount — apply discount code
- DELETE /store/carts/mine/discount — remove discount code
- PUT /store/carts/mine/shipping — set shipping method

#### Orders
- POST /store/orders — create order from active cart (triggers payment)
- GET /store/orders — list own orders
- GET /store/orders/{id} — get order details
- POST /store/orders/{id}/cancel — cancel own order (only if pending)

#### Regions & Shipping (read-only)
- GET /store/regions — list regions
- GET /store/regions/{id}/shipping-methods — list shipping methods for a region

### Admin Endpoints

#### Products
- POST /admin/products — create product
- PUT /admin/products/{id} — update product
- DELETE /admin/products/{id} — delete product

#### Product Variants
- POST /admin/products/{id}/variants — add variant
- PUT /admin/products/{id}/variants/{variantId} — update variant
- DELETE /admin/products/{id}/variants/{variantId} — delete variant

#### Product Options
- POST /admin/products/{id}/options — add option
- DELETE /admin/products/{id}/options/{optionId} — delete option

#### Product Images
- POST /admin/products/{id}/images — add image
- DELETE /admin/products/{id}/images/{imageId} — delete image

#### Categories
- POST /admin/categories — create category
- GET /admin/categories — list categories
- PUT /admin/categories/{id} — update category
- DELETE /admin/categories/{id} — delete category

#### Collections
- POST /admin/collections — create collection
- GET /admin/collections — list collections
- PUT /admin/collections/{id} — update collection
- DELETE /admin/collections/{id} — delete collection

#### Orders (admin)
- GET /admin/orders — list all orders
- PUT /admin/orders/{id}/status — update order status
- POST /admin/orders/{id}/refund — refund order payment

#### Discounts
- POST /admin/discounts — create discount
- GET /admin/discounts — list discounts
- PUT /admin/discounts/{id} — update discount
- DELETE /admin/discounts/{id} — delete discount

#### Shipping Methods
- POST /admin/shipping-methods — create shipping method
- GET /admin/shipping-methods — list shipping methods
- PUT /admin/shipping-methods/{id} — update shipping method
- DELETE /admin/shipping-methods/{id} — delete shipping method

#### Regions
- POST /admin/regions — create region
- GET /admin/regions — list regions
- PUT /admin/regions/{id} — update region
- DELETE /admin/regions/{id} — delete region

## Notes

- All IDs are server-generated (UUIDs or similar)
- All timestamps are ISO 8601 format
- All monetary values are integers in the smallest currency unit (e.g., cents)
- Prices in responses should be integers
- List endpoints should support basic pagination via `limit` and `offset` query parameters
- Storage starts empty — no seed data
- The tech stack is your choice
