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


class TestDriverPortalMission4:
    def test_fuel_receipt_logging(self, client, driver, load):
        """Updated for the scoping repair: a fuel receipt is logged against a
        load this driver holds. Previously this posted with no load at all and
        passed, which is the defect -- see test_fuel_receipt_requires_a_load."""
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": load["load_id"], "gallons": "120.5",
                  "amount": "450.00", "state": "GA"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        purchases = services.list_ifta_fuel_purchases()
        assert len(purchases) == 1
        assert purchases[0]["gallons"] == 120.5
        assert purchases[0]["amount"] == 450.00
        assert purchases[0]["jurisdiction"] == "GA"
        # Provenance: the ledger row records who logged it and against what.
        assert f"driver:{driver['driver_id']}" in purchases[0]["notes"]
        assert f"load:{load['load_id']}" in purchases[0]["notes"]

    def test_driver_settlement_glance_renders(self, client, driver):
        _login(client, driver)
        resp = client.get("/driver/home")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Driver Settlement Glance" in html

    def test_fuel_scanner_hidden_without_an_active_load(self, client, driver):
        """The control writes into the IFTA ledger and the endpoint refuses an
        unscoped post, so it must not be offered when there is nothing to
        scope it to. A button that always fails is worse than no button."""
        _login(client, driver)
        html = client.get("/driver/home").data.decode("utf-8")
        assert "Fuel Scanner" not in html

    def test_fuel_scanner_shown_with_an_active_load(self, client, driver, load):
        _login(client, driver)
        html = client.get("/driver/home").data.decode("utf-8")
        assert "Fuel Scanner" in html
        assert f'name="load_id" value="{load["load_id"]}"' in html


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


class TestDriverFuelReceiptScoping:
    """D-3. The fuel scanner writes into the IFTA ledger -- a quarterly tax
    filing. On the recovery branch it was the one write endpoint with no
    ownership check of any kind."""

    def test_unscoped_post_is_refused_and_writes_nothing(self, client, driver):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"gallons": "120.5", "amount": "450.00", "state": "GA"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "logged against your current load" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_another_drivers_load_is_refused(self, client, driver, other_driver):
        """IDOR: naming a real load that belongs to someone else must fail the
        same way as naming no load at all."""
        theirs = services.create_load(
            customer="Not Yours", driver_id=other_driver["driver_id"]
        )
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": theirs["load_id"], "gallons": "50", "amount": "200", "state": "GA"},
            follow_redirects=True,
        )
        assert "logged against your current load" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    # --- D-4: a non-numeric field must not be a 500 ---
    def test_non_numeric_gallons_is_reported_not_a_crash(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": load["load_id"], "gallons": "eighty", "amount": "200", "state": "GA"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "must be numbers" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_negative_amount_is_refused(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": load["load_id"], "gallons": "10", "amount": "-5", "state": "GA"},
            follow_redirects=True,
        )
        assert "must be numbers" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_unknown_jurisdiction_is_refused(self, client, driver, load):
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": load["load_id"], "gallons": "10", "amount": "40", "state": "ZZ"},
            follow_redirects=True,
        )
        assert "not an IFTA jurisdiction" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []

    def test_missing_jurisdiction_does_not_default_to_florida(self, client, driver, load):
        """The original build fell back to "FL" whenever the scan could not read
        a state -- filing another state's fuel under Florida. An unknown must
        stay unknown, especially in a tax record."""
        _login(client, driver)
        resp = client.post(
            "/driver/fuel-receipt",
            data={"load_id": load["load_id"], "gallons": "10", "amount": "40"},
            follow_redirects=True,
        )
        assert "Enter it by hand" in resp.data.decode("utf-8")
        assert services.list_ifta_fuel_purchases() == []
