import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers():
    return {"X-Api-Key": f"locale-newline-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def _create_project(headers):
    resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"name": f"locale-newline-project-{uuid.uuid4().hex}", "description": "locale newline probe"},
        headers=headers,
        timeout=30,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def test_add_locale_rejects_embedded_newline_code():
    headers = _headers()
    project_id = _create_project(headers)
    invalid_code = "e\nn"  # Fails the specified pattern regardless of $ semantics.

    add_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/locales",
        json={"code": invalid_code},
        headers=headers,
        timeout=30,
    )
    list_resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}/locales", headers=headers, timeout=30)

    assert list_resp.status_code == 200, list_resp.text
    locale_codes = {locale["code"] for locale in list_resp.json()["data"]}
    assert add_resp.status_code == 400, add_resp.text
    assert invalid_code not in locale_codes
