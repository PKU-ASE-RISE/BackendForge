"""
BackendForge — L3 Workflow Tests for Gotify Task

Adversarial multi-step workflow tests targeting common LLM coding agent bugs.
Each test exercises 6-12 steps across multiple entities with 12-20 assertions.

Patterns targeted:
- Pattern 1: camelCase/snake_case confusion
- Pattern 3: Parameters declared but not implemented
- Pattern 6: Data isolation/permission failures
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Ordering/uniqueness issues

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_KEY = "admin-user"  # First user → admin
UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def headers_for(key: str) -> dict:
    return {"X-Gotify-Key": key, "Content-Type": "application/json"}


ADMIN_HEADERS = headers_for(ADMIN_KEY)


def api_get(path, params=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.get(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def api_post(path, json_data=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_put(path, json_data=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30)


def api_delete(path, params=None, headers=None):
    request_headers = ADMIN_HEADERS if headers is None else headers
    return requests.delete(f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30)


def missing_id(items):
    used_ids = {item["id"] for item in items}
    return next(candidate for candidate in range(999999, 999999 + len(used_ids) + 1) if candidate not in used_ids)


def ensure_admin():
    """Ensure the admin user is auto-created first."""
    api_get("/current/user", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════════
# L3 Workflow Tests
# ════════════════════════════════════════════════════════════════════════


class TestMultiUserIsolation:
    """Pattern 6: Multi-user data isolation — User A's data must be invisible to User B."""

    def test_full_isolation_apps_messages_clients(self):
        """
        User A creates apps+messages+clients.
        User B queries all endpoints → MUST NOT see any of A's data.
        Then verify A still sees their own data.
        """
        ensure_admin()
        key_a = f"iso-a-{uuid.uuid4().hex[:8]}"
        key_b = f"iso-b-{uuid.uuid4().hex[:8]}"
        h_a = headers_for(key_a)
        h_b = headers_for(key_b)

        # Step 1: User A creates an app
        app_name = f"A-App-{uuid.uuid4().hex[:8]}"
        app_resp = api_post("/applications", {
            "name": app_name,
            "description": "User A's app",
            "defaultPriority": 3,
        }, headers=h_a)
        assert app_resp.status_code == 200
        app_a = app_resp.json()
        app_a_id = app_a["id"]

        # Step 2: User A creates messages
        unique_msg = f"A-secret-{uuid.uuid4().hex[:8]}"
        msg_resp = api_post("/messages", {
            "message": unique_msg,
            "title": "Secret",
            "priority": 5,
            "appid": app_a_id,
        }, headers=h_a)
        assert msg_resp.status_code == 200
        msg_a_id = msg_resp.json()["id"]

        # Step 3: User A creates a client
        client_name = f"A-Client-{uuid.uuid4().hex[:8]}"
        client_resp = api_post("/clients", {"name": client_name}, headers=h_a)
        assert client_resp.status_code == 200

        # Step 4: User B queries apps → must NOT see A's app
        b_apps = api_get("/applications", headers=h_b).json()
        b_app_names = [a["name"] for a in b_apps]
        assert app_name not in b_app_names, "User B should NOT see User A's applications"

        # Step 5: User B queries messages → must NOT see A's messages
        b_msgs = api_get("/messages", headers=h_b).json()["messages"]
        b_msg_texts = [m["message"] for m in b_msgs]
        assert unique_msg not in b_msg_texts, "User B should NOT see User A's messages"

        # Step 6: User B queries clients → must NOT see A's clients
        b_clients = api_get("/clients", headers=h_b).json()
        b_client_names = [c["name"] for c in b_clients]
        assert client_name not in b_client_names, "User B should NOT see User A's clients"

        # Step 7: User B tries to access A's app messages → 404
        resp = api_get(f"/applications/{app_a_id}/messages", headers=h_b)
        assert resp.status_code == 404, "User B accessing A's app messages should get 404"

        # Step 8: User B tries to delete A's message → 404
        resp = api_delete(f"/messages/{msg_a_id}", headers=h_b)
        assert resp.status_code == 404, "User B deleting A's message should get 404"

        # Step 9: User A can still see their own data
        a_apps = api_get("/applications", headers=h_a).json()
        assert any(a["name"] == app_name for a in a_apps), "User A should still see own app"

        a_msgs = api_get("/messages", headers=h_a).json()["messages"]
        assert any(m["message"] == unique_msg for m in a_msgs), "User A should still see own message"


