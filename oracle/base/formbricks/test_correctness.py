"""
BackendForge — Comprehensive Correctness Tests for Formbricks Task

Tests survey lifecycle, question management, response collection,
analytics (NPS, completion rate, MC stats, rating stats),
required field validation, and environment isolation.

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
PAST_TIMESTAMP = "2000-01-01T00:00:00+00:00"
ENV_ID = "00000000-0000-0000-0000-000000000001"
ENV_ID_2 = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000003"

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

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_patch(path, json_data=None, headers=None):
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)


# ── Domain Helpers ──

def create_survey(name, **kwargs):
    """Create a survey and return the full object."""
    data = {"name": name, **kwargs}
    resp = api_post("/api/surveys", data)
    assert resp.status_code == 201, f"Create survey failed: {resp.status_code} {resp.text}"
    return resp.json()


def get_survey(survey_id):
    """GET /api/surveys/{id} → SurveyDetail."""
    resp = api_get(f"/api/surveys/{survey_id}")
    assert resp.status_code == 200, f"Get survey failed: {resp.status_code} {resp.text}"
    return resp.json()


def activate_survey(survey_id):
    """Transition survey to active status."""
    resp = api_patch(f"/api/surveys/{survey_id}/status", {"status": "active"})
    assert resp.status_code == 200, f"Activate survey failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_question(survey_id, headline, qtype="openText", **kwargs):
    """Create a question and return the full object."""
    data = {"headline": headline, "type": qtype, **kwargs}
    resp = api_post(f"/api/surveys/{survey_id}/questions", data)
    assert resp.status_code == 201, f"Create question failed: {resp.status_code} {resp.text}"
    return resp.json()


def create_person(**kwargs):
    """Create a person and return the full object."""
    resp = api_post("/api/people", kwargs)
    assert resp.status_code == 201, f"Create person failed: {resp.status_code} {resp.text}"
    return resp.json()


def submit_response(survey_id, data, finished=True, person_id=None):
    """Submit a response to a survey."""
    body = {"data": data, "finished": finished}
    if person_id:
        body["personId"] = person_id
    resp = api_post(f"/api/surveys/{survey_id}/responses", body)
    return resp


# ════════════════════════════════════════════════════════════════════
# PART 1: Basic CRUD
# ════════════════════════════════════════════════════════════════════


class TestSurveyCRUD:
    """Create → read → update → delete surveys."""

    def test_survey_lifecycle(self):
        name = f"CRUD Survey {UNIQUE}"
        survey = create_survey(name, type="link")
        survey_id = survey["id"]
        assert survey["name"] == name
        assert survey["status"] == "draft"
        assert survey["type"] == "link"

        # Read
        detail = get_survey(survey_id)
        assert detail["name"] == name
        assert "questions" in detail

        # Update
        resp = api_put(f"/api/surveys/{survey_id}", {
            "name": f"Updated {name}",
            "redirectUrl": "https://example.com/thanks",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"Updated {name}"
        assert updated["redirectUrl"] == "https://example.com/thanks"

        # Delete
        resp = api_delete(f"/api/surveys/{survey_id}")
        assert resp.status_code == 200

        # Verify 404
        resp = api_get(f"/api/surveys/{survey_id}")
        assert resp.status_code == 404

    def test_survey_with_cards(self):
        """Create survey with welcome and thank you cards."""
        survey = create_survey(f"Cards Survey {UNIQUE}", welcomeCard={
            "enabled": True,
            "headline": "Welcome!",
            "description": "Tell us what you think.",
        }, thankYouCard={
            "enabled": True,
            "headline": "Thanks!",
            "description": "We appreciate your feedback.",
        })
        detail = get_survey(survey["id"])
        assert detail["welcomeCard"]["enabled"] is True
        assert detail["welcomeCard"]["headline"] == "Welcome!"
        assert detail["thankYouCard"]["enabled"] is True
        assert detail["thankYouCard"]["headline"] == "Thanks!"

    def test_list_surveys_filter_by_status(self):
        """GET /api/surveys?status= filters correctly."""
        s1 = create_survey(f"Draft {UNIQUE}")
        s2 = create_survey(f"Active {UNIQUE}")
        activate_survey(s2["id"])

        # Filter drafts
        resp = api_get("/api/surveys", params={"status": "draft"})
        assert resp.status_code == 200
        drafts = resp.json()
        draft_ids = [s["id"] for s in drafts]
        assert s1["id"] in draft_ids
        assert s2["id"] not in draft_ids

        # Filter active
        resp = api_get("/api/surveys", params={"status": "active"})
        assert resp.status_code == 200
        actives = resp.json()
        active_ids = [s["id"] for s in actives]
        assert s2["id"] in active_ids
        assert s1["id"] not in active_ids


class TestQuestionCRUD:
    """Create → read → update → delete questions."""

    def test_question_lifecycle(self):
        survey = create_survey(f"Q Survey {UNIQUE}")
        survey_id = survey["id"]

        # Create
        q = create_question(survey_id, f"What is your name? {UNIQUE}", "openText", required=True)
        q_id = q["id"]
        assert q["headline"] == f"What is your name? {UNIQUE}"
        assert q["type"] == "openText"
        assert q["required"] is True
        assert q["position"] == 1

        # Read
        resp = api_get(f"/api/surveys/{survey_id}/questions/{q_id}")
        assert resp.status_code == 200
        assert resp.json()["headline"] == f"What is your name? {UNIQUE}"

        # Update
        resp = api_put(f"/api/surveys/{survey_id}/questions/{q_id}", {
            "headline": "Updated headline",
        })
        assert resp.status_code == 200
        assert resp.json()["headline"] == "Updated headline"

        # Delete
        resp = api_delete(f"/api/surveys/{survey_id}/questions/{q_id}")
        assert resp.status_code == 200

        # Verify 404
        resp = api_get(f"/api/surveys/{survey_id}/questions/{q_id}")
        assert resp.status_code == 404

    def test_question_types(self):
        """Create questions of various types."""
        survey = create_survey(f"Types Survey {UNIQUE}")
        sid = survey["id"]

        # Multiple choice single
        mc = create_question(sid, "Favorite color?", "multipleChoiceSingle",
                             options=["Red", "Blue", "Green"])
        assert mc["type"] == "multipleChoiceSingle"
        assert mc["options"] == ["Red", "Blue", "Green"]

        # Rating
        r = create_question(sid, "Rate us", "rating", ratingRange=5)
        assert r["type"] == "rating"
        assert r["ratingRange"] == 5

        # NPS
        n = create_question(sid, "Recommend us?", "nps")
        assert n["type"] == "nps"


class TestResponseCRUD:
    """Submit → read → delete responses."""

    def test_response_lifecycle(self):
        survey = create_survey(f"Resp Survey {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Tell us something", "openText")
        activate_survey(sid)

        # Submit
        resp = submit_response(sid, {q["id"]: "Hello world"}, finished=True)
        assert resp.status_code == 201
        response = resp.json()
        assert response["finished"] is True
        assert response["data"][q["id"]] == "Hello world"
        response_id = response["id"]

        # Read
        resp = api_get(f"/api/surveys/{sid}/responses/{response_id}")
        assert resp.status_code == 200
        assert resp.json()["data"][q["id"]] == "Hello world"

        # List
        resp = api_get(f"/api/surveys/{sid}/responses")
        assert resp.status_code == 200
        responses = resp.json()
        assert any(r["id"] == response_id for r in responses)

        # Delete
        resp = api_delete(f"/api/surveys/{sid}/responses/{response_id}")
        assert resp.status_code == 200

        resp = api_get(f"/api/surveys/{sid}/responses/{response_id}")
        assert resp.status_code == 404


class TestPeopleCRUD:
    """Create → read → update → delete people."""

    def test_person_lifecycle(self):
        person = create_person(email=f"test-{UNIQUE}@example.com", userId=f"ext-{UNIQUE}",
                               attributes={"plan": "pro", "company": "Acme"})
        pid = person["id"]
        assert person["email"] == f"test-{UNIQUE}@example.com"
        assert person["userId"] == f"ext-{UNIQUE}"
        assert person["attributes"]["plan"] == "pro"

        # Read
        resp = api_get(f"/api/people/{pid}")
        assert resp.status_code == 200
        assert resp.json()["email"] == f"test-{UNIQUE}@example.com"

        # Update
        resp = api_put(f"/api/people/{pid}", {"email": f"updated-{UNIQUE}@example.com"})
        assert resp.status_code == 200
        assert resp.json()["email"] == f"updated-{UNIQUE}@example.com"

        # Delete
        resp = api_delete(f"/api/people/{pid}")
        assert resp.status_code == 200

        resp = api_get(f"/api/people/{pid}")
        assert resp.status_code == 404


class TestTriggerCRUD:
    """Create → read → update → delete triggers."""

    def test_trigger_lifecycle(self):
        survey = create_survey(f"Trigger Survey {UNIQUE}")
        sid = survey["id"]

        # Create manual trigger
        resp = api_post(f"/api/surveys/{sid}/triggers", {"type": "manual"})
        assert resp.status_code == 201
        trigger = resp.json()
        tid = trigger["id"]
        assert trigger["type"] == "manual"

        # Read
        resp = api_get(f"/api/surveys/{sid}/triggers/{tid}")
        assert resp.status_code == 200
        assert resp.json()["type"] == "manual"

        # Update to attribute trigger
        resp = api_put(f"/api/surveys/{sid}/triggers/{tid}", {
            "type": "attribute",
            "attributeName": "plan",
            "attributeValue": "pro",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["type"] == "attribute"
        assert updated["attributeName"] == "plan"
        assert updated["attributeValue"] == "pro"

        # List
        resp = api_get(f"/api/surveys/{sid}/triggers")
        assert resp.status_code == 200
        triggers = resp.json()
        assert any(t["id"] == tid for t in triggers)

        # Delete
        resp = api_delete(f"/api/surveys/{sid}/triggers/{tid}")
        assert resp.status_code == 200

        resp = api_get(f"/api/surveys/{sid}/triggers/{tid}")
        assert resp.status_code == 404


class TestEnvironment:
    """GET /api/environments/current."""

    def test_get_current_environment(self):
        resp = api_get("/api/environments/current")
        assert resp.status_code == 200
        env = resp.json()
        assert env["id"] == ENV_ID


# ════════════════════════════════════════════════════════════════════
# PART 2: Survey Lifecycle State Machine
# ════════════════════════════════════════════════════════════════════


class TestSurveyLifecycle:
    """Rule 1: Survey status transitions."""

    def test_draft_to_active(self):
        survey = create_survey(f"Lifecycle {UNIQUE} d2a")
        assert survey["status"] == "draft"
        result = activate_survey(survey["id"])
        assert result["status"] == "active"

    def test_active_to_paused(self):
        survey = create_survey(f"Lifecycle {UNIQUE} a2p")
        activate_survey(survey["id"])
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_active_to_completed(self):
        survey = create_survey(f"Lifecycle {UNIQUE} a2c")
        activate_survey(survey["id"])
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_paused_to_active(self):
        survey = create_survey(f"Lifecycle {UNIQUE} p2a")
        activate_survey(survey["id"])
        api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "active"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_paused_to_completed(self):
        survey = create_survey(f"Lifecycle {UNIQUE} p2c")
        activate_survey(survey["id"])
        api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_completed_cannot_change(self):
        """Completed is terminal — cannot go back to active or paused."""
        survey = create_survey(f"Lifecycle {UNIQUE} cterm")
        activate_survey(survey["id"])
        api_patch(f"/api/surveys/{survey['id']}/status", {"status": "completed"})

        # Try to reactivate
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "active"})
        assert resp.status_code == 400, f"Completed→active should be 400, got {resp.status_code}"

        # Try to pause
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        assert resp.status_code == 400, f"Completed→paused should be 400, got {resp.status_code}"

    def test_draft_to_paused_invalid(self):
        """draft→paused is invalid."""
        survey = create_survey(f"Lifecycle {UNIQUE} d2p")
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        assert resp.status_code == 400, f"Draft→paused should be 400, got {resp.status_code}"

    def test_draft_to_completed_invalid(self):
        """draft→completed is invalid."""
        survey = create_survey(f"Lifecycle {UNIQUE} d2c")
        resp = api_patch(f"/api/surveys/{survey['id']}/status", {"status": "completed"})
        assert resp.status_code == 400, f"Draft→completed should be 400, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 3: Response Validation
# ════════════════════════════════════════════════════════════════════


class TestResponseValidation:
    """Rules 2, 3: Only active surveys accept responses; required fields enforced."""

    def test_cannot_submit_to_draft_survey(self):
        """Rule 2: Draft survey rejects responses."""
        survey = create_survey(f"DraftReject {UNIQUE}")
        q = create_question(survey["id"], "Question", "openText")
        resp = submit_response(survey["id"], {q["id"]: "answer"}, finished=True)
        assert resp.status_code == 400, f"Draft survey should reject response, got {resp.status_code}"

    def test_cannot_submit_to_paused_survey(self):
        """Rule 2: Paused survey rejects responses."""
        survey = create_survey(f"PausedReject {UNIQUE}")
        q = create_question(survey["id"], "Question", "openText")
        activate_survey(survey["id"])
        api_patch(f"/api/surveys/{survey['id']}/status", {"status": "paused"})
        resp = submit_response(survey["id"], {q["id"]: "answer"}, finished=True)
        assert resp.status_code == 400, f"Paused survey should reject response, got {resp.status_code}"

    def test_cannot_submit_to_completed_survey(self):
        """Rule 2: Completed survey rejects responses."""
        survey = create_survey(f"CompReject {UNIQUE}")
        q = create_question(survey["id"], "Question", "openText")
        activate_survey(survey["id"])
        api_patch(f"/api/surveys/{survey['id']}/status", {"status": "completed"})
        resp = submit_response(survey["id"], {q["id"]: "answer"}, finished=True)
        assert resp.status_code == 400, f"Completed survey should reject response, got {resp.status_code}"

    def test_required_field_missing_rejected(self):
        """Rule 3: Missing required question answer → 422."""
        survey = create_survey(f"Required {UNIQUE}")
        q_req = create_question(survey["id"], "Required Q", "openText", required=True)
        q_opt = create_question(survey["id"], "Optional Q", "openText", required=False)
        activate_survey(survey["id"])

        # Submit without required answer
        resp = submit_response(survey["id"], {q_opt["id"]: "optional answer"}, finished=True)
        assert resp.status_code == 422, f"Missing required field should be 422, got {resp.status_code}"

    def test_required_field_empty_rejected(self):
        """Rule 3: Empty string for required question → 422."""
        survey = create_survey(f"EmptyReq {UNIQUE}")
        q = create_question(survey["id"], "Required", "openText", required=True)
        activate_survey(survey["id"])

        resp = submit_response(survey["id"], {q["id"]: ""}, finished=True)
        assert resp.status_code == 422, f"Empty required field should be 422, got {resp.status_code}"

    def test_required_field_present_accepted(self):
        """Rule 3: When all required fields are answered, response is accepted."""
        survey = create_survey(f"ReqPresent {UNIQUE}")
        q = create_question(survey["id"], "Required", "openText", required=True)
        activate_survey(survey["id"])

        resp = submit_response(survey["id"], {q["id"]: "I answered"}, finished=True)
        assert resp.status_code == 201, f"Valid required field should succeed, got {resp.status_code}"

    def test_optional_field_can_be_omitted(self):
        """Optional questions can be missing from data without error."""
        survey = create_survey(f"OptOmit {UNIQUE}")
        q_req = create_question(survey["id"], "Required", "openText", required=True)
        q_opt = create_question(survey["id"], "Optional", "openText", required=False)
        activate_survey(survey["id"])

        # Only answer required question
        resp = submit_response(survey["id"], {q_req["id"]: "answer"}, finished=True)
        assert resp.status_code == 201, f"Omitting optional should be fine, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 4: Survey Auto-Close
# ════════════════════════════════════════════════════════════════════


class TestSurveyAutoClose:
    """Rule 5: closesAt in the past → behaves as completed."""

    def test_closed_survey_rejects_responses(self):
        """Survey with closesAt in past rejects new responses."""
        survey = create_survey(f"AutoClose {UNIQUE}")
        q = create_question(survey["id"], "Q", "openText")
        activate_survey(survey["id"])
        # Expire an active survey without attempting completed -> active.
        expired = api_put(f"/api/surveys/{survey['id']}", {"closesAt": PAST_TIMESTAMP})
        assert expired.status_code == 200, expired.text

        resp = submit_response(survey["id"], {q["id"]: "too late"}, finished=True)
        assert resp.status_code == 400, f"Closed survey should reject response, got {resp.status_code}"

    def test_closed_survey_status_shows_completed(self):
        """Survey with closesAt in past shows status=completed in GET."""
        survey = create_survey(f"AutoCloseStatus {UNIQUE}")
        activate_survey(survey["id"])
        # Expire an active survey without attempting completed -> active.
        expired = api_put(f"/api/surveys/{survey['id']}", {"closesAt": PAST_TIMESTAMP})
        assert expired.status_code == 200, expired.text

        detail = get_survey(survey["id"])
        assert detail["status"] == "completed", (
            f"Survey with closesAt in past should show completed, got {detail['status']}"
        )


# ════════════════════════════════════════════════════════════════════
# PART 5: Question Ordering
# ════════════════════════════════════════════════════════════════════


class TestQuestionOrdering:
    """Rule 4: Position field management."""

    def test_auto_position_assignment(self):
        """Questions without explicit position get next available."""
        survey = create_survey(f"Order {UNIQUE}")
        sid = survey["id"]

        q1 = create_question(sid, "First", "openText")
        q2 = create_question(sid, "Second", "openText")
        q3 = create_question(sid, "Third", "openText")

        assert q1["position"] == 1
        assert q2["position"] == 2
        assert q3["position"] == 3

    def test_explicit_position(self):
        """Specifying position puts question at that position."""
        survey = create_survey(f"ExplPos {UNIQUE}")
        sid = survey["id"]

        q1 = create_question(sid, "First", "openText")
        q2 = create_question(sid, "Second", "openText", position=1)

        # q2 inserted at position 1, q1 should shift to 2
        resp = api_get(f"/api/surveys/{sid}/questions")
        assert resp.status_code == 200
        questions = resp.json()
        q1_data = next(q for q in questions if q["id"] == q1["id"])
        q2_data = next(q for q in questions if q["id"] == q2["id"])
        assert q2_data["position"] == 1
        assert q1_data["position"] == 2

    def test_delete_compacts_positions(self):
        """Deleting a question compacts remaining positions."""
        survey = create_survey(f"Compact {UNIQUE}")
        sid = survey["id"]

        q1 = create_question(sid, "First", "openText")
        q2 = create_question(sid, "Second", "openText")
        q3 = create_question(sid, "Third", "openText")

        # Delete q2 (position 2)
        api_delete(f"/api/surveys/{sid}/questions/{q2['id']}")

        # Remaining should be compacted: q1=1, q3=2
        resp = api_get(f"/api/surveys/{sid}/questions")
        assert resp.status_code == 200
        questions = resp.json()
        assert len(questions) == 2
        positions = sorted([q["position"] for q in questions])
        assert positions == [1, 2], f"Positions should be compacted to [1,2], got {positions}"

    def test_questions_returned_ordered(self):
        """GET questions returns them ordered by position."""
        survey = create_survey(f"Ordered {UNIQUE}")
        sid = survey["id"]

        create_question(sid, "C Third", "openText")
        create_question(sid, "A First", "openText", position=1)
        create_question(sid, "B Second", "openText", position=2)

        resp = api_get(f"/api/surveys/{sid}/questions")
        assert resp.status_code == 200
        questions = resp.json()
        positions = [q["position"] for q in questions]
        assert positions == sorted(positions), f"Questions not sorted by position: {positions}"


# ════════════════════════════════════════════════════════════════════
# PART 6: Analytics — NPS, Completion Rate, MC Stats, Rating Stats
# ════════════════════════════════════════════════════════════════════


class TestAnalyticsCompletionRate:
    """Rule 7, 10: Completion rate calculation."""

    def test_completion_rate_basic(self):
        """3 total, 2 finished → completionRate = 2/3 ≈ 0.667."""
        survey = create_survey(f"CompRate {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        submit_response(sid, {q["id"]: "a1"}, finished=True)
        submit_response(sid, {q["id"]: "a2"}, finished=True)
        submit_response(sid, {q["id"]: "a3"}, finished=False)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        assert analytics["totalResponses"] == 3
        assert analytics["completedResponses"] == 2
        assert analytics["completionRate"] == pytest.approx(2 / 3, abs=0.01)

    def test_completion_rate_all_finished(self):
        """All finished → completionRate = 1.0."""
        survey = create_survey(f"AllFinished {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        submit_response(sid, {q["id"]: "a1"}, finished=True)
        submit_response(sid, {q["id"]: "a2"}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        assert analytics["completionRate"] == pytest.approx(1.0, abs=0.01)

    def test_completion_rate_none_finished(self):
        """None finished → completionRate = 0.0."""
        survey = create_survey(f"NoneFinished {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        submit_response(sid, {q["id"]: "a1"}, finished=False)
        submit_response(sid, {q["id"]: "a2"}, finished=False)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        assert analytics["totalResponses"] == 2
        assert analytics["completedResponses"] == 0
        assert analytics["completionRate"] == pytest.approx(0.0, abs=0.01)


class TestAnalyticsNPS:
    """Rule 6: NPS calculation."""

    def test_nps_all_promoters(self):
        """All respondents give 9 or 10 → NPS = 100."""
        survey = create_survey(f"NPS Promo {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Recommend?", "nps")
        activate_survey(sid)

        submit_response(sid, {q["id"]: 9}, finished=True)
        submit_response(sid, {q["id"]: 10}, finished=True)
        submit_response(sid, {q["id"]: 9}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        assert nps_stat["nps"] == 100, f"All promoters → NPS=100, got {nps_stat['nps']}"

    def test_nps_all_detractors(self):
        """All respondents give 0-6 → NPS = -100."""
        survey = create_survey(f"NPS Detract {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Recommend?", "nps")
        activate_survey(sid)

        submit_response(sid, {q["id"]: 3}, finished=True)
        submit_response(sid, {q["id"]: 5}, finished=True)
        submit_response(sid, {q["id"]: 0}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        assert nps_stat["nps"] == -100, f"All detractors → NPS=-100, got {nps_stat['nps']}"

    def test_nps_mixed(self):
        """Mixed scores: 2 promoters, 1 passive, 2 detractors → NPS = (2/5 - 2/5)*100 = 0."""
        survey = create_survey(f"NPS Mixed {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Recommend?", "nps")
        activate_survey(sid)

        submit_response(sid, {q["id"]: 10}, finished=True)  # promoter
        submit_response(sid, {q["id"]: 9}, finished=True)   # promoter
        submit_response(sid, {q["id"]: 7}, finished=True)   # passive
        submit_response(sid, {q["id"]: 3}, finished=True)   # detractor
        submit_response(sid, {q["id"]: 5}, finished=True)   # detractor

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        # NPS = (2/5 - 2/5) * 100 = 0
        assert nps_stat["nps"] == 0, f"Expected NPS=0, got {nps_stat['nps']}"

    def test_nps_calculation_detailed(self):
        """4 promoters, 3 passives, 3 detractors → NPS = (4/10 - 3/10)*100 = 10."""
        survey = create_survey(f"NPS Detailed {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Recommend?", "nps")
        activate_survey(sid)

        # 4 promoters (9, 10)
        for score in [9, 10, 9, 10]:
            submit_response(sid, {q["id"]: score}, finished=True)
        # 3 passives (7, 8)
        for score in [7, 8, 7]:
            submit_response(sid, {q["id"]: score}, finished=True)
        # 3 detractors (0-6)
        for score in [2, 4, 6]:
            submit_response(sid, {q["id"]: score}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        # NPS = (4/10 - 3/10) * 100 = 10
        assert nps_stat["nps"] == 10, f"Expected NPS=10, got {nps_stat['nps']}"

    def test_nps_average(self):
        """NPS question also reports average score."""
        survey = create_survey(f"NPS Avg {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Recommend?", "nps")
        activate_survey(sid)

        submit_response(sid, {q["id"]: 6}, finished=True)
        submit_response(sid, {q["id"]: 8}, finished=True)
        submit_response(sid, {q["id"]: 10}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        nps_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        assert nps_stat["average"] == pytest.approx(8.0, abs=0.01)


class TestAnalyticsMultipleChoice:
    """Rule 8: Multiple choice stats."""

    def test_mc_single_distribution(self):
        """multipleChoiceSingle: count per option."""
        survey = create_survey(f"MC Single {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Favorite?", "multipleChoiceSingle",
                            options=["Red", "Blue", "Green"])
        activate_survey(sid)

        submit_response(sid, {q["id"]: "Red"}, finished=True)
        submit_response(sid, {q["id"]: "Red"}, finished=True)
        submit_response(sid, {q["id"]: "Blue"}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        mc_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        dist = mc_stat["distribution"]
        assert dist["Red"] == 2, f"Red should have 2, got {dist.get('Red')}"
        assert dist["Blue"] == 1, f"Blue should have 1, got {dist.get('Blue')}"
        assert dist.get("Green", 0) == 0, f"Green should have 0, got {dist.get('Green')}"

    def test_mc_multi_distribution(self):
        """multipleChoiceMulti: each selected option gets counted."""
        survey = create_survey(f"MC Multi {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Select all", "multipleChoiceMulti",
                            options=["A", "B", "C"])
        activate_survey(sid)

        submit_response(sid, {q["id"]: ["A", "B"]}, finished=True)
        submit_response(sid, {q["id"]: ["B", "C"]}, finished=True)
        submit_response(sid, {q["id"]: ["A"]}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        mc_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])
        dist = mc_stat["distribution"]
        assert dist["A"] == 2, f"A should have 2, got {dist.get('A')}"
        assert dist["B"] == 2, f"B should have 2, got {dist.get('B')}"
        assert dist["C"] == 1, f"C should have 1, got {dist.get('C')}"


class TestAnalyticsRating:
    """Rule 9: Rating stats — average and distribution."""

    def test_rating_average_and_distribution(self):
        """Rating question: average and count per value."""
        survey = create_survey(f"Rating {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Rate us", "rating", ratingRange=5)
        activate_survey(sid)

        submit_response(sid, {q["id"]: 5}, finished=True)
        submit_response(sid, {q["id"]: 4}, finished=True)
        submit_response(sid, {q["id"]: 4}, finished=True)
        submit_response(sid, {q["id"]: 3}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        rating_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q["id"])

        # Average = (5+4+4+3)/4 = 4.0
        assert rating_stat["average"] == pytest.approx(4.0, abs=0.01)

        dist = rating_stat["distribution"]
        assert dist["5"] == 1 or dist.get(5) == 1, f"Rating 5 should have count 1"
        assert dist["4"] == 2 or dist.get(4) == 2, f"Rating 4 should have count 2"
        assert dist["3"] == 1 or dist.get(3) == 1, f"Rating 3 should have count 1"


class TestAnalyticsTotalAnswers:
    """Analytics reports totalAnswers per question."""

    def test_total_answers_count(self):
        survey = create_survey(f"TotalAns {UNIQUE}")
        sid = survey["id"]
        q1 = create_question(sid, "Q1", "openText", required=True)
        q2 = create_question(sid, "Q2", "openText", required=False)
        activate_survey(sid)

        # 3 responses, all answer q1, only 2 answer q2
        submit_response(sid, {q1["id"]: "a", q2["id"]: "b"}, finished=True)
        submit_response(sid, {q1["id"]: "c", q2["id"]: "d"}, finished=True)
        submit_response(sid, {q1["id"]: "e"}, finished=True)

        resp = api_get(f"/api/surveys/{sid}/analytics")
        assert resp.status_code == 200
        analytics = resp.json()
        q1_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q1["id"])
        q2_stat = next(s for s in analytics["questionStats"] if s["questionId"] == q2["id"])
        assert q1_stat["totalAnswers"] == 3
        assert q2_stat["totalAnswers"] == 2


# ════════════════════════════════════════════════════════════════════
# PART 7: Person Linking
# ════════════════════════════════════════════════════════════════════


class TestPersonLinking:
    """Rule 11: Response can optionally link to a person."""

    def test_response_with_valid_person(self):
        """Response with valid personId is accepted."""
        person = create_person(email=f"linked-{UNIQUE}@example.com")
        survey = create_survey(f"PersonLink {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        resp = submit_response(sid, {q["id"]: "answer"}, finished=True, person_id=person["id"])
        assert resp.status_code == 201
        assert resp.json()["personId"] == person["id"]

    def test_response_with_invalid_person_rejected(self):
        """Response with non-existent personId → 422."""
        survey = create_survey(f"BadPerson {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        fake_person_id = str(uuid.uuid4())
        resp = submit_response(sid, {q["id"]: "answer"}, finished=True, person_id=fake_person_id)
        assert resp.status_code == 422, f"Invalid personId should be 422, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 8: Response Filtering
# ════════════════════════════════════════════════════════════════════


class TestResponseFiltering:
    """Filter responses by finished status."""

    def test_filter_finished_true(self):
        survey = create_survey(f"Filter {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        submit_response(sid, {q["id"]: "a"}, finished=True)
        submit_response(sid, {q["id"]: "b"}, finished=False)

        resp = api_get(f"/api/surveys/{sid}/responses", params={"finished": "true"})
        assert resp.status_code == 200
        responses = resp.json()
        assert all(r["finished"] is True for r in responses)
        assert len(responses) >= 1

    def test_filter_finished_false(self):
        survey = create_survey(f"FilterF {UNIQUE}")
        sid = survey["id"]
        q = create_question(sid, "Q", "openText")
        activate_survey(sid)

        submit_response(sid, {q["id"]: "a"}, finished=True)
        submit_response(sid, {q["id"]: "b"}, finished=False)

        resp = api_get(f"/api/surveys/{sid}/responses", params={"finished": "false"})
        assert resp.status_code == 200
        responses = resp.json()
        assert all(r["finished"] is False for r in responses)
        assert len(responses) >= 1


# ════════════════════════════════════════════════════════════════════
# PART 9: Authentication & Environment Isolation
# ════════════════════════════════════════════════════════════════════


class TestAuthMissingHeaders:
    """Requests with missing auth headers should return 401."""

    def test_missing_all_headers(self):
        resp = requests.get(f"{BASE_URL}/api/surveys", timeout=30)
        assert resp.status_code == 401, f"Expected 401 without headers, got {resp.status_code}"

    def test_missing_user_id(self):
        headers = {"X-Environment-Id": ENV_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/api/surveys", headers=headers, timeout=30)
        assert resp.status_code == 401, f"Expected 401 without X-User-Id, got {resp.status_code}"

    def test_missing_environment_id(self):
        headers = {"X-User-Id": USER_ID, "Content-Type": "application/json"}
        resp = requests.get(f"{BASE_URL}/api/surveys", headers=headers, timeout=30)
        assert resp.status_code == 401, f"Expected 401 without X-Environment-Id, got {resp.status_code}"


class TestEnvironmentIsolation:
    """Rule 12: Data from env A invisible to env B."""

    def test_survey_isolation(self):
        """Survey created in env A not visible in env B."""
        name = f"IsoSurvey {UNIQUE}"
        survey = create_survey(name)

        # Env B should not see it
        resp = api_get("/api/surveys", headers=HEADERS_ENV2)
        assert resp.status_code == 200
        surveys = resp.json()
        names = [s["name"] for s in surveys]
        assert name not in names, f"Env B should NOT see env A's survey '{name}'"

    def test_people_isolation(self):
        """Person created in env A not visible in env B."""
        person = create_person(email=f"iso-{UNIQUE}@example.com")

        resp = api_get("/api/people", headers=HEADERS_ENV2)
        assert resp.status_code == 200
        people = resp.json()
        emails = [p.get("email") for p in people]
        assert f"iso-{UNIQUE}@example.com" not in emails

    def test_cross_env_survey_404(self):
        """Accessing env A's survey with env B's headers → 404."""
        survey = create_survey(f"CrossEnv {UNIQUE}")
        resp = api_get(f"/api/surveys/{survey['id']}", headers=HEADERS_ENV2)
        assert resp.status_code == 404, f"Cross-env access should be 404, got {resp.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 10: 404 Handling
# ════════════════════════════════════════════════════════════════════


class TestNotFound:
    """Non-existent resources return 404."""

    def test_survey_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/surveys/{fake_id}")
        assert resp.status_code == 404

    def test_question_not_found(self):
        survey = create_survey(f"404Q {UNIQUE}")
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/surveys/{survey['id']}/questions/{fake_id}")
        assert resp.status_code == 404

    def test_response_not_found(self):
        survey = create_survey(f"404R {UNIQUE}")
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/surveys/{survey['id']}/responses/{fake_id}")
        assert resp.status_code == 404

    def test_person_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/people/{fake_id}")
        assert resp.status_code == 404

    def test_trigger_not_found(self):
        survey = create_survey(f"404T {UNIQUE}")
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/surveys/{survey['id']}/triggers/{fake_id}")
        assert resp.status_code == 404

    def test_tag_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/tags/{fake_id}")
        assert resp.status_code == 404

    def test_segment_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/segments/{fake_id}")
        assert resp.status_code == 404

    def test_webhook_not_found(self):
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/webhooks/{fake_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Tags CRUD
# ════════════════════════════════════════════════════════════════════


class TestTagCRUD:
    """Create → read → update → delete tags."""

    def test_tag_lifecycle(self):
        # Create
        resp = api_post("/api/tags", {"name": f"Tag-{UNIQUE}"})
        assert resp.status_code == 201
        tag = resp.json()
        tag_id = tag["id"]
        assert tag["name"] == f"Tag-{UNIQUE}"
        assert "createdAt" in tag

        # Read
        resp = api_get(f"/api/tags/{tag_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Tag-{UNIQUE}"

        # Update
        resp = api_put(f"/api/tags/{tag_id}", {"name": f"Updated-Tag-{UNIQUE}"})
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Updated-Tag-{UNIQUE}"

        # List
        resp = api_get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()
        assert any(t["id"] == tag_id for t in tags)

        # Delete
        resp = api_delete(f"/api/tags/{tag_id}")
        assert resp.status_code == 200

        # Verify 404
        resp = api_get(f"/api/tags/{tag_id}")
        assert resp.status_code == 404

    def test_tag_name_uniqueness(self):
        """Same name in same environment → 409."""
        name = f"UniqueTag-{UNIQUE}"
        resp1 = api_post("/api/tags", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/api/tags", {"name": name})
        assert resp2.status_code == 409, f"Duplicate tag should be 409, got {resp2.status_code}"

    def test_tag_name_uniqueness_across_envs(self):
        """Same name in different environments is OK."""
        name = f"CrossEnvTag-{UNIQUE}"
        resp1 = api_post("/api/tags", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/api/tags", {"name": name}, headers=HEADERS_ENV2)
        assert resp2.status_code == 201, f"Tag in different env should succeed, got {resp2.status_code}"


# ════════════════════════════════════════════════════════════════════
# PART 12: Survey Tags
# ════════════════════════════════════════════════════════════════════


class TestSurveyTags:
    """Add and remove tags from surveys."""

    def test_add_and_remove_tag(self):
        survey = create_survey(f"TaggedSurvey {UNIQUE}")
        tag_resp = api_post("/api/tags", {"name": f"SurveyTag-{UNIQUE}"})
        tag = tag_resp.json()

        # Add tag to survey
        resp = api_post(f"/api/surveys/{survey['id']}/tags", {"tagId": tag["id"]})
        assert resp.status_code == 201
        data = resp.json()
        assert data["surveyId"] == survey["id"]
        assert data["tagId"] == tag["id"]

        # Remove tag from survey
        resp = api_delete(f"/api/surveys/{survey['id']}/tags/{tag['id']}")
        assert resp.status_code == 200

    def test_add_duplicate_tag_to_survey(self):
        """Adding same tag twice → 409."""
        survey = create_survey(f"DupTagSurvey {UNIQUE}")
        tag_resp = api_post("/api/tags", {"name": f"DupSurveyTag-{UNIQUE}"})
        tag = tag_resp.json()

        resp1 = api_post(f"/api/surveys/{survey['id']}/tags", {"tagId": tag["id"]})
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/surveys/{survey['id']}/tags", {"tagId": tag["id"]})
        assert resp2.status_code == 409

    def test_add_nonexistent_tag_to_survey(self):
        """Adding non-existent tag → 404."""
        survey = create_survey(f"NoTagSurvey {UNIQUE}")
        fake_id = str(uuid.uuid4())
        resp = api_post(f"/api/surveys/{survey['id']}/tags", {"tagId": fake_id})
        assert resp.status_code == 404

    def test_remove_nonexistent_association(self):
        """Removing a tag that's not on the survey → 404."""
        survey = create_survey(f"NoAssocSurvey {UNIQUE}")
        tag_resp = api_post("/api/tags", {"name": f"NoAssocTag-{UNIQUE}"})
        tag = tag_resp.json()

        resp = api_delete(f"/api/surveys/{survey['id']}/tags/{tag['id']}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 13: Segments CRUD + Filtering
# ════════════════════════════════════════════════════════════════════


class TestSegmentCRUD:
    """Create → read → update → delete segments."""

    def test_segment_lifecycle(self):
        filters = [{"attribute": "plan", "operator": "equals", "value": "pro"}]
        resp = api_post("/api/segments", {"name": f"ProUsers-{UNIQUE}", "filters": filters})
        assert resp.status_code == 201
        segment = resp.json()
        seg_id = segment["id"]
        assert segment["name"] == f"ProUsers-{UNIQUE}"
        assert segment["filters"] == filters

        # Read
        resp = api_get(f"/api/segments/{seg_id}")
        assert resp.status_code == 200
        assert resp.json()["filters"] == filters

        # Update
        new_filters = [{"attribute": "plan", "operator": "equals", "value": "enterprise"}]
        resp = api_put(f"/api/segments/{seg_id}", {"name": f"EntUsers-{UNIQUE}", "filters": new_filters})
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == f"EntUsers-{UNIQUE}"
        assert updated["filters"] == new_filters

        # List
        resp = api_get("/api/segments")
        assert resp.status_code == 200
        segments = resp.json()
        assert any(s["id"] == seg_id for s in segments)

        # Delete
        resp = api_delete(f"/api/segments/{seg_id}")
        assert resp.status_code == 200

        resp = api_get(f"/api/segments/{seg_id}")
        assert resp.status_code == 404


class TestSegmentPeopleFiltering:
    """Segment people matching."""

    def test_equals_filter(self):
        """Segment with equals filter returns matching people."""
        # Create people with different plans
        p1 = create_person(email=f"seg-pro-{UNIQUE}@test.com", attributes={"plan": "pro"})
        p2 = create_person(email=f"seg-free-{UNIQUE}@test.com", attributes={"plan": "free"})
        p3 = create_person(email=f"seg-pro2-{UNIQUE}@test.com", attributes={"plan": "pro"})

        # Create segment for pro users
        filters = [{"attribute": "plan", "operator": "equals", "value": "pro"}]
        resp = api_post("/api/segments", {"name": f"ProSeg-{UNIQUE}", "filters": filters})
        seg_id = resp.json()["id"]

        # Get matching people
        resp = api_get(f"/api/segments/{seg_id}/people")
        assert resp.status_code == 200
        people = resp.json()
        people_ids = [p["id"] for p in people]
        assert p1["id"] in people_ids
        assert p3["id"] in people_ids
        assert p2["id"] not in people_ids

    def test_contains_filter(self):
        """Segment with contains filter returns matching people."""
        p1 = create_person(email=f"seg-cont-{UNIQUE}@acme.com", attributes={"company": "Acme Corp"})
        p2 = create_person(email=f"seg-cont-{UNIQUE}@beta.com", attributes={"company": "Beta Inc"})

        filters = [{"attribute": "company", "operator": "contains", "value": "Acme"}]
        resp = api_post("/api/segments", {"name": f"AcmeSeg-{UNIQUE}", "filters": filters})
        seg_id = resp.json()["id"]

        resp = api_get(f"/api/segments/{seg_id}/people")
        assert resp.status_code == 200
        people = resp.json()
        people_ids = [p["id"] for p in people]
        assert p1["id"] in people_ids
        assert p2["id"] not in people_ids

    def test_multiple_filters_anded(self):
        """Multiple filters are ANDed together."""
        p1 = create_person(email=f"seg-and1-{UNIQUE}@test.com",
                           attributes={"plan": "pro", "country": "US"})
        p2 = create_person(email=f"seg-and2-{UNIQUE}@test.com",
                           attributes={"plan": "pro", "country": "UK"})
        p3 = create_person(email=f"seg-and3-{UNIQUE}@test.com",
                           attributes={"plan": "free", "country": "US"})

        filters = [
            {"attribute": "plan", "operator": "equals", "value": "pro"},
            {"attribute": "country", "operator": "equals", "value": "US"},
        ]
        resp = api_post("/api/segments", {"name": f"AndSeg-{UNIQUE}", "filters": filters})
        seg_id = resp.json()["id"]

        resp = api_get(f"/api/segments/{seg_id}/people")
        assert resp.status_code == 200
        people = resp.json()
        people_ids = [p["id"] for p in people]
        assert p1["id"] in people_ids
        assert p2["id"] not in people_ids
        assert p3["id"] not in people_ids

    def test_notEquals_filter(self):
        """notEquals filter excludes matching people."""
        p1 = create_person(email=f"seg-ne1-{UNIQUE}@test.com", attributes={"plan": "pro"})
        p2 = create_person(email=f"seg-ne2-{UNIQUE}@test.com", attributes={"plan": "free"})

        filters = [{"attribute": "plan", "operator": "notEquals", "value": "free"}]
        resp = api_post("/api/segments", {"name": f"NotFreeSeg-{UNIQUE}", "filters": filters})
        seg_id = resp.json()["id"]

        resp = api_get(f"/api/segments/{seg_id}/people")
        assert resp.status_code == 200
        people = resp.json()
        people_ids = [p["id"] for p in people]
        assert p1["id"] in people_ids
        assert p2["id"] not in people_ids

    def test_notContains_filter(self):
        """notContains filter excludes matching people."""
        p1 = create_person(email=f"seg-nc1-{UNIQUE}@test.com", attributes={"company": "Acme Corp"})
        p2 = create_person(email=f"seg-nc2-{UNIQUE}@test.com", attributes={"company": "Beta Inc"})

        filters = [{"attribute": "company", "operator": "notContains", "value": "Acme"}]
        resp = api_post("/api/segments", {"name": f"NotAcmeSeg-{UNIQUE}", "filters": filters})
        seg_id = resp.json()["id"]

        resp = api_get(f"/api/segments/{seg_id}/people")
        assert resp.status_code == 200
        people = resp.json()
        people_ids = [p["id"] for p in people]
        assert p1["id"] not in people_ids
        assert p2["id"] in people_ids

    def test_segment_people_nonexistent_segment(self):
        """GET /api/segments/{fake}/people → 404."""
        fake_id = str(uuid.uuid4())
        resp = api_get(f"/api/segments/{fake_id}/people")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Webhooks CRUD
# ════════════════════════════════════════════════════════════════════


class TestWebhookCRUD:
    """Create → read → delete webhooks."""

    def test_webhook_lifecycle(self):
        # Create
        resp = api_post("/api/webhooks", {
            "url": "https://example.com/hook",
            "triggers": ["responseCreated", "surveyCompleted"],
        })
        assert resp.status_code == 201
        webhook = resp.json()
        wh_id = webhook["id"]
        assert webhook["url"] == "https://example.com/hook"
        assert "responseCreated" in webhook["triggers"]
        assert "surveyCompleted" in webhook["triggers"]
        assert "createdAt" in webhook

        # Read
        resp = api_get(f"/api/webhooks/{wh_id}")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://example.com/hook"

        # List
        resp = api_get("/api/webhooks")
        assert resp.status_code == 200
        webhooks = resp.json()
        assert any(w["id"] == wh_id for w in webhooks)

        # Delete
        resp = api_delete(f"/api/webhooks/{wh_id}")
        assert resp.status_code == 200

        # Verify 404
        resp = api_get(f"/api/webhooks/{wh_id}")
        assert resp.status_code == 404

    def test_webhook_with_all_triggers(self):
        """Webhook with all valid trigger types."""
        resp = api_post("/api/webhooks", {
            "url": "https://example.com/all-triggers",
            "triggers": ["responseCreated", "responseFinished", "surveyActivated", "surveyCompleted"],
        })
        assert resp.status_code == 201
        webhook = resp.json()
        assert len(webhook["triggers"]) == 4
