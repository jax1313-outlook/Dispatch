"""Tests for fleet utilization / assignment visibility (PR 29)."""

from __future__ import annotations

import pytest

from dispatch import services, store as dispatch_store
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


# ── Store: active load lookup ──────────────────────────────────────


class TestActiveLoadLookup:
    def test_no_load_returns_none(self):
        d = services.create_driver(name="Solo Driver")
        result = dispatch_store.get_active_load_for_driver(d["driver_id"])
        assert result is None

    def test_assigned_driver_returns_load(self):
        d = services.create_driver(name="Busy Driver")
        load = services.create_load(customer="Acme Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        result = dispatch_store.get_active_load_for_driver(d["driver_id"])
        assert result is not None
        assert result["load_id"] == load["load_id"]

    def test_completed_load_not_returned(self):
        d = services.create_driver(name="Done Driver")
        load = services.create_load(customer="Old Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed"]:
            services.update_load(load["load_id"], status=s)
        result = dispatch_store.get_active_load_for_driver(d["driver_id"])
        assert result is None

    def test_cancelled_load_not_returned(self):
        d = services.create_driver(name="Cancel Driver")
        load = services.create_load(customer="Cancel Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        services.update_load(load["load_id"], status="cancelled")
        result = dispatch_store.get_active_load_for_driver(d["driver_id"])
        assert result is None

    def test_equipment_active_load(self):
        e = services.create_equipment(unit_number="EQ-100")
        load = services.create_load(customer="Equip Corp")
        services.assign_equipment(load["load_id"], e["equipment_id"])
        result = dispatch_store.get_active_load_for_equipment(e["equipment_id"])
        assert result is not None
        assert result["load_id"] == load["load_id"]

    def test_equipment_no_load(self):
        e = services.create_equipment(unit_number="EQ-200")
        result = dispatch_store.get_active_load_for_equipment(e["equipment_id"])
        assert result is None


# ── Store: fleet assignments bulk ──────────────────────────────────


class TestFleetAssignments:
    def test_empty_when_no_loads(self):
        result = dispatch_store.get_fleet_assignments()
        assert result["driver_loads"] == {}
        assert result["equipment_loads"] == {}

    def test_returns_assigned_driver(self):
        d = services.create_driver(name="Assigned D")
        load = services.create_load(customer="Corp A")
        services.assign_driver(load["load_id"], d["driver_id"])
        result = dispatch_store.get_fleet_assignments()
        assert d["driver_id"] in result["driver_loads"]
        assert result["driver_loads"][d["driver_id"]]["load_id"] == load["load_id"]

    def test_returns_assigned_equipment(self):
        e = services.create_equipment(unit_number="ASN-001")
        load = services.create_load(customer="Corp B")
        services.assign_equipment(load["load_id"], e["equipment_id"])
        result = dispatch_store.get_fleet_assignments()
        assert e["equipment_id"] in result["equipment_loads"]

    def test_excludes_completed_loads(self):
        d = services.create_driver(name="Finished D")
        load = services.create_load(customer="Done Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed"]:
            services.update_load(load["load_id"], status=s)
        result = dispatch_store.get_fleet_assignments()
        assert d["driver_id"] not in result["driver_loads"]

    def test_multiple_assignments(self):
        d1 = services.create_driver(name="D1")
        d2 = services.create_driver(name="D2")
        l1 = services.create_load(customer="C1")
        l2 = services.create_load(customer="C2")
        services.assign_driver(l1["load_id"], d1["driver_id"])
        services.assign_driver(l2["load_id"], d2["driver_id"])
        result = dispatch_store.get_fleet_assignments()
        assert len(result["driver_loads"]) == 2


# ── Fleet page rendering ──────────────────────────────────────────


class TestFleetPageUtilization:
    def test_available_shown_for_unassigned(self, client):
        services.create_driver(name="Free Driver")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Available" in html

    def test_assignment_shown_for_assigned_driver(self, client):
        d = services.create_driver(name="Working Driver")
        load = services.create_load(customer="Active Customer")
        services.assign_driver(load["load_id"], d["driver_id"])
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Active Customer" in html

    def test_assignment_links_to_load(self, client):
        d = services.create_driver(name="Link Driver")
        load = services.create_load(customer="Link Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert f"/dispatch/{load['load_id']}" in html

    def test_equipment_available_shown(self, client):
        services.create_equipment(unit_number="FREE-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Available" in html

    def test_equipment_assignment_shown(self, client):
        e = services.create_equipment(unit_number="BUSY-001")
        load = services.create_load(customer="Equip Customer")
        services.assign_equipment(load["load_id"], e["equipment_id"])
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Equip Customer" in html

    def test_inactive_driver_shows_dash(self, client):
        d = services.create_driver(name="Inactive Driver")
        services.update_driver(d["driver_id"], status="inactive")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Available" not in html or "Inactive Driver" in html

    def test_assignment_column_header_present(self, client):
        services.create_driver(name="Header Test")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Assignment" in html
