"""
BackendForge — L3 Workflow Tests for Documenso Task

Multi-step adversarial workflow tests covering 3+ entity types per test,
targeting common LLM implementation bugs across complex scenarios.

"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")

USER_A_KEY = f"wf-userA-{uuid.uuid4().hex[:8]}"
USER_B_KEY = f"wf-userB-{uuid.uuid4().hex[:8]}"

HEADERS_A = {"X-Api-Key": USER_A_KEY}
HEADERS_B = {"X-Api-Key": USER_B_KEY}


@pytest.fixture(autouse=True)
def isolate_test_users():
    """Give every item fresh user namespaces so persisted state cannot cross tests."""
    global USER_A_KEY, USER_B_KEY, HEADERS_A, HEADERS_B

    run_id = uuid.uuid4().hex
    USER_A_KEY = f"wf-userA-{run_id}"
    USER_B_KEY = f"wf-userB-{run_id}"
    HEADERS_A = {"X-Api-Key": USER_A_KEY}
    HEADERS_B = {"X-Api-Key": USER_B_KEY}


def get(path, params=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def post(path, json=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def put(path, json=None, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json, headers=request_headers, timeout=30)


def delete(path, headers=None):
    request_headers = HEADERS_A if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


def require_status(response, expected, action):
    """Validate a prerequisite request before its result is used by a test."""
    assert response.status_code == expected, (
        f"{action}: expected {expected}, got {response.status_code}: {response.text}"
    )
    return response


def require_json(response, expected, action):
    return require_status(response, expected, action).json()


def create_document(body, headers=None):
    return require_json(
        post("/api/documents", body, headers=headers),
        201,
        "Failed to create document",
    )


def add_recipient(document_id, body, headers=None):
    return require_json(
        post(f"/api/documents/{document_id}/recipients", body, headers=headers),
        201,
        "Failed to add document recipient",
    )


def add_field(document_id, body, headers=None):
    return require_json(
        post(f"/api/documents/{document_id}/fields", body, headers=headers),
        201,
        "Failed to add document field",
    )


def send_document(document_id, headers=None):
    return require_json(
        post(f"/api/documents/{document_id}/send", headers=headers),
        200,
        "Failed to send document",
    )


def create_template(body, headers=None):
    return require_json(
        post("/api/templates", body, headers=headers),
        201,
        "Failed to create template",
    )


def add_template_recipient(template_id, body, headers=None):
    return require_json(
        post(f"/api/templates/{template_id}/recipients", body, headers=headers),
        201,
        "Failed to add template recipient",
    )


def add_template_field(template_id, body, headers=None):
    return require_json(
        post(f"/api/templates/{template_id}/fields", body, headers=headers),
        201,
        "Failed to add template field",
    )


def create_token(body, headers=None):
    return require_json(
        post("/api/tokens", body, headers=headers),
        201,
        "Failed to create API token",
    )


# ═══════════════════════════════════════════════════════
# L3 Tests — 13 tests
# ═══════════════════════════════════════════════════════


class TestFullSigningWorkflow:
    """Pattern 2+5+7: Complete signing lifecycle with side-effect verification."""

    def test_full_document_sign_complete_lifecycle(self):
        """
        Full lifecycle: create doc → add 2 signers → add fields → send →
        sign fields → complete → verify document COMPLETED + all statuses.
        """
        tag = uuid.uuid4().hex[:8]
        # 1. Create document
        doc = create_document({"title": f"FullLC-{tag}", "message": "Full lifecycle test"})
        assert doc["status"] == "DRAFT"

        # 2. Add two signers
        s1 = add_recipient(doc["id"], {
            "name": f"Signer1-{tag}", "email": f"s1-{tag}@test.com", "role": "SIGNER"
        })
        s2 = add_recipient(doc["id"], {
            "name": f"Signer2-{tag}", "email": f"s2-{tag}@test.com", "role": "SIGNER"
        })

        # 3. Add fields for each
        f1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s1["id"], "page": 1,
            "positionX": 100, "positionY": 200, "width": 150, "height": 50
        })
        f2 = add_field(doc["id"], {
            "type": "TEXT", "recipientId": s2["id"], "page": 1,
            "positionX": 100, "positionY": 300, "width": 200, "height": 40
        })

        # 4. Send document
        sent = send_document(doc["id"])
        assert sent["status"] == "PENDING"

        # 5. Signer 1 signs and completes
        r = post(f"/api/documents/{doc['id']}/signing/{s1['id']}/fields/{f1['id']}",
                 {"value": f"sig1-{tag}"})
        assert r.status_code == 200
        assert r.json()["value"] == f"sig1-{tag}"

        r = post(f"/api/documents/{doc['id']}/signing/{s1['id']}/complete")
        assert r.status_code == 200
        result = r.json()
        assert result["recipient"]["status"] == "COMPLETED"
        assert result["document"]["status"] == "PENDING"  # Not done yet

        # 6. Signer 2 signs and completes
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f2['id']}",
                 {"value": f"text2-{tag}"})
        assert r.status_code == 200

        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/complete")
        assert r.status_code == 200
        result = r.json()
        assert result["recipient"]["status"] == "COMPLETED"
        assert result["document"]["status"] == "COMPLETED"  # All done!

        # 7. Verify final state via GET
        detail = require_json(
            get(f"/api/documents/{doc['id']}"),
            200,
            "Failed to get document detail",
        )
        assert detail["status"] == "COMPLETED"
        assert len(detail["recipients"]) == 2
        for rec in detail["recipients"]:
            assert rec["status"] == "COMPLETED"
        # Fields should have values
        for field in detail["fields"]:
            assert field["value"] is not None
            assert field["signedAt"] is not None

    def test_viewer_auto_complete_on_send(self):
        """
        Viewer auto-completes on send; only signer/approver needed for doc completion.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"ViewAuto-{tag}"})
        signer = add_recipient(doc["id"], {
            "name": f"S-{tag}", "email": f"s-{tag}@t.com", "role": "SIGNER"
        })
        viewer = add_recipient(doc["id"], {
            "name": f"V-{tag}", "email": f"v-{tag}@t.com", "role": "VIEWER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": signer["id"]
        })

        # Send
        send_document(doc["id"])

        # Check viewer is COMPLETED
        recipients = require_json(
            get(f"/api/documents/{doc['id']}/recipients"),
            200,
            "Failed to list recipients",
        )
        viewer_rec = next(r for r in recipients if r["id"] == viewer["id"])
        assert viewer_rec["status"] == "COMPLETED"
        signer_rec = next(r for r in recipients if r["id"] == signer["id"])
        assert signer_rec["status"] == "PENDING"

        # Viewer cannot manually complete
        r = post(f"/api/documents/{doc['id']}/signing/{viewer['id']}/complete")
        assert r.status_code == 400

        # Viewer cannot reject
        r = post(f"/api/documents/{doc['id']}/signing/{viewer['id']}/reject")
        assert r.status_code == 400

        # Signer completes → doc completed
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{signer['id']}/fields/{field['id']}",
                {"value": "done"},
            ),
            200,
            "Signer field signing failed",
        )
        r = post(f"/api/documents/{doc['id']}/signing/{signer['id']}/complete")
        require_status(r, 200, "Signer completion failed")
        assert r.json()["document"]["status"] == "COMPLETED"


