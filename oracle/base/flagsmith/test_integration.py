"""
BackendForge — L2 Integration Tests for Flagsmith Task

Adversarial tests targeting common LLM implementation bugs:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned properly
- Pattern 3: Parameters declared but not implemented
- Pattern 4: Wrong status codes
- Pattern 5: Business logic exists but behavior is empty
- Pattern 6: Data isolation failures
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Uniqueness/ordering issues

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

ORG_KEY = f"org-integ-{uuid.uuid4().hex[:8]}"
ORG2_KEY = f"org2-integ-{uuid.uuid4().hex[:8]}"

HEADERS = {"X-Api-Key": ORG_KEY, "Content-Type": "application/json"}
HEADERS2 = {"X-Api-Key": ORG2_KEY, "Content-Type": "application/json"}


# ── HTTP Helpers ──

def _expect_status(response, expected_status):
    assert response.status_code == expected_status, (
        f"Expected HTTP {expected_status}, got {response.status_code}: {response.text}"
    )
    return response


def get(path, params=None, headers=None, expected_status=None):
    response = requests.get(f"{BASE_URL}{path}", params=params, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def post(path, json_data=None, headers=None, expected_status=None):
    response = requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def put(path, json_data=None, headers=None, expected_status=None):
    response = requests.put(f"{BASE_URL}{path}", json=json_data, headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


def delete(path, headers=None, expected_status=None):
    response = requests.delete(f"{BASE_URL}{path}", headers=headers or HEADERS, timeout=30)
    if expected_status is not None:
        _expect_status(response, expected_status)
    return response


# ── Setup Helpers ──

@pytest.fixture(autouse=True)
def isolate_test_organization():
    global ORG_KEY, ORG2_KEY

    token = uuid.uuid4().hex
    ORG_KEY = f"org-integ-{token}"
    ORG2_KEY = f"org2-integ-{token}"
    HEADERS["X-Api-Key"] = ORG_KEY
    HEADERS2["X-Api-Key"] = ORG2_KEY


def make_project(name=None, headers=None):
    name = name or f"proj-{uuid.uuid4().hex[:8]}"
    r = post("/api/projects", {"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()


def make_env(project_id, name=None, headers=None):
    name = name or f"env-{uuid.uuid4().hex[:8]}"
    r = post(f"/api/projects/{project_id}/environments", {"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()


def make_feature(project_id, name=None, ftype="FLAG", enabled=False, value="", headers=None):
    name = name or f"feat-{uuid.uuid4().hex[:8]}"
    r = post(f"/api/projects/{project_id}/features", {
        "name": name, "type": ftype, "defaultEnabled": enabled, "initialValue": value,
    }, headers=headers)
    assert r.status_code == 201
    return r.json()


def make_segment(project_id, name=None, match_type="ALL", rules=None, headers=None):
    name = name or f"seg-{uuid.uuid4().hex[:8]}"
    r = post(f"/api/projects/{project_id}/segments", {
        "name": name, "matchType": match_type, "rules": rules or [],
    }, headers=headers)
    assert r.status_code == 201
    return r.json()


def make_identity(env_id, identifier=None, headers=None):
    identifier = identifier or f"id-{uuid.uuid4().hex[:8]}"
    r = post(f"/api/environments/{env_id}/identities", {"identifier": identifier}, headers=headers)
    assert r.status_code == 201
    return r.json()


def set_trait(env_id, identity_id, key, value, headers=None):
    r = post(f"/api/environments/{env_id}/identities/{identity_id}/traits",
             {"key": key, "value": value}, headers=headers)
    assert r.status_code == 200
    return r.json()


# ════════════════════════════════════════════════════════════════
# L2 Tests
# ════════════════════════════════════════════════════════════════


class TestProjectFieldNames:
    """Pattern 1+4: camelCase fields and correct status codes on project CRUD."""

    def test_create_project_returns_camel_case_fields_and_201(self):
        r = post("/api/projects", {"name": f"CamelTest-{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 201
        data = r.json()
        # camelCase field check
        assert "id" in data
        assert "name" in data
        assert "createdAt" in data
        # NOT snake_case
        assert "created_at" not in data
        assert "project_id" not in data
        # Value checks
        assert isinstance(data["id"], int)
        assert isinstance(data["createdAt"], str)
        assert len(data["createdAt"]) > 0

    def test_update_project_preserves_id_and_created_at(self):
        proj = make_project()
        original_id = proj["id"]
        original_created = proj["createdAt"]

        r = put(f"/api/projects/{proj['id']}", {"name": f"renamed-{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 200
        updated = r.json()
        assert updated["id"] == original_id
        assert updated["createdAt"] == original_created
        assert "createdAt" in updated
        assert "created_at" not in updated


class TestEnvironmentFieldsAndApiKey:
    """Pattern 1+2: Environment camelCase fields, apiKey generation, projectId reference."""

    def test_environment_response_has_all_camel_case_fields(self):
        proj = make_project()
        r = post(f"/api/projects/{proj['id']}/environments", {"name": "Production"})
        assert r.status_code == 201
        env = r.json()
        # All required camelCase fields
        assert "id" in env
        assert "name" in env
        assert "apiKey" in env
        assert "projectId" in env
        assert "createdAt" in env
        # NOT snake_case variants
        assert "api_key" not in env
        assert "project_id" not in env
        assert "created_at" not in env
        assert "environment_id" not in env
        # Value correctness
        assert env["projectId"] == proj["id"]
        assert len(env["apiKey"]) >= 16
        assert env["name"] == "Production"

    def test_environment_api_key_is_unique_across_environments(self):
        proj = make_project()
        env1 = make_env(proj["id"], "Env-A")
        env2 = make_env(proj["id"], "Env-B")
        assert env1["apiKey"] != env2["apiKey"]
        assert len(env1["apiKey"]) >= 16
        assert len(env2["apiKey"]) >= 16

    def test_environment_api_key_immutable_on_update(self):
        proj = make_project()
        env = make_env(proj["id"], "Original")
        original_key = env["apiKey"]

        r = put(f"/api/environments/{env['id']}", {"name": "Renamed"})
        assert r.status_code == 200
        assert r.json()["apiKey"] == original_key
        assert r.json()["name"] == "Renamed"


class TestFeatureFieldsAndDefaults:
    """Pattern 1+5: Feature camelCase, default values actually applied."""

    def test_feature_camel_case_fields(self):
        proj = make_project()
        r = post(f"/api/projects/{proj['id']}/features", {
            "name": "my-feature", "type": "CONFIG",
            "defaultEnabled": True, "initialValue": "42",
        })
        assert r.status_code == 201
        feat = r.json()
        assert "id" in feat
        assert "name" in feat
        assert "type" in feat
        assert "defaultEnabled" in feat
        assert "initialValue" in feat
        assert "projectId" in feat
        assert "createdAt" in feat
        # NOT snake_case
        assert "default_enabled" not in feat
        assert "initial_value" not in feat
        assert "project_id" not in feat
        assert "created_at" not in feat
        assert "feature_id" not in feat
        # Values
        assert feat["defaultEnabled"] is True
        assert feat["initialValue"] == "42"
        assert feat["projectId"] == proj["id"]
        assert feat["type"] == "CONFIG"

    def test_feature_defaults_when_omitted(self):
        """defaultEnabled defaults to false, initialValue to empty string."""
        proj = make_project()
        r = post(f"/api/projects/{proj['id']}/features", {
            "name": f"minimal-{uuid.uuid4().hex[:8]}", "type": "FLAG",
        })
        assert r.status_code == 201
        feat = r.json()
        assert feat["defaultEnabled"] is False
        assert feat["initialValue"] == ""


class TestFeatureStateAutoCreation:
    """Pattern 5+7: Auto-create feature states is real logic, not just echo."""

    def test_creating_feature_creates_states_in_all_envs(self):
        proj = make_project()
        env1 = make_env(proj["id"], "Dev")
        env2 = make_env(proj["id"], "Staging")
        env3 = make_env(proj["id"], "Prod")

        feat = make_feature(proj["id"], enabled=True, value="init_val")

        # Each environment should have the feature state
        for env in [env1, env2, env3]:
            r = get(f"/api/environments/{env['id']}/featurestates")
            assert r.status_code == 200
            states = r.json()
            fs = next((s for s in states if s["featureId"] == feat["id"]), None)
            assert fs is not None, f"Feature state missing in env {env['id']}"
            assert fs["enabled"] is True
            assert fs["value"] == "init_val"
            assert fs["featureName"] == feat["name"]
            assert fs["environmentId"] == env["id"]

    def test_creating_env_creates_states_for_all_features(self):
        proj = make_project()
        f1 = make_feature(proj["id"], "feat-x", enabled=True, value="A")
        f2 = make_feature(proj["id"], "feat-y", enabled=False, value="B")

        new_env = make_env(proj["id"], "NewEnv")
        r = get(f"/api/environments/{new_env['id']}/featurestates")
        assert r.status_code == 200
        states = r.json()
        assert len(states) == 2

        fs1 = next(s for s in states if s["featureId"] == f1["id"])
        fs2 = next(s for s in states if s["featureId"] == f2["id"])
        assert fs1["enabled"] is True
        assert fs1["value"] == "A"
        assert fs1["featureName"] == "feat-x"
        assert fs2["enabled"] is False
        assert fs2["value"] == "B"
        assert fs2["featureName"] == "feat-y"


class TestFeatureStateCamelCase:
    """Pattern 1+2: FeatureState has camelCase fields and nested feature info."""

    def test_feature_state_fields(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"], "check-fields", value="val123")

        r = get(f"/api/environments/{env['id']}/featurestates")
        states = r.json()
        fs = next(s for s in states if s["featureId"] == feat["id"])

        # camelCase fields
        assert "id" in fs
        assert "featureId" in fs
        assert "featureName" in fs
        assert "environmentId" in fs
        assert "enabled" in fs
        assert "value" in fs
        # NOT snake_case
        assert "feature_id" not in fs
        assert "feature_name" not in fs
        assert "environment_id" not in fs
        # Values
        assert fs["featureId"] == feat["id"]
        assert fs["featureName"] == "check-fields"
        assert fs["environmentId"] == env["id"]
        assert fs["value"] == "val123"

    def test_update_feature_state_returns_full_object(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])

        states = get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feat["id"])

        r = put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "updated_val",
        })
        assert r.status_code == 200
        updated = r.json()
        assert updated["id"] == fs["id"]
        assert updated["featureId"] == feat["id"]
        assert updated["featureName"] == feat["name"]
        assert updated["environmentId"] == env["id"]
        assert updated["enabled"] is True
        assert updated["value"] == "updated_val"


class TestSegmentFieldsAndRules:
    """Pattern 1+2: Segment camelCase + rules array returned with IDs."""

    def test_segment_create_returns_rules_with_ids(self):
        proj = make_project()
        r = post(f"/api/projects/{proj['id']}/segments", {
            "name": "testers",
            "matchType": "ANY",
            "rules": [
                {"property": "email", "operator": "CONTAINS", "value": "@test.com"},
                {"property": "role", "operator": "EQUAL", "value": "tester"},
            ],
        })
        assert r.status_code == 201
        seg = r.json()
        # camelCase
        assert "matchType" in seg
        assert "projectId" in seg
        assert "createdAt" in seg
        assert "match_type" not in seg
        assert "project_id" not in seg
        # Rules have IDs
        assert len(seg["rules"]) == 2
        for rule in seg["rules"]:
            assert "id" in rule
            assert isinstance(rule["id"], int)
            assert "property" in rule
            assert "operator" in rule
            assert "value" in rule

    def test_get_segment_returns_full_rules(self):
        """Pattern 2: GET segment returns rules array, not empty."""
        proj = make_project()
        seg = make_segment(proj["id"], rules=[
            {"property": "age", "operator": "GREATER_THAN", "value": "21"},
        ])

        r = get(f"/api/projects/{proj['id']}/segments/{seg['id']}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["rules"]) == 1
        assert data["rules"][0]["property"] == "age"
        assert data["rules"][0]["operator"] == "GREATER_THAN"
        assert data["rules"][0]["value"] == "21"
        assert "id" in data["rules"][0]


class TestSegmentOverrideFields:
    """Pattern 1+4: Segment override camelCase fields and correct status codes."""

    def test_segment_override_response_fields(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])
        seg = make_segment(proj["id"], rules=[
            {"property": "k", "operator": "EQUAL", "value": "v"},
        ])

        r = post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "seg_val", "priority": 7,
        })
        assert r.status_code == 201
        override = r.json()
        # camelCase
        assert "id" in override
        assert "featureId" in override
        assert "segmentId" in override
        assert "environmentId" in override
        assert "enabled" in override
        assert "value" in override
        assert "priority" in override
        # NOT snake_case
        assert "feature_id" not in override
        assert "segment_id" not in override
        assert "environment_id" not in override
        # Values
        assert override["featureId"] == feat["id"]
        assert override["segmentId"] == seg["id"]
        assert override["environmentId"] == env["id"]
        assert override["priority"] == 7

    def test_segment_override_duplicate_returns_409(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])
        seg = make_segment(proj["id"], rules=[
            {"property": "k", "operator": "EQUAL", "value": "v"},
        ])

        r1 = post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "v1", "priority": 1,
        })
        assert r1.status_code == 201

        r2 = post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": False, "value": "v2", "priority": 2,
        }, expected_status=409)
        assert r2.status_code == 409


class TestIdentityFields:
    """Pattern 1+4: Identity camelCase fields and correct status codes."""

    def test_identity_response_fields(self):
        proj = make_project()
        env = make_env(proj["id"])
        r = post(f"/api/environments/{env['id']}/identities", {"identifier": "user-abc"})
        assert r.status_code == 201
        identity = r.json()
        assert "id" in identity
        assert "identifier" in identity
        assert "environmentId" in identity
        assert "createdAt" in identity
        assert "environment_id" not in identity
        assert "created_at" not in identity
        assert identity["identifier"] == "user-abc"
        assert identity["environmentId"] == env["id"]

    def test_delete_identity_returns_204(self):
        proj = make_project()
        env = make_env(proj["id"])
        identity = make_identity(env["id"])
        r = delete(f"/api/environments/{env['id']}/identities/{identity['id']}")
        assert r.status_code == 204


class TestTraitUpsertBehavior:
    """Pattern 4+5: Trait upsert returns 200 (not 201), actually updates."""

    def test_trait_create_returns_200_not_201(self):
        """Trait POST always returns 200 per spec (upsert semantics)."""
        proj = make_project()
        env = make_env(proj["id"])
        identity = make_identity(env["id"])

        r = post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "color", "value": "blue",
        })
        assert r.status_code == 200
        trait = r.json()
        assert trait["key"] == "color"
        assert trait["value"] == "blue"
        assert "identityId" in trait
        assert "identity_id" not in trait
        assert trait["identityId"] == identity["id"]

    def test_trait_upsert_updates_value_preserves_id(self):
        proj = make_project()
        env = make_env(proj["id"])
        identity = make_identity(env["id"])
        base = f"/api/environments/{env['id']}/identities/{identity['id']}/traits"

        r1 = post(base, {"key": "level", "value": "5"})
        assert r1.status_code == 200
        trait_id = r1.json()["id"]

        r2 = post(base, {"key": "level", "value": "10"})
        assert r2.status_code == 200
        assert r2.json()["id"] == trait_id
        assert r2.json()["value"] == "10"

        # Verify only one trait
        r3 = get(base)
        traits = r3.json()
        level_traits = [t for t in traits if t["key"] == "level"]
        assert len(level_traits) == 1
        assert level_traits[0]["value"] == "10"


class TestIdentityOverrideFields:
    """Pattern 1+8: Identity override camelCase + uniqueness constraint."""

    def test_identity_override_response_fields(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])
        identity = make_identity(env["id"])

        r = post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "override_v",
        })
        assert r.status_code == 201
        ov = r.json()
        assert "id" in ov
        assert "featureId" in ov
        assert "identityId" in ov
        assert "environmentId" in ov
        assert "enabled" in ov
        assert "value" in ov
        # NOT snake_case
        assert "feature_id" not in ov
        assert "identity_id" not in ov
        assert "environment_id" not in ov
        # Values
        assert ov["featureId"] == feat["id"]
        assert ov["identityId"] == identity["id"]
        assert ov["environmentId"] == env["id"]
        assert ov["enabled"] is True
        assert ov["value"] == "override_v"

    def test_identity_override_duplicate_feature_returns_409(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])
        identity = make_identity(env["id"])
        base = f"/api/environments/{env['id']}/identities/{identity['id']}/overrides"

        r1 = post(base, {"featureId": feat["id"], "enabled": True, "value": "v1"})
        assert r1.status_code == 201
        r2 = post(
            base,
            {"featureId": feat["id"], "enabled": False, "value": "v2"},
            expected_status=409,
        )
        assert r2.status_code == 409


class TestResolvedFlagFields:
    """Pattern 1+5: Resolved flag response has correct camelCase fields and source logic."""

    def test_resolved_flags_camel_case_structure(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"], "check-flag", enabled=True, value="hello")
        identity = make_identity(env["id"])

        r = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        assert r.status_code == 200
        flags = r.json()
        assert isinstance(flags, list)
        assert len(flags) >= 1

        flag = next(f for f in flags if f["featureId"] == feat["id"])
        # camelCase fields
        assert "featureId" in flag
        assert "featureName" in flag
        assert "enabled" in flag
        assert "value" in flag
        assert "source" in flag
        # NOT snake_case
        assert "feature_id" not in flag
        assert "feature_name" not in flag
        # Values
        assert flag["featureName"] == "check-flag"
        assert flag["enabled"] is True
        assert flag["value"] == "hello"
        assert flag["source"] == "DEFAULT"

    def test_resolved_flags_reflect_updated_feature_state(self):
        """Pattern 5: Flag resolution uses actual feature state, not just initial values."""
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"], enabled=False, value="original")
        identity = make_identity(env["id"])

        # Update feature state in this environment
        states = get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feat["id"])
        put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "modified",
        })

        r = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = r.json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["enabled"] is True
        assert flag["value"] == "modified"
        assert flag["source"] == "DEFAULT"


class TestAuditLogFields:
    """Pattern 1+3: Audit log camelCase, pagination actually works."""

    def test_audit_log_response_structure(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])

        # Trigger an audit event
        states = get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feat["id"])
        put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "x",
        })

        r = get(f"/api/projects/{proj['id']}/audit-log")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "total" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 1

        entry = data["results"][0]
        assert "id" in entry
        assert "action" in entry
        assert "entityType" in entry
        assert "entityId" in entry
        assert "author" in entry
        assert "timestamp" in entry
        # NOT snake_case
        assert "entity_type" not in entry
        assert "entity_id" not in entry
        assert entry["author"] == ORG_KEY

    def test_audit_log_pagination_limit_offset(self):
        """Pattern 3: Pagination params actually limit results."""
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"])

        states = get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feat["id"])

        # Generate several audit events
        for i in range(5):
            put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
                "enabled": True, "value": f"v{i}",
            })

        # Get with limit=2
        r = get(f"/api/projects/{proj['id']}/audit-log", params={"limit": 2, "offset": 0})
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 2
        assert data["total"] >= 5

        # Get with offset
        r2 = get(f"/api/projects/{proj['id']}/audit-log", params={"limit": 2, "offset": 2})
        assert r2.status_code == 200
        data2 = r2.json()
        assert len(data2["results"]) == 2
        # Different entries than first page
        ids_page1 = {e["id"] for e in data["results"]}
        ids_page2 = {e["id"] for e in data2["results"]}
        assert ids_page1.isdisjoint(ids_page2)


class TestDataIsolationBetweenOrgs:
    """Pattern 6: Multi-org data scoping."""

    def test_org2_cannot_see_org1_environments(self):
        proj = make_project()
        env = make_env(proj["id"])
        # Org2 tries to access the environment
        r = get(f"/api/environments/{env['id']}", headers=HEADERS2, expected_status=404)
        assert r.status_code == 404

    def test_org2_cannot_modify_org1_feature(self):
        proj = make_project()
        feat = make_feature(proj["id"])
        r = put(f"/api/projects/{proj['id']}/features/{feat['id']}", {
            "name": "hacked", "type": "FLAG", "defaultEnabled": True, "initialValue": "",
        }, headers=HEADERS2, expected_status=404)
        assert r.status_code == 404

    def test_org2_cannot_delete_org1_project(self):
        proj = make_project()
        r = delete(f"/api/projects/{proj['id']}", headers=HEADERS2, expected_status=404)
        assert r.status_code == 404
        # Verify still exists for org1
        r2 = get(f"/api/projects/{proj['id']}")
        assert r2.status_code == 200


class TestNotFoundAndErrorHandling:
    """Pattern 4: Correct 404 on missing resources, 401 without key."""

    def test_401_without_api_key(self):
        r = requests.get(f"{BASE_URL}/api/projects", timeout=30)
        assert r.status_code == 401

    def test_404_nonexistent_feature_state(self):
        proj = make_project()
        env = make_env(proj["id"])
        r = get(f"/api/environments/{env['id']}/featurestates/999999", expected_status=404)
        assert r.status_code == 404

    def test_404_identity_in_nonexistent_env(self):
        r = get("/api/environments/999999/identities", expected_status=404)
        assert r.status_code == 404

    def test_delete_nonexistent_project_returns_404(self):
        r = delete("/api/projects/999999", expected_status=404)
        assert r.status_code == 404

    def test_delete_project_returns_204_not_200(self):
        proj = make_project()
        r = delete(f"/api/projects/{proj['id']}")
        assert r.status_code == 204

    def test_delete_environment_returns_204(self):
        proj = make_project()
        env = make_env(proj["id"])
        r = delete(f"/api/environments/{env['id']}")
        assert r.status_code == 204

    def test_delete_feature_returns_204(self):
        proj = make_project()
        feat = make_feature(proj["id"])
        r = delete(f"/api/projects/{proj['id']}/features/{feat['id']}")
        assert r.status_code == 204


class TestSegmentEvaluationOperators:
    """Pattern 5: Segment rule operators actually compute correctly."""

    def _flag_for_trait(self, operator, rule_value, trait_value):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"], enabled=False, value="default")
        seg = make_segment(proj["id"], rules=[
            {"property": "p", "operator": operator, "value": rule_value},
        ])
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })
        identity = make_identity(env["id"])
        set_trait(env["id"], identity["id"], "p", trait_value)

        r = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = r.json()
        return next(f for f in flags if f["featureId"] == feat["id"])

    def test_greater_than_boundary_equal_value_no_match(self):
        """18 is NOT greater than 18."""
        flag = self._flag_for_trait("GREATER_THAN", "18", "18")
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_less_than_boundary_equal_value_no_match(self):
        """18 is NOT less than 18."""
        flag = self._flag_for_trait("LESS_THAN", "18", "18")
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"

    def test_contains_is_substring_not_equality(self):
        """CONTAINS checks substring, 'abc' contains 'b'."""
        flag = self._flag_for_trait("CONTAINS", "b", "abc")
        assert flag["value"] == "matched"
        assert flag["source"] == "SEGMENT"

    def test_regex_partial_no_match_with_anchors(self):
        """Regex '^foo$' should not match 'foobar'."""
        flag = self._flag_for_trait("REGEX", "^foo$", "foobar")
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"


class TestMissingTraitRuleEvaluation:
    """Pattern 5: Missing trait for a rule evaluates to false."""

    def test_missing_trait_means_rule_fails(self):
        proj = make_project()
        env = make_env(proj["id"])
        feat = make_feature(proj["id"], enabled=False, value="default")
        seg = make_segment(proj["id"], match_type="ALL", rules=[
            {"property": "nonexistent_trait", "operator": "EQUAL", "value": "x"},
        ])
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "matched", "priority": 1,
        })
        identity = make_identity(env["id"])
        # Identity has a different trait, not the one the rule references
        set_trait(env["id"], identity["id"], "some_other_key", "x")

        r = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags")
        flags = r.json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "default"
        assert flag["source"] == "DEFAULT"
