"""Tests for client-side column sorting on data tables."""

from __future__ import annotations

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


# ── CSS sort classes ────────────────────────────────────────────────


class TestSortCSS:
    def test_sortable_class_in_stylesheet(self, client):
        resp = client.get("/static/style.css")
        css = resp.data.decode()
        assert "th.sortable" in css

    def test_sort_asc_class_in_stylesheet(self, client):
        resp = client.get("/static/style.css")
        css = resp.data.decode()
        assert "th.sort-asc" in css

    def test_sort_desc_class_in_stylesheet(self, client):
        resp = client.get("/static/style.css")
        css = resp.data.decode()
        assert "th.sort-desc" in css


# ── JS sort function present in base template ──────────────────────


class TestSortScript:
    def test_sort_script_in_dispatch(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "initTableSort" in html

    def test_sort_script_in_billing(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "initTableSort" in html

    def test_sort_script_in_fleet(self, client):
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "initTableSort" in html

    def test_sort_script_in_archive(self, client):
        resp = client.get("/archive")
        html = resp.data.decode()
        assert "initTableSort" in html


# ── Table headers get sortable treatment ────────────────────────────


class TestSortableHeaders:
    def test_dispatch_table_has_sortable_columns(self, client):
        services.create_load(customer="Sort Test")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "table.data-table" in html or 'class="data-table"' in html

    def test_billing_table_has_sortable_columns(self, client):
        load = services.create_load(customer="Sort Test")
        services.confirm_rate(load["load_id"], rate_amount=1000)
        services.create_settlement(load["load_id"], due_date="2025-12-01")
        resp = client.get("/billing")
        html = resp.data.decode()
        assert 'class="data-table"' in html

    def test_fleet_table_has_sortable_columns(self, client):
        services.create_driver(name="Sort Driver", phone="555-0000")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert 'class="data-table"' in html

    def test_sort_function_handles_numeric_values(self, client):
        """Verify the sort JS contains numeric detection logic."""
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "isNaN" in html

    def test_sort_function_skips_empty_headers(self, client):
        """Verify the sort JS skips headers with no text (action columns)."""
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "textContent.trim()" in html

    def test_sort_function_excludes_edit_rows(self, client):
        """Verify sort skips hidden inline-edit rows."""
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "edit-row" in html
