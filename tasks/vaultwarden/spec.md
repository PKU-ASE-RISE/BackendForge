# Vaultwarden — Bitwarden-Compatible Password Vault Server

## Overview

Vaultwarden is a lightweight, Bitwarden-compatible password vault server. It provides a REST API for managing encrypted vault items (ciphers), organized into folders and collections, with support for organizations, temporary sharing (Sends), two-factor authentication, and more.

## Core Concepts

### Authentication
- Users register with email and master password
- Login returns a Bearer access token
- All protected endpoints require `Authorization: Bearer {token}` header
- Invalid or missing token returns 401 Unauthorized

### Encryption Model (Simplified)
- In this simplified implementation, "encrypted" data is base64-encoded
- The server stores cipher data as-is (base64 strings) — no server-side encryption/decryption
- Clients are responsible for encoding/decoding

### Data Model

**User Account**: email, name, masterPasswordHash (bcrypt), optional TOTP secret for 2FA

**Cipher** (vault item): The core entity. Has a `type` field:
- Type 1 — Login: uri, username, password
- Type 2 — Secure Note: text content in notes field
- Type 3 — Card: cardholderName, brand, number, expMonth, expYear, code
- Type 4 — Identity: firstName, lastName, address1, city, state, postalCode, country, email, phone

Each cipher can belong to a folder, an organization, and/or collections.

**Folder**: Simple named container for organizing ciphers (per-user).

**Organization**: A group entity. Users are members with roles: owner (0), admin (1), manager (2), member (3).

**Collection**: Named grouping within an organization. Ciphers assigned to collections are visible to all org members with access.

**Send**: Temporary sharing mechanism. Contains text or file data with:
- Optional password protection
- Optional expiration date
- Optional max access count
- Access via public endpoint (no auth required for accessing)

## API Endpoints

### Accounts (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/accounts/register | Register new account |
| POST | /identity/connect/token | Login (get access token) |
| GET | /api/accounts/profile | Get current user profile |
| PUT | /api/accounts/profile | Update profile |
| POST | /api/accounts/password | Change master password |
| DELETE | /api/accounts | Delete account |

### Ciphers (10 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/ciphers | List all ciphers |
| POST | /api/ciphers | Create cipher |
| GET | /api/ciphers/{id} | Get cipher by ID |
| PUT | /api/ciphers/{id} | Update cipher |
| DELETE | /api/ciphers/{id} | Delete cipher |
| PUT | /api/ciphers/{id}/favorite | Toggle favorite |
| GET | /api/ciphers/{id}/history | Get password history |
| POST | /api/ciphers/{id}/attachment | Upload attachment |
| GET | /api/ciphers/{id}/attachment/{attachmentId} | Download attachment |
| DELETE | /api/ciphers/{id}/attachment/{attachmentId} | Delete attachment |

### Folders (4 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/folders | List folders |
| POST | /api/folders | Create folder |
| PUT | /api/folders/{id} | Rename folder |
| DELETE | /api/folders/{id} | Delete folder |

### Organizations (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/organizations | Create organization |
| GET | /api/organizations/{id} | Get organization |
| GET | /api/organizations/{id}/members | List members |
| POST | /api/organizations/{id}/members/invite | Invite member |
| POST | /api/organizations/{id}/members/{memberId}/confirm | Confirm member |
| DELETE | /api/organizations/{id}/members/{memberId} | Remove member |

### Collections (5 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/organizations/{orgId}/collections | List collections |
| POST | /api/organizations/{orgId}/collections | Create collection |
| GET | /api/organizations/{orgId}/collections/{id} | Get collection |
| PUT | /api/organizations/{orgId}/collections/{id} | Update collection |
| DELETE | /api/organizations/{orgId}/collections/{id} | Delete collection |

### Sends (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/sends | List user's sends |
| POST | /api/sends | Create send |
| GET | /api/sends/{id} | Get send details |
| PUT | /api/sends/{id} | Update send |
| DELETE | /api/sends/{id} | Delete send |
| POST | /api/sends/{sendId}/access | Access send content (public) |

### Two-Factor Authentication (5 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/two-factor | Get 2FA status |
| POST | /api/two-factor/setup | Generate TOTP secret |
| POST | /api/two-factor/enable | Enable 2FA with verification code |
| POST | /api/two-factor/disable | Disable 2FA |
| GET | /api/two-factor/recovery | Get recovery codes |

### Password Generator (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/generator/password | Generate password |

### Sync (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/sync | Full vault sync |

**Total: 44 endpoints**

## Business Logic

### Registration & Login
- Master password is hashed with bcrypt before storage
- Login validates email + bcrypt hash comparison
- Successful login returns `{ accessToken, tokenType: "Bearer", expiresIn: 3600 }`
- If 2FA is enabled, first login attempt returns `{ twoFactorRequired: true, twoFactorProviders: [0] }`
- Second login call must include `twoFactorToken` field with valid TOTP code

### Cipher Operations
- Cipher type determines which fields in the type-specific data are required
- Creating/updating a cipher with an organization ID makes it an org cipher
- Password history: when a login cipher's password field changes on update, the old password is pushed to the cipher's passwordHistory array (max 5 entries, FIFO)
- Favorites are per-user (toggled via PUT /api/ciphers/{id}/favorite)

### Organizations & Collections
- Creator becomes owner (role 0)
- Roles: owner(0) > admin(1) > manager(2) > member(3)
- Only owner/admin can invite new members
- Invited members must be confirmed before gaining access
- Manager+ can create/manage collections
- Ciphers assigned to a collection are visible to all confirmed org members

### Sends
- Each send has a unique accessId (UUID) used in the access URL
- Send types: text (0) or file (1)
- If `password` is set on send, the access endpoint requires matching password
- If `expirationDate` is set and current time > expiration, access returns 404
- If `maxAccessCount` is set and `accessCount >= maxAccessCount`, access returns 404
- Each successful access increments `accessCount`

### Two-Factor Authentication
- Setup returns a TOTP secret (base32 encoded)
- Enable requires a valid TOTP token generated from that secret
- Once enabled, login flow requires TOTP verification
- Recovery codes: generated when 2FA is enabled, can be used as alternative to TOTP

### Password Generator
- Parameters: length (default 14), uppercase (bool), lowercase (bool), numbers (bool), special (bool)
- Returns a randomly generated password matching the criteria
- At least one character type must be enabled

### Sync
- Returns all user data: ciphers, folders, collections, organizations
- Accepts optional `?since=ISO_TIMESTAMP` query parameter
- When `since` is provided, only returns items with `revisionDate` after that timestamp
