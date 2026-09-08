import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": "direct-reference-prober-rack-shrink",
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


def create_stack():
    site = api_post("/api/dcim/sites/", {"name": unique("site"), "status": "active"})
    assert site.status_code == 201, site.text

    manufacturer = api_post("/api/dcim/manufacturers/", {"name": unique("mfr")})
    assert manufacturer.status_code == 201, manufacturer.text

    device_type = api_post(
        "/api/dcim/device-types/",
        {
            "manufacturer": manufacturer.json()["id"],
            "model": unique("model"),
            "u_height": 2,
            "is_full_depth": True,
        },
    )
    assert device_type.status_code == 201, device_type.text

    role = api_post(
        "/api/dcim/device-roles/",
        {"name": unique("role"), "color": "aa1409"},
    )
    assert role.status_code == 201, role.text

    rack = api_post(
        "/api/dcim/racks/",
        {
            "name": unique("rack"),
            "site": site.json()["id"],
            "status": "active",
            "u_height": 10,
        },
    )
    assert rack.status_code == 201, rack.text

    device = api_post(
        "/api/dcim/devices/",
        {
            "name": unique("device"),
            "device_role": role.json()["id"],
            "device_type": device_type.json()["id"],
            "site": site.json()["id"],
            "rack": rack.json()["id"],
            "position": 9,
            "status": "active",
        },
    )
    assert device.status_code == 201, device.text

    return {"site": site.json(), "rack": rack.json(), "device": device.json()}


def test_update_rack_rejects_height_that_would_exclude_existing_device():
    stack = create_stack()
    rack = stack["rack"]

    response = api_put(
        f"/api/dcim/racks/{rack['id']}/",
        {
            "name": rack["name"],
            "site": stack["site"]["id"],
            "status": rack["status"],
            "u_height": 9,
        },
    )

    assert response.status_code == 400, response.text
    reloaded_rack = api_get(f"/api/dcim/racks/{rack['id']}/")
    assert reloaded_rack.status_code == 200, reloaded_rack.text
    assert reloaded_rack.json()["u_height"] == 10

    reloaded_device = api_get(f"/api/dcim/devices/{stack['device']['id']}/")
    assert reloaded_device.status_code == 200, reloaded_device.text
    assert reloaded_device.json()["position"] == 9
