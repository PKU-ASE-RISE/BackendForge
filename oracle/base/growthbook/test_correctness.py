"""
BackendForge — Comprehensive Correctness Tests for GrowthBook Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# Organization API keys — the key IS the org identifier (auto-created on first request)
RUN_ID = uuid.uuid4().hex
ORG_KEY = f"test-org-{RUN_ID}"
ORG2_KEY = f"other-org-{RUN_ID}"

ORG_HEADERS = {
    "X-Api-Key": ORG_KEY,
    "Content-Type": "application/json",
}

ORG2_HEADERS = {
    "X-Api-Key": ORG2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = RUN_ID


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item its own organization namespace."""
    global ORG_KEY, ORG2_KEY, ORG_HEADERS, ORG2_HEADERS, UNIQUE

    UNIQUE = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    ORG_KEY = f"test-org-{UNIQUE}"
    ORG2_KEY = f"other-org-{UNIQUE}"
    ORG_HEADERS = {"X-Api-Key": ORG_KEY, "Content-Type": "application/json"}
    ORG2_HEADERS = {"X-Api-Key": ORG2_KEY, "Content-Type": "application/json"}


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers or ORG_HEADERS, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or ORG_HEADERS, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or ORG_HEADERS, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers or ORG_HEADERS, timeout=30)


# ── FNV-1a helper (must match server) ──

def fnv1a_32(s: str) -> int:
    """FNV-1a 32-bit hash."""
    h = 2166136261
    for byte in s.encode("utf-8"):
        h = h ^ byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


# ════════════════════════════════════════════════════════════════════
# PART 1: Health (no auth required)
# ════════════════════════════════════════════════════════════════════


class TestHealth:

    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_health_no_auth_required(self):
        """Health endpoint should work without any auth header."""
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """Protected endpoints must return 401 without X-Api-Key header."""
        resp = requests.get(f"{BASE_URL}/api/projects", timeout=30)
        assert resp.status_code == 401

    def test_valid_api_key_auto_creates_org(self):
        """A valid API key auto-creates the organization."""
        resp = api_get("/api/projects")
        assert resp.status_code == 200

    def test_data_isolation_between_orgs(self):
        """Org1's data should not be visible to org2."""
        # Create a project in org1
        resp = api_post("/api/projects", {"name": f"isolation-proj-{UNIQUE}"})
        assert resp.status_code == 201

        # Org2 should not see it
        resp2 = api_get("/api/projects", headers=ORG2_HEADERS)
        assert resp2.status_code == 200
        projects = resp2.json()["projects"]
        names = [p["name"] for p in projects]
        assert f"isolation-proj-{UNIQUE}" not in names


