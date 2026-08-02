"""Tests for billing enhancements: record payment UI, create invoice, uninvoiced loads."""

from __future__ import annotations

import pytest

from dispatch import services, store
from dispatch.db import set_db_path
from dispatch.models import Load, RateConfirmation


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_load(load_id="LD-001", status="delivered", customer="Acme"):
    load = Load(
        load_id=load_id,
        customer=customer,
        status=status,
        pickup_location="Origin",
        delivery_location="Dest",
    )
    return store.create_load(load)


def _make_rate(load_id="LD-001", rate_amount=5000.0):
    rc = RateConfirmation(load_id=load_id, rate_amount=rate_amount)
    return store.create_rate_confirmation(rc)


# ── Uninvoiced Loads (store) ─────────────────────────────────────────


class TestUninvoicedLoads:
    def test_delivered_load_without_settlement_is_uninvoiced(self):
        _make_load("LD-001", status="delivered")
        result = store.list_uninvoiced_loads()
        assert len(result) == 1
        assert result[0]["load_id"] == "LD-001"

    def test_completed_load_without_settlement_is_uninvoiced(self):
        _make_load("LD-002", status="completed")
        result = store.list_uninvoiced_loads()
        assert len(result) == 1
        assert result[0]["load_id"] == "LD-002"

    def test_in_transit_load_is_not_uninvoiced(self):
        _make_load("LD-003", status="in_transit")
        result = store.list_uninvoiced_loads()
        assert len(result) == 0

    def test_created_load_is_not_uninvoiced(self):
        _make_load("LD-004", status="created")
        result = store.list_uninvoiced_loads()
        assert len(result) == 0

    def test_delivered_load_with_settlement_is_excluded(self):
        _make_load("LD-005", status="delivered")
        _make_rate("LD-005")
        services.create_settlement(load_id="LD-005")
        result = store.list_uninvoiced_loads()
        assert len(result) == 0

    def test_multiple_uninvoiced_loads(self):
        _make_load("LD-A", status="delivered")
        _make_load("LD-B", status="completed")
        _make_load("LD-C", status="in_transit")
        result = store.list_uninvoiced_loads()
        ids = [r["load_id"] for r in result]
        assert "LD-A" in ids
        assert "LD-B" in ids
        assert "LD-C" not in ids

    def test_services_passthrough(self):
        _make_load("LD-006", status="delivered")
        result = services.list_uninvoiced_loads()
        assert len(result) == 1


# ── Record Payment (API) ────────────────────────────────────────────