class TestCascadeDeleteApplication:
    """Pattern 7: Deleting an app MUST cascade-delete its messages, but NOT other apps' data."""

    def test_delete_app_cascades_messages_preserves_other_app(self):
        """
        Create 2 apps → create messages for both → delete app1 →
        Verify app1's messages gone AND app2's messages untouched.
        Also verify the deleted app no longer appears in the apps list.
        """
        ensure_admin()
        key = f"cascade-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Step 1: Create two apps
        app1_resp = api_post("/applications", {"name": "CascadeApp1"}, headers=h)
        assert app1_resp.status_code == 200
        app1_id = app1_resp.json()["id"]

        app2_resp = api_post("/applications", {"name": "CascadeApp2"}, headers=h)
        assert app2_resp.status_code == 200
        app2_id = app2_resp.json()["id"]

        # Step 2: Create messages for app1
        app1_msg_ids = []
        for i in range(3):
            r = api_post("/messages", {"message": f"app1-msg-{i}", "appid": app1_id}, headers=h)
            assert r.status_code == 200
            app1_msg_ids.append(r.json()["id"])

        # Step 3: Create messages for app2
        app2_msg_unique = f"app2-preserved-{uuid.uuid4().hex[:8]}"
        r = api_post("/messages", {"message": app2_msg_unique, "appid": app2_id}, headers=h)
        assert r.status_code == 200
        app2_msg_id = r.json()["id"]

        # Step 4: Verify all messages exist before deletion
        all_msgs = api_get("/messages", headers=h).json()["messages"]
        all_ids = [m["id"] for m in all_msgs]
        for mid in app1_msg_ids:
            assert mid in all_ids, f"Pre-check: app1 msg {mid} should exist"
        assert app2_msg_id in all_ids, "Pre-check: app2 msg should exist"

        # Step 5: Delete app1
        del_resp = api_delete(f"/applications/{app1_id}", headers=h)
        assert del_resp.status_code == 200

        # Step 6: Verify app1 is gone from list
        apps = api_get("/applications", headers=h).json()
        app_ids = [a["id"] for a in apps]
        assert app1_id not in app_ids, "Deleted app1 should not appear in apps list"
        assert app2_id in app_ids, "App2 should still exist"

        # Step 7: Verify app1's messages are ALL gone
        all_msgs_after = api_get("/messages", headers=h).json()["messages"]
        remaining_ids = [m["id"] for m in all_msgs_after]
        for mid in app1_msg_ids:
            assert mid not in remaining_ids, f"App1 message {mid} should be cascade-deleted"

        # Step 8: Verify app2's messages are UNTOUCHED
        assert app2_msg_id in remaining_ids, \
            "App2 message should NOT be affected by deleting app1"
        app2_msgs = api_get(f"/applications/{app2_id}/messages", headers=h).json()["messages"]
        assert any(m["message"] == app2_msg_unique for m in app2_msgs), \
            "App2 message content should be preserved"


