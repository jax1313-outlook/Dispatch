"""Tests for visual load status stepper and dispatch KPI bar (PR 29)."""

from __future__ import annotations

import pytest

from dispatch import services
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
def sample_load():
    return services.create_load(customer="Stepper Customer")


# ── Visual Status Stepper ──────────────────────────────────────────


class TestStatusStepper:
    def test_stepper_present_on_detail(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "load-stepper" in html
        assert "Status Progress" in html

    def test_created_step_is_current(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert 'class="step current"' in html

    def test_dispatched_shows_completed_and_current(self, client, sample_load):
        services.update_load(sample_load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert 'class="step completed"' in html
        assert 'class="step current"' in html

    def test_in_transit_shows_multiple_completed(self, client, sample_load):
        load_id = sample_load["load_id"]
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up", "in_transit"]:
            services.update_load(load_id, status=s)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert html.count('class="step completed"') == 5
        assert html.count('class="step current"') == 1

    def test_cancelled_shows_cancelled_class(self, client, sample_load):
        services.update_load(sample_load["load_id"], status="cancelled")
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "cancelled" in html

    def test_archived_all_steps_completed_or_current(self, client, sample_load):
        load_id = sample_load["load_id"]
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed", "archived"]:
            services.update_load(load_id, status=s)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert html.count('class="step completed"') == 9
        assert html.count('class="step current"') == 1

    def test_all_lifecycle_steps_labeled(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        for label in ["created", "dispatched", "in transit", "delivered", "archived"]:
            assert label in html


# ── Dispatch KPI Bar ───────────────────────────────────────────────


class TestDispatchKPIBar:
    def test_no_kpi_bar_when_no_active(self, client):
        services.create_load(customer="Done Load")
        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "dispatch-kpi-bar" not in html or "Dispatched" not in html

    def test_kpi_shows_dispatched_count(self, client):
        l1 = services.create_load(customer="A")
        services.update_load(l1["load_id"], status="dispatched")
        l2 = services.create_load(customer="B")
        services.update_load(l2["load_id"], status="dispatched")

        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "dispatch-kpi-bar" in html
        assert "Dispatched" in html

    def test_kpi_shows_in_transit(self, client):
        ld = services.create_load(customer="Transit Co")
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up", "in_transit"]:
            services.update_load(ld["load_id"], status=s)

        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "In Transit" in html

    def test_kpi_shows_delivered(self, client):
        ld = services.create_load(customer="Del Co")
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered"]:
            services.update_load(ld["load_id"], status=s)

        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "Delivered" in html

    def test_kpi_not_shown_for_completed(self, client):
        ld = services.create_load(customer="Comp Co")
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed"]:
            services.update_load(ld["load_id"], status=s)

        resp = client.get("/dispatch")
        html = resp.data.decode()
        assert "kpi-chip" not in html or "Completed" not in html
