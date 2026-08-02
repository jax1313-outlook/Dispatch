"""Tests for load deletion (PR 34)."""

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


# ── Service layer ────────────────────────────────────────────────


class TestDeleteLoadService:
    def test_delete_created_load(self):
        load = services.create_load(customer="Delete Me")
        assert load["status"] == "created"
        result = services.delete_load(load["load_id"])
        assert result is True
        assert services.get_load(load["load_id"]) is None

    def test_delete_cancelled_load(self):
        load = services.create_load(customer="Cancel Me")
        services.update_load(load["load_id"], status="cancelled")
        result = services.delete_load(load["load_id"])
        assert result is True
        assert services.get_load(load["load_id"]) is None

    def test_cannot_delete_dispatched_load(self):
        load = services.create_load(customer="Dispatched")
        services.update_load(load["load_id"], status="dispatched")
        with pytest.raises(ValueError, match="Cannot delete"):
            services.delete_load(load["load_id"])

    def test_cannot_delete_in_transit_load(self):
        load = services.create_load(customer="In Transit")
        lid = load["load_id"]
        for s in ("dispatched", "en_route_pickup", "at_pickup", "picked_up", "in_transit"):
            services.update_load(lid, status=s)
        with pytest.raises(ValueError, match="Cannot delete"):
            services.delete_load(lid)

    def test_cannot_delete_delivered_load(self):
        load = services.create_load(customer="Delivered")
        lid = load["load_id"]
        for s in ("dispatched", "en_route_pickup", "at_pickup", "picked_up",
                  "in_transit", "at_delivery", "delivered"):
            services.update_load(lid, status=s)
        with pytest.raises(ValueError, match="Cannot delete"):
            services.delete_load(lid)

    def test_cannot_delete_completed_load(self):
        load = services.create_load(customer="Completed")
        lid = load["load_id"]
        for s in ("dispatched", "en_route_pickup", "at_pickup", "picked_up",
                  "in_transit", "at_delivery", "delivered", "completed"):
            services.update_load(lid, status=s)
        with pytest.raises(ValueError, match="Cannot delete"):
            services.delete_load(lid)

    def test_delete_nonexistent_load(self):
        with pytest.raises(ValueError, match="not found"):
            services.delete_load("NONEXISTENT")

    def test_error_message_lists_allowed_statuses(self):
        load = services.create_load(customer="Check Msg")
        services.update_load(load["load_id"], status="dispatched")
        with pytest.raises(ValueError, match="cancelled") as exc_info:
            services.delete_load(load["load_id"])
        assert "created" in str(exc_info.value)


# ── API endpoint ─────────────────────────────────────────────────


class TestDeleteLoadAPI:
    def test_delete_via_api(self, client):
        load = services.create_load(customer="API Delete")
        resp = client.delete(f"/api/dispatch/loads/{load['load_id']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["deleted"] is True

    def test_delete_returns_404_for_missing(self, client):
        resp = client.delete("/api/dispatch/loads/NOPE")
        assert resp.status_code == 404

    def test_delete_returns_400_for_bad_status(self, client):
        load = services.create_load(customer="No Delete")
        services.update_load(load["load_id"], status="dispatched")
        resp = client.delete(f"/api/dispatch/loads/{load['load_id']}")
        assert resp.status_code == 400
        assert "Cannot delete" in resp.get_json()["error"]

    def test_load_gone_after_api_delete(self, client):
        load = services.create_load(customer="Gone")
        client.delete(f"/api/dispatch/loads/{load['load_id']}")
        assert services.get_load(load["load_id"]) is None


# ── UI button visibility ─────────────────────────────────────────


class TestDeleteButtonVisibility:
    def test_delete_button_on_created_load(self, client):
        load = services.create_load(customer="Show Button")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Delete Load</button>" in html

    def test_delete_button_on_cancelled_load(self, client):
        load = services.create_load(customer="Cancelled Show")
        services.update_load(load["load_id"], status="cancelled")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Delete Load</button>" in html

    def test_no_delete_button_on_dispatched_load(self, client):
        load = services.create_load(customer="No Button")
        services.update_load(load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "Delete Load</button>" not in html

    def test_no_delete_button_on_completed_load(self, client):
        load = services.create_load(customer="Completed No")
        lid = load["load_id"]
        for s in ("dispatched", "en_route_pickup", "at_pickup", "picked_up",
                  "in_transit", "at_delivery", "delivered", "completed"):
            services.update_load(lid, status=s)
        resp = client.get(f"/dispatch/{lid}")
        html = resp.data.decode()
        assert "Delete Load</button>" not in html

    def test_delete_redirects_to_dispatch_list(self, client):
        load = services.create_load(customer="Redirect Test")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode()
        assert "window.location.href = '/dispatch'" in html
