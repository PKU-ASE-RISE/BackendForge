# Saleor — Headless E-Commerce Platform

## Overview

Build a headless e-commerce API inspired by **Saleor** — a multi-channel, multi-warehouse commerce platform. The system manages products with dynamic attributes, per-channel pricing, warehouse-level stock tracking, checkout with shipping zone awareness, voucher discounts, tax calculation, and order fulfillment with partial shipments.

## Architecture

- **API Style**: RESTful JSON API
- **Authentication**: `X-API-Key` header. Keys starting with `"staff_"` grant staff (admin) permissions; all other keys are treated as customer tokens (the key value is the customer identifier).
- **Channel Scoping**: Most product/checkout/order queries require a `?channel=<slug>` query parameter. Products without a listing in the requested channel are invisible.
- **Storage**: Starts empty — no seed data. All state is created via the API.
- **Tech Stack**: Your choice of language, framework, and database.

## External Services

A **payment gateway** is available through the `PAYMENT_URL` environment variable. The evaluator sets this variable to the reachable service URL; use `http://localhost:9999` as the local-development fallback. It supports:
- `POST /v1/charges` — Create a charge (with optional `capture: false` for authorize-only)
- `GET /v1/charges/{id}` — Get charge status
- `POST /v1/captures` — Capture a previously authorized charge
- `POST /v1/refunds` — Refund a charge

The payment flow is **authorize + capture**: during checkout completion, create a charge with `capture: false`. When an order is fulfilled, capture the charge. Refunds are issued when orders are returned.

## Domain Concepts

### Channels
Channels represent distinct sales surfaces (e.g., "web-us", "mobile-eu", "b2b"). Each channel has:
- `slug` (unique identifier)
- `name`
- `currencyCode` (ISO 4217, e.g., "USD", "EUR")
- `isActive` flag

Products, prices, and checkouts are scoped to a channel. A product can have different prices in different channels.

### Warehouses
Physical or logical stock locations. Each warehouse has:
- `name`
- `slug` (unique)
- `address` (country, city, postal code, street)
- `shippingZones` — which shipping zones this warehouse serves

Stock is tracked per (variant, warehouse) pair.

### Product Types
Templates defining the structure of a product:
- `name`
- `slug`
- `productAttributes` — list of attribute definitions (name, type: "text"|"numeric"|"boolean"|"select", choices for select)
- `variantAttributes` — attributes that differ per variant (e.g., size, color)
- `taxClassId` — default tax class for products of this type
- `isDigital` — whether products of this type are digital (no shipping)

### Products
- Belong to a product type
- `name`, `slug`, `description`
- `categoryId`
- `attributes` — values for the product-level attributes
- **Channel Listings**: per-channel visibility and pricing config
- **Variants**: each variant has SKU, attributes, weight, and per-channel prices

### Product Variants
- Belong to a product
- `name`, `sku`
- `attributes` — variant-level attribute values
- `weight` (grams)
- `channelListings` — array of `{channelSlug, price, costPrice, currencyCode}`
- `stocks` — array of `{warehouseId, quantity, allocatedQuantity}`

### Categories
Hierarchical tree structure:
- `name`, `slug`, `description`
- `parentId` (null for root categories)
- Children accessible via API

### Collections
Curated product groupings:
- `name`, `slug`, `description`
- Products can be added/removed
- Per-channel visibility (published/unpublished per channel)

### Shipping Zones
Geographic regions with shipping methods:
- `name`
- `countries` — list of ISO country codes this zone covers
- `warehouses` — which warehouses can fulfill to this zone
- **Shipping Methods**: each method has name, type ("price"|"weight"), min/max order values, and a rate

### Tax Classes
- `name`
- `rates` — array of `{countryCode, rate}` (rate is a decimal, e.g., 0.20 for 20%)

Products inherit tax class from their product type (or override). Tax is calculated based on the shipping destination country.

### Vouchers
Discount codes with constraints:
- `code` (unique)
- `type`: "percentage" | "fixed" | "freeShipping"
- `value` — discount value (percentage or fixed amount)
- `channelSlug` — if set, voucher only works in this channel (null = all channels)
- `minOrderValue` — minimum order amount to apply
- `usageLimit` — max total uses (null = unlimited)
- `usedCount` — current usage count
- `products` — if set, only applies to these product IDs
- `categories` — if set, only applies to products in these category IDs
- `startDate`, `endDate`

### Customers
- `email`, `firstName`, `lastName`
- `addresses` — list of addresses (with `isDefaultShipping`, `isDefaultBilling`)
- `note` — staff-editable note

### Checkout
A checkout is a cart-in-progress:
- `channelSlug` — scoped to a channel
- `lines` — items with `variantId` and `quantity`
- `shippingAddress`, `billingAddress`
- `shippingMethodId` — chosen shipping method
- `voucherCode` — applied discount code
- `customerEmail`

Checkout flow:
1. Create checkout (with channel)
2. Add/update/remove lines
3. Set addresses
4. Select shipping method (only methods valid for the shipping address country)
5. Optionally apply voucher
6. Complete checkout → creates Order, allocates stock, authorizes payment

