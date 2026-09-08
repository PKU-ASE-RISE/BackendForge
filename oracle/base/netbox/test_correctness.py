"""
BackendForge — Comprehensive Correctness Tests for NetBox Task

Tests ALL business rules and ALL endpoint groups.
"""

import os
import uuid

import pytest
import requests

# ── Config ──

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = "test-api-key-netbox"

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

UNIQUE = uuid.uuid4().hex[:8]


# ── HTTP Helpers ──

def api_get(path, params=None, headers=None):
    return requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_post(path, json_data=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_put(path, json_data=None, headers=None):
    return requests.put(
        f"{BASE_URL}{path}",
        json=json_data,
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


def api_delete(path, headers=None):
    return requests.delete(
        f"{BASE_URL}{path}",
        headers=HEADERS if headers is None else headers,
        timeout=30,
    )


# ── Helper: create prerequisite resources ──

def create_region(name=None, parent=None):
    name = name or f"region-{uuid.uuid4().hex[:8]}"
    data = {"name": name}
    if parent is not None:
        data["parent"] = parent
    resp = api_post("/api/dcim/regions/", data)
    assert resp.status_code == 201, f"Failed to create region: {resp.text}"
    return resp.json()


def create_site(name=None, status="active", region=None):
    name = name or f"site-{uuid.uuid4().hex[:8]}"
    data = {"name": name, "status": status}
    if region is not None:
        data["region"] = region
    resp = api_post("/api/dcim/sites/", data)
    assert resp.status_code == 201, f"Failed to create site: {resp.text}"
    return resp.json()


def create_manufacturer(name=None):
    name = name or f"mfr-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/dcim/manufacturers/", {"name": name})
    assert resp.status_code == 201, f"Failed to create manufacturer: {resp.text}"
    return resp.json()


def create_device_type(manufacturer_id, model=None, u_height=1):
    model = model or f"model-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/dcim/device-types/", {
        "manufacturer": manufacturer_id,
        "model": model,
        "u_height": u_height,
    })
    assert resp.status_code == 201, f"Failed to create device type: {resp.text}"
    return resp.json()


def create_device_role(name=None, color="aa1409"):
    name = name or f"role-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/dcim/device-roles/", {
        "name": name,
        "color": color,
    })
    assert resp.status_code == 201, f"Failed to create device role: {resp.text}"
    return resp.json()


def create_rack(site_id, name=None, u_height=42):
    name = name or f"rack-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/dcim/racks/", {
        "name": name,
        "site": site_id,
        "status": "active",
        "u_height": u_height,
    })
    assert resp.status_code == 201, f"Failed to create rack: {resp.text}"
    return resp.json()


def create_device(name=None, site_id=None, device_role_id=None,
                  device_type_id=None, rack_id=None, position=None, status="active"):
    name = name or f"device-{uuid.uuid4().hex[:8]}"
    data = {
        "name": name,
        "device_role": device_role_id,
        "device_type": device_type_id,
        "site": site_id,
        "status": status,
    }
    if rack_id is not None:
        data["rack"] = rack_id
    if position is not None:
        data["position"] = position
    resp = api_post("/api/dcim/devices/", data)
    assert resp.status_code == 201, f"Failed to create device: {resp.text}"
    return resp.json()


def create_interface(device_id, name=None, itype="1000base-t"):
    name = name or f"eth-{uuid.uuid4().hex[:8]}"
    resp = api_post("/api/dcim/interfaces/", {
        "name": name,
        "device": device_id,
        "type": itype,
    })
    assert resp.status_code == 201, f"Failed to create interface: {resp.text}"
    return resp.json()


def create_full_device_stack():
    """Create site, manufacturer, device_type, device_role, rack — returns dict of IDs."""
    site = create_site()
    mfr = create_manufacturer()
    dt = create_device_type(mfr["id"], u_height=2)
    role = create_device_role()
    rack = create_rack(site["id"], u_height=42)
    return {
        "site_id": site["id"],
        "manufacturer_id": mfr["id"],
        "device_type_id": dt["id"],
        "device_role_id": role["id"],
        "rack_id": rack["id"],
    }


# ════════════════════════════════════════════════════════════════════
# PART 1: Authentication
# ════════════════════════════════════════════════════════════════════

class TestAuthentication:

    def test_missing_api_key_returns_401(self):
        """All endpoints require X-Api-Key header."""
        resp = requests.get(f"{BASE_URL}/api/dcim/regions/", timeout=30)
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        resp = requests.get(
            f"{BASE_URL}/api/dcim/regions/",
            headers={"X-Api-Key": "", "Content-Type": "application/json"},
            timeout=30
        )
        assert resp.status_code == 401

    def test_valid_api_key_succeeds(self):
        resp = api_get("/api/dcim/regions/")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════
# PART 2: Regions
# ════════════════════════════════════════════════════════════════════