class TestAdminVsNonAdmin:
    """Pattern 6: Admin-only operations fail for non-admin, succeed after promotion."""

    def test_admin_promotion_unlocks_user_management(self):
        """
        1. Non-admin tries admin ops → 403
        2. Admin promotes them
        3. Same ops succeed
        """
        ensure_admin()
        non_admin_key = f"promoted-{uuid.uuid4().hex[:8]}"
        h_nonadmin = headers_for(non_admin_key)

        # Step 1: Trigger user creation (non-admin)
        me_resp = api_get("/current/user", headers=h_nonadmin)
        assert me_resp.status_code == 200
        user = me_resp.json()
        assert user["admin"] is False, "Newly created user should NOT be admin"
        user_id = user["id"]

        # Step 2: Non-admin tries to list users → 403
        resp = api_get("/users", headers=h_nonadmin)
        assert resp.status_code == 403, f"Non-admin list users should be 403, got {resp.status_code}"

        # Step 3: Non-admin tries to create user → 403
        resp = api_post("/users", {
            "name": f"hack-{uuid.uuid4().hex[:8]}",
            "pass": "x",
            "admin": False,
        }, headers=h_nonadmin)
        assert resp.status_code == 403

        # Step 4: Admin promotes the user
        promote_resp = api_put(f"/users/{user_id}", {
            "name": non_admin_key,
            "admin": True,
        }, headers=ADMIN_HEADERS)
        assert promote_resp.status_code == 200
        assert promote_resp.json()["admin"] is True

        # Step 5: Now the promoted user can list users
        resp = api_get("/users", headers=h_nonadmin)
        assert resp.status_code == 200, f"Promoted user should access /users, got {resp.status_code}"
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) >= 2  # At least admin + promoted user

        # Step 6: Promoted user can create a user
        new_name = f"created-by-promoted-{uuid.uuid4().hex[:8]}"
        resp = api_post("/users", {
            "name": new_name,
            "pass": "pw",
            "admin": False,
        }, headers=h_nonadmin)
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name


class TestFullNotificationFlow:
    """Pattern 3+7: End-to-end notification flow with pagination verification."""

    def test_create_app_send_messages_paginate_delete_cascade(self):
        """
        Full lifecycle:
        1. Create app → 2. Send 6 messages with varying priorities →
        3. Paginate (limit=3) → verify order → 4. Get page 2 using since →
        5. Delete subset → verify count → 6. Delete app → verify cascade
        """
        ensure_admin()
        key = f"flow-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Step 1: Create application
        app_resp = api_post("/applications", {
            "name": "FlowApp",
            "description": "Full flow test",
            "defaultPriority": 0,
        }, headers=h)
        assert app_resp.status_code == 200
        app = app_resp.json()
        app_id = app["id"]
        app_token = app["token"]
        assert len(app_token) >= 15

        # Step 2: Send 6 messages with different priorities
        msg_ids = []
        for i in range(6):
            r = api_post("/messages", {
                "message": f"Flow message #{i}",
                "title": f"Title {i}",
                "priority": i * 2,  # 0, 2, 4, 6, 8, 10
                "appid": app_id,
            }, headers=h)
            assert r.status_code == 200
            msg = r.json()
            assert msg["priority"] == i * 2
            msg_ids.append(msg["id"])

        # Step 3: Paginate — get first page (limit=3)
        page1_resp = api_get("/messages", params={"limit": 3}, headers=h)
        assert page1_resp.status_code == 200
        page1_data = page1_resp.json()
        page1_msgs = page1_data["messages"]
        assert len(page1_msgs) == 3, f"Expected 3 msgs with limit=3, got {len(page1_msgs)}"

        # Verify newest-first ordering
        page1_ids = [m["id"] for m in page1_msgs]
        assert page1_ids == sorted(page1_ids, reverse=True), "Page 1 not in desc order"

        # The newest 3 messages should be the last 3 created
        assert page1_ids[0] == msg_ids[5]  # newest
        assert page1_ids[1] == msg_ids[4]
        assert page1_ids[2] == msg_ids[3]

        # Step 4: Get page 2 using since parameter
        since_val = page1_msgs[-1]["id"]  # smallest ID on page 1
        page2_resp = api_get("/messages", params={"limit": 3, "since": since_val}, headers=h)
        assert page2_resp.status_code == 200
        page2_msgs = page2_resp.json()["messages"]
        assert len(page2_msgs) == 3, f"Expected 3 msgs on page 2, got {len(page2_msgs)}"

        # All page 2 message IDs should be < since_val
        for msg in page2_msgs:
            assert msg["id"] < since_val

        # Page 2 should contain the first 3 created messages (in desc order)
        page2_ids = [m["id"] for m in page2_msgs]
        assert page2_ids[0] == msg_ids[2]
        assert page2_ids[1] == msg_ids[1]
        assert page2_ids[2] == msg_ids[0]

        # Step 5: Delete 2 messages
        api_delete(f"/messages/{msg_ids[0]}", headers=h)
        api_delete(f"/messages/{msg_ids[1]}", headers=h)

        # Verify count decreased
        remaining_resp = api_get("/messages", headers=h)
        remaining_msgs = remaining_resp.json()["messages"]
        assert len(remaining_msgs) == 4, f"Expected 4 after deleting 2, got {len(remaining_msgs)}"

        # Verify deleted ones are gone
        remaining_ids = [m["id"] for m in remaining_msgs]
        assert msg_ids[0] not in remaining_ids
        assert msg_ids[1] not in remaining_ids

        # Step 6: Delete the app → cascade delete remaining messages
        del_resp = api_delete(f"/applications/{app_id}", headers=h)
        assert del_resp.status_code == 200

        # All messages should be gone
        final_msgs = api_get("/messages", headers=h).json()["messages"]
        for mid in msg_ids[2:]:  # remaining after step 5
            assert mid not in [m["id"] for m in final_msgs], \
                f"Message {mid} should be cascade-deleted with app"


