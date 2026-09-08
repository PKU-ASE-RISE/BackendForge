"""
BackendForge — L3 Workflow Tests for GrowthBook Task

Multi-step adversarial tests: feature evaluation with force/rollout/experiment rules,
environment cascade, targeting conditions, SDK eval endpoint.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-Api-Key": f"org-{uuid.uuid4().hex[:12]}", "Content-Type": "application/json"}


def api(method, path, headers, json=None, params=None):
    return getattr(requests, method)(
        f"{BASE_URL}{path}", json=json, params=params, headers=headers, timeout=30
    )


class TestForceRuleEvaluation:
    """Pattern 5: Force rule returns forced value via SDK eval."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()
        # Create environment
        self.env_id = f"prod-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": self.env_id, "name": "Production"})

    def test_force_rule_overrides_default(self):
        """Feature with force rule returns forced value, not default."""
        feat_key = f"force-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "string", "defaultValue": "off"
        })
        # Add force rule
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "force", "value": "on"
        })
        # Create SDK connection
        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "ProdSDK", "environment": self.env_id
        }).json()["connection"]

        # Eval
        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "user123"}}, timeout=30)
        assert r.status_code == 200
        features = r.json()["features"]
        assert feat_key in features
        assert features[feat_key]["value"] == "on"
        assert features[feat_key]["source"] == "force"

    def test_disabled_feature_returns_default(self):
        """If feature is disabled in env, returns defaultValue."""
        feat_key = f"dis-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "false"
        })
        # Add force rule
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "force", "value": "true"
        })
        # Disable feature in this env
        api("post", f"/api/features/{feat_key}/toggle/{self.env_id}", self.h)

        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "DisSDK", "environment": self.env_id
        }).json()["connection"]

        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "user1"}}, timeout=30)
        features = r.json()["features"]
        assert feat_key in features
        # Disabled → defaultValue
        assert features[feat_key]["source"] == "defaultValue"


class TestConditionTargeting:
    """Pattern 5: Force rule with condition targeting."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()
        self.env_id = f"cond-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": self.env_id, "name": "Cond Env"})

    def test_condition_eq_matches(self):
        """Rule with $eq condition only triggers for matching users."""
        feat_key = f"condf-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "string", "defaultValue": "default"
        })
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "force", "value": "premium",
            "condition": {"plan": {"$eq": "pro"}}
        })

        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "CondSDK", "environment": self.env_id
        }).json()["connection"]

        # Matching user
        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "u1", "plan": "pro"}}, timeout=30)
        assert r.json()["features"][feat_key]["value"] == "premium"

        # Non-matching user
        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "u2", "plan": "free"}}, timeout=30)
        assert r.json()["features"][feat_key]["value"] == "default"


class TestEnvironmentDeletionCascade:
    """Pattern 7: Deleting environment removes it from features."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_delete_env_removes_from_features(self):
        """After deleting an environment, it's gone from feature environments map."""
        env1 = f"keep-{uuid.uuid4().hex[:6]}"
        env2 = f"del-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": env1, "name": "Keep"})
        api("post", "/api/environments", self.h, json={"id": env2, "name": "Delete"})

        feat_key = f"envdel-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "true"
        })

        # Verify both envs present
        feat = api("get", f"/api/features/{feat_key}", self.h).json()["feature"]
        assert env1 in feat["environments"]
        assert env2 in feat["environments"]

        # Delete env2
        r = api("delete", f"/api/environments/{env2}", self.h)
        assert r.status_code == 200

        # env2 should be gone from feature
        feat = api("get", f"/api/features/{feat_key}", self.h).json()["feature"]
        assert env1 in feat["environments"]
        assert env2 not in feat["environments"]


class TestExperimentLifecycle:
    """Pattern 5+8: Full experiment lifecycle with status transitions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_experiment_full_lifecycle(self):
        """Create → start → stop, verify each state."""
        tag = uuid.uuid4().hex[:6]
        feat_key = f"lcfeat-{tag}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "false"
        })

        # Create experiment
        exp = api("post", "/api/experiments", self.h, json={
            "name": f"LC-{tag}", "key": f"lc-key-{tag}",
            "featureId": feat_key,
            "variations": [
                {"name": "Control", "value": "false", "weight": 0.5},
                {"name": "Variant", "value": "true", "weight": 0.5}
            ]
        }).json()["experiment"]
        assert exp["status"] == "draft"
        assert exp["featureId"] == feat_key

        # Cannot go backwards to draft from draft (already draft)
        # Start experiment
        r = api("put", f"/api/experiments/{exp['id']}", self.h, json={"status": "running"})
        assert r.status_code == 200
        assert r.json()["experiment"]["status"] == "running"

        # Cannot go back to draft
        r = api("put", f"/api/experiments/{exp['id']}", self.h, json={"status": "draft"})
        assert r.status_code == 400

        # Stop
        r = api("put", f"/api/experiments/{exp['id']}", self.h, json={"status": "stopped"})
        assert r.status_code == 200
        assert r.json()["experiment"]["status"] == "stopped"

        # Cannot go back to running
        r = api("put", f"/api/experiments/{exp['id']}", self.h, json={"status": "running"})
        assert r.status_code == 400


class TestFeatureWithMultipleRules:
    """Pattern 5: Multiple rules, first match wins."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()
        self.env_id = f"multi-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": self.env_id, "name": "Multi"})

    def test_first_matching_rule_wins(self):
        """Two force rules: first with condition, second unconditional. Correct one wins."""
        feat_key = f"mrf-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "string", "defaultValue": "default"
        })
        # Rule 0: conditional
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "force", "value": "admin-value",
            "condition": {"role": {"$eq": "admin"}}
        })
        # Rule 1: unconditional catch-all
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "force", "value": "everyone-value"
        })

        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "MultiSDK", "environment": self.env_id
        }).json()["connection"]

        # Admin user → rule 0 matches
        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "u1", "role": "admin"}}, timeout=30)
        assert r.json()["features"][feat_key]["value"] == "admin-value"

        # Normal user → rule 0 doesn't match, rule 1 catches
        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "u2", "role": "user"}}, timeout=30)
        assert r.json()["features"][feat_key]["value"] == "everyone-value"


