"""Tests for settlement tracking and financial dashboard."""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store
from dispatch.db import set_db_path
from dispatch.models import (
    PAYMENT_METHODS,
    SETTLEMENT_STATUSES,
    Settlement,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Test Broker",
        broker_shipper="Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


@pytest.fixture()
def load_with_rate(load):
    dispatch_svc.confirm_rate(load["load_id"], rate_amount=625.0)
    return load


# ── Settlement Model ────────────────────────────────────────────────


class TestSettlementModel:
    def test_defaults(self):
        stl = Settlement(load_id="L1", invoice_amount=625.0)
        assert stl.settlement_id.startswith("STL-")
        assert stl.invoice_number.startswith("INV-")
        assert stl.payment_status == "draft"
        assert stl.invoice_date

    def test_net_payment(self):
        stl = Settlement(payment_amount=600.0, factoring_fee=18.0)
        assert stl.net_payment == 582.0

    def test_net_payment_no_fee(self):
        stl = Settlement(payment_amount=600.0)
        assert stl.net_payment == 600.0

    def test_to_dict_includes_net_payment(self):
        stl = Settlement(payment_amount=500.0, factoring_fee=15.0)
        d = stl.to_dict()
        assert d["net_payment"] == 485.0

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="payment_status"):
            Settlement(payment_status="pending")

    def test_valid_statuses(self):
        for s in SETTLEMENT_STATUSES:
            stl = Settlement(payment_status=s)
            assert stl.payment_status == s

    def test_invalid_payment_method(self):
        with pytest.raises(ValueError, match="payment_method"):
            Settlement(payment_method="bitcoin")

    def test_valid_payment_methods(self):
        for m in PAYMENT_METHODS:
            stl = Settlement(payment_method=m)
            assert stl.payment_method == m

    def test_empty_payment_method_ok(self):
        stl = Settlement(payment_method="")
        assert stl.payment_method == ""


# ── Store CRUD ──────────────────────────────────────────────────────


class TestSettlementStore:
    def test_create_and_get(self, load):
        stl = Settlement(load_id=load["load_id"], invoice_amount=625.0, payment_status="invoiced")
        result = store.create_settlement(stl)
        assert result["invoice_amount"] == 625.0

        fetched = store.get_settlement(load["load_id"])
        assert fetched is not None
        assert fetched["invoice_amount"] == 625.0

    def test_get_nonexistent(self, load):
        assert store.get_settlement(load["load_id"]) is None

    def test_update(self, load):
        stl = Settlement(load_id=load["load_id"], invoice_amount=500.0, payment_status="invoiced")
        store.create_settlement(stl)

        updated = store.update_settlement(load["load_id"], payment_status="paid", payment_amount=500.0)
        assert updated["payment_status"] == "paid"
        assert updated["payment_amount"] == 500.0

    def test_update_nonexistent(self):
        assert store.update_settlement("NONE", payment_status="paid") is None

    def test_list(self, load):
        stl = Settlement(load_id=load["load_id"], invoice_amount=500.0, payment_status="invoiced")
        store.create_settlement(stl)

        items = store.list_settlements()
        assert len(items) == 1

    def test_list_by_status(self, load):
        stl = Settlement(load_id=load["load_id"], invoice_amount=500.0, payment_status="invoiced")
        store.create_settlement(stl)

        assert len(store.list_settlements(payment_status="invoiced")) == 1
        assert len(store.list_settlements(payment_status="paid")) == 0

    def test_unique_load_id(self, load):
        stl1 = Settlement(load_id=load["load_id"], invoice_amount=500.0, payment_status="invoiced")
        store.create_settlement(stl1)

        stl2 = Settlement(load_id=load["load_id"], invoice_amount=600.0, payment_status="invoiced")
        with pytest.raises(Exception):
            store.create_settlement(stl2)


# ── Service Functions ───────────────────────────────────────────────


