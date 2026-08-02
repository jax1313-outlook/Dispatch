"""Tests for fleet-to-load assignment — PR 22.

Covers: model fields, store persistence, service validation,
assignment/unassignment, API endpoints, and load bundle enrichment.
"""

from __future__ import annotations

import json
import pytest

from dispatch import services, store
from dispatch.db import get_connection, set_db_path
from dispatch.models import Load, Driver, Equipment


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Model ────────────────────────────────────────────────────────────


class TestLoadModelFleetFields:
    def test_default_driver_id_empty(self):
        load = Load(customer="Acme")
        assert load.driver_id == ""

    def test_default_equipment_id_empty(self):
        load = Load(customer="Acme")
        assert load.equipment_id == ""

    def test_set_driver_id(self):
        load = Load(customer="Acme", driver_id="DRV-123")
        assert load.driver_id == "DRV-123"

    def test_set_equipment_id(self):
        load = Load(customer="Acme", equipment_id="EQP-456")
        assert load.equipment_id == "EQP-456"

    def test_to_dict_includes_fleet_ids(self):
        load = Load(customer="Acme", driver_id="DRV-1", equipment_id="EQP-2")
        d = load.to_dict()
        assert d["driver_id"] == "DRV-1"
        assert d["equipment_id"] == "EQP-2"


# ── Store ────────────────────────────────────────────────────────────


class TestStoreFleetFields:
    def test_create_load_persists_driver_id(self):
        load = Load(customer="Acme", driver_id="DRV-X")
        result = store.create_load(load)
        assert result["driver_id"] == "DRV-X"
        fetched = store.get_load(load.load_id)
        assert fetched["driver_id"] == "DRV-X"

    def test_create_load_persists_equipment_id(self):
        load = Load(customer="Acme", equipment_id="EQP-Y")
        result = store.create_load(load)
        assert result["equipment_id"] == "EQP-Y"
        fetched = store.get_load(load.load_id)
        assert fetched["equipment_id"] == "EQP-Y"

    def test_update_load_driver_id(self):
        load = Load(customer="Acme")
        store.create_load(load)
        updated = store.update_load(load.load_id, driver_id="DRV-NEW")
        assert updated["driver_id"] == "DRV-NEW"

    def test_update_load_equipment_id(self):
        load = Load(customer="Acme")
        store.create_load(load)
        updated = store.update_load(load.load_id, equipment_id="EQP-NEW")
        assert updated["equipment_id"] == "EQP-NEW"

    def test_update_load_clear_driver_id(self):
        load = Load(customer="Acme", driver_id="DRV-X")
        store.create_load(load)
        updated = store.update_load(load.load_id, driver_id="")
        assert updated["driver_id"] == ""

    def test_list_loads_includes_fleet_ids(self):
        load = Load(customer="Acme", driver_id="DRV-1", equipment_id="EQP-2")
        store.create_load(load)
        loads = store.list_loads()
        assert loads[0]["driver_id"] == "DRV-1"
        assert loads[0]["equipment_id"] == "EQP-2"


# ── Service validation ──────────────────────────────────────────────


class TestAssignmentValidation:
    def _make_driver(self, **kw):
        return services.create_driver(name=kw.get("name", "Test Driver"), **{
            k: v for k, v in kw.items() if k != "name"
        })

    def _make_equipment(self, **kw):
        return services.create_equipment(unit_number=kw.get("unit_number", "T-100"), **{
            k: v for k, v in kw.items() if k != "unit_number"
        })

    def test_create_load_with_valid_driver(self):
        drv = self._make_driver()
        load = services.create_load(customer="Acme", driver_id=drv["driver_id"])
        assert load["driver_id"] == drv["driver_id"]

    def test_create_load_with_valid_equipment(self):
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme", equipment_id=eqp["equipment_id"])
        assert load["equipment_id"] == eqp["equipment_id"]

    def test_create_load_rejects_nonexistent_driver(self):
        with pytest.raises(ValueError, match="Driver not found"):
            services.create_load(customer="Acme", driver_id="DRV-FAKE")

    def test_create_load_rejects_nonexistent_equipment(self):
        with pytest.raises(ValueError, match="Equipment not found"):
            services.create_load(customer="Acme", equipment_id="EQP-FAKE")

    def test_create_load_rejects_inactive_driver(self):
        drv = self._make_driver()
        services.deactivate_driver(drv["driver_id"])
        with pytest.raises(ValueError, match="not active"):
            services.create_load(customer="Acme", driver_id=drv["driver_id"])

    def test_create_load_rejects_retired_equipment(self):
        eqp = self._make_equipment()
        services.retire_equipment(eqp["equipment_id"])
        with pytest.raises(ValueError, match="not active"):
            services.create_load(customer="Acme", equipment_id=eqp["equipment_id"])

    def test_create_load_no_driver_id_skips_validation(self):
        load = services.create_load(customer="Acme")
        assert load["driver_id"] == ""

    def test_update_load_validates_driver(self):
        load = services.create_load(customer="Acme")
        with pytest.raises(ValueError, match="Driver not found"):
            services.update_load(load["load_id"], driver_id="DRV-FAKE")

    def test_update_load_validates_equipment(self):
        load = services.create_load(customer="Acme")
        with pytest.raises(ValueError, match="Equipment not found"):
            services.update_load(load["load_id"], equipment_id="EQP-FAKE")

    def test_update_load_allows_empty_driver_id(self):
        drv = self._make_driver()
        load = services.create_load(customer="Acme", driver_id=drv["driver_id"])
        result = services.update_load(load["load_id"], driver_id="")
        assert result["driver_id"] == ""


