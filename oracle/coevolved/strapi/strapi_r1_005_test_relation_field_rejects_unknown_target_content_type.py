import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def test_relation_field_rejects_unknown_target_content_type():
    content_type_name = f"ct_{uuid.uuid4().hex[:10]}"
    missing_target = f"missing_{uuid.uuid4().hex[:10]}"

    create_resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": content_type_name, "displayName": "Relation Holder"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert create_resp.status_code == 201, create_resp.text
    content_type_id = create_resp.json()["data"]["id"]

    resp = requests.post(
        f"{BASE_URL}/content-types/{content_type_id}/fields",
        json={
            "name": "bad_relation",
            "type": "relation",
            "target": missing_target,
            "relationType": "oneToOne",
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["status"] == 400
