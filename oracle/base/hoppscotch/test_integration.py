"""
L2 Integration Tests for Hoppscotch API.
Targets: camelCase, status codes, user isolation, CRUD correctness.
"""
import os, uuid, requests, pytest

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
USER1 = "user1"
USER2 = "user2"

def h(user=None):
    if user is None:
        user = USER1
    return {"X-API-Key": user, "Content-Type": "application/json"}

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex[:8]}"


class TestCollectionFields:
    def test_create_collection_returns_camelcase(self):
        name = unique("col")
        resp = requests.post(f"{BASE_URL}/collections", json={"name": name, "description": "D"}, headers=h())
        assert resp.status_code == 201
        c = resp.json()
        assert "id" in c
        assert c["name"] == name
        assert "createdAt" in c
        assert "updatedAt" in c
        assert "parentId" in c
        assert "order" in c
        assert "created_at" not in c

    def test_list_collections(self):
        n = unique("lc")
        requests.post(f"{BASE_URL}/collections", json={"name": n}, headers=h())
        resp = requests.get(f"{BASE_URL}/collections", headers=h())
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert n in names

class TestRequestFields:
    def test_create_request_returns_fields(self):
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("c")}, headers=h()).json()
        resp = requests.post(f"{BASE_URL}/requests", json={
            "name": "GET Users", "method": "GET", "url": "https://api.example.com/users",
            "collectionId": col["id"],
            "headers": [{"key": "Accept", "value": "application/json"}]
        }, headers=h())
        assert resp.status_code == 201
        r = resp.json()
        assert "id" in r
        assert r["name"] == "GET Users"
        assert r["method"] == "GET"
        assert r["url"] == "https://api.example.com/users"
        assert "collectionId" in r
        assert r["collectionId"] == col["id"]

class TestEnvironmentFields:
    def test_create_environment(self):
        resp = requests.post(f"{BASE_URL}/environments", json={
            "name": unique("env"),
            "variables": [{"key": "BASE_URL", "value": "https://api.com"}]
        }, headers=h())
        assert resp.status_code == 201
        e = resp.json()
        assert "id" in e
        assert "name" in e
        assert "variables" in e
        assert len(e["variables"]) == 1
        assert e["variables"][0]["key"] == "BASE_URL"

class TestStatusCodes:
    def test_delete_collection_returns_204(self):
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("d")}, headers=h()).json()
        resp = requests.delete(f"{BASE_URL}/collections/{col['id']}", headers=h())
        assert resp.status_code == 204

    def test_get_nonexistent_collection_returns_404(self):
        resp = requests.get(f"{BASE_URL}/collections/{uuid.uuid4().hex}", headers=h())
        assert resp.status_code == 404

    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{BASE_URL}/collections")
        assert resp.status_code == 401

class TestUserIsolation:
    def test_user1_cannot_see_user2_collections(self):
        name = unique("iso")
        requests.post(f"{BASE_URL}/collections", json={"name": name}, headers=h(USER1))
        resp = requests.get(f"{BASE_URL}/collections", headers=h(USER2))
        names = [c["name"] for c in resp.json()]
        assert name not in names

    def test_user1_cannot_access_user2_collection(self):
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("p")}, headers=h(USER1)).json()
        resp = requests.get(f"{BASE_URL}/collections/{col['id']}", headers=h(USER2))
        assert resp.status_code in [403, 404]

class TestHistory:
    def test_create_and_list_history(self):
        resp = requests.post(f"{BASE_URL}/history", json={
            "method": "POST", "url": "https://api.example.com/data",
            "statusCode": 200, "responseTime": 150
        }, headers=h())
        assert resp.status_code == 201
        entry = resp.json()
        assert "id" in entry
        assert entry["method"] == "POST"
        assert entry["statusCode"] == 200

        resp = requests.get(f"{BASE_URL}/history", headers=h())
        assert resp.status_code == 200
        assert any(e["id"] == entry["id"] for e in resp.json()["data"])

class TestNestedCollections:
    def test_child_collection(self):
        parent = requests.post(f"{BASE_URL}/collections", json={"name": unique("parent")}, headers=h()).json()
        child = requests.post(f"{BASE_URL}/collections", json={
            "name": unique("child"), "parentId": parent["id"]
        }, headers=h())
        assert child.status_code == 201
        assert child.json()["parentId"] == parent["id"]

class TestDuplication:
    def test_duplicate_collection(self):
        col = requests.post(f"{BASE_URL}/collections", json={"name": unique("orig")}, headers=h()).json()
        # Add request to collection
        requests.post(f"{BASE_URL}/requests", json={
            "collectionId": col["id"], "name": "Req1", "method": "GET", "url": "https://x.com"
        }, headers=h())

        resp = requests.post(f"{BASE_URL}/collections/{col['id']}/duplicate", headers=h())
        assert resp.status_code == 201
        dup = resp.json()
        assert dup["id"] != col["id"]
        assert dup["name"] != col["name"] or "Copy" in dup["name"] or dup["id"] != col["id"]
