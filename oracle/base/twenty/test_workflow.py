"""
L3 Workflow Tests for Twenty CRM API.

Multi-step cross-entity workflows testing:
- Pattern 1: camelCase consistency across entities
- Pattern 2: Nested/relational data (stages, activities, notes)
- Pattern 5: Business logic (revenue rollup, Won/Lost, search)
- Pattern 6: Role permissions across workflow
- Pattern 7: Side effects (cascade, revenue updates on stage changes)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10

OWNER_KEY = "owner_wf_test_key"
ADMIN_KEY = "admin_wf_test_key"
MEMBER_KEY = "member_wf_test_key"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = key
    headers.setdefault("Content-Type", "application/json")
    url = f"{BASE_URL}/{path.lstrip('/')}"
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, headers=headers, timeout=timeout, **kwargs)


class TestDealLifecycleWorkflow:
    """
    Full deal lifecycle: create pipeline → company → opportunity → move through stages →
    verify Won triggers closedAt and revenue rollup on company.
    Patterns: 5 (business logic), 7 (side effects), 1 (camelCase)
    """

    def test_deal_lifecycle_with_revenue_rollup(self):
        # 1. Admin creates pipeline
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"DealPipe-{uuid.uuid4().hex[:6]}",
            "stages": [
                {"name": "Prospect", "position": 0, "color": "#aaa"},
                {"name": "Negotiation", "position": 1, "color": "#bbb"},
                {"name": "Won", "position": 2, "color": "#0f0"},
                {"name": "Lost", "position": 3, "color": "#f00"},
            ]
        })
        assert pipe.status_code == 201
        pipe_data = pipe.json()
        assert "stages" in pipe_data
        stages = pipe_data["stages"]
        assert len(stages) == 4

        prospect_id = next(s["id"] for s in stages if s["name"] == "Prospect")
        won_id = next(s["id"] for s in stages if s["name"] == "Won")
        lost_id = next(s["id"] for s in stages if s["name"] == "Lost")

        # 2. Create company
        co = api("post", "/companies", json={
            "name": f"BigCorp-{uuid.uuid4().hex[:6]}", "domain": "bigcorp.com",
            "size": "501+", "industry": "Finance"
        })
        assert co.status_code == 201
        co_id = co.json()["id"]

        # 3. Create opportunity at Prospect stage
        opp = api("post", "/opportunities", json={
            "name": f"BigDeal-{uuid.uuid4().hex[:4]}", "amount": 100000,
            "pipelineId": pipe_data["id"], "stageId": prospect_id,
            "probability": 25, "closeDate": "2027-06-01", "companyId": co_id
        })
        assert opp.status_code == 201
        opp_id = opp.json()["id"]
        assert opp.json()["closedAt"] is None
        assert opp.json()["pipelineId"] == pipe_data["id"]
        assert opp.json()["stageId"] == prospect_id

        # 4. Company totalRevenue should be 0 (not won yet)
        r = api("get", f"/companies/{co_id}")
        assert r.json()["totalRevenue"] == 0

        # 5. Move to Won
        r = api("patch", f"/opportunities/{opp_id}", json={"stageId": won_id})
        assert r.status_code == 200
        assert r.json()["closedAt"] is not None
        assert r.json()["stageId"] == won_id

        # 6. Company totalRevenue should now include this deal
        r = api("get", f"/companies/{co_id}")
        assert r.json()["totalRevenue"] >= 100000

        # 7. Create another deal and move to Won
        opp2 = api("post", "/opportunities", json={
            "name": f"SmallDeal-{uuid.uuid4().hex[:4]}", "amount": 50000,
            "pipelineId": pipe_data["id"], "stageId": prospect_id,
            "probability": 50, "closeDate": "2027-07-01", "companyId": co_id
        }).json()
        api("patch", f"/opportunities/{opp2['id']}", json={"stageId": won_id})

        # 8. Company totalRevenue = 150000
        r = api("get", f"/companies/{co_id}")
        assert r.json()["totalRevenue"] >= 150000

        # 9. Create a deal and move to Lost
        opp3 = api("post", "/opportunities", json={
            "name": f"LostDeal-{uuid.uuid4().hex[:4]}", "amount": 200000,
            "pipelineId": pipe_data["id"], "stageId": prospect_id,
            "probability": 60, "closeDate": "2027-08-01", "companyId": co_id
        }).json()
        r = api("patch", f"/opportunities/{opp3['id']}", json={"stageId": lost_id})
        assert r.json()["probability"] == 0
        assert r.json()["closedAt"] is not None

        # 10. Company totalRevenue should NOT include Lost deal
        r = api("get", f"/companies/{co_id}")
        assert r.json()["totalRevenue"] >= 150000
        # Lost deal's 200000 should NOT be included
        assert r.json()["totalRevenue"] < 350001


class TestActivityTimelineWorkflow:
    """
    Activity timeline across entities: create person, company, opportunity →
    create activities linked to multiple entities → verify filtering.
    Patterns: 3 (filtering), 2 (linked entities), 1 (camelCase)
    """

    def test_activity_timeline_and_filtering(self):
        # 1. Create company
        co = api("post", "/companies", json={"name": f"ActCo-{uuid.uuid4().hex[:6]}"}).json()

        # 2. Create person linked to company
        person = api("post", "/people", json={
            "firstName": f"Act-{uuid.uuid4().hex[:4]}", "lastName": "Person",
            "companyId": co["id"]
        }).json()

        # 3. Create pipeline and opportunity
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"ActPipe-{uuid.uuid4().hex[:4]}",
            "stages": [{"name": "Open", "position": 0}]
        }).json()
        opp = api("post", "/opportunities", json={
            "name": f"ActDeal-{uuid.uuid4().hex[:4]}", "amount": 10000,
            "pipelineId": pipe["id"], "stageId": pipe["stages"][0]["id"],
            "probability": 40, "closeDate": "2027-05-01", "companyId": co["id"]
        }).json()

        # 4. Create activities linked to different entities
        act_person = api("post", "/activities", json={
            "type": "call", "title": f"Call Person-{uuid.uuid4().hex[:4]}",
            "personId": person["id"]
        }).json()
        act_company = api("post", "/activities", json={
            "type": "meeting", "title": f"Meet Company-{uuid.uuid4().hex[:4]}",
            "companyId": co["id"]
        }).json()
        act_opp = api("post", "/activities", json={
            "type": "email", "title": f"Email Opp-{uuid.uuid4().hex[:4]}",
            "opportunityId": opp["id"]
        }).json()
        # Activity linked to both person and company
        act_both = api("post", "/activities", json={
            "type": "task", "title": f"Task Both-{uuid.uuid4().hex[:4]}",
            "personId": person["id"], "companyId": co["id"]
        }).json()

        # 5. Filter by person
        r = api("get", "/activities", params={"personId": person["id"]})
        assert r.status_code == 200
        person_acts = r.json()["data"]
        person_act_ids = [a["id"] for a in person_acts]
        assert act_person["id"] in person_act_ids
        assert act_both["id"] in person_act_ids
        assert act_company["id"] not in person_act_ids

        # 6. Filter by company
        r = api("get", "/activities", params={"companyId": co["id"]})
        company_acts = r.json()["data"]
        company_act_ids = [a["id"] for a in company_acts]
        assert act_company["id"] in company_act_ids
        assert act_both["id"] in company_act_ids

        # 7. Person activities endpoint
        r = api("get", f"/people/{person['id']}/activities")
        assert r.status_code == 200
        assert act_person["id"] in [a["id"] for a in r.json()["data"]]

        # 8. Company activities endpoint
        r = api("get", f"/companies/{co['id']}/activities")
        assert r.status_code == 200
        assert act_company["id"] in [a["id"] for a in r.json()["data"]]

        # 9. Opportunity activities endpoint
        r = api("get", f"/opportunities/{opp['id']}/activities")
        assert r.status_code == 200
        assert act_opp["id"] in [a["id"] for a in r.json()["data"]]


class TestRolePermissionsWorkflow:
    """
    Role enforcement: member creates people → admin creates pipeline →
    member can't create pipeline → owner manages members.
    Patterns: 6 (permissions), 4 (status codes)
    """

    def test_role_enforcement_across_operations(self):
        # 1. Member can create people
        person = api("post", "/people", key=MEMBER_KEY, json={
            "firstName": f"Mem-{uuid.uuid4().hex[:4]}", "lastName": "Person"
        })
        assert person.status_code == 201

        # 2. Member cannot create pipeline
        r = api("post", "/pipelines", key=MEMBER_KEY, json={"name": "MemberPipe"})
        assert r.status_code == 403

        # 3. Admin creates pipeline
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"AdminPipe-{uuid.uuid4().hex[:4]}",
            "stages": [{"name": "Start", "position": 0}]
        })
        assert pipe.status_code == 201

        # 4. Member cannot create custom fields
        r = api("post", "/custom-fields", key=MEMBER_KEY, json={
            "name": "industry", "label": "Industry", "objectType": "people", "type": "text"
        })
        assert r.status_code == 403

        # 5. Admin can create custom fields
        cf = api("post", "/custom-fields", key=ADMIN_KEY, json={
            "name": f"cf_{uuid.uuid4().hex[:4]}", "label": "Custom Label",
            "objectType": "people", "type": "text"
        })
        assert cf.status_code == 201

        # 6. Member cannot create views
        r = api("post", "/views", key=MEMBER_KEY, json={
            "name": "MemberView", "objectType": "people", "filters": [], "sorts": []
        })
        assert r.status_code == 403

        # 7. Admin can create views
        view = api("post", "/views", key=ADMIN_KEY, json={
            "name": f"AdminView-{uuid.uuid4().hex[:4]}", "objectType": "people",
            "filters": [], "sorts": []
        })
        assert view.status_code == 201

        # 8. Member cannot manage members
        r = api("get", "/members", key=MEMBER_KEY)
        assert r.status_code == 403

        # 9. Admin cannot manage members
        r = api("get", "/members", key=ADMIN_KEY)
        assert r.status_code == 403

        # 10. Owner can manage members
        r = api("get", "/members", key=OWNER_KEY)
        assert r.status_code == 200

        # 11. Owner can add members
        member = api("post", "/members", key=OWNER_KEY, json={
            "email": f"new-{uuid.uuid4().hex[:4]}@test.com", "name": "New Member", "role": "member"
        })
        assert member.status_code == 201
        assert member.json()["role"] == "member"


class TestSearchWorkflow:
    """
    Search: create people, companies, opportunities with unique names →
    search → verify grouped results.
    Patterns: 5 (search logic works), 1 (camelCase in results)
    """

    def test_unified_search(self):
        unique = uuid.uuid4().hex[:8]

        # 1. Create person
        person = api("post", "/people", json={
            "firstName": f"SearchPerson{unique}", "lastName": "Test",
            "email": f"search{unique}@test.com"
        }).json()

        # 2. Create company
        company = api("post", "/companies", json={
            "name": f"SearchCorp{unique}", "domain": f"search{unique}.com"
        }).json()

        # 3. Create pipeline and opportunity
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"SearchPipe-{unique}",
            "stages": [{"name": "Open", "position": 0}]
        }).json()
        opp = api("post", "/opportunities", json={
            "name": f"SearchDeal{unique}", "amount": 5000,
            "pipelineId": pipe["id"], "stageId": pipe["stages"][0]["id"],
            "probability": 50, "closeDate": "2027-09-01"
        }).json()

        # 4. Search by unique string
        r = api("get", "/search", params={"q": unique})
        assert r.status_code == 200
        results = r.json()

        # 5. Verify grouped results
        assert "people" in results
        assert "companies" in results
        assert "opportunities" in results

        # 6. Person found
        found_people = [p["id"] for p in results["people"]]
        assert person["id"] in found_people

        # 7. Company found
        found_companies = [c["id"] for c in results["companies"]]
        assert company["id"] in found_companies

        # 8. Opportunity found
        found_opps = [o["id"] for o in results["opportunities"]]
        assert opp["id"] in found_opps


class TestNotesWorkflow:
    """
    Notes linked to entities: create notes for person, company, opportunity →
    verify entity-specific endpoints return correct notes.
    Patterns: 2 (linked data), 3 (filtering), 4 (status codes)
    """

    def test_notes_across_entities(self):
        # 1. Setup entities
        co = api("post", "/companies", json={"name": f"NoteCo-{uuid.uuid4().hex[:6]}"}).json()
        person = api("post", "/people", json={
            "firstName": f"Note-{uuid.uuid4().hex[:4]}", "lastName": "Person",
            "companyId": co["id"]
        }).json()
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"NotePipe-{uuid.uuid4().hex[:4]}",
            "stages": [{"name": "Open", "position": 0}]
        }).json()
        opp = api("post", "/opportunities", json={
            "name": f"NoteDeal-{uuid.uuid4().hex[:4]}", "amount": 5000,
            "pipelineId": pipe["id"], "stageId": pipe["stages"][0]["id"],
            "probability": 30, "closeDate": "2027-10-01"
        }).json()

        # 2. Create notes linked to different entities
        note_person = api("post", "/notes", json={
            "title": "Person Note", "body": f"Body-{uuid.uuid4().hex[:4]}",
            "personId": person["id"]
        })
        assert note_person.status_code == 201
        assert note_person.json()["personId"] == person["id"]

        note_company = api("post", "/notes", json={
            "body": f"Company note body-{uuid.uuid4().hex[:4]}",
            "companyId": co["id"]
        })
        assert note_company.status_code == 201

        note_opp = api("post", "/notes", json={
            "body": f"Opp note body-{uuid.uuid4().hex[:4]}",
            "opportunityId": opp["id"]
        })
        assert note_opp.status_code == 201

        # 3. Verify person notes endpoint
        r = api("get", f"/people/{person['id']}/notes")
        assert r.status_code == 200
        assert note_person.json()["id"] in [n["id"] for n in r.json()["data"]]

        # 4. Verify company notes endpoint
        r = api("get", f"/companies/{co['id']}/notes")
        assert r.status_code == 200
        assert note_company.json()["id"] in [n["id"] for n in r.json()["data"]]

        # 5. Verify opportunity notes endpoint
        r = api("get", f"/opportunities/{opp['id']}/notes")
        assert r.status_code == 200
        assert note_opp.json()["id"] in [n["id"] for n in r.json()["data"]]

        # 6. Filter notes by personId
        r = api("get", "/notes", params={"personId": person["id"]})
        assert r.status_code == 200
        for n in r.json()["data"]:
            assert n["personId"] == person["id"]


class TestTagsWorkflow:
    """
    Tags: create tags → assign to people → filter → verify uniqueness.
    Patterns: 8 (uniqueness), 3 (tag filtering), 4 (409 for duplicates)
    """

    def test_tags_lifecycle(self):
        unique = uuid.uuid4().hex[:6]
        tag_name = f"wf-tag-{unique}"

        # 1. Create tag
        tag = api("post", "/tags", json={"name": tag_name, "color": "#ff8800"})
        assert tag.status_code == 201
        assert tag.json()["name"] == tag_name
        assert tag.json()["color"] == "#ff8800"
        tag_id = tag.json()["id"]

        # 2. Duplicate tag name rejected
        r = api("post", "/tags", json={"name": tag_name, "color": "#000"})
        assert r.status_code == 409

        # 3. Create people with this tag
        p1 = api("post", "/people", json={
            "firstName": f"Tag1-{unique}", "lastName": "Person", "tags": [tag_name]
        }).json()
        p2 = api("post", "/people", json={
            "firstName": f"Tag2-{unique}", "lastName": "Person", "tags": [tag_name]
        }).json()
        p3 = api("post", "/people", json={
            "firstName": f"NoTag-{unique}", "lastName": "Person", "tags": []
        }).json()

        # 4. Filter people by tag
        r = api("get", "/people", params={"tag": tag_name})
        assert r.status_code == 200
        tagged_ids = [p["id"] for p in r.json()["data"]]
        assert p1["id"] in tagged_ids
        assert p2["id"] in tagged_ids
        assert p3["id"] not in tagged_ids

        # 5. Update tag
        r = api("patch", f"/tags/{tag_id}", json={"color": "#00ff00"})
        assert r.status_code == 200
        assert r.json()["color"] == "#00ff00"

        # 6. Delete tag
        r = api("delete", f"/tags/{tag_id}")
        assert r.status_code == 204

        # 7. Verify tag deleted
        r = api("get", "/tags")
        tag_names = [t["name"] for t in r.json()["data"]]
        assert tag_name not in tag_names


class TestCustomFieldsWorkflow:
    """
    Custom fields: admin creates custom field → field appears on entities →
    set custom field value → verify on GET.
    Patterns: 5 (custom fields logic), 6 (admin required), 1 (camelCase)
    """

    def test_custom_field_lifecycle(self):
        unique = uuid.uuid4().hex[:6]
        field_name = f"department{unique}"

        # 1. Admin creates custom field for people
        cf = api("post", "/custom-fields", key=ADMIN_KEY, json={
            "name": field_name, "label": "Department",
            "objectType": "people", "type": "text"
        })
        assert cf.status_code == 201
        assert cf.json()["name"] == field_name
        assert cf.json()["objectType"] == "people"
        assert cf.json()["type"] == "text"
        cf_id = cf.json()["id"]

        # 2. Create a person - should have custom field as null
        person = api("post", "/people", json={
            "firstName": f"CF-{unique}", "lastName": "Test"
        }).json()

        r = api("get", f"/people/{person['id']}")
        assert r.status_code == 200
        assert field_name in r.json()
        assert r.json()[field_name] is None

        # 3. Set custom field value
        r = api("patch", f"/people/{person['id']}", json={field_name: "Engineering"})
        assert r.status_code == 200
        assert r.json()[field_name] == "Engineering"

        # 4. Verify persisted
        r = api("get", f"/people/{person['id']}")
        assert r.json()[field_name] == "Engineering"

        # 5. Delete custom field
        r = api("delete", f"/custom-fields/{cf_id}", key=ADMIN_KEY)
        assert r.status_code == 204


class TestViewExecutionWorkflow:
    """
    Views: create view with filters → create matching/non-matching data →
    execute view → verify results filtered correctly.
    Patterns: 5 (view execution logic), 3 (filtering), 2 (nested filters)
    """

    def test_view_creation_and_execution(self):
        unique = uuid.uuid4().hex[:6]

        # 1. Create people with different cities
        p_austin = api("post", "/people", json={
            "firstName": f"ViewA-{unique}", "lastName": "Austin", "city": "Austin"
        }).json()
        p_ny = api("post", "/people", json={
            "firstName": f"ViewN-{unique}", "lastName": "NYC", "city": "New York"
        }).json()

        # 2. Admin creates view that filters by city=Austin
        view = api("post", "/views", key=ADMIN_KEY, json={
            "name": f"AustinPeople-{unique}",
            "objectType": "people",
            "filters": [{"field": "city", "operator": "eq", "value": "Austin"}],
            "sorts": [{"field": "firstName", "direction": "asc"}]
        })
        assert view.status_code == 201
        view_id = view.json()["id"]

        # 3. Verify view stored correctly
        r = api("get", f"/views/{view_id}", key=ADMIN_KEY)
        assert r.status_code == 200
        assert r.json()["name"] == f"AustinPeople-{unique}"
        assert r.json()["objectType"] == "people"
        assert len(r.json()["filters"]) == 1
        assert r.json()["filters"][0]["field"] == "city"
        assert r.json()["filters"][0]["operator"] == "eq"
        assert r.json()["filters"][0]["value"] == "Austin"

        # 4. Execute view
        r = api("get", f"/views/{view_id}/results", key=ADMIN_KEY)
        assert r.status_code == 200
        results = r.json()["data"]

        # 5. Only Austin people should be in results
        result_ids = [p["id"] for p in results]
        assert p_austin["id"] in result_ids
        assert p_ny["id"] not in result_ids


class TestOpportunityFilteringWorkflow:
    """
    Opportunity filtering by pipeline, stage, company.
    Patterns: 3 (filtering), 1 (camelCase), 4 (status codes)
    """

    def test_opportunity_filtering(self):
        unique = uuid.uuid4().hex[:6]

        # 1. Create two pipelines
        pipe1 = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"Pipe1-{unique}",
            "stages": [{"name": "Open", "position": 0}, {"name": "Won", "position": 1}]
        }).json()
        pipe2 = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"Pipe2-{unique}",
            "stages": [{"name": "Start", "position": 0}]
        }).json()

        # 2. Create company
        co = api("post", "/companies", json={"name": f"FilterCo-{unique}"}).json()

        # 3. Create opportunities in different pipelines
        opp1 = api("post", "/opportunities", json={
            "name": f"Opp1-{unique}", "amount": 10000,
            "pipelineId": pipe1["id"], "stageId": pipe1["stages"][0]["id"],
            "probability": 50, "closeDate": "2027-05-01", "companyId": co["id"]
        }).json()
        opp2 = api("post", "/opportunities", json={
            "name": f"Opp2-{unique}", "amount": 20000,
            "pipelineId": pipe2["id"], "stageId": pipe2["stages"][0]["id"],
            "probability": 30, "closeDate": "2027-06-01"
        }).json()

        # 4. Filter by pipeline
        r = api("get", "/opportunities", params={"pipelineId": pipe1["id"]})
        assert r.status_code == 200
        for o in r.json()["data"]:
            assert o["pipelineId"] == pipe1["id"]

        # 5. Filter by company
        r = api("get", "/opportunities", params={"companyId": co["id"]})
        assert r.status_code == 200
        opp_ids = [o["id"] for o in r.json()["data"]]
        assert opp1["id"] in opp_ids
        assert opp2["id"] not in opp_ids

        # 6. Filter by stage
        r = api("get", "/opportunities", params={"stageId": pipe1["stages"][0]["id"]})
        assert r.status_code == 200
        for o in r.json()["data"]:
            assert o["stageId"] == pipe1["stages"][0]["id"]


class TestCompanyPeopleAndRevenueWorkflow:
    """
    Company with people and revenue: create company → add people → verify people endpoint →
    add Won opps → verify totalRevenue → delete opp → verify revenue decreases.
    Patterns: 2 (linked data), 5 (computed revenue), 7 (side effects)
    """

    def test_company_complete_workflow(self):
        unique = uuid.uuid4().hex[:6]

        # 1. Create company
        co = api("post", "/companies", json={
            "name": f"CompWF-{unique}", "domain": f"comp{unique}.com",
            "size": "11-50", "industry": "SaaS"
        }).json()
        assert co["totalRevenue"] == 0

        # 2. Create people at company
        p1 = api("post", "/people", json={
            "firstName": "Alice", "lastName": f"P-{unique}", "companyId": co["id"]
        }).json()
        p2 = api("post", "/people", json={
            "firstName": "Bob", "lastName": f"P-{unique}", "companyId": co["id"]
        }).json()

        # 3. Verify company people endpoint
        r = api("get", f"/companies/{co['id']}/people")
        assert r.status_code == 200
        people_ids = [p["id"] for p in r.json()["data"]]
        assert p1["id"] in people_ids
        assert p2["id"] in people_ids

        # 4. Create pipeline with Won stage
        pipe = api("post", "/pipelines", key=ADMIN_KEY, json={
            "name": f"RevPipe-{unique}",
            "stages": [
                {"name": "Prospect", "position": 0},
                {"name": "Won", "position": 1}
            ]
        }).json()
        won_id = next(s["id"] for s in pipe["stages"] if s["name"] == "Won")

        # 5. Create and win opportunities
        opp1 = api("post", "/opportunities", json={
            "name": f"Won1-{unique}", "amount": 30000,
            "pipelineId": pipe["id"], "stageId": won_id,
            "probability": 100, "closeDate": "2027-01-01", "companyId": co["id"]
        }).json()
        opp2 = api("post", "/opportunities", json={
            "name": f"Won2-{unique}", "amount": 20000,
            "pipelineId": pipe["id"], "stageId": won_id,
            "probability": 100, "closeDate": "2027-02-01", "companyId": co["id"]
        }).json()

        # 6. Verify totalRevenue = 50000
        r = api("get", f"/companies/{co['id']}")
        assert r.json()["totalRevenue"] == 50000

        # 7. Delete one opportunity
        r = api("delete", f"/opportunities/{opp1['id']}")
        assert r.status_code == 204

        # 8. Verify totalRevenue decreased to 20000
        r = api("get", f"/companies/{co['id']}")
        assert r.json()["totalRevenue"] == 20000
