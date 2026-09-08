import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers(label):
    return {"X-Api-Key": f"{label}-{uuid.uuid4().hex}"}


def get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def post(path, headers, json_data=None):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def make_pending_document(owner_headers):
    tag = uuid.uuid4().hex
    doc_resp = post("/api/documents", owner_headers, {"title": f"ScopedSign-{tag}"})
    assert doc_resp.status_code == 201, doc_resp.text
    doc = doc_resp.json()

    recip_resp = post(
        f"/api/documents/{doc['id']}/recipients",
        owner_headers,
        {"name": f"Signer-{tag}", "email": f"signer-{tag}@example.com", "role": "SIGNER"},
    )
    assert recip_resp.status_code == 201, recip_resp.text
    recipient = recip_resp.json()

    field_resp = post(
        f"/api/documents/{doc['id']}/fields",
        owner_headers,
        {"type": "SIGNATURE", "recipientId": recipient["id"], "required": True},
    )
    assert field_resp.status_code == 201, field_resp.text
    field = field_resp.json()

    send_resp = post(f"/api/documents/{doc['id']}/send", owner_headers)
    assert send_resp.status_code == 200, send_resp.text
    assert send_resp.json()["status"] == "PENDING"
    return doc, recipient, field


def field_from_detail(doc_id, field_id, owner_headers):
    detail_resp = get(f"/api/documents/{doc_id}", owner_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    return next(field for field in detail_resp.json()["fields"] if field["id"] == field_id)


def recipient_from_detail(doc_id, recipient_id, owner_headers):
    detail_resp = get(f"/api/documents/{doc_id}", owner_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    return next(recipient for recipient in detail_resp.json()["recipients"] if recipient["id"] == recipient_id)


def test_other_user_cannot_sign_field_on_owned_document():
    owner_headers = headers("owner-sign-field")
    intruder_headers = headers("intruder-sign-field")
    doc, recipient, field = make_pending_document(owner_headers)
    value = f"unauthorized-{uuid.uuid4().hex}"

    resp = post(
        f"/api/documents/{doc['id']}/signing/{recipient['id']}/fields/{field['id']}",
        intruder_headers,
        {"value": value},
    )

    assert resp.status_code == 404, resp.text
    stored_field = field_from_detail(doc["id"], field["id"], owner_headers)
    assert stored_field["value"] is None
    assert stored_field["signedAt"] is None


def test_other_user_cannot_complete_owned_document_recipient():
    owner_headers = headers("owner-complete")
    intruder_headers = headers("intruder-complete")
    doc, recipient, field = make_pending_document(owner_headers)

    sign_resp = post(
        f"/api/documents/{doc['id']}/signing/{recipient['id']}/fields/{field['id']}",
        owner_headers,
        {"value": f"owner-signed-{uuid.uuid4().hex}"},
    )
    assert sign_resp.status_code == 200, sign_resp.text

    resp = post(f"/api/documents/{doc['id']}/signing/{recipient['id']}/complete", intruder_headers)

    assert resp.status_code == 404, resp.text
    detail_resp = get(f"/api/documents/{doc['id']}", owner_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "PENDING"
    assert recipient_from_detail(doc["id"], recipient["id"], owner_headers)["status"] == "PENDING"


def test_other_user_cannot_reject_owned_document():
    owner_headers = headers("owner-reject")
    intruder_headers = headers("intruder-reject")
    doc, recipient, _field = make_pending_document(owner_headers)

    resp = post(f"/api/documents/{doc['id']}/signing/{recipient['id']}/reject", intruder_headers, {"reason": "no access"})

    assert resp.status_code == 404, resp.text
    detail_resp = get(f"/api/documents/{doc['id']}", owner_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "PENDING"
    assert recipient_from_detail(doc["id"], recipient["id"], owner_headers)["status"] == "PENDING"
