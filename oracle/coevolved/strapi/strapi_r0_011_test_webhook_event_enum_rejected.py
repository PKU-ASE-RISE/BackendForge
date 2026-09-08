import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def test_webhook_event_enum_rejected():
    suffix = uuid.uuid4().hex[:10]
    resp = requests.post(
        f"{BASE_URL}/webhooks",
        json={
            "name": f"hook_{suffix}",
            "url": f"https://example.com/hooks/{suffix}",
            "events": ["entry.publish"],
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
