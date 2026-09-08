import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user):
    return {"X-API-Key": user, "Content-Type": "application/json"}


def test_invalid_invitation_role_rejected():
    owner = f"owner_{uuid.uuid4().hex}"
    invitee = f"invitee_{uuid.uuid4().hex}"
    team = requests.post(
        f"{BASE_URL}/teams",
        json={"name": f"team_{uuid.uuid4().hex}"},
        headers=headers(owner),
    )
    assert team.status_code == 201
    team_id = team.json()["id"]

    resp = requests.post(
        f"{BASE_URL}/teams/{team_id}/invitations",
        json={"inviteeUserId": invitee, "role": "owner"},
        headers=headers(owner),
    )

    assert resp.status_code == 400
    invitations = requests.get(
        f"{BASE_URL}/teams/{team_id}/invitations",
        headers=headers(owner),
    )
    assert invitations.status_code == 200
    assert all(inv["inviteeUserId"] != invitee for inv in invitations.json())
