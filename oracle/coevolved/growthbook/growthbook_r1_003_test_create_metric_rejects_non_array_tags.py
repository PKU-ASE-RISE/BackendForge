import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-Api-Key": f"probe-org-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def api(method, path, headers, json=None, params=None):
    return getattr(requests, method)(
        f"{BASE_URL}{path}",
        headers=headers,
        json=json,
        params=params,
        timeout=30,
    )


def test_create_metric_rejects_non_array_tags():
    headers = make_headers()
    metric_name = f"metric-tags-{uuid.uuid4().hex[:10]}"

    response = api(
        "post",
        "/api/metrics",
        headers,
        json={"name": metric_name, "type": "count", "tags": "not-a-list"},
    )
    assert response.status_code == 400, response.text

    metrics = api("get", "/api/metrics", headers)
    assert metrics.status_code == 200
    assert metric_name not in {metric["name"] for metric in metrics.json()["metrics"]}
