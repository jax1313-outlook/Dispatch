"""Dispatch Spine state-transition guard.

`transition()` is the only function that may compute a work item state
change. `dispatch.spine.store.apply_transition()` is the only function
that may persist one -- see DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md
Section 3. No other code path may write `work_items.current_state`
directly; a structural test guards this the same way this codebase
already guards e.g. `build_ifta_review_dashboard()`'s read-only contract.

Transition table follows docs/DISPATCH_SPINE_SPECIFICATION_v1.md
Section 7 verbatim.
"""

from __future__ import annotations

from dispatch.spine.models import STATE_LIST, Event

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "CREATED": ["VALIDATION_PENDING"],
    "VALIDATION_PENDING": ["VALIDATED", "VALIDATION_FAILED"],
    "VALIDATION_FAILED": ["CONFLICT_RAISED", "ARCHIVED"],
    "VALIDATED": [
        "SCORING_PENDING",
        "COGNITIVE_REVIEW_PENDING",
        "ROUTING_PENDING",
        "PORTAL_CARD_PENDING",
    ],
    "SCORING_PENDING": ["SCORED", "CONFLICT_RAISED"],
    "SCORED": ["COGNITIVE_REVIEW_PENDING", "ROUTING_PENDING", "PORTAL_CARD_PENDING"],
    "COGNITIVE_REVIEW_PENDING": ["COGNITIVE_REVIEW_COMPLETE", "CONFLICT_RAISED"],
    "COGNITIVE_REVIEW_COMPLETE": ["ROUTING_PENDING", "PORTAL_CARD_PENDING"],
    "ROUTING_PENDING": [
        "ROUTED_TO_MANAGER",
        "ROUTED_TO_INTELLIGENCE",
        "ROUTED_TO_PUBLISHER",
        "ROUTED_TO_LIBRARY_REVIEW",
        "ROUTED_TO_ARCHIVE",
        "CONFLICT_RAISED",
    ],
    "ROUTED_TO_MANAGER": [],
    "ROUTED_TO_INTELLIGENCE": [],
    "ROUTED_TO_PUBLISHER": [],
    "ROUTED_TO_LIBRARY_REVIEW": [],
    "ROUTED_TO_ARCHIVE": [],
    "PORTAL_CARD_PENDING": ["PORTAL_CARD_CREATED", "CONFLICT_RAISED"],
    "PORTAL_CARD_CREATED": ["WAITING_FOR_MIKE"],
    "WAITING_FOR_MIKE": [
        "MIKE_APPROVED",
        "MIKE_REJECTED",
        "MIKE_REQUESTED_REVISION",
        "DEFERRED",
        "CONFLICT_RAISED",
    ],
    "MIKE_APPROVED": [
        "COMPLETED",
        "ROUTED_TO_PUBLISHER",
        "ROUTED_TO_LIBRARY_REVIEW",
        "ROUTED_TO_ARCHIVE",
    ],
    "MIKE_REJECTED": ["ARCHIVED", "COMPLETED"],
    "MIKE_REQUESTED_REVISION": [
        "ROUTED_TO_PUBLISHER",
        "ROUTED_TO_INTELLIGENCE",
        "ROUTED_TO_MANAGER",
        "COGNITIVE_REVIEW_PENDING",
    ],
    "DEFERRED": ["ROUTING_PENDING", "ARCHIVED"],
    "CONFLICT_RAISED": ["CONFLICT_RESOLVED", "WAITING_FOR_MIKE", "ARCHIVED"],
    "CONFLICT_RESOLVED": ["VALIDATION_PENDING", "ROUTING_PENDING", "PORTAL_CARD_PENDING"],
    "COMPLETED": ["ARCHIVED"],
    "ARCHIVED": [],
}

# Fails loudly at import time on a typo rather than silently allowing or
# blocking the wrong transition -- every state in STATE_LIST must have a
# (possibly empty) entry, and every named destination must itself be a
# real state.
assert set(ALLOWED_TRANSITIONS) == set(STATE_LIST), (
    "ALLOWED_TRANSITIONS must cover exactly STATE_LIST"
)
for _from_state, _targets in ALLOWED_TRANSITIONS.items():
    for _target in _targets:
        assert _target in STATE_LIST, f"Unknown target state {_target!r} from {_from_state!r}"


class InvalidTransitionError(ValueError):
    """Raised when a requested state transition is not in ALLOWED_TRANSITIONS."""


def is_allowed(current_state: str, new_state: str) -> bool:
    return new_state in ALLOWED_TRANSITIONS.get(current_state, [])


def transition(
    work_item: dict,
    new_state: str,
    *,
    actor_type: str,
    actor_id: str,
    summary: str = "",
    source_refs: list | None = None,
) -> Event:
    """Validate a work item state transition and build the Event that
    records it. Does not persist anything -- callers use
    `dispatch.spine.store.apply_transition()` for the persisted version,
    which wraps this in the same connection as the `work_items` UPDATE.
    """
    current_state = work_item["current_state"]
    if not is_allowed(current_state, new_state):
        raise InvalidTransitionError(
            f"{current_state!r} -> {new_state!r} is not an allowed transition"
        )
    return Event(
        work_item_id=work_item["work_item_id"],
        event_type="STATE_TRANSITION",
        actor_type=actor_type,
        actor_id=actor_id,
        previous_state=current_state,
        new_state=new_state,
        summary=summary or f"{current_state} -> {new_state}",
        source_refs=source_refs or [],
        requires_audit=True,
    )
