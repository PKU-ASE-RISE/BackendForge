# Developer Community Platform (Forem)

## Overview

A developer blogging and community platform inspired by [Forem/dev.to](https://github.com/forem/forem). Users can write articles, comment on posts, follow other users and tags, react to articles, post classifieds (listings), and organize into organizations.

## Tech Stack

Your choice.

## Authentication

- **Header**: `X-User-Id` (UUID string)
- **Behavior**: Trust the header value directly. If the header is missing on endpoints that require auth, return `401`.
- **Auto-provisioning**: On first request with a new `X-User-Id`, automatically create a user profile with `username` derived from the UUID (e.g., `user_<first-8-chars>`). The `joined_at` timestamp is set at creation time.
- **Data isolation**: Articles, comments, listings are scoped to their author for write operations. Read access is public (except unpublished articles).

## Endpoints

### Articles

- `POST /articles` — Create article (auth required). Body: `title`, `body_markdown`, `published` (bool, default false), `tags` (list of tag names, max 4), `canonical_url`, `cover_image_url`, `description`. Returns created article with computed fields.
- `GET /articles` — List published articles. Query params: `page` (default 1), `per_page` (default 20, max 100), `tag` (filter by tag name). Sorted by `published_at` descending.
- `GET /articles/{id}` — Get single article. Public articles visible to all. Unpublished articles only visible to author.
- `PUT /articles/{id}` — Update article (author only).
- `DELETE /articles/{id}` — Delete article (author only).
- `GET /articles/me` — List current user's articles (includes unpublished). Query: `page`, `per_page`.
- `GET /articles/feed` — Personalized feed (auth required). Returns articles from followed users/tags from last 7 days, sorted by score descending. Query: `page`, `per_page`.

### Comments

- `POST /articles/{article_id}/comments` — Create comment (auth required). Body: `body`, `parent_id` (optional, for threading).
- `GET /articles/{article_id}/comments` — List comments on article (public). Returns flat list sorted by creation time ascending.
- `GET /comments/{id}` — Get single comment (public).
- `PUT /comments/{id}` — Update comment (author only). Body: `body`.
- `DELETE /comments/{id}` — Delete comment (author only). Sets body to `[deleted]` and clears `user_id` (soft delete). Children remain.

### Tags

- `GET /tags` — List all tags. Query: `page`, `per_page`.
- `POST /tags` — Create tag (auth required). Body: `name`, `bg_color`, `text_color`, `description`, `rules_markdown`.
- `GET /tags/{id}` — Get single tag.
- `PUT /tags/{id}` — Update tag (auth required).
- `DELETE /tags/{id}` — Delete tag (auth required).

### Users

- `GET /users/me` — Get current user's profile (auth required).
- `GET /users/{username}` — Get user profile by username (public). Includes `articles_count` (number of published articles).

### Follows

- `POST /follows/users/{user_id}` — Follow a user (auth required). Cannot follow self.
- `DELETE /follows/users/{user_id}` — Unfollow a user (auth required).
- `GET /follows/users` — List users the current user follows (auth required).
- `POST /follows/tags/{tag_id}` — Follow a tag (auth required).
- `DELETE /follows/tags/{tag_id}` — Unfollow a tag (auth required).
- `GET /follows/tags` — List tags the current user follows (auth required).
- `GET /users/{username}/followers` — List followers of a user (public).

### Reactions

- `POST /articles/{article_id}/reactions` — Toggle a reaction (auth required). Body: `category` (one of: `like`, `unicorn`, `readinglist`). If reaction exists, remove it (toggle off). If not, create it (toggle on). Returns the current state.
- `GET /articles/{article_id}/reactions` — List reactions on an article (public). Returns summary counts and user's own reactions.

### Listings (Classifieds)

- `POST /listings` — Create listing (auth required). Body: `title`, `body`, `category` (one of: `jobs`, `events`, `misc`, `mentors`), `contact_via`, `published` (default true).
- `GET /listings` — List published listings. Query: `page`, `per_page`, `category`.
- `GET /listings/{id}` — Get single listing.
- `PUT /listings/{id}` — Update listing (author only).
- `DELETE /listings/{id}` — Delete listing (author only).

### Organizations

- `POST /organizations` — Create organization (auth required). Body: `name`, `slug`, `description`. Creator becomes first member.
- `GET /organizations` — List organizations. Query: `page`, `per_page`.
- `GET /organizations/{slug}` — Get organization by slug.
- `PUT /organizations/{slug}` — Update organization (members only).
- `DELETE /organizations/{slug}` — Delete organization (members only).
- `POST /organizations/{slug}/members` — Add member (existing members only). Body: `username`.
- `DELETE /organizations/{slug}/members/{username}` — Remove member (existing members only). Cannot remove last member.
- `GET /organizations/{slug}/members` — List members (public).
- `GET /organizations/{slug}/articles` — List published articles by org members (public).

### Search

- `GET /search/articles` — Full-text search articles by title, body, and tags. Query: `q` (required), `page`, `per_page`. Only searches published articles.

### Reading List

- `GET /readinglist` — Get current user's reading list (auth required). Returns articles the user has reacted to with `readinglist` category. Query: `page`, `per_page`.

## Business Rules

### Reading Time
- Computed as: `ceil(word_count / 200)` where `word_count` is the number of whitespace-separated tokens in `body_markdown`.
- Minimum 1 minute.

### Article Score
- Computed as: `(reactions_count × 2) + (comments_count × 3)`
- Used for feed ranking.

### Slug Generation
- Generated from article title: lowercase, replace non-alphanumeric with hyphens, collapse consecutive hyphens, trim leading/trailing hyphens.
- Must be globally unique. If slug already exists, append `-<random-4-hex-chars>`.

### Published Flag
- Unpublished articles (`published: false`) are only visible to their author.
- `GET /articles` only returns published articles.
- `GET /articles/me` returns both published and unpublished.
- `published_at` is set when article is first published (transitions from false to true).

### Feed Algorithm
- Returns articles from the last 7 days that are:
  - Written by users the current user follows, OR
  - Tagged with tags the current user follows
- Sorted by score descending (ties broken by `published_at` descending).
- Page size controlled by `per_page` (default 20).
- If fewer than `per_page` results from follows, backfill with recent popular articles (not already in result).

### Reaction Uniqueness
- One reaction of each `category` per user per article.
- Toggling: POST the same category again → removes the reaction.
- Three categories: `like`, `unicorn`, `readinglist`.

### Threaded Comments
- `parent_id` references another comment on the same article.
- Deleting a comment soft-deletes it (body becomes `[deleted]`, user_id set to null). Children remain attached.

### Tag Limit
- Maximum 4 tags per article. Attempting to set more returns 400.

### articles_count
- Computed field on user profiles. Counts only published articles by that user.

### Pagination
- All list endpoints support `page` (1-based) and `per_page`.
- Default `per_page` is 20, max is 100.
- Response should include pagination metadata: `total`, `page`, `per_page`.

## Response Format

All responses are JSON. List endpoints return:
```json
{
  "data": [...],
  "meta": {
    "total": 42,
    "page": 1,
    "per_page": 20
  }
}
```

Single resource endpoints return the resource object directly (no wrapper).

## Error Format

```json
{
  "error": "description of what went wrong"
}
```

Standard HTTP status codes: 400 (bad request), 401 (unauthorized), 403 (forbidden), 404 (not found), 409 (conflict).
