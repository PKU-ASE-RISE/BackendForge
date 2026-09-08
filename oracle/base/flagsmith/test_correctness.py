"""
BackendForge — Comprehensive Correctness Tests for Flagsmith Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# Organization API keys
ORG_KEY = f"org-{uuid.uuid4().hex[:8]}"
ORG2_KEY = f"org2-{uuid.uuid4().hex[:8]}"

HEADERS = {
    "X-Api-Key": ORG_KEY,
    "Content-Type": "application/json",
}

HEADERS2 = {
    "X-Api-Key": ORG2_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def _expect_status(response, expected_status):
    assert response.status_code == expected_status, (
        f"Expected HTTP {expected_status}, got {response.status_code}: {response.text}"
    )
    return response


def api_get(path, params=None, headers=None, expected_status=None):
    response = requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def api_post(path, json_data=None, headers=None, expected_status=None):
    response = requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def api_put(path, json_data=None, headers=None, expected_status=None):
    response = requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def api_delete(path, headers=None, expected_status=None):
    response = requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


# ── Fixtures ──

@pytest.fixture(autouse=True)
def isolate_test_organization():
    global ORG_KEY, ORG2_KEY, UNIQUE

    token = uuid.uuid4().hex
    ORG_KEY = f"org-{token}"
    ORG2_KEY = f"org2-{token}"
    UNIQUE = token[:8]
    HEADERS["X-Api-Key"] = ORG_KEY
    HEADERS2["X-Api-Key"] = ORG2_KEY


def create_project(name=None, headers=None):
    name = name or f"Project-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/projects", {"name": name}, headers=headers)
    assert resp.status_code == 201, f"Failed to create project: {resp.text}"
    return resp.json()


def create_environment(project_id, name=None, headers=None):
    name = name or f"Env-{uuid.uuid4().hex[:8]}"
    resp = api_post(f"/api/projects/{project_id}/environments", {"name": name}, headers=headers)
    assert resp.status_code == 201, f"Failed to create environment: {resp.text}"
    return resp.json()


def create_feature(project_id, name=None, feature_type="FLAG", default_enabled=False, initial_value="", headers=None):
    name = name or f"feature-{uuid.uuid4().hex[:8]}"
    resp = api_post(f"/api/projects/{project_id}/features", {
        "name": name,
        "type": feature_type,
        "defaultEnabled": default_enabled,
        "initialValue": initial_value,
    }, headers=headers)
    assert resp.status_code == 201, f"Failed to create feature: {resp.text}"
    return resp.json()


def create_segment(project_id, name=None, match_type="ALL", rules=None, headers=None):
    name = name or f"segment-{uuid.uuid4().hex[:8]}"
    rules = rules or []
    resp = api_post(f"/api/projects/{project_id}/segments", {
        "name": name,
        "matchType": match_type,
        "rules": rules,
    }, headers=headers)
    assert resp.status_code == 201, f"Failed to create segment: {resp.text}"
    return resp.json()


def create_identity(environment_id, identifier=None, headers=None):
    identifier = identifier or f"user-{uuid.uuid4().hex[:8]}"
    resp = api_post(f"/api/environments/{environment_id}/identities", {
        "identifier": identifier,
    }, headers=headers)
    assert resp.status_code == 201, f"Failed to create identity: {resp.text}"
    return resp.json()


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════


class TestAuthentication:

    def test_missing_header_returns_401(self):
        """Requests without X-Api-Key should return 401."""
        resp = requests.get(f"{BASE_URL}/api/projects", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_environments(self):
        resp = requests.get(f"{BASE_URL}/api/environments/1", timeout=30)
        assert resp.status_code == 401

    def test_missing_header_on_features(self):
        resp = requests.get(f"{BASE_URL}/api/projects/1/features", timeout=30)
        assert resp.status_code == 401

    def test_valid_key_works(self):
        """Any non-empty key should work."""
        resp = api_get("/api/projects")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Project CRUD
# ════════════════════════════════════════════════════════════════════


class TestProjectCRUD:

    def test_create_project(self):
        resp = api_post("/api/projects", {"name": f"TestProj-{UNIQUE}"})
        assert resp.status_code == 201
        project = resp.json()
        assert project["name"] == f"TestProj-{UNIQUE}"
        assert "id" in project
        assert "createdAt" in project

    def test_list_projects(self):
        name = f"ListProj-{UNIQUE}"
        api_post("/api/projects", {"name": name})
        resp = api_get("/api/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert isinstance(projects, list)
        names = [p["name"] for p in projects]
        assert name in names

    def test_get_project(self):
        project = create_project()
        resp = api_get(f"/api/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == project["name"]

    def test_update_project(self):
        project = create_project()
        new_name = f"Updated-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/projects/{project['id']}", {"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    def test_delete_project(self):
        project = create_project()
        resp = api_delete(f"/api/projects/{project['id']}")
        assert resp.status_code == 204
        # Verify gone
        get_resp = api_get(f"/api/projects/{project['id']}", expected_status=404)
        assert get_resp.status_code == 404

    def test_get_nonexistent_project(self):
        resp = api_get("/api/projects/999999", expected_status=404)
        assert resp.status_code == 404

    def test_duplicate_project_name(self):
        name = f"DupProj-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/api/projects", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post("/api/projects", {"name": name}, expected_status=409)
        assert resp2.status_code == 409


# ════════════════════════════════════════════════════════════════════
# PART 3: Environment CRUD
# ════════════════════════════════════════════════════════════════════


class TestEnvironmentCRUD:

    def test_create_environment(self):
        project = create_project()
        resp = api_post(f"/api/projects/{project['id']}/environments", {"name": "Development"})
        assert resp.status_code == 201
        env = resp.json()
        assert env["name"] == "Development"
        assert "id" in env
        assert "apiKey" in env
        assert len(env["apiKey"]) >= 16
        assert env["projectId"] == project["id"]
        assert "createdAt" in env

    def test_list_environments(self):
        project = create_project()
        create_environment(project["id"], "Dev")
        create_environment(project["id"], "Staging")
        resp = api_get(f"/api/projects/{project['id']}/environments")
        assert resp.status_code == 200
        envs = resp.json()
        assert len(envs) == 2
        names = [e["name"] for e in envs]
        assert "Dev" in names
        assert "Staging" in names

    def test_get_environment(self):
        project = create_project()
        env = create_environment(project["id"])
        resp = api_get(f"/api/environments/{env['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == env["name"]

    def test_update_environment(self):
        project = create_project()
        env = create_environment(project["id"])
        new_name = f"Renamed-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/environments/{env['id']}", {"name": new_name})
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name
        # apiKey should not change
        assert resp.json()["apiKey"] == env["apiKey"]

    def test_delete_environment(self):
        project = create_project()
        env = create_environment(project["id"])
        resp = api_delete(f"/api/environments/{env['id']}")
        assert resp.status_code == 204
        get_resp = api_get(f"/api/environments/{env['id']}", expected_status=404)
        assert get_resp.status_code == 404

    def test_duplicate_environment_name(self):
        project = create_project()
        name = f"DupEnv-{uuid.uuid4().hex[:8]}"
        resp1 = api_post(f"/api/projects/{project['id']}/environments", {"name": name})
        assert resp1.status_code == 201
        resp2 = api_post(
            f"/api/projects/{project['id']}/environments", {"name": name}, expected_status=409
        )
        assert resp2.status_code == 409

    def test_environment_for_nonexistent_project(self):
        resp = api_post(
            "/api/projects/999999/environments", {"name": "Ghost"}, expected_status=404
        )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 4: Feature CRUD
# ════════════════════════════════════════════════════════════════════


class TestFeatureCRUD:

    def test_create_feature_flag(self):
        project = create_project()
        resp = api_post(f"/api/projects/{project['id']}/features", {
            "name": "dark_mode",
            "type": "FLAG",
            "defaultEnabled": True,
            "initialValue": "",
        })
        assert resp.status_code == 201
        feature = resp.json()
        assert feature["name"] == "dark_mode"
        assert feature["type"] == "FLAG"
        assert feature["defaultEnabled"] is True
        assert feature["initialValue"] == ""
        assert feature["projectId"] == project["id"]
        assert "id" in feature
        assert "createdAt" in feature

    def test_create_feature_config(self):
        project = create_project()
        resp = api_post(f"/api/projects/{project['id']}/features", {
            "name": "max_items",
            "type": "CONFIG",
            "defaultEnabled": True,
            "initialValue": "50",
        })
        assert resp.status_code == 201
        feature = resp.json()
        assert feature["type"] == "CONFIG"
        assert feature["initialValue"] == "50"

    def test_list_features(self):
        project = create_project()
        create_feature(project["id"], "feature-a")
        create_feature(project["id"], "feature-b")
        resp = api_get(f"/api/projects/{project['id']}/features")
        assert resp.status_code == 200
        features = resp.json()
        assert len(features) == 2

    def test_get_feature(self):
        project = create_project()
        feature = create_feature(project["id"])
        resp = api_get(f"/api/projects/{project['id']}/features/{feature['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == feature["name"]

    def test_update_feature(self):
        project = create_project()
        feature = create_feature(project["id"])
        new_name = f"updated-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/projects/{project['id']}/features/{feature['id']}", {
            "name": new_name,
            "type": "CONFIG",
            "defaultEnabled": True,
            "initialValue": "100",
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["type"] == "CONFIG"
        assert updated["initialValue"] == "100"

    def test_delete_feature(self):
        project = create_project()
        feature = create_feature(project["id"])
        resp = api_delete(f"/api/projects/{project['id']}/features/{feature['id']}")
        assert resp.status_code == 204
        get_resp = api_get(
            f"/api/projects/{project['id']}/features/{feature['id']}", expected_status=404
        )
        assert get_resp.status_code == 404

    def test_duplicate_feature_name(self):
        project = create_project()
        name = f"dup-feature-{uuid.uuid4().hex[:8]}"
        resp1 = api_post(f"/api/projects/{project['id']}/features", {
            "name": name, "type": "FLAG",
        })
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/projects/{project['id']}/features", {
            "name": name, "type": "FLAG",
        }, expected_status=409)
        assert resp2.status_code == 409

    def test_feature_default_values(self):
        """defaultEnabled defaults to false, initialValue to empty string."""
        project = create_project()
        resp = api_post(f"/api/projects/{project['id']}/features", {
            "name": f"minimal-{uuid.uuid4().hex[:8]}",
            "type": "FLAG",
        })
        assert resp.status_code == 201
        feature = resp.json()
        assert feature["defaultEnabled"] is False
        assert feature["initialValue"] == ""


# ════════════════════════════════════════════════════════════════════
# PART 5: Feature States
# ════════════════════════════════════════════════════════════════════


class TestFeatureStates:

    def test_auto_create_feature_states_for_existing_envs(self):
        """Creating a feature should auto-create feature states for all existing environments."""
        project = create_project()
        env1 = create_environment(project["id"], "Dev")
        env2 = create_environment(project["id"], "Prod")

        feature = create_feature(project["id"], default_enabled=True, initial_value="hello")

        # Both environments should have feature states
        resp1 = api_get(f"/api/environments/{env1['id']}/featurestates")
        assert resp1.status_code == 200
        states1 = resp1.json()
        feature_ids_1 = [s["featureId"] for s in states1]
        assert feature["id"] in feature_ids_1

        resp2 = api_get(f"/api/environments/{env2['id']}/featurestates")
        states2 = resp2.json()
        feature_ids_2 = [s["featureId"] for s in states2]
        assert feature["id"] in feature_ids_2

    def test_auto_create_feature_states_for_new_env(self):
        """Creating an environment should auto-create feature states for all existing features."""
        project = create_project()
        feature = create_feature(project["id"], default_enabled=True, initial_value="42")

        env = create_environment(project["id"], "New Env")
        resp = api_get(f"/api/environments/{env['id']}/featurestates")
        assert resp.status_code == 200
        states = resp.json()
        assert len(states) >= 1
        fs = next(s for s in states if s["featureId"] == feature["id"])
        assert fs["enabled"] is True
        assert fs["value"] == "42"

    def test_feature_state_has_correct_fields(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], "test-fs-fields", default_enabled=False, initial_value="val")
        resp = api_get(f"/api/environments/{env['id']}/featurestates")
        states = resp.json()
        fs = next(s for s in states if s["featureId"] == feature["id"])
        assert "id" in fs
        assert fs["featureName"] == "test-fs-fields"
        assert fs["environmentId"] == env["id"]
        assert fs["enabled"] is False
        assert fs["value"] == "val"

    def test_update_feature_state(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])

        # Get the feature state
        resp = api_get(f"/api/environments/{env['id']}/featurestates")
        states = resp.json()
        fs = next(s for s in states if s["featureId"] == feature["id"])

        # Update it
        update_resp = api_put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True,
            "value": "new_value",
        })
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["enabled"] is True
        assert updated["value"] == "new_value"

    def test_get_single_feature_state(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        resp = api_get(f"/api/environments/{env['id']}/featurestates")
        states = resp.json()
        fs = next(s for s in states if s["featureId"] == feature["id"])

        get_resp = api_get(f"/api/environments/{env['id']}/featurestates/{fs['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == fs["id"]

    def test_feature_states_different_per_environment(self):
        """Feature states can be independently set per environment."""
        project = create_project()
        env_dev = create_environment(project["id"], "Dev")
        env_prod = create_environment(project["id"], "Prod")
        feature = create_feature(project["id"], default_enabled=False)

        # Get feature states
        dev_states = api_get(f"/api/environments/{env_dev['id']}/featurestates").json()
        prod_states = api_get(f"/api/environments/{env_prod['id']}/featurestates").json()

        dev_fs = next(s for s in dev_states if s["featureId"] == feature["id"])
        prod_fs = next(s for s in prod_states if s["featureId"] == feature["id"])

        # Enable in dev only
        api_put(f"/api/environments/{env_dev['id']}/featurestates/{dev_fs['id']}", {
            "enabled": True, "value": "dev_value",
        })

        # Verify dev is enabled, prod is not
        dev_updated = api_get(f"/api/environments/{env_dev['id']}/featurestates/{dev_fs['id']}").json()
        prod_current = api_get(f"/api/environments/{env_prod['id']}/featurestates/{prod_fs['id']}").json()

        assert dev_updated["enabled"] is True
        assert dev_updated["value"] == "dev_value"
        assert prod_current["enabled"] is False


# ════════════════════════════════════════════════════════════════════
# PART 6: Segments
# ════════════════════════════════════════════════════════════════════


class TestSegments:

    def test_create_segment_with_rules(self):
        project = create_project()
        resp = api_post(f"/api/projects/{project['id']}/segments", {
            "name": "adults",
            "matchType": "ALL",
            "rules": [
                {"property": "age", "operator": "GREATER_THAN", "value": "18"},
            ],
        })
        assert resp.status_code == 201
        segment = resp.json()
        assert segment["name"] == "adults"
        assert segment["matchType"] == "ALL"
        assert len(segment["rules"]) == 1
        assert segment["rules"][0]["property"] == "age"
        assert segment["rules"][0]["operator"] == "GREATER_THAN"
        assert segment["rules"][0]["value"] == "18"
        assert "id" in segment["rules"][0]

    def test_create_segment_multiple_rules(self):
        project = create_project()
        segment = create_segment(project["id"], match_type="ANY", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
            {"property": "country", "operator": "EQUAL", "value": "UK"},
        ])
        assert segment["matchType"] == "ANY"
        assert len(segment["rules"]) == 2

    def test_list_segments(self):
        project = create_project()
        create_segment(project["id"], "seg-a")
        create_segment(project["id"], "seg-b")
        resp = api_get(f"/api/projects/{project['id']}/segments")
        assert resp.status_code == 200
        segments = resp.json()
        assert len(segments) == 2

    def test_get_segment(self):
        project = create_project()
        segment = create_segment(project["id"], rules=[
            {"property": "tier", "operator": "EQUAL", "value": "premium"},
        ])
        resp = api_get(f"/api/projects/{project['id']}/segments/{segment['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == segment["name"]
        assert len(data["rules"]) == 1

    def test_update_segment(self):
        project = create_project()
        segment = create_segment(project["id"], rules=[
            {"property": "age", "operator": "GREATER_THAN", "value": "18"},
        ])
        new_name = f"updated-seg-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/projects/{project['id']}/segments/{segment['id']}", {
            "name": new_name,
            "matchType": "ANY",
            "rules": [
                {"property": "country", "operator": "EQUAL", "value": "FR"},
            ],
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["name"] == new_name
        assert updated["matchType"] == "ANY"
        assert len(updated["rules"]) == 1
        assert updated["rules"][0]["property"] == "country"

    def test_delete_segment(self):
        project = create_project()
        segment = create_segment(project["id"])
        resp = api_delete(f"/api/projects/{project['id']}/segments/{segment['id']}")
        assert resp.status_code == 204
        get_resp = api_get(
            f"/api/projects/{project['id']}/segments/{segment['id']}", expected_status=404
        )
        assert get_resp.status_code == 404

    def test_duplicate_segment_name(self):
        project = create_project()
        name = f"dup-seg-{uuid.uuid4().hex[:8]}"
        resp1 = api_post(f"/api/projects/{project['id']}/segments", {
            "name": name, "matchType": "ALL", "rules": [],
        })
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/projects/{project['id']}/segments", {
            "name": name, "matchType": "ALL", "rules": [],
        }, expected_status=409)
        assert resp2.status_code == 409


# ════════════════════════════════════════════════════════════════════
# PART 7: Segment Overrides
# ════════════════════════════════════════════════════════════════════


class TestSegmentOverrides:

    def test_create_segment_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "tier", "operator": "EQUAL", "value": "premium"},
        ])

        resp = api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"],
            "segmentId": segment["id"],
            "enabled": True,
            "value": "premium_value",
            "priority": 10,
        })
        assert resp.status_code == 201
        override = resp.json()
        assert override["featureId"] == feature["id"]
        assert override["segmentId"] == segment["id"]
        assert override["enabled"] is True
        assert override["value"] == "premium_value"
        assert override["priority"] == 10
        assert override["environmentId"] == env["id"]

    def test_list_segment_overrides(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        seg1 = create_segment(project["id"], rules=[
            {"property": "a", "operator": "EQUAL", "value": "1"},
        ])
        seg2 = create_segment(project["id"], rules=[
            {"property": "b", "operator": "EQUAL", "value": "2"},
        ])

        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": seg1["id"],
            "enabled": True, "value": "v1", "priority": 1,
        })
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": seg2["id"],
            "enabled": True, "value": "v2", "priority": 2,
        })

        resp = api_get(f"/api/environments/{env['id']}/segment-overrides")
        assert resp.status_code == 200
        overrides = resp.json()
        assert len(overrides) == 2

    def test_update_segment_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "x", "operator": "EQUAL", "value": "y"},
        ])

        create_resp = api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": False, "value": "old", "priority": 1,
        })
        override_id = create_resp.json()["id"]

        resp = api_put(f"/api/environments/{env['id']}/segment-overrides/{override_id}", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "new", "priority": 5,
        })
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["enabled"] is True
        assert updated["value"] == "new"
        assert updated["priority"] == 5

    def test_delete_segment_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "x", "operator": "EQUAL", "value": "y"},
        ])

        create_resp = api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "v", "priority": 1,
        })
        override_id = create_resp.json()["id"]

        resp = api_delete(f"/api/environments/{env['id']}/segment-overrides/{override_id}")
        assert resp.status_code == 204

        # Verify gone
        list_resp = api_get(f"/api/environments/{env['id']}/segment-overrides")
        ids = [o["id"] for o in list_resp.json()]
        assert override_id not in ids

    def test_duplicate_segment_override(self):
        """Cannot have two overrides for same segment+feature in same env."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "x", "operator": "EQUAL", "value": "y"},
        ])

        resp1 = api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "v1", "priority": 1,
        })
        assert resp1.status_code == 201
        resp2 = api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": False, "value": "v2", "priority": 2,
        }, expected_status=409)
        assert resp2.status_code == 409


