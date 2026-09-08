"""
Correctness tests for Vaultwarden API.
Tests cover all core features: accounts, ciphers, folders, organizations,
collections, sends, 2FA, password generator, password history, favorites,
attachments, and sync.
"""

import os
import time
import base64
import hashlib
import hmac
import struct
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


# ─── Helpers ────────────────────────────────────────────────────────────────

def register_user(email, password="MasterPass123!", name="Test User"):
    """Register a new user and return the response."""
    resp = requests.post(f"{BASE_URL}/api/accounts/register", json={
        "email": email,
        "masterPasswordHash": password,
        "name": name
    })
    return resp


def login_user(email, password="MasterPass123!", totp_token=None):
    """Login and return the response."""
    payload = {
        "email": email,
        "masterPasswordHash": password
    }
    if totp_token:
        payload["twoFactorToken"] = totp_token
        payload["twoFactorProvider"] = 0
    resp = requests.post(f"{BASE_URL}/identity/connect/token", json=payload)
    return resp


def get_token(email, password="MasterPass123!"):
    """Register (if needed) and login, return bearer token."""
    register_user(email, password)
    resp = login_user(email, password)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["accessToken"]


def auth_headers(token):
    """Return authorization headers."""
    return {"Authorization": f"Bearer {token}"}


def unique_email(prefix):
    """Return an isolated account identity for one test scenario."""
    return f"{prefix}_{uuid.uuid4().hex}@example.com"


