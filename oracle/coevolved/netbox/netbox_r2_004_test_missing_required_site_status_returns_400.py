import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {"X-Api-Key": "direct-prober-r2", "Content-Type": "application/json"}


def test_missing_required_site_status_returns_400():
    response = requests.post(
        f"{BASE_URL}/api/dcim/sites/",
        json={"name": f"missing-status-site-{uuid.uuid4().hex[:8]}"},
        headers=HEADERS,
        timeout=30,
    )
    assert response.status_code == 400, response.text
