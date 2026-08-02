"""Tests for detention tracking — model, store, service, API, and UI."""

from __future__ import annotations

import pytest

from dispatch import services, store
from dispatch.db import set_db_path
from dispatch.models import DetentionEvent, DETENTION_LOCATIONS, DETENTION_STATUSES


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


# ── Model Tests ────────────────────────────────────────────────────────


class TestDetentionModel:
    def test_defaults(self):
        det = DetentionEvent(load_id="L1")
        assert det.detention_id.startswith("DET-")
        assert det.location_type == "pickup"
        assert det.free_hours == 2.0
        assert det.hourly_rate == 75.0
        assert det.status == "active"
        assert det.started_at

    def test_invalid_location_type(self):
        with pytest.raises(ValueError, match="location_type"):
            DetentionEvent(load_id="L1", location_type="warehouse")

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="status"):
            DetentionEvent(load_id="L1", status="pending")

    def test_total_hours_no_end(self):
        det = DetentionEvent(load_id="L1")
        assert det.total_hours == 0.0

    def test_total_hours_computed(self):
        det = DetentionEvent(
            load_id="L1",
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T13:00:00Z",
        )
        assert det.total_hours == 5.0

    def test_billable_hours(self):
        det = DetentionEvent(
            load_id="L1",
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T13:00:00Z",
            free_hours=2.0,
        )
        assert det.billable_hours == 3.0

    def test_billable_hours_under_free(self):
        det = DetentionEvent(
            load_id="L1",
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T09:00:00Z",
            free_hours=2.0,
        )
        assert det.billable_hours == 0.0

    def test_billable_amount(self):
        det = DetentionEvent(
            load_id="L1",
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T13:00:00Z",
            free_hours=2.0,
            hourly_rate=100.0,
        )
        assert det.billable_amount == 300.0

    def test_to_dict_has_computed_fields(self):
        det = DetentionEvent(
            load_id="L1",
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T12:00:00Z",
            free_hours=1.0,
            hourly_rate=50.0,
        )
        d = det.to_dict()
        assert d["total_hours"] == 4.0
        assert d["billable_hours"] == 3.0
        assert d["billable_amount"] == 150.0

    def test_constants(self):
        assert "pickup" in DETENTION_LOCATIONS
        assert "delivery" in DETENTION_LOCATIONS
        assert "active" in DETENTION_STATUSES
        assert "completed" in DETENTION_STATUSES
        assert "billed" in DETENTION_STATUSES


# ── Store Tests ────────────────────────────────────────────────────────


class TestDetentionStore:
    def setup_method(self):
        from dispatch.models import Load
        self.load = store.create_load(Load(customer="Test"))

    def test_create_and_get(self):
        det = DetentionEvent(load_id=self.load["load_id"])
        created = store.create_detention(det)
        assert created["detention_id"] == det.detention_id
        fetched = store.get_detention(det.detention_id)
        assert fetched is not None
        assert fetched["load_id"] == self.load["load_id"]

    def test_list_by_load(self):
        d1 = DetentionEvent(load_id=self.load["load_id"])
        d2 = DetentionEvent(load_id=self.load["load_id"], location_type="delivery")
        store.create_detention(d1)
        store.create_detention(d2)
        result = store.list_detentions(load_id=self.load["load_id"])
        assert len(result) == 2

    def test_list_by_status(self):
        d1 = DetentionEvent(load_id=self.load["load_id"], status="active")
        d2 = DetentionEvent(load_id=self.load["load_id"], status="completed")
        store.create_detention(d1)
        store.create_detention(d2)
        active = store.list_detentions(status="active")
        assert any(d["detention_id"] == d1.detention_id for d in active)

    def test_update(self):
        det = DetentionEvent(load_id=self.load["load_id"])
        store.create_detention(det)
        updated = store.update_detention(det.detention_id, notes="Updated note")
        assert updated["notes"] == "Updated note"

    def test_update_not_found(self):
        assert store.update_detention("DET-FAKE", notes="x") is None

    def test_delete(self):
        det = DetentionEvent(load_id=self.load["load_id"])
        store.create_detention(det)
        assert store.delete_detention(det.detention_id) is True
        assert store.get_detention(det.detention_id) is None

    def test_delete_not_found(self):
        assert store.delete_detention("DET-FAKE") is False

    def test_get_not_found(self):
        assert store.get_detention("DET-FAKE") is None

    def test_computed_fields_from_store(self):
        det = DetentionEvent(
            load_id=self.load["load_id"],
            started_at="2026-01-15T08:00:00Z",
            ended_at="2026-01-15T11:00:00Z",
            free_hours=1.0,
            hourly_rate=50.0,
        )
        store.create_detention(det)
        fetched = store.get_detention(det.detention_id)
        assert fetched["total_hours"] == 3.0
        assert fetched["billable_hours"] == 2.0
        assert fetched["billable_amount"] == 100.0

    def test_delete_load_cascades(self):
        det = DetentionEvent(load_id=self.load["load_id"])
        store.create_detention(det)
        store.delete_load(self.load["load_id"])
        assert store.get_detention(det.detention_id) is None


