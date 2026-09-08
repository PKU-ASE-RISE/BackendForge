import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def _headers():
    return {
        "X-Api-Key": f"drp-template-field-type-{uuid.uuid4().hex}",
    }


def _post(path, payload=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_template_field_requires_type():
    headers = _headers()
    tag = uuid.uuid4().hex
    template_resp = _post("/api/templates", {"title": f"template-field-required-type-{tag}"}, headers)
    assert template_resp.status_code == 201, template_resp.text
    template_id = template_resp.json()["id"]

    recipient_resp = _post(
        f"/api/templates/{template_id}/recipients",
        {"name": f"Template Signer {tag}", "email": f"tmpl-signer-{tag}@example.com", "role": "SIGNER"},
        headers,
    )
    assert recipient_resp.status_code == 201, recipient_resp.text
    recipient_id = recipient_resp.json()["id"]

    bad_resp = _post(
        f"/api/templates/{template_id}/fields",
        {"recipientId": recipient_id, "page": 1, "positionX": 10, "positionY": 20},
        headers,
    )
    assert 400 <= bad_resp.status_code < 500, bad_resp.text

    detail_resp = _get(f"/api/templates/{template_id}", headers)
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["fields"] == []
