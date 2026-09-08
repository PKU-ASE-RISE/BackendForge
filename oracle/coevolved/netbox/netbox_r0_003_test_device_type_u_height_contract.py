import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
HEADERS = {
    "X-Api-Key": "direct-reference-prober-device-type-height",
    "Content-Type": "application/json",
}


def api_get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def api_post(path, json_data):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def create_manufacturer():
    response = api_post("/api/dcim/manufacturers/", {"name": unique("mfr")})
    assert response.status_code == 201, response.text
    return response.json()


def assert_model_not_created(manufacturer_id, model):
    response = api_get("/api/dcim/device-types/", params={"manufacturer_id": manufacturer_id})
    assert response.status_code == 200, response.text
    assert all(item["model"] != model for item in response.json()["results"])


def test_device_type_rejects_zero_u_height():
    manufacturer = create_manufacturer()
    model = unique("zero-height-model")

    response = api_post(
        "/api/dcim/device-types/",
        {
            "manufacturer": manufacturer["id"],
            "model": model,
            "u_height": 0,
            "is_full_depth": True,
        },
    )

    assert response.status_code == 400, response.text
    assert_model_not_created(manufacturer["id"], model)


def test_device_type_rejects_missing_required_u_height():
    manufacturer = create_manufacturer()
    model = unique("missing-height-model")

    response = api_post(
        "/api/dcim/device-types/",
        {
            "manufacturer": manufacturer["id"],
            "model": model,
            "is_full_depth": True,
        },
    )

    assert response.status_code == 400, response.text
    assert_model_not_created(manufacturer["id"], model)
