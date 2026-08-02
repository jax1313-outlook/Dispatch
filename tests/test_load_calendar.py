"""Tests for load calendar: service, API, and page rendering."""

from __future__ import annotations

import pytest

from dispatch import services
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


# ── Service layer ───────────────────────────────────────────────────


class TestLoadCalendarService:
    def test_empty_calendar(self):
        cal = services.get_load_calendar(2026, 8)
        assert cal["year"] == 2026
        assert cal["month"] == 8
        assert cal["month_name"] == "August"
        assert cal["pickups"] == {}
        assert cal["deliveries"] == {}
        assert len(cal["weeks"]) >= 4

    def test_pickups_grouped_by_day(self):
        services.create_load(
            customer="PickupCo",
            pickup_datetime="2026-08-15 10:00",
        )
        cal = services.get_load_calendar(2026, 8)
        assert "2026-08-15" in cal["pickups"]
        assert len(cal["pickups"]["2026-08-15"]) == 1
        assert cal["pickups"]["2026-08-15"][0]["customer"] == "PickupCo"

    def test_deliveries_grouped_by_day(self):
        services.create_load(
            customer="DeliveryCo",
            delivery_datetime="2026-08-20 14:00",
        )
        cal = services.get_load_calendar(2026, 8)
        assert "2026-08-20" in cal["deliveries"]
        assert len(cal["deliveries"]["2026-08-20"]) == 1

    def test_different_month_excluded(self):
        services.create_load(
            customer="JulyCo",
            pickup_datetime="2026-07-15 10:00",
        )
        cal = services.get_load_calendar(2026, 8)
        assert cal["pickups"] == {}

    def test_multiple_loads_same_day(self):
        services.create_load(customer="A", pickup_datetime="2026-08-10 08:00")
        services.create_load(customer="B", pickup_datetime="2026-08-10 14:00")
        cal = services.get_load_calendar(2026, 8)
        assert len(cal["pickups"]["2026-08-10"]) == 2

    def test_load_appears_in_both_pickup_and_delivery(self):
        services.create_load(
            customer="BothCo",
            pickup_datetime="2026-08-05 08:00",
            delivery_datetime="2026-08-07 16:00",
        )
        cal = services.get_load_calendar(2026, 8)
        assert "2026-08-05" in cal["pickups"]
        assert "2026-08-07" in cal["deliveries"]

    def test_weeks_structure(self):
        cal = services.get_load_calendar(2026, 8)
        for week in cal["weeks"]:
            assert len(week) == 7
            for day in week:
                assert 0 <= day <= 31


# ── API layer ───────────────────────────────────────────────────────


class TestLoadCalendarAPI:
    def test_calendar_endpoint(self, client):
        resp = client.get("/api/dispatch/calendar?year=2026&month=8")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["year"] == 2026
        assert data["month"] == 8
        assert "weeks" in data

    def test_calendar_with_data(self, client):
        services.create_load(customer="APICal", pickup_datetime="2026-08-12 09:00")
        resp = client.get("/api/dispatch/calendar?year=2026&month=8")
        data = resp.get_json()
        assert "2026-08-12" in data["pickups"]

    def test_defaults_to_current_month(self, client):
        resp = client.get("/api/dispatch/calendar")
        assert resp.status_code == 200


# ── Page rendering ──────────────────────────────────────────────────


class TestLoadCalendarPage:
    def test_page_renders(self, client):
        resp = client.get("/calendar?year=2026&month=8")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Load Calendar" in html
        assert "August 2026" in html

    def test_shows_pickup_events(self, client):
        services.create_load(customer="CalRender", pickup_datetime="2026-08-18 10:00")
        resp = client.get("/calendar?year=2026&month=8")
        html = resp.data.decode()
        assert "CalRender" in html

    def test_navigation_links(self, client):
        resp = client.get("/calendar?year=2026&month=8")
        html = resp.data.decode()
        assert "month=7" in html
        assert "month=9" in html

    def test_empty_state(self, client):
        resp = client.get("/calendar?year=2026&month=8")
        html = resp.data.decode()
        assert "No pickups or deliveries" in html

    def test_nav_link_exists(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "/calendar" in html
        assert "Calendar</a>" in html

    def test_legend_shown(self, client):
        resp = client.get("/calendar?year=2026&month=8")
        html = resp.data.decode()
        assert "Pickup" in html
        assert "Delivery" in html
