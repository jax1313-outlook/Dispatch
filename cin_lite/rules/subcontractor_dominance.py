"""Subcontractor dominance rule module.

Deterministic detection plus a heuristic score for the risk that subcontractors
dominate the work (prime acting as a pass-through). Subcontractor emphasis raises
the signal; protective requirements (Limitations on Subcontracting, a stated
self-performance floor) lower it. Explicit weights keep the score auditable.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "subcontractor_dominance"
VERSION = "1.0.0"

_SUBCONTRACT_TERMS = ["subcontractor", "subcontracting", "subcontract"]
_LIMITATIONS = [
    "limitations on subcontracting", "limitation on subcontracting", "52.219-14",
]
_SELF_PERFORM = [
    "self-perform", "self perform", "perform at least", "primarily perform",
    "percentage of work performed by the prime", "percent of the cost",
]
_PLAN = ["small business subcontracting plan", "subcontracting plan"]
_PERCENT_RE = re.compile(r"(\d{1,3})\s*(?:%|percent)")

_WEIGHTS = {"emphasis_high": 3, "emphasis_low": 1, "plan": 1, "limitations": -2, "self_perform": -2}


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    mentions = sum(text.count(term) for term in _SUBCONTRACT_TERMS)
    limitations = any(n in text for n in _LIMITATIONS)
    self_perform = any(n in text for n in _SELF_PERFORM)
    plan_required = any(n in text for n in _PLAN)
    percentages = sorted({int(p) for p in _PERCENT_RE.findall(text)})

    score = 0
    if mentions >= 3:
        score += _WEIGHTS["emphasis_high"]
    elif mentions >= 1:
        score += _WEIGHTS["emphasis_low"]
    if plan_required:
        score += _WEIGHTS["plan"]
    if limitations:
        score += _WEIGHTS["limitations"]
    if self_perform:
        score += _WEIGHTS["self_perform"]
    score = max(0, score)

    # Max attainable score is 4 (heavy emphasis + plan, no mitigations), so the
    # top bucket lands at >= 4.
    if score == 0:
        risk = "none"
    elif score <= 2:
        risk = "low"
    elif score == 3:
        risk = "moderate"
    else:
        risk = "elevated"

    flags: list[str] = []
    flags.append("subcontractor_dominance_signal" if score > 0 else "no_subcontractor_dominance")
    if limitations:
        flags.append("limitations_on_subcontracting")
    if plan_required:
        flags.append("subcontracting_plan_required")

    signals: list[str] = []
    if mentions:
        signals.append(f"{mentions} subcontracting reference(s)")
    if plan_required:
        signals.append("subcontracting plan required")
    if limitations:
        signals.append("limitations-on-subcontracting clause (mitigating)")
    if self_perform:
        signals.append("self-performance floor stated (mitigating)")
    summary = (
        f"{risk.capitalize()} subcontractor-dominance signal: " + "; ".join(signals) + "."
        if signals
        else "No subcontractor-dominance signals detected."
    )

    findings = {
        "subcontract_mentions": mentions,
        "limitations_on_subcontracting": limitations,
        "self_performance_required": self_perform,
        "subcontracting_plan_required": plan_required,
        "percentages": percentages,
        "dominance_risk": risk,
    }

    return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings,
                      summary=summary, score=score)
