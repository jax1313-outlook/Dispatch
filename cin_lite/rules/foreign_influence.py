"""Foreign-influence indicators rule module.

Deterministic detection plus a heuristic sensitivity score for foreign
ownership/control/influence (FOCI), export control (ITAR/EAR), U.S.-person /
citizenship restrictions, security-clearance requirements, and supply-chain
prohibitions (Section 889). Explicit weights keep the score auditable.
"""

from __future__ import annotations

from .base import RuleResult

NAME = "foreign_influence_indicators"
VERSION = "1.0.0"

_EXPORT_CONTROL = {
    "ITAR": ["itar", "international traffic in arms"],
    "EAR": ["export administration regulations", " ear ", "export-controlled", "export controlled"],
    "export control": ["export control"],
}
_FOCI = ["foreign ownership", "foreign control", "foreign influence", "foci", "foreign owned"]
_US_PERSONS = ["u.s. persons only", "us persons only", "u.s. person", "united states person"]
_CITIZENSHIP = ["u.s. citizen", "us citizen", "citizenship", "must be a citizen"]
_CLEARANCE = [
    "security clearance", "secret clearance", "top secret", "ts/sci",
    "facility clearance", "personnel clearance",
]
_SECTION_889 = ["section 889", "covered telecommunications", "huawei", "zte", "prohibited telecommunications"]

_WEIGHTS = {
    "export_control": 2,
    "foci": 3,
    "section_889": 2,
    "us_persons": 1,
    "citizenship": 1,
    "clearance": 1,
}


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    export_control = sorted(
        label for label, needles in _EXPORT_CONTROL.items() if any(n in text for n in needles)
    )
    foci = any(n in text for n in _FOCI)
    us_persons = any(n in text for n in _US_PERSONS)
    citizenship = any(n in text for n in _CITIZENSHIP)
    clearance = any(n in text for n in _CLEARANCE)
    section_889 = any(n in text for n in _SECTION_889)

    score = 0
    signals: list[str] = []
    if export_control:
        score += _WEIGHTS["export_control"]
        signals.append("export control (" + ", ".join(export_control) + ")")
    if foci:
        score += _WEIGHTS["foci"]
        signals.append("foreign ownership/control/influence")
    if section_889:
        score += _WEIGHTS["section_889"]
        signals.append("Section 889 supply-chain prohibition")
    if us_persons:
        score += _WEIGHTS["us_persons"]
        signals.append("U.S. persons only")
    if citizenship:
        score += _WEIGHTS["citizenship"]
        signals.append("U.S. citizenship required")
    if clearance:
        score += _WEIGHTS["clearance"]
        signals.append("security clearance required")

    if score == 0:
        sensitivity = "none"
    elif score <= 2:
        sensitivity = "low"
    elif score <= 5:
        sensitivity = "moderate"
    else:
        sensitivity = "elevated"

    flags: list[str] = []
    flags.append("foreign_influence_signals" if score > 0 else "no_foreign_influence_signals")
    if export_control:
        flags.append("export_controlled")
    if foci:
        flags.append("foci_indicator")
    if section_889:
        flags.append("section_889")
    if clearance:
        flags.append("clearance_required")

    summary = (
        f"{sensitivity.capitalize()} foreign-influence sensitivity: " + "; ".join(signals) + "."
        if signals
        else "No foreign-influence indicators detected."
    )

    findings = {
        "export_control": export_control,
        "foci": foci,
        "us_persons_only": us_persons,
        "citizenship_required": citizenship,
        "clearance_required": clearance,
        "section_889": section_889,
        "sensitivity": sensitivity,
    }

    return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings,
                      summary=summary, score=score)
