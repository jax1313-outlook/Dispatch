"""Tests for home page financial dashboard and aging check button — PR 25.

Covers: financial snapshot on home page, aging check JS availability,
and dispatch page aging check button.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


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


class TestHomeFinancialSnapshot:
    """The Financial Snapshot came off Home on 2026-09-09.

    Home carries two counts and the cards. Money is not immediate operational
    awareness, and the same figures already render on Billing and Dispatch.
    These tests now hold the removal in place and check the figures still exist
    where they were not removed from.
    """

    def test_home_carries_no_financials_at_all(self, client):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1500.0)

        html = client.get("/home").data.decode()
        assert "Financial Snapshot" not in html
        # The shared script still defines runAgingCheck; what went away is the
        # button on this page that called it.
        assert "Run Aging Check" not in html
        assert "Outstanding" not in html

    def test_home_carries_no_financials_when_money_has_moved_either(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "http://localhost:8080")
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=3000.0)
        services.create_settlement(load["load_id"], due_date="2026-12-01")
        services.record_payment(load["load_id"], payment_amount=3000.0)

        html = client.get("/home").data.decode()
        assert "Financial Snapshot" not in html
        assert "Paid" not in html

    def test_the_figures_still_render_on_billing(self, client):
        """Removed from Home, not removed. Billing is where money is worked."""
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1500.0)
        services.create_settlement(load["load_id"], due_date="2026-12-01")

        html = client.get("/billing").data.decode()
        assert "Total Revenue" in html
        assert "Run Aging Check" in html


class TestDispatchAgingCheckButton:
    def test_dispatch_page_has_aging_button(self, client):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1000.0)

        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "runAgingCheck" in html
        assert "Run Aging Check" in html

    def test_dispatch_page_no_button_without_rates(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Run Aging Check" not in html


class TestAgingCheckAPI:
    def test_aging_check_marks_overdue(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "http://localhost:8080")
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        services.create_settlement(load["load_id"], due_date="2025-01-01")

        resp = client.post("/api/dispatch/settlements/aging")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

        stl = services.get_settlement(load["load_id"])
        assert stl["payment_status"] == "overdue"

    def test_aging_check_no_overdue(self, client):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        services.create_settlement(load["load_id"], due_date="2099-12-31")

        resp = client.post("/api/dispatch/settlements/aging")
        data = resp.get_json()
        assert data["count"] == 0


class TestRunAgingCheckJS:
    def test_base_template_has_aging_function(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "function runAgingCheck" in html
