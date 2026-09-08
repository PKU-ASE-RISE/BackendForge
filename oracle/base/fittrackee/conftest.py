"""
Conftest for FitTrackee tests - ensures admin user is created first.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True, scope="session")
def ensure_admin_created_first():
    """Ensure the fixed admin user ID is the first user created (becomes admin)."""
    headers = {"X-User-Id": ADMIN_USER_ID, "Content-Type": "application/json"}
    response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers, timeout=30)
    assert response.status_code == 200, (
        f"failed to initialize the deterministic admin user: "
        f"HTTP {response.status_code}: {response.text}"
    )
