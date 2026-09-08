"""
Test suite for Hoppscotch API.
Tests cover: collections, requests, environments, history, teams, team collections,
team requests, team environments, import/export, duplication, and role enforcement.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

USER1 = "user1"
USER2 = "user2"
USER3 = "user3"


def headers(user=None):
    if user is None:
        user = USER1
    return {"X-API-Key": user, "Content-Type": "application/json"}


# ==================== AUTH ====================

class TestAuth:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/collections")
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/collections", headers={"X-API-Key": ""})
        assert resp.status_code == 401


# ==================== COLLECTIONS ====================

class TestCollections:
    def test_create_collection(self):
        resp = requests.post(f"{BASE_URL}/collections", json={
            "name": "My API Collection",
            "description": "Test collection"
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My API Collection"
        assert data["description"] == "Test collection"
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert data["parentId"] is None
        assert "order" in data

    def test_create_collection_missing_name_returns_400(self):
        resp = requests.post(f"{BASE_URL}/collections", json={
            "description": "No name"
        }, headers=headers())
        assert resp.status_code == 400

    def test_list_collections(self):
        # Create two collections
        requests.post(f"{BASE_URL}/collections", json={"name": "Col A"}, headers=headers())
        requests.post(f"{BASE_URL}/collections", json={"name": "Col B"}, headers=headers())
        resp = requests.get(f"{BASE_URL}/collections", headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_get_collection(self):
        create_resp = requests.post(f"{BASE_URL}/collections", json={"name": "Get Me"}, headers=headers())
        col_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/collections/{col_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_get_nonexistent_collection_returns_404(self):
        resp = requests.get(f"{BASE_URL}/collections/nonexistent-id", headers=headers())
        assert resp.status_code == 404

    def test_update_collection(self):
        create_resp = requests.post(f"{BASE_URL}/collections", json={"name": "Old Name"}, headers=headers())
        col_id = create_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/collections/{col_id}", json={
            "name": "New Name",
            "description": "Updated"
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["description"] == "Updated"

    def test_delete_collection(self):
        create_resp = requests.post(f"{BASE_URL}/collections", json={"name": "Delete Me"}, headers=headers())
        col_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/collections/{col_id}", headers=headers())
        assert resp.status_code == 204
        # Verify deleted
        get_resp = requests.get(f"{BASE_URL}/collections/{col_id}", headers=headers())
        assert get_resp.status_code == 404

    def test_nested_collection(self):
        parent_resp = requests.post(f"{BASE_URL}/collections", json={"name": "Parent"}, headers=headers())
        parent_id = parent_resp.json()["id"]
        child_resp = requests.post(f"{BASE_URL}/collections", json={
            "name": "Child",
            "parentId": parent_id
        }, headers=headers())
        assert child_resp.status_code == 201
        child = child_resp.json()
        assert child["parentId"] == parent_id

    def test_list_collections_filter_by_parent(self):
        parent_resp = requests.post(f"{BASE_URL}/collections", json={"name": "FilterParent"}, headers=headers())
        parent_id = parent_resp.json()["id"]
        requests.post(f"{BASE_URL}/collections", json={"name": "FilterChild1", "parentId": parent_id}, headers=headers())
        requests.post(f"{BASE_URL}/collections", json={"name": "FilterChild2", "parentId": parent_id}, headers=headers())
        resp = requests.get(f"{BASE_URL}/collections", params={"parentId": parent_id}, headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        for col in data:
            assert col["parentId"] == parent_id

    def test_delete_collection_cascades(self):
        parent_resp = requests.post(f"{BASE_URL}/collections", json={"name": "CascadeParent"}, headers=headers())
        parent_id = parent_resp.json()["id"]
        child_resp = requests.post(f"{BASE_URL}/collections", json={"name": "CascadeChild", "parentId": parent_id}, headers=headers())
        child_id = child_resp.json()["id"]
        # Create request in child
        req_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": child_id,
            "name": "CascadeReq",
            "method": "GET",
            "url": "http://example.com"
        }, headers=headers())
        req_id = req_resp.json()["id"]
        # Delete parent
        requests.delete(f"{BASE_URL}/collections/{parent_id}", headers=headers())
        # Child and request should be gone
        assert requests.get(f"{BASE_URL}/collections/{child_id}", headers=headers()).status_code == 404
        assert requests.get(f"{BASE_URL}/requests/{req_id}", headers=headers()).status_code == 404

    def test_collection_ordering(self):
        resp1 = requests.post(f"{BASE_URL}/collections", json={"name": "Order3", "order": 3}, headers=headers())
        resp2 = requests.post(f"{BASE_URL}/collections", json={"name": "Order1", "order": 1}, headers=headers())
        resp3 = requests.post(f"{BASE_URL}/collections", json={"name": "Order2", "order": 2}, headers=headers())
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp3.status_code == 201

    def test_personal_collections_are_private(self):
        create_resp = requests.post(f"{BASE_URL}/collections", json={"name": "Private"}, headers=headers(USER1))
        col_id = create_resp.json()["id"]
        # Another user cannot see it
        resp = requests.get(f"{BASE_URL}/collections/{col_id}", headers=headers(USER2))
        assert resp.status_code == 404


# ==================== COLLECTION DUPLICATE ====================

class TestCollectionDuplicate:
    def test_duplicate_collection(self):
        # Create parent with child and request
        parent_resp = requests.post(f"{BASE_URL}/collections", json={"name": "DupParent"}, headers=headers())
        parent_id = parent_resp.json()["id"]
        child_resp = requests.post(f"{BASE_URL}/collections", json={"name": "DupChild", "parentId": parent_id}, headers=headers())
        child_id = child_resp.json()["id"]
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": child_id,
            "name": "DupReq",
            "method": "POST",
            "url": "http://example.com/api"
        }, headers=headers())
        # Duplicate
        dup_resp = requests.post(f"{BASE_URL}/collections/{parent_id}/duplicate", headers=headers())
        assert dup_resp.status_code == 201
        dup = dup_resp.json()
        assert "(copy)" in dup["name"]
        assert dup["id"] != parent_id
        # Check duplicated children
        children_resp = requests.get(f"{BASE_URL}/collections", params={"parentId": dup["id"]}, headers=headers())
        children = children_resp.json()
        assert len(children) >= 1
        # Check duplicated requests in child
        dup_child_id = children[0]["id"]
        reqs_resp = requests.get(f"{BASE_URL}/requests", params={"collectionId": dup_child_id}, headers=headers())
        reqs = reqs_resp.json()
        assert len(reqs) >= 1
        assert reqs[0]["name"] == "DupReq"


# ==================== COLLECTION MOVE ====================

class TestCollectionMove:
    def test_move_collection_to_new_parent(self):
        parent1 = requests.post(f"{BASE_URL}/collections", json={"name": "MoveParent1"}, headers=headers()).json()
        parent2 = requests.post(f"{BASE_URL}/collections", json={"name": "MoveParent2"}, headers=headers()).json()
        child = requests.post(f"{BASE_URL}/collections", json={"name": "MoveChild", "parentId": parent1["id"]}, headers=headers()).json()
        resp = requests.patch(f"{BASE_URL}/collections/{child['id']}/move", json={
            "parentId": parent2["id"]
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["parentId"] == parent2["id"]

    def test_move_collection_to_root(self):
        parent = requests.post(f"{BASE_URL}/collections", json={"name": "MoveToRootParent"}, headers=headers()).json()
        child = requests.post(f"{BASE_URL}/collections", json={"name": "MoveToRoot", "parentId": parent["id"]}, headers=headers()).json()
        resp = requests.patch(f"{BASE_URL}/collections/{child['id']}/move", json={
            "parentId": None
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["parentId"] is None

    def test_move_collection_cycle_detection(self):
        parent = requests.post(f"{BASE_URL}/collections", json={"name": "CycleParent"}, headers=headers()).json()
        child = requests.post(f"{BASE_URL}/collections", json={"name": "CycleChild", "parentId": parent["id"]}, headers=headers()).json()
        # Try to move parent under child (cycle)
        resp = requests.patch(f"{BASE_URL}/collections/{parent['id']}/move", json={
            "parentId": child["id"]
        }, headers=headers())
        assert resp.status_code == 400


# ==================== REQUESTS ====================

class TestRequests:
    def test_create_request(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "ReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id,
            "name": "Get Users",
            "method": "GET",
            "url": "https://api.example.com/users",
            "headers": [{"key": "Authorization", "value": "Bearer {{token}}", "active": True}],
            "params": [{"key": "page", "value": "1", "active": True}],
            "body": {"contentType": "application/json", "content": "{}"},
            "auth": {"type": "bearer", "token": "abc123"},
            "preRequestScript": "console.log('pre');",
            "testScript": "pm.test('status', () => pm.response.to.have.status(200));"
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Get Users"
        assert data["method"] == "GET"
        assert data["url"] == "https://api.example.com/users"
        assert len(data["headers"]) == 1
        assert data["headers"][0]["key"] == "Authorization"
        assert len(data["params"]) == 1
        assert data["body"]["contentType"] == "application/json"
        assert data["auth"]["type"] == "bearer"
        assert data["preRequestScript"] == "console.log('pre');"
        assert data["testScript"] == "pm.test('status', () => pm.response.to.have.status(200));"
        assert "id" in data
        assert data["collectionId"] == col_id

    def test_create_request_missing_fields_returns_400(self):
        resp = requests.post(f"{BASE_URL}/requests", json={
            "name": "Incomplete"
        }, headers=headers())
        assert resp.status_code == 400

    def test_list_requests_by_collection(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "ListReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "Req1", "method": "GET", "url": "http://a.com"
        }, headers=headers())
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "Req2", "method": "POST", "url": "http://b.com"
        }, headers=headers())
        resp = requests.get(f"{BASE_URL}/requests", params={"collectionId": col_id}, headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    def test_get_request(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "GetReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        create_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "GetReq", "method": "GET", "url": "http://get.com"
        }, headers=headers())
        req_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/requests/{req_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetReq"

    def test_update_request(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "UpdReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        create_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "OrigReq", "method": "GET", "url": "http://orig.com"
        }, headers=headers())
        req_id = create_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/requests/{req_id}", json={
            "name": "Updated Req",
            "method": "POST",
            "url": "http://updated.com"
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Req"
        assert resp.json()["method"] == "POST"
        assert resp.json()["url"] == "http://updated.com"

    def test_delete_request(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "DelReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        create_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "DelReq", "method": "GET", "url": "http://del.com"
        }, headers=headers())
        req_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/requests/{req_id}", headers=headers())
        assert resp.status_code == 204
        assert requests.get(f"{BASE_URL}/requests/{req_id}", headers=headers()).status_code == 404

    def test_duplicate_request(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "DupReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        create_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "DupReq", "method": "PUT", "url": "http://dup.com",
            "headers": [{"key": "X-Test", "value": "val", "active": True}]
        }, headers=headers())
        req_id = create_resp.json()["id"]
        resp = requests.post(f"{BASE_URL}/requests/{req_id}/duplicate", headers=headers())
        assert resp.status_code == 201
        dup = resp.json()
        assert dup["id"] != req_id
        assert dup["collectionId"] == col_id
        assert dup["method"] == "PUT"
        assert dup["url"] == "http://dup.com"
        assert len(dup["headers"]) == 1

    def test_move_request(self):
        col1 = requests.post(f"{BASE_URL}/collections", json={"name": "MoveReqCol1"}, headers=headers()).json()
        col2 = requests.post(f"{BASE_URL}/collections", json={"name": "MoveReqCol2"}, headers=headers()).json()
        req = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col1["id"], "name": "MoveMe", "method": "GET", "url": "http://move.com"
        }, headers=headers()).json()
        resp = requests.patch(f"{BASE_URL}/requests/{req['id']}/move", json={
            "collectionId": col2["id"]
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["collectionId"] == col2["id"]


# ==================== ENVIRONMENTS ====================

class TestEnvironments:
    def test_create_environment(self):
        resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "Production",
            "variables": [
                {"key": "baseUrl", "value": "https://api.prod.com", "active": True},
                {"key": "token", "value": "prod-token", "active": True}
            ]
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Production"
        assert len(data["variables"]) == 2
        assert data["global"] is False
        assert "id" in data

    def test_create_global_environment(self):
        resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "Global",
            "variables": [{"key": "appName", "value": "MyApp", "active": True}],
            "global": True
        }, headers=headers(USER3))
        assert resp.status_code == 201
        assert resp.json()["global"] is True

    def test_duplicate_global_environment_returns_409(self):
        requests.post(f"{BASE_URL}/environments", json={
            "name": "Global1",
            "variables": [{"key": "a", "value": "b", "active": True}],
            "global": True
        }, headers=headers("globaluser"))
        resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "Global2",
            "variables": [{"key": "c", "value": "d", "active": True}],
            "global": True
        }, headers=headers("globaluser"))
        assert resp.status_code == 409

    def test_list_environments(self):
        requests.post(f"{BASE_URL}/environments", json={
            "name": "ListEnv1",
            "variables": [{"key": "k", "value": "v", "active": True}]
        }, headers=headers())
        resp = requests.get(f"{BASE_URL}/environments", headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_environment(self):
        create_resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "GetEnv",
            "variables": [{"key": "host", "value": "localhost", "active": True}]
        }, headers=headers())
        env_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/environments/{env_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetEnv"
        assert resp.json()["variables"][0]["key"] == "host"

    def test_update_environment(self):
        create_resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "UpdEnv",
            "variables": [{"key": "old", "value": "val", "active": True}]
        }, headers=headers())
        env_id = create_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/environments/{env_id}", json={
            "name": "Updated Env",
            "variables": [
                {"key": "new", "value": "newval", "active": True},
                {"key": "extra", "value": "extraval", "active": False}
            ]
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Env"
        assert len(resp.json()["variables"]) == 2

    def test_delete_environment(self):
        create_resp = requests.post(f"{BASE_URL}/environments", json={
            "name": "DelEnv",
            "variables": []
        }, headers=headers())
        env_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/environments/{env_id}", headers=headers())
        assert resp.status_code == 204
        assert requests.get(f"{BASE_URL}/environments/{env_id}", headers=headers()).status_code == 404


# ==================== HISTORY ====================

class TestHistory:
    def test_create_history_entry(self):
        resp = requests.post(f"{BASE_URL}/history", json={
            "method": "GET",
            "url": "https://api.example.com/users",
            "statusCode": 200,
            "responseTime": 150,
            "requestHeaders": [{"key": "Authorization", "value": "Bearer tok", "active": True}],
            "requestBody": None,
            "responseHeaders": [{"key": "Content-Type", "value": "application/json", "active": True}],
            "responseBody": '{"users": []}'
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["method"] == "GET"
        assert data["statusCode"] == 200
        assert data["responseTime"] == 150
        assert "executedAt" in data
        assert "id" in data

    def test_list_history_with_pagination(self):
        # Create multiple entries
        for i in range(5):
            requests.post(f"{BASE_URL}/history", json={
                "method": "GET",
                "url": f"https://api.example.com/item/{i}",
                "statusCode": 200,
                "responseTime": 100 + i
            }, headers=headers())
        resp = requests.get(f"{BASE_URL}/history", params={"page": 1, "perPage": 3}, headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "perPage" in data
        assert len(data["data"]) <= 3
        assert data["page"] == 1
        assert data["perPage"] == 3

    def test_get_history_entry(self):
        create_resp = requests.post(f"{BASE_URL}/history", json={
            "method": "POST",
            "url": "https://api.example.com/submit",
            "statusCode": 201,
            "responseTime": 250
        }, headers=headers())
        entry_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/history/{entry_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["method"] == "POST"
        assert resp.json()["statusCode"] == 201

    def test_clear_history(self):
        requests.post(f"{BASE_URL}/history", json={
            "method": "DELETE",
            "url": "https://api.example.com/clear",
            "statusCode": 204,
            "responseTime": 50
        }, headers=headers("historyuser"))
        resp = requests.delete(f"{BASE_URL}/history", headers=headers("historyuser"))
        assert resp.status_code == 204
        list_resp = requests.get(f"{BASE_URL}/history", headers=headers("historyuser"))
        assert list_resp.json()["total"] == 0

    def test_history_ordered_newest_first(self):
        user = "historder"
        # Clear first
        requests.delete(f"{BASE_URL}/history", headers=headers(user))
        for i in range(3):
            if i:
                # executedAt is server-generated; separate values even at one-second precision.
                time.sleep(1.05)
            requests.post(f"{BASE_URL}/history", json={
                "method": "GET",
                "url": f"https://api.example.com/order/{i}",
                "statusCode": 200,
                "responseTime": 100
            }, headers=headers(user))
        resp = requests.get(f"{BASE_URL}/history", headers=headers(user))
        data = resp.json()["data"]
        # Newest first: last created should be first in list
        assert "order/2" in data[0]["url"]


# ==================== TEAMS ====================

class TestTeams:
    def test_create_team(self):
        resp = requests.post(f"{BASE_URL}/teams", json={
            "name": "Backend Team",
            "description": "Our backend devs"
        }, headers=headers(USER1))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Backend Team"
        assert "id" in data
        # Creator should be owner
        assert any(m["userId"] == USER1 and m["role"] == "owner" for m in data.get("members", []))

    def test_list_teams(self):
        requests.post(f"{BASE_URL}/teams", json={"name": "ListTeam1"}, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams", headers=headers(USER1))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_team(self):
        create_resp = requests.post(f"{BASE_URL}/teams", json={"name": "GetTeam"}, headers=headers(USER1))
        team_id = create_resp.json()["id"]
        resp = requests.get(f"{BASE_URL}/teams/{team_id}", headers=headers(USER1))
        assert resp.status_code == 200
        assert resp.json()["name"] == "GetTeam"

    def test_update_team_owner_only(self):
        create_resp = requests.post(f"{BASE_URL}/teams", json={"name": "UpdTeam"}, headers=headers(USER1))
        team_id = create_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/teams/{team_id}", json={"name": "Updated Team"}, headers=headers(USER1))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Team"

    def test_update_team_non_owner_returns_403(self):
        create_resp = requests.post(f"{BASE_URL}/teams", json={"name": "NoUpdTeam"}, headers=headers(USER1))
        team_id = create_resp.json()["id"]
        # Invite user2 as editor
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "editor"
        }, headers=headers(USER1))
        inv_id = inv_resp.json()["id"]
        requests.post(f"{BASE_URL}/invitations/{inv_id}/accept", headers=headers(USER2))
        # User2 (editor) tries to update team
        resp = requests.put(f"{BASE_URL}/teams/{team_id}", json={"name": "Hacked"}, headers=headers(USER2))
        assert resp.status_code == 403

    def test_delete_team_owner_only(self):
        create_resp = requests.post(f"{BASE_URL}/teams", json={"name": "DelTeam"}, headers=headers(USER1))
        team_id = create_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/teams/{team_id}", headers=headers(USER1))
        assert resp.status_code == 204

    def test_delete_team_non_owner_returns_403(self):
        create_resp = requests.post(f"{BASE_URL}/teams", json={"name": "NoDelTeam"}, headers=headers(USER1))
        team_id = create_resp.json()["id"]
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "editor"
        }, headers=headers(USER1))
        inv_id = inv_resp.json()["id"]
        requests.post(f"{BASE_URL}/invitations/{inv_id}/accept", headers=headers(USER2))
        resp = requests.delete(f"{BASE_URL}/teams/{team_id}", headers=headers(USER2))
        assert resp.status_code == 403


# ==================== TEAM INVITATIONS ====================

class TestTeamInvitations:
    def test_invite_and_accept(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "InviteTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        # Invite user2
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2,
            "role": "editor"
        }, headers=headers(USER1))
        assert inv_resp.status_code == 201
        inv = inv_resp.json()
        assert inv["status"] == "pending"
        assert inv["inviteeUserId"] == USER2
        assert inv["role"] == "editor"
        # Accept
        accept_resp = requests.post(f"{BASE_URL}/invitations/{inv['id']}/accept", headers=headers(USER2))
        assert accept_resp.status_code == 200
        assert accept_resp.json()["status"] == "accepted"
        # Verify membership
        members_resp = requests.get(f"{BASE_URL}/teams/{team_id}/members", headers=headers(USER1))
        members = members_resp.json()
        assert any(m["userId"] == USER2 and m["role"] == "editor" for m in members)

    def test_invite_non_owner_returns_403(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "InvForbidTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        # Add user2 as editor first
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "editor"
        }, headers=headers(USER1))
        requests.post(f"{BASE_URL}/invitations/{inv_resp.json()['id']}/accept", headers=headers(USER2))
        # User2 (editor) tries to invite user3
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER3, "role": "viewer"
        }, headers=headers(USER2))
        assert resp.status_code == 403

    def test_accept_invitation_wrong_user_returns_403(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "WrongAcceptTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "viewer"
        }, headers=headers(USER1))
        inv_id = inv_resp.json()["id"]
        # User3 tries to accept user2's invitation
        resp = requests.post(f"{BASE_URL}/invitations/{inv_id}/accept", headers=headers(USER3))
        assert resp.status_code == 403

    def test_list_pending_invitations(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "ListInvTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "viewer"
        }, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/invitations", headers=headers(USER1))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ==================== TEAM COLLECTIONS ====================

class TestTeamCollections:
    def _setup_team_with_editor(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "TCTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER2, "role": "editor"
        }, headers=headers(USER1))
        requests.post(f"{BASE_URL}/invitations/{inv_resp.json()['id']}/accept", headers=headers(USER2))
        return team_id

    def _setup_team_with_viewer(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "TVTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER3, "role": "viewer"
        }, headers=headers(USER1))
        requests.post(f"{BASE_URL}/invitations/{inv_resp.json()['id']}/accept", headers=headers(USER3))
        return team_id

    def test_create_team_collection_as_owner(self):
        team_id = self._setup_team_with_editor()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "Team API Col"
        }, headers=headers(USER1))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Team API Col"

    def test_create_team_collection_as_editor(self):
        team_id = self._setup_team_with_editor()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "Editor Col"
        }, headers=headers(USER2))
        assert resp.status_code == 201

    def test_create_team_collection_as_viewer_returns_403(self):
        team_id = self._setup_team_with_viewer()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "Viewer Col"
        }, headers=headers(USER3))
        assert resp.status_code == 403

    def test_list_team_collections_as_viewer(self):
        team_id = self._setup_team_with_viewer()
        requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "Visible Col"
        }, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/collections", headers=headers(USER3))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_team_collection_not_visible_to_non_member(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "PrivTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={"name": "Secret"}, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/collections", headers=headers(USER3))
        assert resp.status_code == 403

    def test_delete_team_collection_as_editor(self):
        team_id = self._setup_team_with_editor()
        col_resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "DelTeamCol"
        }, headers=headers(USER2))
        col_id = col_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/teams/{team_id}/collections/{col_id}", headers=headers(USER2))
        assert resp.status_code == 204

    def test_duplicate_team_collection(self):
        team_id = self._setup_team_with_editor()
        col_resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "DupTeamCol"
        }, headers=headers(USER1))
        col_id = col_resp.json()["id"]
        # Add a request
        requests.post(f"{BASE_URL}/teams/{team_id}/requests", json={
            "collectionId": col_id, "name": "TeamReq", "method": "GET", "url": "http://t.com"
        }, headers=headers(USER1))
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections/{col_id}/duplicate", headers=headers(USER1))
        assert resp.status_code == 201
        assert "(copy)" in resp.json()["name"]


# ==================== TEAM REQUESTS ====================

class TestTeamRequests:
    def _setup_team_collection(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "TRTeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        col_resp = requests.post(f"{BASE_URL}/teams/{team_id}/collections", json={
            "name": "TRCol"
        }, headers=headers(USER1))
        col_id = col_resp.json()["id"]
        return team_id, col_id

    def test_create_team_request(self):
        team_id, col_id = self._setup_team_collection()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/requests", json={
            "collectionId": col_id,
            "name": "Team Request",
            "method": "POST",
            "url": "https://team-api.com/data"
        }, headers=headers(USER1))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Team Request"
        assert resp.json()["collectionId"] == col_id

    def test_list_team_requests(self):
        team_id, col_id = self._setup_team_collection()
        requests.post(f"{BASE_URL}/teams/{team_id}/requests", json={
            "collectionId": col_id, "name": "TR1", "method": "GET", "url": "http://a.com"
        }, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/requests", params={"collectionId": col_id}, headers=headers(USER1))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_team_request(self):
        team_id, col_id = self._setup_team_collection()
        req_resp = requests.post(f"{BASE_URL}/teams/{team_id}/requests", json={
            "collectionId": col_id, "name": "UpdTR", "method": "GET", "url": "http://old.com"
        }, headers=headers(USER1))
        req_id = req_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/teams/{team_id}/requests/{req_id}", json={
            "name": "Updated TR", "url": "http://new.com"
        }, headers=headers(USER1))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated TR"

    def test_delete_team_request(self):
        team_id, col_id = self._setup_team_collection()
        req_resp = requests.post(f"{BASE_URL}/teams/{team_id}/requests", json={
            "collectionId": col_id, "name": "DelTR", "method": "GET", "url": "http://del.com"
        }, headers=headers(USER1))
        req_id = req_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/teams/{team_id}/requests/{req_id}", headers=headers(USER1))
        assert resp.status_code == 204


# ==================== TEAM ENVIRONMENTS ====================

class TestTeamEnvironments:
    def _setup_team(self):
        team_resp = requests.post(f"{BASE_URL}/teams", json={"name": "TETeam"}, headers=headers(USER1))
        team_id = team_resp.json()["id"]
        inv_resp = requests.post(f"{BASE_URL}/teams/{team_id}/invitations", json={
            "inviteeUserId": USER3, "role": "viewer"
        }, headers=headers(USER1))
        requests.post(f"{BASE_URL}/invitations/{inv_resp.json()['id']}/accept", headers=headers(USER3))
        return team_id

    def test_create_team_environment(self):
        team_id = self._setup_team()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/environments", json={
            "name": "Team Staging",
            "variables": [{"key": "host", "value": "staging.api.com", "active": True}]
        }, headers=headers(USER1))
        assert resp.status_code == 201
        assert resp.json()["name"] == "Team Staging"

    def test_list_team_environments_as_viewer(self):
        team_id = self._setup_team()
        requests.post(f"{BASE_URL}/teams/{team_id}/environments", json={
            "name": "Team Dev",
            "variables": [{"key": "k", "value": "v", "active": True}]
        }, headers=headers(USER1))
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/environments", headers=headers(USER3))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_update_team_environment(self):
        team_id = self._setup_team()
        env_resp = requests.post(f"{BASE_URL}/teams/{team_id}/environments", json={
            "name": "UpdTeamEnv",
            "variables": [{"key": "a", "value": "1", "active": True}]
        }, headers=headers(USER1))
        env_id = env_resp.json()["id"]
        resp = requests.put(f"{BASE_URL}/teams/{team_id}/environments/{env_id}", json={
            "name": "Updated Team Env",
            "variables": [{"key": "b", "value": "2", "active": True}]
        }, headers=headers(USER1))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Team Env"

    def test_viewer_cannot_create_team_environment(self):
        team_id = self._setup_team()
        resp = requests.post(f"{BASE_URL}/teams/{team_id}/environments", json={
            "name": "Viewer Env",
            "variables": []
        }, headers=headers(USER3))
        assert resp.status_code == 403

    def test_delete_team_environment(self):
        team_id = self._setup_team()
        env_resp = requests.post(f"{BASE_URL}/teams/{team_id}/environments", json={
            "name": "DelTeamEnv",
            "variables": []
        }, headers=headers(USER1))
        env_id = env_resp.json()["id"]
        resp = requests.delete(f"{BASE_URL}/teams/{team_id}/environments/{env_id}", headers=headers(USER1))
        assert resp.status_code == 204


# ==================== IMPORT/EXPORT ====================

class TestImportExport:
    def test_import_postman_collection(self):
        postman_json = {
            "info": {
                "name": "Imported Collection",
                "description": "From Postman"
            },
            "item": [
                {
                    "name": "Users Folder",
                    "item": [
                        {
                            "name": "Get Users",
                            "request": {
                                "method": "GET",
                                "url": {"raw": "https://api.example.com/users"},
                                "header": [{"key": "Accept", "value": "application/json"}],
                                "body": None
                            }
                        },
                        {
                            "name": "Create User",
                            "request": {
                                "method": "POST",
                                "url": {"raw": "https://api.example.com/users"},
                                "header": [{"key": "Content-Type", "value": "application/json"}],
                                "body": {"mode": "raw", "raw": '{"name": "John"}'}
                            }
                        }
                    ]
                },
                {
                    "name": "Health Check",
                    "request": {
                        "method": "GET",
                        "url": {"raw": "https://api.example.com/health"},
                        "header": []
                    }
                }
            ]
        }
        resp = requests.post(f"{BASE_URL}/import/postman", json={
            "collectionJson": postman_json
        }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Imported Collection"
        col_id = data["id"]
        # Check that subfolder was created
        children = requests.get(f"{BASE_URL}/collections", params={"parentId": col_id}, headers=headers()).json()
        assert len(children) >= 1
        folder = [c for c in children if c["name"] == "Users Folder"]
        assert len(folder) == 1
        # Check requests in folder
        folder_reqs = requests.get(f"{BASE_URL}/requests", params={"collectionId": folder[0]["id"]}, headers=headers()).json()
        assert len(folder_reqs) >= 2
        # Check root-level request
        root_reqs = requests.get(f"{BASE_URL}/requests", params={"collectionId": col_id}, headers=headers()).json()
        assert any(r["name"] == "Health Check" for r in root_reqs)

    def test_import_postman_invalid_format_returns_400(self):
        resp = requests.post(f"{BASE_URL}/import/postman", json={
            "collectionJson": {"invalid": True}
        }, headers=headers())
        assert resp.status_code == 400

    def test_export_collection(self):
        # Create collection with request
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "ExportCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id,
            "name": "ExportReq",
            "method": "GET",
            "url": "http://export.com"
        }, headers=headers())
        # Create child collection with request
        child_resp = requests.post(f"{BASE_URL}/collections", json={
            "name": "ExportChild", "parentId": col_id
        }, headers=headers())
        child_id = child_resp.json()["id"]
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": child_id,
            "name": "ChildReq",
            "method": "POST",
            "url": "http://child.com"
        }, headers=headers())
        # Export
        resp = requests.post(f"{BASE_URL}/collections/{col_id}/export", headers=headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "collection" in data
        export = data["collection"]
        assert export["name"] == "ExportCol"
        assert "requests" in export
        assert "collections" in export
        assert len(export["requests"]) >= 1
        assert len(export["collections"]) >= 1
        assert export["collections"][0]["name"] == "ExportChild"
        assert len(export["collections"][0]["requests"]) >= 1


# ==================== REORDER ====================

class TestReorder:
    def test_reorder_collections(self):
        col1 = requests.post(f"{BASE_URL}/collections", json={"name": "Reorder1", "order": 1}, headers=headers()).json()
        col2 = requests.post(f"{BASE_URL}/collections", json={"name": "Reorder2", "order": 2}, headers=headers()).json()
        # Update order
        resp = requests.put(f"{BASE_URL}/collections/{col2['id']}", json={"order": 0}, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["order"] == 0

    def test_reorder_requests(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "ReorderReqCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        req1 = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "R1", "method": "GET", "url": "http://1.com", "order": 1
        }, headers=headers()).json()
        req2 = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id, "name": "R2", "method": "GET", "url": "http://2.com", "order": 2
        }, headers=headers()).json()
        resp = requests.put(f"{BASE_URL}/requests/{req2['id']}", json={"order": 0}, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["order"] == 0


# ==================== SCRIPTS STORAGE ====================

class TestScriptsStorage:
    def test_pre_request_script_stored(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "ScriptCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        script = "pm.environment.set('timestamp', Date.now());"
        req_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id,
            "name": "ScriptReq",
            "method": "GET",
            "url": "http://script.com",
            "preRequestScript": script
        }, headers=headers())
        assert req_resp.status_code == 201
        req_id = req_resp.json()["id"]
        get_resp = requests.get(f"{BASE_URL}/requests/{req_id}", headers=headers())
        assert get_resp.json()["preRequestScript"] == script

    def test_test_script_stored(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "TestScriptCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        test_script = "pm.test('Response time < 200ms', () => { pm.expect(pm.response.responseTime).to.be.below(200); });"
        req_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id,
            "name": "TestScriptReq",
            "method": "POST",
            "url": "http://test.com",
            "testScript": test_script
        }, headers=headers())
        assert req_resp.status_code == 201
        req_id = req_resp.json()["id"]
        get_resp = requests.get(f"{BASE_URL}/requests/{req_id}", headers=headers())
        assert get_resp.json()["testScript"] == test_script

    def test_update_scripts(self):
        col_resp = requests.post(f"{BASE_URL}/collections", json={"name": "UpdScriptCol"}, headers=headers())
        col_id = col_resp.json()["id"]
        req_resp = requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col_id,
            "name": "UpdScriptReq",
            "method": "GET",
            "url": "http://upd.com"
        }, headers=headers())
        req_id = req_resp.json()["id"]
        new_pre = "console.log('updated pre');"
        new_test = "pm.test('updated', () => {});"
        resp = requests.put(f"{BASE_URL}/requests/{req_id}", json={
            "preRequestScript": new_pre,
            "testScript": new_test
        }, headers=headers())
        assert resp.status_code == 200
        assert resp.json()["preRequestScript"] == new_pre
        assert resp.json()["testScript"] == new_test
