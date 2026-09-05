"""Workstream B: Opportunity advises, Spine owns the lifecycle.

CF-04, adjudicated 2026-08-23. Opportunity kept every analytical thing it did
-- discovery, scoring, capacity consumption, deadhead, fuel, projected profit,
filtering, ranking, recommendation -- and lost the one thing it should never
have had: a lifecycle of its own.
"""

from __future__ import annotations

import pytest

from dispatch import opportunities as opp_module
from dispatch.capacity import DynamicCapacity
from dispatch.db import set_db_path
from dispatch.opportunities import LifecycleAuthorityError, OpportunityPipeline
from dispatch.spine.commitment import CommitmentNotAuthorized
from dispatch.spine.store import list_approval_events, list_events, get_work_item


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "opp.db")
    yield
    set_db_path(None)


@pytest.fixture()
def pipeline():
    return OpportunityPipeline()


RAW = {
    "source": "intelligence",
    "origin_location": "Jacksonville, FL",
    "destination_location": "Atlanta, GA",
    "offered_rate": 2400.0,
    "estimated_miles": 350.0,
    "equipment_type": "dry_van",
    "weight_lbs": 20000.0,
}


def _scored(pipeline, raw=None):
    card = pipeline.ingest_opportunities([raw or RAW])[0]
    pipeline.analyze_opportunity(card.opportunity_id)
    pipeline.score_opportunity(card.opportunity_id)
    return card


class TestOpportunityHasNoLifecycleOfItsOwn:
    def test_the_second_state_list_is_gone(self):
        assert not hasattr(opp_module, "OPPORTUNITY_LIFECYCLE_STAGES")

    def test_the_second_transition_table_is_gone(self):
        assert not hasattr(opp_module, "ALLOWED_LIFECYCLE_TRANSITIONS")

    def test_the_card_cannot_transition_itself(self):
        from dispatch.opportunities import OpportunityCard
        assert not hasattr(OpportunityCard, "transition_to")

    def test_stage_is_read_from_spine_not_stored(self, pipeline):
        """A stored copy would be a second source of truth to keep in sync --
        the same defect C1 exists to remove from the sandbox."""
        from dataclasses import fields
        from dispatch.opportunities import OpportunityCard
        assert "stage" not in {f.name for f in fields(OpportunityCard)}
        card = pipeline.ingest_opportunities([RAW])[0]
        assert card.stage == get_work_item(card.work_item_id)["current_state"]

    def test_an_uncorrelated_card_reports_no_lifecycle_position(self):
        """Not a default, not "Discovered" -- the honest answer."""
        from dispatch.opportunities import OpportunityCard
        assert OpportunityCard().stage == "UNCORRELATED"

    def test_an_uncorrelated_card_cannot_request_a_transition(self):
        from dispatch.opportunities import OpportunityCard
        with pytest.raises(LifecycleAuthorityError):
            OpportunityCard().request_transition("validated", actor_id="mike")


class TestSpineOwnsTheTransitions:
    def test_intake_correlates_to_a_spine_work_item(self, pipeline):
        card = pipeline.ingest_opportunities([RAW])[0]
        item = get_work_item(card.work_item_id)
        assert item is not None
        assert item["source_type"] == "opportunity"
        assert item["source_id"] == card.opportunity_id
        assert item["current_state"] == "CREATED"

    def test_analysis_requests_a_transition_rather_than_making_one(self, pipeline):
        card = pipeline.ingest_opportunities([RAW])[0]
        pipeline.analyze_opportunity(card.opportunity_id)
        assert card.stage == "VALIDATED"
        # Spine recorded the movement as its own event, which is the audit
        # trail Opportunity used to have no way of producing.
        events = list_events(card.work_item_id)
        assert any(e["new_state"] == "VALIDATED" for e in events)

    def test_scoring_walks_the_spine_states(self, pipeline):
        card = _scored(pipeline)
        assert card.stage == "SCORED"
        states = [e["new_state"] for e in list_events(card.work_item_id)]
        assert "SCORING_PENDING" in states and "SCORED" in states

    def test_spine_refuses_an_illegal_transition(self, pipeline):
        """The refusal is Spine's, and Opportunity does not swallow it."""
        card = pipeline.ingest_opportunities([RAW])[0]
        with pytest.raises(ValueError):
            card.request_transition("approved", actor_id="mike")
        assert card.stage == "CREATED"

    def test_presentation_puts_the_card_in_front_of_a_human(self, pipeline):
        card = _scored(pipeline)
        pipeline.present()
        assert card.stage == "WAITING_FOR_MIKE"


