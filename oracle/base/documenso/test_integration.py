"""
BackendForge — L2 Integration Tests for Documenso Task

Adversarial tests targeting common LLM implementation bugs:
- camelCase field naming (Pattern 1)
- Nested data completeness (Pattern 2)
- Filtering/pagination actually working (Pattern 3)
- Exact status codes (Pattern 4)
- Business logic correctness (Pattern 5)
- Data isolation (Pattern 6)
- Cascade/side effects (Pattern 7)

"""

import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")

USER_A_KEY = f"integ-userA-{uuid.uuid4().hex[:8]}"
USER_B_KEY = f"integ-userB-{uuid.uuid4().hex[:8]}"

HEADERS_A = {"X-Api-Key": USER_A_KEY}
HEADERS_B = {"X-Api-Key": USER_B_KEY}


@pytest.fixture(autouse=True)
def isolate_test_users():
    """Give every item fresh user namespaces so persisted state cannot cross tests."""
    global USER_A_KEY, USER_B_KEY, HEADERS_A, HEADERS_B

    run_id = uuid.uuid4().hex
    USER_A_KEY = f"integ-userA-{run_id}"
    USER_B_KEY = f"integ-userB-{run_id}"
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
# L2 Tests — 33 tests
# ═══════════════════════════════════════════════════════


class TestDocumentCreateAndRetrieve:
    """Pattern 1+2: camelCase fields + nested data on GET detail"""

    def test_create_returns_correct_camel_case_fields(self):
        """Verify POST /api/documents returns proper camelCase fields."""
        unique_title = f"CamelDoc-{uuid.uuid4().hex[:8]}"
        r = post("/api/documents", {"title": unique_title, "message": "Test msg"})
        assert r.status_code == 201, f"Expected 201, got {r.status_code}"
        data = r.json()
        # Pattern 1: field naming
        assert "id" in data
        assert "title" in data
        assert "message" in data
        assert "status" in data
        assert "userId" in data, "Missing camelCase 'userId'"
        assert "createdAt" in data, "Missing camelCase 'createdAt'"
        assert "updatedAt" in data, "Missing camelCase 'updatedAt'"
        # Values
        assert data["title"] == unique_title
        assert data["message"] == "Test msg"
        assert data["status"] == "DRAFT"
        assert isinstance(data["userId"], int)

    def test_get_detail_includes_recipients_and_fields_arrays(self):
        """Pattern 2: GET detail must include nested recipients and fields."""
        doc = create_document({"title": f"Nested-{uuid.uuid4().hex[:8]}"})
        # Add recipient with specific data
        recip = add_recipient(doc["id"], {
            "name": "NestedRecip",
            "email": f"nested-{uuid.uuid4().hex[:6]}@test.com",
            "role": "SIGNER",
            "signingOrder": 3,
        })
        # Add field
        field = add_field(doc["id"], {
            "type": "TEXT",
            "recipientId": recip["id"],
            "required": True,
            "page": 2,
            "positionX": 55.5,
            "positionY": 77.3,
            "width": 120,
            "height": 35,
        })

        # GET detail
        r = get(f"/api/documents/{doc['id']}")
        assert r.status_code == 200
        detail = r.json()
        assert "recipients" in detail
        assert "fields" in detail
        assert isinstance(detail["recipients"], list)
        assert isinstance(detail["fields"], list)
        assert len(detail["recipients"]) == 1
        assert len(detail["fields"]) == 1
        # Verify nested recipient fields (camelCase)
        rec = detail["recipients"][0]
        assert rec["id"] == recip["id"]
        assert rec["documentId"] == doc["id"]
        assert rec["name"] == "NestedRecip"
        assert rec["role"] == "SIGNER"
        assert rec["signingOrder"] == 3
        assert "status" in rec
        # Verify nested field data
        f = detail["fields"][0]
        assert f["id"] == field["id"]
        assert f["documentId"] == doc["id"]
        assert f["recipientId"] == recip["id"]
        assert f["type"] == "TEXT"
        assert f["required"] is True
        assert f["page"] == 2
        assert f["positionX"] == 55.5
        assert f["positionY"] == 77.3


