import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {
    "X-Api-Key": "direct-reference-prober",
    "Content-Type": "application/json",
}


def _collect_visits(path):
    params = {"itemsPerPage": 100, "page": 1}
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=30)
    assert resp.status_code == 200, resp.text
    payload = resp.json()["visits"]
    visits = list(payload["data"])
    pages_count = payload["pagination"]["pagesCount"]

    for page in range(2, pages_count + 1):
        page_params = dict(params, page=page)
        page_resp = requests.get(
            f"{BASE_URL}{path}", headers=HEADERS, params=page_params, timeout=30
        )
        assert page_resp.status_code == 200, page_resp.text
        visits.extend(page_resp.json()["visits"]["data"])
    return visits


def _has_probe_visit(visits, user_agent, referer):
    return any(
        visit.get("userAgent") == user_agent and visit.get("referer") == referer
        for visit in visits
    )


def test_delete_short_url_removes_global_visit_records():
    unique = uuid.uuid4().hex
    slug = f"delvisit-{unique}"
    long_url = f"https://example.com/delete-cascade/{unique}"
    user_agent = f"DeleteCascadeProbe/{unique}"
    referer = f"https://ref.example/{unique}"
    create_resp = requests.post(
        f"{BASE_URL}/rest/v3/short-urls",
        headers=HEADERS,
        json={"longUrl": long_url, "customSlug": slug},
        timeout=30,
    )
    assert create_resp.status_code == 200, create_resp.text

    redirect_resp = requests.get(
        f"{BASE_URL}/{slug}",
        headers={"User-Agent": user_agent, "Referer": referer},
        allow_redirects=False,
        timeout=30,
    )
    assert redirect_resp.status_code == 302, redirect_resp.text

    before_delete = _collect_visits("/rest/v3/visits/non-orphan")
    assert _has_probe_visit(before_delete, user_agent, referer)

    delete_resp = requests.delete(
        f"{BASE_URL}/rest/v3/short-urls/{slug}", headers=HEADERS, timeout=30
    )
    assert delete_resp.status_code == 204, delete_resp.text

    non_orphan_after = _collect_visits("/rest/v3/visits/non-orphan")
    orphan_after = _collect_visits("/rest/v3/visits/orphan")
    assert not _has_probe_visit(non_orphan_after, user_agent, referer)
    assert not _has_probe_visit(orphan_after, user_agent, referer)