class TestMessageOrderingUnderStress:
    """Pattern 3+8: Ordering correctness with many messages."""

    def test_rapid_message_creation_ordering(self):
        """
        Send 12 messages rapidly → verify they come back in STRICT descending ID order.
        Also verifies pagination works correctly across multiple pages.
        """
        ensure_admin()
        key = f"stress-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "StressApp"}, headers=h)
        app_id = app_resp.json()["id"]

        # Create 12 messages rapidly with unique content
        created_ids = []
        for i in range(12):
            r = api_post("/messages", {
                "message": f"Stress-{i}-{uuid.uuid4().hex[:6]}",
                "priority": i % 5,
                "appid": app_id,
            }, headers=h)
            assert r.status_code == 200
            created_ids.append(r.json()["id"])

        # IDs should be monotonically increasing at creation time
        for i in range(len(created_ids) - 1):
            assert created_ids[i] < created_ids[i + 1], \
                f"Created IDs not monotonically increasing: {created_ids}"

        # GET all messages — should be in reverse order (newest first)
        resp = api_get("/messages", params={"limit": 200}, headers=h)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        returned_ids = [m["id"] for m in messages]

        # Strict descending order
        for i in range(len(returned_ids) - 1):
            assert returned_ids[i] > returned_ids[i + 1], \
                f"Not in descending order at index {i}: {returned_ids[i]} vs {returned_ids[i+1]}"

        # The full set should match
        assert set(returned_ids) == set(created_ids)

        # Paginate: get first 5, then next 5
        page1 = api_get("/messages", params={"limit": 5}, headers=h).json()
        assert len(page1["messages"]) == 5
        assert page1["paging"]["size"] == 5

        since_val = page1["messages"][-1]["id"]
        page2 = api_get("/messages", params={"limit": 5, "since": since_val}, headers=h).json()
        assert len(page2["messages"]) == 5
        assert page2["paging"]["size"] == 5

        # No overlap between pages
        page1_ids = set(m["id"] for m in page1["messages"])
        page2_ids = set(m["id"] for m in page2["messages"])
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

        # All page2 IDs < all page1 IDs (since page1 is newest)
        assert max(page2_ids) < min(page1_ids), "Page 2 should have older messages than page 1"


class TestCrossEntityConsistency:
    """Pattern 7: After mutations, verify all related entities remain consistent."""

    def test_delete_messages_app_endpoint_still_works(self):
        """
        After deleting messages:
        - App endpoint still returns the app
        - App messages endpoint returns empty
        - Global message count reflects deletion
        """
        ensure_admin()
        key = f"consist-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Create app and messages
        app_resp = api_post("/applications", {"name": "ConsistApp", "defaultPriority": 4}, headers=h)
        assert app_resp.status_code == 200
        app_id = app_resp.json()["id"]
        app_token = app_resp.json()["token"]

        for i in range(3):
            api_post("/messages", {"message": f"consist-{i}", "appid": app_id}, headers=h)

        # Verify messages exist
        msgs_before = api_get(f"/applications/{app_id}/messages", headers=h).json()["messages"]
        assert len(msgs_before) == 3

        # Delete all messages for this app
        del_resp = api_delete(f"/applications/{app_id}/messages", headers=h)
        assert del_resp.status_code == 200

        # App endpoint still works and returns the app
        apps = api_get("/applications", headers=h).json()
        found_app = [a for a in apps if a["id"] == app_id]
        assert len(found_app) == 1, "App should still exist after deleting its messages"
        assert found_app[0]["token"] == app_token
        assert found_app[0]["defaultPriority"] == 4

        # App messages endpoint returns empty
        msgs_after = api_get(f"/applications/{app_id}/messages", headers=h).json()
        assert len(msgs_after["messages"]) == 0
        assert msgs_after["paging"]["size"] == 0

        # Global messages also empty
        global_msgs = api_get("/messages", headers=h).json()
        assert len(global_msgs["messages"]) == 0


