"""
TubeArchivist API — Correctness Test Suite
Tests all endpoints for proper behavior including CRUD operations,
business logic, authentication, and edge cases.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
DEFAULT_SETTINGS = {
    "downloadQuality": "best",
    "subtitleLanguages": ["en"],
    "autoDownloadNewVideos": False,
    "storageLimit": 0,
    "theme": "dark",
}


def url(path):
    return f"{BASE_URL}{path}"


# ─── Authentication ────────────────────────────────────────────────────────────


class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        r = requests.get(url("/api/videos"))
        assert r.status_code == 401

    def test_invalid_api_key_returns_401(self):
        r = requests.get(url("/api/videos"), headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_valid_api_key_returns_200(self):
        r = requests.get(url("/api/videos"), headers=HEADERS)
        assert r.status_code == 200


# ─── Videos ────────────────────────────────────────────────────────────────────


class TestVideos:
    def test_list_videos_empty(self):
        r = requests.get(url("/api/videos"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 0

    def test_create_video_minimal(self):
        payload = {"title": "Test Video"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Test Video"
        assert "id" in data
        assert "createdAt" in data
        assert data["watched"] is False
        assert data["watchedAt"] is None

    def test_create_video_full_metadata(self):
        payload = {
            "title": "Full Metadata Video",
            "description": "A detailed description",
            "duration": 3600,
            "uploadDate": "2024-01-15",
            "thumbnailUrl": "https://example.com/thumb.jpg",
            "mediaUrl": "https://example.com/video.mp4",
            "fileSize": 1073741824,
            "resolution": "1920x1080",
            "tags": ["tutorial", "python", "coding"],
        }
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Full Metadata Video"
        assert data["description"] == "A detailed description"
        assert data["duration"] == 3600
        assert data["uploadDate"] == "2024-01-15"
        assert data["fileSize"] == 1073741824
        assert data["resolution"] == "1920x1080"
        assert data["tags"] == ["tutorial", "python", "coding"]

    def test_create_video_missing_title_returns_400(self):
        payload = {"description": "No title here"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        assert r.status_code == 400

    def test_get_video(self):
        # Create
        payload = {"title": "Get Me"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        vid_id = r.json()["id"]
        # Fetch
        r = requests.get(url(f"/api/videos/{vid_id}"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["id"] == vid_id
        assert r.json()["title"] == "Get Me"

    def test_get_video_not_found(self):
        r = requests.get(url("/api/videos/nonexistent-id"), headers=HEADERS)
        assert r.status_code == 404

    def test_update_video(self):
        # Create
        payload = {"title": "Original Title", "duration": 100}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        vid_id = r.json()["id"]
        # Update
        update = {"title": "Updated Title", "duration": 200}
        r = requests.put(url(f"/api/videos/{vid_id}"), json=update, headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Updated Title"
        assert data["duration"] == 200

    def test_delete_video(self):
        # Create
        payload = {"title": "Delete Me"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        vid_id = r.json()["id"]
        # Delete
        r = requests.delete(url(f"/api/videos/{vid_id}"), headers=HEADERS)
        assert r.status_code == 200
        # Verify gone
        r = requests.get(url(f"/api/videos/{vid_id}"), headers=HEADERS)
        assert r.status_code == 404

    def test_pagination(self):
        # Create 3 videos
        for i in range(3):
            requests.post(
                url("/api/videos"),
                json={"title": f"Paginate {i}"},
                headers=HEADERS,
            )
        r = requests.get(url("/api/videos?page=1&limit=2"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["limit"] == 2


# ─── Watch State ───────────────────────────────────────────────────────────────


class TestWatchState:
    def test_mark_watched(self):
        payload = {"title": "Watch Me"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        vid_id = r.json()["id"]

        r = requests.post(url(f"/api/videos/{vid_id}/watch"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["watched"] is True
        assert data["watchedAt"] is not None

    def test_mark_unwatched(self):
        payload = {"title": "Unwatch Me"}
        r = requests.post(url("/api/videos"), json=payload, headers=HEADERS)
        vid_id = r.json()["id"]

        # Watch first
        requests.post(url(f"/api/videos/{vid_id}/watch"), headers=HEADERS)
        # Unwatch
        r = requests.post(url(f"/api/videos/{vid_id}/unwatch"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["watched"] is False
        assert data["watchedAt"] is None

    def test_watch_nonexistent_video_returns_404(self):
        r = requests.post(url("/api/videos/nonexistent/watch"), headers=HEADERS)
        assert r.status_code == 404


# ─── Channels ──────────────────────────────────────────────────────────────────


class TestChannels:
    def test_create_channel(self):
        payload = {"name": "Tech Channel", "description": "All about tech", "subscriberCount": 50000}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Tech Channel"
        assert data["subscriberCount"] == 50000
        assert data["subscribed"] is True
        assert data["videoCount"] == 0

    def test_create_channel_missing_name_returns_400(self):
        payload = {"description": "No name"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        assert r.status_code == 400

    def test_get_channel(self):
        payload = {"name": "Get Channel"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        ch_id = r.json()["id"]

        r = requests.get(url(f"/api/channels/{ch_id}"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["name"] == "Get Channel"

    def test_update_channel(self):
        payload = {"name": "Old Name"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        ch_id = r.json()["id"]

        r = requests.put(
            url(f"/api/channels/{ch_id}"),
            json={"name": "New Name", "subscribed": False},
            headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"
        assert r.json()["subscribed"] is False

    def test_delete_channel(self):
        payload = {"name": "Delete Channel"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        ch_id = r.json()["id"]

        r = requests.delete(url(f"/api/channels/{ch_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/channels/{ch_id}"), headers=HEADERS)
        assert r.status_code == 404

    def test_channel_video_count_auto_calculated(self):
        # Create channel
        payload = {"name": "Video Count Channel"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        ch_id = r.json()["id"]

        # Create videos for channel
        for i in range(3):
            requests.post(
                url("/api/videos"),
                json={"title": f"Channel Video {i}", "channelId": ch_id},
                headers=HEADERS,
            )

        # Check channel videoCount
        r = requests.get(url(f"/api/channels/{ch_id}"), headers=HEADERS)
        assert r.json()["videoCount"] == 3

    def test_list_channel_videos(self):
        payload = {"name": "Channel With Videos"}
        r = requests.post(url("/api/channels"), json=payload, headers=HEADERS)
        ch_id = r.json()["id"]

        requests.post(
            url("/api/videos"),
            json={"title": "Channel Vid 1", "channelId": ch_id},
            headers=HEADERS,
        )
        requests.post(
            url("/api/videos"),
            json={"title": "Channel Vid 2", "channelId": ch_id},
            headers=HEADERS,
        )

        r = requests.get(url(f"/api/channels/{ch_id}/videos"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2


# ─── Playlists ─────────────────────────────────────────────────────────────────


class TestPlaylists:
    def test_create_playlist(self):
        payload = {"name": "My Favorites", "description": "Best videos"}
        r = requests.post(url("/api/playlists"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My Favorites"
        assert data["videoCount"] == 0
        assert data["totalDuration"] == 0

    def test_add_video_to_playlist(self):
        # Create video
        r = requests.post(
            url("/api/videos"),
            json={"title": "Playlist Video", "duration": 120},
            headers=HEADERS,
        )
        vid_id = r.json()["id"]

        # Create playlist
        r = requests.post(
            url("/api/playlists"), json={"name": "Add Test"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        # Add video
        r = requests.post(
            url(f"/api/playlists/{pl_id}/videos"),
            json={"videoId": vid_id},
            headers=HEADERS,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["videoId"] == vid_id
        assert data["position"] == 1

    def test_playlist_video_ordering(self):
        # Create videos
        vids = []
        for i in range(3):
            r = requests.post(
                url("/api/videos"),
                json={"title": f"Order Video {i}", "duration": 100 * (i + 1)},
                headers=HEADERS,
            )
            vids.append(r.json()["id"])

        # Create playlist and add videos
        r = requests.post(
            url("/api/playlists"), json={"name": "Order Test"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        for vid_id in vids:
            requests.post(
                url(f"/api/playlists/{pl_id}/videos"),
                json={"videoId": vid_id},
                headers=HEADERS,
            )

        # Check ordering
        r = requests.get(url(f"/api/playlists/{pl_id}/videos"), headers=HEADERS)
        items = r.json()["items"]
        assert len(items) == 3
        assert items[0]["position"] == 1
        assert items[1]["position"] == 2
        assert items[2]["position"] == 3

    def test_reorder_video_in_playlist(self):
        # Create videos
        vids = []
        for i in range(3):
            r = requests.post(
                url("/api/videos"),
                json={"title": f"Reorder Video {i}", "duration": 60},
                headers=HEADERS,
            )
            vids.append(r.json()["id"])

        # Create playlist
        r = requests.post(
            url("/api/playlists"), json={"name": "Reorder Test"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        for vid_id in vids:
            requests.post(
                url(f"/api/playlists/{pl_id}/videos"),
                json={"videoId": vid_id},
                headers=HEADERS,
            )

        # Move video at position 3 to position 1
        r = requests.put(
            url(f"/api/playlists/{pl_id}/videos/{vids[2]}/reorder"),
            json={"position": 1},
            headers=HEADERS,
        )
        assert r.status_code == 200

        # Verify new order
        r = requests.get(url(f"/api/playlists/{pl_id}/videos"), headers=HEADERS)
        items = r.json()["items"]
        assert items[0]["videoId"] == vids[2]
        assert items[0]["position"] == 1
        assert items[1]["videoId"] == vids[0]
        assert items[1]["position"] == 2
        assert items[2]["videoId"] == vids[1]
        assert items[2]["position"] == 3

    def test_remove_video_from_playlist(self):
        # Create video
        r = requests.post(
            url("/api/videos"),
            json={"title": "Remove Playlist Video", "duration": 60},
            headers=HEADERS,
        )
        vid_id = r.json()["id"]

        # Create playlist and add
        r = requests.post(
            url("/api/playlists"), json={"name": "Remove Test"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        requests.post(
            url(f"/api/playlists/{pl_id}/videos"),
            json={"videoId": vid_id},
            headers=HEADERS,
        )

        # Remove
        r = requests.delete(
            url(f"/api/playlists/{pl_id}/videos/{vid_id}"), headers=HEADERS
        )
        assert r.status_code == 200

        # Verify
        r = requests.get(url(f"/api/playlists/{pl_id}/videos"), headers=HEADERS)
        assert len(r.json()["items"]) == 0

    def test_playlist_metadata_updates(self):
        # Create video
        r = requests.post(
            url("/api/videos"),
            json={"title": "Duration Video", "duration": 300},
            headers=HEADERS,
        )
        vid_id = r.json()["id"]

        # Create playlist
        r = requests.post(
            url("/api/playlists"), json={"name": "Meta Test"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        # Add video
        requests.post(
            url(f"/api/playlists/{pl_id}/videos"),
            json={"videoId": vid_id},
            headers=HEADERS,
        )

        # Check playlist
        r = requests.get(url(f"/api/playlists/{pl_id}"), headers=HEADERS)
        data = r.json()
        assert data["videoCount"] == 1
        assert data["totalDuration"] == 300

    def test_delete_playlist(self):
        r = requests.post(
            url("/api/playlists"), json={"name": "Delete Me"}, headers=HEADERS
        )
        pl_id = r.json()["id"]

        r = requests.delete(url(f"/api/playlists/{pl_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/playlists/{pl_id}"), headers=HEADERS)
        assert r.status_code == 404


# ─── Downloads ─────────────────────────────────────────────────────────────────


class TestDownloads:
    def test_add_to_download_queue(self):
        payload = {
            "url": "https://youtube.com/watch?v=abc123",
            "title": "Cool Video",
            "priority": 3,
        }
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["url"] == "https://youtube.com/watch?v=abc123"
        assert data["status"] == "pending"
        assert data["priority"] == 3
        assert data["addedAt"] is not None

    def test_add_download_default_priority(self):
        payload = {"url": "https://youtube.com/watch?v=default"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["priority"] == 5

    def test_download_priority_ordering(self):
        # Add items with different priorities
        requests.post(
            url("/api/downloads"),
            json={"url": "https://example.com/low", "priority": 10},
            headers=HEADERS,
        )
        requests.post(
            url("/api/downloads"),
            json={"url": "https://example.com/high", "priority": 1},
            headers=HEADERS,
        )
        requests.post(
            url("/api/downloads"),
            json={"url": "https://example.com/mid", "priority": 5},
            headers=HEADERS,
        )

        r = requests.get(url("/api/downloads"), headers=HEADERS)
        items = r.json()["items"]
        # Filter to just our items
        our_urls = {"https://example.com/low", "https://example.com/high", "https://example.com/mid"}
        our_items = [i for i in items if i["url"] in our_urls]

        # Should be ordered by priority (1 first)
        priorities = [i["priority"] for i in our_items]
        assert priorities == sorted(priorities)

    def test_download_status_transition(self):
        payload = {"url": "https://example.com/transition"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        dl_id = r.json()["id"]

        # pending -> downloading
        r = requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "downloading"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "downloading"

        # downloading -> completed
        r = requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "completed"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_download_failed_status(self):
        payload = {"url": "https://example.com/fail"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        dl_id = r.json()["id"]

        r = requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "downloading"},
            headers=HEADERS,
        )

        r = requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "failed", "errorMessage": "Network error"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "failed"
        assert r.json()["errorMessage"] == "Network error"

    def test_retry_failed_download(self):
        payload = {"url": "https://example.com/retry"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        dl_id = r.json()["id"]

        # Set to failed
        requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "downloading"},
            headers=HEADERS,
        )
        requests.put(
            url(f"/api/downloads/{dl_id}"),
            json={"status": "failed", "errorMessage": "Timeout"},
            headers=HEADERS,
        )

        # Retry
        r = requests.post(url(f"/api/downloads/{dl_id}/retry"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        assert r.json()["errorMessage"] is None

    def test_retry_non_failed_download_returns_400(self):
        payload = {"url": "https://example.com/not-failed"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        dl_id = r.json()["id"]

        r = requests.post(url(f"/api/downloads/{dl_id}/retry"), headers=HEADERS)
        assert r.status_code == 400

    def test_delete_download(self):
        payload = {"url": "https://example.com/delete-dl"}
        r = requests.post(url("/api/downloads"), json=payload, headers=HEADERS)
        dl_id = r.json()["id"]

        r = requests.delete(url(f"/api/downloads/{dl_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/downloads/{dl_id}"), headers=HEADERS)
        assert r.status_code == 404


# ─── Comments ──────────────────────────────────────────────────────────────────


class TestComments:
    def _create_video(self):
        r = requests.post(
            url("/api/videos"),
            json={"title": "Comment Video"},
            headers=HEADERS,
        )
        return r.json()["id"]

    def test_create_comment(self):
        vid_id = self._create_video()
        payload = {
            "author": "John Doe",
            "text": "Great video!",
            "timestamp": 42,
            "likes": 5,
        }
        r = requests.post(
            url(f"/api/videos/{vid_id}/comments"), json=payload, headers=HEADERS
        )
        assert r.status_code == 201
        data = r.json()
        assert data["author"] == "John Doe"
        assert data["text"] == "Great video!"
        assert data["timestamp"] == 42
        assert data["likes"] == 5
        assert data["videoId"] == vid_id
        assert data["parentId"] is None

    def test_threaded_comments(self):
        vid_id = self._create_video()

        # Parent comment
        r = requests.post(
            url(f"/api/videos/{vid_id}/comments"),
            json={"author": "Alice", "text": "First!"},
            headers=HEADERS,
        )
        parent_id = r.json()["id"]

        # Reply
        r = requests.post(
            url(f"/api/videos/{vid_id}/comments"),
            json={"author": "Bob", "text": "Nice one!", "parentId": parent_id},
            headers=HEADERS,
        )
        assert r.status_code == 201
        assert r.json()["parentId"] == parent_id

    def test_list_comments_for_video(self):
        vid_id = self._create_video()

        for i in range(3):
            requests.post(
                url(f"/api/videos/{vid_id}/comments"),
                json={"author": f"User{i}", "text": f"Comment {i}"},
                headers=HEADERS,
            )

        r = requests.get(url(f"/api/videos/{vid_id}/comments"), headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3

    def test_get_comment(self):
        vid_id = self._create_video()
        r = requests.post(
            url(f"/api/videos/{vid_id}/comments"),
            json={"author": "Tester", "text": "Get me"},
            headers=HEADERS,
        )
        comment_id = r.json()["id"]

        r = requests.get(url(f"/api/comments/{comment_id}"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["text"] == "Get me"

    def test_delete_comment(self):
        vid_id = self._create_video()
        r = requests.post(
            url(f"/api/videos/{vid_id}/comments"),
            json={"author": "Tester", "text": "Delete me"},
            headers=HEADERS,
        )
        comment_id = r.json()["id"]

        r = requests.delete(url(f"/api/comments/{comment_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/comments/{comment_id}"), headers=HEADERS)
        assert r.status_code == 404

    def test_comment_on_nonexistent_video_returns_404(self):
        r = requests.post(
            url("/api/videos/nonexistent/comments"),
            json={"author": "A", "text": "B"},
            headers=HEADERS,
        )
        assert r.status_code == 404


# ─── Subtitles ─────────────────────────────────────────────────────────────────


class TestSubtitles:
    def _create_video(self, title="Sub Video"):
        r = requests.post(
            url("/api/videos"), json={"title": title}, headers=HEADERS
        )
        return r.json()["id"]

    def test_add_subtitle_track(self):
        vid_id = self._create_video()
        payload = {
            "language": "en",
            "content": "Hello world\nThis is a subtitle\nEnd of video",
        }
        r = requests.post(
            url(f"/api/videos/{vid_id}/subtitles"), json=payload, headers=HEADERS
        )
        assert r.status_code == 201
        data = r.json()
        assert data["language"] == "en"
        assert data["videoId"] == vid_id
        assert "Hello world" in data["content"]

    def test_list_subtitles_for_video(self):
        vid_id = self._create_video()
        requests.post(
            url(f"/api/videos/{vid_id}/subtitles"),
            json={"language": "en", "content": "English subs"},
            headers=HEADERS,
        )
        requests.post(
            url(f"/api/videos/{vid_id}/subtitles"),
            json={"language": "es", "content": "Spanish subs"},
            headers=HEADERS,
        )

        r = requests.get(url(f"/api/videos/{vid_id}/subtitles"), headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_delete_subtitle(self):
        vid_id = self._create_video()
        r = requests.post(
            url(f"/api/videos/{vid_id}/subtitles"),
            json={"language": "en", "content": "Delete me"},
            headers=HEADERS,
        )
        sub_id = r.json()["id"]

        r = requests.delete(url(f"/api/subtitles/{sub_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/videos/{vid_id}/subtitles"), headers=HEADERS)
        assert len(r.json()["items"]) == 0

    def test_search_subtitles(self):
        vid_id = self._create_video("Searchable Video")
        requests.post(
            url(f"/api/videos/{vid_id}/subtitles"),
            json={
                "language": "en",
                "content": "Welcome to the tutorial\nToday we learn Python\nThank you for watching",
            },
            headers=HEADERS,
        )

        r = requests.get(
            url("/api/search/subtitles?q=Python"), headers=HEADERS
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        # Find our result
        found = False
        for item in data["items"]:
            if item["videoId"] == vid_id:
                found = True
                assert any("Python" in line for line in item["matchingLines"])
                break
        assert found, "Expected video not found in subtitle search results"


# ─── SponsorBlock Segments ─────────────────────────────────────────────────────


class TestSegments:
    def _create_video(self):
        r = requests.post(
            url("/api/videos"),
            json={"title": "Segment Video", "duration": 600},
            headers=HEADERS,
        )
        return r.json()["id"]

    def test_create_segment(self):
        vid_id = self._create_video()
        payload = {"startTime": 0, "endTime": 30, "category": "intro"}
        r = requests.post(
            url(f"/api/videos/{vid_id}/segments"), json=payload, headers=HEADERS
        )
        assert r.status_code == 201
        data = r.json()
        assert data["startTime"] == 0
        assert data["endTime"] == 30
        assert data["category"] == "intro"
        assert data["videoId"] == vid_id

    def test_list_segments(self):
        vid_id = self._create_video()
        requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 0, "endTime": 15, "category": "intro"},
            headers=HEADERS,
        )
        requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 100, "endTime": 150, "category": "sponsor"},
            headers=HEADERS,
        )

        r = requests.get(url(f"/api/videos/{vid_id}/segments"), headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_overlapping_same_category_rejected(self):
        vid_id = self._create_video()
        # Create first segment
        requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 10, "endTime": 50, "category": "sponsor"},
            headers=HEADERS,
        )
        # Try overlapping segment with same category
        r = requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 30, "endTime": 70, "category": "sponsor"},
            headers=HEADERS,
        )
        assert r.status_code == 409

    def test_overlapping_different_category_allowed(self):
        vid_id = self._create_video()
        # Create first segment
        requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 10, "endTime": 50, "category": "sponsor"},
            headers=HEADERS,
        )
        # Overlapping but different category should be OK
        r = requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 30, "endTime": 70, "category": "selfpromo"},
            headers=HEADERS,
        )
        assert r.status_code == 201

    def test_delete_segment(self):
        vid_id = self._create_video()
        r = requests.post(
            url(f"/api/videos/{vid_id}/segments"),
            json={"startTime": 0, "endTime": 10, "category": "intro"},
            headers=HEADERS,
        )
        seg_id = r.json()["id"]

        r = requests.delete(url(f"/api/segments/{seg_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/videos/{vid_id}/segments"), headers=HEADERS)
        assert len(r.json()["items"]) == 0


# ─── Search ────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_search_videos_by_title(self):
        requests.post(
            url("/api/videos"),
            json={"title": "Machine Learning Basics", "description": "Intro to ML"},
            headers=HEADERS,
        )
        requests.post(
            url("/api/videos"),
            json={"title": "Cooking Recipe", "description": "Pasta guide"},
            headers=HEADERS,
        )

        r = requests.get(url("/api/search/videos?q=Machine Learning"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        titles = [v["title"] for v in data["items"]]
        assert any("Machine Learning" in t for t in titles)

    def test_search_videos_by_description(self):
        requests.post(
            url("/api/videos"),
            json={
                "title": "Unique Title XYZ123",
                "description": "quantum computing explanation",
            },
            headers=HEADERS,
        )

        r = requests.get(url("/api/search/videos?q=quantum"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_search_channels(self):
        requests.post(
            url("/api/channels"),
            json={"name": "Python Mastery Channel"},
            headers=HEADERS,
        )

        r = requests.get(
            url("/api/search/channels?q=Python Mastery"), headers=HEADERS
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# ─── Snapshots ─────────────────────────────────────────────────────────────────


class TestSnapshots:
    def test_create_snapshot(self):
        # Add some data first
        requests.post(
            url("/api/videos"), json={"title": "Snapshot Video"}, headers=HEADERS
        )

        r = requests.post(
            url("/api/snapshots"), json={"name": "Test Backup"}, headers=HEADERS
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Test Backup"
        assert "id" in data
        assert data["videoCount"] >= 1

    def test_list_snapshots(self):
        requests.post(
            url("/api/snapshots"), json={"name": "List Test"}, headers=HEADERS
        )

        r = requests.get(url("/api/snapshots"), headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 1

    def test_get_snapshot(self):
        r = requests.post(
            url("/api/snapshots"), json={"name": "Get Test"}, headers=HEADERS
        )
        snap_id = r.json()["id"]

        r = requests.get(url(f"/api/snapshots/{snap_id}"), headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["name"] == "Get Test"

    def test_delete_snapshot(self):
        r = requests.post(
            url("/api/snapshots"), json={"name": "Delete Test"}, headers=HEADERS
        )
        snap_id = r.json()["id"]

        r = requests.delete(url(f"/api/snapshots/{snap_id}"), headers=HEADERS)
        assert r.status_code == 200

        r = requests.get(url(f"/api/snapshots/{snap_id}"), headers=HEADERS)
        assert r.status_code == 404

    def test_restore_snapshot(self):
        # Create a video
        r = requests.post(
            url("/api/videos"),
            json={"title": "Before Snapshot", "duration": 100},
            headers=HEADERS,
        )
        vid_before_id = r.json()["id"]

        # Create snapshot
        r = requests.post(
            url("/api/snapshots"), json={"name": "Restore Test"}, headers=HEADERS
        )
        snap_id = r.json()["id"]

        # Add another video after snapshot
        requests.post(
            url("/api/videos"),
            json={"title": "After Snapshot"},
            headers=HEADERS,
        )

        # Restore
        r = requests.post(
            url(f"/api/snapshots/{snap_id}/restore"), headers=HEADERS
        )
        assert r.status_code == 200

        # The video created before snapshot should exist
        r = requests.get(url(f"/api/videos/{vid_before_id}"), headers=HEADERS)
        assert r.status_code == 200

        # The video list should not contain the post-snapshot video
        r = requests.get(url("/api/videos?limit=100"), headers=HEADERS)
        titles = [v["title"] for v in r.json()["items"]]
        assert "After Snapshot" not in titles


# ─── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_reflect_data(self):
        # Clear state with snapshot/restore trick: create snapshot of current state
        # just test stats are consistent with what we can observe
        r = requests.get(url("/api/stats"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "totalVideos" in data
        assert "totalChannels" in data
        assert "totalPlaylists" in data
        assert "totalDuration" in data
        assert "totalFileSize" in data
        assert "videosWatched" in data
        assert "watchedPercentage" in data
        assert "downloadQueueSize" in data

    def test_stats_update_after_adding_video(self):
        # Get current stats
        r = requests.get(url("/api/stats"), headers=HEADERS)
        before_count = r.json()["totalVideos"]
        before_duration = r.json()["totalDuration"]

        # Add video
        requests.post(
            url("/api/videos"),
            json={"title": "Stats Video", "duration": 500, "fileSize": 1000000},
            headers=HEADERS,
        )

        # Check stats updated
        r = requests.get(url("/api/stats"), headers=HEADERS)
        data = r.json()
        assert data["totalVideos"] == before_count + 1
        assert data["totalDuration"] == before_duration + 500

    def test_stats_watched_percentage(self):
        # Create two videos
        r = requests.post(
            url("/api/videos"),
            json={"title": "Stats Watched 1"},
            headers=HEADERS,
        )
        vid1_id = r.json()["id"]
        requests.post(
            url("/api/videos"),
            json={"title": "Stats Watched 2"},
            headers=HEADERS,
        )

        # Mark one as watched
        requests.post(url(f"/api/videos/{vid1_id}/watch"), headers=HEADERS)

        # Check stats
        r = requests.get(url("/api/stats"), headers=HEADERS)
        data = r.json()
        assert data["videosWatched"] >= 1
        assert data["watchedPercentage"] >= 0
        assert data["watchedPercentage"] <= 100


# ─── Settings ──────────────────────────────────────────────────────────────────


class TestSettings:
    def test_get_default_settings(self):
        r = requests.get(url("/api/settings"), headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["downloadQuality"] == "best"
        assert data["subtitleLanguages"] == ["en"]
        assert data["autoDownloadNewVideos"] is False
        assert data["storageLimit"] == 0
        assert data["theme"] == "dark"

    def test_update_settings(self):
        payload = {
            "downloadQuality": "1080p",
            "subtitleLanguages": ["en", "es", "fr"],
            "autoDownloadNewVideos": True,
            "storageLimit": 107374182400,
            "theme": "light",
        }
        try:
            r = requests.put(url("/api/settings"), json=payload, headers=HEADERS)
            assert r.status_code == 200
            data = r.json()
            assert data["downloadQuality"] == "1080p"
            assert data["subtitleLanguages"] == ["en", "es", "fr"]
            assert data["autoDownloadNewVideos"] is True
            assert data["storageLimit"] == 107374182400
            assert data["theme"] == "light"
        finally:
            requests.put(
                url("/api/settings"), json=DEFAULT_SETTINGS, headers=HEADERS
            )

    def test_partial_settings_update(self):
        try:
            # First reset to defaults
            requests.put(
                url("/api/settings"),
                json=DEFAULT_SETTINGS,
                headers=HEADERS,
            )

            # Partial update
            r = requests.put(
                url("/api/settings"),
                json={"theme": "light"},
                headers=HEADERS,
            )
            assert r.status_code == 200
            data = r.json()
            assert data["theme"] == "light"
            # Other settings should remain
            assert data["downloadQuality"] == "best"
        finally:
            requests.put(
                url("/api/settings"), json=DEFAULT_SETTINGS, headers=HEADERS
            )
