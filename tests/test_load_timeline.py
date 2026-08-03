"""Tests for load timeline visualization feature."""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from dispatch import services, store
from dispatch.models import LoadActivity


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def client():
    from portal.app import create_app
    app = create_app({"TESTING": True})
    with app.test_client() as c:
        yield c


def _make_load(**kw) -> dict:
    defaults = {"customer": "Timeline Co", "pickup_location": "A", "delivery_location": "B"}
    defaults.update(kw)
    return services.create_load(**defaults)


# ── Progress bar rendering ──────────────────────────────────────────


class TestProgressBar:
    def test_load_progress_section_renders(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Load Progress" in html
        assert "timeline-progress" in html

    def test_all_lifecycle_steps_shown(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        for step in [
            "Dispatched", "En Route Pickup", "Arrived Pickup", "Loaded",
            "Departed Pickup", "In Transit", "Arrived Delivery",
            "Delivered", "Pod Received", "Completed",
        ]:
            assert step in html

    def test_completed_steps_show_checkmark(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Yard")
        services.add_milestone(load["load_id"], "en_route_pickup")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "&#10003;" in html

    def test_current_step_highlighted_green(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Yard")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "box-shadow:0 0 0 3px rgba(39,174,96,0.3)" in html

    def test_next_expected_step_shown_orange(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Yard")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "border:2px solid #f39c12" in html

    def test_no_milestones_all_steps_grey(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "&#10003;" not in html
        assert "background:#eee" in html

    def test_multiple_milestones_progress(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        services.add_milestone(load["load_id"], "en_route_pickup")
        services.add_milestone(load["load_id"], "arrived_pickup")
        services.add_milestone(load["load_id"], "loaded")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert html.count("&#10003;") >= 4

    def test_completed_load_all_checkmarks(self, client):
        load = _make_load()
        for step in [
            "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
            "departed_pickup", "in_transit", "arrived_delivery",
            "delivered", "pod_received", "completed",
        ]:
            services.add_milestone(load["load_id"], step)
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert html.count("&#10003;") >= 10

    def test_green_connector_line_between_completed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        services.add_milestone(load["load_id"], "en_route_pickup")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "background:#27ae60" in html

    def test_grey_connector_line_for_future_steps(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "background:#ddd" in html


# ── Event feed rendering ────────────────────────────────────────────


class TestEventFeed:
    def test_event_feed_renders_with_milestones(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Yard A")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Event Feed" in html
        assert "timeline-feed" in html

    def test_event_feed_hidden_when_no_events(self, client):
        load = _make_load()
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Event Feed" not in html
        assert "timeline-feed" not in html

    def test_milestone_events_green_dot(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Yard")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert ">MS</div>" in html

    def test_exception_events_red_dot(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Late arrival")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert ">EX</div>" in html
        assert "Late arrival" in html

    def test_status_change_events_blue_dot(self, client):
        load = _make_load()
        services.update_load(load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert ">ST</div>" in html
        assert "Status Change" in html

    def test_milestone_location_in_feed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "arrived_pickup", location="Chicago IL")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Chicago IL" in html
        assert "Arrived Pickup" in html

    def test_milestone_note_in_feed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "loaded", note="Full truckload")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Full truckload" in html

    def test_exception_severity_shown(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="damage", severity="high", description="Cargo damaged")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "high" in html
        assert "Cargo damaged" in html

    def test_mixed_events_in_feed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="Start")
        services.update_load(load["load_id"], status="dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Weather")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert ">MS</div>" in html
        assert ">ST</div>" in html
        assert ">EX</div>" in html

    def test_events_sorted_chronologically(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", location="First")
        services.add_milestone(load["load_id"], "en_route_pickup", location="Second")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        pos_first = html.index("First")
        pos_second = html.index("Second")
        assert pos_first < pos_second

    def test_milestone_source_in_feed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched", source="eld")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "eld" in html

    def test_multiple_exceptions_in_feed(self, client):
        load = _make_load()
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Flat tire")
        services.open_exception(load["load_id"], exception_type="damage", description="Dented trailer")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Flat tire" in html
        assert "Dented trailer" in html

    def test_status_change_message_in_feed(self, client):
        load = _make_load()
        services.update_load(load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Status changed from created to dispatched" in html
