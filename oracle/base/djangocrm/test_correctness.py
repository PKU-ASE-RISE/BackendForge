"""
BackendForge — Comprehensive Correctness Tests for Django CRM Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

# Org and user IDs (UUIDs)
ORG_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
USER2_ID = str(uuid.uuid4())
OTHER_ORG_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Org-Id": ORG_ID,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-User-Id": USER2_ID,
    "X-Org-Id": ORG_ID,
    "Content-Type": "application/json",
}

OTHER_ORG_HEADERS = {
    "X-User-Id": OTHER_USER_ID,
    "X-Org-Id": OTHER_ORG_ID,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


def _reset_test_context():
    """Give every test two fresh tenants so persisted data cannot cross test boundaries."""
    global ORG_ID, USER_ID, USER2_ID, OTHER_ORG_ID, OTHER_USER_ID
    global HEADERS, HEADERS2, OTHER_ORG_HEADERS, UNIQUE

    ORG_ID = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    USER2_ID = str(uuid.uuid4())
    OTHER_ORG_ID = str(uuid.uuid4())
    OTHER_USER_ID = str(uuid.uuid4())
    HEADERS = {
        "X-User-Id": USER_ID,
        "X-Org-Id": ORG_ID,
        "Content-Type": "application/json",
    }
    HEADERS2 = {
        "X-User-Id": USER2_ID,
        "X-Org-Id": ORG_ID,
        "Content-Type": "application/json",
    }
    OTHER_ORG_HEADERS = {
        "X-User-Id": OTHER_USER_ID,
        "X-Org-Id": OTHER_ORG_ID,
        "Content-Type": "application/json",
    }
    UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def _utc_today():
    return datetime.now(timezone.utc).date()


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def api_delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def register_user(user_id, org_id):
    """Make a request to register a user in the org (for assigned_to validation)."""
    headers = {"X-User-Id": user_id, "X-Org-Id": org_id, "Content-Type": "application/json"}
    response = api_get("/contacts", headers=headers)
    assert response.status_code == 200, response.text


# ════════════════════════════════════════════════════════════════════
# PART 1: Health Check
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_no_auth_required(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_headers_returns_401(self):
        resp = requests.get(f"{BASE_URL}/contacts", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_missing_user_id_returns_401(self):
        headers = {"X-Org-Id": ORG_ID, "Content-Type": "application/json"}
        resp = requests.get(
            f"{BASE_URL}/contacts",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_missing_org_id_returns_401(self):
        headers = {"X-User-Id": USER_ID, "Content-Type": "application/json"}
        resp = requests.get(
            f"{BASE_URL}/contacts",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_auth_on_leads(self):
        resp = requests.get(f"{BASE_URL}/leads", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_auth_on_opportunities(self):
        resp = requests.get(
            f"{BASE_URL}/opportunities",
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_auth_on_activities(self):
        resp = requests.get(f"{BASE_URL}/activities", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_auth_on_pipeline(self):
        resp = requests.get(f"{BASE_URL}/pipeline", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401

    def test_auth_on_comments(self):
        resp = requests.get(
            f"{BASE_URL}/comments",
            params={"entity_type": "lead", "entity_id": str(uuid.uuid4())},
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 401

    def test_auth_on_tags(self):
        resp = requests.get(f"{BASE_URL}/tags", timeout=REQUEST_TIMEOUT)
        assert resp.status_code == 401


# ════════════════════════════════════════════════════════════════════
# PART 3: Company CRUD
# ════════════════════════════════════════════════════════════════════


class TestCompanyCRUD:

    def test_create_company(self):
        resp = api_post("/companies", {
            "name": f"Acme Corp {UNIQUE}",
            "domain": "acme.com",
            "industry": "Technology",
            "size": "large",
            "address": "123 Main St",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        company = resp.json()
        assert company["name"] == f"Acme Corp {UNIQUE}"
        assert company["domain"] == "acme.com"
        assert company["industry"] == "Technology"
        assert company["size"] == "large"
        assert company["address"] == "123 Main St"
        assert "id" in company
        assert company["org_id"] == ORG_ID
        assert company["created_by"] == USER_ID

    def test_create_company_minimal(self):
        resp = api_post("/companies", {"name": f"MinCo {UNIQUE}"})
        assert resp.status_code == 201
        company = resp.json()
        assert company["name"] == f"MinCo {UNIQUE}"
        assert company.get("domain") is None
        assert company.get("industry") is None
        assert company.get("size") is None

    def test_list_companies(self):
        api_post("/companies", {"name": f"ListCo {UNIQUE}"})
        resp = api_get("/companies")
        assert resp.status_code == 200
        companies = resp.json()
        assert isinstance(companies, list)
        names = [c["name"] for c in companies]
        assert f"ListCo {UNIQUE}" in names

    def test_get_company(self):
        create_resp = api_post("/companies", {"name": f"GetCo {UNIQUE}"})
        company_id = create_resp.json()["id"]
        resp = api_get(f"/companies/{company_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == company_id

    def test_update_company(self):
        create_resp = api_post("/companies", {"name": f"UpdCo {UNIQUE}"})
        company_id = create_resp.json()["id"]
        resp = api_put(f"/companies/{company_id}", {
            "name": f"Updated Co {UNIQUE}",
            "domain": "updated.com",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"Updated Co {UNIQUE}"
        assert updated["domain"] == "updated.com"

    def test_delete_company(self):
        create_resp = api_post("/companies", {"name": f"DelCo {UNIQUE}"})
        company_id = create_resp.json()["id"]
        resp = api_delete(f"/companies/{company_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/companies/{company_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_company(self):
        resp = api_get(f"/companies/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_search_companies_by_name(self):
        unique_name = f"SearchableCo_{UNIQUE}"
        api_post("/companies", {"name": unique_name, "domain": "other.io"})
        resp = api_get("/companies", params={"search": unique_name[:10]})
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert unique_name in names

    def test_search_companies_by_domain(self):
        unique_domain = f"{UNIQUE}-domain.com"
        api_post("/companies", {"name": f"DomainCo {UNIQUE}", "domain": unique_domain})
        resp = api_get("/companies", params={"search": unique_domain[:10]})
        assert resp.status_code == 200
        domains = [c.get("domain") for c in resp.json()]
        assert unique_domain in domains


# ════════════════════════════════════════════════════════════════════
# PART 4: Contact CRUD
# ════════════════════════════════════════════════════════════════════


class TestContactCRUD:

    def test_create_contact(self):
        resp = api_post("/contacts", {
            "first_name": "John",
            "last_name": f"Doe-{UNIQUE}",
            "email": f"john-{UNIQUE}@example.com",
            "phone": "+1234567890",
            "address": "456 Oak Ave",
            "tags": ["vip", "enterprise"],
            "notes": "Important client",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        contact = resp.json()
        assert contact["first_name"] == "John"
        assert contact["last_name"] == f"Doe-{UNIQUE}"
        assert contact["email"] == f"john-{UNIQUE}@example.com"
        assert contact["phone"] == "+1234567890"
        assert "vip" in contact["tags"]
        assert "enterprise" in contact["tags"]
        assert contact["org_id"] == ORG_ID
        assert contact["created_by"] == USER_ID
        assert "id" in contact
        assert "created_at" in contact
        assert "updated_at" in contact

    def test_create_contact_minimal(self):
        resp = api_post("/contacts", {
            "first_name": "Min",
            "last_name": f"Contact-{UNIQUE}",
        })
        assert resp.status_code == 201
        contact = resp.json()
        assert contact["first_name"] == "Min"
        assert contact["tags"] == []

    def test_create_contact_with_company(self):
        co_resp = api_post("/companies", {"name": f"ContactCo {UNIQUE}"})
        company_id = co_resp.json()["id"]
        resp = api_post("/contacts", {
            "first_name": "Linked",
            "last_name": f"Person-{UNIQUE}",
            "company_id": company_id,
        })
        assert resp.status_code == 201
        assert resp.json()["company_id"] == company_id

    def test_list_contacts(self):
        api_post("/contacts", {"first_name": "List", "last_name": f"User-{UNIQUE}"})
        resp = api_get("/contacts")
        assert resp.status_code == 200
        contacts = resp.json()
        assert isinstance(contacts, list)
        assert len(contacts) >= 1

    def test_get_contact(self):
        create_resp = api_post("/contacts", {"first_name": "Get", "last_name": f"Me-{UNIQUE}"})
        contact_id = create_resp.json()["id"]
        resp = api_get(f"/contacts/{contact_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == contact_id

    def test_update_contact(self):
        create_resp = api_post("/contacts", {"first_name": "Upd", "last_name": f"Contact-{UNIQUE}"})
        contact_id = create_resp.json()["id"]
        resp = api_put(f"/contacts/{contact_id}", {
            "first_name": "Updated",
            "last_name": f"Contact-{UNIQUE}",
            "email": "updated@example.com",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["first_name"] == "Updated"
        assert updated["email"] == "updated@example.com"

    def test_delete_contact(self):
        create_resp = api_post("/contacts", {"first_name": "Del", "last_name": f"Contact-{UNIQUE}"})
        contact_id = create_resp.json()["id"]
        resp = api_delete(f"/contacts/{contact_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/contacts/{contact_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_contact(self):
        resp = api_get(f"/contacts/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_search_contacts_by_name(self):
        unique_last = f"Searchable-{UNIQUE}"
        api_post("/contacts", {"first_name": "Finder", "last_name": unique_last})
        resp = api_get("/contacts", params={"search": unique_last[:10]})
        assert resp.status_code == 200
        last_names = [c["last_name"] for c in resp.json()]
        assert unique_last in last_names

    def test_search_contacts_by_email(self):
        unique_email = f"unique-{UNIQUE}@search.com"
        api_post(
            "/contacts",
            {
                "first_name": "Email",
                "last_name": f"Search-{UNIQUE}",
                "email": unique_email,
            },
        )
        resp = api_get("/contacts", params={"search": f"unique-{UNIQUE}"})
        assert resp.status_code == 200
        emails = [c.get("email") for c in resp.json()]
        assert unique_email in emails

    def test_filter_contacts_by_tag(self):
        tag_name = f"filtertag-{UNIQUE}"
        api_post(
            "/contacts",
            {"first_name": "Tagged", "last_name": f"One-{UNIQUE}", "tags": [tag_name]},
        )
        api_post(
            "/contacts",
            {"first_name": "NoTag", "last_name": f"Two-{UNIQUE}", "tags": []},
        )
        resp = api_get("/contacts", params={"tag": tag_name})
        assert resp.status_code == 200
        contacts = resp.json()
        for c in contacts:
            assert tag_name in c["tags"]


# ════════════════════════════════════════════════════════════════════
# PART 5: Lead CRUD
# ════════════════════════════════════════════════════════════════════


class TestLeadCRUD:

    def test_create_lead(self):
        # Register user first for assigned_to
        register_user(USER_ID, ORG_ID)
        contact_resp = api_post("/contacts", {"first_name": "Lead", "last_name": f"Contact-{UNIQUE}"})
        contact_id = contact_resp.json()["id"]

        resp = api_post("/leads", {
            "contact_id": contact_id,
            "source": "web",
            "assigned_to": USER_ID,
            "value": 5000,
            "tags": ["hot"],
            "notes": "Great prospect",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        lead = resp.json()
        assert lead["source"] == "web"
        assert lead["status"] == "new"
        assert lead["assigned_to"] == USER_ID
        assert lead["value"] == 5000
        assert "hot" in lead["tags"]
        assert lead["contact_id"] == contact_id
        assert lead["org_id"] == ORG_ID
        assert "id" in lead

    def test_create_lead_minimal(self):
        resp = api_post("/leads", {"source": "email"})
        assert resp.status_code == 201
        lead = resp.json()
        assert lead["source"] == "email"
        assert lead["status"] == "new"
        assert lead["tags"] == []

    def test_list_leads(self):
        api_post("/leads", {"source": "referral"})
        resp = api_get("/leads")
        assert resp.status_code == 200
        leads = resp.json()
        assert isinstance(leads, list)
        assert len(leads) >= 1

    def test_get_lead(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        resp = api_get(f"/leads/{lead_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == lead_id

    def test_update_lead_basic(self):
        create_resp = api_post("/leads", {"source": "web", "value": 1000})
        lead_id = create_resp.json()["id"]
        resp = api_put(f"/leads/{lead_id}", {"value": 2000, "notes": "Updated"})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["value"] == 2000
        assert updated["notes"] == "Updated"

    def test_delete_lead(self):
        create_resp = api_post("/leads", {"source": "other"})
        lead_id = create_resp.json()["id"]
        resp = api_delete(f"/leads/{lead_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/leads/{lead_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_lead(self):
        resp = api_get(f"/leads/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_filter_leads_by_status(self):
        api_post("/leads", {"source": "web"})  # status = new
        resp = api_get("/leads", params={"status": "new"})
        assert resp.status_code == 200
        for lead in resp.json():
            assert lead["status"] == "new"

    def test_filter_leads_by_assigned_to(self):
        register_user(USER_ID, ORG_ID)
        api_post("/leads", {"source": "web", "assigned_to": USER_ID})
        resp = api_get("/leads", params={"assigned_to": USER_ID})
        assert resp.status_code == 200
        for lead in resp.json():
            assert lead["assigned_to"] == USER_ID


# ════════════════════════════════════════════════════════════════════
# PART 6: Lead Status Transitions
# ════════════════════════════════════════════════════════════════════


class TestLeadStatusTransitions:

    def test_valid_transition_new_to_contacted(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        resp = api_put(f"/leads/{lead_id}", {"status": "contacted"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "contacted"

    def test_valid_transition_contacted_to_qualified(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        resp = api_put(f"/leads/{lead_id}", {"status": "qualified"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "qualified"

    def test_valid_transition_new_to_lost(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        resp = api_put(f"/leads/{lead_id}", {"status": "lost"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "lost"

    def test_valid_transition_contacted_to_lost(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        resp = api_put(f"/leads/{lead_id}", {"status": "lost"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "lost"

    def test_valid_transition_qualified_to_lost(self):
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        api_put(f"/leads/{lead_id}", {"status": "qualified"})
        resp = api_put(f"/leads/{lead_id}", {"status": "lost"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "lost"

    def test_invalid_transition_backwards(self):
        """Cannot go from contacted back to new."""
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        resp = api_put(f"/leads/{lead_id}", {"status": "new"})
        assert resp.status_code == 422

    def test_invalid_transition_skip_forward(self):
        """Cannot skip from new to qualified."""
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        resp = api_put(f"/leads/{lead_id}", {"status": "qualified"})
        assert resp.status_code == 422

    def test_cannot_set_converted_via_put(self):
        """Cannot directly set status to converted via PUT."""
        create_resp = api_post("/leads", {"source": "web"})
        lead_id = create_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        api_put(f"/leads/{lead_id}", {"status": "qualified"})
        resp = api_put(f"/leads/{lead_id}", {"status": "converted"})
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 7: Lead Conversion
# ════════════════════════════════════════════════════════════════════


class TestLeadConversion:

    def test_convert_qualified_lead(self):
        register_user(USER_ID, ORG_ID)
        # Create contact
        contact_resp = api_post("/contacts", {"first_name": "Convert", "last_name": f"Lead-{UNIQUE}"})
        contact_id = contact_resp.json()["id"]

        # Create and qualify lead
        lead_resp = api_post("/leads", {
            "source": "web",
            "contact_id": contact_id,
            "assigned_to": USER_ID,
            "value": 10000,
        })
        lead_id = lead_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        api_put(f"/leads/{lead_id}", {"status": "qualified"})

        # Convert
        resp = api_post(f"/leads/{lead_id}/convert")
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        opp = resp.json()
        assert opp["stage"] == "prospecting"
        assert opp["value"] == 10000
        assert opp["probability"] == 10
        assert opp["lead_id"] == lead_id
        assert opp["contact_id"] == contact_id
        assert opp["assigned_to"] == USER_ID
        assert "Opportunity from Convert" in opp["title"] or "Convert" in opp["title"]

        # Verify lead is now converted
        lead_resp = api_get(f"/leads/{lead_id}")
        assert lead_resp.json()["status"] == "converted"

    def test_convert_non_qualified_lead_fails(self):
        """Lead must be qualified to convert."""
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]
        resp = api_post(f"/leads/{lead_id}/convert")
        assert resp.status_code == 422

    def test_convert_contacted_lead_fails(self):
        """Even contacted is not enough — must be qualified."""
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]
        api_put(f"/leads/{lead_id}", {"status": "contacted"})
        resp = api_post(f"/leads/{lead_id}/convert")
        assert resp.status_code == 422

    def test_convert_nonexistent_lead(self):
        resp = api_post(f"/leads/{uuid.uuid4()}/convert")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Opportunity CRUD
# ════════════════════════════════════════════════════════════════════


class TestOpportunityCRUD:

    def test_create_opportunity(self):
        register_user(USER_ID, ORG_ID)
        resp = api_post("/opportunities", {
            "title": f"Big Deal {UNIQUE}",
            "stage": "prospecting",
            "value": 50000,
            "probability": 25,
            "close_date": "2025-12-31",
            "assigned_to": USER_ID,
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        opp = resp.json()
        assert opp["title"] == f"Big Deal {UNIQUE}"
        assert opp["stage"] == "prospecting"
        assert opp["value"] == 50000
        assert opp["probability"] == 25
        assert opp["close_date"] == "2025-12-31"
        assert opp["org_id"] == ORG_ID
        assert "id" in opp

    def test_create_opportunity_minimal(self):
        resp = api_post("/opportunities", {"title": f"Min Deal {UNIQUE}"})
        assert resp.status_code == 201
        opp = resp.json()
        assert opp["title"] == f"Min Deal {UNIQUE}"
        assert opp["stage"] == "prospecting"
        assert opp["value"] == 0
        assert opp["probability"] == 10

    def test_list_opportunities(self):
        api_post("/opportunities", {"title": f"List Deal {UNIQUE}"})
        resp = api_get("/opportunities")
        assert resp.status_code == 200
        opps = resp.json()
        assert isinstance(opps, list)
        assert len(opps) >= 1

    def test_get_opportunity(self):
        create_resp = api_post("/opportunities", {"title": f"Get Deal {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        resp = api_get(f"/opportunities/{opp_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == opp_id

    def test_update_opportunity(self):
        create_resp = api_post("/opportunities", {"title": f"Upd Deal {UNIQUE}", "value": 1000})
        opp_id = create_resp.json()["id"]
        resp = api_put(f"/opportunities/{opp_id}", {"value": 2000, "probability": 50})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["value"] == 2000
        assert updated["probability"] == 50

    def test_delete_opportunity(self):
        create_resp = api_post("/opportunities", {"title": f"Del Deal {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        resp = api_delete(f"/opportunities/{opp_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_opportunity(self):
        resp = api_get(f"/opportunities/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_filter_opportunities_by_stage(self):
        api_post(
            "/opportunities", {"title": f"Stage Deal {UNIQUE}", "stage": "proposal"}
        )
        resp = api_get("/opportunities", params={"stage": "proposal"})
        assert resp.status_code == 200
        for opp in resp.json():
            assert opp["stage"] == "proposal"

    def test_filter_opportunities_by_assigned_to(self):
        register_user(USER_ID, ORG_ID)
        api_post(
            "/opportunities",
            {"title": f"Assigned Deal {UNIQUE}", "assigned_to": USER_ID},
        )
        resp = api_get("/opportunities", params={"assigned_to": USER_ID})
        assert resp.status_code == 200
        for opp in resp.json():
            assert opp["assigned_to"] == USER_ID


# ════════════════════════════════════════════════════════════════════
# PART 9: Opportunity Stage Transitions
# ════════════════════════════════════════════════════════════════════


class TestOpportunityStageTransitions:

    def test_valid_transition_prospecting_to_proposal(self):
        create_resp = api_post("/opportunities", {"title": f"Trans1 {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        assert resp.status_code == 200
        assert resp.json()["stage"] == "proposal"

    def test_valid_transition_proposal_to_negotiation(self):
        create_resp = api_post("/opportunities", {"title": f"Trans2 {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "negotiation"})
        assert resp.status_code == 200
        assert resp.json()["stage"] == "negotiation"

    def test_valid_transition_negotiation_to_closed_won(self):
        create_resp = api_post("/opportunities", {"title": f"Trans3 {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        api_put(f"/opportunities/{opp_id}", {"stage": "negotiation"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "closed_won"})
        assert resp.status_code == 200
        assert resp.json()["stage"] == "closed_won"

    def test_any_stage_to_closed_lost(self):
        """Any stage can go to closed_lost."""
        create_resp = api_post("/opportunities", {"title": f"Lost1 {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "closed_lost"})
        assert resp.status_code == 200
        assert resp.json()["stage"] == "closed_lost"

    def test_proposal_to_closed_lost(self):
        create_resp = api_post("/opportunities", {"title": f"Lost2 {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "closed_lost"})
        assert resp.status_code == 200
        assert resp.json()["stage"] == "closed_lost"

    def test_invalid_transition_skip_stages(self):
        """Cannot skip from prospecting to negotiation."""
        create_resp = api_post("/opportunities", {"title": f"Skip {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "negotiation"})
        assert resp.status_code == 422

    def test_invalid_transition_backwards(self):
        """Cannot go from proposal back to prospecting."""
        create_resp = api_post("/opportunities", {"title": f"Back {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "prospecting"})
        assert resp.status_code == 422

    def test_cannot_transition_from_closed_won(self):
        """closed_won is terminal."""
        create_resp = api_post("/opportunities", {"title": f"Won {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "proposal"})
        api_put(f"/opportunities/{opp_id}", {"stage": "negotiation"})
        api_put(f"/opportunities/{opp_id}", {"stage": "closed_won"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "prospecting"})
        assert resp.status_code == 422

    def test_cannot_transition_from_closed_lost(self):
        """closed_lost is terminal."""
        create_resp = api_post("/opportunities", {"title": f"LostTerm {UNIQUE}"})
        opp_id = create_resp.json()["id"]
        api_put(f"/opportunities/{opp_id}", {"stage": "closed_lost"})
        resp = api_put(f"/opportunities/{opp_id}", {"stage": "prospecting"})
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 10: Activities CRUD
# ════════════════════════════════════════════════════════════════════


class TestActivityCRUD:

    def test_create_activity(self):
        future_date = (_utc_today() + timedelta(days=7)).isoformat()
        resp = api_post("/activities", {
            "type": "call",
            "subject": f"Follow up {UNIQUE}",
            "due_date": future_date,
            "completed": False,
            "notes": "Call about proposal",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        activity = resp.json()
        assert activity["type"] == "call"
        assert activity["subject"] == f"Follow up {UNIQUE}"
        assert activity["due_date"] == future_date
        assert activity["completed"] is False
        assert activity["org_id"] == ORG_ID
        assert "id" in activity

    def test_create_activity_minimal(self):
        resp = api_post("/activities", {
            "type": "task",
            "subject": f"Min Activity {UNIQUE}",
        })
        assert resp.status_code == 201
        activity = resp.json()
        assert activity["type"] == "task"
        assert activity["completed"] is False

    def test_create_activity_linked_to_contact(self):
        contact_resp = api_post("/contacts", {"first_name": "Act", "last_name": f"Contact-{UNIQUE}"})
        contact_id = contact_resp.json()["id"]
        resp = api_post("/activities", {
            "type": "email",
            "subject": f"Email to {UNIQUE}",
            "contact_id": contact_id,
        })
        assert resp.status_code == 201
        assert resp.json()["contact_id"] == contact_id

    def test_create_activity_linked_to_lead(self):
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]
        resp = api_post("/activities", {
            "type": "meeting",
            "subject": f"Meet about {UNIQUE}",
            "lead_id": lead_id,
        })
        assert resp.status_code == 201
        assert resp.json()["lead_id"] == lead_id

    def test_create_activity_linked_to_opportunity(self):
        opp_resp = api_post("/opportunities", {"title": f"Opp Act {UNIQUE}"})
        opp_id = opp_resp.json()["id"]
        resp = api_post("/activities", {
            "type": "task",
            "subject": f"Prep for {UNIQUE}",
            "opportunity_id": opp_id,
        })
        assert resp.status_code == 201
        assert resp.json()["opportunity_id"] == opp_id

    def test_list_activities(self):
        api_post("/activities", {"type": "call", "subject": f"List Act {UNIQUE}"})
        resp = api_get("/activities")
        assert resp.status_code == 200
        activities = resp.json()
        assert isinstance(activities, list)
        assert len(activities) >= 1

    def test_get_activity(self):
        create_resp = api_post("/activities", {"type": "task", "subject": f"Get Act {UNIQUE}"})
        act_id = create_resp.json()["id"]
        resp = api_get(f"/activities/{act_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == act_id

    def test_update_activity(self):
        future_date = (_utc_today() + timedelta(days=7)).isoformat()
        create_resp = api_post("/activities", {"type": "call", "subject": f"Upd Act {UNIQUE}", "due_date": future_date})
        act_id = create_resp.json()["id"]
        resp = api_put(f"/activities/{act_id}", {"subject": f"Updated Act {UNIQUE}", "completed": True})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["subject"] == f"Updated Act {UNIQUE}"
        assert updated["completed"] is True

    def test_delete_activity(self):
        create_resp = api_post("/activities", {"type": "task", "subject": f"Del Act {UNIQUE}"})
        act_id = create_resp.json()["id"]
        resp = api_delete(f"/activities/{act_id}")
        assert resp.status_code == 204
        get_resp = api_get(f"/activities/{act_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_activity(self):
        resp = api_get(f"/activities/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_filter_activities_by_type(self):
        api_post(
            "/activities", {"type": "meeting", "subject": f"Filter Meet {UNIQUE}"}
        )
        resp = api_get("/activities", params={"type": "meeting"})
        assert resp.status_code == 200
        for act in resp.json():
            assert act["type"] == "meeting"

    def test_filter_activities_by_completed(self):
        future_date = (_utc_today() + timedelta(days=7)).isoformat()
        create_resp = api_post("/activities", {"type": "task", "subject": f"Comp Act {UNIQUE}", "due_date": future_date})
        act_id = create_resp.json()["id"]
        api_put(f"/activities/{act_id}", {"completed": True})

        resp = api_get("/activities", params={"completed": "true"})
        assert resp.status_code == 200
        for act in resp.json():
            assert act["completed"] is True

    def test_due_date_in_past_rejected_on_create(self):
        """Cannot create activity with due_date in the past."""
        past_date = (_utc_today() - timedelta(days=1)).isoformat()
        resp = api_post("/activities", {
            "type": "call",
            "subject": f"Past Act {UNIQUE}",
            "due_date": past_date,
        })
        assert resp.status_code == 422

    def test_due_date_in_past_allowed_on_update(self):
        """Updating an activity with past due_date is allowed."""
        future_date = (_utc_today() + timedelta(days=7)).isoformat()
        create_resp = api_post("/activities", {"type": "call", "subject": f"Reschedule {UNIQUE}", "due_date": future_date})
        act_id = create_resp.json()["id"]
        past_date = (_utc_today() - timedelta(days=1)).isoformat()
        resp = api_put(f"/activities/{act_id}", {"due_date": past_date})
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 11: Pipeline
# ════════════════════════════════════════════════════════════════════


class TestPipeline:

    def test_pipeline_structure(self):
        resp = api_get("/pipeline")
        assert resp.status_code == 200
        data = resp.json()
        for stage in ["prospecting", "proposal", "negotiation", "closed_won", "closed_lost"]:
            assert stage in data, f"Missing stage: {stage}"
            assert "count" in data[stage]
            assert "total_value" in data[stage]
            assert "weighted_value" in data[stage]

    def test_pipeline_aggregation(self):
        """Pipeline should aggregate values correctly."""
        # Create opportunities with known values
        unique_suffix = uuid.uuid4().hex[:8]
        api_post("/opportunities", {"title": f"Pipe1-{unique_suffix}", "stage": "prospecting", "value": 10000, "probability": 20})
        api_post("/opportunities", {"title": f"Pipe2-{unique_suffix}", "stage": "prospecting", "value": 20000, "probability": 30})

        resp = api_get("/pipeline")
        assert resp.status_code == 200
        prospecting = resp.json()["prospecting"]
        # At least these two should be there (there might be more from other tests)
        assert prospecting["count"] >= 2
        assert prospecting["total_value"] >= 30000
        # weighted = 10000*20/100 + 20000*30/100 = 2000 + 6000 = 8000 (at least)
        assert prospecting["weighted_value"] >= 8000

    def test_pipeline_empty_stages_have_zeros(self):
        """Stages with no deals should still appear with zero values."""
        # Use a separate org to get clean pipeline
        clean_org = str(uuid.uuid4())
        clean_user = str(uuid.uuid4())
        headers = {"X-User-Id": clean_user, "X-Org-Id": clean_org, "Content-Type": "application/json"}
        resp = api_get("/pipeline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for stage in ["prospecting", "proposal", "negotiation", "closed_won", "closed_lost"]:
            assert data[stage]["count"] == 0
            assert data[stage]["total_value"] == 0
            assert data[stage]["weighted_value"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 12: Comments
# ════════════════════════════════════════════════════════════════════


class TestComments:

    def test_create_comment_on_lead(self):
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]
        resp = api_post("/comments", {
            "entity_type": "lead",
            "entity_id": lead_id,
            "content": f"This is a comment {UNIQUE}",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        comment = resp.json()
        assert comment["entity_type"] == "lead"
        assert comment["entity_id"] == lead_id
        assert comment["content"] == f"This is a comment {UNIQUE}"
        assert comment["created_by"] == USER_ID
        assert "id" in comment
        assert "created_at" in comment

    def test_create_comment_on_opportunity(self):
        opp_resp = api_post("/opportunities", {"title": f"Comment Opp {UNIQUE}"})
        opp_id = opp_resp.json()["id"]
        resp = api_post("/comments", {
            "entity_type": "opportunity",
            "entity_id": opp_id,
            "content": f"Deal looks promising {UNIQUE}",
        })
        assert resp.status_code == 201
        comment = resp.json()
        assert comment["entity_type"] == "opportunity"
        assert comment["entity_id"] == opp_id

    def test_list_comments_for_lead(self):
        lead_resp = api_post("/leads", {"source": "email"})
        lead_id = lead_resp.json()["id"]
        api_post(
            "/comments",
            {"entity_type": "lead", "entity_id": lead_id, "content": "Comment A"},
        )
        api_post(
            "/comments",
            {"entity_type": "lead", "entity_id": lead_id, "content": "Comment B"},
        )

        resp = api_get("/comments", params={"entity_type": "lead", "entity_id": lead_id})
        assert resp.status_code == 200
        comments = resp.json()
        assert isinstance(comments, list)
        assert len(comments) >= 2

    def test_list_comments_for_opportunity(self):
        opp_resp = api_post("/opportunities", {"title": f"List Comm Opp {UNIQUE}"})
        opp_id = opp_resp.json()["id"]
        api_post(
            "/comments",
            {"entity_type": "opportunity", "entity_id": opp_id, "content": "Great deal"},
        )

        resp = api_get("/comments", params={"entity_type": "opportunity", "entity_id": opp_id})
        assert resp.status_code == 200
        comments = resp.json()
        assert len(comments) >= 1

    def test_delete_comment(self):
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]
        comment_resp = api_post("/comments", {
            "entity_type": "lead",
            "entity_id": lead_id,
            "content": "To be deleted",
        })
        comment_id = comment_resp.json()["id"]
        resp = api_delete(f"/comments/{comment_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_comment(self):
        resp = api_delete(f"/comments/{uuid.uuid4()}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Tags
# ════════════════════════════════════════════════════════════════════


class TestTags:

    def test_create_tag(self):
        resp = api_post("/tags", {"name": f"tag-{UNIQUE}"})
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        tag = resp.json()
        assert tag["name"] == f"tag-{UNIQUE}"
        assert tag["org_id"] == ORG_ID
        assert "id" in tag
        assert "created_at" in tag

    def test_create_tag_idempotent(self):
        """Creating same tag name twice returns the same tag."""
        tag_name = f"idem-tag-{UNIQUE}"
        resp1 = api_post("/tags", {"name": tag_name})
        assert resp1.status_code == 201
        resp2 = api_post("/tags", {"name": tag_name})
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]

    def test_list_tags(self):
        tag_name = f"list-tag-{UNIQUE}"
        api_post("/tags", {"name": tag_name})
        resp = api_get("/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert isinstance(tags, list)
        names = [t["name"] for t in tags]
        assert tag_name in names

    def test_delete_tag(self):
        resp = api_post("/tags", {"name": f"del-tag-{UNIQUE}"})
        tag_id = resp.json()["id"]
        del_resp = api_delete(f"/tags/{tag_id}")
        assert del_resp.status_code == 204

        # Verify it's gone
        list_resp = api_get("/tags")
        tag_ids = [t["id"] for t in list_resp.json()]
        assert tag_id not in tag_ids

    def test_delete_nonexistent_tag(self):
        resp = api_delete(f"/tags/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_tags_auto_created_on_contact(self):
        """Tags specified on contact creation are auto-created."""
        tag_name = f"auto-tag-{UNIQUE}"
        api_post("/contacts", {"first_name": "Auto", "last_name": f"Tag-{UNIQUE}", "tags": [tag_name]})
        resp = api_get("/tags")
        names = [t["name"] for t in resp.json()]
        assert tag_name in names

    def test_delete_tag_removes_from_contacts(self):
        """Deleting a tag removes it from contacts that reference it."""
        tag_name = f"remove-tag-{UNIQUE}"
        contact_resp = api_post("/contacts", {"first_name": "TagRm", "last_name": f"Test-{UNIQUE}", "tags": [tag_name]})
        contact_id = contact_resp.json()["id"]

        # Get the tag id
        tags_resp = api_get("/tags")
        tag_id = None
        for t in tags_resp.json():
            if t["name"] == tag_name:
                tag_id = t["id"]
                break
        assert tag_id is not None

        # Delete the tag
        api_delete(f"/tags/{tag_id}")

        # Contact should no longer have this tag
        contact_resp = api_get(f"/contacts/{contact_id}")
        assert tag_name not in contact_resp.json()["tags"]


# ════════════════════════════════════════════════════════════════════
# PART 14: Assigned-To Validation
# ════════════════════════════════════════════════════════════════════


class TestAssignedToValidation:

    def test_valid_assigned_to_on_lead(self):
        """A registered user in the org can be assigned."""
        register_user(USER_ID, ORG_ID)
        resp = api_post("/leads", {"source": "web", "assigned_to": USER_ID})
        assert resp.status_code == 201
        assert resp.json()["assigned_to"] == USER_ID

    def test_invalid_assigned_to_on_lead(self):
        """An unknown user cannot be assigned."""
        fake_user = str(uuid.uuid4())
        resp = api_post("/leads", {"source": "web", "assigned_to": fake_user})
        assert resp.status_code == 422

    def test_valid_assigned_to_on_opportunity(self):
        register_user(USER_ID, ORG_ID)
        resp = api_post("/opportunities", {"title": f"Assign Opp {UNIQUE}", "assigned_to": USER_ID})
        assert resp.status_code == 201
        assert resp.json()["assigned_to"] == USER_ID

    def test_invalid_assigned_to_on_opportunity(self):
        fake_user = str(uuid.uuid4())
        resp = api_post("/opportunities", {"title": f"Bad Assign {UNIQUE}", "assigned_to": fake_user})
        assert resp.status_code == 422

    def test_null_assigned_to_is_valid(self):
        """Null assigned_to is always valid."""
        resp = api_post("/leads", {"source": "web", "assigned_to": None})
        assert resp.status_code == 201
        assert resp.json()["assigned_to"] is None

    def test_other_org_user_not_valid(self):
        """A user registered in a different org is not valid for this org."""
        register_user(OTHER_USER_ID, OTHER_ORG_ID)
        resp = api_post("/leads", {"source": "web", "assigned_to": OTHER_USER_ID})
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════════════
# PART 15: Data Isolation (Org Scoping)
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_contacts_isolated_by_org(self):
        """Contacts from one org are not visible to another org."""
        unique_name = f"Isolated-{UNIQUE}"
        api_post("/contacts", {"first_name": "Org1", "last_name": unique_name})

        resp = api_get("/contacts", headers=OTHER_ORG_HEADERS)
        assert resp.status_code == 200
        last_names = [c["last_name"] for c in resp.json()]
        assert unique_name not in last_names

    def test_companies_isolated_by_org(self):
        unique_name = f"IsolatedCo-{UNIQUE}"
        api_post("/companies", {"name": unique_name})

        resp = api_get("/companies", headers=OTHER_ORG_HEADERS)
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert unique_name not in names

    def test_leads_isolated_by_org(self):
        lead_resp = api_post("/leads", {"source": "web", "notes": f"isolated-{UNIQUE}"})
        lead_id = lead_resp.json()["id"]

        resp = api_get(f"/leads/{lead_id}", headers=OTHER_ORG_HEADERS)
        assert resp.status_code == 404

    def test_opportunities_isolated_by_org(self):
        opp_resp = api_post("/opportunities", {"title": f"Isolated Opp {UNIQUE}"})
        opp_id = opp_resp.json()["id"]

        resp = api_get(f"/opportunities/{opp_id}", headers=OTHER_ORG_HEADERS)
        assert resp.status_code == 404

    def test_same_org_different_users_share_data(self):
        """Two users in the same org can see each other's data."""
        unique_name = f"Shared-{UNIQUE}"
        api_post("/contacts", {"first_name": "User1", "last_name": unique_name}, headers=HEADERS)

        resp = api_get("/contacts", headers=HEADERS2)
        assert resp.status_code == 200
        last_names = [c["last_name"] for c in resp.json()]
        assert unique_name in last_names

    def test_tags_isolated_by_org(self):
        tag_name = f"org-tag-{UNIQUE}"
        api_post("/tags", {"name": tag_name})

        resp = api_get("/tags", headers=OTHER_ORG_HEADERS)
        names = [t["name"] for t in resp.json()]
        assert tag_name not in names

    def test_pipeline_isolated_by_org(self):
        """Pipeline should only show opportunities from the same org."""
        api_post("/opportunities", {"title": f"Pipe Iso {UNIQUE}", "value": 99999, "probability": 100})

        resp = api_get("/pipeline", headers=OTHER_ORG_HEADERS)
        data = resp.json()
        # The other org should have empty pipeline
        total = sum(data[stage]["total_value"] for stage in data)
        assert 99999 not in [data[stage]["total_value"] for stage in data]