def invalid_totp_token(secret):
    """Return a six-digit token that is invalid across the adjacent TOTP windows."""
    key = base64.b32decode(secret, casefold=True)
    counter = int(time.time() // 30)
    valid_tokens = set()
    for offset in (-1, 0, 1):
        message = struct.pack(">Q", counter + offset)
        digest = hmac.new(key, message, hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        value = struct.unpack(">I", digest[index : index + 4])[0] & 0x7FFFFFFF
        valid_tokens.add(f"{value % 1000000:06d}")
    return next(token for token in ("000000", "111111", "222222", "333333") if token not in valid_tokens)


# ─── Account Tests ──────────────────────────────────────────────────────────

class TestAccounts:
    def test_register_success(self):
        email = unique_email("register_test")
        resp = register_user(email)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == email
        assert data["name"] == "Test User"
        assert "id" in data

    def test_register_duplicate_email(self):
        email = unique_email("dup")
        register_user(email)
        resp = register_user(email)
        assert resp.status_code == 409

    def test_login_success(self):
        email = unique_email("login_test")
        register_user(email)
        resp = login_user(email)
        assert resp.status_code == 200
        data = resp.json()
        assert "accessToken" in data
        assert data["tokenType"] == "Bearer"
        assert data["expiresIn"] == 3600

    def test_login_invalid_password(self):
        email = unique_email("bad_pw")
        register_user(email)
        resp = login_user(email, "WrongPassword!")
        assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        resp = login_user(unique_email("nobody"))
        assert resp.status_code == 401

    def test_get_profile(self):
        email = unique_email("profile")
        token = get_token(email)
        resp = requests.get(f"{BASE_URL}/api/accounts/profile", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == email
        assert data["name"] == "Test User"

    def test_update_profile(self):
        token = get_token(unique_email("update_profile"))
        resp = requests.put(f"{BASE_URL}/api/accounts/profile",
                           headers=auth_headers(token),
                           json={"name": "Updated Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_change_password(self):
        email = unique_email("change_pw")
        token = get_token(email)
        resp = requests.post(f"{BASE_URL}/api/accounts/password",
                            headers=auth_headers(token),
                            json={
                                "currentMasterPasswordHash": "MasterPass123!",
                                "newMasterPasswordHash": "NewPass456!"
                            })
        assert resp.status_code == 200
        # Old password should fail
        resp2 = login_user(email, "MasterPass123!")
        assert resp2.status_code == 401
        # New password should work
        resp3 = login_user(email, "NewPass456!")
        assert resp3.status_code == 200

    def test_change_password_wrong_current(self):
        token = get_token(unique_email("change_pw_fail"))
        resp = requests.post(f"{BASE_URL}/api/accounts/password",
                            headers=auth_headers(token),
                            json={
                                "currentMasterPasswordHash": "WrongPassword",
                                "newMasterPasswordHash": "NewPass456!"
                            })
        assert resp.status_code == 400

    def test_delete_account(self):
        email = unique_email("delete_me")
        token = get_token(email)
        resp = requests.delete(f"{BASE_URL}/api/accounts",
                              headers=auth_headers(token),
                              json={"masterPasswordHash": "MasterPass123!"})
        assert resp.status_code == 200
        # Login should fail after deletion
        resp2 = login_user(email)
        assert resp2.status_code == 401

    def test_unauthorized_access(self):
        resp = requests.get(f"{BASE_URL}/api/accounts/profile")
        assert resp.status_code == 401

    def test_invalid_token(self):
        resp = requests.get(f"{BASE_URL}/api/accounts/profile",
                           headers={"Authorization": "Bearer invalidtoken123"})
        assert resp.status_code == 401


# ─── Cipher Tests ───────────────────────────────────────────────────────────

class TestCiphers:
    def setup_method(self):
        self.email = unique_email("cipher")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_create_login_cipher(self):
        resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "My Login",
            "login": {
                "uri": "https://example.com",
                "username": "user@example.com",
                "password": "c2VjcmV0"  # base64 "secret"
            }
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 1
        assert data["name"] == "My Login"
        assert data["login"]["uri"] == "https://example.com"
        assert data["login"]["username"] == "user@example.com"
        assert "id" in data
        assert "createdAt" in data
        assert "revisionDate" in data

    def test_create_note_cipher(self):
        resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2,
            "name": "My Note",
            "notes": "VGhpcyBpcyBhIHNlY3JldCBub3Rl"  # base64
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 2
        assert data["notes"] == "VGhpcyBpcyBhIHNlY3JldCBub3Rl"

    def test_create_card_cipher(self):
        resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 3,
            "name": "My Card",
            "card": {
                "cardholderName": "John Doe",
                "brand": "Visa",
                "number": "4111111111111111",
                "expMonth": "12",
                "expYear": "2099",
                "code": "123"
            }
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 3
        assert data["card"]["cardholderName"] == "John Doe"
        assert data["card"]["number"] == "4111111111111111"

    def test_create_identity_cipher(self):
        resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 4,
            "name": "My Identity",
            "identity": {
                "firstName": "John",
                "lastName": "Doe",
                "address1": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "postalCode": "90210",
                "country": "US",
                "email": "john@example.com",
                "phone": "555-1234"
            }
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 4
        assert data["identity"]["firstName"] == "John"
        assert data["identity"]["city"] == "Anytown"

    def test_list_ciphers(self):
        # Create two ciphers
        requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Note 1", "notes": "bm90ZTE="
        })
        requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Note 2", "notes": "bm90ZTI="
        })
        resp = requests.get(f"{BASE_URL}/api/ciphers", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_get_cipher(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "Get Test",
            "login": {"uri": "https://test.com", "username": "u", "password": "p"}
        })
        cipher_id = create.json()["id"]
        resp = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    def test_update_cipher(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "Before Update",
            "login": {"uri": "https://old.com", "username": "u", "password": "old_pw"}
        })
        cipher_id = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers, json={
            "type": 1,
            "name": "After Update",
            "login": {"uri": "https://new.com", "username": "u", "password": "new_pw"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "After Update"
        assert data["login"]["uri"] == "https://new.com"

    def test_delete_cipher(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Delete Me", "notes": "bye"
        })
        cipher_id = create.json()["id"]
        resp = requests.delete(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers)
        assert resp.status_code == 200
        # Verify deleted
        resp2 = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers)
        assert resp2.status_code == 404

    def test_cipher_not_found(self):
        resp = requests.get(f"{BASE_URL}/api/ciphers/nonexistent-id", headers=self.headers)
        assert resp.status_code == 404

    def test_cipher_with_folder(self):
        # Create a folder first
        folder_resp = requests.post(f"{BASE_URL}/api/folders", headers=self.headers,
                                    json={"name": "Work"})
        folder_id = folder_resp.json()["id"]
        # Create cipher in folder
        resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2,
            "name": "Work Note",
            "notes": "d29yaw==",
            "folderId": folder_id
        })
        assert resp.status_code == 201
        assert resp.json()["folderId"] == folder_id


