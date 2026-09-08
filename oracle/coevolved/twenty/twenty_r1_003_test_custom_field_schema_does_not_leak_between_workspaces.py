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


def test_custom_field_schema_does_not_leak_between_workspaces():
    unique = uuid.uuid4().hex
    workspace_a_admin = f"admin_custom_field_a_{unique}"
    workspace_b_member = f"member_custom_field_b_{unique}"
    field_name = f"probeField{unique[:12]}"

    field_resp = request(
        "post",
        f"{BASE_URL}/custom-fields",
        headers=headers(workspace_a_admin),
        json={
            "name": field_name,
            "label": f"Probe Field {unique[:8]}",
            "objectType": "people",
            "type": "text",
        },
    )
    assert field_resp.status_code == 201
    assert field_resp.json()["name"] == field_name

    person_resp = request(
        "post",
        f"{BASE_URL}/people",
        headers=headers(workspace_b_member),
        json={"firstName": f"Schema{unique[:6]}", "lastName": "Isolation"},
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["id"]

    fetched = request("get", f"{BASE_URL}/people/{person_id}", headers=headers(workspace_b_member))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == person_id
    assert field_name not in fetched.json()

    listed = request(
        "get",
        f"{BASE_URL}/people",
        headers=headers(workspace_b_member),
        params={"limit": 100, "offset": 0},
    )
    assert listed.status_code == 200
    matching_people = [person for person in listed.json()["data"] if person["id"] == person_id]
    assert len(matching_people) == 1
    assert field_name not in matching_people[0]
