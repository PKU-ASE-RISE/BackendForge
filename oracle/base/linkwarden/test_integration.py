"""
BackendForge — L2 Integration Tests for Linkwarden
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
RUN_ID = uuid.uuid4().hex
USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-a"))
USER_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:user-b"))
HA = {"X-User-Id": USER_A, "Content-Type": "application/json"}
HB = {"X-User-Id": USER_B, "Content-Type": "application/json"}
U = RUN_ID[:8]


@pytest.fixture(autouse=True)
def isolate_test_data(request):
    """Give every collected item independent user namespaces."""
    global USER_A, USER_B, HA, HB, U

    item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{RUN_ID}:{request.node.nodeid}").hex
    USER_A = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-a"))
    USER_B = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{item_id}:user-b"))
    HA = {"X-User-Id": USER_A, "Content-Type": "application/json"}
    HB = {"X-User-Id": USER_B, "Content-Type": "application/json"}
    U = item_id[:8]


def get(p, params=None, h=None):
    return requests.get(f"{BASE_URL}{p}", params=params, headers=HA if h is None else h, timeout=30)


def post(p, json=None, h=None):
    return requests.post(f"{BASE_URL}{p}", json=json, headers=HA if h is None else h, timeout=30)


def put(p, json=None, h=None):
    return requests.put(f"{BASE_URL}{p}", json=json, headers=HA if h is None else h, timeout=30)


def delete(p, params=None, h=None):
    return requests.delete(f"{BASE_URL}{p}", params=params, headers=HA if h is None else h, timeout=30)


class TestLinkFieldsAndStatusCodes:
    """Pattern 1+4: Verify link response fields (camelCase) and status codes."""

    def test_link_create_returns_201_with_all_fields(self):
        r = post("/api/links", {"url": f"https://ex-{U}.com", "name": "Test Link", "description": "desc"})
        assert r.status_code == 201
        link = r.json()
        assert "id" in link
        assert "url" in link
        assert "name" in link
        assert "description" in link
        assert "collectionId" in link  # camelCase
        assert "tags" in link
        assert "createdBy" in link  # camelCase
        assert "createdAt" in link  # camelCase
        assert link["url"] == f"https://ex-{U}.com"
        assert link["name"] == "Test Link"
        assert link["createdBy"] == USER_A
        assert isinstance(link["tags"], list)

    def test_link_assigned_to_unorganized_when_no_collection(self):
        """Links without collectionId go to user's default 'Unorganized' collection."""
        link = post("/api/links", {"url": f"https://unorg-{U}.com"}).json()
        assert link["collectionId"] is not None
        # Verify the collection is named "Unorganized"
        coll = get(f"/api/collections/{link['collectionId']}").json()
        assert coll["name"] == "Unorganized"

    def test_link_404_for_nonexistent(self):
        r = get("/api/links/999999")
        assert r.status_code == 404

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/links", timeout=30)
        assert r.status_code == 401


class TestCollectionFields:
    """Pattern 1+2: Collection field names and nested members."""

    def test_collection_create_returns_201_with_fields(self):
        r = post("/api/collections", {"name": f"Coll-{U}", "description": "test", "color": "#ff0000", "isPublic": False})
        assert r.status_code == 201
        coll = r.json()
        assert "id" in coll
        assert "name" in coll
        assert "description" in coll
        assert "color" in coll
        assert "parentId" in coll  # camelCase
        assert "isPublic" in coll  # camelCase
        assert "ownerId" in coll  # camelCase
        assert "createdAt" in coll
        assert coll["name"] == f"Coll-{U}"
        assert coll["color"] == "#ff0000"
        assert coll["isPublic"] is False
        assert coll["ownerId"] == USER_A

    def test_collection_includes_members(self):
        """GET collection should include members array."""
        coll = post("/api/collections", {"name": f"MemColl-{U}"}).json()
        resp = get(f"/api/collections/{coll['id']}").json()
        assert "members" in resp
        assert isinstance(resp["members"], list)
        # Owner should be listed
        assert any(m["role"] == "owner" for m in resp["members"])


