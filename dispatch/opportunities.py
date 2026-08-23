"""Opportunity Processing Pipeline and Opportunity Card Lifecycle.

Architecture concepts:
  - High-Volume Opportunity Intake (assumes abundance: 50, 100, 200+ opportunities)
  - Opportunity Card Formal Lifecycle (Possibility state machine):
      Discovered -> Analyzed -> Scored -> Filtered -> Presented -> Selected -> Committed -> Calendar Event -> Current Reality
  - Score Reduces Noise, Humans Decide (Score does not decide or auto-book)
  - Strict Separation of Possible Futures (State 2) from Current Reality (State 1)
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from dispatch.capacity import DynamicCapacity
from dispatch.truck_arrangement import TruckArrangement


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


OPPORTUNITY_LIFECYCLE_STAGES = [
    "Discovered",
    "Analyzed",
    "Scored",
    "Filtered",
    "Presented",
    "Selected",
    "Committed",
    "Calendar Event",
    "Current Reality",
]

ALLOWED_LIFECYCLE_TRANSITIONS = {
    "Discovered": {"Analyzed"},
    "Analyzed": {"Scored"},
    "Scored": {"Filtered"},
    "Filtered": {"Presented"},
    "Presented": {"Selected", "Filtered"},
    "Selected": {"Committed", "Presented"},
    "Committed": {"Calendar Event"},
    "Calendar Event": {"Current Reality"},
    "Current Reality": set(),
}


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
    equipment_type: str = "dry_van"

    # Analysis fields
    deadhead_miles: float = 0.0
    estimated_fuel_cost: float = 0.0
    estimated_hos_drive_hours: float = 0.0
    estimated_net_profit: float = 0.0

    # Score field (0 - 100)
    score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)

    # Lifecycle
    stage: str = "Discovered"
    committed_by: str = ""
    committed_at: str = ""
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
        if self.stage not in OPPORTUNITY_LIFECYCLE_STAGES:
            raise ValueError(f"Invalid stage: {self.stage!r}. Must be one of {OPPORTUNITY_LIFECYCLE_STAGES}")

    @property
    def rpm(self) -> float:
        if self.estimated_miles > 0:
            return round(self.offered_rate / self.estimated_miles, 2)
        return 0.0

    def transition_to(self, target_stage: str, actor: str = "") -> None:
        """Advance the opportunity lifecycle stage according to strict rules."""
        if target_stage not in OPPORTUNITY_LIFECYCLE_STAGES:
            raise ValueError(f"Invalid target stage: {target_stage!r}")

        allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(self.stage, set())
        if target_stage not in allowed:
            raise ValueError(
                f"Invalid lifecycle transition: {self.stage} -> {target_stage}. "
                f"Allowed from {self.stage}: {sorted(allowed)}"
            )

        # Human authority enforcement rule: Committed requires explicit human actor
        if target_stage == "Committed":
            if not actor:
                raise ValueError("Transition to 'Committed' requires explicit human authority actor")
            self.committed_by = actor
            self.committed_at = _utc_now()

        self.stage = target_stage
        self.updated_at = _utc_now()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rpm"] = self.rpm
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
                equipment_type=raw.get("equipment_type", "dry_van"),
            )
            self._opportunities[card.opportunity_id] = card
            ingested.append(card)
        return ingested

    def analyze_opportunity(
        self,
        opportunity_id: str,
        capacity: DynamicCapacity | None = None,
        arrangement: TruckArrangement | None = None,
    ) -> OpportunityCard:
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        if card.stage == "Discovered":
            card.transition_to("Analyzed")

        # Operational analysis additions
        if capacity:
            card.deadhead_miles = capacity.position.estimated_deadhead_miles

        # Estimate HOS drive hours
        if card.estimated_miles > 0:
            card.estimated_hos_drive_hours = round((card.estimated_miles + card.deadhead_miles) / 50.0, 1)

        # Estimate fuel cost ($3.80/gal @ 6.5 mpg)
        total_miles = card.estimated_miles + card.deadhead_miles
        card.estimated_fuel_cost = round((total_miles / 6.5) * 3.80, 2)
        card.estimated_net_profit = round(card.offered_rate - card.estimated_fuel_cost, 2)

        return card

    def score_opportunity(self, opportunity_id: str) -> OpportunityCard:
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        if card.stage == "Analyzed":
            card.transition_to("Scored")

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

    def filter_and_present(
        self, min_score: float = 0.0, min_rpm: float = 0.0
    ) -> list[OpportunityCard]:
        presented = []
        for card in self._opportunities.values():
            if card.stage in ("Scored", "Filtered", "Presented"):
                if card.score >= min_score and card.rpm >= min_rpm:
                    if card.stage == "Scored":
                        card.transition_to("Filtered")
                    if card.stage == "Filtered":
                        card.transition_to("Presented")
                    presented.append(card)

        # Sort presented opportunities by score descending (reducing noise)
        presented.sort(key=lambda c: c.score, reverse=True)
        return presented

    def commit_opportunity_to_reality(self, opportunity_id: str, human_actor: str) -> dict:
        """Commit an Opportunity Card (State 2 Possibility) to State 1 Reality."""
        card = self._opportunities.get(opportunity_id)
        if not card:
            raise ValueError(f"Opportunity not found: {opportunity_id}")

        if card.stage == "Presented":
            card.transition_to("Selected")

        card.transition_to("Committed", actor=human_actor)
        card.transition_to("Calendar Event")
        card.transition_to("Current Reality")

        # Create canonical State 1 Load
        from dispatch import services
        load = services.create_load(
            customer=card.source.upper(),
            pickup_location=card.origin_location,
            delivery_location=card.destination_location,
            pickup_datetime=card.pickup_window_start,
            delivery_datetime=card.delivery_window_start,
            equipment=card.equipment_type,
            notes=f"Committed from Opportunity {card.opportunity_id} by {human_actor}",
        )

        # Confirm Rate
        if card.offered_rate > 0:
            services.confirm_rate(
                load_id=load["load_id"],
                rate_amount=card.offered_rate,
                distance_miles=card.estimated_miles,
                confirmed_by=human_actor,
                notes=f"Auto-created upon opportunity commitment (RPM: ${card.rpm:.2f})",
            )

        card.linked_load_id = load["load_id"]
        return load