class TestRecordPaymentAPI:
    def test_record_payment_success(self, client):
        _make_load("LD-PAY")
        _make_rate("LD-PAY", rate_amount=1000.0)
        services.create_settlement(load_id="LD-PAY")

        resp = client.post(
            "/api/dispatch/loads/LD-PAY/payment",
            json={"payment_amount": 1000.0, "payment_method": "ach"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["settlement"]["payment_status"] == "paid"
        assert data["settlement"]["payment_amount"] == 1000.0

    def test_record_payment_partial(self, client):
        _make_load("LD-PAY2")
        _make_rate("LD-PAY2", rate_amount=2000.0)
        services.create_settlement(load_id="LD-PAY2")

        resp = client.post(
            "/api/dispatch/loads/LD-PAY2/payment",
            json={"payment_amount": 1500.0, "payment_method": "check"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["settlement"]["payment_amount"] == 1500.0
        assert data["settlement"]["payment_method"] == "check"

    def test_record_payment_with_factoring_fee(self, client):
        _make_load("LD-PAY3")
        _make_rate("LD-PAY3", rate_amount=3000.0)
        services.create_settlement(load_id="LD-PAY3")

        resp = client.post(
            "/api/dispatch/loads/LD-PAY3/payment",
            json={
                "payment_amount": 3000.0,
                "payment_method": "factored",
                "factoring_fee": 90.0,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["settlement"]["factoring_fee"] == 90.0
        assert data["settlement"]["payment_method"] == "factored"

    def test_record_payment_missing_amount(self, client):
        _make_load("LD-PAY4")
        _make_rate("LD-PAY4")
        services.create_settlement(load_id="LD-PAY4")

        resp = client.post(
            "/api/dispatch/loads/LD-PAY4/payment",
            json={"payment_method": "ach"},
        )
        assert resp.status_code == 400
        assert "payment_amount" in resp.get_json()["error"]

    def test_record_payment_invalid_method(self, client):
        _make_load("LD-PAY5")
        _make_rate("LD-PAY5")
        services.create_settlement(load_id="LD-PAY5")

        resp = client.post(
            "/api/dispatch/loads/LD-PAY5/payment",
            json={"payment_amount": 100, "payment_method": "bitcoin"},
        )
        assert resp.status_code == 400

    def test_record_payment_no_settlement(self, client):
        _make_load("LD-PAY6")
        resp = client.post(
            "/api/dispatch/loads/LD-PAY6/payment",
            json={"payment_amount": 100},
        )
        assert resp.status_code == 404


# ── Create Invoice (API) ────────────────────────────────────────────


class TestCreateInvoiceAPI:
    def test_create_invoice_from_load(self, client):
        _make_load("LD-INV1")
        _make_rate("LD-INV1", rate_amount=5000.0)

        resp = client.post(
            "/api/dispatch/loads/LD-INV1/settlement",
            json={"due_date": "2026-09-01", "notes": "Net 30"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["settlement"]["invoice_amount"] == 5000.0
        assert data["settlement"]["payment_status"] == "invoiced"

    def test_create_invoice_without_rate(self, client):
        _make_load("LD-INV2")

        resp = client.post(
            "/api/dispatch/loads/LD-INV2/settlement",
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["settlement"]["invoice_amount"] == 0.0

    def test_create_invoice_duplicate(self, client):
        _make_load("LD-INV3")
        _make_rate("LD-INV3")
        services.create_settlement(load_id="LD-INV3")

        resp = client.post(
            "/api/dispatch/loads/LD-INV3/settlement",
            json={},
        )
        assert resp.status_code == 409

    def test_create_invoice_no_load(self, client):
        resp = client.post(
            "/api/dispatch/loads/NONEXISTENT/settlement",
            json={},
        )
        assert resp.status_code == 404


# ── Billing Page (template) ─────────────────────────────────────────


class TestBillingPage:
    def test_billing_page_renders(self, client):
        resp = client.get("/billing")
        assert resp.status_code == 200

    def test_billing_page_shows_record_payment_button(self, client):
        _make_load("LD-BIL1")
        _make_rate("LD-BIL1", rate_amount=1000.0)
        services.create_settlement(load_id="LD-BIL1")

        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Record Payment" in html
        assert "showPaymentForm" in html

    def test_billing_page_shows_payment_form_row(self, client):
        _make_load("LD-BIL2")
        _make_rate("LD-BIL2", rate_amount=2000.0)
        services.create_settlement(load_id="LD-BIL2")

        resp = client.get("/billing")
        html = resp.data.decode()
        assert "pay-row-LD-BIL2" in html
        assert "pay-amount-LD-BIL2" in html
        assert "pay-method-LD-BIL2" in html

    def test_billing_page_payment_methods_in_select(self, client):
        _make_load("LD-BIL3")
        _make_rate("LD-BIL3")
        services.create_settlement(load_id="LD-BIL3")

        resp = client.get("/billing")
        html = resp.data.decode()
        for method in ("check", "ach", "wire", "factored", "other"):
            assert method in html.lower()

    def test_billing_page_no_record_payment_for_paid(self, client):
        _make_load("LD-BIL4")
        _make_rate("LD-BIL4", rate_amount=500.0)
        services.create_settlement(load_id="LD-BIL4")
        services.record_payment("LD-BIL4", payment_amount=500.0)

        resp = client.get("/billing")
        html = resp.data.decode()
        assert "pay-row-LD-BIL4" not in html

    def test_billing_page_shows_uninvoiced_loads(self, client):
        _make_load("LD-UNIV", status="delivered", customer="TestCo")

        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Uninvoiced Loads" in html
        assert "LD-UNIV" in html
        assert "Create Invoice" in html

    def test_billing_page_no_uninvoiced_section_when_empty(self, client):
        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Uninvoiced Loads" not in html

    def test_billing_page_uninvoiced_excludes_invoiced(self, client):
        _make_load("LD-DONE", status="delivered")
        _make_rate("LD-DONE")
        services.create_settlement(load_id="LD-DONE")

        resp = client.get("/billing")
        html = resp.data.decode()
        assert "Uninvoiced Loads" not in html

    def test_record_payment_for_disputed_settlement(self, client):
        _make_load("LD-DISP")
        _make_rate("LD-DISP", rate_amount=1000.0)
        services.create_settlement(load_id="LD-DISP")
        services.dispute_settlement("LD-DISP", reason="test")

        resp = client.get("/billing?status=disputed")
        html = resp.data.decode()
        assert "Record Payment" in html
        assert "pay-row-LD-DISP" in html
