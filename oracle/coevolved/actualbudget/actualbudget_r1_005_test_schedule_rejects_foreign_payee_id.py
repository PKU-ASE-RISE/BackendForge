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


def test_schedule_rejects_foreign_payee_id():
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex
    schedule_name = f"foreign-payee-schedule-{suffix}"

    account_resp = api(
        "POST",
        "/accounts",
        user_id,
        {"name": f"schedule-owner-account-{suffix}", "type": "checking"},
    )
    assert account_resp.status_code == 201, account_resp.text
    account_id = account_resp.json()["id"]

    foreign_payee_resp = api(
        "POST",
        "/payees",
        other_user_id,
        {"name": f"schedule-foreign-payee-{suffix}"},
    )
    assert foreign_payee_resp.status_code == 201, foreign_payee_resp.text
    foreign_payee_id = foreign_payee_resp.json()["id"]

    schedule_resp = api(
        "POST",
        "/schedules",
        user_id,
        {
            "name": schedule_name,
            "frequency": "monthly",
            "nextDate": "2025-04-15",
            "amount": -4200,
            "accountId": account_id,
            "payeeId": foreign_payee_id,
        },
    )
    assert schedule_resp.status_code == 400, schedule_resp.text

    listed_resp = api("GET", "/schedules", user_id)
    assert listed_resp.status_code == 200, listed_resp.text
    assert all(item["name"] != schedule_name for item in listed_resp.json())
