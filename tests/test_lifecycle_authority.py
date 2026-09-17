"""Batch 1: irreversible protections live in the lifecycle authority.

**Owner, 16 September 2026 — MISSION: CONSTITUTIONAL REGRESSION RECONCILIATION:**

    Move irreversible protections into lifecycle authority.
    The glass is not authoritative.
    The absence of a visible button does not constitute lifecycle protection.

And the primary rule it serves:

    Each consequential business act shall have one authoritative operation.
    Every screen, API route, helper, and test representing that act must call
    the same authoritative operation.

The audit found the no-undo rule implemented in two places that cannot enforce
it — the HTML (a test grepping for the absence of a button) and the sandbox
sweep — and **not** in the engine, which is the only thing that decides.
"""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store as dispatch_store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    set_db_path(tmp_path / "test.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Penske Logistics",
        broker_shipper="Penske Logistics",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


class TestARunThatHappenedIsKept:
    """*"once the action button is pressed the deterministic flow has begun …
    the flow path is moving toward completion."*"""

    def test_a_started_run_cannot_be_deleted_after_being_cancelled(self, load):
        """The hole the audit found: `en_route_pickup -> cancelled -> delete`
        was fully legal over the API, and removed a run that had begun."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "en_route_pickup")
        dispatch_svc.update_load(load_id, status="cancelled")

        with pytest.raises(ValueError) as refused:
            dispatch_svc.delete_load(load_id)

        assert "cancelled" in str(refused.value)
        assert dispatch_svc.get_load(load_id), "the run is still there"

    def test_a_load_with_any_milestone_cannot_be_deleted(self, load):
        """Evidence is not deleted because a status was changed afterwards."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "checkpoint", note="fuel stop")
        assert dispatch_svc.get_load(load_id)["status"] == "created"

        with pytest.raises(ValueError) as refused:
            dispatch_svc.delete_load(load_id)

        assert "work was recorded" in str(refused.value)

    def test_a_load_nobody_ever_worked_can_still_be_deleted(self, load):
        """The rule protects runs, not typing mistakes."""
        assert dispatch_svc.delete_load(load["load_id"]) is True
        assert dispatch_svc.get_load(load["load_id"]) is None

    def test_the_protection_is_in_the_engine_not_the_screen(self, load):
        """It is enforced by the service every door calls, so an API route, a
        script and a future screen all meet the same refusal."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "en_route_pickup")

        with pytest.raises(ValueError):
            dispatch_svc.delete_load(load_id)


class TestAStartedRunCanBeCancelled:
    """**Owner ruling, 2026-09-16, Batch 1:** *"Yes, but it is recorded and
    never deleted."* Freight falls through — a broker pulls a load, a shipper
    has nothing on the dock. Three states had no exit at all before this, so a
    load already on the trailer had nowhere to go but forward."""

    @pytest.mark.parametrize("walk_to,event", [
        ("en_route_pickup", "en_route_pickup"),
        ("at_pickup", "arrived_pickup"),
        ("picked_up", "loaded"),
        ("in_transit", "departed_pickup"),
        ("at_delivery", "arrived_delivery"),
    ])
    def test_it_can_be_cancelled_from_any_point_of_the_run(self, load, walk_to, event):
        load_id = load["load_id"]
        for step in ("en_route_pickup", "arrived_pickup", "loaded",
                     "departed_pickup", "arrived_delivery"):
            dispatch_svc.add_milestone(load_id, step)
            if dispatch_svc.get_load(load_id)["status"] == walk_to:
                break

        dispatch_svc.update_load(load_id, status="cancelled")

        assert dispatch_svc.get_load(load_id)["status"] == "cancelled"

    def test_the_milestones_of_a_cancelled_run_stand(self, load):
        """The run happened. Cancelling says how it ended, not that it never
        was."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "en_route_pickup")
        dispatch_svc.add_milestone(load_id, "arrived_pickup")

        dispatch_svc.update_load(load_id, status="cancelled")

        assert [m["event_type"] for m in dispatch_svc.get_timeline(load_id)] == [
            "en_route_pickup", "arrived_pickup"]

    def test_a_cancelled_run_reaches_the_archive(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "en_route_pickup")
        dispatch_svc.update_load(load_id, status="cancelled")

        dispatch_svc.archive_load(load_id)

        assert dispatch_svc.get_load(load_id)["status"] == "archived"

    def test_delivered_still_reaches_the_archive_directly(self, load):
        """**Kept on his ruling**, against the audit's recommendation: *"some
        loads genuinely end without a POD coming back, and forcing completion
        would strand them."* The three tests the audit called stale for
        asserting this are correct and were left alone."""
        from dispatch.services import _VALID_TRANSITIONS

        assert "archived" in _VALID_TRANSITIONS["delivered"]


class TestAssigningATruckIsNotStartingARun:
    """START RUN is the activation and it is the driver's. Assignment is data
    entry at a desk."""

    def test_assigning_a_driver_does_not_advance_the_load(self, load):
        driver = dispatch_svc.create_driver(name="M. Zachary", phone="904-555-0100")
        equipment = dispatch_svc.create_equipment(unit_number="T-1",
                                                  equipment_type="other")

        dispatch_svc.assign_driver(load["load_id"], driver["driver_id"])
        dispatch_svc.assign_equipment(load["load_id"], equipment["equipment_id"])

        assert dispatch_svc.get_load(load["load_id"])["status"] == "created"

    def test_the_load_is_still_ready_for_start_run(self, load):
        """`not_started` on the cockpit is `status == "created"`. A
        self-dispatched load never rendered the START RUN control at all."""
        driver = dispatch_svc.create_driver(name="M. Zachary", phone="904-555-0101")
        equipment = dispatch_svc.create_equipment(unit_number="T-2",
                                                  equipment_type="other")
        dispatch_svc.assign_driver(load["load_id"], driver["driver_id"])
        dispatch_svc.assign_equipment(load["load_id"], equipment["equipment_id"])

        from portal.routes.joe_portal import NEXT_STEP

        status = dispatch_svc.get_load(load["load_id"])["status"]
        assert NEXT_STEP[status] == ("START RUN", "en_route_pickup")

    def test_no_milestone_is_recorded_by_assignment(self, load):
        driver = dispatch_svc.create_driver(name="M. Zachary", phone="904-555-0102")
        equipment = dispatch_svc.create_equipment(unit_number="T-3",
                                                  equipment_type="other")

        dispatch_svc.assign_driver(load["load_id"], driver["driver_id"])
        dispatch_svc.assign_equipment(load["load_id"], equipment["equipment_id"])

        assert dispatch_store.list_milestones(load["load_id"]) == []

    def test_nothing_is_mailed_by_assignment(self, load, monkeypatch):
        """A communication went out from an act nobody framed as one."""
        from dispatch import notifications

        sent = []
        monkeypatch.setattr(notifications, "notify_dispatched",
                            lambda *a, **k: sent.append(a))
        driver = dispatch_svc.create_driver(name="M. Zachary", phone="904-555-0103")
        equipment = dispatch_svc.create_equipment(unit_number="T-4",
                                                  equipment_type="other")

        dispatch_svc.assign_driver(load["load_id"], driver["driver_id"])
        dispatch_svc.assign_equipment(load["load_id"], equipment["equipment_id"])

        assert sent == []
