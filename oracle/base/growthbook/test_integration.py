"""
BackendForge — L2 Integration Tests for GrowthBook Task

Adversarial tests targeting: camelCase fields, nested environments map,
filtering, status codes, business logic, data isolation, cascades.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

RUN_ID = uuid.uuid4().hex
ORG_A_KEY = f"org-a-{RUN_ID}"
ORG_B_KEY = f"org-b-{RUN_ID}"

HEADERS_A = {"X-Api-Key": ORG_A_KEY, "Content-Type": "application/json"}
HEADERS_B = {"X-Api-Key": ORG_B_KEY, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent primary and secondary organizations."""
    global ORG_A_KEY, ORG_B_KEY, HEADERS_A, HEADERS_B

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    ORG_A_KEY = f"org-a-{item_id}"
    ORG_B_KEY = f"org-b-{item_id}"
    HEADERS_A = {"X-Api-Key": ORG_A_KEY, "Content-Type": "application/json"}
    HEADERS_B = {"X-Api-Key": ORG_B_KEY, "Content-Type": "application/json"}


def get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS_A, timeout=30)


def post(path, json=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS_A, timeout=30)


def put(path, json=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json, headers=headers or HEADERS_A, timeout=30)


def delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS_A, timeout=30)


class TestProjectResponseFields:
    """Pattern 1+4: Project response wrapped in {project:...} with camelCase."""

    def test_create_project_returns_201_wrapped(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/projects", {"name": f"Proj-{tag}", "description": "Desc"})
        assert r.status_code == 201
        data = r.json()
        assert "project" in data
        p = data["project"]
        assert "id" in p
        assert "name" in p
        assert "description" in p
        assert "dateCreated" in p
        assert "dateUpdated" in p
        assert p["name"] == f"Proj-{tag}"
        assert p["description"] == "Desc"

    def test_list_projects_wrapped(self):
        post("/api/projects", {"name": f"List-{uuid.uuid4().hex[:6]}"})
        r = get("/api/projects")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data
        assert isinstance(data["projects"], list)
        assert len(data["projects"]) >= 1

    def test_get_project_wrapped(self):
        p = post("/api/projects", {"name": f"Get-{uuid.uuid4().hex[:6]}"}).json()["project"]
        r = get(f"/api/projects/{p['id']}")
        assert r.status_code == 200
        assert "project" in r.json()
        assert r.json()["project"]["id"] == p["id"]


class TestEnvironmentResponseFields:
    """Pattern 1+4: Environment response with custom ID and wrapping."""

    def test_create_environment_returns_201(self):
        env_id = f"env-{uuid.uuid4().hex[:6]}"
        r = post("/api/environments", {"id": env_id, "name": "Dev", "description": "Development"})
        assert r.status_code == 201
        data = r.json()
        assert "environment" in data
        env = data["environment"]
        assert env["id"] == env_id
        assert env["name"] == "Dev"
        assert "dateCreated" in env
        assert "dateUpdated" in env

    def test_duplicate_environment_id_returns_409(self):
        env_id = f"dup-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "First"})
        r = post("/api/environments", {"id": env_id, "name": "Second"})
        assert r.status_code == 409


class TestFeatureResponseFields:
    """Pattern 1+2: Feature response with environments map."""

    def test_create_feature_has_environments_map(self):
        env_id = f"fenv-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "Prod"})
        feat_key = f"feat-{uuid.uuid4().hex[:6]}"
        r = post("/api/features", {
            "key": feat_key, "valueType": "boolean", "defaultValue": "true"
        })
        assert r.status_code == 201
        data = r.json()
        assert "feature" in data
        feat = data["feature"]
        assert feat["id"] == feat_key
        assert feat["key"] == feat_key
        assert feat["valueType"] == "boolean"
        assert feat["defaultValue"] == "true"
        assert "environments" in feat
        assert isinstance(feat["environments"], dict)
        # Should have the environment we created
        assert env_id in feat["environments"]
        env_data = feat["environments"][env_id]
        assert "enabled" in env_data
        assert "rules" in env_data
        assert env_data["enabled"] is True
        assert isinstance(env_data["rules"], list)

    def test_duplicate_feature_key_returns_409(self):
        key = f"dupf-{uuid.uuid4().hex[:6]}"
        post("/api/features", {"key": key, "valueType": "string", "defaultValue": "hello"})
        r = post("/api/features", {"key": key, "valueType": "string", "defaultValue": "world"})
        assert r.status_code == 409


class TestFeatureToggle:
    """Pattern 5: Toggle flips enabled state."""

    def test_toggle_feature_environment(self):
        env_id = f"tenv-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "Toggle Env"})
        feat_key = f"tfeat-{uuid.uuid4().hex[:6]}"
        post("/api/features", {"key": feat_key, "valueType": "boolean", "defaultValue": "false"})

        # Initially enabled=True
        feat = get(f"/api/features/{feat_key}").json()["feature"]
        assert feat["environments"][env_id]["enabled"] is True

        # Toggle → False
        r = post(f"/api/features/{feat_key}/toggle/{env_id}")
        assert r.status_code == 200
        assert r.json()["feature"]["environments"][env_id]["enabled"] is False

        # Toggle again → True
        r = post(f"/api/features/{feat_key}/toggle/{env_id}")
        assert r.status_code == 200
        assert r.json()["feature"]["environments"][env_id]["enabled"] is True


class TestFeatureRules:
    """Pattern 1+5: Feature rules CRUD and response structure."""

    def test_add_force_rule(self):
        env_id = f"renv-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "Rule Env"})
        feat_key = f"rfeat-{uuid.uuid4().hex[:6]}"
        post("/api/features", {"key": feat_key, "valueType": "string", "defaultValue": "off"})

        r = post(f"/api/features/{feat_key}/rules/{env_id}", {
            "type": "force", "value": "on", "condition": {"country": {"$eq": "US"}}
        })
        assert r.status_code == 201
        data = r.json()
        assert "rules" in data
        assert len(data["rules"]) == 1
        rule = data["rules"][0]
        assert rule["type"] == "force"
        assert rule["value"] == "on"
        assert rule["condition"] == {"country": {"$eq": "US"}}

    def test_delete_rule_by_index(self):
        env_id = f"denv-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "Del Rule Env"})
        feat_key = f"dfeat-{uuid.uuid4().hex[:6]}"
        post("/api/features", {"key": feat_key, "valueType": "boolean", "defaultValue": "false"})
        post(f"/api/features/{feat_key}/rules/{env_id}", {"type": "force", "value": "true"})
        post(f"/api/features/{feat_key}/rules/{env_id}", {"type": "force", "value": "false"})

        # Delete rule at index 0
        r = delete(f"/api/features/{feat_key}/rules/{env_id}/0")
        assert r.status_code == 200
        rules = r.json()["rules"]
        assert len(rules) == 1
        assert rules[0]["value"] == "false"


class TestExperimentResponseFields:
    """Pattern 1+4: Experiment response with camelCase and status."""

    def test_create_experiment_returns_201(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/experiments", {
            "name": f"Exp-{tag}", "key": f"exp-key-{tag}",
            "variations": [
                {"name": "Control", "value": "false", "weight": 0.5},
                {"name": "Treatment", "value": "true", "weight": 0.5}
            ]
        })
        assert r.status_code == 201
        data = r.json()
        assert "experiment" in data
        exp = data["experiment"]
        assert "id" in exp
        assert exp["name"] == f"Exp-{tag}"
        assert exp["key"] == f"exp-key-{tag}"
        assert exp["status"] == "draft"
        assert "variations" in exp
        assert len(exp["variations"]) == 2
        assert "dateCreated" in exp
        assert "dateUpdated" in exp


