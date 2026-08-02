"""Tests for inline load editing and status transitions (PR 28)."""

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
    return services.create_load(
        customer="Test Customer",
        broker_shipper="Test Broker",
        pickup_location="Chicago, IL",
        delivery_location="Dallas, TX",
        pickup_datetime="2026-08-05 08:00",
        delivery_datetime="2026-08-06 16:00",
        notes="Fragile cargo",
    )


# ── Inline editing via PATCH API ───────────────────────────────────


class TestLoadEditAPI:
    def test_update_customer(self, client, sample_load):
        load_id = sample_load["load_id"]
        resp = client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={"customer": "New Customer"},
        )
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["load"]["customer"] == "New Customer"

    def test_update_multiple_fields(self, client, sample_load):
        load_id = sample_load["load_id"]
        resp = client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={
                "broker_shipper": "New Broker",
                "pickup_location": "Detroit, MI",
                "notes": "Updated notes",
            },
        )
        data = resp.get_json()
        assert data["load"]["broker_shipper"] == "New Broker"
        assert data["load"]["pickup_location"] == "Detroit, MI"
        assert data["load"]["notes"] == "Updated notes"

    def test_update_preserves_unchanged(self, client, sample_load):
        load_id = sample_load["load_id"]
        client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={"customer": "Changed"},
        )
        load = services.get_load(load_id)
        assert load["customer"] == "Changed"
        assert load["delivery_location"] == "Dallas, TX"

    def test_update_status_via_patch(self, client, sample_load):
        load_id = sample_load["load_id"]
        resp = client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={"status": "dispatched"},
        )
        data = resp.get_json()
        assert data["load"]["status"] == "dispatched"

    def test_invalid_status_rejected(self, client, sample_load):
        load_id = sample_load["load_id"]
        resp = client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={"status": "bogus"},
        )
        assert resp.status_code == 400
        assert "Invalid status" in resp.get_json()["error"]

    def test_update_nonexistent_load(self, client):
        resp = client.patch(
            "/api/dispatch/loads/nonexistent",
            json={"customer": "X"},
        )
        assert resp.status_code == 404


# ── Status transitions ─────────────────────────────────────────────


class TestStatusTransitions:
    def test_full_lifecycle(self, client, sample_load):
        load_id = sample_load["load_id"]
        sequence = [
            "dispatched", "en_route_pickup", "at_pickup",
            "picked_up", "in_transit", "at_delivery",
            "delivered", "completed", "archived",
        ]
        for status in sequence:
            resp = client.patch(
                f"/api/dispatch/loads/{load_id}",
                json={"status": status},
            )
            assert resp.get_json()["load"]["status"] == status

    def test_cancel_from_created(self, client, sample_load):
        resp = client.patch(
            f"/api/dispatch/loads/{sample_load['load_id']}",
            json={"status": "cancelled"},
        )
        assert resp.get_json()["load"]["status"] == "cancelled"

    def test_cancel_from_dispatched(self, client, sample_load):
        load_id = sample_load["load_id"]
        services.update_load(load_id, status="dispatched")
        resp = client.patch(
            f"/api/dispatch/loads/{load_id}",
            json={"status": "cancelled"},
        )
        assert resp.get_json()["load"]["status"] == "cancelled"


# ── Detail page rendering ─────────────────────────────────────────


class TestDetailPageEdit:
    def test_edit_button_present(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert 'id="edit-load-btn"' in html

    def test_edit_form_present(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert 'id="load-info-edit"' in html
        assert 'name="customer"' in html
        assert 'name="broker_shipper"' in html

    def test_edit_form_prepopulated(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert 'value="Test Customer"' in html
        assert 'value="Chicago, IL"' in html

    def test_status_dropdown_present(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert '<option value="created"' in html
        assert '<option value="dispatched"' in html

    def test_advance_buttons_for_created(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "Dispatched" in html
        assert "Cancelled" in html

    def test_advance_buttons_for_dispatched(self, client, sample_load):
        services.update_load(sample_load["load_id"], status="dispatched")
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "En Route Pickup" in html

    def test_no_advance_for_archived(self, client, sample_load):
        load_id = sample_load["load_id"]
        for s in ["dispatched", "en_route_pickup", "at_pickup", "picked_up",
                   "in_transit", "at_delivery", "delivered", "completed", "archived"]:
            services.update_load(load_id, status=s)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert "Advance:" not in html

    def test_no_advance_for_cancelled(self, client, sample_load):
        services.update_load(sample_load["load_id"], status="cancelled")
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "Advance:" not in html

    def test_save_js_function_present(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert "saveLoadInfo" in html
        assert "advanceLoadStatus" in html

    def test_load_statuses_in_form(self, client, sample_load):
        resp = client.get(f"/dispatch/{sample_load['load_id']}")
        html = resp.data.decode()
        assert '<option value="completed"' in html
        assert '<option value="archived"' in html