class TestSigningOrderWorkflow:
    """Pattern 5+8: Signing order enforcement across multiple recipients."""

    def test_three_level_signing_order(self):
        """
        3 signers with order 1, 2, 3. Verify strict sequential enforcement.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"Order3-{tag}"})

        s1 = add_recipient(doc["id"], {
            "name": f"First-{tag}", "email": f"o1-{tag}@t.com",
            "role": "SIGNER", "signingOrder": 1
        })
        s2 = add_recipient(doc["id"], {
            "name": f"Second-{tag}", "email": f"o2-{tag}@t.com",
            "role": "SIGNER", "signingOrder": 2
        })
        s3 = add_recipient(doc["id"], {
            "name": f"Third-{tag}", "email": f"o3-{tag}@t.com",
            "role": "SIGNER", "signingOrder": 3
        })

        f1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s1["id"]
        })
        f2 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s2["id"]
        })
        f3 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s3["id"]
        })

        send_document(doc["id"])

        # S3 cannot sign (order 1 and 2 not done)
        r = post(f"/api/documents/{doc['id']}/signing/{s3['id']}/fields/{f3['id']}",
                 {"value": "nope"})
        assert r.status_code == 400

        # S2 cannot sign (order 1 not done)
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f2['id']}",
                 {"value": "nope"})
        assert r.status_code == 400

        # S1 signs and completes
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{s1['id']}/fields/{f1['id']}",
                {"value": f"first-{tag}"},
            ),
            200,
            "First signer field signing failed",
        )
        require_status(
            post(f"/api/documents/{doc['id']}/signing/{s1['id']}/complete"),
            200,
            "First signer completion failed",
        )

        # Now S2 can sign but S3 still cannot
        r = post(f"/api/documents/{doc['id']}/signing/{s3['id']}/fields/{f3['id']}",
                 {"value": "still-no"})
        assert r.status_code == 400

        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f2['id']}",
                 {"value": f"second-{tag}"})
        assert r.status_code == 200
        require_status(
            post(f"/api/documents/{doc['id']}/signing/{s2['id']}/complete"),
            200,
            "Second signer completion failed",
        )

        # Now S3 can sign
        r = post(f"/api/documents/{doc['id']}/signing/{s3['id']}/fields/{f3['id']}",
                 {"value": f"third-{tag}"})
        assert r.status_code == 200
        r = post(f"/api/documents/{doc['id']}/signing/{s3['id']}/complete")
        assert r.status_code == 200
        assert r.json()["document"]["status"] == "COMPLETED"


class TestCancelAndResendWorkflow:
    """Pattern 5+7: Cancel resets state, re-enables editing, allows re-send."""

    def test_cancel_resets_then_resend(self):
        """
        Send → cancel → verify editable → modify → re-send → sign → complete.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"CancelRS-{tag}"})
        recip = add_recipient(doc["id"], {
            "name": f"CR-{tag}", "email": f"cr-{tag}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })

        # Send
        send_document(doc["id"])
        # Verify cannot edit
        r = put(f"/api/documents/{doc['id']}", {"title": "Nope"})
        assert r.status_code == 400

        # Cancel
        r = post(f"/api/documents/{doc['id']}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "DRAFT"

        # Verify recipients reset to PENDING
        recipients = require_json(
            get(f"/api/documents/{doc['id']}/recipients"),
            200,
            "Failed to list recipients",
        )
        for rec in recipients:
            assert rec["status"] == "PENDING"

        # Now can edit
        r = put(f"/api/documents/{doc['id']}", {"title": f"Edited-{tag}"})
        assert r.status_code == 200
        assert r.json()["title"] == f"Edited-{tag}"

        # Re-send
        r = post(f"/api/documents/{doc['id']}/send")
        assert r.status_code == 200
        assert r.json()["status"] == "PENDING"

        # Sign and complete
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": f"resigned-{tag}"},
            ),
            200,
            "Field signing failed after resend",
        )
        r = post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert r.status_code == 200
        assert r.json()["document"]["status"] == "COMPLETED"


class TestTemplateToDocumentWorkflow:
    """Pattern 2+5+7: Template creates document with correct data propagation."""

    def test_template_use_copies_all_data_correctly(self):
        """
        Create template with 2 recipients + fields → use → verify document
        has all copied data with correct field linkage.
        """
        tag = uuid.uuid4().hex[:8]
        tmpl = create_template({
            "title": f"TmplWF-{tag}", "message": f"Tmpl msg {tag}"
        })

        # Add 2 recipients with different roles
        tr1 = add_template_recipient(tmpl["id"], {
            "name": f"TmplSigner-{tag}", "email": f"ts-{tag}@t.com",
            "role": "SIGNER", "signingOrder": 1
        })
        tr2 = add_template_recipient(tmpl["id"], {
            "name": f"TmplAppr-{tag}", "email": f"ta-{tag}@t.com",
            "role": "APPROVER", "signingOrder": 2
        })

        # Add fields
        tf1 = add_template_field(tmpl["id"], {
            "type": "SIGNATURE", "recipientId": tr1["id"],
            "page": 1, "positionX": 10, "positionY": 20, "width": 100, "height": 50
        })
        tf2 = add_template_field(tmpl["id"], {
            "type": "TEXT", "recipientId": tr1["id"],
            "page": 2, "positionX": 30, "positionY": 40, "width": 80, "height": 30
        })

        # Verify template detail
        tmpl_detail = require_json(
            get(f"/api/templates/{tmpl['id']}"),
            200,
            "Failed to get template detail",
        )
        assert len(tmpl_detail["recipients"]) == 2
        assert len(tmpl_detail["fields"]) == 2

        # Use template with title override
        r = post(f"/api/templates/{tmpl['id']}/use", {"title": f"FromTmpl-{tag}"})
        assert r.status_code == 201
        doc = r.json()
        assert doc["title"] == f"FromTmpl-{tag}"
        assert doc["status"] == "DRAFT"
        assert len(doc["recipients"]) == 2
        assert len(doc["fields"]) == 2

        # Verify recipient data copied
        signer_rec = next(r for r in doc["recipients"] if r["role"] == "SIGNER")
        approver_rec = next(r for r in doc["recipients"] if r["role"] == "APPROVER")
        assert signer_rec["name"] == f"TmplSigner-{tag}"
        assert signer_rec["email"] == f"ts-{tag}@t.com"
        assert approver_rec["name"] == f"TmplAppr-{tag}"

        # Verify fields point to document recipients (not template recipients)
        for field in doc["fields"]:
            assert field["recipientId"] in [signer_rec["id"], approver_rec["id"]]
            assert field["documentId"] == doc["id"]

        # Verify the document is usable: can send and sign
        r = post(f"/api/documents/{doc['id']}/send")
        assert r.status_code == 200


class TestRejectionWorkflow:
    """Pattern 5+7: Rejection cascades to block all further actions."""

    def test_rejection_blocks_all_subsequent_actions(self):
        """
        2 signers; first rejects → verify doc REJECTED, second cannot sign/complete/reject.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"RejWF-{tag}"})
        s1 = add_recipient(doc["id"], {
            "name": f"Rej1-{tag}", "email": f"rj1-{tag}@t.com", "role": "SIGNER"
        })
        s2 = add_recipient(doc["id"], {
            "name": f"Rej2-{tag}", "email": f"rj2-{tag}@t.com", "role": "SIGNER"
        })
        f1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s1["id"]
        })
        f2 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s2["id"]
        })
        send_document(doc["id"])

        # S1 rejects
        r = post(f"/api/documents/{doc['id']}/signing/{s1['id']}/reject")
        assert r.status_code == 200
        assert r.json()["document"]["status"] == "REJECTED"
        assert r.json()["recipient"]["status"] == "REJECTED"

        # S2 cannot sign
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f2['id']}",
                 {"value": "too late"})
        assert r.status_code == 400

        # S2 cannot complete
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/complete")
        assert r.status_code == 400

        # S2 cannot reject again
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/reject")
        assert r.status_code == 400

        # Cannot cancel rejected doc
        r = post(f"/api/documents/{doc['id']}/cancel")
        assert r.status_code == 400


class TestImmutabilityAfterSend:
    """Pattern 5+4: Once sent, document structure is frozen."""

    def test_pending_document_is_immutable(self):
        """
        After send: cannot add/update/delete recipients, fields, or update doc.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"Immut-{tag}"})
        recip = add_recipient(doc["id"], {
            "name": f"Im-{tag}", "email": f"im-{tag}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        send_document(doc["id"])

        # Cannot update document
        r = put(f"/api/documents/{doc['id']}", {"title": "Hacked"})
        assert r.status_code == 400

        # Cannot delete document
        r = delete(f"/api/documents/{doc['id']}")
        assert r.status_code == 400

        # Cannot add recipient
        r = post(f"/api/documents/{doc['id']}/recipients", {
            "name": "New", "email": "new@t.com", "role": "SIGNER"
        })
        assert r.status_code == 400

        # Cannot update recipient
        r = put(f"/api/documents/{doc['id']}/recipients/{recip['id']}", {"name": "Changed"})
        assert r.status_code == 400

        # Cannot delete recipient
        r = delete(f"/api/documents/{doc['id']}/recipients/{recip['id']}")
        assert r.status_code == 400

        # Cannot add field
        r = post(f"/api/documents/{doc['id']}/fields", {
            "type": "TEXT", "recipientId": recip["id"]
        })
        assert r.status_code == 400

        # Cannot update field
        r = put(f"/api/documents/{doc['id']}/fields/{field['id']}", {"positionX": 999})
        assert r.status_code == 400

        # Cannot delete field
        r = delete(f"/api/documents/{doc['id']}/fields/{field['id']}")
        assert r.status_code == 400


class TestMultiUserIsolationWorkflow:
    """Pattern 6: Complete isolation between users across all entities."""

    def test_full_isolation_across_documents_templates_tokens(self):
        """
        User A creates doc + template + token.
        User B cannot access any of them via direct ID or list endpoints.
        """
        tag = uuid.uuid4().hex[:8]
        # User A creates all resources
        doc_a = create_document({"title": f"IsoDoc-{tag}"}, headers=HEADERS_A)
        tmpl_a = create_template({"title": f"IsoTmpl-{tag}"}, headers=HEADERS_A)
        tok_a = create_token({"name": f"IsoTok-{tag}"}, headers=HEADERS_A)

        # User B: cannot get doc
        assert get(f"/api/documents/{doc_a['id']}", headers=HEADERS_B).status_code == 404
        # User B: cannot get template
        assert get(f"/api/templates/{tmpl_a['id']}", headers=HEADERS_B).status_code == 404
        # User B: cannot delete token
        assert delete(f"/api/tokens/{tok_a['id']}", headers=HEADERS_B).status_code == 404

        # User B: list should not contain A's items
        docs_b = require_json(
            get("/api/documents", headers=HEADERS_B),
            200,
            "Failed to list second user's documents",
        )["items"]
        assert doc_a["id"] not in [d["id"] for d in docs_b]

        tmpls_b = require_json(
            get("/api/templates", headers=HEADERS_B),
            200,
            "Failed to list second user's templates",
        )["items"]
        assert tmpl_a["id"] not in [t["id"] for t in tmpls_b]

        tokens_b = require_json(
            get("/api/tokens", headers=HEADERS_B),
            200,
            "Failed to list second user's API tokens",
        )
        assert tok_a["id"] not in [t["id"] for t in tokens_b]


class TestApproverWorkflow:
    """Pattern 5: Approver can complete without signing fields."""

    def test_signer_plus_approver_completion(self):
        """
        Doc with signer + approver. Approver completes without fields.
        Both needed for doc to become COMPLETED.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"ApprWF-{tag}"})
        signer = add_recipient(doc["id"], {
            "name": f"Sgn-{tag}", "email": f"sgn-{tag}@t.com", "role": "SIGNER"
        })
        approver = add_recipient(doc["id"], {
            "name": f"Apr-{tag}", "email": f"apr-{tag}@t.com", "role": "APPROVER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": signer["id"]
        })
        send_document(doc["id"])

        # Approver completes first (no fields to sign)
        r = post(f"/api/documents/{doc['id']}/signing/{approver['id']}/complete")
        assert r.status_code == 200
        assert r.json()["recipient"]["status"] == "COMPLETED"
        assert r.json()["document"]["status"] == "PENDING"  # Signer not done

        # Signer signs and completes
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{signer['id']}/fields/{field['id']}",
                {"value": f"sig-{tag}"},
            ),
            200,
            "Signer field signing failed",
        )
        r = post(f"/api/documents/{doc['id']}/signing/{signer['id']}/complete")
        assert r.status_code == 200
        assert r.json()["document"]["status"] == "COMPLETED"


class TestOptionalFieldsWorkflow:
    """Pattern 5: Required vs optional field handling for completion."""

    def test_optional_fields_dont_block_completion(self):
        """
        Signer with 2 required + 1 optional field. Sign only required → complete.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"OptF-{tag}"})
        recip = add_recipient(doc["id"], {
            "name": f"OF-{tag}", "email": f"of-{tag}@t.com", "role": "SIGNER"
        })
        req1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"], "required": True
        })
        req2 = add_field(doc["id"], {
            "type": "TEXT", "recipientId": recip["id"], "required": True
        })
        opt = add_field(doc["id"], {
            "type": "CHECKBOX", "recipientId": recip["id"], "required": False
        })
        send_document(doc["id"])

        # Sign only required fields
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{req1['id']}",
                {"value": f"sig-{tag}"},
            ),
            200,
            "First required field signing failed",
        )
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{req2['id']}",
                {"value": f"text-{tag}"},
            ),
            200,
            "Second required field signing failed",
        )

        # Should not need to sign optional
        r = post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert r.status_code == 200
        assert r.json()["recipient"]["status"] == "COMPLETED"
        assert r.json()["document"]["status"] == "COMPLETED"

        # Verify optional field remains unsigned
        fields = require_json(
            get(f"/api/documents/{doc['id']}/fields"),
            200,
            "Failed to list document fields",
        )
        opt_field = next(f for f in fields if f["id"] == opt["id"])
        assert opt_field["value"] is None
        assert opt_field["signedAt"] is None

    def test_missing_required_field_blocks_completion(self):
        """Cannot complete if any required field is unsigned."""
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"MissReq-{tag}"})
        recip = add_recipient(doc["id"], {
            "name": f"MR-{tag}", "email": f"mr-{tag}@t.com", "role": "SIGNER"
        })
        req1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"], "required": True
        })
        req2 = add_field(doc["id"], {
            "type": "TEXT", "recipientId": recip["id"], "required": True
        })
        send_document(doc["id"])

        # Sign only one required field
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{req1['id']}",
                {"value": "partial"},
            ),
            200,
            "Partial field signing failed",
        )

        # Cannot complete
        r = post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert r.status_code == 400


