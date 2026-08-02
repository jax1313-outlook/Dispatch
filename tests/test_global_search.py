"""Tests for global search: API endpoint, page route, and store function."""

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


# ── Store-level search ────────────────────────────────────────────────


class TestGlobalSearchStore:
    def test_finds_loads_by_customer(self):
        from dispatch.store import global_search
        services.create_load(customer="Acme Freight")
        results = global_search("Acme")
        assert len(results["loads"]) == 1
        assert results["loads"][0]["customer"] == "Acme Freight"

    def test_finds_drivers_by_name(self):
        from dispatch.store import global_search
        services.create_driver(name="John Smith")
        results = global_search("John")
        assert len(results["drivers"]) == 1
        assert results["drivers"][0]["name"] == "John Smith"

    def test_finds_equipment_by_unit(self):
        from dispatch.store import global_search
        services.create_equipment(unit_number="TRUCK-99", equipment_type="dry_van")
        results = global_search("TRUCK-99")
        assert len(results["equipment"]) == 1

    def test_finds_settlements_by_invoice(self):
        from dispatch.store import global_search
        load = services.create_load(customer="Invoice Co")
        services.confirm_rate(load["load_id"], rate_amount=1000)
        stl = services.create_settlement(load["load_id"])
        results = global_search(stl["invoice_number"][:8])
        assert len(results["settlements"]) >= 1

    def test_cross_entity_search(self):
        from dispatch.store import global_search
        services.create_load(customer="Universal Corp")
        services.create_driver(name="Universal Driver", email="universal@test.com")
        results = global_search("Universal")
        assert len(results["loads"]) == 1
        assert len(results["drivers"]) == 1

    def test_no_results(self):
        from dispatch.store import global_search
        results = global_search("XYZNONEXISTENT")
        assert all(len(v) == 0 for v in results.values())

    def test_finds_by_location(self):
        from dispatch.store import global_search
        services.create_load(customer="Location Co", pickup_location="Chicago, IL")
        results = global_search("Chicago")
        assert len(results["loads"]) == 1

    def test_finds_driver_by_phone(self):
        from dispatch.store import global_search
        services.create_driver(name="Phone Test", phone="555-867-5309")
        results = global_search("867-5309")
        assert len(results["drivers"]) == 1

    def test_finds_equipment_by_vin(self):
        from dispatch.store import global_search
        services.create_equipment(
            unit_number="VIN-TEST", equipment_type="reefer",
            vin="1HGCM82633A123456",
        )
        results = global_search("1HGCM82633A")
        assert len(results["equipment"]) == 1


# ── API endpoint ──────────────────────────────────────────────────────


class TestGlobalSearchAPI:
    def test_search_returns_results(self, client):
        services.create_load(customer="API Search Co")
        resp = client.get("/api/dispatch/search?q=API Search")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        assert data["query"] == "API Search"
        assert len(data["loads"]) >= 1

    def test_missing_query(self, client):
        resp = client.get("/api/dispatch/search")
        assert resp.status_code == 400

    def test_short_query(self, client):
        resp = client.get("/api/dispatch/search?q=X")
        assert resp.status_code == 400

    def test_empty_query(self, client):
        resp = client.get("/api/dispatch/search?q=")
        assert resp.status_code == 400

    def test_no_results(self, client):
        resp = client.get("/api/dispatch/search?q=ZZZNONEXISTENT")
        data = resp.get_json()
        assert data["total"] == 0


# ── Search page ──────────────────────────────────────────────────────


class TestSearchPage:
    def test_page_loads_empty(self, client):
        resp = client.get("/search")
        assert resp.status_code == 200
        assert b"Search" in resp.data

    def test_page_with_query(self, client):
        services.create_load(customer="Page Search Corp")
        resp = client.get("/search?q=Page Search")
        assert resp.status_code == 200
        assert b"Page Search Corp" in resp.data

    def test_page_no_results(self, client):
        resp = client.get("/search?q=ZZZNOMATCH")
        assert resp.status_code == 200
        assert b"No results found" in resp.data

    def test_page_short_query(self, client):
        resp = client.get("/search?q=X")
        assert resp.status_code == 200
        assert b"at least 2 characters" in resp.data

    def test_search_shows_drivers(self, client):
        services.create_driver(name="Searchable Driver")
        resp = client.get("/search?q=Searchable")
        assert resp.status_code == 200
        assert b"Searchable Driver" in resp.data
        assert b"Drivers" in resp.data

    def test_search_shows_equipment(self, client):
        services.create_equipment(unit_number="SEARCH-001", equipment_type="flatbed")
        resp = client.get("/search?q=SEARCH-001")
        assert resp.status_code == 200
        assert b"SEARCH-001" in resp.data
        assert b"Equipment" in resp.data


# ── Sidebar link ─────────────────────────────────────────────────────


class TestSearchSidebar:
    def test_search_link_in_sidebar(self, client):
        resp = client.get("/home")
        assert b"/search" in resp.data