class TestTagFields:
    """Pattern 1+5: Tag fields and deduplication behavior."""

    def test_tag_create_returns_201_with_fields(self):
        r = post("/api/tags", {"name": f"Tag-{U}"})
        assert r.status_code == 201
        tag = r.json()
        assert "id" in tag
        assert "name" in tag
        assert "ownerId" in tag  # camelCase
        assert "createdAt" in tag
        assert tag["name"] == f"Tag-{U}"
        assert tag["ownerId"] == USER_A

    def test_tag_dedup_returns_200_not_409(self):
        """Creating duplicate tag returns existing tag with 200, not 409."""
        name = f"Dedup-{uuid.uuid4().hex[:6]}"
        r1 = post("/api/tags", {"name": name})
        assert r1.status_code == 201
        r2 = post("/api/tags", {"name": name})
        assert r2.status_code == 200
        assert r2.json()["id"] == r1.json()["id"]

    def test_tag_dedup_case_insensitive(self):
        """Tag dedup is case-insensitive."""
        name = f"CaseTag-{uuid.uuid4().hex[:6]}"
        r1 = post("/api/tags", {"name": name.lower()})
        r2 = post("/api/tags", {"name": name.upper()})
        assert r2.status_code == 200
        assert r2.json()["id"] == r1.json()["id"]


class TestFilteringWorks:
    """Pattern 3: Filtering actually filters results."""

    def test_links_filter_by_collectionId(self):
        c1 = post("/api/collections", {"name": f"FC1-{U}"}).json()
        c2 = post("/api/collections", {"name": f"FC2-{U}"}).json()
        l1 = post("/api/links", {"url": "https://in-c1.com", "collectionId": c1["id"]}).json()
        l2 = post("/api/links", {"url": "https://in-c2.com", "collectionId": c2["id"]}).json()

        r = get("/api/links", params={"collectionId": c1["id"]})
        ids = [l["id"] for l in r.json()["links"]]
        assert l1["id"] in ids
        assert l2["id"] not in ids

    def test_links_filter_by_tagId(self):
        tag = post("/api/tags", {"name": f"FiltTag-{uuid.uuid4().hex[:6]}"}).json()
        l1 = post("/api/links", {"url": "https://tagged.com", "tags": [{"name": tag["name"]}]}).json()
        l2 = post("/api/links", {"url": "https://untagged.com"}).json()

        r = get("/api/links", params={"tagId": tag["id"]})
        ids = [l["id"] for l in r.json()["links"]]
        assert l1["id"] in ids
        assert l2["id"] not in ids

    def test_link_list_returns_total_count(self):
        """Response must include 'total' field."""
        r = get("/api/links")
        data = r.json()
        assert "links" in data
        assert "total" in data
        assert isinstance(data["total"], int)


class TestDataIsolation:
    """Pattern 6: User A can't see User B's data."""

    def test_links_isolated(self):
        link = post("/api/links", {"url": f"https://private-{U}.com"}).json()
        r = get(f"/api/links/{link['id']}", h=HB)
        assert r.status_code in (403, 404)

    def test_collections_isolated(self):
        coll = post("/api/collections", {"name": f"Private-{U}"}).json()
        r = get(f"/api/collections/{coll['id']}", h=HB)
        assert r.status_code in (403, 404)

    def test_tags_isolated(self):
        post("/api/tags", {"name": f"IsoTag-{uuid.uuid4().hex[:6]}"})
        r = get("/api/tags", h=HB)
        tags_b = [t["name"] for t in r.json()["tags"]]
        # User B should not have User A's tags
        assert not any("IsoTag" in t for t in tags_b)


