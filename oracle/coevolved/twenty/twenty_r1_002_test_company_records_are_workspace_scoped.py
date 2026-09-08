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


def test_company_records_are_workspace_scoped():
    unique = uuid.uuid4().hex
    workspace_a = f"member_company_a_{unique}"
    workspace_b = f"member_company_b_{unique}"
    company_name = f"ScopedCompany-{unique}"

    create_resp = request(
        "post",
        f"{BASE_URL}/companies",
        headers=headers(workspace_a),
        json={
            "name": company_name,
            "domain": f"{unique}.example.com",
            "industry": "Isolation",
        },
    )
    assert create_resp.status_code == 201
    company_id = create_resp.json()["id"]

    own_get = request("get", f"{BASE_URL}/companies/{company_id}", headers=headers(workspace_a))
    assert own_get.status_code == 200
    assert own_get.json()["id"] == company_id

    other_get = request("get", f"{BASE_URL}/companies/{company_id}", headers=headers(workspace_b))
    assert other_get.status_code == 404

    other_list = request(
        "get",
        f"{BASE_URL}/companies",
        headers=headers(workspace_b),
        params={"limit": 100, "offset": 0},
    )
    assert other_list.status_code == 200
    leaked_ids = {company["id"] for company in other_list.json()["data"]}
    assert company_id not in leaked_ids
