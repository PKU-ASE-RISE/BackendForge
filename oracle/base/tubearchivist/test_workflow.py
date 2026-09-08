"""
L3 Workflow Tests for TubeArchivist API.
Multi-step: video+channel lifecycle, playlist management, download queue.
"""
import os, uuid, requests, pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
H = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex[:8]}"


class TestVideoChannelLifecycle:
    def test_channel_video_relationship(self):
        # 1. Create channel
        ch = requests.post(f"{BASE_URL}/api/channels", json={
            "name": unique("ch"), "description": "Test Channel"
        }, headers=H).json()
        assert ch["videoCount"] == 0

        # 2. Add videos
        v1 = requests.post(f"{BASE_URL}/api/videos", json={
            "title": "Video 1", "channelId": ch["id"], "duration": 300
        }, headers=H).json()
        v2 = requests.post(f"{BASE_URL}/api/videos", json={
            "title": "Video 2", "channelId": ch["id"], "duration": 600
        }, headers=H).json()

        # 3. Verify channel video count
        resp = requests.get(f"{BASE_URL}/api/channels/{ch['id']}", headers=H)
        assert resp.json()["videoCount"] == 2

        # 4. Delete a video
        requests.delete(f"{BASE_URL}/api/videos/{v1['id']}", headers=H)

        # 5. Channel count decreases
        resp = requests.get(f"{BASE_URL}/api/channels/{ch['id']}", headers=H)
        assert resp.json()["videoCount"] == 1

        # 6. Delete channel
        requests.delete(f"{BASE_URL}/api/channels/{ch['id']}", headers=H)


class TestPlaylistWorkflow:
    def test_playlist_ordering_and_computed(self):
        # 1. Create videos
        v1 = requests.post(f"{BASE_URL}/api/videos", json={"title": "PL1", "duration": 100}, headers=H).json()
        v2 = requests.post(f"{BASE_URL}/api/videos", json={"title": "PL2", "duration": 200}, headers=H).json()
        v3 = requests.post(f"{BASE_URL}/api/videos", json={"title": "PL3", "duration": 150}, headers=H).json()

        # 2. Create playlist
        pl = requests.post(f"{BASE_URL}/api/playlists", json={"name": unique("pl")}, headers=H).json()

        # 3. Add videos with positions
        requests.post(f"{BASE_URL}/api/playlists/{pl['id']}/videos",
                      json={"videoId": v1["id"], "position": 1}, headers=H)
        requests.post(f"{BASE_URL}/api/playlists/{pl['id']}/videos",
                      json={"videoId": v2["id"], "position": 2}, headers=H)
        requests.post(f"{BASE_URL}/api/playlists/{pl['id']}/videos",
                      json={"videoId": v3["id"], "position": 3}, headers=H)

        # 4. Verify computed fields
        resp = requests.get(f"{BASE_URL}/api/playlists/{pl['id']}", headers=H)
        data = resp.json()
        assert data["videoCount"] == 3
        assert data["totalDuration"] == 450

        # 5. Get playlist videos - verify order
        resp = requests.get(f"{BASE_URL}/api/playlists/{pl['id']}/videos", headers=H)
        videos = resp.json()["items"]
        positions = [entry["position"] for entry in videos]
        assert positions == [1, 2, 3]

        # 6. Remove video from playlist
        requests.delete(f"{BASE_URL}/api/playlists/{pl['id']}/videos/{v2['id']}", headers=H)
        resp = requests.get(f"{BASE_URL}/api/playlists/{pl['id']}", headers=H)
        assert resp.json()["videoCount"] == 2
        assert resp.json()["totalDuration"] == 250


class TestDownloadQueueWorkflow:
    def test_download_queue_status_transitions(self):
        # 1. Add items with different priorities
        d1 = requests.post(f"{BASE_URL}/api/downloads", json={
            "url": "https://yt.com/1", "priority": 3
        }, headers=H).json()
        d2 = requests.post(f"{BASE_URL}/api/downloads", json={
            "url": "https://yt.com/2", "priority": 1
        }, headers=H).json()

        assert d1["status"] == "pending"
        assert d2["status"] == "pending"

        # 2. Start download
        resp = requests.put(f"{BASE_URL}/api/downloads/{d2['id']}",
                            json={"status": "downloading"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "downloading"
        assert resp.json()["startedAt"] is not None

        # 3. Complete download
        resp = requests.put(f"{BASE_URL}/api/downloads/{d2['id']}",
                            json={"status": "completed"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completedAt"] is not None

        # 4. Fail another download
        requests.put(f"{BASE_URL}/api/downloads/{d1['id']}",
                     json={"status": "downloading"}, headers=H)
        resp = requests.put(f"{BASE_URL}/api/downloads/{d1['id']}",
                            json={"status": "failed", "errorMessage": "Network error"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["errorMessage"] == "Network error"

        # 5. Retry failed download
        resp = requests.post(f"{BASE_URL}/api/downloads/{d1['id']}/retry", headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"


class TestWatchedWorkflow:
    def test_watch_unwatch_operations(self):
        v1 = requests.post(f"{BASE_URL}/api/videos", json={"title": "W1"}, headers=H).json()
        v2 = requests.post(f"{BASE_URL}/api/videos", json={"title": "W2"}, headers=H).json()

        # Mark as watched
        requests.post(f"{BASE_URL}/api/videos/{v1['id']}/watch", headers=H)
        requests.post(f"{BASE_URL}/api/videos/{v2['id']}/watch", headers=H)

        # Verify
        resp = requests.get(f"{BASE_URL}/api/videos/{v1['id']}", headers=H)
        assert resp.json()["watched"] is True
        resp = requests.get(f"{BASE_URL}/api/videos/{v2['id']}", headers=H)
        assert resp.json()["watched"] is True

        # Unwatch one
        requests.post(f"{BASE_URL}/api/videos/{v1['id']}/unwatch", headers=H)
        resp = requests.get(f"{BASE_URL}/api/videos/{v1['id']}", headers=H)
        assert resp.json()["watched"] is False


class TestVideoTagging:
    def test_tags_stored_correctly(self):
        tag = unique("tag")
        v = requests.post(f"{BASE_URL}/api/videos", json={"title": "Tagged", "tags": [tag, "other"]}, headers=H).json()
        resp = requests.get(f"{BASE_URL}/api/videos/{v['id']}", headers=H)
        assert tag in resp.json()["tags"]
        assert "other" in resp.json()["tags"]
