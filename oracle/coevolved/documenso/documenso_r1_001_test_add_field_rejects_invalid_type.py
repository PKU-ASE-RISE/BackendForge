import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def _headers():
    return {
        "X-Api-Key": f"drp-field-invalid-type-{uuid.uuid4().hex}",
    }


def _post(path, payload=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_add_field_rejects_invalid_type():
    headers = _headers()
    tag = uuid.uuid4().hex
    doc_resp = _post("/api/documents", {"title": f"invalid-field-type-{tag}"}, headers)
    assert doc_resp.status_code == 201, doc_resp.text
    doc_id = doc_resp.json()["id"]

    recipient_resp = _post(
        f"/api/documents/{doc_id}/recipients",
        {"name": f"Signer {tag}", "email": f"signer-{tag}@example.com", "role": "SIGNER"},
        headers,
    )
    assert recipient_resp.status_code == 201, recipient_resp.text
    recipient_id = recipient_resp.json()["id"]

    bad_resp = _post(
        f"/api/documents/{doc_id}/fields",
        {"type": "INITIALS", "recipientId": recipient_id, "page": 1},
        headers,
    )
    assert 400 <= bad_resp.status_code < 500, bad_resp.text

    fields_resp = _get(f"/api/documents/{doc_id}/fields", headers)
    assert fields_resp.status_code == 200, fields_resp.text
    assert all(field["type"] != "INITIALS" for field in fields_resp.json())
