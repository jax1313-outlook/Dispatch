"""Control Layer — email-based human decision gate.

In Phase 1 there is no email API wired up, so the checkbox email is RENDERED to a
text file (and the console) and the user's selection is read from the CLI or an
interactive prompt. The action -> route mapping is deterministic; swap the
`send`/`collect` bodies for a real email API later without changing that mapping.
"""

from __future__ import annotations

from typing import Any

# action key -> (human label, resulting route)
ACTIONS: dict[str, tuple[str, str]] = {
    "approve_archive": ("Approve for archive", "ARCHIVE"),
    "approve_proposal": ("Approve for proposal", "PROPOSAL_QUEUE"),
    "reject": ("Reject", "REJECTED"),
    "flag_review": ("Flag for review", "HUMAN_REVIEW"),
    "deeper_analysis": ("Request deeper analysis", "DEEP_ANALYSIS_QUEUE"),
}


def render_email(
    contract: dict,
    intelligence: dict,
    summary: str,
    flags: list[str],
    decision: dict | None = None,
) -> str:
    """Render the checkbox-driven control email as plain text."""
    lines = [
        "=" * 64,
        "CIN-Lite — Contract Control Email",
        "=" * 64,
        f"Title       : {contract.get('title')}",
        f"Agency      : {contract.get('agency')}",
        f"Solicitation: {contract.get('solicitation_number')}",
        f"Est. value  : {contract.get('estimated_value')}",
        "",
        "Summary:",
        f"  {summary}",
        "",
    ]

    module_notes = [r["summary"] for r in intelligence.values() if r.get("summary")]
    if module_notes:
        lines.append("Module notes:")
        lines.extend(f"  - {note}" for note in module_notes)
        lines.append("")

    lines.append(f"Flags raised: {', '.join(flags) if flags else 'none'}")
    lines.append("")

    scored = [(r["module"], r["score"]) for r in intelligence.values() if r.get("score") is not None]
    if scored:
        lines.append("Risk scores:")
        lines.extend(f"  {module}: {score}" for module, score in scored)
        lines.append("")

    recommended = None
    if decision:
        recommended = decision.get("action")
        rec_label = ACTIONS.get(recommended, (recommended, ""))[0]
        lines += [
            "Recommended decision (routing agent):",
            f"  Action   : {rec_label} [{recommended}]",
            f"  Priority : {decision.get('priority')}",
            f"  Recipient: {decision.get('recipient')}",
            f"  Reason   : {decision.get('reason')}",
            f"  Notes    : {decision.get('notes')}",
            "",
        ]

    lines.append("Choose ONE action (reply with the key in brackets):")
    for key, (label, route) in ACTIONS.items():
        mark = "*" if key == recommended else " "
        flag = "  <- recommended" if key == recommended else ""
        lines.append(f"  [{mark}] {key:<16} {label}  ->  {route}{flag}")
    lines.append("=" * 64)
    return "\n".join(lines)


def resolve(action: str) -> tuple[str, str]:
    """Map an action key to (label, route). Raises on unknown actions."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown action {action!r}. Valid: {', '.join(ACTIONS)}")
    return ACTIONS[action]


def collect(default: str | None = None, recommended: str | None = None) -> str:
    """Get the user's action. Non-interactive callers pass `default`.

    When interactive, an empty reply accepts the `recommended` action (if any).
    """
    if default is not None:
        return default
    valid = ", ".join(ACTIONS)
    suffix = f" (enter = recommended: {recommended})" if recommended in ACTIONS else ""
    while True:
        choice = input(f"\nAction [{valid}]{suffix}: ").strip()
        if not choice and recommended in ACTIONS:
            return recommended
        if choice in ACTIONS:
            return choice
        print(f"  '{choice}' is not valid.")
