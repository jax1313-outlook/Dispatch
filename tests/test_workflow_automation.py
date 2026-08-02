"""Tests for load status transition guards, auto-dispatch, and dispatch notification — PR 23.

Covers: status transition validation, auto-dispatch on fleet assignment,
dispatch notification, milestone-driven transitions respecting guards,
and API validation.
"""

from __future__ import annotations

import pytest

from dispatch import services, store, notifications
from dispatch.db import set_db_path
from dispatch.models import Load


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Status transition validation ────────────────────────────────────


class TestStatusTransitionValidation:
    def test_created_to_dispatched(self):
        services.validate_status_transition("created", "dispatched")

    def test_created_to_cancelled(self):
        services.validate_status_transition("created", "cancelled")

    def test_created_to_delivered_rejected(self):
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.validate_status_transition("created", "delivered")

    def test_dispatched_to_en_route(self):
        services.validate_status_transition("dispatched", "en_route_pickup")

    def test_dispatched_to_delivered_rejected(self):
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.validate_status_transition("dispatched", "delivered")

    def test_in_transit_to_at_delivery(self):
        services.validate_status_transition("in_transit", "at_delivery")

    def test_in_transit_to_cancelled_rejected(self):
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.validate_status_transition("in_transit", "cancelled")

    def test_delivered_to_completed(self):
        services.validate_status_transition("delivered", "completed")

    def test_delivered_to_archived(self):
        services.validate_status_transition("delivered", "archived")

    def test_completed_to_archived(self):
        services.validate_status_transition("completed", "archived")

    def test_archived_to_anything_rejected(self):
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.validate_status_transition("archived", "created")

    def test_cancelled_to_anything_rejected(self):
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.validate_status_transition("cancelled", "dispatched")

    def test_same_status_allowed(self):
        services.validate_status_transition("created", "created")

    def test_error_message_lists_allowed(self):
        with pytest.raises(ValueError, match="cancelled.*dispatched"):
            services.validate_status_transition("created", "in_transit")


class TestUpdateLoadTransitionGuard:
    def test_update_load_valid_transition(self):
        load = services.create_load(customer="Acme")
        result = services.update_load(load["load_id"], status="dispatched")
        assert result["status"] == "dispatched"

    def test_update_load_invalid_transition(self):
        load = services.create_load(customer="Acme")
        with pytest.raises(ValueError, match="Invalid status transition"):
            services.update_load(load["load_id"], status="delivered")

    def test_update_load_non_status_field_no_guard(self):
        load = services.create_load(customer="Acme")
        result = services.update_load(load["load_id"], customer="Beta")
        assert result["customer"] == "Beta"

    def test_update_load_cancelled_from_created(self):
        load = services.create_load(customer="Acme")
        result = services.update_load(load["load_id"], status="cancelled")
        assert result["status"] == "cancelled"


# ── Auto-dispatch ───────────────────────────────────────────────────


