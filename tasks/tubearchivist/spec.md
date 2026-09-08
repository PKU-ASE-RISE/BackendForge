# TubeArchivist — Media Management Server

## Overview

TubeArchivist is a self-hosted media management server for archiving and organizing video content. It provides a comprehensive API for managing video metadata, channels, playlists, download queues, comments, subtitles, sponsor segments, and application settings.

This is a **single-user application** — there is no multi-tenancy, but all endpoints require authentication via an API key.

## Authentication

All endpoints require the `X-API-Key` header. If the header is missing or invalid, the server must respond with HTTP 401.

The valid API key is configured server-side. For testing purposes, the key is `test-api-key-123`.

## Core Resources

### Videos

Videos are the primary resource. Each video has:
- `id` (string, auto-generated UUID)
- `title` (string, required)
- `description` (string)
- `duration` (integer, seconds)
- `uploadDate` (string, ISO date)
- `channelId` (string, reference to channel)
- `thumbnailUrl` (string, URL)
- `mediaUrl` (string, URL)
- `fileSize` (integer, bytes)
- `resolution` (string, e.g. "1920x1080")
- `tags` (array of strings)
- `watched` (boolean, default false)
- `watchedAt` (string, ISO datetime, null if not watched)
- `createdAt` (string, ISO datetime)

### Channels

Channels group videos by their source:
- `id` (string, auto-generated UUID)
- `name` (string, required)
- `description` (string)
- `subscriberCount` (integer)
- `videoCount` (integer, auto-calculated from stored videos)
- `subscribed` (boolean, default true)
- `createdAt` (string, ISO datetime)

The `videoCount` field is always derived from the actual number of videos associated with this channel.

### Playlists

User-created playlists for organizing videos:
- `id` (string, auto-generated UUID)
- `name` (string, required)
- `description` (string)
- `videoCount` (integer, auto-calculated)
- `totalDuration` (integer, sum of video durations)
- `createdAt` (string, ISO datetime)
- `updatedAt` (string, ISO datetime)

Playlist entries have explicit positions (1-based). Reordering updates positions of affected entries.

### Downloads (Queue)

Download queue for tracking media acquisition:
- `id` (string, auto-generated UUID)
- `url` (string, required)
- `title` (string, optional — may be populated after metadata fetch)
- `status` (string: "pending", "downloading", "completed", "failed")
- `priority` (integer, 1=highest, default 5)
- `errorMessage` (string, null unless failed)
- `addedAt` (string, ISO datetime)
- `startedAt` (string, ISO datetime, null until started)
- `completedAt` (string, ISO datetime, null until completed)

**Priority ordering**: Items are processed by priority (1 = highest). Items with the same priority are processed in FIFO order (by `addedAt`).

**Status transitions**:
- pending → downloading → completed
- pending → downloading → failed
- failed → pending (via retry)

### Comments

Video comments with threading support:
- `id` (string, auto-generated UUID)
- `videoId` (string, required)
- `parentId` (string, null for top-level comments)
- `author` (string, required)
- `text` (string, required)
- `timestamp` (integer, seconds into video, optional)
- `likes` (integer, default 0)
- `createdAt` (string, ISO datetime)

### Subtitles

Subtitle tracks associated with videos:
- `id` (string, auto-generated UUID)
- `videoId` (string, required)
- `language` (string, required, e.g. "en", "es")
- `content` (string, required — full subtitle text)
- `createdAt` (string, ISO datetime)

**Subtitle search**: Searching within subtitles returns matching videos and the specific subtitle lines containing the search term.

### SponsorBlock Segments

Marked segments within videos (sponsors, intros, outros):
- `id` (string, auto-generated UUID)
- `videoId` (string, required)
- `startTime` (number, seconds)
- `endTime` (number, seconds)
- `category` (string: "sponsor", "intro", "outro", "selfpromo", "interaction", "music_offtopic")
- `createdAt` (string, ISO datetime)

**Overlap validation**: Segments within the same video and same category must not overlap in time. The server must reject overlapping segments with HTTP 409.

### Snapshots (Backups)

Point-in-time snapshots of all metadata:
- `id` (string, auto-generated UUID)
- `name` (string, auto-generated or user-provided)
- `videoCount` (integer)
- `channelCount` (integer)
- `playlistCount` (integer)
- `size` (integer, bytes of serialized data)
- `createdAt` (string, ISO datetime)

**Create**: Serializes all current data to a stored JSON structure.
**Restore**: Replaces ALL current data with the snapshot data. This is destructive.

### Settings

Application configuration (key-value pairs):
- `downloadQuality` (string: "best", "1080p", "720p", "480p", default "best")
- `subtitleLanguages` (array of strings, default ["en"])
- `autoDownloadNewVideos` (boolean, default false)
- `storageLimit` (integer, bytes, default 0 = unlimited)
- `theme` (string: "dark", "light", default "dark")

