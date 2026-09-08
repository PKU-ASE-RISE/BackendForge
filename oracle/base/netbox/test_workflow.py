"""
NetBox — L3 Workflow Tests (Adversarial)

Multi-step workflows crossing 3+ entity types.
Targets: rack utilization, IP/prefix containment, cables, cascade constraints.

"""

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

HEADERS = {
    "X-Api-Key": "test-key-workflow",
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


class TestDatacenterBuildout:
    """Pattern 2+5+7: Build complete datacenter, verify utilization and constraints."""

    def test_full_rack_lifecycle(self):
        """
        Create site -> rack -> device types -> devices in rack
        -> verify utilization -> remove device -> utilization decreases
        -> try to delete rack with devices -> 400.
        """
        uid = unique()

        # Setup
        site = api_post("/api/dcim/sites/", {"name": f"DC-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"Dell-{uid}"}).json()
        dt_1u = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"R640-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        dt_2u = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"R740-{uid}", "u_height": 2, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"Server-{uid}", "color": "aa1409"}).json()

        rack = api_post("/api/dcim/racks/", {
            "name": f"A01-{uid}", "site": site["id"], "u_height": 42, "status": "active"
        }).json()
        assert rack["u_height"] == 42

        # Place devices
        dev1 = api_post("/api/dcim/devices/", {
            "name": f"srv01-{uid}", "device_type": dt_1u["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        }).json()
        dev2 = api_post("/api/dcim/devices/", {
            "name": f"srv02-{uid}", "device_type": dt_2u["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 2, "status": "active"
        }).json()

        # Utilization = floor((1+2)/42 * 100) = 7
        detail = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert detail["utilization"] == 7

        # Delete dev1
        api_delete(f"/api/dcim/devices/{dev1['id']}/")
        # Utilization = floor(2/42 * 100) = 4
        detail2 = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert detail2["utilization"] == 4

        # Cannot delete rack while dev2 is still in it
        r = api_delete(f"/api/dcim/racks/{rack['id']}/")
        assert r.status_code == 400

        # Remove dev2, now can delete rack
        api_delete(f"/api/dcim/devices/{dev2['id']}/")
        r = api_delete(f"/api/dcim/racks/{rack['id']}/")
        assert r.status_code == 204


class TestCablingWorkflow:
    """Pattern 7+8: Cable lifecycle with interface constraints."""

    def test_cable_lifecycle_and_constraints(self):
        """
        Create devices + interfaces -> cable them -> verify cable fields
        -> try to cable already-connected interface -> 400
        -> delete cable -> interfaces free -> re-cable works.
        """
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"CblSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"CblMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"Switch-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"NetRole-{uid}", "color": "bb2200"}).json()

        sw1 = api_post("/api/dcim/devices/", {
            "name": f"sw1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        sw2 = api_post("/api/dcim/devices/", {
            "name": f"sw2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()

        i1 = api_post("/api/dcim/interfaces/", {"name": "ge-0/0/0", "device": sw1["id"], "type": "1000base-t"}).json()
        i2 = api_post("/api/dcim/interfaces/", {"name": "ge-0/0/0", "device": sw2["id"], "type": "1000base-t"}).json()
        i3 = api_post("/api/dcim/interfaces/", {"name": "ge-0/0/1", "device": sw1["id"], "type": "1000base-t"}).json()

        # Cable i1 <-> i2
        cable = api_post("/api/dcim/cables/", {
            "interface_a": i1["id"], "interface_b": i2["id"], "status": "connected"
        }).json()
        assert cable["interface_a"] == i1["id"]
        assert cable["interface_b"] == i2["id"]
        assert cable["status"] == "connected"

        # Try to cable i1 again (already connected)
        r = api_post("/api/dcim/cables/", {
            "interface_a": i1["id"], "interface_b": i3["id"], "status": "connected"
        })
        assert r.status_code == 400

        # Delete cable -> interfaces freed
        api_delete(f"/api/dcim/cables/{cable['id']}/")

        # Now can cable i1 again
        r2 = api_post("/api/dcim/cables/", {
            "interface_a": i1["id"], "interface_b": i3["id"], "status": "connected"
        })
        assert r2.status_code == 201


class TestIPPrefixContainment:
    """Pattern 2+5: Prefix GET includes contained IP addresses."""

    def test_prefix_contains_ip_addresses(self):
        """
        Create prefix -> create IPs within and outside -> verify prefix detail
        only shows contained IPs.
        """
        uid = unique()
        # Use unique octets based on uid to avoid collision
        oct = int(uid[:2], 16) % 200 + 10

        prefix = api_post("/api/ipam/prefixes/", {
            "prefix": f"10.{oct}.0.0/24", "status": "active"
        }).json()

        # IPs within the prefix
        ip1 = api_post("/api/ipam/ip-addresses/", {
            "address": f"10.{oct}.0.1/24", "status": "active"
        }).json()
        ip2 = api_post("/api/ipam/ip-addresses/", {
            "address": f"10.{oct}.0.100/24", "status": "active"
        }).json()

        # IP outside the prefix
        api_post("/api/ipam/ip-addresses/", {
            "address": f"10.{oct + 1}.0.1/24", "status": "active"
        })

        # Get prefix detail — should include ip_addresses
        detail = api_get(f"/api/ipam/prefixes/{prefix['id']}/").json()
        assert "ip_addresses" in detail
        contained_ids = [ip["id"] for ip in detail["ip_addresses"]]
        assert ip1["id"] in contained_ids
        assert ip2["id"] in contained_ids
        assert len(detail["ip_addresses"]) == 2


class TestDeviceInterfaceCascade:
    """Pattern 7: Delete device cascades to interfaces and cables."""

    def test_device_delete_cascades_interfaces_and_cables(self):
        """
        Create 2 devices -> add interfaces -> cable them ->
        delete one device -> its interfaces AND attached cable gone.
        """
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"CascSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"CascMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"CascDT-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"CascRole-{uid}", "color": "cc3300"}).json()

        dev1 = api_post("/api/dcim/devices/", {
            "name": f"cd1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()
        dev2 = api_post("/api/dcim/devices/", {
            "name": f"cd2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "status": "active"
        }).json()

        i1 = api_post("/api/dcim/interfaces/", {"name": "eth0", "device": dev1["id"], "type": "1000base-t"}).json()
        i2 = api_post("/api/dcim/interfaces/", {"name": "eth0", "device": dev2["id"], "type": "1000base-t"}).json()

        cable = api_post("/api/dcim/cables/", {
            "interface_a": i1["id"], "interface_b": i2["id"], "status": "connected"
        }).json()

        # Delete dev1 — cascades to i1 and cable
        r = api_delete(f"/api/dcim/devices/{dev1['id']}/")
        assert r.status_code == 204

        assert api_get(f"/api/dcim/interfaces/{i1['id']}/").status_code == 404
        assert api_get(f"/api/dcim/cables/{cable['id']}/").status_code == 404

        # dev2's interface still exists (cable removed from that side)
        assert api_get(f"/api/dcim/interfaces/{i2['id']}/").status_code == 200


class TestSiteRegionTenantWorkflow:
    """Pattern 2+3: Sites with regions and tenants, filtering."""

    def test_site_region_tenant_lifecycle(self):
        """
        Create region -> tenant -> sites in region
        -> filter sites by region -> verify.
        """
        uid = unique()
        region = api_post("/api/dcim/regions/", {"name": f"US-West-{uid}"}).json()
        tenant = api_post("/api/tenancy/tenants/", {"name": f"Acme-{uid}"}).json()

        s1 = api_post("/api/dcim/sites/", {
            "name": f"SV-{uid}", "status": "active",
            "region": region["id"], "tenant": tenant["id"]
        }).json()
        s2 = api_post("/api/dcim/sites/", {
            "name": f"LA-{uid}", "status": "planned",
            "region": region["id"]
        }).json()
        s3 = api_post("/api/dcim/sites/", {
            "name": f"NY-{uid}", "status": "active"
        }).json()

        # Verify site fields
        assert s1["region"] == region["id"]
        assert s1["tenant"] == tenant["id"]
        assert s1["status"] == "active"

        # Filter by region
        r = api_get("/api/dcim/sites/", params={"region_id": region["id"]})
        assert r.status_code == 200
        results = r.json()["results"]
        site_ids = [s["id"] for s in results]
        assert s1["id"] in site_ids
        assert s2["id"] in site_ids
        assert s3["id"] not in site_ids


class TestRackSpaceNonOverlap:
    """Pattern 5+8: Complex rack placement scenario."""

    def test_rack_placement_then_move_device(self):
        """
        Place devices in rack -> update device to new position
        -> verify no overlap at new position -> old position freed.
        """
        uid = unique()
        site = api_post("/api/dcim/sites/", {"name": f"MvSite-{uid}", "status": "active"}).json()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"MvMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"MvDT-{uid}", "u_height": 2, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"MvRole-{uid}", "color": "dd4400"}).json()
        rack = api_post("/api/dcim/racks/", {
            "name": f"MvRack-{uid}", "site": site["id"], "u_height": 10, "status": "active"
        }).json()

        # Place dev1 at position 1-2
        dev1 = api_post("/api/dcim/devices/", {
            "name": f"mv1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        }).json()
        # Place dev2 at position 5-6
        dev2 = api_post("/api/dcim/devices/", {
            "name": f"mv2-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 5, "status": "active"
        }).json()

        # Move dev1 to position 3-4 (should succeed — no overlap)
        r = api_put(f"/api/dcim/devices/{dev1['id']}/", {
            "name": f"mv1-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 3, "status": "active"
        })
        assert r.status_code == 200
        assert r.json()["position"] == 3

        # Now position 1-2 is free; place new device there
        r2 = api_post("/api/dcim/devices/", {
            "name": f"mv3-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": site["id"], "rack": rack["id"], "position": 1, "status": "active"
        })
        assert r2.status_code == 201

        # Utilization = floor((2+2+2)/10 * 100) = 60
        rack_detail = api_get(f"/api/dcim/racks/{rack['id']}/").json()
        assert rack_detail["utilization"] == 60


class TestForeignKeyValidation:
    """Pattern 8: FK references must exist."""

    def test_device_invalid_site_rejected(self):
        uid = unique()
        mfr = api_post("/api/dcim/manufacturers/", {"name": f"FkMfr-{uid}"}).json()
        dt = api_post("/api/dcim/device-types/", {
            "manufacturer": mfr["id"], "model": f"FkDT-{uid}", "u_height": 1, "is_full_depth": True
        }).json()
        role = api_post("/api/dcim/device-roles/", {"name": f"FkRole-{uid}", "color": "ee5500"}).json()

        r = api_post("/api/dcim/devices/", {
            "name": f"FkDev-{uid}", "device_type": dt["id"], "device_role": role["id"],
            "site": 999999, "status": "active"
        })
        assert r.status_code == 400

    def test_rack_invalid_site_rejected(self):
        uid = unique()
        r = api_post("/api/dcim/racks/", {
            "name": f"FkRack-{uid}", "site": 999999, "u_height": 42, "status": "active"
        })
        assert r.status_code == 400