# ════════════════════════════════════════════════════════════════════
# PART 3: Projects CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjects:

    def test_create_project(self):
        resp = api_post("/api/projects", {"name": f"proj-{UNIQUE}", "description": "Test project"})
        assert resp.status_code == 201
        data = resp.json()
        assert "project" in data
        project = data["project"]
        assert project["name"] == f"proj-{UNIQUE}"
        assert project["description"] == "Test project"
        assert "id" in project
        assert "dateCreated" in project
        assert "dateUpdated" in project

    def test_create_project_missing_name_returns_400(self):
        resp = api_post("/api/projects", {"description": "no name"})
        assert resp.status_code == 400

    def test_list_projects(self):
        resp = api_get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data
        assert isinstance(data["projects"], list)

    def test_get_project_by_id(self):
        # Create
        resp = api_post("/api/projects", {"name": f"get-proj-{UNIQUE}"})
        assert resp.status_code == 201
        project_id = resp.json()["project"]["id"]

        # Get
        resp = api_get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["project"]["name"] == f"get-proj-{UNIQUE}"

    def test_get_project_not_found(self):
        resp = api_get("/api/projects/nonexistent-id")
        assert resp.status_code == 404

    def test_update_project(self):
        # Create
        resp = api_post("/api/projects", {"name": f"upd-proj-{UNIQUE}"})
        project_id = resp.json()["project"]["id"]

        # Update
        resp = api_put(f"/api/projects/{project_id}", {"name": f"upd-proj-{UNIQUE}-v2", "description": "updated"})
        assert resp.status_code == 200
        assert resp.json()["project"]["name"] == f"upd-proj-{UNIQUE}-v2"
        assert resp.json()["project"]["description"] == "updated"

    def test_delete_project(self):
        # Create
        resp = api_post("/api/projects", {"name": f"del-proj-{UNIQUE}"})
        project_id = resp.json()["project"]["id"]

        # Delete
        resp = api_delete(f"/api/projects/{project_id}")
        assert resp.status_code == 200

        # Verify deleted
        resp = api_get(f"/api/projects/{project_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Environments CRUD
# ════════════════════════════════════════════════════════════════════


class TestEnvironments:

    def test_create_environment(self):
        resp = api_post("/api/environments", {"id": f"env-{UNIQUE}", "name": "Production", "description": "Prod env"})
        assert resp.status_code == 201
        data = resp.json()
        assert "environment" in data
        env = data["environment"]
        assert env["id"] == f"env-{UNIQUE}"
        assert env["name"] == "Production"
        assert "dateCreated" in env

    def test_create_environment_duplicate_id_returns_409(self):
        env_id = f"dup-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "First"})
        resp = api_post("/api/environments", {"id": env_id, "name": "Second"})
        assert resp.status_code == 409

    def test_create_environment_missing_fields_returns_400(self):
        resp = api_post("/api/environments", {"name": "No ID"})
        assert resp.status_code == 400

    def test_list_environments(self):
        resp = api_get("/api/environments")
        assert resp.status_code == 200
        data = resp.json()
        assert "environments" in data
        assert isinstance(data["environments"], list)

    def test_get_environment(self):
        env_id = f"get-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Get Env"})
        resp = api_get(f"/api/environments/{env_id}")
        assert resp.status_code == 200
        assert resp.json()["environment"]["id"] == env_id

    def test_get_environment_not_found(self):
        resp = api_get("/api/environments/nonexistent-env")
        assert resp.status_code == 404

    def test_update_environment(self):
        env_id = f"upd-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Original"})
        resp = api_put(f"/api/environments/{env_id}", {"name": "Updated", "description": "Updated desc"})
        assert resp.status_code == 200
        assert resp.json()["environment"]["name"] == "Updated"
        assert resp.json()["environment"]["description"] == "Updated desc"

    def test_delete_environment(self):
        env_id = f"del-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "To Delete"})
        resp = api_delete(f"/api/environments/{env_id}")
        assert resp.status_code == 200
        resp = api_get(f"/api/environments/{env_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 5: Features CRUD
# ════════════════════════════════════════════════════════════════════


class TestFeatures:

    def test_create_feature(self):
        # Ensure at least one environment exists for the environments map
        api_post("/api/environments", {"id": f"feat-env-{UNIQUE}", "name": "Feature Env"})

        resp = api_post("/api/features", {
            "key": f"feat-{UNIQUE}",
            "valueType": "boolean",
            "defaultValue": "true",
            "description": "A test feature",
            "tags": ["test"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "feature" in data
        feature = data["feature"]
        assert feature["key"] == f"feat-{UNIQUE}"
        assert feature["id"] == f"feat-{UNIQUE}"
        assert feature["valueType"] == "boolean"
        assert feature["defaultValue"] == "true"
        assert feature["description"] == "A test feature"
        assert feature["tags"] == ["test"]
        assert "environments" in feature
        assert "dateCreated" in feature
        assert "dateUpdated" in feature

    def test_create_feature_duplicate_key_returns_409(self):
        key = f"dup-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        resp = api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        assert resp.status_code == 409

    def test_create_feature_missing_fields_returns_400(self):
        resp = api_post("/api/features", {"key": "no-type"})
        assert resp.status_code == 400

    def test_create_feature_has_all_environments(self):
        """Feature should be created with environments map for all existing environments."""
        env_id = f"auto-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Auto Env"})

        resp = api_post("/api/features", {
            "key": f"auto-feat-{UNIQUE}",
            "valueType": "string",
            "defaultValue": "hello",
        })
        assert resp.status_code == 201
        feature = resp.json()["feature"]
        assert env_id in feature["environments"]
        env_data = feature["environments"][env_id]
        assert env_data["enabled"] is True
        assert env_data["rules"] == []

    def test_list_features(self):
        resp = api_get("/api/features")
        assert resp.status_code == 200
        data = resp.json()
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_list_features_filter_by_project(self):
        # Create a project
        proj_resp = api_post("/api/projects", {"name": f"filter-proj-{UNIQUE}"})
        project_id = proj_resp.json()["project"]["id"]

        # Create features with and without project
        api_post("/api/features", {
            "key": f"proj-feat-{UNIQUE}",
            "valueType": "boolean",
            "defaultValue": "true",
            "projectId": project_id,
        })
        api_post("/api/features", {
            "key": f"noproj-feat-{UNIQUE}",
            "valueType": "boolean",
            "defaultValue": "false",
        })

        # Filter by project
        resp = api_get("/api/features", params={"projectId": project_id})
        assert resp.status_code == 200
        features = resp.json()["features"]
        keys = [f["key"] for f in features]
        assert f"proj-feat-{UNIQUE}" in keys
        assert f"noproj-feat-{UNIQUE}" not in keys

    def test_get_feature(self):
        key = f"get-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "number", "defaultValue": "42"})
        resp = api_get(f"/api/features/{key}")
        assert resp.status_code == 200
        assert resp.json()["feature"]["key"] == key
        assert resp.json()["feature"]["defaultValue"] == "42"

    def test_get_feature_not_found(self):
        resp = api_get("/api/features/nonexistent-feature")
        assert resp.status_code == 404

    def test_update_feature(self):
        key = f"upd-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "old"})
        resp = api_put(f"/api/features/{key}", {"defaultValue": "new", "description": "Updated"})
        assert resp.status_code == 200
        feature = resp.json()["feature"]
        assert feature["defaultValue"] == "new"
        assert feature["description"] == "Updated"

    def test_delete_feature(self):
        key = f"del-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})
        resp = api_delete(f"/api/features/{key}")
        assert resp.status_code == 200
        resp = api_get(f"/api/features/{key}")
        assert resp.status_code == 404

    def test_delete_feature_referenced_by_running_experiment_returns_409(self):
        key = f"exp-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})

        # Create experiment referencing this feature
        api_post("/api/experiments", {
            "name": f"exp-{UNIQUE}",
            "key": f"exp-key-{UNIQUE}",
            "variations": [
                {"name": "Control", "value": "false", "weight": 0.5},
                {"name": "Treatment", "value": "true", "weight": 0.5},
            ],
            "featureId": key,
            "status": "draft",
        })
        # Start the experiment
        resp = api_get("/api/experiments")
        experiments = resp.json()["experiments"]
        exp = next(e for e in experiments if e["key"] == f"exp-key-{UNIQUE}")
        api_put(f"/api/experiments/{exp['id']}", {"status": "running"})

        # Try to delete the feature
        resp = api_delete(f"/api/features/{key}")
        assert resp.status_code == 409

    def test_toggle_feature(self):
        env_id = f"toggle-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Toggle Env"})
        key = f"toggle-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})

        # Initially enabled
        resp = api_get(f"/api/features/{key}")
        feature = resp.json()["feature"]
        assert feature["environments"][env_id]["enabled"] is True

        # Toggle off
        resp = api_post(f"/api/features/{key}/toggle/{env_id}")
        assert resp.status_code == 200
        feature = resp.json()["feature"]
        assert feature["environments"][env_id]["enabled"] is False

        # Toggle on again
        resp = api_post(f"/api/features/{key}/toggle/{env_id}")
        assert resp.status_code == 200
        feature = resp.json()["feature"]
        assert feature["environments"][env_id]["enabled"] is True

    def test_toggle_feature_not_found(self):
        resp = api_post("/api/features/nonexistent/toggle/someenv")
        assert resp.status_code == 404

    def test_toggle_env_not_in_feature_returns_404(self):
        key = f"toggle-nf-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})
        resp = api_post(f"/api/features/{key}/toggle/nonexistent-env-xyz")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 6: Feature Rules
