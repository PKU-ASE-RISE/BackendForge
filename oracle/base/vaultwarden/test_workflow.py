"""
L3 Workflow Tests for Vaultwarden API.
Multi-step: cipher lifecycle, org/collection sharing, send access, 2FA.
"""
import os, uuid, requests, pytest, base64
from datetime import datetime, timedelta, timezone

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")

def unique(p="t"):
    return f"{p}_{uuid.uuid4().hex}"

def register_and_login(email=None, password="MasterPass123!"):
    email = email or f"{unique('u')}@test.com"
    requests.post(f"{BASE_URL}/api/accounts/register", json={
        "email": email, "masterPasswordHash": password, "name": "Test"
    })
    resp = requests.post(f"{BASE_URL}/identity/connect/token", json={
        "email": email, "masterPasswordHash": password
    })
    assert resp.status_code == 200
    return resp.json()["accessToken"], email

def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestCipherLifecycle:
    def test_create_update_favorite_delete(self):
        token, _ = register_and_login()
        # Create
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Lifecycle").decode(),
            "login": {"uri": "https://a.com", "username": "u1", "password": "p1"}
        }, headers=auth(token)).json()
        assert "id" in c

        # Update
        resp = requests.put(f"{BASE_URL}/api/ciphers/{c['id']}", json={
            "type": 1, "name": base64.b64encode(b"Updated").decode(),
            "login": {"uri": "https://b.com", "username": "u2", "password": "p2"}
        }, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == base64.b64encode(b"Updated").decode()

        # Favorite
        resp = requests.put(f"{BASE_URL}/api/ciphers/{c['id']}/favorite",
                            json={"favorite": True}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["favorite"] is True

        # Delete
        resp = requests.delete(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token))
        assert resp.status_code in [200, 204]

        # Verify gone
        resp = requests.get(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token))
        assert resp.status_code == 404


class TestOrganizationWorkflow:
    def test_create_org_and_collection(self):
        token_a, email_a = register_and_login()

        # Create org
        resp = requests.post(f"{BASE_URL}/api/organizations", json={
            "name": unique("org"), "billingEmail": email_a
        }, headers=auth(token_a))
        assert resp.status_code == 201
        org = resp.json()
        org_id = org["id"]

        # Create collection
        resp = requests.post(f"{BASE_URL}/api/organizations/{org_id}/collections", json={
            "name": base64.b64encode(b"Shared Creds").decode()
        }, headers=auth(token_a))
        assert resp.status_code == 201
        collection = resp.json()
        assert "id" in collection

        # Create cipher in org
        resp = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Org Cipher").decode(),
            "organizationId": org_id,
            "collectionIds": [collection["id"]],
            "login": {"uri": "https://shared.com", "username": "s", "password": "p"}
        }, headers=auth(token_a))
        assert resp.status_code == 201


class TestSendWorkflow:
    def test_send_create_and_access(self):
        token, _ = register_and_login()

        # Create send with max access count
        resp = requests.post(f"{BASE_URL}/api/sends", json={
            "type": 0, "name": "Limited Send",
            "text": {"text": "Secret message"},
            "maxAccessCount": 2
        }, headers=auth(token))
        assert resp.status_code == 201
        send = resp.json()
        access_id = send["accessId"]

        # Access send publicly (POST not GET)
        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code == 200

        # Access again
        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code == 200

        # Third access should fail (max 2)
        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code in [404, 410]


class TestFolderWorkflow:
    def test_folder_cipher_organization(self):
        token, _ = register_and_login()

        # Create folder
        folder = requests.post(f"{BASE_URL}/api/folders", json={
            "name": base64.b64encode(b"Work").decode()
        }, headers=auth(token)).json()

        # Create cipher in folder
        c = requests.post(f"{BASE_URL}/api/ciphers", json={
            "type": 1, "name": base64.b64encode(b"Work Login").decode(),
            "folderId": folder["id"],
            "login": {"uri": "https://work.com", "username": "w", "password": "p"}
        }, headers=auth(token)).json()
        assert c["folderId"] == folder["id"]

        # Delete folder
        resp = requests.delete(f"{BASE_URL}/api/folders/{folder['id']}", headers=auth(token))
        assert resp.status_code in [200, 204]

        # Cipher should still exist (just unfoldered)
        resp = requests.get(f"{BASE_URL}/api/ciphers/{c['id']}", headers=auth(token))
        assert resp.status_code == 200


class TestPasswordChange:
    def test_change_master_password(self):
        token, email = register_and_login(password="OldPass123!")

        # Change password
        resp = requests.post(f"{BASE_URL}/api/accounts/password", json={
            "currentMasterPasswordHash": "OldPass123!",
            "newMasterPasswordHash": "NewPass456!"
        }, headers=auth(token))
        assert resp.status_code == 200

        # Login with new password
        resp = requests.post(f"{BASE_URL}/identity/connect/token", json={
            "email": email, "masterPasswordHash": "NewPass456!"
        })
        assert resp.status_code == 200
        assert "accessToken" in resp.json()
