import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def unique_slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def test_warehouse_update_rejects_non_array_shipping_zones():
    created = requests.post(
        f"{BASE_URL}/warehouses",
        json={
            "name": "Warehouse Shipping Zones Probe",
            "slug": unique_slug("drp-wh-zones"),
            "address": {
                "street": "100 Commerce Dr",
                "city": "New York",
                "postalCode": "10001",
                "country": "US",
            },
            "shippingZones": [],
        },
        headers=staff_headers(),
        timeout=30,
    )
    assert created.status_code == 201
    warehouse_id = created.json()["id"]

    updated = requests.put(
        f"{BASE_URL}/warehouses/{warehouse_id}",
        json={"shippingZones": "not-an-array"},
        headers=staff_headers(),
        timeout=30,
    )
    assert updated.status_code == 400
    assert "error" in updated.json()

    reloaded = requests.get(
        f"{BASE_URL}/warehouses/{warehouse_id}",
        headers=staff_headers(),
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["shippingZones"] == []