class TestRolloutRule:
    """Pattern 5: Rollout rule returns value based on user hash."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()
        self.env_id = f"roll-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": self.env_id, "name": "Rollout"})

    def test_rollout_100_percent(self):
        """100% rollout always returns the rule value."""
        feat_key = f"roll100-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "false"
        })
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "rollout", "value": "true", "coverage": 1.0
        })
        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "Roll100", "environment": self.env_id
        }).json()["connection"]

        # All users should get true
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                              json={"attributes": {"id": f"user-{i}"}}, timeout=30)
            assert r.json()["features"][feat_key]["value"] == True

    def test_rollout_0_percent(self):
        """0% rollout always returns default."""
        feat_key = f"roll0-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "false"
        })
        api("post", f"/api/features/{feat_key}/rules/{self.env_id}", self.h, json={
            "type": "rollout", "value": "true", "coverage": 0.0
        })
        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "Roll0", "environment": self.env_id
        }).json()["connection"]

        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                              json={"attributes": {"id": f"user-{i}"}}, timeout=30)
            # 0% rollout → default value
            assert r.json()["features"][feat_key]["value"] == False


class TestSdkEvalMultipleFeatures:
    """Pattern 2+5: Eval returns all features for the connection's environment."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()
        self.env_id = f"sdk-multi-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": self.env_id, "name": "SDK Multi"})

    def test_eval_returns_all_features(self):
        """Multiple features created, eval returns all of them."""
        keys = []
        for i in range(3):
            key = f"multi-{uuid.uuid4().hex[:6]}-{i}"
            api("post", "/api/features", self.h, json={
                "key": key, "valueType": "boolean", "defaultValue": "true"
            })
            keys.append(key)

        conn = api("post", "/api/sdk-connections", self.h, json={
            "name": "MultiF", "environment": self.env_id
        }).json()["connection"]

        r = requests.post(f"{BASE_URL}/api/eval/{conn['clientKey']}",
                          json={"attributes": {"id": "u1"}}, timeout=30)
        assert r.status_code == 200
        features = r.json()["features"]
        for key in keys:
            assert key in features
            assert features[key]["value"] == True


class TestFeatureProjectFilter:
    """Pattern 3: Feature filter by projectId."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_filter_features_by_project(self):
        proj = api("post", "/api/projects", self.h, json={"name": f"FP-{uuid.uuid4().hex[:6]}"}).json()["project"]
        # Feature in project
        key_in = f"inproj-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": key_in, "valueType": "boolean", "defaultValue": "true", "projectId": proj["id"]
        })
        # Feature not in project
        key_out = f"outproj-{uuid.uuid4().hex[:6]}"
        api("post", "/api/features", self.h, json={
            "key": key_out, "valueType": "boolean", "defaultValue": "false"
        })

        # Filter by project
        r = api("get", "/api/features", self.h, params={"projectId": proj["id"]})
        features = r.json()["features"]
        feat_keys = [f["key"] for f in features]
        assert key_in in feat_keys
        assert key_out not in feat_keys


class TestDefaultEnvironmentsOnFeatureCreate:
    """Pattern 5: New feature gets all existing environments."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.h = make_headers()

    def test_feature_gets_all_envs(self):
        """Creating a feature after environments exist includes all envs."""
        env1 = f"ae1-{uuid.uuid4().hex[:6]}"
        env2 = f"ae2-{uuid.uuid4().hex[:6]}"
        api("post", "/api/environments", self.h, json={"id": env1, "name": "Env1"})
        api("post", "/api/environments", self.h, json={"id": env2, "name": "Env2"})

        feat_key = f"allenv-{uuid.uuid4().hex[:6]}"
        r = api("post", "/api/features", self.h, json={
            "key": feat_key, "valueType": "boolean", "defaultValue": "true"
        })
        feat = r.json()["feature"]
        assert env1 in feat["environments"]
        assert env2 in feat["environments"]
        assert feat["environments"][env1]["enabled"] is True
        assert feat["environments"][env2]["enabled"] is True
        assert feat["environments"][env1]["rules"] == []
        assert feat["environments"][env2]["rules"] == []
