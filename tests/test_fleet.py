"""Tests for driver and equipment management."""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store
from dispatch.db import set_db_path
from dispatch.models import (
    DRIVER_STATUSES,
    EQUIPMENT_STATUSES,
    EQUIPMENT_TYPES,
    LICENSE_CLASSES,
    Driver,
    Equipment,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Driver Model ────────────────────────────────────────────────────


class TestDriverModel:
    def test_defaults(self):
        d = Driver(name="Mike")
        assert d.driver_id.startswith("DRV-")
        assert d.status == "active"
        assert d.created_at
        assert d.updated_at == d.created_at

    def test_valid_statuses(self):
        for s in DRIVER_STATUSES:
            d = Driver(name="Test", status=s)
            assert d.status == s

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            Driver(name="Test", status="fired")

    def test_valid_license_class(self):
        for lc in LICENSE_CLASSES:
            d = Driver(name="Test", license_class=lc)
            assert d.license_class == lc

    def test_invalid_license_class(self):
        with pytest.raises(ValueError):
            Driver(name="Test", license_class="Z")

    def test_empty_license_class_ok(self):
        d = Driver(name="Test", license_class="")
        assert d.license_class == ""

    def test_to_dict(self):
        d = Driver(name="Mike", phone="555-1234")
        dd = d.to_dict()
        assert dd["name"] == "Mike"
        assert dd["phone"] == "555-1234"
        assert "driver_id" in dd


# ── Equipment Model ─────────────────────────────────────────────────


class TestEquipmentModel:
    def test_defaults(self):
        e = Equipment(unit_number="T-101")
        assert e.equipment_id.startswith("EQP-")
        assert e.equipment_type == "dry_van"
        assert e.status == "active"

    def test_valid_types(self):
        for et in EQUIPMENT_TYPES:
            e = Equipment(unit_number="T-1", equipment_type=et)
            assert e.equipment_type == et

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            Equipment(unit_number="T-1", equipment_type="helicopter")

    def test_valid_statuses(self):
        for s in EQUIPMENT_STATUSES:
            e = Equipment(unit_number="T-1", status=s)
            assert e.status == s

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            Equipment(unit_number="T-1", status="destroyed")

    def test_to_dict(self):
        e = Equipment(unit_number="T-101", make="Volvo", model="VNL860")
        ed = e.to_dict()
        assert ed["unit_number"] == "T-101"
        assert ed["make"] == "Volvo"


# ── Driver Store ────────────────────────────────────────────────────


class TestDriverStore:
    def test_create_and_get(self):
        d = Driver(name="Mike Smith", license_class="A")
        result = store.create_driver(d)
        assert result["name"] == "Mike Smith"
        fetched = store.get_driver(d.driver_id)
        assert fetched["name"] == "Mike Smith"

    def test_list_drivers(self):
        store.create_driver(Driver(name="Alice", status="active"))
        store.create_driver(Driver(name="Bob", status="inactive"))
        all_drivers = store.list_drivers()
        assert len(all_drivers) == 2
        active = store.list_drivers(status="active")
        assert len(active) == 1
        assert active[0]["name"] == "Alice"

    def test_update_driver(self):
        d = Driver(name="Charlie")
        store.create_driver(d)
        updated = store.update_driver(d.driver_id, phone="555-9999")
        assert updated["phone"] == "555-9999"

    def test_update_nonexistent(self):
        assert store.update_driver("DRV-FAKE", name="X") is None

    def test_delete_driver(self):
        d = Driver(name="Dave")
        store.create_driver(d)
        assert store.delete_driver(d.driver_id)
        assert store.get_driver(d.driver_id) is None

    def test_delete_nonexistent(self):
        assert not store.delete_driver("DRV-FAKE")


# ── Equipment Store ─────────────────────────────────────────────────


class TestEquipmentStore:
    def test_create_and_get(self):
        e = Equipment(unit_number="T-201", equipment_type="reefer")
        result = store.create_equipment(e)
        assert result["unit_number"] == "T-201"
        fetched = store.get_equipment(e.equipment_id)
        assert fetched["equipment_type"] == "reefer"

    def test_list_equipment(self):
        store.create_equipment(Equipment(unit_number="T-1", equipment_type="dry_van"))
        store.create_equipment(Equipment(unit_number="T-2", equipment_type="reefer"))
        store.create_equipment(Equipment(unit_number="T-3", equipment_type="dry_van", status="maintenance"))
        all_eq = store.list_equipment()
        assert len(all_eq) == 3
        active = store.list_equipment(status="active")
        assert len(active) == 2
        dry_vans = store.list_equipment(equipment_type="dry_van")
        assert len(dry_vans) == 2

    def test_update_equipment(self):
        e = Equipment(unit_number="T-301")
        store.create_equipment(e)
        updated = store.update_equipment(e.equipment_id, license_plate="ABC-1234")
        assert updated["license_plate"] == "ABC-1234"

    def test_update_nonexistent(self):
        assert store.update_equipment("EQP-FAKE", make="X") is None

    def test_delete_equipment(self):
        e = Equipment(unit_number="T-401")
        store.create_equipment(e)
        assert store.delete_equipment(e.equipment_id)
        assert store.get_equipment(e.equipment_id) is None


# ── Driver Service ──────────────────────────────────────────────────


class TestDriverService:
    def test_create_driver(self):
        d = dispatch_svc.create_driver(name="Mike", license_class="A", phone="555-1111")
        assert d["name"] == "Mike"
        assert d["license_class"] == "A"
        assert d["status"] == "active"

    def test_deactivate_driver(self):
        d = dispatch_svc.create_driver(name="Bob")
        result = dispatch_svc.deactivate_driver(d["driver_id"])
        assert result["status"] == "inactive"

    def test_get_driver_by_name(self):
        dispatch_svc.create_driver(name="Jane Doe")
        result = dispatch_svc.get_driver_by_name("Jane Doe")
        assert result is not None
        assert result["name"] == "Jane Doe"

    def test_get_driver_by_name_not_found(self):
        assert dispatch_svc.get_driver_by_name("Nobody") is None

    def test_get_driver_by_name_inactive_not_returned(self):
        d = dispatch_svc.create_driver(name="Inactive Guy")
        dispatch_svc.deactivate_driver(d["driver_id"])
        assert dispatch_svc.get_driver_by_name("Inactive Guy") is None


# ── Equipment Service ───────────────────────────────────────────────


class TestEquipmentService:
    def test_create_equipment(self):
        e = dispatch_svc.create_equipment(
            unit_number="T-501", equipment_type="flatbed", make="Great Dane"
        )
        assert e["unit_number"] == "T-501"
        assert e["equipment_type"] == "flatbed"

    def test_retire_equipment(self):
        e = dispatch_svc.create_equipment(unit_number="T-502")
        result = dispatch_svc.retire_equipment(e["equipment_id"])
        assert result["status"] == "retired"

    def test_list_by_type(self):
        dispatch_svc.create_equipment(unit_number="T-1", equipment_type="dry_van")
        dispatch_svc.create_equipment(unit_number="T-2", equipment_type="reefer")
        dry = dispatch_svc.list_equipment(equipment_type="dry_van")
        assert len(dry) == 1


# ── Fleet Summary ──────────────────────────────────────────────────


class TestFleetSummary:
    def test_empty_fleet(self):
        s = dispatch_svc.get_fleet_summary()
        assert s["total_drivers"] == 0
        assert s["total_equipment"] == 0

    def test_summary_counts(self):
        dispatch_svc.create_driver(name="A")
        dispatch_svc.create_driver(name="B")
        d3 = dispatch_svc.create_driver(name="C")
        dispatch_svc.deactivate_driver(d3["driver_id"])

        dispatch_svc.create_equipment(unit_number="T-1", equipment_type="dry_van")
        dispatch_svc.create_equipment(unit_number="T-2", equipment_type="dry_van")
        dispatch_svc.create_equipment(unit_number="T-3", equipment_type="reefer")
        e4 = dispatch_svc.create_equipment(unit_number="T-4", equipment_type="flatbed")
        dispatch_svc.update_equipment(e4["equipment_id"], status="maintenance")

        s = dispatch_svc.get_fleet_summary()
        assert s["total_drivers"] == 3
        assert s["drivers_by_status"]["active"] == 2
        assert s["drivers_by_status"]["inactive"] == 1
        assert s["total_equipment"] == 4
        assert s["equipment_by_status"]["active"] == 3
        assert s["equipment_by_status"]["maintenance"] == 1
        assert s["active_equipment_by_type"]["dry_van"] == 2
        assert s["active_equipment_by_type"]["reefer"] == 1


# ── Driver API ──────────────────────────────────────────────────────


class TestDriverAPI:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_create_driver(self, client):
        resp = client.post("/api/dispatch/drivers", json={"name": "API Driver", "license_class": "A"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["driver"]["name"] == "API Driver"

    def test_create_driver_missing_name(self, client):
        resp = client.post("/api/dispatch/drivers", json={})
        assert resp.status_code == 400

    def test_create_driver_invalid_license(self, client):
        resp = client.post("/api/dispatch/drivers", json={"name": "X", "license_class": "Z"})
        assert resp.status_code == 400

    def test_list_drivers(self, client):
        client.post("/api/dispatch/drivers", json={"name": "D1"})
        client.post("/api/dispatch/drivers", json={"name": "D2"})
        resp = client.get("/api/dispatch/drivers")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 2

    def test_get_driver(self, client):
        r = client.post("/api/dispatch/drivers", json={"name": "Solo"})
        did = r.get_json()["driver"]["driver_id"]
        resp = client.get(f"/api/dispatch/drivers/{did}")
        assert resp.status_code == 200
        assert resp.get_json()["driver"]["name"] == "Solo"

    def test_get_driver_not_found(self, client):
        resp = client.get("/api/dispatch/drivers/DRV-FAKE")
        assert resp.status_code == 404

    def test_update_driver(self, client):
        r = client.post("/api/dispatch/drivers", json={"name": "Update Me"})
        did = r.get_json()["driver"]["driver_id"]
        resp = client.patch(f"/api/dispatch/drivers/{did}", json={"phone": "555-0000"})
        assert resp.status_code == 200
        assert resp.get_json()["driver"]["phone"] == "555-0000"

    def test_delete_driver(self, client):
        r = client.post("/api/dispatch/drivers", json={"name": "Delete Me"})
        did = r.get_json()["driver"]["driver_id"]
        resp = client.delete(f"/api/dispatch/drivers/{did}")
        assert resp.status_code == 200

    def test_filter_by_status(self, client):
        client.post("/api/dispatch/drivers", json={"name": "Active One"})
        resp = client.get("/api/dispatch/drivers?status=active")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_invalid_status_filter(self, client):
        resp = client.get("/api/dispatch/drivers?status=fired")
        assert resp.status_code == 400


# ── Equipment API ───────────────────────────────────────────────────


class TestEquipmentAPI:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_create_equipment(self, client):
        resp = client.post("/api/dispatch/equipment", json={
            "unit_number": "T-API-1", "equipment_type": "reefer",
        })
        assert resp.status_code == 201
        assert resp.get_json()["equipment"]["unit_number"] == "T-API-1"

    def test_create_missing_unit(self, client):
        resp = client.post("/api/dispatch/equipment", json={"equipment_type": "reefer"})
        assert resp.status_code == 400

    def test_create_invalid_type(self, client):
        resp = client.post("/api/dispatch/equipment", json={
            "unit_number": "T-1", "equipment_type": "spaceship",
        })
        assert resp.status_code == 400

    def test_list_equipment(self, client):
        client.post("/api/dispatch/equipment", json={"unit_number": "T-1"})
        client.post("/api/dispatch/equipment", json={"unit_number": "T-2"})
        resp = client.get("/api/dispatch/equipment")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 2

    def test_get_equipment(self, client):
        r = client.post("/api/dispatch/equipment", json={"unit_number": "T-Solo"})
        eid = r.get_json()["equipment"]["equipment_id"]
        resp = client.get(f"/api/dispatch/equipment/{eid}")
        assert resp.status_code == 200

    def test_update_equipment(self, client):
        r = client.post("/api/dispatch/equipment", json={"unit_number": "T-Upd"})
        eid = r.get_json()["equipment"]["equipment_id"]
        resp = client.patch(f"/api/dispatch/equipment/{eid}", json={"make": "Freightliner"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["make"] == "Freightliner"

    def test_delete_equipment(self, client):
        r = client.post("/api/dispatch/equipment", json={"unit_number": "T-Del"})
        eid = r.get_json()["equipment"]["equipment_id"]
        resp = client.delete(f"/api/dispatch/equipment/{eid}")
        assert resp.status_code == 200

    def test_filter_by_type(self, client):
        client.post("/api/dispatch/equipment", json={"unit_number": "T-1", "equipment_type": "dry_van"})
        client.post("/api/dispatch/equipment", json={"unit_number": "T-2", "equipment_type": "reefer"})
        resp = client.get("/api/dispatch/equipment?equipment_type=dry_van")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_invalid_status_filter(self, client):
        resp = client.get("/api/dispatch/equipment?status=destroyed")
        assert resp.status_code == 400


# ── Fleet Summary API ──────────────────────────────────────────────


class TestFleetSummaryAPI:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_empty_fleet_summary(self, client):
        resp = client.get("/api/dispatch/fleet/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_drivers"] == 0
        assert data["total_equipment"] == 0

    def test_fleet_summary_with_data(self, client):
        client.post("/api/dispatch/drivers", json={"name": "D1"})
        client.post("/api/dispatch/equipment", json={"unit_number": "T-1"})
        resp = client.get("/api/dispatch/fleet/summary")
        data = resp.get_json()
        assert data["total_drivers"] == 1
        assert data["total_equipment"] == 1


# ── Fleet Page ──────────────────────────────────────────────────────


class TestFleetPage:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_fleet_page_loads(self, client):
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert b"Fleet Management" in resp.data

    def test_fleet_page_shows_driver(self, client):
        client.post("/api/dispatch/drivers", json={"name": "Page Driver"})
        resp = client.get("/fleet")
        assert b"Page Driver" in resp.data

    def test_fleet_page_shows_equipment(self, client):
        client.post("/api/dispatch/equipment", json={"unit_number": "T-PAGE"})
        resp = client.get("/fleet")
        assert b"T-PAGE" in resp.data
