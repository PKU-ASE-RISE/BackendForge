"""
Test suite for Twenty CRM API.
Tests cover CRUD operations, business logic, role enforcement, and search.
"""

import os
import pytest
import requests
import time

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10

# Each complete API key identifies its own workspace.
# Linked-object workflows use one key throughout; role-denial tests keep
# distinct keys so authorization checks remain independent.
# API keys for different roles
OWNER_KEY = "owner_test_key_123"
ADMIN_KEY = "admin_test_key_456"
MEMBER_KEY = "member_test_key_789"


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def owner_headers():
    return {"X-API-Key": OWNER_KEY, "Content-Type": "application/json"}


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def member_headers():
    return {"X-API-Key": MEMBER_KEY, "Content-Type": "application/json"}


# ============================================================
# Authentication Tests
# ============================================================


class TestAuthentication:
    def test_missing_api_key_returns_401(self):
        resp = request("get", f"{BASE_URL}/people")
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        resp = request("get", f"{BASE_URL}/people", headers={"X-API-Key": ""})
        assert resp.status_code == 401

    def test_valid_api_key_returns_200(self):
        resp = request("get", f"{BASE_URL}/people", headers=member_headers())
        assert resp.status_code == 200


# ============================================================
# People CRUD Tests
# ============================================================


