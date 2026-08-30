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


@pytest.fixture
def truck():
    """Truck identity -- required by the fuel-receipt ownership chain."""
    return services.create_equipment(unit_number="TRK-101", equipment_type="dry_van")


@pytest.fixture
def load(driver):
    """A load assigned to `driver` -- the scope every driver write endpoint
    now requires."""
    return services.create_load(customer="Cockpit Co", driver_id=driver["driver_id"])


@pytest.fixture
def other_driver():
    d = services.create_driver(name="Someone Else", phone="904-555-0111")
    pin_registry.create_pin_card(d["driver_id"], "4321", "anchor", "mike")
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


def _receipt(name: str = "receipt.jpg"):
    return (io.BytesIO(b"fake receipt image bytes"), name)


class TestDriverPortalMission4:
    def test_fuel_receipt_logging(self, client, driver, truck, load):
        """The full ownership chain, with a load present."""
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "load_id": load["load_id"],
                  "gallons": "120.5", "amount": "450.00", "state": "GA",
                  "fuel_file": _receipt()},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        purchases = services.list_ifta_fuel_purchases()
        assert len(purchases) == 1
        p = purchases[0]
        assert p["gallons"] == 120.5
        assert p["amount"] == 450.00
        assert p["jurisdiction"] == "GA"
        # The five links of the chain.
        assert f"driver:{driver['driver_id']}" in p["notes"]      # driver identity
        assert p["vehicle_id"] == truck["equipment_id"]            # truck identity
        assert p["date"]                                           # timestamp
        assert p["jurisdiction"] == "GA"                           # jurisdiction
        assert p["evidence_id"]                                    # receipt evidence
        # Load association, present because a load was named.
        assert f"load:{load['load_id']}" in p["notes"]

    def test_driver_settlement_glance_renders(self, client, driver):
        _login(client, driver)
        resp = client.get("/driver/home")
        assert resp.status_code == 200
        assert "Driver Settlement Glance" in resp.data.decode("utf-8")

    def test_fuel_scanner_offered_without_any_active_load(self, client, driver, truck):
        """Mike's ruling: association with an active load is preferred but not
        required. An owner/operator fuels between loads, so the control must be
        there when no mission is."""
        _login(client, driver)
        html = client.get("/driver/home").data.decode("utf-8")
        assert "Fuel Scanner" in html
        assert truck["equipment_id"] in html

    def test_fuel_scanner_closed_when_no_active_truck_exists(self, client, driver):
        """Truck identity is mandatory, so with no active fleet there is nothing
        the receipt could be scoped to."""
        _login(client, driver)
        html = client.get("/driver/home").data.decode("utf-8")
        assert "has to name one" in html


