"""Tests for home dashboard enhancements (PR 31)."""

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
    old_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    dispatch_store.update_load(load_id, updated_at=old_time)


# ── get_recent_activity store function ────────────────────────────


class TestGetRecentActivity:
    def test_empty_when_no_milestones(self):
        assert dispatch_store.get_recent_activity() == []

    def test_returns_milestones_with_customer(self):
        load = services.create_load(customer="Test Corp")
        services.add_milestone(load["load_id"], event_type="arrived_pickup", location="NYC")
        result = dispatch_store.get_recent_activity()
        assert len(result) == 1
        assert result[0]["customer"] == "Test Corp"
        assert result[0]["event_type"] == "arrived_pickup"

    def test_ordered_by_event_time_desc(self):
        load = services.create_load(customer="Order Corp")
        t1 = "2025-01-01T10:00:00Z"
        t2 = "2025-01-01T12:00:00Z"
        services.add_milestone(load["load_id"], event_type="dispatched", location="A", event_time=t1)
        services.add_milestone(load["load_id"], event_type="en_route_pickup", location="B", event_time=t2)
        result = dispatch_store.get_recent_activity()
        assert result[0]["event_type"] == "en_route_pickup"
        assert result[1]["event_type"] == "dispatched"

    def test_limit_respected(self):
        load = services.create_load(customer="Limit Corp")
        types = ["dispatched", "arrived_pickup", "loaded", "in_transit", "delivered"]
        for t in types:
            services.add_milestone(load["load_id"], event_type=t, location="X")
        result = dispatch_store.get_recent_activity(limit=3)
        assert len(result) == 3

    def test_spans_multiple_loads(self):
        l1 = services.create_load(customer="Corp A")
        l2 = services.create_load(customer="Corp B")
        services.add_milestone(l1["load_id"], event_type="arrived_pickup", location="A")
        services.add_milestone(l2["load_id"], event_type="delivered", location="B")
        result = dispatch_store.get_recent_activity()
        customers = {r["customer"] for r in result}
        assert customers == {"Corp A", "Corp B"}

    def test_includes_load_status(self):
        load = services.create_load(customer="Status Corp")
        services.add_milestone(load["load_id"], event_type="dispatched", location="HQ")
        result = dispatch_store.get_recent_activity()
        assert result[0]["load_status"] == "dispatched"


# ── Home page rendering ──────────────────────────────────────────


class TestHomePage:
    def test_home_loads(self, client):
        resp = client.get("/home")
        assert resp.status_code == 200

    def test_no_stalled_section_when_none(self, client):
        services.create_load(customer="Fresh Corp")
        resp = client.get("/home")
        html = resp.data.decode()
        assert "stalled-alert" not in html

    def test_stalled_section_shown(self, client):
        load = services.create_load(customer="Old Corp")
        _age_load(load["load_id"], 30)
        resp = client.get("/home")
        html = resp.data.decode()
        assert "stalled-alert" in html
        assert "Old Corp" in html
        assert "Stalled Loads" in html

    def test_stalled_links_to_detail(self, client):
        load = services.create_load(customer="Link Corp")
        _age_load(load["load_id"], 30)
        resp = client.get("/home")
        html = resp.data.decode()
        assert load["load_id"][:8] in html

    def test_no_activity_section_when_empty(self, client):
        resp = client.get("/home")
        html = resp.data.decode()
        assert "recent-activity" not in html

    def test_activity_section_shown(self, client):
        load = services.create_load(customer="Activity Corp")
        services.add_milestone(load["load_id"], event_type="arrived_pickup", location="NYC")
        resp = client.get("/home")
        html = resp.data.decode()
        assert "recent-activity" in html
        assert "Recent Activity" in html
        assert "arrived_pickup" in html
        assert "Activity Corp" in html

    def test_activity_note_shown(self, client):
        load = services.create_load(customer="Note Corp")
        services.add_milestone(
            load["load_id"], event_type="delivered", location="LA", note="Arrived early"
        )
        resp = client.get("/home")
        html = resp.data.decode()
        assert "Arrived early" in html

    def test_stalled_table_has_threshold(self, client):
        load = services.create_load(customer="Threshold Corp")
        _age_load(load["load_id"], 30)
        resp = client.get("/home")
        html = resp.data.decode()
        assert "24h" in html
