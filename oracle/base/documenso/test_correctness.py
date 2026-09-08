"""
BackendForge — Comprehensive Correctness Tests for Documenso Task

Tests business rules: document lifecycle, signing workflow, signing order enforcement,
status transitions, template instantiation, field signing, and data isolation.

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")

# API keys — the key IS the user identifier (auto-created on first request)
USER1_KEY = f"user1-{uuid.uuid4().hex[:8]}"
USER2_KEY = f"user2-{uuid.uuid4().hex[:8]}"

USER1_HEADERS = {
    "X-Api-Key": USER1_KEY,
}

USER2_HEADERS = {
    "X-Api-Key": USER2_KEY,
}

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def isolate_test_users():
    """Give every item fresh user namespaces so persisted state cannot cross tests."""
    global USER1_KEY, USER2_KEY, USER1_HEADERS, USER2_HEADERS, UNIQUE

    run_id = uuid.uuid4().hex
    USER1_KEY = f"user1-{run_id}"
    USER2_KEY = f"user2-{run_id}"
    USER1_HEADERS = {"X-Api-Key": USER1_KEY}
    USER2_HEADERS = {"X-Api-Key": USER2_KEY}
    UNIQUE = run_id[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = USER1_HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


def require_status(response, expected, action):
    """Validate a prerequisite request before its result is used by a test."""
    assert response.status_code == expected, (
        f"{action}: expected {expected}, got {response.status_code}: {response.text}"
    )
    return response


# ── Helpers to set up common test scenarios ──

def create_document(title=None, headers=None):
    """Create a document and return its data."""
    title = title or f"Doc-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/documents", {"title": title, "message": "Test message"}, headers=headers)
    assert resp.status_code == 201, f"Failed to create document: {resp.text}"
    return resp.json()


def create_template(title=None, message=None, headers=None):
    """Create a template and return its data."""
    body = {"title": title or f"Template-{uuid.uuid4().hex[:8]}"}
    if message is not None:
        body["message"] = message
    resp = api_post("/api/templates", body, headers=headers)
    assert resp.status_code == 201, f"Failed to create template: {resp.text}"
    return resp.json()


def create_token(name=None, headers=None):
    """Create an API token and return its data."""
    body = {"name": name or f"Token-{uuid.uuid4().hex[:8]}"}
    resp = api_post("/api/tokens", body, headers=headers)
    assert resp.status_code == 201, f"Failed to create API token: {resp.text}"
    return resp.json()


def add_recipient(doc_id, email=None, name=None, role="SIGNER", signing_order=None, headers=None):
    """Add a recipient to a document."""
    email = email or f"{uuid.uuid4().hex[:8]}@example.com"
    name = name or f"Recipient-{uuid.uuid4().hex[:8]}"
    body = {"email": email, "name": name, "role": role}
    if signing_order is not None:
        body["signingOrder"] = signing_order
    resp = api_post(f"/api/documents/{doc_id}/recipients", body, headers=headers)
    assert resp.status_code == 201, f"Failed to add recipient: {resp.text}"
    return resp.json()


def add_field(doc_id, recipient_id, field_type="SIGNATURE", required=True, headers=None):
    """Add a field to a document."""
    body = {
        "type": field_type,
        "recipientId": recipient_id,
        "required": required,
        "page": 1,
        "positionX": 100,
        "positionY": 200,
        "width": 150,
        "height": 50,
    }
    resp = api_post(f"/api/documents/{doc_id}/fields", body, headers=headers)
    assert resp.status_code == 201, f"Failed to add field: {resp.text}"
    return resp.json()


def send_document(doc_id, headers=None):
    """Send a document."""
    resp = api_post(f"/api/documents/{doc_id}/send", headers=headers)
    assert resp.status_code == 200, f"Failed to send document: {resp.text}"
    return resp.json()


def setup_signable_document(headers=None):
    """Create a document with one signer + one field, then send it. Returns (doc, recipient, field)."""
    doc = create_document(headers=headers)
    recip = add_recipient(doc["id"], role="SIGNER", headers=headers)
    field = add_field(doc["id"], recip["id"], headers=headers)
    sent_doc = send_document(doc["id"], headers=headers)
    return sent_doc, recip, field


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/documents", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_templates(self):
        resp = requests.get(f"{BASE_URL}/api/templates", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_tokens(self):
        resp = requests.get(f"{BASE_URL}/api/tokens", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_user(self):
        """A new key should auto-create a user."""
        new_key = f"new-user-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": new_key}
        resp = api_get("/api/me", headers=headers)
        assert resp.status_code == 200
        user = resp.json()
        assert "id" in user
        assert "email" in user
        assert "name" in user

    def test_same_key_same_user(self):
        """Same key should return same user."""
        resp1 = api_get("/api/me", headers=USER1_HEADERS)
        resp2 = api_get("/api/me", headers=USER1_HEADERS)
        require_status(resp1, 200, "First profile request failed")
        require_status(resp2, 200, "Second profile request failed")
        assert resp1.json()["id"] == resp2.json()["id"]


# ════════════════════════════════════════════════════════════════════
# PART 2: Document CRUD
# ════════════════════════════════════════════════════════════════════


class TestDocumentCRUD:

    def test_create_document(self):
        resp = api_post("/api/documents", {"title": f"TestDoc-{UNIQUE}", "message": "Hello"})
        assert resp.status_code == 201
        doc = resp.json()
        assert doc["title"] == f"TestDoc-{UNIQUE}"
        assert doc["message"] == "Hello"
        assert doc["status"] == "DRAFT"
        assert "id" in doc
        assert "createdAt" in doc
        assert "updatedAt" in doc

    def test_create_document_without_message(self):
        resp = api_post("/api/documents", {"title": f"NoMsg-{UNIQUE}"})
        assert resp.status_code == 201
        doc = resp.json()
        assert doc["title"] == f"NoMsg-{UNIQUE}"

    def test_create_document_missing_title(self):
        resp = api_post("/api/documents", {"message": "no title"})
        assert resp.status_code in [400, 422]

    def test_get_document(self):
        doc = create_document()
        resp = api_get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == doc["id"]
        assert detail["title"] == doc["title"]
        assert "recipients" in detail
        assert "fields" in detail
        assert isinstance(detail["recipients"], list)
        assert isinstance(detail["fields"], list)

    def test_update_document(self):
        doc = create_document()
        resp = api_put(f"/api/documents/{doc['id']}", {"title": "Updated Title", "message": "Updated msg"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated Title"
        assert updated["message"] == "Updated msg"

    def test_delete_document(self):
        doc = create_document()
        resp = api_delete(f"/api/documents/{doc['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = api_get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 404

    def test_get_nonexistent_document(self):
        resp = api_get("/api/documents/999999")
        assert resp.status_code == 404

    def test_list_documents(self):
        create_document(title=f"List-{UNIQUE}")
        resp = api_get("/api/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 1
        # Check pagination structure
        pag = data["pagination"]
        assert "page" in pag
        assert "perPage" in pag
        assert "totalItems" in pag
        assert "totalPages" in pag

    def test_list_documents_status_filter(self):
        create_document(title=f"FilterDoc-{UNIQUE}")
        resp = api_get("/api/documents", params={"status": "DRAFT"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "DRAFT"

    def test_list_documents_pagination(self):
        # Create enough documents
        for i in range(3):
            create_document(title=f"Page-{UNIQUE}-{i}")
        resp = api_get("/api/documents", params={"page": 1, "perPage": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["pagination"]["perPage"] == 2


# ════════════════════════════════════════════════════════════════════
# PART 3: Document Lifecycle
# ════════════════════════════════════════════════════════════════════


class TestDocumentLifecycle:

    def test_send_document(self):
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])

        resp = api_post(f"/api/documents/{doc['id']}/send")
        assert resp.status_code == 200
        sent = resp.json()
        assert sent["status"] == "PENDING"

    def test_send_requires_draft_status(self):
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        send_document(doc["id"])

        # Try to send again
        resp = api_post(f"/api/documents/{doc['id']}/send")
        assert resp.status_code == 400

    def test_send_requires_signers(self):
        """Cannot send document with no signers/approvers."""
        doc = create_document()
        # Add only a viewer
        recip = add_recipient(doc["id"], role="VIEWER")
        add_field(doc["id"], recip["id"])

        resp = api_post(f"/api/documents/{doc['id']}/send")
        assert resp.status_code == 400

    def test_send_requires_fields(self):
        """Cannot send document with no fields."""
        doc = create_document()
        add_recipient(doc["id"], role="SIGNER")
        # No fields added

        resp = api_post(f"/api/documents/{doc['id']}/send")
        assert resp.status_code == 400

    def test_cancel_document(self):
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        send_document(doc["id"])

        resp = api_post(f"/api/documents/{doc['id']}/cancel")
        assert resp.status_code == 200
        cancelled = resp.json()
        assert cancelled["status"] == "DRAFT"

    def test_cancel_requires_pending(self):
        """Cannot cancel a DRAFT document."""
        doc = create_document()
        resp = api_post(f"/api/documents/{doc['id']}/cancel")
        assert resp.status_code == 400

    def test_cancel_resets_recipient_statuses(self):
        """After cancel, recipient statuses should reset to PENDING."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        send_document(doc["id"])

        # Cancel
        require_status(
            api_post(f"/api/documents/{doc['id']}/cancel"),
            200,
            "Failed to cancel document",
        )

        # Check recipients
        resp = api_get(f"/api/documents/{doc['id']}/recipients")
        assert resp.status_code == 200
        recipients = resp.json()
        for r in recipients:
            assert r["status"] == "PENDING"

    def test_cannot_update_non_draft_document(self):
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        send_document(doc["id"])

        resp = api_put(f"/api/documents/{doc['id']}", {"title": "New Title"})
        assert resp.status_code == 400

    def test_cannot_delete_non_draft_document(self):
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        send_document(doc["id"])

        resp = api_delete(f"/api/documents/{doc['id']}")
        assert resp.status_code == 400

    def test_viewers_auto_completed_on_send(self):
        """VIEWER recipients should be automatically COMPLETED when document is sent."""
        doc = create_document()
        signer = add_recipient(doc["id"], role="SIGNER")
        viewer = add_recipient(doc["id"], role="VIEWER")
        add_field(doc["id"], signer["id"])
        send_document(doc["id"])

        # Check viewer status
        resp = api_get(f"/api/documents/{doc['id']}/recipients")
        require_status(resp, 200, "Failed to list recipients")
        recipients = resp.json()
        viewer_rec = next(r for r in recipients if r["id"] == viewer["id"])
        assert viewer_rec["status"] == "COMPLETED"


