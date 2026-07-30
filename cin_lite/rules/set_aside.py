"""Set-aside detection rule module.

Deterministic keyword scan over the contract's combined text. Detects common
federal set-aside designations. No LLM, no network — same input always yields
the same output.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "set_aside_detection"
VERSION = "1.0.0"

# Ordered most-specific phrasing first; matching is case-insensitive substring.
_SET_ASIDES: list[tuple[str, list[str]]] = [
    ("8(a)", ["8(a)", "8a set-aside", "section 8(a)"]),
    ("SDVOSB", ["sdvosb", "service-disabled veteran", "service disabled veteran"]),
    ("VOSB", ["vosb", "veteran-owned small business"]),
    ("WOSB", ["wosb", "woman-owned small business", "women-owned small business"]),
    ("EDWOSB", ["edwosb", "economically disadvantaged woman"]),
    ("HUBZone", ["hubzone", "hub zone"]),
    ("Total Small Business", ["total small business set-aside", "total small business set aside"]),
    ("Small Business", ["small business set-aside", "small business set aside"]),
]


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def _matches(needle: str, text: str) -> bool:
    # Boundary-aware match so short acronyms (VOSB) don't match inside longer
    # ones (SDVOSB). Boundaries are non-alphanumeric, which also tolerates the
    # parentheses in "8(a)".
    pattern = r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text) is not None


def run(contract: dict) -> RuleResult:
    text = _text(contract)
    detected: list[str] = []
    for label, needles in _SET_ASIDES:
        if any(_matches(n, text) for n in needles):
            detected.append(label)

    flags = []
    if detected:
        flags.append("set_aside_present")
    else:
        flags.append("full_and_open_or_unspecified")

    return RuleResult(
        module=NAME,
        version=VERSION,
        flags=flags,
        findings={"set_asides": detected, "count": len(detected)},
    )
