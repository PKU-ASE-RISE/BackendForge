import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_ref_probe"
CUSTOMER_KEY = f"customer_direct_ref_probe_{uuid.uuid4().hex}"


def headers(key):
    return {"X-API-Key": key, "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def test_staff_only_configuration_reads_reject_customer_tokens():
    channel_slug = unique("staff-read-ch-")
    channel = requests.post(
        f"{BASE_URL}/channels",
        json={
            "slug": channel_slug,
            "name": "Staff Read Channel",
            "currencyCode": "USD",
            "isActive": True,
        },
        headers=headers(STAFF_KEY),
        timeout=30,
    )
    assert channel.status_code == 201

    warehouse = requests.post(
        f"{BASE_URL}/warehouses",
        json={
            "name": "Staff Read Warehouse",
            "slug": unique("staff-read-wh-"),
            "address": {
                "street": "1 Admin Way",
                "city": "New York",
                "postalCode": "10001",
                "country": "US",
            },
        },
        headers=headers(STAFF_KEY),
        timeout=30,
    )
    assert warehouse.status_code == 201
    warehouse_id = warehouse.json()["id"]

    product_type = requests.post(
        f"{BASE_URL}/product-types",
        json={
            "name": unique("staff-read-ptype-"),
            "slug": unique("staff-read-ptype-"),
            "productAttributes": [],
            "variantAttributes": [],
            "isDigital": False,
        },
        headers=headers(STAFF_KEY),
        timeout=30,
    )
    assert product_type.status_code == 201
    product_type_id = product_type.json()["id"]

    customer_headers = headers(CUSTOMER_KEY)
    protected_reads = [
        "/channels",
        f"/channels/{channel_slug}",
        "/warehouses",
        f"/warehouses/{warehouse_id}",
        "/product-types",
        f"/product-types/{product_type_id}",
    ]
    for path in protected_reads:
        response = requests.get(f"{BASE_URL}{path}", headers=customer_headers, timeout=30)
        assert response.status_code == 403, f"{path} should be staff-only"
