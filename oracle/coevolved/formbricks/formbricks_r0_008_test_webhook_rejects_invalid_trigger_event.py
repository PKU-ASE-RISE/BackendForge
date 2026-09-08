import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(env_id, user_id):
    return {
        "X-User-Id": user_id,
        "X-Environment-Id": env_id,
        "Content-Type": "application/json",
    }


def test_webhook_rejects_invalid_trigger_event():
    user_id = str(uuid.uuid4())
    env_id = str(uuid.uuid4())
    hdrs = headers(env_id, user_id)
    token = uuid.uuid4().hex
    invalid_trigger = f"invalidTrigger-{token}"

    created = requests.post(
        f"{BASE_URL}/api/webhooks",
        json={"url": f"https://example.com/hooks/{token}", "triggers": [invalid_trigger]},
        headers=hdrs,
        timeout=30,
    )
    assert created.status_code in (400, 422), created.text

    listed = requests.get(
        f"{BASE_URL}/api/webhooks",
        headers=hdrs,
        timeout=30,
    )
    assert listed.status_code == 200, listed.text
    assert all(invalid_trigger not in webhook.get("triggers", []) for webhook in listed.json())
