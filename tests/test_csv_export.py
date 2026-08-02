"""Tests for CSV export endpoints (PR 36)."""

from __future__ import annotations

import csv
import io

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _parse_csv(data: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(data.decode()))
    return list(reader)


# ── Loads CSV Export ─────────────────────────────────────────────


class TestLoadsExport:
    def test_export_returns_csv(self, client):
        services.create_load(customer="Export Corp")
        resp = client.get("/api/dispatch/loads/export.csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"

    def test_export_has_content_disposition(self, client):
        resp = client.get("/api/dispatch/loads/export.csv")
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        assert "loads.csv" in resp.headers.get("Content-Disposition", "")

    def test_export_contains_header_row(self, client):
        resp = client.get("/api/dispatch/loads/export.csv")
        rows = _parse_csv(resp.data)
        assert isinstance(rows, list)

    def test_export_contains_load_data(self, client):
        services.create_load(customer="CSV Corp")
        resp = client.get("/api/dispatch/loads/export.csv")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["customer"] == "CSV Corp"

    def test_export_multiple_loads(self, client):
        services.create_load(customer="A Corp")
        services.create_load(customer="B Corp")
        resp = client.get("/api/dispatch/loads/export.csv")
        rows = _parse_csv(resp.data)
        assert len(rows) == 2

    def test_export_respects_status_filter(self, client):
        services.create_load(customer="Created")
        load2 = services.create_load(customer="Cancelled")
        services.update_load(load2["load_id"], status="cancelled")
        resp = client.get("/api/dispatch/loads/export.csv?status=cancelled")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["customer"] == "Cancelled"

    def test_export_respects_customer_filter(self, client):
        services.create_load(customer="Find Me")
        services.create_load(customer="Not Me")
        resp = client.get("/api/dispatch/loads/export.csv?customer=Find")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["customer"] == "Find Me"

    def test_export_has_expected_columns(self, client):
        services.create_load(customer="Columns Check")
        resp = client.get("/api/dispatch/loads/export.csv")
        rows = _parse_csv(resp.data)
        expected = {"load_id", "customer", "status", "pickup_location",
                    "delivery_location", "created_at"}
        assert expected.issubset(set(rows[0].keys()))

    def test_export_empty_returns_headers_only(self, client):
        resp = client.get("/api/dispatch/loads/export.csv")
        text = resp.data.decode()
        assert "load_id" in text
        rows = _parse_csv(resp.data)
        assert len(rows) == 0


# ── Settlements CSV Export ───────────────────────────────────────


def _create_invoiced_load(customer="Test Corp", rate=5000.0, due_date="2025-12-01"):
    load = services.create_load(customer=customer)
    services.confirm_rate(load["load_id"], rate_amount=rate)
    stl = services.create_settlement(load["load_id"], due_date=due_date)
    return load, stl


class TestSettlementsExport:
    def test_export_returns_csv(self, client):
        _create_invoiced_load()
        resp = client.get("/api/dispatch/settlements/export.csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"

    def test_export_has_content_disposition(self, client):
        resp = client.get("/api/dispatch/settlements/export.csv")
        assert "settlements.csv" in resp.headers.get("Content-Disposition", "")

    def test_export_contains_settlement_data(self, client):
        _, stl = _create_invoiced_load(customer="Invoice Corp", rate=7500.0)
        resp = client.get("/api/dispatch/settlements/export.csv")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["invoice_number"] == stl["invoice_number"]
        assert rows[0]["customer"] == "Invoice Corp"

    def test_export_includes_customer_column(self, client):
        _create_invoiced_load(customer="Customer Col")
        resp = client.get("/api/dispatch/settlements/export.csv")
        rows = _parse_csv(resp.data)
        assert "customer" in rows[0]
        assert rows[0]["customer"] == "Customer Col"

    def test_export_respects_status_filter(self, client):
        load1, _ = _create_invoiced_load(customer="Invoiced One")
        load2, _ = _create_invoiced_load(customer="Paid One")
        services.record_payment(load2["load_id"], payment_amount=5000.0)
        resp = client.get("/api/dispatch/settlements/export.csv?status=invoiced")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["customer"] == "Invoiced One"

    def test_export_respects_customer_filter(self, client):
        _create_invoiced_load(customer="Alpha Billing")
        _create_invoiced_load(customer="Beta Billing")
        resp = client.get("/api/dispatch/settlements/export.csv?customer=Alpha")
        rows = _parse_csv(resp.data)
        assert len(rows) == 1
        assert rows[0]["customer"] == "Alpha Billing"

    def test_export_empty(self, client):
        resp = client.get("/api/dispatch/settlements/export.csv")
        rows = _parse_csv(resp.data)
        assert len(rows) == 0


# ── Export button in UI ──────────────────────────────────────────


class TestExportButtons:
    def test_dispatch_page_has_export_button(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Export CSV</a>" in html
        assert "loads/export.csv" in html

    def test_billing_page_has_export_button(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Export CSV</a>" in html
        assert "settlements/export.csv" in html