# ════════════════════════════════════════════════════════════════════
# PART 4: Recipients CRUD
# ════════════════════════════════════════════════════════════════════


class TestRecipientsCRUD:

    def test_add_recipient(self):
        doc = create_document()
        resp = api_post(f"/api/documents/{doc['id']}/recipients", {
            "name": "Alice",
            "email": "alice@example.com",
            "role": "SIGNER",
            "signingOrder": 1,
        })
        assert resp.status_code == 201
        recip = resp.json()
        assert recip["name"] == "Alice"
        assert recip["email"] == "alice@example.com"
        assert recip["role"] == "SIGNER"
        assert recip["signingOrder"] == 1
        assert recip["documentId"] == doc["id"]
        assert "id" in recip

    def test_list_recipients(self):
        doc = create_document()
        add_recipient(doc["id"], name="Bob", email="bob@example.com")
        resp = api_get(f"/api/documents/{doc['id']}/recipients")
        assert resp.status_code == 200
        recipients = resp.json()
        assert isinstance(recipients, list)
        assert len(recipients) >= 1

    def test_update_recipient(self):
        doc = create_document()
        recip = add_recipient(doc["id"], name="Charlie", email="charlie@example.com")
        resp = api_put(f"/api/documents/{doc['id']}/recipients/{recip['id']}", {
            "name": "Charles",
            "email": "charles@example.com",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == "Charles"
        assert updated["email"] == "charles@example.com"

    def test_delete_recipient(self):
        doc = create_document()
        recip = add_recipient(doc["id"])
        resp = api_delete(f"/api/documents/{doc['id']}/recipients/{recip['id']}")
        assert resp.status_code == 204

        # Verify deleted
        resp = api_get(f"/api/documents/{doc['id']}/recipients")
        require_status(resp, 200, "Failed to list recipients")
        ids = [r["id"] for r in resp.json()]
        assert recip["id"] not in ids

    def test_cannot_add_recipient_to_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_post(f"/api/documents/{doc['id']}/recipients", {
            "name": "Late",
            "email": "late@example.com",
            "role": "SIGNER",
        })
        assert resp.status_code == 400

    def test_cannot_update_recipient_on_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_put(f"/api/documents/{doc['id']}/recipients/{recip['id']}", {
            "name": "Changed",
        })
        assert resp.status_code == 400

    def test_cannot_delete_recipient_on_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_delete(f"/api/documents/{doc['id']}/recipients/{recip['id']}")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 5: Fields CRUD
# ════════════════════════════════════════════════════════════════════


class TestFieldsCRUD:

    def test_add_field(self):
        doc = create_document()
        recip = add_recipient(doc["id"])
        resp = api_post(f"/api/documents/{doc['id']}/fields", {
            "type": "SIGNATURE",
            "recipientId": recip["id"],
            "required": True,
            "page": 1,
            "positionX": 50,
            "positionY": 100,
            "width": 200,
            "height": 60,
        })
        assert resp.status_code == 201
        field = resp.json()
        assert field["type"] == "SIGNATURE"
        assert field["recipientId"] == recip["id"]
        assert field["required"] is True
        assert field["page"] == 1
        assert field["positionX"] == 50
        assert field["positionY"] == 100
        assert field["width"] == 200
        assert field["height"] == 60
        assert field["documentId"] == doc["id"]
        assert "id" in field

    def test_add_field_types(self):
        """All field types should be accepted."""
        doc = create_document()
        recip = add_recipient(doc["id"])
        for ftype in ["SIGNATURE", "TEXT", "DATE", "CHECKBOX"]:
            resp = api_post(f"/api/documents/{doc['id']}/fields", {
                "type": ftype,
                "recipientId": recip["id"],
            })
            assert resp.status_code == 201, f"Failed for type {ftype}: {resp.text}"
            assert resp.json()["type"] == ftype

    def test_add_field_invalid_recipient(self):
        doc = create_document()
        resp = api_post(f"/api/documents/{doc['id']}/fields", {
            "type": "SIGNATURE",
            "recipientId": 999999,
        })
        assert resp.status_code == 400

    def test_list_fields(self):
        doc = create_document()
        recip = add_recipient(doc["id"])
        add_field(doc["id"], recip["id"])
        resp = api_get(f"/api/documents/{doc['id']}/fields")
        assert resp.status_code == 200
        fields = resp.json()
        assert isinstance(fields, list)
        assert len(fields) >= 1

    def test_update_field(self):
        doc = create_document()
        recip = add_recipient(doc["id"])
        field = add_field(doc["id"], recip["id"])
        resp = api_put(f"/api/documents/{doc['id']}/fields/{field['id']}", {
            "positionX": 300,
            "positionY": 400,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["positionX"] == 300
        assert updated["positionY"] == 400

    def test_delete_field(self):
        doc = create_document()
        recip = add_recipient(doc["id"])
        field = add_field(doc["id"], recip["id"])
        resp = api_delete(f"/api/documents/{doc['id']}/fields/{field['id']}")
        assert resp.status_code == 204

    def test_cannot_add_field_to_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_post(f"/api/documents/{doc['id']}/fields", {
            "type": "TEXT",
            "recipientId": recip["id"],
        })
        assert resp.status_code == 400

    def test_cannot_update_field_on_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_put(f"/api/documents/{doc['id']}/fields/{field['id']}", {
            "positionX": 999,
        })
        assert resp.status_code == 400

    def test_cannot_delete_field_on_non_draft(self):
        doc, recip, field = setup_signable_document()
        resp = api_delete(f"/api/documents/{doc['id']}/fields/{field['id']}")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 6: Field Signing
# ════════════════════════════════════════════════════════════════════


class TestFieldSigning:

    def test_sign_field(self):
        doc, recip, field = setup_signable_document()
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
            {"value": "John Doe Signature"},
        )
        assert resp.status_code == 200
        signed_field = resp.json()
        assert signed_field["value"] == "John Doe Signature"
        assert signed_field["signedAt"] is not None

    def test_cannot_sign_field_twice(self):
        doc, recip, field = setup_signable_document()
        # Sign once
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": "Signature 1"},
            ),
            200,
            "Initial field signing failed",
        )
        # Try again
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
            {"value": "Signature 2"},
        )
        assert resp.status_code == 400

    def test_cannot_sign_others_field(self):
        """A recipient cannot sign a field assigned to another recipient."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="Signer1", email="s1@example.com")
        recip2 = add_recipient(doc["id"], role="SIGNER", name="Signer2", email="s2@example.com")
        field1 = add_field(doc["id"], recip1["id"])
        add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # recip2 tries to sign recip1's field
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field1['id']}",
            {"value": "Sneaky"},
        )
        assert resp.status_code == 403

    def test_cannot_sign_on_draft_document(self):
        """Cannot sign fields if document is not PENDING."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        field = add_field(doc["id"], recip["id"])
        # Document is still DRAFT — not sent

        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
            {"value": "Too early"},
        )
        assert resp.status_code == 400

    def test_cannot_sign_on_rejected_document(self):
        """Cannot sign fields after document is rejected."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="S1", email="s1r@example.com")
        recip2 = add_recipient(doc["id"], role="SIGNER", name="S2", email="s2r@example.com")
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # recip1 rejects
        require_status(
            api_post(f"/api/documents/{doc['id']}/signing/{recip1['id']}/reject"),
            200,
            "Failed to reject document",
        )

        # recip2 tries to sign
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field2['id']}",
            {"value": "Too late"},
        )
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 7: Signing Completion
# ════════════════════════════════════════════════════════════════════


class TestSigningCompletion:

    def test_complete_signing(self):
        doc, recip, field = setup_signable_document()
        # Sign the field first
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": "My Signature"},
            ),
            200,
            "Field signing prerequisite failed",
        )
        # Now complete
        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert resp.status_code == 200
        result = resp.json()
        assert result["recipient"]["status"] == "COMPLETED"

    def test_complete_requires_all_required_fields_signed(self):
        """Cannot complete if required fields are unsigned."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"], field_type="SIGNATURE", required=True)
        add_field(doc["id"], recip["id"], field_type="TEXT", required=True)
        send_document(doc["id"])

        # Only sign one field — shouldn't be able to complete
        fields_resp = api_get(f"/api/documents/{doc['id']}/fields")
        require_status(fields_resp, 200, "Failed to list document fields")
        fields = fields_resp.json()
        first_field = fields[0]
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{first_field['id']}",
                {"value": "Partial"},
            ),
            200,
            "Partial field signing failed",
        )

        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert resp.status_code == 400

    def test_document_completed_when_all_signers_done(self):
        """Document becomes COMPLETED when all signers/approvers complete."""
        doc = create_document()
        signer = add_recipient(doc["id"], role="SIGNER", name="OnlySigner", email="only@example.com")
        field = add_field(doc["id"], signer["id"])
        send_document(doc["id"])

        # Sign and complete
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{signer['id']}/fields/{field['id']}",
                {"value": "Done"},
            ),
            200,
            "Field signing prerequisite failed",
        )
        resp = api_post(f"/api/documents/{doc['id']}/signing/{signer['id']}/complete")
        assert resp.status_code == 200
        result = resp.json()
        assert result["document"]["status"] == "COMPLETED"

    def test_document_not_completed_until_all_signers_done(self):
        """With multiple signers, document stays PENDING until all complete."""
        doc = create_document()
        signer1 = add_recipient(doc["id"], role="SIGNER", name="S1", email="s1c@example.com")
        signer2 = add_recipient(doc["id"], role="SIGNER", name="S2", email="s2c@example.com")
        field1 = add_field(doc["id"], signer1["id"])
        field2 = add_field(doc["id"], signer2["id"])
        send_document(doc["id"])

        # Signer1 signs and completes
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{signer1['id']}/fields/{field1['id']}",
                {"value": "S1 sig"},
            ),
            200,
            "First signer field signing failed",
        )
        resp = api_post(f"/api/documents/{doc['id']}/signing/{signer1['id']}/complete")
        assert resp.status_code == 200
        result = resp.json()
        # Document should still be PENDING
        assert result["document"]["status"] == "PENDING"

        # Signer2 signs and completes
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{signer2['id']}/fields/{field2['id']}",
                {"value": "S2 sig"},
            ),
            200,
            "Second signer field signing failed",
        )
        resp = api_post(f"/api/documents/{doc['id']}/signing/{signer2['id']}/complete")
        assert resp.status_code == 200
        result = resp.json()
        # Now document should be COMPLETED
        assert result["document"]["status"] == "COMPLETED"

    def test_cannot_complete_twice(self):
        """A recipient that already completed cannot complete again."""
        doc, recip, field = setup_signable_document()
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": "Done"},
            ),
            200,
            "Field signing prerequisite failed",
        )
        require_status(
            api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete"),
            200,
            "Initial completion failed",
        )

        # Try again
        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert resp.status_code == 400

    def test_viewer_cannot_complete(self):
        """VIEWER recipients cannot manually complete (they're auto-completed on send)."""
        doc = create_document()
        signer = add_recipient(doc["id"], role="SIGNER", name="S", email="sv@example.com")
        viewer = add_recipient(doc["id"], role="VIEWER", name="V", email="vv@example.com")
        add_field(doc["id"], signer["id"])
        send_document(doc["id"])

        resp = api_post(f"/api/documents/{doc['id']}/signing/{viewer['id']}/complete")
        assert resp.status_code == 400

    def test_approver_can_complete_without_fields(self):
        """APPROVER can complete even without fields (they approve, not sign)."""
        doc = create_document()
        signer = add_recipient(doc["id"], role="SIGNER", name="Signer", email="sap@example.com")
        approver = add_recipient(doc["id"], role="APPROVER", name="Approver", email="aap@example.com")
        field = add_field(doc["id"], signer["id"])
        send_document(doc["id"])

        # Approver completes (no fields assigned to them)
        resp = api_post(f"/api/documents/{doc['id']}/signing/{approver['id']}/complete")
        assert resp.status_code == 200
        result = resp.json()
        assert result["recipient"]["status"] == "COMPLETED"


