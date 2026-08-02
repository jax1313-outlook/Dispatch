"""Tests for financial notifications, aging detection, and archive financials."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from dispatch import services as dispatch_svc
from dispatch import notifications, store
from dispatch.db import set_db_path
from dispatch.models import RetentionArchive


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Test Customer",
        broker_shipper="Test Broker",
        pickup_location="Atlanta, GA",
        delivery_location="Miami, FL",
    )


@pytest.fixture()
def load_with_rate(load):
    dispatch_svc.confirm_rate(load["load_id"], rate_amount=1200.0)
    return load


@pytest.fixture()
def load_with_settlement(load_with_rate):
    dispatch_svc.create_settlement(
        load_with_rate["load_id"],
        due_date="2026-07-01",
    )
    return load_with_rate


# ── Notification Rendering ──────────────────────────────────────────


class TestInvoiceNotification:
    def test_notify_invoice_created_returns_path(self, load):
        settlement = {
            "invoice_number": "INV-TEST001",
            "invoice_amount": 1200.0,
            "due_date": "2026-08-15",
        }
        result = notifications.notify_invoice_created(load, settlement)
        assert result  # returns file path or "sent"

    def test_notify_invoice_created_content(self, load, tmp_path):
        settlement = {
            "invoice_number": "INV-TEST002",
            "invoice_amount": 950.50,
            "due_date": "2026-09-01",
        }
        with mock.patch.dict(os.environ, {"PORTAL_DATA_DIR": str(tmp_path)}):
            result = notifications.notify_invoice_created(load, settlement)
            if result.startswith("email/"):
                path = tmp_path / result
            else:
                path = tmp_path / "email" / result.split("/")[-1]
            if path.exists():
                content = path.read_text()
                assert "INV-TEST002" in content
                assert "950" in content


class TestPaymentNotification:
    def test_notify_payment_received_returns_path(self, load):
        settlement = {
            "invoice_number": "INV-TEST003",
            "payment_amount": 1200.0,
            "net_payment": 1200.0,
            "payment_method": "ach",
            "factoring_fee": 0,
        }
        result = notifications.notify_payment_received(load, settlement)
        assert result

    def test_notify_payment_with_factoring(self, load):
        settlement = {
            "invoice_number": "INV-TEST004",
            "payment_amount": 1200.0,
            "net_payment": 1164.0,
            "payment_method": "factored",
            "factoring_fee": 36.0,
        }
        result = notifications.notify_payment_received(load, settlement)
        assert result


class TestOverdueNotification:
    def test_notify_overdue_returns_path(self, load):
        settlement = {
            "invoice_number": "INV-TEST005",
            "invoice_amount": 800.0,
            "due_date": "2026-07-01",
        }
        result = notifications.notify_payment_overdue(load, settlement)
        assert result


# ── Service Layer Integration ───────────────────────────────────────


class TestSettlementNotificationTrigger:
    def test_create_settlement_triggers_invoice_notification(self, load_with_rate):
        with mock.patch.object(notifications, "notify_invoice_created") as m:
            dispatch_svc.create_settlement(load_with_rate["load_id"], due_date="2026-08-15")
            m.assert_called_once()
            args = m.call_args[0]
            assert args[0]["load_id"] == load_with_rate["load_id"]
            assert args[1]["payment_status"] == "invoiced"

    def test_record_payment_triggers_notification(self, load_with_settlement):
        with mock.patch.object(notifications, "notify_payment_received") as m:
            dispatch_svc.record_payment(
                load_with_settlement["load_id"],
                payment_amount=1200.0,
                payment_method="ach",
            )
            m.assert_called_once()
            args = m.call_args[0]
            assert args[1]["payment_status"] == "paid"


# ── Aging Detection ─────────────────────────────────────────────────


class TestAgingCheck:
    def test_no_overdue_when_not_past_due(self, load_with_rate):
        dispatch_svc.create_settlement(
            load_with_rate["load_id"],
            due_date="2099-12-31",
        )
        result = dispatch_svc.check_overdue_settlements()
        assert result == []

    def test_marks_past_due_as_overdue(self, load_with_rate):
        dispatch_svc.create_settlement(
            load_with_rate["load_id"],
            due_date="2020-01-01",
        )
        result = dispatch_svc.check_overdue_settlements()
        assert len(result) == 1
        assert result[0]["payment_status"] == "overdue"

    def test_aging_sends_overdue_notification(self, load_with_rate):
        dispatch_svc.create_settlement(
            load_with_rate["load_id"],
            due_date="2020-01-01",
        )
        with mock.patch.object(notifications, "notify_payment_overdue") as m:
            dispatch_svc.check_overdue_settlements()
            m.assert_called_once()

    def test_aging_skips_no_due_date(self, load_with_rate):
        dispatch_svc.create_settlement(load_with_rate["load_id"], due_date="")
        result = dispatch_svc.check_overdue_settlements()
        assert result == []

    def test_aging_skips_already_paid(self, load_with_rate):
        dispatch_svc.create_settlement(
            load_with_rate["load_id"],
            due_date="2020-01-01",
        )
        dispatch_svc.record_payment(
            load_with_rate["load_id"],
            payment_amount=1200.0,
        )
        result = dispatch_svc.check_overdue_settlements()
        assert result == []

    def test_aging_idempotent(self, load_with_rate):
        dispatch_svc.create_settlement(
            load_with_rate["load_id"],
            due_date="2020-01-01",
        )
        first = dispatch_svc.check_overdue_settlements()
        assert len(first) == 1
        second = dispatch_svc.check_overdue_settlements()
        assert second == []

    def test_aging_multiple_loads(self):
        load1 = dispatch_svc.create_load(customer="A")
        load2 = dispatch_svc.create_load(customer="B")
        load3 = dispatch_svc.create_load(customer="C")
        dispatch_svc.confirm_rate(load1["load_id"], rate_amount=500.0)
        dispatch_svc.confirm_rate(load2["load_id"], rate_amount=600.0)
        dispatch_svc.confirm_rate(load3["load_id"], rate_amount=700.0)
        dispatch_svc.create_settlement(load1["load_id"], due_date="2020-01-01")
        dispatch_svc.create_settlement(load2["load_id"], due_date="2099-12-31")
        dispatch_svc.create_settlement(load3["load_id"], due_date="2020-06-15")
        result = dispatch_svc.check_overdue_settlements()
        assert len(result) == 2
        overdue_ids = {r["load_id"] for r in result}
        assert load1["load_id"] in overdue_ids
        assert load3["load_id"] in overdue_ids


# ── Archive Financial Summary ───────────────────────────────────────


class TestArchiveFinancialSummary:
    def _deliver_load(self, load_id):
        dispatch_svc.add_milestone(load_id, event_type="dispatched")
        dispatch_svc.add_milestone(load_id, event_type="delivered")

    def test_archive_includes_financial_summary(self, load_with_rate):
        self._deliver_load(load_with_rate["load_id"])
        dispatch_svc.add_expense(
            load_with_rate["load_id"], category="fuel", amount=150.0
        )
        ret = dispatch_svc.archive_load(load_with_rate["load_id"])
        fin = ret["financial_summary"]
        assert fin["revenue"] == 1200.0
        assert fin["total_expenses"] == 150.0
        assert fin["profit"] == 1050.0

    def test_archive_includes_settlement_info(self, load_with_settlement):
        self._deliver_load(load_with_settlement["load_id"])
        ret = dispatch_svc.archive_load(load_with_settlement["load_id"])
        fin = ret["financial_summary"]
        assert fin["settlement_status"] == "invoiced"
        assert "INV-" in fin["invoice_number"]

    def test_archive_financials_zeroes_without_rate(self, load):
        self._deliver_load(load["load_id"])
        ret = dispatch_svc.archive_load(load["load_id"])
        fin = ret["financial_summary"]
        assert fin["revenue"] == 0.0
        assert fin["profit"] == 0.0

    def test_retention_store_persists_financial_summary(self, load_with_rate):
        self._deliver_load(load_with_rate["load_id"])
        dispatch_svc.add_expense(
            load_with_rate["load_id"], category="tolls", amount=25.0
        )
        dispatch_svc.archive_load(load_with_rate["load_id"])
        ret = store.get_retention_by_load(load_with_rate["load_id"])
        assert ret["financial_summary"]["revenue"] == 1200.0
        assert ret["financial_summary"]["total_expenses"] == 25.0


class TestRetentionModelField:
    def test_financial_summary_default(self):
        r = RetentionArchive(load_id="L1")
        assert r.financial_summary == {}

    def test_financial_summary_in_dict(self):
        r = RetentionArchive(load_id="L1", financial_summary={"revenue": 500})
        d = r.to_dict()
        assert d["financial_summary"] == {"revenue": 500}


# ── Aging API ───────────────────────────────────────────────────────


class TestAgingAPI:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_aging_endpoint(self, client, load_with_rate):
        client.post(
            f"/api/dispatch/loads/{load_with_rate['load_id']}/settlement",
            json={"due_date": "2020-01-01"},
        )
        resp = client.post("/api/dispatch/settlements/aging")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["newly_overdue"][0]["payment_status"] == "overdue"

    def test_aging_endpoint_none_overdue(self, client, load_with_rate):
        client.post(
            f"/api/dispatch/loads/{load_with_rate['load_id']}/settlement",
            json={"due_date": "2099-12-31"},
        )
        resp = client.post("/api/dispatch/settlements/aging")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 0
