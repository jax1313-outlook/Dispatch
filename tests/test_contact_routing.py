"""Tests for Lane D: Contact Routing Foundation -- the shared
dispatch.services.get_load_contacts() helper and its two consumers, the
Driver Portal (portal/routes/driver_portal.py) and the Stakeholder Portal
(portal/routes/stakeholder.py via dispatch.services.build_stakeholder_view).

Covers: the helper's own contract (matching broker contact, no
broker_shipper set, unknown load_id, dispatch_email always present), that
the Driver Portal's existing per-load broker-contact display keeps working
after the refactor to use the shared helper, the new page-level "everyone I
might need to call today" unified contact summary (deduped by broker_id
across a driver's active loads), and that the Stakeholder Portal now
discloses dispatch/broker contact info (a real gap Lane D closes) while
still rendering cleanly when no broker contact is on file.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry


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


@pytest.fixture
def driver():
    return services.create_driver(name="Jane Trucker", phone="904-555-0100")


def _url(load_id: str, token: str | None = None) -> str:
    token = notifications.make_stakeholder_token(load_id) if token is None else token
    return f"/portal/loads/{load_id}?token={token}"


# ── get_load_contacts() unit tests ───────────────────────────────────


class TestGetLoadContacts:
    def test_matching_broker_contact_returned(self):
        services.add_broker_contact(
            company_name="Acme Brokerage", contact_name="Bob Broker",
            phone="555-111-2222", email="bob@acmebrokerage.example.com",
        )
        load = services.create_load(customer="Contact Co", broker_shipper="Acme Brokerage")
        result = services.get_load_contacts(load["load_id"])
        assert result["broker_contact"] is not None
        assert result["broker_contact"]["contact_name"] == "Bob Broker"
        assert result["broker_contact"]["phone"] == "555-111-2222"

    def test_no_broker_shipper_returns_none(self):
        load = services.create_load(customer="No Broker Co")
        result = services.get_load_contacts(load["load_id"])
        assert result["broker_contact"] is None

    def test_unknown_load_id_returns_dict_not_crash(self):
        result = services.get_load_contacts("LOAD-DOES-NOT-EXIST")
        assert result["broker_contact"] is None
        assert result["dispatch_email"]
        assert "@" in result["dispatch_email"]

    def test_dispatch_email_always_present(self):
        load = services.create_load(customer="Dispatch Email Co")
        result = services.get_load_contacts(load["load_id"])
        assert result["dispatch_email"]
        assert result["dispatch_email"] == services.reviewer_contact_email()

    def test_dispatch_email_present_even_with_broker_match(self):
        services.add_broker_contact(company_name="Zenith Freight")
        load = services.create_load(customer="Both Co", broker_shipper="Zenith Freight")
        result = services.get_load_contacts(load["load_id"])
        assert result["dispatch_email"]
        assert result["broker_contact"] is not None


# ── Driver Portal ─────────────────────────────────────────────────────


class TestDriverPortalContactRouting:
    def test_home_shows_broker_contact(self, client, driver):
        """Pre-existing test from tests/test_driver_pin_registry.py, kept
        here verbatim as a second guard on the get_load_contacts() refactor
        of driver_portal.py::driver_home() -- must keep passing unchanged."""
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        services.add_broker_contact(
            company_name="Acme Brokerage", contact_name="Bob Broker",
            phone="555-111-2222", email="bob@acmebrokerage.example.com",
        )
        load = services.create_load(customer="Contact Co", broker_shipper="Acme Brokerage")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert "Bob Broker" in html
        assert "555-111-2222" in html

    def test_home_unified_contact_summary_dedups_broker_across_loads(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        services.add_broker_contact(
            company_name="Shared Brokerage", contact_name="Sam Shared",
            phone="555-999-8888", email="sam@sharedbrokerage.example.com",
        )
        load1 = services.create_load(customer="Dedup Co 1", broker_shipper="Shared Brokerage")
        services.update_load(load1["load_id"], driver_id=driver["driver_id"])
        load2 = services.create_load(customer="Dedup Co 2", broker_shipper="Shared Brokerage")
        services.update_load(load2["load_id"], driver_id=driver["driver_id"])

        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")

        # The page-level summary card dedups by broker_id: exactly one
        # mention of Sam Shared within that card, even though the driver
        # has two active loads for the same broker.
        summary_card = html.split("Broker Contacts (today's loads):", 1)[1]
        summary_card = summary_card.split("Your Active Loads", 1)[0]
        assert summary_card.count("Sam Shared") == 1
        assert summary_card.count("555-999-8888") == 1

        # The per-load broker-contact display is additive, not replaced --
        # it still appears once per load-block (two loads here).
        assert html.count("Sam Shared") == 3

    def test_home_shows_dispatch_contact_email(self, client, driver):
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"@" in resp.data


# ── Stakeholder Portal ────────────────────────────────────────────────


class TestStakeholderPortalContactRouting:
    def test_shows_broker_contact_when_present(self, client):
        services.add_broker_contact(
            company_name="Visible Brokerage", contact_name="Vera Visible",
            phone="555-222-3333", email="vera@visiblebrokerage.example.com",
        )
        load = services.create_load(customer="Stakeholder Contact Co", broker_shipper="Visible Brokerage")
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Vera Visible" in html
        assert "555-222-3333" in html

    def test_no_broken_section_when_no_broker_contact(self, client):
        load = services.create_load(customer="Stakeholder No Contact Co")
        resp = client.get(_url(load["load_id"]))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "None" not in html
        assert "Broker Contact" not in html

    def test_dispatch_email_always_shown(self, client):
        load = services.create_load(customer="Stakeholder Dispatch Email Co")
        resp = client.get(_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert services.reviewer_contact_email() in html

    def test_build_stakeholder_view_includes_contacts_key(self):
        load = services.create_load(customer="Stakeholder View Dict Co")
        view = services.build_stakeholder_view(load["load_id"])
        assert "contacts" in view
        assert view["contacts"]["dispatch_email"]
        assert view["contacts"]["broker_contact"] is None
