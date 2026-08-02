"""Routing-decision agent — Claude-backed (with deterministic fallback).

Consumes all rule-module intelligence plus the summary and produces a structured
`routing_decision` recommendation:

    {action, reason, priority, recipient, notes}

`action` is one of the Control Layer's action keys (see control.ACTIONS), so the
orchestrator can resolve it to a route. This is a RECOMMENDATION — the human still
makes the final call via the email control system; the recommendation is shown in
the email and archived alongside the human's decision.

Claude path uses structured outputs (json_schema) for a guaranteed shape. Falls
back to a deterministic rule-based decision when Claude is unavailable or returns
something invalid, so the pipeline runs end-to-end offline.
"""

from __future__ import annotations

import json
import os
import sys

from cin_lite.control import ACTIONS

MODEL = os.environ.get("DISPATCH_MODEL", "claude-opus-4-8")
MAX_TOKENS = 500

PRIORITIES = ("low", "medium", "high", "urgent")

# Where each action routes its contract for human follow-up.
_RECIPIENTS = {
    "approve_proposal": "proposal-team",
    "approve_archive": "archive-system",
    "reject": "none",
    "flag_review": "review-queue",
    "deeper_analysis": "analysis-queue",
}

_SYSTEM = (
    "You are the routing-decision agent in a government-contract intelligence "
    "pipeline. You are given one contract, the JSON output of deterministic rule "
    "modules, and a human-readable summary. Recommend exactly one routing action "
    "for a human reviewer. Weigh: set-aside qualification (pursue qualifying "
    "set-asides), NAICS/SIN fit, pricing anomalies (flag for human verification), "
    "and cyber-compliance burden (higher burden raises priority). Choose the "
    "action, a one-sentence reason grounded in the rule findings, a priority, the "
    "recipient queue, and any notes the reviewer should see. Do not invent facts."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "reason": {"type": "string"},
        "priority": {"type": "string", "enum": list(PRIORITIES)},
        "recipient": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["action", "reason", "priority", "recipient", "notes"],
    "additionalProperties": False,
}

_CONTRACT_FIELDS = (
    "title",
    "agency",
    "solicitation_number",
    "estimated_value",
    "response_date",
)


def _facts(intelligence: dict, flags: list[str]) -> dict:
    """Pull the decision-relevant findings out of the rule intelligence."""
    sa = intelligence.get("set_aside_detection", {}).get("findings", {})
    ns = intelligence.get("naics_sin_extraction", {}).get("findings", {})
    cyber = intelligence.get("cyber_compliance_readiness", {}).get("findings", {})
    return {
        "set_asides": sa.get("set_asides", []),
        "naics": ns.get("naics", []),
        "sins": ns.get("sins", []),
        "cyber_burden": cyber.get("readiness_burden", "none"),
        "has_set_aside": "set_aside_present" in flags,
        "cyber_present": "cyber_requirements_present" in flags,
        "cyber_high": "cmmc_level_2_or_higher" in flags or "sensitive_data_handling" in flags,
        # Out-of-band values are real anomalies worth human review. A missing value
        # is expected for most solicitations, so it's informational only.
        "value_anomaly": any(f in flags for f in ("value_below_band", "value_above_band")),
        "value_missing": "value_missing" in flags,
        "value_round": "suspiciously_round" in flags,
    }


def _deterministic_decision(intelligence: dict, flags: list[str]) -> dict:
    """Auditable rule-based routing used when Claude is unavailable."""
    f = _facts(intelligence, flags)

    if f["value_anomaly"]:
        action, priority = "flag_review", "high"
        reason = "Estimated value is outside the expected band; route to a human to verify before pursuit."
    elif not f["has_set_aside"]:
        action, priority = "deeper_analysis", "medium"
        reason = "No set-aside detected; assess full-and-open competitiveness before committing."
    else:
        action = "approve_proposal"
        priority = "high" if f["cyber_high"] else "medium"
        reason = (
            f"Qualifying set-aside ({', '.join(f['set_asides']) or 'present'}) with "
            f"{f['cyber_burden']} cyber-compliance burden; recommend pursuing a proposal."
        )

    notes_bits = []
    if f["naics"]:
        notes_bits.append(f"NAICS {', '.join(f['naics'])}")
    if f["sins"]:
        notes_bits.append(f"SIN {', '.join(f['sins'])}")
    if f["cyber_present"]:
        notes_bits.append(f"cyber burden: {f['cyber_burden']}")
    if f["value_round"]:
        notes_bits.append("estimated value is suspiciously round")
    if f["value_missing"]:
        notes_bits.append("no estimated value published")
    notes = "; ".join(notes_bits) or "no additional indicators"

    return {
        "action": action,
        "reason": reason,
        "priority": priority,
        "recipient": _RECIPIENTS.get(action, "review-queue"),
        "notes": notes,
    }


def _valid(decision: object) -> bool:
    return (
        isinstance(decision, dict)
        and decision.get("action") in ACTIONS
        and decision.get("priority") in PRIORITIES
        and all(isinstance(decision.get(k), str) and decision[k] for k in ("reason", "recipient", "notes"))
    )


def decide(contract: dict, intelligence: dict, summary: str, flags: list[str]) -> dict:
    """Return a routing_decision dict, Claude-generated when possible."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _deterministic_decision(intelligence, flags)

    try:
        import anthropic
    except ImportError:
        print("dispatch: `anthropic` not installed; using deterministic routing.", file=sys.stderr)
        return _deterministic_decision(intelligence, flags)

    payload = {
        "contract": {k: contract.get(k) for k in _CONTRACT_FIELDS},
        "summary": summary,
        "intelligence": intelligence,
        "flags": flags,
    }

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": "Recommend a routing action for this contract.\n\n"
                    + json.dumps(payload, indent=2),
                }
            ],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        decision = json.loads(text)
        if _valid(decision):
            # Normalize recipient to the canonical queue for the chosen action.
            decision["recipient"] = _RECIPIENTS.get(decision["action"], decision["recipient"])
            return decision
        print("dispatch: routing agent returned an invalid decision; using deterministic routing.",
              file=sys.stderr)
    except Exception as exc:  # never break the pipeline on a recommendation
        print(f"dispatch: routing agent failed ({exc}); using deterministic routing.",
              file=sys.stderr)

    return _deterministic_decision(intelligence, flags)
