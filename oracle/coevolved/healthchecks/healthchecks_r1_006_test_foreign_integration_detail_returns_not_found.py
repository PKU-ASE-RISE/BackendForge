import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def test_foreign_integration_detail_returns_not_found():
    owner_key = f"bf-probe-integration-owner-{uuid.uuid4().hex}"
    other_key = f"bf-probe-integration-other-{uuid.uuid4().hex}"
    owner_headers = _headers(owner_key)
    other_headers = _headers(other_key)

    created = requests.post(
        f"{BASE_URL}/api/v1/integrations/",
        json={
            "kind": "webhook",
            "name": f"foreign-integration-{uuid.uuid4().hex}",
            "webhook_url": f"https://example.com/{uuid.uuid4().hex}",
        },
        headers=owner_headers,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    integration_id = created.json()["id"]

    foreign_get = requests.get(f"{BASE_URL}/api/v1/integrations/{integration_id}", headers=other_headers, timeout=30)
    assert foreign_get.status_code == 404, foreign_get.text

    other_list = requests.get(f"{BASE_URL}/api/v1/integrations/", headers=other_headers, timeout=30)
    assert other_list.status_code == 200, other_list.text
    assert integration_id not in {integration["id"] for integration in other_list.json()["integrations"]}

    owner_get = requests.get(f"{BASE_URL}/api/v1/integrations/{integration_id}", headers=owner_headers, timeout=30)
    assert owner_get.status_code == 200, owner_get.text
    assert owner_get.json()["id"] == integration_id