class TestSendValidationWorkflow:
    """Pattern 5+8: Send validation with various invalid states."""

    def test_send_requires_signer_or_approver_and_fields(self):
        """
        Verify all send preconditions: must have signer/approver AND fields.
        """
        tag = uuid.uuid4().hex[:8]

        # Case 1: No recipients at all
        doc1 = create_document({"title": f"NoRecip-{tag}"})
        r = post(f"/api/documents/{doc1['id']}/send")
        assert r.status_code == 400

        # Case 2: Only viewer (no signer/approver)
        doc2 = create_document({"title": f"OnlyViewer-{tag}"})
        viewer = add_recipient(doc2["id"], {
            "name": "V", "email": f"v2-{tag}@t.com", "role": "VIEWER"
        })
        add_field(doc2["id"], {
            "type": "TEXT", "recipientId": viewer["id"]
        })
        r = post(f"/api/documents/{doc2['id']}/send")
        assert r.status_code == 400

        # Case 3: Signer but no fields
        doc3 = create_document({"title": f"NoFields-{tag}"})
        add_recipient(doc3["id"], {
            "name": "S", "email": f"s3-{tag}@t.com", "role": "SIGNER"
        })
        r = post(f"/api/documents/{doc3['id']}/send")
        assert r.status_code == 400

        # Case 4: Valid — signer + field
        doc4 = create_document({"title": f"Valid-{tag}"})
        s = add_recipient(doc4["id"], {
            "name": "S4", "email": f"s4-{tag}@t.com", "role": "SIGNER"
        })
        add_field(doc4["id"], {
            "type": "SIGNATURE", "recipientId": s["id"]
        })
        r = post(f"/api/documents/{doc4['id']}/send")
        assert r.status_code == 200
        assert r.json()["status"] == "PENDING"


