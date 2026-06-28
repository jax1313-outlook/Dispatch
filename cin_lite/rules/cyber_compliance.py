"""Cyber compliance readiness rule module.

Deterministic scan for cybersecurity compliance requirements a contract imposes
on offerors: CMMC level, NIST control families, DFARS safeguarding, FedRAMP,
FISMA, CUI/ITAR handling, and POA&M / SSP expectations. Emits structured JSON
findings plus a human-readable summary.

No LLM, no network — same input always yields the same output.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "cyber_compliance_readiness"
VERSION = "1.0.0"

# framework label -> case-insensitive substrings that indicate it.
_FRAMEWORKS: list[tuple[str, list[str]]] = [
    ("CMMC", ["cmmc", "cybersecurity maturity model"]),
    ("NIST SP 800-171", ["800-171", "800 171", "nist sp 800-171"]),
    ("NIST SP 800-53", ["800-53", "800 53", "nist sp 800-53"]),
    ("DFARS 252.204-7012", ["252.204-7012", "dfars 7012", "dfars clause"]),
    ("FedRAMP", ["fedramp", "fed ramp"]),
    ("FISMA", ["fisma"]),
    ("CUI handling", ["cui", "controlled unclassified information"]),
    ("ITAR", ["itar", "international traffic in arms"]),
    ("POA&M", ["poa&m", "poam", "plan of action and milestones"]),
    ("SSP", ["system security plan", "ssp"]),
]

# Detect an explicit CMMC level, e.g. "CMMC Level 2", "CMMC L3".
_CMMC_LEVEL_RE = re.compile(r"cmmc\s*(?:level|l)\s*([123])", re.IGNORECASE)

# Each detected framework contributes to a coarse readiness-burden score.
_FRAMEWORK_WEIGHT = 1
_CMMC_LEVEL_WEIGHT = {1: 1, 2: 3, 3: 5}


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    frameworks = [label for label, needles in _FRAMEWORKS if any(n in text for n in needles)]

    cmmc_level = None
    match = _CMMC_LEVEL_RE.search(text)
    if match:
        cmmc_level = int(match.group(1))

    # Coarse, auditable burden score: more frameworks + higher CMMC = heavier lift.
    burden = len(frameworks) * _FRAMEWORK_WEIGHT
    if cmmc_level:
        burden += _CMMC_LEVEL_WEIGHT[cmmc_level]

    if burden == 0:
        readiness_burden = "none"
    elif burden <= 3:
        readiness_burden = "low"
    elif burden <= 7:
        readiness_burden = "moderate"
    else:
        readiness_burden = "high"

    flags: list[str] = []
    if frameworks or cmmc_level:
        flags.append("cyber_requirements_present")
    else:
        flags.append("no_cyber_requirements")
    if cmmc_level and cmmc_level >= 2:
        flags.append("cmmc_level_2_or_higher")
    if "CUI handling" in frameworks or "ITAR" in frameworks:
        flags.append("sensitive_data_handling")

    findings = {
        "frameworks": frameworks,
        "cmmc_level": cmmc_level,
        "framework_count": len(frameworks),
        "burden_score": burden,
        "readiness_burden": readiness_burden,
    }

    summary = _summarize(frameworks, cmmc_level, readiness_burden)

    return RuleResult(
        module=NAME,
        version=VERSION,
        flags=flags,
        findings=findings,
        summary=summary,
    )


def _summarize(frameworks: list[str], cmmc_level: int | None, readiness_burden: str) -> str:
    if not frameworks and cmmc_level is None:
        return "No explicit cybersecurity compliance requirements detected."
    parts = []
    if cmmc_level:
        parts.append(f"CMMC Level {cmmc_level} required")
    if frameworks:
        parts.append("references " + ", ".join(frameworks))
    return f"{readiness_burden.capitalize()} compliance burden: " + "; ".join(parts) + "."
