import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def unique_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def create_content_type(name):
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": name, "displayName": name.replace("_", " ").title()},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def add_field(content_type_id, name, field_type, **extra):
    payload = {"name": name, "type": field_type}
    payload.update(extra)
    resp = requests.post(
        f"{BASE_URL}/content-types/{content_type_id}/fields",
        json=payload,
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def create_entry(content_type_name, payload):
    resp = requests.post(
        f"{BASE_URL}/content/{content_type_name}", json=payload, headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def get_entry(content_type_name, entry_id):
    resp = requests.get(
        f"{BASE_URL}/content/{content_type_name}/{entry_id}", headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_manytomany_inverse_relation_populates_target_side():
    tag_type = unique_name("tag")
    article_type = unique_name("article")

    tag_ct = create_content_type(tag_type)
    article_ct = create_content_type(article_type)

    add_field(tag_ct["id"], "label", "text")
    add_field(article_ct["id"], "title", "text")
    add_field(
        article_ct["id"],
        "tags",
        "relation",
        target=tag_type,
        relationType="manyToMany",
    )
    add_field(
        tag_ct["id"],
        "articles",
        "relation",
        target=article_type,
        relationType="manyToMany",
    )

    tag = create_entry(tag_type, {"label": f"tag-{uuid.uuid4().hex}"})
    article = create_entry(
        article_type,
        {"title": f"article-{uuid.uuid4().hex}", "tags": [tag["id"]]},
    )

    reloaded_tag = get_entry(tag_type, tag["id"])
    assert "articles" in reloaded_tag
    assert isinstance(reloaded_tag["articles"], list)
    assert any(item["id"] == article["id"] for item in reloaded_tag["articles"])
