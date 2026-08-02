"""Intelligence extraction agent — Claude-backed (with deterministic fallback).

Per the architecture (section 7.1), this is the third Claude agent: it performs
deeper, non-deterministic analysis BEYOND the deterministic rule modules.  Given a
contract and the structured rule-module outputs, it produces an enriched
intelligence brief highlighting cross-module patterns, strategic implications,
and competitive-landscape observations that pure rule logic cannot surface.

Falls back to a deterministic extraction (reformatting rule outputs) when the
Anthropic API key is not configured or the call fails, so the pipeline runs
end-to-end offline.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

MODEL = os.environ.get("DISPATCH_MODEL", "claude-opus-4-8")
MAX_TOKENS = 600

_SYSTEM = (
    "You are the intelligence extraction agent in a government-contract "
    "intelligence pipeline. You receive one contract and the structured JSON "
    "output of nine deterministic rule modules. Your job is to surface "
    "cross-module patterns, strategic implications, and competitive-landscape "
    "observations that individual rules cannot detect on their own. "
    "Produce a JSON object with exactly these keys:\n"
    "  strategic_assessment — one-paragraph strategic overview\n"
    "  cross_module_findings — array of {finding, modules, implication} objects\n"
    "  competitive_factors — array of short strings\n"
    "  risk_level — one of: low, moderate, elevated, high\n"
    "  pursuit_readiness — one of: ready, conditional, not_ready\n"
    "Ground every observation in the provided data; do not invent facts."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "strategic_assessment": {"type": "string"},
        "cross_module_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "modules": {"type": "array", "items": {"type": "string"}},
                    "implication": {"type": "string"},
                },
                "required": ["finding", "modules", "implication"],
            },
        },
        "competitive_factors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "moderate", "elevated", "high"],
        },
        "pursuit_readiness": {
            "type": "string",
            "enum": ["ready", "conditional", "not_ready"],
        },
    },
    "required": [
        "strategic_assessment",
        "cross_module_findings",
        "competitive_factors",
        "risk_level",
        "pursuit_readiness",
    ],
    "additionalProperties": False,
}

_CONTRACT_FIELDS = (
    "title",
    "agency",
    "solicitation_number",
    "estimated_value",
    "response_date",
    "description",
)

RISK_LEVELS = ("low", "moderate", "elevated", "high")
READINESS_VALUES = ("ready", "conditional", "not_ready")


def _deterministic_extraction(
    contract: dict, intelligence: dict, flags: list[str],
) -> dict[str, Any]:
    """Offline extraction that reformats rule outputs into the enriched shape."""
    sa = intelligence.get("set_aside_detection", {}).get("findings", {})
    ns = intelligence.get("naics_sin_extraction", {}).get("findings", {})
    cyber = intelligence.get("cyber_compliance_readiness", {}).get("findings", {})
    pricing = intelligence.get("pricing_anomaly", {}).get("findings", {})
    foreign = intelligence.get("foreign_influence_indicators", {}).get("findings", {})
    vendor = intelligence.get("vendor_network_indicators", {}).get("findings", {})
    sub = intelligence.get("subcontractor_dominance", {}).get("findings", {})
    jv = intelligence.get("jv_mp_structure", {}).get("findings", {})

    findings: list[dict] = []
    competitive: list[str] = []

    set_asides = sa.get("set_asides", [])
    if set_asides:
        findings.append({
            "finding": f"Set-aside detected: {', '.join(set_asides)}",
            "modules": ["set_aside_detection"],
            "implication": "Limits competition to qualifying small businesses.",
        })
        competitive.append(f"Set-aside pool: {', '.join(set_asides)}")

    naics = ns.get("naics", [])
    if naics and set_asides:
        findings.append({
            "finding": f"NAICS {', '.join(naics)} with {', '.join(set_asides)} set-aside",
            "modules": ["naics_sin_extraction", "set_aside_detection"],
            "implication": "Verify small-business size standard for these NAICS codes.",
        })

    frameworks = cyber.get("frameworks", [])
    if frameworks and pricing.get("estimated_value"):
        findings.append({
            "finding": f"Cyber frameworks ({', '.join(frameworks)}) on a "
                       f"${pricing['estimated_value']:,.0f} contract",
            "modules": ["cyber_compliance_readiness", "pricing_anomaly"],
            "implication": "Compliance cost may affect pricing competitiveness.",
        })

    if foreign.get("indicators"):
        competitive.append("Foreign-influence indicators present — may limit teaming")

    if vendor.get("indicators", {}).get("limited_competition"):
        competitive.append("Sole-source/limited-competition indicators suggest incumbent advantage")

    if sub.get("subcontracting_plan_required"):
        competitive.append("Subcontracting plan required — teaming strategy needed")

    if jv.get("joint_venture") or jv.get("mentor_protege"):
        competitive.append("JV/mentor-protege arrangements referenced")

    cyber_flags = [f for f in flags if f in (
        "cyber_requirements_present", "cmmc_level_2_or_higher", "sensitive_data_handling",
    )]
    value_flags = [f for f in flags if f in ("value_below_band", "value_above_band")]

    if cyber_flags and value_flags:
        risk = "high"
    elif cyber_flags or value_flags:
        risk = "elevated"
    elif len(flags) > 3:
        risk = "moderate"
    else:
        risk = "low"

    if set_asides and not value_flags:
        readiness = "ready"
    elif set_asides or naics:
        readiness = "conditional"
    else:
        readiness = "not_ready"

    title = contract.get("title", "Unknown")
    agency = contract.get("agency", "Unknown")
    assessment = (
        f"{title} from {agency} — {len(flags)} flag(s) raised across "
        f"{len(intelligence)} rule modules. "
        f"Risk level: {risk}. Pursuit readiness: {readiness}."
    )

    return {
        "strategic_assessment": assessment,
        "cross_module_findings": findings,
        "competitive_factors": competitive,
        "risk_level": risk,
        "pursuit_readiness": readiness,
    }


def _valid(result: object) -> bool:
    return (
        isinstance(result, dict)
        and isinstance(result.get("strategic_assessment"), str)
        and result["strategic_assessment"]
        and isinstance(result.get("cross_module_findings"), list)
        and isinstance(result.get("competitive_factors"), list)
        and result.get("risk_level") in RISK_LEVELS
        and result.get("pursuit_readiness") in READINESS_VALUES
    )


def extract(
    contract: dict, intelligence: dict, flags: list[str],
) -> dict[str, Any]:
    """Return an enriched intelligence brief, Claude-generated when possible."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _deterministic_extraction(contract, intelligence, flags)

    try:
        import anthropic
    except ImportError:
        print("dispatch: `anthropic` not installed; using deterministic extraction.",
              file=sys.stderr)
        return _deterministic_extraction(contract, intelligence, flags)

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
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": "Extract enriched intelligence from this contract.\n\n"
                    + json.dumps(payload, indent=2),
                }
            ],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        result = json.loads(text)
        if _valid(result):
            return result
        print("dispatch: extraction agent returned invalid result; using deterministic extraction.",
              file=sys.stderr)
    except Exception as exc:
        print(f"dispatch: extraction agent failed ({exc}); using deterministic extraction.",
              file=sys.stderr)

    return _deterministic_extraction(contract, intelligence, flags)
