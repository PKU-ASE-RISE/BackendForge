import os
import uuid

import pytest
import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": f"drp-r2-doc-recipient-{uuid.uuid4().hex}",
}


@pytest.fixture(autouse=True)
def isolate_test_user():
    global HEADERS
    HEADERS = {
        "X-Api-Key": f"drp-r2-doc-recipient-{uuid.uuid4().hex}",
    }


def post(path, json_data=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def get(path):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def create_document():
    response = post("/api/documents", {"title": f"RequiredRecipient-{uuid.uuid4().hex}"})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("omitted_field", ["name", "email", "role"])
def test_document_recipient_requires_required_fields(omitted_field):
    tag = uuid.uuid4().hex
    doc = create_document()
    body = {
        "name": f"Recipient {tag}",
        "email": f"recipient-{tag}@example.com",
        "role": "SIGNER",
    }
    expected_name = body["name"]
    expected_email = body["email"]
    body.pop(omitted_field)

    response = post(f"/api/documents/{doc['id']}/recipients", body)

    assert response.status_code in (400, 422), response.text
    recipients_response = get(f"/api/documents/{doc['id']}/recipients")
    assert recipients_response.status_code == 200, recipients_response.text
    recipients = recipients_response.json()
    assert all(
        recipient["name"] != expected_name and recipient["email"] != expected_email
        for recipient in recipients
    )