# ════════════════════════════════════════════════════════════════════


class TestFeatureRules:

    def setup_method(self):
        """Ensure we have an environment and feature for rule tests."""
        self.env_id = f"rule-env-{UNIQUE}"
        self.feature_key = f"rule-feat-{UNIQUE}"
        # Create environment (may already exist from another test)
        api_post("/api/environments", {"id": self.env_id, "name": "Rule Env"})
        # Create feature (may already exist)
        api_post("/api/features", {"key": self.feature_key, "valueType": "boolean", "defaultValue": "false"})

    def test_list_rules_empty(self):
        resp = api_get(f"/api/features/{self.feature_key}/rules/{self.env_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)

    def test_add_force_rule(self):
        resp = api_post(f"/api/features/{self.feature_key}/rules/{self.env_id}", {
            "type": "force",
            "value": "true",
        })
        assert resp.status_code == 201
        rules = resp.json()["rules"]
        assert len(rules) >= 1
        rule = rules[-1]  # Last added
        assert rule["type"] == "force"
        assert rule["value"] == "true"

    def test_add_rollout_rule(self):
        key = f"rollout-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        resp = api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 0.5,
        })
        assert resp.status_code == 201
        rules = resp.json()["rules"]
        last_rule = rules[-1]
        assert last_rule["type"] == "rollout"
        assert last_rule["coverage"] == 0.5

    def test_add_experiment_rule(self):
        key = f"exprule-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "control"})
        resp = api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "experiment",
            "value": "control",
            "experimentKey": f"exp-{UNIQUE}",
            "variations": [
                {"value": "control", "weight": 0.5},
                {"value": "treatment", "weight": 0.5},
            ],
        })
        assert resp.status_code == 201
        rules = resp.json()["rules"]
        last_rule = rules[-1]
        assert last_rule["type"] == "experiment"
        assert last_rule["experimentKey"] == f"exp-{UNIQUE}"
        assert len(last_rule["variations"]) == 2

    def test_add_rule_with_condition(self):
        key = f"cond-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        resp = api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "true",
            "condition": {"country": {"$eq": "US"}},
        })
        assert resp.status_code == 201
        rules = resp.json()["rules"]
        last_rule = rules[-1]
        assert last_rule["condition"] == {"country": {"$eq": "US"}}

    def test_update_rule(self):
        key = f"upd-rule-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {"type": "force", "value": "true"})

        resp = api_put(f"/api/features/{key}/rules/{self.env_id}/0", {"value": "false"})
        assert resp.status_code == 200
        rules = resp.json()["rules"]
        assert rules[0]["value"] == "false"

    def test_update_rule_invalid_index_returns_404(self):
        key = f"upd-bad-idx-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        resp = api_put(f"/api/features/{key}/rules/{self.env_id}/99", {"value": "true"})
        assert resp.status_code == 404

    def test_delete_rule(self):
        key = f"del-rule-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {"type": "force", "value": "true"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {"type": "force", "value": "false"})

        # Delete first rule
        resp = api_delete(f"/api/features/{key}/rules/{self.env_id}/0")
        assert resp.status_code == 200
        rules = resp.json()["rules"]
        # Should now have only the second rule (which becomes index 0)
        assert len(rules) >= 1
        assert rules[0]["value"] == "false"

    def test_delete_rule_invalid_index_returns_404(self):
        key = f"del-bad-idx-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        resp = api_delete(f"/api/features/{key}/rules/{self.env_id}/99")
        assert resp.status_code == 404

    def test_rules_for_nonexistent_feature_returns_404(self):
        resp = api_get(f"/api/features/nonexistent-xyz/rules/{self.env_id}")
        assert resp.status_code == 404

    def test_rules_for_nonexistent_env_returns_404(self):
        resp = api_get(f"/api/features/{self.feature_key}/rules/nonexistent-env-xyz")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 7: Experiments CRUD
