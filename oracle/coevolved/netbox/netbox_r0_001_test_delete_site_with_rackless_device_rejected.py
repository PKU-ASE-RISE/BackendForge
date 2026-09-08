import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": "direct-reference-prober-site-device-delete",
    "Content-Type": "application/json",
}


def api_get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def api_post(path, json_data):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def api_delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def create_rackless_device():
    site = api_post("/api/dcim/sites/", {"name": unique("site"), "status": "active"})
    assert site.status_code == 201, site.text

    manufacturer = api_post("/api/dcim/manufacturers/", {"name": unique("mfr")})
    assert manufacturer.status_code == 201, manufacturer.text

    device_type = api_post(
        "/api/dcim/device-types/",
        {
            "manufacturer": manufacturer.json()["id"],
            "model": unique("model"),
            "u_height": 1,
            "is_full_depth": True,
        },
    )
    assert device_type.status_code == 201, device_type.text

    role = api_post(
        "/api/dcim/device-roles/",
        {"name": unique("role"), "color": "aa1409"},
    )
    assert role.status_code == 201, role.text

    device = api_post(
        "/api/dcim/devices/",
        {
            "name": unique("rackless-device"),
            "device_role": role.json()["id"],
            "device_type": device_type.json()["id"],
            "site": site.json()["id"],
            "status": "active",
        },
    )
    assert device.status_code == 201, device.text

    return site.json(), device.json()


def test_delete_site_with_rackless_device_returns_400_and_preserves_resources():
    site, device = create_rackless_device()

    response = api_delete(f"/api/dcim/sites/{site['id']}/")

    assert response.status_code == 400, response.text
    reloaded_site = api_get(f"/api/dcim/sites/{site['id']}/")
    assert reloaded_site.status_code == 200, reloaded_site.text
    reloaded_device = api_get(f"/api/dcim/devices/{device['id']}/")
    assert reloaded_device.status_code == 200, reloaded_device.text
    assert reloaded_device.json()["site"] == site["id"]
