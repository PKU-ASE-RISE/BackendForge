"""
BackendForge — L2 Integration Tests for DjangoCRM Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: snake_case field names (first_name, company_id, created_by, etc.)
- Pattern 2: Nested data (tags array on contacts/leads)
- Pattern 3: Search/filter actually implemented
- Pattern 4: Exact status codes (201/204/404/422)
- Pattern 5: Business logic (pipeline aggregation, lead conversion)
- Pattern 6: Org data isolation
- Pattern 7: Cascade/side-effect correctness
- Pattern 8: Uniqueness/dedup (tags)
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30

ORG_ID = str(uuid.uuid4())
ORG_ID_2 = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())

H1 = {"X-User-Id": USER_ID, "X-Org-Id": ORG_ID, "Content-Type": "application/json"}
H_OTHER = {"X-User-Id": str(uuid.uuid4()), "X-Org-Id": ORG_ID_2, "Content-Type": "application/json"}

FUTURE_DATE = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()


def _reset_test_context():
    """Use fresh tenant identities and dates for every independently runnable test."""
    global ORG_ID, ORG_ID_2, USER_ID
    global H1, H_OTHER, FUTURE_DATE

    ORG_ID = str(uuid.uuid4())
    ORG_ID_2 = str(uuid.uuid4())
    USER_ID = str(uuid.uuid4())
    H1 = {"X-User-Id": USER_ID, "X-Org-Id": ORG_ID, "Content-Type": "application/json"}
    H_OTHER = {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": ORG_ID_2,
        "Content-Type": "application/json",
    }
    FUTURE_DATE = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def post(path, json=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json,
        headers=H1 if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=H1 if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def put(path, json=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json,
        headers=H1 if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


def delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=H1 if headers is None else headers,
        timeout=REQUEST_TIMEOUT,
    )


class TestContactFields:
    """Pattern 1+2: Contact response has correct field names and tags."""

    def test_contact_create_returns_all_fields(self):
        r = post("/contacts", {
            "first_name": "John", "last_name": "Doe",
            "email": "john@test.com", "phone": "+1234",
            "tags": ["vip", "enterprise"], "notes": "Important client"
        })
        assert r.status_code == 201
        c = r.json()
        assert "id" in c
        assert c["first_name"] == "John"
        assert c["last_name"] == "Doe"
        assert c["email"] == "john@test.com"
        assert c["phone"] == "+1234"
        assert "tags" in c
        assert isinstance(c["tags"], list)
        assert "vip" in c["tags"]
        assert "enterprise" in c["tags"]
        assert c["notes"] == "Important client"
        assert "created_by" in c
        assert c["created_by"] == USER_ID
        assert "org_id" in c
        assert c["org_id"] == ORG_ID
        assert "created_at" in c
        assert "updated_at" in c

    def test_contact_tags_auto_created(self):
        """Tags in contact payload auto-create tag entries."""
        tag_name = f"auto-{uuid.uuid4().hex[:6]}"
        post("/contacts", {"first_name": "A", "last_name": "B", "tags": [tag_name]})
        r = get("/tags")
        tag_names = [t["name"] for t in r.json()]
        assert tag_name in tag_names


class TestLeadFields:
    """Pattern 1: Lead response has correct snake_case fields."""

    def test_lead_create_returns_all_fields(self):
        contact = post("/contacts", {"first_name": "Lead", "last_name": "Contact"}).json()
        r = post("/leads", {
            "contact_id": contact["id"],
            "source": "web",
            "value": 5000,
            "assigned_to": USER_ID,
            "tags": ["hot"]
        })
        assert r.status_code == 201
        lead = r.json()
        assert "id" in lead
        assert lead["contact_id"] == contact["id"]
        assert lead["status"] == "new"
        assert lead["source"] == "web"
        assert lead["value"] == 5000
        assert lead["assigned_to"] == USER_ID
        assert "tags" in lead
        assert "hot" in lead["tags"]
        assert "created_by" in lead
        assert "org_id" in lead
        assert "created_at" in lead
        assert "updated_at" in lead


class TestOpportunityFields:
    """Pattern 1: Opportunity fields."""

    def test_opportunity_create_returns_all_fields(self):
        contact = post("/contacts", {"first_name": "Opp", "last_name": "Contact"}).json()
        r = post("/opportunities", {
            "title": "Big Deal",
            "contact_id": contact["id"],
            "value": 10000,
            "probability": 50,
            "stage": "prospecting",
            "assigned_to": USER_ID,
            "close_date": "2025-12-31"
        })
        assert r.status_code == 201
        opp = r.json()
        assert opp["title"] == "Big Deal"
        assert opp["value"] == 10000
        assert opp["probability"] == 50
        assert opp["stage"] == "prospecting"
        assert opp["assigned_to"] == USER_ID
        assert opp["close_date"] == "2025-12-31"
        assert "id" in opp
        assert "created_by" in opp
        assert "org_id" in opp


class TestExactStatusCodes:
    """Pattern 4: Verify exact status codes."""

    def test_create_contact_201(self):
        r = post("/contacts", {"first_name": "S", "last_name": "C"})
        assert r.status_code == 201

    def test_create_company_201(self):
        r = post("/companies", {"name": "TestCo", "domain": "test.co"})
        assert r.status_code == 201

    def test_create_lead_201(self):
        c = post("/contacts", {"first_name": "L", "last_name": "C"}).json()
        r = post("/leads", {"contact_id": c["id"], "source": "web"})
        assert r.status_code == 201

    def test_create_opportunity_201(self):
        c = post("/contacts", {"first_name": "O", "last_name": "C"}).json()
        r = post("/opportunities", {"title": "Deal", "contact_id": c["id"], "stage": "prospecting"})
        assert r.status_code == 201

    def test_create_activity_201(self):
        c = post("/contacts", {"first_name": "Act", "last_name": "C"}).json()
        r = post("/activities", {
            "type": "call", "subject": "Follow up",
            "contact_id": c["id"], "due_date": FUTURE_DATE
        })
        assert r.status_code == 201

    def test_create_tag_201(self):
        r = post("/tags", {"name": f"tag-{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 201

    def test_delete_contact_204(self):
        c = post("/contacts", {"first_name": "Del", "last_name": "C"}).json()
        r = delete(f"/contacts/{c['id']}")
        assert r.status_code == 204

    def test_delete_company_204(self):
        co = post("/companies", {"name": "DelCo"}).json()
        r = delete(f"/companies/{co['id']}")
        assert r.status_code == 204

    def test_nonexistent_contact_404(self):
        r = get(f"/contacts/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_nonexistent_lead_404(self):
        r = get(f"/leads/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_invalid_lead_transition_422(self):
        c = post("/contacts", {"first_name": "T", "last_name": "C"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()
        # new → qualified is invalid (skip)
        r = put(f"/leads/{lead['id']}", {"status": "qualified"})
        assert r.status_code == 422


class TestSearchFilters:
    """Pattern 3: Search and filter params actually work."""

    def test_contact_search_by_name(self):
        post("/contacts", {"first_name": "Xander", "last_name": "Smith"})
        post("/contacts", {"first_name": "Alice", "last_name": "Xero"})
        post("/contacts", {"first_name": "Bob", "last_name": "Jones"})

        r = get("/contacts", params={"search": "xan"})
        assert r.status_code == 200
        names = [c["first_name"] for c in r.json()]
        assert "Xander" in names
        assert "Bob" not in names

    def test_lead_status_filter(self):
        c = post("/contacts", {"first_name": "F", "last_name": "L"}).json()
        l1 = post("/leads", {"contact_id": c["id"], "source": "web"}).json()
        l2 = post("/leads", {"contact_id": c["id"], "source": "email"}).json()
        put(f"/leads/{l2['id']}", {"status": "contacted"})

        r = get("/leads", params={"status": "new"})
        ids = [l["id"] for l in r.json()]
        assert l1["id"] in ids
        assert l2["id"] not in ids

    def test_activity_type_filter(self):
        c = post("/contacts", {"first_name": "AF", "last_name": "C"}).json()
        post("/activities", {"type": "call", "subject": "Call1", "contact_id": c["id"], "due_date": FUTURE_DATE})
        post("/activities", {"type": "email", "subject": "Email1", "contact_id": c["id"], "due_date": FUTURE_DATE})

        r = get("/activities", params={"type": "call"})
        types = [a["type"] for a in r.json()]
        assert all(t == "call" for t in types)

    def test_contact_tag_filter(self):
        post("/contacts", {"first_name": "Tagged", "last_name": "One", "tags": ["premium"]})
        post("/contacts", {"first_name": "Not", "last_name": "Tagged"})

        r = get("/contacts", params={"tag": "premium"})
        assert r.status_code == 200
        names = [c["first_name"] for c in r.json()]
        assert "Tagged" in names
        assert "Not" not in names


class TestPipelineAggregation:
    """Pattern 5: Pipeline returns correct aggregation."""

    def test_pipeline_has_all_stages(self):
        r = get("/pipeline")
        assert r.status_code == 200
        pipeline = r.json()
        for stage in ["prospecting", "proposal", "negotiation", "closed_won", "closed_lost"]:
            assert stage in pipeline
            assert "count" in pipeline[stage]
            assert "total_value" in pipeline[stage]
            assert "weighted_value" in pipeline[stage]

    def test_pipeline_calculation(self):
        """Create opportunity and verify pipeline values."""
        c = post("/contacts", {"first_name": "Pipe", "last_name": "C"}).json()
        post("/opportunities", {
            "title": "PipeDeal", "contact_id": c["id"],
            "stage": "prospecting", "value": 1000, "probability": 20
        })

        r = get("/pipeline")
        pipe = r.json()
        assert pipe["prospecting"]["count"] >= 1
        assert pipe["prospecting"]["total_value"] >= 1000
        # weighted_value = 1000 * 20 / 100 = 200
        assert pipe["prospecting"]["weighted_value"] >= 200


class TestOrgIsolation:
    """Pattern 6: Data isolated between organizations."""

    def test_contacts_isolated(self):
        c = post("/contacts", {"first_name": "Isolated", "last_name": "C"}).json()
        r = get(f"/contacts/{c['id']}", headers=H_OTHER)
        assert r.status_code == 404

    def test_leads_isolated(self):
        c = post("/contacts", {"first_name": "LI", "last_name": "C"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()
        r = get(f"/leads/{lead['id']}", headers=H_OTHER)
        assert r.status_code == 404

    def test_companies_isolated(self):
        co = post("/companies", {"name": "IsoCo"}).json()
        r = get(f"/companies/{co['id']}", headers=H_OTHER)
        assert r.status_code == 404


class TestCascadeDeleteContact:
    """Pattern 7: Deleting contact cascades activities."""

    def test_delete_contact_deletes_activities(self):
        c = post("/contacts", {"first_name": "CasDel", "last_name": "C"}).json()
        act = post("/activities", {
            "type": "task", "subject": "Cascade act",
            "contact_id": c["id"], "due_date": FUTURE_DATE
        }).json()

        delete(f"/contacts/{c['id']}")
        r = get(f"/activities/{act['id']}")
        assert r.status_code == 404


class TestCascadeDeleteCompany:
    """Pattern 7: Deleting company nullifies contact.company_id."""

    def test_delete_company_nullifies_contacts(self):
        co = post("/companies", {"name": "NullCo"}).json()
        c = post("/contacts", {"first_name": "Comp", "last_name": "C", "company_id": co["id"]}).json()
        assert c["company_id"] == co["id"]

        delete(f"/companies/{co['id']}")
        r = get(f"/contacts/{c['id']}")
        assert r.status_code == 200
        assert r.json()["company_id"] is None


class TestTagDedup:
    """Pattern 8: Tag creation is idempotent."""

    def test_tag_dedup_returns_same_id(self):
        name = f"dedup-{uuid.uuid4().hex[:6]}"
        r1 = post("/tags", {"name": name})
        assert r1.status_code == 201
        r2 = post("/tags", {"name": name})
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]


class TestAssignedToValidation:
    """Pattern 4+8: assigned_to must be a valid org member."""

    def test_invalid_assigned_to_returns_422(self):
        c = post("/contacts", {"first_name": "Inv", "last_name": "C"}).json()
        fake_user = str(uuid.uuid4())
        r = post("/leads", {"contact_id": c["id"], "source": "web", "assigned_to": fake_user})
        assert r.status_code == 422

    def test_null_assigned_to_valid(self):
        c = post("/contacts", {"first_name": "Null", "last_name": "A"}).json()
        r = post("/leads", {"contact_id": c["id"], "source": "web", "assigned_to": None})
        assert r.status_code == 201
