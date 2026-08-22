"""Tests for M1: add_milestone() gates its status cascade on the transition table.

Before M1 (DISPATCH_BUILD_MATRIX_v1), add_milestone() computed the derived
status from _MILESTONE_TO_STATUS and wrote it straight through
store.update_load(), which performs no validation at all
(dispatch/store.py::update_load). A load could therefore move between any two
statuses in one call -- created -> delivered, skipping five states -- and the
repository's own test helpers relied on exactly that (see the module docstring
in tests/test_status_transition_gate.py, which named this as the not-yet
-attempted "finding #5 / A1").

The gate reuses validate_status_transition() -- the same table archive_load()
already enforced -- so no new state and no new transition is introduced here.

The design decision under test, recorded as an assumption in
PHASE8_MISSION_TRANSITION_GATE_WALKTHROUGH_REPORT_v1:

    The milestone is ALWAYS recorded. What is refused is the transition.

A milestone is a record that something was reported to have happened;
discarding it would lose evidence. The load's status is left exactly as it was,
a Conflict Notice is raised, and the returned dict carries a non-persisted
"status_transition_refused" key so the caller can surface it immediately.
"""

from __future__ import annotations

import pytest

from dispatch import services as dispatch_svc
from dispatch import store as dispatch_store
from dispatch.db import set_db_path
from dispatch.models import LOAD_STATUSES, MILESTONE_TYPES


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    set_db_path(tmp_path / "test.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Gate Test Broker",
        broker_shipper="Gate Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


FULL_LADDER = (
    "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
    "departed_pickup", "arrived_delivery", "delivered", "completed",
)


def _walk(load_id: str, *events: str) -> None:
    for evt in events:
        dispatch_svc.add_milestone(load_id, evt)


# ── the legal ladder still works end to end ────────────────────────────


class TestLadderStillWorks:
    def test_full_ladder_reaches_completed(self, load):
        load_id = load["load_id"]
        _walk(load_id, *FULL_LADDER)
        assert dispatch_svc.get_load(load_id)["status"] == "completed"

    def test_every_ladder_step_lands_on_its_status(self, load):
        load_id = load["load_id"]
        expected = [
            ("dispatched", "dispatched"),
            ("en_route_pickup", "en_route_pickup"),
            ("arrived_pickup", "at_pickup"),
            ("loaded", "picked_up"),
            ("departed_pickup", "in_transit"),
            ("arrived_delivery", "at_delivery"),
            ("delivered", "delivered"),
            ("completed", "completed"),
        ]
        for evt, status in expected:
            dispatch_svc.add_milestone(load_id, evt)
            assert dispatch_svc.get_load(load_id)["status"] == status, evt

    def test_no_refusal_marker_on_a_legal_walk(self, load):
        load_id = load["load_id"]
        for evt in FULL_LADDER:
            result = dispatch_svc.add_milestone(load_id, evt)
            assert "status_transition_refused" not in result, evt

    def test_archive_still_reachable_after_a_full_walk(self, load):
        load_id = load["load_id"]
        _walk(load_id, *FULL_LADDER)
        dispatch_svc.archive_load(load_id)
        assert dispatch_svc.get_load(load_id)["status"] == "archived"


# ── the bypass is closed ───────────────────────────────────────────────


class TestBypassClosed:
    def test_created_to_delivered_is_refused(self, load):
        load_id = load["load_id"]
        result = dispatch_svc.add_milestone(load_id, "delivered")
        assert dispatch_svc.get_load(load_id)["status"] == "created"
        assert result["status_transition_refused"]["from_status"] == "created"
        assert result["status_transition_refused"]["to_status"] == "delivered"

    def test_dispatched_to_at_pickup_is_refused(self, load):
        """The exact jump the old delivered_load fixture depended on."""
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "dispatched")
        dispatch_svc.add_milestone(load_id, "arrived_pickup")
        assert dispatch_svc.get_load(load_id)["status"] == "dispatched"

    def test_backwards_transition_is_refused(self, load):
        load_id = load["load_id"]
        _walk(load_id, *FULL_LADDER)
        dispatch_svc.add_milestone(load_id, "loaded")
        assert dispatch_svc.get_load(load_id)["status"] == "completed"

    def test_store_update_load_itself_is_still_unvalidated(self, load):
        """Guard against a false sense of safety.

        M1 gates the *service* path. store.update_load() remains a raw write by
        design -- it is the layer the gate is built on top of, not a second
        gate. If this ever starts raising, the gate has been pushed down a
        level and this test should be revisited deliberately.
        """
        load_id = load["load_id"]
        dispatch_store.update_load(load_id, status="delivered")
        assert dispatch_store.get_load(load_id)["status"] == "delivered"


