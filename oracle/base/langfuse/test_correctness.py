"""
BackendForge — Comprehensive Correctness Tests for Langfuse Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# Project keys — the key IS the project identifier (auto-created on first request)
PROJECT_KEY = f"test-project-{uuid.uuid4().hex[:8]}"
PROJECT2_KEY = f"other-project-{uuid.uuid4().hex[:8]}"

HEADERS = {
    "X-Api-Key": PROJECT_KEY,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-Api-Key": PROJECT2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


def _reset_test_context():
    """Give every test fresh project namespaces and resource names."""
    global PROJECT_KEY, PROJECT2_KEY, HEADERS, HEADERS2, UNIQUE

    PROJECT_KEY = f"test-project-{uuid.uuid4().hex[:8]}"
    PROJECT2_KEY = f"other-project-{uuid.uuid4().hex[:8]}"
    HEADERS = {
        "X-Api-Key": PROJECT_KEY,
        "Content-Type": "application/json",
    }
    HEADERS2 = {
        "X-Api-Key": PROJECT2_KEY,
        "Content-Type": "application/json",
    }
    UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _isolate_test_data():
    _reset_test_context()


# ── HTTP Helpers ──

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


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/traces", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_spans(self):
        resp = requests.get(f"{BASE_URL}/api/spans", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_generations(self):
        resp = requests.get(f"{BASE_URL}/api/generations", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_scores(self):
        resp = requests.get(f"{BASE_URL}/api/scores", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_datasets(self):
        resp = requests.get(f"{BASE_URL}/api/datasets", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_prompts(self):
        resp = requests.get(f"{BASE_URL}/api/prompts", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_sessions(self):
        resp = requests.get(f"{BASE_URL}/api/sessions", timeout=30)
        assert resp.status_code == 401

    def test_auto_create_project(self):
        """A new API key should auto-create a project."""
        new_key = f"new-project-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": new_key, "Content-Type": "application/json"}
        resp = api_get("/api/traces", headers=headers)
        assert resp.status_code == 200
        # Should return empty list for new project
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)


# ════════════════════════════════════════════════════════════════════
# PART 3: Trace CRUD
# ════════════════════════════════════════════════════════════════════


class TestTraceCRUD:

    def test_create_trace(self):
        resp = api_post("/api/traces", {
            "name": f"test-trace-{UNIQUE}",
            "input": {"query": "hello"},
            "output": {"response": "world"},
            "metadata": {"env": "test"},
            "userId": "user-1",
            "sessionId": f"session-{UNIQUE}",
            "tags": ["test", "demo"],
        })
        assert resp.status_code == 201
        trace = resp.json()
        assert trace["name"] == f"test-trace-{UNIQUE}"
        assert trace["input"] == {"query": "hello"}
        assert trace["output"] == {"response": "world"}
        assert trace["metadata"] == {"env": "test"}
        assert trace["userId"] == "user-1"
        assert trace["sessionId"] == f"session-{UNIQUE}"
        assert trace["tags"] == ["test", "demo"]
        assert "id" in trace
        assert "createdAt" in trace
        assert "updatedAt" in trace
        assert "startTime" in trace

    def test_create_trace_minimal(self):
        resp = api_post("/api/traces", {"name": f"minimal-{UNIQUE}"})
        assert resp.status_code == 201
        trace = resp.json()
        assert trace["name"] == f"minimal-{UNIQUE}"
        assert trace["tags"] == []
        assert trace["input"] is None
        assert trace["output"] is None

    def test_create_trace_with_client_id(self):
        """Client can provide their own ID."""
        custom_id = str(uuid.uuid4())
        resp = api_post("/api/traces", {
            "id": custom_id,
            "name": f"custom-id-{UNIQUE}",
        })
        assert resp.status_code == 201
        trace = resp.json()
        assert trace["id"] == custom_id

    def test_create_trace_duplicate_id_returns_409(self):
        """Duplicate client-provided ID should return 409."""
        custom_id = str(uuid.uuid4())
        resp1 = api_post("/api/traces", {"id": custom_id, "name": "first"})
        assert resp1.status_code == 201
        resp2 = api_post("/api/traces", {"id": custom_id, "name": "second"})
        assert resp2.status_code == 409

    def test_list_traces(self):
        # Create a trace to ensure non-empty
        api_post("/api/traces", {"name": f"list-trace-{UNIQUE}"})

        resp = api_get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["data"], list)
        assert data["total"] >= 1

    def test_list_traces_pagination(self):
        """Test limit and offset work."""
        # Create several traces
        for i in range(3):
            api_post("/api/traces", {"name": f"pag-trace-{UNIQUE}-{i}"})

        resp = api_get("/api/traces", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_list_traces_filter_by_userId(self):
        user_id = f"filter-user-{UNIQUE}"
        api_post("/api/traces", {"name": "with-user", "userId": user_id})
        api_post("/api/traces", {"name": "without-user", "userId": "other"})

        resp = api_get("/api/traces", params={"userId": user_id})
        assert resp.status_code == 200
        data = resp.json()
        for trace in data["data"]:
            assert trace["userId"] == user_id

    def test_list_traces_filter_by_sessionId(self):
        session_id = f"filter-session-{UNIQUE}"
        api_post("/api/traces", {"name": "with-session", "sessionId": session_id})

        resp = api_get("/api/traces", params={"sessionId": session_id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1
        for trace in data["data"]:
            assert trace["sessionId"] == session_id

    def test_list_traces_filter_by_tags(self):
        tag = f"special-tag-{UNIQUE}"
        api_post("/api/traces", {"name": "tagged-trace", "tags": [tag, "other"]})
        api_post("/api/traces", {"name": "untagged-trace", "tags": ["other"]})

        resp = api_get("/api/traces", params={"tags": tag})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1
        for trace in data["data"]:
            assert tag in trace["tags"]

    def test_get_trace(self):
        create_resp = api_post("/api/traces", {"name": f"get-trace-{UNIQUE}"})
        trace_id = create_resp.json()["id"]

        resp = api_get(f"/api/traces/{trace_id}")
        assert resp.status_code == 200
        trace = resp.json()
        assert trace["id"] == trace_id
        assert trace["name"] == f"get-trace-{UNIQUE}"
        assert "totalCost" in trace
        assert "totalTokens" in trace
        assert "duration" in trace

    def test_get_trace_not_found(self):
        resp = api_get(f"/api/traces/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_trace(self):
        create_resp = api_post("/api/traces", {"name": "to-update"})
        trace_id = create_resp.json()["id"]

        resp = api_patch(f"/api/traces/{trace_id}", {
            "name": "updated-name",
            "output": {"result": "done"},
            "tags": ["updated"],
        })
        assert resp.status_code == 200
        trace = resp.json()
        assert trace["name"] == "updated-name"
        assert trace["output"] == {"result": "done"}
        assert trace["tags"] == ["updated"]

    def test_update_trace_not_found(self):
        resp = api_patch(f"/api/traces/{uuid.uuid4()}", {"name": "ghost"})
        assert resp.status_code == 404

    def test_delete_trace(self):
        create_resp = api_post("/api/traces", {"name": "to-delete"})
        trace_id = create_resp.json()["id"]

        resp = api_delete(f"/api/traces/{trace_id}")
        assert resp.status_code == 204

        # Verify it's gone
        get_resp = api_get(f"/api/traces/{trace_id}")
        assert get_resp.status_code == 404

    def test_delete_trace_not_found(self):
        resp = api_delete(f"/api/traces/{uuid.uuid4()}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Span CRUD
# ════════════════════════════════════════════════════════════════════


class TestSpanCRUD:

    def test_create_span(self):
        # Create a trace first
        trace_resp = api_post("/api/traces", {"name": "span-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/spans", {
            "traceId": trace_id,
            "name": f"test-span-{UNIQUE}",
            "input": {"prompt": "hi"},
            "output": {"result": "hello"},
            "level": "DEFAULT",
            "startTime": "2024-01-01T00:00:00.000Z",
            "endTime": "2024-01-01T00:00:01.000Z",
        })
        assert resp.status_code == 201
        span = resp.json()
        assert span["traceId"] == trace_id
        assert span["name"] == f"test-span-{UNIQUE}"
        assert span["level"] == "DEFAULT"
        assert "id" in span
        assert "createdAt" in span

    def test_create_span_with_parent(self):
        trace_resp = api_post("/api/traces", {"name": "tree-trace"})
        trace_id = trace_resp.json()["id"]

        # Root span
        root_resp = api_post("/api/spans", {
            "traceId": trace_id,
            "name": "root-span",
        })
        root_id = root_resp.json()["id"]

        # Child span
        child_resp = api_post("/api/spans", {
            "traceId": trace_id,
            "name": "child-span",
            "parentSpanId": root_id,
        })
        assert child_resp.status_code == 201
        child = child_resp.json()
        assert child["parentSpanId"] == root_id

    def test_create_span_invalid_trace_returns_404(self):
        resp = api_post("/api/spans", {
            "traceId": str(uuid.uuid4()),
            "name": "orphan-span",
        })
        assert resp.status_code == 404

    def test_create_span_duplicate_id_returns_409(self):
        trace_resp = api_post("/api/traces", {"name": "dup-span-trace"})
        trace_id = trace_resp.json()["id"]
        custom_id = str(uuid.uuid4())

        resp1 = api_post("/api/spans", {"id": custom_id, "traceId": trace_id, "name": "first"})
        assert resp1.status_code == 201
        resp2 = api_post("/api/spans", {"id": custom_id, "traceId": trace_id, "name": "second"})
        assert resp2.status_code == 409

    def test_list_spans(self):
        trace_resp = api_post("/api/traces", {"name": "list-spans-trace"})
        trace_id = trace_resp.json()["id"]
        api_post("/api/spans", {"traceId": trace_id, "name": "span-a"})
        api_post("/api/spans", {"traceId": trace_id, "name": "span-b"})

        resp = api_get("/api/spans", params={"traceId": trace_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert len(data["data"]) >= 2

    def test_list_spans_filter_by_traceId(self):
        trace1 = api_post("/api/traces", {"name": "trace-for-span-filter-1"}).json()["id"]
        trace2 = api_post("/api/traces", {"name": "trace-for-span-filter-2"}).json()["id"]
        api_post("/api/spans", {"traceId": trace1, "name": "span-in-1"})
        api_post("/api/spans", {"traceId": trace2, "name": "span-in-2"})

        resp = api_get("/api/spans", params={"traceId": trace1})
        data = resp.json()
        for span in data["data"]:
            assert span["traceId"] == trace1

    def test_get_span(self):
        trace_resp = api_post("/api/traces", {"name": "get-span-trace"})
        trace_id = trace_resp.json()["id"]
        span_resp = api_post("/api/spans", {"traceId": trace_id, "name": "get-me"})
        span_id = span_resp.json()["id"]

        resp = api_get(f"/api/spans/{span_id}")
        assert resp.status_code == 200
        span = resp.json()
        assert span["id"] == span_id
        assert span["name"] == "get-me"

    def test_get_span_not_found(self):
        resp = api_get(f"/api/spans/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_span(self):
        trace_resp = api_post("/api/traces", {"name": "update-span-trace"})
        trace_id = trace_resp.json()["id"]
        span_resp = api_post("/api/spans", {"traceId": trace_id, "name": "orig-span"})
        span_id = span_resp.json()["id"]

        resp = api_patch(f"/api/spans/{span_id}", {
            "name": "updated-span",
            "level": "WARNING",
            "endTime": "2024-01-01T01:00:00.000Z",
            "output": {"final": "result"},
        })
        assert resp.status_code == 200
        span = resp.json()
        assert span["name"] == "updated-span"
        assert span["level"] == "WARNING"
        assert span["endTime"] is not None and span["endTime"].startswith("2024-01-01T01:00:00")
        assert span["output"] == {"final": "result"}

    def test_update_span_not_found(self):
        resp = api_patch(f"/api/spans/{uuid.uuid4()}", {"name": "ghost"})
        assert resp.status_code == 404

    def test_span_level_enum(self):
        """Span level should be one of DEBUG, DEFAULT, WARNING, ERROR."""
        trace_resp = api_post("/api/traces", {"name": "level-trace"})
        trace_id = trace_resp.json()["id"]

        for level in ["DEBUG", "DEFAULT", "WARNING", "ERROR"]:
            resp = api_post("/api/spans", {
                "traceId": trace_id,
                "name": f"span-{level}",
                "level": level,
            })
            assert resp.status_code == 201
            assert resp.json()["level"] == level


# ════════════════════════════════════════════════════════════════════
# PART 5: Generation CRUD
# ════════════════════════════════════════════════════════════════════


class TestGenerationCRUD:

    def test_create_generation(self):
        trace_resp = api_post("/api/traces", {"name": "gen-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/generations", {
            "traceId": trace_id,
            "name": f"test-gen-{UNIQUE}",
            "model": "gpt-4",
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "output": {"content": "hello"},
            "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
            "cost": 0.001,
            "startTime": "2024-01-01T00:00:00.000Z",
            "endTime": "2024-01-01T00:00:01.000Z",
        })
        assert resp.status_code == 201
        gen = resp.json()
        assert gen["traceId"] == trace_id
        assert gen["name"] == f"test-gen-{UNIQUE}"
        assert gen["model"] == "gpt-4"
        assert gen["usage"]["promptTokens"] == 10
        assert gen["usage"]["completionTokens"] == 5
        assert gen["usage"]["totalTokens"] == 15
        assert gen["cost"] == 0.001
        assert "id" in gen
        assert "createdAt" in gen

    def test_create_generation_auto_compute_total_tokens(self):
        """totalTokens should be auto-computed if not provided."""
        trace_resp = api_post("/api/traces", {"name": "auto-token-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/generations", {
            "traceId": trace_id,
            "name": "auto-tokens",
            "usage": {"promptTokens": 100, "completionTokens": 50},
        })
        assert resp.status_code == 201
        gen = resp.json()
        assert gen["usage"]["totalTokens"] == 150

    def test_create_generation_invalid_trace_returns_404(self):
        resp = api_post("/api/generations", {
            "traceId": str(uuid.uuid4()),
            "name": "orphan-gen",
        })
        assert resp.status_code == 404

    def test_create_generation_duplicate_id_returns_409(self):
        trace_resp = api_post("/api/traces", {"name": "dup-gen-trace"})
        trace_id = trace_resp.json()["id"]
        custom_id = str(uuid.uuid4())

        resp1 = api_post("/api/generations", {"id": custom_id, "traceId": trace_id, "name": "first"})
        assert resp1.status_code == 201
        resp2 = api_post("/api/generations", {"id": custom_id, "traceId": trace_id, "name": "second"})
        assert resp2.status_code == 409

    def test_list_generations(self):
        trace_resp = api_post("/api/traces", {"name": "list-gen-trace"})
        trace_id = trace_resp.json()["id"]
        api_post("/api/generations", {"traceId": trace_id, "name": "gen-a"})
        api_post("/api/generations", {"traceId": trace_id, "name": "gen-b"})

        resp = api_get("/api/generations", params={"traceId": trace_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert len(data["data"]) >= 2

    def test_list_generations_filter_by_traceId(self):
        trace1 = api_post("/api/traces", {"name": "gen-filter-1"}).json()["id"]
        trace2 = api_post("/api/traces", {"name": "gen-filter-2"}).json()["id"]
        api_post("/api/generations", {"traceId": trace1, "name": "gen-in-1"})
        api_post("/api/generations", {"traceId": trace2, "name": "gen-in-2"})

        resp = api_get("/api/generations", params={"traceId": trace1})
        data = resp.json()
        for gen in data["data"]:
            assert gen["traceId"] == trace1

    def test_get_generation(self):
        trace_resp = api_post("/api/traces", {"name": "get-gen-trace"})
        trace_id = trace_resp.json()["id"]
        gen_resp = api_post("/api/generations", {"traceId": trace_id, "name": "get-me"})
        gen_id = gen_resp.json()["id"]

        resp = api_get(f"/api/generations/{gen_id}")
        assert resp.status_code == 200
        gen = resp.json()
        assert gen["id"] == gen_id

    def test_get_generation_not_found(self):
        resp = api_get(f"/api/generations/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_generation(self):
        trace_resp = api_post("/api/traces", {"name": "update-gen-trace"})
        trace_id = trace_resp.json()["id"]
        gen_resp = api_post("/api/generations", {
            "traceId": trace_id,
            "name": "orig-gen",
            "model": "gpt-3.5",
        })
        gen_id = gen_resp.json()["id"]

        resp = api_patch(f"/api/generations/{gen_id}", {
            "model": "gpt-4",
            "output": {"result": "updated"},
            "usage": {"promptTokens": 20, "completionTokens": 10, "totalTokens": 30},
            "cost": 0.005,
        })
        assert resp.status_code == 200
        gen = resp.json()
        assert gen["model"] == "gpt-4"
        assert gen["output"] == {"result": "updated"}
        assert gen["usage"]["promptTokens"] == 20
        assert gen["usage"]["totalTokens"] == 30
        assert gen["cost"] == 0.005

    def test_update_generation_not_found(self):
        resp = api_patch(f"/api/generations/{uuid.uuid4()}", {"name": "ghost"})
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Score CRUD
# ════════════════════════════════════════════════════════════════════


class TestScoreCRUD:

    def test_create_score(self):
        trace_resp = api_post("/api/traces", {"name": "score-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/scores", {
            "traceId": trace_id,
            "name": "accuracy",
            "value": 0.95,
            "comment": "Great result",
            "source": "human",
        })
        assert resp.status_code == 201
        score = resp.json()
        assert score["traceId"] == trace_id
        assert score["name"] == "accuracy"
        assert score["value"] == 0.95
        assert score["comment"] == "Great result"
        assert score["source"] == "human"
        assert "id" in score
        assert "createdAt" in score

    def test_create_score_default_source(self):
        trace_resp = api_post("/api/traces", {"name": "score-default-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/scores", {
            "traceId": trace_id,
            "name": "quality",
            "value": 0.8,
        })
        assert resp.status_code == 201
        score = resp.json()
        assert score["source"] == "api"

    def test_create_score_invalid_trace_returns_404(self):
        resp = api_post("/api/scores", {
            "traceId": str(uuid.uuid4()),
            "name": "orphan-score",
            "value": 1.0,
        })
        assert resp.status_code == 404

    def test_list_scores(self):
        trace_resp = api_post("/api/traces", {"name": "list-score-trace"})
        trace_id = trace_resp.json()["id"]
        api_post("/api/scores", {"traceId": trace_id, "name": "s1", "value": 0.5})
        api_post("/api/scores", {"traceId": trace_id, "name": "s2", "value": 0.9})

        resp = api_get("/api/scores")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_list_scores_filter_by_traceId(self):
        trace1 = api_post("/api/traces", {"name": "score-filter-1"}).json()["id"]
        trace2 = api_post("/api/traces", {"name": "score-filter-2"}).json()["id"]
        api_post("/api/scores", {"traceId": trace1, "name": "x", "value": 1})
        api_post("/api/scores", {"traceId": trace2, "name": "y", "value": 2})

        resp = api_get("/api/scores", params={"traceId": trace1})
        data = resp.json()
        for s in data["data"]:
            assert s["traceId"] == trace1

    def test_list_scores_filter_by_name(self):
        trace_resp = api_post("/api/traces", {"name": "score-name-filter"})
        trace_id = trace_resp.json()["id"]
        score_name = f"unique-score-{UNIQUE}"
        api_post("/api/scores", {"traceId": trace_id, "name": score_name, "value": 1.0})
        api_post("/api/scores", {"traceId": trace_id, "name": "other", "value": 0.5})

        resp = api_get("/api/scores", params={"name": score_name})
        data = resp.json()
        for s in data["data"]:
            assert s["name"] == score_name

    def test_list_scores_filter_by_source(self):
        trace_resp = api_post("/api/traces", {"name": "score-source-filter"})
        trace_id = trace_resp.json()["id"]
        api_post("/api/scores", {"traceId": trace_id, "name": "a", "value": 1, "source": "human"})
        api_post("/api/scores", {"traceId": trace_id, "name": "b", "value": 2, "source": "model"})

        resp = api_get("/api/scores", params={"source": "human"})
        data = resp.json()
        for s in data["data"]:
            assert s["source"] == "human"

    def test_get_score(self):
        trace_resp = api_post("/api/traces", {"name": "get-score-trace"})
        trace_id = trace_resp.json()["id"]
        score_resp = api_post("/api/scores", {"traceId": trace_id, "name": "get-me", "value": 0.7})
        score_id = score_resp.json()["id"]

        resp = api_get(f"/api/scores/{score_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == score_id

    def test_get_score_not_found(self):
        resp = api_get(f"/api/scores/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_score(self):
        trace_resp = api_post("/api/traces", {"name": "del-score-trace"})
        trace_id = trace_resp.json()["id"]
        score_resp = api_post("/api/scores", {"traceId": trace_id, "name": "del-me", "value": 0.5})
        score_id = score_resp.json()["id"]

        resp = api_delete(f"/api/scores/{score_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/scores/{score_id}")
        assert get_resp.status_code == 404

    def test_delete_score_not_found(self):
        resp = api_delete(f"/api/scores/{uuid.uuid4()}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Dataset CRUD
# ════════════════════════════════════════════════════════════════════


class TestDatasetCRUD:

    def test_create_dataset(self):
        resp = api_post("/api/datasets", {
            "name": f"test-dataset-{UNIQUE}",
            "description": "A test dataset",
        })
        assert resp.status_code == 201
        ds = resp.json()
        assert ds["name"] == f"test-dataset-{UNIQUE}"
        assert ds["description"] == "A test dataset"
        assert "id" in ds
        assert "projectId" in ds
        assert "createdAt" in ds

    def test_create_dataset_duplicate_name_returns_409(self):
        name = f"dup-dataset-{UNIQUE}"
        resp1 = api_post("/api/datasets", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/api/datasets", {"name": name})
        assert resp2.status_code == 409

    def test_list_datasets(self):
        api_post("/api/datasets", {"name": f"list-ds-{UNIQUE}"})

        resp = api_get("/api/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_dataset_by_name(self):
        name = f"get-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": name, "description": "find me"})

        resp = api_get(f"/api/datasets/{name}")
        assert resp.status_code == 200
        ds = resp.json()
        assert ds["name"] == name
        assert ds["description"] == "find me"

    def test_get_dataset_not_found(self):
        resp = api_get("/api/datasets/nonexistent-ds-xyz")
        assert resp.status_code == 404

    def test_delete_dataset(self):
        name = f"del-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": name})

        resp = api_delete(f"/api/datasets/{name}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/datasets/{name}")
        assert get_resp.status_code == 404

    def test_delete_dataset_not_found(self):
        resp = api_delete("/api/datasets/nonexistent-ds-xyz")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Dataset Item CRUD
# ════════════════════════════════════════════════════════════════════


class TestDatasetItemCRUD:

    def test_create_dataset_item(self):
        ds_name = f"item-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})

        resp = api_post("/api/dataset-items", {
            "datasetName": ds_name,
            "input": {"question": "What is 2+2?"},
            "expectedOutput": {"answer": "4"},
            "metadata": {"difficulty": "easy"},
        })
        assert resp.status_code == 201
        item = resp.json()
        assert item["input"] == {"question": "What is 2+2?"}
        assert item["expectedOutput"] == {"answer": "4"}
        assert item["metadata"] == {"difficulty": "easy"}
        assert "id" in item
        assert "datasetId" in item
        assert "createdAt" in item

    def test_create_dataset_item_invalid_dataset_returns_404(self):
        resp = api_post("/api/dataset-items", {
            "datasetName": "nonexistent-ds",
            "input": {"test": "data"},
        })
        assert resp.status_code == 404

    def test_get_dataset_item(self):
        ds_name = f"get-item-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {
            "datasetName": ds_name,
            "input": {"q": "test"},
        })
        item_id = item_resp.json()["id"]

        resp = api_get(f"/api/dataset-items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id

    def test_get_dataset_item_not_found(self):
        resp = api_get(f"/api/dataset-items/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_dataset_item(self):
        ds_name = f"del-item-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {
            "datasetName": ds_name,
            "input": {"delete": "me"},
        })
        item_id = item_resp.json()["id"]

        resp = api_delete(f"/api/dataset-items/{item_id}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/dataset-items/{item_id}")
        assert get_resp.status_code == 404

    def test_delete_dataset_item_not_found(self):
        resp = api_delete(f"/api/dataset-items/{uuid.uuid4()}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Dataset Runs
# ════════════════════════════════════════════════════════════════════


class TestDatasetRuns:

    def test_create_dataset_run_item(self):
        ds_name = f"run-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {
            "datasetName": ds_name,
            "input": {"q": "hello"},
        })
        item_id = item_resp.json()["id"]

        trace_resp = api_post("/api/traces", {"name": "run-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": trace_id,
            "runName": f"run-{UNIQUE}",
            "datasetName": ds_name,
        })
        assert resp.status_code == 201
        run_item = resp.json()
        assert run_item["datasetItemId"] == item_id
        assert run_item["traceId"] == trace_id
        assert "id" in run_item
        assert "runId" in run_item
        assert "createdAt" in run_item

    def test_create_run_item_auto_creates_run(self):
        """Creating a run item should auto-create the run if it doesn't exist."""
        ds_name = f"auto-run-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "test"}})
        item_id = item_resp.json()["id"]
        trace_resp = api_post("/api/traces", {"name": "auto-run-trace"})
        trace_id = trace_resp.json()["id"]

        run_name = f"auto-run-{UNIQUE}"
        api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": trace_id,
            "runName": run_name,
            "datasetName": ds_name,
        })

        # The run should now exist
        resp = api_get(f"/api/datasets/{ds_name}/runs")
        assert resp.status_code == 200
        runs = resp.json()["data"]
        run_names = [r["name"] for r in runs]
        assert run_name in run_names

    def test_create_run_item_invalid_dataset_returns_404(self):
        trace_resp = api_post("/api/traces", {"name": "invalid-ds-run"})
        trace_id = trace_resp.json()["id"]

        resp = api_post("/api/dataset-run-items", {
            "datasetItemId": str(uuid.uuid4()),
            "traceId": trace_id,
            "runName": "bad-run",
            "datasetName": "nonexistent-ds",
        })
        assert resp.status_code == 404

    def test_create_run_item_invalid_trace_returns_404(self):
        ds_name = f"invalid-trace-run-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "x"}})
        item_id = item_resp.json()["id"]

        resp = api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": str(uuid.uuid4()),
            "runName": "bad-trace-run",
            "datasetName": ds_name,
        })
        assert resp.status_code == 404

    def test_list_dataset_runs(self):
        ds_name = f"list-runs-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "x"}})
        item_id = item_resp.json()["id"]
        trace_resp = api_post("/api/traces", {"name": "list-runs-trace"})
        trace_id = trace_resp.json()["id"]

        api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": trace_id,
            "runName": f"list-run-{UNIQUE}",
            "datasetName": ds_name,
        })

        resp = api_get(f"/api/datasets/{ds_name}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) >= 1

    def test_list_dataset_runs_dataset_not_found(self):
        resp = api_get("/api/datasets/nonexistent-ds/runs")
        assert resp.status_code == 404

    def test_get_dataset_run(self):
        ds_name = f"get-run-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "x"}})
        item_id = item_resp.json()["id"]
        trace_resp = api_post("/api/traces", {"name": "get-run-trace"})
        trace_id = trace_resp.json()["id"]

        run_name = f"get-run-{UNIQUE}"
        api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": trace_id,
            "runName": run_name,
            "datasetName": ds_name,
        })

        resp = api_get(f"/api/datasets/{ds_name}/runs/{run_name}")
        assert resp.status_code == 200
        data = resp.json()
        assert "run" in data
        assert "items" in data
        assert data["run"]["name"] == run_name
        assert len(data["items"]) >= 1
        assert data["items"][0]["traceId"] == trace_id

    def test_get_dataset_run_not_found(self):
        ds_name = f"run-404-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})

        resp = api_get(f"/api/datasets/{ds_name}/runs/nonexistent-run")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: Prompts