# ════════════════════════════════════════════════════════════════════
# PART 8: Identities
# ════════════════════════════════════════════════════════════════════


class TestIdentities:

    def test_create_identity(self):
        project = create_project()
        env = create_environment(project["id"])
        resp = api_post(f"/api/environments/{env['id']}/identities", {
            "identifier": "user-123",
        })
        assert resp.status_code == 201
        identity = resp.json()
        assert identity["identifier"] == "user-123"
        assert identity["environmentId"] == env["id"]
        assert "id" in identity
        assert "createdAt" in identity

    def test_list_identities(self):
        project = create_project()
        env = create_environment(project["id"])
        create_identity(env["id"], "alice")
        create_identity(env["id"], "bob")
        resp = api_get(f"/api/environments/{env['id']}/identities")
        assert resp.status_code == 200
        identities = resp.json()
        assert len(identities) == 2

    def test_get_identity(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])
        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}")
        assert resp.status_code == 200
        assert resp.json()["identifier"] == identity["identifier"]

    def test_delete_identity(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])
        resp = api_delete(f"/api/environments/{env['id']}/identities/{identity['id']}")
        assert resp.status_code == 204
        get_resp = api_get(
            f"/api/environments/{env['id']}/identities/{identity['id']}", expected_status=404
        )
        assert get_resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Traits
