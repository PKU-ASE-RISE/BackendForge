"""
Langfuse — L3 Workflow Tests (Adversarial)

Multi-step workflows crossing 3+ entity types.
Targets: computed stats, cascade, sessions, prompts, datasets.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

PROJECT_KEY = f"test-wf-project-{uuid.uuid4().hex[:8]}"

HEADERS = {
    "X-Api-Key": PROJECT_KEY,
    "Content-Type": "application/json",
}


def _reset_test_context():
    """Give every test a fresh default project namespace."""
    global PROJECT_KEY, HEADERS

    PROJECT_KEY = f"test-wf-project-{uuid.uuid4().hex[:8]}"
    HEADERS = {
        "X-Api-Key": PROJECT_KEY,
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


class TestTraceObservabilityWorkflow:
    """Pattern 2+5+7: Full trace with spans/generations/scores, verify computed stats."""

    def test_full_trace_lifecycle_with_stats(self):
        """
        Create trace -> add spans (nested) -> add generations with cost/tokens
        -> add scores -> verify trace stats -> delete trace -> all gone.
        """
        uid = unique()

        # 1. Create trace
        trace = api_post("/api/traces", {
            "name": f"lifecycle-{uid}",
            "startTime": "2024-03-01T10:00:00Z",
            "userId": f"user-{uid}",
            "sessionId": f"sess-{uid}",
            "tags": ["workflow", "test"]
        }).json()
        assert trace["name"] == f"lifecycle-{uid}"

        # 2. Add root span
        root_span = api_post("/api/spans", {
            "traceId": trace["id"],
            "name": "retrieval",
            "startTime": "2024-03-01T10:00:00.100Z",
            "endTime": "2024-03-01T10:00:00.500Z",
            "level": "DEFAULT"
        }).json()

        # 3. Add child span
        child_span = api_post("/api/spans", {
            "traceId": trace["id"],
            "name": "embedding",
            "parentSpanId": root_span["id"],
            "startTime": "2024-03-01T10:00:00.200Z",
            "endTime": "2024-03-01T10:00:00.400Z"
        }).json()
        assert child_span["parentSpanId"] == root_span["id"]

        # 4. Add generations
        gen1 = api_post("/api/generations", {
            "traceId": trace["id"],
            "name": "llm-call-1",
            "model": "gpt-4",
            "cost": 0.05,
            "usage": {"promptTokens": 500, "completionTokens": 200, "totalTokens": 700},
            "startTime": "2024-03-01T10:00:01Z",
            "endTime": "2024-03-01T10:00:02Z"
        }).json()
        gen2 = api_post("/api/generations", {
            "traceId": trace["id"],
            "name": "llm-call-2",
            "model": "gpt-4",
            "cost": 0.03,
            "usage": {"promptTokens": 300, "completionTokens": 100, "totalTokens": 400},
            "startTime": "2024-03-01T10:00:02Z",
            "endTime": "2024-03-01T10:00:03Z"
        }).json()

        # 5. Add score
        score = api_post("/api/scores", {
            "traceId": trace["id"],
            "name": "quality",
            "value": 0.9,
            "source": "human"
        }).json()

        # 6. Verify trace computed stats
        detail = api_get(f"/api/traces/{trace['id']}").json()
        assert detail["totalCost"] == pytest.approx(0.08)
        assert detail["totalTokens"] == 1100
        # Duration: from trace start to latest endTime (gen2 endTime = 10:00:03)
        assert detail["duration"] == pytest.approx(3000, abs=100)

        # 7. Delete trace — cascades
        r = api_delete(f"/api/traces/{trace['id']}")
        assert r.status_code == 204
        assert api_get(f"/api/spans/{root_span['id']}").status_code == 404
        assert api_get(f"/api/spans/{child_span['id']}").status_code == 404
        assert api_get(f"/api/generations/{gen1['id']}").status_code == 404
        assert api_get(f"/api/generations/{gen2['id']}").status_code == 404
        assert api_get(f"/api/scores/{score['id']}").status_code == 404


class TestSessionAggregation:
    """Pattern 5: Session aggregates from multiple traces."""

    def test_session_stats_computed_from_traces(self):
        """
        Create multiple traces with same sessionId -> verify session aggregation.
        """
        uid = unique()
        sess_id = f"session-{uid}"
        headers = {"X-Api-Key": f"sess-proj-{uid}", "Content-Type": "application/json"}

        # Trace 1
        t1 = api_post("/api/traces", {
            "name": "t1", "sessionId": sess_id,
            "startTime": "2024-04-01T09:00:00Z"
        }, headers=headers).json()
        api_post("/api/generations", {
            "traceId": t1["id"], "name": "g1",
            "cost": 0.10, "usage": {"totalTokens": 500}
        }, headers=headers)

        # Trace 2
        t2 = api_post("/api/traces", {
            "name": "t2", "sessionId": sess_id,
            "startTime": "2024-04-01T10:00:00Z"
        }, headers=headers).json()
        api_post("/api/generations", {
            "traceId": t2["id"], "name": "g2",
            "cost": 0.05, "usage": {"totalTokens": 300}
        }, headers=headers)

        # Trace 3 — different session (control)
        api_post("/api/traces", {
            "name": "t3", "sessionId": "other-session",
            "startTime": "2024-04-01T11:00:00Z"
        }, headers=headers)

        # List sessions
        r = api_get("/api/sessions", headers=headers)
        assert r.status_code == 200
        sessions = r.json()["data"]
        our_sess = [s for s in sessions if s["sessionId"] == sess_id]
        assert len(our_sess) == 1
        sess = our_sess[0]
        assert sess["totalTraces"] == 2
        assert sess["totalCost"] == pytest.approx(0.15)
        assert sess["totalTokens"] == 800

        # Get session detail
        detail = api_get(f"/api/sessions/{sess_id}", headers=headers)
        assert detail.status_code == 200


class TestPromptVersionWorkflow:
    """Pattern 5+8: Prompt versioning with production label management."""

    def test_prompt_version_and_production_label_lifecycle(self):
        """
        Create v1 (no label) -> v2 (production) -> v3 (no label)
        -> GET returns v2 (production) -> create v4 with production
        -> GET returns v4 -> v2 loses production label.
        """
        uid = unique()
        name = f"my-prompt-{uid}"
        headers = {"X-Api-Key": f"prompt-proj-{uid}", "Content-Type": "application/json"}

        # v1 — no label
        p1 = api_post("/api/prompts", {"name": name, "prompt": "template v1"}, headers=headers).json()
        assert p1["version"] == 1

        # v2 — production label
        p2 = api_post("/api/prompts", {
            "name": name, "prompt": "template v2", "labels": ["production"]
        }, headers=headers).json()
        assert p2["version"] == 2
        assert "production" in p2["labels"]

        # v3 — no label
        p3 = api_post("/api/prompts", {"name": name, "prompt": "template v3"}, headers=headers).json()
        assert p3["version"] == 3

        # Default GET returns production (v2)
        r = api_get(f"/api/prompts/{name}", headers=headers)
        assert r.status_code == 200
        assert r.json()["version"] == 2
        assert r.json()["prompt"] == "template v2"

        # GET with version param
        r_v1 = api_get(f"/api/prompts/{name}", params={"version": 1}, headers=headers)
        assert r_v1.json()["prompt"] == "template v1"

        # Create v4 with production — should remove production from v2
        p4 = api_post("/api/prompts", {
            "name": name, "prompt": "template v4", "labels": ["production"]
        }, headers=headers).json()
        assert p4["version"] == 4

        # Default GET now returns v4
        r2 = api_get(f"/api/prompts/{name}", headers=headers)
        assert r2.json()["version"] == 4
        assert r2.json()["prompt"] == "template v4"

        # List all versions
        versions_resp = api_get(f"/api/prompts/{name}/versions", headers=headers).json()
        assert len(versions_resp["data"]) == 4


class TestDatasetEvaluationWorkflow:
    """Pattern 2+5+7: Create dataset, items, run items, verify structure."""

    def test_dataset_run_workflow(self):
        """
        Create dataset + items -> run traces against items -> verify run details.
        """
        uid = unique()
        headers = {"X-Api-Key": f"ds-proj-{uid}", "Content-Type": "application/json"}

        # Create dataset
        ds = api_post("/api/datasets", {
            "name": f"eval-ds-{uid}", "description": "Test dataset"
        }, headers=headers).json()

        # Create items
        item1 = api_post("/api/dataset-items", {
            "datasetName": ds["name"],
            "input": {"question": "What is 2+2?"},
            "expectedOutput": {"answer": "4"}
        }, headers=headers).json()
        item2 = api_post("/api/dataset-items", {
            "datasetName": ds["name"],
            "input": {"question": "What is 3+3?"},
            "expectedOutput": {"answer": "6"}
        }, headers=headers).json()

        # Create traces (simulating evaluation runs)
        t1 = api_post("/api/traces", {"name": "eval-t1"}, headers=headers).json()
        t2 = api_post("/api/traces", {"name": "eval-t2"}, headers=headers).json()

        # Create run items (auto-creates run)
        run_name = f"run-{uid}"
        ri1 = api_post("/api/dataset-run-items", {
            "datasetItemId": item1["id"],
            "traceId": t1["id"],
            "runName": run_name,
            "datasetName": ds["name"]
        }, headers=headers).json()
        assert "id" in ri1
        assert ri1["datasetItemId"] == item1["id"]
        assert ri1["traceId"] == t1["id"]

        ri2 = api_post("/api/dataset-run-items", {
            "datasetItemId": item2["id"],
            "traceId": t2["id"],
            "runName": run_name,
            "datasetName": ds["name"]
        }, headers=headers).json()

        # List runs for dataset
        runs_resp = api_get(f"/api/datasets/{ds['name']}/runs", headers=headers).json()
        runs = runs_resp["data"]
        assert len(runs) >= 1
        our_run = [r for r in runs if r["name"] == run_name]
        assert len(our_run) == 1

        # Get run detail
        run_detail = api_get(f"/api/datasets/{ds['name']}/runs/{run_name}", headers=headers).json()
        assert run_detail["run"]["name"] == run_name

        # Delete dataset — cascades items and runs
        r = api_delete(f"/api/datasets/{ds['name']}", headers=headers)
        assert r.status_code == 204
        assert api_get(f"/api/dataset-items/{item1['id']}", headers=headers).status_code == 404


class TestTraceUpdateWorkflow:
    """Pattern 1+5: Update trace and verify fields change correctly."""

    def test_update_trace_preserves_and_modifies(self):
        """
        Create trace -> update some fields -> verify original fields preserved
        and updated fields changed.
        """
        uid = unique()
        trace = api_post("/api/traces", {
            "name": f"upd-{uid}",
            "input": {"original": True},
            "userId": f"user-{uid}",
            "tags": ["original"]
        }).json()

        # Update
        r = api_patch(f"/api/traces/{trace['id']}", {
            "output": {"result": "done"},
            "tags": ["updated", "modified"],
            "endTime": "2024-05-01T12:00:00Z"
        })
        assert r.status_code == 200
        updated = r.json()
        assert updated["name"] == f"upd-{uid}"  # Preserved
        assert updated["input"] == {"original": True}  # Preserved
        assert updated["output"] == {"result": "done"}  # Updated
        assert updated["tags"] == ["updated", "modified"]  # Updated
        assert updated["userId"] == f"user-{uid}"  # Preserved

        # Verify via GET
        detail = api_get(f"/api/traces/{trace['id']}").json()
        assert detail["output"] == {"result": "done"}
        assert detail["tags"] == ["updated", "modified"]


class TestScoreFilteringWorkflow:
    """Pattern 3: Score filtering by traceId, name, source."""

    def test_score_filtering(self):
        """
        Create multiple scores with different attributes -> filter correctly.
        """
        uid = unique()
        headers = {"X-Api-Key": f"score-proj-{uid}", "Content-Type": "application/json"}

        t1 = api_post("/api/traces", {"name": "t1"}, headers=headers).json()
        t2 = api_post("/api/traces", {"name": "t2"}, headers=headers).json()

        api_post("/api/scores", {"traceId": t1["id"], "name": "accuracy", "value": 0.9, "source": "human"}, headers=headers)
        api_post("/api/scores", {"traceId": t1["id"], "name": "relevance", "value": 0.8, "source": "model"}, headers=headers)
        api_post("/api/scores", {"traceId": t2["id"], "name": "accuracy", "value": 0.7, "source": "api"}, headers=headers)

        # Filter by traceId
        r1 = api_get("/api/scores", params={"traceId": t1["id"]}, headers=headers)
        assert r1.json()["total"] == 2

        # Filter by name
        r2 = api_get("/api/scores", params={"name": "accuracy"}, headers=headers)
        assert r2.json()["total"] == 2

        # Filter by source
        r3 = api_get("/api/scores", params={"source": "human"}, headers=headers)
        assert r3.json()["total"] == 1
        assert r3.json()["data"][0]["source"] == "human"


class TestMultiProjectIsolation:
    """Pattern 6: Full isolation between projects."""

    def test_complete_isolation(self):
        """
        Project A creates traces/datasets/prompts.
        Project B sees nothing from A.
        """
        uid = unique()
        proj_a = {"X-Api-Key": f"iso-a-{uid}", "Content-Type": "application/json"}
        proj_b = {"X-Api-Key": f"iso-b-{uid}", "Content-Type": "application/json"}

        # Project A creates
        trace_a = api_post("/api/traces", {"name": f"trace-a-{uid}"}, headers=proj_a).json()
        ds_a = api_post("/api/datasets", {"name": f"ds-a-{uid}"}, headers=proj_a).json()
        api_post("/api/prompts", {"name": f"prompt-a-{uid}", "prompt": "v1"}, headers=proj_a)

        # Project B cannot see anything from A
        assert api_get(f"/api/traces/{trace_a['id']}", headers=proj_b).status_code == 404
        assert api_get(f"/api/datasets/{ds_a['name']}", headers=proj_b).status_code == 404
        assert api_get(f"/api/prompts/prompt-a-{uid}", headers=proj_b).status_code == 404

        # Project B sees empty lists
        assert api_get("/api/traces", headers=proj_b).json()["total"] == 0
        assert api_get("/api/datasets", headers=proj_b).json()["data"] == []
