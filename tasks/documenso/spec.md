# Documenso — Backend Implementation Spec

## Overview

Documenso is an **open-source document signing platform** (based on [Documenso](https://github.com/documenso/documenso), 12.7K stars). Users create documents, add recipients (signers/viewers/approvers), place signature fields, send documents for signing, and track completion. It supports templates for reusable document flows and API tokens for access management.

**Note**: This is a metadata-only implementation. No actual PDF/file handling — documents are represented as metadata (title, status) plus fields.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the user

Rules:
- The `X-Api-Key` header is required on all endpoints.
- If the header is missing or empty on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the user identifier. If a user with that key doesn't exist, **auto-create** the user (with the key as both their name and email). All subsequent requests with the same key authenticate as the same user.
- **Data scoping**: All documents, templates, and tokens are scoped to the authenticated user. A user can only see/modify their own data. Accessing another user's resource returns `404 Not Found`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Documents — CRUD + lifecycle management (7 endpoints)

Documents are the core entity. They go through a lifecycle: DRAFT → PENDING → COMPLETED/REJECTED.

- `POST /api/documents` — Create a document (body: `title`, optional `message`; status defaults to `DRAFT`)
- `GET /api/documents` — List all documents for the current user (supports `page`, `perPage`, `status` filter)
- `GET /api/documents/{id}` — Get a single document with its recipients and fields
- `PUT /api/documents/{id}` — Update a document (title, message; only when status is DRAFT)
- `DELETE /api/documents/{id}` — Delete a document (only when status is DRAFT)
- `POST /api/documents/{id}/send` — Send a document (transitions from DRAFT to PENDING)
- `POST /api/documents/{id}/cancel` — Cancel a pending document (transitions from PENDING back to DRAFT)

### 2. Recipients — manage document recipients (4 endpoints)

Recipients are people who need to act on a document (sign, view, approve).

- `POST /api/documents/{id}/recipients` — Add a recipient (body: `email`, `name`, `role`, optional `signingOrder`)
- `GET /api/documents/{id}/recipients` — List recipients for a document
- `PUT /api/documents/{documentId}/recipients/{recipientId}` — Update a recipient (only when document is DRAFT)
- `DELETE /api/documents/{documentId}/recipients/{recipientId}` — Remove a recipient (only when document is DRAFT)

### 3. Fields — manage signature fields (4 endpoints)

Fields are placed on documents and assigned to recipients.

- `POST /api/documents/{id}/fields` — Add a field (body: `type`, `recipientId`, `page`, `positionX`, `positionY`, `width`, `height`)
- `GET /api/documents/{id}/fields` — List all fields for a document
- `PUT /api/documents/{documentId}/fields/{fieldId}` — Update a field (only when document is DRAFT)
- `DELETE /api/documents/{documentId}/fields/{fieldId}` — Remove a field (only when document is DRAFT)

### 4. Signing — recipients complete their fields (3 endpoints)

The signing flow allows recipients to sign individual fields and mark themselves as done.

- `POST /api/documents/{documentId}/signing/{recipientId}/fields/{fieldId}` — Sign/complete a specific field (body: `value`)
- `POST /api/documents/{documentId}/signing/{recipientId}/complete` — Mark a recipient as completed (all their required fields must be signed first)
- `POST /api/documents/{documentId}/signing/{recipientId}/reject` — Reject signing (sets recipient status to REJECTED, document status to REJECTED)

### 5. Templates — reusable document templates (10 endpoints)

Templates allow creating pre-configured document flows.

- `POST /api/templates` — Create a template (body: `title`, optional `message`)
- `GET /api/templates` — List all templates for the current user
- `GET /api/templates/{id}` — Get a single template with its recipients and fields
- `PUT /api/templates/{id}` — Update a template
- `DELETE /api/templates/{id}` — Delete a template
- `POST /api/templates/{id}/use` — Create a document from a template (copies recipients and fields)
- `POST /api/templates/{id}/recipients` — Add a recipient to a template
- `DELETE /api/templates/{templateId}/recipients/{recipientId}` — Remove a template recipient
- `POST /api/templates/{id}/fields` — Add a field to a template
- `DELETE /api/templates/{templateId}/fields/{fieldId}` — Remove a template field

### 6. API Tokens — manage API access tokens (3 endpoints)

- `POST /api/tokens` — Create an API token (body: `name`, optional `expiresAt`)
- `GET /api/tokens` — List all tokens for the current user
- `DELETE /api/tokens/{id}` — Delete/revoke a token

### 7. User Profile (1 endpoint)

- `GET /api/me` — Get the current user's profile

---

**Totals: 32 endpoints across 7 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users**: When a request comes in with `X-Api-Key: somevalue`, if no user with that key exists, automatically create a user with that key as both their name and email. All subsequent requests with the same key authenticate as the same user.

2. **Document lifecycle**:
   - New documents start as `DRAFT`.
   - `POST /api/documents/{id}/send` transitions a document from `DRAFT` to `PENDING`. Returns `400` if document is not in `DRAFT` status. Also returns `400` if document has no recipients with role `SIGNER` or `APPROVER`, or has no fields.
   - `POST /api/documents/{id}/cancel` transitions a document from `PENDING` back to `DRAFT`. Returns `400` if not in `PENDING` status. When cancelled, all recipient statuses reset to `PENDING`.
   - Document becomes `COMPLETED` when ALL recipients with role `SIGNER` or `APPROVER` have status `COMPLETED`.
   - Document becomes `REJECTED` if ANY signer/approver rejects.

3. **Immutable after send**: Once a document is sent (status = `PENDING`, `COMPLETED`, or `REJECTED`):
   - Cannot add/update/delete recipients (return `400`)
   - Cannot add/update/delete fields (return `400`)
   - Cannot update document title/message (return `400`)
   - Cannot delete the document (return `400`)
   - Exception: cancelling moves it back to DRAFT, re-enabling edits.

4. **Recipient roles**:
   - `SIGNER` — must sign all assigned required fields to complete
   - `VIEWER` — no action required; viewers are automatically set to `COMPLETED` status when document is sent
   - `APPROVER` — must explicitly complete (like a signer but without signing fields)

5. **Recipient statuses**: `PENDING`, `COMPLETED`, `REJECTED`
   - Start as `PENDING` when document is sent (except VIEWERs which become `COMPLETED`)
   - Move to `COMPLETED` when they complete signing/approving
   - Move to `REJECTED` if they reject

6. **Signing order enforcement**: If recipients have `signingOrder` set (values > 0), a recipient can only sign/complete/reject if all recipients with a LOWER `signingOrder` value already have status `COMPLETED`. Return `400` if order is violated. Recipients with the SAME `signingOrder` can act in parallel. If `signingOrder` is 0 or null for all recipients, no ordering is enforced (all can sign in parallel).

7. **Field signing rules**:
   - A recipient can only sign fields assigned to them (return `403` for others' fields)
   - A field can only be signed once (return `400` if already signed/has a value)
   - The document must be in `PENDING` status to sign (return `400` otherwise)
   - Signing a field stores the `value` and sets `signedAt` timestamp on the field

8. **Recipient completion rules**:
   - Calling `complete` requires ALL required fields assigned to this recipient to have a value (return `400` if any required field is unsigned)
   - VIEWER recipients cannot be manually completed (they are auto-completed on send) — return `400`
   - After a recipient completes, check if ALL signers/approvers are done → if yes, set document status to `COMPLETED`
   - A recipient that already has status `COMPLETED` cannot complete again (return `400`)

9. **Rejection**:
   - Any SIGNER or APPROVER can reject while document is `PENDING`
   - Rejecting sets that recipient's status to `REJECTED` and the document's status to `REJECTED`
   - A VIEWER cannot reject (return `400`)
   - Cannot reject if document is not `PENDING` (return `400`)
   - Once rejected, no further signing/completion is possible on that document (return `400`)

10. **Templates**:
    - Templates have their own recipients and fields (separate from documents)
    - Template fields reference template recipients (not document recipients)
    - `POST /api/templates/{id}/use` creates a new document in `DRAFT` status, copying: title, message, all template recipients (as document recipients), and all template fields (as document fields linked to the new document recipients)
    - The field `recipientId` on copied fields points to the newly created document recipient (matched by position/order)

11. **API Tokens**:
    - Tokens are simple named metadata records belonging to the user
    - Each token has: `id`, `name`, generated `token` value (random string, at least 20 chars), `createdAt`, and optional `expiresAt`
    - The actual authentication is via the `X-Api-Key` header — these token records are just for management/display

12. **Pagination**: List endpoints (`GET /api/documents`, `GET /api/templates`) support `page` (1-based, default 1) and `perPage` (default 20, max 100). Response includes a `pagination` object with `page`, `perPage`, `totalPages`, `totalItems`.

13. **Data isolation**: Users can only access their own documents, templates, and tokens. Accessing another user's resource returns `404`.

14. **Cascade deletes**:
    - Deleting a document deletes all its recipients and fields
    - Deleting a template deletes all its template recipients and template fields
