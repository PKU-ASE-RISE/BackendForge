import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def test_warehouse_rejects_non_array_shipping_zones():
    slug = f"wh-invalid-zones-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/warehouses",
        json={
            "name": "Invalid Shipping Zones Warehouse",
            "slug": slug,
            "address": {
                "street": "100 Commerce Dr",
                "city": "New York",
                "postalCode": "10001",
                "country": "US",
            },
            "shippingZones": "not-a-list",
        },
        headers=staff_headers(),
        timeout=30,
    )

    assert response.status_code == 400, response.text

    list_response = requests.get(
        f"{BASE_URL}/warehouses",
        headers=staff_headers(),
        timeout=30,
    )
    assert list_response.status_code == 200
    created_slugs = {item.get("slug") for item in list_response.json()["data"]}
    assert slug not in created_slugs
