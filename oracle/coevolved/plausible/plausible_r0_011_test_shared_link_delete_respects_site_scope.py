import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = API_KEY
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def create_site():
    domain = f"drp-{uuid.uuid4().hex}.example.com"
    response = api("POST", "/api/sites", json={"domain": domain, "timezone": "UTC"})
    assert response.status_code == 201, response.text
    return response.json()


def test_shared_link_delete_respects_site_scope():
    owner_site = create_site()
    other_site = create_site()
    created = api(
        "POST",
        f"/api/sites/{owner_site['id']}/shared-links",
        json={"name": f"Public {uuid.uuid4().hex}"},
    )
    assert created.status_code == 201, created.text
    link = created.json()

    wrong_site_delete = api(
        "DELETE",
        f"/api/sites/{other_site['id']}/shared-links/{link['id']}",
    )
    assert wrong_site_delete.status_code == 404, wrong_site_delete.text

    links = api("GET", f"/api/sites/{owner_site['id']}/shared-links")
    assert links.status_code == 200, links.text
    assert link["id"] in {item["id"] for item in links.json()}

    shared_dashboard = requests.get(f"{BASE_URL}/api/shared/{link['slug']}")
    assert shared_dashboard.status_code == 200, shared_dashboard.text
