"""Tests for load duplication and conflict resolution notes."""

from __future__ import annotations

import json
import os

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    os.environ.setdefault("SECRET_KEY", "test")
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


# ── Load Duplication (service layer) ────────────────────────────────


class TestDuplicateLoadService:
    def test_duplicate_copies_fields(self):
        original = services.create_load(
            customer="Acme Corp",
            broker_shipper="Broker X",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
            pickup_datetime="2026-08-01T08:00:00Z",
            delivery_datetime="2026-08-02T14:00:00Z",
            equipment="Flatbed",
            notes="Handle with care",
        )
        dup = services.duplicate_load(original["load_id"])
        assert dup["load_id"] != original["load_id"]
        assert dup["customer"] == "Acme Corp"
        assert dup["broker_shipper"] == "Broker X"
        assert dup["pickup_location"] == "Dallas, TX"
        assert dup["delivery_location"] == "Houston, TX"
        assert dup["equipment"] == "Flatbed"
        assert dup["notes"] == "Handle with care"
        assert dup["status"] == "created"

    def test_duplicate_does_not_copy_driver_or_equipment_ids(self):
        drv = services.create_driver(name="Test Driver")
        eqp = services.create_equipment(unit_number="T-100")
        original = services.create_load(
            customer="Customer",
            driver_id=drv["driver_id"],
            equipment_id=eqp["equipment_id"],
        )
        dup = services.duplicate_load(original["load_id"])
        assert dup["driver_id"] == ""
        assert dup["equipment_id"] == ""

    def test_duplicate_creates_visibility(self):
        original = services.create_load(customer="Customer")
        dup = services.duplicate_load(original["load_id"])
        vis = services.get_visibility(dup["load_id"])
        assert vis is not None
        assert vis["current_status"] == "created"

    def test_duplicate_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.duplicate_load("NONEXISTENT")

    def test_duplicate_independent_lifecycle(self):
        original = services.create_load(customer="Customer")
        services.update_load(original["load_id"], status="dispatched")
        dup = services.duplicate_load(original["load_id"])
        assert dup["status"] == "created"
        updated_original = services.get_load(original["load_id"])
        assert updated_original["status"] == "dispatched"


# ── Load Duplication (API layer) ────────────────────────────────────


class TestDuplicateLoadAPI:
    def test_duplicate_via_api(self, client):
        r = client.post(
            "/api/dispatch/loads",
            json={"customer": "API Corp", "pickup_location": "NYC"},
        )
        load_id = r.get_json()["load"]["load_id"]

        r = client.post(f"/api/dispatch/loads/{load_id}/duplicate")
        assert r.status_code == 201
        data = r.get_json()
        assert data["status"] == "ok"
        assert data["load"]["customer"] == "API Corp"
        assert data["load"]["pickup_location"] == "NYC"
        assert data["load"]["load_id"] != load_id

    def test_duplicate_not_found_api(self, client):
        r = client.post("/api/dispatch/loads/MISSING/duplicate")
        assert r.status_code == 404
        assert "not found" in r.get_json()["error"].lower()


# ── Load Detail Page — Duplicate Button ─────────────────────────────


class TestDuplicateButton:
    def test_duplicate_button_present(self, client):
        r = client.post(
            "/api/dispatch/loads",
            json={"customer": "Test"},
        )
        load_id = r.get_json()["load"]["load_id"]

        r = client.get(f"/dispatch/{load_id}")
        assert r.status_code == 200
        html = r.data.decode()
        assert "duplicateLoad" in html
        assert "Duplicate" in html


# ── Conflict Resolution Notes ───────────────────────────────────────


class TestConflictResolutionNotes:
    def test_resolve_with_note(self):
        from portal.models import conflict

        cn = conflict.create_notice(
            conflict_type="missing_data",
            severity="medium",
            sandbox_id="TEST-001",
            explanation="Missing broker email",
            recommended_action="Add broker contact",
        )
        resolved = conflict.resolve_notice(cn["id"], resolution_note="Contacted broker, email added")
        assert resolved["resolved"] is True
        assert resolved["resolution_note"] == "Contacted broker, email added"
        assert "resolved_at" in resolved

    def test_resolve_without_note(self):
        from portal.models import conflict

        cn = conflict.create_notice(
            conflict_type="data_mismatch",
            severity="low",
            sandbox_id="TEST-002",
            explanation="Weight mismatch",
            recommended_action="Verify weight",
        )
        resolved = conflict.resolve_notice(cn["id"])
        assert resolved["resolved"] is True
        assert resolved.get("resolved_at") is not None
        assert "resolution_note" not in resolved

    def test_resolve_via_api_with_note(self, client):
        from portal.models import conflict

        cn = conflict.create_notice(
            conflict_type="missing_data",
            severity="high",
            sandbox_id="TEST-003",
            explanation="Missing pickup time",
            recommended_action="Enter time",
        )
        r = client.post(
            "/api/conflict/resolve",
            json={"notice_id": cn["id"], "resolution_note": "Time confirmed with driver"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["notice"]["resolved"] is True
        assert data["notice"]["resolution_note"] == "Time confirmed with driver"

    def test_resolve_via_api_without_note(self, client):
        from portal.models import conflict

        cn = conflict.create_notice(
            conflict_type="missing_data",
            severity="low",
            sandbox_id="TEST-004",
            explanation="Minor issue",
            recommended_action="Fix it",
        )
        r = client.post(
            "/api/conflict/resolve",
            json={"notice_id": cn["id"]},
        )
        assert r.status_code == 200
        assert r.get_json()["notice"]["resolved"] is True


# ── Conflicts Page ─────────────────────────────────────────────────


class TestConflictsPage:
    def test_conflicts_page_shows_resolution_note(self, client):
        from portal.models import conflict

        cn = conflict.create_notice(
            conflict_type="data_mismatch",
            severity="medium",
            sandbox_id="TEST-005",
            explanation="Address mismatch",
            recommended_action="Verify",
        )
        conflict.resolve_notice(cn["id"], resolution_note="Corrected address in system")
        r = client.get("/conflicts")
        assert r.status_code == 200
        html = r.data.decode()
        assert "Corrected address in system" in html

    def test_conflicts_page_resolve_button_present(self, client):
        from portal.models import conflict

        conflict.create_notice(
            conflict_type="missing_data",
            severity="high",
            sandbox_id="TEST-006",
            explanation="Missing data",
            recommended_action="Add it",
        )
        r = client.get("/conflicts")
        html = r.data.decode()
        assert "resolveConflict" in html
