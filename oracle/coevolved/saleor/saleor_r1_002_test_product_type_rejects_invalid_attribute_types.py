import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
STAFF_KEY = "staff_direct_reference_prober"


def staff_headers():
    return {"X-API-Key": STAFF_KEY, "Content-Type": "application/json"}


def unique_slug(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


@pytest.mark.parametrize("attribute_field", ["productAttributes", "variantAttributes"])
def test_product_type_rejects_invalid_attribute_types(attribute_field):
    slug = unique_slug(f"pt-invalid-{attribute_field}-")
    payload = {
        "name": f"Invalid Attribute Type {uuid.uuid4().hex}",
        "slug": slug,
        "productAttributes": [],
        "variantAttributes": [],
        "isDigital": False,
    }
    payload[attribute_field] = [{"name": "Unsupported", "type": "currency"}]

    response = requests.post(
        f"{BASE_URL}/product-types",
        json=payload,
        headers=staff_headers(),
        timeout=30,
    )

    assert response.status_code == 400, response.text

    list_response = requests.get(
        f"{BASE_URL}/product-types",
        headers=staff_headers(),
        timeout=30,
    )
    assert list_response.status_code == 200
    created_slugs = {item.get("slug") for item in list_response.json()["data"]}
    assert slug not in created_slugs
