"""Portal helpers — data loading and card processing.

Reads from pipeline layers without modifying them.
"""

from __future__ import annotations

from cin_lite import acquisition, processing
from cin_lite.agents import summarizer, router


#: The bands, as shares of the engine's real maximum (`dispatch.scoring.MAX_SCORE`).
#:
#: They were written as 90 / 75 / 60 / 40 against a 100-point score. Broker trust
#: left the engine and the maximum became 90, so HIGH VALUE MATCH needed a perfect
#: score and every band sat ten percent too high -- the "calibrated against" note in
#: `scoring.py` said so and nothing followed it. Fixed 2026-09-14 (CO-3) by keeping
#: each band's share of the maximum, which is the policy as written; the shares
#: themselves remain the Owner's to change.
SCORE_BAND_SHARES = (
    (0.90, {"icon": "✅", "label": "HIGH VALUE MATCH", "css": "card-high"}),
    (0.75, {"icon": "🟢", "label": "STRONG MATCH", "css": "card-strong"}),
    (0.60, {"icon": "🟡", "label": "MODERATE", "css": "card-moderate"}),
    (0.40, {"icon": "🟠", "label": "LOW VALUE", "css": "card-low"}),
)


def _score_max(rate_pending: bool = False) -> int:
    """The maximum a score is read against.

    With the rate pending it is the maximum without the rate factor (Owner ruling
    2026-09-15, "2a"), so the bands keep the same shares of what that card can
    actually score -- a card is never banded lower for a rate nobody has given.
    """
    from dispatch.scoring import MAX_SCORE, MAX_SCORE_WITHOUT_RATE

    return MAX_SCORE_WITHOUT_RATE if rate_pending else MAX_SCORE


#: Kept for callers that read it: the score at which a card is HIGH VALUE.
SCORE_HIGH_THRESHOLD = 81

INQUIRY_TEMPLATE_SUBJECT = "Load Inquiry - Level 1 Transport"

INQUIRY_TEMPLATE_BODY = """\
Hello,

We reviewed your posted load and believe it may fit our operating area and equipment profile.

Please contact us when available to discuss load details, timing, and rate.

Thank you,

Mike Zachary
Level 1 Transport Inc.

---
Important:
This is not acceptance.
This is not commitment.
This is not negotiation.
This is a non-binding early inquiry."""


def load_and_process_sam() -> list[dict]:
    """Acquire SAM contracts and process through the pipeline."""
    contracts = acquisition.acquire()
    results = []
    for contract in contracts:
        intel = processing.process(contract)
        flags = processing.all_flags(intel)
        summary = summarizer.summarize(contract, intel, flags)
        decision = router.decide(contract, intel, summary, flags)
        results.append({
            "contract": contract,
            "intelligence": intel,
            "flags": flags,
            "summary": summary,
            "decision": decision,
        })
    return results


def load_dispatch_data() -> list[dict]:
    """Acquire dispatch/load data and run scoring on each load."""
    from dispatch.acquisition import acquire
    from dispatch.scoring import score_load

    loads = acquire()
    for data in loads:
        scoring = score_load(data)
        data["deadhead_miles"] = scoring.get("deadhead_miles")
        data["fuel_estimate"] = scoring.get("fuel_estimate")
        data["score"] = scoring["score"]
        data["_scoring"] = scoring
    return loads


def card_visual(score: int | None, decision: dict | None = None, *,
                rate_pending: bool = False) -> dict:
    """Determine card visual header based on score or routing decision.

    `rate_pending` reads the score against the maximum without the rate factor.
    """
    if score is not None:
        for share, visual in SCORE_BAND_SHARES:
            if score >= share * _score_max(bool(rate_pending)):
                return dict(visual)
        return {"icon": "🔴", "label": "POOR MATCH", "css": "card-poor"}

    if decision:
        action = decision.get("action", "")
        priority = decision.get("priority", "")
        if action == "approve_proposal":
            return {"icon": "✅", "label": f"PURSUE CANDIDATE | {priority}", "css": "card-high"}
        if action == "flag_review":
            return {"icon": "\U0001f7e5", "label": "FLAG FOR REVIEW", "css": "card-investigate"}
        if action == "deeper_analysis":
            return {"icon": "⚠️", "label": "DEEPER ANALYSIS", "css": "card-analysis"}
        if action == "reject":
            return {"icon": "❌", "label": "REJECT", "css": "card-reject"}

    return {"icon": "", "label": "", "css": "card-default"}


#: How a score with the rate pending is marked. Owner ruling 2026-09-15:
#: *"(a) a score from everything except the rate, marked '* rate pending'"*.
RATE_PENDING_MARK = "* rate pending"


def format_score(score: int | None, rate_pending: bool = False) -> str:
    """The score as shown. With the rate pending: "52 of 60 · * rate pending"."""
    if score is None:
        return "Unknown"
    if rate_pending:
        return "%s of %s · %s" % (score, _score_max(True), RATE_PENDING_MARK)
    return str(score)


def score_share(score: int | None, rate_pending: bool = False) -> float | None:
    """A score as a share of the maximum that applies to it. None when unscored.

    What a threshold set against the full maximum is compared with, so a card
    with the rate pending is measured like with like.
    """
    if score is None:
        return None
    return float(score) / _score_max(bool(rate_pending))


def attention_needed(limit: int = 5) -> list[dict]:
    """Compose a small cross-department preview of items awaiting action.

    Portal Presentation-Layer Consolidation (Claude-3 repo,
    PRESENTATION_LAYER_CONSOLIDATION_SCOPE_v1.md): a strictly read-only composition over three
    existing queues -- portal/models/publisher.py's action queue, cin_lite's pending decisions,
    and cin_lite's HUMAN_REVIEW routing queue -- so /home can show a user real cross-department
    work without visiting /publisher, /pipeline, and /queues separately. Reads only; does not
    modify any of the three sources, and is not orchestration, routing, or decision logic --
    explicitly not Manager (see MANAGER_ORCHESTRATION_REVIEW_v1.md; that capability stays
    dormant and this function has no relationship to it).
    """
    from cin_lite.pipeline import routing_history
    from cin_lite import pending as cin_pending
    from portal.models import publisher as pub_model

    items: list[dict] = []

    for action in pub_model.get_queue():
        if action["status"] in ("PENDING", "DRAFT", "READY"):
            items.append({
                "source": "Publisher",
                "title": action["action_type"],
                "detail": action.get("trigger_reason", ""),
                "url": "/publisher",
            })

    for record in cin_pending.list_pending():
        contract = record.get("contract", {})
        items.append({
            "source": "Pipeline",
            "title": contract.get("title") or record.get("contract_id", ""),
            "detail": record.get("summary", ""),
            "url": "/pipeline",
        })

    for entry in routing_history(route_filter="HUMAN_REVIEW"):
        metadata = entry.get("metadata") or {}
        items.append({
            "source": "Review Queue",
            "title": metadata.get("title") or entry.get("contract_id", ""),
            "detail": entry.get("action_label", ""),
            "url": "/queues",
        })

    return items[:limit]
