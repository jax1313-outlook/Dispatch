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
        # The Run Aging Check button went on 2026-09-17. The figures stayed:
        # Billing is where money is worked, Dispatch just does not chase it.
        assert "Run Aging Check" not in html


# Deleted with the feature, 2026-09-17: the Run Aging Check button went with the route.


# Deleted with the feature, 2026-09-17: the aging endpoint is gone.


# Deleted with the feature, 2026-09-17: runAgingCheck() went with the button that called it.


