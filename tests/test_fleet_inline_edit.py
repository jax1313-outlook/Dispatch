"""Tests for fleet inline editing UI (PR 35)."""

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


# ── Driver inline edit UI ────────────────────────────────────────


class TestDriverInlineEdit:
    def test_edit_button_shown(self, client):
        services.create_driver(name="Alice")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Edit</button>" in html

    def test_delete_button_shown(self, client):
        services.create_driver(name="Bob")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Delete</button>" in html

    def test_edit_row_present_hidden(self, client):
        drv = services.create_driver(name="Carol")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert f"edit-driver-{drv['driver_id']}" in html
        assert 'style="display:none;background:#f8f9fa;"' in html

    def test_edit_form_has_phone_field(self, client):
        services.create_driver(name="Dan", phone="555-1234")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "555-1234" in html
        assert 'name="phone"' in html

    def test_edit_form_has_email_field(self, client):
        services.create_driver(name="Eve", email="eve@test.com")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "eve@test.com" in html
        assert 'name="email"' in html

    def test_edit_form_has_license_field(self, client):
        services.create_driver(name="Frank", license_number="CDL-999")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "CDL-999" in html
        assert 'name="license_number"' in html

    def test_edit_form_has_notes_field(self, client):
        services.create_driver(name="Grace")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert 'name="notes"' in html

    def test_patch_driver_via_api(self, client):
        drv = services.create_driver(name="Hank", phone="old")
        resp = client.patch(
            f"/api/dispatch/drivers/{drv['driver_id']}",
            json={"phone": "new-phone"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["driver"]["phone"] == "new-phone"

    def test_delete_driver_via_api(self, client):
        drv = services.create_driver(name="Iris")
        resp = client.delete(f"/api/dispatch/drivers/{drv['driver_id']}")
        assert resp.status_code == 200


# ── Equipment inline edit UI ─────────────────────────────────────


class TestEquipmentInlineEdit:
    def test_edit_button_shown(self, client):
        services.create_equipment(unit_number="EQ-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Edit</button>" in html

    def test_delete_button_shown(self, client):
        services.create_equipment(unit_number="EQ-002")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Delete</button>" in html

    def test_edit_row_present_hidden(self, client):
        eqp = services.create_equipment(unit_number="EQ-003")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert f"edit-equip-{eqp['equipment_id']}" in html

    def test_edit_form_has_vin_field(self, client):
        services.create_equipment(unit_number="EQ-004", vin="1HGBH41JXMN109186")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "1HGBH41JXMN109186" in html
        assert 'name="vin"' in html

    def test_edit_form_has_plate_field(self, client):
        services.create_equipment(unit_number="EQ-005", license_plate="ABC-123")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "ABC-123" in html
        assert 'name="license_plate"' in html

    def test_edit_form_has_make_model(self, client):
        services.create_equipment(unit_number="EQ-006", make="Freightliner", model="Cascadia")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "Freightliner" in html
        assert "Cascadia" in html

    def test_edit_form_has_year_field(self, client):
        services.create_equipment(unit_number="EQ-007", year="2024")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "2024" in html
        assert 'name="year"' in html

    def test_patch_equipment_via_api(self, client):
        eqp = services.create_equipment(unit_number="EQ-008", vin="old")
        resp = client.patch(
            f"/api/dispatch/equipment/{eqp['equipment_id']}",
            json={"vin": "NEW-VIN"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["vin"] == "NEW-VIN"

    def test_delete_equipment_via_api(self, client):
        eqp = services.create_equipment(unit_number="EQ-009")
        resp = client.delete(f"/api/dispatch/equipment/{eqp['equipment_id']}")
        assert resp.status_code == 200


# ── JS function presence ─────────────────────────────────────────


class TestFleetJSFunctions:
    def test_toggle_driver_edit_function(self, client):
        services.create_driver(name="JS Test")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "toggleDriverEdit" in html

    def test_save_driver_edit_function(self, client):
        services.create_driver(name="JS Test")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "saveDriverEdit" in html

    def test_delete_driver_function(self, client):
        services.create_driver(name="JS Test")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "deleteDriver" in html

    def test_toggle_equipment_edit_function(self, client):
        services.create_equipment(unit_number="JS-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "toggleEquipmentEdit" in html

    def test_save_equipment_edit_function(self, client):
        services.create_equipment(unit_number="JS-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "saveEquipmentEdit" in html

    def test_delete_equipment_function(self, client):
        services.create_equipment(unit_number="JS-001")
        resp = client.get("/fleet")
        html = resp.data.decode()
        assert "deleteEquipment" in html