# ─── Favorites Tests ────────────────────────────────────────────────────────

class TestFavorites:
    def setup_method(self):
        self.email = unique_email("fav")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_mark_favorite(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Fav Test", "notes": "test"
        })
        cipher_id = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}/favorite",
                           headers=self.headers, json={"favorite": True})
        assert resp.status_code == 200
        assert resp.json()["favorite"] is True

    def test_unmark_favorite(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Unfav Test", "notes": "test", "favorite": True
        })
        cipher_id = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}/favorite",
                           headers=self.headers, json={"favorite": False})
        assert resp.status_code == 200
        assert resp.json()["favorite"] is False


# ─── Password History Tests ─────────────────────────────────────────────────

class TestPasswordHistory:
    def setup_method(self):
        self.email = unique_email("history")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_password_history_on_update(self):
        # Create login cipher
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "History Test",
            "login": {"uri": "https://test.com", "username": "u", "password": "pass1"}
        })
        cipher_id = create.json()["id"]

        # Update password
        requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers, json={
            "type": 1,
            "name": "History Test",
            "login": {"uri": "https://test.com", "username": "u", "password": "pass2"}
        })

        # Check history
        resp = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}/history", headers=self.headers)
        assert resp.status_code == 200
        history = resp.json()["data"]
        assert len(history) == 1
        assert history[0]["password"] == "pass1"

    def test_password_history_max_5(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "Max History",
            "login": {"uri": "https://test.com", "username": "u", "password": "pass0"}
        })
        cipher_id = create.json()["id"]

        # Update password 6 times
        for i in range(1, 7):
            requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers, json={
                "type": 1,
                "name": "Max History",
                "login": {"uri": "https://test.com", "username": "u", "password": f"pass{i}"}
            })

        resp = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}/history", headers=self.headers)
        history = resp.json()["data"]
        # Should only keep last 5
        assert len(history) == 5
        # Most recent old password should be pass5 (the one just replaced)
        passwords = [h["password"] for h in history]
        assert "pass5" in passwords
        # pass0 should have been evicted
        assert "pass0" not in passwords

    def test_no_history_when_password_unchanged(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 1,
            "name": "No Change",
            "login": {"uri": "https://test.com", "username": "u", "password": "same"}
        })
        cipher_id = create.json()["id"]

        # Update without changing password
        requests.put(f"{BASE_URL}/api/ciphers/{cipher_id}", headers=self.headers, json={
            "type": 1,
            "name": "No Change Updated",
            "login": {"uri": "https://test.com", "username": "u", "password": "same"}
        })

        resp = requests.get(f"{BASE_URL}/api/ciphers/{cipher_id}/history", headers=self.headers)
        history = resp.json()["data"]
        assert len(history) == 0


# ─── Attachments Tests ──────────────────────────────────────────────────────

