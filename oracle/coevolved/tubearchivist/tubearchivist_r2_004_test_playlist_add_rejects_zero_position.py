import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_playlist_add_rejects_zero_position():
    suffix = uuid.uuid4().hex
    playlist_id = None
    video_id = None

    try:
        playlist = requests.post(
            f"{BASE_URL}/api/playlists",
            json={"name": f"zero-position-playlist-{suffix}"},
            headers=HEADERS,
        )
        assert playlist.status_code == 201
        playlist_id = playlist.json()["id"]

        video = requests.post(
            f"{BASE_URL}/api/videos",
            json={"title": f"zero-position-video-{suffix}"},
            headers=HEADERS,
        )
        assert video.status_code == 201
        video_id = video.json()["id"]

        response = requests.post(
            f"{BASE_URL}/api/playlists/{playlist_id}/videos",
            json={"videoId": video_id, "position": 0},
            headers=HEADERS,
        )

        entries_response = requests.get(f"{BASE_URL}/api/playlists/{playlist_id}/videos", headers=HEADERS)
        assert entries_response.status_code == 200
        entries = entries_response.json()["items"]

        assert response.status_code in (400, 422)
        assert all(entry["videoId"] != video_id for entry in entries)
    finally:
        if playlist_id and video_id:
            requests.delete(f"{BASE_URL}/api/playlists/{playlist_id}/videos/{video_id}", headers=HEADERS)
        if playlist_id:
            requests.delete(f"{BASE_URL}/api/playlists/{playlist_id}", headers=HEADERS)
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
