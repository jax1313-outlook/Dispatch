"""Operational Intelligence Libraries (System Rule 2) and the publisher
workflow (System Rule 4).

`LocationIntelligence` and `BrokerIntelligence` are the "capture once, use
many" (Rule 14) entities: acquisition/ingestion populates them once, and
planning, pricing, negotiation, and dispatch all read the same record rather
than each re-deriving it. They are the L2-COS replacement for cin_lite's
per-contract fields that don't recur across runs.

`IntelligenceScore` mirrors cin_lite's `RuleResult`
(cin_lite/rules/base.py) — deterministic rule-module output as structured
JSON — scoped to a 0-100 score. `InquiryArtifacts` + `PUBLISH_THRESHOLD`
implement the auto-contact/publisher trigger (Rule 4): once a load's score
reaches the threshold, the publisher workflow may fire using this fixed
document set.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Publisher workflow fires load inquiries once a load's IntelligenceScore
# reaches this threshold (System Rule 4).
PUBLISH_THRESHOLD = 90


class LocationIntelligence(BaseModel):
    """Location Intelligence Library entry — one row per facility."""

    facility_id: str
    name: str
    address: str
    gate_location: str | None = None
    dock_specs: str | None = None
    check_in_procedure: str | None = None
    security_requirements: str | None = None
    historical_problems: list[str] = Field(default_factory=list)
    last_verified_at: datetime | None = None


class BrokerIntelligence(BaseModel):
    """Broker Intelligence Library entry — one row per broker."""

    broker_id: str
    company_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    payment_terms: str | None = None
    preferred_lanes: list[str] = Field(default_factory=list)
    historical_rates: dict[str, float] = Field(default_factory=dict)
    communication_notes: list[str] = Field(default_factory=list)


class IntelligenceScore(BaseModel):
    """Deterministic rule-module output for one load (RuleResult analog)."""

    module: str
    version: str
    score: int = Field(ge=0, le=100)
    flags: list[str] = Field(default_factory=list)
    findings: dict = Field(default_factory=dict)

    @property
    def publisher_eligible(self) -> bool:
        return self.score >= PUBLISH_THRESHOLD


class InquiryArtifacts(BaseModel):
    """The fixed document packet the publisher workflow attaches to an
    outbound load inquiry (System Rule 4)."""

    business_card: bool = False
    w9: bool = False
    insurance: bool = False
    authority: bool = False
    rate_sheet: bool = False
    terms: bool = False
    rate_confirmation_package: bool = False

    def is_complete(self) -> bool:
        return all(self.model_dump().values())