# ════════════════════════════════════════════════════════════════════


class TestExperiments:

    def test_create_experiment(self):
        resp = api_post("/api/experiments", {
            "name": f"exp-{UNIQUE}",
            "key": f"exp-create-{UNIQUE}",
            "description": "Test experiment",
            "hypothesis": "Users will convert more",
            "variations": [
                {"name": "Control", "value": "false", "weight": 0.5},
                {"name": "Treatment", "value": "true", "weight": 0.5},
            ],
            "trafficPercentage": 0.8,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "experiment" in data
        exp = data["experiment"]
        assert exp["name"] == f"exp-{UNIQUE}"
        assert exp["key"] == f"exp-create-{UNIQUE}"
        assert exp["status"] == "draft"
        assert len(exp["variations"]) == 2
        assert exp["trafficPercentage"] == 0.8
        assert "id" in exp
        assert "dateCreated" in exp

    def test_create_experiment_missing_fields_returns_400(self):
        resp = api_post("/api/experiments", {"name": "no key"})
        assert resp.status_code == 400

    def test_list_experiments(self):
        resp = api_get("/api/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert "experiments" in data
        assert isinstance(data["experiments"], list)

    def test_list_experiments_filter_by_status(self):
        # Create a draft experiment
        resp = api_post("/api/experiments", {
            "name": f"status-exp-{UNIQUE}",
            "key": f"status-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        assert resp.status_code == 201

        # Keep a contrasting status in this test's isolated organization.
        running = api_post("/api/experiments", {
            "name": f"status-running-exp-{UNIQUE}",
            "key": f"status-running-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        }).json()["experiment"]
        api_put(f"/api/experiments/{running['id']}", {"status": "running"})

        # Filter by draft
        resp = api_get("/api/experiments", params={"status": "draft"})
        assert resp.status_code == 200
        experiments = resp.json()["experiments"]
        assert all(e["status"] == "draft" for e in experiments)

    def test_get_experiment(self):
        resp = api_post("/api/experiments", {
            "name": f"get-exp-{UNIQUE}",
            "key": f"get-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        exp_id = resp.json()["experiment"]["id"]

        resp = api_get(f"/api/experiments/{exp_id}")
        assert resp.status_code == 200
        assert resp.json()["experiment"]["key"] == f"get-key-{UNIQUE}"

    def test_get_experiment_not_found(self):
        resp = api_get("/api/experiments/nonexistent-exp-id")
        assert resp.status_code == 404

    def test_update_experiment(self):
        resp = api_post("/api/experiments", {
            "name": f"upd-exp-{UNIQUE}",
            "key": f"upd-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        exp_id = resp.json()["experiment"]["id"]

        resp = api_put(f"/api/experiments/{exp_id}", {"description": "Updated desc"})
        assert resp.status_code == 200
        assert resp.json()["experiment"]["description"] == "Updated desc"

    def test_experiment_status_transitions(self):
        """draft → running → stopped are valid. Backwards are not."""
        resp = api_post("/api/experiments", {
            "name": f"trans-exp-{UNIQUE}",
            "key": f"trans-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        exp_id = resp.json()["experiment"]["id"]
        assert resp.json()["experiment"]["status"] == "draft"

        # draft → running
        resp = api_put(f"/api/experiments/{exp_id}", {"status": "running"})
        assert resp.status_code == 200
        assert resp.json()["experiment"]["status"] == "running"

        # running → stopped
        resp = api_put(f"/api/experiments/{exp_id}", {"status": "stopped"})
        assert resp.status_code == 200
        assert resp.json()["experiment"]["status"] == "stopped"

        # stopped → running (invalid)
        resp = api_put(f"/api/experiments/{exp_id}", {"status": "running"})
        assert resp.status_code == 400

        # stopped → draft (invalid)
        resp = api_put(f"/api/experiments/{exp_id}", {"status": "draft"})
        assert resp.status_code == 400

    def test_experiment_status_skip_not_allowed(self):
        """draft → stopped is not a valid transition (must go through running)."""
        resp = api_post("/api/experiments", {
            "name": f"skip-exp-{UNIQUE}",
            "key": f"skip-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        exp_id = resp.json()["experiment"]["id"]

        resp = api_put(f"/api/experiments/{exp_id}", {"status": "stopped"})
        assert resp.status_code == 400

    def test_delete_experiment(self):
        resp = api_post("/api/experiments", {
            "name": f"del-exp-{UNIQUE}",
            "key": f"del-key-{UNIQUE}",
            "variations": [
                {"name": "A", "value": "a", "weight": 0.5},
                {"name": "B", "value": "b", "weight": 0.5},
            ],
        })
        exp_id = resp.json()["experiment"]["id"]

        resp = api_delete(f"/api/experiments/{exp_id}")
        assert resp.status_code == 200
        resp = api_get(f"/api/experiments/{exp_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 8: Metrics CRUD
# ════════════════════════════════════════════════════════════════════


class TestMetrics:

    def test_create_metric(self):
        resp = api_post("/api/metrics", {
            "name": f"metric-{UNIQUE}",
            "type": "binomial",
            "description": "Conversion rate",
            "sql": "SELECT * FROM events",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "metric" in data
        metric = data["metric"]
        assert metric["name"] == f"metric-{UNIQUE}"
        assert metric["type"] == "binomial"
        assert "id" in metric
        assert "dateCreated" in metric

    def test_create_metric_missing_fields_returns_400(self):
        resp = api_post("/api/metrics", {"name": "no type"})
        assert resp.status_code == 400

    def test_create_metric_invalid_type_returns_400(self):
        resp = api_post("/api/metrics", {"name": "bad", "type": "invalid"})
        assert resp.status_code == 400

    def test_list_metrics(self):
        resp = api_get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert isinstance(data["metrics"], list)

    def test_get_metric(self):
        resp = api_post("/api/metrics", {"name": f"get-metric-{UNIQUE}", "type": "count"})
        metric_id = resp.json()["metric"]["id"]

        resp = api_get(f"/api/metrics/{metric_id}")
        assert resp.status_code == 200
        assert resp.json()["metric"]["name"] == f"get-metric-{UNIQUE}"

    def test_get_metric_not_found(self):
        resp = api_get("/api/metrics/nonexistent-metric-id")
        assert resp.status_code == 404

    def test_update_metric(self):
        resp = api_post("/api/metrics", {"name": f"upd-metric-{UNIQUE}", "type": "duration"})
        metric_id = resp.json()["metric"]["id"]

        resp = api_put(f"/api/metrics/{metric_id}", {"description": "Updated", "sql": "SELECT 1"})
        assert resp.status_code == 200
        assert resp.json()["metric"]["description"] == "Updated"
        assert resp.json()["metric"]["sql"] == "SELECT 1"

    def test_delete_metric(self):
        resp = api_post("/api/metrics", {"name": f"del-metric-{UNIQUE}", "type": "revenue"})
        metric_id = resp.json()["metric"]["id"]

        resp = api_delete(f"/api/metrics/{metric_id}")
        assert resp.status_code == 200
        resp = api_get(f"/api/metrics/{metric_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: SDK Connections
# ════════════════════════════════════════════════════════════════════


class TestSdkConnections:

    def test_create_sdk_connection(self):
        env_id = f"sdk-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "SDK Env"})

        resp = api_post("/api/sdk-connections", {
            "name": f"sdk-conn-{UNIQUE}",
            "environment": env_id,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "connection" in data
        conn = data["connection"]
        assert conn["name"] == f"sdk-conn-{UNIQUE}"
        assert conn["environment"] == env_id
        assert "clientKey" in conn
        assert len(conn["clientKey"]) >= 20
        assert "id" in conn
        assert "dateCreated" in conn

    def test_create_sdk_connection_missing_fields_returns_400(self):
        resp = api_post("/api/sdk-connections", {"name": "no env"})
        assert resp.status_code == 400

    def test_list_sdk_connections(self):
        resp = api_get("/api/sdk-connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "connections" in data
        assert isinstance(data["connections"], list)

    def test_get_sdk_connection(self):
        env_id = f"get-sdk-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Get SDK Env"})
        resp = api_post("/api/sdk-connections", {"name": f"get-sdk-{UNIQUE}", "environment": env_id})
        conn_id = resp.json()["connection"]["id"]

        resp = api_get(f"/api/sdk-connections/{conn_id}")
        assert resp.status_code == 200
        assert resp.json()["connection"]["name"] == f"get-sdk-{UNIQUE}"

    def test_get_sdk_connection_not_found(self):
        resp = api_get("/api/sdk-connections/nonexistent-sdk-id")
        assert resp.status_code == 404

    def test_delete_sdk_connection(self):
        env_id = f"del-sdk-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Del SDK Env"})
        resp = api_post("/api/sdk-connections", {"name": f"del-sdk-{UNIQUE}", "environment": env_id})
        conn_id = resp.json()["connection"]["id"]

        resp = api_delete(f"/api/sdk-connections/{conn_id}")
        assert resp.status_code == 200
        resp = api_get(f"/api/sdk-connections/{conn_id}")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 10: SDK Evaluation — Feature Resolution
# ════════════════════════════════════════════════════════════════════


class TestSdkEval:
    """Test the core feature evaluation logic."""

    @pytest.fixture(autouse=True)
    def setup_eval(self):
        """Create a clean environment and SDK connection for eval tests."""
        self.env_id = f"eval-env-{UNIQUE}"
        api_post("/api/environments", {"id": self.env_id, "name": "Eval Env"})

        resp = api_post("/api/sdk-connections", {
            "name": f"eval-sdk-{UNIQUE}",
            "environment": self.env_id,
        })
        self.client_key = resp.json()["connection"]["clientKey"]

    def test_eval_invalid_client_key_returns_401(self):
        resp = requests.post(f"{BASE_URL}/api/eval/invalid-key-xyz", json={"attributes": {}}, timeout=30)
        assert resp.status_code == 401

    def test_eval_no_auth_header_required(self):
        """Eval endpoint authenticates via clientKey, not X-Api-Key."""
        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        assert resp.status_code == 200

    def test_eval_returns_default_value(self):
        """Feature with no rules returns default value."""
        key = f"eval-default-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "features" in data
        assert key in data["features"]
        result = data["features"][key]
        assert result["value"] is True  # boolean "true" → True
        assert result["source"] == "defaultValue"

    def test_eval_disabled_feature_returns_default(self):
        """Disabled feature ignores rules and returns default value."""
        key = f"eval-disabled-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        # Add a force rule
        api_post(f"/api/features/{key}/rules/{self.env_id}", {"type": "force", "value": "true"})
        # Disable the feature
        api_post(f"/api/features/{key}/toggle/{self.env_id}")

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        assert resp.status_code == 200
        result = resp.json()["features"][key]
        assert result["value"] is False  # Returns default, not forced value
        assert result["source"] == "defaultValue"

    def test_eval_force_rule(self):
        """Force rule overrides default value."""
        key = f"eval-force-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "off"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {"type": "force", "value": "on"})

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        assert resp.status_code == 200
        result = resp.json()["features"][key]
        assert result["value"] == "on"
        assert result["source"] == "force"

    def test_eval_force_rule_with_condition_match(self):
        """Force rule with matching condition applies."""
        key = f"eval-cond-match-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "true",
            "condition": {"country": {"$eq": "US"}},
        })

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1", "country": "US"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] is True
        assert result["source"] == "force"

    def test_eval_force_rule_with_condition_no_match(self):
        """Force rule with non-matching condition is skipped."""
        key = f"eval-cond-nomatch-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "true",
            "condition": {"country": {"$eq": "US"}},
        })

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1", "country": "UK"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] is False  # Default value
        assert result["source"] == "defaultValue"

    def test_eval_rollout_rule_full_coverage(self):
        """Rollout with 100% coverage always applies."""
        key = f"eval-rollout100-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 1.0,
        })

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "any-user-123"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] is True
        assert result["source"] == "rollout"

    def test_eval_rollout_rule_zero_coverage(self):
        """Rollout with 0% coverage never applies."""
        key = f"eval-rollout0-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 0.0,
        })

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "any-user-456"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] is False
        assert result["source"] == "defaultValue"

    def test_eval_rollout_deterministic(self):
        """Same user always gets the same rollout result."""
        key = f"eval-rollout-det-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 0.5,
        })

        results = []
        for _ in range(5):
            resp = requests.post(
                f"{BASE_URL}/api/eval/{self.client_key}",
                json={"attributes": {"id": "deterministic-user"}},
                timeout=30,
            )
            results.append(resp.json()["features"][key]["value"])

        # All results should be the same
        assert len(set(str(r) for r in results)) == 1

    def test_eval_rollout_hash_correctness(self):
        """Verify rollout uses correct FNV-1a hash."""
        key = f"eval-rollout-hash-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 0.5,
        })

        # Compute expected result using FNV-1a
        user_id = "hash-test-user"
        hash_val = fnv1a_32(key + user_id) % 10000
        expected_in = hash_val < 5000  # coverage 0.5 * 10000

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": user_id}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        if expected_in:
            assert result["value"] is True
            assert result["source"] == "rollout"
        else:
            assert result["value"] is False
            assert result["source"] == "defaultValue"

    def test_eval_experiment_rule(self):
        """Experiment rule assigns variation based on hash."""
        key = f"eval-exp-{UNIQUE}"
        exp_key = f"eval-exp-key-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "default"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "experiment",
            "value": "default",
            "experimentKey": exp_key,
            "variations": [
                {"value": "control", "weight": 0.5},
                {"value": "treatment", "weight": 0.5},
            ],
        })

        user_id = "experiment-user-1"
        hash_val = fnv1a_32(exp_key + user_id) % 10000
        if hash_val < 5000:
            expected = "control"
        else:
            expected = "treatment"

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": user_id}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] == expected
        assert result["source"] == "experiment"

    def test_eval_experiment_deterministic(self):
        """Same user always gets the same experiment variation."""
        key = f"eval-exp-det-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "default"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "experiment",
            "value": "default",
            "experimentKey": "det-exp",
            "variations": [
                {"value": "A", "weight": 0.5},
                {"value": "B", "weight": 0.5},
            ],
        })

        results = []
        for _ in range(5):
            resp = requests.post(
                f"{BASE_URL}/api/eval/{self.client_key}",
                json={"attributes": {"id": "stable-user"}},
                timeout=30,
            )
            results.append(resp.json()["features"][key]["value"])
        assert len(set(results)) == 1

    def test_eval_rules_first_match_wins(self):
        """Rules are evaluated in order; first match wins."""
        key = f"eval-order-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "default"})
        # Rule 0: force "first" for country=US
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "first",
            "condition": {"country": {"$eq": "US"}},
        })
        # Rule 1: force "second" (no condition, always matches)
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "second",
        })

        # US user should get "first" (first rule matches)
        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1", "country": "US"}},
            timeout=30,
        )
        assert resp.json()["features"][key]["value"] == "first"

        # UK user should get "second" (first rule doesn't match, second matches)
        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1", "country": "UK"}},
            timeout=30,
        )
        assert resp.json()["features"][key]["value"] == "second"

    def test_eval_number_type(self):
        """Number features return numeric values."""
        key = f"eval-num-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "number", "defaultValue": "42"})

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] == 42

    def test_eval_json_type(self):
        """JSON features return parsed JSON values."""
        key = f"eval-json-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "json", "defaultValue": '{"color":"red"}'})

        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        result = resp.json()["features"][key]
        assert result["value"] == {"color": "red"}