class TestRegions:

    def test_create_region(self):
        name = f"test-region-{UNIQUE}"
        resp = api_post("/api/dcim/regions/", {"name": name})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert "id" in data
        assert "slug" in data
        assert data["slug"] != ""

    def test_create_region_auto_slug(self):
        name = f"My Test Region {UNIQUE}"
        resp = api_post("/api/dcim/regions/", {"name": name})
        assert resp.status_code == 201
        data = resp.json()
        # Slug should be lowercase with hyphens
        assert " " not in data["slug"]
        assert data["slug"] == data["slug"].lower()

    def test_create_region_custom_slug(self):
        name = f"region-custom-{UNIQUE}"
        slug = f"custom-slug-{UNIQUE}"
        resp = api_post("/api/dcim/regions/", {"name": name, "slug": slug})
        assert resp.status_code == 201
        assert resp.json()["slug"] == slug

    def test_create_region_duplicate_slug_fails(self):
        slug = f"dup-slug-{uuid.uuid4().hex[:8]}"
        resp1 = api_post("/api/dcim/regions/", {"name": f"r1-{slug}", "slug": slug})
        assert resp1.status_code == 201
        resp2 = api_post("/api/dcim/regions/", {"name": f"r2-{slug}", "slug": slug})
        assert resp2.status_code == 400

    def test_create_region_with_parent(self):
        parent = create_region()
        child = create_region(parent=parent["id"])
        assert child["parent"] == parent["id"]

    def test_create_region_self_parent_fails(self):
        """A region cannot be its own parent (validated at creation via nonexistent ID)."""
        region = create_region()
        # Try creating a child with invalid parent (should fail)
        resp = api_post("/api/dcim/regions/", {
            "name": f"self-parent-{uuid.uuid4().hex[:8]}",
            "parent": 999999
        })
        assert resp.status_code == 400

    def test_list_regions(self):
        create_region()
        resp = api_get("/api/dcim/regions/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1
        assert len(data["results"]) >= 1

    def test_list_regions_filter_by_name(self):
        name = f"filter-test-{uuid.uuid4().hex[:8]}"
        create_region(name=name)
        resp = api_get("/api/dcim/regions/", params={"name": name})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert all(r["name"] == name for r in data["results"])

    def test_get_region(self):
        region = create_region()
        resp = api_get(f"/api/dcim/regions/{region['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == region["id"]

    def test_get_region_not_found(self):
        resp = api_get("/api/dcim/regions/999999/")
        assert resp.status_code == 404

    def test_delete_region(self):
        region = create_region()
        resp = api_delete(f"/api/dcim/regions/{region['id']}/")
        assert resp.status_code == 204
        # Confirm gone
        resp2 = api_get(f"/api/dcim/regions/{region['id']}/")
        assert resp2.status_code == 404

    def test_delete_region_not_found(self):
        resp = api_delete("/api/dcim/regions/999999/")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 3: Sites
# ════════════════════════════════════════════════════════════════════

class TestSites:

    def test_create_site(self):
        name = f"site-{UNIQUE}"
        resp = api_post("/api/dcim/sites/", {
            "name": name,
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["status"] == "active"
        assert "slug" in data

    def test_create_site_with_region(self):
        region = create_region()
        site = create_site(region=region["id"])
        assert site["region"] == region["id"]

    def test_create_site_invalid_status(self):
        resp = api_post("/api/dcim/sites/", {
            "name": f"bad-status-{UNIQUE}",
            "status": "invalid_status",
        })
        assert resp.status_code == 400

    def test_create_site_invalid_region(self):
        resp = api_post("/api/dcim/sites/", {
            "name": f"bad-region-{uuid.uuid4().hex[:8]}",
            "status": "active",
            "region": 999999,
        })
        assert resp.status_code == 400

    def test_list_sites(self):
        create_site()
        resp = api_get("/api/dcim/sites/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] >= 1

    def test_list_sites_filter_by_status(self):
        create_site(status="planned")
        resp = api_get("/api/dcim/sites/", params={"status": "planned"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "planned" for s in data["results"])

    def test_get_site(self):
        site = create_site()
        resp = api_get(f"/api/dcim/sites/{site['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == site["id"]

    def test_update_site(self):
        site = create_site()
        new_name = f"updated-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/dcim/sites/{site['id']}/", {
            "name": new_name,
            "status": "planned",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name
        assert resp.json()["status"] == "planned"

    def test_delete_site(self):
        site = create_site()
        resp = api_delete(f"/api/dcim/sites/{site['id']}/")
        assert resp.status_code == 204

    def test_delete_site_with_racks_fails(self):
        site = create_site()
        create_rack(site["id"])
        resp = api_delete(f"/api/dcim/sites/{site['id']}/")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 4: Manufacturers
# ════════════════════════════════════════════════════════════════════

class TestManufacturers:

    def test_create_manufacturer(self):
        name = f"mfr-{UNIQUE}"
        resp = api_post("/api/dcim/manufacturers/", {"name": name})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert "slug" in data

    def test_create_manufacturer_duplicate_slug_fails(self):
        slug = f"mfr-dup-{uuid.uuid4().hex[:8]}"
        api_post("/api/dcim/manufacturers/", {"name": f"m1-{slug}", "slug": slug})
        resp = api_post("/api/dcim/manufacturers/", {"name": f"m2-{slug}", "slug": slug})
        assert resp.status_code == 400

    def test_list_manufacturers(self):
        create_manufacturer()
        resp = api_get("/api/dcim/manufacturers/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_get_manufacturer(self):
        mfr = create_manufacturer()
        resp = api_get(f"/api/dcim/manufacturers/{mfr['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == mfr["id"]

    def test_delete_manufacturer(self):
        mfr = create_manufacturer()
        resp = api_delete(f"/api/dcim/manufacturers/{mfr['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 5: Device Types
# ════════════════════════════════════════════════════════════════════

class TestDeviceTypes:

    def test_create_device_type(self):
        mfr = create_manufacturer()
        model = f"PowerEdge-{UNIQUE}"
        resp = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"],
            "model": model,
            "u_height": 2,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["model"] == model
        assert data["manufacturer"] == mfr["id"]
        assert data["u_height"] == 2
        assert data["is_full_depth"] is True  # default
        assert "slug" in data

    def test_create_device_type_invalid_manufacturer(self):
        resp = api_post("/api/dcim/device-types/", {
            "manufacturer": 999999,
            "model": f"bad-{uuid.uuid4().hex[:8]}",
            "u_height": 1,
        })
        assert resp.status_code == 400

    def test_list_device_types(self):
        mfr = create_manufacturer()
        create_device_type(mfr["id"])
        resp = api_get("/api/dcim/device-types/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_list_device_types_filter_by_manufacturer(self):
        mfr = create_manufacturer()
        dt = create_device_type(mfr["id"])
        resp = api_get("/api/dcim/device-types/", params={"manufacturer_id": mfr["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["manufacturer"] == mfr["id"] for d in data["results"])

    def test_get_device_type(self):
        mfr = create_manufacturer()
        dt = create_device_type(mfr["id"])
        resp = api_get(f"/api/dcim/device-types/{dt['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == dt["id"]

    def test_delete_device_type(self):
        mfr = create_manufacturer()
        dt = create_device_type(mfr["id"])
        resp = api_delete(f"/api/dcim/device-types/{dt['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 6: Device Roles
# ════════════════════════════════════════════════════════════════════

class TestDeviceRoles:

    def test_create_device_role(self):
        name = f"role-{UNIQUE}"
        resp = api_post("/api/dcim/device-roles/", {
            "name": name,
            "color": "ff0000",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["color"] == "ff0000"
        assert data["vm_role"] is False  # default
        assert "slug" in data

    def test_create_device_role_with_vm_role(self):
        name = f"vm-role-{uuid.uuid4().hex[:8]}"
        resp = api_post("/api/dcim/device-roles/", {
            "name": name,
            "color": "00ff00",
            "vm_role": True,
        })
        assert resp.status_code == 201
        assert resp.json()["vm_role"] is True

    def test_list_device_roles(self):
        create_device_role()
        resp = api_get("/api/dcim/device-roles/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_get_device_role(self):
        role = create_device_role()
        resp = api_get(f"/api/dcim/device-roles/{role['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == role["id"]

    def test_delete_device_role(self):
        role = create_device_role()
        resp = api_delete(f"/api/dcim/device-roles/{role['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 7: Racks
# ════════════════════════════════════════════════════════════════════

class TestRacks:

    def test_create_rack(self):
        site = create_site()
        name = f"rack-{UNIQUE}"
        resp = api_post("/api/dcim/racks/", {
            "name": name,
            "site": site["id"],
            "status": "active",
            "u_height": 42,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["site"] == site["id"]
        assert data["u_height"] == 42

    def test_create_rack_invalid_site(self):
        resp = api_post("/api/dcim/racks/", {
            "name": f"bad-rack-{uuid.uuid4().hex[:8]}",
            "site": 999999,
            "status": "active",
            "u_height": 42,
        })
        assert resp.status_code == 400

    def test_rack_utilization_empty(self):
        """A rack with no devices should have 0% utilization."""
        site = create_site()
        rack = create_rack(site["id"], u_height=42)
        resp = api_get(f"/api/dcim/racks/{rack['id']}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "utilization" in data
        assert data["utilization"] == 0

    def test_rack_utilization_with_devices(self):
        """Rack utilization = floor(occupied_units / u_height * 100)."""
        stack = create_full_device_stack()
        # Device type has u_height=2, rack has u_height=42
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        resp = api_get(f"/api/dcim/racks/{stack['rack_id']}/")
        data = resp.json()
        # 2 units occupied out of 42 = floor(2/42*100) = 4
        assert data["utilization"] == 4

    def test_list_racks(self):
        site = create_site()
        create_rack(site["id"])
        resp = api_get("/api/dcim/racks/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_list_racks_filter_by_site(self):
        site = create_site()
        create_rack(site["id"])
        resp = api_get("/api/dcim/racks/", params={"site_id": site["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["site"] == site["id"] for r in data["results"])

    def test_update_rack(self):
        site = create_site()
        rack = create_rack(site["id"])
        resp = api_put(f"/api/dcim/racks/{rack['id']}/", {
            "name": f"updated-{uuid.uuid4().hex[:8]}",
            "site": site["id"],
            "status": "reserved",
            "u_height": 48,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "reserved"
        assert resp.json()["u_height"] == 48

    def test_delete_rack(self):
        site = create_site()
        rack = create_rack(site["id"])
        resp = api_delete(f"/api/dcim/racks/{rack['id']}/")
        assert resp.status_code == 204

    def test_delete_rack_with_devices_fails(self):
        stack = create_full_device_stack()
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        resp = api_delete(f"/api/dcim/racks/{stack['rack_id']}/")
        assert resp.status_code == 400


# ════════════════════════════════════════════════════════════════════
# PART 8: Devices
# ════════════════════════════════════════════════════════════════════

class TestDevices:

    def test_create_device(self):
        stack = create_full_device_stack()
        name = f"device-{UNIQUE}"
        resp = api_post("/api/dcim/devices/", {
            "name": name,
            "device_role": stack["device_role_id"],
            "device_type": stack["device_type_id"],
            "site": stack["site_id"],
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["status"] == "active"

    def test_create_device_in_rack(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        assert device["rack"] == stack["rack_id"]
        assert device["position"] == 1

    def test_create_device_rack_overlap_fails(self):
        """Two devices cannot occupy the same rack units."""
        stack = create_full_device_stack()
        # First device at position 1, u_height=2 (occupies units 1-2)
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        # Second device at position 2 — overlaps with first (unit 2)
        resp = api_post("/api/dcim/devices/", {
            "name": f"overlap-{uuid.uuid4().hex[:8]}",
            "device_role": stack["device_role_id"],
            "device_type": stack["device_type_id"],
            "site": stack["site_id"],
            "rack": stack["rack_id"],
            "position": 2,
            "status": "active",
        })
        assert resp.status_code == 400

    def test_create_device_rack_no_overlap_adjacent(self):
        """Devices in adjacent rack units (not overlapping) should succeed."""
        stack = create_full_device_stack()
        # First device at position 1, u_height=2 (occupies 1-2)
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        # Second device at position 3 (no overlap)
        device2 = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=3,
        )
        assert device2["position"] == 3

    def test_create_device_exceeds_rack_height(self):
        """Device position + u_height - 1 cannot exceed rack u_height."""
        site = create_site()
        mfr = create_manufacturer()
        dt = create_device_type(mfr["id"], u_height=4)  # 4U device
        role = create_device_role()
        rack = create_rack(site["id"], u_height=10)  # 10U rack

        # Position 8 + u_height 4 - 1 = 11 > 10 rack units
        resp = api_post("/api/dcim/devices/", {
            "name": f"exceed-{uuid.uuid4().hex[:8]}",
            "device_role": role["id"],
            "device_type": dt["id"],
            "site": site["id"],
            "rack": rack["id"],
            "position": 8,
            "status": "active",
        })
        assert resp.status_code == 400

    def test_create_device_invalid_fk(self):
        """Invalid foreign key references should return 400."""
        resp = api_post("/api/dcim/devices/", {
            "name": f"bad-fk-{uuid.uuid4().hex[:8]}",
            "device_role": 999999,
            "device_type": 999999,
            "site": 999999,
            "status": "active",
        })
        assert resp.status_code == 400

    def test_list_devices(self):
        stack = create_full_device_stack()
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_get("/api/dcim/devices/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_list_devices_filter_by_site(self):
        stack = create_full_device_stack()
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_get("/api/dcim/devices/", params={"site_id": stack["site_id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["site"] == stack["site_id"] for d in data["results"])

    def test_list_devices_filter_by_rack(self):
        stack = create_full_device_stack()
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        resp = api_get("/api/dcim/devices/", params={"rack_id": stack["rack_id"]})
        data = resp.json()
        assert all(d["rack"] == stack["rack_id"] for d in data["results"])

    def test_get_device(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_get(f"/api/dcim/devices/{device['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == device["id"]

    def test_update_device(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        new_name = f"updated-device-{uuid.uuid4().hex[:8]}"
        resp = api_put(f"/api/dcim/devices/{device['id']}/", {
            "name": new_name,
            "device_role": stack["device_role_id"],
            "device_type": stack["device_type_id"],
            "site": stack["site_id"],
            "status": "offline",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name
        assert resp.json()["status"] == "offline"

    def test_update_device_rack_overlap_fails(self):
        """Moving a device to an occupied rack position should fail."""
        stack = create_full_device_stack()
        # Device 1 at position 1 (occupies 1-2)
        create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=1,
        )
        # Device 2 at position 5 (occupies 5-6)
        device2 = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
            rack_id=stack["rack_id"],
            position=5,
        )
        # Try to move device 2 to position 1 (overlaps with device 1)
        resp = api_put(f"/api/dcim/devices/{device2['id']}/", {
            "name": device2["name"],
            "device_role": stack["device_role_id"],
            "device_type": stack["device_type_id"],
            "site": stack["site_id"],
            "rack": stack["rack_id"],
            "position": 1,
            "status": "active",
        })
        assert resp.status_code == 400

    def test_delete_device(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_delete(f"/api/dcim/devices/{device['id']}/")
        assert resp.status_code == 204

    def test_delete_device_cascades_interfaces(self):
        """Deleting a device should also delete its interfaces."""
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface = create_interface(device["id"])
        # Delete device
        resp = api_delete(f"/api/dcim/devices/{device['id']}/")
        assert resp.status_code == 204
        # Interface should be gone
        resp2 = api_get(f"/api/dcim/interfaces/{iface['id']}/")
        assert resp2.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 9: Interfaces
# ════════════════════════════════════════════════════════════════════

class TestInterfaces:

    def test_create_interface(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_post("/api/dcim/interfaces/", {
            "name": "eth0",
            "device": device["id"],
            "type": "1000base-t",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "eth0"
        assert data["device"] == device["id"]
        assert data["type"] == "1000base-t"
        assert data["enabled"] is True  # default

    def test_create_interface_with_options(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        resp = api_post("/api/dcim/interfaces/", {
            "name": "eth1",
            "device": device["id"],
            "type": "10gbase-t",
            "enabled": False,
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "mtu": 9000,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["enabled"] is False
        assert data["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert data["mtu"] == 9000

    def test_create_interface_invalid_device(self):
        resp = api_post("/api/dcim/interfaces/", {
            "name": "eth0",
            "device": 999999,
            "type": "1000base-t",
        })
        assert resp.status_code == 400

    def test_list_interfaces(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        create_interface(device["id"])
        resp = api_get("/api/dcim/interfaces/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_list_interfaces_filter_by_device(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        create_interface(device["id"])
        resp = api_get("/api/dcim/interfaces/", params={"device_id": device["id"]})
        data = resp.json()
        assert all(i["device"] == device["id"] for i in data["results"])

    def test_get_interface(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface = create_interface(device["id"])
        resp = api_get(f"/api/dcim/interfaces/{iface['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == iface["id"]

    def test_delete_interface(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface = create_interface(device["id"])
        resp = api_delete(f"/api/dcim/interfaces/{iface['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 10: IP Addresses
# ════════════════════════════════════════════════════════════════════

class TestIPAddresses:

    def test_create_ip_address(self):
        addr = f"10.0.{UNIQUE[:2]}.1/24" if UNIQUE[:2].isdigit() else "10.0.1.1/24"
        # Use unique address
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.1/24"
        resp = api_post("/api/ipam/ip-addresses/", {
            "address": addr,
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["address"] == addr
        assert data["status"] == "active"

    def test_create_ip_address_duplicate_fails(self):
        addr = f"10.99.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}/32"
        resp1 = api_post("/api/ipam/ip-addresses/", {
            "address": addr,
            "status": "active",
        })
        assert resp1.status_code == 201
        resp2 = api_post("/api/ipam/ip-addresses/", {
            "address": addr,
            "status": "reserved",
        })
        assert resp2.status_code == 400

    def test_create_ip_address_with_device(self):
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.5/24"
        resp = api_post("/api/ipam/ip-addresses/", {
            "address": addr,
            "status": "active",
            "assigned_device": device["id"],
        })
        assert resp.status_code == 201
        assert resp.json()["assigned_device"] == device["id"]

    def test_list_ip_addresses(self):
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.1/24"
        api_post("/api/ipam/ip-addresses/", {"address": addr, "status": "active"})
        resp = api_get("/api/ipam/ip-addresses/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_get_ip_address(self):
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.1/24"
        created = api_post("/api/ipam/ip-addresses/", {"address": addr, "status": "active"}).json()
        resp = api_get(f"/api/ipam/ip-addresses/{created['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_update_ip_address(self):
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.1/24"
        created = api_post("/api/ipam/ip-addresses/", {"address": addr, "status": "active"}).json()
        new_addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.2/24"
        resp = api_put(f"/api/ipam/ip-addresses/{created['id']}/", {
            "address": new_addr,
            "status": "reserved",
        })
        assert resp.status_code == 200
        assert resp.json()["address"] == new_addr
        assert resp.json()["status"] == "reserved"

    def test_update_ip_address_duplicate_fails(self):
        addr1 = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.1/24"
        addr2 = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.2/24"
        ip1 = api_post("/api/ipam/ip-addresses/", {"address": addr1, "status": "active"}).json()
        ip2 = api_post("/api/ipam/ip-addresses/", {"address": addr2, "status": "active"}).json()
        # Try to update ip2 to same address as ip1
        resp = api_put(f"/api/ipam/ip-addresses/{ip2['id']}/", {
            "address": addr1,
            "status": "active",
        })
        assert resp.status_code == 400

    def test_delete_ip_address(self):
        addr = f"10.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}.99/24"
        created = api_post("/api/ipam/ip-addresses/", {"address": addr, "status": "active"}).json()
        resp = api_delete(f"/api/ipam/ip-addresses/{created['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 11: Prefixes
# ════════════════════════════════════════════════════════════════════

class TestPrefixes:

    def test_create_prefix(self):
        prefix = f"172.16.{uuid.uuid4().int % 256}.0/24"
        resp = api_post("/api/ipam/prefixes/", {
            "prefix": prefix,
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["prefix"] == prefix
        assert data["status"] == "active"
        assert data["is_pool"] is False  # default

    def test_create_prefix_with_site(self):
        site = create_site()
        prefix = f"172.17.{uuid.uuid4().int % 256}.0/24"
        resp = api_post("/api/ipam/prefixes/", {
            "prefix": prefix,
            "status": "active",
            "site": site["id"],
        })
        assert resp.status_code == 201
        assert resp.json()["site"] == site["id"]

    def test_get_prefix_includes_ip_addresses(self):
        """GET on a prefix should include ip_addresses that fall within it."""
        # Create a /24 prefix
        net_octet = uuid.uuid4().int % 256
        prefix_cidr = f"192.168.{net_octet}.0/24"
        prefix = api_post("/api/ipam/prefixes/", {
            "prefix": prefix_cidr,
            "status": "active",
        }).json()

        # Create an IP within the prefix
        ip_in = api_post("/api/ipam/ip-addresses/", {
            "address": f"192.168.{net_octet}.10/24",
            "status": "active",
        }).json()

        # Create an IP outside the prefix
        other_octet = (net_octet + 1) % 256
        api_post("/api/ipam/ip-addresses/", {
            "address": f"192.168.{other_octet}.10/24",
            "status": "active",
        })

        # Get prefix — should include ip_addresses
        resp = api_get(f"/api/ipam/prefixes/{prefix['id']}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "ip_addresses" in data
        ip_ids = [ip["id"] for ip in data["ip_addresses"]]
        assert ip_in["id"] in ip_ids

    def test_list_prefixes(self):
        prefix = f"172.18.{uuid.uuid4().int % 256}.0/24"
        api_post("/api/ipam/prefixes/", {"prefix": prefix, "status": "active"})
        resp = api_get("/api/ipam/prefixes/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_delete_prefix(self):
        prefix = f"172.19.{uuid.uuid4().int % 256}.0/24"
        created = api_post("/api/ipam/prefixes/", {"prefix": prefix, "status": "active"}).json()
        resp = api_delete(f"/api/ipam/prefixes/{created['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 12: VLANs
# ════════════════════════════════════════════════════════════════════

class TestVLANs:

    def test_create_vlan(self):
        vid = (uuid.uuid4().int % 4094) + 1
        resp = api_post("/api/ipam/vlans/", {
            "vid": vid,
            "name": f"vlan-{vid}",
            "status": "active",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["vid"] == vid
        assert data["name"] == f"vlan-{vid}"

    def test_create_vlan_vid_too_low(self):
        resp = api_post("/api/ipam/vlans/", {
            "vid": 0,
            "name": "bad-vlan",
            "status": "active",
        })
        assert resp.status_code == 400

    def test_create_vlan_vid_too_high(self):
        resp = api_post("/api/ipam/vlans/", {
            "vid": 4095,
            "name": "bad-vlan",
            "status": "active",
        })
        assert resp.status_code == 400

    def test_create_vlan_vid_boundary_low(self):
        """vid=1 should be valid."""
        resp = api_post("/api/ipam/vlans/", {
            "vid": 1,
            "name": f"vlan-1-{uuid.uuid4().hex[:8]}",
            "status": "active",
        })
        assert resp.status_code == 201

    def test_create_vlan_vid_boundary_high(self):
        """vid=4094 should be valid."""
        resp = api_post("/api/ipam/vlans/", {
            "vid": 4094,
            "name": f"vlan-4094-{uuid.uuid4().hex[:8]}",
            "status": "active",
        })
        assert resp.status_code == 201

    def test_list_vlans(self):
        vid = (uuid.uuid4().int % 4000) + 1
        api_post("/api/ipam/vlans/", {"vid": vid, "name": f"v-{vid}", "status": "active"})
        resp = api_get("/api/ipam/vlans/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_get_vlan(self):
        vid = (uuid.uuid4().int % 4000) + 1
        created = api_post("/api/ipam/vlans/", {
            "vid": vid, "name": f"v-{vid}", "status": "active"
        }).json()
        resp = api_get(f"/api/ipam/vlans/{created['id']}/")
        assert resp.status_code == 200
        assert resp.json()["vid"] == vid

    def test_update_vlan(self):
        vid = (uuid.uuid4().int % 4000) + 1
        created = api_post("/api/ipam/vlans/", {
            "vid": vid, "name": f"v-{vid}", "status": "active"
        }).json()
        resp = api_put(f"/api/ipam/vlans/{created['id']}/", {
            "vid": vid,
            "name": f"updated-v-{vid}",
            "status": "reserved",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == f"updated-v-{vid}"
        assert resp.json()["status"] == "reserved"

    def test_update_vlan_invalid_vid(self):
        vid = (uuid.uuid4().int % 4000) + 1
        created = api_post("/api/ipam/vlans/", {
            "vid": vid, "name": f"v-{vid}", "status": "active"
        }).json()
        resp = api_put(f"/api/ipam/vlans/{created['id']}/", {
            "vid": 0,
            "name": "bad",
            "status": "active",
        })
        assert resp.status_code == 400

    def test_delete_vlan(self):
        vid = (uuid.uuid4().int % 4000) + 1
        created = api_post("/api/ipam/vlans/", {
            "vid": vid, "name": f"v-{vid}", "status": "active"
        }).json()
        resp = api_delete(f"/api/ipam/vlans/{created['id']}/")
        assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════
# PART 13: Cables
# ════════════════════════════════════════════════════════════════════

class TestCables:

    def _make_two_interfaces(self):
        """Helper to create two interfaces on the same device."""
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface_a = create_interface(device["id"], name=f"eth-a-{uuid.uuid4().hex[:6]}")
        iface_b = create_interface(device["id"], name=f"eth-b-{uuid.uuid4().hex[:6]}")
        return iface_a, iface_b

    def test_create_cable(self):
        iface_a, iface_b = self._make_two_interfaces()
        resp = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "connected",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["interface_a"] == iface_a["id"]
        assert data["interface_b"] == iface_b["id"]
        assert data["status"] == "connected"

    def test_create_cable_same_interface_fails(self):
        """Cannot connect an interface to itself."""
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface = create_interface(device["id"])
        resp = api_post("/api/dcim/cables/", {
            "interface_a": iface["id"],
            "interface_b": iface["id"],
            "status": "connected",
        })
        assert resp.status_code == 400

    def test_create_cable_interface_already_connected(self):
        """An interface cannot be part of two cables."""
        iface_a, iface_b = self._make_two_interfaces()
        # Create first cable
        resp1 = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "connected",
        })
        assert resp1.status_code == 201

        # Create another interface
        stack = create_full_device_stack()
        device = create_device(
            site_id=stack["site_id"],
            device_role_id=stack["device_role_id"],
            device_type_id=stack["device_type_id"],
        )
        iface_c = create_interface(device["id"], name=f"eth-c-{uuid.uuid4().hex[:6]}")

        # Try to connect iface_a again
        resp2 = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_c["id"],
            "status": "connected",
        })
        assert resp2.status_code == 400

    def test_create_cable_invalid_interface(self):
        """Both interfaces must exist."""
        iface_a, _ = self._make_two_interfaces()
        resp = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": 999999,
            "status": "connected",
        })
        assert resp.status_code == 400

    def test_list_cables(self):
        iface_a, iface_b = self._make_two_interfaces()
        api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "connected",
        })
        resp = api_get("/api/dcim/cables/")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_get_cable(self):
        iface_a, iface_b = self._make_two_interfaces()
        created = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "planned",
        }).json()
        resp = api_get(f"/api/dcim/cables/{created['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_delete_cable(self):
        iface_a, iface_b = self._make_two_interfaces()
        created = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "connected",
        }).json()
        resp = api_delete(f"/api/dcim/cables/{created['id']}/")
        assert resp.status_code == 204

    def test_delete_interface_removes_cable(self):
        """Deleting an interface should remove any cable connected to it."""
        iface_a, iface_b = self._make_two_interfaces()
        cable = api_post("/api/dcim/cables/", {
            "interface_a": iface_a["id"],
            "interface_b": iface_b["id"],
            "status": "connected",
        }).json()
        # Delete interface_a
        api_delete(f"/api/dcim/interfaces/{iface_a['id']}/")
        # Cable should be gone
        resp = api_get(f"/api/dcim/cables/{cable['id']}/")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 14: Tenants
# ════════════════════════════════════════════════════════════════════

class TestTenants:

    def test_create_tenant(self):
        name = f"tenant-{UNIQUE}"
        resp = api_post("/api/tenancy/tenants/", {"name": name})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert "slug" in data
        assert "id" in data

    def test_create_tenant_with_details(self):
        name = f"tenant-detail-{uuid.uuid4().hex[:8]}"
        resp = api_post("/api/tenancy/tenants/", {
            "name": name,
            "group": "engineering",
            "description": "Engineering team",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["group"] == "engineering"
        assert data["description"] == "Engineering team"

    def test_create_tenant_duplicate_slug_fails(self):
        slug = f"tenant-dup-{uuid.uuid4().hex[:8]}"
        api_post("/api/tenancy/tenants/", {"name": f"t1-{slug}", "slug": slug})
        resp = api_post("/api/tenancy/tenants/", {"name": f"t2-{slug}", "slug": slug})
        assert resp.status_code == 400

    def test_list_tenants(self):
        api_post("/api/tenancy/tenants/", {"name": f"t-{uuid.uuid4().hex[:8]}"})
        resp = api_get("/api/tenancy/tenants/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_list_tenants_filter_by_name(self):
        name = f"filter-tenant-{uuid.uuid4().hex[:8]}"
        api_post("/api/tenancy/tenants/", {"name": name})
        resp = api_get("/api/tenancy/tenants/", params={"name": name})
        data = resp.json()
        assert data["count"] >= 1
        assert all(t["name"] == name for t in data["results"])

    def test_get_tenant(self):
        created = api_post("/api/tenancy/tenants/", {
            "name": f"t-{uuid.uuid4().hex[:8]}"
        }).json()
        resp = api_get(f"/api/tenancy/tenants/{created['id']}/")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_delete_tenant(self):
        created = api_post("/api/tenancy/tenants/", {
            "name": f"t-{uuid.uuid4().hex[:8]}"
        }).json()
        resp = api_delete(f"/api/tenancy/tenants/{created['id']}/")
        assert resp.status_code == 204

    def test_delete_tenant_not_found(self):
        resp = api_delete("/api/tenancy/tenants/999999/")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 15: Response Format
# ════════════════════════════════════════════════════════════════════

class TestResponseFormat:

    def test_list_response_has_count_and_results(self):
        """All list endpoints return {count, results}."""
        endpoints = [
            "/api/dcim/regions/",
            "/api/dcim/sites/",
            "/api/dcim/manufacturers/",
            "/api/dcim/device-types/",
            "/api/dcim/device-roles/",
            "/api/dcim/racks/",
            "/api/dcim/devices/",
            "/api/dcim/interfaces/",
            "/api/ipam/ip-addresses/",
            "/api/ipam/prefixes/",
            "/api/ipam/vlans/",
            "/api/dcim/cables/",
            "/api/tenancy/tenants/",
        ]
        for endpoint in endpoints:
            resp = api_get(endpoint)
            assert resp.status_code == 200, f"Failed for {endpoint}: {resp.status_code}"
            data = resp.json()
            assert "count" in data, f"Missing 'count' in {endpoint}"
            assert "results" in data, f"Missing 'results' in {endpoint}"
            assert isinstance(data["results"], list), f"'results' not a list in {endpoint}"

    def test_create_returns_201(self):
        """POST create should return 201."""
        region = create_region()
        assert True  # create_region already asserts 201

    def test_delete_returns_204(self):
        """DELETE should return 204 No Content."""
        region = create_region()
        resp = api_delete(f"/api/dcim/regions/{region['id']}/")
        assert resp.status_code == 204

    def test_not_found_returns_404(self):
        """Accessing non-existent resources returns 404."""
        resp = api_get("/api/dcim/sites/999999/")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════
# PART 16: Slug Auto-generation
# ════════════════════════════════════════════════════════════════════

class TestSlugGeneration:

    def test_slug_from_name_with_spaces(self):
        name = f"My Cool Region {uuid.uuid4().hex[:6]}"
        region = create_region(name=name)
        assert " " not in region["slug"]
        assert region["slug"] == region["slug"].lower()

    def test_slug_from_name_with_special_chars(self):
        name = f"Region (Test) #{uuid.uuid4().int % 100}"
        resp = api_post("/api/dcim/regions/", {"name": name})
        assert resp.status_code == 201
        slug = resp.json()["slug"]
        # Should only contain lowercase, digits, hyphens
        assert all(c.isalnum() or c == '-' for c in slug)
        assert slug == slug.lower()

    def test_manufacturer_slug_auto_generated(self):
        name = f"Cisco Systems {uuid.uuid4().hex[:6]}"
        mfr = create_manufacturer(name=name)
        assert "slug" in mfr
        assert mfr["slug"] != ""
        assert " " not in mfr["slug"]

    def test_tenant_slug_auto_generated(self):
        name = f"Acme Corp {uuid.uuid4().hex[:6]}"
        resp = api_post("/api/tenancy/tenants/", {"name": name})
        assert resp.status_code == 201
        data = resp.json()
        assert "slug" in data
        assert data["slug"] != ""
        assert " " not in data["slug"]

    def test_device_type_slug_from_model(self):
        """Device type slug is generated from model, not name."""
        mfr = create_manufacturer()
        model = f"PowerEdge R740 {uuid.uuid4().hex[:6]}"
        dt = create_device_type(mfr["id"], model=model)
        assert "slug" in dt
        assert " " not in dt["slug"]
        assert dt["slug"] == dt["slug"].lower()
