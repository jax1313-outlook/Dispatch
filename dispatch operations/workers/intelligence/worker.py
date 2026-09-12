"""Pre-Commit Intelligence Worker Implementation.

Evaluates 6 Dynamic Capacity dimensions, scores freight opportunities, generates calendar
placement recommendations, and presents opportunities to Mike Zachary.

Constitutional Rule: INTELLIGENCE recommends. INTELLIGENCE stops at Mike's commit gate.
INTELLIGENCE may never commit loads or override human decisions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from dispatch.capacity import DynamicCapacity
from dispatch.opportunities import OpportunityCard, OpportunityPipeline
from worker_framework.base import (
    BaseWorker,
    WorkerConstitution,
    WorkerBoundaryViolationError,
)

INTELLIGENCE_CONSTITUTION = WorkerConstitution(
    worker_id="INTELLIGENCE",
    name="Pre-Commit Freight Intelligence Worker",
    purpose="Pre-commit lifecycle evaluation: dynamic capacity analysis, scoring, and calendar recommendations.",
    capabilities=[
        "dynamic_capacity_6d_evaluation",
        "opportunity_scoring",
        "calendar_placement_recommendation",
        "consumption_metric_calculation",
    ],
    boundaries={
        "may_commit": False,
        "may_override_human": False,
        "stop_condition": "Mike Commit Gate",
    },
    inputs=["OpportunityCard", "DynamicCapacityData", "CalendarState"],
    outputs=["ScoredOpportunityCard", "CapacityFinding", "CalendarRecommendation"],
    relationships=["JOE", "MIKE"],
    handoffs=["MIKE"],
    stop_conditions=["Commitment attempt", "Mike approval gate"],
    escalation_conditions=["Unconfigured physical asset data", "HOS clock violation"],
)


class IntelligenceWorker(BaseWorker):
    """Intelligence Worker executing pre-commit load evaluation and scoring."""

    RECOMMENDATION_NOTICE = "This is a recommendation only. No action is authorized. Mike decides."

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        pipeline: Optional[OpportunityPipeline] = None,
    ):
        super().__init__(constitution=INTELLIGENCE_CONSTITUTION, config=config)
        self.pipeline = pipeline or OpportunityPipeline()

    def evaluate_capacity_and_score(
        self,
        card: OpportunityCard,
        capacity: Optional[DynamicCapacity] = None,
        analyst: str = "INTELLIGENCE",
    ) -> OpportunityCard:
        """Run 6-dimension Dynamic Capacity analysis and calculate score."""
        if card.opportunity_id not in self.pipeline._opportunities:
            self.pipeline._opportunities[card.opportunity_id] = card

        analyzed_card = self.pipeline.analyze_opportunity(
            opportunity_id=card.opportunity_id,
            capacity=capacity,
            analyst=analyst,
        )

        scored_card = self.pipeline.score_opportunity(
            opportunity_id=card.opportunity_id,
            analyst=analyst,
        )

        self.state = "EVALUATED_AND_SCORED"
        return scored_card

    def recommend_calendar_placement(self, card: OpportunityCard) -> Dict[str, Any]:
        """Generate calendar placement recommendation for an opportunity."""
        pickup_start = card.pickup_window_start or "2026-09-15T08:00:00Z"
        delivery_start = card.delivery_window_start or "2026-09-16T17:00:00Z"
        return {
            "opportunity_id": card.opportunity_id,
            "recommended_slot_start": pickup_start,
            "recommended_slot_end": delivery_start,
            "estimated_drive_hours": card.estimated_hos_drive_hours,
            "notice": self.RECOMMENDATION_NOTICE,
        }

    def present_to_mike(self, card: OpportunityCard) -> OpportunityCard:
        """Present opportunity to Mike on LOADS screen, moving state to WAITING_FOR_MIKE."""
        presented_list = self.pipeline.present(min_score=0.0, analyst="INTELLIGENCE")
        for item in presented_list:
            if item.opportunity_id == card.opportunity_id:
                self.state = "AWAITING_MIKE_DECISION"
                return item
        self.state = "AWAITING_MIKE_DECISION"
        return card

    def commit_opportunity(self, opportunity_id: str, actor_id: str = "INTELLIGENCE") -> None:
        """Constitutional Guard: INTELLIGENCE is strictly forbidden from committing loads."""
        self.verify_authority("COMMIT_OPPORTUNITY", actor_id=actor_id)
        raise WorkerBoundaryViolationError("INTELLIGENCE worker cannot commit loads.")