# ════════════════════════════════════════════════════════════════════
# PART 11: Targeting Conditions
# ════════════════════════════════════════════════════════════════════


class TestTargetingConditions:
    """Test all targeting condition operators."""

    @pytest.fixture(autouse=True)
    def setup_targeting(self):
        self.env_id = f"target-env-{UNIQUE}"
        api_post("/api/environments", {"id": self.env_id, "name": "Target Env"})
        resp = api_post("/api/sdk-connections", {
            "name": f"target-sdk-{UNIQUE}",
            "environment": self.env_id,
        })
        self.client_key = resp.json()["connection"]["clientKey"]

    def _create_feature_with_condition(self, suffix, condition):
        key = f"target-{suffix}-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{self.env_id}", {
            "type": "force",
            "value": "true",
            "condition": condition,
        })
        return key

    def _eval(self, key, attributes):
        resp = requests.post(
            f"{BASE_URL}/api/eval/{self.client_key}",
            json={"attributes": attributes},
            timeout=30,
        )
        return resp.json()["features"][key]["value"]

    def test_eq_operator(self):
        key = self._create_feature_with_condition("eq", {"plan": {"$eq": "pro"}})
        assert self._eval(key, {"id": "u1", "plan": "pro"}) is True
        assert self._eval(key, {"id": "u1", "plan": "free"}) is False

    def test_ne_operator(self):
        key = self._create_feature_with_condition("ne", {"plan": {"$ne": "free"}})
        assert self._eval(key, {"id": "u1", "plan": "pro"}) is True
        assert self._eval(key, {"id": "u1", "plan": "free"}) is False

    def test_gt_operator(self):
        key = self._create_feature_with_condition("gt", {"age": {"$gt": 18}})
        assert self._eval(key, {"id": "u1", "age": 25}) is True
        assert self._eval(key, {"id": "u1", "age": 18}) is False
        assert self._eval(key, {"id": "u1", "age": 10}) is False

    def test_lt_operator(self):
        key = self._create_feature_with_condition("lt", {"age": {"$lt": 18}})
        assert self._eval(key, {"id": "u1", "age": 10}) is True
        assert self._eval(key, {"id": "u1", "age": 18}) is False
        assert self._eval(key, {"id": "u1", "age": 25}) is False

    def test_gte_operator(self):
        key = self._create_feature_with_condition("gte", {"age": {"$gte": 18}})
        assert self._eval(key, {"id": "u1", "age": 18}) is True
        assert self._eval(key, {"id": "u1", "age": 25}) is True
        assert self._eval(key, {"id": "u1", "age": 17}) is False

    def test_lte_operator(self):
        key = self._create_feature_with_condition("lte", {"age": {"$lte": 18}})
        assert self._eval(key, {"id": "u1", "age": 18}) is True
        assert self._eval(key, {"id": "u1", "age": 10}) is True
        assert self._eval(key, {"id": "u1", "age": 19}) is False

    def test_in_operator(self):
        key = self._create_feature_with_condition("in", {"country": {"$in": ["US", "CA", "UK"]}})
        assert self._eval(key, {"id": "u1", "country": "US"}) is True
        assert self._eval(key, {"id": "u1", "country": "CA"}) is True
        assert self._eval(key, {"id": "u1", "country": "DE"}) is False

    def test_nin_operator(self):
        key = self._create_feature_with_condition("nin", {"country": {"$nin": ["CN", "RU"]}})
        assert self._eval(key, {"id": "u1", "country": "US"}) is True
        assert self._eval(key, {"id": "u1", "country": "CN"}) is False

    def test_regex_operator(self):
        key = self._create_feature_with_condition("regex", {"email": {"$regex": ".*@example\\.com$"}})
        assert self._eval(key, {"id": "u1", "email": "user@example.com"}) is True
        assert self._eval(key, {"id": "u1", "email": "user@other.com"}) is False

    def test_exists_operator(self):
        key = self._create_feature_with_condition("exists", {"premium": {"$exists": True}})
        assert self._eval(key, {"id": "u1", "premium": True}) is True
        assert self._eval(key, {"id": "u1"}) is False

    def test_exists_false_operator(self):
        key = self._create_feature_with_condition("nexists", {"premium": {"$exists": False}})
        assert self._eval(key, {"id": "u1"}) is True
        assert self._eval(key, {"id": "u1", "premium": True}) is False

    def test_multiple_conditions_and(self):
        """Multiple attributes in condition are ANDed."""
        key = self._create_feature_with_condition("multi", {
            "country": {"$eq": "US"},
            "age": {"$gte": 18},
        })
        assert self._eval(key, {"id": "u1", "country": "US", "age": 25}) is True
        assert self._eval(key, {"id": "u1", "country": "US", "age": 15}) is False
        assert self._eval(key, {"id": "u1", "country": "UK", "age": 25}) is False


