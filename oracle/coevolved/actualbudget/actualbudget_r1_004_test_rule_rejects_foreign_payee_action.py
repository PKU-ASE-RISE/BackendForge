import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api(method, path, user_id, json_data=None, params=None):
    return requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers(user_id),
        json=json_data,
        params=params,
        timeout=30,
    )


def test_rule_rejects_foreign_payee_action():
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex

    foreign_payee_resp = api(
        "POST",
        "/payees",
        other_user_id,
        {"name": f"rule-foreign-payee-{suffix}"},
    )
    assert foreign_payee_resp.status_code == 201, foreign_payee_resp.text
    foreign_payee_id = foreign_payee_resp.json()["id"]

    rule_resp = api(
        "POST",
        "/rules",
        user_id,
        {
            "conditions": [
                {"field": "notes", "op": "contains", "value": f"rule-marker-{suffix}"}
            ],
            "actions": [{"field": "payee", "value": foreign_payee_id}],
        },
    )
    assert rule_resp.status_code == 400, rule_resp.text

    listed_resp = api("GET", "/rules", user_id)
    assert listed_resp.status_code == 200, listed_resp.text
    assert all(
        foreign_payee_id not in [action.get("value") for action in rule["actions"]]
        for rule in listed_resp.json()
    )
