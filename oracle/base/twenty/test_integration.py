"""
L2 Integration Tests for Twenty CRM API.

Targets LLM bug patterns:
- Pattern 1: camelCase field naming (firstName, lastName, companyId, totalRevenue, etc.)
- Pattern 2: Nested data (pipeline stages, tags on people)
- Pattern 3: Filtering/pagination actually works
- Pattern 4: Status codes (201/204/404/409)
- Pattern 5: Business logic (totalRevenue, Won/Lost auto-closedAt, probability)
- Pattern 6: Role-based access control
- Pattern 7: Side effects (cascade, revenue rollup updates)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10

OWNER_KEY = "owner_l2_test_key"
ADMIN_KEY = "admin_l2_test_key"
MEMBER_KEY = "member_l2_test_key"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = key
    headers.setdefault("Content-Type", "application/json")
    url = f"{BASE_URL}/{path.lstrip('/')}"
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, headers=headers, timeout=timeout, **kwargs)


@pytest.fixture
def pipeline_with_stages():
    """Create a pipeline with stages including Won and Lost."""
    unique = uuid.uuid4().hex[:6]
    r = api("post", "/pipelines", key=ADMIN_KEY, json={
        "name": f"Sales-{unique}",
        "stages": [
            {"name": "Lead", "position": 0, "color": "#aaa"},
            {"name": "Qualified", "position": 1, "color": "#bbb"},
            {"name": "Proposal", "position": 2, "color": "#ccc"},
            {"name": "Won", "position": 3, "color": "#0f0"},
            {"name": "Lost", "position": 4, "color": "#f00"},
        ]
    })
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def company():
    """Create a test company."""
    unique = uuid.uuid4().hex[:6]
    r = api("post", "/companies", json={
        "name": f"Acme-{unique}", "domain": f"acme-{unique}.com",
        "size": "51-200", "industry": "Technology", "annualRevenue": 5000000
    })
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def person(company):
    """Create a test person linked to company."""
    unique = uuid.uuid4().hex[:6]
    r = api("post", "/people", json={
        "firstName": f"Jane-{unique}", "lastName": f"Smith-{unique}",
        "email": f"jane-{unique}@test.com", "phone": "+1555000111",
        "companyId": company["id"], "city": "Austin", "jobTitle": "Engineer",
        "tags": ["vip", "customer"]
    })
    assert r.status_code == 201
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# L2 Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPersonFieldNaming:
    """Pattern 1: camelCase fields in Person responses."""

    def test_person_response_has_camelcase_fields(self, person):
        r = api("get", f"/people/{person['id']}")
        assert r.status_code == 200
        p = r.json()
        assert "firstName" in p
        assert "lastName" in p
        assert "companyId" in p
        assert "jobTitle" in p
        assert "createdAt" in p
        assert "updatedAt" in p
        # snake_case should NOT be present
        assert "first_name" not in p
        assert "last_name" not in p
        assert "company_id" not in p
        assert "job_title" not in p
        assert "created_at" not in p

    def test_company_response_has_camelcase_fields(self, company):
        r = api("get", f"/companies/{company['id']}")
        assert r.status_code == 200
        c = r.json()
        assert "annualRevenue" in c
        assert "totalRevenue" in c
        assert "createdAt" in c
        assert "updatedAt" in c
        assert "annual_revenue" not in c
        assert "total_revenue" not in c

    def test_opportunity_response_has_camelcase_fields(self, pipeline_with_stages, company):
        stages = pipeline_with_stages["stages"]
        r = api("post", "/opportunities", json={
            "name": f"Deal-{uuid.uuid4().hex[:4]}", "amount": 10000,
            "pipelineId": pipeline_with_stages["id"], "stageId": stages[0]["id"],
            "probability": 50, "closeDate": "2027-06-01", "companyId": company["id"]
        })
        assert r.status_code == 201
        opp = r.json()
        assert "pipelineId" in opp
        assert "stageId" in opp
        assert "closeDate" in opp
        assert "closedAt" in opp
        assert "companyId" in opp
        assert "createdAt" in opp
        assert "pipeline_id" not in opp
        assert "stage_id" not in opp
        assert "close_date" not in opp


class TestPaginationFormat:
    """Pattern 3: Paginated responses have correct format."""

    def test_people_list_pagination_format(self):
        # Create a few people
        for i in range(3):
            api("post", "/people", json={"firstName": f"PagF{i}", "lastName": f"PagL{i}"})
        r = api("get", "/people", params={"limit": 2, "offset": 0})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "totalCount" in body
        assert "limit" in body
        assert "offset" in body
        assert isinstance(body["data"], list)
        assert body["limit"] == 2
        assert body["offset"] == 0
        assert len(body["data"]) <= 2

    def test_pagination_offset_works(self):
        # Create people
        created_ids = []
        for i in range(4):
            r = api("post", "/people", json={"firstName": f"Off{uuid.uuid4().hex[:4]}", "lastName": f"Set{i}"})
            created_ids.append(r.json()["id"])

        r1 = api("get", "/people", params={"limit": 2, "offset": 0})
        r2 = api("get", "/people", params={"limit": 2, "offset": 2})
        page1_ids = [p["id"] for p in r1.json()["data"]]
        page2_ids = [p["id"] for p in r2.json()["data"]]
        # Pages should not overlap
        assert not set(page1_ids) & set(page2_ids)

    def test_companies_list_pagination_format(self):
        r = api("get", "/companies", params={"limit": 5, "offset": 0})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "totalCount" in body
        assert isinstance(body["totalCount"], int)


class TestStatusCodes:
    """Pattern 4: Correct HTTP status codes."""

    def test_create_person_returns_201(self):
        r = api("post", "/people", json={"firstName": "SC", "lastName": "Test"})
        assert r.status_code == 201

    def test_delete_person_returns_204(self):
        r = api("post", "/people", json={"firstName": "Del", "lastName": "Me"})
        pid = r.json()["id"]
        r2 = api("delete", f"/people/{pid}")
        assert r2.status_code == 204

    def test_get_nonexistent_person_returns_404(self):
        r = api("get", f"/people/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_create_pipeline_returns_201(self):
        r = api("post", "/pipelines", json={"name": f"SC-Pipe-{uuid.uuid4().hex[:4]}"})
        assert r.status_code == 201

    def test_delete_pipeline_returns_204(self):
        r = api("post", "/pipelines", json={"name": f"DelPipe-{uuid.uuid4().hex[:4]}"})
        pipe_id = r.json()["id"]
        r2 = api("delete", f"/pipelines/{pipe_id}")
        assert r2.status_code == 204

    def test_create_tag_returns_201(self):
        r = api("post", "/tags", json={"name": f"tag-{uuid.uuid4().hex[:6]}", "color": "#ff0000"})
        assert r.status_code == 201

    def test_duplicate_tag_name_returns_409(self):
        tag_name = f"dup-{uuid.uuid4().hex[:6]}"
        api("post", "/tags", json={"name": tag_name})
        r = api("post", "/tags", json={"name": tag_name})
        assert r.status_code == 409


class TestPipelineWithStages:
    """Pattern 2: Pipeline returns nested stages array."""

    def test_pipeline_includes_stages(self, pipeline_with_stages):
        r = api("get", f"/pipelines/{pipeline_with_stages['id']}")
        assert r.status_code == 200
        pipe = r.json()
        assert "stages" in pipe
        assert isinstance(pipe["stages"], list)
        assert len(pipe["stages"]) == 5
        # Verify stage structure
        for stage in pipe["stages"]:
            assert "id" in stage
            assert "name" in stage
            assert "position" in stage

    def test_stages_ordered_by_position(self, pipeline_with_stages):
        r = api("get", f"/pipelines/{pipeline_with_stages['id']}")
        stages = r.json()["stages"]
        positions = [s["position"] for s in stages]
        assert positions == sorted(positions)


class TestPersonTags:
    """Pattern 2: Tags on people are preserved."""

    def test_person_tags_preserved(self, person):
        r = api("get", f"/people/{person['id']}")
        assert r.status_code == 200
        assert isinstance(r.json()["tags"], list)
        assert "vip" in r.json()["tags"]
        assert "customer" in r.json()["tags"]

    def test_update_person_tags(self, person):
        r = api("patch", f"/people/{person['id']}", json={"tags": ["enterprise"]})
        assert r.status_code == 200
        assert "enterprise" in r.json()["tags"]
        # Revert
        api("patch", f"/people/{person['id']}", json={"tags": ["vip", "customer"]})


class TestCompanyRevenueRollup:
    """Pattern 5: totalRevenue computed from Won opportunities."""

    def test_total_revenue_computed(self, pipeline_with_stages, company):
        stages = pipeline_with_stages["stages"]
        won_stage = next(s for s in stages if s["name"] == "Won")

        # Create two Won opportunities for this company
        for amt in [25000, 50000]:
            api("post", "/opportunities", json={
                "name": f"Rev-{uuid.uuid4().hex[:4]}", "amount": amt,
                "pipelineId": pipeline_with_stages["id"], "stageId": won_stage["id"],
                "probability": 100, "closeDate": "2027-01-01", "companyId": company["id"]
            })

        # Get company - totalRevenue should be sum of won opps
        r = api("get", f"/companies/{company['id']}")
        assert r.status_code == 200
        assert r.json()["totalRevenue"] >= 75000

    def test_non_won_not_included_in_revenue(self, pipeline_with_stages):
        stages = pipeline_with_stages["stages"]
        lead_stage = next(s for s in stages if s["name"] == "Lead")

        # New company
        co = api("post", "/companies", json={"name": f"NRev-{uuid.uuid4().hex[:4]}"}).json()

        # Create non-Won opportunity
        api("post", "/opportunities", json={
            "name": f"NotWon-{uuid.uuid4().hex[:4]}", "amount": 100000,
            "pipelineId": pipeline_with_stages["id"], "stageId": lead_stage["id"],
            "probability": 20, "closeDate": "2027-06-01", "companyId": co["id"]
        })

        r = api("get", f"/companies/{co['id']}")
        assert r.json()["totalRevenue"] == 0


class TestOpportunityWonLostLogic:
    """Pattern 5: Won/Lost stage triggers closedAt and probability changes."""

    def test_moving_to_won_sets_closed_at(self, pipeline_with_stages):
        stages = pipeline_with_stages["stages"]
        lead_stage = next(s for s in stages if s["name"] == "Lead")
        won_stage = next(s for s in stages if s["name"] == "Won")

        opp = api("post", "/opportunities", json={
            "name": f"WinDeal-{uuid.uuid4().hex[:4]}", "amount": 30000,
            "pipelineId": pipeline_with_stages["id"], "stageId": lead_stage["id"],
            "probability": 30, "closeDate": "2027-03-01"
        }).json()
        assert opp["closedAt"] is None

        # Move to Won
        r = api("patch", f"/opportunities/{opp['id']}", json={"stageId": won_stage["id"]})
        assert r.status_code == 200
        assert r.json()["closedAt"] is not None

    def test_moving_to_lost_sets_probability_zero(self, pipeline_with_stages):
        stages = pipeline_with_stages["stages"]
        lead_stage = next(s for s in stages if s["name"] == "Lead")
        lost_stage = next(s for s in stages if s["name"] == "Lost")

        opp = api("post", "/opportunities", json={
            "name": f"LoseDeal-{uuid.uuid4().hex[:4]}", "amount": 20000,
            "pipelineId": pipeline_with_stages["id"], "stageId": lead_stage["id"],
            "probability": 50, "closeDate": "2027-04-01"
        }).json()

        # Move to Lost
        r = api("patch", f"/opportunities/{opp['id']}", json={"stageId": lost_stage["id"]})
        assert r.status_code == 200
        assert r.json()["probability"] == 0
        assert r.json()["closedAt"] is not None


class TestFilteringActivities:
    """Pattern 3: Activity filtering by personId, companyId, type."""

    def test_filter_activities_by_person(self, person):
        # Create activity for person
        api("post", "/activities", json={
            "type": "call", "title": f"Call-{uuid.uuid4().hex[:4]}",
            "personId": person["id"]
        })
        api("post", "/activities", json={
            "type": "email", "title": f"Email-{uuid.uuid4().hex[:4]}",
            "personId": person["id"]
        })

        r = api("get", "/activities", params={"personId": person["id"]})
        assert r.status_code == 200
        acts = r.json()["data"]
        assert len(acts) >= 2
        for a in acts:
            assert a["personId"] == person["id"]

    def test_filter_activities_by_type(self, person):
        api("post", "/activities", json={
            "type": "meeting", "title": f"Mtg-{uuid.uuid4().hex[:4]}",
            "personId": person["id"]
        })

        r = api("get", "/activities", params={"type": "meeting"})
        assert r.status_code == 200
        for a in r.json()["data"]:
            assert a["type"] == "meeting"


class TestPeopleFiltering:
    """Pattern 3: People filtering by companyId and tag."""

    def test_filter_people_by_company(self, person, company):
        r = api("get", "/people", params={"companyId": company["id"]})
        assert r.status_code == 200
        people = r.json()["data"]
        assert len(people) >= 1
        for p in people:
            assert p["companyId"] == company["id"]

    def test_filter_people_by_tag(self, person):
        r = api("get", "/people", params={"tag": "vip"})
        assert r.status_code == 200
        people = r.json()["data"]
        assert len(people) >= 1
        for p in people:
            assert "vip" in p["tags"]


class TestRolePermissions:
    """Pattern 6: Role-based access control."""

    def test_member_cannot_create_pipeline(self):
        r = api("post", "/pipelines", key=MEMBER_KEY, json={"name": "MemberPipe"})
        assert r.status_code == 403

    def test_admin_can_create_pipeline(self):
        r = api("post", "/pipelines", key=ADMIN_KEY, json={"name": f"AdminPipe-{uuid.uuid4().hex[:4]}"})
        assert r.status_code == 201

    def test_member_cannot_manage_members(self):
        r = api("get", "/members", key=MEMBER_KEY)
        assert r.status_code == 403

    def test_admin_cannot_manage_members(self):
        r = api("get", "/members", key=ADMIN_KEY)
        assert r.status_code == 403

    def test_owner_can_manage_members(self):
        r = api("get", "/members", key=OWNER_KEY)
        assert r.status_code == 200

    def test_member_cannot_create_views(self):
        r = api("post", "/views", key=MEMBER_KEY, json={
            "name": "MemberView", "objectType": "people", "filters": [], "sorts": []
        })
        assert r.status_code == 403


class TestCompanyPeopleRelation:
    """Pattern 2: Company people endpoint returns linked people."""

    def test_company_people_endpoint(self, company, person):
        r = api("get", f"/companies/{company['id']}/people")
        assert r.status_code == 200
        data = r.json()["data"]
        person_ids = [p["id"] for p in data]
        assert person["id"] in person_ids


class TestSearch:
    """Pattern 5: Unified search works across entities."""

    def test_search_returns_grouped_results(self, person, company):
        # Search by a unique part of person's name
        search_term = person["firstName"]
        r = api("get", "/search", params={"q": search_term})
        assert r.status_code == 200
        result = r.json()
        assert "people" in result
        assert "companies" in result
        assert "opportunities" in result
        assert isinstance(result["people"], list)

    def test_search_finds_company_by_name(self, company):
        r = api("get", "/search", params={"q": company["name"]})
        assert r.status_code == 200
        company_ids = [c["id"] for c in r.json()["companies"]]
        assert company["id"] in company_ids


class TestNotesLinking:
    """Pattern 2: Notes linked to entities."""

    def test_note_linked_to_person(self, person):
        note = api("post", "/notes", json={
            "title": f"Note-{uuid.uuid4().hex[:4]}",
            "body": "Important note content",
            "personId": person["id"]
        })
        assert note.status_code == 201
        assert note.json()["personId"] == person["id"]

        # Get person notes
        r = api("get", f"/people/{person['id']}/notes")
        assert r.status_code == 200
        note_ids = [n["id"] for n in r.json()["data"]]
        assert note.json()["id"] in note_ids
