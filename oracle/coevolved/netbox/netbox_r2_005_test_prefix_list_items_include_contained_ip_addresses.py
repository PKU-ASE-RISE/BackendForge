import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {"X-Api-Key": "direct-prober-r2", "Content-Type": "application/json"}


def api_get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def api_post(path, payload):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=HEADERS, timeout=30)


def unique_ipv4_triplet():
    raw = uuid.uuid4().hex
    return int(raw[:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def test_prefix_list_items_include_contained_ip_addresses():
    a, b, c = unique_ipv4_triplet()
    prefix_cidr = f"10.{a}.{b}.0/24"
    inside_address = f"10.{a}.{b}.{max(1, c)}/24"
    outside_address = f"10.{a}.{(b + 1) % 256}.{max(1, c)}/24"

    prefix = api_post("/api/ipam/prefixes/", {"prefix": prefix_cidr, "status": "active"})
    assert prefix.status_code == 201, prefix.text
    inside = api_post("/api/ipam/ip-addresses/", {"address": inside_address, "status": "active"})
    assert inside.status_code == 201, inside.text
    outside = api_post("/api/ipam/ip-addresses/", {"address": outside_address, "status": "active"})
    assert outside.status_code == 201, outside.text

    listed = api_get("/api/ipam/prefixes/", params={"status": "active"})
    assert listed.status_code == 200, listed.text
    item = next((row for row in listed.json()["results"] if row["id"] == prefix.json()["id"]), None)
    assert item is not None
    assert "ip_addresses" in item
    contained_ids = {ip["id"] for ip in item["ip_addresses"]}
    assert inside.json()["id"] in contained_ids
    assert outside.json()["id"] not in contained_ids
