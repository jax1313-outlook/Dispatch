"""Realising an approved opportunity into Current Reality.

CF-04, adjudicated 2026-08-23: "Opportunity recommends. Spine records reality.
Opportunity may request transitions. Spine owns transitions." This module is
the Spine side of that boundary -- the only path from an approved opportunity
to a committed load.

Before the ruling, `OpportunityPipeline.commit_opportunity_to_reality()` walked
its own four stages and then created the load and confirmed the rate itself.
That was Opportunity writing Current Reality directly, which the ruling forbids.
The work is not lost, it moved offices: Opportunity still asks, a human still
decides, and this function -- on the Spine side of the line -- is what acts.

Nothing here infers authority. A commitment is realised only when the Spine
work item is already in MIKE_APPROVED and carries an ApprovalEvent naming a
real actor. No default actor, no implied approval, no "verified by" that nobody
typed.
"""

from __future__ import annotations

from dispatch.spine.models import AuditEvent
from dispatch.spine.store import (
    create_audit_event,
    get_work_item,
    list_approval_events,
)

APPROVED_STATE = "MIKE_APPROVED"


class CommitmentNotAuthorized(ValueError):
    """Raised when something asks Spine to realise a commitment that no human
    has actually approved."""


def approval_for(work_item_id: str) -> dict | None:
    """The approval this commitment would rest on, or None.

    Reserved system identities cannot stand in for a person -- the same rule
    portal/models/library.py enforces for Library approvals, applied here so a
    machine cannot approve a load by naming itself.
    """
    reserved = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY", ""}
    for approval in list_approval_events(work_item_id):
        actor = (approval.get("user_id") or "").strip()
        if actor.upper() not in reserved:
            return approval
    return None


def realize(
    work_item_id: str,
    *,
    actor_id: str,
    opportunity: dict,
) -> dict:
    """Create the committed load for an approved opportunity.

    `opportunity` is the analytical record Opportunity produced -- lane, rate,
    windows, equipment. Spine reads it; Opportunity does not write the load.
    """
    work_item = get_work_item(work_item_id)
    if work_item is None:
        raise CommitmentNotAuthorized(f"Unknown work item: {work_item_id!r}")

    if work_item["current_state"] != APPROVED_STATE:
        raise CommitmentNotAuthorized(
            f"Work item {work_item_id} is in {work_item['current_state']}, not "
            f"{APPROVED_STATE}. A commitment is realised only after a human approval."
        )

    approval = approval_for(work_item_id)
    if approval is None:
        raise CommitmentNotAuthorized(
            f"Work item {work_item_id} is {APPROVED_STATE} but carries no approval "
            f"event naming a real actor. Nothing may infer that approval."
        )

    # Imported here rather than at module scope: dispatch.services imports a
    # great deal of the engine, and dispatch/spine/ is deliberately free of
    # dependencies on it in every other file.
    from dispatch import services

    load = services.create_load(
        customer=opportunity.get("customer") or opportunity.get("source", "").upper(),
        pickup_location=opportunity.get("origin_location", ""),
        delivery_location=opportunity.get("destination_location", ""),
        pickup_datetime=opportunity.get("pickup_window_start", ""),
        delivery_datetime=opportunity.get("delivery_window_start", ""),
        equipment=opportunity.get("equipment_type", ""),
        notes=(
            f"Committed from opportunity {opportunity.get('opportunity_id', '')} "
            f"via work item {work_item_id}, approved by {approval['user_id']}"
        ),
    )

    rate = float(opportunity.get("offered_rate") or 0.0)
    if rate > 0:
        services.confirm_rate(
            load_id=load["load_id"],
            rate_amount=rate,
            distance_miles=float(opportunity.get("estimated_miles") or 0.0),
            confirmed_by=approval["user_id"],
            notes=(
                f"Rate carried from opportunity {opportunity.get('opportunity_id', '')} "
                f"on the approval recorded as {approval['approval_event_id']}"
            ),
        )

    create_audit_event(
        AuditEvent(
            work_item_id=work_item_id,
            actor_type="spine_commitment",
            actor_id=actor_id,
            action="REALIZED_COMMITMENT",
            notes=f"Created load {load['load_id']} from opportunity "
                  f"{opportunity.get('opportunity_id', '')}",
        )
    )
    return load
