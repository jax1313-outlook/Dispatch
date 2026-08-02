"""Tests for fleet search and filtering (PR 28)."""

from __future__ import annotations

import pytest

from dispatch import services, store as dispatch_store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Driver name search (store) ──────────────────────────────────────


class TestDriverNameSearch:
    def test_filter_by_name(self):
        services.create_driver(name="John Smith")
        services.create_driver(name="Jane Doe")
        services.create_driver(name="Johnny Appleseed")

        results = dispatch_store.list_drivers(name="John")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"John Smith", "Johnny Appleseed"}

    def test_name_search_case_insensitive(self):
        services.create_driver(name="Alice Walker")
        results = dispatch_store.list_drivers(name="alice")
        assert len(results) == 1

    def test_name_no_match(self):
        services.create_driver(name="Bob Builder")
        results = dispatch_store.list_drivers(name="Zebra")
        assert len(results) == 0

    def test_name_and_status_combined(self):
        d1 = services.create_driver(name="Active Al")
        d2 = services.create_driver(name="Active Amy")
        services.update_driver(d2["driver_id"], status="inactive")

        results = dispatch_store.list_drivers(status="active", name="Active")
        assert len(results) == 1
        assert results[0]["name"] == "Active Al"


# ── Equipment unit_number search (store) ────────────────────────────


class TestEquipmentUnitSearch:
    def test_filter_by_unit_number(self):
        services.create_equipment(unit_number="TR-001")
        services.create_equipment(unit_number="TR-002")
        services.create_equipment(unit_number="VN-001")

        results = dispatch_store.list_equipment(unit_number="TR")
        assert len(results) == 2
        units = {r["unit_number"] for r in results}
        assert units == {"TR-001", "TR-002"}

    def test_unit_number_no_match(self):
        services.create_equipment(unit_number="TR-001")
        results = dispatch_store.list_equipment(unit_number="ZZ")
        assert len(results) == 0

    def test_unit_and_status_combined(self):
        e1 = services.create_equipment(unit_number="TR-100")
        e2 = services.create_equipment(unit_number="TR-200")
        services.update_equipment(e2["equipment_id"], status="maintenance")

        results = dispatch_store.list_equipment(status="active", unit_number="TR")
        assert len(results) == 1
        assert results[0]["unit_number"] == "TR-100"

    def test_unit_and_type_combined(self):
        services.create_equipment(unit_number="FB-001", equipment_type="flatbed")
        services.create_equipment(unit_number="FB-002", equipment_type="reefer")

        results = dispatch_store.list_equipment(
            equipment_type="flatbed", unit_number="FB"
        )
        assert len(results) == 1
        assert results[0]["unit_number"] == "FB-001"


# ── Service passthrough ─────────────────────────────────────────────


class TestServicePassthrough:
    def test_drivers_name_passthrough(self):
        services.create_driver(name="Target Driver")
        services.create_driver(name="Other Driver")
        results = services.list_drivers(name="Target")
        assert len(results) == 1

    def test_equipment_unit_passthrough(self):
        services.create_equipment(unit_number="EQ-999")
        services.create_equipment(unit_number="XX-001")
        results = services.list_equipment(unit_number="EQ")
        assert len(results) == 1


# ── API endpoints ───────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestDriverAPI:
    def test_filter_by_name(self, client):
        services.create_driver(name="Alpha Driver")
        services.create_driver(name="Bravo Driver")

        resp = client.get("/api/dispatch/drivers?name=Alpha")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["drivers"][0]["name"] == "Alpha Driver"

    def test_filter_by_status_and_name(self, client):
        services.create_driver(name="Search Me")
        resp = client.get("/api/dispatch/drivers?status=active&name=Search")
        data = resp.get_json()
        assert data["count"] == 1


class TestEquipmentAPI:
    def test_filter_by_unit_number(self, client):
        services.create_equipment(unit_number="API-001")
        services.create_equipment(unit_number="OTHER-001")

        resp = client.get("/api/dispatch/equipment?unit_number=API")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["equipment"][0]["unit_number"] == "API-001"

    def test_filter_by_type_and_unit(self, client):
        services.create_equipment(unit_number="RR-001", equipment_type="reefer")
        services.create_equipment(unit_number="RR-002", equipment_type="flatbed")

        resp = client.get("/api/dispatch/equipment?equipment_type=reefer&unit_number=RR")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["equipment"][0]["unit_number"] == "RR-001"


# ── Fleet page ──────────────────────────────────────────────────────


class TestFleetPage:
    def test_driver_search_on_page(self, client):
        services.create_driver(name="Fleet Driver")
        resp = client.get("/fleet?driver_name=Fleet")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Fleet Driver" in html

    def test_driver_status_filter(self, client):
        d = services.create_driver(name="InactiveGuy")
        services.update_driver(d["driver_id"], status="inactive")
        services.create_driver(name="ActiveGuy")

        resp = client.get("/fleet?driver_status=active")
        html = resp.data.decode()
        assert "ActiveGuy" in html
        assert "InactiveGuy" not in html

    def test_equipment_search_on_page(self, client):
        services.create_equipment(unit_number="SRCH-001")
        resp = client.get("/fleet?unit_number=SRCH")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "SRCH-001" in html

    def test_equipment_type_filter(self, client):
        services.create_equipment(unit_number="FB-010", equipment_type="flatbed")
        services.create_equipment(unit_number="RF-010", equipment_type="reefer")

        resp = client.get("/fleet?equip_type=flatbed")
        html = resp.data.decode()
        assert "FB-010" in html
        assert "RF-010" not in html

    def test_clear_button_shown(self, client):
        resp = client.get("/fleet?driver_name=test")
        html = resp.data.decode()
        assert "Clear" in html

    def test_no_clear_without_filters(self, client):
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert html.count('Clear</a>') == 0
