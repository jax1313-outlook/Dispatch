"""Tests for Driver Portal Driver-First Cockpit (Missions 1-4):
  - Mission 1: Dual-Layer Cockpit (Current Mission + Rolling 7-Day Horizon)
  - Mission 2: 1-Tap Milestone Controls, Native Dialers & Map Navigation
  - Mission 3: Camera POD / Evidence Capture & 1-Tap Dock Detention Timers
  - Mission 4: Vision Fuel Intake Scan & Driver Pay Settlement Glance
"""

from __future__ import annotations

import io
import pytest

from dispatch import services
from dispatch.db import set_db_path
from portal.models import driver_pin_registry as pin_registry


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def driver():
    d = services.create_driver(name="Cockpit Driver", phone="904-555-0999")
    pin_registry.create_pin_card(d["driver_id"], "1234", "anchor", "mike")
    return d


def _login(client, driver):
    client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"})


class TestDriverPortalMission1And2:
    def test_cockpit_renders_active_card_and_tel_links(self, client, driver):
        services.add_broker_contact(
            company_name="Fast Freight", contact_name="Fred Fast", phone="555-888-9999",
        )
        load = services.create_load(
            customer="Cockpit Co",
            broker_shipper="Fast Freight",
            pickup_location="Jacksonville, FL",
            delivery_location="Savannah, GA",
            driver_id=driver["driver_id"],
        )
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")

        assert resp.status_code == 200
        assert "Active Mission" in html
        assert "Jacksonville, FL" in html
        assert "Savannah, GA" in html
        assert "tel:555-888-9999" in html
        assert "LAUNCH MAP" in html

    def test_one_tap_milestone_progression(self, client, driver):
        load = services.create_load(customer="Milestone Step Co", driver_id=driver["driver_id"])
        services.add_milestone(load["load_id"], event_type="dispatched")

        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "en_route_pickup"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        updated = services.get_load(load["load_id"])
        assert updated["status"] == "en_route_pickup"


class TestDriverPortalMission3:
    def test_upload_pod_attaches_evidence(self, client, driver, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = services.create_load(customer="POD Test Co", driver_id=driver["driver_id"])

        _login(client, driver)
        file_data = (io.BytesIO(b"fake pod photo bytes"), "signed_pod.jpg")
        resp = client.post(
            f"/driver/loads/{load['load_id']}/pod",
            data={"pod_file": file_data},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        evidence_list = services.list_evidence(load["load_id"])
        assert len(evidence_list) == 1
        assert evidence_list[0]["evidence_type"] == "pod"
        assert "signed_pod.jpg" in evidence_list[0]["original_filename"]

    def test_log_exception_opens_exception(self, client, driver):
        load = services.create_load(customer="Exception Test Co", driver_id=driver["driver_id"])

        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/exception",
            data={"exception_type": "detention", "description": "2 hour dock delay"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        exceptions = services.list_exceptions(load_id=load["load_id"])
        assert len(exceptions) == 1
        assert exceptions[0]["exception_type"] == "detention"
        assert "2 hour dock delay" in exceptions[0]["description"]


class TestDriverPortalMission4:
    def test_fuel_receipt_logging(self, client, driver):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"gallons": "120.5", "amount": "450.00", "state": "GA"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        purchases = services.list_ifta_fuel_purchases()
        assert len(purchases) == 1
        assert purchases[0]["gallons"] == 120.5
        assert purchases[0]["amount"] == 450.00
        assert purchases[0]["jurisdiction"] == "GA"

    def test_driver_settlement_glance_renders(self, client, driver):
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Driver Settlement Glance" in html
        assert "Truck Stop &amp; Fuel Scanner" in html or "Truck Stop & Fuel Scanner" in html
