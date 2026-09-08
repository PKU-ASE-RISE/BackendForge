import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def test_opportunity_records_are_workspace_scoped():
    unique = uuid.uuid4().hex
    workspace_a = f"admin_opportunity_a_{unique}"
    workspace_b = f"admin_opportunity_b_{unique}"

    pipeline_resp = request(
        "post",
        f"{BASE_URL}/pipelines",
        headers=headers(workspace_a),
        json={
            "name": f"ScopedPipeline-{unique}",
            "stages": [
                {"name": "Open", "position": 0, "color": "#999999"},
                {"name": "Won", "position": 1, "color": "#00aa00"},
            ],
        },
    )
    assert pipeline_resp.status_code == 201
    pipeline = pipeline_resp.json()
    stage_id = pipeline["stages"][0]["id"]

    company_resp = request(
        "post",
        f"{BASE_URL}/companies",
        headers=headers(workspace_a),
        json={"name": f"OppCompany-{unique}"},
    )
    assert company_resp.status_code == 201

    opportunity_resp = request(
        "post",
        f"{BASE_URL}/opportunities",
        headers=headers(workspace_a),
        json={
            "name": f"ScopedOpportunity-{unique}",
            "amount": 12345,
            "pipelineId": pipeline["id"],
            "stageId": stage_id,
            "companyId": company_resp.json()["id"],
            "probability": 35,
            "closeDate": "2027-05-01",
        },
    )
    assert opportunity_resp.status_code == 201
    opportunity_id = opportunity_resp.json()["id"]

    own_get = request("get", f"{BASE_URL}/opportunities/{opportunity_id}", headers=headers(workspace_a))
    assert own_get.status_code == 200
    assert own_get.json()["id"] == opportunity_id

    other_get = request("get", f"{BASE_URL}/opportunities/{opportunity_id}", headers=headers(workspace_b))
    assert other_get.status_code == 404

    other_list = request(
        "get",
        f"{BASE_URL}/opportunities",
        headers=headers(workspace_b),
        params={"limit": 100, "offset": 0},
    )
    assert other_list.status_code == 200
    leaked_ids = {opportunity["id"] for opportunity in other_list.json()["data"]}
    assert opportunity_id not in leaked_ids
