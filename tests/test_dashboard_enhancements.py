"""Tests for dashboard enhancements: stalled badge, fleet utilization summary,
settings stall thresholds, and notify-all button."""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Fleet summary utilization counts ─────────────────────────────────


class TestFleetSummaryUtilization:
    def test_no_assignments_all_available(self):
        services.create_driver(name="D1")
        services.create_driver(name="D2")
        services.create_equipment(unit_number="T-001")
        summary = services.get_fleet_summary()
        assert summary["drivers_assigned"] == 0
        assert summary["drivers_available"] == 2
        assert summary["equipment_assigned"] == 0
        assert summary["equipment_available"] == 1

    def test_one_assigned_one_available(self):
        d1 = services.create_driver(name="Assigned")
        services.create_driver(name="Available")
        load = services.create_load(customer="TestCo")
        services.assign_driver(load["load_id"], d1["driver_id"])
        summary = services.get_fleet_summary()
        assert summary["drivers_assigned"] == 1
        assert summary["drivers_available"] == 1

    def test_completed_load_not_counted(self):
        d = services.create_driver(name="Done Driver")
        load = services.create_load(customer="Done Corp")
        services.assign_driver(load["load_id"], d["driver_id"])
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed"]:
            services.update_load(load["load_id"], status=s)
        summary = services.get_fleet_summary()
        assert summary["drivers_assigned"] == 0
        assert summary["drivers_available"] == 1

    def test_equipment_utilization(self):
        e = services.create_equipment(unit_number="T-100")
        load = services.create_load(customer="EqCo")
        services.assign_equipment(load["load_id"], e["equipment_id"])
        summary = services.get_fleet_summary()
        assert summary["equipment_assigned"] == 1
        assert summary["equipment_available"] == 0


# ── Fleet page utilization section ───────────────────────────────────


class TestFleetPageUtilizationSection:
    def test_utilization_section_present(self, client):
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert 'id="fleet-utilization"' in html

    def test_show_utilization_button(self, client):
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Show Utilization" in html

    def test_utilization_counts_rendered(self, client):
        services.create_driver(name="D1")
        services.create_equipment(unit_number="T-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Drivers Assigned" in html
        assert "Drivers Available" in html
        assert "Equipment Assigned" in html
        assert "Equipment Available" in html


# ── Home page stalled loads badge ────────────────────────────────────


class TestHomeStalledBadge:
    def test_no_stalled_no_badge(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Stalled Loads" not in html or "summary-danger" not in html

    def test_notify_all_button_present_when_stalled(self, client):
        load = services.create_load(customer="Stalled Co")
        services.update_load(load["load_id"], status="dispatched")
        from dispatch import store
        from datetime import datetime, timezone, timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        with store.get_connection() as conn:
            conn.execute(
                "UPDATE loads SET updated_at=? WHERE load_id=?",
                (old_time, load["load_id"]),
            )
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Notify All Stalled" in html
        assert "notifyStalled()" in html


# ── Notify stalled API ──────────────────────────────────────────────


class TestNotifyStalledAPI:
    def test_notify_endpoint_returns_ok(self, client):
        resp = client.post(
            "/api/dispatch/loads/stalled/notify",
            content_type="application/json",
            data="{}",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "notified" in data


# ── Settings page stall thresholds ───────────────────────────────────


class TestSettingsStallThresholds:
    def test_thresholds_displayed(self, client):
        resp = client.get("/settings")
        html = resp.data.decode()
        assert "Stall Detection Thresholds" in html
        assert "Created" in html
        assert "Dispatched" in html
        assert "In Transit" in html

    def test_quickbooks_section(self, client):
        resp = client.get("/settings")
        html = resp.data.decode()
        assert "QuickBooks Online" in html
        assert "Accounting Integration" in html
