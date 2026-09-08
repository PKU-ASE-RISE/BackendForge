import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_playlist_reorder_rejects_zero_position():
    suffix = uuid.uuid4().hex
    playlist_id = None
    video_ids = []

    try:
        playlist = requests.post(
            f"{BASE_URL}/api/playlists",
            json={"name": f"reorder-zero-playlist-{suffix}"},
            headers=HEADERS,
        )
        assert playlist.status_code == 201
        playlist_id = playlist.json()["id"]

        for index in range(2):
            video = requests.post(
                f"{BASE_URL}/api/videos",
                json={"title": f"reorder-zero-video-{index}-{suffix}"},
                headers=HEADERS,
            )
            assert video.status_code == 201
            video_id = video.json()["id"]
            video_ids.append(video_id)
            added = requests.post(
                f"{BASE_URL}/api/playlists/{playlist_id}/videos",
                json={"videoId": video_id, "position": index + 1},
                headers=HEADERS,
            )
            assert added.status_code == 201

        response = requests.put(
            f"{BASE_URL}/api/playlists/{playlist_id}/videos/{video_ids[1]}/reorder",
            json={"position": 0},
            headers=HEADERS,
        )

        entries_response = requests.get(f"{BASE_URL}/api/playlists/{playlist_id}/videos", headers=HEADERS)
        assert entries_response.status_code == 200
        entries = entries_response.json()["items"]

        assert response.status_code in (400, 422)
        assert [(entry["videoId"], entry["position"]) for entry in entries] == [
            (video_ids[0], 1),
            (video_ids[1], 2),
        ]
    finally:
        if playlist_id:
            for video_id in video_ids:
                requests.delete(f"{BASE_URL}/api/playlists/{playlist_id}/videos/{video_id}", headers=HEADERS)
            requests.delete(f"{BASE_URL}/api/playlists/{playlist_id}", headers=HEADERS)
        for video_id in video_ids:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