# ── Assign / Unassign ───────────────────────────────────────────────


class TestAssignDriver:
    def test_assign_driver_sets_both_fields(self):
        drv = services.create_driver(name="Alice")
        load = services.create_load(customer="Acme")
        result = services.assign_driver(load["load_id"], drv["driver_id"])
        assert result["driver_id"] == drv["driver_id"]
        assert result["driver"] == "Alice"

    def test_assign_driver_nonexistent_load(self):
        drv = services.create_driver(name="Bob")
        with pytest.raises(ValueError, match="Load not found"):
            services.assign_driver("LOAD-FAKE", drv["driver_id"])

    def test_assign_driver_inactive_rejected(self):
        drv = services.create_driver(name="Charlie")
        services.deactivate_driver(drv["driver_id"])
        load = services.create_load(customer="Acme")
        with pytest.raises(ValueError, match="not active"):
            services.assign_driver(load["load_id"], drv["driver_id"])

    def test_unassign_driver_clears_fields(self):
        drv = services.create_driver(name="Dana")
        load = services.create_load(customer="Acme", driver_id=drv["driver_id"])
        result = services.unassign_driver(load["load_id"])
        assert result["driver_id"] == ""
        assert result["driver"] == ""

    def test_unassign_driver_nonexistent_load(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.unassign_driver("LOAD-FAKE")


class TestAssignEquipment:
    def test_assign_equipment_sets_both_fields(self):
        eqp = services.create_equipment(unit_number="TR-500", equipment_type="reefer")
        load = services.create_load(customer="Acme")
        result = services.assign_equipment(load["load_id"], eqp["equipment_id"])
        assert result["equipment_id"] == eqp["equipment_id"]
        assert "TR-500" in result["equipment"]
        assert "reefer" in result["equipment"]

    def test_assign_equipment_nonexistent_load(self):
        eqp = services.create_equipment(unit_number="TR-600")
        with pytest.raises(ValueError, match="Load not found"):
            services.assign_equipment("LOAD-FAKE", eqp["equipment_id"])

    def test_assign_equipment_retired_rejected(self):
        eqp = services.create_equipment(unit_number="TR-700")
        services.retire_equipment(eqp["equipment_id"])
        load = services.create_load(customer="Acme")
        with pytest.raises(ValueError, match="not active"):
            services.assign_equipment(load["load_id"], eqp["equipment_id"])

    def test_unassign_equipment_clears_fields(self):
        eqp = services.create_equipment(unit_number="TR-800")
        load = services.create_load(customer="Acme")
        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        result = services.unassign_equipment(load["load_id"])
        assert result["equipment_id"] == ""
        assert result["equipment"] == ""

    def test_unassign_equipment_nonexistent_load(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.unassign_equipment("LOAD-FAKE")


# ── Load bundle ─────────────────────────────────────────────────────


class TestLoadBundle:
    def test_bundle_includes_fleet_data(self):
        drv = services.create_driver(name="Eve")
        eqp = services.create_equipment(unit_number="TR-999")
        load = services.create_load(
            customer="Acme",
            driver_id=drv["driver_id"],
            equipment_id=eqp["equipment_id"],
        )
        bundle = services.get_load_bundle(load["load_id"])
        assert bundle["assigned_driver"]["driver_id"] == drv["driver_id"]
        assert bundle["assigned_equipment"]["equipment_id"] == eqp["equipment_id"]
        assert len(bundle["active_drivers"]) >= 1
        assert len(bundle["active_equipment"]) >= 1

    def test_bundle_no_assignment(self):
        load = services.create_load(customer="Acme")
        bundle = services.get_load_bundle(load["load_id"])
        assert bundle["assigned_driver"] is None
        assert bundle["assigned_equipment"] is None

    def test_bundle_active_lists(self):
        services.create_driver(name="Frank")
        inactive_drv = services.create_driver(name="Grace")
        services.deactivate_driver(inactive_drv["driver_id"])
        load = services.create_load(customer="Acme")
        bundle = services.get_load_bundle(load["load_id"])
        names = [d["name"] for d in bundle["active_drivers"]]
        assert "Frank" in names
        assert "Grace" not in names


# ── API ─────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    import importlib
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestAssignmentAPI:
    def test_create_load_with_driver_id(self, client):
        drv = services.create_driver(name="API Driver")
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Acme",
            "driver_id": drv["driver_id"],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["load"]["driver_id"] == drv["driver_id"]

    def test_create_load_invalid_driver_id(self, client):
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Acme",
            "driver_id": "DRV-FAKE",
        })
        assert resp.status_code == 400
        assert "not found" in resp.get_json()["error"].lower()

    def test_create_load_with_equipment_id(self, client):
        eqp = services.create_equipment(unit_number="API-EQ")
        resp = client.post("/api/dispatch/loads", json={
            "customer": "Acme",
            "equipment_id": eqp["equipment_id"],
        })
        assert resp.status_code == 201
        assert resp.get_json()["load"]["equipment_id"] == eqp["equipment_id"]

    def test_assign_driver_endpoint(self, client):
        drv = services.create_driver(name="Endpoint Driver")
        load = services.create_load(customer="Acme")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/assign-driver",
            json={"driver_id": drv["driver_id"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["load"]["driver_id"] == drv["driver_id"]
        assert data["load"]["driver"] == "Endpoint Driver"

    def test_assign_driver_missing_id(self, client):
        load = services.create_load(customer="Acme")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/assign-driver",
            json={},
        )
        assert resp.status_code == 400

    def test_assign_driver_inactive(self, client):
        drv = services.create_driver(name="Inactive")
        services.deactivate_driver(drv["driver_id"])
        load = services.create_load(customer="Acme")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/assign-driver",
            json={"driver_id": drv["driver_id"]},
        )
        assert resp.status_code == 400

    def test_unassign_driver_endpoint(self, client):
        drv = services.create_driver(name="To Remove")
        load = services.create_load(customer="Acme", driver_id=drv["driver_id"])
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/unassign-driver",
            json={},
        )
        assert resp.status_code == 200
        assert resp.get_json()["load"]["driver_id"] == ""

    def test_assign_equipment_endpoint(self, client):
        eqp = services.create_equipment(unit_number="EQ-API")
        load = services.create_load(customer="Acme")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/assign-equipment",
            json={"equipment_id": eqp["equipment_id"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["load"]["equipment_id"] == eqp["equipment_id"]

    def test_assign_equipment_missing_id(self, client):
        load = services.create_load(customer="Acme")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/assign-equipment",
            json={},
        )
        assert resp.status_code == 400

    def test_unassign_equipment_endpoint(self, client):
        eqp = services.create_equipment(unit_number="EQ-REM")
        load = services.create_load(customer="Acme", equipment_id=eqp["equipment_id"])
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/unassign-equipment",
            json={},
        )
        assert resp.status_code == 200
        assert resp.get_json()["load"]["equipment_id"] == ""

    def test_update_load_validates_driver_via_api(self, client):
        load = services.create_load(customer="Acme")
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"driver_id": "DRV-FAKE"},
        )
        assert resp.status_code == 400

    def test_assign_driver_nonexistent_load(self, client):
        drv = services.create_driver(name="Ghost")
        resp = client.post(
            "/api/dispatch/loads/LOAD-FAKE/assign-driver",
            json={"driver_id": drv["driver_id"]},
        )
        assert resp.status_code == 404

    def test_assign_equipment_nonexistent_load(self, client):
        eqp = services.create_equipment(unit_number="EQ-GHOST")
        resp = client.post(
            "/api/dispatch/loads/LOAD-FAKE/assign-equipment",
            json={"equipment_id": eqp["equipment_id"]},
        )
        assert resp.status_code == 404


class TestDispatchDetailPage:
    def test_detail_page_shows_fleet_assignment(self, client):
        drv = services.create_driver(name="Page Driver")
        eqp = services.create_equipment(unit_number="PG-100")
        load = services.create_load(
            customer="Acme",
            driver_id=drv["driver_id"],
            equipment_id=eqp["equipment_id"],
        )
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Fleet Assignment" in html
        assert "Page Driver" in html
        assert "PG-100" in html

    def test_detail_page_no_assignment(self, client):
        load = services.create_load(customer="Acme")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Fleet Assignment" in html
        assert "None" in html
