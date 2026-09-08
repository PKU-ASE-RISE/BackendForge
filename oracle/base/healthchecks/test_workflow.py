"""
BackendForge — L3 Workflow Tests for Healthchecks Task

Multi-step adversarial workflow tests covering end-to-end scenarios.
Each test: 6-12 steps, 12-20 assertions, 3+ entity types, 2+ bug patterns.

Targets:
- Complete monitoring lifecycle
- Grace period / status transitions
- Notification channel integration
- Multi-check with tag filtering
- Badge aggregation
- Various ping signals
- Pause/resume behavior
- Data isolation across projects
"""

import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
API_KEY_A = f"test-l3-workflow-key-alpha-{RUN_ID}"
API_KEY_B = f"test-l3-workflow-key-beta-{RUN_ID}"

HEADERS_A = {"X-Api-Key": API_KEY_A, "Content-Type": "application/json"}
HEADERS_B = {"X-Api-Key": API_KEY_B, "Content-Type": "application/json"}

UID = RUN_ID[:6]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent primary and secondary projects."""
    global API_KEY_A, API_KEY_B, HEADERS_A, HEADERS_B, UID

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    API_KEY_A = f"test-l3-workflow-key-alpha-{item_id}"
    API_KEY_B = f"test-l3-workflow-key-beta-{item_id}"
    HEADERS_A = {"X-Api-Key": API_KEY_A, "Content-Type": "application/json"}
    HEADERS_B = {"X-Api-Key": API_KEY_B, "Content-Type": "application/json"}
    UID = item_id[:6]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS_A if headers is None else headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS_A if headers is None else headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS_A if headers is None else headers, timeout=30)


def api_delete(path, headers=None):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS_A if headers is None else headers, timeout=30)


def ping(check_id, action="success", body=None):
    if action == "success":
        url = f"{BASE_URL}/ping/{check_id}"
    else:
        url = f"{BASE_URL}/ping/{check_id}/{action}"
    return requests.post(url, data=body or "", timeout=30)


# ════════════════════════════════════════════════════════════════════
# L3 WORKFLOW TESTS
# ════════════════════════════════════════════════════════════════════


class TestMonitoringLifecycle:
    """Complete monitoring lifecycle: create → ping → verify status + counters → ping again."""

    def test_full_check_lifecycle_with_pings(self):
        """
        Pattern 1+5+7: Field names + computed status + side effects

        1. Create check (timeout=86400, grace=3600)
        2. Verify initial state (status=new, n_pings=0)
        3. Ping it → verify status=up, n_pings=1, last_ping set
        4. Ping again → verify n_pings=2, last_ping updated
        5. Send fail → verify status=down, n_pings=3
        6. Send success → verify recovery to up, n_pings=4
        7. Check ping history has 4 entries in correct order
        8. Verify flips recorded for each transition
        """
        # Step 1: Create
        resp = api_post("/api/v1/checks/", {
            "name": f"lifecycle-{UID}",
            "tags": f"lifecycle {UID}",
            "timeout": 86400,
            "grace": 3600
        })
        assert resp.status_code == 201
        check = resp.json()
        check_id = check["id"]

        # Step 2: Initial state
        assert check["status"] == "new"
        assert check["n_pings"] == 0
        assert check["last_ping"] is None
        assert check["last_start"] is None
        assert check["kind"] == "simple"
        assert check["timeout"] == 86400
        assert check["grace"] == 3600

        # Step 3: First ping
        pr = ping(check_id)
        assert pr.status_code == 200
        resp2 = api_get(f"/api/v1/checks/{check_id}")
        c2 = resp2.json()
        assert c2["status"] == "up"
        assert c2["n_pings"] == 1
        assert c2["last_ping"] is not None
        first_ping_time = c2["last_ping"]

        # Step 4: Second ping
        time.sleep(0.05)
        ping(check_id)
        resp3 = api_get(f"/api/v1/checks/{check_id}")
        c3 = resp3.json()
        assert c3["status"] == "up"
        assert c3["n_pings"] == 2
        assert c3["last_ping"] is not None
        # last_ping should be updated (newer than first)
        assert c3["last_ping"] >= first_ping_time

        # Step 5: Fail ping
        ping(check_id, "fail")
        resp4 = api_get(f"/api/v1/checks/{check_id}")
        c4 = resp4.json()
        assert c4["status"] == "down"
        assert c4["n_pings"] == 3

        # Step 6: Recovery
        ping(check_id)
        resp5 = api_get(f"/api/v1/checks/{check_id}")
        c5 = resp5.json()
        assert c5["status"] == "up"
        assert c5["n_pings"] == 4

        # Step 7: Ping history
        resp6 = api_get(f"/api/v1/checks/{check_id}/pings/")
        pings_data = resp6.json()["pings"]
        assert len(pings_data) == 4
        # Most recent first
        assert pings_data[0]["n"] == 4
        assert pings_data[3]["n"] == 1
        types = [p["type"] for p in pings_data]
        assert "fail" in types
        assert types.count("success") == 3

        # Step 8: Flips
        resp7 = api_get(f"/api/v1/checks/{check_id}/flips/")
        flips = resp7.json()["flips"]
        # Should have at least: new→up, up→down, down→up
        assert len(flips) >= 3
        up_vals = [f["up"] for f in flips]
        assert 1 in up_vals
        assert 0 in up_vals


class TestChannelIntegrationWorkflow:
    """Create check + create channel + assign + verify + delete channel."""

    def test_channel_lifecycle_with_check(self):
        """
        Pattern 2+7: Nested data + cascade side effects

        1. Create check
        2. Create email channel → 201
        3. Assign channel to check → verify both sides updated
        4. Create second channel → assign both
        5. Verify check.channels lists both
        6. Remove first channel from check
        7. Verify only second remains
        8. Delete second channel entirely → verify check's channels updated
        """
        # Step 1: Create check
        cr = api_post("/api/v1/checks/", {"name": f"chlife-{UID}"})
        assert cr.status_code == 201
        check_id = cr.json()["id"]
        assert cr.json()["channels"] == ""

        # Step 2: Create channel
        ch1r = api_post("/api/v1/channels/", {"kind": "email", "name": f"ch1-{UID}", "email": f"ch1-{UID}@test.com"})
        assert ch1r.status_code == 201
        ch1_id = ch1r.json()["id"]
        assert ch1r.json()["checks"] == []

        # Step 3: Assign channel to check
        ar = api_post(f"/api/v1/checks/{check_id}/channels/{ch1_id}", {})
        assert ar.status_code == 200

        # Verify check has channel
        cr2 = api_get(f"/api/v1/checks/{check_id}")
        assert ch1_id in cr2.json()["channels"]

        # Verify channel has check
        chr2 = api_get(f"/api/v1/channels/{ch1_id}")
        assert check_id in chr2.json()["checks"]

        # Step 4: Create second channel and assign
        ch2r = api_post("/api/v1/channels/", {"kind": "webhook", "name": f"ch2-{UID}", "webhook_url": f"https://hook-{UID}.test"})
        assert ch2r.status_code == 201
        ch2_id = ch2r.json()["id"]

        ar2 = api_post(f"/api/v1/checks/{check_id}/channels/{ch2_id}", {})
        assert ar2.status_code == 200

        # Step 5: Check has both channels
        cr3 = api_get(f"/api/v1/checks/{check_id}")
        assert ch1_id in cr3.json()["channels"]
        assert ch2_id in cr3.json()["channels"]

        # Step 6: Remove first channel from check
        rr = api_delete(f"/api/v1/checks/{check_id}/channels/{ch1_id}")
        assert rr.status_code == 200

        cr4 = api_get(f"/api/v1/checks/{check_id}")
        assert ch1_id not in cr4.json()["channels"]
        assert ch2_id in cr4.json()["channels"]

        # Step 7: Verify first channel no longer lists this check
        chr3 = api_get(f"/api/v1/channels/{ch1_id}")
        assert check_id not in chr3.json()["checks"]

        # Step 8: Delete second channel entirely
        dr = api_delete(f"/api/v1/channels/{ch2_id}")
        assert dr.status_code == 200

        # Check's channels should no longer include the deleted channel
        cr5 = api_get(f"/api/v1/checks/{check_id}")
        assert ch2_id not in cr5.json()["channels"]


class TestMultiCheckTagWorkflow:
    """Create multiple checks with tags → filter → ping → filter by status."""

    def test_multi_check_tag_filtering_and_status(self):
        """
        Pattern 3+5: Filtering works + status transitions are real

        1. Create 4 checks: 2 with tag 'web', 2 with tag 'db'
        2. List with tag=web → verify only 2 returned
        3. Ping one web check → it becomes 'up'
        4. Fail-ping one db check → it becomes 'down'
        5. List all → verify mixed statuses
        6. Verify correct badge status for each tag
        """
        tag_web = f"web-{UID}"
        tag_db = f"db-{UID}"

        # Step 1: Create 4 checks
        w1 = api_post("/api/v1/checks/", {"name": f"web1-{UID}", "tags": tag_web, "timeout": 86400, "grace": 3600})
        w2 = api_post("/api/v1/checks/", {"name": f"web2-{UID}", "tags": tag_web, "timeout": 86400, "grace": 3600})
        d1 = api_post("/api/v1/checks/", {"name": f"db1-{UID}", "tags": tag_db, "timeout": 86400, "grace": 3600})
        d2 = api_post("/api/v1/checks/", {"name": f"db2-{UID}", "tags": tag_db, "timeout": 86400, "grace": 3600})
        assert w1.status_code == 201
        assert w2.status_code == 201
        assert d1.status_code == 201
        assert d2.status_code == 201

        w1_id = w1.json()["id"]
        w2_id = w2.json()["id"]
        d1_id = d1.json()["id"]
        d2_id = d2.json()["id"]

        # Step 2: Filter by web tag
        resp_web = api_get("/api/v1/checks/", params={"tag": tag_web})
        web_checks = resp_web.json()["checks"]
        web_ids = [c["id"] for c in web_checks]
        assert w1_id in web_ids
        assert w2_id in web_ids
        assert d1_id not in web_ids
        assert d2_id not in web_ids

        # Step 3: Ping one web check
        ping(w1_id)
        r = api_get(f"/api/v1/checks/{w1_id}")
        assert r.json()["status"] == "up"

        # Step 4: Fail one db check
        ping(d1_id, "fail")
        r2 = api_get(f"/api/v1/checks/{d1_id}")
        assert r2.json()["status"] == "down"

        # Step 5: Verify mixed statuses
        resp_all = api_get("/api/v1/checks/", params={"tag": tag_web})
        statuses = {c["id"]: c["status"] for c in resp_all.json()["checks"]}
        assert statuses[w1_id] == "up"
        assert statuses[w2_id] == "new"

        # Step 6: Badge for web tag (should be "up" since no web checks are down)
        badge_web = api_get(f"/api/v1/badges/{tag_web}")
        assert badge_web.status_code == 200
        bw = badge_web.json()
        assert bw["status"] == "up"
        assert bw["total"] == 2
        assert bw["down"] == 0

        # Badge for db tag (should be "down" since d1 is down)
        badge_db = api_get(f"/api/v1/badges/{tag_db}")
        assert badge_db.status_code == 200
        bd = badge_db.json()
        assert bd["status"] == "down"
        assert bd["total"] == 2
        assert bd["down"] == 1


class TestBadgeAggregation:
    """Badge endpoints must aggregate check statuses correctly."""

    def test_badge_reflects_all_check_statuses(self):
        """
        Pattern 5+3: Computed aggregation + filtering by tag

        1. Create 3 checks with same tag
        2. All 'new' → badge status = 'up'
        3. Ping one → badge still 'up'
        4. Fail one → badge becomes 'down'
        5. Recover failed one → badge back to 'up'
        6. List badges endpoint shows all tags
        """
        tag = f"badgeall-{UID}"

        # Step 1: Create 3 checks
        c1 = api_post("/api/v1/checks/", {"name": f"b1-{UID}", "tags": tag, "timeout": 86400, "grace": 3600})
        c2 = api_post("/api/v1/checks/", {"name": f"b2-{UID}", "tags": tag, "timeout": 86400, "grace": 3600})
        c3 = api_post("/api/v1/checks/", {"name": f"b3-{UID}", "tags": tag, "timeout": 86400, "grace": 3600})
        c1_id = c1.json()["id"]
        c2_id = c2.json()["id"]
        c3_id = c3.json()["id"]

        # Step 2: All new → badge is "up"
        br1 = api_get(f"/api/v1/badges/{tag}")
        assert br1.json()["status"] == "up"
        assert br1.json()["total"] == 3
        assert br1.json()["down"] == 0
        assert br1.json()["grace"] == 0

        # Step 3: Ping one → still "up"
        ping(c1_id)
        br2 = api_get(f"/api/v1/badges/{tag}")
        assert br2.json()["status"] == "up"

        # Step 4: Fail one → "down"
        ping(c2_id, "fail")
        br3 = api_get(f"/api/v1/badges/{tag}")
        assert br3.json()["status"] == "down"
        assert br3.json()["down"] >= 1

        # Step 5: Recover → "up"
        ping(c2_id)
        br4 = api_get(f"/api/v1/badges/{tag}")
        assert br4.json()["status"] == "up"
        assert br4.json()["down"] == 0

        # Step 6: List badges
        bl = api_get("/api/v1/badges/")
        assert bl.status_code == 200
        badges = bl.json()["badges"]
        assert "*" in badges
        assert tag in badges


class TestPingSignalVariations:
    """Different ping types affect check state differently."""

    def test_all_ping_types_behavior(self):
        """
        Pattern 5: Business logic for each ping type

        1. Create check
        2. /start → status stays 'new', last_start set, n_pings=1
        3. /success → status='up', last_ping set, duration computed, n_pings=2
        4. /log → status stays 'up', last_ping unchanged, n_pings=3
        5. /fail → status='down', n_pings=4
        6. /start → status stays 'down', last_start updated, n_pings=5
        7. /success → status='up', duration computed, n_pings=6
        8. Verify ping history has 6 entries with correct types
        """
        cr = api_post("/api/v1/checks/", {"name": f"signals-{UID}", "timeout": 86400, "grace": 3600})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        # Step 2: /start
        ping(check_id, "start")
        r1 = api_get(f"/api/v1/checks/{check_id}")
        c1 = r1.json()
        assert c1["status"] == "new"
        assert c1["last_start"] is not None
        assert c1["last_ping"] is None
        assert c1["n_pings"] == 1

        # Step 3: /success (should compute duration from start)
        time.sleep(0.15)
        ping(check_id)
        r2 = api_get(f"/api/v1/checks/{check_id}")
        c2 = r2.json()
        assert c2["status"] == "up"
        assert c2["last_ping"] is not None
        assert c2["n_pings"] == 2
        assert c2["last_duration"] is not None
        assert c2["last_duration"] >= 0.1
        last_ping_after_success = c2["last_ping"]

        # Step 4: /log (no status change, no last_ping update)
        time.sleep(0.05)
        ping(check_id, "log")
        r3 = api_get(f"/api/v1/checks/{check_id}")
        c3 = r3.json()
        assert c3["status"] == "up"
        assert c3["n_pings"] == 3
        assert c3["last_ping"] == last_ping_after_success

        # Step 5: /fail
        ping(check_id, "fail")
        r4 = api_get(f"/api/v1/checks/{check_id}")
        c4 = r4.json()
        assert c4["status"] == "down"
        assert c4["n_pings"] == 4

        # Step 6: /start (does not change status from 'down')
        ping(check_id, "start")
        r5 = api_get(f"/api/v1/checks/{check_id}")
        c5 = r5.json()
        assert c5["status"] == "down"
        assert c5["n_pings"] == 5
        assert c5["last_start"] is not None

        # Step 7: /success (recovers, computes duration)
        time.sleep(0.15)
        ping(check_id)
        r6 = api_get(f"/api/v1/checks/{check_id}")
        c6 = r6.json()
        assert c6["status"] == "up"
        assert c6["n_pings"] == 6
        assert c6["last_duration"] is not None
        assert c6["last_duration"] >= 0.1

        # Step 8: Verify ping history
        rh = api_get(f"/api/v1/checks/{check_id}/pings/")
        pings_data = rh.json()["pings"]
        assert len(pings_data) == 6
        types = [p["type"] for p in pings_data]
        assert types.count("success") == 2
        assert types.count("start") == 2
        assert types.count("fail") == 1
        assert types.count("log") == 1


class TestPauseResumeWorkflow:
    """Pause/resume affects status and interacts with pings."""

    def test_pause_resume_full_cycle(self):
        """
        Pattern 4+5: Status codes + state transitions

        1. Create check → status=new
        2. Ping → status=up
        3. Pause → status=paused (200)
        4. Pause again → idempotent (200, still paused)
        5. Resume → status=new, last_ping=None (200)
        6. Resume again → 409 Conflict
        7. Ping after resume → status=up again
        8. Verify flips tracked transitions
        """
        cr = api_post("/api/v1/checks/", {"name": f"prlife-{UID}", "timeout": 86400, "grace": 3600})
        assert cr.status_code == 201
        check_id = cr.json()["id"]
        assert cr.json()["status"] == "new"

        # Step 2: Ping → up
        ping(check_id)
        r1 = api_get(f"/api/v1/checks/{check_id}")
        assert r1.json()["status"] == "up"
        assert r1.json()["last_ping"] is not None

        # Step 3: Pause
        pr = api_post(f"/api/v1/checks/{check_id}/pause", {})
        assert pr.status_code == 200
        assert pr.json()["status"] == "paused"

        # Step 4: Pause again (idempotent)
        pr2 = api_post(f"/api/v1/checks/{check_id}/pause", {})
        assert pr2.status_code == 200
        assert pr2.json()["status"] == "paused"

        # Step 5: Resume
        rr = api_post(f"/api/v1/checks/{check_id}/resume", {})
        assert rr.status_code == 200
        assert rr.json()["status"] == "new"
        assert rr.json()["last_ping"] is None

        # Step 6: Resume again → 409
        rr2 = api_post(f"/api/v1/checks/{check_id}/resume", {})
        assert rr2.status_code == 409

        # Step 7: Ping after resume
        ping(check_id)
        r2 = api_get(f"/api/v1/checks/{check_id}")
        assert r2.json()["status"] == "up"
        assert r2.json()["n_pings"] >= 2

        # Step 8: Check flips
        fr = api_get(f"/api/v1/checks/{check_id}/flips/")
        flips = fr.json()["flips"]
        # Should have multiple flips: new→up, up→paused, paused→new, new→up
        assert len(flips) >= 3
        up_values = [f["up"] for f in flips]
        assert 1 in up_values
        assert 0 in up_values


class TestDataIsolationWorkflow:
    """Two different API keys → completely isolated data."""

    def test_full_isolation_between_projects(self):
        """
        Pattern 6: Data isolation

        1. Project A creates check + channel
        2. Project B creates check + channel
        3. Verify A can't see B's checks
        4. Verify B can't see A's channels
        5. Verify A can't access B's check by ID (403)
        6. Both pings work independently (no auth on pings)
        7. Project info shows correct counts per project
        """
        # Step 1: Project A
        ca = api_post("/api/v1/checks/", {"name": f"isoA-{UID}", "tags": f"iso-{UID}"}, headers=HEADERS_A)
        assert ca.status_code == 201
        a_check_id = ca.json()["id"]

        cha = api_post("/api/v1/channels/", {"kind": "email", "email": f"a-{UID}@test.com"}, headers=HEADERS_A)
        assert cha.status_code == 201
        a_channel_id = cha.json()["id"]

        # Step 2: Project B
        cb = api_post("/api/v1/checks/", {"name": f"isoB-{UID}", "tags": f"iso-{UID}"}, headers=HEADERS_B)
        assert cb.status_code == 201
        b_check_id = cb.json()["id"]

        chb = api_post("/api/v1/channels/", {"kind": "webhook", "webhook_url": f"https://b-{UID}.test"}, headers=HEADERS_B)
        assert chb.status_code == 201
        b_channel_id = chb.json()["id"]

        # Step 3: A can't see B's checks
        ra = api_get("/api/v1/checks/", headers=HEADERS_A)
        a_ids = [c["id"] for c in ra.json()["checks"]]
        assert a_check_id in a_ids
        assert b_check_id not in a_ids

        # Step 4: B can't see A's channels
        rb = api_get("/api/v1/channels/", headers=HEADERS_B)
        b_ch_ids = [c["id"] for c in rb.json()["channels"]]
        assert b_channel_id in b_ch_ids
        assert a_channel_id not in b_ch_ids

        # Step 5: Cross-project access → 403
        cross = api_get(f"/api/v1/checks/{a_check_id}", headers=HEADERS_B)
        assert cross.status_code == 403

        cross2 = api_get(f"/api/v1/checks/{b_check_id}", headers=HEADERS_A)
        assert cross2.status_code == 403

        # Step 6: Both pings work (no auth needed)
        pa = ping(a_check_id)
        assert pa.status_code == 200
        pb = ping(b_check_id)
        assert pb.status_code == 200

        # Verify each updated correctly
        ra2 = api_get(f"/api/v1/checks/{a_check_id}", headers=HEADERS_A)
        assert ra2.json()["status"] == "up"
        rb2 = api_get(f"/api/v1/checks/{b_check_id}", headers=HEADERS_B)
        assert rb2.json()["status"] == "up"

        # Step 7: Project info
        pa_info = api_get("/api/v1/project/", headers=HEADERS_A)
        assert pa_info.json()["api_key"] == API_KEY_A
        assert pa_info.json()["check_count"] >= 1

        pb_info = api_get("/api/v1/project/", headers=HEADERS_B)
        assert pb_info.json()["api_key"] == API_KEY_B
        assert pb_info.json()["check_count"] >= 1


class TestUniqueUpsertWorkflow:
    """Unique field enables upsert semantics across multiple operations."""

    def test_upsert_preserves_state_while_updating_fields(self):
        """
        Pattern 5+8: Upsert logic + ordering sensitivity

        1. Create check with unique=['name'] → 201
        2. Ping it → status=up, n_pings=1
        3. Create again with same name + unique=['name'] → 200 (upsert)
        4. Verify it's the SAME check (same id)
        5. Verify the update applied (tags changed)
        6. Verify n_pings preserved (not reset to 0)
        7. Verify status preserved
        8. Different name → 201 (new check)
        """
        name = f"upsert-{UID}"

        # Step 1: Create
        r1 = api_post("/api/v1/checks/", {"name": name, "tags": "v1", "unique": ["name"]})
        assert r1.status_code == 201
        check_id = r1.json()["id"]
        assert r1.json()["tags"] == "v1"

        # Step 2: Ping
        ping(check_id)
        r2 = api_get(f"/api/v1/checks/{check_id}")
        assert r2.json()["status"] == "up"
        assert r2.json()["n_pings"] == 1

        # Step 3: Upsert (same name)
        r3 = api_post("/api/v1/checks/", {"name": name, "tags": "v2", "unique": ["name"]})
        assert r3.status_code == 200

        # Step 4: Same ID
        assert r3.json()["id"] == check_id

        # Step 5: Tags updated
        assert r3.json()["tags"] == "v2"

        # Step 6: n_pings preserved
        assert r3.json()["n_pings"] == 1

        # Step 7: Status preserved
        assert r3.json()["status"] == "up"

        # Step 8: Different name → new check
        r4 = api_post("/api/v1/checks/", {"name": f"different-{UID}", "unique": ["name"]})
        assert r4.status_code == 201
        assert r4.json()["id"] != check_id


class TestCheckWithChannelsCreation:
    """Creating/updating checks with channels='*' and specific IDs."""

    def test_channels_assignment_via_check_creation(self):
        """
        Pattern 2+7: Related data + cascade effects

        1. Create 2 channels
        2. Create check with channels='*' → both assigned
        3. Create third channel
        4. Create another check with channels='*' → all 3 assigned
        5. Update first check with channels='' → all cleared
        6. Update with specific channel ID → only that one assigned
        7. Verify channel.checks arrays updated correctly
        """
        # Step 1: Create channels
        ch1 = api_post("/api/v1/channels/", {"kind": "email", "name": f"star1-{UID}", "email": f"s1-{UID}@t.com"})
        ch2 = api_post("/api/v1/channels/", {"kind": "webhook", "name": f"star2-{UID}", "webhook_url": f"https://s2-{UID}.t"})
        assert ch1.status_code == 201
        assert ch2.status_code == 201
        ch1_id = ch1.json()["id"]
        ch2_id = ch2.json()["id"]

        # Step 2: Create check with channels='*'
        c1 = api_post("/api/v1/checks/", {"name": f"star-{UID}", "channels": "*"})
        assert c1.status_code == 201
        check1_id = c1.json()["id"]
        # Both channels should be assigned
        assert ch1_id in c1.json()["channels"]
        assert ch2_id in c1.json()["channels"]

        # Step 3: Create third channel
        ch3 = api_post("/api/v1/channels/", {"kind": "slack", "name": f"star3-{UID}", "webhook_url": f"https://s3-{UID}.t"})
        assert ch3.status_code == 201
        ch3_id = ch3.json()["id"]

        # Step 4: New check with '*' gets all 3
        c2 = api_post("/api/v1/checks/", {"name": f"star2-{UID}", "channels": "*"})
        assert c2.status_code == 201
        assert ch1_id in c2.json()["channels"]
        assert ch2_id in c2.json()["channels"]
        assert ch3_id in c2.json()["channels"]

        # Step 5: Clear all channels from first check
        ur = api_post(f"/api/v1/checks/{check1_id}", {"channels": ""})
        assert ur.status_code == 200
        assert ur.json()["channels"] == ""

        # Step 6: Assign specific channel
        ur2 = api_post(f"/api/v1/checks/{check1_id}", {"channels": ch3_id})
        assert ur2.status_code == 200
        assert ch3_id in ur2.json()["channels"]
        assert ch1_id not in ur2.json()["channels"]

        # Step 7: Verify channel's checks array
        chr3 = api_get(f"/api/v1/channels/{ch3_id}")
        assert check1_id in chr3.json()["checks"]


class TestProjectInfoWorkflow:
    """Project endpoint reflects real counts."""

    def test_project_counts_reflect_reality(self):
        """
        Pattern 5: Computed values actually computed

        1. Get initial project info
        2. Create 2 checks → check_count increases by 2
        3. Create 1 channel → channel_count increases by 1
        4. Delete 1 check → check_count decreases
        5. Verify api_key in response matches header
        """
        # Step 1: Initial
        r0 = api_get("/api/v1/project/")
        assert r0.status_code == 200
        initial_checks = r0.json()["check_count"]
        initial_channels = r0.json()["channel_count"]
        assert r0.json()["api_key"] == API_KEY_A

        # Step 2: Create 2 checks
        c1 = api_post("/api/v1/checks/", {"name": f"proj1-{UID}"})
        c2 = api_post("/api/v1/checks/", {"name": f"proj2-{UID}"})
        assert c1.status_code == 201
        assert c2.status_code == 201

        r1 = api_get("/api/v1/project/")
        assert r1.json()["check_count"] == initial_checks + 2

        # Step 3: Create 1 channel
        ch = api_post("/api/v1/channels/", {"kind": "email", "email": f"proj-{UID}@t.com"})
        assert ch.status_code == 201

        r2 = api_get("/api/v1/project/")
        assert r2.json()["channel_count"] == initial_channels + 1

        # Step 4: Delete 1 check
        api_delete(f"/api/v1/checks/{c1.json()['id']}")
        r3 = api_get("/api/v1/project/")
        assert r3.json()["check_count"] == initial_checks + 1

        # Step 5: Verify api_key
        assert r3.json()["api_key"] == API_KEY_A


class TestFlipFilteringWorkflow:
    """Flips can be filtered by start/end timestamps."""

    def test_flip_timestamp_filtering(self):
        """
        Pattern 3+5: Filter parameters work + data computed correctly

        1. Create check
        2. Ping → flip (new→up)
        3. Derive a filter boundary from the first server timestamp
        4. Fail after the boundary → flip (up→down)
        5. Filter flips by start boundary → should only have the down flip
        6. Filter by end boundary → should only have the up flip
        """
        cr = api_post("/api/v1/checks/", {"name": f"flipfilt-{UID}", "timeout": 86400, "grace": 3600})
        assert cr.status_code == 201
        check_id = cr.json()["id"]

        # Step 2: First ping
        ping(check_id)

        # Step 3: Use the server's timestamp to avoid client/server clock skew.
        first_flips = api_get(f"/api/v1/checks/{check_id}/flips/").json()["flips"]
        first_flip_at = datetime.fromisoformat(first_flips[0]["timestamp"].replace("Z", "+00:00"))
        t2 = (first_flip_at + timedelta(microseconds=1)).isoformat()

        # Ensure the second flip is later even if timestamps have one-second precision.
        time.sleep(1.1)

        # Step 4: Fail
        ping(check_id, "fail")

        # Step 5: All flips
        r_all = api_get(f"/api/v1/checks/{check_id}/flips/")
        all_flips = r_all.json()["flips"]
        assert len(all_flips) >= 2

        # Filter by start boundary → only flips after it (the down flip)
        r_after = api_get(f"/api/v1/checks/{check_id}/flips/", params={"start": t2})
        after_flips = r_after.json()["flips"]
        assert len(after_flips) >= 1
        # The down flip (up=0) should be here
        assert any(f["up"] == 0 for f in after_flips)

        # Filter by end boundary → only flips before it (the up flip)
        r_before = api_get(f"/api/v1/checks/{check_id}/flips/", params={"end": t2})
        before_flips = r_before.json()["flips"]
        assert len(before_flips) >= 1
        # The up flip (up=1) should be here
        assert any(f["up"] == 1 for f in before_flips)


class TestIntegrationCRUDWorkflow:
    """Integration endpoints CRUD lifecycle."""

    def test_integration_full_lifecycle(self):
        """
        Pattern 1+4: Field names + status codes

        1. Create integration → 201, is_active=True by default
        2. Get it → verify all fields present
        3. Update is_active=False → verify reflected
        4. List integrations → verify in list
        5. Delete → 200, verify gone (404)
        6. Verify integration isolation between projects
        """
        # Step 1: Create
        r1 = api_post("/api/v1/integrations/", {
            "kind": "webhook",
            "name": f"integ-{UID}",
            "webhook_url": f"https://integ-{UID}.test/hook"
        })
        assert r1.status_code == 201
        integ = r1.json()
        integ_id = integ["id"]
        assert integ["is_active"] is True
        assert integ["kind"] == "webhook"
        assert integ["name"] == f"integ-{UID}"

        # Step 2: Get
        r2 = api_get(f"/api/v1/integrations/{integ_id}")
        assert r2.status_code == 200
        assert "id" in r2.json()
        assert "kind" in r2.json()
        assert "is_active" in r2.json()
        assert "checks" in r2.json()
        assert isinstance(r2.json()["checks"], list)

        # Step 3: Update
        r3 = api_put(f"/api/v1/integrations/{integ_id}", {"is_active": False, "name": f"updated-{UID}"})
        assert r3.status_code == 200
        assert r3.json()["is_active"] is False
        assert r3.json()["name"] == f"updated-{UID}"

        # Step 4: List
        r4 = api_get("/api/v1/integrations/")
        assert r4.status_code == 200
        ids = [i["id"] for i in r4.json()["integrations"]]
        assert integ_id in ids

        # Step 5: Delete
        r5 = api_delete(f"/api/v1/integrations/{integ_id}")
        assert r5.status_code == 200
        assert r5.json()["id"] == integ_id

        r6 = api_get(f"/api/v1/integrations/{integ_id}")
        assert r6.status_code == 404

        # Step 6: Isolation
        i_b = api_post("/api/v1/integrations/", {
            "kind": "email",
            "name": f"b-integ-{UID}",
            "email": f"b-{UID}@test.com"
        }, headers=HEADERS_B)
        assert i_b.status_code == 201
        b_id = i_b.json()["id"]

        # A can't see B's integrations
        r7 = api_get("/api/v1/integrations/")
        a_ids = [i["id"] for i in r7.json()["integrations"]]
        assert b_id not in a_ids


class TestDeleteCascadeWorkflow:
    """Deleting entities has proper cascade/cleanup effects."""

    def test_delete_check_cleans_up_relationships(self):
        """
        Pattern 7: Cascade effects

        1. Create check + channel
        2. Assign channel to check
        3. Verify channel.checks includes the check
        4. Delete the check
        5. Verify channel.checks no longer includes deleted check
        6. Channel still exists and works
        """
        # Steps 1-2
        cr = api_post("/api/v1/checks/", {"name": f"cascade-{UID}"})
        check_id = cr.json()["id"]
        chr = api_post("/api/v1/channels/", {"kind": "email", "email": f"casc-{UID}@test.com"})
        ch_id = chr.json()["id"]
        api_post(f"/api/v1/checks/{check_id}/channels/{ch_id}", {})

        # Step 3: Verify assignment
        r1 = api_get(f"/api/v1/channels/{ch_id}")
        assert check_id in r1.json()["checks"]

        # Step 4: Delete check
        dr = api_delete(f"/api/v1/checks/{check_id}")
        assert dr.status_code == 200

        # Step 5: Channel should no longer reference deleted check
        r2 = api_get(f"/api/v1/channels/{ch_id}")
        assert r2.status_code == 200
        assert check_id not in r2.json()["checks"]

        # Step 6: Channel still works
        assert r2.json()["kind"] == "email"
        assert r2.json()["id"] == ch_id
