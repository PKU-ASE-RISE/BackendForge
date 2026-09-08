import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30
HEADERS = {"X-Api-Key": "test-api-key-inventree", "Content-Type": "application/json"}


def api_get(path):
    return requests.get(
        f"{BASE_URL}{path}",
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path, payload):
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path, payload):
    return requests.put(
        f"{BASE_URL}{path}",
        json=payload,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )


def test_part_update_preserves_template_invariant_for_existing_variants():
    token = uuid.uuid4().hex
    template_resp = api_post("/api/parts", {"name": f"TemplateWithVariant-{token}", "is_template": True})
    assert template_resp.status_code == 201
    template = template_resp.json()

    variant_resp = api_post("/api/parts", {"name": f"VariantOfTemplate-{token}", "variant_of": template["id"]})
    assert variant_resp.status_code == 201
    variant = variant_resp.json()
    assert variant["variant_of"] == template["id"]

    demote = api_put(
        f"/api/parts/{template['id']}",
        {
            "name": template["name"],
            "is_template": False,
        },
    )
    assert demote.status_code == 400
    assert "error" in demote.json()

    reloaded_template = api_get(f"/api/parts/{template['id']}")
    assert reloaded_template.status_code == 200
    assert reloaded_template.json()["is_template"] is True

    reloaded_variant = api_get(f"/api/parts/{variant['id']}")
    assert reloaded_variant.status_code == 200
    assert reloaded_variant.json()["variant_of"] == template["id"]
