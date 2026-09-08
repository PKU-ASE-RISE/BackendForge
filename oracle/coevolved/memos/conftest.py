"""Shared fixtures for explicitly collected Memos coevolved tests."""

import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def first_user_response():
    """Create the single HOST shared by all explicitly collected files."""
    unique = uuid.uuid4().hex
    return requests.post(
        f"{BASE_URL}/api/users",
        json={
            "username": f"coevolved_host_{unique}",
            "nickname": "Coevolved Test Host",
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
