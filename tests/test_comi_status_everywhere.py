"""Tests for Lane B: COMI Status Everywhere.

Covers the new shared helper `dispatch.services.get_comi_status()` and its
three consumers: the Driver Portal (`portal/routes/driver_portal.py`), the
external Stakeholder Portal (`portal/templates/stakeholder_view.html` via
`dispatch.services.build_stakeholder_view()`), and the Operations Feed
(`portal/models/operations_feed.py`'s `_comi_cards()` source).

All three consumers now read the same DRAFT/REVIEWED/SUBMITTED signal from
portal.models.email_helper through the one shared helper instead of each
querying email_helper directly.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry
from portal.models import email_helper, operations_feed


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


def _draft(load_id: str, **kwargs) -> dict:
    return email_helper.create_draft(load_id, load=services.get_load(load_id), **kwargs)


# ── dispatch.services.get_comi_status ───────────────────────────────


class TestGetComiStatus:
    def test_no_package_returns_not_exists(self):
        load = services.create_load(customer="No Package Co")
        assert services.get_comi_status(load["load_id"]) == {"exists": False, "status": None}

    def test_draft_package_passthrough(self):
        load = services.create_load(customer="Draft Package Co")
        _draft(load["load_id"])
        assert services.get_comi_status(load["load_id"]) == {"exists": True, "status": "DRAFT"}

    def test_reviewed_package_passthrough(self):
        load = services.create_load(customer="Reviewed Package Co")
        _draft(load["load_id"])
        email_helper.update_draft(load["load_id"], broker_body="edited body")
        assert services.get_comi_status(load["load_id"]) == {"exists": True, "status": "REVIEWED"}

    def test_submitted_package_passthrough(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        load = services.create_load(customer="Submitted Package Co")
        _draft(load["load_id"], broker_contact={"email": "broker@test.com"})
        email_helper.submit_package(load["load_id"], "Mike Zachary")
        assert services.get_comi_status(load["load_id"]) == {"exists": True, "status": "SUBMITTED"}


# ── Driver Portal (via dispatch_svc.get_comi_status) ────────────────


class TestDriverPortalComiStatus:
    def test_home_shows_no_package_language(self, client):
        driver = services.create_driver(name="Driver No Comi", phone="555-000-1111")
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(customer="No Comi Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"No communications drafted yet" in resp.data

    def test_home_shows_draft_status(self, client):
        driver = services.create_driver(name="Driver Comi Draft", phone="555-000-2222")
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        load = services.create_load(customer="Comi Draft Co")
        services.update_load(load["load_id"], driver_id=driver["driver_id"])
        _draft(load["load_id"])
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})
        resp = client.get("/driver/home")
        assert b"DRAFT" in resp.data


# ── Stakeholder Portal ───────────────────────────────────────────────


class TestStakeholderComiStatus:
    def test_submitted_shows_sent_language(self, client, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        load = services.create_load(customer="Stakeholder Comi Submitted Co")
        _draft(load["load_id"], broker_contact={"email": "broker@test.com"})
        email_helper.submit_package(load["load_id"], "Mike Zachary")
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Closeout communications sent" in html

    def test_draft_shows_in_progress_language(self, client):
        load = services.create_load(customer="Stakeholder Comi Draft Co")
        _draft(load["load_id"])
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Closeout communications in progress" in html

    def test_no_package_shows_no_comi_line(self, client):
        load = services.create_load(customer="Stakeholder Comi None Co")
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert "Closeout communications" not in html

    def test_draft_email_body_and_contact_never_leak(self, client):
        """Mirrors TestStakeholderViewExcludesInternalContent's pattern in
        test_stakeholder_portal.py: only a status glance is shown, never the
        draft email's own body/subject/recipient content."""
        load = services.create_load(customer="Stakeholder Comi Leak Co")
        package = _draft(
            load["load_id"],
            broker_contact={"email": "broker@test.com", "contact_name": "Secret Contact Name"},
        )
        resp = client.get(_stakeholder_url(load["load_id"]))
        html = resp.data.decode("utf-8")
        assert package["broker_subject"] not in html
        assert package["broker_email"] not in html
        assert "Secret Contact Name" not in html


# ── Operations Feed ──────────────────────────────────────────────────


class TestOperationsFeedComiCards:
    def test_draft_package_produces_level_2_card(self):
        load = services.create_load(customer="Feed Comi Draft Co")
        _draft(load["load_id"])
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "comi"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 2
        assert "Feed Comi Draft Co" in cards[0]["title"]
        assert cards[0]["closing"] == ""

    def test_submitted_package_produces_no_card(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        load = services.create_load(customer="Feed Comi Submitted Co")
        _draft(load["load_id"], broker_contact={"email": "broker@test.com"})
        email_helper.submit_package(load["load_id"], "Mike Zachary")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "comi"] == []

    def test_card_disappears_once_submitted(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        load = services.create_load(customer="Feed Comi Transition Co")
        _draft(load["load_id"], broker_contact={"email": "broker@test.com"})

        feed_before = operations_feed.build_feed()
        assert len([c for c in feed_before["cards"] if c["source"] == "comi"]) == 1

        email_helper.submit_package(load["load_id"], "Mike Zachary")
        feed_after = operations_feed.build_feed()
        assert [c for c in feed_after["cards"] if c["source"] == "comi"] == []
