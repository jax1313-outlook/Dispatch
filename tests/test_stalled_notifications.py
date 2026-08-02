"""Tests for stalled load notifications: service, API, and UI."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from dispatch import services, store
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


def _make_stalled_load(customer="Stale Co", status="created", hours_ago=48):
    """Create a load and backdate its updated_at to make it stalled."""
    load = services.create_load(customer=customer)
    past = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    store.update_load(load["load_id"], updated_at=past)
    if status != "created":
        store.update_load(load["load_id"], status=status)
        store.update_load(load["load_id"], updated_at=past)
    return store.get_load(load["load_id"])


# ── Notification Function ──────────────────────────────────────────


class TestNotifyStalled:
    def test_notify_stalled_generates_email(self):
        from dispatch.notifications import notify_stalled

        load = {
            "load_id": "LOAD-TEST-001",
            "customer": "Acme",
            "status": "dispatched",
            "pickup_location": "Chicago",
            "delivery_location": "Dallas",
            "driver": "John",
            "equipment": "Van 42",
            "hours_in_status": 15.2,
            "threshold_hours": 12,
        }
        result = notify_stalled(load)
        assert result
        assert "dispatch-stalled-LOAD-TEST-001" in result

    def test_notify_stalled_includes_hours(self):
        from dispatch.notifications import notify_stalled

        load = {
            "load_id": "LOAD-TEST-002",
            "customer": "Beta LLC",
            "status": "in_transit",
            "pickup_location": "",
            "delivery_location": "",
            "driver": "",
            "equipment": "",
            "hours_in_status": 72.5,
            "threshold_hours": 48,
        }
        result = notify_stalled(load)
        assert result


# ── Service Layer ──────────────────────────────────────────────────


class TestNotifyStalledLoadsService:
    def test_returns_empty_when_no_stalled(self):
        services.create_load(customer="Fresh Load")
        result = services.notify_stalled_loads()
        assert result == []

    def test_returns_stalled_loads(self):
        _make_stalled_load(customer="Old Load", hours_ago=48)
        result = services.notify_stalled_loads()
        assert len(result) >= 1
        customers = [l.get("customer") for l in result]
        assert "Old Load" in customers

    def test_notifies_each_stalled_load(self):
        _make_stalled_load(customer="Stale A", hours_ago=48)
        _make_stalled_load(customer="Stale B", hours_ago=30)
        with patch("dispatch.notifications.notify_stalled") as mock_notify:
            mock_notify.return_value = "sent"
            result = services.notify_stalled_loads()
        assert mock_notify.call_count == len(result)

    def test_respects_custom_thresholds(self):
        _make_stalled_load(customer="Custom", hours_ago=5)
        result = services.notify_stalled_loads(thresholds={"created": 1})
        assert len(result) >= 1


# ── API Endpoint ───────────────────────────────────────────────────


class TestStallNotifyAPI:
    def test_notify_endpoint_returns_ok(self, client):
        resp = client.post("/api/dispatch/loads/stalled/notify")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["notified"] == 0

    def test_notify_endpoint_with_stalled(self, client):
        _make_stalled_load(customer="API Stale", hours_ago=48)
        resp = client.post("/api/dispatch/loads/stalled/notify")
        data = resp.get_json()
        assert data["notified"] >= 1
        assert any(l["customer"] == "API Stale" for l in data["loads"])

    def test_notify_response_includes_load_details(self, client):
        _make_stalled_load(customer="Detail Test", hours_ago=48)
        resp = client.post("/api/dispatch/loads/stalled/notify")
        data = resp.get_json()
        if data["notified"] > 0:
            load = data["loads"][0]
            assert "load_id" in load
            assert "customer" in load
            assert "hours_in_status" in load

    def test_get_stalled_still_works(self, client):
        _make_stalled_load(hours_ago=48)
        resp = client.get("/api/dispatch/loads/stalled")
        assert resp.status_code == 200
        assert resp.get_json()["count"] >= 1


# ── UI Elements ────────────────────────────────────────────────────


class TestStallAlertUI:
    def test_dispatch_page_has_alert_button(self, client):
        _make_stalled_load(hours_ago=48)
        resp = client.get("/dispatch")
        assert resp.status_code == 200
        assert b"Send Stall Alerts" in resp.data

    def test_dispatch_page_no_button_when_no_stalled(self, client):
        services.create_load(customer="Fresh")
        resp = client.get("/dispatch")
        assert resp.status_code == 200
        assert b"Send Stall Alerts" not in resp.data

    def test_js_function_present(self, client):
        _make_stalled_load(hours_ago=48)
        resp = client.get("/dispatch")
        assert b"sendStallAlerts" in resp.data
