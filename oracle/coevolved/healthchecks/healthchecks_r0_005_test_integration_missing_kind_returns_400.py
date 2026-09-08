import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_integration_missing_kind_returns_400():
    api_key = f"bf-probe-integration-kind-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    response = requests.post(
        f"{BASE_URL}/api/v1/integrations/",
        json={"name": f"missing-kind-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 400, response.text
