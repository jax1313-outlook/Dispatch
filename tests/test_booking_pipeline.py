"""Tests for booking pipeline improvements — PR 24.

Covers: auto-rate confirmation on booking, multi-tier card visuals,
and booking API behavior.
"""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc, store as dispatch_store
from dispatch.db import set_db_path
from portal import helpers


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Card visual tiers ─────────────────────────────────────────────────


class TestCardVisualTiers:
    # The bands were 90 / 75 / 60 / 40 against a 100-point score. The engine's
    # maximum is 90 (dispatch.scoring.MAX_SCORE), so since CO-3 (2026-09-14) each
    # band keeps its share of the real maximum: 81 / 67.5 / 54 / 36.
    def test_high_value_at_ninety_percent_of_max(self):
        v = helpers.card_visual(81)
        assert v["css"] == "card-high"
        assert "HIGH VALUE" in v["label"]

    def test_the_real_maximum_is_high_value(self):
        from dispatch.scoring import MAX_SCORE
        assert helpers.card_visual(MAX_SCORE)["css"] == "card-high"
        assert helpers.card_visual(100)["css"] == "card-high"

    def test_strong_match_68(self):
        v = helpers.card_visual(68)
        assert v["css"] == "card-strong"
        assert "STRONG" in v["label"]

    def test_strong_match_80(self):
        v = helpers.card_visual(80)
        assert v["css"] == "card-strong"

    def test_moderate_54(self):
        v = helpers.card_visual(54)
        assert v["css"] == "card-moderate"
        assert "MODERATE" in v["label"]

    def test_moderate_67(self):
        v = helpers.card_visual(67)
        assert v["css"] == "card-moderate"

    def test_low_value_36(self):
        v = helpers.card_visual(36)
        assert v["css"] == "card-low"
        assert "LOW" in v["label"]

    def test_low_value_53(self):
        v = helpers.card_visual(53)
        assert v["css"] == "card-low"

    def test_poor_match_0(self):
        v = helpers.card_visual(0)
        assert v["css"] == "card-poor"
        assert "POOR" in v["label"]

    def test_poor_match_35(self):
        v = helpers.card_visual(35)
        assert v["css"] == "card-poor"

    def test_none_score_with_decision(self):
        v = helpers.card_visual(None, decision={"action": "approve_proposal", "priority": "high"})
        assert v["css"] == "card-high"

    def test_none_score_no_decision(self):
        v = helpers.card_visual(None)
        assert v["css"] == "card-default"


# ── Auto rate confirmation on booking ──────────────────────────────────


class TestAutoRateConfirmOnBooking:
    def _make_dispatch_entry(self, sandbox, rate=None, rpm=None, distance=None):
        """Create a sandbox entry with dispatch card data."""
        cd = {
            "broker": "Test Broker",
            "origin": "Dallas, TX",
            "destination": "Houston, TX",
            "pickup_window": "2026-08-01 06:00 - 10:00",
            "delivery_window": "2026-08-01 14:00 - 18:00",
            "equipment_required": "dry_van",
        }
        if rate is not None:
            cd["rate"] = rate
        if rpm is not None:
            cd["rpm"] = rpm
        if distance is not None:
            cd["distance_miles"] = distance

        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="TEST-001",
            title="Test Load",
            card_data=cd,
            score=85,
        )
        return entry

    def test_booking_creates_rate_confirmation(self, client, tmp_path, monkeypatch):
        from portal.models import sandbox
        entry = self._make_dispatch_entry(sandbox, rate=1500, rpm=3.50, distance=428)

        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]

        rate = dispatch_svc.get_rate_confirmation(engine_load_id)
        assert rate is not None
        assert rate["rate_amount"] == 1500.0
        assert rate["distance_miles"] == 428.0
        assert rate["confirmed_by"] == "booking-auto"
        assert "RPM" in rate["notes"]

    def test_booking_no_rate_skips_confirmation(self, client, tmp_path, monkeypatch):
        from portal.models import sandbox
        entry = self._make_dispatch_entry(sandbox)

        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]

        rate = dispatch_svc.get_rate_confirmation(engine_load_id)
        assert rate is None

    def test_booking_invalid_rate_skips_confirmation(self, client, tmp_path, monkeypatch):
        from portal.models import sandbox
        entry = self._make_dispatch_entry(sandbox, rate="TBD")

        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]

        rate = dispatch_svc.get_rate_confirmation(engine_load_id)
        assert rate is None

    def test_booking_rate_with_no_distance(self, client, tmp_path, monkeypatch):
        from portal.models import sandbox
        entry = self._make_dispatch_entry(sandbox, rate=800)

        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]

        rate = dispatch_svc.get_rate_confirmation(engine_load_id)
        assert rate is not None
        assert rate["rate_amount"] == 800.0
        assert rate["distance_miles"] == 0.0

    def test_booked_load_shows_revenue_in_financials(self, client, tmp_path, monkeypatch):
        from portal.models import sandbox
        entry = self._make_dispatch_entry(sandbox, rate=2000, distance=500)

        resp = client.post("/api/action", json={
            "sandbox_id": entry["id"],
            "action": "book",
        })
        data = resp.get_json()
        engine_load_id = data["engine_load"]["load_id"]

        financials = dispatch_svc.get_financials(engine_load_id)
        assert financials is not None
        assert financials["summary"]["revenue"] == 2000.0


# ── Auto rate confirm helper directly ──────────────────────────────────


class TestAutoRateConfirmHelper:
    def test_auto_rate_with_numeric_string(self):
        from portal.routes.api import _auto_rate_confirm
        load = dispatch_svc.create_load(customer="Test")
        _auto_rate_confirm(dispatch_svc, load["load_id"], {"rate": "1200.50", "distance_miles": "350"})
        rate = dispatch_svc.get_rate_confirmation(load["load_id"])
        assert rate is not None
        assert rate["rate_amount"] == 1200.50
        assert rate["distance_miles"] == 350.0

    def test_auto_rate_with_none_rate(self):
        from portal.routes.api import _auto_rate_confirm
        load = dispatch_svc.create_load(customer="Test")
        _auto_rate_confirm(dispatch_svc, load["load_id"], {"rate": None})
        rate = dispatch_svc.get_rate_confirmation(load["load_id"])
        assert rate is None

    def test_auto_rate_with_empty_cd(self):
        from portal.routes.api import _auto_rate_confirm
        load = dispatch_svc.create_load(customer="Test")
        _auto_rate_confirm(dispatch_svc, load["load_id"], {})
        rate = dispatch_svc.get_rate_confirmation(load["load_id"])
        assert rate is None

    def test_auto_rate_with_invalid_distance(self):
        from portal.routes.api import _auto_rate_confirm
        load = dispatch_svc.create_load(customer="Test")
        _auto_rate_confirm(dispatch_svc, load["load_id"], {"rate": 500, "distance_miles": "N/A"})
        rate = dispatch_svc.get_rate_confirmation(load["load_id"])
        assert rate is not None
        assert rate["distance_miles"] == 0.0
