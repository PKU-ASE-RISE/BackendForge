import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def _headers():
    return {
        "X-Api-Key": f"drp-template-rec-email-{uuid.uuid4().hex}",
    }


def _post(path, payload=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def _get(path, headers=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_template_recipient_requires_email():
    headers = _headers()
    tag = uuid.uuid4().hex
    template_resp = _post("/api/templates", {"title": f"template-required-email-{tag}"}, headers)
    assert template_resp.status_code == 201, template_resp.text
    template_id = template_resp.json()["id"]

    bad_resp = _post(
        f"/api/templates/{template_id}/recipients",
        {"name": f"No Email {tag}", "role": "SIGNER"},
        headers,
    )
    assert 400 <= bad_resp.status_code < 500, bad_resp.text

    detail_resp = _get(f"/api/templates/{template_id}", headers)
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["recipients"] == []
