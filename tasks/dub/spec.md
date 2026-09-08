# Dub — Modern Link Management Platform

## Overview

Dub is a modern link management platform with analytics. It allows teams to create short links, track clicks with rich analytics, organize links with tags and folders, and manage custom domains — all within isolated workspaces with role-based access control.

## Authentication & Authorization

- **Authentication**: All API requests require an `X-API-Key` header.
  - Missing or invalid key returns `401 Unauthorized`.
- **API Key Format**: `{role}_{workspaceId}_{userId}` (e.g., `admin_ws1_user1`)
  - The key encodes the user's role, workspace, and identity.
- **Workspace Isolation**: All data is scoped to the workspace derived from the API key. Users cannot access data from other workspaces.
- **Roles**:
  - **owner**: Full access — manage workspace settings, members, and all resources.
  - **admin**: Manage all links, tags, domains, and folders in the workspace.
  - **member**: Create and manage their own links, view analytics for their own links.

## Core Resources

### Links

Short links that redirect to a destination URL. Each link belongs to a workspace and optionally a domain and folder.

**Fields:**
- `id` (string, auto-generated UUID)
- `domain` (string, default: workspace default domain or "dub.sh")
- `slug` (string, unique within domain; auto-generated 7-char alphanumeric if not provided)
- `url` (string, required — destination URL)
- `title` (string, optional)
- `description` (string, optional)
- `tags` (array of tag IDs, optional)
- `folderId` (string, optional)
- `expiresAt` (ISO datetime, optional — link expires after this time)
- `password` (string, optional — password-protect the link)
- `ios` (string, optional — iOS-specific redirect URL)
- `android` (string, optional — Android-specific redirect URL)
- `ogTitle` (string, optional — Open Graph title override)
- `ogDescription` (string, optional — Open Graph description override)
- `ogImage` (string, optional — Open Graph image URL override)
- `archived` (boolean, default false)
- `createdAt` (ISO datetime)
- `updatedAt` (ISO datetime)
- `userId` (string — creator)
- `clicks` (integer — total click count)

**Business Rules:**
- Slug must be unique within a domain. If slug is already taken, return 409 Conflict.
- If no slug provided, auto-generate a random 7-character alphanumeric string.
- Members can only update/delete their own links. Admins/owners can manage all links.

### Domains

Custom domains for short links (e.g., `myco.link`).

**Fields:**
- `id` (string, auto-generated UUID)
- `slug` (string — the domain name, e.g., "myco.link")
- `verified` (boolean, default false)
- `primary` (boolean, default false — workspace default domain)
- `createdAt` (ISO datetime)

**Business Rules:**
- Only admins/owners can manage domains.
- Domain slug must be unique within the workspace.
- Only one domain can be primary per workspace.

### Tags

Colored labels to organize links.

**Fields:**
- `id` (string, auto-generated UUID)
- `name` (string, unique within workspace)
- `color` (string — hex color code, e.g., "#FF0000")
- `createdAt` (ISO datetime)

**Business Rules:**
- Tag name must be unique within a workspace.
- Only admins/owners can create/update/delete tags. Members can use tags on their own links.

### Folders

Hierarchical folders to organize links.

**Fields:**
- `id` (string, auto-generated UUID)
- `name` (string)
- `parentId` (string, optional — parent folder ID for nesting)
- `createdAt` (ISO datetime)

**Business Rules:**
- Only admins/owners can manage folders. Members can place their links in folders.
- Folder names must be unique within the same parent (or at root level).

### Workspaces

A workspace represents a team or project.

**Fields:**
- `id` (string)
- `name` (string)
- `slug` (string, unique)
- `createdAt` (ISO datetime)

### Members

Users within a workspace.

**Fields:**
- `userId` (string)
- `role` (string: "owner", "admin", "member")
- `email` (string)
- `name` (string)
- `createdAt` (ISO datetime)

**Business Rules:**
- Only owners can manage members (invite, update role, remove).
- A workspace must always have at least one owner.

## Link Redirect & Click Tracking

**Redirect Endpoint:** `GET /r/{slug}` (uses default domain) or `GET /r/{domain}/{slug}`

**Behavior:**
1. Look up the link by slug (and domain if provided).
2. If link not found → 404.
3. If link is expired (`expiresAt` < now) → 410 Gone.
4. If link has a password:
   - Check `password` query parameter.
   - If missing or incorrect → 401 Unauthorized.
5. Device-specific redirects:
   - If User-Agent contains "iPhone" or "iPad" or "iOS" and `ios` URL is set → redirect to `ios` URL.
   - If User-Agent contains "Android" and `android` URL is set → redirect to `android` URL.
   - Otherwise → redirect to main `url`.
