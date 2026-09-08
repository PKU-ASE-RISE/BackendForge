import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

GROUP_A = "00000000-0000-0000-0000-301000000001"
HOUSEHOLD_A = "00000000-0000-0000-0000-301000000002"
USER_A = "00000000-0000-0000-0000-301000000003"
GROUP_B = "00000000-0000-0000-0000-301000000011"
HOUSEHOLD_B = "00000000-0000-0000-0000-301000000012"
USER_B = "00000000-0000-0000-0000-301000000013"

HEADERS_A = {
    "X-Group-Id": GROUP_A,
    "X-User-Id": USER_A,
    "X-Household-Id": HOUSEHOLD_A,
    "Content-Type": "application/json",
}
HEADERS_B = {
    "X-Group-Id": GROUP_B,
    "X-User-Id": USER_B,
    "X-Household-Id": HOUSEHOLD_B,
    "Content-Type": "application/json",
}


def request(method, path, request_headers, **kwargs):
    return requests.request(
        method, f"{BASE_URL}{path}", headers=request_headers, timeout=30, **kwargs
    )


def create_recipe(name, request_headers):
    response = request("POST", "/api/recipes", request_headers, json={"name": name})
    assert response.status_code == 201, response.text
    body = response.json()
    return body if isinstance(body, str) else body.get("slug") or body.get("id")


def get_recipe(slug, request_headers):
    response = request("GET", f"/api/recipes/{slug}", request_headers)
    assert response.status_code == 200, response.text
    return response.json()


def get_recipe_comment_texts(slug, request_headers):
    response = request("GET", f"/api/recipes/{slug}/comments", request_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    if isinstance(body, dict):
        items = body.get("items", [])
    else:
        items = body
    return [item.get("text") for item in items]


def test_comment_create_rejects_cross_group_recipe_id():
    marker = uuid.uuid4().hex
    slug_a = create_recipe(f"cross-comment-target-{marker}", HEADERS_A)
    recipe_a = get_recipe(slug_a, HEADERS_A)
    intrusion_text = f"cross-group-comment-{marker}"

    response = request(
        "POST",
        "/api/comments",
        HEADERS_B,
        json={"recipeId": recipe_a["id"], "text": intrusion_text},
    )

    assert response.status_code != 201, (
        "Cross-group comment creation returned success for another group's recipe"
    )
    assert intrusion_text not in get_recipe_comment_texts(slug_a, HEADERS_A)
