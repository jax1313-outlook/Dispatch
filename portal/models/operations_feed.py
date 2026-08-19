"""Operations Feed -- a single, consequence-sorted view of every open
decision-worthy item currently scattered across Publisher, Conflicts,
CIN-Lite pending decisions, Dispatch exceptions, settlements, stalled
loads, review/analysis queues, and Library asset gaps.

Real Dispatch already has all of this data -- it's just spread across
seven separate pages (§18 of the deployment blueprint: "Real Dispatch
spreads decisions across separate Publisher/Library/Archive/Pipeline/
Queues/Conflicts pages -- no equivalent unified feed exists yet.").
This module adds no new business logic and owns no new state: it reads
each subsystem's own existing listing function and normalizes the
result into one comparable card shape. Resolving/dismissing an item
still happens on that item's own page -- this is a read-only feed, not
a new action surface.

The consequence-level taxonomy (0-5) is a design reference borrowed
from the Jules sandbox's `PortalCard` (§18 of the blueprint), reused
here because it independently corroborates Driver-First Doctrine's
"Mike decides" posture (§0) -- level 3+ cards carry a non-optional
closing statement for exactly that reason, not because Jules's code
was ported (it wasn't; this reads real Dispatch data via real Dispatch
service functions).
"""

from __future__ import annotations

from dispatch import services as dispatch_svc

from portal.models import conflict, publisher, email_helper
from portal.models import library as lib_model

CARD_LEVELS: dict[int, str] = {
    0: "Silent Log",
    1: "Status",
    2: "Review",
    3: "Decision",
    4: "Conflict",
    5: "Authority",
}

REQUIRED_CARD_CLOSING = "This is a recommendation only. No action is authorized. Mike decides."

# Card levels at or above this carry the non-optional closing statement --
# these are the tiers where a human decision, not just awareness, is implied.
_DECISION_THRESHOLD = 3


def _card(
    *,
    card_id: str,
    source: str,
    card_level: int,
    title: str,
    summary: str,
    url: str,
    created_at: str = "",
) -> dict:
    return {
        "card_id": card_id,
        "source": source,
        "card_level": card_level,
        "level_label": CARD_LEVELS[card_level],
        "title": title,
        "summary": summary,
        "url": url,
        "created_at": created_at or "",
        "closing": REQUIRED_CARD_CLOSING if card_level >= _DECISION_THRESHOLD else "",
    }


def _publisher_cards() -> list[dict]:
    cards = []
    for action in publisher.get_queue():
        if action.get("status") in ("APPROVED", "ARCHIVED"):
            continue
        cards.append(_card(
            card_id=f"publisher-{action.get('id', '')}",
            source="publisher",
            card_level=5,
            title=action.get("action_type", "Publisher Action"),
            summary=f"{action.get('trigger_reason', '')} (status: {action.get('status', '')})",
            url="/publisher",
            created_at=action.get("created_at", ""),
        ))
    return cards


def _conflict_cards() -> list[dict]:
    cards = []
    severity_levels = {"critical": 4, "warning": 3, "info": 2}
    for notice in conflict.get_unresolved():
        level = severity_levels.get(notice.get("severity", "info"), 2)
        if not notice.get("human_decision_required", True):
            level = min(level, 2)
        cards.append(_card(
            card_id=f"conflict-{notice.get('id', '')}",
            source="conflict",
            card_level=level,
            title=notice.get("conflict_type", "conflict").replace("_", " ").title(),
            summary=notice.get("explanation", ""),
            url="/conflicts",
            created_at=notice.get("created_at", ""),
        ))
    return cards


def _govcon_pending_cards() -> list[dict]:
    from cin_lite import pending

    cards = []
    for item in pending.list_pending():
        decision = item.get("decision") or {}
        priority = (decision.get("priority") or "").lower()
        level = 4 if priority in ("critical", "high") else 3
        contract = item.get("contract") or {}
        cards.append(_card(
            card_id=f"govcon-{item.get('contract_id', '')}",
            source="govcon_pending",
            card_level=level,
            title=contract.get("title") or item.get("contract_id", "Pending Contract Decision"),
            summary=item.get("summary") or f"Recommended: {decision.get('action', 'review')}",
            url="/pipeline",
            created_at="",
        ))
    return cards


def _exception_cards() -> list[dict]:
    cards = []
    severity_levels = {"critical": 4, "high": 3, "medium": 2, "low": 2}
    for exc in dispatch_svc.list_exceptions():
        if exc.get("status") not in ("open", "investigating"):
            continue
        load = dispatch_svc.get_load(exc["load_id"]) or {}
        level = severity_levels.get(exc.get("severity", "medium"), 2)
        title = f"{exc.get('exception_type', '').replace('_', ' ').title()}"
        if load.get("customer"):
            title = f"{title} — {load['customer']}"
        cards.append(_card(
            card_id=f"exception-{exc.get('exception_id', '')}",
            source="exception",
            card_level=level,
            title=title,
            summary=exc.get("description", ""),
            url=f"/dispatch/{exc['load_id']}",
            created_at=exc.get("first_reported", ""),
        ))
    return cards