# ── Service Tests ──────────────────────────────────────────────────────


class TestDetentionService:
    def setup_method(self):
        self.load = services.create_load("DetentionCorp")

    def test_start_detention(self):
        det = services.start_detention(self.load["load_id"])
        assert det["status"] == "active"
        assert det["location_type"] == "pickup"

    def test_start_detention_delivery(self):
        det = services.start_detention(self.load["load_id"], location_type="delivery")
        assert det["location_type"] == "delivery"

    def test_start_detention_custom_rates(self):
        det = services.start_detention(
            self.load["load_id"],
            free_hours=3.0,
            hourly_rate=100.0,
        )
        assert det["free_hours"] == 3.0
        assert det["hourly_rate"] == 100.0

    def test_start_duplicate_blocked(self):
        services.start_detention(self.load["load_id"])
        with pytest.raises(ValueError, match="already has an active"):
            services.start_detention(self.load["load_id"])

    def test_start_after_stop_allowed(self):
        det = services.start_detention(self.load["load_id"])
        services.stop_detention(det["detention_id"], create_expense=False)
        det2 = services.start_detention(self.load["load_id"])
        assert det2["status"] == "active"

    def test_start_load_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.start_detention("LOAD-FAKE")

    def test_stop_detention_no_bill(self):
        det = services.start_detention(
            self.load["load_id"],
            started_at="2026-01-15T08:00:00Z",
        )
        result = services.stop_detention(
            det["detention_id"],
            ended_at="2026-01-15T12:00:00Z",
            create_expense=False,
        )
        assert result["status"] == "completed"
        assert result["total_hours"] == 4.0

    def test_stop_detention_with_expense(self):
        services.confirm_rate(self.load["load_id"], rate_amount=1000.0)
        det = services.start_detention(
            self.load["load_id"],
            started_at="2026-01-15T08:00:00Z",
            free_hours=1.0,
            hourly_rate=50.0,
        )
        result = services.stop_detention(
            det["detention_id"],
            ended_at="2026-01-15T12:00:00Z",
        )
        assert result["status"] == "billed"
        assert result["expense_id"]
        expenses = services.list_expenses(self.load["load_id"])
        detention_exp = [e for e in expenses if e["category"] == "detention"]
        assert len(detention_exp) == 1
        assert detention_exp[0]["amount"] == 150.0

    def test_stop_no_billable_stays_completed(self):
        det = services.start_detention(
            self.load["load_id"],
            started_at="2026-01-15T08:00:00Z",
            free_hours=2.0,
        )
        result = services.stop_detention(
            det["detention_id"],
            ended_at="2026-01-15T09:00:00Z",
        )
        assert result["status"] == "completed"
        assert result.get("expense_id", "") == ""

    def test_stop_already_stopped(self):
        det = services.start_detention(self.load["load_id"])
        services.stop_detention(det["detention_id"], create_expense=False)
        with pytest.raises(ValueError, match="not active"):
            services.stop_detention(det["detention_id"])

    def test_stop_not_found(self):
        assert services.stop_detention("DET-FAKE") is None

    def test_list_detentions(self):
        services.start_detention(self.load["load_id"])
        result = services.list_detentions(load_id=self.load["load_id"])
        assert len(result) == 1

    def test_get_detention(self):
        det = services.start_detention(self.load["load_id"])
        result = services.get_detention(det["detention_id"])
        assert result is not None
        assert result["detention_id"] == det["detention_id"]

    def test_delete_detention(self):
        det = services.start_detention(self.load["load_id"])
        assert services.delete_detention(det["detention_id"]) is True
        assert services.get_detention(det["detention_id"]) is None

    def test_bundle_includes_detentions(self):
        services.start_detention(self.load["load_id"])
        bundle = services.get_load_bundle(self.load["load_id"])
        assert "detentions" in bundle
        assert len(bundle["detentions"]) == 1

    def test_detention_summary_empty(self):
        summary = services.get_detention_summary()
        assert summary["total_events"] == 0

    def test_detention_summary(self):
        l1 = services.create_load("C1")
        l2 = services.create_load("C2")
        d1 = services.start_detention(l1["load_id"], started_at="2026-01-15T08:00:00Z")
        services.stop_detention(d1["detention_id"], ended_at="2026-01-15T12:00:00Z", create_expense=False)
        services.start_detention(l2["load_id"], location_type="delivery")
        summary = services.get_detention_summary()
        assert summary["total_events"] == 2
        assert summary["active_count"] == 1
        assert summary["completed_count"] == 1
        assert summary["pickup_count"] == 1
        assert summary["delivery_count"] == 1


