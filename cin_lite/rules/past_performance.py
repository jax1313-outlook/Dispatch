"""Past-performance relevance rule module.

Deterministic detection plus a heuristic score for how heavily a solicitation
weighs past performance: an explicit PP requirement, relevance dimensions
(scope/size/complexity), CPARS, reference/questionnaire requirements, and a
recency window. Explicit weights keep the demand score auditable.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "past_performance_relevance"
VERSION = "1.0.0"

_RELEVANCE_DIMS = [
    "similar in scope", "similar in size", "similar in complexity", "scope and complexity",
    "comparable", "relevant experience", "corporate experience", "relevancy", "relevant",
]
_CPARS = ["cpars", "contractor performance assessment"]
_REFERENCES = ["past performance questionnaire", "reference questionnaire", "ppq", "references"]
_YEARS_RE = re.compile(r"(\d+)\s*-?\s*year")

_WEIGHTS = {"requires_pp": 2, "relevance": 1, "cpars": 1, "references": 1, "recency": 1}


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    requires_pp = "past performance" in text
    relevance_factors = sorted({d for d in _RELEVANCE_DIMS if d in text})
    cpars = any(n in text for n in _CPARS)
    references = any(n in text for n in _REFERENCES)
    recency_years = sorted({int(y) for y in _YEARS_RE.findall(text)})

    score = 0
    signals: list[str] = []
    if requires_pp:
        score += _WEIGHTS["requires_pp"]
        signals.append("past performance required")
    if relevance_factors:
        score += _WEIGHTS["relevance"]
        signals.append("relevance by " + ", ".join(relevance_factors))
    if cpars:
        score += _WEIGHTS["cpars"]
        signals.append("CPARS evaluated")
    if references:
        score += _WEIGHTS["references"]
        signals.append("references/questionnaire required")
    if recency_years:
        score += _WEIGHTS["recency"]
        signals.append(f"recency window: {max(recency_years)} years")

    if score == 0:
        demand = "none"
    elif score <= 2:
        demand = "low"
    elif score <= 4:
        demand = "moderate"
    else:
        demand = "high"

    flags: list[str] = []
    if score == 0:
        flags.append("no_past_performance_emphasis")
    else:
        flags.append("past_performance_required" if requires_pp else "past_performance_signals")
    if demand == "high":
        flags.append("pp_high_demand")

    summary = (
        f"{demand.capitalize()} past-performance demand: " + "; ".join(signals) + "."
        if signals
        else "No past-performance emphasis detected."
    )

    findings = {
        "requires_past_performance": requires_pp,
        "relevance_factors": relevance_factors,
        "cpars": cpars,
        "references_required": references,
        "recency_years": recency_years,
        "demand": demand,
    }

    return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings,
                      summary=summary, score=score)
