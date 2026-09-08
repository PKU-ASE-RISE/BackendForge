import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": f"drp-r2-doc-field-type-{uuid.uuid4().hex}",
}


def post(path, json_data=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_document_field_requires_type():
    tag = uuid.uuid4().hex
    doc_response = post("/api/documents", {"title": f"FieldType-{tag}"})
    assert doc_response.status_code == 201, doc_response.text
    doc = doc_response.json()

    recipient_response = post(
        f"/api/documents/{doc['id']}/recipients",
        {"name": f"Signer {tag}", "email": f"signer-{tag}@example.com", "role": "SIGNER"},
    )
    assert recipient_response.status_code == 201, recipient_response.text
    recipient = recipient_response.json()

    response = post(
        f"/api/documents/{doc['id']}/fields",
        {
            "recipientId": recipient["id"],
            "page": 1,
            "positionX": 10,
            "positionY": 20,
            "width": 100,
            "height": 30,
        },
    )

    assert response.status_code in (400, 422), response.text
    fields_response = get(f"/api/documents/{doc['id']}/fields")
    assert fields_response.status_code == 200, fields_response.text
    assert fields_response.json() == []
