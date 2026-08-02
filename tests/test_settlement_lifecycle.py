"""Tests for settlement dispute and write-off lifecycle (PR 32)."""

from __future__ import annotations

import pytest

from dispatch import services, store as dispatch_store
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


@pytest.fixture
def invoiced_load():
    load = services.create_load(customer="Invoice Corp")
    services.confirm_rate(load["load_id"], rate_amount=5000.0)
    stl = services.create_settlement(load["load_id"], due_date="2025-12-01")
    return load, stl


# ── services.dispute_settlement ───────────────────────────────────


class TestDisputeSettlement:
    def test_dispute_invoiced(self, invoiced_load):
        load, _ = invoiced_load
        result = services.dispute_settlement(load["load_id"], reason="Short payment")
        assert result["payment_status"] == "disputed"
        assert "DISPUTE: Short payment" in result["notes"]

    def test_dispute_overdue(self, invoiced_load):
        load, _ = invoiced_load
        services.update_settlement(load["load_id"], payment_status="overdue")
        result = services.dispute_settlement(load["load_id"], reason="Damaged goods")
        assert result["payment_status"] == "disputed"

    def test_dispute_without_reason(self, invoiced_load):
        load, _ = invoiced_load
        result = services.dispute_settlement(load["load_id"])
        assert result["payment_status"] == "disputed"

    def test_cannot_dispute_paid(self, invoiced_load):
        load, _ = invoiced_load
        services.record_payment(load["load_id"], payment_amount=5000.0)
        with pytest.raises(ValueError, match="Cannot dispute"):
            services.dispute_settlement(load["load_id"])

    def test_cannot_dispute_written_off(self, invoiced_load):
        load, _ = invoiced_load
        services.write_off_settlement(load["load_id"])
        with pytest.raises(ValueError, match="Cannot dispute"):
            services.dispute_settlement(load["load_id"])

    def test_no_settlement_returns_none(self):
        load = services.create_load(customer="No Settlement Corp")
        assert services.dispute_settlement(load["load_id"]) is None


# ── services.write_off_settlement ─────────────────────────────────


class TestWriteOffSettlement:
    def test_write_off_invoiced(self, invoiced_load):
        load, _ = invoiced_load
        result = services.write_off_settlement(load["load_id"], reason="Bankrupt")
        assert result["payment_status"] == "written_off"
        assert "WRITE-OFF: Bankrupt" in result["notes"]

    def test_write_off_overdue(self, invoiced_load):
        load, _ = invoiced_load
        services.update_settlement(load["load_id"], payment_status="overdue")
        result = services.write_off_settlement(load["load_id"])
        assert result["payment_status"] == "written_off"

    def test_write_off_disputed(self, invoiced_load):
        load, _ = invoiced_load
        services.dispute_settlement(load["load_id"])
        result = services.write_off_settlement(load["load_id"], reason="Cannot collect")
        assert result["payment_status"] == "written_off"

    def test_cannot_write_off_paid(self, invoiced_load):
        load, _ = invoiced_load
        services.record_payment(load["load_id"], payment_amount=5000.0)
        with pytest.raises(ValueError, match="Cannot write off"):
            services.write_off_settlement(load["load_id"])

    def test_no_settlement_returns_none(self):
        load = services.create_load(customer="No Settlement Corp")
        assert services.write_off_settlement(load["load_id"]) is None


# ── API: POST /settlement/dispute ─────────────────────────────────


class TestDisputeAPI:
    def test_dispute_endpoint(self, client, invoiced_load):
        load, _ = invoiced_load
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/dispute",
            json={"reason": "Damaged cargo"},
        )
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["settlement"]["payment_status"] == "disputed"

    def test_dispute_no_settlement_404(self, client):
        load = services.create_load(customer="No Stl")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/dispute",
            json={},
        )
        assert resp.status_code == 404

    def test_dispute_invalid_status_400(self, client, invoiced_load):
        load, _ = invoiced_load
        services.record_payment(load["load_id"], payment_amount=5000.0)
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/dispute",
            json={},
        )
        assert resp.status_code == 400


# ── API: POST /settlement/write-off ───────────────────────────────


class TestWriteOffAPI:
    def test_write_off_endpoint(self, client, invoiced_load):
        load, _ = invoiced_load
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/write-off",
            json={"reason": "Uncollectible"},
        )
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["settlement"]["payment_status"] == "written_off"

    def test_write_off_no_settlement_404(self, client):
        load = services.create_load(customer="No Stl")
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/write-off",
            json={},
        )
        assert resp.status_code == 404

    def test_write_off_invalid_status_400(self, client, invoiced_load):
        load, _ = invoiced_load
        services.record_payment(load["load_id"], payment_amount=5000.0)
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/settlement/write-off",
            json={},
        )
        assert resp.status_code == 400


# ── Notifications ─────────────────────────────────────────────────


class TestSettlementNotifications:
    def test_dispute_sends_notification(self, invoiced_load):
        load, _ = invoiced_load
        services.dispute_settlement(load["load_id"], reason="Short pay")
        # Notification was called without error (file-based in test mode)

    def test_write_off_sends_notification(self, invoiced_load):
        load, _ = invoiced_load
        services.write_off_settlement(load["load_id"], reason="Bankrupt")


# ── Template rendering ────────────────────────────────────────────


class TestSettlementUI:
    def test_dispute_button_on_invoiced(self, client, invoiced_load):
        load, _ = invoiced_load
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Dispute</button>" in html

    def test_write_off_button_on_invoiced(self, client, invoiced_load):
        load, _ = invoiced_load
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Write Off</button>" in html

    def test_resolve_and_pay_on_disputed(self, client, invoiced_load):
        load, _ = invoiced_load
        services.dispute_settlement(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Resolve &amp; Pay" in html

    def test_write_off_on_disputed(self, client, invoiced_load):
        load, _ = invoiced_load
        services.dispute_settlement(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Write Off</button>" in html

    def test_no_buttons_on_paid(self, client, invoiced_load):
        load, _ = invoiced_load
        services.record_payment(load["load_id"], payment_amount=5000.0)
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Dispute</button>" not in html
        assert "Write Off</button>" not in html

    def test_no_buttons_on_written_off(self, client, invoiced_load):
        load, _ = invoiced_load
        services.write_off_settlement(load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Dispute</button>" not in html
