import base64
import hashlib
import hmac
import os
import struct
import time
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
TOTP_PERIOD_SECONDS = 30
TOTP_MIN_VALIDITY_SECONDS = 5


def _register_and_login():
    email = f"totp_setup_{uuid.uuid4().hex}@example.com"
    password = "MasterPass123!"
    register = requests.post(
        f"{BASE_URL}/api/accounts/register",
        json={"email": email, "masterPasswordHash": password, "name": "TOTP Setup"},
    )
    assert register.status_code == 201, register.text
    login = requests.post(
        f"{BASE_URL}/identity/connect/token",
        json={"email": email, "masterPasswordHash": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["accessToken"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _totp_now(secret):
    now = time.time()
    remaining = TOTP_PERIOD_SECONDS - (now % TOTP_PERIOD_SECONDS)
    if remaining < TOTP_MIN_VALIDITY_SECONDS:
        time.sleep(remaining + 0.05)
        now = time.time()

    key = base64.b32decode(secret, casefold=True)
    counter = int(now // TOTP_PERIOD_SECONDS)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1000000:06d}"


def test_two_factor_enable_requires_setup_secret():
    token = _register_and_login()

    setup_resp = requests.post(f"{BASE_URL}/api/two-factor/setup", headers=_auth(token))
    assert setup_resp.status_code == 200, setup_resp.text
    setup_secret = setup_resp.json()["secret"]

    replacement = "A" if setup_secret[0].upper() != "A" else "B"
    unissued_secret = replacement + setup_secret[1:]
    assert unissued_secret != setup_secret
    token_for_unissued_secret = _totp_now(unissued_secret)

    enable_resp = requests.post(
        f"{BASE_URL}/api/two-factor/enable",
        headers=_auth(token),
        json={"secret": unissued_secret, "token": token_for_unissued_secret},
    )

    assert enable_resp.status_code == 400, enable_resp.text
