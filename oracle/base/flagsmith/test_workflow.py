"""
BackendForge — L3 Workflow Tests for Flagsmith Task

Multi-step workflow tests that exercise cross-entity interactions and
complex business logic. Each test covers 6-12 steps across 3+ entity types.

Targeted Bug Patterns:
- Pattern 2+5+7: Nested data + business logic + cascade side effects
- Pattern 1+5+6: camelCase + flag resolution logic + data isolation
- Pattern 3+7+8: Parameters + cascades + ordering/uniqueness

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

ORG_KEY = f"org-wf-{uuid.uuid4().hex[:8]}"
ORG2_KEY = f"org2-wf-{uuid.uuid4().hex[:8]}"

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


@pytest.fixture(autouse=True)
def isolate_test_organization():
    global ORG_KEY, ORG2_KEY

    token = uuid.uuid4().hex
    ORG_KEY = f"org-wf-{token}"
    ORG2_KEY = f"org2-wf-{token}"
    HEADERS["X-Api-Key"] = ORG_KEY
    HEADERS2["X-Api-Key"] = ORG2_KEY


# ════════════════════════════════════════════════════════════════
# L3 Workflow Tests
# ════════════════════════════════════════════════════════════════


class TestFlagResolutionPriorityChain:
    """
    Pattern 2+5+7: Full priority chain test.
    Identity override > Segment override > Environment default.
    Tests all three levels and verifies the source field changes correctly.
    """

    def test_full_priority_chain_default_segment_identity(self):
        # 1. Create project + environment + feature
        proj = post("/api/projects", {"name": f"prio-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "prod"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"banner-{uuid.uuid4().hex[:8]}", "type": "CONFIG",
            "defaultEnabled": False, "initialValue": "default_banner",
        }).json()

        # 2. Create segment matching country=US
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"us-users-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "country", "operator": "EQUAL", "value": "US"}],
        }).json()

        # 3. Create segment override
        seg_or = post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "segment_banner", "priority": 5,
        })
        assert seg_or.status_code == 201

        # 4. Create identity
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "user-priority-test",
        }).json()

        # 5. Without traits → DEFAULT
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "default_banner"
        assert flag["source"] == "DEFAULT"
        assert flag["enabled"] is False

        # 6. Add matching trait → SEGMENT
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits", {
            "key": "country", "value": "US",
        })
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "segment_banner"
        assert flag["source"] == "SEGMENT"
        assert flag["enabled"] is True

        # 7. Add identity override → IDENTITY
        id_or = post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "identity_banner",
        })
        assert id_or.status_code == 201
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "identity_banner"
        assert flag["source"] == "IDENTITY"
        assert flag["enabled"] is True

        # 8. Delete identity override → falls back to SEGMENT
        override_id = id_or.json()["id"]
        r = delete(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides/{override_id}")
        assert r.status_code == 204
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "segment_banner"
        assert flag["source"] == "SEGMENT"

        # 9. Delete trait → no longer matches segment → DEFAULT
        traits = get(f"/api/environments/{env['id']}/identities/{identity['id']}/traits").json()
        country_trait = next(t for t in traits if t["key"] == "country")
        delete(f"/api/environments/{env['id']}/identities/{identity['id']}/traits/{country_trait['id']}")
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "default_banner"
        assert flag["source"] == "DEFAULT"


class TestMultiSegmentPriorityResolution:
    """
    Pattern 5+8: When identity matches multiple segments,
    highest priority segment override wins.
    """

    def test_multiple_matching_segments_highest_priority_wins(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"multi-seg-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "staging"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"theme-{uuid.uuid4().hex[:8]}", "type": "CONFIG",
            "defaultEnabled": False, "initialValue": "default_theme",
        }).json()

        # 2. Create three segments the identity will match
        seg_country = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"seg-country-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "country", "operator": "EQUAL", "value": "US"}],
        }).json()
        seg_tier = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"seg-tier-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "tier", "operator": "EQUAL", "value": "gold"}],
        }).json()
        seg_age = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"seg-age-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "age", "operator": "GREATER_THAN", "value": "18"}],
        }).json()

        # 3. Create segment overrides with different priorities
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg_country["id"],
            "enabled": True, "value": "country_theme", "priority": 1,
        })
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg_tier["id"],
            "enabled": True, "value": "tier_theme", "priority": 10,
        })
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg_age["id"],
            "enabled": True, "value": "age_theme", "priority": 5,
        })

        # 4. Create identity matching ALL three segments
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "multi-seg-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "country", "value": "US"})
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "tier", "value": "gold"})
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "age", "value": "25"})

        # 5. Verify highest priority (10) wins
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "tier_theme"
        assert flag["source"] == "SEGMENT"

        # 6. Remove the tier trait → now matches country(1) and age(5) → age wins
        traits = get(f"/api/environments/{env['id']}/identities/{identity['id']}/traits").json()
        tier_trait = next(t for t in traits if t["key"] == "tier")
        delete(f"/api/environments/{env['id']}/identities/{identity['id']}/traits/{tier_trait['id']}")

        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "age_theme"
        assert flag["source"] == "SEGMENT"


class TestEnvironmentIsolation:
    """
    Pattern 6+5: Feature states are independent per environment.
    A change in dev doesn't affect prod.
    """

    def test_feature_state_isolation_between_environments(self):
        # 1. Create project with two environments
        proj = post("/api/projects", {"name": f"iso-{uuid.uuid4().hex[:8]}"}).json()
        dev = post(f"/api/projects/{proj['id']}/environments", {"name": "dev"}).json()
        prod = post(f"/api/projects/{proj['id']}/environments", {"name": "prod"}).json()

        # 2. Create feature (disabled by default)
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"new-ui-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "",
        }).json()

        # 3. Get feature states
        dev_states = get(f"/api/environments/{dev['id']}/featurestates").json()
        prod_states = get(f"/api/environments/{prod['id']}/featurestates").json()
        dev_fs = next(s for s in dev_states if s["featureId"] == feat["id"])
        prod_fs = next(s for s in prod_states if s["featureId"] == feat["id"])

        # 4. Enable in dev only
        r = put(f"/api/environments/{dev['id']}/featurestates/{dev_fs['id']}", {
            "enabled": True, "value": "dev_config",
        })
        assert r.status_code == 200

        # 5. Verify dev is enabled, prod is NOT
        dev_updated = get(f"/api/environments/{dev['id']}/featurestates/{dev_fs['id']}").json()
        prod_current = get(f"/api/environments/{prod['id']}/featurestates/{prod_fs['id']}").json()
        assert dev_updated["enabled"] is True
        assert dev_updated["value"] == "dev_config"
        assert prod_current["enabled"] is False
        assert prod_current["value"] == ""

        # 6. Create identities in each environment
        dev_id = post(f"/api/environments/{dev['id']}/identities", {"identifier": "u1"}).json()
        prod_id = post(f"/api/environments/{prod['id']}/identities", {"identifier": "u1"}).json()

        # 7. Resolve flags → different per environment
        dev_flags = get(f"/api/environments/{dev['id']}/identities/{dev_id['id']}/flags").json()
        prod_flags = get(f"/api/environments/{prod['id']}/identities/{prod_id['id']}/flags").json()
        dev_flag = next(f for f in dev_flags if f["featureId"] == feat["id"])
        prod_flag = next(f for f in prod_flags if f["featureId"] == feat["id"])
        assert dev_flag["enabled"] is True
        assert dev_flag["value"] == "dev_config"
        assert prod_flag["enabled"] is False
        assert prod_flag["value"] == ""


class TestCascadeDeleteProject:
    """
    Pattern 7: Deleting a project cascades to environments, features,
    segments, identities, overrides.
    """

    def test_project_delete_cascades_everything(self):
        # 1. Create a full project setup
        proj = post("/api/projects", {"name": f"cascade-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "env1"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"f-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": True, "initialValue": "val",
        }).json()
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"s-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "k", "operator": "EQUAL", "value": "v"}],
        }).json()
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "cascade-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "k", "value": "v"})
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "seg_v", "priority": 1,
        })
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "id_v",
        })

        # 2. Verify everything exists
        assert get(f"/api/projects/{proj['id']}").status_code == 200
        assert get(f"/api/environments/{env['id']}").status_code == 200
        assert get(f"/api/environments/{env['id']}/identities/{identity['id']}").status_code == 200

        # 3. Delete project
        r = delete(f"/api/projects/{proj['id']}")
        assert r.status_code == 204

        # 4. Verify cascade — project gone
        assert get(f"/api/projects/{proj['id']}", expected_status=404).status_code == 404

        # 5. Environment gone
        assert get(f"/api/environments/{env['id']}", expected_status=404).status_code == 404

        # 6. Feature gone (via project)
        assert get(
            f"/api/projects/{proj['id']}/features/{feat['id']}", expected_status=404
        ).status_code == 404

        # 7. Segment gone
        assert get(
            f"/api/projects/{proj['id']}/segments/{seg['id']}", expected_status=404
        ).status_code == 404


class TestCascadeDeleteFeature:
    """
    Pattern 7: Deleting a feature removes feature states, segment overrides,
    and identity overrides across all environments.
    """

    def test_feature_delete_removes_all_related_data(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"feat-del-{uuid.uuid4().hex[:8]}"}).json()
        env1 = post(f"/api/projects/{proj['id']}/environments", {"name": "e1"}).json()
        env2 = post(f"/api/projects/{proj['id']}/environments", {"name": "e2"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"doomed-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": True, "initialValue": "x",
        }).json()
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"s-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "k", "operator": "EQUAL", "value": "v"}],
        }).json()

        # 2. Create overrides
        post(f"/api/environments/{env1['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "sv", "priority": 1,
        })
        identity = post(f"/api/environments/{env1['id']}/identities", {
            "identifier": "u1",
        }).json()
        post(f"/api/environments/{env1['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "iv",
        })

        # 3. Verify feature states exist in both envs
        states1 = get(f"/api/environments/{env1['id']}/featurestates").json()
        states2 = get(f"/api/environments/{env2['id']}/featurestates").json()
        assert any(s["featureId"] == feat["id"] for s in states1)
        assert any(s["featureId"] == feat["id"] for s in states2)

        # 4. Delete feature
        r = delete(f"/api/projects/{proj['id']}/features/{feat['id']}")
        assert r.status_code == 204

        # 5. Feature states gone
        states1_after = get(f"/api/environments/{env1['id']}/featurestates").json()
        states2_after = get(f"/api/environments/{env2['id']}/featurestates").json()
        assert not any(s["featureId"] == feat["id"] for s in states1_after)
        assert not any(s["featureId"] == feat["id"] for s in states2_after)

        # 6. Segment overrides gone
        overrides = get(f"/api/environments/{env1['id']}/segment-overrides").json()
        assert not any(o["featureId"] == feat["id"] for o in overrides)

        # 7. Identity overrides gone
        id_overrides = get(
            f"/api/environments/{env1['id']}/identities/{identity['id']}/overrides").json()
        assert not any(o["featureId"] == feat["id"] for o in id_overrides)


class TestSegmentMatchingWorkflow:
    """
    Pattern 5: Segment matching with ALL vs ANY, multiple rules,
    and dynamic trait changes.
    """

    def test_all_match_type_with_dynamic_traits(self):
        # 1. Setup project + env + feature
        proj = post("/api/projects", {"name": f"seg-wf-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "test"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"premium-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "free",
        }).json()

        # 2. Create segment: ALL of (country=US, age>21, tier=gold)
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"premium-us-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [
                {"property": "country", "operator": "EQUAL", "value": "US"},
                {"property": "age", "operator": "GREATER_THAN", "value": "21"},
                {"property": "tier", "operator": "EQUAL", "value": "gold"},
            ],
        }).json()
        assert len(seg["rules"]) == 3

        # 3. Segment override
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "premium", "priority": 1,
        })

        # 4. Create identity with partial traits (only 2 of 3)
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "partial-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "country", "value": "US"})
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "age", "value": "30"})

        # 5. Partial match → DEFAULT (ALL requires all rules)
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "free"
        assert flag["source"] == "DEFAULT"

        # 6. Add the missing trait → NOW matches
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "tier", "value": "gold"})
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "premium"
        assert flag["source"] == "SEGMENT"

        # 7. Change a trait so it no longer matches → back to DEFAULT
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "country", "value": "UK"})
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "free"
        assert flag["source"] == "DEFAULT"


class TestAuditTrailWorkflow:
    """
    Pattern 5+1: Audit log records real actions with correct fields.
    """

    def test_audit_log_tracks_feature_state_and_override_changes(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"audit-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "aud-env"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"aud-feat-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "",
        }).json()
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"aud-seg-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "x", "operator": "EQUAL", "value": "y"}],
        }).json()

        # 2. Update feature state → should generate audit entry
        states = get(f"/api/environments/{env['id']}/featurestates").json()
        fs = next(s for s in states if s["featureId"] == feat["id"])
        put(f"/api/environments/{env['id']}/featurestates/{fs['id']}", {
            "enabled": True, "value": "on",
        })

        # 3. Create segment override → audit entry
        so = post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "seg_v", "priority": 1,
        }).json()

        # 4. Create identity override → audit entry
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "aud-user",
        }).json()
        io = post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "id_v",
        }).json()

        # 5. Check audit log
        r = get(f"/api/projects/{proj['id']}/audit-log")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "total" in data
        assert data["total"] >= 3

        # 6. Verify entries have correct structure
        for entry in data["results"]:
            assert "id" in entry
            assert "action" in entry
            assert "entityType" in entry
            assert "entityId" in entry
            assert "author" in entry
            assert "timestamp" in entry
            assert entry["author"] == ORG_KEY
            # NOT snake_case
            assert "entity_type" not in entry
            assert "entity_id" not in entry

        # 7. Should have UPDATE_FEATURE_STATE action
        actions = [e["action"] for e in data["results"]]
        assert "UPDATE_FEATURE_STATE" in actions


class TestMultiFeatureResolution:
    """
    Pattern 5: Identity flags endpoint returns ALL features with correct
    overrides applied per-feature.
    """

    def test_flags_endpoint_resolves_each_feature_independently(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"multi-feat-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "mf-env"}).json()

        # 2. Create 3 features
        feat_a = post(f"/api/projects/{proj['id']}/features", {
            "name": f"feat-a-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "a_default",
        }).json()
        feat_b = post(f"/api/projects/{proj['id']}/features", {
            "name": f"feat-b-{uuid.uuid4().hex[:8]}", "type": "CONFIG",
            "defaultEnabled": True, "initialValue": "b_default",
        }).json()
        feat_c = post(f"/api/projects/{proj['id']}/features", {
            "name": f"feat-c-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "c_default",
        }).json()

        # 3. Create segment for feat_b override
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"vip-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "vip", "operator": "EQUAL", "value": "true"}],
        }).json()
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat_b["id"], "segmentId": seg["id"],
            "enabled": True, "value": "b_vip", "priority": 1,
        })

        # 4. Create identity with vip trait
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "vip-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "vip", "value": "true"})

        # 5. Add identity override for feat_c
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/overrides", {
            "featureId": feat_c["id"], "enabled": True, "value": "c_override",
        })

        # 6. Resolve flags → each feature has correct source
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        assert len(flags) >= 3

        flag_a = next(f for f in flags if f["featureId"] == feat_a["id"])
        flag_b = next(f for f in flags if f["featureId"] == feat_b["id"])
        flag_c = next(f for f in flags if f["featureId"] == feat_c["id"])

        # feat_a: DEFAULT (no overrides)
        assert flag_a["value"] == "a_default"
        assert flag_a["source"] == "DEFAULT"
        assert flag_a["enabled"] is False

        # feat_b: SEGMENT (matches vip segment)
        assert flag_b["value"] == "b_vip"
        assert flag_b["source"] == "SEGMENT"
        assert flag_b["enabled"] is True

        # feat_c: IDENTITY (has identity override)
        assert flag_c["value"] == "c_override"
        assert flag_c["source"] == "IDENTITY"
        assert flag_c["enabled"] is True


class TestVacuousTruthSegment:
    """
    Pattern 5: A segment with matchType=ALL and no rules matches all identities
    (vacuous truth). This is a subtle business rule LLMs often miss.
    """

    def test_empty_rules_all_match_type_matches_everyone(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"vac-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "vac-env"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"global-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "off",
        }).json()

        # 2. Create segment with empty rules + ALL
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"everyone-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [],
        }).json()
        assert seg["rules"] == []
        assert seg["matchType"] == "ALL"

        # 3. Segment override
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "global_on", "priority": 1,
        })

        # 4. Identity with no traits at all
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "empty-user",
        }).json()

        # 5. Should match the segment (vacuous truth)
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "global_on"
        assert flag["source"] == "SEGMENT"
        assert flag["enabled"] is True

        # 6. Another identity with traits also matches
        identity2 = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "traits-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity2['id']}/traits",
             {"key": "anything", "value": "something"})

        flags2 = get(f"/api/environments/{env['id']}/identities/{identity2['id']}/flags").json()
        flag2 = next(f for f in flags2 if f["featureId"] == feat["id"])
        assert flag2["value"] == "global_on"
        assert flag2["source"] == "SEGMENT"


class TestUniqueConstraintWorkflow:
    """
    Pattern 8: Unique name constraints enforced within correct scope.
    Same name in different projects should be fine.
    """

    def test_unique_names_scoped_to_project(self):
        # 1. Create two projects
        proj_a = post("/api/projects", {"name": f"scope-a-{uuid.uuid4().hex[:8]}"}).json()
        proj_b = post("/api/projects", {"name": f"scope-b-{uuid.uuid4().hex[:8]}"}).json()

        feat_name = f"shared-name-{uuid.uuid4().hex[:8]}"
        env_name = f"shared-env-{uuid.uuid4().hex[:8]}"
        seg_name = f"shared-seg-{uuid.uuid4().hex[:8]}"

        # 2. Create feature with same name in both projects → OK
        r1 = post(f"/api/projects/{proj_a['id']}/features", {
            "name": feat_name, "type": "FLAG",
        })
        assert r1.status_code == 201
        r2 = post(f"/api/projects/{proj_b['id']}/features", {
            "name": feat_name, "type": "FLAG",
        })
        assert r2.status_code == 201

        # 3. Duplicate in same project → 409
        r3 = post(f"/api/projects/{proj_a['id']}/features", {
            "name": feat_name, "type": "FLAG",
        }, expected_status=409)
        assert r3.status_code == 409

        # 4. Environment same name in both → OK
        r4 = post(f"/api/projects/{proj_a['id']}/environments", {"name": env_name})
        assert r4.status_code == 201
        r5 = post(f"/api/projects/{proj_b['id']}/environments", {"name": env_name})
        assert r5.status_code == 201

        # 5. Duplicate env in same project → 409
        r6 = post(
            f"/api/projects/{proj_a['id']}/environments",
            {"name": env_name},
            expected_status=409,
        )
        assert r6.status_code == 409

        # 6. Segment same name in both → OK
        r7 = post(f"/api/projects/{proj_a['id']}/segments", {
            "name": seg_name, "matchType": "ALL", "rules": [],
        })
        assert r7.status_code == 201
        r8 = post(f"/api/projects/{proj_b['id']}/segments", {
            "name": seg_name, "matchType": "ALL", "rules": [],
        })
        assert r8.status_code == 201

        # 7. Duplicate segment in same project → 409
        r9 = post(f"/api/projects/{proj_a['id']}/segments", {
            "name": seg_name, "matchType": "ANY", "rules": [],
        }, expected_status=409)
        assert r9.status_code == 409


class TestDeleteSegmentCascadesOverrides:
    """
    Pattern 7: Deleting a segment removes all its overrides,
    and flag resolution falls back to default.
    """

    def test_segment_delete_removes_overrides_and_affects_resolution(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"seg-del-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "sd-env"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"sd-feat-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "default_val",
        }).json()

        # 2. Create segment + override
        seg = post(f"/api/projects/{proj['id']}/segments", {
            "name": f"sd-seg-{uuid.uuid4().hex[:8]}", "matchType": "ALL",
            "rules": [{"property": "k", "operator": "EQUAL", "value": "v"}],
        }).json()
        post(f"/api/environments/{env['id']}/segment-overrides", {
            "featureId": feat["id"], "segmentId": seg["id"],
            "enabled": True, "value": "seg_val", "priority": 1,
        })

        # 3. Create identity matching segment
        identity = post(f"/api/environments/{env['id']}/identities", {
            "identifier": "seg-del-user",
        }).json()
        post(f"/api/environments/{env['id']}/identities/{identity['id']}/traits",
             {"key": "k", "value": "v"})

        # 4. Verify segment override applies
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "seg_val"
        assert flag["source"] == "SEGMENT"

        # 5. Delete segment
        r = delete(f"/api/projects/{proj['id']}/segments/{seg['id']}")
        assert r.status_code == 204

        # 6. Segment overrides should be gone
        overrides = get(f"/api/environments/{env['id']}/segment-overrides").json()
        assert len(overrides) == 0

        # 7. Flag resolution falls back to DEFAULT
        flags = get(f"/api/environments/{env['id']}/identities/{identity['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "default_val"
        assert flag["source"] == "DEFAULT"

        # 8. Segment itself is 404
        r = get(f"/api/projects/{proj['id']}/segments/{seg['id']}", expected_status=404)
        assert r.status_code == 404


class TestIdentityDeleteCascade:
    """
    Pattern 7: Deleting an identity removes its traits and overrides.
    Other identities are unaffected.
    """

    def test_identity_delete_only_affects_that_identity(self):
        # 1. Setup
        proj = post("/api/projects", {"name": f"id-del-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "id-env"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"id-feat-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": False, "initialValue": "default",
        }).json()

        # 2. Create two identities
        id_a = post(f"/api/environments/{env['id']}/identities", {"identifier": "alice"}).json()
        id_b = post(f"/api/environments/{env['id']}/identities", {"identifier": "bob"}).json()

        # 3. Add traits and overrides to both
        post(f"/api/environments/{env['id']}/identities/{id_a['id']}/traits",
             {"key": "color", "value": "blue"})
        post(f"/api/environments/{env['id']}/identities/{id_b['id']}/traits",
             {"key": "color", "value": "red"})
        post(f"/api/environments/{env['id']}/identities/{id_a['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "alice_v",
        })
        post(f"/api/environments/{env['id']}/identities/{id_b['id']}/overrides", {
            "featureId": feat["id"], "enabled": True, "value": "bob_v",
        })

        # 4. Delete alice
        r = delete(f"/api/environments/{env['id']}/identities/{id_a['id']}")
        assert r.status_code == 204

        # 5. Alice is gone
        assert get(
            f"/api/environments/{env['id']}/identities/{id_a['id']}", expected_status=404
        ).status_code == 404

        # 6. Bob is still there with her overrides and traits
        assert get(f"/api/environments/{env['id']}/identities/{id_b['id']}").status_code == 200
        bob_traits = get(f"/api/environments/{env['id']}/identities/{id_b['id']}/traits").json()
        assert len(bob_traits) == 1
        assert bob_traits[0]["key"] == "color"
        assert bob_traits[0]["value"] == "red"

        bob_overrides = get(
            f"/api/environments/{env['id']}/identities/{id_b['id']}/overrides").json()
        assert len(bob_overrides) == 1
        assert bob_overrides[0]["value"] == "bob_v"

        # 7. Bob's flag resolution still works
        flags = get(f"/api/environments/{env['id']}/identities/{id_b['id']}/flags").json()
        flag = next(f for f in flags if f["featureId"] == feat["id"])
        assert flag["value"] == "bob_v"
        assert flag["source"] == "IDENTITY"


class TestOrgIsolationWorkflow:
    """
    Pattern 6: Complete organization isolation — org2 cannot see or
    modify any of org1's data.
    """

    def test_complete_org_isolation(self):
        # 1. Org1 creates full setup
        proj = post("/api/projects", {"name": f"org1-{uuid.uuid4().hex[:8]}"}).json()
        env = post(f"/api/projects/{proj['id']}/environments", {"name": "org1-env"}).json()
        feat = post(f"/api/projects/{proj['id']}/features", {
            "name": f"org1-feat-{uuid.uuid4().hex[:8]}", "type": "FLAG",
            "defaultEnabled": True, "initialValue": "secret",
        }).json()

        # 2. Org2 cannot list org1's projects
        r = get("/api/projects", headers=HEADERS2)
        assert r.status_code == 200
        assert all(p["id"] != proj["id"] for p in r.json())

        # 3. Org2 cannot GET org1's project
        r = get(f"/api/projects/{proj['id']}", headers=HEADERS2, expected_status=404)
        assert r.status_code == 404

        # 4. Org2 cannot GET org1's environment
        r = get(f"/api/environments/{env['id']}", headers=HEADERS2, expected_status=404)
        assert r.status_code == 404

        # 5. Org2 cannot list org1's features
        r = get(
            f"/api/projects/{proj['id']}/features", headers=HEADERS2, expected_status=404
        )
        assert r.status_code == 404

        # 6. Org2 cannot list feature states
        r = get(
            f"/api/environments/{env['id']}/featurestates", headers=HEADERS2, expected_status=404
        )
        assert r.status_code == 404

        # 7. Org2 can create their own project with same name
        proj2 = post("/api/projects", {"name": proj["name"]}, headers=HEADERS2)
        assert proj2.status_code == 201
        assert proj2.json()["id"] != proj["id"]
