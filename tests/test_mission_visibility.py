"""Tests for the Mission Visibility Foundation (Lane A):

- dispatch/services.py::get_mission_visibility() -- the shared, externally-safe
  visibility snapshot for a load.
- Its wiring into the Driver Portal home page, the external Stakeholder
  Portal, and the Operations Feed's stalled-load / exception cards.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
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


def _stakeholder_url(load_id: str) -> str:
    token = notifications.make_stakeholder_token(load_id)
    return f"/portal/loads/{load_id}?token={token}"


# ── get_mission_visibility() ────────────────────────────────────────────


class TestGetMissionVisibility:
    def test_returns_expected_fields_for_a_real_visibility_record(self):
        load = services.create_load(customer="Mission Vis Co")
        services.add_milestone(load["load_id"], event_type="dispatched")

        mv = services.get_mission_visibility(load["load_id"])

        assert mv["current_status"] == "dispatched"
        assert mv["last_milestone"] == "dispatched"
        assert mv["next_expected_milestone"] == "en_route_pickup"
        assert mv["customer_note"] == ""
        assert mv["updated_at"]

    def test_customer_note_reflected_via_update_visibility_notes(self):
        load = services.create_load(customer="Mission Vis Note Co")
        services.update_visibility_notes(load["load_id"], customer_note="Running on time")

        mv = services.get_mission_visibility(load["load_id"])

        assert mv["customer_note"] == "Running on time"

    def test_internal_note_never_in_returned_dict(self):
        load = services.create_load(customer="Mission Vis Internal Co")
        services.update_visibility_notes(
            load["load_id"],
            customer_note="On schedule",
            internal_note="Driver called in sick once",
        )

        mv = services.get_mission_visibility(load["load_id"])

        assert "internal_note" not in mv
        assert "Driver called in sick once" not in mv.values()

    def test_no_visibility_record_returns_empty_shape_not_none(self):
        mv = services.get_mission_visibility("LOAD-DOES-NOT-EXIST")

        assert mv is not None
        assert mv == {
            "current_status": None,
            "last_milestone": None,
            "next_expected_milestone": None,
            "customer_note": "",
            "updated_at": None,
        }
        assert "internal_note" not in mv


# ── Driver Portal ────────────────────────────────────────────────────────


class TestDriverPortalMissionVisibility:
    def test_driver_home_includes_next_expected_milestone(self, client):
        driver = services.create_driver(name="Jane Trucker", phone="555-000-1111")
        load = services.create_load(customer="Driver Vis Co", driver_id=driver["driver_id"])
        services.add_milestone(load["load_id"], event_type="dispatched")

        with client.session_transaction() as sess:
            sess["driver_id"] = driver["driver_id"]

        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")

        assert resp.status_code == 200
        assert "Next Expected" in html
        assert "en_route_pickup" in html


# ── Stakeholder Portal ───────────────────────────────────────────────────


class TestStakeholderPortalMissionVisibility:
    def test_includes_next_expected_milestone_and_excludes_internal_note(self, client):
        load = services.create_load(customer="Stakeholder Vis Co")
        services.add_milestone(load["load_id"], event_type="dispatched")
        services.update_visibility_notes(
            load["load_id"],
            customer_note="On schedule",
            internal_note="Driver called in sick once",
        )

        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")

        assert resp.status_code == 200
        assert "en_route_pickup" in html
        assert "Driver called in sick once" not in html


# ── Operations Feed ──────────────────────────────────────────────────────


class TestOperationsFeedMissionVisibility:
    def test_stalled_load_card_summary_includes_next_expected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
        from datetime import datetime, timedelta, timezone

        from dispatch import store as dispatch_store
        from portal.models import operations_feed

        load = services.create_load(customer="Stalled Vis Co")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        dispatch_store.update_load(load["load_id"], updated_at=old_time)

        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "stalled_load"]

        assert len(cards) == 1
        assert "next expected: dispatched" in cards[0]["summary"]

    def test_exception_card_summary_includes_next_expected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
        from portal.models import operations_feed

        load = services.create_load(customer="Exception Vis Co")
        services.add_milestone(load["load_id"], event_type="dispatched")
        services.open_exception(
            load["load_id"], exception_type="damage", severity="critical", description="Cargo damaged"
        )

        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "exception"]

        assert len(cards) == 1
        assert "Cargo damaged" in cards[0]["summary"]
        assert "next expected: en_route_pickup" in cards[0]["summary"]
