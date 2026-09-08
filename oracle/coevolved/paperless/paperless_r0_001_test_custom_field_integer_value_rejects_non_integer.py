import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"drp-cf-int-value-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_custom_field_integer_value_rejects_non_integer():
    h = headers()
    field_resp = requests.post(
        f"{BASE_URL}/api/custom_fields/",
        json={"name": f"int-field-{uuid.uuid4().hex}", "data_type": "integer"},
        headers=h,
        timeout=30,
    )
    assert field_resp.status_code == 201, field_resp.text
    field_id = field_resp.json()["id"]
    title = f"bad-int-cf-{uuid.uuid4().hex}"

    resp = requests.post(
        f"{BASE_URL}/api/documents/",
        json={
            "title": title,
            "content": "contains an invalid integer custom field value",
            "custom_fields": [{"field": field_id, "value": "hello"}],
        },
        headers=h,
        timeout=30,
    )

    assert resp.status_code == 400, resp.text

    listed = requests.get(
        f"{BASE_URL}/api/documents/",
        params={"title__icontains": title},
        headers=h,
        timeout=30,
    )
    assert listed.status_code == 200
    assert all(doc["title"] != title for doc in listed.json()["results"])