# ── API Tests ──────────────────────────────────────────────────────────


class TestDetentionAPI:
    def setup_method(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.load = services.create_load("APICorp")

    def test_start_via_api(self):
        r = self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={"location_type": "pickup", "free_hours": 1.5, "hourly_rate": 80},
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data["status"] == "active"
        assert data["free_hours"] == 1.5

    def test_start_invalid_location(self):
        r = self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={"location_type": "warehouse"},
        )
        assert r.status_code == 400

    def test_list_via_api(self):
        self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={},
        )
        r = self.client.get(f"/api/dispatch/loads/{self.load['load_id']}/detentions")
        assert r.status_code == 200
        data = r.get_json()
        assert data["count"] == 1

    def test_stop_via_api(self):
        r = self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={"started_at": "2026-01-15T08:00:00Z"},
        )
        det_id = r.get_json()["detention_id"]
        r2 = self.client.post(
            f"/api/dispatch/detentions/{det_id}/stop",
            json={"ended_at": "2026-01-15T12:00:00Z", "create_expense": False},
        )
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "completed"

    def test_stop_not_found(self):
        r = self.client.post(
            "/api/dispatch/detentions/DET-FAKE/stop",
            json={},
        )
        assert r.status_code == 404

    def test_update_via_api(self):
        r = self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={},
        )
        det_id = r.get_json()["detention_id"]
        r2 = self.client.patch(
            f"/api/dispatch/detentions/{det_id}",
            json={"notes": "Waiting on dock"},
            content_type="application/json",
        )
        assert r2.status_code == 200
        assert r2.get_json()["notes"] == "Waiting on dock"

    def test_delete_via_api(self):
        r = self.client.post(
            f"/api/dispatch/loads/{self.load['load_id']}/detentions",
            json={},
        )
        det_id = r.get_json()["detention_id"]
        r2 = self.client.delete(f"/api/dispatch/detentions/{det_id}")
        assert r2.status_code == 200

    def test_delete_not_found(self):
        r = self.client.delete("/api/dispatch/detentions/DET-FAKE")
        assert r.status_code == 404

    def test_summary_api(self):
        r = self.client.get("/api/dispatch/detentions/summary")
        assert r.status_code == 200
        data = r.get_json()
        assert "total_events" in data


# ── Template Tests ─────────────────────────────────────────────────────


class TestDetentionTemplate:
    def setup_method(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.load = services.create_load("TemplateCorp")

    def test_detail_page_shows_detention_section(self):
        r = self.client.get(f"/dispatch/{self.load['load_id']}")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Detention" in html
        assert "Start Detention" in html

    def test_detail_page_shows_active_detention(self):
        services.start_detention(self.load["load_id"], notes="Stuck at dock")
        r = self.client.get(f"/dispatch/{self.load['load_id']}")
        html = r.data.decode()
        assert "Stuck at dock" in html
        assert "Stop &amp; Bill" in html

    def test_detail_page_shows_completed_detention(self):
        det = services.start_detention(
            self.load["load_id"],
            started_at="2026-01-15T08:00:00Z",
        )
        services.stop_detention(
            det["detention_id"],
            ended_at="2026-01-15T12:00:00Z",
            create_expense=False,
        )
        r = self.client.get(f"/dispatch/{self.load['load_id']}")
        html = r.data.decode()
        assert "completed" in html
        assert "4.0h" in html

    def test_empty_state(self):
        r = self.client.get(f"/dispatch/{self.load['load_id']}")
        html = r.data.decode()
        assert "No detention events recorded" in html
