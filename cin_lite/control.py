"""Control Layer — email-based human decision gate.

Renders checkpoint emails in both plain-text and HTML formats. The HTML version
contains styled action buttons that link to the portal's decision endpoint,
implementing the blueprint's "checkbox-driven email interface." The action -> route
mapping is deterministic; the email response maps directly to an archive/routing
action.
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


_ACTION_COLORS: dict[str, str] = {
    "approve_archive": "#2e7d32",
    "approve_proposal": "#1565c0",
    "reject": "#c62828",
    "flag_review": "#e65100",
    "deeper_analysis": "#6a1b9a",
}


def render_html_email(
    contract: dict,
    intelligence: dict,
    summary: str,
    flags: list[str],
    decision: dict | None = None,
    action_url_base: str = "http://127.0.0.1:8080/api/decision",
    token_fn: Any = None,
    contract_id: str = "",
) -> str:
    """Render the checkbox-driven control email as HTML with action buttons.

    Each button links to ``{action_url_base}/{contract_id}/{action}?token=…``
    so the reviewer can decide directly from the email.
    """

    def _link(action: str) -> str:
        token_part = ""
        if token_fn and contract_id:
            token_part = f"?token={token_fn(contract_id, action)}"
        return f"{action_url_base}/{contract_id}/{action}{token_part}"

    scored = [
        (r["module"], r["score"])
        for r in intelligence.values()
        if r.get("score") is not None
    ]
    module_notes = [r["summary"] for r in intelligence.values() if r.get("summary")]
    recommended = decision.get("action") if decision else None

    rows = []
    for key, (label, route) in ACTIONS.items():
        color = _ACTION_COLORS.get(key, "#333")
        rec_badge = (
            ' <span style="background:#fff3e0;color:#e65100;padding:2px 6px;'
            'border-radius:3px;font-size:11px;">RECOMMENDED</span>'
            if key == recommended
            else ""
        )
        rows.append(
            f'<tr><td style="padding:8px 12px;">'
            f'<a href="{_link(key)}" style="display:inline-block;padding:8px 20px;'
            f"background:{color};color:#fff;text-decoration:none;border-radius:4px;"
            f'font-weight:600;font-size:14px;">{label}</a>{rec_badge}'
            f'</td><td style="padding:8px 12px;color:#666;font-size:13px;">'
            f"{route}</td></tr>"
        )

    flags_html = ", ".join(flags) if flags else "<em>none</em>"

    score_rows = ""
    if scored:
        score_rows = '<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        for module, score in scored:
            score_rows += (
                f'<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;">{module}</td>'
                f'<td style="padding:4px 8px;border-bottom:1px solid #eee;'
                f'font-weight:600;">{score}</td></tr>'
            )
        score_rows += "</table>"

    notes_html = ""
    if module_notes:
        notes_html = '<ul style="margin:4px 0;padding-left:20px;">'
        for note in module_notes:
            notes_html += f"<li>{note}</li>"
        notes_html += "</ul>"

    rec_html = ""
    if decision:
        rec_label = ACTIONS.get(recommended, (recommended, ""))[0]
        rec_html = f"""
        <div style="background:#f5f5f5;border-left:4px solid #1565c0;padding:12px 16px;margin:16px 0;">
            <strong>Routing Agent Recommendation</strong><br>
            Action: {rec_label} [{recommended}]<br>
            Priority: {decision.get('priority', 'n/a')}<br>
            Reason: {decision.get('reason', '')}<br>
            Recipient: {decision.get('recipient', '')}<br>
        </div>"""

    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#333;">
    <div style="background:#1a237e;color:#fff;padding:16px 24px;">
        <h1 style="margin:0;font-size:20px;">CIN-Lite — Contract Decision Required</h1>
    </div>

    <div style="padding:20px 24px;border:1px solid #ddd;border-top:none;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr><td style="padding:6px 0;color:#666;width:120px;">Title</td>
                <td style="padding:6px 0;font-weight:600;">{contract.get('title', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Agency</td>
                <td style="padding:6px 0;">{contract.get('agency', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Solicitation</td>
                <td style="padding:6px 0;">{contract.get('solicitation_number', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Est. Value</td>
                <td style="padding:6px 0;">{contract.get('estimated_value', 'N/A')}</td></tr>
        </table>

        <div style="background:#fafafa;padding:12px 16px;border-radius:4px;margin-bottom:16px;">
            <strong>Summary</strong><br>{summary}
        </div>

        {notes_html and f'<div style="margin-bottom:16px;"><strong>Module Notes</strong>{notes_html}</div>' or ''}

        <div style="margin-bottom:16px;">
            <strong>Flags:</strong> {flags_html}
        </div>

        {score_rows and f'<div style="margin-bottom:16px;"><strong>Risk Scores</strong>{score_rows}</div>' or ''}

        {rec_html}

        <div style="margin-top:24px;">
            <h2 style="font-size:16px;margin-bottom:12px;border-bottom:2px solid #1a237e;padding-bottom:8px;">
                Select Action
            </h2>
            <table style="width:100%;border-collapse:collapse;">
                {''.join(rows)}
            </table>
        </div>
    </div>

    <div style="padding:12px 24px;font-size:11px;color:#999;border:1px solid #ddd;border-top:none;">
        CIN-Lite Hybrid System &mdash; Contract ID: {contract_id}
    </div>
</div>"""


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
