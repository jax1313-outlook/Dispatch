"""Summarization agent — Claude-backed.

Replaces the deterministic placeholder summary with a Claude-generated summary of
the contract plus the rule-module intelligence. This is a NON-deterministic helper
and sits OUTSIDE the deterministic rule path (the rules in cin_lite/rules/ stay
deterministic per the architecture).

Single Messages API call via the official `anthropic` SDK. Falls back to a
deterministic summary when the SDK isn't installed, no API key is configured, or
the call fails — so the Phase-1 pipeline still runs end-to-end offline.

Configuration (environment):
    ANTHROPIC_API_KEY   required to use Claude (else deterministic fallback)
    DISPATCH_MODEL      optional model override (default: claude-opus-4-8)
"""

from __future__ import annotations

import json
import os
import sys

# Default to the latest, most capable Claude model. Override via DISPATCH_MODEL.
MODEL = os.environ.get("DISPATCH_MODEL", "claude-opus-4-8")
MAX_TOKENS = 400

_SYSTEM = (
    "You are the summarization agent in a government-contract intelligence "
    "pipeline. You are given one contract and the JSON output of deterministic "
    "rule modules that have already analyzed it. Write a concise 2-3 sentence "
    "summary for a human reviewer who is deciding whether to pursue the contract. "
    "Lead with the most decision-relevant facts: set-aside type, NAICS/SIN codes, "
    "pricing flags, and cyber-compliance burden. Be factual and do not invent "
    "details beyond the provided data. Output only the summary, no preamble."
)

# Only these contract fields are sent to the model.
_CONTRACT_FIELDS = (
    "title",
    "agency",
    "solicitation_number",
    "estimated_value",
    "response_date",
    "description",
)


def _deterministic_summary(contract: dict, flags: list[str]) -> str:
    """Offline stand-in used when Claude is unavailable."""
    return (
        f"{contract.get('title')} ({contract.get('agency')}) — "
        f"est. {contract.get('estimated_value')}, due {contract.get('response_date')}. "
        f"{len(flags)} flag(s): {', '.join(flags) if flags else 'none'}."
    )


def summarize(contract: dict, intelligence: dict, flags: list[str]) -> str:
    """Return a human-readable summary, Claude-generated when possible."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _deterministic_summary(contract, flags)

    try:
        import anthropic
    except ImportError:
        print("dispatch: `anthropic` not installed; using deterministic summary.", file=sys.stderr)
        return _deterministic_summary(contract, flags)

    payload = {
        "contract": {k: contract.get(k) for k in _CONTRACT_FIELDS},
        "intelligence": intelligence,
        "flags": flags,
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
                    "content": "Summarize this contract for the reviewer.\n\n"
                    + json.dumps(payload, indent=2),
                }
            ],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or _deterministic_summary(contract, flags)
    except Exception as exc:  # never break the human-in-the-loop pipeline on a summary
        print(f"dispatch: summarization agent failed ({exc}); using deterministic summary.",
              file=sys.stderr)
        return _deterministic_summary(contract, flags)
