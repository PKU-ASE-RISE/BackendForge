"""
L2 Integration Tests for Vaultwarden API.
Targets: camelCase, status codes, cipher types, folder/org operations.
"""
import os, uuid, requests, pytest, base64
from datetime import datetime, timedelta, timezone

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex}"

def register_user(email=None, password="MasterPass123!", name="Test"):
    email = email or f"{unique('u')}@test.com"
    resp = requests.post(f"{BASE_URL}/api/accounts/register", json={
        "email": email, "masterPasswordHash": password, "name": name
    })
    return resp, email, password

def get_token(email=None, password="MasterPass123!"):
    if email is None:
        _, email, password = register_user()
    else:
        register_user(email, password)
    resp = requests.post(f"{BASE_URL}/identity/connect/token", json={
        "email": email, "masterPasswordHash": password
    })
    assert resp.status_code == 200
    return resp.json()["accessToken"], email

def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestAccountFields:
    def test_register_returns_correct_fields(self):
        resp, email, _ = register_user()
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["email"] == email
        assert "createdAt" in data or "name" in data

    def test_login_returns_access_token(self):
        _, email, pw = register_user()
        resp = requests.post(f"{BASE_URL}/identity/connect/token", json={
            "email": email, "masterPasswordHash": pw
        })
        assert resp.status_code == 200
        assert "accessToken" in resp.json()

    def test_missing_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/api/ciphers")
        assert resp.status_code == 401

class TestCipherCRUD:
    def test_create_login_cipher_returns_201(self):
        token, _ = get_token()
        resp = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"MyLogin").decode(),
            "login": {"uri": "https://example.com", "username": "user", "password": "pass"}
        }, headers=auth(token))
        assert resp.status_code == 201
        c = resp.json()
        assert "id" in c
        assert c["type"] == 1
        assert "createdAt" in c or "revisionDate" in c

    def test_create_secure_note_cipher(self):
        token, _ = get_token()
        resp = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 2, "name": base64.b64encode(b"Secret Note").decode(),
            "notes": base64.b64encode(b"My secret text").decode()
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["type"] == 2

    def test_get_cipher_returns_200(self):
        token, _ = get_token()
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Get").decode(),
            "login": {"uri": "https://x.com", "username": "u", "password": "p"}
        }, headers=auth(token)).json()
        resp = requests.get(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == c["id"]

    def test_delete_cipher_returns_200_or_204(self):
        token, _ = get_token()
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Del").decode(),
            "login": {"uri": "x", "username": "u", "password": "p"}
        }, headers=auth(token)).json()
        resp = requests.delete(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token))
        assert resp.status_code in [200, 204]

    def test_get_nonexistent_cipher_returns_404(self):
        token, _ = get_token()
        resp = requests.get(f"{BASE_URL}/api/ciphers/{uuid.uuid4().hex}", headers=auth(token))
        assert resp.status_code == 404

class TestFolderCRUD:
    def test_create_folder_returns_201(self):
        token, _ = get_token()
        resp = requests.post(f"{BASE_URL}/api/folders", json={
            "name": base64.b64encode(b"Work").decode()
        }, headers=auth(token))
        assert resp.status_code == 201
        f = resp.json()
        assert "id" in f
        assert "name" in f

    def test_list_folders(self):
        token, _ = get_token()
        requests.post(f"{BASE_URL}/api/folders", json={"name": base64.b64encode(b"F1").decode()}, headers=auth(token))
        requests.post(f"{BASE_URL}/api/folders", json={"name": base64.b64encode(b"F2").decode()}, headers=auth(token))
        resp = requests.get(f"{BASE_URL}/api/folders", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

class TestFavorite:
    def test_toggle_favorite(self):
        token, _ = get_token()
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Fav").decode(),
            "login": {"uri": "x", "username": "u", "password": "p"}
        }, headers=auth(token)).json()
        resp = requests.put(f"{BASE_URL}/api/ciphers/{c['id']}/favorite",
                            json={"favorite": True}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["favorite"] is True

class TestUserIsolation:
    def test_user_cannot_see_other_ciphers(self):
        token_a, _ = get_token()
        token_b, _ = get_token()
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Private").decode(),
            "login": {"uri": "x", "username": "u", "password": "p"}
        }, headers=auth(token_a)).json()
        resp = requests.get(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token_b))
        assert resp.status_code in [403, 404]

class TestSend:
    def test_create_send(self):
        token, _ = get_token()
        resp = requests.post(f"{BASE_URL}/api/sends", json={
            "type": 0, "name": "Shared text",
            "text": {"text": "Hello from send"}
        }, headers=auth(token))
        assert resp.status_code == 201
        s = resp.json()
        assert "id" in s
        assert "accessId" in s
        assert "createdAt" in s or "revisionDate" in s
