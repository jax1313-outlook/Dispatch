"""State Model Lock — Load lifecycle (System Rule 3).

Enforces the 11-stage operational lifecycle as a locked, forward-only state
machine:

    Available -> Booked -> Planned -> En Route -> At Pickup -> Loaded
              -> In Transit -> At Delivery -> Delivered -> Invoiced -> Closed

This mirrors the shape of cin_lite's rule-module framework
(cin_lite/rules/base.py: RuleResult) but as Pydantic models, per Rule 15
(reuse the pattern; don't redesign it). `Load` is the L2-COS equivalent of
cin_lite's `contract` dict, and `StageEvent` history is the dispatch analog
of cin_lite's Routing/ archive record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class LifecycleStage(str, Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    PLANNED = "PLANNED"
    EN_ROUTE = "EN_ROUTE"
    AT_PICKUP = "AT_PICKUP"
    LOADED = "LOADED"
    IN_TRANSIT = "IN_TRANSIT"
    AT_DELIVERY = "AT_DELIVERY"
    DELIVERED = "DELIVERED"
    INVOICED = "INVOICED"
    CLOSED = "CLOSED"


# Locked forward-only transition table. No stage may be skipped or reversed
# through this model; out-of-band conditions (e.g. a cancelled load) are a
# separate status field on Load, not a transition in this table.
_TRANSITIONS: dict[LifecycleStage, tuple[LifecycleStage, ...]] = {
    LifecycleStage.AVAILABLE: (LifecycleStage.BOOKED,),
    LifecycleStage.BOOKED: (LifecycleStage.PLANNED,),
    LifecycleStage.PLANNED: (LifecycleStage.EN_ROUTE,),
    LifecycleStage.EN_ROUTE: (LifecycleStage.AT_PICKUP,),
    LifecycleStage.AT_PICKUP: (LifecycleStage.LOADED,),
    LifecycleStage.LOADED: (LifecycleStage.IN_TRANSIT,),
    LifecycleStage.IN_TRANSIT: (LifecycleStage.AT_DELIVERY,),
    LifecycleStage.AT_DELIVERY: (LifecycleStage.DELIVERED,),
    LifecycleStage.DELIVERED: (LifecycleStage.INVOICED,),
    LifecycleStage.INVOICED: (LifecycleStage.CLOSED,),
    LifecycleStage.CLOSED: (),
}


def next_stages(stage: LifecycleStage) -> tuple[LifecycleStage, ...]:
    """Stages `stage` is permitted to advance to (empty tuple if terminal)."""
    return _TRANSITIONS[stage]


def can_transition(current: LifecycleStage, target: LifecycleStage) -> bool:
    return target in _TRANSITIONS[current]


class StageEvent(BaseModel):
    """One recorded transition in a load's lifecycle history."""

    stage: LifecycleStage
    at: datetime
    actor: str = Field(description="dispatcher, driver, or system component recording the transition")
    notes: str = ""


class Load(BaseModel):
    """The L2-COS unit of work — the dispatch analog of a cin_lite contract."""

    load_id: str
    stage: LifecycleStage = LifecycleStage.AVAILABLE
    pickup_facility_id: str | None = None
    delivery_facility_id: str | None = None
    broker_id: str | None = None
    intelligence_score: int | None = Field(default=None, ge=0, le=100)
    history: list[StageEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def advance(self, target: LifecycleStage, actor: str, notes: str = "") -> "Load":
        """Move to `target` if it is a legal next stage; raises otherwise."""
        if not can_transition(self.stage, target):
            raise ValueError(
                f"illegal transition for load {self.load_id}: "
                f"{self.stage.value} -> {target.value} "
                f"(allowed: {[s.value for s in next_stages(self.stage)] or 'none (terminal)'})"
            )
        self.history.append(StageEvent(stage=target, at=datetime.now(timezone.utc), actor=actor, notes=notes))
        self.stage = target
        return self