class TestDocumentPaginationAndFilter:
    """Pattern 3: Verify pagination and status filter actually work."""

    def test_pagination_limits_results(self):
        """Create known count, verify perPage limits items returned."""
        tag = uuid.uuid4().hex[:8]
        # Create 5 docs
        for i in range(5):
            create_document({"title": f"PagDoc-{tag}-{i}"})
        # Request page 1 with perPage=2
        r = get("/api/documents", params={"page": 1, "perPage": 2})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) <= 2
        pag = data["pagination"]
        assert pag["page"] == 1
        assert pag["perPage"] == 2
        assert pag["totalItems"] >= 5
        assert pag["totalPages"] >= 3

    def test_pagination_page2_has_different_items(self):
        """Page 2 should return different items than page 1."""
        tag = uuid.uuid4().hex[:8]
        for i in range(4):
            create_document({"title": f"P2Doc-{tag}-{i}"})
        r1 = get("/api/documents", params={"page": 1, "perPage": 2})
        r2 = get("/api/documents", params={"page": 2, "perPage": 2})
        require_status(r1, 200, "Failed to get first document page")
        require_status(r2, 200, "Failed to get second document page")
        ids_page1 = {d["id"] for d in r1.json()["items"]}
        ids_page2 = {d["id"] for d in r2.json()["items"]}
        # Pages should not overlap
        assert ids_page1.isdisjoint(ids_page2), "Page 1 and 2 have overlapping items"

    def test_status_filter_only_returns_matching(self):
        """Status filter must actually filter, not return all docs."""
        tag = uuid.uuid4().hex[:8]
        # Create a DRAFT doc
        draft_doc = create_document({"title": f"FilterDraft-{tag}"})
        # Create a PENDING doc
        pending_doc = create_document({"title": f"FilterPend-{tag}"})
        recip = add_recipient(pending_doc["id"], {
            "name": "S", "email": f"s-{tag}@test.com", "role": "SIGNER"
        })
        add_field(pending_doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        send_document(pending_doc["id"])

        # Filter by DRAFT
        r = get("/api/documents", params={"status": "DRAFT"})
        assert r.status_code == 200
        items = r.json()["items"]
        for item in items:
            assert item["status"] == "DRAFT", f"Got non-DRAFT item: {item['status']}"
        # Draft doc should be present
        ids = [d["id"] for d in items]
        assert draft_doc["id"] in ids

        # Filter by PENDING
        r = get("/api/documents", params={"status": "PENDING"})
        require_status(r, 200, "Failed to filter pending documents")
        items = r.json()["items"]
        for item in items:
            assert item["status"] == "PENDING"
        ids = [d["id"] for d in items]
        assert pending_doc["id"] in ids


class TestRecipientFieldCamelCase:
    """Pattern 1: Verify all response fields use correct camelCase."""

    def test_recipient_response_fields(self):
        """Recipient response must have exact camelCase field names."""
        doc = create_document({"title": f"RecFld-{uuid.uuid4().hex[:8]}"})
        r = post(f"/api/documents/{doc['id']}/recipients", {
            "name": "CamelRecip",
            "email": f"camel-{uuid.uuid4().hex[:6]}@test.com",
            "role": "APPROVER",
            "signingOrder": 5,
        })
        assert r.status_code == 201
        recip = r.json()
        # All camelCase fields present
        assert "id" in recip
        assert "documentId" in recip
        assert "name" in recip
        assert "email" in recip
        assert "role" in recip
        assert "signingOrder" in recip
        assert "status" in recip
        assert "signedAt" in recip
        # Values correct
        assert recip["documentId"] == doc["id"]
        assert recip["signingOrder"] == 5
        assert recip["role"] == "APPROVER"
        assert recip["status"] == "PENDING"

    def test_field_response_fields(self):
        """Field response must have exact camelCase field names."""
        doc = create_document({"title": f"FldFld-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "X", "email": f"x-{uuid.uuid4().hex[:6]}@test.com", "role": "SIGNER"
        })
        r = post(f"/api/documents/{doc['id']}/fields", {
            "type": "DATE",
            "recipientId": recip["id"],
            "required": False,
            "page": 3,
            "positionX": 10.5,
            "positionY": 20.7,
            "width": 80,
            "height": 25,
        })
        assert r.status_code == 201
        field = r.json()
        # camelCase checks
        assert "id" in field
        assert "documentId" in field
        assert "recipientId" in field
        assert "positionX" in field
        assert "positionY" in field
        assert "signedAt" in field
        # Values
        assert field["documentId"] == doc["id"]
        assert field["recipientId"] == recip["id"]
        assert field["type"] == "DATE"
        assert field["required"] is False
        assert field["page"] == 3
        assert field["value"] is None
        assert field["signedAt"] is None


class TestSigningFieldResponse:
    """Pattern 1+5: Sign a field and verify response structure + value stored."""

    def test_sign_field_response_has_value_and_signed_at(self):
        """Signing stores value and sets signedAt timestamp."""
        doc = create_document({"title": f"SignResp-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "Signer", "email": f"sr-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        send_document(doc["id"])

        unique_val = f"sig-{uuid.uuid4().hex[:12]}"
        r = post(
            f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
            {"value": unique_val}
        )
        assert r.status_code == 200
        signed = r.json()
        assert signed["value"] == unique_val
        assert signed["signedAt"] is not None
        assert signed["id"] == field["id"]

    def test_signed_field_persists_on_get(self):
        """After signing, GET fields shows the signed value."""
        doc = create_document({"title": f"Persist-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "P", "email": f"p-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "TEXT", "recipientId": recip["id"]
        })
        send_document(doc["id"])

        unique_val = f"text-{uuid.uuid4().hex[:10]}"
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": unique_val},
            ),
            200,
            "Field signing prerequisite failed",
        )

        # GET fields and verify
        r = get(f"/api/documents/{doc['id']}/fields")
        assert r.status_code == 200
        fields = r.json()
        signed_field = next(f for f in fields if f["id"] == field["id"])
        assert signed_field["value"] == unique_val
        assert signed_field["signedAt"] is not None


class TestCompletionResult:
    """Pattern 1+5: Verify SigningResult structure with document + recipient."""

    def test_complete_returns_signing_result(self):
        """Complete returns {document, recipient} with correct statuses."""
        doc = create_document({"title": f"Compl-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "C", "email": f"c-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        send_document(doc["id"])

        # Sign and complete
        require_status(
            post(
                f"/api/documents/{doc['id']}/signing/{recip['id']}/fields/{field['id']}",
                {"value": "done"},
            ),
            200,
            "Field signing prerequisite failed",
        )
        r = post(f"/api/documents/{doc['id']}/signing/{recip['id']}/complete")
        assert r.status_code == 200
        result = r.json()
        # SigningResult structure
        assert "document" in result
        assert "recipient" in result
        assert result["document"]["id"] == doc["id"]
        assert result["document"]["status"] == "COMPLETED"
        assert result["recipient"]["id"] == recip["id"]
        assert result["recipient"]["status"] == "COMPLETED"

    def test_reject_returns_signing_result(self):
        """Reject returns {document, recipient} with REJECTED statuses."""
        doc = create_document({"title": f"Rej-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "R", "email": f"r-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        send_document(doc["id"])

        r = post(f"/api/documents/{doc['id']}/signing/{recip['id']}/reject",
                 {"reason": "Bad doc"})
        assert r.status_code == 200
        result = r.json()
        assert "document" in result
        assert "recipient" in result
        assert result["document"]["status"] == "REJECTED"
        assert result["recipient"]["status"] == "REJECTED"


class TestStatusCodeExactness:
    """Pattern 4: Verify exact status codes (201, 204, 404)."""

    def test_create_document_returns_201(self):
        r = post("/api/documents", {"title": f"SC-{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 201

    def test_create_recipient_returns_201(self):
        doc = create_document({"title": f"SC2-{uuid.uuid4().hex[:8]}"})
        r = post(f"/api/documents/{doc['id']}/recipients", {
            "name": "A", "email": f"a-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        assert r.status_code == 201

    def test_create_field_returns_201(self):
        doc = create_document({"title": f"SC3-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "B", "email": f"b-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        r = post(f"/api/documents/{doc['id']}/fields", {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        assert r.status_code == 201

    def test_delete_document_returns_204(self):
        doc = create_document({"title": f"SC4-{uuid.uuid4().hex[:8]}"})
        r = delete(f"/api/documents/{doc['id']}")
        assert r.status_code == 204

    def test_delete_recipient_returns_204(self):
        doc = create_document({"title": f"SC5-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "D", "email": f"d-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        r = delete(f"/api/documents/{doc['id']}/recipients/{recip['id']}")
        assert r.status_code == 204

    def test_delete_field_returns_204(self):
        doc = create_document({"title": f"SC6-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "E", "email": f"e-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        field = add_field(doc["id"], {
            "type": "TEXT", "recipientId": recip["id"]
        })
        r = delete(f"/api/documents/{doc['id']}/fields/{field['id']}")
        assert r.status_code == 204

    def test_nonexistent_document_returns_404(self):
        r = get("/api/documents/99999999")
        assert r.status_code == 404

    def test_nonexistent_template_returns_404(self):
        r = get("/api/templates/99999999")
        assert r.status_code == 404

    def test_delete_nonexistent_token_returns_404(self):
        r = delete("/api/tokens/99999999")
        assert r.status_code == 404


class TestTokenResponseFields:
    """Pattern 1+5: Token response has correct fields and generated value."""

    def test_token_create_returns_all_fields(self):
        """Token creation returns all camelCase fields with generated token."""
        tag = uuid.uuid4().hex[:8]
        r = post("/api/tokens", {"name": f"TK-{tag}", "expiresAt": "2035-06-15T10:00:00Z"})
        assert r.status_code == 201
        token = r.json()
        assert "id" in token
        assert "name" in token
        assert "token" in token
        assert "createdAt" in token
        assert "expiresAt" in token
        assert token["name"] == f"TK-{tag}"
        assert len(token["token"]) >= 20
        assert token["expiresAt"] is not None

    def test_token_values_unique(self):
        """Each token should have a unique generated token value."""
        r1 = post("/api/tokens", {"name": f"U1-{uuid.uuid4().hex[:6]}"})
        r2 = post("/api/tokens", {"name": f"U2-{uuid.uuid4().hex[:6]}"})
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["token"] != r2.json()["token"]


class TestTemplateFields:
    """Pattern 1+2: Template and template recipient/field have correct fields."""

    def test_template_create_response(self):
        """Template response has camelCase fields."""
        tag = uuid.uuid4().hex[:8]
        r = post("/api/templates", {"title": f"Tmpl-{tag}", "message": "Hi"})
        assert r.status_code == 201
        t = r.json()
        assert "id" in t
        assert "title" in t
        assert "message" in t
        assert "userId" in t
        assert "createdAt" in t
        assert "updatedAt" in t
        assert t["title"] == f"Tmpl-{tag}"
        assert t["message"] == "Hi"

    def test_template_recipient_has_template_id(self):
        """Template recipient must include templateId, not documentId."""
        tmpl = create_template({"title": f"TR-{uuid.uuid4().hex[:8]}"})
        r = post(f"/api/templates/{tmpl['id']}/recipients", {
            "name": "TmplR", "email": f"tr-{uuid.uuid4().hex[:6]}@t.com",
            "role": "SIGNER", "signingOrder": 2,
        })
        assert r.status_code == 201
        rec = r.json()
        assert "templateId" in rec
        assert rec["templateId"] == tmpl["id"]
        assert "signingOrder" in rec
        assert rec["signingOrder"] == 2

    def test_template_field_has_template_id(self):
        """Template field must include templateId, not documentId."""
        tmpl = create_template({"title": f"TF-{uuid.uuid4().hex[:8]}"})
        recip = add_template_recipient(tmpl["id"], {
            "name": "TFR", "email": f"tfr-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        r = post(f"/api/templates/{tmpl['id']}/fields", {
            "type": "CHECKBOX",
            "recipientId": recip["id"],
            "required": True,
            "page": 4,
            "positionX": 33,
            "positionY": 44,
            "width": 20,
            "height": 20,
        })
        assert r.status_code == 201
        field = r.json()
        assert "templateId" in field
        assert field["templateId"] == tmpl["id"]
        assert "recipientId" in field
        assert field["recipientId"] == recip["id"]
        assert field["type"] == "CHECKBOX"
        assert field["page"] == 4


class TestDataIsolationBetweenUsers:
    """Pattern 6: User B cannot see or modify User A's data."""

    def test_user_b_cannot_get_user_a_document(self):
        doc = create_document({"title": f"Iso-{uuid.uuid4().hex[:8]}"}, headers=HEADERS_A)
        r = get(f"/api/documents/{doc['id']}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_user_b_cannot_update_user_a_document(self):
        doc = create_document({"title": f"IsoU-{uuid.uuid4().hex[:8]}"}, headers=HEADERS_A)
        r = put(f"/api/documents/{doc['id']}", {"title": "Hacked"}, headers=HEADERS_B)
        assert r.status_code == 404

    def test_user_b_cannot_delete_user_a_document(self):
        doc = create_document({"title": f"IsoD-{uuid.uuid4().hex[:8]}"}, headers=HEADERS_A)
        r = delete(f"/api/documents/{doc['id']}", headers=HEADERS_B)
        assert r.status_code == 404
        # Verify still exists for user A
        r = get(f"/api/documents/{doc['id']}", headers=HEADERS_A)
        assert r.status_code == 200

    def test_user_b_tokens_isolated_from_user_a(self):
        tag = uuid.uuid4().hex[:8]
        create_token({"name": f"IsoTok-{tag}"}, headers=HEADERS_A)
        tokens_response = get("/api/tokens", headers=HEADERS_B)
        require_status(tokens_response, 200, "Failed to list second user's API tokens")
        tokens_b = tokens_response.json()
        names_b = [t["name"] for t in tokens_b]
        assert f"IsoTok-{tag}" not in names_b


class TestCascadeDeleteSideEffects:
    """Pattern 7: Deleting parent removes children completely."""

    def test_delete_document_cascades_recipients_and_fields(self):
        """After deleting document, its detail returns 404 (recipients/fields gone)."""
        doc = create_document({"title": f"Casc-{uuid.uuid4().hex[:8]}"})
        recip = add_recipient(doc["id"], {
            "name": "Cas", "email": f"cas-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        add_field(doc["id"], {
            "type": "SIGNATURE", "recipientId": recip["id"]
        })
        r = delete(f"/api/documents/{doc['id']}")
        assert r.status_code == 204
        # Document is gone
        assert get(f"/api/documents/{doc['id']}").status_code == 404
        # Recipients endpoint also 404
        assert get(f"/api/documents/{doc['id']}/recipients").status_code == 404
        # Fields endpoint also 404
        assert get(f"/api/documents/{doc['id']}/fields").status_code == 404

    def test_delete_template_cascades_recipients_and_fields(self):
        """After deleting template, it returns 404."""
        tmpl = create_template({"title": f"CascT-{uuid.uuid4().hex[:8]}"})
        recip = add_template_recipient(tmpl["id"], {
            "name": "CT", "email": f"ct-{uuid.uuid4().hex[:6]}@t.com", "role": "SIGNER"
        })
        add_template_field(tmpl["id"], {
            "type": "TEXT", "recipientId": recip["id"]
        })
        r = delete(f"/api/templates/{tmpl['id']}")
        assert r.status_code == 204
        assert get(f"/api/templates/{tmpl['id']}").status_code == 404


class TestUserProfile:
    """Pattern 1: /api/me returns correct camelCase user fields."""

    def test_me_returns_user_fields(self):
        r = get("/api/me", headers=HEADERS_A)
        assert r.status_code == 200
        user = r.json()
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "createdAt" in user
        assert isinstance(user["id"], int)

    def test_me_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/me", timeout=30)
        assert r.status_code == 401
