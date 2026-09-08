import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def create_localized_content_type():
    name = f"ct_{uuid.uuid4().hex[:10]}"
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={
            "name": name,
            "displayName": "Localization Probe",
            "settings": {"localization": True},
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201
    ct = resp.json()["data"]
    field_resp = requests.post(
        f"{BASE_URL}/content-types/{ct['id']}/fields",
        json={"name": "title", "type": "text"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert field_resp.status_code == 201
    return ct


def test_localization_rejects_original_locale_duplicate():
    ct = create_localized_content_type()
    entry_resp = requests.post(
        f"{BASE_URL}/content/{ct['name']}",
        json={"title": "Original English"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert entry_resp.status_code == 201
    original = entry_resp.json()["data"]
    assert original["locale"] == "en"

    resp = requests.post(
        f"{BASE_URL}/content/{ct['name']}/{original['id']}/localizations",
        json={"locale": "en", "title": "Duplicate English"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
