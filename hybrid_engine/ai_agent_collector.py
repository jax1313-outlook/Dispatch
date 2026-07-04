"""AI Agent Collector — assembles structured outputs from multiple Claude agents
into a unified BidPackage and persists to the archive.

This module receives validated JSON from five agent roles:
  - PARSER (solicitation metadata)
  - COMPLIANCE_ANALYST (compliance flags and recommendation)
  - BID_WRITER x3 (executive_summary, technical_approach, management_plan,
    price_narrative, past_performance)
  - RULE_ENGINE_BUILDER (deterministic rule matches)

It validates required fields, assembles a BidPackage, writes it to
data/{solicitation_id}_bid_package.json, and returns an assembly summary.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ComplianceFlag(BaseModel):
    """Single compliance flag from the COMPLIANCE_ANALYST agent."""

    code: str
    description: str
    severity: str = Field(description="PASS | WARN | FAIL")
    detail: str = ""


class ComplianceResult(BaseModel):
    """Full compliance analysis output."""

    solicitation_id: str
    score: int = Field(ge=0, le=100)
    recommendation: str = Field(description="BID | NO_BID | REVIEW")
    flags: list[ComplianceFlag] = Field(default_factory=list)


class BidComponent(BaseModel):
    """A single bid-writing component (one section of the proposal)."""

    section: str
    content: str


class RuleMatch(BaseModel):
    """A single deterministic rule match from the RULE_ENGINE_BUILDER agent."""

    id: str
    name: str
    field: str
    operator: str
    value: Any
    action: str = Field(description="PASS | WARN | FAIL")


class SolicitationMetadata(BaseModel):
    """Parsed solicitation metadata from the PARSER agent."""

    solicitation_id: str
    title: str = ""
    agency: str = ""
    naics_code: str = ""
    set_aside: str = ""
    due_date: str = ""
    estimated_value: float = 0.0
    performance_location: str = ""
    description: str = ""
    keywords: list[str] = Field(default_factory=list)


class BidPackage(BaseModel):
    """Complete assembled bid package combining all agent outputs."""

    solicitation_id: str
    assembled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: SolicitationMetadata
    compliance: ComplianceResult
    bid_components: dict[str, str] = Field(default_factory=dict)
    rule_matches: list[RuleMatch] = Field(default_factory=list)
    component_count: int = 0
    missing_components: list[str] = Field(default_factory=list)
    overall_status: str = "FAILED"


class AssemblySummary(BaseModel):
    """Summary returned after bid package assembly."""

    solicitation_id: str
    component_count: int
    missing_components: list[str]
    overall_status: str
    output_path: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_BID_SECTIONS = [
    "executive_summary",
    "technical_approach",
    "management_plan",
    "price_narrative",
    "past_performance",
]

DATA_DIR = Path("data")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_parser_output(data: dict) -> SolicitationMetadata | None:
    """Validate and parse the PARSER agent output."""
    if not data.get("solicitation_id"):
        logger.error("Parser output missing required field: solicitation_id")
        return None
    try:
        return SolicitationMetadata(**data)
    except Exception as exc:
        logger.error(f"Parser output validation failed: {exc}")
        return None


def _validate_compliance_output(data: dict) -> ComplianceResult | None:
    """Validate and parse the COMPLIANCE_ANALYST agent output."""
    required = {"solicitation_id", "score", "recommendation", "flags"}
    missing = required - set(data.keys())
    if missing:
        logger.error(f"Compliance output missing required fields: {missing}")
        return None
    try:
        return ComplianceResult(**data)
    except Exception as exc:
        logger.error(f"Compliance output validation failed: {exc}")
        return None


def _validate_bid_components(components: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Validate bid components dict and return (valid_components, missing_sections)."""
    valid: dict[str, str] = {}
    missing: list[str] = []
    for section in REQUIRED_BID_SECTIONS:
        content = components.get(section, "").strip()
        if content:
            valid[section] = content
        else:
            missing.append(section)
            logger.warning(f"Bid component missing or empty: {section}")
    return valid, missing


def _validate_rule_matches(data: list[dict]) -> list[RuleMatch]:
    """Validate and parse RULE_ENGINE_BUILDER output."""
    matches: list[RuleMatch] = []
    for item in data:
        try:
            matches.append(RuleMatch(**item))
        except Exception as exc:
            logger.warning(f"Skipping invalid rule match: {exc}")
    return matches


# ---------------------------------------------------------------------------
# Core assembly
# ---------------------------------------------------------------------------

def assemble_bid_package(
    parser_output: dict,
    compliance_output: dict,
    bid_components: dict[str, str],
    rule_matches: list[dict],
) -> dict[str, Any]:
    """Assemble a complete BidPackage from agent outputs and persist to disk.

    Args:
        parser_output: Structured JSON from the PARSER agent (solicitation metadata).
        compliance_output: Structured JSON from the COMPLIANCE_ANALYST agent.
        bid_components: Dict mapping section names to content strings from BID_WRITER agents.
        rule_matches: List of rule match dicts from the RULE_ENGINE_BUILDER agent.

    Returns:
        Summary dict with solicitation_id, component_count, missing_components,
        overall_status, and output_path.
    """
    logger.info("Beginning bid package assembly")

    # Validate parser output
    metadata = _validate_parser_output(parser_output)
    if metadata is None:
        logger.error("Assembly aborted: invalid parser output")
        return AssemblySummary(
            solicitation_id=parser_output.get("solicitation_id", "UNKNOWN"),
            component_count=0,
            missing_components=REQUIRED_BID_SECTIONS.copy(),
            overall_status="FAILED",
            output_path="",
        ).model_dump()

    solicitation_id = metadata.solicitation_id
    logger.info(f"Assembling bid package for {solicitation_id}")

    # Validate compliance output
    compliance = _validate_compliance_output(compliance_output)
    if compliance is None:
        logger.error(f"Assembly failed for {solicitation_id}: invalid compliance output")
        return AssemblySummary(
            solicitation_id=solicitation_id,
            component_count=0,
            missing_components=REQUIRED_BID_SECTIONS.copy(),
            overall_status="FAILED",
            output_path="",
        ).model_dump()

    # Validate bid components
    valid_components, missing = _validate_bid_components(bid_components)
    component_count = len(valid_components)

    # Validate rule matches
    validated_rules = _validate_rule_matches(rule_matches)
    logger.info(f"Validated {len(validated_rules)} rule matches")

    # Determine overall status
    if component_count == len(REQUIRED_BID_SECTIONS):
        overall_status = "COMPLETE"
    elif component_count > 0:
        overall_status = "PARTIAL"
    else:
        overall_status = "FAILED"

    logger.info(
        f"Assembly status: {overall_status} "
        f"({component_count}/{len(REQUIRED_BID_SECTIONS)} components)"
    )

    # Build the package
    package = BidPackage(
        solicitation_id=solicitation_id,
        metadata=metadata,
        compliance=compliance,
        bid_components=valid_components,
        rule_matches=validated_rules,
        component_count=component_count,
        missing_components=missing,
        overall_status=overall_status,
    )

    # Persist to disk
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / f"{solicitation_id}_bid_package.json"
    output_path.write_text(json.dumps(package.model_dump(), indent=2, default=str))
    logger.info(f"Bid package saved to {output_path}")

    return AssemblySummary(
        solicitation_id=solicitation_id,
        component_count=component_count,
        missing_components=missing,
        overall_status=overall_status,
        output_path=str(output_path),
    ).model_dump()
