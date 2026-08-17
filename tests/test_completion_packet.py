"""Tests for the End Load / Completion Packet workflow.

Covers: dispatch.services.build_completion_packet (assembly + eligibility gate), the
/end-load API route (routes to Publisher, idempotent, never auto-sends), and the
Completion Packet section on the load detail page.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


def _delivered_load(**overrides):
    load = services.create_load(customer="Packet Co", **overrides)
    services.update_load(load["load_id"], status="dispatched")
    services.update_load(load["load_id"], status="en_route_pickup")
    services.update_load(load["load_id"], status="at_pickup")
    services.update_load(load["load_id"], status="picked_up")
    services.update_load(load["load_id"], status="in_transit")
    services.update_load(load["load_id"], status="at_delivery")
    services.update_load(load["load_id"], status="delivered")
    return services.get_load(load["load_id"])


# ── dispatch.services.build_completion_packet ───────────────────────────


class TestBuildCompletionPacket:
    def test_rejects_unknown_load(self, client):
        with pytest.raises(ValueError, match="not found"):
            services.build_completion_packet("nope")

    def test_rejects_load_not_yet_delivered(self, client):
        load = services.create_load(customer="Too Early Co")
        with pytest.raises(ValueError, match="delivered or completed"):
            services.build_completion_packet(load["load_id"])

    def test_assembles_available_and_missing(self, client):
        load = _delivered_load()
        packet = services.build_completion_packet(load["load_id"])
        assert packet["load_id"] == load["load_id"]
        assert "Rate Confirmation" in packet["missing"]
        assert "POD" in packet["missing"]

    def test_picks_up_existing_artifacts(self, client):
        load = _delivered_load()
        services.confirm_rate(load["load_id"], rate_amount=1500)
        services.generate_pod(load["load_id"])
        packet = services.build_completion_packet(load["load_id"])
        assert "Rate Confirmation" in packet["available"]
        assert "POD" in packet["available"]
        assert packet["rate_confirmation"]["rate_amount"] == 1500
        assert len(packet["pods"]) == 1

    def test_matches_broker_contact_by_name(self, client):
        services.add_broker_contact(company_name="Acme Brokerage")
        load = _delivered_load(broker_shipper="Acme Brokerage")
        packet = services.build_completion_packet(load["load_id"])
        assert packet["broker_contact"] is not None
        assert packet["broker_contact"]["company_name"] == "Acme Brokerage"
        assert "Broker Contact" in packet["available"]


# ── /api/dispatch/loads/<id>/end-load ────────────────────────────────


class TestEndLoadRoute:
    def test_end_load_requires_delivered_status(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "Not Ready"})
        load = resp.get_json()["load"]
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        assert resp.status_code == 409

    def test_end_load_creates_packet_and_publisher_action(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "End Load Co"})
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})

        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["packet"]["load_id"] == load["load_id"]
        assert data["packet"]["status"] == "ROUTED"
        assert data["publisher_action"]["action_type"] == "Completion Packet Ready"
        assert data["publisher_action"]["sandbox_id"] == f"LOAD-{load['load_id']}"
        assert data["publisher_action"]["status"] == "PENDING"

    def test_end_load_never_auto_approves_or_sends(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "No Auto Send Co"})
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")
        action = resp.get_json()["publisher_action"]
        assert action["status"] == "PENDING"
        assert action["human_approval_required"] is True

    def test_end_load_is_idempotent(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "Idempotent Co"})
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})

        first = client.post(f"/api/dispatch/loads/{load['load_id']}/end-load").get_json()
        second = client.post(f"/api/dispatch/loads/{load['load_id']}/end-load").get_json()
        assert first["packet"]["id"] == second["packet"]["id"]
        assert second.get("already_ended") is True

    def test_get_completion_packet_404_before_end_load(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "No Packet Yet Co"})
        load = r.get_json()["load"]
        resp = client.get(f"/api/dispatch/loads/{load['load_id']}/completion-packet")
        assert resp.status_code == 404


# ── Load detail page ─────────────────────────────────────────────────


class TestCompletionPacketPage:
    def test_end_load_button_hidden_before_delivery(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "Page Not Ready Co"})
        load = r.get_json()["load"]
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        assert b"onclick=\"endLoad(" not in resp.data

    def test_end_load_button_shown_when_delivered(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "Page Ready Co"})
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b"onclick=\"endLoad(" in resp.data

    def test_page_shows_packet_summary_after_end_load(self, client):
        r = client.post("/api/dispatch/loads", json={"customer": "Page Summary Co"})
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
        client.post(f"/api/dispatch/loads/{load['load_id']}/end-load")

        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        assert b"ROUTED" in resp.data
        assert b"No broker or customer email is sent automatically" in resp.data
