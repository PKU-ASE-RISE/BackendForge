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


def test_workspace_isolation_by_api_key():
    unique = uuid.uuid4().hex
    workspace_a_key = f"memberwsA_{unique}"
    workspace_b_key = f"memberwsB_{unique}"

    created = request(
        "post",
        f"{BASE_URL}/people",
        headers=headers(workspace_a_key),
        json={
            "firstName": f"IsoFirst{unique[:8]}",
            "lastName": f"IsoLast{unique[:8]}",
            "email": f"iso-{unique}@example.com",
        },
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["id"]

    other_list = request("get", f"{BASE_URL}/people", headers=headers(workspace_b_key))
    assert other_list.status_code == 200, other_list.text
    other_ids = {person["id"] for person in other_list.json()["data"]}
    assert person_id not in other_ids

    other_get = request("get", f"{BASE_URL}/people/{person_id}", headers=headers(workspace_b_key))
    assert other_get.status_code == 404, other_get.text

    tag_name = f"workspace-tag-{unique}"
    first_tag = request(
        "post",
        f"{BASE_URL}/tags",
        headers=headers(workspace_a_key),
        json={"name": tag_name, "color": "#123456"},
    )
    assert first_tag.status_code == 201, first_tag.text

    second_workspace_tag = request(
        "post",
        f"{BASE_URL}/tags",
        headers=headers(workspace_b_key),
        json={"name": tag_name, "color": "#654321"},
    )
    assert second_workspace_tag.status_code == 201, second_workspace_tag.text
