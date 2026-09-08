# Zitadel — Identity and Access Management Platform

## Overview

Zitadel is a multi-tenant identity and access management (IAM) platform that provides authentication, authorization, and user management capabilities. It supports organizations as isolated tenants, human and machine users, project-based role management, configurable security policies, and audit logging.

## Core Concepts

### Organizations
Organizations are the top-level tenant boundary. Each organization has its own users, projects, policies, and audit trail. Users in one organization cannot access resources in another organization.

### Users
Two types of users exist:
- **Human users**: authenticate with email + password, have profiles (firstName, lastName, displayName)
- **Machine users**: used for API access, authenticate via Personal Access Tokens

Users can be in states: `active`, `inactive`, `locked`.

### Authentication
Human users authenticate via email + password. Successful login returns a session token that encodes the userId and orgId. This token is used for subsequent API requests.

If the organization's login policy requires MFA, the initial login returns a partial session with `mfaRequired: true`. A second call with a TOTP code completes authentication.

### Sessions
Each successful login creates a session. Users can list their active sessions and revoke them.

### Projects
Projects represent applications or services that use authentication. Each project belongs to an organization and defines its own set of roles.

### Roles
Roles are defined within a project (e.g., "admin", "viewer", "editor"). They have a key (unique within project), display name, and optional group.

### Grants
Grants assign roles to users within a project. A grant says "user X has role Y in project Z."

### Policies
Organizations configure security policies:
- **Password Policy**: minLength, requireUppercase, requireLowercase, requireNumber, requireSymbol
- **Login Policy**: mfaRequired, allowUsernamePassword, sessionLifetime (seconds)
- **Lockout Policy**: maxAttempts (failed logins before lock), lockoutDuration (seconds, 0 = permanent until admin unlock)

### Actions (Hooks)
Actions are custom logic triggers on events. Each action has a name, event type (e.g., "pre.login", "post.login", "pre.registration", "post.registration"), a script (JavaScript-like string), and enabled/disabled state.

### Personal Access Tokens (PAT)
Users can generate API tokens with specific scopes and expiration dates. PATs can be used as Bearer tokens for API access.

### Audit Events
All significant actions are logged: login success/failure, user created/updated/deleted, role granted/revoked, policy changed, etc.

### OIDC/OAuth Metadata
Simplified well-known endpoints for OIDC discovery and JWKS.

## Authorization Model

All management API endpoints require `Authorization: Bearer {token}` header.

- **System admin**: the special token `"system_admin"` has unrestricted access to all endpoints
- **Org owners**: the first user created in an org (or users with orgOwner grant) can manage all resources within their org
- **Regular users**: can only manage their own profile, sessions, and PATs

Missing or invalid token returns 401. Accessing resources outside your org returns 403.

## API Design

- All request/response bodies use JSON with camelCase field names
- List endpoints support `offset` and `limit` query parameters (default limit=20)
- Successful creation returns 201 with the created resource
- Successful update returns 200 with the updated resource
- Successful deletion returns 204
- Validation errors return 400 with `{"error": "description"}`
- Not found returns 404 with `{"error": "not found"}`
- IDs are server-generated UUIDs

## Business Logic Details

### Password Policy Enforcement
When creating a human user, the password is validated against the organization's password policy. Default policy (if none set): minLength=8, no other requirements.

### Login Lockout
Each failed login increments a counter. When it reaches the lockout policy's maxAttempts, the user is locked. Default lockout policy: maxAttempts=5. A locked user cannot login until unlocked by an admin.

### Session Tokens
Login returns a token string. This token must be accepted on subsequent requests. The token encodes userId and orgId context.

### MFA Flow
If login policy has mfaRequired=true:
1. POST /auth/login returns 200 with `{"mfaRequired": true, "mfaToken": "..."}`
2. POST /auth/login/mfa with the mfaToken and a code (any 6-digit string is accepted in this simplified version) returns the full session token

### PAT Authentication
PATs can be used as Bearer tokens. An expired PAT returns 401. PATs have scopes: `["admin"]`, `["read"]`, or `["project:{projectId}"]`.

### Audit Event Types
- `user.created`, `user.updated`, `user.deactivated`, `user.reactivated`, `user.locked`, `user.unlocked`
- `session.created`, `session.revoked`
- `login.succeeded`, `login.failed`
- `role.created`, `role.deleted`
- `grant.created`, `grant.revoked`
- `policy.updated`
- `action.created`, `action.updated`, `action.deleted`
- `pat.created`, `pat.revoked`
