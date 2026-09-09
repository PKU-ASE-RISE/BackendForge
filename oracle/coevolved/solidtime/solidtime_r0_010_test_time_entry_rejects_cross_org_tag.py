import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_time_entry_does_not_attach_cross_org_tag():
    org_a_headers = fresh_headers()
    org_b_headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=org_a_headers, timeout=30)
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=org_b_headers, timeout=30)

    tag_response = requests.post(
        f"{BASE_URL}/api/v1/tags",
        headers=org_a_headers,
        json={"name": f"foreign-tag-{uuid.uuid4().hex}"},
        timeout=30,
    )
    assert tag_response.status_code == 201
    foreign_tag_id = tag_response.json()["id"]
    description = f"cross-org-tag-entry-{uuid.uuid4().hex}"

    create_response = requests.post(
        f"{BASE_URL}/api/v1/time-entries",
        headers=org_b_headers,
        json={
            "start": "2024-05-02T09:00:00Z",
            "end": "2024-05-02T10:00:00Z",
            "billable": False,
            "description": description,
            "tag_ids": [foreign_tag_id],
        },
        timeout=30,
    )

    # Isolation does not specify rejection versus ignoring foreign references.
    assert create_response.status_code in (201, 422), create_response.text
    entries = requests.get(
        f"{BASE_URL}/api/v1/time-entries",
        headers=org_b_headers,
        timeout=30,
    ).json()
    matching = [entry for entry in entries if entry.get("description") == description]
    if create_response.status_code == 422:
        assert matching == []
    else:
        assert len(matching) == 1
        assert matching[0]["id"] == create_response.json()["id"]
        assert foreign_tag_id not in {tag["id"] for tag in matching[0]["tags"]}
        assert foreign_tag_id not in {tag["id"] for tag in create_response.json()["tags"]}
    source_tags = requests.get(f"{BASE_URL}/api/v1/tags", headers=org_a_headers, timeout=30)
    assert source_tags.status_code == 200
    assert [tag for tag in source_tags.json() if tag["id"] == foreign_tag_id] == [tag_response.json()]