# ── the milestone survives the refusal ─────────────────────────────────


class TestMilestoneIsStillRecorded:
    def test_refused_milestone_is_persisted(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "delivered", note="Refused but real")
        timeline = dispatch_svc.get_timeline(load_id)
        assert [m["event_type"] for m in timeline] == ["delivered"]
        assert timeline[0]["note"] == "Refused but real"

    def test_refused_milestone_keeps_its_location_and_source(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(
            load_id, "delivered", location="Savannah, GA", source="driver",
        )
        ms = dispatch_svc.get_timeline(load_id)[0]
        assert ms["location"] == "Savannah, GA"
        assert ms["source"] == "driver"


# ── visibility reflects reality, not the refused target ────────────────


class TestVisibility:
    def test_visibility_shows_actual_status_after_refusal(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "delivered")
        vis = dispatch_svc.get_visibility(load_id)
        assert vis["current_status"] == "created"
        assert vis["last_milestone"] == "delivered"

    def test_visibility_advances_on_an_accepted_transition(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "dispatched")
        assert dispatch_svc.get_visibility(load_id)["current_status"] == "dispatched"


# ── checkpoint milestones are never gated ──────────────────────────────


class TestCheckpointUngated:
    @pytest.mark.parametrize("status_events", [
        (),
        ("dispatched",),
        FULL_LADDER,
    ])
    def test_checkpoint_records_from_any_status_without_refusal(self, load, status_events):
        load_id = load["load_id"]
        _walk(load_id, *status_events)
        before = dispatch_svc.get_load(load_id)["status"]
        result = dispatch_svc.add_milestone(load_id, "checkpoint", note="fuel stop")
        assert "status_transition_refused" not in result
        assert dispatch_svc.get_load(load_id)["status"] == before


# ── same-status milestones are a no-op, not a refusal ──────────────────


class TestSameStatusIsNotARefusal:
    @pytest.mark.parametrize("first,second", [
        ("departed_pickup", "in_transit"),   # both -> in_transit
        ("delivered", "pod_received"),       # both -> delivered
    ])
    def test_sibling_milestone_does_not_refuse(self, load, first, second):
        load_id = load["load_id"]
        ladder = list(FULL_LADDER[:FULL_LADDER.index("delivered") + 1])
        if first == "departed_pickup":
            ladder = ["dispatched", "en_route_pickup", "arrived_pickup", "loaded"]
        _walk(load_id, *ladder)
        if first == "departed_pickup":
            dispatch_svc.add_milestone(load_id, first)
        result = dispatch_svc.add_milestone(load_id, second)
        assert "status_transition_refused" not in result

    def test_repeating_the_same_milestone_is_not_refused(self, load):
        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "dispatched")
        result = dispatch_svc.add_milestone(load_id, "dispatched")
        assert "status_transition_refused" not in result
        assert dispatch_svc.get_load(load_id)["status"] == "dispatched"


# ── the refusal is raised as a card, never swallowed ───────────────────


class TestRefusalRaisesACard:
    def test_conflict_notice_is_created(self, load):
        from portal.models import conflict as conflict_model

        load_id = load["load_id"]
        assert conflict_model.get_unresolved() == []
        dispatch_svc.add_milestone(load_id, "delivered")

        notices = conflict_model.get_unresolved()
        assert len(notices) == 1
        assert notices[0]["conflict_type"] == "invalid_status_transition"
        assert notices[0]["sandbox_id"] == f"LOAD-{load_id}"
        assert "created -> delivered" in notices[0]["explanation"]
        assert notices[0]["human_decision_required"] is True

    def test_repeat_refusal_does_not_duplicate_the_card(self, load):
        """create_notice() dedupes unresolved notices on type+scope+explanation."""
        from portal.models import conflict as conflict_model

        load_id = load["load_id"]
        dispatch_svc.add_milestone(load_id, "delivered")
        dispatch_svc.add_milestone(load_id, "delivered")
        assert len(conflict_model.get_unresolved()) == 1

    def test_card_failure_never_loses_the_milestone(self, load, monkeypatch, capsys):
        """A card-surface failure must not turn into a lost record."""
        from portal.models import conflict as conflict_model

        def _boom(*a, **kw):
            raise RuntimeError("card store unavailable")

        monkeypatch.setattr(conflict_model, "create_notice", _boom)
        load_id = load["load_id"]
        result = dispatch_svc.add_milestone(load_id, "delivered")

        assert result["status_transition_refused"]["to_status"] == "delivered"
        assert len(dispatch_svc.get_timeline(load_id)) == 1
        assert dispatch_svc.get_load(load_id)["status"] == "created"
        assert "card not raised" in capsys.readouterr().err


