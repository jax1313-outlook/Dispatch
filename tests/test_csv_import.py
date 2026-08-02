"""Tests for CSV load import."""

from __future__ import annotations

import io

import pytest

from dispatch import services, store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _csv_bytes(content: str) -> bytes:
    return content.encode("utf-8")


# ── API Tests ────────────────────────────────────────────────────────


class TestCSVImportAPI:
    def test_import_single_load(self, client):
        csv = _csv_bytes(
            "customer,broker_shipper,pickup_location,delivery_location\n"
            "Acme Corp,Broker A,Chicago IL,Dallas TX\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["created"] == 1
        assert data["errors"] == []

        loads = store.list_loads()
        assert len(loads) == 1
        assert loads[0]["customer"] == "Acme Corp"
        assert loads[0]["broker_shipper"] == "Broker A"
        assert loads[0]["pickup_location"] == "Chicago IL"
        assert loads[0]["delivery_location"] == "Dallas TX"

    def test_import_multiple_loads(self, client):
        csv = _csv_bytes(
            "customer,pickup_location,delivery_location\n"
            "Customer A,Origin A,Dest A\n"
            "Customer B,Origin B,Dest B\n"
            "Customer C,Origin C,Dest C\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 3
        assert len(store.list_loads()) == 3

    def test_import_with_optional_fields(self, client):
        csv = _csv_bytes(
            "customer,pickup_datetime,delivery_datetime,equipment,driver,notes\n"
            "TestCo,2026-08-15,2026-08-16,Flatbed,John Doe,Fragile cargo\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1

        loads = store.list_loads()
        assert loads[0]["equipment"] == "Flatbed"
        assert loads[0]["driver"] == "John Doe"
        assert loads[0]["notes"] == "Fragile cargo"

    def test_import_missing_customer_column(self, client):
        csv = _csv_bytes(
            "pickup_location,delivery_location\n"
            "Chicago,Dallas\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "customer" in resp.get_json()["error"].lower()

    def test_import_empty_customer_value(self, client):
        csv = _csv_bytes(
            "customer,pickup_location\n"
            ",Chicago\n"
            "ValidCo,Dallas\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert "Row 2" in data["errors"][0]

    def test_import_no_file(self, client):
        resp = client.post(
            "/api/dispatch/loads/import",
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "file" in resp.get_json()["error"]

    def test_import_empty_csv(self, client):
        csv = _csv_bytes("")
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "empty.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "empty" in resp.get_json()["error"].lower()

    def test_import_extra_columns_ignored(self, client):
        csv = _csv_bytes(
            "customer,unknown_column,pickup_location\n"
            "TestCo,ignored_value,Chicago\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1

    def test_import_with_bom(self, client):
        csv = b"\xef\xbb\xbfcustomer,pickup_location\nBOM Corp,Chicago\n"
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1
        loads = store.list_loads()
        assert loads[0]["customer"] == "BOM Corp"

    def test_import_strips_whitespace(self, client):
        csv = _csv_bytes(
            "  customer  ,  pickup_location  \n"
            "  Acme  ,  Chicago IL  \n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1
        loads = store.list_loads()
        assert loads[0]["customer"] == "Acme"
        assert loads[0]["pickup_location"] == "Chicago IL"

    def test_import_case_insensitive_headers(self, client):
        csv = _csv_bytes(
            "Customer,Pickup_Location,Delivery_Location\n"
            "TestCo,Origin,Dest\n"
        )
        resp = client.post(
            "/api/dispatch/loads/import",
            data={"file": (io.BytesIO(csv), "loads.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert data["created"] == 1


# ── Dispatch Page UI ────────────────────────────────────────────────


class TestDispatchImportUI:
    def test_dispatch_page_has_import_button(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Import CSV" in html
        assert "toggleImportForm" in html

    def test_dispatch_page_has_import_form(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert 'id="import-csv-form"' in html
        assert 'id="csv-file"' in html
        assert "importCSV" in html

    def test_dispatch_page_import_help_text(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Required column" in html
        assert "customer" in html