# ════════════════════════════════════════════════════════════════════


class TestTraits:

    def test_create_trait(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        resp = api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "age",
            "value": "25",
        })
        assert resp.status_code == 200
        trait = resp.json()
        assert trait["key"] == "age"
        assert trait["value"] == "25"
        assert trait["identityId"] == identity["id"]
        assert "id" in trait

    def test_list_traits(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "US",
        })
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "age", "value": "30",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/traits")
        assert resp.status_code == 200
        traits = resp.json()
        assert len(traits) == 2

    def test_trait_upsert(self):
        """POST with same key should update instead of creating duplicate."""
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        resp1 = api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "color", "value": "blue",
        })
        assert resp1.status_code == 200
        trait_id = resp1.json()["id"]

        resp2 = api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "color", "value": "red",
        })
        assert resp2.status_code == 200
        assert resp2.json()["value"] == "red"
        assert resp2.json()["id"] == trait_id  # same trait, just updated

        # Verify only one trait with key "color"
        traits = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/traits").json()
        color_traits = [t for t in traits if t["key"] == "color"]
        assert len(color_traits) == 1

    def test_update_trait(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        create_resp = api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "level", "value": "5",
        })
        trait_id = create_resp.json()["id"]

        resp = api_put(
            f"/api/environments/{env['id']}/identities/{identity['id']}/traits/{trait_id}",
            {"key": "level", "value": "10"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "10"

    def test_delete_trait(self):
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        create_resp = api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "temp", "value": "x",
        })
        trait_id = create_resp.json()["id"]

        resp = api_delete(
            f"/api/environments/{env['id']}/identities/{identity['id']}/traits/{trait_id}")
        assert resp.status_code == 204

        traits = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/traits").json()
        ids = [t["id"] for t in traits]
        assert trait_id not in ids