class TestExperimentStatusTransitions:
    """Pattern 5+8: Experiment status transitions."""

    def test_valid_status_transitions(self):
        tag = uuid.uuid4().hex[:6]
        exp = post("/api/experiments", {
            "name": f"Trans-{tag}", "key": f"trans-{tag}",
            "variations": [{"name": "A", "value": "a", "weight": 0.5},
                           {"name": "B", "value": "b", "weight": 0.5}]
        }).json()["experiment"]
        assert exp["status"] == "draft"

        # draft → running
        r = put(f"/api/experiments/{exp['id']}", {"status": "running"})
        assert r.status_code == 200
        assert r.json()["experiment"]["status"] == "running"

        # running → stopped
        r = put(f"/api/experiments/{exp['id']}", {"status": "stopped"})
        assert r.status_code == 200
        assert r.json()["experiment"]["status"] == "stopped"

    def test_invalid_backward_transition(self):
        tag = uuid.uuid4().hex[:6]
        exp = post("/api/experiments", {
            "name": f"Back-{tag}", "key": f"back-{tag}",
            "variations": [{"name": "A", "value": "a", "weight": 1.0}]
        }).json()["experiment"]
        put(f"/api/experiments/{exp['id']}", {"status": "running"})

        # running → draft is invalid
        r = put(f"/api/experiments/{exp['id']}", {"status": "draft"})
        assert r.status_code == 400