class TestAttachments:
    def setup_method(self):
        self.email = unique_email("attach")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_upload_and_list_attachment(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "With Attachment", "notes": "test"
        })
        cipher_id = create.json()["id"]

        # Upload
        file_content = b"Hello, this is a test file"
        files = {"file": ("test.txt", file_content, "text/plain")}
        resp = requests.post(f"{BASE_URL}/api/ciphers/{cipher_id}/attachment",
                            headers=auth_headers(self.token), files=files)
        assert resp.status_code == 201
        cipher_data = resp.json()
        assert len(cipher_data["attachments"]) == 1
        assert cipher_data["attachments"][0]["fileName"] == "test.txt"

    def test_download_attachment(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Download Attach", "notes": "test"
        })
        cipher_id = create.json()["id"]

        file_content = b"Download me"
        files = {"file": ("download.txt", file_content, "text/plain")}
        upload_resp = requests.post(f"{BASE_URL}/api/ciphers/{cipher_id}/attachment",
                                    headers=auth_headers(self.token), files=files)
        attachment_id = upload_resp.json()["attachments"][0]["id"]

        resp = requests.get(
            f"{BASE_URL}/api/ciphers/{cipher_id}/attachment/{attachment_id}",
            headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["fileName"] == "download.txt"
        # Content should be base64 encoded
        decoded = base64.b64decode(data["data"])
        assert decoded == file_content

    def test_delete_attachment(self):
        create = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Del Attach", "notes": "test"
        })
        cipher_id = create.json()["id"]

        file_content = b"Delete me"
        files = {"file": ("delete.txt", file_content, "text/plain")}
        upload_resp = requests.post(f"{BASE_URL}/api/ciphers/{cipher_id}/attachment",
                                    headers=auth_headers(self.token), files=files)
        attachment_id = upload_resp.json()["attachments"][0]["id"]

        resp = requests.delete(
            f"{BASE_URL}/api/ciphers/{cipher_id}/attachment/{attachment_id}",
            headers=self.headers)
        assert resp.status_code == 200

        # Verify deleted
        resp2 = requests.get(
            f"{BASE_URL}/api/ciphers/{cipher_id}/attachment/{attachment_id}",
            headers=self.headers)
        assert resp2.status_code == 404


# ─── Folder Tests ───────────────────────────────────────────────────────────

class TestFolders:
    def setup_method(self):
        self.email = unique_email("folder")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_create_folder(self):
        resp = requests.post(f"{BASE_URL}/api/folders", headers=self.headers,
                            json={"name": "Work"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Work"
        assert "id" in data
        assert "revisionDate" in data

    def test_list_folders(self):
        requests.post(f"{BASE_URL}/api/folders", headers=self.headers, json={"name": "A"})
        requests.post(f"{BASE_URL}/api/folders", headers=self.headers, json={"name": "B"})
        resp = requests.get(f"{BASE_URL}/api/folders", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_update_folder(self):
        create = requests.post(f"{BASE_URL}/api/folders", headers=self.headers,
                              json={"name": "Old Name"})
        folder_id = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/api/folders/{folder_id}", headers=self.headers,
                           json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_folder(self):
        create = requests.post(f"{BASE_URL}/api/folders", headers=self.headers,
                              json={"name": "Delete Me"})
        folder_id = create.json()["id"]
        resp = requests.delete(f"{BASE_URL}/api/folders/{folder_id}", headers=self.headers)
        assert resp.status_code == 200

    def test_delete_folder_not_found(self):
        resp = requests.delete(f"{BASE_URL}/api/folders/nonexistent", headers=self.headers)
        assert resp.status_code == 404


# ─── Organization Tests ─────────────────────────────────────────────────────

class TestOrganizations:
    def setup_method(self):
        self.owner_email = unique_email("org_owner")
        self.owner_token = get_token(self.owner_email)
        self.owner_headers = auth_headers(self.owner_token)

    def test_create_organization(self):
        resp = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                            json={"name": "My Org"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Org"
        assert "id" in data

    def test_get_organization(self):
        create = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                              json={"name": "Get Org"})
        org_id = create.json()["id"]
        resp = requests.get(f"{BASE_URL}/api/organizations/{org_id}", headers=self.owner_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Org"

    def test_list_members(self):
        create = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                              json={"name": "Members Org"})
        org_id = create.json()["id"]
        resp = requests.get(f"{BASE_URL}/api/organizations/{org_id}/members",
                           headers=self.owner_headers)
        assert resp.status_code == 200
        members = resp.json()["data"]
        # Owner should be the first member
        assert len(members) >= 1
        assert members[0]["role"] == 0  # owner

    def test_invite_and_confirm_member(self):
        # Create org
        create = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                              json={"name": "Invite Org"})
        org_id = create.json()["id"]

        # Register the member
        member_email = unique_email("member")
        register_user(member_email)

        # Invite
        invite_resp = requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/invite",
            headers=self.owner_headers,
            json={"email": member_email, "role": 3}
        )
        assert invite_resp.status_code == 200
        member_data = invite_resp.json()
        assert member_data["status"] == 0  # invited
        member_id = member_data["id"]

        # Confirm
        confirm_resp = requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/{member_id}/confirm",
            headers=self.owner_headers
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == 1  # confirmed

    def test_remove_member(self):
        create = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                              json={"name": "Remove Org"})
        org_id = create.json()["id"]

        member_email = unique_email("remove_member")
        register_user(member_email)

        invite_resp = requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/invite",
            headers=self.owner_headers,
            json={"email": member_email, "role": 3}
        )
        member_id = invite_resp.json()["id"]

        # Remove
        resp = requests.delete(
            f"{BASE_URL}/api/organizations/{org_id}/members/{member_id}",
            headers=self.owner_headers
        )
        assert resp.status_code == 200

    def test_member_cannot_invite(self):
        # Create org
        create = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                              json={"name": "No Invite Org"})
        org_id = create.json()["id"]

        # Create and invite a member
        member_email = unique_email("noinvite")
        member_token = get_token(member_email)
        member_headers = auth_headers(member_token)

        invite_resp = requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/invite",
            headers=self.owner_headers,
            json={"email": member_email, "role": 3}
        )
        member_id = invite_resp.json()["id"]
        requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/{member_id}/confirm",
            headers=self.owner_headers
        )

        # Member tries to invite someone else
        another_email = unique_email("another")
        register_user(another_email)
        resp = requests.post(
            f"{BASE_URL}/api/organizations/{org_id}/members/invite",
            headers=member_headers,
            json={"email": another_email, "role": 3}
        )
        assert resp.status_code == 403


