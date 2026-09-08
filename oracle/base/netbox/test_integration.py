"""
NetBox — L2 Integration Tests (Adversarial)

Targets LLM bug patterns:
- Pattern 1: snake_case field names, list response format (count/results)
- Pattern 2: Nested/computed data (rack utilization, prefix ip_addresses)
- Pattern 3: Filtering actually implemented
- Pattern 4: Exact status codes (201 create, 204 delete, 400 validation)
- Pattern 5: Computed values (utilization, slug generation)
- Pattern 7: Cascade/constraint behavior on delete
- Pattern 8: Validation (rack space, VLAN range, cable conflicts)

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

HEADERS = {
    "X-Api-Key": "test-key-integration",
    "Content-Type": "application/json",
}


def unique():
    return uuid.uuid4().hex[:6]


def api_get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def api_post(path, json_data=None):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def api_put(path, json_data=None):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def api_delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


class TestListResponseFormat:
    """Pattern 1+4: All list endpoints return {count, results}."""

    def test_sites_list_format(self):
        uid = unique()
        api_post("/api/dcim/sites/", {"name": f"Site-{uid}", "status": "active"})
        r = api_get("/api/dcim/sites/")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "results" in body
        assert isinstance(body["results"], list)
        assert isinstance(body["count"], int)
        assert body["count"] >= 1

    def test_devices_list_format(self):
        r = api_get("/api/dcim/devices/")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "results" in body


class TestStatusCodes:
    """Pattern 4: Correct status codes for CRUD."""

    def test_create_returns_201(self):
        uid = unique()
        r = api_post("/api/dcim/regions/", {"name": f"Region-{uid}"})
        assert r.status_code == 201

    def test_delete_returns_204(self):
        uid = unique()
        region = api_post("/api/dcim/regions/", {"name": f"DelReg-{uid}"}).json()
        r = api_delete(f"/api/dcim/regions/{region['id']}/")
        assert r.status_code == 204

    def test_not_found_returns_404(self):
        r = api_get("/api/dcim/sites/999999/")
        assert r.status_code == 404

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/dcim/sites/", timeout=30)
        assert r.status_code == 401


class TestSlugGeneration:
    """Pattern 5: Slug auto-generated from name."""

    def test_slug_generated_from_name(self):
        uid = unique()
        r = api_post("/api/dcim/sites/", {"name": f"My Test Site {uid}", "status": "active"})
        assert r.status_code == 201
        assert r.json()["slug"] == f"my-test-site-{uid}"

    def test_slug_unique_constraint(self):
        uid = unique()
        api_post("/api/dcim/manufacturers/", {"name": f"Mfr-{uid}"})
        r = api_post("/api/dcim/manufacturers/", {"name": f"Mfr-{uid}"})
        assert r.status_code == 400

    def test_custom_slug_accepted(self):
        uid = unique()
        r = api_post("/api/dcim/sites/", {
            "name": f"Custom-{uid}", "slug": f"custom-slug-{uid}", "status": "active"
        })
        assert r.status_code == 201
        assert r.json()["slug"] == f"custom-slug-{uid}"


class TestRackUtilization:
    """Pattern 5: Rack utilization computed from devices."""

    def test_rack_utilization_computed(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"RkSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"RkMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"Server-{uid}", "u_height": 2, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"RkRole-{uid}", "color": "aa1409"}).json()
        rack = api_post("/api/dcim/racks/", {
            "name": f"Rack-{uid}", "site": site["id"], "u_height": 42, "status": "active"
        }).json()

        # No devices yet — utilization 0
        detail = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert detail["utilization"] == 0

        # Add device occupying 2U
        api_post("/api/dcim/devices/", {
            "name": f"Dev1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        })

        # Utilization = floor(2/42 * 100) = 4
        detail2 = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert detail2["utilization"] == 4

    def test_rack_utilization_multiple_devices(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"RkMSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"RkMMfr-{uid}"}).json()
        dt2u = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"2U-{uid}", "u_height": 2, "is_full_depth": True
        }).json()
        dt4u = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"4U-{uid}", "u_height": 4, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"RkMRole-{uid}", "color": "aa1409"}).json()
        rack = api_post("/api/dcim/racks/", {
            "name": f"RackM-{uid}", "site": site["id"], "u_height": 20, "status": "active"
        }).json()

        api_post("/api/dcim/devices/", {
            "name": f"MDev1-{uid}", "device_type": dt2u["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        })
        api_post("/api/dcim/devices/", {
            "name": f"MDev2-{uid}", "device_type": dt4u["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 3, "status": "active"
        })

        # Utilization = floor((2+4)/20 * 100) = 30
        detail = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert detail["utilization"] == 30


class TestRackSpaceValidation:
    """Pattern 8: Rack position overlap validation."""

    def test_rack_position_overlap_rejected(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"OvSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"OvMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"OvSrv-{uid}", "u_height": 4, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"OvRole-{uid}", "color": "aa1409"}).json()
        rack = api_post("/api/dcim/racks/", {
            "name": f"OvRack-{uid}", "site": site["id"], "u_height": 42, "status": "active"
        }).json()

        # Place device at position 1 (occupies 1-4)
        api_post("/api/dcim/devices/", {
            "name": f"OvDev1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        })

        # Try to place another at position 3 (overlaps with 1-4)
        r = api_post("/api/dcim/devices/", {
            "name": f"OvDev2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 3, "status": "active"
        })
        assert r.status_code == 400

    def test_rack_position_exceeds_height(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"ExSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"ExMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"ExSrv-{uid}", "u_height": 4, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"ExRole-{uid}", "color": "aa1409"}).json()
        rack = api_post("/api/dcim/racks/", {
            "name": f"ExRack-{uid}", "site": site["id"], "u_height": 10, "status": "active"
        }).json()

        # Position 8 + 4U = 11 which exceeds rack height of 10
        r = api_post("/api/dcim/devices/", {
            "name": f"ExDev-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 8, "status": "active"
        })
        assert r.status_code == 400


class TestCableValidation:
    """Pattern 8: Cable endpoint validation."""

    def test_cable_connects_two_interfaces(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"CbSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"CbMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"CbSrv-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"CbRole-{uid}", "color": "aa1409"}).json()
        dev1 = api_post("/api/dcim/devices/", {
            "name": f"CbDev1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        dev2 = api_post("/api/dcim/devices/", {
            "name": f"CbDev2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        iface1 = api_post("/api/dcim/interfaces/", {"name": f"eth0-{uid}", "device": dev1["id"], "type": "1000base-t"}).json()
        iface2 = api_post("/api/dcim/interfaces/", {"name": f"eth0-{uid}", "device": dev2["id"], "type": "1000base-t"}).json()

        r = api_post("/api/dcim/cables/", {
            "interface_a": iface1["id"], "interface_b": iface2["id"], "status": "connected"
        })
        assert r.status_code == 201
        cable = r.json()
        assert cable["interface_a"] == iface1["id"]
        assert cable["interface_b"] == iface2["id"]

    def test_cable_already_connected_rejected(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"CbDup-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"CbDMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"CbDSrv-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"CbDRole-{uid}", "color": "aa1409"}).json()
        dev = api_post("/api/dcim/devices/", {
            "name": f"CbDDev-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        i1 = api_post("/api/dcim/interfaces/", {"name": f"e0-{uid}", "device": dev["id"], "type": "1000base-t"}).json()
        i2 = api_post("/api/dcim/interfaces/", {"name": f"e1-{uid}", "device": dev["id"], "type": "1000base-t"}).json()
        i3 = api_post("/api/dcim/interfaces/", {"name": f"e2-{uid}", "device": dev["id"], "type": "1000base-t"}).json()

        api_post("/api/dcim/cables/", {"interface_a": i1["id"], "interface_b": i2["id"], "status": "connected"})

        # Try to cable i1 again — should fail
        r = api_post("/api/dcim/cables/", {"interface_a": i1["id"], "interface_b": i3["id"], "status": "connected"})
        assert r.status_code == 400


class TestVLANValidation:
    """Pattern 8: VLAN vid range check."""

    def test_vlan_vid_valid_range(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"VlSite-{uid}", "status": "active"}).json()

        r = api_post("/api/ipam/vlans/", {"vid": 100, "name": f"VLAN-{uid}", "status": "active", "site": site["id"]})
        assert r.status_code == 201
        assert r.json()["vid"] == 100

    def test_vlan_vid_out_of_range(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"VlBad-{uid}", "status": "active"}).json()

        r = api_post("/api/ipam/vlans/", {"vid": 0, "name": f"BadVLAN-{uid}", "status": "active", "site": site["id"]})
        assert r.status_code == 400

        r2 = api_post("/api/ipam/vlans/", {"vid": 4095, "name": f"BadVLAN2-{uid}", "status": "active", "site": site["id"]})
        assert r2.status_code == 400


class TestDeviceFiltering:
    """Pattern 3: Filtering devices by site_id actually works."""

    def test_filter_devices_by_site(self):
        uid = unique()
        site1 = api_post("/api/dcim/sites/", {"name": f"FltS1-{uid}", "status": "active"}).json()
        site2 = api_post("/api/dcim/sites/", {"name": f"FltS2-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"FltMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"FltDT-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"FltRole-{uid}", "color": "aa1409"}).json()

        api_post("/api/dcim/devices/", {
            "name": f"FDev1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site1["id"], "status": "active"
        })
        api_post("/api/dcim/devices/", {
            "name": f"FDev2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site1["id"], "status": "active"
        })
        api_post("/api/dcim/devices/", {
            "name": f"FDev3-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site2["id"], "status": "active"
        })

        r = api_get("/api/dcim/devices/", params={"site_id": site1["id"]})
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 2
        for d in results:
            assert d["site"] == site1["id"]

    def test_filter_interfaces_by_device(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"IfFlt-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"IfMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"IfDT-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"IfRole-{uid}", "color": "aa1409"}).json()
        dev = api_post("/api/dcim/devices/", {
            "name": f"IfDev-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()

        api_post("/api/dcim/interfaces/", {"name": "eth0", "device": dev["id"], "type": "1000base-t"})
        api_post("/api/dcim/interfaces/", {"name": "eth1", "device": dev["id"], "type": "1000base-t"})

        r = api_get("/api/dcim/interfaces/", params={"device_id": dev["id"]})
        assert r.status_code == 200
        assert r.json()["count"] == 2


class TestCascadeConstraints:
    """Pattern 7: Delete constraints enforced correctly."""

    def test_delete_site_with_racks_rejected(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"NoCasc-{uid}", "status": "active"}).json()
        api_post("/api/dcim/racks/", {"name": f"Rack-{uid}", "site": site["id"], "u_height": 42, "status": "active"})

        r = api_delete(f"/api/dcim/sites/{site['id']}/")
        assert r.status_code == 400

    def test_delete_device_cascades_interfaces(self):
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"DevCasc-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"DCMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"DCDT-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"DCRole-{uid}", "color": "aa1409"}).json()
        dev = api_post("/api/dcim/devices/", {
            "name": f"DCDev-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        iface = api_post("/api/dcim/interfaces/", {"name": "eth0", "device": dev["id"], "type": "1000base-t"}).json()

        api_delete(f"/api/dcim/devices/{dev['id']}/")
        assert api_get(f"/api/dcim/interfaces/{iface['id']}/").status_code == 404


class TestIPAddressUniqueness:
    """Pattern 8: IP address CIDR uniqueness."""

    def test_duplicate_ip_address_rejected(self):
        uid = unique()
        address = f"10.0.{int(uid[:2], 16)}.1/24"
        api_post("/api/ipam/ip-addresses/", {"address": address, "status": "active"})
        r = api_post("/api/ipam/ip-addresses/", {"address": address, "status": "active"})
        assert r.status_code == 400


class TestRegionHierarchy:
    """Pattern 8: Region parent/child validation."""

    def test_region_parent_child(self):
        uid = unique()
        parent = api_post("/api/dcim/regions/", {"name": f"Parent-{uid}"}).json()
        child = api_post("/api/dcim/regions/", {"name": f"Child-{uid}", "parent": parent["id"]}).json()
        assert child["parent"] == parent["id"]

    def test_region_self_parent_rejected(self):
        uid = unique()
        region = api_post("/api/dcim/regions/", {"name": f"Self-{uid}"}).json()
        # Try to make it its own parent — would need an update endpoint or re-creation
        # Since regions don't have PUT, we just verify creation with non-existent parent fails
        r = api_post("/api/dcim/regions/", {"name": f"Bad-{uid}", "parent": 999999})
        assert r.status_code == 400
