import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_settings_rejects_invalid_theme_value():
    original = requests.get(f"{BASE_URL}/api/settings", headers=HEADERS)
    assert original.status_code == 200
    original_settings = original.json()
    original_theme = original_settings["theme"]
    invalid_theme = f"sepia-{uuid.uuid4().hex}"

    try:
        response = requests.put(
            f"{BASE_URL}/api/settings",
            json={"theme": invalid_theme},
            headers=HEADERS,
        )

        reloaded = requests.get(f"{BASE_URL}/api/settings", headers=HEADERS)
        assert reloaded.status_code == 200

        assert response.status_code in (400, 422)
        assert reloaded.json()["theme"] == original_theme
    finally:
        requests.put(f"{BASE_URL}/api/settings", json={"theme": original_theme}, headers=HEADERS)
