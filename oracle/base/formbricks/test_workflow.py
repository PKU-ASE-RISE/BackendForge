"""
BackendForge — L3 Workflow Tests for Formbricks Task

Multi-step, cross-entity workflows that target:
- Pattern 2+5+7: Nested data + business logic + cascades
- Pattern 3+6: Filtering + isolation
- Pattern 1+4+8: Field names + status codes + uniqueness
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
PAST_TIMESTAMP = "2000-01-01T00:00:00+00:00"
FUTURE_TIMESTAMP = "2037-01-01T00:00:00+00:00"
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


class TestSurveyLifecycleWithResponses:
    """Pattern 2+4+5+7: Full survey lifecycle with responses and analytics."""

    def test_full_survey_lifecycle_and_analytics(self):
        """
        1. Create survey with cards
        2. Add NPS + MC questions
        3. Activate survey
        4. Submit varied responses
        5. Verify analytics: NPS, completion rate, MC distribution
        6. Complete survey
        7. Verify responses rejected after completion
        8. Verify analytics still accessible
        """
        # 1. Create survey
        r = post("/api/surveys", {
            "name": "Full Lifecycle",
            "welcomeCard": {"enabled": True, "headline": "Welcome", "description": "Hi"},
            "thankYouCard": {"enabled": True, "headline": "Thanks", "description": "Done"},
        })
        assert r.status_code == 201
        survey = r.json()
        sid = survey["id"]
        assert survey["status"] == "draft"
        assert survey["welcomeCard"]["headline"] == "Welcome"

        # 2. Add questions
        r = post(f"/api/surveys/{sid}/questions", {
            "type": "nps", "headline": "Recommend us?", "required": True
        })
        assert r.status_code == 201
        nps_qid = r.json()["id"]
        assert r.json()["position"] == 1

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "multipleChoiceSingle", "headline": "How found?",
            "options": ["Google", "Friend", "Ad"], "required": False
        })
        assert r.status_code == 201
        mc_qid = r.json()["id"]
        assert r.json()["position"] == 2

        # 3. Activate
        r = patch(f"/api/surveys/{sid}/status", {"status": "active"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        # 4. Submit responses
        responses_data = [
            ({nps_qid: 10, mc_qid: "Google"}, True),
            ({nps_qid: 9, mc_qid: "Friend"}, True),
            ({nps_qid: 7, mc_qid: "Google"}, True),
            ({nps_qid: 3, mc_qid: "Ad"}, True),
            ({nps_qid: 5}, False),  # partial, no MC answer
        ]
        for data, finished in responses_data:
            r = post(f"/api/surveys/{sid}/responses", {"data": data, "finished": finished})
            assert r.status_code == 201

        # 5. Verify analytics
        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        a = r.json()
        assert a["surveyId"] == sid
        assert a["totalResponses"] == 5
        assert a["completedResponses"] == 4
        assert a["completionRate"] == pytest.approx(0.8, abs=0.01)

        nps_stat = next(s for s in a["questionStats"] if s["questionId"] == nps_qid)
        # 2 promoters (10,9), 1 passive (7), 2 detractors (3,5) → NPS = (2/5 - 2/5)*100 = 0
        assert nps_stat["nps"] == 0
        assert nps_stat["totalAnswers"] == 5
        # Average = (10+9+7+3+5)/5 = 6.8
        assert nps_stat["average"] == pytest.approx(6.8, abs=0.1)

        mc_stat = next(s for s in a["questionStats"] if s["questionId"] == mc_qid)
        assert mc_stat["totalAnswers"] == 4
        dist = mc_stat["distribution"]
        assert dist["Google"] == 2
        assert dist["Friend"] == 1
        assert dist["Ad"] == 1

        # 6. Complete
        r = patch(f"/api/surveys/{sid}/status", {"status": "completed"})
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        # 7. Responses rejected
        r = post(f"/api/surveys/{sid}/responses", {"data": {nps_qid: 10}, "finished": True})
        assert r.status_code == 400

        # 8. Analytics still accessible
        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        assert r.json()["totalResponses"] == 5


class TestPersonResponseLinkingWorkflow:
    """Pattern 2+6: Person linking and isolation."""

    def test_person_linked_responses_workflow(self):
        """
        1. Create person in env1
        2. Create survey + question, activate
        3. Submit response linked to person
        4. Verify person link in response
        5. Verify person NOT visible in env2
        6. Submit response with non-existent person → 422
        7. Delete person
        8. Verify person is gone, survey still exists
        """
        # 1. Create person
        r = post("/api/people", {
            "email": f"linked-{uuid.uuid4().hex[:6]}@example.com",
            "userId": "ext-linked",
            "attributes": {"plan": "enterprise"}
        })
        assert r.status_code == 201
        person = r.json()
        pid = person["id"]
        assert person["environmentId"] == ENV_ID

        # 2. Create survey + question, activate
        r = post("/api/surveys", {"name": "Person Link WF"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Feedback"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        # 3. Submit linked response
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {qid: "Great product"}, "finished": True, "personId": pid
        })
        assert r.status_code == 201
        resp = r.json()
        rid = resp["id"]

        # 4. Verify link
        assert resp["personId"] == pid
        assert resp["surveyId"] == sid

        # 5. Person invisible in env2
        r = get(f"/api/people/{pid}", headers=HEADERS_ENV2)
        assert r.status_code == 404

        # 6. Non-existent person link fails
        fake_pid = str(uuid.uuid4())
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {qid: "another"}, "finished": True, "personId": fake_pid
        })
        assert r.status_code == 422

        # 7. Delete person
        r = delete(f"/api/people/{pid}")
        assert r.status_code == 200

        # 8. Person gone, survey intact
        r = get(f"/api/people/{pid}")
        assert r.status_code == 404
        r = get(f"/api/surveys/{sid}")
        assert r.status_code == 200


class TestSurveyCascadeDeleteWorkflow:
    """Pattern 7: Deleting survey cascades to all sub-entities."""

    def test_survey_delete_cascades_everything(self):
        """
        1. Create survey
        2. Add 3 questions
        3. Add 2 triggers
        4. Create tag and associate
        5. Activate and submit responses
        6. Delete survey
        7. Verify ALL sub-entities are 404
        8. Verify tag itself still exists
        """
        # 1. Create survey
        r = post("/api/surveys", {"name": "Cascade All"})
        sid = r.json()["id"]

        # 2. Questions
        q_ids = []
        for i in range(3):
            r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": f"Q{i}"})
            assert r.status_code == 201
            q_ids.append(r.json()["id"])

        # 3. Triggers
        t_ids = []
        for _ in range(2):
            r = post(f"/api/surveys/{sid}/triggers", {"type": "manual"})
            assert r.status_code == 201
            t_ids.append(r.json()["id"])

        # 4. Tag
        tag_name = f"cascade-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": tag_name})
        tag_id = r.json()["id"]
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tag_id})
        assert r.status_code == 201

        # 5. Responses
        patch(f"/api/surveys/{sid}/status", {"status": "active"})
        r = post(f"/api/surveys/{sid}/responses", {"data": {q_ids[0]: "ans"}, "finished": True})
        assert r.status_code == 201
        resp_id = r.json()["id"]

        # 6. Delete survey
        r = delete(f"/api/surveys/{sid}")
        assert r.status_code == 200

        # 7. All sub-entities 404
        r = get(f"/api/surveys/{sid}")
        assert r.status_code == 404

        for qid in q_ids:
            r = get(f"/api/surveys/{sid}/questions/{qid}")
            assert r.status_code == 404

        for tid in t_ids:
            r = get(f"/api/surveys/{sid}/triggers/{tid}")
            assert r.status_code == 404

        r = get(f"/api/surveys/{sid}/responses/{resp_id}")
        assert r.status_code == 404

        # 8. Tag itself still exists
        r = get(f"/api/tags/{tag_id}")
        assert r.status_code == 200
        assert r.json()["name"] == tag_name


class TestSegmentFilterWorkflow:
    """Pattern 3+5+6: Segment filtering evaluates correctly across multiple people."""

    def test_segment_complex_filtering(self):
        """
        1. Create 5 people with varied attributes
        2. Create segment with AND filters (plan=pro AND country contains 'United')
        3. Verify only matching people returned
        4. Update segment filters
        5. Verify updated results
        6. Verify segment invisible in env2
        """
        # 1. Create people
        people = []
        attrs_list = [
            {"plan": "pro", "country": "United States"},
            {"plan": "pro", "country": "United Kingdom"},
            {"plan": "pro", "country": "Germany"},
            {"plan": "free", "country": "United States"},
            {"plan": "enterprise", "country": "United Kingdom"},
        ]
        for i, attrs in enumerate(attrs_list):
            r = post("/api/people", {
                "email": f"seg-wf-{uuid.uuid4().hex[:6]}-{i}@test.com",
                "attributes": attrs
            })
            assert r.status_code == 201
            people.append(r.json())

        # 2. Create segment: plan=pro AND country contains "United"
        r = post("/api/segments", {
            "name": f"pro-united-{uuid.uuid4().hex[:6]}",
            "filters": [
                {"attribute": "plan", "operator": "equals", "value": "pro"},
                {"attribute": "country", "operator": "contains", "value": "United"},
            ]
        })
        assert r.status_code == 201
        seg_id = r.json()["id"]

        # 3. Verify matching people (indices 0, 1)
        r = get(f"/api/segments/{seg_id}/people")
        assert r.status_code == 200
        matched_ids = [p["id"] for p in r.json()]
        assert people[0]["id"] in matched_ids
        assert people[1]["id"] in matched_ids
        assert people[2]["id"] not in matched_ids  # Germany
        assert people[3]["id"] not in matched_ids  # free
        assert people[4]["id"] not in matched_ids  # enterprise

        # 4. Update: now just country contains "Germany"
        r = put(f"/api/segments/{seg_id}", {
            "name": "germany-only",
            "filters": [{"attribute": "country", "operator": "contains", "value": "Germany"}]
        })
        assert r.status_code == 200

        # 5. Verify updated results
        r = get(f"/api/segments/{seg_id}/people")
        assert r.status_code == 200
        matched_ids = [p["id"] for p in r.json()]
        assert people[2]["id"] in matched_ids
        assert people[0]["id"] not in matched_ids
        assert people[1]["id"] not in matched_ids

        # 6. Segment invisible in env2
        r = get(f"/api/segments/{seg_id}", headers=HEADERS_ENV2)
        assert r.status_code == 404


class TestSurveyStatusMachineWorkflow:
    """Pattern 4+5+8: Complete state machine traversal with response validation."""

    def test_full_state_machine_traversal(self):
        """
        1. Create survey (draft)
        2. Verify can't submit response to draft
        3. Activate
        4. Submit responses
        5. Pause → verify can't submit
        6. Resume → verify can submit
        7. Complete → verify can't submit
        8. Verify can't change from completed
        """
        # 1.
        r = post("/api/surveys", {"name": "State Machine WF"})
        assert r.status_code == 201
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q", "required": True})
        qid = r.json()["id"]

        # 2. Can't submit to draft
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "x"}, "finished": True})
        assert r.status_code == 400

        # 3. Activate
        r = patch(f"/api/surveys/{sid}/status", {"status": "active"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        # 4. Submit
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "x"}, "finished": True})
        assert r.status_code == 201

        # 5. Pause
        r = patch(f"/api/surveys/{sid}/status", {"status": "paused"})
        assert r.status_code == 200
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "y"}, "finished": True})
        assert r.status_code == 400

        # 6. Resume
        r = patch(f"/api/surveys/{sid}/status", {"status": "active"})
        assert r.status_code == 200
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "z"}, "finished": True})
        assert r.status_code == 201

        # 7. Complete
        r = patch(f"/api/surveys/{sid}/status", {"status": "completed"})
        assert r.status_code == 200
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "w"}, "finished": True})
        assert r.status_code == 400

        # 8. Can't change from completed
        r = patch(f"/api/surveys/{sid}/status", {"status": "active"})
        assert r.status_code == 400
        r = patch(f"/api/surveys/{sid}/status", {"status": "paused"})
        assert r.status_code == 400
        r = patch(f"/api/surveys/{sid}/status", {"status": "draft"})
        assert r.status_code == 400


class TestTagSurveyAssociationWorkflow:
    """Pattern 7+8: Tag associations, uniqueness, and cascade."""

    def test_tag_survey_association_lifecycle(self):
        """
        1. Create 2 tags
        2. Create survey
        3. Add both tags to survey
        4. Verify duplicate add fails (409)
        5. Remove one tag
        6. Delete the other tag → association gone
        7. Verify removed association returns 404
        """
        # 1.
        tag1_name = f"tag1-{uuid.uuid4().hex[:8]}"
        tag2_name = f"tag2-{uuid.uuid4().hex[:8]}"
        r = post("/api/tags", {"name": tag1_name})
        assert r.status_code == 201
        tag1_id = r.json()["id"]
        r = post("/api/tags", {"name": tag2_name})
        assert r.status_code == 201
        tag2_id = r.json()["id"]

        # 2.
        r = post("/api/surveys", {"name": "Tag WF Survey"})
        sid = r.json()["id"]

        # 3.
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tag1_id})
        assert r.status_code == 201
        assert r.json()["surveyId"] == sid
        assert r.json()["tagId"] == tag1_id
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tag2_id})
        assert r.status_code == 201

        # 4. Duplicate → 409
        r = post(f"/api/surveys/{sid}/tags", {"tagId": tag1_id})
        assert r.status_code == 409

        # 5. Remove tag1
        r = delete(f"/api/surveys/{sid}/tags/{tag1_id}")
        assert r.status_code == 200

        # Verify it's gone
        r = delete(f"/api/surveys/{sid}/tags/{tag1_id}")
        assert r.status_code == 404

        # 6. Delete tag2 → association cascade
        r = delete(f"/api/tags/{tag2_id}")
        assert r.status_code == 200

        # 7. Association gone
        r = delete(f"/api/surveys/{sid}/tags/{tag2_id}")
        assert r.status_code == 404


class TestRequiredFieldValidationWorkflow:
    """Pattern 4+5: Required field validation with multiple questions."""

    def test_required_validation_complex(self):
        """
        1. Create survey with 3 questions (2 required, 1 optional)
        2. Activate
        3. Submit missing first required → 422
        4. Submit missing second required → 422
        5. Submit empty required → 422
        6. Submit all required + optional → 201
        7. Submit only required (omit optional) → 201
        8. Verify response data roundtrip
        """
        r = post("/api/surveys", {"name": "Required WF"})
        sid = r.json()["id"]

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "openText", "headline": "Name", "required": True
        })
        q1 = r.json()["id"]

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "nps", "headline": "Score", "required": True
        })
        q2 = r.json()["id"]

        r = post(f"/api/surveys/{sid}/questions", {
            "type": "openText", "headline": "Comments", "required": False
        })
        q3 = r.json()["id"]

        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        # 3. Missing q1
        r = post(f"/api/surveys/{sid}/responses", {"data": {q2: 8}, "finished": True})
        assert r.status_code == 422

        # 4. Missing q2
        r = post(f"/api/surveys/{sid}/responses", {"data": {q1: "Bob"}, "finished": True})
        assert r.status_code == 422

        # 5. Empty required
        r = post(f"/api/surveys/{sid}/responses", {"data": {q1: "", q2: 8}, "finished": True})
        assert r.status_code == 422

        # 6. All present
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {q1: "Alice", q2: 9, q3: "Great"}, "finished": True
        })
        assert r.status_code == 201
        resp = r.json()
        assert resp["data"][q1] == "Alice"
        assert resp["data"][q2] == 9
        assert resp["data"][q3] == "Great"

        # 7. Only required
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {q1: "Bob", q2: 7}, "finished": True
        })
        assert r.status_code == 201

        # 8. Verify roundtrip
        rid = r.json()["id"]
        r = get(f"/api/surveys/{sid}/responses/{rid}")
        assert r.status_code == 200
        assert r.json()["data"][q1] == "Bob"
        assert r.json()["data"][q2] == 7


class TestAutoCloseWorkflow:
    """Pattern 5+4: Auto-close (closesAt) interacts with state machine."""

    def test_auto_close_with_past_timestamp(self):
        """
        1. Create survey with closesAt in the past
        2. Activate it
        3. GET shows status=completed
        4. Submitting response → 400
        5. Create another survey with future closesAt
        6. Activate and submit → 201
        """
        # 1+2.
        r = post("/api/surveys", {"name": "Auto Close WF", "closesAt": PAST_TIMESTAMP})
        assert r.status_code == 201
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        # 3. Status shows completed
        r = get(f"/api/surveys/{sid}")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        # 4. Response rejected
        r = post(f"/api/surveys/{sid}/responses", {"data": {qid: "late"}, "finished": True})
        assert r.status_code == 400

        # 5+6. Future closesAt works fine
        r = post("/api/surveys", {"name": "Future Close", "closesAt": FUTURE_TIMESTAMP})
        sid2 = r.json()["id"]
        r = post(f"/api/surveys/{sid2}/questions", {"type": "openText", "headline": "Q2"})
        qid2 = r.json()["id"]
        patch(f"/api/surveys/{sid2}/status", {"status": "active"})

        r = post(f"/api/surveys/{sid2}/responses", {"data": {qid2: "on time"}, "finished": True})
        assert r.status_code == 201


class TestMultiEnvironmentWorkflow:
    """Pattern 6: Complete isolation workflow between two environments."""

    def test_full_isolation_across_entities(self):
        """
        1. Create survey, person, tag, webhook in env1
        2. Verify all accessible in env1
        3. Verify NONE accessible in env2
        4. Create same-named tag in env2 → succeeds (no conflict)
        5. Verify env2 tag is separate
        """
        # 1. Create in env1
        r = post("/api/surveys", {"name": "Iso WF Survey"})
        assert r.status_code == 201
        s1_id = r.json()["id"]

        r = post("/api/people", {"email": "iso-wf@test.com"})
        assert r.status_code == 201
        p1_id = r.json()["id"]

        tag_name = f"iso-tag-{uuid.uuid4().hex[:6]}"
        r = post("/api/tags", {"name": tag_name})
        assert r.status_code == 201
        t1_id = r.json()["id"]

        r = post("/api/webhooks", {"url": "https://iso.test", "triggers": ["responseCreated"]})
        assert r.status_code == 201
        w1_id = r.json()["id"]

        # 2. Accessible in env1
        assert get(f"/api/surveys/{s1_id}").status_code == 200
        assert get(f"/api/people/{p1_id}").status_code == 200
        assert get(f"/api/tags/{t1_id}").status_code == 200
        assert get(f"/api/webhooks/{w1_id}").status_code == 200

        # 3. NOT accessible in env2
        assert get(f"/api/surveys/{s1_id}", headers=HEADERS_ENV2).status_code == 404
        assert get(f"/api/people/{p1_id}", headers=HEADERS_ENV2).status_code == 404
        assert get(f"/api/tags/{t1_id}", headers=HEADERS_ENV2).status_code == 404
        assert get(f"/api/webhooks/{w1_id}", headers=HEADERS_ENV2).status_code == 404

        # 4. Same tag name in env2 → no conflict
        r = post("/api/tags", {"name": tag_name}, headers=HEADERS_ENV2)
        assert r.status_code == 201
        t2_id = r.json()["id"]
        assert t2_id != t1_id

        # 5. Env2 tag is separate
        r = get(f"/api/tags/{t2_id}", headers=HEADERS_ENV2)
        assert r.status_code == 200
        assert r.json()["name"] == tag_name
        assert r.json()["environmentId"] == ENV_ID_2


class TestRatingAnalyticsWorkflow:
    """Pattern 5: Rating analytics computed correctly with varied inputs."""

    def test_rating_analytics_comprehensive(self):
        """
        1. Create survey with rating question (range=5)
        2. Activate and submit 6 ratings: 1,2,3,4,5,5
        3. Verify average = 3.33
        4. Verify distribution: {1:1, 2:1, 3:1, 4:1, 5:2}
        5. Verify totalAnswers = 6
        """
        r = post("/api/surveys", {"name": "Rating WF"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {
            "type": "rating", "headline": "Rate us", "ratingRange": 5
        })
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        for score in [1, 2, 3, 4, 5, 5]:
            r = post(f"/api/surveys/{sid}/responses", {"data": {qid: score}, "finished": True})
            assert r.status_code == 201

        r = get(f"/api/surveys/{sid}/analytics")
        assert r.status_code == 200
        a = r.json()
        rating_stat = next(s for s in a["questionStats"] if s["questionId"] == qid)

        assert rating_stat["totalAnswers"] == 6
        # Average = (1+2+3+4+5+5)/6 = 20/6 ≈ 3.33
        assert rating_stat["average"] == pytest.approx(20.0 / 6, abs=0.1)

        dist = rating_stat["distribution"]
        assert dist.get("1") == 1 or dist.get(1) == 1
        assert dist.get("2") == 1 or dist.get(2) == 1
        assert dist.get("3") == 1 or dist.get(3) == 1
        assert dist.get("4") == 1 or dist.get(4) == 1
        assert dist.get("5") == 2 or dist.get(5) == 2


class TestTriggerAndQuestionOrdering:
    """Pattern 1+3+7: Triggers and question ordering edge cases."""

    def test_triggers_and_question_ordering(self):
        """
        1. Create survey
        2. Add 3 questions
        3. Verify positions 1,2,3
        4. Delete position 1
        5. Verify remaining compact to 1,2
        6. Add attribute trigger
        7. Verify trigger fields (camelCase)
        8. Delete survey → triggers gone
        """
        r = post("/api/surveys", {"name": "Trigger Order WF"})
        sid = r.json()["id"]

        # 2. Add questions
        q_ids = []
        for i in range(3):
            r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": f"Q{i+1}"})
            assert r.status_code == 201
            q_ids.append(r.json()["id"])
            assert r.json()["position"] == i + 1

        # 4. Delete first
        r = delete(f"/api/surveys/{sid}/questions/{q_ids[0]}")
        assert r.status_code == 200

        # 5. Compact
        r = get(f"/api/surveys/{sid}/questions")
        assert r.status_code == 200
        qs = r.json()
        assert len(qs) == 2
        positions = sorted([q["position"] for q in qs])
        assert positions == [1, 2]

        # 6. Add trigger
        r = post(f"/api/surveys/{sid}/triggers", {
            "type": "attribute",
            "attributeName": "plan",
            "attributeValue": "premium",
        })
        assert r.status_code == 201
        trigger = r.json()
        assert trigger["type"] == "attribute"
        assert trigger["attributeName"] == "plan"
        assert trigger["attributeValue"] == "premium"
        assert "id" in trigger
        assert "surveyId" in trigger
        assert trigger["surveyId"] == sid
        assert "createdAt" in trigger
        tid = trigger["id"]

        # 8. Delete survey → trigger gone
        delete(f"/api/surveys/{sid}")
        r = get(f"/api/surveys/{sid}/triggers/{tid}")
        assert r.status_code == 404


class TestPersonInvalidLinking:
    """Pattern 4+8: Invalid person linking."""

    def test_invalid_person_linking_workflow(self):
        """
        1. Create person
        2. Create survey, activate
        3. Link response to non-existent person → 422
        4. Link response to valid person → 201
        5. Verify personId in response
        6. Verify response accessible by GET
        """
        email = f"unique-{uuid.uuid4().hex[:8]}@test.com"

        # 1.
        r = post("/api/people", {"email": email, "attributes": {"tier": "gold"}})
        assert r.status_code == 201
        pid = r.json()["id"]

        # 2.
        r = post("/api/surveys", {"name": "Link Invalid"})
        sid = r.json()["id"]
        r = post(f"/api/surveys/{sid}/questions", {"type": "openText", "headline": "Q"})
        qid = r.json()["id"]
        patch(f"/api/surveys/{sid}/status", {"status": "active"})

        # 3. Non-existent person → 422
        fake_pid = str(uuid.uuid4())
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {qid: "x"}, "finished": True, "personId": fake_pid
        })
        assert r.status_code == 422

        # 4. Valid person → 201
        r = post(f"/api/surveys/{sid}/responses", {
            "data": {qid: "y"}, "finished": True, "personId": pid
        })
        assert r.status_code == 201

        # 5. Verify
        resp = r.json()
        assert resp["personId"] == pid
        assert resp["surveyId"] == sid
        assert resp["finished"] is True

        # 6. GET roundtrip
        r = get(f"/api/surveys/{sid}/responses/{resp['id']}")
        assert r.status_code == 200
        assert r.json()["personId"] == pid
        assert r.json()["data"][qid] == "y"