def _settlement_cards() -> list[dict]:
    cards = []
    for status, level in (("disputed", 4), ("overdue", 3)):
        for stl in dispatch_svc.list_settlements(payment_status=status):
            load = dispatch_svc.get_load(stl["load_id"]) or {}
            title = f"Invoice {stl.get('invoice_number', '')}"
            if load.get("customer"):
                title = f"{title} — {load['customer']}"
            summary = f"${stl.get('invoice_amount', 0):,.2f} {status}"
            if stl.get("due_date"):
                summary += f", due {stl['due_date']}"
            cards.append(_card(
                card_id=f"settlement-{stl.get('settlement_id', '')}",
                source="settlement",
                card_level=level,
                title=title,
                summary=summary,
                url=f"/dispatch/{stl['load_id']}",
                created_at=stl.get("invoice_date", ""),
            ))
    return cards


def _stalled_load_cards() -> list[dict]:
    cards = []
    for load in dispatch_svc.check_stalled_loads():
        title = "Stalled"
        if load.get("customer"):
            title = f"{title} — {load['customer']}"
        summary = (
            f"{load.get('hours_in_status')}h in "
            f"{load.get('status', '').replace('_', ' ')} "
            f"(threshold {load.get('threshold_hours')}h)"
        )
        cards.append(_card(
            card_id=f"stalled-{load.get('load_id', '')}",
            source="stalled_load",
            card_level=2,
            title=title,
            summary=summary,
            url=f"/dispatch/{load['load_id']}",
            created_at=load.get("updated_at", ""),
        ))
    return cards


def _queue_cards() -> list[dict]:
    from cin_lite.pipeline import routing_history

    cards = []
    for record in routing_history(route_filter="HUMAN_REVIEW"):
        cards.append(_card(
            card_id=f"queue-review-{record.get('contract_id', '')}",
            source="queue_review",
            card_level=2,
            title=record.get("summary") or record.get("contract_id", "Review Item"),
            summary=f"Routed to human review ({record.get('action_label') or record.get('action', '')}).",
            url="/queues",
            created_at=record.get("decided_at", ""),
        ))
    for record in routing_history(route_filter="DEEP_ANALYSIS_QUEUE"):
        cards.append(_card(
            card_id=f"queue-analysis-{record.get('contract_id', '')}",
            source="queue_analysis",
            card_level=1,
            title=record.get("summary") or record.get("contract_id", "Analysis Item"),
            summary=f"Queued for deeper analysis ({record.get('action_label') or record.get('action', '')}).",
            url="/queues",
            created_at=record.get("decided_at", ""),
        ))
    return cards


def _comi_cards() -> list[dict]:
    cards = []
    for package in email_helper.list_packages():
        if package.get("status") == "SUBMITTED":
            continue
        load = dispatch_svc.get_load(package["load_id"])
        title = (
            f"Closeout Communications — {load['customer']}"
            if load and load.get("customer")
            else package["load_id"]
        )
        cards.append(_card(
            card_id=f"comi-{package.get('id', '')}",
            source="comi",
            card_level=2,
            title=title,
            summary=f"Status: {package['status']}",
            url=f"/dispatch/{package['load_id']}",
            created_at=package.get("updated_at") or package.get("created_at") or "",
        ))
    return cards


def _library_gap_cards() -> list[dict]:
    cards = []
    for asset in lib_model.get_missing_company_assets():
        cards.append(_card(
            card_id=f"library-gap-{asset.replace(' ', '-').lower()}",
            source="library_gap",
            card_level=1,
            title=f"Missing: {asset}",
            summary="Required company asset not yet uploaded to the Library.",
            url="/library",
            created_at="",
        ))
    return cards


_SOURCE_BUILDERS = (
    _publisher_cards,
    _conflict_cards,
    _govcon_pending_cards,
    _exception_cards,
    _settlement_cards,
    _stalled_load_cards,
    _queue_cards,
    _library_gap_cards,
    _comi_cards,
)


def build_feed() -> dict:
    """Assemble every open card, sorted highest-consequence first and,
    within a level, most-recent first (cards with no timestamp sort last
    within their level, not first -- a missing timestamp is not the same
    as "just happened")."""
    cards: list[dict] = []
    for builder in _SOURCE_BUILDERS:
        cards.extend(builder())

    cards.sort(key=lambda c: c["created_at"], reverse=True)
    cards.sort(key=lambda c: c["card_level"], reverse=True)

    counts_by_level = {level: 0 for level in CARD_LEVELS}
    for c in cards:
        counts_by_level[c["card_level"]] += 1

    return {
        "cards": cards,
        "counts_by_level": counts_by_level,
        "levels": CARD_LEVELS,
        "total": len(cards),
    }
