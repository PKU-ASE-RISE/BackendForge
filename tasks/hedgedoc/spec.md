# HedgeDoc — Collaborative Markdown Editor API

## Overview

HedgeDoc is a collaborative markdown editing platform that allows users to create, share, and collaboratively edit markdown notes in real-time. This specification describes a RESTful API for managing notes, permissions, revisions, users, groups, media, aliases, history, and tags.

## Authentication

All endpoints require authentication via the `X-API-Key` header. Each API key corresponds to a registered user. Requests without a valid `X-API-Key` header receive a `401 Unauthorized` response.

## Core Concepts

### Notes
A note is a markdown document with:
- **id**: unique identifier (server-generated UUID)
- **content**: markdown text body
- **title**: automatically extracted from the first H1 heading (`# Title`) in the content, or "Untitled" if no H1 is found
- **owner**: the user who created the note
- **permission**: visibility level — `private`, `limited`, or `public`
- **tags**: list of string tags
- **createdAt** / **updatedAt**: ISO 8601 timestamps

### Permissions Model
- **Private**: only the owner can read or write
- **Limited**: owner has full access; specific users or groups can be granted `read` or `write` access explicitly
- **Public**: any authenticated user can read; only the owner and users/groups with explicit `write` permission can edit

Permission checks are enforced on every note access (read or write).

### Aliases
Each note has one or more aliases (URL-friendly slugs). One alias is marked as the **primary** alias. Aliases are globally unique across all notes. A note can be accessed by any of its aliases.

### Revisions
Every time a note's content is updated (via PUT), a new revision is automatically created. Each revision stores:
- **id**: unique revision identifier
- **content**: the full note content at that point
- **title**: title at that point
- **createdAt**: timestamp of the revision
- **authorId**: the user who made the edit

### Users
Users register with a username and display name. Each user has:
- **id**: unique identifier
- **username**: unique login name
- **displayName**: human-readable name
- **photoUrl**: optional avatar URL
- **createdAt**: registration timestamp

### Groups
Users can create groups and add members. Groups can be granted permissions on notes, which apply to all members of the group.
- **id**: unique identifier
- **name**: group name (unique)
- **displayName**: human-readable name
- **members**: list of user IDs
- **ownerId**: the user who created the group

### Media
Users can upload files (images) that are linked to a specific note:
- **id**: unique identifier
- **noteId**: the note this media is associated with
- **fileName**: original file name
- **createdAt**: upload timestamp
- **userId**: uploader
- **url**: URL to access the media (server-generated)

### History
Each user has a personal history of notes they have accessed. When a user reads (GET) a note, it is automatically added to or updated in their history. Users can pin notes in their history.

### Tags
Notes can have tags (string labels). The API supports listing all unique tags across all accessible notes and filtering notes by tag.

## API Endpoints

### Users (4 endpoints)
- `POST /api/v2/users` — Register a new user
- `GET /api/v2/users/{userId}` — Get user profile
- `PUT /api/v2/users/{userId}` — Update user profile (display name, photo URL)
- `DELETE /api/v2/users/{userId}` — Delete user account

### Notes (6 endpoints)
- `POST /api/v2/notes` — Create a new note (with initial content, optional alias)
- `GET /api/v2/notes/{noteIdOrAlias}` — Get a note by ID or alias (triggers history update)
- `PUT /api/v2/notes/{noteIdOrAlias}` — Update note content (creates revision)
- `DELETE /api/v2/notes/{noteIdOrAlias}` — Delete a note (owner only)
- `GET /api/v2/notes` — List all notes accessible to the current user
- `PATCH /api/v2/notes/{noteIdOrAlias}` — Update note metadata (tags, permission level)

### Aliases (4 endpoints)
- `POST /api/v2/notes/{noteIdOrAlias}/aliases` — Add an alias to a note
- `GET /api/v2/notes/{noteIdOrAlias}/aliases` — List aliases for a note
- `PUT /api/v2/aliases/{alias}` — Update alias (set as primary)
- `DELETE /api/v2/aliases/{alias}` — Remove an alias from a note