Settings are a singleton resource (GET/PUT).

### Stats

Aggregate statistics derived from actual data:
- `totalVideos` (integer)
- `totalChannels` (integer)
- `totalPlaylists` (integer)
- `totalDuration` (integer, sum of all video durations in seconds)
- `totalFileSize` (integer, sum of all video file sizes in bytes)
- `videosWatched` (integer)
- `watchedPercentage` (number, 0-100)
- `videosPerDay` (object, date → count mapping for last 30 days based on video createdAt)
- `downloadQueueSize` (integer, count of pending/downloading items)

## API Endpoints

### Videos
- `GET /api/videos` — List videos (supports pagination: `page`, `limit`)
- `POST /api/videos` — Create video
- `GET /api/videos/{id}` — Get video by ID
- `PUT /api/videos/{id}` — Update video
- `DELETE /api/videos/{id}` — Delete video
- `POST /api/videos/{id}/watch` — Mark as watched
- `POST /api/videos/{id}/unwatch` — Mark as unwatched

### Channels
- `GET /api/channels` — List channels
- `POST /api/channels` — Create/subscribe to channel
- `GET /api/channels/{id}` — Get channel (includes computed videoCount)
- `PUT /api/channels/{id}` — Update channel
- `DELETE /api/channels/{id}` — Delete/unsubscribe from channel
- `GET /api/channels/{id}/videos` — List videos for a channel

### Playlists
- `GET /api/playlists` — List playlists
- `POST /api/playlists` — Create playlist
- `GET /api/playlists/{id}` — Get playlist
- `PUT /api/playlists/{id}` — Update playlist metadata
- `DELETE /api/playlists/{id}` — Delete playlist
- `GET /api/playlists/{id}/videos` — List videos in playlist (ordered by position)
- `POST /api/playlists/{id}/videos` — Add video to playlist
- `DELETE /api/playlists/{id}/videos/{videoId}` — Remove video from playlist
- `PUT /api/playlists/{id}/videos/{videoId}/reorder` — Change video position

### Downloads
- `GET /api/downloads` — List download queue (ordered by priority, then addedAt)
- `POST /api/downloads` — Add to download queue
- `GET /api/downloads/{id}` — Get download item
- `PUT /api/downloads/{id}` — Update download item (status, priority)
- `DELETE /api/downloads/{id}` — Remove from queue
- `POST /api/downloads/{id}/retry` — Retry failed download (resets to pending)

### Comments
- `GET /api/videos/{videoId}/comments` — List comments for video
- `POST /api/videos/{videoId}/comments` — Create comment
- `GET /api/comments/{id}` — Get single comment
- `DELETE /api/comments/{id}` — Delete comment

### Subtitles
- `GET /api/videos/{videoId}/subtitles` — List subtitle tracks for video
- `POST /api/videos/{videoId}/subtitles` — Add subtitle track
- `DELETE /api/subtitles/{id}` — Delete subtitle track
- `GET /api/search/subtitles` — Search within subtitles (query param: `q`)

### SponsorBlock Segments
- `GET /api/videos/{videoId}/segments` — List segments for video
- `POST /api/videos/{videoId}/segments` — Create segment
- `DELETE /api/segments/{id}` — Delete segment

### Search
- `GET /api/search/videos` — Full-text search videos (query param: `q`, searches title + description)
- `GET /api/search/channels` — Search channels by name (query param: `q`)
- `GET /api/search/subtitles` — Search within subtitle content (query param: `q`)

### Snapshots
- `GET /api/snapshots` — List snapshots
- `POST /api/snapshots` — Create snapshot
- `GET /api/snapshots/{id}` — Get snapshot metadata
- `DELETE /api/snapshots/{id}` — Delete snapshot
- `POST /api/snapshots/{id}/restore` — Restore from snapshot

### Stats
- `GET /api/stats` — Get aggregate statistics

### Settings
- `GET /api/settings` — Get current settings
- `PUT /api/settings` — Update settings

## Error Handling

All errors return JSON with `error` field:
```json
{"error": "Description of the error"}
```

Standard HTTP status codes:
- 200: Success
- 201: Created
- 400: Bad request (validation error)
- 401: Unauthorized (missing/invalid API key)
- 404: Resource not found
- 409: Conflict (e.g., overlapping sponsor segments)
- 422: Unprocessable entity

## Pagination

List endpoints support pagination via query parameters:
- `page` (integer, default 1)
- `limit` (integer, default 20, max 100)

Response includes:
- `items` (array)
- `total` (integer, total count)
- `page` (integer, current page)
- `limit` (integer, items per page)
