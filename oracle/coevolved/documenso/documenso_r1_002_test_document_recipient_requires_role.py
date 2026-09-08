import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def _headers():
    return {
        "X-Api-Key": f"drp-doc-rec-role-{uuid.uuid4().hex}",
    }


def _post(path, payload=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_document_recipient_requires_role():
    headers = _headers()
    tag = uuid.uuid4().hex
    doc_resp = _post("/api/documents", {"title": f"recipient-required-role-{tag}"}, headers)
    assert doc_resp.status_code == 201, doc_resp.text
    doc_id = doc_resp.json()["id"]

    email = f"missing-role-{tag}@example.com"
    bad_resp = _post(
        f"/api/documents/{doc_id}/recipients",
        {"name": f"Missing Role {tag}", "email": email},
        headers,
    )
    assert 400 <= bad_resp.status_code < 500, bad_resp.text

    recipients_resp = _get(f"/api/documents/{doc_id}/recipients", headers)
    assert recipients_resp.status_code == 200, recipients_resp.text
    assert all(recipient["email"] != email for recipient in recipients_resp.json())