# ════════════════════════════════════════════════════════════════════
# PART 10: Identity Overrides
# ════════════════════════════════════════════════════════════════════


class TestIdentityOverrides:

    def test_create_identity_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        identity = create_identity(env["id"])

        resp = api_post(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides",
            {"featureId": feature["id"], "enabled": True, "value": "override_val"},
        )
        assert resp.status_code == 201
        override = resp.json()
        assert override["featureId"] == feature["id"]
        assert override["identityId"] == identity["id"]
        assert override["enabled"] is True
        assert override["value"] == "override_val"
        assert override["environmentId"] == env["id"]

    def test_list_identity_overrides(self):
        project = create_project()
        env = create_environment(project["id"])
        f1 = create_feature(project["id"])
        f2 = create_feature(project["id"])
        identity = create_identity(env["id"])

        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": f1["id"], "enabled": True, "value": "v1",
        })
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": f2["id"], "enabled": False, "value": "v2",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides")
        assert resp.status_code == 200
        overrides = resp.json()
        assert len(overrides) == 2

    def test_update_identity_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        identity = create_identity(env["id"])

        create_resp = api_post(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides",
            {"featureId": feature["id"], "enabled": False, "value": "old"},
        )
        override_id = create_resp.json()["id"]

        resp = api_put(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides/{override_id}",
            {"featureId": feature["id"], "enabled": True, "value": "new"},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["enabled"] is True
        assert updated["value"] == "new"

    def test_delete_identity_override(self):
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        identity = create_identity(env["id"])

        create_resp = api_post(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides",
            {"featureId": feature["id"], "enabled": True, "value": "v"},
        )
        override_id = create_resp.json()["id"]

        resp = api_delete(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides/{override_id}")
        assert resp.status_code == 204

    def test_duplicate_identity_override(self):
        """Cannot have two overrides for same feature on same identity."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        identity = create_identity(env["id"])

        resp1 = api_post(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides",
            {"featureId": feature["id"], "enabled": True, "value": "v1"},
        )
        assert resp1.status_code == 201
        resp2 = api_post(
            f"/api/environments/{env['id']}/identities/{identity['id']}/overrides",
            {"featureId": feature["id"], "enabled": False, "value": "v2"},
            expected_status=409,
        )
        assert resp2.status_code == 409


# ════════════════════════════════════════════════════════════════════
# PART 11: Flag Resolution — THE CORE BUSINESS LOGIC
# ════════════════════════════════════════════════════════════════════


class TestFlagResolution:

    def test_default_flag_resolution(self):
        """Without any overrides, identity gets environment defaults."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], "my-flag", default_enabled=True, initial_value="default_val")
        identity = create_identity(env["id"])

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        assert resp.status_code == 200
        flags = resp.json()
        assert isinstance(flags, list)
        assert len(flags) >= 1

        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["featureName"] == "my-flag"
        assert flag["enabled"] is True
        assert flag["value"] == "default_val"
        assert flag["source"] == "DEFAULT"

    def test_identity_override_takes_precedence(self):
        """Identity override should beat environment default."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")
        identity = create_identity(env["id"])

        # Create identity override
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feature["id"], "enabled": True, "value": "identity_val",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["enabled"] is True
        assert flag["value"] == "identity_val"
        assert flag["source"] == "IDENTITY"

    def test_segment_override_takes_precedence_over_default(self):
        """Segment override should beat environment default for matching identity."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        # Create segment: country == US
        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])

        # Create segment override
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "segment_val", "priority": 1,
        })

        # Create identity with matching trait
        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "US",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["enabled"] is True
        assert flag["value"] == "segment_val"
        assert flag["source"] == "SEGMENT"

    def test_identity_override_beats_segment_override(self):
        """Identity override > segment override > default."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        # Segment + override
        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "tier", "operator": "EQUAL", "value": "gold"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "segment_val", "priority": 1,
        })

        # Identity with matching trait
        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "tier", "value": "gold",
        })

        # Identity override
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feature["id"], "enabled": True, "value": "identity_val",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "identity_val"
        assert flag["source"] == "IDENTITY"

    def test_non_matching_segment_uses_default(self):
        """If identity doesn't match segment, use default."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "segment_val", "priority": 1,
        })

        # Identity with NON-matching trait
        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "UK",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_multiple_segments_highest_priority_wins(self):
        """When identity matches multiple segments, highest priority override wins."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        # Segment 1: country == US (priority 5)
        seg1 = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": seg1["id"],
            "enabled": True, "value": "low_priority", "priority": 5,
        })

        # Segment 2: tier == gold (priority 10)
        seg2 = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "tier", "operator": "EQUAL", "value": "gold"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": seg2["id"],
            "enabled": True, "value": "high_priority", "priority": 10,
        })

        # Identity matches BOTH segments
        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "US",
        })
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "tier", "value": "gold",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "high_priority"
        assert flag["source"] == "SEGMENT"

    def test_returns_all_features(self):
        """Identity flags endpoint returns ALL features for the environment."""
        project = create_project()
        env = create_environment(project["id"])
        f1 = create_feature(project["id"], "feat-1")
        f2 = create_feature(project["id"], "feat-2")
        f3 = create_feature(project["id"], "feat-3")
        identity = create_identity(env["id"])

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        feature_ids = [f["featureId"] for f in flags]
        assert f1["id"] in feature_ids
        assert f2["id"] in feature_ids
        assert f3["id"] in feature_ids

    def test_updated_feature_state_reflected_in_flags(self):
        """After updating a feature state, resolution should reflect the new value."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="old")
        identity = create_identity(env["id"])

        # Update feature state
        states = api_get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feature["id"])
        api_put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "new",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["enabled"] is True
        assert flag["value"] == "new"


