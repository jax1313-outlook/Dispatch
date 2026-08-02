"""Programmatic pipeline API — shared by CLI (run.py) and portal (pipeline routes).

Provides a reusable ``process_contracts()`` that runs the full Phase-1 flow:
acquire -> process -> summarize -> route -> store pending -> send checkpoint email.

Also provides ``resolve_decision()`` for completing a pending decision from any
caller (portal UI, email click, CLI).
"""

from __future__ import annotations

from datetime import datetime, timezone

from cin_lite import acquisition, processing, archive, control, email_delivery, pending
from cin_lite.agents import summarizer, router
from cin_lite.workflows import proposal


def process_contracts(action_override: str | None = None) -> list[dict]:
    """Run the pipeline on all acquired contracts.

    Returns a list of result dicts, one per contract:
        {contract_id, title, agency, summary, recommendation, status, ...}

    When *action_override* is set the decision is applied immediately
    (status="decided"); otherwise the contract is left pending
    (status="pending").
    """
    contracts = acquisition.acquire()
    results: list[dict] = []

    for contract in contracts:
        contract["_acquired_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        intelligence = processing.process(contract)
        flags = processing.all_flags(intelligence)
        summary = summarizer.summarize(contract, intelligence, flags)
        decision = router.decide(contract, intelligence, summary, flags)
        contract_id = archive.make_id(contract)

        text_email = control.render_email(contract, intelligence, summary, flags, decision)
        html_email = control.render_html_email(
            contract, intelligence, summary, flags, decision,
            token_fn=email_delivery.make_token,
            contract_id=contract_id,
        )

        pending.store(contract_id, contract, intelligence, summary, decision, flags)
        checkpoint_status = email_delivery.deliver_checkpoint(
            contract, contract_id, text_email, html_email,
        )

        result = {
            "contract_id": contract_id,
            "title": contract.get("title"),
            "agency": contract.get("agency"),
            "solicitation_number": contract.get("solicitation_number"),
            "summary": summary,
            "recommendation": decision.get("action"),
            "priority": decision.get("priority"),
            "flag_count": len(flags),
            "checkpoint_email": checkpoint_status,
            "status": "pending",
        }

        if action_override:
            dec = resolve_decision(contract_id, action_override)
            result.update(dec)
            result["status"] = "decided"

        results.append(result)

    return results


def resolve_decision(contract_id: str, action: str) -> dict:
    """Complete a pending decision: archive, route, and send confirmation.

    Returns a result dict with the action taken, route, and proposal info.
    Raises ValueError if the contract_id is not pending or the action is invalid.
    """
    record = pending.load(contract_id)
    if not record:
        raise ValueError(f"No pending decision for {contract_id}")

    label, route = control.resolve(action)

    contract_data = record["contract"]
    intelligence = record["intelligence"]
    summary = record["summary"]
    decision = record["decision"]
    flags = record["flags"]

    metadata = archive.store(contract_data, intelligence, summary)
    archive.record_routing(
        metadata["contract_id"], action, route, metadata, decision,
        action_label=label, flags=flags, summary=summary,
    )
    email_delivery.deliver_decision(
        contract_data, metadata["contract_id"], summary, decision, action, route, flags,
    )

    pending.complete(contract_id)

    result: dict = {
        "contract_id": metadata["contract_id"],
        "title": contract_data.get("title", ""),
        "action": action,
        "action_label": label,
        "route": route,
        "followed_recommendation": decision.get("action") == action,
    }

    if proposal.is_triggered(action):
        prop = proposal.trigger(
            contract_data, metadata["contract_id"], intelligence, decision, summary, flags,
        )
        result["proposal"] = {
            "proposal_id": prop["proposal_id"],
            "email_status": prop["email_status"],
        }

    return result


def routing_history() -> list[dict]:
    """Read completed routing decisions from the archive."""
    routing_dir = archive.ARCHIVE_ROOT / "Routing"
    if not routing_dir.exists():
        return []
    import json
    results = []
    for path in sorted(routing_dir.glob("*.json"), reverse=True):
        with path.open(encoding="utf-8") as fh:
            results.append(json.load(fh))
    return results
