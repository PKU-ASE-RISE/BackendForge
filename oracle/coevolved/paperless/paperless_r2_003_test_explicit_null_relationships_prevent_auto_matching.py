import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def make_headers():
    return {
        "X-Api-Key": f"drp-null-rel-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_explicit_null_relationships_prevent_auto_matching():
    headers = make_headers()
    corr_word = f"corrword{uuid.uuid4().hex}"
    type_phrase = f"type phrase {uuid.uuid4().hex}"

    corr = post(
        "/api/correspondents/",
        {"name": f"corr-{uuid.uuid4().hex}", "match": corr_word, "matching_algorithm": 1},
        headers,
    )
    assert corr.status_code == 201, corr.text

    doc_type = post(
        "/api/document_types/",
        {"name": f"type-{uuid.uuid4().hex}", "match": type_phrase, "matching_algorithm": 3},
        headers,
    )
    assert doc_type.status_code == 201, doc_type.text

    created = post(
        "/api/documents/",
        {
            "title": f"document containing {corr_word}",
            "content": f"content containing {type_phrase}",
            "correspondent": None,
            "document_type": None,
        },
        headers,
    )
    assert created.status_code == 201, created.text
    created_doc = created.json()
    assert created_doc["correspondent"] is None
    assert created_doc["document_type"] is None

    reloaded = get(f"/api/documents/{created_doc['id']}/", headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["correspondent"] is None
    assert reloaded.json()["document_type"] is None