# ─── Collection Tests ───────────────────────────────────────────────────────

class TestCollections:
    def setup_method(self):
        self.owner_email = unique_email("col_owner")
        self.owner_token = get_token(self.owner_email)
        self.owner_headers = auth_headers(self.owner_token)
        # Create org
        resp = requests.post(f"{BASE_URL}/api/organizations", headers=self.owner_headers,
                            json={"name": "Col Org"})
        self.org_id = resp.json()["id"]

    def test_create_collection(self):
        resp = requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections",
            headers=self.owner_headers,
            json={"name": "My Collection"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Collection"
        assert data["organizationId"] == self.org_id

    def test_list_collections(self):
        requests.post(f"{BASE_URL}/api/organizations/{self.org_id}/collections",
                     headers=self.owner_headers, json={"name": "Col A"})
        requests.post(f"{BASE_URL}/api/organizations/{self.org_id}/collections",
                     headers=self.owner_headers, json={"name": "Col B"})
        resp = requests.get(f"{BASE_URL}/api/organizations/{self.org_id}/collections",
                           headers=self.owner_headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    def test_update_collection(self):
        create = requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections",
            headers=self.owner_headers, json={"name": "Old Col"})
        col_id = create.json()["id"]
        resp = requests.put(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections/{col_id}",
            headers=self.owner_headers, json={"name": "New Col"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Col"

    def test_delete_collection(self):
        create = requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections",
            headers=self.owner_headers, json={"name": "Del Col"})
        col_id = create.json()["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections/{col_id}",
            headers=self.owner_headers)
        assert resp.status_code == 200

    def test_collection_sharing(self):
        """Test that org member can see ciphers in a shared collection."""
        # Create collection
        col_resp = requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/collections",
            headers=self.owner_headers, json={"name": "Shared Col"})
        col_id = col_resp.json()["id"]

        # Create cipher in org + collection
        cipher_resp = requests.post(f"{BASE_URL}/api/ciphers", headers=self.owner_headers, json={
            "type": 2,
            "name": "Shared Note",
            "notes": "c2hhcmVk",
            "organizationId": self.org_id,
            "collectionIds": [col_id]
        })
        assert cipher_resp.status_code == 201
        cipher_id = cipher_resp.json()["id"]

        # Add member to org
        member_email = unique_email("share_member")
        member_token = get_token(member_email)
        member_headers = auth_headers(member_token)

        invite_resp = requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/members/invite",
            headers=self.owner_headers,
            json={"email": member_email, "role": 3}
        )
        member_id = invite_resp.json()["id"]
        requests.post(
            f"{BASE_URL}/api/organizations/{self.org_id}/members/{member_id}/confirm",
            headers=self.owner_headers
        )

        # Member should see the cipher in their list
        resp = requests.get(f"{BASE_URL}/api/ciphers", headers=member_headers)
        assert resp.status_code == 200
        cipher_ids = [c["id"] for c in resp.json()["data"]]
        assert cipher_id in cipher_ids


