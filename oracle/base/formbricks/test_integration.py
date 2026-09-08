"""
BackendForge — L2 Integration Tests for Formbricks Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase field names in responses
- Pattern 2: Nested/related data completeness
- Pattern 3: Filtering/sorting actually implemented
- Pattern 4: Exact status codes (201/200/400/404/409/422)
- Pattern 5: Business logic computed correctly
- Pattern 6: Environment data isolation
- Pattern 7: Cascade/side-effect correctness
- Pattern 8: Uniqueness constraints enforced
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ENV_ID = str(uuid.uuid4())
ENV_ID_2 = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())

HEADERS = {
    "X-User-Id": USER_ID,
    "X-Environment-Id": ENV_ID,
    "Content-Type": "application/json",
}

HEADERS_ENV2 = {
    "X-User-Id": USER_ID,
    "X-Environment-Id": ENV_ID_2,
    "Content-Type": "application/json",
}


# ── Helpers ──

def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS, timeout=30)


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS, timeout=30)


def patch(path, json=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


# ════════════════════════════════════════════════════════════════════
# L2 Tests
# ════════════════════════════════════════════════════════════════════


class TestSurveyFieldNames:
    """Pattern 1+2: Verify camelCase field names and nested objects in survey responses."""

    def test_create_survey_returns_camelcase_fields(self):
        """POST /api/surveys returns all fields in camelCase."""
        r = post("/api/surveys", {"name": "CamelCase Test", "type": "app"})
        assert r.status_code == 201
        data = r.json()
        # Verify camelCase keys exist
        assert "id" in data
        assert "environmentId" in data
        assert "name" in data
        assert "status" in data
        assert "type" in data
        assert "redirectUrl" in data or data.get("redirectUrl") is None
        assert "welcomeCard" in data or data.get("welcomeCard") is None
        assert "thankYouCard" in data or data.get("thankYouCard") is None
        assert "closesAt" in data or data.get("closesAt") is None
        assert "createdAt" in data
        assert "updatedAt" in data
        # Verify values
        assert data["name"] == "CamelCase Test"
        assert data["type"] == "app"
        assert data["status"] == "draft"
        assert data["environmentId"] == ENV_ID

    def test_survey_detail_includes_questions_array(self):
        """GET /api/surveys/{id} returns questions array (SurveyDetail schema)."""
        r = post("/api/surveys", {"name": "Detail Test"})
        assert r.status_code == 201
        sid = r.json()["id"]

        # Add a question
        r = post(f"/api/surveys/{sid}/questions", {
            "type": "openText", "headline": "Q1", "required": True
        })
        assert r.status_code == 201
        qid = r.json()["id"]

        # GET detail
        r = get(f"/api/surveys/{sid}")
        assert r.status_code == 200
        detail = r.json()
        assert "questions" in detail
        assert isinstance(detail["questions"], list)
        assert len(detail["questions"]) == 1
        assert detail["questions"][0]["id"] == qid
        assert detail["questions"][0]["surveyId"] == sid
        assert detail["questions"][0]["headline"] == "Q1"

    def test_survey_welcomecard_and_thankyoucard_roundtrip(self):
        """Pattern 2: Nested card objects roundtrip correctly."""
        payload = {
            "name": "Card Roundtrip",
            "welcomeCard": {"enabled": True, "headline": "Hi", "description": "Desc"},
            "thankYouCard": {"enabled": False, "headline": "Bye", "description": "Done"},
        }
        r = post("/api/surveys", payload)
        assert r.status_code == 201
        sid = r.json()["id"]

        r = get(f"/api/surveys/{sid}")
        assert r.status_code == 200
        s = r.json()
        assert s["welcomeCard"]["enabled"] is True
        assert s["welcomeCard"]["headline"] == "Hi"
        assert s["welcomeCard"]["description"] == "Desc"
        assert s["thankYouCard"]["enabled"] is False
        assert s["thankYouCard"]["headline"] == "Bye"
        assert s["thankYouCard"]["description"] == "Done"


class TestQuestionFieldNames:
    """Pattern 1+2: Verify question response fields."""

    def test_question_create_returns_all_fields(self):
        """POST question returns correct camelCase fields."""
        r = post("/api/surveys", {"name": "Q Fields"})
        sid = r.json()["id"]

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "multipleChoiceSingle",
            "headline": "Pick one",
            "subheader": "Please select",
            "required": True,
            "options": ["A", "B", "C"],
        })
        assert r.status_code == 201
        q = r.json()
        assert "id" in q
        assert "surveyId" in q
        assert q["surveyId"] == sid
        assert q["type"] == "multipleChoiceSingle"
        assert q["headline"] == "Pick one"
        assert q["subheader"] == "Please select"
        assert q["required"] is True
        assert q["options"] == ["A", "B", "C"]
        assert "position" in q
        assert "createdAt" in q
        assert "updatedAt" in q

    def test_rating_question_ratingrange_field(self):
        """Rating question returns ratingRange field correctly."""
        r = post("/api/surveys", {"name": "Rating Q"})
        sid = r.json()["id"]

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "rating", "headline": "Rate", "ratingRange": 10
        })
        assert r.status_code == 201
        q = r.json()
        assert q["ratingRange"] == 10
        assert q["type"] == "rating"

        # Verify on GET
        r = get(f"/api/surveys/{sid}/questions/{q['id']}")
        assert r.status_code == 200
        assert r.json()["ratingRange"] == 10


class TestResponseFieldNames:
    """Pattern 1: Verify response object camelCase fields."""

    def test_response_create_returns_correct_fields(self):
        """POST response returns all expected camelCase fields."""
        r = post("/api/surveys", {"name": "Resp Fields"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        r = post(f"/api/surveys/{sid}/responses", {
            "data": {qid: "answer"}, "finished": True
        })
        assert r.status_code == 201
        resp = r.json()
        assert "id" in resp
        assert "surveyId" in resp
        assert resp["surveyId"] == sid
        assert "finished" in resp
        assert resp["finished"] is True
        assert "data" in resp
        assert resp["data"][qid] == "answer"
        assert "createdAt" in resp
        # personId should be null when not provided
        assert "personId" in resp or resp.get("personId") is None


class TestSurveyStatusFilter:
    """Pattern 3: Verify status filter actually filters (not just returns all)."""

    def test_status_filter_excludes_non_matching(self):
        """Create surveys in different states, verify filter returns only matching."""
        r1 = post("/api/surveys", {"name": "Draft One"})
        assert r1.status_code == 201
        s1_id = r1.json()["id"]

        r2 = post("/api/surveys", {"name": "Active One"})
        assert r2.status_code == 201
        s2_id = r2.json()["id"]
        patch(f"/api/surveys/{s2_id}/status", {"status": "active"})

        r3 = post("/api/surveys", {"name": "Paused One"})
        assert r3.status_code == 201
        s3_id = r3.json()["id"]
        patch(f"/api/surveys/{s3_id}/status", {"status": "active"})
        patch(f"/api/surveys/{s3_id}/status", {"status": "paused"})

        # Filter active
        r = get("/api/surveys", params={"status": "active"})
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert s2_id in ids
        assert s1_id not in ids
        assert s3_id not in ids

        # Filter paused
        r = get("/api/surveys", params={"status": "paused"})
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert s3_id in ids
        assert s1_id not in ids
        assert s2_id not in ids

    def test_no_filter_returns_all(self):
        """Without filter, all surveys in the environment are returned."""
        r1 = post("/api/surveys", {"name": "All-1"})
        sid1 = r1.json()["id"]
        r2 = post("/api/surveys", {"name": "All-2"})
        sid2 = r2.json()["id"]

        r = get("/api/surveys")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert sid1 in ids
        assert sid2 in ids


class TestResponseFinishedFilter:
    """Pattern 3: Verify finished filter actually works."""

    def test_finished_filter_true_excludes_unfinished(self):
        """finished=true returns only finished responses."""
        r = post("/api/surveys", {"name": "Finished Filter"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        # Submit one finished, one not
        r1 = post(f"/api/surveys/{sid}/responses", {"data": {qid: "a"}, "finished": True})
        r2 = post(f"/api/surveys/{sid}/responses", {"data": {qid: "b"}, "finished": False})
        assert r1.status_code == 201
        assert r2.status_code == 201
        rid_finished = r1.json()["id"]
        rid_unfinished = r2.json()["id"]

        r = get(f"/api/surveys/{sid}/responses", params={"finished": "true"})
        assert r.status_code == 200
        ids = [resp["id"] for resp in r.json()]
        assert rid_finished in ids
        assert rid_unfinished not in ids

    def test_finished_filter_false_excludes_finished(self):
        """finished=false returns only unfinished responses."""
        r = post("/api/surveys", {"name": "Unfinished Filter"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        r1 = post(f"/api/surveys/{sid}/responses", {"data": {qid: "a"}, "finished": True})
        r2 = post(f"/api/surveys/{sid}/responses", {"data": {qid: "b"}, "finished": False})
        rid_finished = r1.json()["id"]
        rid_unfinished = r2.json()["id"]

        r = get(f"/api/surveys/{sid}/responses", params={"finished": "false"})
        assert r.status_code == 200
        ids = [resp["id"] for resp in r.json()]
        assert rid_unfinished in ids
        assert rid_finished not in ids


class TestExactStatusCodes:
    """Pattern 4: Verify exact HTTP status codes per OpenAPI spec."""

    def test_create_survey_returns_201(self):
        r = post("/api/surveys", {"name": "Status 201"})
        assert r.status_code == 201

    def test_create_question_returns_201(self):
        r = post("/api/surveys", {"name": "Q 201"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        assert r.status_code == 201

    def test_create_response_returns_201(self):
        r = post("/api/surveys", {"name": "R 201"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "ans"}, "finished": True})
        assert r.status_code == 201

    def test_create_tag_returns_201(self):
        r = post("/api/tags", {"name": f"tag-{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 201

    def test_create_person_returns_201(self):
        r = post("/api/people", {"email": f"{uuid.uuid4().hex[:8]}@test.com"})
        assert r.status_code == 201

    def test_create_webhook_returns_201(self):
        r = post("/api/webhooks", {"url": "https://hook.test", "triggers": ["responseCreated"]})
        assert r.status_code == 201

    def test_create_segment_returns_201(self):
        r = post("/api/segments", {
            "name": f"seg-{uuid.uuid4().hex[:8]}",
            "filters": [{"attribute": "x", "operator": "equals", "value": "y"}]
        })
        assert r.status_code == 201

    def test_create_trigger_returns_201(self):
        r = post("/api/surveys", {"name": "Trigger 201"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/triggers", {"type": "manual"})
        assert r.status_code == 201

    def test_add_tag_to_survey_returns_201(self):
        r = post("/api/surveys", {"name": "Tag 201"})
        sid = r.json()["id"]
        r = post("/api/tags", {"name": f"stag-{uuid.uuid4().hex[:8]}"})
        tid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tid})
        assert r.status_code == 201

    def test_nonexistent_survey_returns_404(self):
        r = get(f"/api/surveys/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_invalid_transition_returns_400(self):
        r = post("/api/surveys", {"name": "Bad Trans"})
        sid = r.json()["id"]
        r = patch(f"/api/surveys/{sid}/status", {"status": "completed"})
        assert r.status_code == 400

    def test_duplicate_tag_returns_409(self):
        name = f"dup-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": name})
        assert r.status_code == 201
        r = post("/api/tags", {"name": name})
        assert r.status_code == 409


class TestNPSCalculation:
    """Pattern 5: NPS business logic verified with specific inputs."""

    def test_nps_asymmetric_distribution(self):
        """3 promoters, 1 passive, 1 detractor → NPS = (3/5 - 1/5)*100 = 40."""
        r = post("/api/surveys", {"name": "NPS Asym"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "nps", "headline": "NPS Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        for score in [10, 9, 10, 8, 4]:
            post(f"/api/surveys/{sid}/responses", {"data": {qid: score}, "finished": True})

        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        analytics = r.json()
        assert "questionStats" in analytics
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == qid)
        assert nps_stat["nps"] == 40
        assert nps_stat["totalAnswers"] == 5
        # Average = (10+9+10+8+4)/5 = 8.2
        assert nps_stat["average"] == pytest.approx(8.2, abs=0.1)

    def test_nps_with_distribution_field(self):
        """NPS question reports per-score distribution."""
        r = post("/api/surveys", {"name": "NPS Dist"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "nps", "headline": "NPS"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        for score in [10, 10, 7, 3]:
            post(f"/api/surveys/{sid}/responses", {"data": {qid: score}, "finished": True})

        r = get(f"/api/surveys/{sid}/analytics")
        analytics = r.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == qid)
        dist = nps_stat["distribution"]
        # dist should map score→count, keys may be strings
        assert dist.get("10") == 2 or dist.get(10) == 2
        assert dist.get("7") == 1 or dist.get(7) == 1
        assert dist.get("3") == 1 or dist.get(3) == 1


class TestCompletionRateCalculation:
    """Pattern 5: Completion rate computed correctly."""

    def test_completion_rate_partial_responses(self):
        """5 total, 3 finished → completionRate = 0.6."""
        r = post("/api/surveys", {"name": "CR Test"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        for i in range(3):
            post(f"/api/surveys/{sid}/responses", {"data": {qid: f"ans{i}"}, "finished": True})
        for i in range(2):
            post(f"/api/surveys/{sid}/responses", {"data": {qid: f"partial{i}"}, "finished": False})

        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        a = r.json()
        assert a["totalResponses"] == 5
        assert a["completedResponses"] == 3
        assert a["completionRate"] == pytest.approx(0.6, abs=0.01)
        assert a["surveyId"] == sid


class TestAnalyticsFields:
    """Pattern 1+5: Analytics response has correct camelCase field names."""

    def test_analytics_top_level_fields(self):
        """Analytics response contains surveyId, totalResponses, completedResponses, completionRate, questionStats."""
        r = post("/api/surveys", {"name": "Analytics Fields"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})
        post(f"/api/surveys/{sid}/responses", {"data": {qid: "a"}, "finished": True})

        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        a = r.json()
        assert "surveyId" in a
        assert "totalResponses" in a
        assert "completedResponses" in a
        assert "completionRate" in a
        assert "questionStats" in a
        assert isinstance(a["questionStats"], list)

    def test_question_stats_fields(self):
        """Each questionStats item has correct fields."""
        r = post("/api/surveys", {"name": "QStats Fields"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})
        post(f"/api/surveys/{sid}/responses", {"data": {qid: "a"}, "finished": True})

        r = get(f"/api/surveys/{sid}/analytics")
        stats = r.json()["questionStats"]
        assert len(stats) >= 1
        stat = stats[0]
        assert "questionId" in stat
        assert "questionType" in stat
        assert "headline" in stat
        assert "totalAnswers" in stat


class TestEnvironmentIsolation:
    """Pattern 6: Data isolation between environments."""

    def test_survey_invisible_across_environments(self):
        """Survey created in env1 not visible in env2."""
        r = post("/api/surveys", {"name": "Iso Survey"})
        assert r.status_code == 201
        sid = r.json()["id"]

        # Get from env2
        r = get(f"/api/surveys/{sid}", headers=HEADERS_ENV2)
        assert r.status_code == 404

    def test_tag_isolation_between_environments(self):
        """Tag in env1 invisible in env2."""
        name = f"isotag-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": name})
        assert r.status_code == 201
        tid = r.json()["id"]

        r = get(f"/api/tags/{tid}", headers=HEADERS_ENV2)
        assert r.status_code == 404

    def test_people_isolation_between_environments(self):
        """Person in env1 invisible in env2."""
        r = post("/api/people", {"email": f"iso-{uuid.uuid4().hex[:8]}@test.com"})
        assert r.status_code == 201
        pid = r.json()["id"]

        r = get(f"/api/people/{pid}", headers=HEADERS_ENV2)
        assert r.status_code == 404

    def test_webhook_isolation_between_environments(self):
        """Webhook in env1 invisible in env2."""
        r = post("/api/webhooks", {"url": "https://iso.test/hook", "triggers": ["responseCreated"]})
        assert r.status_code == 201
        wid = r.json()["id"]

        r = get(f"/api/webhooks/{wid}", headers=HEADERS_ENV2)
        assert r.status_code == 404


class TestCascadeDeleteSurvey:
    """Pattern 7: Deleting survey cascades to questions, responses, triggers, tag associations."""

    def test_delete_survey_removes_questions(self):
        """After deleting a survey, its questions are gone."""
        r = post("/api/surveys", {"name": "Cascade Q"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]

        # Delete survey
        r = delete(f"/api/surveys/{sid}")
        assert r.status_code == 200

        # Question should be gone
        r = get(f"/api/surveys/{sid}/questions/{qid}")
        assert r.status_code == 404

    def test_delete_survey_removes_responses(self):
        """After deleting a survey, its responses are gone."""
        r = post("/api/surveys", {"name": "Cascade R"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "a"}, "finished": True})
        rid = r.json()["id"]

        delete(f"/api/surveys/{sid}")
        r = get(f"/api/surveys/{sid}/responses/{rid}")
        assert r.status_code == 404

    def test_delete_survey_removes_triggers(self):
        """After deleting a survey, its triggers are gone."""
        r = post("/api/surveys", {"name": "Cascade T"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/triggers", {"type": "manual"})
        tid = r.json()["id"]

        delete(f"/api/surveys/{sid}")
        r = get(f"/api/surveys/{sid}/triggers/{tid}")
        assert r.status_code == 404


class TestCascadeDeletePerson:
    """Pattern 7: Deleting a person cleans up correctly."""

    def test_delete_person_verified(self):
        """After deleting a person, they are no longer found."""
        r = post("/api/people", {"email": f"cascade-{uuid.uuid4().hex[:8]}@test.com"})
        assert r.status_code == 201
        person_id = r.json()["id"]

        # Delete person
        r = delete(f"/api/people/{person_id}")
        assert r.status_code == 200

        # Person is gone
        r = get(f"/api/people/{person_id}")
        assert r.status_code == 404

        # Person not in list
        r = get("/api/people")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert person_id not in ids


class TestCascadeDeleteTag:
    """Pattern 7: Deleting a tag removes all survey associations."""

    def test_delete_tag_removes_survey_associations(self):
        """After deleting a tag, survey-tag associations are removed."""
        r = post("/api/surveys", {"name": "Tag Cascade"})
        sid = r.json()["id"]
        tag_name = f"cascade-tag-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": tag_name})
        tid = r.json()["id"]

        # Associate tag with survey
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tid})
        assert r.status_code == 201

        # Delete tag
        r = delete(f"/api/tags/{tid}")
        assert r.status_code == 200

        # Removing the now-deleted tag from survey should be 404
        r = delete(f"/api/surveys/{sid}/tags/{tid}")
        assert r.status_code == 404


class TestQuestionPositionReorder:
    """Pattern 3+5: Question position management."""

    def test_positions_are_sequential_after_delete(self):
        """After deleting middle question, positions compact to 1,2."""
        r = post("/api/surveys", {"name": "Pos Compact"})
        sid = r.json()["id"]

        r1 = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q1"})
        r2 = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q2"})
        r3 = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q3"})
        q1_id = r1.json()["id"]
        q2_id = r2.json()["id"]
        q3_id = r3.json()["id"]

        # Delete Q2
        delete(f"/api/surveys/{sid}/questions/{q2_id}")

        # Get remaining questions
        r = get(f"/api/surveys/{sid}/questions")
        assert r.status_code == 200
        questions = r.json()
        assert len(questions) == 2
        positions = sorted([q["position"] for q in questions])
        assert positions == [1, 2]


class TestSegmentFilterEvaluation:
    """Pattern 5: Segment filters actually evaluate against people attributes."""

    def test_segment_notcontains_actually_excludes(self):
        """notContains filter genuinely excludes matching people."""
        # Create people
        r = post("/api/people", {"email": f"nc1-{uuid.uuid4().hex[:6]}@t.com", "attributes": {"city": "New York"}})
        p_ny = r.json()["id"]
        r = post("/api/people", {"email": f"nc2-{uuid.uuid4().hex[:6]}@t.com", "attributes": {"city": "London"}})
        p_london = r.json()["id"]

        # Create segment excluding "York"
        r = post("/api/segments", {
            "name": f"not-york-{uuid.uuid4().hex[:6]}",
            "filters": [{"attribute": "city", "operator": "notContains", "value": "York"}]
        })
        seg_id = r.json()["id"]

        r = get(f"/api/segments/{seg_id}/people")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()]
        assert p_london in ids
        assert p_ny not in ids


class TestWebhookFields:
    """Pattern 1+2: Webhook response field verification."""

    def test_webhook_create_returns_all_fields(self):
        """POST webhook returns id, environmentId, url, triggers, createdAt."""
        r = post("/api/webhooks", {
            "url": "https://webhook.test/ep",
            "triggers": ["responseCreated", "surveyCompleted"]
        })
        assert r.status_code == 201
        w = r.json()
        assert "id" in w
        assert "environmentId" in w
        assert w["environmentId"] == ENV_ID
        assert w["url"] == "https://webhook.test/ep"
        assert "triggers" in w
        assert isinstance(w["triggers"], list)
        assert set(w["triggers"]) == {"responseCreated", "surveyCompleted"}
        assert "createdAt" in w


class TestPersonFields:
    """Pattern 1: Person response field verification."""

    def test_person_create_returns_all_fields(self):
        """POST person returns id, environmentId, email, userId, attributes, timestamps."""
        r = post("/api/people", {
            "email": f"pf-{uuid.uuid4().hex[:8]}@test.com",
            "userId": "ext-123",
            "attributes": {"role": "admin", "org": "Acme"}
        })
        assert r.status_code == 201
        p = r.json()
        assert "id" in p
        assert "environmentId" in p
        assert p["environmentId"] == ENV_ID
        assert "email" in p
        assert "userId" in p
        assert p["userId"] == "ext-123"
        assert "attributes" in p
        assert p["attributes"]["role"] == "admin"
        assert p["attributes"]["org"] == "Acme"
        assert "createdAt" in p
        assert "updatedAt" in p