class TestCascadeDeleteUser:
    """Pattern 7: Deleting a user cascades to ALL their data."""

    def test_delete_user_removes_all_data(self):
        """
        Admin creates user → user creates apps+clients+messages →
        Admin deletes user → verify ALL data gone but admin's data untouched.
        """
        ensure_admin()

        # Step 1: Admin creates a user
        target_name = f"target-{uuid.uuid4().hex[:8]}"
        create_resp = api_post("/users", {
            "name": target_name,
            "pass": "pw123",
            "admin": False,
        }, headers=ADMIN_HEADERS)
        assert create_resp.status_code == 200
        target_user = create_resp.json()
        target_id = target_user["id"]
        target_h = headers_for(target_name)

        # Step 2: Target user creates an app
        app_resp = api_post("/applications", {"name": "TargetApp"}, headers=target_h)
        assert app_resp.status_code == 200
        target_app_id = app_resp.json()["id"]

        # Step 3: Target user creates messages
        msg_resp = api_post("/messages", {
            "message": f"target-msg-{uuid.uuid4().hex[:8]}",
            "appid": target_app_id,
        }, headers=target_h)
        assert msg_resp.status_code == 200

        # Step 4: Target user creates a client
        client_resp = api_post("/clients", {"name": "TargetClient"}, headers=target_h)
        assert client_resp.status_code == 200

        # Step 5: Admin creates their own app (should be untouched)
        admin_app_name = f"AdminApp-{uuid.uuid4().hex[:8]}"
        admin_app_resp = api_post("/applications", {"name": admin_app_name}, headers=ADMIN_HEADERS)
        assert admin_app_resp.status_code == 200
        admin_app_id = admin_app_resp.json()["id"]

        # Step 6: Admin deletes the target user
        del_resp = api_delete(f"/users/{target_id}", headers=ADMIN_HEADERS)
        assert del_resp.status_code == 200

        # Step 7: Verify user is gone
        get_resp = api_get(f"/users/{target_id}", headers=ADMIN_HEADERS)
        assert get_resp.status_code == 404

        # Step 8: Admin's data is untouched
        admin_apps = api_get("/applications", headers=ADMIN_HEADERS).json()
        admin_app_ids = [a["id"] for a in admin_apps]
        assert admin_app_id in admin_app_ids, "Admin's app should be untouched"


class TestCannotDeleteSelf:
    """Pattern 8: Admin cannot delete themselves."""

    def test_admin_self_delete_blocked(self):
        """
        Admin gets own ID → tries to delete self → must get 400 →
        verify admin still exists and can operate afterwards.
        """
        ensure_admin()

        # Step 1: Get admin's own ID
        me_resp = api_get("/current/user", headers=ADMIN_HEADERS)
        assert me_resp.status_code == 200
        admin_id = me_resp.json()["id"]
        assert me_resp.json()["admin"] is True

        # Step 2: Try to delete self → 400
        del_resp = api_delete(f"/users/{admin_id}", headers=ADMIN_HEADERS)
        assert del_resp.status_code == 400, \
            f"Self-delete should return 400, got {del_resp.status_code}"

        # Step 3: Admin still exists and works
        still_me = api_get("/current/user", headers=ADMIN_HEADERS)
        assert still_me.status_code == 200
        assert still_me.json()["id"] == admin_id
        assert still_me.json()["admin"] is True

        # Step 4: Admin can still perform admin operations
        users_resp = api_get("/users", headers=ADMIN_HEADERS)
        assert users_resp.status_code == 200


