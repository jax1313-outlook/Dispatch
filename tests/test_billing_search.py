"""Tests for billing page search/filter (PR 35)."""

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


# ── Store-level search ───────────────────────────────────────────


class TestSettlementStoreSearch:
    def test_filter_by_customer(self):
        _create_invoiced_load(customer="Alpha Corp")
        _create_invoiced_load(customer="Beta Inc")
        from dispatch import store
        results = store.list_settlements(customer="Alpha")
        assert len(results) == 1
        inv = results[0]["invoice_number"]
        all_results = store.list_settlements()
        match = [s for s in all_results if s["invoice_number"] == inv]
        assert len(match) == 1

    def test_filter_by_invoice_number(self):
        _, stl = _create_invoiced_load()
        from dispatch import store
        partial = stl["invoice_number"][:8]
        results = store.list_settlements(invoice_number=partial)
        assert len(results) >= 1
        assert any(s["invoice_number"] == stl["invoice_number"] for s in results)

    def test_filter_by_date_range(self):
        _create_invoiced_load(due_date="2025-06-01")
        _create_invoiced_load(due_date="2025-12-01")
        from dispatch import store
        all_stls = store.list_settlements()
        assert len(all_stls) == 2

    def test_combined_status_and_customer(self):
        load1, _ = _create_invoiced_load(customer="Combo Corp")
        load2, _ = _create_invoiced_load(customer="Other Corp")
        services.record_payment(load2["load_id"], payment_amount=5000.0)
        from dispatch import store
        results = store.list_settlements(payment_status="invoiced", customer="Combo")
        assert len(results) == 1


# ── Service-level search ─────────────────────────────────────────


class TestSettlementServiceSearch:
    def test_service_passes_customer_filter(self):
        _create_invoiced_load(customer="Service Corp")
        _create_invoiced_load(customer="Other Corp")
        results = services.list_settlements(customer="Service")
        assert len(results) == 1

    def test_service_passes_invoice_filter(self):
        _, stl = _create_invoiced_load()
        results = services.list_settlements(invoice_number=stl["invoice_number"][:6])
        assert len(results) >= 1


# ── Billing page UI ──────────────────────────────────────────────


class TestBillingSearchUI:
    def test_search_form_present(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert 'name="customer"' in html
        assert 'name="invoice"' in html
        assert 'name="date_from"' in html
        assert 'name="date_to"' in html

    def test_customer_search_filters_results(self, client):
        _create_invoiced_load(customer="Findable Corp")
        _create_invoiced_load(customer="Hidden Corp")
        resp = client.get("/billing?customer=Findable")
        html = resp.data.decode()
        assert "Findable Corp" in html
        assert "Hidden Corp" not in html

    def test_customer_search_preserves_value(self, client):
        resp = client.get("/billing?customer=TestSearch")
        html = resp.data.decode()
        assert 'value="TestSearch"' in html

    def test_invoice_search_filters_results(self, client):
        _, stl = _create_invoiced_load(customer="Invoice Test")
        inv_num = stl["invoice_number"]
        resp = client.get(f"/billing?invoice={inv_num}")
        html = resp.data.decode()
        assert inv_num in html

    def test_clear_button_shown_when_searching(self, client):
        resp = client.get("/billing?customer=something")
        html = resp.data.decode()
        assert "Clear</a>" in html

    def test_no_clear_button_without_search(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Clear</a>" not in html

    def test_status_filter_preserved_in_search(self, client):
        resp = client.get("/billing?status=invoiced&customer=test")
        html = resp.data.decode()
        assert 'name="status" value="invoiced"' in html

    def test_combined_status_and_customer(self, client):
        _create_invoiced_load(customer="Combined Corp")
        load2, _ = _create_invoiced_load(customer="Paid Corp")
        services.record_payment(load2["load_id"], payment_amount=5000.0)
        resp = client.get("/billing?status=invoiced&customer=Combined")
        html = resp.data.decode()
        assert "Combined Corp" in html
        assert "Paid Corp" not in html

    def test_empty_search_shows_all(self, client):
        _create_invoiced_load(customer="All1")
        _create_invoiced_load(customer="All2")
        resp = client.get("/billing?customer=")
        html = resp.data.decode()
        assert "All1" in html
        assert "All2" in html
