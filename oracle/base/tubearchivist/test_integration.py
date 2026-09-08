"""
L2 Integration Tests for TubeArchivist API.
Targets: camelCase, computed values, status codes, filtering.
"""
import os, uuid, requests, pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
H = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex[:8]}"


class TestVideoFieldCasing:
    def test_create_video_returns_camelcase(self):
        resp = requests.post(f"{BASE_URL}/api/videos", json={
            "title": "Test Video", "description": "A test", "duration": 120,
            "tags": ["test", "demo"]
        }, headers=H)
        assert resp.status_code == 201
        v = resp.json()
        assert "id" in v
        assert v["title"] == "Test Video"
        assert v["duration"] == 120
        assert "createdAt" in v
        assert "watched" in v and v["watched"] is False
        assert "watchedAt" in v
        assert "tags" in v and "test" in v["tags"]
        assert "created_at" not in v
        assert "watched_at" not in v

    def test_get_video_by_id(self):
        v = requests.post(f"{BASE_URL}/api/videos", json={"title": "Get Me"}, headers=H).json()
        resp = requests.get(f"{BASE_URL}/api/videos/{v['id']}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == v["id"]

class TestChannelVideoCount:
    def test_video_count_computed(self):
        # Create channel
        ch = requests.post(f"{BASE_URL}/api/channels", json={"name": unique("ch")}, headers=H).json()
        assert ch["videoCount"] == 0

        # Add videos to channel
        requests.post(f"{BASE_URL}/api/videos", json={"title": "V1", "channelId": ch["id"]}, headers=H)
        requests.post(f"{BASE_URL}/api/videos", json={"title": "V2", "channelId": ch["id"]}, headers=H)

        # Check count
        resp = requests.get(f"{BASE_URL}/api/channels/{ch['id']}", headers=H)
        assert resp.json()["videoCount"] == 2

class TestPlaylistComputed:
    def test_playlist_video_count_and_duration(self):
        v1 = requests.post(f"{BASE_URL}/api/videos", json={"title": "P1", "duration": 60}, headers=H).json()
        v2 = requests.post(f"{BASE_URL}/api/videos", json={"title": "P2", "duration": 90}, headers=H).json()

        pl = requests.post(f"{BASE_URL}/api/playlists", json={"name": unique("pl")}, headers=H).json()

        requests.post(f"{BASE_URL}/api/playlists/{pl['id']}/videos", json={"videoId": v1["id"], "position": 1}, headers=H)
        requests.post(f"{BASE_URL}/api/playlists/{pl['id']}/videos", json={"videoId": v2["id"], "position": 2}, headers=H)

        resp = requests.get(f"{BASE_URL}/api/playlists/{pl['id']}", headers=H)
        data = resp.json()
        assert data["videoCount"] == 2
        assert data["totalDuration"] == 150

class TestStatusCodes:
    def test_create_returns_201(self):
        resp = requests.post(f"{BASE_URL}/api/videos", json={"title": "S"}, headers=H)
        assert resp.status_code == 201

    def test_delete_returns_200(self):
        v = requests.post(f"{BASE_URL}/api/videos", json={"title": "Del"}, headers=H).json()
        resp = requests.delete(f"{BASE_URL}/api/videos/{v['id']}", headers=H)
        assert resp.status_code == 200

    def test_get_nonexistent_returns_404(self):
        resp = requests.get(f"{BASE_URL}/api/videos/{uuid.uuid4().hex}", headers=H)
        assert resp.status_code == 404

    def test_missing_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/videos")
        assert resp.status_code == 401

class TestWatchedStatus:
    def test_mark_watched(self):
        v = requests.post(f"{BASE_URL}/api/videos", json={"title": "Watch"}, headers=H).json()
        assert v["watched"] is False

        resp = requests.post(f"{BASE_URL}/api/videos/{v['id']}/watch", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["watched"] is True
        assert data["watchedAt"] is not None

    def test_mark_unwatched(self):
        v = requests.post(f"{BASE_URL}/api/videos", json={"title": "Unwatch"}, headers=H).json()
        requests.post(f"{BASE_URL}/api/videos/{v['id']}/watch", headers=H)
        resp = requests.post(f"{BASE_URL}/api/videos/{v['id']}/unwatch", headers=H)
        assert resp.status_code == 200
        assert resp.json()["watched"] is False

class TestDownloadQueue:
    def test_queue_item_fields(self):
        resp = requests.post(f"{BASE_URL}/api/downloads", json={
            "url": "https://youtube.com/watch?v=abc", "priority": 1
        }, headers=H)
        assert resp.status_code == 201
        d = resp.json()
        assert "id" in d
        assert d["url"] == "https://youtube.com/watch?v=abc"
        assert d["status"] == "pending"
        assert d["priority"] == 1
        assert "addedAt" in d
        assert "errorMessage" in d

class TestVideoFiltering:
    def test_channel_videos_endpoint(self):
        ch = requests.post(f"{BASE_URL}/api/channels", json={"name": unique("fc")}, headers=H).json()
        requests.post(f"{BASE_URL}/api/videos", json={"title": "InCh", "channelId": ch["id"]}, headers=H)
        requests.post(f"{BASE_URL}/api/videos", json={"title": "InCh2", "channelId": ch["id"]}, headers=H)

        resp = requests.get(f"{BASE_URL}/api/channels/{ch['id']}/videos", headers=H)
        assert resp.status_code == 200
        videos = resp.json()["items"]
        assert len(videos) == 2

class TestVideoSearch:
    def test_search_by_title(self):
        unique_title = unique("search")
        requests.post(f"{BASE_URL}/api/videos", json={"title": unique_title}, headers=H)

        resp = requests.get(f"{BASE_URL}/api/search/videos", params={"q": unique_title}, headers=H)
        assert resp.status_code == 200
        videos = resp.json()["items"]
        assert len(videos) >= 1
        assert any(unique_title in v["title"] for v in videos)
