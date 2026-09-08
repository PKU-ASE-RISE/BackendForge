"""
BackendForge — L2 Integration Tests for Gotify Task

Adversarial tests targeting common LLM coding agent bugs:
- Pattern 1: camelCase/snake_case field name confusion
- Pattern 2: Nested/related data not returned correctly
- Pattern 3: Parameters declared but not implemented (pagination, ordering)
- Pattern 4: Status code errors (200 vs 201 vs 204)
- Pattern 5: Business logic "exists but behavior empty"
- Pattern 7: Cascade/side-effect omissions
- Pattern 8: Uniqueness/ordering sensitivity

"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

# Each test run uses unique keys to avoid cross-run contamination
RUN_ID = uuid.uuid4().hex[:8]
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


def ensure_admin():
    """Ensure the admin user is auto-created first."""
    api_get("/current/user", headers=ADMIN_HEADERS)


# ════════════════════════════════════════════════════════════════════════
# L2 Integration Tests
# ════════════════════════════════════════════════════════════════════════


class TestApplicationFieldNames:
    """Pattern 1: Verify camelCase field names in application responses."""

    def test_create_application_returns_all_camelcase_fields(self):
        """Create an app with all optional fields → verify EXACT camelCase keys in response."""
        ensure_admin()
        unique_name = f"CamelApp-{uuid.uuid4().hex[:8]}"
        resp = api_post("/applications", {
            "name": unique_name,
            "description": "A described app",
            "defaultPriority": 5,
        })
        assert resp.status_code == 200
        app = resp.json()

        # Verify ALL required camelCase keys exist
        assert "id" in app, "Missing 'id' field"
        assert "token" in app, "Missing 'token' field"
        assert "name" in app, "Missing 'name' field"
        assert "description" in app, "Missing 'description' field"
        assert "defaultPriority" in app, "Missing 'defaultPriority' (camelCase) field"
        assert "lastUsed" in app, "Missing 'lastUsed' (camelCase) field"

        # Verify NO snake_case variants snuck in
        assert "default_priority" not in app, "Found snake_case 'default_priority' — must be camelCase"
        assert "last_used" not in app, "Found snake_case 'last_used' — must be camelCase"

        # Verify values
        assert app["name"] == unique_name
        assert app["description"] == "A described app"
        assert app["defaultPriority"] == 5
        assert isinstance(app["id"], int)
        assert len(app["token"]) >= 15

    def test_list_applications_camelcase_fields(self):
        """GET /applications returns list with camelCase fields."""
        ensure_admin()
        key = f"camellist-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        api_post("/applications", {"name": "CamelListApp", "defaultPriority": 3}, headers=h)

        resp = api_get("/applications", headers=h)
        assert resp.status_code == 200
        apps = resp.json()
        assert len(apps) == 1
        app = apps[0]
        assert "defaultPriority" in app
        assert "lastUsed" in app
        assert "default_priority" not in app
        assert "last_used" not in app
        assert app["defaultPriority"] == 3


class TestApplicationCreateAndRoundtrip:
    """Pattern 1+2: Create → GET roundtrip with full field verification."""

    def test_create_then_list_preserves_all_fields(self):
        """Create app with ALL optional fields → list apps → verify every field roundtrips."""
        ensure_admin()
        key = f"roundtrip-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        unique_name = f"RoundtripApp-{uuid.uuid4().hex[:8]}"

        # Create with all fields
        create_resp = api_post("/applications", {
            "name": unique_name,
            "description": "Detailed description here",
            "defaultPriority": 8,
        }, headers=h)
        assert create_resp.status_code == 200
        created = create_resp.json()
        app_id = created["id"]
        token = created["token"]

        # GET the list back
        list_resp = api_get("/applications", headers=h)
        assert list_resp.status_code == 200
        apps = list_resp.json()
        assert len(apps) == 1

        fetched = apps[0]
        # Verify EVERY field roundtrips correctly
        assert fetched["id"] == app_id
        assert fetched["token"] == token
        assert fetched["name"] == unique_name
        assert fetched["description"] == "Detailed description here"
        assert fetched["defaultPriority"] == 8

    def test_application_default_values(self):
        """Create app with ONLY required field → verify defaults are correctly applied."""
        ensure_admin()
        key = f"defaults-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        name = f"DefaultApp-{uuid.uuid4().hex[:8]}"

        resp = api_post("/applications", {"name": name}, headers=h)
        assert resp.status_code == 200
        app = resp.json()

        # Defaults per spec
        assert app["description"] == "", f"Default description should be empty string, got: {app['description']!r}"
        assert app["defaultPriority"] == 0, f"Default priority should be 0, got: {app['defaultPriority']}"


class TestTokenImmutability:
    """Pattern 5: Token MUST NOT change when application/client is updated."""

    def test_app_token_immutable_after_update(self):
        """Create app → note token → update name+description → verify token unchanged."""
        ensure_admin()
        key = f"immutable-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Create
        create_resp = api_post("/applications", {
            "name": "ImmutableApp",
            "description": "v1",
            "defaultPriority": 1,
        }, headers=h)
        assert create_resp.status_code == 200
        original = create_resp.json()
        original_token = original["token"]
        app_id = original["id"]

        # Update name, description, and priority
        update_resp = api_put(f"/applications/{app_id}", {
            "name": "ImmutableAppRenamed",
            "description": "v2 updated",
            "defaultPriority": 9,
        }, headers=h)
        assert update_resp.status_code == 200
        updated = update_resp.json()

        # Token MUST be identical
        assert updated["token"] == original_token, \
            f"Token changed after update! {original_token!r} → {updated['token']!r}"

        # Other fields should be updated
        assert updated["name"] == "ImmutableAppRenamed"
        assert updated["description"] == "v2 updated"
        assert updated["defaultPriority"] == 9

    def test_client_token_immutable_after_update(self):
        """Create client → note token → update name → verify token unchanged."""
        ensure_admin()
        key = f"clientimm-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        create_resp = api_post("/clients", {"name": "ImmClient"}, headers=h)
        assert create_resp.status_code == 200
        original = create_resp.json()
        original_token = original["token"]
        client_id = original["id"]

        update_resp = api_put(f"/clients/{client_id}", {"name": "RenamedClient"}, headers=h)
        assert update_resp.status_code == 200
        updated = update_resp.json()

        assert updated["token"] == original_token, \
            f"Client token changed after update! {original_token!r} → {updated['token']!r}"
        assert updated["name"] == "RenamedClient"


class TestStatusCodes:
    """Pattern 4: Verify EXACT status codes (not 201, not 204)."""

    def test_create_application_returns_200_not_201(self):
        """POST /applications → 200 (Gotify uses 200 for creation, NOT 201)."""
        ensure_admin()
        resp = api_post("/applications", {"name": f"StatusApp-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_create_message_returns_200_not_201(self):
        """POST /messages → 200 (not 201)."""
        ensure_admin()
        key = f"status-msg-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "StatusMsgApp"}, headers=h)
        app_id = app_resp.json()["id"]

        resp = api_post("/messages", {"message": "test", "appid": app_id}, headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_create_client_returns_200_not_201(self):
        """POST /clients → 200 (not 201)."""
        ensure_admin()
        resp = api_post("/clients", {"name": f"StatusClient-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_delete_application_returns_200_not_204(self):
        """DELETE /applications/{id} → 200 (not 204)."""
        ensure_admin()
        key = f"status-del-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "DelStatusApp"}, headers=h)
        app_id = app_resp.json()["id"]

        resp = api_delete(f"/applications/{app_id}", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_delete_message_returns_200_not_204(self):
        """DELETE /messages/{id} → 200 (not 204)."""
        ensure_admin()
        key = f"status-delmsg-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "DelMsgStatusApp"}, headers=h)
        app_id = app_resp.json()["id"]
        msg_resp = api_post("/messages", {"message": "delete me", "appid": app_id}, headers=h)
        msg_id = msg_resp.json()["id"]

        resp = api_delete(f"/messages/{msg_id}", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_delete_all_messages_returns_200_not_204(self):
        """DELETE /messages → 200 (not 204)."""
        ensure_admin()
        key = f"status-delall-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        resp = api_delete("/messages", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_delete_client_returns_200_not_204(self):
        """DELETE /clients/{id} → 200 (not 204)."""
        ensure_admin()
        key = f"status-delcli-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        client_resp = api_post("/clients", {"name": "DelClientStatus"}, headers=h)
        client_id = client_resp.json()["id"]

        resp = api_delete(f"/clients/{client_id}", headers=h)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


class TestMessageFieldsAndRoundtrip:
    """Pattern 1+2: Message creation with all fields and roundtrip verification."""

    def test_create_message_with_all_fields_roundtrip(self):
        """Create message with ALL optional fields → GET back → verify every field."""
        ensure_admin()
        key = f"msground-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "MsgRoundApp"}, headers=h)
        app_id = app_resp.json()["id"]

        unique_msg = f"Hello-{uuid.uuid4().hex[:8]}"
        unique_title = f"Title-{uuid.uuid4().hex[:8]}"
        extras = {"client::display": {"contentType": "text/markdown"}, "key": "value"}

        create_resp = api_post("/messages", {
            "message": unique_msg,
            "title": unique_title,
            "priority": 7,
            "extras": extras,
            "appid": app_id,
        }, headers=h)
        assert create_resp.status_code == 200
        msg = create_resp.json()

        # Verify creation response fields
        assert msg["message"] == unique_msg
        assert msg["title"] == unique_title
        assert msg["priority"] == 7
        assert msg["appid"] == app_id
        assert msg["extras"] == extras
        assert "id" in msg
        assert "date" in msg
        msg_id = msg["id"]

        # GET messages and verify the message is there with correct fields
        list_resp = api_get("/messages", headers=h)
        assert list_resp.status_code == 200
        messages = list_resp.json()["messages"]
        found = [m for m in messages if m["id"] == msg_id]
        assert len(found) == 1, f"Message {msg_id} not found in list"
        retrieved = found[0]

        assert retrieved["message"] == unique_msg
        assert retrieved["title"] == unique_title
        assert retrieved["priority"] == 7
        assert retrieved["appid"] == app_id
        assert retrieved["extras"] == extras
        assert "date" in retrieved

    def test_message_default_fields(self):
        """Create message with only required fields → verify defaults."""
        ensure_admin()
        key = f"msgdef-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "MsgDefApp"}, headers=h)
        app_id = app_resp.json()["id"]

        resp = api_post("/messages", {"message": "Just the message", "appid": app_id}, headers=h)
        assert resp.status_code == 200
        msg = resp.json()

        # Defaults per spec
        assert msg["title"] == "", f"Default title should be empty string, got: {msg['title']!r}"
        assert msg["priority"] == 0, f"Default priority should be 0, got: {msg['priority']}"


class TestPaginationActuallyWorks:
    """Pattern 3: Verify pagination parameters are actually implemented."""

    def test_limit_restricts_results(self):
        """Create 5 messages, request limit=2 → MUST get exactly 2."""
        ensure_admin()
        key = f"paglimit-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "PagLimitApp"}, headers=h)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"Pag msg {i}", "appid": app_id}, headers=h)

        resp = api_get("/messages", params={"limit": 2}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2, \
            f"Expected exactly 2 messages with limit=2, got {len(data['messages'])}"
        assert data["paging"]["limit"] == 2
        assert data["paging"]["size"] == 2

    def test_since_parameter_actually_filters(self):
        """Create messages, use since parameter → verify only older messages returned."""
        ensure_admin()
        key = f"pagsince-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "PagSinceApp"}, headers=h)
        app_id = app_resp.json()["id"]

        # Create 5 messages and track IDs
        msg_ids = []
        for i in range(5):
            r = api_post("/messages", {"message": f"Since msg {i}", "appid": app_id}, headers=h)
            msg_ids.append(r.json()["id"])

        # Use the 4th message as "since" (should return messages with id < msg_ids[3])
        since_id = msg_ids[3]
        resp = api_get("/messages", params={"since": since_id}, headers=h)
        assert resp.status_code == 200
        messages = resp.json()["messages"]

        # ALL returned messages must have id < since_id
        for msg in messages:
            assert msg["id"] < since_id, \
                f"Message id {msg['id']} should be < since={since_id}"

        # And we should have gotten some messages (the first 3)
        assert len(messages) >= 1, "since parameter returned no messages — may not be implemented"

    def test_ordering_is_newest_first(self):
        """Create messages in sequence → verify they come back newest-first (desc by ID)."""
        ensure_admin()
        key = f"pagorder-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "PagOrderApp"}, headers=h)
        app_id = app_resp.json()["id"]

        # Create 5 messages
        created_ids = []
        for i in range(5):
            r = api_post("/messages", {"message": f"Order msg {i}", "appid": app_id}, headers=h)
            created_ids.append(r.json()["id"])

        resp = api_get("/messages", headers=h)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        returned_ids = [m["id"] for m in messages]

        # Must be strictly descending
        for i in range(len(returned_ids) - 1):
            assert returned_ids[i] > returned_ids[i + 1], \
                f"Messages not in descending order: {returned_ids}"

    def test_paging_next_field_present_when_more_data(self):
        """With more data than limit, paging.next must be non-empty string."""
        ensure_admin()
        key = f"pagnext-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "PagNextApp"}, headers=h)
        app_id = app_resp.json()["id"]

        for i in range(5):
            api_post("/messages", {"message": f"Next msg {i}", "appid": app_id}, headers=h)

        resp = api_get("/messages", params={"limit": 2}, headers=h)
        data = resp.json()
        assert data["paging"]["next"] != "", \
            "paging.next should be non-empty when there are more messages"

    def test_paging_next_field_empty_when_no_more_data(self):
        """When all data fits in limit, paging.next must be empty string."""
        ensure_admin()
        key = f"pagnone-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "PagNoneApp"}, headers=h)
        app_id = app_resp.json()["id"]

        # Create only 2 messages, request with limit=100
        api_post("/messages", {"message": "msg1", "appid": app_id}, headers=h)
        api_post("/messages", {"message": "msg2", "appid": app_id}, headers=h)

        resp = api_get("/messages", params={"limit": 100}, headers=h)
        data = resp.json()
        # next should be empty string (not absent, not None)
        assert data["paging"].get("next", "") == "", \
            f"paging.next should be empty string when no more data, got: {data['paging'].get('next')!r}"


class TestDeleteScoping:
    """Pattern 7: Delete operations must be correctly scoped."""

    def test_delete_app_messages_doesnt_affect_other_apps(self):
        """Delete messages for app1 → app2's messages must be untouched."""
        ensure_admin()
        key = f"delscope-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        # Create two apps
        app1_resp = api_post("/applications", {"name": "ScopeApp1"}, headers=h)
        app1_id = app1_resp.json()["id"]
        app2_resp = api_post("/applications", {"name": "ScopeApp2"}, headers=h)
        app2_id = app2_resp.json()["id"]

        # Create messages for both
        unique_msg1 = f"app1-msg-{uuid.uuid4().hex[:8]}"
        unique_msg2 = f"app2-msg-{uuid.uuid4().hex[:8]}"
        api_post("/messages", {"message": unique_msg1, "appid": app1_id}, headers=h)
        api_post("/messages", {"message": unique_msg2, "appid": app2_id}, headers=h)

        # Delete messages for app1 only
        resp = api_delete(f"/applications/{app1_id}/messages", headers=h)
        assert resp.status_code == 200

        # Verify app1 messages gone
        app1_msgs = api_get(f"/applications/{app1_id}/messages", headers=h).json()["messages"]
        assert len(app1_msgs) == 0, "App1 messages should be deleted"

        # Verify app2 messages UNTOUCHED
        app2_msgs = api_get(f"/applications/{app2_id}/messages", headers=h).json()["messages"]
        assert len(app2_msgs) == 1, f"App2 should still have 1 message, got {len(app2_msgs)}"
        assert app2_msgs[0]["message"] == unique_msg2

    def test_delete_single_message_doesnt_affect_others(self):
        """Delete one specific message → other messages from same app still exist."""
        ensure_admin()
        key = f"delsingle-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "DelSingleApp"}, headers=h)
        app_id = app_resp.json()["id"]

        # Create 3 messages
        msg_ids = []
        for i in range(3):
            r = api_post("/messages", {"message": f"msg-{i}", "appid": app_id}, headers=h)
            msg_ids.append(r.json()["id"])

        # Delete middle message
        resp = api_delete(f"/messages/{msg_ids[1]}", headers=h)
        assert resp.status_code == 200

        # Verify only that one is gone
        msgs_resp = api_get("/messages", headers=h)
        remaining_ids = [m["id"] for m in msgs_resp.json()["messages"]]
        assert msg_ids[0] in remaining_ids, "First message should still exist"
        assert msg_ids[1] not in remaining_ids, "Deleted message should be gone"
        assert msg_ids[2] in remaining_ids, "Third message should still exist"


