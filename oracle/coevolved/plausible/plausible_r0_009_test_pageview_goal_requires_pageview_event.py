import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def api(method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["X-API-Key"] = API_KEY
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def create_site():
    domain = f"drp-{uuid.uuid4().hex}.example.com"
    response = api("POST", "/api/sites", json={"domain": domain, "timezone": "UTC"})
    assert response.status_code == 201, response.text
    return response.json()


def test_pageview_goal_requires_pageview_event():
    site = create_site()
    goal_path = f"/thank-you-{uuid.uuid4().hex}"
    created_goal = api(
        "POST",
        f"/api/sites/{site['id']}/goals",
        json={"goalType": "pageview", "pagePath": goal_path},
    )
    assert created_goal.status_code == 201, created_goal.text
    goal = created_goal.json()

    day = "2024-01-15"
    custom_only = requests.post(
        f"{BASE_URL}/api/event",
        json={
            "domain": site["domain"],
            "name": "Purchase",
            "url": goal_path,
            "userAgent": f"GoalUA-{uuid.uuid4().hex}",
            "country": "US",
            "timestamp": f"{day}T12:00:00+00:00",
        },
    )
    assert custom_only.status_code == 202, custom_only.text

    conversions = api(
        "GET",
        f"/api/sites/{site['id']}/goals/conversions",
        params={"period": "custom", "dateFrom": day, "dateTo": day},
    )
    assert conversions.status_code == 200, conversions.text
    conversion_by_goal = {item["goalId"]: item for item in conversions.json()}
    assert conversion_by_goal[goal["id"]]["visitors"] == 0
    assert conversion_by_goal[goal["id"]]["conversionRate"] == 0
