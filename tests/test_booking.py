"""Tests for load board → engine booking integration.

Covers:
 1. Book action creates engine load from card data
 2. Card data fields map correctly to engine load
 3. Sandbox entry links to engine load
 4. Sandbox status updates to BOOKED
 5. Double-booking is rejected
 6. Only dispatch entries can be booked
 7. Engine status syncs back to sandbox
 8. Brief template shows engine load link
 9. Dispatch template shows Book button
10. Helper functions: window parsing, notes builder
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from dispatch import db
from portal.models import sandbox

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


SAMPLE_CARD_DATA = {
    "load_id": "LOAD-BOOK-001",
    "origin": "Jacksonville, FL 32202",
    "destination": "Savannah, GA 31401",
    "distance_miles": 140,
    "broker": "Southeast Freight Partners",
    "broker_email": "dispatch@sefp.example.com",
    "rate": 625,
    "rpm": 4.46,
    "pickup_window": "2026-07-30 06:00 - 10:00",
    "delivery_window": "2026-07-30 14:00 - 18:00",
    "equipment_required": "Dry Van 53'",
    "equipment_match": "match",
    "weight_lbs": 38000,
    "detention_history": "Low - avg 30 min",
    "broker_intelligence": "Reliable - 12 loads completed",
}


@pytest.fixture(autouse=True)
def portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    return tmp_path / "portal_data"


@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path):
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


@pytest.fixture
def app(tmp_path, monkeypatch):
    from portal.app import create_app
    from cin_lite import pending

    monkeypatch.setattr(pending, "_PENDING_DIR", tmp_path / "Pending")
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def dispatch_entry():
    return sandbox.create_entry(
        source_type="dispatch",
        source_id="LOAD-BOOK-001",
        title="Dry Van - JAX to SAV",
        card_data=SAMPLE_CARD_DATA.copy(),
        score=92,
    )


@pytest.fixture
def sam_entry():
    return sandbox.create_entry(
        source_type="sam",
        source_id="SOL-001",
        title="Some SAM contract",
        card_data={"solicitation_number": "SOL-001"},
    )


class TestBookAction:
    def test_book_creates_engine_load(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "engine_load" in data
        assert data["engine_load"]["load_id"].startswith("LOAD-")

    def test_book_updates_sandbox_status(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        data = resp.get_json()
        assert data["entry"]["status"] == "BOOKED"

    def test_book_links_engine_load_id(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]
        assert data["entry"]["engine_load_id"] == engine_load_id

    def test_book_maps_card_data_to_engine(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        load = resp.get_json()["engine_load"]
        assert load["customer"] == "Southeast Freight Partners"
        assert load["broker_shipper"] == "Southeast Freight Partners"
        assert load["pickup_location"] == "Jacksonville, FL 32202"
        assert load["delivery_location"] == "Savannah, GA 31401"
        assert load["equipment"] == "Dry Van 53'"
        assert "2026-07-30 06:00" in load["pickup_datetime"]
        assert "2026-07-30 14:00" in load["delivery_datetime"]

    def test_book_includes_notes(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        load = resp.get_json()["engine_load"]
        assert "LOAD-BOOK-001" in load["notes"]
        assert "$625" in load["notes"]
        assert "140 mi" in load["notes"]

    def test_double_book_rejected(self, client, dispatch_entry):
        client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        assert resp.status_code == 409
        assert "already booked" in resp.get_json()["error"]

    def test_book_sam_entry_rejected(self, client, sam_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": sam_entry["id"],
            "action": "book",
        })
        assert resp.status_code == 400
        assert "dispatch" in resp.get_json()["error"].lower()

    def test_book_not_found(self, client):
        resp = client.post("/api/action", json={
            "sandbox_id": "NONEXISTENT",
            "action": "book",
        })
        assert resp.status_code == 404

    def test_book_event_recorded(self, client, dispatch_entry):
        client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        entry = sandbox.get(dispatch_entry["id"])
        engine_events = [e for e in entry["events"] if e["action"] == "engine_linked"]
        assert len(engine_events) == 1

    def test_book_card_without_broker_uses_title(self, client):
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="LOAD-NOBROKER",
            title="Test Load No Broker",
            card_data={"origin": "JAX, FL", "destination": "ATL, GA"},
        )
        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        load = resp.get_json()["engine_load"]
        assert load["customer"] == "Test Load No Broker"


class TestEngineSync:
    def test_sync_updates_sandbox(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        engine_load_id = resp.get_json()["engine_load"]["load_id"]

        from dispatch import services
        services.add_milestone(engine_load_id, "dispatched")

        resp = client.post("/api/sync-engine")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["synced"][0]["engine_status"] == "dispatched"

    def test_sync_no_change(self, client, dispatch_entry):
        client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        client.post("/api/sync-engine")
        resp = client.post("/api/sync-engine")
        data = resp.get_json()
        assert data["count"] == 0

    def test_sync_skips_unlinked(self, client, dispatch_entry):
        resp = client.post("/api/sync-engine")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0

    def test_sync_through_lifecycle(self, client, dispatch_entry):
        resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        engine_load_id = resp.get_json()["engine_load"]["load_id"]

        from dispatch import services
        services.add_milestone(engine_load_id, "dispatched")
        services.add_milestone(engine_load_id, "arrived_pickup")
        services.add_milestone(engine_load_id, "loaded")
        services.add_milestone(engine_load_id, "departed_pickup")

        resp = client.post("/api/sync-engine")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["synced"][0]["engine_status"] == "in_transit"


class TestSandboxLinkModel:
    def test_link_engine_load(self, dispatch_entry):
        result = sandbox.link_engine_load(dispatch_entry["id"], "LOAD-20260801-ABC12345")
        assert result["engine_load_id"] == "LOAD-20260801-ABC12345"

    def test_link_not_found(self):
        with pytest.raises(KeyError):
            sandbox.link_engine_load("NONEXISTENT", "LOAD-X")

    def test_update_engine_status(self, dispatch_entry):
        sandbox.link_engine_load(dispatch_entry["id"], "LOAD-X")
        result = sandbox.update_engine_status(dispatch_entry["id"], "dispatched")
        assert result["card_data"]["engine_status"] == "dispatched"

    def test_update_engine_status_not_found(self):
        result = sandbox.update_engine_status("NONEXISTENT", "dispatched")
        assert result is None


class TestHelperFunctions:
    def test_extract_window_start_standard(self):
        from portal.routes.api import _extract_window_start
        assert _extract_window_start("2026-07-30 06:00 - 10:00") == "2026-07-30 06:00"

    def test_extract_window_start_full_datetime(self):
        from portal.routes.api import _extract_window_start
        assert _extract_window_start("2026-07-30 06:00 - 2026-07-30 10:00") == "2026-07-30 06:00"

    def test_extract_window_start_empty(self):
        from portal.routes.api import _extract_window_start
        assert _extract_window_start("") == ""

    def test_extract_window_start_none(self):
        from portal.routes.api import _extract_window_start
        assert _extract_window_start(None) == ""

    def test_build_booking_notes(self):
        from portal.routes.api import _build_booking_notes
        entry = {"source_id": "LOAD-001"}
        cd = {"rate": 625, "rpm": 4.46, "distance_miles": 140, "weight_lbs": 38000}
        result = _build_booking_notes(cd, entry)
        assert "LOAD-001" in result
        assert "$625" in result
        assert "140 mi" in result
        assert "38000 lbs" in result

    def test_build_booking_notes_minimal(self):
        from portal.routes.api import _build_booking_notes
        result = _build_booking_notes({}, {})
        assert result == ""


class TestTemplateRendering:
    def test_dispatch_page_shows_book_button(self, client, dispatch_entry):
        resp = client.get("/dispatch")
        assert resp.status_code == 200
        assert b"Book Load" in resp.data

    def test_dispatch_page_hides_actions_when_booked(self, client, dispatch_entry):
        client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Engine Load:" in html

    def test_brief_page_shows_engine_link(self, client, dispatch_entry):
        book_resp = client.post("/api/action", json={
            "sandbox_id": dispatch_entry["id"],
            "action": "book",
        })
        engine_load_id = book_resp.get_json()["engine_load"]["load_id"]
        resp = client.get(f"/brief/{dispatch_entry['id']}")
        assert resp.status_code == 200
        assert engine_load_id.encode() in resp.data

    def test_brief_page_shows_book_button_for_dispatch(self, client, dispatch_entry):
        resp = client.get(f"/brief/{dispatch_entry['id']}")
        assert b"Book Load" in resp.data

    def test_brief_page_hides_book_button_for_sam(self, client, sam_entry):
        resp = client.get(f"/brief/{sam_entry['id']}")
        assert b"Book Load" not in resp.data