class TestFieldAssignmentEnforcement:
    """Pattern 5: Field ownership is enforced during signing."""

    def test_cannot_sign_another_recipients_field(self):
        """
        Two signers, each with their own field. Neither can sign the other's.
        """
        tag = uuid.uuid4().hex[:8]
        doc = create_document({"title": f"FieldOwn-{tag}"})
        s1 = add_recipient(doc["id"], {
            "name": f"Own1-{tag}", "email": f"own1-{tag}@t.com", "role": "SIGNER"
        })
        s2 = add_recipient(doc["id"], {
            "name": f"Own2-{tag}", "email": f"own2-{tag}@t.com", "role": "SIGNER"
        })
        f1 = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": s1["id"]
        })
        f2 = add_field(doc["id"], {
            "type": "TEXT", "recipientId": s2["id"]
        })
        send_document(doc["id"])

        # S1 cannot sign S2's field
        r = post(f"/api/documents/{doc['id']}/signing/{s1['id']}/fields/{f2['id']}",
                 {"value": "steal"})
        assert r.status_code == 403

        # S2 cannot sign S1's field
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f1['id']}",
                 {"value": "steal"})
        assert r.status_code == 403

        # Each can sign their own
        r = post(f"/api/documents/{doc['id']}/signing/{s1['id']}/fields/{f1['id']}",
                 {"value": f"s1-{tag}"})
        assert r.status_code == 200
        r = post(f"/api/documents/{doc['id']}/signing/{s2['id']}/fields/{f2['id']}",
                 {"value": f"s2-{tag}"})
        assert r.status_code == 200