# ════════════════════════════════════════════════════════════════════
# PART 12: Segment Rule Evaluation
# ════════════════════════════════════════════════════════════════════


class TestSegmentRuleEvaluation:

    def _setup_segment_test(self, operator, rule_value, trait_value, match_type="ALL"):
        """Helper to set up a segment test scenario."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type=match_type, rules=[
            {"property": "prop", "operator": operator, "value": rule_value},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "prop", "value": trait_value,
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        return flag

    def test_equal_match(self):
        flag = self._setup_segment_test("EQUAL", "hello", "hello")
        assert flag["value"] == "matched"
        assert flag["source"] == "SEGMENT"

    def test_equal_no_match(self):
        flag = self._setup_segment_test("EQUAL", "hello", "world")
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_not_equal_match(self):
        flag = self._setup_segment_test("NOT_EQUAL", "hello", "world")
        assert flag["value"] == "matched"
        assert flag["source"] == "SEGMENT"

    def test_not_equal_no_match(self):
        flag = self._setup_segment_test("NOT_EQUAL", "hello", "hello")
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_greater_than_numeric_match(self):
        flag = self._setup_segment_test("GREATER_THAN", "18", "25")
        assert flag["value"] == "matched"

    def test_greater_than_numeric_no_match(self):
        flag = self._setup_segment_test("GREATER_THAN", "18", "10")
        assert flag["value"] == "default"

    def test_less_than_numeric_match(self):
        flag = self._setup_segment_test("LESS_THAN", "100", "50")
        assert flag["value"] == "matched"

    def test_less_than_numeric_no_match(self):
        flag = self._setup_segment_test("LESS_THAN", "100", "200")
        assert flag["value"] == "default"

    def test_contains_match(self):
        flag = self._setup_segment_test("CONTAINS", "admin", "super-admin-user")
        assert flag["value"] == "matched"

    def test_contains_no_match(self):
        flag = self._setup_segment_test("CONTAINS", "admin", "regular-user")
        assert flag["value"] == "default"

    def test_regex_match(self):
        flag = self._setup_segment_test("REGEX", "^user-\\d+$", "user-123")
        assert flag["value"] == "matched"

    def test_regex_no_match(self):
        flag = self._setup_segment_test("REGEX", "^user-\\d+$", "admin-abc")
        assert flag["value"] == "default"

    def test_all_match_type_requires_all_rules(self):
        """matchType ALL: all rules must match."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "age", "operator": "GREATER_THAN", "value": "18"},
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        # Identity matches only ONE rule (age > 18 but country != US)
        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "age", "value": "25",
        })
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "UK",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "default"  # Should NOT match

    def test_all_match_type_both_rules_match(self):
        """matchType ALL: when all rules match, segment matches."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "age", "operator": "GREATER_THAN", "value": "18"},
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "age", "value": "25",
        })
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "US",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "matched"
        assert flag["source"] == "SEGMENT"

    def test_any_match_type_one_rule_matches(self):
        """matchType ANY: at least one rule matching is sufficient."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ANY", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
            {"property": "country", "operator": "EQUAL", "value": "UK"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "UK",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "matched"
        assert flag["source"] == "SEGMENT"

    def test_any_match_type_no_rules_match(self):
        """matchType ANY: no matching rules means no match."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ANY", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
            {"property": "country", "operator": "EQUAL", "value": "UK"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        identity = create_identity(env["id"])
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "FR",
        })

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_no_traits_never_matches_segment(self):
        """Identity with no traits should never match a segment with rules."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ALL", rules=[
            {"property": "country", "operator": "EQUAL", "value": "US"},
        ])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })

        # Identity with NO traits
        identity = create_identity(env["id"])

        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"


