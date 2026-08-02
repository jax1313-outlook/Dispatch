"""Proposal-drafting agent — Claude-backed (with deterministic fallback).

Given a contract, its rule intelligence, and a proposal brief, drafts a concise
proposal outline (volumes/sections + win themes) in Markdown. This is a
NON-deterministic helper outside the rule path. Falls back to a deterministic
standard-GovCon outline when Claude is unavailable, so the workflow always runs.
"""

from __future__ import annotations

import json
import os
import sys

MODEL = os.environ.get("DISPATCH_MODEL", "claude-opus-4-8")
MAX_TOKENS = 900

_SYSTEM = (
    "You are the proposal-drafting agent for federal contract pursuits. Given a "
    "contract, its rule-module intelligence, and a proposal brief, produce a "
    "concise proposal outline in Markdown: the standard volumes (Technical, "
    "Management, Past Performance, Price) with 2-4 bullets each, a compliance "
    "matrix tied to the detected requirements (set-asides, NAICS/SIN, cyber "
    "frameworks), and 2-3 win themes. Ground every point in the provided data; do "
    "not invent requirements. Output only the Markdown outline."
)


def _deterministic_outline(contract: dict, intelligence: dict, brief: dict) -> str:
    sa = intelligence.get("set_aside_detection", {}).get("findings", {}).get("set_asides", [])
    ns = intelligence.get("naics_sin_extraction", {}).get("findings", {})
    cyber = intelligence.get("cyber_compliance_readiness", {}).get("findings", {})
    frameworks = cyber.get("frameworks", [])

    lines = [
        f"# Proposal Outline — {contract.get('title')}",
        f"Solicitation {contract.get('solicitation_number')} | "
        f"{contract.get('agency')} | due {brief.get('response_deadline')}",
        "",
        "## Volume I — Technical Approach",
        "- Restate the requirement and our understanding of the objective",
        "- Proposed technical solution and methodology",
        "- Staffing plan mapped to required skills",
        "",
        "## Volume II — Management Approach",
        "- Program management plan, schedule, and risk management",
        "- Quality control and reporting cadence",
        "",
        "## Volume III — Past Performance",
        f"- Relevant work under NAICS {', '.join(ns.get('naics', [])) or 'n/a'}",
        "- CPARS / references demonstrating scope and complexity",
        "",
        "## Volume IV — Price / Cost",
        "- Basis of estimate (no published value)"
        if "value_missing" in brief.get("flags", [])
        else "- Price validated against published estimate",
        "- Cost realism narrative",
        "",
        "## Compliance Matrix",
    ]
    if sa:
        lines.append(f"- Confirm set-aside eligibility: {', '.join(sa)} (certifications current)")
    if ns.get("sins"):
        lines.append(f"- Confirm GSA SIN(s) on schedule: {', '.join(ns['sins'])}")
    for fw in frameworks:
        lines.append(f"- Address {fw} compliance in the technical volume")
    if cyber.get("cmmc_level"):
        lines.append(f"- Provide CMMC Level {cyber['cmmc_level']} evidence")
    if not (sa or ns.get("sins") or frameworks):
        lines.append("- No special compliance requirements detected")

    lines += [
        "",
        "## Win Themes",
        "- Demonstrated past performance directly relevant to this requirement",
        "- Low-risk execution via a proven management approach",
    ]
    if frameworks:
        lines.append("- Mature cyber-compliance posture reduces customer risk")
    return "\n".join(lines)


def draft_outline(contract: dict, intelligence: dict, brief: dict, summary: str) -> str:
    """Return a Markdown proposal outline, Claude-generated when possible."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _deterministic_outline(contract, intelligence, brief)

    try:
        import anthropic
    except ImportError:
        print("dispatch: `anthropic` not installed; using deterministic outline.", file=sys.stderr)
        return _deterministic_outline(contract, intelligence, brief)

    payload = {
        "contract": {
            k: contract.get(k)
            for k in ("title", "agency", "solicitation_number", "response_date")
        },
        "summary": summary,
        "brief": brief,
        "intelligence": intelligence,
    }
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": "Draft the proposal outline.\n\n" + json.dumps(payload, indent=2),
                }
            ],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or _deterministic_outline(contract, intelligence, brief)
    except Exception as exc:  # never break the workflow on a draft
        print(f"dispatch: proposal agent failed ({exc}); using deterministic outline.",
              file=sys.stderr)
        return _deterministic_outline(contract, intelligence, brief)