class TestHighlightFields:
    """Pattern 1+2: Highlight fields on links."""

    def test_highlight_create_returns_201_with_fields(self):
        link = post("/api/links", {"url": "https://hl.com"}).json()
        r = post(f"/api/links/{link['id']}/highlights", {"text": "highlighted text", "color": "#ffff00", "note": "my note"})
        assert r.status_code == 201
        hl = r.json()
        assert "id" in hl
        assert "linkId" in hl  # camelCase
        assert "text" in hl
        assert "color" in hl
        assert "note" in hl
        assert "createdBy" in hl  # camelCase
        assert hl["text"] == "highlighted text"
        assert hl["color"] == "#ffff00"
        assert hl["linkId"] == link["id"]

    def test_highlight_roundtrip(self):
        link = post("/api/links", {"url": "https://hlrt.com"}).json()
        hl = post(f"/api/links/{link['id']}/highlights", {"text": "round trip"}).json()
        r = get(f"/api/links/{link['id']}/highlights")
        assert r.status_code == 200
        hls = r.json()["highlights"]
        assert any(h["id"] == hl["id"] for h in hls)


class TestPublicAccess:
    """Pattern 6: Public collections accessible without auth."""

    def test_public_collection_accessible_without_auth(self):
        coll = post("/api/collections", {"name": f"Public-{U}", "isPublic": True}).json()
        post("/api/links", {"url": "https://pub.com", "collectionId": coll["id"]})

        r = requests.get(f"{BASE_URL}/api/public/collections/{coll['id']}", timeout=30)
        assert r.status_code == 200
        assert r.json()["name"] == f"Public-{U}"

        r2 = requests.get(f"{BASE_URL}/api/public/collections/{coll['id']}/links", timeout=30)
        assert r2.status_code == 200
        assert len(r2.json()["links"]) >= 1

    def test_private_collection_returns_404_on_public_endpoint(self):
        coll = post("/api/collections", {"name": f"Priv-{U}", "isPublic": False}).json()
        r = requests.get(f"{BASE_URL}/api/public/collections/{coll['id']}", timeout=30)
        assert r.status_code == 404


class TestDashboardAndExport:
    """Pattern 1+5: Dashboard computed values and export."""

    def test_dashboard_returns_all_fields(self):
        r = get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "totalLinks" in data  # camelCase
        assert "totalCollections" in data
        assert "totalTags" in data
        assert "linksPerDay" in data
        assert isinstance(data["linksPerDay"], list)

    def test_export_returns_all_links(self):
        # Create a link
        post("/api/links", {"url": f"https://exp-{U}.com"})
        r = get("/api/export")
        assert r.status_code == 200
        data = r.json()
        assert "links" in data
        assert isinstance(data["links"], list)
        assert any(l["url"] == f"https://exp-{U}.com" for l in data["links"])


class TestSearchEndpoint:
    """Pattern 3+5: Search actually works."""

    def test_search_finds_by_name(self):
        unique = f"searchterm{uuid.uuid4().hex[:6]}"
        post("/api/links", {"url": "https://s.com", "name": unique})
        r = get("/api/search", params={"q": unique})
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        assert any(unique in l.get("name", "") for l in r.json()["links"])

    def test_search_finds_by_url(self):
        unique = f"xyzsite{uuid.uuid4().hex[:6]}"
        post("/api/links", {"url": f"https://{unique}.com"})
        r = get("/api/search", params={"q": unique})
        assert r.json()["total"] >= 1


class TestBulkImport:
    """Pattern 1+4: Bulk import returns correct structure."""

    def test_bulk_import_returns_201_with_links_and_count(self):
        r = post("/api/links/bulk", {"links": [
            {"url": "https://b1.com", "name": "B1"},
            {"url": "https://b2.com", "name": "B2"},
        ]})
        assert r.status_code == 201
        data = r.json()
        assert "links" in data
        assert "count" in data
        assert data["count"] == 2
        assert len(data["links"]) == 2