class TestFilteredIsAQueryNotAState:
    def test_filtering_does_not_move_anything(self, pipeline):
        card = _scored(pipeline)
        before = card.stage
        pipeline.filter(min_score=0.0)
        pipeline.filter(min_score=95.0)
        assert card.stage == before

    def test_filtering_answers_differently_for_different_thresholds(self, pipeline):
        _scored(pipeline)
        assert pipeline.filter(min_score=0.0)
        assert pipeline.filter(min_score=101.0) == []

    def test_ranking_is_by_score_descending(self, pipeline):
        low = _scored(pipeline, {**RAW, "offered_rate": 400.0})
        high = _scored(pipeline, {**RAW, "offered_rate": 4000.0})
        ranked = pipeline.filter()
        assert ranked[0].opportunity_id == high.opportunity_id
        assert ranked[-1].opportunity_id == low.opportunity_id


class TestCalendarEventIsNotALifecycleState:
    def test_no_calendar_state_exists(self):
        assert "Calendar Event" not in opp_module.SPINE_STATE_FOR_STEP.values()
        assert "CALENDAR" not in " ".join(opp_module.SPINE_STATE_FOR_STEP.values())

    def test_nothing_here_creates_a_calendar_entry(self):
        """Outlook is the scheduling source of truth and stays outside. The
        assertion is about calls, not prose -- the module docstring says the
        word "Outlook" precisely because it explains why none of this exists."""
        import inspect
        code = "\n".join(
            line for line in inspect.getsource(opp_module).splitlines()
            if not line.strip().startswith("#")
        )
        for api in ("icalendar", "graph.microsoft", "exchangelib", "msal",
                    "create_event", "calendar_event"):
            assert api not in code.lower(), f"{api} reached the opportunity module"


class TestHumanAuthorityBeforeCommitment:
    def test_commitment_requires_an_explicit_actor(self, pipeline):
        card = _scored(pipeline)
        pipeline.present()
        with pytest.raises(LifecycleAuthorityError, match="explicit human actor"):
            pipeline.request_commitment(card.opportunity_id, "")

    def test_a_system_identity_cannot_approve(self, pipeline):
        card = _scored(pipeline)
        pipeline.present()
        for machine in ("SYSTEM", "AUTOMATION", "PUBLISHER", "intelligence"):
            with pytest.raises(LifecycleAuthorityError):
                pipeline.request_commitment(card.opportunity_id, machine)

    def test_approval_records_the_actor_action_and_states(self, pipeline):
        card = _scored(pipeline)
        pipeline.present()
        pipeline.request_commitment(card.opportunity_id, "mike")

        approvals = list_approval_events(card.work_item_id)
        assert len(approvals) == 1
        approval = approvals[0]
        assert approval["user_id"] == "mike"
        assert approval["action"] == "APPROVE_LOAD_PURSUIT"
        assert approval["new_state"] == "MIKE_APPROVED"
        assert approval["object_id"] == card.opportunity_id

    def test_refused_commitment_leaves_the_lifecycle_alone(self, pipeline):
        card = _scored(pipeline)
        pipeline.present()
        with pytest.raises(LifecycleAuthorityError):
            pipeline.request_commitment(card.opportunity_id, "SYSTEM")
        assert card.stage == "WAITING_FOR_MIKE"