class TestExperimentFilter:
    """Pattern 3: Experiment filter by status actually works."""

    def test_filter_by_status(self):
        tag = uuid.uuid4().hex[:6]
        exp1 = post("/api/experiments", {
            "name": f"Filt1-{tag}", "key": f"f1-{tag}",
            "variations": [{"name": "A", "value": "a", "weight": 1.0}]
        }).json()["experiment"]
        exp2 = post("/api/experiments", {
            "name": f"Filt2-{tag}", "key": f"f2-{tag}",
            "variations": [{"name": "A", "value": "a", "weight": 1.0}]
        }).json()["experiment"]
        put(f"/api/experiments/{exp2['id']}", {"status": "running"})

        # Filter by draft
        r = get("/api/experiments", params={"status": "draft"})
        exps = r.json()["experiments"]
        for e in exps:
            assert e["status"] == "draft"

        # Filter by running
        r = get("/api/experiments", params={"status": "running"})
        exps = r.json()["experiments"]
        for e in exps:
            assert e["status"] == "running"
        assert any(e["id"] == exp2["id"] for e in exps)


class TestMetricResponseFields:
    """Pattern 1: Metric response with correct camelCase."""

    def test_create_metric_wrapped(self):
        tag = uuid.uuid4().hex[:6]
        r = post("/api/metrics", {"name": f"Met-{tag}", "type": "binomial", "sql": "SELECT 1"})
        assert r.status_code == 201
        data = r.json()
        assert "metric" in data
        m = data["metric"]
        assert "id" in m
        assert m["name"] == f"Met-{tag}"
        assert m["type"] == "binomial"
        assert m["sql"] == "SELECT 1"
        assert "dateCreated" in m
        assert "dateUpdated" in m


class TestSdkConnectionFields:
    """Pattern 1+5: SDK connection generates clientKey."""

    def test_create_sdk_connection_generates_key(self):
        env_id = f"sdk-env-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "SDK Env"})
        r = post("/api/sdk-connections", {"name": f"SDK-{uuid.uuid4().hex[:6]}", "environment": env_id})
        assert r.status_code == 201
        data = r.json()
        assert "connection" in data
        conn = data["connection"]
        assert "id" in conn
        assert "clientKey" in conn
        assert len(conn["clientKey"]) >= 20
        assert conn["environment"] == env_id
        assert "dateCreated" in conn

    def test_sdk_connection_keys_unique(self):
        env_id = f"sdk-u-{uuid.uuid4().hex[:6]}"
        post("/api/environments", {"id": env_id, "name": "SDK U"})
        c1 = post("/api/sdk-connections", {"name": "C1", "environment": env_id}).json()["connection"]
        c2 = post("/api/sdk-connections", {"name": "C2", "environment": env_id}).json()["connection"]
        assert c1["clientKey"] != c2["clientKey"]


class TestDataIsolation:
    """Pattern 6: Different orgs cannot see each other's data."""

    def test_features_isolated(self):
        key = f"iso-{uuid.uuid4().hex[:6]}"
        post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"}, headers=HEADERS_A)
        r = get(f"/api/features/{key}", headers=HEADERS_B)
        assert r.status_code == 404

    def test_projects_isolated(self):
        p = post("/api/projects", {"name": f"IsoP-{uuid.uuid4().hex[:6]}"}, headers=HEADERS_A).json()["project"]
        r = get(f"/api/projects/{p['id']}", headers=HEADERS_B)
        assert r.status_code == 404


class TestFeatureDeletionProtection:
    """Pattern 7: Cannot delete feature referenced by running experiment."""

    def test_cannot_delete_feature_with_running_experiment(self):
        tag = uuid.uuid4().hex[:6]
        feat_key = f"prot-{tag}"
        post("/api/features", {"key": feat_key, "valueType": "boolean", "defaultValue": "false"})
        exp = post("/api/experiments", {
            "name": f"Prot-{tag}", "key": f"protexp-{tag}",
            "featureId": feat_key,
            "variations": [{"name": "A", "value": "a", "weight": 1.0}]
        }).json()["experiment"]
        put(f"/api/experiments/{exp['id']}", {"status": "running"})

        # Try to delete feature
        r = delete(f"/api/features/{feat_key}")
        assert r.status_code == 409


class TestAuthRequired:
    """Pattern 4: Missing auth returns 401, health doesn't need it."""

    def test_health_no_auth(self):
        r = requests.get(f"{BASE_URL}/health", timeout=30)
        assert r.status_code == 200
        assert "status" in r.json()

    def test_features_require_auth(self):
        r = requests.get(f"{BASE_URL}/api/features", timeout=30)
        assert r.status_code == 401

    def test_eval_invalid_key_returns_401(self):
        r = requests.post(f"{BASE_URL}/api/eval/invalid-key-xyz",
                          json={"attributes": {"id": "user1"}}, timeout=30)
        assert r.status_code == 401