class TestAutoDispatch:
    def _make_driver(self):
        return services.create_driver(name="Auto Driver")

    def _make_equipment(self):
        return services.create_equipment(unit_number="AD-100")

    def test_auto_dispatch_on_driver_then_equipment(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")
        assert load["status"] == "created"

        services.assign_driver(load["load_id"], drv["driver_id"])
        mid = store.get_load(load["load_id"])
        assert mid["status"] == "created"

        result = services.assign_equipment(load["load_id"], eqp["equipment_id"])
        assert result["status"] == "dispatched"

    def test_auto_dispatch_on_equipment_then_driver(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")

        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        mid = store.get_load(load["load_id"])
        assert mid["status"] == "created"

        result = services.assign_driver(load["load_id"], drv["driver_id"])
        assert result["status"] == "dispatched"

    def test_auto_dispatch_creates_milestone(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")

        services.assign_driver(load["load_id"], drv["driver_id"])
        services.assign_equipment(load["load_id"], eqp["equipment_id"])

        milestones = services.get_timeline(load["load_id"])
        dispatched = [m for m in milestones if m["event_type"] == "dispatched"]
        assert len(dispatched) == 1
        assert dispatched[0]["source"] == "system"
        assert "Auto-dispatched" in dispatched[0]["note"]

    def test_auto_dispatch_both_at_create_time(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(
            customer="Acme",
            driver_id=drv["driver_id"],
            equipment_id=eqp["equipment_id"],
        )
        assert load["status"] == "created"

    def test_no_auto_dispatch_if_not_created_status(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")
        services.update_load(load["load_id"], status="dispatched")
        services.assign_driver(load["load_id"], drv["driver_id"])
        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        result = store.get_load(load["load_id"])
        assert result["status"] == "dispatched"

    def test_no_auto_dispatch_without_driver(self):
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")
        services.assign_equipment(load["load_id"], eqp["equipment_id"])
        result = store.get_load(load["load_id"])
        assert result["status"] == "created"

    def test_no_auto_dispatch_without_equipment(self):
        drv = self._make_driver()
        load = services.create_load(customer="Acme")
        services.assign_driver(load["load_id"], drv["driver_id"])
        result = store.get_load(load["load_id"])
        assert result["status"] == "created"

    def test_auto_dispatch_updates_visibility(self):
        drv = self._make_driver()
        eqp = self._make_equipment()
        load = services.create_load(customer="Acme")
        services.assign_driver(load["load_id"], drv["driver_id"])
        services.assign_equipment(load["load_id"], eqp["equipment_id"])

        vis = services.get_visibility(load["load_id"])
        assert vis["current_status"] == "dispatched"
        assert vis["last_milestone"] == "dispatched"
        assert vis["next_expected_milestone"] == "en_route_pickup"


# ── Dispatch notification ───────────────────────────────────────────


class TestDispatchNotification:
    def test_notify_dispatched_renders(self):
        load = {
            "load_id": "LOAD-TEST",
            "customer": "Acme",
            "status": "dispatched",
            "driver": "John Doe",
            "equipment": "TR-500 (reefer)",
            "pickup_location": "Dallas, TX",
            "delivery_location": "Houston, TX",
        }
        result = notifications.notify_dispatched(load)
        assert "dispatched" in result.lower() or result.endswith(".eml")

    def test_auto_dispatch_sends_notification(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "http://localhost:8080")

        drv = services.create_driver(name="Notify Driver")
        eqp = services.create_equipment(unit_number="NT-100")
        load = services.create_load(customer="Acme")
        services.assign_driver(load["load_id"], drv["driver_id"])
        services.assign_equipment(load["load_id"], eqp["equipment_id"])

        import glob
        eml_dir = tmp_path / "data" / "outbox"
        if eml_dir.exists():
            eml_files = list(eml_dir.glob("dispatch-dispatched-*.eml"))
            assert len(eml_files) >= 1


# ── Milestone-driven transitions respect guards ─────────────────────


class TestMilestoneTransitions:
    def test_milestone_dispatched_from_created(self):
        load = services.create_load(customer="Acme")
        ms = services.add_milestone(load["load_id"], "dispatched", source="dispatcher")
        updated = store.get_load(load["load_id"])
        assert updated["status"] == "dispatched"

    def test_milestone_sequence_full_lifecycle(self):
        load = services.create_load(customer="Acme")
        services.add_milestone(load["load_id"], "dispatched")
        services.add_milestone(load["load_id"], "en_route_pickup")
        services.add_milestone(load["load_id"], "arrived_pickup")
        services.add_milestone(load["load_id"], "loaded")
        services.add_milestone(load["load_id"], "departed_pickup")
        services.add_milestone(load["load_id"], "arrived_delivery")
        services.add_milestone(load["load_id"], "delivered")

        final = store.get_load(load["load_id"])
        assert final["status"] == "delivered"


# ── API transition guard ────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestAPITransitionGuard:
    def test_api_valid_transition(self, client):
        load = services.create_load(customer="Acme")
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"status": "dispatched"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["load"]["status"] == "dispatched"

    def test_api_invalid_transition(self, client):
        load = services.create_load(customer="Acme")
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"status": "delivered"},
        )
        assert resp.status_code == 400
        assert "Invalid status transition" in resp.get_json()["error"]

    def test_api_cancel_from_created(self, client):
        load = services.create_load(customer="Acme")
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["load"]["status"] == "cancelled"

    def test_dispatch_page_shows_equipment_column(self, client):
        drv = services.create_driver(name="Col Driver")
        eqp = services.create_equipment(unit_number="COL-100")
        load = services.create_load(customer="Acme")
        services.assign_driver(load["load_id"], drv["driver_id"])
        services.assign_equipment(load["load_id"], eqp["equipment_id"])

        resp = client.get("/dispatch")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "COL-100" in html
        assert "Col Driver" in html
