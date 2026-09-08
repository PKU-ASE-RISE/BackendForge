import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"value-required-{uuid.uuid4().hex}"}


def get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def post(path, headers, json_data=None):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def test_sign_field_requires_value_property_and_does_not_mutate():
    h = headers()
    tag = uuid.uuid4().hex

    doc_resp = post("/api/documents", h, {"title": f"MissingValue-{tag}"})
    assert doc_resp.status_code == 201, doc_resp.text
    doc = doc_resp.json()

    recip_resp = post(
        f"/api/documents/{doc['id']}/recipients",
        h,
        {"name": f"Signer-{tag}", "email": f"mv-{tag}@example.com", "role": "SIGNER"},
    )
    assert recip_resp.status_code == 201, recip_resp.text
    recipient = recip_resp.json()

    field_resp = post(
        f"/api/documents/{doc['id']}/fields",
        h,
        {"type": "TEXT", "recipientId": recipient["id"], "required": True},
    )
    assert field_resp.status_code == 201, field_resp.text
    field = field_resp.json()

    send_resp = post(f"/api/documents/{doc['id']}/send", h)
    assert send_resp.status_code == 200, send_resp.text

    sign_resp = post(
        f"/api/documents/{doc['id']}/signing/{recipient['id']}/fields/{field['id']}",
        h,
        {},
    )

    assert sign_resp.status_code in (400, 422), sign_resp.text
    detail_resp = get(f"/api/documents/{doc['id']}", h)
    assert detail_resp.status_code == 200, detail_resp.text
    stored_field = next(item for item in detail_resp.json()["fields"] if item["id"] == field["id"])
    assert stored_field["value"] is None
    assert stored_field["signedAt"] is None
