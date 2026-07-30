"""NAICS / SIN extraction rule module.

Deterministic regex extraction of NAICS codes (6-digit) and GSA Schedule SIN
codes (e.g. 54151S, 511210) from the contract's combined text.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "naics_sin_extraction"
VERSION = "1.0.0"

# NAICS: exactly 6 digits, not embedded in a longer number.
_NAICS_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
# SIN: 5-6 digit/letter GSA schedule codes like 54151S, 33411, OLM, 561730.
_SIN_RE = re.compile(r"\bSIN[s]?[:\s]+([0-9A-Z]{3,10}(?:\s*,\s*[0-9A-Z]{3,10})*)", re.IGNORECASE)


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts)


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    naics = sorted(set(_NAICS_RE.findall(text)))

    sins: list[str] = []
    for group in _SIN_RE.findall(text):
        for code in re.split(r"\s*,\s*", group):
            code = code.strip().upper()
            if code:
                sins.append(code)
    sins = sorted(set(sins))

    flags = []
    if not naics:
        flags.append("naics_missing")
    if len(naics) > 1:
        flags.append("multiple_naics")

    return RuleResult(
        module=NAME,
        version=VERSION,
        flags=flags,
        findings={"naics": naics, "sins": sins},
    )