# ─── Send Tests ─────────────────────────────────────────────────────────────

class TestSends:
    def setup_method(self):
        self.email = unique_email("send")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_create_text_send(self):
        resp = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0,
            "name": "My Text Send",
            "text": {"text": "Hello World", "hidden": False}
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 0
        assert data["name"] == "My Text Send"
        assert "accessId" in data
        assert data["accessCount"] == 0

    def test_access_text_send(self):
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0,
            "name": "Access Test",
            "text": {"text": "Secret Message", "hidden": False}
        })
        access_id = create.json()["accessId"]

        # Access without auth
        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"]["text"] == "Secret Message"

    def test_send_password_protection(self):
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0,
            "name": "Protected Send",
            "text": {"text": "Secret", "hidden": False},
            "password": "sendpass123"
        })
        access_id = create.json()["accessId"]

        # Access without password
        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code == 401

        # Access with wrong password
        resp2 = requests.post(f"{BASE_URL}/api/sends/{access_id}/access",
                             json={"password": "wrong"})
        assert resp2.status_code == 401

        # Access with correct password
        resp3 = requests.post(f"{BASE_URL}/api/sends/{access_id}/access",
                             json={"password": "sendpass123"})
        assert resp3.status_code == 200
        assert resp3.json()["text"]["text"] == "Secret"

    def test_send_expiration(self):
        # Create send that is already expired
        past_time = "2000-01-01T00:00:00+00:00"
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0,
            "name": "Expired Send",
            "text": {"text": "Too late", "hidden": False},
            "expirationDate": past_time
        })
        access_id = create.json()["accessId"]

        resp = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp.status_code == 404

    def test_send_max_access_count(self):
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0,
            "name": "Limited Send",
            "text": {"text": "Once only", "hidden": False},
            "maxAccessCount": 2
        })
        access_id = create.json()["accessId"]

        # First access
        resp1 = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp1.status_code == 200

        # Second access
        resp2 = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp2.status_code == 200

        # Third access should fail
        resp3 = requests.post(f"{BASE_URL}/api/sends/{access_id}/access", json={})
        assert resp3.status_code == 404

    def test_list_sends(self):
        requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0, "name": "Send 1", "text": {"text": "one", "hidden": False}
        })
        resp = requests.get(f"{BASE_URL}/api/sends", headers=self.headers)
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_delete_send(self):
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0, "name": "Del Send", "text": {"text": "del", "hidden": False}
        })
        send_id = create.json()["id"]
        resp = requests.delete(f"{BASE_URL}/api/sends/{send_id}", headers=self.headers)
        assert resp.status_code == 200

    def test_update_send(self):
        create = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 0, "name": "Update Send", "text": {"text": "old", "hidden": False}
        })
        send_id = create.json()["id"]
        resp = requests.put(f"{BASE_URL}/api/sends/{send_id}", headers=self.headers, json={
            "type": 0, "name": "Updated Send", "text": {"text": "new", "hidden": True}
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Send"

    def test_create_file_send(self):
        file_data = base64.b64encode(b"file content here").decode()
        resp = requests.post(f"{BASE_URL}/api/sends", headers=self.headers, json={
            "type": 1,
            "name": "File Send",
            "file": {"fileName": "secret.txt", "data": file_data}
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == 1
        assert data["file"]["fileName"] == "secret.txt"


# ─── Two-Factor Authentication Tests ───────────────────────────────────────

class TestTwoFactor:
    def setup_method(self):
        self.email = unique_email("2fa")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_2fa_status_disabled(self):
        resp = requests.get(f"{BASE_URL}/api/two-factor", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_2fa_setup(self):
        resp = requests.post(f"{BASE_URL}/api/two-factor/setup", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert len(data["secret"]) > 0

    def test_2fa_enable_invalid_token(self):
        setup_resp = requests.post(f"{BASE_URL}/api/two-factor/setup", headers=self.headers)
        secret = setup_resp.json()["secret"]

        resp = requests.post(f"{BASE_URL}/api/two-factor/enable",
                            headers=self.headers,
                            json={"token": invalid_totp_token(secret), "secret": secret})
        assert resp.status_code == 400

# ─── Password Generator Tests ──────────────────────────────────────────────

class TestPasswordGenerator:
    def setup_method(self):
        self.email = unique_email("gen")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_generate_default_password(self):
        resp = requests.post(f"{BASE_URL}/api/generator/password",
                            headers=self.headers, json={})
        assert resp.status_code == 200
        pw = resp.json()["password"]
        assert len(pw) == 14  # default length

    def test_generate_custom_length(self):
        resp = requests.post(f"{BASE_URL}/api/generator/password",
                            headers=self.headers,
                            json={"length": 20})
        assert resp.status_code == 200
        pw = resp.json()["password"]
        assert len(pw) == 20

    def test_generate_only_lowercase(self):
        resp = requests.post(f"{BASE_URL}/api/generator/password",
                            headers=self.headers,
                            json={"length": 30, "uppercase": False, "numbers": False,
                                  "special": False, "lowercase": True})
        assert resp.status_code == 200
        pw = resp.json()["password"]
        assert pw.islower()
        assert pw.isalpha()

    def test_generate_with_special(self):
        resp = requests.post(f"{BASE_URL}/api/generator/password",
                            headers=self.headers,
                            json={"length": 50, "special": True, "uppercase": True,
                                  "lowercase": True, "numbers": True})
        assert resp.status_code == 200
        pw = resp.json()["password"]
        assert len(pw) == 50
        # With 50 chars and all types enabled, very likely to have at least one special
        has_special = any(c in "!@#$%^&*()-_=+[]{}|;:',.<>?/`~" for c in pw)
        # Not guaranteed for very short passwords, but 50 chars makes it virtually certain
        assert has_special

    def test_generate_numbers_only(self):
        resp = requests.post(f"{BASE_URL}/api/generator/password",
                            headers=self.headers,
                            json={"length": 20, "uppercase": False, "lowercase": False,
                                  "numbers": True, "special": False})
        assert resp.status_code == 200
        pw = resp.json()["password"]
        assert pw.isdigit()


# ─── Sync Tests ─────────────────────────────────────────────────────────────

class TestSync:
    def setup_method(self):
        self.email = unique_email("sync")
        self.token = get_token(self.email)
        self.headers = auth_headers(self.token)

    def test_sync_full(self):
        # Create some data
        requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Sync Note", "notes": "c3luYw=="
        })
        requests.post(f"{BASE_URL}/api/folders", headers=self.headers, json={"name": "Sync Folder"})

        resp = requests.get(f"{BASE_URL}/api/sync", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ciphers" in data
        assert "folders" in data
        assert "collections" in data
        assert "organizations" in data
        assert len(data["ciphers"]) >= 1
        assert len(data["folders"]) >= 1

    def test_sync_since_timestamp(self):
        # Create first cipher
        old_cipher = requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "Old Note", "notes": "b2xk"
        })

        # Use the server's revision clock so host/container skew cannot alter the scenario.
        since = old_cipher.json()["revisionDate"]
        time.sleep(1)

        # Create second cipher
        requests.post(f"{BASE_URL}/api/ciphers", headers=self.headers, json={
            "type": 2, "name": "New Note", "notes": "bmV3"
        })

        # Sync since timestamp
        resp = requests.get(f"{BASE_URL}/api/sync", headers=self.headers,
                           params={"since": since})
        assert resp.status_code == 200
        data = resp.json()
        cipher_names = [c["name"] for c in data["ciphers"]]
        assert "New Note" in cipher_names
        assert "Old Note" not in cipher_names

    def test_sync_unauthorized(self):
        resp = requests.get(f"{BASE_URL}/api/sync")
        assert resp.status_code == 401