class TestOpportunityCannotCreateCurrentReality:
    def test_the_direct_commit_path_is_gone(self, pipeline):
        assert not hasattr(pipeline, "commit_opportunity_to_reality")

    def test_realizing_without_an_approval_is_refused(self, pipeline):
        from dispatch import services
        card = _scored(pipeline)
        pipeline.present()
        before = len(services.list_loads())
        with pytest.raises(CommitmentNotAuthorized):
            pipeline.realize_commitment(card.opportunity_id, actor_id="mike")
        assert len(services.list_loads()) == before

    def test_realizing_after_approval_creates_the_load_through_spine(self, pipeline):
        from dispatch import services
        card = _scored(pipeline)
        pipeline.present()
        pipeline.request_commitment(card.opportunity_id, "mike")

        load = pipeline.realize_commitment(card.opportunity_id, actor_id="mike")
        assert load["pickup_location"] == "Jacksonville, FL"
        assert load["delivery_location"] == "Atlanta, GA"
        assert card.linked_load_id == load["load_id"]

    def test_the_rate_is_confirmed_against_the_approving_human(self, pipeline):
        from dispatch import services
        card = _scored(pipeline)
        pipeline.present()
        pipeline.request_commitment(card.opportunity_id, "mike")
        load = pipeline.realize_commitment(card.opportunity_id, actor_id="mike")

        rate = services.get_rate_confirmation(load["load_id"])
        assert rate is not None
        assert rate["confirmed_by"] == "mike"

    def test_a_candidate_is_distinguishable_from_a_committed_load(self, pipeline):
        """A11: Possible Future may never look like Current Reality."""
        card = _scored(pipeline)
        assert card.linked_load_id == ""
        pipeline.present()
        pipeline.request_commitment(card.opportunity_id, "mike")
        pipeline.realize_commitment(card.opportunity_id, actor_id="mike")
        assert card.linked_load_id


class TestAnalysisIsUnchanged:
    """The reason Opportunity remains its own subsystem."""

    def test_scoring_still_produces_a_score_and_reasons(self, pipeline):
        card = _scored(pipeline)
        assert 0.0 <= card.score <= 100.0
        assert card.score_reasons

    def test_rpm_is_still_computed(self, pipeline):
        card = pipeline.ingest_opportunities([RAW])[0]
        assert card.rpm == round(2400.0 / 350.0, 2)

    def test_capacity_consumption_is_still_computed(self, pipeline):
        capacity = DynamicCapacity()
        capacity.physical.max_weight_lbs = 40000.0
        card = pipeline.ingest_opportunities([RAW])[0]
        pipeline.analyze_opportunity(card.opportunity_id, capacity=capacity)
        assert card.weight_consumption_pct == 50.0

    def test_fuel_and_profit_are_still_estimated(self, pipeline):
        card = pipeline.ingest_opportunities([RAW])[0]
        pipeline.analyze_opportunity(card.opportunity_id)
        assert card.estimated_fuel_cost > 0
        assert card.estimated_net_profit != 0


class TestStructuralLock:
    """OPP-06. The rule has to be enforceable, or it is only a paragraph."""

    def test_only_spine_defines_a_lifecycle_transition_table(self):
        import pathlib
        offenders = []
        for path in pathlib.Path(".").rglob("*.py"):
            text = str(path)
            if "/spine/" in text or text.startswith("tests/") or "__pycache__" in text:
                continue
            if not text.startswith(("dispatch/", "portal/", "cin_lite/", "route_risk/")):
                continue
            source = path.read_text(encoding="utf-8")
            if "ALLOWED_LIFECYCLE_TRANSITIONS" in source or "OPPORTUNITY_LIFECYCLE_STAGES" in source:
                offenders.append(text)
        assert offenders == [], f"a competing lifecycle table reappeared in: {offenders}"

    def test_only_spine_writes_work_item_state(self):
        import pathlib
        offenders = []
        for path in pathlib.Path(".").rglob("*.py"):
            text = str(path)
            if "/spine/" in text or text.startswith("tests/") or "__pycache__" in text:
                continue
            if not text.startswith(("dispatch/", "portal/", "cin_lite/", "route_risk/")):
                continue
            if "current_state=" in path.read_text(encoding="utf-8").replace(
                "current_state=\"CREATED\"", ""
            ) and "UPDATE work_items" in path.read_text(encoding="utf-8"):
                offenders.append(text)
        assert offenders == [], f"work_items.current_state written outside Spine: {offenders}"

    def test_opportunity_does_not_import_a_load_creation_path(self):
        """Spine creates loads. Opportunity asks."""
        import inspect
        source = inspect.getsource(opp_module)
        assert "services.create_load" not in source
        assert "services.confirm_rate" not in source
