"""
L3 Workflow Tests for NocoDB API.
Multi-step workflows: linked tables, rollup/lookup, shared views,
comments, full table lifecycle, view filtering with sorts.
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
    resp = requests.post(f"{API}/bases/{base_id}/tables", json={"title": title},
                         headers=h(owner_key(base_id)))
    assert resp.status_code == 201
    return resp.json()


def create_column(base_id, table_id, title, col_type, options=None):
    payload = {"title": title, "type": col_type}
    if options:
        payload["options"] = options
    resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                         json=payload, headers=h(owner_key(base_id)))
    assert resp.status_code == 201
    return resp.json()


def create_record(base_id, table_id, data):
    resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                         json=data, headers=h(owner_key(base_id)))
    assert resp.status_code == 201
    return resp.json()


# =============================================================================
# L3 TESTS
# =============================================================================


class TestLinkedTablesWorkflow:
    """Link columns, lookup, and rollup across tables."""

    def test_link_lookup_rollup(self):
        """
        Pattern 2+5: Create linked tables, verify link data,
        lookup pulls values, rollup computes aggregates.
        """
        base = create_base()
        key = owner_key(base["id"])

        # 1. Create Orders and Items tables
        orders_table = create_table(base["id"], "orders")
        items_table = create_table(base["id"], "items")

        # 2. Add columns
        create_column(base["id"], orders_table["id"], "customer", "text")
        create_column(base["id"], items_table["id"], "product", "text")
        price_col = create_column(base["id"], items_table["id"], "price", "number")

        # 3. Create link column on orders -> items
        link_col = create_column(base["id"], orders_table["id"], "items_link", "link",
                                 options={"linkedTableId": items_table["id"]})

        # 4. Create item records
        item1 = create_record(base["id"], items_table["id"], {"product": "Widget", "price": 10})
        item2 = create_record(base["id"], items_table["id"], {"product": "Gadget", "price": 25})
        item3 = create_record(base["id"], items_table["id"], {"product": "Doohickey", "price": 15})

        # 5. Create order linked to items
        order = create_record(base["id"], orders_table["id"], {
            "customer": "Alice",
            "items_link": [item1["id"], item2["id"]]
        })

        # 6. Verify link field
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{orders_table['id']}/records/{order['id']}",
            headers=h(key))
        order_data = resp.json()
        assert item1["id"] in order_data["items_link"]
        assert item2["id"] in order_data["items_link"]

        # 7. Create lookup column (product names via link)
        create_column(base["id"], orders_table["id"], "item_names", "lookup",
                      options={"linkColumnId": link_col["id"], "lookupColumnId": price_col["id"]})

        # 8. Create rollup column (SUM of prices)
        create_column(base["id"], orders_table["id"], "total_price", "rollup",
                      options={"linkColumnId": link_col["id"], "rollupColumnId": price_col["id"],
                               "aggregation": "SUM"})

        # 9. Verify rollup computes correctly
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{orders_table['id']}/records/{order['id']}",
            headers=h(key))
        data = resp.json()
        assert data["total_price"] == 35  # 10 + 25


class TestSharedViewWorkflow:
    """Shared views with password protection."""

    def test_shared_view_access(self):
        """
        Pattern 5+6: Create view, share it, access without auth,
        verify password protection works.
        """
        base = create_base()
        key = owner_key(base["id"])
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "name", "text")
        create_record(base["id"], table["id"], {"name": "Public Data"})

        # 1. Create view
        view = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views",
                             json={"title": "Public View", "type": "grid"},
                             headers=h(key)).json()

        # 2. Share view with password
        share = requests.post(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/shares",
            json={"password": "secret123"}, headers=h(key)).json()
        assert "uuid" in share

        # 3. Access without password should fail
        resp = requests.get(f"{API}/shared/{share['uuid']}/records")
        assert resp.status_code == 401

        # 4. Access with correct password
        resp = requests.get(f"{API}/shared/{share['uuid']}/records",
                            params={"password": "secret123"})
        assert resp.status_code == 200
        records = resp.json()["records"]
        assert len(records) >= 1
        assert records[0]["name"] == "Public Data"


class TestViewFilterSortCombined:
    """View with both filters and sorts."""

    def test_filter_and_sort_combined(self):
        """
        Pattern 3+5: View with filter AND sort applied correctly.
        """
        base = create_base()
        key = owner_key(base["id"])
        table = create_table(base["id"])
        cat_col = create_column(base["id"], table["id"], "category", "text")
        score_col = create_column(base["id"], table["id"], "score", "number")

        # Create records
        create_record(base["id"], table["id"], {"category": "A", "score": 30})
        create_record(base["id"], table["id"], {"category": "B", "score": 50})
        create_record(base["id"], table["id"], {"category": "A", "score": 10})
        create_record(base["id"], table["id"], {"category": "A", "score": 20})

        # Create view with filter (category=A) and sort (score desc)
        view = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/views",
                             json={"title": "FilteredSorted", "type": "grid"},
                             headers=h(key)).json()
        requests.post(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/filters",
            json={"columnId": cat_col["id"], "operator": "eq", "value": "A"},
            headers=h(key))
        requests.post(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/sorts",
            json={"columnId": score_col["id"], "direction": "desc"},
            headers=h(key))

        # Get records through view
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{table['id']}/views/{view['id']}/records",
            headers=h(key))
        records = resp.json()["records"]
        assert len(records) == 3  # Only category A
        scores = [r["score"] for r in records]
        assert scores == [30, 20, 10]  # Sorted desc


class TestCommentWorkflow:
    """Comments on records."""

    def test_comment_crud(self):
        """Pattern 1+4: Create and list comments with correct fields."""
        base = create_base()
        key = owner_key(base["id"])
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "task", "text")
        rec = create_record(base["id"], table["id"], {"task": "Do something"})

        # 1. Create comment
        resp = requests.post(
            f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}/comments",
            json={"body": "This needs review"}, headers=h(key))
        assert resp.status_code == 201
        comment = resp.json()
        assert "id" in comment
        assert comment["body"] == "This needs review"
        assert "userId" in comment
        assert "createdAt" in comment
        assert comment["recordId"] == rec["id"]

        # 2. List comments
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}/comments",
            headers=h(key))
        assert resp.status_code == 200
        comments = resp.json()["items"]
        assert any(c["id"] == comment["id"] for c in comments)

        # 3. Delete comment
        resp = requests.delete(
            f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}/comments/{comment['id']}",
            headers=h(key))
        assert resp.status_code == 204


class TestAuditTrailWorkflow:
    """Audit trail records all changes."""

    def test_crud_generates_audit_entries(self):
        """
        Pattern 7: Create, update, delete records -> each generates audit entry.
        """
        base = create_base()
        key = owner_key(base["id"])
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "val", "text")

        # 1. Create record
        rec = create_record(base["id"], table["id"], {"val": "original"})

        # 2. Update record
        requests.patch(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                       json={"val": "updated"}, headers=h(key))

        # 3. Delete record
        requests.delete(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
                        headers=h(key))

        # 4. Check audit log
        resp = requests.get(f"{API}/bases/{base['id']}/audit", headers=h(key))
        entries = resp.json()["items"]
        actions = [e["action"] for e in entries]
        assert "created" in actions
        assert "updated" in actions
        assert "deleted" in actions


class TestHookWorkflow:
    """Webhook CRUD."""

    def test_hook_lifecycle(self):
        """Pattern 1+4: Create, list, update, delete hooks."""
        base = create_base()
        key = owner_key(base["id"])
        table = create_table(base["id"])

        # 1. Create hook
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/hooks", json={
            "title": "Notify on Create",
            "event": "record.created",
            "url": "https://hooks.example.com/notify",
            "enabled": True
        }, headers=h(key))
        assert resp.status_code == 201
        hook = resp.json()
        assert hook["title"] == "Notify on Create"
        assert hook["event"] == "record.created"
        assert hook["enabled"] is True
        assert "id" in hook

        # 2. List hooks
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/hooks", headers=h(key))
        assert resp.status_code == 200
        hooks = resp.json()["items"]
        assert any(hk["id"] == hook["id"] for hk in hooks)

        # 3. Update hook
        resp = requests.patch(f"{API}/bases/{base['id']}/tables/{table['id']}/hooks/{hook['id']}",
                              json={"enabled": False}, headers=h(key))
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # 4. Delete hook
        resp = requests.delete(f"{API}/bases/{base['id']}/tables/{table['id']}/hooks/{hook['id']}",
                               headers=h(key))
        assert resp.status_code == 204


class TestMultiSelectAndTypes:
    """Various column types work correctly."""

    def test_multi_select_stores_array(self):
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "tags", "multiSelect",
                      options={"choices": ["urgent", "bug", "feature"]})

        rec = create_record(base["id"], table["id"], {"tags": ["urgent", "bug"]})
        resp = requests.get(
            f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec['id']}",
            headers=h(owner_key(base["id"])))
        data = resp.json()
        assert set(data["tags"]) == {"urgent", "bug"}


class TestRoleBasedWorkflow:
    """Full role hierarchy test."""

    def test_role_hierarchy_enforcement(self):
        """
        Pattern 6: Each role can do what's allowed and nothing more.
        """
        base = create_base()
        table = create_table(base["id"])
        create_column(base["id"], table["id"], "data", "text")

        # Editor can create record
        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/records",
                             json={"data": "editor data"},
                             headers=h(f"editor_{base['id']}_user3"))
        assert resp.status_code == 201
        rec_id = resp.json()["id"]

        # Viewer can read but not create
        resp = requests.get(f"{API}/bases/{base['id']}/tables/{table['id']}/records/{rec_id}",
                            headers=h(f"viewer_{base['id']}_user5"))
        assert resp.status_code == 200

        resp = requests.post(f"{API}/bases/{base['id']}/tables/{table['id']}/records",
                             json={"data": "no"},
                             headers=h(f"viewer_{base['id']}_user5"))
        assert resp.status_code == 403

        # Editor cannot create table (needs creator)
        resp = requests.post(f"{API}/bases/{base['id']}/tables",
                             json={"title": "nope"},
                             headers=h(f"editor_{base['id']}_user3"))
        assert resp.status_code == 403

        # Creator can create table
        resp = requests.post(f"{API}/bases/{base['id']}/tables",
                             json={"title": unique("cr_tbl")},
                             headers=h(f"creator_{base['id']}_user2"))
        assert resp.status_code == 201
