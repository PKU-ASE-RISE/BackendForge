import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = API_KEY
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_timeseries_month_interval_handles_month_end_custom_range():
    domain = f"month-end-{uuid.uuid4().hex}.example"
    site_resp = api("POST", "/api/sites", json={"domain": domain})
    assert site_resp.status_code == 201, site_resp.text
    site = site_resp.json()

    resp = api(
        "GET",
        f"/api/sites/{site['id']}/stats/timeseries",
        params={
            "period": "custom",
            "dateFrom": "2026-01-31",
            "dateTo": "2026-03-31",
            "interval": "month",
        },
    )

    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)
