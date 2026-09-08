import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10
ADMIN_KEY = "admin_opportunity_foreign_stage"


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def post(path, payload):
    response = request("post", f"{BASE_URL}{path}", headers=headers(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_opportunity_stage_update_rejects_foreign_stage():
    unique = uuid.uuid4().hex
    company = post(
        "/companies",
        {
            "name": f"Foreign Stage Co {unique[:8]}",
            "domain": f"foreign-stage-{unique[:8]}.example.com",
        },
    )
    pipeline_a = post(
        "/pipelines",
        {
            "name": f"Pipeline A {unique[:8]}",
            "stages": [{"name": "Open", "position": 0, "color": "#aaaaaa"}],
        },
    )
    pipeline_b = post(
        "/pipelines",
        {
            "name": f"Pipeline B {unique[:8]}",
            "stages": [{"name": "Won", "position": 0, "color": "#00aa00"}],
        },
    )

    original_stage_id = pipeline_a["stages"][0]["id"]
    foreign_won_stage_id = pipeline_b["stages"][0]["id"]
    opportunity = post(
        "/opportunities",
        {
            "name": f"Foreign Stage Deal {unique[:8]}",
            "amount": 43210,
            "companyId": company["id"],
            "pipelineId": pipeline_a["id"],
            "stageId": original_stage_id,
            "probability": 25,
            "closeDate": "2027-05-01",
        },
    )

    update = request(
        "patch",
        f"{BASE_URL}/opportunities/{opportunity['id']}",
        headers=headers(),
        json={"stageId": foreign_won_stage_id},
    )
    assert update.status_code == 400, update.text

    reloaded_opp = request("get", f"{BASE_URL}/opportunities/{opportunity['id']}", headers=headers())
    assert reloaded_opp.status_code == 200, reloaded_opp.text
    assert reloaded_opp.json()["stageId"] == original_stage_id
    assert reloaded_opp.json()["closedAt"] is None

    reloaded_company = request("get", f"{BASE_URL}/companies/{company['id']}", headers=headers())
    assert reloaded_company.status_code == 200, reloaded_company.text
    assert reloaded_company.json()["totalRevenue"] == 0
