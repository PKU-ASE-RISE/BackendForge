"""
Correctness tests for NocoDB API.
Tests cover: base/table/column CRUD, record CRUD with validation,
formula/lookup/rollup computation, views with filters/sorts,
role-based access control, shared views, comments, and audit log.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def owner_key(base_id, user="user1"):
    return f"owner_{base_id}_{user}"


def creator_key(base_id, user="user2"):
    return f"creator_{base_id}_{user}"


def editor_key(base_id, user="user3"):
    return f"editor_{base_id}_{user}"


def commenter_key(base_id, user="user4"):
    return f"commenter_{base_id}_{user}"


def viewer_key(base_id, user="user5"):
    return f"viewer_{base_id}_{user}"


def h(api_key):
    return {"X-API-Key": api_key}


# ========================== AUTH TESTS ==========================

class TestAuth:
    def test_missing_api_key_returns_401(self):
        resp = requests.get(f"{API}/bases")
        assert resp.status_code == 401

    def test_empty_api_key_returns_401(self):
        resp = requests.get(f"{API}/bases", headers={"X-API-Key": ""})
        assert resp.status_code == 401


# ========================== BASE TESTS ==========================

class TestBases:
    def test_create_and_get_base(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "My Project", "description": "Test base"}, headers=h(key))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Project"
        assert data["description"] == "Test base"
        assert "id" in data
        assert "createdAt" in data

        # Get it back
        base_id = data["id"]
        key2 = owner_key(base_id)
        resp2 = requests.get(f"{API}/bases/{base_id}", headers=h(key2))
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "My Project"

    def test_list_bases(self):
        key = owner_key("base1")
        requests.post(f"{API}/bases", json={"title": "Base A"}, headers=h(key))
        resp = requests.get(f"{API}/bases", headers=h(key))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_update_base(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "Original"}, headers=h(key))
        base_id = resp.json()["id"]
        key2 = owner_key(base_id)
        resp2 = requests.patch(f"{API}/bases/{base_id}", json={"title": "Updated"}, headers=h(key2))
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "Updated"

    def test_delete_base(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "ToDelete"}, headers=h(key))
        base_id = resp.json()["id"]
        key2 = owner_key(base_id)
        resp2 = requests.delete(f"{API}/bases/{base_id}", headers=h(key2))
        assert resp2.status_code == 204

        resp3 = requests.get(f"{API}/bases/{base_id}", headers=h(key2))
        assert resp3.status_code == 404

    def test_get_nonexistent_base_returns_404(self):
        key = owner_key("nonexistent")
        resp = requests.get(f"{API}/bases/nonexistent", headers=h(key))
        assert resp.status_code == 404


# ========================== TABLE TESTS ==========================

class TestTables:
    @pytest.fixture
    def base(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "TableTestBase"}, headers=h(key))
        return resp.json()

    def test_create_and_list_tables(self, base):
        base_id = base["id"]
        key = creator_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "Users"}, headers=h(key))
        assert resp.status_code == 201
        table = resp.json()
        assert table["title"] == "Users"
        assert table["baseId"] == base_id

        resp2 = requests.get(f"{API}/bases/{base_id}/tables", headers=h(key))
        assert resp2.status_code == 200
        assert len(resp2.json()["items"]) >= 1

    def test_update_table(self, base):
        base_id = base["id"]
        key = creator_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "OldName"}, headers=h(key))
        table_id = resp.json()["id"]
        resp2 = requests.patch(f"{API}/bases/{base_id}/tables/{table_id}", json={"title": "NewName"}, headers=h(key))
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "NewName"

    def test_delete_table(self, base):
        base_id = base["id"]
        key = creator_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "ToDelete"}, headers=h(key))
        table_id = resp.json()["id"]
        resp2 = requests.delete(f"{API}/bases/{base_id}/tables/{table_id}", headers=h(key))
        assert resp2.status_code == 204


# ========================== COLUMN TESTS ==========================

class TestColumns:
    @pytest.fixture
    def table(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "ColTestBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key2 = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "TestTable"}, headers=h(key2))
        return {"baseId": base_id, "tableId": resp2.json()["id"]}

    def test_create_text_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "Name", "type": "text"},
            headers=h(key)
        )
        assert resp.status_code == 201
        col = resp.json()
        assert col["title"] == "Name"
        assert col["type"] == "text"

    def test_create_number_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "Age", "type": "number"},
            headers=h(key)
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "number"

    def test_create_single_select_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "Status", "type": "singleSelect", "options": {"choices": ["active", "inactive", "pending"]}},
            headers=h(key)
        )
        assert resp.status_code == 201
        col = resp.json()
        assert col["type"] == "singleSelect"
        assert "choices" in col["options"]

    def test_create_multi_select_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "Tags", "type": "multiSelect", "options": {"choices": ["frontend", "backend", "devops"]}},
            headers=h(key)
        )
        assert resp.status_code == 201
        assert resp.json()["type"] == "multiSelect"

    def test_list_columns(self, table):
        key = creator_key(table["baseId"])
        requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "Col1", "type": "text"},
            headers=h(key)
        )
        resp = requests.get(f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns", headers=h(key))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1

    def test_update_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "OldCol", "type": "text"},
            headers=h(key)
        )
        col_id = resp.json()["id"]
        resp2 = requests.patch(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns/{col_id}",
            json={"title": "NewCol"},
            headers=h(key)
        )
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "NewCol"

    def test_delete_column(self, table):
        key = creator_key(table["baseId"])
        resp = requests.post(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns",
            json={"title": "DelCol", "type": "text"},
            headers=h(key)
        )
        col_id = resp.json()["id"]
        resp2 = requests.delete(
            f"{API}/bases/{table['baseId']}/tables/{table['tableId']}/columns/{col_id}",
            headers=h(key)
        )
        assert resp2.status_code == 204


# ========================== RECORD TESTS ==========================

class TestRecords:
    @pytest.fixture
    def setup(self):
        """Create a base, table, and columns for record tests."""
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "RecordTestBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "People"}, headers=h(key_c))
        table_id = resp2.json()["id"]

        # Create columns
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Name", "type": "text"}, headers=h(key_c))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Age", "type": "number"}, headers=h(key_c))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Email", "type": "email"}, headers=h(key_c))

        return {"baseId": base_id, "tableId": table_id}

    def test_create_and_get_record(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = editor_key(base_id)
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/records",
            json={"Name": "Alice", "Age": 30, "Email": "alice@example.com"},
            headers=h(key)
        )
        assert resp.status_code == 201
        record = resp.json()
        assert record["Name"] == "Alice"
        assert record["Age"] == 30
        assert "id" in record

        # Get it
        record_id = record["id"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key))
        assert resp2.status_code == 200
        assert resp2.json()["Name"] == "Alice"

    def test_list_records(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = editor_key(base_id)
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Name": "Bob", "Age": 25, "Email": "bob@example.com"}, headers=h(key))
        resp = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records", headers=h(key))
        assert resp.status_code == 200
        assert "records" in resp.json()
        assert len(resp.json()["records"]) >= 1

    def test_update_record(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Name": "Charlie", "Age": 35, "Email": "charlie@example.com"}, headers=h(key))
        record_id = resp.json()["id"]
        resp2 = requests.patch(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}",
                               json={"Age": 36}, headers=h(key))
        assert resp2.status_code == 200
        assert resp2.json()["Age"] == 36
        assert resp2.json()["Name"] == "Charlie"

    def test_delete_record(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Name": "Dave", "Age": 40, "Email": "dave@example.com"}, headers=h(key))
        record_id = resp.json()["id"]
        resp2 = requests.delete(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key))
        assert resp2.status_code == 204

        resp3 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key))
        assert resp3.status_code == 404


# ========================== FIELD VALIDATION TESTS ==========================

class TestFieldValidation:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "ValidationBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "ValTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        return {"baseId": base_id, "tableId": table_id, "creatorKey": key_c}

    def test_number_rejects_text(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Score", "type": "number"}, headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Score": "not a number"}, headers=h(key_e))
        assert resp.status_code == 400

    def test_email_validates_format(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Contact", "type": "email"}, headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Contact": "not-an-email"}, headers=h(key_e))
        assert resp.status_code == 400

    def test_email_accepts_valid(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Mail", "type": "email"}, headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Mail": "valid@example.com"}, headers=h(key_e))
        assert resp.status_code == 201

    def test_single_select_rejects_invalid_option(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Priority", "type": "singleSelect", "options": {"choices": ["low", "medium", "high"]}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Priority": "critical"}, headers=h(key_e))
        assert resp.status_code == 400

    def test_single_select_accepts_valid_option(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Level", "type": "singleSelect", "options": {"choices": ["a", "b", "c"]}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Level": "b"}, headers=h(key_e))
        assert resp.status_code == 201
        assert resp.json()["Level"] == "b"

    def test_multi_select_rejects_invalid_option(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Skills", "type": "multiSelect", "options": {"choices": ["python", "java", "go"]}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Skills": ["python", "rust"]}, headers=h(key_e))
        assert resp.status_code == 400

    def test_checkbox_field(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Active", "type": "checkbox"}, headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Active": True}, headers=h(key_e))
        assert resp.status_code == 201
        assert resp.json()["Active"] is True


# ========================== FORMULA TESTS ==========================

class TestFormulas:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "FormulaBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "FormulaTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]

        # Create text columns
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "FirstName", "type": "text"}, headers=h(key_c))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "LastName", "type": "text"}, headers=h(key_c))
        # Create number columns
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Price", "type": "number"}, headers=h(key_c))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Quantity", "type": "number"}, headers=h(key_c))

        return {"baseId": base_id, "tableId": table_id, "creatorKey": key_c}

    def test_concat_formula(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        # Create formula column
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "FullName", "type": "formula",
                            "options": {"expression": 'CONCAT(FirstName, " ", LastName)'}},
                      headers=h(key_c))
        # Add a record
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"FirstName": "John", "LastName": "Doe", "Price": 10, "Quantity": 2},
                             headers=h(key_e))
        assert resp.status_code == 201
        record_id = resp.json()["id"]

        # Read the record and check formula
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key_e))
        assert resp2.json()["FullName"] == "John Doe"

    def test_add_formula(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Total", "type": "formula",
                            "options": {"expression": "ADD(Price, Quantity)"}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"FirstName": "X", "LastName": "Y", "Price": 100, "Quantity": 5},
                             headers=h(key_e))
        record_id = resp.json()["id"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key_e))
        assert resp2.json()["Total"] == 105

    def test_upper_formula(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "UpperFirst", "type": "formula",
                            "options": {"expression": "UPPER(FirstName)"}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"FirstName": "alice", "LastName": "smith", "Price": 1, "Quantity": 1},
                             headers=h(key_e))
        record_id = resp.json()["id"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key_e))
        assert resp2.json()["UpperFirst"] == "ALICE"

    def test_len_formula(self, setup):
        base_id, table_id, key_c = setup["baseId"], setup["tableId"], setup["creatorKey"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "NameLen", "type": "formula",
                            "options": {"expression": "LEN(FirstName)"}},
                      headers=h(key_c))
        key_e = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"FirstName": "hello", "LastName": "world", "Price": 1, "Quantity": 1},
                             headers=h(key_e))
        record_id = resp.json()["id"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key_e))
        assert resp2.json()["NameLen"] == 5


# ========================== LINK / LOOKUP / ROLLUP TESTS ==========================

class TestLinksLookupRollup:
    @pytest.fixture
    def setup(self):
        """Create two tables: Orders and Products with a link between them."""
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "LinkBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)

        # Create Products table
        resp_p = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "Products"}, headers=h(key_c))
        products_table_id = resp_p.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{products_table_id}/columns",
                      json={"title": "ProductName", "type": "text"}, headers=h(key_c))
        requests.post(f"{API}/bases/{base_id}/tables/{products_table_id}/columns",
                      json={"title": "Price", "type": "number"}, headers=h(key_c))

        # Create Orders table
        resp_o = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "Orders"}, headers=h(key_c))
        orders_table_id = resp_o.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{orders_table_id}/columns",
                      json={"title": "OrderName", "type": "text"}, headers=h(key_c))

        # Create link column from Orders to Products
        resp_link = requests.post(f"{API}/bases/{base_id}/tables/{orders_table_id}/columns",
                                  json={"title": "LinkedProducts", "type": "link",
                                        "options": {"linkedTableId": products_table_id}},
                                  headers=h(key_c))
        link_col_id = resp_link.json()["id"]

        return {
            "baseId": base_id,
            "productsTableId": products_table_id,
            "ordersTableId": orders_table_id,
            "linkColId": link_col_id,
            "creatorKey": key_c
        }

    def test_link_records(self, setup):
        base_id = setup["baseId"]
        key_e = editor_key(base_id)
        key_c = setup["creatorKey"]
        products_tid = setup["productsTableId"]
        orders_tid = setup["ordersTableId"]

        # Create products
        r1 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "Widget", "Price": 10}, headers=h(key_e))
        r2 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "Gadget", "Price": 20}, headers=h(key_e))
        pid1, pid2 = r1.json()["id"], r2.json()["id"]

        # Create order linked to products
        resp = requests.post(f"{API}/bases/{base_id}/tables/{orders_tid}/records",
                             json={"OrderName": "Order1", "LinkedProducts": [pid1, pid2]}, headers=h(key_e))
        assert resp.status_code == 201
        order = resp.json()
        assert set(order["LinkedProducts"]) == {pid1, pid2}

    def test_lookup_field(self, setup):
        base_id = setup["baseId"]
        key_e = editor_key(base_id)
        key_c = setup["creatorKey"]
        products_tid = setup["productsTableId"]
        orders_tid = setup["ordersTableId"]
        link_col_id = setup["linkColId"]

        # Get product name column ID
        cols_resp = requests.get(f"{API}/bases/{base_id}/tables/{products_tid}/columns", headers=h(key_c))
        prod_name_col = next(c for c in cols_resp.json()["items"] if c["title"] == "ProductName")

        # Create lookup column on Orders
        requests.post(f"{API}/bases/{base_id}/tables/{orders_tid}/columns",
                      json={"title": "ProductNames", "type": "lookup",
                            "options": {"linkColumnId": link_col_id, "lookupColumnId": prod_name_col["id"]}},
                      headers=h(key_c))

        # Create products and linked order
        r1 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "Alpha", "Price": 5}, headers=h(key_e))
        r2 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "Beta", "Price": 15}, headers=h(key_e))
        pid1, pid2 = r1.json()["id"], r2.json()["id"]

        resp = requests.post(f"{API}/bases/{base_id}/tables/{orders_tid}/records",
                             json={"OrderName": "Order2", "LinkedProducts": [pid1, pid2]}, headers=h(key_e))
        record_id = resp.json()["id"]

        # Read back and check lookup
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{orders_tid}/records/{record_id}", headers=h(key_e))
        lookup_val = resp2.json()["ProductNames"]
        assert sorted(lookup_val) == ["Alpha", "Beta"]

    def test_rollup_field(self, setup):
        base_id = setup["baseId"]
        key_e = editor_key(base_id)
        key_c = setup["creatorKey"]
        products_tid = setup["productsTableId"]
        orders_tid = setup["ordersTableId"]
        link_col_id = setup["linkColId"]

        # Get Price column ID
        cols_resp = requests.get(f"{API}/bases/{base_id}/tables/{products_tid}/columns", headers=h(key_c))
        price_col = next(c for c in cols_resp.json()["items"] if c["title"] == "Price")

        # Create rollup column (SUM of Price)
        requests.post(f"{API}/bases/{base_id}/tables/{orders_tid}/columns",
                      json={"title": "TotalPrice", "type": "rollup",
                            "options": {"linkColumnId": link_col_id, "rollupColumnId": price_col["id"],
                                        "aggregation": "SUM"}},
                      headers=h(key_c))

        # Create products
        r1 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "X", "Price": 30}, headers=h(key_e))
        r2 = requests.post(f"{API}/bases/{base_id}/tables/{products_tid}/records",
                           json={"ProductName": "Y", "Price": 70}, headers=h(key_e))
        pid1, pid2 = r1.json()["id"], r2.json()["id"]

        resp = requests.post(f"{API}/bases/{base_id}/tables/{orders_tid}/records",
                             json={"OrderName": "Order3", "LinkedProducts": [pid1, pid2]}, headers=h(key_e))
        record_id = resp.json()["id"]

        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{orders_tid}/records/{record_id}", headers=h(key_e))
        assert resp2.json()["TotalPrice"] == 100


# ========================== VIEW TESTS ==========================

class TestViews:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "ViewBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "ViewTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]

        # Create columns
        resp_col = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                                 json={"title": "Name", "type": "text"}, headers=h(key_c))
        name_col_id = resp_col.json()["id"]
        resp_col2 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                                  json={"title": "Score", "type": "number"}, headers=h(key_c))
        score_col_id = resp_col2.json()["id"]

        # Add records
        key_e = editor_key(base_id)
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Name": "Alice", "Score": 90}, headers=h(key_e))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Name": "Bob", "Score": 60}, headers=h(key_e))
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Name": "Charlie", "Score": 80}, headers=h(key_e))

        return {
            "baseId": base_id, "tableId": table_id,
            "nameColId": name_col_id, "scoreColId": score_col_id,
            "creatorKey": key_c, "editorKey": key_e
        }

    def test_create_view(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_c = setup["creatorKey"]
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                             json={"title": "High Scorers", "type": "grid"}, headers=h(key_c))
        assert resp.status_code == 201
        assert resp.json()["type"] == "grid"

    def test_view_with_filter(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_c = setup["creatorKey"]
        score_col_id = setup["scoreColId"]

        # Create view
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                             json={"title": "TopScorers", "type": "grid"}, headers=h(key_c))
        view_id = resp.json()["id"]

        # Add filter: Score > 70
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters",
                      json={"columnId": score_col_id, "operator": "gt", "value": 70},
                      headers=h(key_c))

        # Query through view
        key_e = setup["editorKey"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/records", headers=h(key_e))
        assert resp2.status_code == 200
        records = resp2.json()["records"]
        # Only Alice (90) and Charlie (80) should pass
        assert len(records) == 2
        names = [r["Name"] for r in records]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names

    def test_view_with_sort(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_c = setup["creatorKey"]
        score_col_id = setup["scoreColId"]

        # Create view
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                             json={"title": "SortedView", "type": "grid"}, headers=h(key_c))
        view_id = resp.json()["id"]

        # Add sort: Score descending
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts",
                      json={"columnId": score_col_id, "direction": "desc"},
                      headers=h(key_c))

        key_e = setup["editorKey"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/records", headers=h(key_e))
        records = resp2.json()["records"]
        scores = [r["Score"] for r in records]
        assert scores == sorted(scores, reverse=True)

    def test_view_filter_and_sort_combined(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_c = setup["creatorKey"]
        score_col_id = setup["scoreColId"]
        name_col_id = setup["nameColId"]

        # Create view
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                             json={"title": "FilterSort", "type": "grid"}, headers=h(key_c))
        view_id = resp.json()["id"]

        # Filter: Score >= 60
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters",
                      json={"columnId": score_col_id, "operator": "gte", "value": 60},
                      headers=h(key_c))
        # Sort: Name ascending
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts",
                      json={"columnId": name_col_id, "direction": "asc"},
                      headers=h(key_c))

        key_e = setup["editorKey"]
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/records", headers=h(key_e))
        records = resp2.json()["records"]
        names = [r["Name"] for r in records]
        # All three pass (>=60), sorted alphabetically
        assert names == ["Alice", "Bob", "Charlie"]

    def test_list_and_delete_view(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_c = setup["creatorKey"]
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                             json={"title": "TempView", "type": "gallery"}, headers=h(key_c))
        view_id = resp.json()["id"]

        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/views", headers=h(key_c))
        assert any(v["id"] == view_id for v in resp2.json()["items"])

        resp3 = requests.delete(f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}", headers=h(key_c))
        assert resp3.status_code == 204


# ========================== FILTER CRUD TESTS ==========================

class TestFilterCRUD:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "FilterCRUDBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "FTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        resp3 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                              json={"title": "Val", "type": "number"}, headers=h(key_c))
        col_id = resp3.json()["id"]
        resp4 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                              json={"title": "FView", "type": "grid"}, headers=h(key_c))
        view_id = resp4.json()["id"]
        return {"baseId": base_id, "tableId": table_id, "viewId": view_id,
                "colId": col_id, "creatorKey": key_c}

    def test_create_get_update_delete_filter(self, setup):
        base_id, table_id, view_id = setup["baseId"], setup["tableId"], setup["viewId"]
        col_id, key_c = setup["colId"], setup["creatorKey"]

        # Create
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters",
            json={"columnId": col_id, "operator": "gt", "value": 10},
            headers=h(key_c))
        assert resp.status_code == 201
        filt = resp.json()
        filt_id = filt["id"]
        assert filt["operator"] == "gt"

        # Get
        resp2 = requests.get(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters/{filt_id}",
            headers=h(key_c))
        assert resp2.status_code == 200
        assert resp2.json()["operator"] == "gt"

        # Update
        resp3 = requests.patch(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters/{filt_id}",
            json={"operator": "lt", "value": 5},
            headers=h(key_c))
        assert resp3.status_code == 200
        assert resp3.json()["operator"] == "lt"

        # Delete
        resp4 = requests.delete(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/filters/{filt_id}",
            headers=h(key_c))
        assert resp4.status_code == 204


# ========================== SORT CRUD TESTS ==========================

class TestSortCRUD:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "SortCRUDBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "STable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        resp3 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                              json={"title": "Val", "type": "number"}, headers=h(key_c))
        col_id = resp3.json()["id"]
        resp4 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                              json={"title": "SView", "type": "grid"}, headers=h(key_c))
        view_id = resp4.json()["id"]
        return {"baseId": base_id, "tableId": table_id, "viewId": view_id,
                "colId": col_id, "creatorKey": key_c}

    def test_create_get_update_delete_sort(self, setup):
        base_id, table_id, view_id = setup["baseId"], setup["tableId"], setup["viewId"]
        col_id, key_c = setup["colId"], setup["creatorKey"]

        # Create
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts",
            json={"columnId": col_id, "direction": "asc"},
            headers=h(key_c))
        assert resp.status_code == 201
        sort = resp.json()
        sort_id = sort["id"]
        assert sort["direction"] == "asc"

        # Get
        resp2 = requests.get(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts/{sort_id}",
            headers=h(key_c))
        assert resp2.status_code == 200

        # Update
        resp3 = requests.patch(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts/{sort_id}",
            json={"direction": "desc"},
            headers=h(key_c))
        assert resp3.status_code == 200
        assert resp3.json()["direction"] == "desc"

        # Delete
        resp4 = requests.delete(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/sorts/{sort_id}",
            headers=h(key_c))
        assert resp4.status_code == 204


# ========================== ROLE ENFORCEMENT TESTS ==========================

class TestRoleEnforcement:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "RoleBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "RoleTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Data", "type": "text"}, headers=h(key_c))
        return {"baseId": base_id, "tableId": table_id}

    def test_viewer_cannot_create_record(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = viewer_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Data": "test"}, headers=h(key))
        assert resp.status_code == 403

    def test_viewer_can_read_records(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key_e = editor_key(base_id)
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Data": "hello"}, headers=h(key_e))
        key_v = viewer_key(base_id)
        resp = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/records", headers=h(key_v))
        assert resp.status_code == 200

    def test_editor_cannot_create_table(self, setup):
        base_id = setup["baseId"]
        key = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables",
                             json={"title": "Nope"}, headers=h(key))
        assert resp.status_code == 403

    def test_editor_cannot_create_column(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = editor_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                             json={"title": "Nope", "type": "text"}, headers=h(key))
        assert resp.status_code == 403

    def test_commenter_cannot_create_record(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = commenter_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                             json={"Data": "nope"}, headers=h(key))
        assert resp.status_code == 403

    def test_creator_cannot_delete_base(self, setup):
        base_id = setup["baseId"]
        key = creator_key(base_id)
        resp = requests.delete(f"{API}/bases/{base_id}", headers=h(key))
        assert resp.status_code == 403


# ========================== SHARED VIEW TESTS ==========================

class TestSharedViews:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "ShareBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "ShareTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Info", "type": "text"}, headers=h(key_c))
        key_e = editor_key(base_id)
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                      json={"Info": "public data"}, headers=h(key_e))

        # Create view
        resp3 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/views",
                              json={"title": "PublicView", "type": "grid"}, headers=h(key_c))
        view_id = resp3.json()["id"]

        return {"baseId": base_id, "tableId": table_id, "viewId": view_id,
                "ownerKey": owner_key(base_id)}

    def test_share_without_password(self, setup):
        base_id, table_id, view_id = setup["baseId"], setup["tableId"], setup["viewId"]
        key = setup["ownerKey"]

        # Create share
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/shares",
            json={}, headers=h(key))
        assert resp.status_code == 201
        share = resp.json()
        uuid = share["uuid"]

        # Access without auth
        resp2 = requests.get(f"{API}/shared/{uuid}/records")
        assert resp2.status_code == 200
        assert len(resp2.json()["records"]) >= 1

    def test_share_with_password(self, setup):
        base_id, table_id, view_id = setup["baseId"], setup["tableId"], setup["viewId"]
        key = setup["ownerKey"]

        # Create share with password
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/shares",
            json={"password": "secret123"}, headers=h(key))
        assert resp.status_code == 201
        uuid = resp.json()["uuid"]

        # Access without password — should fail
        resp2 = requests.get(f"{API}/shared/{uuid}/records")
        assert resp2.status_code == 401

        # Access with wrong password
        resp3 = requests.get(f"{API}/shared/{uuid}/records", params={"password": "wrong"})
        assert resp3.status_code == 401

        # Access with correct password
        resp4 = requests.get(f"{API}/shared/{uuid}/records", params={"password": "secret123"})
        assert resp4.status_code == 200
        assert len(resp4.json()["records"]) >= 1

    def test_share_not_found(self):
        resp = requests.get(f"{API}/shared/nonexistent-uuid/records")
        assert resp.status_code == 404

    def test_delete_share(self, setup):
        base_id, table_id, view_id = setup["baseId"], setup["tableId"], setup["viewId"]
        key = setup["ownerKey"]

        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/shares",
            json={}, headers=h(key))
        share_id = resp.json()["id"]
        uuid = resp.json()["uuid"]

        resp2 = requests.delete(
            f"{API}/bases/{base_id}/tables/{table_id}/views/{view_id}/shares/{share_id}",
            headers=h(key))
        assert resp2.status_code == 204

        # Access after delete should fail
        resp3 = requests.get(f"{API}/shared/{uuid}/records")
        assert resp3.status_code == 404


# ========================== HOOK TESTS ==========================

class TestHooks:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "HookBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "HookTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        return {"baseId": base_id, "tableId": table_id, "ownerKey": owner_key(base_id)}

    def test_hook_crud(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = setup["ownerKey"]

        # Create
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/hooks",
                             json={"title": "OnCreate", "event": "record.created",
                                   "url": "https://example.com/hook"},
                             headers=h(key))
        assert resp.status_code == 201
        hook = resp.json()
        hook_id = hook["id"]
        assert hook["event"] == "record.created"
        assert hook["enabled"] is True

        # List
        resp2 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/hooks", headers=h(key))
        assert resp2.status_code == 200
        assert len(resp2.json()["items"]) >= 1

        # Get
        resp3 = requests.get(f"{API}/bases/{base_id}/tables/{table_id}/hooks/{hook_id}", headers=h(key))
        assert resp3.status_code == 200
        assert resp3.json()["title"] == "OnCreate"

        # Update
        resp4 = requests.patch(f"{API}/bases/{base_id}/tables/{table_id}/hooks/{hook_id}",
                               json={"enabled": False}, headers=h(key))
        assert resp4.status_code == 200
        assert resp4.json()["enabled"] is False

        # Delete
        resp5 = requests.delete(f"{API}/bases/{base_id}/tables/{table_id}/hooks/{hook_id}", headers=h(key))
        assert resp5.status_code == 204

    def test_non_owner_cannot_manage_hooks(self, setup):
        base_id, table_id = setup["baseId"], setup["tableId"]
        key = creator_key(base_id)
        resp = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/hooks",
                             json={"title": "X", "event": "record.created",
                                   "url": "https://example.com/x"},
                             headers=h(key))
        assert resp.status_code == 403


# ========================== COMMENT TESTS ==========================

class TestComments:
    @pytest.fixture
    def setup(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "CommentBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "CommentTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Note", "type": "text"}, headers=h(key_c))
        key_e = editor_key(base_id)
        resp3 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                              json={"Note": "something"}, headers=h(key_e))
        record_id = resp3.json()["id"]
        return {"baseId": base_id, "tableId": table_id, "recordId": record_id}

    def test_create_and_list_comments(self, setup):
        base_id, table_id, record_id = setup["baseId"], setup["tableId"], setup["recordId"]
        key = commenter_key(base_id)

        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}/comments",
            json={"body": "This looks good!"}, headers=h(key))
        assert resp.status_code == 201
        comment = resp.json()
        assert comment["body"] == "This looks good!"
        assert "id" in comment
        assert comment["userId"] == "user4"

        resp2 = requests.get(
            f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}/comments",
            headers=h(key))
        assert resp2.status_code == 200
        assert len(resp2.json()["items"]) >= 1

    def test_viewer_cannot_comment(self, setup):
        base_id, table_id, record_id = setup["baseId"], setup["tableId"], setup["recordId"]
        key = viewer_key(base_id)
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}/comments",
            json={"body": "nope"}, headers=h(key))
        assert resp.status_code == 403

    def test_delete_comment(self, setup):
        base_id, table_id, record_id = setup["baseId"], setup["tableId"], setup["recordId"]
        key_comm = commenter_key(base_id)
        resp = requests.post(
            f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}/comments",
            json={"body": "delete me"}, headers=h(key_comm))
        comment_id = resp.json()["id"]

        key_owner = owner_key(base_id)
        resp2 = requests.delete(
            f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}/comments/{comment_id}",
            headers=h(key_owner))
        assert resp2.status_code == 204


# ========================== AUDIT LOG TESTS ==========================

class TestAuditLog:
    def test_audit_log_on_record_operations(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "AuditBase"}, headers=h(key))
        base_id = resp.json()["id"]
        key_c = creator_key(base_id)
        resp2 = requests.post(f"{API}/bases/{base_id}/tables", json={"title": "AuditTable"}, headers=h(key_c))
        table_id = resp2.json()["id"]
        requests.post(f"{API}/bases/{base_id}/tables/{table_id}/columns",
                      json={"title": "Val", "type": "text"}, headers=h(key_c))

        key_e = editor_key(base_id)
        # Create record
        resp3 = requests.post(f"{API}/bases/{base_id}/tables/{table_id}/records",
                              json={"Val": "initial"}, headers=h(key_e))
        record_id = resp3.json()["id"]

        # Update record
        requests.patch(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}",
                       json={"Val": "updated"}, headers=h(key_e))

        # Delete record
        requests.delete(f"{API}/bases/{base_id}/tables/{table_id}/records/{record_id}", headers=h(key_e))

        # Check audit log
        key_o = owner_key(base_id)
        resp4 = requests.get(f"{API}/bases/{base_id}/audit", headers=h(key_o))
        assert resp4.status_code == 200
        entries = resp4.json()["items"]
        actions = [e["action"] for e in entries]
        assert "created" in actions
        assert "updated" in actions
        assert "deleted" in actions

    def test_audit_log_requires_owner_or_creator(self):
        key = owner_key("base1")
        resp = requests.post(f"{API}/bases", json={"title": "AuditBase2"}, headers=h(key))
        base_id = resp.json()["id"]

        key_v = viewer_key(base_id)
        resp2 = requests.get(f"{API}/bases/{base_id}/audit", headers=h(key_v))
        assert resp2.status_code == 403
