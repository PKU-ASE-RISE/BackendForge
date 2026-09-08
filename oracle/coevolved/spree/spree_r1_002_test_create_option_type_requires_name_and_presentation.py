import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def test_create_option_type_requires_name_and_presentation():
    store = f"r1opt{uuid.uuid4().hex[:12]}"
    headers = {"X-Store-Token": f"admin_{store}_admin", "Content-Type": "application/json"}

    response = requests.post(f"{BASE_URL}/api/v1/option-types", headers=headers, json={}, timeout=10)

    assert response.status_code == 422
    assert "error" in response.json()
