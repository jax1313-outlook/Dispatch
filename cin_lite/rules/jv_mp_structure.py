"""Joint-Venture / Mentor-Protégé structure detection rule module.

Deterministic detection plus a small heuristic count for JV and Mentor-Protégé
(MP) structures and SBA approval signals. Distinct from vendor-network teaming:
this targets the specific JV/MP eligibility structures used to qualify for awards.
"""

from __future__ import annotations

import re

from .base import RuleResult

NAME = "jv_mp_structure"
VERSION = "1.0.0"

_JV = ["joint venture", "joint-venture"]
_JV_TOKEN = re.compile(r"\bjv\b")
_MP = ["mentor-protégé", "mentor-protege", "mentor protege", "mentor protégé", "protege program"]
_SBA = ["sba-approved", "sba approved", "approved joint venture", "8(a) joint venture"]
_POPULATION = ["populated joint venture", "unpopulated joint venture"]


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    joint_venture = any(n in text for n in _JV) or bool(_JV_TOKEN.search(text))
    mentor_protege = any(n in text for n in _MP)
    sba_approved = any(n in text for n in _SBA)
    population = [n for n in _POPULATION if n in text]

    structures: list[str] = []
    if joint_venture:
        structures.append("joint venture")
    if mentor_protege:
        structures.append("mentor-protégé")
    if sba_approved:
        structures.append("SBA-approved")
    structures.extend(population)

    score = sum([joint_venture, mentor_protege, sba_approved]) + len(population)

    if score == 0:
        presence = "none"
    elif score <= 1:
        presence = "low"
    else:
        presence = "moderate"

    flags: list[str] = []
    if score == 0:
        flags.append("no_jv_mp_structure")
    else:
        flags.append("jv_mp_structure")
    if joint_venture:
        flags.append("jv_structure")
    if mentor_protege:
        flags.append("mentor_protege")

    summary = (
        "JV/MP structures referenced: " + "; ".join(structures) + "."
        if structures
        else "No JV/MP structures referenced."
    )

    findings = {
        "joint_venture": joint_venture,
        "mentor_protege": mentor_protege,
        "sba_approved": sba_approved,
        "structures": structures,
        "presence": presence,
    }

    return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings,
                      summary=summary, score=score)
