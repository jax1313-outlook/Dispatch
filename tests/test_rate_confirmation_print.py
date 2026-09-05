"""Tests for print-friendly rate confirmation feature."""

from __future__ import annotations

import os

import pytest

from dispatch.db import set_db_path
from dispatch import services, store
from dispatch.models import RateConfirmation


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def client():
    from portal.app import create_app
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        yield c


def _make_load(**kw) -> dict:
    defaults = {"customer": "Print Co", "pickup_location": "Dallas TX", "delivery_location": "Houston TX"}
    defaults.update(kw)
    return services.create_load(**defaults)


def _confirm_rate(load_id, **kw) -> dict:
    defaults = {"rate_amount": 2500.00, "rate_type": "flat", "distance_miles": 250.0, "confirmed_by": "Dispatcher"}
    defaults.update(kw)
    rc = RateConfirmation(load_id=load_id, **defaults)
    return store.create_rate_confirmation(rc)


# ── Route tests ─────────────────────────────────────────────────────


class TestRateConfirmationPrintRoute:
    def test_print_page_renders(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        assert resp.status_code == 200

    def test_redirects_without_rate(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        assert resp.status_code == 302

    def test_redirects_nonexistent_load(self, client):
        resp = client.get("/dispatch/FAKE-ID/rate-confirmation/print")
        assert resp.status_code == 302


# ── Template content tests ──────────────────────────────────────────


class TestRateConfirmationPrintContent:
    def test_shows_rate_confirmation_title(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Rate Confirmation" in html

    def test_shows_load_id(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert load["load_id"] in html

    def test_shows_customer(self, client):
        load = _make_load(customer="Acme Freight LLC")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Acme Freight LLC" in html

    def test_shows_locations(self, client):
        load = _make_load(pickup_location="Chicago IL", delivery_location="Miami FL")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Chicago IL" in html
        assert "Miami FL" in html

    def test_shows_rate_amount(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], rate_amount=3500.00)
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "3500.00" in html

    def test_shows_rate_type(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], rate_type="per_mile")
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Per Mile" in html

    def test_shows_distance(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], distance_miles=450.0)
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "450.0" in html
        assert "miles" in html

    def test_shows_revenue(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], rate_amount=2500.00)
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "2500.00" in html

    def test_per_mile_revenue_calculated(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], rate_amount=3.00, rate_type="per_mile", distance_miles=500.0)
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "1500.00" in html

    def test_shows_confirmed_by(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], confirmed_by="John Smith")
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "John Smith" in html

    def test_shows_notes(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"], notes="Lumper fee included")
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Lumper fee included" in html

    def test_shows_broker_shipper(self, client):
        load = _make_load(broker_shipper="XPO Logistics")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "XPO Logistics" in html

    def test_shows_pickup_datetime(self, client):
        load = _make_load(pickup_datetime="2026-08-10 08:00")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "2026-08-10 08:00" in html

    def test_shows_delivery_datetime(self, client):
        load = _make_load(delivery_datetime="2026-08-12 14:00")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "2026-08-12 14:00" in html

    def test_shows_equipment_type(self, client):
        load = _make_load(equipment="Dry Van 53ft")
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Dry Van 53ft" in html


# ── Company info tests ──────────────────────────────────────────────


class TestRateConfirmationCompanyInfo:
    def test_shows_company_name(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_COMPANY_NAME", "Big Rig Transport LLC")
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Big Rig Transport LLC" in html

    def test_shows_mc_number(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_MC_NUMBER", "MC-123456")
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "MC-123456" in html

    def test_shows_dot_number(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_DOT_NUMBER", "DOT-789012")
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "DOT-789012" in html

    def test_shows_company_phone(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_COMPANY_PHONE", "(555) 123-4567")
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "(555) 123-4567" in html

    def test_no_company_info_renders_clean(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "MC#" not in html
        assert "DOT#" not in html


# ── Print layout tests ──────────────────────────────────────────────


class TestRateConfirmationPrintLayout:
    def test_has_print_button(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "window.print()" in html

    def test_has_back_button(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "window.history.back()" in html

    def test_has_print_media_query(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "@media print" in html

    def test_print_hides_controls(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert ".print-controls { display: none" in html

    def test_has_signature_lines(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "Carrier Signature" in html
        assert "Shipper/Broker Signature" in html

    def test_has_terms_section(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "net 30 days" in html

    def test_standalone_page_no_sidebar(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}/rate-confirmation/print")
        html = resp.data.decode()
        assert "sidebar" not in html
        # The print view must not inherit the portal chrome. The sidebar
        # heading is the chrome's signature; the superseded program name is
        # kept as a second guard so this test still fails if the old base
        # template is ever reintroduced.
        assert "<h2>Dispatch</h2>" not in html
        assert "L2-COS" not in html


# ── Dispatch detail print link test ─────────────────────────────────


class TestDispatchDetailPrintLink:
    def test_print_link_shown_with_rate(self, client):
        load = _make_load()
        _confirm_rate(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Print Rate Confirmation" in html
        assert f"/dispatch/{load['load_id']}/rate-confirmation/print" in html

    def test_no_print_link_without_rate(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Print Rate Confirmation" not in html
