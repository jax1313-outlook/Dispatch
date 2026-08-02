"""Tests for lane history: store, service, and template rendering."""

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


class TestLaneHistoryStore:
    def test_empty_when_no_matching_loads(self):
        result = store.get_lane_history("Dallas, TX", "Houston, TX")
        assert result == []

    def test_returns_matching_loads(self):
        l1 = services.create_load(
            customer="A", pickup_location="Dallas, TX", delivery_location="Houston, TX"
        )
        l2 = services.create_load(
            customer="B", pickup_location="Dallas, TX", delivery_location="Houston, TX"
        )
        result = store.get_lane_history("Dallas, TX", "Houston, TX")
        ids = {r["load_id"] for r in result}
        assert l1["load_id"] in ids
        assert l2["load_id"] in ids

    def test_excludes_specified_load(self):
        l1 = services.create_load(
            customer="A", pickup_location="Dallas, TX", delivery_location="Houston, TX"
        )
        l2 = services.create_load(
            customer="B", pickup_location="Dallas, TX", delivery_location="Houston, TX"
        )
        result = store.get_lane_history(
            "Dallas, TX", "Houston, TX", exclude_load_id=l1["load_id"]
        )
        ids = {r["load_id"] for r in result}
        assert l1["load_id"] not in ids
        assert l2["load_id"] in ids

    def test_does_not_match_different_lane(self):
        services.create_load(
            customer="A", pickup_location="Dallas, TX", delivery_location="Houston, TX"
        )
        result = store.get_lane_history("Chicago, IL", "Houston, TX")
        assert result == []

    def test_empty_locations_return_empty(self):
        assert store.get_lane_history("", "Houston, TX") == []
        assert store.get_lane_history("Dallas, TX", "") == []
        assert store.get_lane_history("", "") == []

    def test_limit_respected(self):
        for i in range(5):
            services.create_load(
                customer=f"C{i}", pickup_location="A", delivery_location="B"
            )
        result = store.get_lane_history("A", "B", limit=3)
        assert len(result) == 3


# ── Service layer ───────────────────────────────────────────────────


class TestLaneHistoryService:
    def test_empty_for_nonexistent_load(self):
        result = services.get_lane_history("nonexistent-id")
        assert result == []

    def test_returns_history_with_rate_enrichment(self):
        l1 = services.create_load(
            customer="Old", pickup_location="A", delivery_location="B"
        )
        services.confirm_rate(l1["load_id"], rate_amount=1500.0)
        l2 = services.create_load(
            customer="New", pickup_location="A", delivery_location="B"
        )
        history = services.get_lane_history(l2["load_id"])
        assert len(history) == 1
        assert history[0]["load_id"] == l1["load_id"]
        assert history[0]["rate_amount"] == 1500.0
        assert history[0]["revenue"] == 1500.0

    def test_none_rate_when_no_rate_confirmed(self):
        l1 = services.create_load(
            customer="No Rate", pickup_location="X", delivery_location="Y"
        )
        l2 = services.create_load(
            customer="Current", pickup_location="X", delivery_location="Y"
        )
        history = services.get_lane_history(l2["load_id"])
        assert len(history) == 1
        assert history[0]["rate_amount"] is None
        assert history[0]["revenue"] is None

    def test_excludes_current_load(self):
        load = services.create_load(
            customer="Solo", pickup_location="M", delivery_location="N"
        )
        history = services.get_lane_history(load["load_id"])
        assert len(history) == 0

    def test_included_in_load_bundle(self):
        l1 = services.create_load(
            customer="Bundle Old", pickup_location="P", delivery_location="Q"
        )
        l2 = services.create_load(
            customer="Bundle New", pickup_location="P", delivery_location="Q"
        )
        bundle = services.get_load_bundle(l2["load_id"])
        assert "lane_history" in bundle
        assert len(bundle["lane_history"]) == 1
        assert bundle["lane_history"][0]["load_id"] == l1["load_id"]


# ── Template rendering ──────────────────────────────────────────────


class TestLaneHistoryTemplate:
    def test_lane_history_section_shown(self, client):
        l1 = services.create_load(
            customer="Template Old", pickup_location="Dallas", delivery_location="Houston"
        )
        l2 = services.create_load(
            customer="Template New", pickup_location="Dallas", delivery_location="Houston"
        )
        resp = client.get(f"/dispatch/{l2['load_id']}")
        html = resp.data.decode()
        assert "Lane History" in html
        assert "Template Old" in html

    def test_no_lane_history_section_when_empty(self, client):
        load = services.create_load(
            customer="Only Load", pickup_location="Unique1", delivery_location="Unique2"
        )
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Lane History" not in html
