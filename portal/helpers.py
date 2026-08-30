"""Portal helpers — data loading and card processing.

Reads from pipeline layers without modifying them.
"""

from __future__ import annotations

from cin_lite import acquisition, processing
from cin_lite.agents import summarizer, router


SCORE_HIGH_THRESHOLD = 90

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


def card_visual(score: int | None, decision: dict | None = None) -> dict:
    """Determine card visual header based on score or routing decision."""
    if score is not None:
        if score >= SCORE_HIGH_THRESHOLD:
            return {"icon": "✅", "label": "HIGH VALUE MATCH", "css": "card-high"}
        if score >= 75:
            return {"icon": "🟢", "label": "STRONG MATCH", "css": "card-strong"}
        if score >= 60:
            return {"icon": "🟡", "label": "MODERATE", "css": "card-moderate"}
        if score >= 40:
            return {"icon": "🟠", "label": "LOW VALUE", "css": "card-low"}
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


def format_score(score: int | None) -> str:
    if score is None:
        return "Unknown"
    return str(score)


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
