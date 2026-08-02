"""Tests for broker scorecard: store, service, API, and page rendering."""

from __future__ import annotations

import pytest

from dispatch import services, store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Store layer ─────────────────────────────────────────────────────


class TestBrokerScorecardStore:
    def test_empty_when_no_loads(self):
        assert store.get_broker_scorecards() == []

    def test_groups_by_broker(self):
        services.create_load(customer="A", broker_shipper="BrokerX")
        services.create_load(customer="B", broker_shipper="BrokerX")
        services.create_load(customer="C", broker_shipper="BrokerY")
        cards = store.get_broker_scorecards()
        names = {c["broker_shipper"] for c in cards}
        assert "BrokerX" in names
        assert "BrokerY" in names
        bx = next(c for c in cards if c["broker_shipper"] == "BrokerX")
        assert bx["total_loads"] == 2

    def test_excludes_empty_broker(self):
        services.create_load(customer="NoBroker")
        cards = store.get_broker_scorecards()
        assert len(cards) == 0

    def test_revenue_aggregation(self):
        l1 = services.create_load(customer="A", broker_shipper="BRK")
        services.confirm_rate(l1["load_id"], rate_amount=1000.0)
        l2 = services.create_load(customer="B", broker_shipper="BRK")
        services.confirm_rate(l2["load_id"], rate_amount=2000.0)
        cards = store.get_broker_scorecards()
        brk = cards[0]
        assert brk["total_revenue"] == 3000.0
        assert brk["avg_rate"] == 1500.0

    def test_completion_rate(self):
        l1 = services.create_load(customer="A", broker_shipper="BRK")
        services.update_load(l1["load_id"], status="dispatched")
        services.update_load(l1["load_id"], status="en_route_pickup")
        services.update_load(l1["load_id"], status="at_pickup")
        services.update_load(l1["load_id"], status="picked_up")
        services.update_load(l1["load_id"], status="in_transit")
        services.update_load(l1["load_id"], status="at_delivery")
        services.update_load(l1["load_id"], status="delivered")
        services.update_load(l1["load_id"], status="completed")
        services.create_load(customer="B", broker_shipper="BRK")
        cards = store.get_broker_scorecards()
        brk = cards[0]
        assert brk["completion_rate"] == 50.0

    def test_payment_reliability(self):
        l1 = services.create_load(customer="A", broker_shipper="BRK")
        services.confirm_rate(l1["load_id"], rate_amount=500.0)
        services.create_settlement(l1["load_id"])
        services.update_settlement(l1["load_id"], payment_status="paid", payment_amount=500.0)
        l2 = services.create_load(customer="B", broker_shipper="BRK")
        services.confirm_rate(l2["load_id"], rate_amount=500.0)
        services.create_settlement(l2["load_id"])
        services.update_settlement(l2["load_id"], payment_status="overdue")
        cards = store.get_broker_scorecards()
        brk = cards[0]
        assert brk["paid_count"] == 1
        assert brk["overdue_count"] == 1
        assert brk["payment_reliability"] == 50.0

    def test_broker_loads(self):
        services.create_load(customer="A", broker_shipper="BRK")
        services.create_load(customer="B", broker_shipper="BRK")
        services.create_load(customer="C", broker_shipper="OTHER")
        loads = store.get_broker_loads("BRK")
        assert len(loads) == 2


# ── Service layer ───────────────────────────────────────────────────


class TestBrokerScorecardService:
    def test_get_scorecards(self):
        services.create_load(customer="A", broker_shipper="SvcBroker")
        cards = services.get_broker_scorecards()
        assert len(cards) == 1
        assert cards[0]["broker_shipper"] == "SvcBroker"

    def test_get_broker_detail(self):
        l = services.create_load(customer="A", broker_shipper="DetailBrk")
        services.confirm_rate(l["load_id"], rate_amount=800.0)
        detail = services.get_broker_detail("DetailBrk")
        assert detail["broker"] == "DetailBrk"
        assert len(detail["loads"]) == 1
        assert detail["loads"][0]["rate_amount"] == 800.0
        assert detail["loads"][0]["revenue"] == 800.0

    def test_broker_detail_empty(self):
        detail = services.get_broker_detail("Nonexistent")
        assert detail["loads"] == []


# ── API layer ───────────────────────────────────────────────────────


class TestBrokerScorecardAPI:
    def test_list_brokers(self, client):
        services.create_load(customer="A", broker_shipper="APIBrk")
        resp = client.get("/api/dispatch/brokers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert any(b["broker_shipper"] == "APIBrk" for b in data)

    def test_broker_detail(self, client):
        services.create_load(customer="A", broker_shipper="DetailAPI")
        resp = client.get("/api/dispatch/brokers/DetailAPI")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["broker"] == "DetailAPI"
        assert len(data["loads"]) == 1

    def test_broker_detail_404(self, client):
        resp = client.get("/api/dispatch/brokers/Nobody")
        assert resp.status_code == 404


# ── Template rendering ──────────────────────────────────────────────


class TestBrokerScorecardPage:
    def test_page_renders(self, client):
        services.create_load(customer="A", broker_shipper="PageBrk")
        resp = client.get("/brokers")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Broker Scorecard" in html
        assert "PageBrk" in html

    def test_empty_state(self, client):
        resp = client.get("/brokers")
        html = resp.data.decode()
        assert "No broker data yet" in html

    def test_summary_cards(self, client):
        services.create_load(customer="A", broker_shipper="SumBrk")
        resp = client.get("/brokers")
        html = resp.data.decode()
        assert "Active Brokers" in html
        assert "Total Loads" in html

    def test_nav_link(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "/brokers" in html
        assert "Brokers</a>" in html