class TestClientFieldNames:
    """Pattern 1: Verify camelCase field names in client responses."""

    def test_create_client_camelcase_fields(self):
        """POST /clients → response has camelCase lastUsed, not snake_case."""
        ensure_admin()
        key = f"clicamel-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        resp = api_post("/clients", {"name": "CamelClient"}, headers=h)
        assert resp.status_code == 200
        client = resp.json()

        assert "id" in client
        assert "token" in client
        assert "name" in client
        assert "lastUsed" in client, "Missing camelCase 'lastUsed' field"
        assert "last_used" not in client, "Found snake_case 'last_used'"
        assert len(client["token"]) >= 15

    def test_list_clients_camelcase_fields(self):
        """GET /clients → all items have camelCase fields."""
        ensure_admin()
        key = f"clilist-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        api_post("/clients", {"name": "ListCamelClient"}, headers=h)

        resp = api_get("/clients", headers=h)
        assert resp.status_code == 200
        clients = resp.json()
        assert len(clients) == 1
        assert "lastUsed" in clients[0]
        assert "last_used" not in clients[0]


class TestVersionAndHealthFields:
    """Pattern 1: Verify camelCase in version/health responses."""

    def test_version_response_camelcase(self):
        """GET /version must have 'buildDate' (camelCase) not 'build_date'."""
        resp = requests.get(f"{BASE_URL}/version", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "commit" in data
        assert "buildDate" in data, "Missing camelCase 'buildDate'"
        assert "build_date" not in data, "Found snake_case 'build_date'"

    def test_health_response_fields(self):
        """GET /health returns both 'health' and 'database' fields."""
        resp = requests.get(f"{BASE_URL}/health", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "health" in data
        assert "database" in data
        # Values should be strings
        assert isinstance(data["health"], str)
        assert isinstance(data["database"], str)


class TestPagingObjectStructure:
    """Pattern 1+3: Paging object must have correct structure and field names."""

    def test_paging_object_fields(self):
        """GET /messages response must have paging with size, since, limit, next."""
        ensure_admin()
        key = f"pagobj-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)

        resp = api_get("/messages", headers=h)
        assert resp.status_code == 200
        data = resp.json()

        assert "messages" in data, "Response missing 'messages' key"
        assert "paging" in data, "Response missing 'paging' key"

        paging = data["paging"]
        assert "size" in paging, "paging missing 'size'"
        assert "since" in paging, "paging missing 'since'"
        assert "limit" in paging, "paging missing 'limit'"
        # 'next' may be present or default to empty
        # The key must exist in the response
        assert "next" in paging, "paging missing 'next' field"

    def test_app_messages_paging_object(self):
        """GET /applications/{id}/messages also returns paging object."""
        ensure_admin()
        key = f"apppagobj-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        app_resp = api_post("/applications", {"name": "AppPagObjApp"}, headers=h)
        app_id = app_resp.json()["id"]

        resp = api_get(f"/applications/{app_id}/messages", headers=h)
        assert resp.status_code == 200
        data = resp.json()

        assert "messages" in data
        assert "paging" in data
        paging = data["paging"]
        assert "size" in paging
        assert "since" in paging
        assert "limit" in paging
        assert "next" in paging


class TestUniqueConstraints:
    """Pattern 8: Uniqueness constraints actually enforced."""

    def test_duplicate_app_name_same_user_rejected(self):
        """Same user cannot create two apps with same name → 400."""
        ensure_admin()
        key = f"dupapp-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        name = f"UniqueApp-{uuid.uuid4().hex[:8]}"

        resp1 = api_post("/applications", {"name": name}, headers=h)
        assert resp1.status_code == 200

        resp2 = api_post("/applications", {"name": name}, headers=h)
        assert resp2.status_code == 400, \
            f"Duplicate app name should return 400, got {resp2.status_code}"

    def test_same_app_name_different_users_allowed(self):
        """Different users CAN have apps with the same name."""
        ensure_admin()
        key1 = f"dupuser1-{uuid.uuid4().hex[:8]}"
        key2 = f"dupuser2-{uuid.uuid4().hex[:8]}"
        h1 = headers_for(key1)
        h2 = headers_for(key2)
        name = f"SharedName-{uuid.uuid4().hex[:8]}"

        resp1 = api_post("/applications", {"name": name}, headers=h1)
        assert resp1.status_code == 200

        resp2 = api_post("/applications", {"name": name}, headers=h2)
        assert resp2.status_code == 200, \
            f"Different users should be able to use same app name, got {resp2.status_code}"


class TestUserFieldsAndAuth:
    """Pattern 1+4: User response field verification."""

    def test_current_user_response_fields(self):
        """GET /current/user returns id, name, admin (no snake_case)."""
        ensure_admin()
        resp = api_get("/current/user", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        user = resp.json()
        assert "id" in user
        assert "name" in user
        assert "admin" in user
        assert isinstance(user["id"], int)
        assert isinstance(user["name"], str)
        assert isinstance(user["admin"], bool)

    def test_non_admin_forbidden_on_user_endpoints(self):
        """Non-admin → 403 on admin endpoints (not 401, not 404)."""
        ensure_admin()
        key = f"nonadmin-{uuid.uuid4().hex[:8]}"
        h = headers_for(key)
        # Trigger user creation
        api_get("/current/user", headers=h)

        resp = api_get("/users", headers=h)
        assert resp.status_code == 403, f"Non-admin should get 403, got {resp.status_code}"

    def test_missing_auth_returns_401(self):
        """No X-Gotify-Key header → 401 (not 403, not 400)."""
        resp = requests.get(f"{BASE_URL}/applications", timeout=30)
        assert resp.status_code == 401, f"Missing auth should return 401, got {resp.status_code}"
