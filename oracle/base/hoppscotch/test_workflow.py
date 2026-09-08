"""
L3 Workflow Tests for Hoppscotch API.
Multi-step: collection lifecycle, team collaboration, import/export.
"""
import os, uuid, requests, pytest

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
USER1 = "user1"
USER2 = "user2"
USER3 = "user3"

def h(user=None):
    if user is None:
        user = USER1
    return {"X-API-Key": user, "Content-Type": "application/json"}

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex[:8]}"


class TestCollectionLifecycle:
    def test_create_requests_and_delete(self):
        # 1. Create collection
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("lc")}, headers=h()).json()
        assert "id" in col

        # 2. Add requests
        r1 = requests.post(f"{BASE_URL}/requests", json={
            "name": "List Users", "method": "GET", "url": "https://api.com/users",
            "collectionId": col["id"]
        }, headers=h()).json()
        assert "id" in r1

        # 3. Verify request in collection
        resp = requests.get(f"{BASE_URL}/requests/{r1['id']}", headers=h())
        assert resp.status_code == 200
        assert resp.json()["collectionId"] == col["id"]

        # 4. Delete collection
        resp = requests.delete(f"{BASE_URL}/collections/{col['id']}", headers=h())
        assert resp.status_code == 204

        # 5. Collection should be gone
        resp = requests.get(f"{BASE_URL}/collections/{col['id']}", headers=h())
        assert resp.status_code == 404


class TestTeamWorkflow:
    def test_create_team_and_invite_member(self):
        # 1. Create team
        resp = requests.post(f"{BASE_URL}/teams", json={"name": unique("team")}, headers=h(USER1))
        assert resp.status_code == 201
        team = resp.json()
        assert "id" in team

        # 2. Invite member
        resp = requests.post(f"{BASE_URL}/teams/{team['id']}/invitations", json={
            "inviteeUserId": USER2, "role": "editor"
        }, headers=h(USER1))
        assert resp.status_code == 201

        # 3. List invitations
        resp = requests.get(f"{BASE_URL}/teams/{team['id']}/invitations", headers=h(USER1))
        assert resp.status_code == 200


class TestImportExport:
    def test_export_collection(self):
        # 1. Create collection with requests
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("exp")}, headers=h()).json()
        requests.post(f"{BASE_URL}/requests", json={
            "name": "Exported Req", "method": "GET", "url": "https://exported.com",
            "collectionId": col["id"]
        }, headers=h())

        # 2. Export (POST)
        resp = requests.post(f"{BASE_URL}/collections/{col['id']}/export", headers=h())
        assert resp.status_code == 200
        export_data = resp.json()
        # Export wraps in "collection" key
        assert "collection" in export_data or "name" in export_data


class TestEnvironmentWorkflow:
    def test_environment_crud_and_variables(self):
        # 1. Create environment
        env = requests.post(f"{BASE_URL}/environments", json={
            "name": unique("env"),
            "variables": [
                {"key": "API_URL", "value": "https://api.com"},
                {"key": "TOKEN", "value": "abc123"}
            ]
        }, headers=h()).json()
        assert len(env["variables"]) == 2

        # 2. Update environment
        resp = requests.put(f"{BASE_URL}/environments/{env['id']}", json={
            "name": env["name"],
            "variables": [
                {"key": "API_URL", "value": "https://api.v2.com"},
                {"key": "TOKEN", "value": "xyz789"},
                {"key": "NEW_VAR", "value": "new"}
            ]
        }, headers=h())
        assert resp.status_code == 200
        updated = resp.json()
        assert len(updated["variables"]) == 3

        # 3. Delete
        resp = requests.delete(f"{BASE_URL}/environments/{env['id']}", headers=h())
        assert resp.status_code == 204


class TestRequestOrderAndMove:
    def test_request_creation_with_collection(self):
        col_a = requests.post(f"{BASE_URL}/collections", json={"name": unique("a")}, headers=h()).json()

        # Create request in col_a
        req = requests.post(f"{BASE_URL}/requests", json={
            "name": "InColA", "method": "GET", "url": "https://a.com",
            "collectionId": col_a["id"]
        }, headers=h()).json()
        assert req["collectionId"] == col_a["id"]

        # Get request
        resp = requests.get(f"{BASE_URL}/requests/{req['id']}", headers=h())
        assert resp.status_code == 200
        assert resp.json()["collectionId"] == col_a["id"]