class TestAppMessagesScopedPagination:
    """Pattern 3+5: GET /applications/{id}/messages pagination actually works."""

    def test_app_messages_pagination_with_since(self):
        """
        Create app → send 8 messages → paginate app messages with limit=3 →
        use since for page 2 → verify no overlap → verify all from correct app.
        """
        ensure_admin()
        key = f"appmsgpag-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Step 1: Create app
        app_resp = api_post("/applications", {"name": "AppMsgPagApp"}, headers=h)
        assert app_resp.status_code == 200
        app_id = app_resp.json()["id"]

        # Step 2: Create 8 messages
        created_ids = []
        for i in range(8):
            r = api_post("/messages", {
                "message": f"appmsg-{i}-{uuid.uuid4().hex[:6]}",
                "appid": app_id,
            }, headers=h)
            assert r.status_code == 200
            created_ids.append(r.json()["id"])

        # Step 3: Get page 1 with limit=3
        page1_resp = api_get(f"/applications/{app_id}/messages", params={"limit": 3}, headers=h)
        assert page1_resp.status_code == 200
        page1 = page1_resp.json()
        assert len(page1["messages"]) == 3
        assert page1["paging"]["size"] == 3
        assert page1["paging"]["limit"] == 3

        # Verify all from correct app
        for msg in page1["messages"]:
            assert msg["appid"] == app_id

        # Verify descending order
        page1_ids = [m["id"] for m in page1["messages"]]
        assert page1_ids == sorted(page1_ids, reverse=True)

        # Step 4: Get page 2 using since
        since_val = page1["messages"][-1]["id"]
        page2_resp = api_get(f"/applications/{app_id}/messages",
                             params={"limit": 3, "since": since_val}, headers=h)
        assert page2_resp.status_code == 200
        page2 = page2_resp.json()
        assert len(page2["messages"]) == 3

        # All page 2 IDs < since_val
        for msg in page2["messages"]:
            assert msg["id"] < since_val
            assert msg["appid"] == app_id

        # No overlap
        page2_ids = [m["id"] for m in page2["messages"]]
        assert set(page1_ids).isdisjoint(set(page2_ids))

        # Step 5: paging.next should be non-empty for page 1 (more data exists)
        assert page1["paging"].get("next", "") != "", \
            "paging.next should indicate more pages available"


class TestMultiAppMessageSegregation:
    """Pattern 5+7: Messages are properly segregated by app."""

    def test_messages_correctly_associated_to_apps(self):
        """
        Create 2 apps → send messages to each → query per-app →
        verify each endpoint returns ONLY that app's messages with correct appid values.
        Then delete messages from one app → verify cross-check.
        """
        ensure_admin()
        key = f"segreg-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Step 1: Create two apps
        app1_resp = api_post("/applications", {"name": "SegApp1"}, headers=h)
        app1_id = app1_resp.json()["id"]
        app2_resp = api_post("/applications", {"name": "SegApp2"}, headers=h)
        app2_id = app2_resp.json()["id"]

        # Step 2: Send 3 messages to app1 and 2 to app2
        app1_msgs = []
        for i in range(3):
            r = api_post("/messages", {
                "message": f"seg1-{i}-{uuid.uuid4().hex[:6]}",
                "appid": app1_id,
            }, headers=h)
            app1_msgs.append(r.json()["id"])

        app2_msgs = []
        for i in range(2):
            r = api_post("/messages", {
                "message": f"seg2-{i}-{uuid.uuid4().hex[:6]}",
                "appid": app2_id,
            }, headers=h)
            app2_msgs.append(r.json()["id"])

        # Step 3: Query app1's messages
        app1_data = api_get(f"/applications/{app1_id}/messages", headers=h).json()
        assert len(app1_data["messages"]) == 3
        for msg in app1_data["messages"]:
            assert msg["appid"] == app1_id, f"App1 endpoint returned msg with appid={msg['appid']}"

        # Step 4: Query app2's messages
        app2_data = api_get(f"/applications/{app2_id}/messages", headers=h).json()
        assert len(app2_data["messages"]) == 2
        for msg in app2_data["messages"]:
            assert msg["appid"] == app2_id, f"App2 endpoint returned msg with appid={msg['appid']}"

        # Step 5: Global messages should have all 5
        global_msgs = api_get("/messages", headers=h).json()["messages"]
        assert len(global_msgs) == 5

        # Step 6: Delete app1's messages
        del_resp = api_delete(f"/applications/{app1_id}/messages", headers=h)
        assert del_resp.status_code == 200

        # Step 7: App1 has 0 messages, app2 still has 2
        app1_after = api_get(f"/applications/{app1_id}/messages", headers=h).json()
        assert len(app1_after["messages"]) == 0

        app2_after = api_get(f"/applications/{app2_id}/messages", headers=h).json()
        assert len(app2_after["messages"]) == 2

        # Step 8: Global messages should now have only 2
        global_after = api_get("/messages", headers=h).json()["messages"]
        assert len(global_after) == 2
        for msg in global_after:
            assert msg["appid"] == app2_id