### Revisions (3 endpoints)
- `GET /api/v2/notes/{noteIdOrAlias}/revisions` — List all revisions of a note
- `GET /api/v2/notes/{noteIdOrAlias}/revisions/{revisionId}` — Get a specific revision
- `GET /api/v2/notes/{noteIdOrAlias}/revisions/{revisionId}/diff` — Get diff between a revision and its predecessor

### Permissions (5 endpoints)
- `GET /api/v2/notes/{noteIdOrAlias}/permissions` — Get permission settings for a note
- `PUT /api/v2/notes/{noteIdOrAlias}/permissions` — Set overall permission level (private/limited/public)
- `POST /api/v2/notes/{noteIdOrAlias}/permissions/users` — Grant a user permission on a note
- `DELETE /api/v2/notes/{noteIdOrAlias}/permissions/users/{userId}` — Revoke a user's permission
- `POST /api/v2/notes/{noteIdOrAlias}/permissions/groups` — Grant a group permission on a note
- `DELETE /api/v2/notes/{noteIdOrAlias}/permissions/groups/{groupId}` — Revoke a group's permission

### Groups (6 endpoints)
- `POST /api/v2/groups` — Create a group
- `GET /api/v2/groups` — List groups the user belongs to
- `GET /api/v2/groups/{groupId}` — Get group details
- `PUT /api/v2/groups/{groupId}` — Update group (display name)
- `DELETE /api/v2/groups/{groupId}` — Delete group (owner only)
- `POST /api/v2/groups/{groupId}/members` — Add a member to a group
- `DELETE /api/v2/groups/{groupId}/members/{userId}` — Remove a member from a group

### Media (3 endpoints)
- `POST /api/v2/notes/{noteIdOrAlias}/media` — Upload media linked to a note
- `GET /api/v2/notes/{noteIdOrAlias}/media` — List media for a note
- `DELETE /api/v2/media/{mediaId}` — Delete a media file

### History (4 endpoints)
- `GET /api/v2/me/history` — Get current user's note history
- `PUT /api/v2/me/history/{noteId}` — Update history entry (pin/unpin)
- `DELETE /api/v2/me/history/{noteId}` — Remove a note from history
- `DELETE /api/v2/me/history` — Clear entire history

### Tags (2 endpoints)
- `GET /api/v2/tags` — List all unique tags from accessible notes
- `GET /api/v2/notes?tag={tag}` — Filter notes by tag (query parameter on list notes)

### Import/Export (2 endpoints)
- `POST /api/v2/notes/import` — Import a note from markdown content
- `GET /api/v2/notes/{noteIdOrAlias}/export/markdown` — Export note as raw markdown

## Business Logic Rules

1. **Title Extraction**: The title of a note is derived from the first line of content that starts with `# `. If no such line exists, the title defaults to `"Untitled"`.

2. **Automatic Revision Creation**: Every successful `PUT` to a note's content creates a new revision entry with the previous content state.

3. **Alias Uniqueness**: No two notes can share the same alias. Attempting to create a duplicate alias returns `409 Conflict`.

4. **Primary Alias**: Every note has exactly one primary alias. When a new alias is set as primary, the previous primary alias becomes non-primary.

5. **Permission Inheritance**: If a group is granted `write` permission on a note, all members of that group can write to the note. Same for `read`.

6. **History Auto-Update**: When a user performs a GET on a note, the note is automatically added to (or its timestamp updated in) the user's history.

7. **Owner Privileges**: The note owner always has full read/write access regardless of the permission level setting.

8. **Cascade Deletion**: Deleting a note removes all associated aliases, revisions, media, permissions, and history entries.

## Error Responses

- `400 Bad Request` — Invalid input (missing required fields, malformed data)
- `401 Unauthorized` — Missing or invalid API key
- `403 Forbidden` — User lacks permission for the requested operation
- `404 Not Found` — Resource does not exist
- `409 Conflict` — Alias already exists, username already taken, etc.