class TestDriverFuelReceiptOwnershipChain:
    """Mike's ruling, 2026-08-23: "Fuel receipt ownership shall remain scoped.
    Fuel receipts shall never be anonymous." Minimum chain: Driver Identity,
    Truck Identity, Timestamp, Jurisdiction, Receipt Evidence. Load association
    preferred but NOT required, and never fabricated."""

    def test_logged_without_a_load_and_no_load_is_invented(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "80",
                  "amount": "300", "state": "FL", "fuel_file": _receipt()},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        purchases = services.list_ifta_fuel_purchases()
        assert len(purchases) == 1
        p = purchases[0]
        # Fully owned...
        assert f"driver:{driver['driver_id']}" in p["notes"]
        assert p["vehicle_id"] == truck["equipment_id"]
        assert p["evidence_id"]
        # ...and no artificial load association was created.
        assert "load:" not in p["notes"]

    def test_receipt_without_a_load_is_still_auditable_and_reportable(self, client, driver, truck):
        """It must remain visible to IFTA reporting, not stranded."""
        _login(client, driver)
        client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "80",
                  "amount": "300", "state": "FL", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        p = services.list_ifta_fuel_purchases()[0]
        evidence_records = services.list_ifta_fuel_evidence(p["purchase_id"])
        assert len(evidence_records) == 1
        evidence = evidence_records[0]
        assert evidence["evidence_id"] == p["evidence_id"]
        assert evidence["checksum"]
        assert f"driver:{driver['driver_id']}" in evidence["uploaded_by"]
        assert any(q["purchase_id"] == p["purchase_id"]
                   for q in services.list_ifta_fuel_purchases(jurisdiction="FL"))

    # --- Truck identity ---
    def test_missing_truck_is_refused(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"gallons": "80", "amount": "300", "state": "FL", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "Which truck?" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_unknown_truck_is_refused(self, client, driver):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": "EQ-NOPE", "gallons": "80", "amount": "300",
                  "state": "FL", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "not on the active fleet" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_retired_truck_is_refused(self, client, driver, truck):
        services.retire_equipment(truck["equipment_id"])
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "80",
                  "amount": "300", "state": "FL", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "not on the active fleet" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    # --- Receipt evidence ---
    def test_missing_receipt_is_refused(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "80",
                  "amount": "300", "state": "FL"},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "never logged without one" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_rejected_receipt_type_leaves_nothing_behind(self, client, driver, truck):
        """The chain requires evidence, so a purchase must never survive a
        receipt that could not be stored."""
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "80",
                  "amount": "300", "state": "FL", "fuel_file": _receipt("receipt.exe")},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "File type not allowed" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    # --- Load association, when offered ---
    def test_another_drivers_load_is_refused(self, client, driver, other_driver, truck):
        theirs = services.create_load(customer="Not Yours", driver_id=other_driver["driver_id"])
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "load_id": theirs["load_id"],
                  "gallons": "50", "amount": "200", "state": "GA", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "not yours" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    # --- Numbers and jurisdiction ---
    def test_non_numeric_gallons_is_reported_not_a_crash(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "eighty",
                  "amount": "200", "state": "GA", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "must be numbers" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_negative_amount_is_refused(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "10",
                  "amount": "-5", "state": "GA", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "must be numbers" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_unknown_jurisdiction_is_refused(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "10",
                  "amount": "40", "state": "ZZ", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "not an IFTA jurisdiction" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_missing_jurisdiction_does_not_default_to_florida(self, client, driver, truck):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"equipment_id": truck["equipment_id"], "gallons": "10",
                  "amount": "40", "fuel_file": _receipt()},
            content_type="multipart/form-data", follow_redirects=True,
        )
        assert "Enter it by hand" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []


class TestDriverPortalNothingFailsQuietly:
    """The repairs. Each test here corresponds to a defect that shipped on the
    recovery branch, where the driver's tap produced a silent redirect that was
    indistinguishable from success."""

    # --- D-1: a refused transition must reach the driver ---
    def test_refused_transition_tells_the_driver(self, client, driver, load):
        """`created -> delivered` is not a legal step. add_milestone() does not
        raise for this -- it records the milestone, leaves the status alone and
        returns `status_transition_refused`. The original build discarded that
        return value, so the cab saw nothing."""
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "delivered"},
            follow_redirects=True,
        )
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "the load stays in created" in html
        assert "notice-warning" in html

    def test_refused_transition_does_not_move_the_load(self, client, driver, load):
        _login(client, driver)
        client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "delivered"},
            follow_redirects=True,
        )
        assert services.get_load(load["load_id"])["status"] == "created"

    def test_refused_transition_still_keeps_the_reported_milestone(self, client, driver, load):
        """The accepted ruling: a refused status transition may still retain the
        reported milestone evidence. The driver said it happened; that record
        stays even though the status did not move."""
        _login(client, driver)
        client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "delivered"},
            follow_redirects=True,
        )
        from dispatch import store
        events = [m["event_type"] for m in store.list_milestones(load["load_id"])]
        assert "delivered" in events

    def test_accepted_transition_confirms_to_the_driver(self, client, driver, load):
        _login(client, driver)
        services.add_milestone(load["load_id"], event_type="dispatched")
        resp = client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "en_route_pickup"},
            follow_redirects=True,
        )
        html = resp.data.decode("utf-8")
        assert "notice-success" in html
        assert "En Route Pickup recorded." in html

    def test_empty_milestone_selection_is_reported(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={}, follow_redirects=True,
        )
        assert "No milestone was selected." in resp.data.decode("utf-8")

    # --- D-5: a rejected file must reach the driver, not 500 ---
    def test_rejected_file_type_is_reported_not_a_crash(self, client, driver, load, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/pod",
            data={"pod_file": (io.BytesIO(b"not a photo"), "receipt.exe")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "File type not allowed" in html
        assert services.list_evidence(load["load_id"]) == []

    def test_missing_pod_file_is_reported(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/pod", data={}, follow_redirects=True
        )
        assert "No photo or file was attached." in resp.data.decode("utf-8")

    def test_successful_pod_confirms_to_the_driver(self, client, driver, load, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/pod",
            data={"pod_file": (io.BytesIO(b"photo bytes"), "pod.jpg")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert "POD uploaded." in resp.data.decode("utf-8")

    # --- D-2: an exception failure must not be swallowed ---
    def test_exception_failure_is_reported_not_swallowed(self, client, driver, load, monkeypatch):
        def _boom(*a, **k):
            raise ValueError("Exception store unavailable")
        monkeypatch.setattr(services, "open_exception", _boom)
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/exception",
            data={"exception_type": "detention", "description": "stuck at the dock"},
            follow_redirects=True,
        )
        assert "Exception store unavailable" in resp.data.decode("utf-8")

    def test_exception_success_confirms_to_the_driver(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            f"/driver/loads/{load['load_id']}/exception",
            data={"exception_type": "detention", "description": "stuck at the dock"},
            follow_redirects=True,
        )
        assert "Detention logged." in resp.data.decode("utf-8")
