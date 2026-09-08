"""
Langfuse — L2 Integration Tests (Adversarial)

Targets LLM bug patterns:
- Pattern 1: camelCase field names (traceId, projectId, totalCost, sessionId, etc.)
- Pattern 2: Nested/computed data (usage object, trace stats)
- Pattern 3: Filtering actually implemented
- Pattern 4: Exact status codes (201 create, 204 delete, 404 not found, 409 conflict)
- Pattern 5: Computed values (totalCost, totalTokens, duration)
- Pattern 6: Project data isolation
- Pattern 7: Cascade deletes

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

PROJECT_KEY = f"test-project-{uuid.uuid4().hex[:8]}"
PROJECT2_KEY = f"test-project2-{uuid.uuid4().hex[:8]}"

HEADERS = {
    "X-Api-Key": PROJECT_KEY,
    "Content-Type": "application/json",
}

HEADERS_P2 = {
    "X-Api-Key": PROJECT2_KEY,
    "Content-Type": "application/json",
}


def _reset_test_context():
    """Give every test two fresh projects so group order cannot affect results."""
    global PROJECT_KEY, PROJECT2_KEY, HEADERS, HEADERS_P2

    PROJECT_KEY = f"test-project-{uuid.uuid4().hex[:8]}"
    PROJECT2_KEY = f"test-project2-{uuid.uuid4().hex[:8]}"
    HEADERS = {
        "X-Api-Key": PROJECT_KEY,
        "Content-Type": "application/json",
    }
    HEADERS_P2 = {
        "X-Api-Key": PROJECT2_KEY,
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


def unique():
    return uuid.uuid4().hex[:8]


def api_get(path, params=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_patch(path, json_data=None, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.patch(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, headers=None):
    request_headers = HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", headers=request_headers, timeout=30)


class TestHealthEndpoint:
    """Health endpoint requires no auth."""

    def test_health_no_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "status" in body
        assert body["status"] == "ok"


class TestTraceFieldIntegrity:
    """Pattern 1+4: Trace creation with correct fields and status codes."""

    def test_create_trace_201_with_all_fields(self):
        uid = unique()
        r = api_post("/api/traces", {
            "name": f"trace-{uid}",
            "input": {"query": "hello"},
            "output": {"response": "world"},
            "metadata": {"env": "test"},
            "userId": f"user-{uid}",
            "sessionId": f"sess-{uid}",
            "tags": ["test", "integration"],
            "startTime": "2024-01-15T10:00:00Z"
        })
        assert r.status_code == 201
        trace = r.json()
        assert "id" in trace
        assert trace["name"] == f"trace-{uid}"
        assert trace["input"] == {"query": "hello"}
        assert trace["output"] == {"response": "world"}
        assert trace["metadata"] == {"env": "test"}
        assert trace["userId"] == f"user-{uid}"
        assert trace["sessionId"] == f"sess-{uid}"
        assert trace["tags"] == ["test", "integration"]
        assert "projectId" in trace
        assert "createdAt" in trace
        assert "updatedAt" in trace
        assert "startTime" in trace

    def test_client_provided_id(self):
        custom_id = str(uuid.uuid4())
        r = api_post("/api/traces", {"id": custom_id, "name": "custom-id-trace"})
        assert r.status_code == 201
        assert r.json()["id"] == custom_id

    def test_duplicate_id_returns_409(self):
        trace_id = str(uuid.uuid4())
        api_post("/api/traces", {"id": trace_id, "name": "first"})
        r = api_post("/api/traces", {"id": trace_id, "name": "second"})
        assert r.status_code == 409

    def test_get_nonexistent_trace_404(self):
        r = api_get(f"/api/traces/{uuid.uuid4()}")
        assert r.status_code == 404


class TestTraceComputedStats:
    """Pattern 5: totalCost, totalTokens, duration computed from generations."""

    def test_total_cost_and_tokens_computed(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"stats-{uid}"}).json()

        # Create generations with cost and usage
        api_post("/api/generations", {
            "traceId": trace["id"], "name": "gen1",
            "model": "gpt-4", "cost": 0.05,
            "usage": {"promptTokens": 100, "completionTokens": 50, "totalTokens": 150}
        })
        api_post("/api/generations", {
            "traceId": trace["id"], "name": "gen2",
            "model": "gpt-4", "cost": 0.03,
            "usage": {"promptTokens": 80, "completionTokens": 40, "totalTokens": 120}
        })

        # Get trace — should have computed stats
        detail = api_get(f"/api/traces/{trace['id']}").json()
        assert detail["totalCost"] == pytest.approx(0.08)
        assert detail["totalTokens"] == 270

    def test_duration_computed_from_times(self):
        uid = unique()
        trace = api_post("/api/traces", {
            "name": f"dur-{uid}",
            "startTime": "2024-01-15T10:00:00Z",
            "endTime": "2024-01-15T10:00:02.500Z"
        }).json()

        detail = api_get(f"/api/traces/{trace['id']}").json()
        assert detail["duration"] == pytest.approx(2500, abs=100)

    def test_duration_from_generation_end_time(self):
        uid = unique()
        trace = api_post("/api/traces", {
            "name": f"dur-gen-{uid}",
            "startTime": "2024-01-15T10:00:00Z"
        }).json()

        # Generation ends 3 seconds later
        api_post("/api/generations", {
            "traceId": trace["id"], "name": "gen",
            "startTime": "2024-01-15T10:00:00Z",
            "endTime": "2024-01-15T10:00:03Z"
        })

        detail = api_get(f"/api/traces/{trace['id']}").json()
        assert detail["duration"] == pytest.approx(3000, abs=100)


class TestSpanFields:
    """Pattern 1+2: Span creation and tree structure."""

    def test_span_create_with_parent(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"span-trace-{uid}"}).json()

        # Root span
        root = api_post("/api/spans", {
            "traceId": trace["id"], "name": "root-span",
            "level": "DEFAULT", "startTime": "2024-02-01T10:00:00Z"
        }).json()
        assert root["traceId"] == trace["id"]
        assert root["parentSpanId"] is None
        assert root["level"] == "DEFAULT"
        assert "id" in root
        assert "createdAt" in root

        # Child span
        child = api_post("/api/spans", {
            "traceId": trace["id"], "name": "child-span",
            "parentSpanId": root["id"], "level": "DEBUG"
        }).json()
        assert child["parentSpanId"] == root["id"]
        assert child["level"] == "DEBUG"

    def test_span_filter_by_trace_id(self):
        uid = unique()
        t1 = api_post("/api/traces", {"name": f"sf-t1-{uid}"}).json()
        t2 = api_post("/api/traces", {"name": f"sf-t2-{uid}"}).json()

        api_post("/api/spans", {"traceId": t1["id"], "name": "span-t1"})
        api_post("/api/spans", {"traceId": t1["id"], "name": "span-t1-2"})
        api_post("/api/spans", {"traceId": t2["id"], "name": "span-t2"})

        r = api_get("/api/spans", params={"traceId": t1["id"]})
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        for s in data:
            assert s["traceId"] == t1["id"]


class TestGenerationUsage:
    """Pattern 1+5: Generation usage object with computed totalTokens."""

    def test_usage_auto_computes_total_tokens(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"usage-{uid}"}).json()

        gen = api_post("/api/generations", {
            "traceId": trace["id"], "name": "gen",
            "model": "gpt-4",
            "usage": {"promptTokens": 200, "completionTokens": 100}
        }).json()

        assert gen["usage"]["promptTokens"] == 200
        assert gen["usage"]["completionTokens"] == 100
        assert gen["usage"]["totalTokens"] == 300

    def test_generation_all_fields(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"gen-fields-{uid}"}).json()

        gen = api_post("/api/generations", {
            "traceId": trace["id"],
            "name": f"gen-{uid}",
            "model": "claude-3",
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "output": {"text": "hello"},
            "cost": 0.02,
            "level": "WARNING",
            "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}
        }).json()

        assert gen["model"] == "claude-3"
        assert gen["input"] == {"messages": [{"role": "user", "content": "hi"}]}
        assert gen["output"] == {"text": "hello"}
        assert gen["cost"] == pytest.approx(0.02)
        assert gen["level"] == "WARNING"
        assert gen["usage"]["totalTokens"] == 15
        assert "id" in gen
        assert "createdAt" in gen


class TestScoreValidation:
    """Pattern 4+8: Score requires valid traceId."""

    def test_score_invalid_trace_returns_404(self):
        r = api_post("/api/scores", {
            "traceId": str(uuid.uuid4()),
            "name": "accuracy",
            "value": 0.9
        })
        assert r.status_code == 404

    def test_score_create_and_fields(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"score-trace-{uid}"}).json()

        r = api_post("/api/scores", {
            "traceId": trace["id"],
            "name": "accuracy",
            "value": 0.95,
            "comment": "good result",
            "source": "human"
        })
        assert r.status_code == 201
        score = r.json()
        assert score["traceId"] == trace["id"]
        assert score["name"] == "accuracy"
        assert score["value"] == pytest.approx(0.95)
        assert score["comment"] == "good result"
        assert score["source"] == "human"
        assert "id" in score
        assert "createdAt" in score


class TestTraceFiltering:
    """Pattern 3: Trace filtering by userId, sessionId, tags."""

    def test_filter_by_user_id(self):
        uid = unique()
        api_post("/api/traces", {"name": f"fu-1-{uid}", "userId": f"user-{uid}"})
        api_post("/api/traces", {"name": f"fu-2-{uid}", "userId": f"user-{uid}"})
        api_post("/api/traces", {"name": f"fu-3-{uid}", "userId": "other-user"})

        r = api_get("/api/traces", params={"userId": f"user-{uid}"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        for t in data["data"]:
            assert t["userId"] == f"user-{uid}"

    def test_filter_by_session_id(self):
        uid = unique()
        sess = f"session-{uid}"
        api_post("/api/traces", {"name": f"fs-1-{uid}", "sessionId": sess})
        api_post("/api/traces", {"name": f"fs-2-{uid}", "sessionId": "other"})

        r = api_get("/api/traces", params={"sessionId": sess})
        data = r.json()
        assert data["total"] == 1
        assert data["data"][0]["sessionId"] == sess

    def test_filter_by_tags(self):
        uid = unique()
        api_post("/api/traces", {"name": f"ft-1-{uid}", "tags": ["prod", "important"]})
        api_post("/api/traces", {"name": f"ft-2-{uid}", "tags": ["prod"]})
        api_post("/api/traces", {"name": f"ft-3-{uid}", "tags": ["dev"]})

        r = api_get("/api/traces", params={"tags": "prod,important"})
        data = r.json()
        # Should only find the one with BOTH tags
        assert data["total"] >= 1
        for t in data["data"]:
            assert "prod" in t["tags"]
            assert "important" in t["tags"]

    def test_pagination(self):
        uid = unique()
        for i in range(5):
            api_post("/api/traces", {"name": f"pg-{uid}-{i}", "userId": f"paguser-{uid}"})

        r1 = api_get("/api/traces", params={"userId": f"paguser-{uid}", "limit": 2, "offset": 0})
        d1 = r1.json()
        assert len(d1["data"]) == 2
        assert d1["total"] == 5
        assert d1["limit"] == 2
        assert d1["offset"] == 0

        r2 = api_get("/api/traces", params={"userId": f"paguser-{uid}", "limit": 2, "offset": 2})
        d2 = r2.json()
        assert len(d2["data"]) == 2
        ids1 = {t["id"] for t in d1["data"]}
        ids2 = {t["id"] for t in d2["data"]}
        assert ids1.isdisjoint(ids2)


class TestCascadeDeleteTrace:
    """Pattern 7: Deleting trace removes spans, generations, scores."""

    def test_delete_trace_cascades(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"casc-{uid}"}).json()
        span = api_post("/api/spans", {"traceId": trace["id"], "name": "s"}).json()
        gen = api_post("/api/generations", {"traceId": trace["id"], "name": "g"}).json()
        score = api_post("/api/scores", {"traceId": trace["id"], "name": "sc", "value": 1.0}).json()

        r = api_delete(f"/api/traces/{trace['id']}")
        assert r.status_code == 204

        assert api_get(f"/api/traces/{trace['id']}").status_code == 404
        assert api_get(f"/api/spans/{span['id']}").status_code == 404
        assert api_get(f"/api/generations/{gen['id']}").status_code == 404
        assert api_get(f"/api/scores/{score['id']}").status_code == 404


class TestPromptVersioning:
    """Pattern 5+8: Prompt versioning and label management."""

    def test_prompt_version_auto_increments(self):
        uid = unique()
        name = f"prompt-{uid}"

        p1 = api_post("/api/prompts", {"name": name, "prompt": "v1 template"}).json()
        assert p1["version"] == 1
        assert p1["name"] == name

        p2 = api_post("/api/prompts", {"name": name, "prompt": "v2 template"}).json()
        assert p2["version"] == 2

        p3 = api_post("/api/prompts", {"name": name, "prompt": "v3 template"}).json()
        assert p3["version"] == 3

    def test_production_label_activates_version(self):
        uid = unique()
        name = f"prod-prompt-{uid}"

        api_post("/api/prompts", {"name": name, "prompt": "v1"})
        api_post("/api/prompts", {"name": name, "prompt": "v2", "labels": ["production"]})
        api_post("/api/prompts", {"name": name, "prompt": "v3"})

        # Default GET returns production-labeled version
        r = api_get(f"/api/prompts/{name}")
        assert r.status_code == 200
        assert r.json()["prompt"] == "v2"
        assert r.json()["version"] == 2


class TestProjectIsolation:
    """Pattern 6: Different API keys see different data."""

    def test_traces_isolated_by_project(self):
        uid = unique()
        trace = api_post("/api/traces", {"name": f"iso-{uid}"}).json()

        # Project 2 cannot see it
        r = api_get(f"/api/traces/{trace['id']}", headers=HEADERS_P2)
        assert r.status_code == 404

    def test_datasets_isolated(self):
        uid = unique()
        ds = api_post("/api/datasets", {"name": f"iso-ds-{uid}"}).json()

        r = api_get(f"/api/datasets/{ds['name']}", headers=HEADERS_P2)
        assert r.status_code == 404


class TestDatasetCRUD:
    """Pattern 1+4: Dataset creation and field verification."""

    def test_create_dataset_fields(self):
        uid = unique()
        r = api_post("/api/datasets", {"name": f"ds-{uid}", "description": "test dataset"})
        assert r.status_code == 201
        ds = r.json()
        assert ds["name"] == f"ds-{uid}"
        assert ds["description"] == "test dataset"
        assert "id" in ds
        assert "projectId" in ds
        assert "createdAt" in ds
        assert "updatedAt" in ds

    def test_delete_dataset_cascades(self):
        uid = unique()
        ds = api_post("/api/datasets", {"name": f"casc-ds-{uid}"}).json()
        item = api_post("/api/dataset-items", {
            "datasetName": ds["name"],
            "input": {"q": "test"},
            "expectedOutput": {"a": "answer"}
        }).json()

        r = api_delete(f"/api/datasets/{ds['name']}")
        assert r.status_code == 204

        assert api_get(f"/api/datasets/{ds['name']}").status_code == 404
        assert api_get(f"/api/dataset-items/{item['id']}").status_code == 404


class TestAuthRequired:
    """Pattern 4: Auth required on all endpoints except health."""

    def test_traces_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/traces", timeout=30)
        assert r.status_code == 401

    def test_generations_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/generations", timeout=30)
        assert r.status_code == 401

    def test_scores_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/scores", timeout=30)
        assert r.status_code == 401

    def test_datasets_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/datasets", timeout=30)
        assert r.status_code == 401