# ════════════════════════════════════════════════════════════════════
# PART 13: Cascade Deletes
# ════════════════════════════════════════════════════════════════════


class TestCascadeDeletes:

    def test_delete_project_cascades(self):
        """Deleting a project removes environments and features."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])

        api_delete(f"/api/projects/{project['id']}")

        # Env should be gone
        resp = api_get(f"/api/environments/{env['id']}", expected_status=404)
        assert resp.status_code == 404

    def test_delete_feature_removes_feature_states(self):
        """Deleting a feature removes its feature states."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])

        # Verify feature state exists
        states = api_get(f"/api/environments/{env['id']}/featurestates").json()
        feature_ids = [s["featureId"] for s in states]
        assert feature["id"] in feature_ids

        # Delete feature
        api_delete(f"/api/projects/{project['id']}/features/{feature['id']}")

        # Feature state should be gone
        states_after = api_get(f"/api/environments/{env['id']}/featurestates").json()
        feature_ids_after = [s["featureId"] for s in states_after]
        assert feature["id"] not in feature_ids_after

    def test_delete_feature_removes_segment_overrides(self):
        """Deleting a feature removes its segment overrides."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "x", "operator": "EQUAL", "value": "y"},
        ])

        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "v", "priority": 1,
        })

        # Delete feature
        api_delete(f"/api/projects/{project['id']}/features/{feature['id']}")

        # Segment override should be gone
        overrides = api_get(f"/api/environments/{env['id']}/segment-overrides").json()
        assert len(overrides) == 0

    def test_delete_segment_removes_overrides(self):
        """Deleting a segment removes its overrides."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        segment = create_segment(project["id"], rules=[
            {"property": "x", "operator": "EQUAL", "value": "y"},
        ])

        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "v", "priority": 1,
        })

        # Delete segment
        api_delete(f"/api/projects/{project['id']}/segments/{segment['id']}")

        # Override should be gone
        overrides = api_get(f"/api/environments/{env['id']}/segment-overrides").json()
        assert len(overrides) == 0

    def test_delete_identity_removes_overrides_and_traits(self):
        """Deleting an identity removes its overrides and traits."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])
        identity = create_identity(env["id"])

        # Add trait
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "k", "value": "v",
        })
        # Add override
        api_post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feature["id"], "enabled": True, "value": "x",
        })

        # Delete identity
        api_delete(f"/api/environments/{env['id']}/identities/{identity['id']}")

        # Identity should be gone
        resp = api_get(
            f"/api/environments/{env['id']}/identities/{identity['id']}", expected_status=404
        )
        assert resp.status_code == 404

    def test_delete_environment_removes_identities(self):
        """Deleting an environment removes identities in it."""
        project = create_project()
        env = create_environment(project["id"])
        identity = create_identity(env["id"])

        api_delete(f"/api/environments/{env['id']}")

        # Identity's environment is gone, so identity should be gone
        resp = api_get(
            f"/api/environments/{env['id']}/identities/{identity['id']}", expected_status=404
        )
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Data Isolation
# ════════════════════════════════════════════════════════════════════


class TestDataIsolation:

    def test_project_isolation(self):
        """Org1's projects are not visible to Org2."""
        project = create_project(f"OrgA-Proj-{UNIQUE}")
        resp = api_get("/api/projects", headers=HEADERS2)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert f"OrgA-Proj-{UNIQUE}" not in names

    def test_cannot_access_other_org_project(self):
        """Org2 cannot GET Org1's project by ID."""
        project = create_project()
        resp = api_get(f"/api/projects/{project['id']}", headers=HEADERS2, expected_status=404)
        assert resp.status_code == 404

    def test_cannot_access_other_org_environment(self):
        """Org2 cannot GET Org1's environment."""
        project = create_project()
        env = create_environment(project["id"])
        resp = api_get(f"/api/environments/{env['id']}", headers=HEADERS2, expected_status=404)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Audit Log
