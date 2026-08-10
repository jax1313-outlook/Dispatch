"""Manager's Staff Report generator -- the orchestrator for this build.

Reads signals (signals.py), classifies (classify.py), ranks
(priority.py), and for anything clearing the Review Needed bar,
creates a Work Item + Portal Card through the Spine's own,
unmodified machinery -- never a direct write to `current_state`.

State path used for every Work Item this module creates, all four
transitions already present in dispatch/spine/state.py's
ALLOWED_TRANSITIONS, unchanged since Stage 4:

    CREATED -> VALIDATION_PENDING -> VALIDATED
             -> PORTAL_CARD_PENDING -> PORTAL_CARD_CREATED

This never touches ROUTED_TO_MANAGER (still a dead end, still
untouched by this build -- see DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md
Section 7). actor_type/actor_id on every transition and event is
"manager" -- a function identity, not a Security-authenticated human
identity; Manager is not a User in dispatch/security/'s sense.

Dedup (Section 6 of the design): a Work Item already existing for a
signal's (source_type, source_id) pair, in any state, blocks creating
a duplicate. This build never itself moves a created Work Item past
PORTAL_CARD_CREATED, so "any state" and "non-terminal state" are
equivalent here -- flagged since a future build that lets Mike dismiss/
resolve a Manager-created item would need to narrow this to true
non-terminal states only.
"""

from __future__ import annotations

from dispatch.manager import classify, priority, signals as signals_mod
from dispatch.spine.models import PortalCard, WorkItem
from dispatch.spine.store import (
    create_portal_card,
    create_work_item,
    apply_transition,
    get_work_item,
    list_portal_cards,
    list_work_items,
)

_ACTOR_TYPE = "manager"
_ACTOR_ID = "manager"

_TRANSITION_PATH = [
    "VALIDATION_PENDING",
    "VALIDATED",
    "PORTAL_CARD_PENDING",
    "PORTAL_CARD_CREATED",
]

_CARD_TYPE_BY_CLASSIFICATION = {
    classify.STATUS: "status",
    classify.REVIEW_NEEDED: "review",
    classify.DECISION_NEEDED: "decision",
    classify.CONFLICT: "conflict",
    classify.AUTHORITY: "authority",
}


def _existing_work_item(existing_by_key: dict, classified: dict) -> dict | None:
    key = (classified["source_type"], classified["source_id"])
    return existing_by_key.get(key)


def _materialize(classified: dict) -> dict:
    """Creates a Work Item, moves it through the allowed transition
    path to PORTAL_CARD_CREATED, and creates its Portal Card. Returns
    the card dict, enriched with priority_tier for display ordering.
    """
    work_item = create_work_item(
        WorkItem(
            source_type=classified["source_type"],
            source_id=classified["source_id"],
            priority=str(classified["priority_tier"]),
            consequence_level=classified["card_level"],
            assigned_function="Manager",
            required_action=classified["title"],
        )
    )
    for target_state in _TRANSITION_PATH:
        work_item = apply_transition(
            work_item["work_item_id"],
            target_state,
            actor_type=_ACTOR_TYPE,
            actor_id=_ACTOR_ID,
            summary=f"Manager: {classified['title']}",
        )

    card = create_portal_card(
        PortalCard(
            work_item_id=work_item["work_item_id"],
            card_level=classified["card_level"],
            card_type=_CARD_TYPE_BY_CLASSIFICATION.get(
                classified["classification"], "status"
            ),
            title=classified["title"],
            summary=classified["summary"],
            recommendation=(
                f"Classified {classified['classification']} "
                f"(source: {classified['source_type']})."
            ),
            decision_needed=classified["title"]
            if classified["classification"] in (classify.DECISION_NEEDED, classify.CONFLICT)
            else None,
        )
    )
    return {**card, "priority_tier": classified["priority_tier"]}


def _active_cards() -> list[dict]:
    """Every currently-tracked Portal Card at or above the Review
    Needed bar -- materialized this pass or any prior pass. This is
    what /manager actually displays: everything still worth Mike's
    attention, not just what changed in this exact request. Each
    card's priority_tier is read back from its Work Item's stored
    `priority` field (set once at creation in _materialize()), so
    ranking stays consistent across passes without recomputing
    classification from a signal that may no longer exist (e.g. an
    exception that was later resolved -- its card still reflects the
    state at materialization time; re-classifying stale cards is
    additive future scope, not part of this build).
    """
    active = [c for c in list_portal_cards() if c["card_level"] >= classify.REVIEW_BAR_CARD_LEVEL]
    enriched = []
    for card in active:
        work_item = get_work_item(card["work_item_id"])
        tier = int(work_item["priority"]) if work_item and work_item["priority"] else priority.TIER_DEFERRED_ROUTINE
        enriched.append({**card, "priority_tier": tier})
    return sorted(enriched, key=lambda c: (c["priority_tier"], -c["card_level"]))


def generate_staff_report() -> dict:
    """Runs the full Staff Report pass: read, classify, rank, dedup,
    materialize any newly-qualifying signal. Returns
    {'counts': {class: count}, 'cards': [...]} where 'counts' reflects
    this pass's signal read (including Status/Routine/Noise, which
    never get a card), and 'cards' is every currently-active card at
    or above the Review Needed bar, ranked highest priority first --
    not only the ones newly created in this pass.
    """
    raw_signals = signals_mod.collect_signals()
    classified_signals = [classify.classify_signal(s) for s in raw_signals]
    ranked = priority.rank(classified_signals)

    existing_by_key = {
        (wi["source_type"], wi["source_id"]): wi for wi in list_work_items()
    }

    counts: dict[str, int] = {}
    for classified in ranked:
        counts[classified["classification"]] = counts.get(classified["classification"], 0) + 1
        if not classify.clears_review_bar(classified):
            continue
        if _existing_work_item(existing_by_key, classified) is not None:
            continue
        _materialize(classified)

    return {"counts": counts, "cards": _active_cards()}