# ════════════════════════════════════════════════════════════════════
# PART 16: Cascade / Nullification Rules
# ════════════════════════════════════════════════════════════════════


class TestCascadeRules:

    def test_delete_contact_deletes_activities(self):
        """Deleting a contact removes its linked activities."""
        contact_resp = api_post("/contacts", {"first_name": "Cascade", "last_name": f"Del-{UNIQUE}"})
        contact_id = contact_resp.json()["id"]

        act_resp = api_post("/activities", {
            "type": "call",
            "subject": f"Cascade Act {UNIQUE}",
            "contact_id": contact_id,
        })
        act_id = act_resp.json()["id"]

        api_delete(f"/contacts/{contact_id}")
        resp = api_get(f"/activities/{act_id}")
        assert resp.status_code == 404

    def test_delete_contact_nullifies_lead_contact_id(self):
        """Deleting a contact nullifies contact_id on linked leads."""
        contact_resp = api_post("/contacts", {"first_name": "LeadLink", "last_name": f"Del-{UNIQUE}"})
        contact_id = contact_resp.json()["id"]

        lead_resp = api_post("/leads", {"source": "web", "contact_id": contact_id})
        lead_id = lead_resp.json()["id"]

        api_delete(f"/contacts/{contact_id}")
        lead = api_get(f"/leads/{lead_id}").json()
        assert lead["contact_id"] is None

    def test_delete_company_nullifies_contact_company_id(self):
        """Deleting a company nullifies company_id on linked contacts."""
        co_resp = api_post("/companies", {"name": f"CascadeCo {UNIQUE}"})
        company_id = co_resp.json()["id"]

        contact_resp = api_post("/contacts", {
            "first_name": "CoLink",
            "last_name": f"Test-{UNIQUE}",
            "company_id": company_id,
        })
        contact_id = contact_resp.json()["id"]

        api_delete(f"/companies/{company_id}")
        contact = api_get(f"/contacts/{contact_id}").json()
        assert contact["company_id"] is None

    def test_delete_lead_deletes_activities(self):
        """Deleting a lead removes its linked activities."""
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]

        act_resp = api_post("/activities", {
            "type": "task",
            "subject": f"Lead Act {UNIQUE}",
            "lead_id": lead_id,
        })
        act_id = act_resp.json()["id"]

        api_delete(f"/leads/{lead_id}")
        resp = api_get(f"/activities/{act_id}")
        assert resp.status_code == 404

    def test_delete_lead_deletes_comments(self):
        """Deleting a lead removes its linked comments."""
        lead_resp = api_post("/leads", {"source": "web"})
        lead_id = lead_resp.json()["id"]

        comment_resp = api_post("/comments", {
            "entity_type": "lead",
            "entity_id": lead_id,
            "content": "Will be deleted",
        })
        comment_id = comment_resp.json()["id"]

        api_delete(f"/leads/{lead_id}")
        # Verify comment is gone by listing
        resp = api_get("/comments", params={"entity_type": "lead", "entity_id": lead_id})
        comment_ids = [c["id"] for c in resp.json()]
        assert comment_id not in comment_ids

    def test_delete_opportunity_deletes_activities(self):
        """Deleting an opportunity removes its linked activities."""
        opp_resp = api_post("/opportunities", {"title": f"Cascade Opp {UNIQUE}"})
        opp_id = opp_resp.json()["id"]

        act_resp = api_post("/activities", {
            "type": "meeting",
            "subject": f"Opp Act {UNIQUE}",
            "opportunity_id": opp_id,
        })
        act_id = act_resp.json()["id"]

        api_delete(f"/opportunities/{opp_id}")
        resp = api_get(f"/activities/{act_id}")
        assert resp.status_code == 404

    def test_delete_opportunity_deletes_comments(self):
        """Deleting an opportunity removes its linked comments."""
        opp_resp = api_post("/opportunities", {"title": f"Cascade Comm Opp {UNIQUE}"})
        opp_id = opp_resp.json()["id"]

        comment_resp = api_post("/comments", {
            "entity_type": "opportunity",
            "entity_id": opp_id,
            "content": "Will be deleted too",
        })
        comment_id = comment_resp.json()["id"]

        api_delete(f"/opportunities/{opp_id}")
        resp = api_get("/comments", params={"entity_type": "opportunity", "entity_id": opp_id})
        comment_ids = [c["id"] for c in resp.json()]
        assert comment_id not in comment_ids


