"""Tests for driver and equipment detail pages."""

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


# ── Driver Detail Page ───────────────────────────────────────────────


class TestDriverDetailPage:
    def test_page_loads(self, client):
        drv = services.create_driver(name="John Doe", phone="555-0100")
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert resp.status_code == 200
        assert b"John Doe" in resp.data
        assert b"555-0100" in resp.data

    def test_not_found(self, client):
        resp = client.get("/fleet/driver/DRV-nonexistent")
        assert resp.status_code == 404

    def test_shows_all_fields(self, client):
        drv = services.create_driver(
            name="Jane Smith",
            license_number="DL12345",
            license_class="A",
            phone="555-0200",
            email="jane@example.com",
            hire_date="2024-01-15",
            notes="Excellent record",
        )
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert b"Jane Smith" in resp.data
        assert b"DL12345" in resp.data
        assert b"Class A" in resp.data
        assert b"555-0200" in resp.data
        assert b"jane@example.com" in resp.data
        assert b"2024-01-15" in resp.data
        assert b"Excellent record" in resp.data

    def test_shows_active_assignment(self, client):
        drv = services.create_driver(name="Active Driver")
        load = services.create_load(customer="Test Customer")
        services.assign_driver(load["load_id"], drv["driver_id"])
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert resp.status_code == 200
        assert b"Test Customer" in resp.data
        assert b"Current Assignment" in resp.data

    def test_shows_no_assignment(self, client):
        drv = services.create_driver(name="Idle Driver")
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert b"No active assignment" in resp.data

    def test_shows_load_history(self, client):
        drv = services.create_driver(name="History Driver")
        load = services.create_load(customer="History Customer")
        services.assign_driver(load["load_id"], drv["driver_id"])
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert b"Load History" in resp.data
        assert b"History Customer" in resp.data

    def test_edit_form_present(self, client):
        drv = services.create_driver(name="Edit Driver")
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert b"driver-edit" in resp.data
        assert b"saveDriver" in resp.data

    def test_back_link(self, client):
        drv = services.create_driver(name="Back Link Driver")
        resp = client.get(f"/fleet/driver/{drv['driver_id']}")
        assert b"Back to Fleet" in resp.data


# ── Equipment Detail Page ────────────────────────────────────────────


class TestEquipmentDetailPage:
    def test_page_loads(self, client):
        eqp = services.create_equipment(unit_number="TRUCK-001", equipment_type="dry_van")
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert resp.status_code == 200
        assert b"TRUCK-001" in resp.data
        assert b"Dry Van" in resp.data

    def test_not_found(self, client):
        resp = client.get("/fleet/equipment/EQP-nonexistent")
        assert resp.status_code == 404

    def test_shows_all_fields(self, client):
        eqp = services.create_equipment(
            unit_number="RIG-42",
            equipment_type="reefer",
            make="Freightliner",
            model="Cascadia",
            year="2023",
            vin="1FUJGLDR5CLBP1234",
            license_plate="ABC-1234",
            notes="New unit",
        )
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert b"RIG-42" in resp.data
        assert b"Reefer" in resp.data
        assert b"Freightliner" in resp.data
        assert b"Cascadia" in resp.data
        assert b"2023" in resp.data
        assert b"1FUJGLDR5CLBP1234" in resp.data
        assert b"ABC-1234" in resp.data
        assert b"New unit" in resp.data

    def test_shows_active_assignment(self, client):
        eqp = services.create_equipment(unit_number="ASSIGNED-01", equipment_type="flatbed")
        load = services.create_load(customer="Equip Customer")
        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert resp.status_code == 200
        assert b"Equip Customer" in resp.data
        assert b"Current Assignment" in resp.data

    def test_shows_no_assignment(self, client):
        eqp = services.create_equipment(unit_number="IDLE-01", equipment_type="tanker")
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert b"No active assignment" in resp.data

    def test_shows_load_history(self, client):
        eqp = services.create_equipment(unit_number="HIST-01", equipment_type="dry_van")
        load = services.create_load(customer="Equip History Co")
        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert b"Load History" in resp.data
        assert b"Equip History Co" in resp.data

    def test_edit_form_present(self, client):
        eqp = services.create_equipment(unit_number="EDIT-01", equipment_type="box_truck")
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert b"equip-edit" in resp.data
        assert b"saveEquipment" in resp.data

    def test_back_link(self, client):
        eqp = services.create_equipment(unit_number="BACK-01", equipment_type="dry_van")
        resp = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        assert b"Back to Fleet" in resp.data


# ── Fleet Table Links ────────────────────────────────────────────────


class TestFleetTableLinks:
    def test_driver_name_is_link(self, client):
        drv = services.create_driver(name="Linked Driver")
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert f"/fleet/driver/{drv['driver_id']}".encode() in resp.data

    def test_equipment_unit_is_link(self, client):
        eqp = services.create_equipment(unit_number="LINK-01", equipment_type="dry_van")
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert f"/fleet/equipment/{eqp['equipment_id']}".encode() in resp.data