6. Record a click event with metadata (timestamp, country from header, device, browser, referer, OS).
7. Return 302 redirect to the target URL.

**Click Event Fields:**
- `id` (string, auto-generated)
- `linkId` (string)
- `timestamp` (ISO datetime)
- `country` (string, from `X-Forwarded-Country` header or "Unknown")
- `device` (string: "Mobile", "Desktop", "Tablet", "Unknown")
- `browser` (string: parsed from User-Agent)
- `os` (string: parsed from User-Agent)
- `referer` (string, from `Referer` header or "Direct")
- `ip` (string, hashed IP)

## Analytics

Analytics endpoints aggregate click data for links.

**Available Aggregations:**
- **Timeseries**: clicks over time (grouped by hour/day/week/month)
- **Countries**: clicks by country
- **Devices**: clicks by device type
- **Browsers**: clicks by browser
- **OS**: clicks by operating system
- **Referers**: clicks by referer

**Filters:**
- `linkId` (optional — specific link, otherwise all workspace links)
- `domain` (optional)
- `tagId` (optional)
- `start` (ISO date)
- `end` (ISO date)
- `interval` (for timeseries: "1h", "24h", "7d", "30d", "90d")

## Bulk Operations

Bulk endpoints allow operating on multiple links at once.

**Business Rules:**
- Bulk operations are atomic: all succeed or all fail (transaction).
- If any item in the batch fails validation, the entire batch is rejected.
- Maximum batch size: 100 items.

## QR Codes

Generate a QR code for any link.

**Endpoint:** `GET /links/{linkId}/qr`

**Parameters:**
- `size` (integer, default 256 — pixel size)
- `format` (string: "svg" or "png", default "svg")

**Response:** Returns the QR code image data with appropriate content type.

## API Endpoints Summary

### Links (8 endpoints)
- `POST /links` — Create a link
- `GET /links` — List links (with filters: domain, tagId, folderId, search, archived)
- `GET /links/{linkId}` — Get a link
- `PUT /links/{linkId}` — Update a link
- `DELETE /links/{linkId}` — Delete a link
- `GET /links/{linkId}/qr` — Get QR code for link
- `GET /links/count` — Get link count (with same filters as list)
- `GET /links/info` — Get link by domain+slug combo (query params)

### Bulk Operations (3 endpoints)
- `POST /links/bulk` — Bulk create links
- `PATCH /links/bulk` — Bulk update links
- `DELETE /links/bulk` — Bulk delete links

### Redirect (2 endpoints)
- `GET /r/{slug}` — Redirect short link (default domain)
- `GET /r/{domain}/{slug}` — Redirect short link (custom domain)

### Analytics (6 endpoints)
- `GET /analytics/timeseries` — Clicks over time
- `GET /analytics/countries` — Clicks by country
- `GET /analytics/devices` — Clicks by device
- `GET /analytics/browsers` — Clicks by browser
- `GET /analytics/os` — Clicks by OS
- `GET /analytics/referers` — Clicks by referer

### Events (1 endpoint)
- `GET /events` — Raw click events log (paginated)

### Domains (5 endpoints)
- `POST /domains` — Create a domain
- `GET /domains` — List domains
- `GET /domains/{domainId}` — Get a domain
- `PATCH /domains/{domainId}` — Update a domain
- `DELETE /domains/{domainId}` — Delete a domain

### Tags (5 endpoints)
- `POST /tags` — Create a tag
- `GET /tags` — List tags
- `GET /tags/{tagId}` — Get a tag
- `PATCH /tags/{tagId}` — Update a tag
- `DELETE /tags/{tagId}` — Delete a tag

### Folders (5 endpoints)
- `POST /folders` — Create a folder
- `GET /folders` — List folders
- `GET /folders/{folderId}` — Get a folder
- `PATCH /folders/{folderId}` — Update a folder
- `DELETE /folders/{folderId}` — Delete a folder

### Workspaces (3 endpoints)
- `GET /workspaces` — Get current workspace info
- `PATCH /workspaces` — Update workspace settings
- `GET /workspaces/members` — List workspace members

### Members (3 endpoints)
- `POST /workspaces/members` — Invite a member
- `PATCH /workspaces/members/{userId}` — Update member role
- `DELETE /workspaces/members/{userId}` — Remove a member

**Total: 41 endpoints**

## Error Responses

All errors follow a consistent format:
```json
{
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

Common error codes:
- `unauthorized` (401) — Missing or invalid API key
- `forbidden` (403) — Insufficient permissions
- `not_found` (404) — Resource not found
- `conflict` (409) — Resource already exists (duplicate slug, name, etc.)
- `gone` (410) — Link has expired
- `unprocessable_entity` (422) — Validation error
- `bad_request` (400) — Invalid request format