# ════════════════════════════════════════════════════════════════════


class TestAuditLog:

    def test_audit_log_on_feature_state_update(self):
        """Updating a feature state should create an audit entry."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])

        states = api_get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feature["id"])

        api_put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "updated",
        })

        resp = api_get(f"/api/projects/{project['id']}/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert data["total"] >= 1

        entries = data["results"]
        assert len(entries) >= 1
        # Find the entry for this update
        update_entries = [e for e in entries if e["action"] == "UPDATE_FEATURE_STATE"]
        assert len(update_entries) >= 1

        entry = update_entries[0]
        assert "id" in entry
        assert "timestamp" in entry
        assert entry["author"] == ORG_KEY

    def test_audit_log_pagination(self):
        """Audit log supports limit and offset."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"])

        states = api_get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feature["id"])

        # Make multiple updates
        for i in range(3):
            api_put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
                "enabled": True, "value": f"val-{i}",
            })

        # Get with limit
        resp = api_get(f"/api/projects/{project['id']}/audit-log", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2
        assert data["total"] >= 3

    def test_audit_log_for_nonexistent_project(self):
        resp = api_get("/api/projects/999999/audit-log", expected_status=404)
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 16: Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_feature_state_not_found(self):
        project = create_project()
        env = create_environment(project["id"])
        resp = api_get(
            f"/api/environments/{env['id']}/featurestates/999999", expected_status=404
        )
        assert resp.status_code == 404

    def test_segment_override_for_nonexistent_env(self):
        resp = api_get("/api/environments/999999/segment-overrides", expected_status=404)
        assert resp.status_code == 404

    def test_identity_flags_for_nonexistent_identity(self):
        project = create_project()
        env = create_environment(project["id"])
        resp = api_get(
            f"/api/environments/{env['id']}/identities/999999/flags", expected_status=404
        )
        assert resp.status_code == 404

    def test_identity_flags_for_nonexistent_env(self):
        resp = api_get("/api/environments/999999/identities/1/flags", expected_status=404)
        assert resp.status_code == 404

    def test_empty_project_list(self):
        """New org should have empty project list."""
        key = f"fresh-org-{uuid.uuid4().hex[:8]}"
        headers = {"X-Api-Key": key, "Content-Type": "application/json"}
        resp = api_get("/api/projects", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_segment_with_empty_rules(self):
        """A segment with no rules should match all identities (vacuous truth for ALL)."""
        project = create_project()
        env = create_environment(project["id"])
        feature = create_feature(project["id"], default_enabled=False, initial_value="default")

        segment = create_segment(project["id"], match_type="ALL", rules=[])
        api_post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feature["id"], "segmentId": segment["id"],
            "enabled": True, "value": "segment_val", "priority": 1,
        })

        identity = create_identity(env["id"])
        resp = api_get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = resp.json()
        flag = next(f for f in flags if f["featureId"] == feature["id"])
        # ALL with empty rules = vacuous truth, should match
        assert flag["value"] == "segment_val"
        assert flag["source"] == "SEGMENT"