### Orders
- Created from checkout completion
- `status`: "unfulfilled" | "partiallyFulfilled" | "fulfilled" | "returned"
- `paymentStatus`: "authorized" | "captured" | "refunded" | "partiallyRefunded"
- `lines` — order line items with prices, tax, quantity
- `shippingPrice`, `subtotal`, `taxTotal`, `total`
- `fulfillments` — partial or full shipments
- `channelSlug`

### Fulfillments
- Belong to an order
- `lines` — which order lines (and quantities) are being shipped
- `trackingNumber`
- `warehouseId` — which warehouse ships this fulfillment
- Creating a fulfillment captures payment (proportional or full on final fulfillment)

### Returns / Refunds
- Staff can mark order lines as returned
- Triggers refund via payment gateway

## Business Rules

1. **Channel Isolation**: A checkout in channel "web-us" can only see products listed in "web-us" with their "web-us" prices.
2. **Stock Allocation**: When checkout completes, `allocatedQuantity` increases for the relevant warehouse. Available stock = `quantity - allocatedQuantity`. Overselling is prevented.
3. **Shipping Zone Matching**: Only shipping methods from zones covering the customer's country are available.
4. **Warehouse-Zone Link**: A fulfillment can only use a warehouse linked to a shipping zone that covers the order's shipping country.
5. **Voucher Validation**: Check channel, min order value, usage limit, product/category constraints, date range.
6. **Tax Calculation**: `taxAmount = lineTotal * taxRate` where taxRate comes from the product's tax class for the shipping country. If no matching rate, tax is 0.
7. **Payment Flow**: Authorize on checkout complete. Capture on fulfillment. Refund on return.
8. **Partial Fulfillment**: An order can have multiple fulfillments. Status becomes "partiallyFulfilled" until all lines are fulfilled.

## API Endpoints Summary

### Channels (staff only)
- POST /channels
- GET /channels
- GET /channels/{slug}
- PUT /channels/{slug}
- DELETE /channels/{slug}

### Warehouses (staff only)
- POST /warehouses
- GET /warehouses
- GET /warehouses/{id}
- PUT /warehouses/{id}
- DELETE /warehouses/{id}

### Product Types (staff only)
- POST /product-types
- GET /product-types
- GET /product-types/{id}
- PUT /product-types/{id}

### Categories (staff only for write, public for read)
- POST /categories
- GET /categories (supports `?parent=<id>` for tree traversal)
- GET /categories/{id}
- PUT /categories/{id}
- DELETE /categories/{id}

### Products (staff only for write, channel-scoped read)
- POST /products
- GET /products?channel=<slug> (filtered by channel listing)
- GET /products/{id}?channel=<slug>
- PUT /products/{id}
- DELETE /products/{id}
- POST /products/{id}/channel-listings
- POST /products/{id}/variants
- GET /products/{id}/variants?channel=<slug>
- PUT /products/{productId}/variants/{variantId}
- POST /products/{productId}/variants/{variantId}/stocks

### Collections (staff only for write, channel-scoped read)
- POST /collections
- GET /collections?channel=<slug>
- GET /collections/{id}?channel=<slug>
- PUT /collections/{id}
- POST /collections/{id}/products
- DELETE /collections/{id}/products/{productId}

### Shipping Zones (staff only)
- POST /shipping-zones
- GET /shipping-zones
- GET /shipping-zones/{id}
- PUT /shipping-zones/{id}
- POST /shipping-zones/{id}/methods
- PUT /shipping-zones/{zoneId}/methods/{methodId}
- DELETE /shipping-zones/{zoneId}/methods/{methodId}

### Tax Classes (staff only)
- POST /tax-classes
- GET /tax-classes
- GET /tax-classes/{id}
- PUT /tax-classes/{id}

### Vouchers (staff only)
- POST /vouchers
- GET /vouchers
- GET /vouchers/{id}
- PUT /vouchers/{id}
- DELETE /vouchers/{id}

### Customers
- POST /customers (self-registration or staff-created)
- GET /customers (staff only)
- GET /customers/{id}
- PUT /customers/{id}
- POST /customers/{id}/addresses
- PUT /customers/{id}/addresses/{addressId}
- DELETE /customers/{id}/addresses/{addressId}

### Checkout (customer or staff)
- POST /checkouts
- GET /checkouts/{id}
- POST /checkouts/{id}/lines
- PUT /checkouts/{id}/lines/{lineId}
- DELETE /checkouts/{id}/lines/{lineId}
- PUT /checkouts/{id}/shipping-address
- PUT /checkouts/{id}/billing-address
- GET /checkouts/{id}/shipping-methods
- PUT /checkouts/{id}/shipping-method
- POST /checkouts/{id}/voucher
- DELETE /checkouts/{id}/voucher
- POST /checkouts/{id}/complete

### Orders (staff for management, customer for own orders)
- GET /orders?channel=<slug>
- GET /orders/{id}
- POST /orders/{id}/fulfillments
- POST /orders/{id}/return

## Response Format

All responses use standard HTTP status codes:
- 200: Success
- 201: Created
- 400: Validation error (with `{"error": "description"}`)
- 401: Unauthorized
- 403: Forbidden (insufficient permissions)
- 404: Not found

List endpoints return: `{"data": [...], "totalCount": N}`
Single resource endpoints return the resource object directly.

## Field Naming

All JSON field names use **camelCase** (e.g., `channelSlug`, `taxClassId`, `shippingAddress`).
