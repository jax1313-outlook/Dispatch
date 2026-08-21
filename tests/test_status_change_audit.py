"""Tests for C3: status-change audit symmetry.

Before C3, four service paths could change a load's status and only one of them
wrote a `status_change` activity:

    services.update_load()      -- validated AND audited
    services.add_milestone()    -- validated (M1), NOT audited
    services._try_auto_dispatch() -- NOT audited
    services.archive_load()     -- NOT audited

The mission brief named the first two. The other two were found during C3's
required analysis and are covered here for the same reason: the required
outcome is "every accepted status change, regardless of approved entry path".

What C3 does NOT change, and what these tests hold in place:

  * the valid transition matrix
  * milestone-recording behavior
  * the M1 ruling that a refused transition still retains its milestone
  * store.update_load(), which stays the raw, unvalidated, unaudited write it
    was designed to be

The no-op divergence is deliberate and is asserted here rather than smoothed
over: update_load() has always written an event when previous == new, and C3
preserves that; the three paths C3 adds fire only on a real change. See
C3_STATUS_CHANGE_AUDIT_WALKTHROUGH_REPORT_v1.md.
"""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store as dispatch_store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Per-test SQLite file, and portal JSON stores redirected to tmp.

    The PORTAL_DATA_DIR redirect matters here: add_milestone() raises a
    Conflict Notice on a refused transition, and that notice is written to a
    portal JSON store. Without this, the refusal tests below would write into
    a live operational store. tests/conftest.py::tmp_archive already does this
    suite-wide; it is repeated explicitly so this module is correct on its own.
    """
    set_db_path(tmp_path / "test.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Audit Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


def status_events(load_id: str) -> list[dict]:
    return [
        a for a in dispatch_store.list_activities(load_id)
        if a["activity_type"] == "status_change"
    ]


def messages(load_id: str) -> list[str]:
    """Messages, unordered.

    store.list_activities() sorts ORDER BY created_at DESC, and created_at has
    second precision -- so several events written inside one second tie and
    their relative order is unspecified. Every assertion in this module is
    therefore membership-based, never positional. That ambiguity is
    pre-existing and out of C3's scope; it is recorded in the walkthrough
    report.
    """
    return [a["message"] for a in status_events(load_id)]


LADDER = (
    "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
    "departed_pickup", "arrived_delivery", "delivered", "completed",
)


def _walk(load_id: str, *events: str) -> None:
    for evt in events:
        dispatch_svc.add_milestone(load_id, evt)


# ── 1. update_load() produces exactly one correct audit event ──────────


class TestUpdateLoadPath:
    def test_one_event_per_change(self, load):
        dispatch_svc.update_load(load["load_id"], status="dispatched")
        events = status_events(load["load_id"])
        assert len(events) == 1

    def test_event_carries_previous_and_new_state(self, load):
        dispatch_svc.update_load(load["load_id"], status="dispatched")
        msg = messages(load["load_id"])[0]
        assert "created" in msg
        assert "dispatched" in msg

    def test_event_carries_the_originating_operation(self, load):
        dispatch_svc.update_load(load["load_id"], status="dispatched")
        assert "via load update" in messages(load["load_id"])[0]

    def test_event_carries_a_timestamp_in_repository_format(self, load):
        dispatch_svc.update_load(load["load_id"], status="dispatched")
        created_at = status_events(load["load_id"])[0]["created_at"]
        assert created_at.endswith("Z")
        assert len(created_at) == 20  # YYYY-MM-DDTHH:MM:SSZ

    def test_non_status_update_writes_no_status_event(self, load):
        dispatch_svc.update_load(load["load_id"], customer="Renamed Co")
        assert status_events(load["load_id"]) == []

    def test_actor_is_not_fabricated(self, load):
        """update_load() has no actor argument. It must not invent one."""
        dispatch_svc.update_load(load["load_id"], status="dispatched")
        event = status_events(load["load_id"])[0]
        assert event["author"] == ""
        assert event["source"] == "system"


# ── 2. add_milestone() produces one equivalent event ───────────────────


class TestMilestonePath:
    def test_one_event_when_status_changes(self, load):
        dispatch_svc.add_milestone(load["load_id"], "dispatched")
        assert len(status_events(load["load_id"])) == 1

    def test_event_carries_previous_and_new_state(self, load):
        dispatch_svc.add_milestone(load["load_id"], "dispatched")
        msg = messages(load["load_id"])[0]
        assert "created" in msg
        assert "dispatched" in msg

    def test_event_names_the_milestone_as_the_operation(self, load):
        dispatch_svc.add_milestone(load["load_id"], "dispatched")
        assert "milestone 'dispatched'" in messages(load["load_id"])[0]

    def test_actor_recorded_when_the_caller_supplies_one(self, load):
        dispatch_svc.add_milestone(
            load["load_id"], "dispatched", entered_by="Mike", source="driver",
        )
        event = status_events(load["load_id"])[0]
        assert event["author"] == "Mike"
        assert event["source"] == "user"
        assert "from driver" in event["message"]

    def test_actor_absent_is_recorded_as_absent_not_invented(self, load):
        dispatch_svc.add_milestone(load["load_id"], "dispatched")
        event = status_events(load["load_id"])[0]
        assert event["author"] == ""
        assert event["source"] == "system"

    def test_full_ladder_writes_one_event_per_transition(self, load):
        load_id = load["load_id"]
        _walk(load_id, *LADDER)
        assert len(status_events(load_id)) == len(LADDER)

    def test_ladder_events_chain_without_gaps(self, load):
        """Each event's new state is the next event's previous state."""
        load_id = load["load_id"]
        _walk(load_id, *LADDER)
        expected = [
            ("created", "dispatched"),
            ("dispatched", "en_route_pickup"),
            ("en_route_pickup", "at_pickup"),
            ("at_pickup", "picked_up"),
            ("picked_up", "in_transit"),
            ("in_transit", "at_delivery"),
            ("at_delivery", "delivered"),
            ("delivered", "completed"),
        ]
        msgs = messages(load_id)
        for prev, new in expected:
            matching = [m for m in msgs if f"from {prev} to {new}" in m]
            assert len(matching) == 1, f"{prev} -> {new}"


# ── the two paths the brief did not name ───────────────────────────────


class TestAutoDispatchPath:
    def test_auto_dispatch_is_audited(self, load):
        load_id = load["load_id"]
        driver = dispatch_svc.create_driver(name="Auto Driver")
        equip = dispatch_svc.create_equipment(unit_number="AUTO-1")
        dispatch_svc.assign_driver(load_id, driver["driver_id"])
        dispatch_svc.assign_equipment(load_id, equip["equipment_id"])

        assert dispatch_svc.get_load(load_id)["status"] == "dispatched"
        events = status_events(load_id)
        assert len(events) == 1
        assert "from created to dispatched" in events[0]["message"]
        assert "via auto-dispatch" in events[0]["message"]

    def test_assignment_without_both_writes_no_event(self, load):
        """No status change, so no audit event."""
        driver = dispatch_svc.create_driver(name="Lonely Driver")
        dispatch_svc.assign_driver(load["load_id"], driver["driver_id"])
        assert dispatch_svc.get_load(load["load_id"])["status"] == "created"
        assert status_events(load["load_id"]) == []


class TestArchivePath:
    def test_archive_is_audited(self, load):
        load_id = load["load_id"]
        _walk(load_id, *LADDER)
        before = len(status_events(load_id))

        dispatch_svc.archive_load(load_id)

        events = status_events(load_id)
        assert len(events) == before + 1
        archive_events = [
            m for m in messages(load_id) if "from completed to archived" in m
        ]
        assert len(archive_events) == 1
        assert "via archive" in archive_events[0]


# ── 3. refused transitions produce no accepted audit event ─────────────


class TestRefusalsAreNotAudited:
    def test_refused_milestone_writes_no_status_event(self, load):
        result = dispatch_svc.add_milestone(load["load_id"], "delivered")
        assert result["status_transition_refused"]["to_status"] == "delivered"
        assert status_events(load["load_id"]) == []

    def test_refused_milestone_leaves_status_untouched(self, load):
        dispatch_svc.add_milestone(load["load_id"], "delivered")
        assert dispatch_svc.get_load(load["load_id"])["status"] == "created"

    def test_refused_update_load_writes_no_status_event(self, load):
        with pytest.raises(ValueError, match="Invalid status transition"):
            dispatch_svc.update_load(load["load_id"], status="delivered")
        assert status_events(load["load_id"]) == []

    def test_refusal_after_real_changes_adds_nothing(self, load):
        load_id = load["load_id"]
        _walk(load_id, "dispatched", "en_route_pickup")
        before = len(status_events(load_id))
        dispatch_svc.add_milestone(load_id, "completed")  # refused
        assert len(status_events(load_id)) == before


# ── 4. retained milestone evidence must not imply the transition ───────


class TestRetainedEvidenceDoesNotImplyTransition:
    def test_milestone_is_retained_but_unaudited(self, load):
        """The M1 ruling and the C3 audit must not contradict each other.

        A refused transition still keeps its reported milestone -- that is
        evidence something was reported. The audit log must NOT contain a
        corresponding status_change, because the status did not change.
        """
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "delivered", note="Driver reported")

        timeline = dispatch_svc.get_timeline(load_id)
        assert [m["event_type"] for m in timeline] == ["delivered"]
        assert timeline[0]["note"] == "Driver reported"

        assert status_events(load_id) == []
        assert dispatch_svc.get_load(load_id)["status"] == "created"

    def test_audit_log_never_claims_a_state_the_load_did_not_reach(self, load):
        load_id = load["load_id"]
        _walk(load_id, "dispatched")
        dispatch_svc.add_milestone(load_id, "delivered")  # refused
        assert not any("to delivered" in m for m in messages(load_id))


# ── 5. repeats and no-ops do not create duplicate entries ──────────────


class TestNoDuplicates:
    def test_repeating_a_milestone_adds_no_second_event(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "dispatched")
        dispatch_svc.add_milestone(load_id, "dispatched")
        assert len(status_events(load_id)) == 1

    @pytest.mark.parametrize("first,second", [
        ("departed_pickup", "in_transit"),   # both -> in_transit
        ("delivered", "pod_received"),       # both -> delivered
    ])
    def test_sibling_milestone_on_same_status_adds_no_event(self, load, first, second):
        """Several milestone types map to a status the load already holds.

        Recording "changed from in_transit to in_transit" would be a false
        statement in the audit log on a routine, correct operation.
        """
        load_id = load["load_id"]
        upto = LADDER[:LADDER.index(first) + 1] if first in LADDER else ()
        _walk(load_id, *upto)
        before = len(status_events(load_id))
        dispatch_svc.add_milestone(load_id, second)
        assert len(status_events(load_id)) == before

    def test_archive_is_not_audited_twice(self, load):
        load_id = load["load_id"]
        _walk(load_id, *LADDER)
        dispatch_svc.archive_load(load_id)
        before = len(status_events(load_id))
        with pytest.raises(ValueError, match="already archived"):
            dispatch_svc.archive_load(load_id)
        assert len(status_events(load_id)) == before

    def test_no_path_chains_into_another(self, load):
        """A single status change must never produce two events.

        add_milestone(), _try_auto_dispatch() and archive_load() all write via
        store.update_load() (the raw layer), never via services.update_load(),
        so no path can audit twice for one change. If that ever changes, this
        test fails.
        """
        load_id = load["load_id"]
        for evt in LADDER:
            before = len(status_events(load_id))
            dispatch_svc.add_milestone(load_id, evt)
            assert len(status_events(load_id)) <= before + 1


class TestNoOpPolicyPreserved:
    """The one deliberate divergence, asserted rather than hidden.

    update_load() wrote an event for a no-op before C3 and still does. The
    three paths C3 added do not. Changing update_load() would alter existing
    repository policy, which C3 was not authorized to do -- it is reported in
    the walkthrough for Mike instead.

    If this test ever fails, the no-op policy changed and the walkthrough
    report's "unresolved issues" section needs updating with it.
    """

    def test_update_load_still_audits_a_no_op(self, load):
        load_id = load["load_id"]
        dispatch_svc.update_load(load_id, status="dispatched")
        dispatch_svc.update_load(load_id, status="dispatched")
        msgs = messages(load_id)
        assert len(msgs) == 2
        assert "from dispatched to dispatched" in msgs[1]

    def test_milestone_path_does_not_audit_a_no_op(self, load):
        load_id = load["load_id"]
        _walk(load_id, "dispatched", "en_route_pickup", "arrived_pickup",
              "loaded", "departed_pickup")
        before = len(status_events(load_id))
        dispatch_svc.add_milestone(load_id, "in_transit")  # already in_transit
        assert len(status_events(load_id)) == before


# ── boundaries C3 must not have crossed ────────────────────────────────


class TestBoundariesHeld:
    def test_store_update_load_is_still_raw_and_unaudited(self):
        """C3 deliberately did NOT push auditing down to the store layer.

        store.update_load() stays the raw write it was designed to be: no
        validation (asserted by test_milestone_transition_gate.py) and no
        audit. The service layer is the only place that knows which operation
        moved the status, which is why the helper lives there.
        """
        load = dispatch_svc.create_load(customer="Raw Write")
        load_id = load["load_id"]
        dispatch_store.update_load(load_id, status="delivered")
        assert dispatch_store.get_load(load_id)["status"] == "delivered"
        assert status_events(load_id) == []

    def test_transition_matrix_untouched(self):
        from dispatch.services import _VALID_TRANSITIONS

        assert _VALID_TRANSITIONS["created"] == {"dispatched", "cancelled"}
        assert _VALID_TRANSITIONS["delivered"] == {"completed", "archived"}
        assert _VALID_TRANSITIONS["archived"] == set()

    def test_milestone_recording_behavior_untouched(self, load):
        """Every milestone is still recorded, accepted or refused."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "delivered")      # refused
        dispatch_svc.add_milestone(load_id, "dispatched")     # accepted
        dispatch_svc.add_milestone(load_id, "checkpoint")     # ungated
        assert [m["event_type"] for m in dispatch_svc.get_timeline(load_id)] == [
            "delivered", "dispatched", "checkpoint",
        ]

    def test_checkpoint_never_produces_a_status_event(self, load):
        load_id = load["load_id"]
        _walk(load_id, "dispatched")
        before = len(status_events(load_id))
        dispatch_svc.add_milestone(load_id, "checkpoint", note="fuel stop")
        assert len(status_events(load_id)) == before
