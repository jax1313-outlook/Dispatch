"""Tests for maintenance schedule alerts feature."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from dispatch.db import set_db_path
from dispatch.models import (
    SERVICE_TYPES, MAINTENANCE_STATUSES, Equipment, MaintenanceSchedule,
)
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _make_equipment(**kw) -> dict:
    defaults = {"unit_number": "TRK-001", "equipment_type": "dry_van"}
    defaults.update(kw)
    return services.create_equipment(**defaults)


def _future(days: int = 5) -> str:
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")


def _past(days: int = 5) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ── Model Tests ─────────────────────────────────────────────────────


class TestMaintenanceModel:
    def test_auto_id(self):
        m = MaintenanceSchedule(equipment_id="EQP-1")
        assert m.schedule_id.startswith("MNT-")

    def test_equipment_id_required(self):
        with pytest.raises(ValueError, match="Equipment ID"):
            MaintenanceSchedule()

    def test_valid_service_types(self):
        for t in SERVICE_TYPES:
            m = MaintenanceSchedule(equipment_id="EQP-1", service_type=t)
            assert m.service_type == t

    def test_invalid_service_type(self):
        with pytest.raises(ValueError, match="service_type"):
            MaintenanceSchedule(equipment_id="EQP-1", service_type="invalid")

    def test_valid_statuses(self):
        for s in MAINTENANCE_STATUSES:
            m = MaintenanceSchedule(equipment_id="EQP-1", status=s)
            assert m.status == s

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            MaintenanceSchedule(equipment_id="EQP-1", status="invalid")

    def test_is_overdue_true(self):
        m = MaintenanceSchedule(equipment_id="EQP-1", next_due_date=_past(1))
        assert m.is_overdue is True

    def test_is_overdue_false(self):
        m = MaintenanceSchedule(equipment_id="EQP-1", next_due_date=_future(1))
        assert m.is_overdue is False

    def test_is_overdue_no_date(self):
        m = MaintenanceSchedule(equipment_id="EQP-1")
        assert m.is_overdue is False

    def test_to_dict_includes_overdue(self):
        m = MaintenanceSchedule(equipment_id="EQP-1", next_due_date=_past(1))
        d = m.to_dict()
        assert "is_overdue" in d
        assert d["is_overdue"] is True


# ── Store Tests ─────────────────────────────────────────────────────


class TestMaintenanceStore:
    def test_create_and_get(self):
        sched = MaintenanceSchedule(
            equipment_id="EQP-1", service_type="oil_change",
            next_due_date=_future(10),
        )
        result = store.create_maintenance_schedule(sched)
        assert result["service_type"] == "oil_change"
        fetched = store.get_maintenance_schedule(result["schedule_id"])
        assert fetched is not None
        assert fetched["equipment_id"] == "EQP-1"

    def test_get_nonexistent(self):
        assert store.get_maintenance_schedule("MNT-NOPE") is None

    def test_list_by_equipment(self):
        store.create_maintenance_schedule(
            MaintenanceSchedule(equipment_id="EQP-A", service_type="oil_change")
        )
        store.create_maintenance_schedule(
            MaintenanceSchedule(equipment_id="EQP-B", service_type="brake_inspection")
        )
        result = store.list_maintenance_schedules(equipment_id="EQP-A")
        assert len(result) == 1

    def test_list_by_status(self):
        store.create_maintenance_schedule(
            MaintenanceSchedule(equipment_id="EQP-A", status="scheduled")
        )
        store.create_maintenance_schedule(
            MaintenanceSchedule(equipment_id="EQP-A", status="completed")
        )
        result = store.list_maintenance_schedules(status="completed")
        assert len(result) == 1

    def test_update(self):
        sched = MaintenanceSchedule(equipment_id="EQP-1", service_type="oil_change")
        created = store.create_maintenance_schedule(sched)
        updated = store.update_maintenance_schedule(
            created["schedule_id"], vendor="Quick Lube", cost_estimate=75.0
        )
        assert updated["vendor"] == "Quick Lube"
        assert updated["cost_estimate"] == 75.0

    def test_update_nonexistent(self):
        assert store.update_maintenance_schedule("MNT-NOPE", vendor="x") is None

    def test_update_ignores_disallowed(self):
        sched = MaintenanceSchedule(equipment_id="EQP-1")
        created = store.create_maintenance_schedule(sched)
        updated = store.update_maintenance_schedule(
            created["schedule_id"], equipment_id="EQP-OTHER"
        )
        assert updated["equipment_id"] == "EQP-1"

    def test_delete(self):
        sched = MaintenanceSchedule(equipment_id="EQP-1")
        created = store.create_maintenance_schedule(sched)
        assert store.delete_maintenance_schedule(created["schedule_id"]) is True
        assert store.get_maintenance_schedule(created["schedule_id"]) is None

    def test_delete_nonexistent(self):
        assert store.delete_maintenance_schedule("MNT-NOPE") is False

    def test_upcoming_maintenance(self):
        eqp = _make_equipment()
        store.create_maintenance_schedule(MaintenanceSchedule(
            equipment_id=eqp["equipment_id"],
            next_due_date=_future(3),
            status="scheduled",
        ))
        store.create_maintenance_schedule(MaintenanceSchedule(
            equipment_id=eqp["equipment_id"],
            next_due_date=_future(30),
            status="scheduled",
        ))
        result = store.get_upcoming_maintenance(days_ahead=7)
        assert len(result) == 1
        assert "unit_number" in result[0]

    def test_overdue_maintenance(self):
        eqp = _make_equipment()
        store.create_maintenance_schedule(MaintenanceSchedule(
            equipment_id=eqp["equipment_id"],
            next_due_date=_past(2),
            status="scheduled",
        ))
        store.create_maintenance_schedule(MaintenanceSchedule(
            equipment_id=eqp["equipment_id"],
            next_due_date=_future(5),
            status="scheduled",
        ))
        result = store.get_overdue_maintenance()
        assert len(result) == 1

    def test_completed_not_in_upcoming(self):
        eqp = _make_equipment()
        store.create_maintenance_schedule(MaintenanceSchedule(
            equipment_id=eqp["equipment_id"],
            next_due_date=_future(3),
            status="completed",
        ))
        result = store.get_upcoming_maintenance(days_ahead=7)
        assert len(result) == 0


# ── Service Tests ───────────────────────────────────────────────────


class TestMaintenanceService:
    def test_add_schedule(self):
        eqp = _make_equipment()
        result = services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            next_due_date=_future(30),
            interval_days=90,
        )
        assert result["service_type"] == "oil_change"
        assert result["interval_days"] == 90

    def test_add_schedule_equipment_not_found(self):
        with pytest.raises(ValueError, match="Equipment not found"):
            services.add_maintenance_schedule("EQP-NOPE", "oil_change")

    def test_add_schedule_invalid_type(self):
        eqp = _make_equipment()
        with pytest.raises(ValueError, match="Invalid service type"):
            services.add_maintenance_schedule(eqp["equipment_id"], "invalid")

    def test_list_schedules(self):
        eqp = _make_equipment()
        services.add_maintenance_schedule(eqp["equipment_id"], "oil_change")
        services.add_maintenance_schedule(eqp["equipment_id"], "brake_inspection")
        result = services.list_maintenance_schedules(equipment_id=eqp["equipment_id"])
        assert len(result) == 2

    def test_update_schedule(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(eqp["equipment_id"], "oil_change")
        updated = services.update_maintenance_schedule(
            created["schedule_id"], vendor="Joe's Shop"
        )
        assert updated["vendor"] == "Joe's Shop"

    def test_update_invalid_type(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(eqp["equipment_id"], "oil_change")
        with pytest.raises(ValueError, match="Invalid service type"):
            services.update_maintenance_schedule(
                created["schedule_id"], service_type="invalid"
            )

    def test_update_invalid_status(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(eqp["equipment_id"], "oil_change")
        with pytest.raises(ValueError, match="Invalid status"):
            services.update_maintenance_schedule(
                created["schedule_id"], status="invalid"
            )

    def test_delete_schedule(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(eqp["equipment_id"], "oil_change")
        assert services.delete_maintenance_schedule(created["schedule_id"]) is True

    def test_complete_maintenance_with_interval(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            next_due_date=_today(),
            interval_days=90,
        )
        result = services.complete_maintenance(
            created["schedule_id"],
            service_date=_today(),
        )
        assert result["status"] == "scheduled"
        assert result["last_service_date"] == _today()
        expected_next = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")
        assert result["next_due_date"] == expected_next

    def test_complete_maintenance_with_miles(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            interval_miles=5000,
        )
        result = services.complete_maintenance(
            created["schedule_id"],
            service_miles=50000,
        )
        assert result["last_service_miles"] == 50000
        assert result["next_due_miles"] == 55000

    def test_complete_maintenance_no_interval(self):
        eqp = _make_equipment()
        created = services.add_maintenance_schedule(
            eqp["equipment_id"], "dot_inspection",
        )
        result = services.complete_maintenance(created["schedule_id"])
        assert result["status"] == "completed"

    def test_complete_nonexistent(self):
        assert services.complete_maintenance("MNT-NOPE") is None

    def test_check_alerts_marks_overdue(self):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            next_due_date=_past(3),
        )
        result = services.check_maintenance_alerts()
        assert result["overdue"] >= 1

    def test_check_alerts_marks_due(self):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "brake_inspection",
            next_due_date=_future(3),
        )
        result = services.check_maintenance_alerts()
        assert result["due_soon"] >= 1

    def test_get_upcoming(self):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            next_due_date=_future(5),
        )
        result = services.get_upcoming_maintenance(days_ahead=7)
        assert len(result) == 1

    def test_get_overdue(self):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "tire_rotation",
            next_due_date=_past(2),
        )
        result = services.get_overdue_maintenance()
        assert len(result) == 1


# ── API Tests ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestMaintenanceAPI:
    def test_create(self, client):
        eqp = _make_equipment()
        r = client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
            "next_due_date": _future(30),
        })
        assert r.status_code == 201
        assert r.get_json()["service_type"] == "oil_change"

    def test_create_missing_equipment(self, client):
        r = client.post("/api/dispatch/maintenance", json={
            "service_type": "oil_change",
        })
        assert r.status_code == 400

    def test_create_bad_equipment(self, client):
        r = client.post("/api/dispatch/maintenance", json={
            "equipment_id": "EQP-NOPE",
            "service_type": "oil_change",
        })
        assert r.status_code == 400

    def test_list(self, client):
        eqp = _make_equipment()
        client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
        })
        r = client.get(f"/api/dispatch/maintenance?equipment_id={eqp['equipment_id']}")
        assert r.status_code == 200
        assert len(r.get_json()) == 1

    def test_get(self, client):
        eqp = _make_equipment()
        created = client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "brake_inspection",
        }).get_json()
        r = client.get(f"/api/dispatch/maintenance/{created['schedule_id']}")
        assert r.status_code == 200

    def test_get_not_found(self, client):
        r = client.get("/api/dispatch/maintenance/MNT-NOPE")
        assert r.status_code == 404

    def test_update(self, client):
        eqp = _make_equipment()
        created = client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
        }).get_json()
        r = client.patch(f"/api/dispatch/maintenance/{created['schedule_id']}", json={
            "vendor": "Quick Lube",
        })
        assert r.status_code == 200
        assert r.get_json()["vendor"] == "Quick Lube"

    def test_delete(self, client):
        eqp = _make_equipment()
        created = client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
        }).get_json()
        r = client.delete(f"/api/dispatch/maintenance/{created['schedule_id']}")
        assert r.status_code == 200

    def test_complete(self, client):
        eqp = _make_equipment()
        created = client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
            "interval_days": 90,
            "next_due_date": _today(),
        }).get_json()
        r = client.post(f"/api/dispatch/maintenance/{created['schedule_id']}/complete", json={
            "service_date": _today(),
        })
        assert r.status_code == 200
        assert r.get_json()["status"] == "scheduled"

    def test_upcoming(self, client):
        eqp = _make_equipment()
        client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
            "next_due_date": _future(3),
        })
        r = client.get("/api/dispatch/maintenance/upcoming?days=7")
        assert r.status_code == 200
        assert len(r.get_json()) == 1

    def test_overdue(self, client):
        eqp = _make_equipment()
        client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "tire_rotation",
            "next_due_date": _past(2),
        })
        r = client.get("/api/dispatch/maintenance/overdue")
        assert r.status_code == 200
        assert len(r.get_json()) == 1

    def test_check_alerts(self, client):
        eqp = _make_equipment()
        client.post("/api/dispatch/maintenance", json={
            "equipment_id": eqp["equipment_id"],
            "service_type": "oil_change",
            "next_due_date": _past(1),
        })
        r = client.post("/api/dispatch/maintenance/check-alerts")
        assert r.status_code == 200
        data = r.get_json()
        assert "overdue" in data


# ── Template Tests ──────────────────────────────────────────────────


class TestMaintenanceTemplate:
    def test_equipment_detail_shows_maintenance(self, client):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            description="Regular oil change",
            next_due_date=_future(10),
        )
        r = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        html = r.data.decode()
        assert "Maintenance Schedule" in html
        assert "Oil Change" in html
        assert "Regular oil change" in html

    def test_equipment_detail_has_add_form(self, client):
        eqp = _make_equipment()
        r = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        html = r.data.decode()
        assert "Add Service" in html
        assert "maint-type" in html

    def test_equipment_detail_overdue_styling(self, client):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "brake_inspection",
            next_due_date=_past(5),
        )
        r = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        html = r.data.decode()
        assert _past(5) in html

    def test_equipment_detail_empty_maintenance(self, client):
        eqp = _make_equipment()
        r = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        html = r.data.decode()
        assert "No maintenance schedules" in html

    def test_equipment_detail_complete_button(self, client):
        eqp = _make_equipment()
        services.add_maintenance_schedule(
            eqp["equipment_id"], "oil_change",
            next_due_date=_future(5),
        )
        r = client.get(f"/fleet/equipment/{eqp['equipment_id']}")
        html = r.data.decode()
        assert "completeMaintenance" in html