class TestTokenUniqueness:
    """Pattern 8: Every generated token must be unique."""

    def test_multiple_apps_have_unique_tokens(self):
        """Create multiple apps and clients → all tokens must be distinct."""
        ensure_admin()
        key = f"uniq-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        tokens = set()
        # Create 5 apps
        for i in range(5):
            r = api_post("/applications", {"name": f"UniqApp-{i}"}, headers=h)
            assert r.status_code == 200
            token = r.json()["token"]
            assert token not in tokens, f"Duplicate app token found: {token}"
            tokens.add(token)

        # Create 5 clients
        for i in range(5):
            r = api_post("/clients", {"name": f"UniqClient-{i}"}, headers=h)
            assert r.status_code == 200
            token = r.json()["token"]
            assert token not in tokens, f"Duplicate client token found: {token}"
            tokens.add(token)

        # All 10 tokens should be unique
        assert len(tokens) == 10


class TestMessageCreationValidation:
    """Pattern 5+6: Message creation validation — appid must belong to user."""

    def test_message_appid_validation_workflow(self):
        """
        User A creates app → User B tries to use A's appid → 400.
        User B creates own app → sends message successfully →
        Verify message has correct appid and user scope.
        """
        ensure_admin()
        key_a = f"msgval-a-{uuid.uuid4().hex[:8]}"
        key_b = f"msgval-b-{uuid.uuid4().hex[:8]}"
        h_a = headers_for(key_a)
        h_b = headers_for(key_b)

        # Step 1: User A creates an app
        app_a = api_post("/applications", {"name": "AApp"}, headers=h_a).json()
        app_a_id = app_a["id"]

        # Step 2: User B tries to use A's appid → must fail
        resp = api_post("/messages", {
            "message": "stolen attempt",
            "appid": app_a_id,
        }, headers=h_b)
        assert resp.status_code == 400, \
            f"Using another user's appid should return 400, got {resp.status_code}"

        # Step 3: User B creates own app
        app_b = api_post("/applications", {"name": "BApp"}, headers=h_b).json()
        app_b_id = app_b["id"]

        # Step 4: User B sends message with own appid → success
        unique_msg = f"b-msg-{uuid.uuid4().hex[:8]}"
        msg_resp = api_post("/messages", {
            "message": unique_msg,
            "appid": app_b_id,
        }, headers=h_b)
        assert msg_resp.status_code == 200
        msg = msg_resp.json()
        assert msg["appid"] == app_b_id
        assert msg["message"] == unique_msg

        # Step 5: User A cannot see B's message
        a_msgs = api_get("/messages", headers=h_a).json()["messages"]
        a_msg_texts = [m["message"] for m in a_msgs]
        assert unique_msg not in a_msg_texts, "User A should not see User B's message"

        # Step 6: User B can see their own message
        b_msgs = api_get("/messages", headers=h_b).json()["messages"]
        b_msg_texts = [m["message"] for m in b_msgs]
        assert unique_msg in b_msg_texts, "User B should see their own message"

        # Step 7: Message without appid → 400
        resp = api_post("/messages", {"message": "no appid"}, headers=h_b)
        assert resp.status_code == 400

        # Step 8: Message with non-existent appid → 400
        app_id = missing_id(api_get("/applications", headers=h_b).json())
        resp = api_post("/messages", {"message": "bad appid", "appid": app_id}, headers=h_b)
        assert resp.status_code == 400
