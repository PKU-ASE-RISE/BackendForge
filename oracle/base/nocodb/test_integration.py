"""
L2 Integration Tests for NocoDB API.
Tests targeting: camelCase fields, filtering, sorting, formula computation,
status codes, role enforcement, and nested data.
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def unique(prefix="t"):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


def owner_key(base_id, user="user1"):
    return f"owner_{base_id}_{user}"


def creator_key(base_id, user="user2"):
    return f"creator_{base_id}_{user}"


def editor_key(base_id, user="user3"):
    return f"editor_{base_id}_{user}"


def viewer_key(base_id, user="user5"):
    return f"viewer_{base_id}_{user}"


def h(api_key):
    return {"X-API-Key": api_key}


def create_base(title=None):
    title = title or unique("base")
    key = owner_key("base1")
    resp = requests.post(f"{API}/bases", json={"title": title}, headers=h(key))
    assert resp.status_code == 201
    return resp.json()


def create_table(base_id, title=None):
    title = title or unique("tbl")
    key = owner_key(base_id)
    resp = requests.post(f"{API}/bases/{base_id}/tables", json={"title": title}, headers=h(key))
    assert resp.status_code == 201
    return resp.json()


def create_column(base_id, table_id, title, col_type, options=None):
    key = owner_key(base_id)
    payload = {"title": title, "type": col_type}
    if options:
        payload["options"] = options
    resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                         json=payload, headers=h(key))
    assert resp.status_code == 201
    return resp.json()


def create_record(base_id, table_id, data, key=None):
    key = key or owner_key(base_id)
    resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                         json=data, headers=h(key))
    assert resp.status_code == 201
    return resp.json()


# =============================================================================
# L2 TESTS
# =============================================================================


class TestFieldCasing:
    """Pattern 1: Verify camelCase in all responses."""

    def test_base_response_camelcase(self):
        base = create_base()
        assert "id" in base
        assert "title" in base
        assert "createdAt" in base
        assert "updatedAt" in base
        assert "created_at" not in base

    def test_table_response_camelcase(self):
        base = create_base()
        table = create_table(base["id"])
        assert "id" in table
        assert "baseId" in table
        assert "title" in table
        assert "createdAt" in table
        assert "updatedAt" in table
        assert "base_id" not in table

    def test_column_response_camelcase(self):
        base = create_base()
        table = create_table(base["id"])
        col = create_column(base["id"], table["id"], "Name", "text")
        assert "id" in col
        assert "tableId" in col
        assert "title" in col
        assert "type" in col
        assert "createdAt" in col
        assert "table_id" not in col


class TestRecordCRUD:
    """Pattern 4+5: Record operations with correct status codes."""

    def test_create_record_returns_201(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "name", "text")
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/records",
                             json={"name": "Test"}, headers=h(owner_key(base["id"])))
        assert resp.status_code == 201
        rec = resp.json()
        assert "id" in rec
        assert rec["name"] == "Test"

    def test_delete_record_returns_204(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "x", "text")
        rec = create_record(base["id"], table["id"], {"x": "del"})
        resp = requests.delete(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                               headers=h(owner_key(base["id"])))
        assert resp.status_code == 204

    def test_get_nonexistent_record_returns_404(self):
        base = create_base()
        table = create_table(base["id"])
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/records/99999",
                            headers=h(owner_key(base["id"])))
        assert resp.status_code == 404


class TestFormulaComputation:
    """Pattern 5: Formula fields compute values, not just echo."""

    def test_concat_formula(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "first", "text")
        create_column(base["id"], table["id"], "last", "text")
        create_column(base["id"], table["id"], "full", "formula",
                      options={"expression": 'CONCAT(first, " ", last)'})

        rec = create_record(base["id"], table["id"], {"first": "John", "last": "Doe"})
        # GET record to see computed formula
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                            headers=h(owner_key(base["id"])))
        data = resp.json()
        assert data["full"] == "John Doe"

    def test_add_formula(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "a", "number")
        create_column(base["id"], table["id"], "b", "number")
        create_column(base["id"], table["id"], "total", "formula",
                      options={"expression": "ADD(a, b)"})

        rec = create_record(base["id"], table["id"], {"a": 10, "b": 25})
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                            headers=h(owner_key(base["id"])))
        data = resp.json()
        assert data["total"] == 35

    def test_upper_formula(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "name", "text")
        create_column(base["id"], table["id"], "upper_name", "formula",
                      options={"expression": "UPPER(name)"})

        rec = create_record(base["id"], table["id"], {"name": "hello"})
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                            headers=h(owner_key(base["id"])))
        assert resp.json()["upper_name"] == "HELLO"


class TestViewFiltering:
    """Pattern 3: View filters actually filter records."""

    def test_view_filter_eq(self):
        base = create_base()
        table = create_table(base["id"])
        col = create_column(base["id"], table["id"], "status", "text")
        key = owner_key(base["id"])

        create_record(base["id"], table["id"], {"status": "active"})
        create_record(base["id"], table["id"], {"status": "inactive"})
        create_record(base["id"], table["id"], {"status": "active"})

        # Create view with filter
        view = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views",
                             json={"title": "Active Only", "type": "grid"}, headers=h(key)).json()
        requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/filters",
                      json={"columnId": col["id"], "operator": "eq", "value": "active"},
                      headers=h(key))

        # Get records through view
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/records",
            headers=h(key))
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert len(records) == 2
        for r in records:
            assert r["status"] == "active"

    def test_view_sort_asc(self):
        base = create_base()
        table = create_table(base["id"])
        col = create_column(base["id"], table["id"], "priority", "number")
        key = owner_key(base["id"])

        create_record(base["id"], table["id"], {"priority": 30})
        create_record(base["id"], table["id"], {"priority": 10})
        create_record(base["id"], table["id"], {"priority": 20})

        view = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views",
                             json={"title": "Sorted", "type": "grid"}, headers=h(key)).json()
        requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/sorts",
                      json={"columnId": col["id"], "direction": "asc"}, headers=h(key))

        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/records",
            headers=h(key))
        records = resp.json()["records"]
        priorities = [r["priority"] for r in records]
        assert priorities == sorted(priorities)


class TestRoleEnforcement:
    """Pattern 6: Role-based access control."""

    def test_viewer_cannot_create_record(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "x", "text")
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/records",
                             json={"x": "hack"}, headers=h(viewer_key(base["id"])))
        assert resp.status_code == 403

    def test_editor_cannot_create_column(self):
        base = create_base()
        table = create_table(base["id"])
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/columns",
                             json={"title": "hack", "type": "text"},
                             headers=h(editor_key(base["id"])))
        assert resp.status_code == 403

    def test_editor_can_create_record(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "val", "text")
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/records",
                             json={"val": "yes"}, headers=h(editor_key(base["id"])))
        assert resp.status_code == 201


class TestColumnTypes:
    """Pattern 5: Column types enforce their constraints."""

    def test_single_select_valid_choice(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "color", "singleSelect",
                      options={"choices": ["red", "green", "blue"]})

        rec = create_record(base["id"], table["id"], {"color": "red"})
        assert rec["color"] == "red"

    def test_checkbox_boolean(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "done", "checkbox")

        rec = create_record(base["id"], table["id"], {"done": True})
        assert rec["done"] is True


class TestDeleteCascade:
    """Pattern 7: Delete operations cascade correctly."""

    def test_delete_table_returns_204(self):
        base = create_base()
        table = create_table(base["id"])
        resp = requests.delete(f"{API}/bases/{base['id']}/tables/{table['id']}",
                               headers=h(owner_key(base["id"])))
        assert resp.status_code == 204

    def test_delete_base_returns_204(self):
        base = create_base()
        resp = requests.delete(f"{API}/bases/{base['id']}",
                               headers=h(owner_key(base["id"])))
        assert resp.status_code == 204


class TestAuditLog:
    """Pattern 7: Record operations generate audit entries."""

    def test_record_create_generates_audit(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "name", "text")
        create_record(base["id"], table["id"], {"name": "AuditMe"})

        resp = requests.get(f"{API}/bases/{base['id']}/audit",
                            headers=h(owner_key(base["id"])))
        assert resp.status_code == 200
        entries = resp.json()["items"]
        assert len(entries) >= 1
        assert any(e["action"] == "created" for e in entries)
