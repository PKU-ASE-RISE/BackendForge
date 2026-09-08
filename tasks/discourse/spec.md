# Discourse — Community Forum Platform

## Overview

Discourse is a community forum platform that supports structured discussions through categories, topics, and posts. It features a trust-level system that progressively grants users more permissions as they participate in the community.

## Core Concepts

### Categories
Categories organize topics into logical groups. Categories support:
- Hierarchical structure (parent/subcategories via `parentCategoryId`)
- Position ordering for display
- Color and text color for visual distinction
- Group-based permissions (which groups can see/create/reply)

### Topics
Topics are discussion threads within a category. They support:
- Title and category assignment
- Pinning (globally or within category)
- Closing (prevents new replies)
- Archiving (read-only preservation)
- Moving between categories
- View count tracking (incremented on GET)
- Tags for cross-cutting organization

### Posts
Posts are individual messages within a topic. The first post in a topic is the "original post" (OP). Posts support:
- Rich text content
- Quoting other posts (via `quotePostId`)
- Likes (one per user per post)
- Bookmarking
- Editing (with revision tracking)
- Soft deletion

### Users
Users have profiles with trust levels (0-4) that determine permissions:
- **Level 0 (New)**: Can create topics and posts, cannot flag or send PMs
- **Level 1 (Basic)**: Can flag posts, send PMs
- **Level 2 (Member)**: Can edit wiki posts, create tags
- **Level 3 (Regular)**: Can recategorize/rename topics, close topics
- **Level 4 (Leader/Admin)**: Full access — manage users, groups, categories

### Groups
Groups enable collective permissions. They can:
- Have members added/removed
- Be granted category-level permissions
- Have visibility settings

### Tags
Tags provide cross-category organization. Tag groups restrict which tags can be used together or in certain categories.

### Notifications
Users receive notifications for:
- Replies to their posts
- Mentions (@username)
- Likes on their posts
- Other activities

### Flags/Reports
Users can flag inappropriate posts for moderation. Flags enter a review queue that admins can resolve or reject.

## Authentication

All endpoints require two headers:
- `X-API-Key`: Must be the string `"discourse-api-key"` (shared key for simplicity)
- `X-Username`: The username of the acting user

Missing either header returns 401. Invalid username (user not found) returns 401.

## Permission Model

Trust level checks return 403 when insufficient:
- Flagging posts: requires trust level >= 1
- Creating tags: requires trust level >= 2
- Recategorizing/renaming/closing topics: requires trust level >= 3
- Admin operations (manage categories, groups, users' trust levels, review flags): requires trust level == 4

## Data Storage

- Storage starts empty — no seed data
- All IDs are auto-incremented integers
- Timestamps are ISO 8601 strings
- Deleted posts are soft-deleted (marked but not removed from DB)

## Field Naming

All request/response field names use camelCase.
