"""Proposal-trigger workflow (Phase 2).

Fires when a contract is approved for proposal (action == "approve_proposal").
Builds a structured proposal brief, drafts an outline via the proposal-writer
agent, persists both to Archive/Proposals, and emails a kickoff to the proposal
team. The brief is deterministic; only the outline is non-deterministic (Claude).
"""

from __future__ import annotations

from datetime import datetime, timezone

from cin_lite import archive, email_delivery
from cin_lite.agents import proposal_writer

# The control action that initiates a proposal.
TRIGGER_ACTION = "approve_proposal"

# How many days before the deadline each internal milestone lands.
_MILESTONE_OFFSETS = [
    ("kickoff", 14),
    ("draft_complete", 7),
    ("internal_review", 3),
    ("submit", 1),
]


def is_triggered(action: str) -> bool:
    return action == TRIGGER_ACTION


def _parse_date(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10])
        except ValueError:
            return None


def _milestones(response_date) -> list[dict]:
    from datetime import timedelta

    deadline = _parse_date(response_date)
    if deadline is None:
        return []
    return [
        {"name": name, "date": (deadline - timedelta(days=days)).strftime("%Y-%m-%d")}
        for name, days in _MILESTONE_OFFSETS
    ]


def _requirements_checklist(intelligence: dict, flags: list[str]) -> list[str]:
    sa = intelligence.get("set_aside_detection", {}).get("findings", {}).get("set_asides", [])
    ns = intelligence.get("naics_sin_extraction", {}).get("findings", {})
    cyber = intelligence.get("cyber_compliance_readiness", {}).get("findings", {})

    items: list[str] = []
    if sa:
        items.append(f"Verify set-aside eligibility and current certifications: {', '.join(sa)}")
    if ns.get("naics"):
        items.append(f"Map relevant past performance to NAICS {', '.join(ns['naics'])}")
    if ns.get("sins"):
        items.append(f"Confirm GSA SIN(s) on schedule: {', '.join(ns['sins'])}")
    for fw in cyber.get("frameworks", []):
        items.append(f"Address {fw} compliance in the technical volume")
    if cyber.get("cmmc_level"):
        items.append(f"Assemble CMMC Level {cyber['cmmc_level']} evidence")
    if "value_missing" in flags:
        items.append("Build a bottoms-up basis of estimate (no published value)")
    items.append("Confirm bid/no-bid sign-off and assign proposal manager")
    return items


def build_brief(
    contract: dict,
    contract_id: str,
    intelligence: dict,
    decision: dict,
    summary: str,
    flags: list[str],
) -> dict:
    """Assemble the deterministic proposal brief."""
    ns = intelligence.get("naics_sin_extraction", {}).get("findings", {})
    sa = intelligence.get("set_aside_detection", {}).get("findings", {}).get("set_asides", [])
    cyber = intelligence.get("cyber_compliance_readiness", {}).get("findings", {})

    return {
        "proposal_id": "PROP-" + contract_id.removeprefix("CIN-"),
        "contract_id": contract_id,
        "title": contract.get("title"),
        "agency": contract.get("agency"),
        "solicitation_number": contract.get("solicitation_number"),
        "status": "initiated",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "priority": decision.get("priority"),
        "assigned_to": decision.get("recipient") or "proposal-team",
        "response_deadline": contract.get("response_date"),
        "milestones": _milestones(contract.get("response_date")),
        "set_aside_basis": sa,
        "naics": ns.get("naics", []),
        "sins": ns.get("sins", []),
        "compliance": {
            "frameworks": cyber.get("frameworks", []),
            "cmmc_level": cyber.get("cmmc_level"),
            "readiness_burden": cyber.get("readiness_burden", "none"),
        },
        "requirements_checklist": _requirements_checklist(intelligence, flags),
        "summary": summary,
        "flags": flags,
        "source": contract.get("_source_file"),
    }


def _kickoff_email(brief: dict, outline: str) -> str:
    ms = "\n".join(f"    {m['name']:<16} {m['date']}" for m in brief["milestones"]) or "    (deadline unknown)"
    checklist = "\n".join(f"    - {item}" for item in brief["requirements_checklist"])
    return "\n".join(
        [
            f"Proposal kickoff: {brief['title']}",
            f"Proposal ID : {brief['proposal_id']}",
            f"Solicitation: {brief['solicitation_number']}",
            f"Agency      : {brief['agency']}",
            f"Priority    : {brief['priority']}",
            f"Deadline    : {brief['response_deadline']}",
            "",
            "Milestones:",
            ms,
            "",
            "Requirements checklist:",
            checklist,
            "",
            "Draft outline:",
            outline,
        ]
    )


def trigger(
    contract: dict,
    contract_id: str,
    intelligence: dict,
    decision: dict,
    summary: str,
    flags: list[str],
) -> dict:
    """Run the proposal-trigger workflow; return a result record."""
    brief = build_brief(contract, contract_id, intelligence, decision, summary, flags)
    outline = proposal_writer.draft_outline(contract, intelligence, brief, summary)
    brief["outline"] = outline

    json_path, md_path = archive.store_proposal(brief, outline)

    recipient = email_delivery.queue_address(brief["assigned_to"]) or email_delivery.reviewer_address()
    email_status = email_delivery.send(
        subject=f"[DISPATCH] Proposal kickoff — {brief['proposal_id']} (priority {brief['priority']})",
        body=_kickoff_email(brief, outline),
        to=[recipient],
        fallback_id=f"{brief['proposal_id']}-kickoff",
    )

    return {
        "proposal_id": brief["proposal_id"],
        "json_path": json_path,
        "outline_path": md_path,
        "email_status": email_status,
        "milestones": brief["milestones"],
    }
