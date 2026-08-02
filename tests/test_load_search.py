"""Tests for load search and filtering (PR 27)."""

from __future__ import annotations

import json
import pytest

from dispatch import services, store as dispatch_store
from dispatch.db import get_connection, set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _create_load(customer="Acme Corp", **kw):
    return services.create_load(customer=customer, **kw)


# ── store.list_loads filtering ──────────────────────────────────────


class TestStoreListLoads:
    def test_filter_by_customer(self):
        _create_load(customer="Acme Corp")
        _create_load(customer="Beta Inc")
        _create_load(customer="Acme Widgets")

        results = dispatch_store.list_loads(customer="Acme")
        assert len(results) == 2
        names = {r["customer"] for r in results}
        assert names == {"Acme Corp", "Acme Widgets"}

    def test_filter_by_customer_case_insensitive(self):
        _create_load(customer="Acme Corp")
        results = dispatch_store.list_loads(customer="acme")
        assert len(results) == 1

    def test_filter_by_customer_no_match(self):
        _create_load(customer="Acme Corp")
        results = dispatch_store.list_loads(customer="Zebra")
        assert len(results) == 0

    def test_filter_by_date_from(self):
        load = _create_load(customer="DateTest")
        with get_connection() as conn:
            conn.execute(
                "UPDATE loads SET created_at=? WHERE load_id=?",
                ("2025-06-15T10:00:00Z", load["load_id"]),
            )
        _create_load(customer="Recent")

        results = dispatch_store.list_loads(date_from="2026-01-01")
        assert len(results) == 1
        assert results[0]["customer"] == "Recent"

    def test_filter_by_date_to(self):
        load = _create_load(customer="OldLoad")
        with get_connection() as conn:
            conn.execute(
                "UPDATE loads SET created_at=? WHERE load_id=?",
                ("2025-01-15T10:00:00Z", load["load_id"]),
            )
        _create_load(customer="NewLoad")

        results = dispatch_store.list_loads(date_to="2025-12-31")
        assert len(results) == 1
        assert results[0]["customer"] == "OldLoad"

    def test_filter_combined(self):
        l1 = _create_load(customer="Acme Corp")
        with get_connection() as conn:
            conn.execute(
                "UPDATE loads SET created_at=? WHERE load_id=?",
                ("2025-06-01T10:00:00Z", l1["load_id"]),
            )
        l2 = _create_load(customer="Acme Widgets")
        _create_load(customer="Beta Inc")

        results = dispatch_store.list_loads(customer="Acme", date_from="2026-01-01")
        assert len(results) == 1
        assert results[0]["customer"] == "Acme Widgets"

    def test_filter_status_and_customer(self):
        _create_load(customer="Acme Corp")
        _create_load(customer="Acme Widgets")

        results = dispatch_store.list_loads(status="created", customer="Acme")
        assert len(results) == 2

        results = dispatch_store.list_loads(status="dispatched", customer="Acme")
        assert len(results) == 0

    def test_no_filters_returns_all(self):
        _create_load(customer="A")
        _create_load(customer="B")
        results = dispatch_store.list_loads()
        assert len(results) == 2


# ── services.list_loads passthrough ─────────────────────────────────


class TestServicesListLoads:
    def test_passthrough_customer(self):
        _create_load(customer="Target Co")
        _create_load(customer="Other Co")
        results = services.list_loads(customer="Target")
        assert len(results) == 1
        assert results[0]["customer"] == "Target Co"

    def test_passthrough_all_params(self):
        _create_load(customer="X Corp")
        results = services.list_loads(
            status="created", customer="X", date_from="2020-01-01"
        )
        assert len(results) == 1


# ── API endpoint filtering ──────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestAPIListLoads:
    def test_filter_by_customer(self, client):
        _create_load(customer="Alpha LLC")
        _create_load(customer="Bravo Inc")

        resp = client.get("/api/dispatch/loads?customer=Alpha")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["loads"][0]["customer"] == "Alpha LLC"

    def test_filter_by_date_range(self, client):
        load = _create_load(customer="OldCo")
        with get_connection() as conn:
            conn.execute(
                "UPDATE loads SET created_at=? WHERE load_id=?",
                ("2025-03-01T10:00:00Z", load["load_id"]),
            )
        _create_load(customer="NewCo")

        resp = client.get("/api/dispatch/loads?date_from=2026-01-01")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["loads"][0]["customer"] == "NewCo"

    def test_combined_filters(self, client):
        _create_load(customer="Target Corp")
        _create_load(customer="Other Corp")

        resp = client.get("/api/dispatch/loads?status=created&customer=Target")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["loads"][0]["customer"] == "Target Corp"


# ── Dispatch page passes search params ──────────────────────────────


class TestDispatchPage:
    def test_search_params_in_context(self, client):
        _create_load(customer="SearchMe Inc")
        _create_load(customer="IgnoreMe LLC")

        resp = client.get("/dispatch?customer=SearchMe")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SearchMe" in html

    def test_date_filter_on_page(self, client):
        _create_load(customer="DatePageTest")
        resp = client.get("/dispatch?date_from=2020-01-01&date_to=2030-12-31")
        assert resp.status_code == 200

    def test_clear_link_present(self, client):
        _create_load(customer="ClearTest")
        resp = client.get("/dispatch?customer=ClearTest")
        html = resp.data.decode()
        assert "Clear" in html

    def test_no_clear_without_filters(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert html.count("Clear</a>") == 0