# ════════════════════════════════════════════════════════════════════
# PART 12: Environment deletion cascade
# ════════════════════════════════════════════════════════════════════


class TestEnvironmentCascade:

    def test_delete_environment_removes_from_features(self):
        """Deleting an environment removes it from feature environments maps."""
        env_id = f"cascade-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Cascade Env"})

        key = f"cascade-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "true"})

        # Verify env is in feature
        resp = api_get(f"/api/features/{key}")
        assert env_id in resp.json()["feature"]["environments"]

        # Delete environment
        api_delete(f"/api/environments/{env_id}")

        # Verify env is removed from feature
        resp = api_get(f"/api/features/{key}")
        assert env_id not in resp.json()["feature"]["environments"]


# ════════════════════════════════════════════════════════════════════
# PART 13: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_feature_value_types(self):
        """All value types are handled correctly."""
        # Boolean
        resp = api_post("/api/features", {"key": f"vt-bool-{UNIQUE}", "valueType": "boolean", "defaultValue": "false"})
        assert resp.status_code == 201

        # String
        resp = api_post("/api/features", {"key": f"vt-str-{UNIQUE}", "valueType": "string", "defaultValue": "hello"})
        assert resp.status_code == 201

        # Number
        resp = api_post("/api/features", {"key": f"vt-num-{UNIQUE}", "valueType": "number", "defaultValue": "3.14"})
        assert resp.status_code == 201

        # JSON
        resp = api_post("/api/features", {"key": f"vt-json-{UNIQUE}", "valueType": "json", "defaultValue": '{"a":1}'})
        assert resp.status_code == 201

    def test_experiment_with_unequal_weights(self):
        """Experiment with 90/10 split assigns correctly."""
        key = f"eval-90-10-{UNIQUE}"
        exp_key = f"eval-90-10-key-{UNIQUE}"

        env_id = f"unequal-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Unequal Env"})

        api_post("/api/features", {"key": key, "valueType": "string", "defaultValue": "default"})
        resp = api_post("/api/sdk-connections", {"name": f"unequal-sdk-{UNIQUE}", "environment": env_id})
        client_key = resp.json()["connection"]["clientKey"]

        api_post(f"/api/features/{key}/rules/{env_id}", {
            "type": "experiment",
            "value": "default",
            "experimentKey": exp_key,
            "variations": [
                {"value": "control", "weight": 0.9},
                {"value": "treatment", "weight": 0.1},
            ],
        })

        # Test with a specific user and verify against expected hash
        user_id = "weight-test-user"
        hash_val = fnv1a_32(exp_key + user_id) % 10000
        if hash_val < 9000:
            expected = "control"
        else:
            expected = "treatment"

        resp = requests.post(
            f"{BASE_URL}/api/eval/{client_key}",
            json={"attributes": {"id": user_id}},
            timeout=30,
        )
        assert resp.json()["features"][key]["value"] == expected

    def test_multiple_features_in_eval(self):
        """Eval returns all features for the environment."""
        env_id = f"multi-feat-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "Multi Feat Env"})
        resp = api_post("/api/sdk-connections", {"name": f"multi-sdk-{UNIQUE}", "environment": env_id})
        client_key = resp.json()["connection"]["clientKey"]

        key1 = f"multi-f1-{UNIQUE}"
        key2 = f"multi-f2-{UNIQUE}"
        api_post("/api/features", {"key": key1, "valueType": "boolean", "defaultValue": "true"})
        api_post("/api/features", {"key": key2, "valueType": "string", "defaultValue": "hello"})

        resp = requests.post(
            f"{BASE_URL}/api/eval/{client_key}",
            json={"attributes": {"id": "user1"}},
            timeout=30,
        )
        features = resp.json()["features"]
        assert key1 in features
        assert key2 in features
        assert features[key1]["value"] is True
        assert features[key2]["value"] == "hello"

    def test_rollout_with_condition(self):
        """Rollout rule with condition: condition must match AND hash must pass."""
        env_id = f"rc-env-{UNIQUE}"
        api_post("/api/environments", {"id": env_id, "name": "RC Env"})
        resp = api_post("/api/sdk-connections", {"name": f"rc-sdk-{UNIQUE}", "environment": env_id})
        client_key = resp.json()["connection"]["clientKey"]

        key = f"rc-feat-{UNIQUE}"
        api_post("/api/features", {"key": key, "valueType": "boolean", "defaultValue": "false"})
        api_post(f"/api/features/{key}/rules/{env_id}", {
            "type": "rollout",
            "value": "true",
            "coverage": 1.0,
            "condition": {"country": {"$eq": "US"}},
        })

        # US user with 100% coverage → should get true
        resp = requests.post(
            f"{BASE_URL}/api/eval/{client_key}",
            json={"attributes": {"id": "user1", "country": "US"}},
            timeout=30,
        )
        assert resp.json()["features"][key]["value"] is True

        # UK user → condition fails, default value
        resp = requests.post(
            f"{BASE_URL}/api/eval/{client_key}",
            json={"attributes": {"id": "user1", "country": "UK"}},
            timeout=30,
        )
        assert resp.json()["features"][key]["value"] is False
