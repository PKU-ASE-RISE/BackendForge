# Zulip — Topic-Based Team Chat API

## Overview

Zulip is a topic-based team chat application. Unlike flat-channel chat tools, Zulip organizes conversations within **streams** (channels) into **topics** (threads). This makes it easy to follow multiple conversations in a busy stream without losing context.

## Core Concepts

### Users
- Users register with email, full name, and password
- Each user has a role: `owner`, `admin`, `moderator`, `member`, or `guest`
- Default role for new users is `member`
- Users have presence status: `online`, `idle`, or `offline`

### Streams
- Streams are the top-level channels for organizing conversations
- Streams can be `public` (anyone can join) or `private` (invite-only)
- Each stream has a name, description, and list of subscribers
- Private streams are invisible to non-subscribers (not returned in list endpoints)

### Topics
- Topics are threads within a stream
- Topics are created implicitly when the first message is sent to a new topic name in a stream
- A topic belongs to exactly one stream

### Messages
- Messages belong to either a stream+topic (stream messages) or a direct-message conversation
- Messages support plain text content
- Messages can be edited (with edit history preserved)
- Messages can be deleted
- Messages support emoji reactions

### Direct Messages
- Direct messages are conversations between 2 or more users
- A DM conversation is identified by the set of participant user IDs

### Subscriptions
- Users subscribe to streams to receive messages
- Users can mute specific topics within streams they're subscribed to

### Presence
- Tracks whether users are online, idle, or offline
- Includes a timestamp of last activity

### Drafts
- Users can save unsent message drafts
- Drafts store the intended stream/topic or DM recipients and content

### Read Markers
- The system tracks which messages each user has read
- When a new message is posted, it's automatically unread for all subscribers except the sender
- Users can mark messages as read at the stream level (all topics) or topic level

### User Groups
- Named groups of users for organizational purposes
- Groups have a name and description

### Starred Messages
- Users can star/unstar messages for quick access later

## Authentication

All API requests require two headers:
- `X-API-Key`: A valid API key (any non-empty string is accepted)
- `X-User-Email`: The email of the authenticated user (must correspond to a registered user)

Missing or invalid headers return `401 Unauthorized`.

## Role Hierarchy & Permissions

**Owner** > **Admin** > **Moderator** > **Member** > **Guest**

| Action | Minimum Role |
|--------|-------------|
| Access subscribed streams | guest |
| Send messages to subscribed streams | guest |
| Access public streams | member |
| Create streams | member |
| Subscribe to public streams | member |
| Delete own messages | member |
| Delete others' messages | moderator |
| Manage all streams (edit/delete) | admin |
| Deactivate users | admin |
| Change user roles | owner |

Guests can only access streams they have been explicitly subscribed to.

## Business Logic

### Topic Auto-Creation
When a message is sent to a stream with a topic name that doesn't yet exist, the topic is created automatically. There is no separate "create topic" endpoint.

### Unread Tracking
- When a message is posted to a stream+topic, it becomes unread for all subscribers of that stream except the sender.
- When a DM is sent, it becomes unread for all other participants.

### Read Markers
- Marking a stream as read marks all topics in that stream as read (up to the latest message).
- Marking a specific topic as read only marks messages in that topic as read.
- "Mark all as read" marks everything as read.

### Message Filtering (Narrow)
Messages can be filtered by:
- `streamId`: messages in a specific stream
- `topic`: messages with a specific topic name (requires streamId)
- `senderId`: messages from a specific user
- `keyword`: search message content (case-insensitive substring match)

### Message Editing
- When a message is edited, the previous content and edit timestamp are saved in the edit history.
- Edit history is accessible via a separate endpoint.

### Reactions
- Users can add emoji reactions to messages.
- Each user can only add each emoji once per message (no duplicates).
- Removing a non-existent reaction is idempotent (returns success).

## API Design

- All responses use JSON
- All field names use camelCase
- Successful creation returns `201 Created`
- Successful updates return `200 OK`
- Successful deletions return `204 No Content`
- Not found returns `404 Not Found`
- Permission denied returns `403 Forbidden`
- Validation errors return `400 Bad Request`
- All list endpoints return arrays (no pagination required for this spec)

## Storage

- Storage starts empty — no seed data
- All data is stored in-memory (no database required)
- IDs are auto-generated integers starting from 1