class TestCreateSettlement:
    def test_create(self, load_with_rate):
        stl = dispatch_svc.create_settlement(load_with_rate["load_id"])
        assert stl["payment_status"] == "invoiced"
        assert stl["invoice_amount"] == 625.0

    def test_create_pulls_rate(self, load_with_rate):
        stl = dispatch_svc.create_settlement(load_with_rate["load_id"])
        assert stl["invoice_amount"] == 625.0

    def test_create_no_rate(self, load):
        stl = dispatch_svc.create_settlement(load["load_id"])
        assert stl["invoice_amount"] == 0.0

    def test_create_duplicate_raises(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        with pytest.raises(ValueError, match="already exists"):
            dispatch_svc.create_settlement(load_with_rate["load_id"])

    def test_create_nonexistent_load(self):
        with pytest.raises(ValueError, match="not found"):
            dispatch_svc.create_settlement("BOGUS")

    def test_with_due_date(self, load_with_rate):
        stl = dispatch_svc.create_settlement(load_with_rate["load_id"], due_date="2026-09-01")
        assert stl["due_date"] == "2026-09-01"


class TestRecordPayment:
    def test_record(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        result = dispatch_svc.record_payment(
            load_with_rate["load_id"], payment_amount=625.0, payment_method="ach"
        )
        assert result["payment_status"] == "paid"
        assert result["payment_amount"] == 625.0

    def test_with_factoring(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        result = dispatch_svc.record_payment(
            load_with_rate["load_id"], payment_amount=625.0,
            payment_method="factored", factoring_fee=18.75,
        )
        assert result["net_payment"] == 606.25

    def test_no_settlement(self, load):
        assert dispatch_svc.record_payment(load["load_id"], payment_amount=100) is None


class TestLoadBundleSettlement:
    def test_bundle_includes_settlement(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        bundle = dispatch_svc.get_load_bundle(load_with_rate["load_id"])
        assert "settlement" in bundle
        assert bundle["settlement"]["payment_status"] == "invoiced"

    def test_bundle_settlement_none(self, load):
        bundle = dispatch_svc.get_load_bundle(load["load_id"])
        assert bundle["settlement"] is None


# ── Financial Dashboard ─────────────────────────────────────────────


class TestFinancialDashboard:
    def test_empty(self):
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["total_loads"] == 0
        assert dash["total_revenue"] == 0.0
        assert dash["total_profit"] == 0.0

    def test_with_loads(self, load_with_rate):
        dispatch_svc.add_expense(load_with_rate["load_id"], category="fuel", amount=150)
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["total_loads"] == 1
        assert dash["loads_with_rate"] == 1
        assert dash["total_revenue"] == 625.0
        assert dash["total_expenses"] == 150.0
        assert dash["total_profit"] == 475.0

    def test_with_settlements(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["invoiced_count"] == 1
        assert dash["total_outstanding"] == 625.0

    def test_paid_settlement(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        dispatch_svc.record_payment(
            load_with_rate["load_id"], payment_amount=625.0, payment_method="ach"
        )
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["paid_count"] == 1
        assert dash["total_paid"] == 625.0
        assert dash["total_outstanding"] == 0.0

    def test_multiple_loads(self):
        l1 = dispatch_svc.create_load(customer="Broker A")
        l2 = dispatch_svc.create_load(customer="Broker B")
        dispatch_svc.confirm_rate(l1["load_id"], rate_amount=500)
        dispatch_svc.confirm_rate(l2["load_id"], rate_amount=750)
        dispatch_svc.add_expense(l1["load_id"], category="fuel", amount=100)
        dispatch_svc.add_expense(l2["load_id"], category="fuel", amount=200)

        dash = dispatch_svc.get_financial_dashboard()
        assert dash["total_revenue"] == 1250.0
        assert dash["total_expenses"] == 300.0
        assert dash["total_profit"] == 950.0
        assert dash["margin_pct"] == 76.0

    def test_overdue_count(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        dispatch_svc.update_settlement(load_with_rate["load_id"], payment_status="overdue")
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["overdue_count"] == 1
        assert dash["total_outstanding"] == 625.0

    def test_factoring_affects_paid(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"])
        dispatch_svc.record_payment(
            load_with_rate["load_id"], payment_amount=625.0,
            payment_method="factored", factoring_fee=18.75,
        )
        dash = dispatch_svc.get_financial_dashboard()
        assert dash["total_paid"] == 606.25


# ── API Endpoints ───────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "api_test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


@pytest.fixture()
def api_load(client):
    resp = client.post("/api/dispatch/loads", json={"customer": "API Test Broker"})
    load = resp.get_json()["load"]
    client.post(
        f"/api/dispatch/loads/{load['load_id']}/rate",
        json={"rate_amount": 625},
    )
    return load


class TestSettlementAPI:
    def test_create_settlement(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/settlement",
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["settlement"]["payment_status"] == "invoiced"
        assert data["settlement"]["invoice_amount"] == 625.0

    def test_get_settlement(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/settlement")
        assert resp.status_code == 200

    def test_get_settlement_404(self, client, api_load):
        resp = client.get(f"/api/dispatch/loads/{api_load['load_id']}/settlement")
        assert resp.status_code == 404

    def test_update_settlement(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.patch(
            f"/api/dispatch/loads/{api_load['load_id']}/settlement",
            json={"payment_status": "overdue"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["settlement"]["payment_status"] == "overdue"

    def test_update_invalid_status(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.patch(
            f"/api/dispatch/loads/{api_load['load_id']}/settlement",
            json={"payment_status": "invalid"},
        )
        assert resp.status_code == 400

    def test_update_invalid_method(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.patch(
            f"/api/dispatch/loads/{api_load['load_id']}/settlement",
            json={"payment_method": "bitcoin"},
        )
        assert resp.status_code == 400

    def test_update_404(self, client, api_load):
        resp = client.patch(
            f"/api/dispatch/loads/{api_load['load_id']}/settlement",
            json={"payment_status": "paid"},
        )
        assert resp.status_code == 404

    def test_duplicate_settlement(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        assert resp.status_code == 409

    def test_nonexistent_load(self, client):
        resp = client.post("/api/dispatch/loads/BOGUS/settlement", json={})
        assert resp.status_code == 404


class TestPaymentAPI:
    def test_record_payment(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_amount": 625, "payment_method": "ach"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["settlement"]["payment_status"] == "paid"
        assert data["settlement"]["payment_amount"] == 625.0

    def test_missing_amount(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_method": "ach"},
        )
        assert resp.status_code == 400

    def test_invalid_amount(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_amount": "abc"},
        )
        assert resp.status_code == 400

    def test_invalid_method(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_amount": 625, "payment_method": "bitcoin"},
        )
        assert resp.status_code == 400

    def test_no_settlement(self, client, api_load):
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_amount": 625},
        )
        assert resp.status_code == 404

    def test_factoring(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/payment",
            json={"payment_amount": 625, "payment_method": "factored", "factoring_fee": 18.75},
        )
        assert resp.status_code == 200
        assert resp.get_json()["settlement"]["net_payment"] == 606.25


class TestSettlementListAPI:
    def test_list_all(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.get("/api/dispatch/settlements")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_list_by_status(self, client, api_load):
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})
        resp = client.get("/api/dispatch/settlements?payment_status=invoiced")
        assert resp.get_json()["count"] == 1
        resp = client.get("/api/dispatch/settlements?payment_status=paid")
        assert resp.get_json()["count"] == 0

    def test_list_invalid_status(self, client):
        resp = client.get("/api/dispatch/settlements?payment_status=invalid")
        assert resp.status_code == 400


class TestDashboardAPI:
    def test_empty_dashboard(self, client):
        resp = client.get("/api/dispatch/dashboard/financials")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_loads"] == 0

    def test_dashboard_with_data(self, client, api_load):
        client.post(
            f"/api/dispatch/loads/{api_load['load_id']}/expenses",
            json={"amount": 150, "category": "fuel"},
        )
        client.post(f"/api/dispatch/loads/{api_load['load_id']}/settlement", json={})

        resp = client.get("/api/dispatch/dashboard/financials")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_revenue"] == 625.0
        assert data["total_expenses"] == 150.0
        assert data["total_profit"] == 475.0
        assert data["invoiced_count"] == 1
