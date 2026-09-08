import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": "direct-reference-prober-primary-ip",
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


def create_device_prerequisites():
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

    return {
        "site": site.json(),
        "device_type": device_type.json(),
        "role": role.json(),
    }


def valid_device_payload(prereqs, name=None):
    return {
        "name": name or unique("dev"),
        "device_role": prereqs["role"]["id"],
        "device_type": prereqs["device_type"]["id"],
        "site": prereqs["site"]["id"],
        "status": "active",
    }


def test_create_device_rejects_nonexistent_primary_ip():
    prereqs = create_device_prerequisites()
    device_name = unique("bad-primary-create")
    payload = valid_device_payload(prereqs, device_name)
    payload["primary_ip"] = 987654321

    response = api_post("/api/dcim/devices/", payload)

    assert response.status_code == 400, response.text
    devices = api_get("/api/dcim/devices/", params={"site_id": prereqs["site"]["id"]})
    assert devices.status_code == 200, devices.text
    assert all(device["name"] != device_name for device in devices.json()["results"])


def test_update_device_rejects_nonexistent_primary_ip_without_changing_device():
    prereqs = create_device_prerequisites()
    payload = valid_device_payload(prereqs)
    created = api_post("/api/dcim/devices/", payload)
    assert created.status_code == 201, created.text
    device = created.json()

    update_payload = dict(payload)
    update_payload["name"] = device["name"]
    update_payload["primary_ip"] = 987654322

    response = api_put(f"/api/dcim/devices/{device['id']}/", update_payload)

    assert response.status_code == 400, response.text
    reloaded = api_get(f"/api/dcim/devices/{device['id']}/")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json().get("primary_ip") in (None, "")