# ════════════════════════════════════════════════════════════════════
# PART 8: Rejection
# ════════════════════════════════════════════════════════════════════


class TestRejection:

    def test_reject_document(self):
        doc, recip, field = setup_signable_document()
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip['id']}/reject",
            {"reason": "Not acceptable"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["recipient"]["status"] == "REJECTED"
        assert result["document"]["status"] == "REJECTED"

    def test_cannot_reject_draft(self):
        """Cannot reject when document is in DRAFT."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        add_field(doc["id"], recip["id"])
        # Don't send

        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/reject")
        assert resp.status_code == 400

    def test_viewer_cannot_reject(self):
        """VIEWER recipients cannot reject."""
        doc = create_document()
        signer = add_recipient(doc["id"], role="SIGNER", name="S", email="svr@example.com")
        viewer = add_recipient(doc["id"], role="VIEWER", name="V", email="vvr@example.com")
        add_field(doc["id"], signer["id"])
        send_document(doc["id"])

        resp = api_post(f"/api/documents/{doc['id']}/signing/{viewer['id']}/reject")
        assert resp.status_code == 400

    def test_cannot_sign_after_rejection(self):
        """After rejection, no further completion is possible."""
        doc = create_document()
        signer1 = add_recipient(doc["id"], role="SIGNER", name="S1", email="s1rej@example.com")
        signer2 = add_recipient(doc["id"], role="SIGNER", name="S2", email="s2rej@example.com")
        field1 = add_field(doc["id"], signer1["id"])
        field2 = add_field(doc["id"], signer2["id"])
        send_document(doc["id"])

        # Signer1 rejects
        require_status(
            api_post(f"/api/documents/{doc['id']}/signing/{signer1['id']}/reject"),
            200,
            "Failed to reject document",
        )

        # Signer2 tries to complete
        resp = api_post(f"/api/documents/{doc['id']}/signing/{signer2['id']}/complete")
        assert resp.status_code == 400

    def test_cannot_reject_after_rejection(self):
        """Cannot reject an already rejected document."""
        doc2 = create_document()
        s1 = add_recipient(doc2["id"], role="SIGNER", name="X", email="x@example.com")
        s2 = add_recipient(doc2["id"], role="SIGNER", name="Y", email="y@example.com")
        add_field(doc2["id"], s1["id"])
        add_field(doc2["id"], s2["id"])
        send_document(doc2["id"])

        # s1 rejects
        require_status(
            api_post(f"/api/documents/{doc2['id']}/signing/{s1['id']}/reject"),
            200,
            "Failed to reject document",
        )
        # s2 tries to reject too
        resp = api_post(f"/api/documents/{doc2['id']}/signing/{s2['id']}/reject")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 9: Signing Order Enforcement
# ════════════════════════════════════════════════════════════════════


class TestSigningOrder:

    def test_signing_order_enforced(self):
        """Cannot sign if earlier-order recipients haven't completed."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="First", email="first@example.com", signing_order=1)
        recip2 = add_recipient(doc["id"], role="SIGNER", name="Second", email="second@example.com", signing_order=2)
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # recip2 tries to sign before recip1 — should fail
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field2['id']}",
            {"value": "Too early"},
        )
        assert resp.status_code == 400

    def test_signing_order_allows_after_previous_completes(self):
        """Once earlier-order recipient completes, next can sign."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="First", email="first2@example.com", signing_order=1)
        recip2 = add_recipient(doc["id"], role="SIGNER", name="Second", email="second2@example.com", signing_order=2)
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # recip1 signs and completes
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip1['id']}/fields/{field1['id']}",
                {"value": "First sig"},
            ),
            200,
            "First recipient field signing failed",
        )
        require_status(
            api_post(f"/api/documents/{doc['id']}/signing/{recip1['id']}/complete"),
            200,
            "First recipient completion failed",
        )

        # Now recip2 should be able to sign
        resp = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field2['id']}",
            {"value": "Second sig"},
        )
        assert resp.status_code == 200

    def test_same_signing_order_parallel(self):
        """Recipients with same signingOrder can sign in parallel."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="ParA", email="para@example.com", signing_order=1)
        recip2 = add_recipient(doc["id"], role="SIGNER", name="ParB", email="parb@example.com", signing_order=1)
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # Both should be able to sign
        resp1 = api_post(
            f"/api/documents/{doc['id']}/signing/{recip1['id']}/fields/{field1['id']}",
            {"value": "A sig"},
        )
        assert resp1.status_code == 200

        resp2 = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field2['id']}",
            {"value": "B sig"},
        )
        assert resp2.status_code == 200

    def test_signing_order_reject_enforced(self):
        """Cannot reject if earlier-order recipients haven't completed."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="First", email="firstr@example.com", signing_order=1)
        recip2 = add_recipient(doc["id"], role="SIGNER", name="Second", email="secondr@example.com", signing_order=2)
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # recip2 tries to reject before recip1 completes — should fail
        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip2['id']}/reject")
        assert resp.status_code == 400

    def test_no_signing_order_all_parallel(self):
        """If no signingOrder is set, all recipients can sign in parallel."""
        doc = create_document()
        recip1 = add_recipient(doc["id"], role="SIGNER", name="NoOrd1", email="noord1@example.com")
        recip2 = add_recipient(doc["id"], role="SIGNER", name="NoOrd2", email="noord2@example.com")
        field1 = add_field(doc["id"], recip1["id"])
        field2 = add_field(doc["id"], recip2["id"])
        send_document(doc["id"])

        # Both should be able to sign without order constraints
        resp2 = api_post(
            f"/api/documents/{doc['id']}/signing/{recip2['id']}/fields/{field2['id']}",
            {"value": "No order sig"},
        )
        assert resp2.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 10: Templates
# ════════════════════════════════════════════════════════════════════


class TestTemplates:

    def test_create_template(self):
        resp = api_post("/api/templates", {"title": f"Template-{UNIQUE}", "message": "Template msg"})
        assert resp.status_code == 201
        tmpl = resp.json()
        assert tmpl["title"] == f"Template-{UNIQUE}"
        assert "id" in tmpl
        assert "createdAt" in tmpl

    def test_list_templates(self):
        create_template(title=f"ListTmpl-{UNIQUE}")
        resp = api_get("/api/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) >= 1

    def test_get_template(self):
        tmpl = create_template(title=f"GetTmpl-{UNIQUE}")
        resp = api_get(f"/api/templates/{tmpl['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == tmpl["id"]
        assert "recipients" in detail
        assert "fields" in detail

    def test_update_template(self):
        tmpl = create_template(title=f"UpdTmpl-{UNIQUE}")
        resp = api_put(f"/api/templates/{tmpl['id']}", {"title": "New Template Title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Template Title"

    def test_delete_template(self):
        tmpl = create_template(title=f"DelTmpl-{UNIQUE}")
        resp = api_delete(f"/api/templates/{tmpl['id']}")
        assert resp.status_code == 204
        # Verify gone
        resp = api_get(f"/api/templates/{tmpl['id']}")
        assert resp.status_code == 404

    def test_add_template_recipient(self):
        tmpl = create_template(title=f"TRTmpl-{UNIQUE}")
        resp = api_post(f"/api/templates/{tmpl['id']}/recipients", {
            "name": "Template Signer",
            "email": "tmplsigner@example.com",
            "role": "SIGNER",
            "signingOrder": 1,
        })
        assert resp.status_code == 201
        recip = resp.json()
        assert recip["name"] == "Template Signer"
        assert recip["role"] == "SIGNER"
        assert recip["templateId"] == tmpl["id"]

    def test_delete_template_recipient(self):
        tmpl = create_template(title=f"DelTR-{UNIQUE}")
        recip = require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "ToDelete",
                "email": "del@example.com",
                "role": "SIGNER",
            }),
            201,
            "Failed to add template recipient",
        ).json()
        resp = api_delete(f"/api/templates/{tmpl['id']}/recipients/{recip['id']}")
        assert resp.status_code == 204

    def test_add_template_field(self):
        tmpl = create_template(title=f"TFTmpl-{UNIQUE}")
        recip = require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "TF Signer",
                "email": "tf@example.com",
                "role": "SIGNER",
            }),
            201,
            "Failed to add template recipient",
        ).json()
        resp = api_post(f"/api/templates/{tmpl['id']}/fields", {
            "type": "SIGNATURE",
            "recipientId": recip["id"],
            "page": 1,
            "positionX": 10,
            "positionY": 20,
            "width": 100,
            "height": 50,
        })
        assert resp.status_code == 201
        field = resp.json()
        assert field["type"] == "SIGNATURE"
        assert field["templateId"] == tmpl["id"]

    def test_delete_template_field(self):
        tmpl = create_template(title=f"DelTF-{UNIQUE}")
        recip = require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "DelF",
                "email": "delf@example.com",
                "role": "SIGNER",
            }),
            201,
            "Failed to add template recipient",
        ).json()
        field = require_status(
            api_post(f"/api/templates/{tmpl['id']}/fields", {
                "type": "TEXT",
                "recipientId": recip["id"],
            }),
            201,
            "Failed to add template field",
        ).json()
        resp = api_delete(f"/api/templates/{tmpl['id']}/fields/{field['id']}")
        assert resp.status_code == 204

    def test_use_template(self):
        """Creating a document from a template copies recipients and fields."""
        tmpl = create_template(title=f"UseTmpl-{UNIQUE}", message="Tmpl msg")
        recip = require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "Tmpl Signer",
                "email": "use@example.com",
                "role": "SIGNER",
                "signingOrder": 1,
            }),
            201,
            "Failed to add template recipient",
        ).json()
        require_status(
            api_post(f"/api/templates/{tmpl['id']}/fields", {
                "type": "SIGNATURE",
                "recipientId": recip["id"],
                "page": 2,
                "positionX": 50,
                "positionY": 60,
                "width": 120,
                "height": 40,
            }),
            201,
            "Failed to add template field",
        )

        # Use template
        resp = api_post(f"/api/templates/{tmpl['id']}/use")
        assert resp.status_code == 201
        doc = resp.json()
        assert doc["status"] == "DRAFT"
        assert doc["title"] == f"UseTmpl-{UNIQUE}"
        assert len(doc["recipients"]) == 1
        assert doc["recipients"][0]["name"] == "Tmpl Signer"
        assert doc["recipients"][0]["email"] == "use@example.com"
        assert doc["recipients"][0]["role"] == "SIGNER"
        assert len(doc["fields"]) == 1
        assert doc["fields"][0]["type"] == "SIGNATURE"
        assert doc["fields"][0]["page"] == 2
        assert doc["fields"][0]["positionX"] == 50

    def test_use_template_override_title(self):
        """Can override the document title when using a template."""
        tmpl = create_template(title=f"OvrdTmpl-{UNIQUE}")
        require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "R",
                "email": "r@example.com",
                "role": "SIGNER",
            }),
            201,
            "Failed to add template recipient",
        )

        resp = api_post(f"/api/templates/{tmpl['id']}/use", {"title": "Custom Title"})
        assert resp.status_code == 201
        assert resp.json()["title"] == "Custom Title"


# ════════════════════════════════════════════════════════════════════
# PART 11: API Tokens
# ════════════════════════════════════════════════════════════════════


class TestApiTokens:

    def test_create_token(self):
        resp = api_post("/api/tokens", {"name": f"Token-{UNIQUE}"})
        assert resp.status_code == 201
        token = resp.json()
        assert token["name"] == f"Token-{UNIQUE}"
        assert "id" in token
        assert "token" in token
        assert len(token["token"]) >= 20
        assert "createdAt" in token

    def test_create_token_with_expiry(self):
        resp = api_post("/api/tokens", {"name": f"ExpToken-{UNIQUE}", "expiresAt": "2030-01-01T00:00:00Z"})
        assert resp.status_code == 201
        token = resp.json()
        assert token["expiresAt"] is not None

    def test_list_tokens(self):
        create_token(name=f"ListToken-{UNIQUE}")
        resp = api_get("/api/tokens")
        assert resp.status_code == 200
        tokens = resp.json()
        assert isinstance(tokens, list)
        assert len(tokens) >= 1

    def test_delete_token(self):
        token = create_token(name=f"DelToken-{UNIQUE}")
        resp = api_delete(f"/api/tokens/{token['id']}")
        assert resp.status_code == 204

        # Verify gone
        tokens_resp = api_get("/api/tokens")
        require_status(tokens_resp, 200, "Failed to list API tokens")
        tokens = tokens_resp.json()
        ids = [t["id"] for t in tokens]
        assert token["id"] not in ids

    def test_delete_nonexistent_token(self):
        resp = api_delete("/api/tokens/999999")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_document_isolation(self):
        """User A's documents are not visible to User B."""
        doc = create_document(title=f"Isolated-{UNIQUE}", headers=USER1_HEADERS)

        # User B should not see it
        resp = api_get(f"/api/documents/{doc['id']}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_document_list_isolation(self):
        """User B's document list should not include User A's documents."""
        title = f"IsoList-{UNIQUE}"
        create_document(title=title, headers=USER1_HEADERS)

        resp = api_get("/api/documents", headers=USER2_HEADERS)
        require_status(resp, 200, "Failed to list second user's documents")
        titles = [d["title"] for d in resp.json()["items"]]
        assert title not in titles

    def test_template_isolation(self):
        """User A's templates are not visible to User B."""
        tmpl = create_template(title=f"IsoTmpl-{UNIQUE}", headers=USER1_HEADERS)

        resp = api_get(f"/api/templates/{tmpl['id']}", headers=USER2_HEADERS)
        assert resp.status_code == 404

    def test_token_isolation(self):
        """User A's tokens are not visible to User B."""
        create_token(name=f"IsoToken-{UNIQUE}", headers=USER1_HEADERS)

        tokens_resp = api_get("/api/tokens", headers=USER2_HEADERS)
        require_status(tokens_resp, 200, "Failed to list second user's API tokens")
        tokens = tokens_resp.json()
        names = [t["name"] for t in tokens]
        assert f"IsoToken-{UNIQUE}" not in names


# ════════════════════════════════════════════════════════════════════
# PART 13: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_document_deletes_recipients_and_fields(self):
        """Deleting a document should delete all its recipients and fields."""
        doc = create_document()
        recip = add_recipient(doc["id"])
        field = add_field(doc["id"], recip["id"])

        require_status(
            api_delete(f"/api/documents/{doc['id']}"),
            204,
            "Failed to delete document",
        )

        # Document should be gone
        resp = api_get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 404

    def test_delete_template_deletes_recipients_and_fields(self):
        """Deleting a template should delete all its recipients and fields."""
        tmpl = create_template(title=f"CascTmpl-{UNIQUE}")
        recip = require_status(
            api_post(f"/api/templates/{tmpl['id']}/recipients", {
                "name": "C", "email": "c@example.com", "role": "SIGNER",
            }),
            201,
            "Failed to add template recipient",
        ).json()
        require_status(
            api_post(f"/api/templates/{tmpl['id']}/fields", {
                "type": "TEXT", "recipientId": recip["id"],
            }),
            201,
            "Failed to add template field",
        )

        require_status(
            api_delete(f"/api/templates/{tmpl['id']}"),
            204,
            "Failed to delete template",
        )

        resp = api_get(f"/api/templates/{tmpl['id']}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_optional_fields_not_required_for_completion(self):
        """Non-required fields don't need to be signed for completion."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        required_field = add_field(doc["id"], recip["id"], field_type="SIGNATURE", required=True)
        add_field(doc["id"], recip["id"], field_type="TEXT", required=False)
        send_document(doc["id"])

        # Only sign required field
        require_status(
            api_post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{required_field['id']}",
                {"value": "My sig"},
            ),
            200,
            "Required field signing failed",
        )

        # Should be able to complete
        resp = api_post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert resp.status_code == 200
        assert resp.json()["recipient"]["status"] == "COMPLETED"

    def test_field_value_null_before_signing(self):
        """Field value should be null before it's signed."""
        doc = create_document()
        recip = add_recipient(doc["id"], role="SIGNER")
        field = add_field(doc["id"], recip["id"])

        resp = api_get(f"/api/documents/{doc['id']}/fields")
        require_status(resp, 200, "Failed to list document fields")
        fields = resp.json()
        assert fields[0]["value"] is None

    def test_document_detail_includes_recipients_and_fields(self):
        """GET document detail should include recipients and fields arrays."""
        doc = create_document()
        recip = add_recipient(doc["id"])
        add_field(doc["id"], recip["id"])

        resp = api_get(f"/api/documents/{doc['id']}")
        require_status(resp, 200, "Failed to get document detail")
        detail = resp.json()
        assert len(detail["recipients"]) == 1
        assert len(detail["fields"]) == 1
        assert detail["recipients"][0]["id"] == recip["id"]