# ════════════════════════════════════════════════════════════════════


class TestPrompts:

    def test_create_prompt(self):
        resp = api_post("/api/prompts", {
            "name": f"test-prompt-{UNIQUE}",
            "prompt": "You are a helpful assistant. {{input}}",
            "labels": ["staging"],
        })
        assert resp.status_code == 201
        prompt = resp.json()
        assert prompt["name"] == f"test-prompt-{UNIQUE}"
        assert prompt["prompt"] == "You are a helpful assistant. {{input}}"
        assert prompt["version"] == 1
        assert prompt["labels"] == ["staging"]
        assert "id" in prompt
        assert "createdAt" in prompt

    def test_prompt_versioning(self):
        """Each POST with same name creates a new version."""
        name = f"versioned-prompt-{UNIQUE}"
        resp1 = api_post("/api/prompts", {"name": name, "prompt": "v1 prompt"})
        assert resp1.status_code == 201
        assert resp1.json()["version"] == 1

        resp2 = api_post("/api/prompts", {"name": name, "prompt": "v2 prompt"})
        assert resp2.status_code == 201
        assert resp2.json()["version"] == 2

        resp3 = api_post("/api/prompts", {"name": name, "prompt": "v3 prompt"})
        assert resp3.status_code == 201
        assert resp3.json()["version"] == 3

    def test_prompt_production_label(self):
        """Only one version per name can have 'production' label."""
        name = f"prod-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1", "labels": ["production"]})
        api_post("/api/prompts", {"name": name, "prompt": "v2", "labels": ["production"]})

        # List versions — only v2 should have production
        resp = api_get(f"/api/prompts/{name}/versions")
        versions = resp.json()["data"]
        prod_versions = [v for v in versions if "production" in v["labels"]]
        assert len(prod_versions) == 1
        assert prod_versions[0]["version"] == 2

    def test_get_prompt_returns_production(self):
        """GET prompt by name should return production-labeled version."""
        name = f"active-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1 text", "labels": ["production"]})
        api_post("/api/prompts", {"name": name, "prompt": "v2 text", "labels": ["staging"]})

        resp = api_get(f"/api/prompts/{name}")
        assert resp.status_code == 200
        prompt = resp.json()
        assert prompt["prompt"] == "v1 text"
        assert prompt["version"] == 1

    def test_get_prompt_returns_latest_if_no_production(self):
        """If no production label, return latest version."""
        name = f"latest-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1"})
        api_post("/api/prompts", {"name": name, "prompt": "v2"})

        resp = api_get(f"/api/prompts/{name}")
        assert resp.status_code == 200
        prompt = resp.json()
        assert prompt["version"] == 2
        assert prompt["prompt"] == "v2"

    def test_get_prompt_by_version(self):
        name = f"by-version-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "version-1"})
        api_post("/api/prompts", {"name": name, "prompt": "version-2"})

        resp = api_get(f"/api/prompts/{name}", params={"version": 1})
        assert resp.status_code == 200
        assert resp.json()["prompt"] == "version-1"
        assert resp.json()["version"] == 1

    def test_get_prompt_by_label(self):
        name = f"by-label-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "staging-v", "labels": ["staging"]})
        api_post("/api/prompts", {"name": name, "prompt": "prod-v", "labels": ["production"]})

        resp = api_get(f"/api/prompts/{name}", params={"label": "staging"})
        assert resp.status_code == 200
        assert resp.json()["prompt"] == "staging-v"

    def test_get_prompt_not_found(self):
        resp = api_get("/api/prompts/nonexistent-prompt-xyz")
        assert resp.status_code == 404

    def test_list_prompts(self):
        name = f"list-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "text"})

        resp = api_get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        # Should contain the prompt we created
        names = [p["name"] for p in data["data"]]
        assert name in names

    def test_list_prompts_shows_latest_version(self):
        """List prompts should show the latest version for each name."""
        name = f"latest-list-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1"})
        api_post("/api/prompts", {"name": name, "prompt": "v2"})
        api_post("/api/prompts", {"name": name, "prompt": "v3"})

        resp = api_get("/api/prompts")
        data = resp.json()
        matching = [p for p in data["data"] if p["name"] == name]
        assert len(matching) == 1  # Only one entry per name
        assert matching[0]["version"] == 3

    def test_list_prompt_versions(self):
        name = f"versions-list-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1"})
        api_post("/api/prompts", {"name": name, "prompt": "v2"})

        resp = api_get(f"/api/prompts/{name}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) == 2
        versions = [p["version"] for p in data["data"]]
        assert 1 in versions
        assert 2 in versions

    def test_list_prompt_versions_not_found(self):
        resp = api_get("/api/prompts/nonexistent-prompt-xyz/versions")
        assert resp.status_code == 404

    def test_delete_prompt(self):
        name = f"del-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "v1"})
        api_post("/api/prompts", {"name": name, "prompt": "v2"})

        resp = api_delete(f"/api/prompts/{name}")
        assert resp.status_code == 204

        get_resp = api_get(f"/api/prompts/{name}")
        assert get_resp.status_code == 404

    def test_delete_prompt_not_found(self):
        resp = api_delete("/api/prompts/nonexistent-prompt-xyz")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 11: Sessions
# ════════════════════════════════════════════════════════════════════


class TestSessions:

    def test_list_sessions(self):
        session_id = f"session-list-{UNIQUE}"
        api_post("/api/traces", {"name": "s-trace-1", "sessionId": session_id})
        api_post("/api/traces", {"name": "s-trace-2", "sessionId": session_id})

        resp = api_get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

        # Find our session
        sessions = [s for s in data["data"] if s["sessionId"] == session_id]
        assert len(sessions) == 1
        session = sessions[0]
        assert session["totalTraces"] >= 2
        assert "totalCost" in session
        assert "totalTokens" in session
        assert "firstTrace" in session
        assert "lastTrace" in session

    def test_list_sessions_with_costs(self):
        """Sessions should aggregate costs from generations."""
        session_id = f"cost-session-{UNIQUE}"
        trace_resp = api_post("/api/traces", {"name": "cost-trace", "sessionId": session_id})
        trace_id = trace_resp.json()["id"]

        api_post("/api/generations", {
            "traceId": trace_id,
            "name": "gen1",
            "cost": 0.01,
            "usage": {"promptTokens": 100, "completionTokens": 50, "totalTokens": 150},
        })
        api_post("/api/generations", {
            "traceId": trace_id,
            "name": "gen2",
            "cost": 0.02,
            "usage": {"promptTokens": 200, "completionTokens": 100, "totalTokens": 300},
        })

        resp = api_get("/api/sessions")
        sessions = [s for s in resp.json()["data"] if s["sessionId"] == session_id]
        assert len(sessions) == 1
        session = sessions[0]
        assert session["totalCost"] == pytest.approx(0.03, abs=0.001)
        assert session["totalTokens"] == 450

    def test_get_session(self):
        session_id = f"get-session-{UNIQUE}"
        api_post("/api/traces", {"name": "gs-trace-1", "sessionId": session_id})
        api_post("/api/traces", {"name": "gs-trace-2", "sessionId": session_id})

        resp = api_get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessionId"] == session_id
        assert data["totalTraces"] >= 2
        assert "traces" in data
        assert isinstance(data["traces"], list)
        assert len(data["traces"]) >= 2
        assert "totalCost" in data
        assert "totalTokens" in data

    def test_get_session_not_found(self):
        resp = api_get(f"/api/sessions/nonexistent-session-{uuid.uuid4().hex[:8]}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 12: Business Rules — Computed Fields
# ════════════════════════════════════════════════════════════════════


class TestComputedFields:

    def test_trace_total_cost(self):
        """Trace totalCost should sum all generation costs."""
        trace_resp = api_post("/api/traces", {"name": "cost-trace"})
        trace_id = trace_resp.json()["id"]

        api_post("/api/generations", {"traceId": trace_id, "name": "g1", "cost": 0.01})
        api_post("/api/generations", {"traceId": trace_id, "name": "g2", "cost": 0.02})
        api_post("/api/generations", {"traceId": trace_id, "name": "g3", "cost": 0.03})

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["totalCost"] == pytest.approx(0.06, abs=0.001)

    def test_trace_total_tokens(self):
        """Trace totalTokens should sum all generation totalTokens."""
        trace_resp = api_post("/api/traces", {"name": "token-trace"})
        trace_id = trace_resp.json()["id"]

        api_post("/api/generations", {
            "traceId": trace_id,
            "name": "g1",
            "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
        })
        api_post("/api/generations", {
            "traceId": trace_id,
            "name": "g2",
            "usage": {"promptTokens": 20, "completionTokens": 10, "totalTokens": 30},
        })

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["totalTokens"] == 45

    def test_trace_duration_from_trace_times(self):
        """Duration should be computed from trace endTime - startTime."""
        trace_resp = api_post("/api/traces", {
            "name": "duration-trace",
            "startTime": "2024-01-01T00:00:00.000Z",
            "endTime": "2024-01-01T00:00:02.500Z",
        })
        trace_id = trace_resp.json()["id"]

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["duration"] == pytest.approx(2500, abs=10)

    def test_trace_duration_from_spans(self):
        """If trace has no endTime, use latest span/generation endTime."""
        trace_resp = api_post("/api/traces", {
            "name": "duration-from-span",
            "startTime": "2024-01-01T00:00:00.000Z",
        })
        trace_id = trace_resp.json()["id"]

        api_post("/api/spans", {
            "traceId": trace_id,
            "name": "long-span",
            "startTime": "2024-01-01T00:00:00.000Z",
            "endTime": "2024-01-01T00:00:05.000Z",
        })

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["duration"] == pytest.approx(5000, abs=10)

    def test_trace_duration_null_when_no_end(self):
        """Duration should be null if no endTime anywhere."""
        trace_resp = api_post("/api/traces", {
            "name": "no-end-trace",
            "startTime": "2024-01-01T00:00:00.000Z",
        })
        trace_id = trace_resp.json()["id"]

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["duration"] is None

    def test_trace_no_generations_defaults(self):
        """Trace with no generations should have 0 cost and 0 tokens."""
        trace_resp = api_post("/api/traces", {"name": "empty-trace"})
        trace_id = trace_resp.json()["id"]

        resp = api_get(f"/api/traces/{trace_id}")
        trace = resp.json()
        assert trace["totalCost"] == 0
        assert trace["totalTokens"] == 0


# ════════════════════════════════════════════════════════════════════
# PART 13: Data Isolation Between Projects
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_trace_isolation(self):
        """Project A's traces should not be visible to Project B."""
        trace_resp = api_post("/api/traces", {"name": f"isolated-trace-{UNIQUE}"})
        trace_id = trace_resp.json()["id"]

        # Project B should not see it
        resp = api_get(f"/api/traces/{trace_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_span_isolation(self):
        """Spans should be scoped to project."""
        trace_resp = api_post("/api/traces", {"name": "iso-span-trace"})
        trace_id = trace_resp.json()["id"]
        span_resp = api_post("/api/spans", {"traceId": trace_id, "name": "iso-span"})
        span_id = span_resp.json()["id"]

        resp = api_get(f"/api/spans/{span_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_generation_isolation(self):
        """Generations should be scoped to project."""
        trace_resp = api_post("/api/traces", {"name": "iso-gen-trace"})
        trace_id = trace_resp.json()["id"]
        gen_resp = api_post("/api/generations", {"traceId": trace_id, "name": "iso-gen"})
        gen_id_val = gen_resp.json()["id"]

        resp = api_get(f"/api/generations/{gen_id_val}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_score_isolation(self):
        """Scores should be scoped to project."""
        trace_resp = api_post("/api/traces", {"name": "iso-score-trace"})
        trace_id = trace_resp.json()["id"]
        score_resp = api_post("/api/scores", {"traceId": trace_id, "name": "iso", "value": 1.0})
        score_id = score_resp.json()["id"]

        resp = api_get(f"/api/scores/{score_id}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_dataset_isolation(self):
        """Datasets should be scoped to project."""
        ds_name = f"iso-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})

        resp = api_get(f"/api/datasets/{ds_name}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_prompt_isolation(self):
        """Prompts should be scoped to project."""
        name = f"iso-prompt-{UNIQUE}"
        api_post("/api/prompts", {"name": name, "prompt": "text"})

        resp = api_get(f"/api/prompts/{name}", headers=HEADERS2)
        assert resp.status_code == 404

    def test_session_isolation(self):
        """Sessions should be scoped to project."""
        session_id = f"iso-session-{UNIQUE}"
        api_post("/api/traces", {"name": "iso-session-trace", "sessionId": session_id})

        resp = api_get(f"/api/sessions/{session_id}", headers=HEADERS2)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_trace_cascades_spans(self):
        """Deleting a trace should delete all its spans."""
        trace_resp = api_post("/api/traces", {"name": "cascade-trace"})
        trace_id = trace_resp.json()["id"]
        span_resp = api_post("/api/spans", {"traceId": trace_id, "name": "cascade-span"})
        span_id = span_resp.json()["id"]

        api_delete(f"/api/traces/{trace_id}")

        resp = api_get(f"/api/spans/{span_id}")
        assert resp.status_code == 404

    def test_delete_trace_cascades_generations(self):
        """Deleting a trace should delete all its generations."""
        trace_resp = api_post("/api/traces", {"name": "cascade-gen-trace"})
        trace_id = trace_resp.json()["id"]
        gen_resp = api_post("/api/generations", {"traceId": trace_id, "name": "cascade-gen"})
        gen_id_val = gen_resp.json()["id"]

        api_delete(f"/api/traces/{trace_id}")

        resp = api_get(f"/api/generations/{gen_id_val}")
        assert resp.status_code == 404

    def test_delete_trace_cascades_scores(self):
        """Deleting a trace should delete all its scores."""
        trace_resp = api_post("/api/traces", {"name": "cascade-score-trace"})
        trace_id = trace_resp.json()["id"]
        score_resp = api_post("/api/scores", {"traceId": trace_id, "name": "cascade-s", "value": 1.0})
        score_id = score_resp.json()["id"]

        api_delete(f"/api/traces/{trace_id}")

        resp = api_get(f"/api/scores/{score_id}")
        assert resp.status_code == 404

    def test_delete_dataset_cascades_items(self):
        """Deleting a dataset should delete all its items."""
        ds_name = f"cascade-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "x"}})
        item_id = item_resp.json()["id"]

        api_delete(f"/api/datasets/{ds_name}")

        resp = api_get(f"/api/dataset-items/{item_id}")
        assert resp.status_code == 404

    def test_delete_dataset_cascades_runs(self):
        """Deleting a dataset should delete all its runs."""
        ds_name = f"cascade-run-ds-{UNIQUE}"
        api_post("/api/datasets", {"name": ds_name})
        item_resp = api_post("/api/dataset-items", {"datasetName": ds_name, "input": {"q": "x"}})
        item_id = item_resp.json()["id"]
        trace_resp = api_post("/api/traces", {"name": "cascade-run-trace"})
        trace_id = trace_resp.json()["id"]

        api_post("/api/dataset-run-items", {
            "datasetItemId": item_id,
            "traceId": trace_id,
            "runName": "cascade-run",
            "datasetName": ds_name,
        })

        api_delete(f"/api/datasets/{ds_name}")

        # The run should be gone (dataset is gone)
        resp = api_get(f"/api/datasets/{ds_name}/runs")
        assert resp.status_code == 404