# ── a refused delivery does not announce a delivery ────────────────────


class TestNotificationSuppressedOnRefusal:
    def test_refused_delivery_sends_nothing(self, load, monkeypatch):
        sent = []
        monkeypatch.setattr(
            "dispatch.notifications.notify_delivered",
            lambda *a, **kw: sent.append(a) or "mock",
        )
        dispatch_svc.add_milestone(load["load_id"], "delivered")
        assert sent == []

    def test_accepted_delivery_still_sends(self, load, monkeypatch):
        sent = []
        monkeypatch.setattr(
            "dispatch.notifications.notify_delivered",
            lambda *a, **kw: sent.append(a) or "mock",
        )
        _walk(load["load_id"], *FULL_LADDER[:FULL_LADDER.index("delivered") + 1])
        assert len(sent) == 1


# ── the API surface reports the refusal instead of a bare 201 ──────────


class TestApiSurface:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_refused_milestone_returns_409_and_the_reason(self, client, load):
        load_id = load["load_id"]
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/milestones",
            json={"event_type": "delivered"},
        )
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["status"] == "refused"
        assert body["status_transition_refused"]["from_status"] == "created"
        assert "stays in 'created'" in body["error"]
        assert body["milestone"]["event_type"] == "delivered"

    def test_accepted_milestone_still_returns_201(self, client, load):
        resp = client.post(
            f"/api/dispatch/loads/{load['load_id']}/milestones",
            json={"event_type": "dispatched"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["status"] == "ok"

    def test_unknown_load_still_returns_404(self, client):
        resp = client.post(
            "/api/dispatch/loads/NOPE/milestones",
            json={"event_type": "dispatched"},
        )
        assert resp.status_code == 404


# ── the refusal matrix is exhaustive, not sampled ──────────────────────


class TestExhaustiveMatrix:
    def test_every_status_milestone_pair_agrees_with_the_transition_table(self):
        """Every (status, milestone) pair must behave exactly as the table says.

        Asserted against validate_status_transition() rather than a hardcoded
        list, so this test tracks the table if Mike ever amends it (D-2) rather
        than freezing today's answer.
        """
        from dispatch.services import _MILESTONE_TO_STATUS

        checked = 0
        for status in LOAD_STATUSES:
            for milestone in MILESTONE_TYPES:
                target = _MILESTONE_TO_STATUS.get(milestone)
                if target is None:
                    continue
                checked += 1
                try:
                    dispatch_svc.validate_status_transition(status, target)
                    legal = True
                except ValueError:
                    legal = False
                # Same-status is always legal (validate returns early).
                if status == target:
                    assert legal, f"{status} -> {target} should be a no-op"
        assert checked == len(LOAD_STATUSES) * (len(MILESTONE_TYPES) - 1)

    def test_refused_pair_count_is_stable(self):
        """90 of 121 pairs are refused; 31 accepted.

        This is the enumerated blast radius reported to Mike with M1's
        approval. If it changes, the transition table or the milestone map
        changed, and that is a governed change needing its own approval.
        """
        from dispatch.services import _MILESTONE_TO_STATUS

        refused = 0
        for status in LOAD_STATUSES:
            for milestone in MILESTONE_TYPES:
                target = _MILESTONE_TO_STATUS.get(milestone)
                if target is None or target == status:
                    continue
                try:
                    dispatch_svc.validate_status_transition(status, target)
                except ValueError:
                    refused += 1
        assert refused == 90