class TestPeopleCRUD:
    def test_create_person(self):
        data = {"firstName": "John", "lastName": "Doe", "email": "john@example.com", "phone": "+1234567890"}
        resp = request("post", f"{BASE_URL}/people", json=data, headers=member_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["firstName"] == "John"
        assert body["lastName"] == "Doe"
        assert body["email"] == "john@example.com"
        assert "id" in body
        assert "createdAt" in body

    def test_create_person_missing_required_fields(self):
        data = {"firstName": "John"}
        resp = request("post", f"{BASE_URL}/people", json=data, headers=member_headers())
        assert resp.status_code == 400

    def test_list_people(self):
        # Create a person first
        data = {"firstName": "List", "lastName": "Test"}
        request("post", f"{BASE_URL}/people", json=data, headers=member_headers())

        resp = request("get", f"{BASE_URL}/people", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "totalCount" in body
        assert isinstance(body["data"], list)
        assert body["totalCount"] >= 1

    def test_get_person(self):
        data = {"firstName": "Get", "lastName": "Test"}
        create_resp = request("post", f"{BASE_URL}/people", json=data, headers=member_headers())
        person_id = create_resp.json()["id"]

        resp = request("get", f"{BASE_URL}/people/{person_id}", headers=member_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == person_id
        assert resp.json()["firstName"] == "Get"

    def test_get_person_not_found(self):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = request("get", f"{BASE_URL}/people/{fake_id}", headers=member_headers())
        assert resp.status_code == 404

    def test_update_person(self):
        data = {"firstName": "Before", "lastName": "Update"}
        create_resp = request("post", f"{BASE_URL}/people", json=data, headers=member_headers())
        person_id = create_resp.json()["id"]

        update_data = {"firstName": "After", "email": "after@example.com"}
        resp = request("patch", f"{BASE_URL}/people/{person_id}", json=update_data, headers=member_headers())
        assert resp.status_code == 200
        assert resp.json()["firstName"] == "After"
        assert resp.json()["email"] == "after@example.com"
        assert resp.json()["lastName"] == "Update"  # unchanged

    def test_delete_person(self):
        data = {"firstName": "Delete", "lastName": "Me"}
        create_resp = request("post", f"{BASE_URL}/people", json=data, headers=member_headers())
        person_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/people/{person_id}", headers=member_headers())
        assert resp.status_code == 204

        # Verify deleted
        resp = request("get", f"{BASE_URL}/people/{person_id}", headers=member_headers())
        assert resp.status_code == 404

    def test_list_people_pagination(self):
        # Create multiple people
        for i in range(3):
            request(
                "post",
                f"{BASE_URL}/people",
                json={"firstName": f"Page{i}", "lastName": "Test"},
                headers=member_headers(),
            )

        resp = request("get", f"{BASE_URL}/people?limit=2&offset=0", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_list_people_filter_by_tag(self):
        # Create a person with tags
        data = {"firstName": "Tagged", "lastName": "Person", "tags": ["vip"]}
        request("post", f"{BASE_URL}/people", json=data, headers=member_headers())

        data2 = {"firstName": "Untagged", "lastName": "Person", "tags": []}
        request("post", f"{BASE_URL}/people", json=data2, headers=member_headers())

        resp = request("get", f"{BASE_URL}/people?tag=vip", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        for person in body["data"]:
            assert "vip" in person["tags"]


# ============================================================
# Companies CRUD Tests
# ============================================================


class TestCompaniesCRUD:
    def test_create_company(self):
        data = {"name": "Acme Corp", "domain": "acme.com", "industry": "Tech", "size": "51-200"}
        resp = request("post", f"{BASE_URL}/companies", json=data, headers=member_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Acme Corp"
        assert body["domain"] == "acme.com"
        assert "id" in body

    def test_create_company_missing_name(self):
        data = {"domain": "noname.com"}
        resp = request("post", f"{BASE_URL}/companies", json=data, headers=member_headers())
        assert resp.status_code == 400

    def test_get_company_includes_total_revenue(self):
        data = {"name": "Revenue Co"}
        create_resp = request("post", f"{BASE_URL}/companies", json=data, headers=member_headers())
        company_id = create_resp.json()["id"]

        resp = request("get", f"{BASE_URL}/companies/{company_id}", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert "totalRevenue" in body
        assert body["totalRevenue"] == 0  # No won deals yet

    def test_update_company(self):
        data = {"name": "Old Name"}
        create_resp = request("post", f"{BASE_URL}/companies", json=data, headers=member_headers())
        company_id = create_resp.json()["id"]

        resp = request(
            "patch",
            f"{BASE_URL}/companies/{company_id}", json={"name": "New Name"}, headers=member_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_company(self):
        data = {"name": "Delete Co"}
        create_resp = request("post", f"{BASE_URL}/companies", json=data, headers=member_headers())
        company_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/companies/{company_id}", headers=member_headers())
        assert resp.status_code == 204

    def test_get_company_people(self):
        # Create company
        company_resp = request(
            "post",
            f"{BASE_URL}/companies", json={"name": "People Co"}, headers=member_headers()
        )
        company_id = company_resp.json()["id"]

        # Create person linked to company
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Employee", "lastName": "One", "companyId": company_id},
            headers=member_headers(),
        )

        resp = request("get", f"{BASE_URL}/companies/{company_id}/people", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) >= 1
        assert body["data"][0]["companyId"] == company_id


# ============================================================
# Pipelines and Stages Tests
# ============================================================


class TestPipelines:
    def test_create_pipeline_as_admin(self):
        data = {
            "name": "Sales Pipeline",
            "stages": [
                {"name": "Lead", "position": 0},
                {"name": "Qualified", "position": 1},
                {"name": "Proposal", "position": 2},
                {"name": "Won", "position": 3},
                {"name": "Lost", "position": 4},
            ],
        }
        resp = request("post", f"{BASE_URL}/pipelines", json=data, headers=admin_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Sales Pipeline"
        assert len(body["stages"]) == 5
        # Verify ordering
        assert body["stages"][0]["name"] == "Lead"
        assert body["stages"][4]["name"] == "Lost"

    def test_create_pipeline_as_member_forbidden(self):
        data = {"name": "Member Pipeline"}
        resp = request("post", f"{BASE_URL}/pipelines", json=data, headers=member_headers())
        assert resp.status_code == 403

    def test_list_pipelines_as_member_forbidden(self):
        resp = request("get", f"{BASE_URL}/pipelines", headers=member_headers())
        assert resp.status_code == 403

    def test_add_stage_to_pipeline(self):
        # Create pipeline
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines", json={"name": "Stage Test Pipeline"}, headers=admin_headers()
        )
        pipeline_id = pipeline_resp.json()["id"]

        # Add stage
        stage_data = {"name": "New Stage", "position": 0, "color": "#FF0000"}
        resp = request(
            "post",
            f"{BASE_URL}/pipelines/{pipeline_id}/stages", json=stage_data, headers=admin_headers()
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Stage"
        assert resp.json()["color"] == "#FF0000"

    def test_update_stage(self):
        # Create pipeline with stage
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={"name": "Update Stage Pipeline", "stages": [{"name": "Old", "position": 0}]},
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stage_id = pipeline_resp.json()["stages"][0]["id"]

        # Update stage
        resp = request(
            "patch",
            f"{BASE_URL}/pipelines/{pipeline_id}/stages/{stage_id}",
            json={"name": "Renamed", "position": 1},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_delete_stage(self):
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={"name": "Delete Stage Pipeline", "stages": [{"name": "ToDelete", "position": 0}]},
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stage_id = pipeline_resp.json()["stages"][0]["id"]

        resp = request(
            "delete",
            f"{BASE_URL}/pipelines/{pipeline_id}/stages/{stage_id}", headers=admin_headers()
        )
        assert resp.status_code == 204

    def test_pipeline_stage_ordering(self):
        """Test that stages are returned in position order."""
        data = {
            "name": "Ordered Pipeline",
            "stages": [
                {"name": "Third", "position": 2},
                {"name": "First", "position": 0},
                {"name": "Second", "position": 1},
            ],
        }
        resp = request("post", f"{BASE_URL}/pipelines", json=data, headers=admin_headers())
        assert resp.status_code == 201
        stages = resp.json()["stages"]
        assert stages[0]["name"] == "First"
        assert stages[1]["name"] == "Second"
        assert stages[2]["name"] == "Third"


# ============================================================
# Opportunities Tests
# ============================================================


class TestOpportunities:
    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        """Create a pipeline with stages for opportunity tests."""
        data = {
            "name": "Opp Test Pipeline",
            "stages": [
                {"name": "Lead", "position": 0},
                {"name": "Qualified", "position": 1},
                {"name": "Won", "position": 2},
                {"name": "Lost", "position": 3},
            ],
        }
        resp = request("post", f"{BASE_URL}/pipelines", json=data, headers=admin_headers())
        assert resp.status_code == 201
        pipeline = resp.json()
        self.pipeline_id = pipeline["id"]
        self.stages = {s["name"]: s["id"] for s in pipeline["stages"]}

    def test_create_opportunity(self):
        data = {
            "name": "Big Deal",
            "amount": 50000,
            "pipelineId": self.pipeline_id,
            "stageId": self.stages["Lead"],
            "probability": 20,
            "closeDate": "2026-06-15",
        }
        resp = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Big Deal"
        assert body["amount"] == 50000
        assert body["stageId"] == self.stages["Lead"]
        assert body["closedAt"] is None

    def test_create_opportunity_missing_pipeline(self):
        data = {"name": "No Pipeline", "stageId": self.stages["Lead"]}
        resp = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        assert resp.status_code == 400

    def test_move_opportunity_to_won_sets_closed_at(self):
        """When opportunity moves to Won stage, closedAt is auto-set."""
        data = {
            "name": "Win Deal",
            "amount": 10000,
            "pipelineId": self.pipeline_id,
            "stageId": self.stages["Lead"],
            "probability": 50,
        }
        create_resp = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        opp_id = create_resp.json()["id"]

        # Move to Won
        resp = request(
            "patch",
            f"{BASE_URL}/opportunities/{opp_id}",
            json={"stageId": self.stages["Won"]},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["closedAt"] is not None
        assert body["stageId"] == self.stages["Won"]

    def test_move_opportunity_to_lost_sets_closed_at_and_zero_probability(self):
        """When opportunity moves to Lost, closedAt is set and probability becomes 0."""
        data = {
            "name": "Lost Deal",
            "amount": 5000,
            "pipelineId": self.pipeline_id,
            "stageId": self.stages["Lead"],
            "probability": 30,
        }
        create_resp = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        opp_id = create_resp.json()["id"]

        # Move to Lost
        resp = request(
            "patch",
            f"{BASE_URL}/opportunities/{opp_id}",
            json={"stageId": self.stages["Lost"]},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["closedAt"] is not None
        assert body["probability"] == 0

    def test_opportunity_lifecycle(self):
        """Test full opportunity lifecycle: Lead → Qualified → Won."""
        data = {
            "name": "Lifecycle Deal",
            "amount": 25000,
            "pipelineId": self.pipeline_id,
            "stageId": self.stages["Lead"],
            "probability": 10,
        }
        create_resp = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        opp_id = create_resp.json()["id"]

        # Move to Qualified
        resp = request(
            "patch",
            f"{BASE_URL}/opportunities/{opp_id}",
            json={"stageId": self.stages["Qualified"], "probability": 50},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["closedAt"] is None  # Not closed yet

        # Move to Won
        resp = request(
            "patch",
            f"{BASE_URL}/opportunities/{opp_id}",
            json={"stageId": self.stages["Won"]},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["closedAt"] is not None

    def test_list_opportunities_filter_by_pipeline(self):
        data = {
            "name": "Filter Test",
            "amount": 1000,
            "pipelineId": self.pipeline_id,
            "stageId": self.stages["Lead"],
        }
        created = request("post", f"{BASE_URL}/opportunities", json=data, headers=admin_headers())
        assert created.status_code == 201, created.text

        resp = request(
            "get",
            f"{BASE_URL}/opportunities?pipelineId={self.pipeline_id}", headers=admin_headers()
        )
        assert resp.status_code == 200
        assert any(opp["id"] == created.json()["id"] for opp in resp.json()["data"])
        for opp in resp.json()["data"]:
            assert opp["pipelineId"] == self.pipeline_id


# ============================================================
# Company Revenue Rollup Tests
# ============================================================


class TestCompanyRevenueRollup:
    def test_total_revenue_sums_won_deals(self):
        """Company totalRevenue = sum of Won opportunity amounts."""
        # Create company
        company_resp = request(
            "post",
            f"{BASE_URL}/companies", json={"name": "Rollup Co"}, headers=admin_headers()
        )
        company_id = company_resp.json()["id"]

        # Create pipeline with Won stage
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={
                "name": "Rollup Pipeline",
                "stages": [
                    {"name": "Open", "position": 0},
                    {"name": "Won", "position": 1},
                ],
            },
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stages = {s["name"]: s["id"] for s in pipeline_resp.json()["stages"]}

        # Create two opportunities linked to company
        opp1_resp = request(
            "post",
            f"{BASE_URL}/opportunities",
            json={
                "name": "Deal 1",
                "amount": 10000,
                "companyId": company_id,
                "pipelineId": pipeline_id,
                "stageId": stages["Open"],
            },
            headers=admin_headers(),
        )
        opp1_id = opp1_resp.json()["id"]

        opp2_resp = request(
            "post",
            f"{BASE_URL}/opportunities",
            json={
                "name": "Deal 2",
                "amount": 15000,
                "companyId": company_id,
                "pipelineId": pipeline_id,
                "stageId": stages["Open"],
            },
            headers=admin_headers(),
        )
        opp2_id = opp2_resp.json()["id"]

        # Move both to Won
        request(
            "patch",
            f"{BASE_URL}/opportunities/{opp1_id}",
            json={"stageId": stages["Won"]},
            headers=admin_headers(),
        )
        request(
            "patch",
            f"{BASE_URL}/opportunities/{opp2_id}",
            json={"stageId": stages["Won"]},
            headers=admin_headers(),
        )

        # Check company totalRevenue
        resp = request("get", f"{BASE_URL}/companies/{company_id}", headers=admin_headers())
        assert resp.status_code == 200
        assert resp.json()["totalRevenue"] == 25000

    def test_total_revenue_excludes_non_won_deals(self):
        """Only Won deals count toward totalRevenue."""
        company_resp = request(
            "post",
            f"{BASE_URL}/companies", json={"name": "Partial Co"}, headers=admin_headers()
        )
        company_id = company_resp.json()["id"]

        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={
                "name": "Partial Pipeline",
                "stages": [
                    {"name": "Open", "position": 0},
                    {"name": "Won", "position": 1},
                    {"name": "Lost", "position": 2},
                ],
            },
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stages = {s["name"]: s["id"] for s in pipeline_resp.json()["stages"]}

        # Create won deal
        opp1_resp = request(
            "post",
            f"{BASE_URL}/opportunities",
            json={
                "name": "Won Deal",
                "amount": 5000,
                "companyId": company_id,
                "pipelineId": pipeline_id,
                "stageId": stages["Open"],
            },
            headers=admin_headers(),
        )
        request(
            "patch",
            f"{BASE_URL}/opportunities/{opp1_resp.json()['id']}",
            json={"stageId": stages["Won"]},
            headers=admin_headers(),
        )

        # Create lost deal (should NOT count)
        opp2_resp = request(
            "post",
            f"{BASE_URL}/opportunities",
            json={
                "name": "Lost Deal",
                "amount": 8000,
                "companyId": company_id,
                "pipelineId": pipeline_id,
                "stageId": stages["Open"],
            },
            headers=admin_headers(),
        )
        request(
            "patch",
            f"{BASE_URL}/opportunities/{opp2_resp.json()['id']}",
            json={"stageId": stages["Lost"]},
            headers=admin_headers(),
        )

        # Create open deal (should NOT count)
        request(
            "post",
            f"{BASE_URL}/opportunities",
            json={
                "name": "Open Deal",
                "amount": 3000,
                "companyId": company_id,
                "pipelineId": pipeline_id,
                "stageId": stages["Open"],
            },
            headers=admin_headers(),
        )

        resp = request("get", f"{BASE_URL}/companies/{company_id}", headers=admin_headers())
        assert resp.json()["totalRevenue"] == 5000


# ============================================================
# Activities Tests
# ============================================================


class TestActivities:
    def test_create_activity(self):
        data = {"type": "call", "title": "Follow-up call", "body": "Discussed pricing"}
        resp = request("post", f"{BASE_URL}/activities", json=data, headers=member_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["type"] == "call"
        assert body["title"] == "Follow-up call"
        assert body["completed"] is False

    def test_create_activity_invalid_type(self):
        data = {"type": "invalid", "title": "Bad type"}
        resp = request("post", f"{BASE_URL}/activities", json=data, headers=member_headers())
        assert resp.status_code == 400

    def test_activity_linked_to_person_and_opportunity(self):
        """Activity can be linked to both a person and an opportunity."""
        # Create person
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Activity", "lastName": "Person"},
            headers=admin_headers(),
        )
        person_id = person_resp.json()["id"]

        # Create pipeline and opportunity
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={"name": "Activity Pipeline", "stages": [{"name": "Open", "position": 0}]},
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stage_id = pipeline_resp.json()["stages"][0]["id"]

        opp_resp = request(
            "post",
            f"{BASE_URL}/opportunities",
            json={"name": "Activity Deal", "pipelineId": pipeline_id, "stageId": stage_id, "amount": 1000},
            headers=admin_headers(),
        )
        opp_id = opp_resp.json()["id"]

        # Create activity linked to both
        activity_data = {
            "type": "meeting",
            "title": "Deal Meeting",
            "personId": person_id,
            "opportunityId": opp_id,
        }
        activity_resp = request("post", f"{BASE_URL}/activities", json=activity_data, headers=admin_headers())
        assert activity_resp.status_code == 201
        assert activity_resp.json()["personId"] == person_id
        assert activity_resp.json()["opportunityId"] == opp_id

        # Check it appears in person's activities
        resp = request("get", f"{BASE_URL}/people/{person_id}/activities", headers=admin_headers())
        assert resp.status_code == 200
        activity_ids = [a["id"] for a in resp.json()["data"]]
        assert activity_resp.json()["id"] in activity_ids

        # Check it appears in opportunity's activities
        resp = request("get", f"{BASE_URL}/opportunities/{opp_id}/activities", headers=admin_headers())
        assert resp.status_code == 200
        activity_ids = [a["id"] for a in resp.json()["data"]]
        assert activity_resp.json()["id"] in activity_ids

    def test_activity_timeline_chronological(self):
        """Activities returned in chronological order (newest first)."""
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Timeline", "lastName": "Person"},
            headers=member_headers(),
        )
        person_id = person_resp.json()["id"]

        # Create activities sequentially
        ids = []
        for i in range(3):
            resp = request(
                "post",
                f"{BASE_URL}/activities",
                json={"type": "task", "title": f"Task {i}", "personId": person_id},
                headers=member_headers(),
            )
            ids.append(resp.json()["id"])
            if i < 2:
                time.sleep(1.1)  # Keep createdAt values distinct at second resolution.

        resp = request("get", f"{BASE_URL}/people/{person_id}/activities", headers=member_headers())
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Should be newest first (descending)
        assert len(data) >= 3
        # Verify chronological descending - last created should be first
        returned_ids = [a["id"] for a in data]
        assert returned_ids.index(ids[2]) < returned_ids.index(ids[0])

    def test_update_activity(self):
        create_resp = request(
            "post",
            f"{BASE_URL}/activities",
            json={"type": "task", "title": "Incomplete"},
            headers=member_headers(),
        )
        activity_id = create_resp.json()["id"]

        resp = request(
            "patch",
            f"{BASE_URL}/activities/{activity_id}",
            json={"completed": True},
            headers=member_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["completed"] is True

    def test_delete_activity(self):
        create_resp = request(
            "post",
            f"{BASE_URL}/activities",
            json={"type": "email", "title": "Delete me"},
            headers=member_headers(),
        )
        activity_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/activities/{activity_id}", headers=member_headers())
        assert resp.status_code == 204

    def test_filter_activities_by_type(self):
        request(
            "post",
            f"{BASE_URL}/activities",
            json={"type": "call", "title": "A call"},
            headers=member_headers(),
        )
        request(
            "post",
            f"{BASE_URL}/activities",
            json={"type": "email", "title": "An email"},
            headers=member_headers(),
        )

        resp = request("get", f"{BASE_URL}/activities?type=call", headers=member_headers())
        assert resp.status_code == 200
        for activity in resp.json()["data"]:
            assert activity["type"] == "call"


# ============================================================
# Notes Tests
# ============================================================


class TestNotes:
    def test_create_note(self):
        data = {"title": "Meeting Notes", "body": "Discussed Q2 targets"}
        resp = request("post", f"{BASE_URL}/notes", json=data, headers=member_headers())
        assert resp.status_code == 201
        assert resp.json()["title"] == "Meeting Notes"
        assert resp.json()["body"] == "Discussed Q2 targets"

    def test_create_note_requires_body(self):
        data = {"title": "No body"}
        resp = request("post", f"{BASE_URL}/notes", json=data, headers=member_headers())
        assert resp.status_code == 400

    def test_note_linked_to_person(self):
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Note", "lastName": "Person"},
            headers=member_headers(),
        )
        person_id = person_resp.json()["id"]

        note_resp = request(
            "post",
            f"{BASE_URL}/notes",
            json={"body": "A note about this person", "personId": person_id},
            headers=member_headers(),
        )
        assert note_resp.status_code == 201

        resp = request("get", f"{BASE_URL}/people/{person_id}/notes", headers=member_headers())
        assert resp.status_code == 200
        note_ids = [n["id"] for n in resp.json()["data"]]
        assert note_resp.json()["id"] in note_ids

    def test_update_note(self):
        create_resp = request(
            "post",
            f"{BASE_URL}/notes", json={"body": "Original"}, headers=member_headers()
        )
        note_id = create_resp.json()["id"]

        resp = request(
            "patch",
            f"{BASE_URL}/notes/{note_id}", json={"body": "Updated"}, headers=member_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["body"] == "Updated"

    def test_delete_note(self):
        create_resp = request(
            "post",
            f"{BASE_URL}/notes", json={"body": "Delete me"}, headers=member_headers()
        )
        note_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/notes/{note_id}", headers=member_headers())
        assert resp.status_code == 204


# ============================================================
# Tags Tests
# ============================================================


class TestTags:
    def test_create_tag(self):
        data = {"name": f"important_{time.time()}", "color": "#FF5733"}
        resp = request("post", f"{BASE_URL}/tags", json=data, headers=member_headers())
        assert resp.status_code == 201
        assert resp.json()["color"] == "#FF5733"

    def test_create_duplicate_tag_returns_409(self):
        tag_name = f"duplicate_{time.time()}"
        request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())
        resp = request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())
        assert resp.status_code == 409

    def test_list_tags(self):
        tag_name = f"listable_{time.time()}"
        request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())

        resp = request("get", f"{BASE_URL}/tags", headers=member_headers())
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_update_tag(self):
        tag_name = f"update_me_{time.time()}"
        create_resp = request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())
        tag_id = create_resp.json()["id"]

        new_name = f"updated_{time.time()}"
        resp = request(
            "patch",
            f"{BASE_URL}/tags/{tag_id}", json={"name": new_name}, headers=member_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    def test_delete_tag(self):
        tag_name = f"delete_me_{time.time()}"
        create_resp = request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())
        tag_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/tags/{tag_id}", headers=member_headers())
        assert resp.status_code == 204

    def test_tag_people_and_filter(self):
        """Add a tag to a person, then list people with that tag."""
        tag_name = f"vip_filter_{time.time()}"
        request("post", f"{BASE_URL}/tags", json={"name": tag_name}, headers=member_headers())

        # Create person with tag
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "VIP", "lastName": "Customer", "tags": [tag_name]},
            headers=member_headers(),
        )
        person_id = person_resp.json()["id"]

        # Create person without tag
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Regular", "lastName": "Customer", "tags": []},
            headers=member_headers(),
        )

        # Filter by tag
        resp = request("get", f"{BASE_URL}/people?tag={tag_name}", headers=member_headers())
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert any(p["id"] == person_id for p in data)
        for p in data:
            assert tag_name in p["tags"]


# ============================================================
# Views Tests
# ============================================================


class TestViews:
    def test_create_view_as_admin(self):
        data = {
            "name": "High Value Deals",
            "objectType": "opportunities",
            "filters": [{"field": "amount", "operator": "gt", "value": 10000}],
            "sorts": [{"field": "amount", "direction": "desc"}],
        }
        resp = request("post", f"{BASE_URL}/views", json=data, headers=admin_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "High Value Deals"
        assert body["objectType"] == "opportunities"
        assert len(body["filters"]) == 1

    def test_create_view_as_member_forbidden(self):
        data = {"name": "Member View", "objectType": "people", "filters": [], "sorts": []}
        resp = request("post", f"{BASE_URL}/views", json=data, headers=member_headers())
        assert resp.status_code == 403

    def test_view_results_apply_filters(self):
        """Execute a view and verify filters are applied."""
        # Create pipeline for opportunities
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={"name": "View Test Pipeline", "stages": [{"name": "Open", "position": 0}]},
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stage_id = pipeline_resp.json()["stages"][0]["id"]

        # Create opportunities with different amounts
        request(
            "post",
            f"{BASE_URL}/opportunities",
            json={"name": "Small Deal", "amount": 5000, "pipelineId": pipeline_id, "stageId": stage_id},
            headers=member_headers(),
        )
        request(
            "post",
            f"{BASE_URL}/opportunities",
            json={"name": "Big Deal", "amount": 50000, "pipelineId": pipeline_id, "stageId": stage_id},
            headers=member_headers(),
        )

        # Create view filtering amount > 10000
        view_resp = request(
            "post",
            f"{BASE_URL}/views",
            json={
                "name": "Big Deals View",
                "objectType": "opportunities",
                "filters": [{"field": "amount", "operator": "gt", "value": 10000}],
                "sorts": [],
            },
            headers=admin_headers(),
        )
        view_id = view_resp.json()["id"]

        # Execute view
        resp = request("get", f"{BASE_URL}/views/{view_id}/results", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()["data"]
        for item in data:
            assert item["amount"] > 10000

    def test_view_results_apply_sorts(self):
        """Execute a view and verify sorts are applied."""
        # Create a view for people sorted by firstName desc
        view_resp = request(
            "post",
            f"{BASE_URL}/views",
            json={
                "name": "People Sorted",
                "objectType": "people",
                "filters": [],
                "sorts": [{"field": "firstName", "direction": "desc"}],
            },
            headers=admin_headers(),
        )
        view_id = view_resp.json()["id"]

        # Create people
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Alice", "lastName": "Z"},
            headers=member_headers(),
        )
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Zara", "lastName": "A"},
            headers=member_headers(),
        )

        # Execute view
        resp = request("get", f"{BASE_URL}/views/{view_id}/results", headers=admin_headers())
        assert resp.status_code == 200
        data = resp.json()["data"]
        if len(data) >= 2:
            # Verify descending order
            for i in range(len(data) - 1):
                assert data[i]["firstName"] >= data[i + 1]["firstName"]


# ============================================================
# Custom Fields Tests
# ============================================================


class TestCustomFields:
    def test_create_custom_field_as_admin(self):
        data = {
            "name": "linkedinUrl",
            "label": "LinkedIn URL",
            "objectType": "people",
            "type": "text",
        }
        resp = request("post", f"{BASE_URL}/custom-fields", json=data, headers=admin_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "linkedinUrl"
        assert body["type"] == "text"
        assert body["objectType"] == "people"

    def test_create_custom_field_as_member_forbidden(self):
        data = {
            "name": "forbidden",
            "label": "Forbidden Field",
            "objectType": "people",
            "type": "text",
        }
        resp = request("post", f"{BASE_URL}/custom-fields", json=data, headers=member_headers())
        assert resp.status_code == 403

    def test_custom_field_appears_in_responses(self):
        """After creating a custom field, it should appear in GET responses with null default."""
        field_name = f"customScore{int(time.time())}"
        # Create custom field for people
        request(
            "post",
            f"{BASE_URL}/custom-fields",
            json={
                "name": field_name,
                "label": "Custom Score",
                "objectType": "people",
                "type": "number",
            },
            headers=admin_headers(),
        )

        # Create a new person
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Custom", "lastName": "Field"},
            headers=admin_headers(),
        )
        assert person_resp.status_code == 201
        person_id = person_resp.json()["id"]
        detail = request("get", f"{BASE_URL}/people/{person_id}", headers=admin_headers())
        assert detail.status_code == 200, detail.text
        body = detail.json()
        # The contract guarantees null defaults on subsequent GET responses.
        assert field_name in body
        assert body[field_name] is None

    def test_set_custom_field_value(self):
        """Custom field values can be set via PATCH."""
        field_name = f"priority{int(time.time())}"
        request(
            "post",
            f"{BASE_URL}/custom-fields",
            json={
                "name": field_name,
                "label": "Priority",
                "objectType": "people",
                "type": "text",
            },
            headers=admin_headers(),
        )

        # Create person
        person_resp = request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Priority", "lastName": "Person"},
            headers=admin_headers(),
        )
        person_id = person_resp.json()["id"]

        # Set custom field value
        resp = request(
            "patch",
            f"{BASE_URL}/people/{person_id}",
            json={field_name: "high"},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()[field_name] == "high"

    def test_delete_custom_field(self):
        field_resp = request(
            "post",
            f"{BASE_URL}/custom-fields",
            json={
                "name": f"deletable{int(time.time())}",
                "label": "Deletable",
                "objectType": "companies",
                "type": "text",
            },
            headers=admin_headers(),
        )
        field_id = field_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/custom-fields/{field_id}", headers=admin_headers())
        assert resp.status_code == 204

    def test_list_custom_fields_filter_by_object_type(self):
        field_name = f"listField{int(time.time())}"
        request(
            "post",
            f"{BASE_URL}/custom-fields",
            json={
                "name": field_name,
                "label": "List Field",
                "objectType": "companies",
                "type": "text",
            },
            headers=admin_headers(),
        )

        resp = request("get", f"{BASE_URL}/custom-fields?objectType=companies", headers=admin_headers())
        assert resp.status_code == 200
        for field in resp.json()["data"]:
            assert field["objectType"] == "companies"


# ============================================================
# Role Enforcement Tests
# ============================================================


class TestRoleEnforcement:
    def test_member_cannot_create_pipeline(self):
        resp = request(
            "post",
            f"{BASE_URL}/pipelines", json={"name": "Forbidden"}, headers=member_headers()
        )
        assert resp.status_code == 403

    def test_member_cannot_manage_views(self):
        resp = request(
            "post",
            f"{BASE_URL}/views",
            json={"name": "Forbidden", "objectType": "people", "filters": [], "sorts": []},
            headers=member_headers(),
        )
        assert resp.status_code == 403

    def test_member_cannot_manage_custom_fields(self):
        resp = request(
            "post",
            f"{BASE_URL}/custom-fields",
            json={"name": "forbidden", "label": "F", "objectType": "people", "type": "text"},
            headers=member_headers(),
        )
        assert resp.status_code == 403

    def test_member_cannot_manage_members(self):
        resp = request("get", f"{BASE_URL}/members", headers=member_headers())
        assert resp.status_code == 403

    def test_admin_cannot_manage_members(self):
        resp = request("get", f"{BASE_URL}/members", headers=admin_headers())
        assert resp.status_code == 403

    def test_admin_can_create_pipeline(self):
        resp = request(
            "post",
            f"{BASE_URL}/pipelines", json={"name": "Admin Pipeline"}, headers=admin_headers()
        )
        assert resp.status_code == 201

    def test_owner_can_manage_members(self):
        resp = request("get", f"{BASE_URL}/members", headers=owner_headers())
        assert resp.status_code == 200

    def test_owner_can_create_pipeline(self):
        resp = request(
            "post",
            f"{BASE_URL}/pipelines", json={"name": "Owner Pipeline"}, headers=owner_headers()
        )
        assert resp.status_code == 201


# ============================================================
# Workspace Members Tests
# ============================================================


class TestWorkspaceMembers:
    def test_create_member(self):
        data = {"email": f"new_{time.time()}@example.com", "name": "New Member", "role": "member"}
        resp = request("post", f"{BASE_URL}/members", json=data, headers=owner_headers())
        assert resp.status_code == 201
        assert resp.json()["role"] == "member"

    def test_update_member_role(self):
        data = {"email": f"promote_{time.time()}@example.com", "name": "Promote Me", "role": "member"}
        create_resp = request("post", f"{BASE_URL}/members", json=data, headers=owner_headers())
        member_id = create_resp.json()["id"]

        resp = request(
            "patch",
            f"{BASE_URL}/members/{member_id}", json={"role": "admin"}, headers=owner_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_delete_member(self):
        data = {"email": f"remove_{time.time()}@example.com", "name": "Remove Me", "role": "member"}
        create_resp = request("post", f"{BASE_URL}/members", json=data, headers=owner_headers())
        member_id = create_resp.json()["id"]

        resp = request("delete", f"{BASE_URL}/members/{member_id}", headers=owner_headers())
        assert resp.status_code == 204


# ============================================================
# Search Tests
# ============================================================


class TestSearch:
    def test_search_people_by_name(self):
        # Create a person with unique name
        unique_name = f"Searchable{int(time.time())}"
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": unique_name, "lastName": "Person"},
            headers=member_headers(),
        )

        resp = request("get", f"{BASE_URL}/search?q={unique_name}", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert "people" in body
        assert any(p["firstName"] == unique_name for p in body["people"])

    def test_search_companies_by_name(self):
        unique_name = f"SearchCo{int(time.time())}"
        request(
            "post",
            f"{BASE_URL}/companies", json={"name": unique_name}, headers=member_headers()
        )

        resp = request("get", f"{BASE_URL}/search?q={unique_name}", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert "companies" in body
        assert any(c["name"] == unique_name for c in body["companies"])

    def test_search_companies_by_domain(self):
        unique_domain = f"search{int(time.time())}.com"
        request(
            "post",
            f"{BASE_URL}/companies",
            json={"name": "Domain Co", "domain": unique_domain},
            headers=member_headers(),
        )

        resp = request("get", f"{BASE_URL}/search?q={unique_domain}", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert any(c["domain"] == unique_domain for c in body["companies"])

    def test_search_opportunities_by_name(self):
        # Create pipeline first
        pipeline_resp = request(
            "post",
            f"{BASE_URL}/pipelines",
            json={"name": "Search Pipeline", "stages": [{"name": "Open", "position": 0}]},
            headers=admin_headers(),
        )
        pipeline_id = pipeline_resp.json()["id"]
        stage_id = pipeline_resp.json()["stages"][0]["id"]

        unique_name = f"SearchDeal{int(time.time())}"
        request(
            "post",
            f"{BASE_URL}/opportunities",
            json={"name": unique_name, "pipelineId": pipeline_id, "stageId": stage_id, "amount": 1000},
            headers=admin_headers(),
        )

        resp = request("get", f"{BASE_URL}/search?q={unique_name}", headers=admin_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert "opportunities" in body
        assert any(o["name"] == unique_name for o in body["opportunities"])

    def test_search_missing_query_returns_400(self):
        resp = request("get", f"{BASE_URL}/search", headers=member_headers())
        assert resp.status_code == 400

    def test_search_people_by_email(self):
        unique_email = f"searchuser{int(time.time())}@example.com"
        request(
            "post",
            f"{BASE_URL}/people",
            json={"firstName": "Email", "lastName": "Search", "email": unique_email},
            headers=member_headers(),
        )

        resp = request("get", f"{BASE_URL}/search?q={unique_email}", headers=member_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert any(p["email"] == unique_email for p in body["people"])
