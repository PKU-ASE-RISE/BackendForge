import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"doc-enum-{uuid.uuid4().hex}"}


def get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def post(path, headers, json_data=None):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def create_document(h):
    resp = post("/api/documents", h, {"title": f"EnumDoc-{uuid.uuid4().hex}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_document_recipient_invalid_role_is_rejected():
    h = headers()
    doc = create_document(h)
    invalid_role = f"NOT_A_ROLE_{uuid.uuid4().hex}"

    resp = post(
        f"/api/documents/{doc['id']}/recipients",
        h,
        {"name": "Bad Role", "email": f"bad-role-{uuid.uuid4().hex}@example.com", "role": invalid_role},
    )

    assert resp.status_code in (400, 422), resp.text
    recipients_resp = get(f"/api/documents/{doc['id']}/recipients", h)
    assert recipients_resp.status_code == 200, recipients_resp.text
    assert all(recipient["role"] != invalid_role for recipient in recipients_resp.json())


def test_document_field_invalid_type_is_rejected():
    h = headers()
    doc = create_document(h)
    recipient_resp = post(
        f"/api/documents/{doc['id']}/recipients",
        h,
        {"name": "Signer", "email": f"field-type-{uuid.uuid4().hex}@example.com", "role": "SIGNER"},
    )
    assert recipient_resp.status_code == 201, recipient_resp.text
    recipient = recipient_resp.json()
    invalid_type = f"NOT_A_FIELD_{uuid.uuid4().hex}"

    resp = post(
        f"/api/documents/{doc['id']}/fields",
        h,
        {"type": invalid_type, "recipientId": recipient["id"]},
    )

    assert resp.status_code in (400, 422), resp.text
    fields_resp = get(f"/api/documents/{doc['id']}/fields", h)
    assert fields_resp.status_code == 200, fields_resp.text
    assert all(field["type"] != invalid_type for field in fields_resp.json())
