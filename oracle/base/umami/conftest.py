"""Deterministic first-user setup for the explicitly collected Umami base tests."""

import os

import pytest
import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
ADMIN_HEADERS = {"X-Api-Key": "admin-user", "Content-Type": "application/json"}


@pytest.fixture(scope="session", autouse=True)
def initialize_admin_first():
    requests.get(f"{BASE_URL}/api/me", headers=ADMIN_HEADERS, timeout=30)
