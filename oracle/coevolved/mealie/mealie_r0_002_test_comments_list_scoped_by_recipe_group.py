import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(group_id, user_id, household_id):
    return {
        "X-Group-Id": group_id,
        "X-User-Id": user_id,
        "X-Household-Id": household_id,
        "Content-Type": "application/json",
    }


GROUP_A = "00000000-0000-0000-0000-300000000001"
HOUSEHOLD_A = "00000000-0000-0000-0000-300000000002"
USER_A = "00000000-0000-0000-0000-300000000003"
GROUP_B = "00000000-0000-0000-0000-300000000011"
HOUSEHOLD_B = "00000000-0000-0000-0000-300000000012"
USER_B = "00000000-0000-0000-0000-300000000013"

HEADERS_A = headers(GROUP_A, USER_A, HOUSEHOLD_A)
HEADERS_B = headers(GROUP_B, USER_B, HOUSEHOLD_B)


def post(path, json_data, request_headers):
    return requests.post(
        f"{BASE_URL}{path}", json=json_data, headers=request_headers, timeout=30
    )


def get(path, request_headers, params=None):
    return requests.get(
        f"{BASE_URL}{path}", params=params, headers=request_headers, timeout=30
    )


def create_recipe(name, request_headers):
    response = post("/api/recipes", {"name": name}, request_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    return body if isinstance(body, str) else body.get("slug") or body.get("id")


def get_recipe(slug, request_headers):
    response = get(f"/api/recipes/{slug}", request_headers)
    assert response.status_code == 200, response.text
    return response.json()


def create_comment(recipe_id, text, request_headers):
    response = post(
        "/api/comments", {"recipeId": recipe_id, "text": text}, request_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def listed_comment_texts(request_headers):
    response = get("/api/comments", request_headers, params={"perPage": 100})
    assert response.status_code == 200, response.text
    return [item.get("text") for item in response.json().get("items", [])]


def test_comments_list_scoped_by_recipe_group():
    marker = uuid.uuid4().hex
    slug_a = create_recipe(f"comment-scope-a-{marker}", HEADERS_A)
    slug_b = create_recipe(f"comment-scope-b-{marker}", HEADERS_B)
    recipe_a = get_recipe(slug_a, HEADERS_A)
    recipe_b = get_recipe(slug_b, HEADERS_B)

    text_a = f"group-a-comment-{marker}"
    text_b = f"group-b-comment-{marker}"
    create_comment(recipe_a["id"], text_a, HEADERS_A)
    create_comment(recipe_b["id"], text_b, HEADERS_B)

    group_a_texts = listed_comment_texts(HEADERS_A)
    group_b_texts = listed_comment_texts(HEADERS_B)

    assert text_a in group_a_texts
    assert text_b not in group_a_texts, "Group A comment list leaked Group B data"
    assert text_b in group_b_texts
    assert text_a not in group_b_texts, "Group B comment list leaked Group A data"
