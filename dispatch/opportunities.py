"""Opportunity discovery, analysis, scoring, filtering, presentation and
recommendation. Advisory throughout.

CF-04, adjudicated by Mike Zachary on 2026-08-23, verbatim: "Dispatch Spine
shall become the authoritative lifecycle engine and single source of lifecycle
truth... Opportunity recommends. Spine records reality. Opportunity may request
transitions. Spine owns transitions. Opportunity may not maintain a competing
lifecycle authority."

WHAT THIS MODULE USED TO DO, AND NO LONGER DOES. It carried its own nine-stage
state list, its own transition table, its own `transition_to()` guard, and a
stored `stage` it treated as authoritative. Analysis moved that stage as a side
effect -- scoring an opportunity advanced it -- and `commit_opportunity_to_reality()`
walked four stages in a row and then created the load and confirmed the rate
itself. That was a second lifecycle authority, and the ruling removed it.

WHAT REPLACED IT. Each opportunity is correlated to one Spine work item. Stage
is read through that correlation, never stored here. Analysis computes and then
*requests* a transition, which Spine validates against its own 25-state table
and either applies or refuses. Commitment is a request that a human answers at
Spine's WAITING_FOR_MIKE gate, and the load is created on the Spine side
(dispatch/spine/commitment.py) once that approval exists.

TWO OF THE OLD NINE STAGES WERE NEVER STATES.

  `Filtered` was a query over scores, not a position in a lifecycle. It is a
  filter argument now, which is what it always was.

  `Calendar Event` is an external side effect of an approval. Outlook is the
  scheduling source of truth and stays outside Dispatch; nothing here creates a
  calendar entry, and a request to do so is something a human authorises after
  the commitment, not a state the opportunity passes through.

The analysis this module exists for -- scoring, capacity consumption, deadhead,
fuel, projected profit, filtering, ranking, recommendation -- is unchanged and
is the reason Opportunity remains its own subsystem rather than being folded
into Spine.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from dispatch.capacity import DynamicCapacity
from dispatch.spine import commitment as spine_commitment
from dispatch.spine.models import ApprovalEvent, AuditEvent, WorkItem
from dispatch.spine.store import (
    apply_transition,
    create_approval_event,
    create_work_item,
    get_work_item,
)
from dispatch.truck_arrangement import TruckArrangement


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# The Spine states an opportunity actually passes through, and the analytical
# step that requests each one. This is a MAP INTO Spine's vocabulary, not a
# state machine of its own: nothing here validates a transition or decides
# whether one is allowed. dispatch/spine/state.py does that, and refusing is
# its job.
SPINE_STATE_FOR_STEP: dict[str, str] = {
    "discovered": "CREATED",
    "validating": "VALIDATION_PENDING",
    "validated": "VALIDATED",
    "scoring": "SCORING_PENDING",
    "scored": "SCORED",
    "presenting": "PORTAL_CARD_PENDING",
    "presented": "PORTAL_CARD_CREATED",
    "awaiting_decision": "WAITING_FOR_MIKE",
    "approved": "MIKE_APPROVED",
    "rejected": "MIKE_REJECTED",
}

# Reserved identities cannot stand in for a person. Same set, same reason, as
# portal/models/library.py: a machine may not approve on Mike's behalf, and
# nothing may default to his name.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}


class LifecycleAuthorityError(RuntimeError):
    """Raised when something asks Opportunity to do what only Spine may do."""


@dataclass
class OpportunityCard:
    opportunity_id: str = ""
    source: str = "intelligence"
    external_ref_id: str = ""
    origin_location: str = ""
    destination_location: str = ""
    pickup_window_start: str = ""
    pickup_window_end: str = ""
    delivery_window_start: str = ""
    delivery_window_end: str = ""
    offered_rate: float = 0.0
    estimated_miles: float = 0.0
    commodity: str = ""
    weight_lbs: float = 0.0
    volume_cuft: float = 0.0
    pallets: int = 0
    linear_feet: float = 0.0
    equipment_type: str = "dry_van"

    # Dynamic Capacity Consumption % Metrics
    weight_consumption_pct: float = 0.0
    volume_consumption_pct: float = 0.0
    pallet_consumption_pct: float = 0.0
    time_consumption_pct: float = 0.0

    # Analysis fields
    deadhead_miles: float = 0.0
    estimated_fuel_cost: float = 0.0
    estimated_hos_drive_hours: float = 0.0
    estimated_net_profit: float = 0.0

    # Score field (0 - 100)
    score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)

    # Correlation to the lifecycle, not a lifecycle of its own. `work_item_id`
    # is a key into Spine (BM-11: correlation, never identifier migration);
    # `linked_load_id` is filled in only once Spine has realised a commitment,
    # which is what keeps a candidate distinguishable from a committed load.
    work_item_id: str = ""
    linked_load_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.opportunity_id:
            self.opportunity_id = f"OPP-{uuid.uuid4().hex[:8].upper()}"
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def rpm(self) -> float:
        if self.estimated_miles > 0:
            return round(self.offered_rate / self.estimated_miles, 2)
        return 0.0

    @property
    def stage(self) -> str:
        """The lifecycle position, read from Spine.

        A property rather than a field on purpose: a stored copy is a second
        source of truth, and keeping one in sync is exactly the failure the
        C1 corrective mission exists to fix elsewhere in this codebase. If
        there is no correlated work item yet, the honest answer is that this
        opportunity has no lifecycle position -- not a default.
        """
        if not self.work_item_id:
            return "UNCORRELATED"
        item = get_work_item(self.work_item_id)
        return item["current_state"] if item else "UNCORRELATED"

    def request_transition(self, step: str, *, actor_id: str, actor_type: str = "opportunity_engine") -> dict:
        """Ask Spine to move this opportunity. Spine validates and may refuse.

        The refusal is Spine's to make and is deliberately not caught here --
        an analytical subsystem swallowing a lifecycle refusal is how a
        competing authority grows back.
        """
        if not self.work_item_id:
            raise LifecycleAuthorityError(
                "This opportunity is not correlated to a Spine work item, so no "
                "transition can be requested for it."
            )
        target = SPINE_STATE_FOR_STEP.get(step)
        if target is None:
            raise ValueError(f"Unknown opportunity step: {step!r}")
        return apply_transition(
            self.work_item_id,
            target,
            actor_type=actor_type,
            actor_id=actor_id,
            summary=f"Opportunity {self.opportunity_id}: {step}",
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rpm"] = self.rpm
        d["stage"] = self.stage
        return d


class OpportunityPipeline:
    """Intake and processing pipeline supporting high volume opportunity processing."""

    def __init__(self) -> None:
        self._opportunities: dict[str, OpportunityCard] = {}

    def ingest_opportunities(self, raw_opportunities: list[dict]) -> list[OpportunityCard]:
        """Ingest batch of raw opportunities from Intelligence intake (50, 100, 200+)."""
        ingested = []
        for raw in raw_opportunities:
            card = OpportunityCard(
                source=raw.get("source", "intelligence"),
                external_ref_id=raw.get("external_ref_id", ""),
                origin_location=raw.get("origin_location", ""),
                destination_location=raw.get("destination_location", ""),
                pickup_window_start=raw.get("pickup_window_start", ""),
                pickup_window_end=raw.get("pickup_window_end", ""),
                delivery_window_start=raw.get("delivery_window_start", ""),
                delivery_window_end=raw.get("delivery_window_end", ""),
                offered_rate=float(raw.get("offered_rate", 0.0)),
                estimated_miles=float(raw.get("estimated_miles", 0.0)),
                commodity=raw.get("commodity", ""),
                weight_lbs=float(raw.get("weight_lbs", 0.0)),
                volume_cuft=float(raw.get("volume_cuft", 0.0)),
                pallets=int(raw.get("pallets", 0)),
                linear_feet=float(raw.get("linear_feet", 0.0)),
                equipment_type=raw.get("equipment_type", "dry_van"),
            )
            # Correlate to Spine at intake. Everything downstream reads its
            # lifecycle position through this key rather than keeping one.
            work_item = create_work_item(
                WorkItem(
                    source_type="opportunity",
                    source_id=card.opportunity_id,
                    assigned_function="Opportunity",
                    required_action="Analyse, score and present for a human decision",
                    current_state="CREATED",
                )
            )
            card.work_item_id = work_item["work_item_id"]
            self._opportunities[card.opportunity_id] = card
            ingested.append(card)
        return ingested

    def analyze_opportunity(
        self,
        opportunity_id: str,
        capacity: DynamicCapacity | None = None,
        arrangement: TruckArrangement | None = None,
        analyst: str = "opportunity_engine",
    ) -> OpportunityCard:
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        # Analysis recommends; it does not move anything on its own authority.
        # The request goes to Spine, which validates it against its own table.
        if card.stage == "CREATED":
            # Spine's table is CREATED -> VALIDATION_PENDING -> VALIDATED and it
            # refuses the shortcut. Walking it is the point: the intermediate
            # state is where a validation failure would be recorded.
            card.request_transition("validating", actor_id=analyst)
            card.request_transition("validated", actor_id=analyst)

        # Operational analysis additions
        if capacity:
            card.deadhead_miles = capacity.position.estimated_deadhead_miles

            # Calculate Consumption % Metrics
            if capacity.physical.max_weight_lbs > 0:
                card.weight_consumption_pct = round((card.weight_lbs / capacity.physical.max_weight_lbs) * 100.0, 1)
            if capacity.physical.max_volume_cuft > 0:
                card.volume_consumption_pct = round((card.volume_cuft / capacity.physical.max_volume_cuft) * 100.0, 1)
            if capacity.physical.max_pallets > 0:
                card.pallet_consumption_pct = round((card.pallets / capacity.physical.max_pallets) * 100.0, 1)

        # Estimate HOS drive hours
        if card.estimated_miles > 0:
            card.estimated_hos_drive_hours = round((card.estimated_miles + card.deadhead_miles) / 50.0, 1)

        if capacity and capacity.time.drive_limit_hours > 0:
            card.time_consumption_pct = round((card.estimated_hos_drive_hours / capacity.time.drive_limit_hours) * 100.0, 1)

        # Estimate fuel cost ($3.80/gal @ 6.5 mpg)
        total_miles = card.estimated_miles + card.deadhead_miles
        card.estimated_fuel_cost = round((total_miles / 6.5) * 3.80, 2)
        card.estimated_net_profit = round(card.offered_rate - card.estimated_fuel_cost, 2)

        return card

    def score_opportunity(self, opportunity_id: str, analyst: str = "opportunity_engine") -> OpportunityCard:
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        if card.stage == "VALIDATED":
            card.request_transition("scoring", actor_id=analyst)
            card.request_transition("scored", actor_id=analyst)

        # Calculate noise reduction score (0 - 100)
        reasons = []
        base_score = 50.0

        if card.rpm >= 3.0:
            base_score += 25.0
            reasons.append(f"High RPM (${card.rpm:.2f}/mi)")
        elif card.rpm >= 2.0:
            base_score += 10.0
            reasons.append(f"Good RPM (${card.rpm:.2f}/mi)")
        else:
            base_score -= 15.0
            reasons.append(f"Low RPM (${card.rpm:.2f}/mi)")

        if card.deadhead_miles > 100:
            base_score -= 20.0
            reasons.append(f"Excessive deadhead ({card.deadhead_miles:.0f} mi)")
        elif card.deadhead_miles <= 30:
            base_score += 15.0
            reasons.append("Low deadhead")

        card.score = max(0.0, min(100.0, round(base_score, 1)))
        card.score_reasons = reasons

        return card

    def filter(self, min_score: float = 0.0, min_rpm: float = 0.0) -> list[OpportunityCard]:
        """Rank the scored opportunities. A QUERY, not a state change.

        `Filtered` used to be a lifecycle stage, which meant asking "which of
        these are worth looking at" permanently changed the things you asked
        about. It was never a position in a lifecycle -- it is a predicate over
        scores, and calling it twice with different thresholds should give two
        answers, not move anything.
        """
        matches = [
            card
            for card in self._opportunities.values()
            if card.stage in ("SCORED", "PORTAL_CARD_PENDING", "PORTAL_CARD_CREATED",
                              "WAITING_FOR_MIKE")
            and card.score >= min_score
            and card.rpm >= min_rpm
        ]
        matches.sort(key=lambda c: c.score, reverse=True)
        return matches

    def present(
        self,
        min_score: float = 0.0,
        min_rpm: float = 0.0,
        analyst: str = "opportunity_engine",
    ) -> list[OpportunityCard]:
        """Put the ranked shortlist in front of a human.

        Presenting is a real lifecycle movement -- it is what puts a card on
        Mike's desk -- so it is requested from Spine, which walks it to
        WAITING_FOR_MIKE. Nothing here decides anything; the whole point of
        the state is that a person now has to.
        """
        shortlist = self.filter(min_score=min_score, min_rpm=min_rpm)
        for card in shortlist:
            if card.stage == "SCORED":
                card.request_transition("presenting", actor_id=analyst)
                card.request_transition("presented", actor_id=analyst)
                card.request_transition("awaiting_decision", actor_id=analyst)
        return shortlist

    def filter_and_present(
        self, min_score: float = 0.0, min_rpm: float = 0.0
    ) -> list[OpportunityCard]:
        """Kept for the callers that already say this. `present()` is the name
        that describes what it does now that filtering is a query."""
        return self.present(min_score=min_score, min_rpm=min_rpm)

    def request_commitment(self, opportunity_id: str, human_actor: str) -> dict:
        """Record a human's decision to commit, and ask Spine to accept it.

        This is where the old `commit_opportunity_to_reality()` stopped being
        Opportunity's business. It used to walk Selected -> Committed ->
        Calendar Event -> Current Reality and then create the load and confirm
        the rate itself. Now it records the approval, asks Spine to move the
        work item, and stops. Spine creates the load
        (dispatch/spine/commitment.py::realize), and only against an approval
        that names a real person.
        """
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        actor = (human_actor or "").strip()
        if not actor:
            raise LifecycleAuthorityError(
                "A commitment requires an explicit human actor. Nothing may "
                "infer, default to, or manufacture one."
            )
        if actor.upper() in RESERVED_SYSTEM_IDENTITIES:
            raise LifecycleAuthorityError(
                f"{actor!r} is a system identity and cannot approve a commitment."
            )

        work_item = card.request_transition("approved", actor_id=actor, actor_type="human_authority")
        # APPROVE_LOAD_PURSUIT is already in Spine's approval vocabulary
        # (dispatch/models.py). Reusing it rather than widening the enum: a
        # commitment IS the pursuit approval, and a new action name would have
        # meant two words for one decision.
        create_approval_event(
            ApprovalEvent(
                user_id=actor,
                work_item_id=card.work_item_id,
                object_type="opportunity",
                object_id=card.opportunity_id,
                action="APPROVE_LOAD_PURSUIT",
                new_state="MIKE_APPROVED",
                comments=f"Committed opportunity {card.opportunity_id} at ${card.offered_rate:,.2f}",
            ),
            audit=AuditEvent(
                work_item_id=card.work_item_id,
                actor_type="human_authority",
                actor_id=actor,
                action="APPROVE_LOAD_PURSUIT",
                notes=f"Opportunity {card.opportunity_id}",
            ),
        )
        return work_item

    def realize_commitment(self, opportunity_id: str, *, actor_id: str) -> dict:
        """Hand an approved opportunity to Spine to become a load.

        Opportunity does not create the load. It asks, with the analytical
        record attached, and Spine refuses unless a human approval is already
        on the work item.
        """
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        load = spine_commitment.realize(
            card.work_item_id, actor_id=actor_id, opportunity=card.to_dict()
        )
        card.linked_load_id = load["load_id"]
        card.updated_at = _utc_now()
        return load

    def reject(self, opportunity_id: str, human_actor: str, reason: str = "") -> dict:
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")
        actor = (human_actor or "").strip()
        if not actor or actor.upper() in RESERVED_SYSTEM_IDENTITIES:
            raise LifecycleAuthorityError("A rejection requires a real human actor.")
        return card.request_transition("rejected", actor_id=actor, actor_type="human_authority")

    def get(self, opportunity_id: str) -> OpportunityCard | None:
        return self._opportunities.get(opportunity_id)
