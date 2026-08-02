"""Tests for dashboard charts: chart data service, API, and template rendering."""

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


# ── Service layer ────────────────────────────────────────────────────


class TestChartDataService:
    def test_empty_when_no_loads(self):
        data = services.get_chart_data()
        assert data["loads_by_status"] == {}
        assert data["monthly_revenue"] == []

    def test_loads_by_status_counted(self):
        services.create_load(customer="A")
        services.create_load(customer="B")
        load3 = services.create_load(customer="C")
        services.update_load(load3["load_id"], status="dispatched")
        data = services.get_chart_data()
        assert data["loads_by_status"]["created"] == 2
        assert data["loads_by_status"]["dispatched"] == 1

    def test_monthly_revenue_with_rates(self):
        load = services.create_load(customer="Revenue Co")
        services.confirm_rate(load["load_id"], rate_amount=1500.0)
        data = services.get_chart_data()
        assert len(data["monthly_revenue"]) >= 1
        assert data["monthly_revenue"][0]["revenue"] == 1500.0
        assert data["monthly_revenue"][0]["loads"] >= 1

    def test_monthly_revenue_without_rate(self):
        services.create_load(customer="No Rate Co")
        data = services.get_chart_data()
        assert len(data["monthly_revenue"]) >= 1
        assert data["monthly_revenue"][0]["revenue"] == 0
        assert data["monthly_revenue"][0]["loads"] == 1

    def test_multiple_months_sorted(self):
        l1 = services.create_load(customer="Jan Co")
        l2 = services.create_load(customer="Feb Co")
        with store.get_connection() as conn:
            conn.execute(
                "UPDATE loads SET created_at='2026-01-15T10:00:00Z' WHERE load_id=?",
                (l1["load_id"],),
            )
            conn.execute(
                "UPDATE loads SET created_at='2026-02-20T10:00:00Z' WHERE load_id=?",
                (l2["load_id"],),
            )
        data = services.get_chart_data()
        months = [m["month"] for m in data["monthly_revenue"]]
        assert months == sorted(months)


# ── API layer ────────────────────────────────────────────────────────


class TestChartDataAPI:
    def test_chart_endpoint_returns_ok(self, client):
        resp = client.get("/api/dispatch/charts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "loads_by_status" in data
        assert "monthly_revenue" in data

    def test_chart_endpoint_with_data(self, client):
        services.create_load(customer="API Chart Co")
        resp = client.get("/api/dispatch/charts")
        data = resp.get_json()
        assert data["loads_by_status"]["created"] == 1


# ── Template rendering ──────────────────────────────────────────────


class TestChartRendering:
    def test_chart_section_shown_with_loads(self, client):
        services.create_load(customer="Chart Render Co")
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Load Overview" in html
        assert "Loads by Status" in html

    def test_no_chart_section_without_loads(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Load Overview" not in html

    def test_revenue_chart_shown_with_rates(self, client):
        load = services.create_load(customer="Rev Chart Co")
        services.confirm_rate(load["load_id"], rate_amount=2000.0)
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Monthly Revenue" in html
        assert "<svg" in html

    def test_status_bar_widths_rendered(self, client):
        services.create_load(customer="Bar Co")
        resp = client.get("/home")
        html = resp.data.decode()
        assert "created" in html
        assert "background:" in html