# ════════════════════════════════════════════════════════════════════
# PART 17: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_contacts_list(self):
        """New org should have empty contacts."""
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "X-Org-Id": org_id, "Content-Type": "application/json"}
        resp = api_get("/contacts", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_leads_list(self):
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "X-Org-Id": org_id, "Content-Type": "application/json"}
        resp = api_get("/leads", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_opportunities_list(self):
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        headers = {"X-User-Id": user_id, "X-Org-Id": org_id, "Content-Type": "application/json"}
        resp = api_get("/opportunities", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_nonexistent_contact(self):
        resp = api_put(f"/contacts/{uuid.uuid4()}", {"first_name": "Ghost"})
        assert resp.status_code == 404

    def test_update_nonexistent_lead(self):
        resp = api_put(f"/leads/{uuid.uuid4()}", {"value": 999})
        assert resp.status_code == 404

    def test_update_nonexistent_opportunity(self):
        resp = api_put(f"/opportunities/{uuid.uuid4()}", {"value": 999})
        assert resp.status_code == 404

    def test_update_nonexistent_activity(self):
        resp = api_put(f"/activities/{uuid.uuid4()}", {"subject": "Ghost"})
        assert resp.status_code == 404

    def test_lead_default_status_is_new(self):
        resp = api_post("/leads", {"source": "referral"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "new"

    def test_opportunity_default_stage_is_prospecting(self):
        resp = api_post("/opportunities", {"title": f"Default {UNIQUE}"})
        assert resp.status_code == 201
        assert resp.json()["stage"] == "prospecting"

    def test_activity_today_due_date_is_valid(self):
        """Due date of today is valid (not in the past)."""
        today = _utc_today().isoformat()
        resp = api_post("/activities", {
            "type": "call",
            "subject": f"Today Act {UNIQUE}",
            "due_date": today,
        })
        current_day = _utc_today().isoformat()
        if resp.status_code != 201 and current_day != today:
            resp = api_post("/activities", {
                "type": "call",
                "subject": f"Today Act Retry {UNIQUE}",
                "due_date": current_day,
            })
        assert resp.status_code == 201

    def test_comment_on_nonexistent_entity(self):
        """Creating a comment on a nonexistent entity should fail."""
        fake_id = str(uuid.uuid4())
        resp = api_post("/comments", {
            "entity_type": "lead",
            "entity_id": fake_id,
            "content": "Ghost comment",
        })
        assert resp.status_code == 422

    def test_search_case_insensitive(self):
        """Search should be case-insensitive."""
        unique_name = f"CaSeMiX-{UNIQUE}"
        api_post("/contacts", {"first_name": unique_name, "last_name": "Test"})
        resp = api_get("/contacts", params={"search": unique_name.lower()})
        assert resp.status_code == 200
        first_names = [c["first_name"] for c in resp.json()]
        assert unique_name in first_names
