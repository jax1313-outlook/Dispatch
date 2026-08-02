"""Tests for stalled load detection and time-in-status display (PR 30)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _age_load(load_id: str, hours: int):
    """Backdate a load's updated_at to simulate staleness."""
    old_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    dispatch_store.update_load(load_id, updated_at=old_time)


# ── Service: check_stalled_loads ───────────────────────────────────


class TestCheckStalledLoads:
    def test_no_loads_returns_empty(self):
        assert services.check_stalled_loads() == []

    def test_fresh_load_not_stalled(self):
        services.create_load(customer="Fresh Corp")
        result = services.check_stalled_loads()
        assert len(result) == 0

    def test_old_created_load_is_stalled(self):
        load = services.create_load(customer="Stale Corp")
        _age_load(load["load_id"], 30)
        result = services.check_stalled_loads()
        assert len(result) == 1
        assert result[0]["load_id"] == load["load_id"]
        assert result[0]["hours_in_status"] >= 29

    def test_threshold_boundary_not_stalled(self):
        load = services.create_load(customer="Edge Corp")
        _age_load(load["load_id"], 23)
        result = services.check_stalled_loads()
        assert len(result) == 0

    def test_completed_load_not_stalled(self):
        load = services.create_load(customer="Done Corp")
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed"]:
            services.update_load(load["load_id"], status=s)
        _age_load(load["load_id"], 100)
        result = services.check_stalled_loads()
        assert len(result) == 0

    def test_cancelled_load_not_stalled(self):
        load = services.create_load(customer="Cancel Corp")
        services.update_load(load["load_id"], status="cancelled")
        _age_load(load["load_id"], 100)
        result = services.check_stalled_loads()
        assert len(result) == 0

    def test_in_transit_threshold(self):
        load = services.create_load(customer="Transit Corp")
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up", "in_transit"]:
            services.update_load(load["load_id"], status=s)
        _age_load(load["load_id"], 50)
        result = services.check_stalled_loads()
        assert len(result) == 1
        assert result[0]["threshold_hours"] == 48

    def test_custom_thresholds(self):
        load = services.create_load(customer="Custom Corp")
        _age_load(load["load_id"], 5)
        result = services.check_stalled_loads(thresholds={"created": 2})
        assert len(result) == 1

    def test_sorted_by_hours_descending(self):
        l1 = services.create_load(customer="Old Corp")
        l2 = services.create_load(customer="Older Corp")
        _age_load(l1["load_id"], 30)
        _age_load(l2["load_id"], 50)
        result = services.check_stalled_loads()
        assert result[0]["hours_in_status"] > result[1]["hours_in_status"]

    def test_multiple_statuses_detected(self):
        l1 = services.create_load(customer="Created Stale")
        _age_load(l1["load_id"], 30)
        l2 = services.create_load(customer="Dispatched Stale")
        services.update_load(l2["load_id"], status="dispatched")
        _age_load(l2["load_id"], 15)
        result = services.check_stalled_loads()
        assert len(result) == 2


# ── API endpoint ───────────────────────────────────────────────────


class TestStalledAPI:
    def test_stalled_endpoint_empty(self, client):
        resp = client.get("/api/dispatch/loads/stalled")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert data["loads"] == []

    def test_stalled_endpoint_returns_stalled(self, client):
        load = services.create_load(customer="API Stale")
        _age_load(load["load_id"], 30)
        resp = client.get("/api/dispatch/loads/stalled")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["loads"][0]["customer"] == "API Stale"


# ── time_ago filter ────────────────────────────────────────────────


class TestTimeAgoFilter:
    def test_filter_minutes(self, client):
        from portal.app import create_app
        app = create_app()
        with app.app_context():
            now = datetime.now(timezone.utc)
            ts = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = app.jinja_env.filters["time_ago"](ts)
            assert result == "30m"

    def test_filter_hours(self, client):
        from portal.app import create_app
        app = create_app()
        with app.app_context():
            now = datetime.now(timezone.utc)
            ts = (now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = app.jinja_env.filters["time_ago"](ts)
            assert result == "5h"

    def test_filter_days(self, client):
        from portal.app import create_app
        app = create_app()
        with app.app_context():
            now = datetime.now(timezone.utc)
            ts = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = app.jinja_env.filters["time_ago"](ts)
            assert result == "3d"

    def test_filter_empty(self, client):
        from portal.app import create_app
        app = create_app()
        with app.app_context():
            assert app.jinja_env.filters["time_ago"]("") == "—"


# ── Dispatch page rendering ───────────────────────────────────────


class TestDispatchPageStalled:
    def test_no_stalled_banner_when_fresh(self, client):
        services.create_load(customer="Fresh")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Stalled" not in html

    def test_stalled_banner_shown(self, client):
        load = services.create_load(customer="Stale Banner Corp")
        _age_load(load["load_id"], 30)
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Stalled" in html
        assert "Stale Banner Corp" in html

    def test_age_column_present(self, client):
        services.create_load(customer="Age Test")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert ">Age<" in html

    def test_stalled_row_highlighted(self, client):
        load = services.create_load(customer="Highlight Corp")
        _age_load(load["load_id"], 30)
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "border-left:3px solid #e74c3c" in html
