import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": "direct-reference-prober-rack-height",
    "Content-Type": "application/json",
}


def api_get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def api_post(path, json_data):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def api_put(path, json_data):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def create_site():
    response = api_post("/api/dcim/sites/", {"name": unique("site"), "status": "active"})
    assert response.status_code == 201, response.text
    return response.json()


def create_rack(site_id, u_height=12):
    response = api_post(
        "/api/dcim/racks/",
        {
            "name": unique("rack"),
            "site": site_id,
            "status": "active",
            "u_height": u_height,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_rack_rejects_zero_u_height():
    site = create_site()
    rack_name = unique("zero-height-rack")

    response = api_post(
        "/api/dcim/racks/",
        {
            "name": rack_name,
            "site": site["id"],
            "status": "active",
            "u_height": 0,
        },
    )

    assert response.status_code == 400, response.text
    racks = api_get("/api/dcim/racks/", params={"site_id": site["id"]})
    assert racks.status_code == 200, racks.text
    assert all(rack["name"] != rack_name for rack in racks.json()["results"])


def test_create_rack_rejects_missing_required_u_height():
    site = create_site()
    rack_name = unique("missing-height-rack")

    response = api_post(
        "/api/dcim/racks/",
        {
            "name": rack_name,
            "site": site["id"],
            "status": "active",
        },
    )

    assert response.status_code == 400, response.text
    racks = api_get("/api/dcim/racks/", params={"site_id": site["id"]})
    assert racks.status_code == 200, racks.text
    assert all(rack["name"] != rack_name for rack in racks.json()["results"])


def test_update_rack_rejects_zero_u_height_and_preserves_original_height():
    site = create_site()
    rack = create_rack(site["id"], u_height=12)

    response = api_put(
        f"/api/dcim/racks/{rack['id']}/",
        {
            "name": rack["name"],
            "site": site["id"],
            "status": "active",
            "u_height": 0,
        },
    )

    assert response.status_code == 400, response.text
    reloaded = api_get(f"/api/dcim/racks/{rack['id']}/")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["u_height"] == 12
