"""Tests for billing page (PR 33)."""

from __future__ import annotations

import pytest

from dispatch import services
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


def _create_invoiced_load(customer="Test Corp", rate=5000.0, due_date="2025-12-01"):
    load = services.create_load(customer=customer)
    services.confirm_rate(load["load_id"], rate_amount=rate)
    stl = services.create_settlement(load["load_id"], due_date=due_date)
    return load, stl


# ── Page rendering ────────────────────────────────────────────────


class TestBillingPage:
    def test_billing_page_loads(self, client):
        resp = client.get("/billing")
        assert resp.status_code == 200

    def test_empty_state(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "No settlements found" in html

    def test_settlement_listed(self, client):
        load, stl = _create_invoiced_load(customer="Billing Corp")
        resp = client.get("/billing")
        html = resp.data.decode()
        assert stl["invoice_number"] in html
        assert "Billing Corp" in html

    def test_invoice_amount_shown(self, client):
        _create_invoiced_load(rate=7500.0)
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "7500.00" in html

    def test_status_filter(self, client):
        _create_invoiced_load(customer="Invoiced Corp")
        load2, _ = _create_invoiced_load(customer="Paid Corp")
        services.record_payment(load2["load_id"], payment_amount=5000.0)
        resp = client.get("/billing?status=invoiced")
        html = resp.data.decode()
        assert "Invoiced Corp" in html
        assert "Paid Corp" not in html

    def test_paid_filter(self, client):
        load, _ = _create_invoiced_load(customer="Paid Only")
        services.record_payment(load["load_id"], payment_amount=5000.0)
        resp = client.get("/billing?status=paid")
        html = resp.data.decode()
        assert "Paid Only" in html

    def test_overdue_highlighted(self, client):
        load, _ = _create_invoiced_load(customer="Overdue Corp")
        services.update_settlement(load["load_id"], payment_status="overdue")
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "border-left:3px solid #e74c3c" in html

    def test_disputed_highlighted(self, client):
        load, _ = _create_invoiced_load(customer="Dispute Corp")
        services.dispute_settlement(load["load_id"])
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "border-left:3px solid #e67e22" in html

    def test_dispute_button_on_invoiced(self, client):
        _create_invoiced_load()
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Dispute</button>" in html

    def test_write_off_button_on_disputed(self, client):
        load, _ = _create_invoiced_load()
        services.dispute_settlement(load["load_id"])
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Write Off</button>" in html

    def test_no_actions_on_paid(self, client):
        load, _ = _create_invoiced_load()
        services.record_payment(load["load_id"], payment_amount=5000.0)
        resp = client.get("/billing?status=paid")
        html = resp.data.decode()
        assert "Dispute</button>" not in html
        assert "Write Off</button>" not in html

    def test_links_to_load_detail(self, client):
        load, stl = _create_invoiced_load()
        resp = client.get("/billing")
        html = resp.data.decode()
        assert f"/dispatch/{load['load_id']}" in html

    def test_financial_summary_shown(self, client):
        _create_invoiced_load(rate=10000.0)
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Total Revenue" in html

    def test_aging_check_button(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Run Aging Check" in html

    def test_filter_buttons_shown(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert ">All<" in html
        assert ">Invoiced<" in html
        assert ">Paid<" in html
        assert ">Overdue<" in html
        assert ">Disputed<" in html

    def test_disputed_count_in_summary(self, client):
        load, _ = _create_invoiced_load()
        services.dispute_settlement(load["load_id"])
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Disputed" in html


# ── Nav link ──────────────────────────────────────────────────────


class TestBillingNavLink:
    def test_billing_link_in_sidebar(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "/billing" in html
        assert "Billing" in html
