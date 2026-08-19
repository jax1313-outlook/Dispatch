"""Tests for Lane E: Publisher Packet Status Visibility.

Publisher's queue (portal/models/publisher.py::create_action()) is keyed by
sandbox_id, a GovCon/sandbox-oriented concept -- freight loads have no
sandbox_id of their own. dispatch/services.py::get_publisher_status() reuses
the synthetic sandbox_id convention already established for freight loads
(f"LOAD-{load_id}", mirroring cin_lite's f"GOVCON-{contract_id}") rather than
adding a load_id field to Publisher's schema.

Covers: the helper itself, the Stakeholder Portal's plain-English rendering,
and the Driver Portal dashboard's plain-English rendering.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry
from portal.models import publisher


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))


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


# ── get_publisher_status() ───────────────────────────────────────────


class TestGetPublisherStatus:
    def test_load_with_no_packet_has_packet_false(self):
        load = services.create_load(customer="No Packet Co")
        result = services.get_publisher_status(load["load_id"])
        assert result == {"has_packet": False, "status": None, "action_type": None}

    def test_load_with_pending_packet_reports_it(self):
        load = services.create_load(customer="Pending Packet Co")
        publisher.create_action(
            "Broker Packet Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="New broker lane",
        )
        result = services.get_publisher_status(load["load_id"])
        assert result["has_packet"] is True
        assert result["status"] == "PENDING"
        assert result["action_type"] == "Broker Packet Required"

    def test_load_with_approved_packet_still_reports_it(self):
        """APPROVED is exactly the good-news status a broker/driver wants to
        see -- unlike the Operations Feed (which hides APPROVED/ARCHIVED
        actions from its own separate feed), this helper must not filter it
        out."""
        load = services.create_load(customer="Approved Packet Co")
        action = publisher.create_action(
            "Rate Confirmation Package Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="Rate confirmed",
        )
        publisher.update_action_status(action["id"], "DRAFT")
        publisher.update_action_status(action["id"], "READY")
        publisher.update_action_status(action["id"], "APPROVED", approved_by="mike")
        result = services.get_publisher_status(load["load_id"])
        assert result == {
            "has_packet": True,
            "status": "APPROVED",
            "action_type": "Rate Confirmation Package Required",
        }

    def test_unrelated_loads_and_sandboxes_do_not_match(self):
        load_a = services.create_load(customer="Load A Co")
        load_b = services.create_load(customer="Load B Co")
        publisher.create_action(
            "Broker Packet Required",
            sandbox_id=f"LOAD-{load_b['load_id']}",
            trigger_reason="x",
        )
        publisher.create_action(
            "GovCon Proposal Draft Required", sandbox_id="GOVCON-9999", trigger_reason="y",
        )
        result = services.get_publisher_status(load_a["load_id"])
        assert result["has_packet"] is False

    def test_multiple_matches_returns_most_recently_updated(self):
        load = services.create_load(customer="Multi Packet Co")
        sandbox_id = f"LOAD-{load['load_id']}"
        older = publisher.create_action(
            "Broker Packet Required", sandbox_id=sandbox_id, trigger_reason="first",
        )
        newer = publisher.create_action(
            "Rate Sheet Request", sandbox_id=sandbox_id, trigger_reason="second",
        )
        # Both actions were created "now" (second-granularity timestamps),
        # so force a deterministic updated_at ordering directly rather than
        # relying on wall-clock timing between two create_action() calls.
        queue = publisher.get_queue()
        for action in queue:
            if action["id"] == older["id"]:
                action["updated_at"] = "2020-01-01T00:00:00Z"
            elif action["id"] == newer["id"]:
                action["updated_at"] = "2020-01-02T00:00:00Z"
        publisher._save(queue)

        result = services.get_publisher_status(load["load_id"])
        assert result["has_packet"] is True
        assert result["action_type"] == "Rate Sheet Request"
        assert result["status"] == "PENDING"


# ── Stakeholder Portal ───────────────────────────────────────────────


class TestStakeholderPortalPublisherStatus:
    def test_pending_packet_shows_being_prepared_language(self, client):
        load = services.create_load(customer="Stakeholder Pending Co")
        publisher.create_action(
            "Broker Packet Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="x",
        )
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Your documentation package is being prepared." in html

    def test_draft_packet_shows_being_prepared_language(self, client):
        load = services.create_load(customer="Stakeholder Draft Co")
        action = publisher.create_action(
            "Direct Shipper Packet Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="x",
        )
        publisher.update_action_status(action["id"], "DRAFT")
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Your documentation package is being prepared." in html

    def test_no_packet_shows_nothing(self, client):
        load = services.create_load(customer="Stakeholder No Packet Co")
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Documentation Package" not in html
        assert "documentation package" not in html.lower()

    def test_approved_packet_shows_finalized_language(self, client):
        load = services.create_load(customer="Stakeholder Approved Co")
        action = publisher.create_action(
            "Rate Confirmation Package Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="x",
        )
        publisher.update_action_status(action["id"], "DRAFT")
        publisher.update_action_status(action["id"], "READY")
        publisher.update_action_status(action["id"], "APPROVED", approved_by="mike")
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Your documentation package has been finalized." in html


# ── Driver Portal ────────────────────────────────────────────────────


@pytest.fixture
def driver():
    return services.create_driver(name="Packet Status Driver", phone="904-555-0199")


def _login(client, driver):
    pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
    client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})


class TestDriverPortalPublisherStatus:
    def test_pending_packet_shows_being_prepared_language(self, client, driver):
        load = services.create_load(customer="Driver Pending Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        publisher.create_action(
            "Broker Packet Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="x",
        )
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Your documentation package is being prepared." in html

    def test_no_packet_shows_nothing(self, client, driver):
        load = services.create_load(customer="Driver No Packet Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Documentation Package" not in html
        assert "documentation package" not in html.lower()

    def test_approved_packet_shows_finalized_language(self, client, driver):
        load = services.create_load(customer="Driver Approved Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        action = publisher.create_action(
            "Rate Confirmation Package Required",
            sandbox_id=f"LOAD-{load['load_id']}",
            trigger_reason="x",
        )
        publisher.update_action_status(action["id"], "DRAFT")
        publisher.update_action_status(action["id"], "READY")
        publisher.update_action_status(action["id"], "APPROVED", approved_by="mike")
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Your documentation package has been finalized." in html
