import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"tmpl-enum-{uuid.uuid4().hex}"}


def get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def post(path, headers, json_data=None):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def create_template(h):
    resp = post("/api/templates", h, {"title": f"EnumTemplate-{uuid.uuid4().hex}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_template_recipient_invalid_role_is_rejected():
    h = headers()
    template = create_template(h)
    invalid_role = f"NOT_A_TEMPLATE_ROLE_{uuid.uuid4().hex}"

    resp = post(
        f"/api/templates/{template['id']}/recipients",
        h,
        {"name": "Bad Template Role", "email": f"bad-template-role-{uuid.uuid4().hex}@example.com", "role": invalid_role},
    )

    assert resp.status_code in (400, 422), resp.text
    detail_resp = get(f"/api/templates/{template['id']}", h)
    assert detail_resp.status_code == 200, detail_resp.text
    assert all(recipient["role"] != invalid_role for recipient in detail_resp.json()["recipients"])


def test_template_field_invalid_type_is_rejected():
    h = headers()
    template = create_template(h)
    recipient_resp = post(
        f"/api/templates/{template['id']}/recipients",
        h,
        {"name": "Signer", "email": f"template-field-type-{uuid.uuid4().hex}@example.com", "role": "SIGNER"},
    )
    assert recipient_resp.status_code == 201, recipient_resp.text
    recipient = recipient_resp.json()
    invalid_type = f"NOT_A_TEMPLATE_FIELD_{uuid.uuid4().hex}"

    resp = post(
        f"/api/templates/{template['id']}/fields",
        h,
        {"type": invalid_type, "recipientId": recipient["id"]},
    )

    assert resp.status_code in (400, 422), resp.text
    detail_resp = get(f"/api/templates/{template['id']}", h)
    assert detail_resp.status_code == 200, detail_resp.text
    assert all(field["type"] != invalid_type for field in detail_resp.json()["fields"])
