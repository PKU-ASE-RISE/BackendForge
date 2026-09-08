"""
BackendForge — L3 Workflow Tests for DjangoCRM Task

Multi-step cross-entity workflows testing:
- Pattern 2+5+7: Business logic (lead conversion, pipeline) + cascades
- Pattern 3+6: Filters + isolation
- Pattern 1+4: Field names + status codes
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


class TestLeadConversionWorkflow:
    """Pattern 5: Full lead lifecycle to conversion."""

    def test_lead_conversion_creates_opportunity(self):
        """
        1. Create contact
        2. Create lead (status=new)
        3. Transition new → contacted
        4. Transition contacted → qualified
        5. Convert lead → creates opportunity
        6. Verify opportunity fields
        7. Verify lead status is 'converted'
        8. Verify opportunity in pipeline
        """
        # 1. Contact
        c = post("/contacts", {"first_name": "Jane", "last_name": "Smith"}).json()

        # 2. Lead
        lead = post("/leads", {
            "contact_id": c["id"], "source": "referral",
            "value": 5000, "assigned_to": USER_ID
        }).json()
        assert lead["status"] == "new"

        # 3. new → contacted
        r = put(f"/leads/{lead['id']}", {"status": "contacted"})
        assert r.status_code == 200
        assert r.json()["status"] == "contacted"

        # 4. contacted → qualified
        r = put(f"/leads/{lead['id']}", {"status": "qualified"})
        assert r.status_code == 200
        assert r.json()["status"] == "qualified"

        # 5. Convert
        r = post(f"/leads/{lead['id']}/convert")
        assert r.status_code == 201
        opp = r.json()

        # 6. Verify opportunity
        assert opp["title"] == "Opportunity from Jane Smith"
        assert opp["contact_id"] == c["id"]
        assert opp["lead_id"] == lead["id"]
        assert opp["stage"] == "prospecting"
        assert opp["value"] == 5000
        assert opp["probability"] == 10
        assert opp["assigned_to"] == USER_ID

        # 7. Lead status
        r = get(f"/leads/{lead['id']}")
        assert r.json()["status"] == "converted"

        # 8. Pipeline
        r = get("/pipeline")
        assert r.json()["prospecting"]["count"] >= 1


class TestLeadStatusTransitions:
    """Pattern 4+5: Status transition enforcement."""

    def test_invalid_transitions_rejected(self):
        """
        1. Create lead (new)
        2. Try new → qualified (skip) → 422
        3. Try new → converted → 422
        4. Valid: new → contacted → 200
        5. Try contacted → new (backwards) → 422
        6. Valid: contacted → lost → 200
        """
        c = post("/contacts", {"first_name": "Trans", "last_name": "Test"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()
        lid = lead["id"]

        # 2. Skip forward
        r = put(f"/leads/{lid}", {"status": "qualified"})
        assert r.status_code == 422

        # 3. Direct to converted
        r = put(f"/leads/{lid}", {"status": "converted"})
        assert r.status_code == 422

        # 4. Valid
        r = put(f"/leads/{lid}", {"status": "contacted"})
        assert r.status_code == 200

        # 5. Backwards
        r = put(f"/leads/{lid}", {"status": "new"})
        assert r.status_code == 422

        # 6. To lost
        r = put(f"/leads/{lid}", {"status": "lost"})
        assert r.status_code == 200


class TestOpportunityStageTransitions:
    """Pattern 4+5: Stage transition enforcement."""

    def test_stage_transitions(self):
        """
        1. Create opportunity (prospecting)
        2. Try skip to negotiation → 422
        3. Valid: prospecting → proposal → 200
        4. Valid: proposal → negotiation → 200
        5. Valid: negotiation → closed_won → 200
        6. Try transition from closed_won → 422
        7. Another opportunity: any → closed_lost works
        """
        c = post("/contacts", {"first_name": "Stage", "last_name": "T"}).json()
        opp = post("/opportunities", {
            "title": "Stage Test", "contact_id": c["id"],
            "stage": "prospecting", "value": 1000, "probability": 10
        }).json()
        oid = opp["id"]

        # 2. Skip
        r = put(f"/opportunities/{oid}", {"stage": "negotiation"})
        assert r.status_code == 422

        # 3. Valid forward
        r = put(f"/opportunities/{oid}", {"stage": "proposal"})
        assert r.status_code == 200

        # 4.
        r = put(f"/opportunities/{oid}", {"stage": "negotiation"})
        assert r.status_code == 200

        # 5.
        r = put(f"/opportunities/{oid}", {"stage": "closed_won"})
        assert r.status_code == 200

        # 6. Terminal
        r = put(f"/opportunities/{oid}", {"stage": "prospecting"})
        assert r.status_code == 422

        # 7. Any to closed_lost
        opp2 = post("/opportunities", {
            "title": "Lost Test", "contact_id": c["id"],
            "stage": "prospecting", "value": 500, "probability": 20
        }).json()
        r = put(f"/opportunities/{opp2['id']}", {"stage": "closed_lost"})
        assert r.status_code == 200


class TestPipelineAggregation:
    """Pattern 5: Pipeline weighted value calculation."""

    def test_pipeline_weighted_values(self):
        """
        1. Create 3 opportunities in different stages with known values
        2. Verify pipeline counts, total_value, weighted_value
        """
        c = post("/contacts", {"first_name": "Pipe", "last_name": "Test"}).json()

        # Prospecting: value=1000, prob=20 → weighted=200
        post("/opportunities", {
            "title": "P1", "contact_id": c["id"],
            "stage": "prospecting", "value": 1000, "probability": 20
        })
        # Proposal: value=2000, prob=50 → weighted=1000
        opp2 = post("/opportunities", {
            "title": "P2", "contact_id": c["id"],
            "stage": "prospecting", "value": 2000, "probability": 50
        }).json()
        put(f"/opportunities/{opp2['id']}", {"stage": "proposal"})

        r = get("/pipeline")
        assert r.status_code == 200
        pipe = r.json()

        assert pipe["prospecting"]["count"] >= 1
        assert pipe["proposal"]["count"] >= 1
        # Verify weighted calculation for proposal
        # At least one entry with 2000*50/100=1000
        assert pipe["proposal"]["weighted_value"] >= 1000


class TestCascadeDeleteWorkflow:
    """Pattern 7: Full cascade verification."""

    def test_delete_lead_cascades_activities_and_comments(self):
        """
        1. Create contact + lead
        2. Create activity on lead
        3. Create comment on lead
        4. Delete lead
        5. Verify activity gone
        6. Verify comment gone
        7. Contact still exists
        """
        c = post("/contacts", {"first_name": "Cas", "last_name": "Lead"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()

        act = post("/activities", {
            "type": "task", "subject": "Lead task",
            "lead_id": lead["id"], "due_date": FUTURE_DATE
        }).json()

        comment = post("/comments", {
            "entity_type": "lead", "entity_id": lead["id"], "content": "Note"
        }).json()

        # Delete lead
        r = delete(f"/leads/{lead['id']}")
        assert r.status_code == 204

        # Activity gone
        r = get(f"/activities/{act['id']}")
        assert r.status_code == 404

        # Comment gone
        r = get("/comments", params={"entity_type": "lead", "entity_id": lead["id"]})
        assert r.status_code == 200
        assert len(r.json()) == 0

        # Contact still exists
        r = get(f"/contacts/{c['id']}")
        assert r.status_code == 200

    def test_delete_contact_nullifies_lead_contact_id(self):
        """
        1. Create contact
        2. Create lead with contact
        3. Delete contact
        4. Lead still exists with contact_id=null
        """
        c = post("/contacts", {"first_name": "NullLead", "last_name": "C"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()
        assert lead["contact_id"] == c["id"]

        delete(f"/contacts/{c['id']}")
        r = get(f"/leads/{lead['id']}")
        assert r.status_code == 200
        assert r.json()["contact_id"] is None


class TestTagWorkflow:
    """Pattern 2+7+8: Tag lifecycle with contacts/leads."""

    def test_tag_lifecycle(self):
        """
        1. Create contact with tags ["vip", "hot"]
        2. Verify tags auto-created
        3. Create another contact with ["vip"] → no new tag created
        4. Filter contacts by tag "vip" → both returned
        5. Delete tag "hot"
        6. First contact should no longer have "hot" tag
        7. "vip" tag still exists
        """
        tag1 = f"vip-{uuid.uuid4().hex[:4]}"
        tag2 = f"hot-{uuid.uuid4().hex[:4]}"

        c1 = post("/contacts", {"first_name": "Tag1", "last_name": "C", "tags": [tag1, tag2]}).json()
        assert tag1 in c1["tags"]
        assert tag2 in c1["tags"]

        # 2. Verify in tag list
        r = get("/tags")
        tag_names = [t["name"] for t in r.json()]
        assert tag1 in tag_names
        assert tag2 in tag_names

        # 3. Another contact with same tag
        c2 = post("/contacts", {"first_name": "Tag2", "last_name": "C", "tags": [tag1]}).json()

        # 4. Filter
        r = get("/contacts", params={"tag": tag1})
        ids = [c["id"] for c in r.json()]
        assert c1["id"] in ids
        assert c2["id"] in ids

        # 5. Delete tag2
        tag2_obj = next(t for t in get("/tags").json() if t["name"] == tag2)
        r = delete(f"/tags/{tag2_obj['id']}")
        assert r.status_code == 204

        # 6. First contact no longer has tag2
        r = get(f"/contacts/{c1['id']}")
        assert tag2 not in r.json()["tags"]
        assert tag1 in r.json()["tags"]

        # 7. vip tag still exists
        r = get("/tags")
        tag_names = [t["name"] for t in r.json()]
        assert tag1 in tag_names


class TestOrgIsolationWorkflow:
    """Pattern 6: Full org isolation."""

    def test_full_org_isolation(self):
        """
        1. Create contact, company, lead in org1
        2. Verify all accessible in org1
        3. Verify none accessible from org2
        """
        co = post("/companies", {"name": "OrgIsoCo"}).json()
        c = post("/contacts", {"first_name": "OrgIso", "last_name": "C", "company_id": co["id"]}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "referral"}).json()

        # Accessible in org1
        assert get(f"/contacts/{c['id']}").status_code == 200
        assert get(f"/companies/{co['id']}").status_code == 200
        assert get(f"/leads/{lead['id']}").status_code == 200

        # Not in org2
        assert get(f"/contacts/{c['id']}", headers=H_OTHER).status_code == 404
        assert get(f"/companies/{co['id']}", headers=H_OTHER).status_code == 404
        assert get(f"/leads/{lead['id']}", headers=H_OTHER).status_code == 404


class TestLeadConvertNotQualified:
    """Pattern 4: Convert requires qualified status."""

    def test_convert_non_qualified_lead_fails(self):
        """
        1. Create lead (new)
        2. Try convert → 422
        3. Move to contacted, try convert → 422
        4. Move to qualified, convert → 201
        """
        c = post("/contacts", {"first_name": "Conv", "last_name": "Fail"}).json()
        lead = post("/leads", {"contact_id": c["id"], "source": "web"}).json()

        # new → convert fails
        r = post(f"/leads/{lead['id']}/convert")
        assert r.status_code == 422

        # contacted → convert fails
        put(f"/leads/{lead['id']}", {"status": "contacted"})
        r = post(f"/leads/{lead['id']}/convert")
        assert r.status_code == 422

        # qualified → convert succeeds
        put(f"/leads/{lead['id']}", {"status": "qualified"})
        r = post(f"/leads/{lead['id']}/convert")
        assert r.status_code == 201
        assert r.json()["stage"] == "prospecting"


class TestActivityCompletedFilter:
    """Pattern 3: Activity completed filter works."""

    def test_completed_filter(self):
        """
        1. Create 2 activities
        2. Complete one
        3. Filter completed=true → only completed
        4. Filter completed=false → only incomplete
        """
        c = post("/contacts", {"first_name": "CompF", "last_name": "C"}).json()
        a1 = post("/activities", {
            "type": "task", "subject": "Done", "contact_id": c["id"], "due_date": FUTURE_DATE
        }).json()
        a2 = post("/activities", {
            "type": "call", "subject": "Pending", "contact_id": c["id"], "due_date": FUTURE_DATE
        }).json()

        # Complete a1
        put(f"/activities/{a1['id']}", {"completed": True})

        # Filter completed
        r = get("/activities", params={"completed": "true"})
        ids = [a["id"] for a in r.json()]
        assert a1["id"] in ids
        assert a2["id"] not in ids

        # Filter not completed
        r = get("/activities", params={"completed": "false"})
        ids = [a["id"] for a in r.json()]
        assert a2["id"] in ids
        assert a1["id"] not in ids
