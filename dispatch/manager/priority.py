"""Priority ranking per DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md Section 8
(consequence first, urgency second; MANAGER.md Section 6's nine tiers,
with the mission's safety/security/legal/compliance/authority items
folded into Tier 1 rather than treated as separate tiers).

Which source_type/classification pair lands in which tier is this
build's own tunable default -- the nine-tier ORDER is doctrine, the
per-signal-type tier assignment below is a documented, correctable
implementation choice, same status as classify.py's thresholds.
"""

from __future__ import annotations

from dispatch.manager import security_monitor, signals
from dispatch.manager.classify import CONFLICT, DECISION_NEEDED

TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY = 1
TIER_ACTIVE_REVENUE_OPPORTUNITY = 2
TIER_CUSTOMER_BROKER_DRIVER_FACING = 3
TIER_GOVERNMENT_DEADLINE = 4
TIER_OPERATIONAL_POSITIONING = 5
TIER_DOCUMENT_PRODUCTION = 6
TIER_LIBRARY_ARCHIVE_CLEANUP = 7
TIER_DISCOVERY_RESEARCH = 8
TIER_DEFERRED_ROUTINE = 9

# IFTA suspect entries are always Tier 1: an uncorrected low-confidence
# extraction risks an inaccurate government filing -- a compliance
# matter, not a routine data-quality note, regardless of classification.
_IFTA_TIER = TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY


def _tier_for_stalled_load(classified: dict) -> int:
    if classified["classification"] == DECISION_NEEDED:
        return TIER_CUSTOMER_BROKER_DRIVER_FACING
    return TIER_OPERATIONAL_POSITIONING


def _tier_for_overdue_settlement(classified: dict) -> int:
    if classified["classification"] == DECISION_NEEDED:
        return TIER_CUSTOMER_BROKER_DRIVER_FACING
    return TIER_DOCUMENT_PRODUCTION


def _tier_for_open_exception(classified: dict) -> int:
    if classified["classification"] == CONFLICT:
        return TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY
    if classified["classification"] == DECISION_NEEDED:
        return TIER_CUSTOMER_BROKER_DRIVER_FACING
    return TIER_OPERATIONAL_POSITIONING


def _tier_for_unresolved_conflict(classified: dict) -> int:
    if classified["classification"] == CONFLICT:
        return TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY
    if classified["classification"] == DECISION_NEEDED:
        return TIER_CUSTOMER_BROKER_DRIVER_FACING
    return TIER_OPERATIONAL_POSITIONING


def _tier_for_ifta_suspect_entry(_classified: dict) -> int:
    return _IFTA_TIER


def _tier_for_ifta_exception(_classified: dict) -> int:
    # Same reasoning as suspect entries: a finding against a
    # not-yet-sealed government filing is a compliance matter.
    return _IFTA_TIER


def _tier_for_security_pattern(_classified: dict) -> int:
    return TIER_SAFETY_SECURITY_LEGAL_COMPLIANCE_AUTHORITY


def _tier_for_archive_review_item(_classified: dict) -> int:
    # DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md Section 8 names this tier
    # explicitly for "Library, Archive, or cleanup work" -- not a
    # judgment call the way some other tier assignments in this build
    # have been.
    return TIER_LIBRARY_ARCHIVE_CLEANUP


_TIER_FUNCTIONS = {
    signals.STALLED_LOAD: _tier_for_stalled_load,
    signals.OVERDUE_SETTLEMENT: _tier_for_overdue_settlement,
    signals.OPEN_EXCEPTION: _tier_for_open_exception,
    signals.UNRESOLVED_CONFLICT: _tier_for_unresolved_conflict,
    signals.IFTA_SUSPECT_ENTRY: _tier_for_ifta_suspect_entry,
    signals.IFTA_EXCEPTION: _tier_for_ifta_exception,
    security_monitor.SECURITY_PATTERN: _tier_for_security_pattern,
    signals.ARCHIVE_REVIEW_ITEM: _tier_for_archive_review_item,
}


def assign_priority(classified: dict) -> dict:
    """Returns classified signal enriched with a 'priority_tier' (1-9,
    1 highest). Never mutates the input.
    """
    tier_fn = _TIER_FUNCTIONS.get(classified["source_type"])
    tier = tier_fn(classified) if tier_fn else TIER_DEFERRED_ROUTINE
    return {**classified, "priority_tier": tier}


def rank(classified_signals: list[dict]) -> list[dict]:
    """Ranks by priority tier (ascending -- Tier 1 first), then by
    card_level (descending, higher consequence first) as the
    within-tier tiebreak. A Tier 1 item is never displaced by a
    lower-tier item regardless of card_level, matching the buildout
    design's conflict-handling rule (tier first, always).
    """
    prioritized = [assign_priority(s) for s in classified_signals]
    return sorted(prioritized, key=lambda s: (s["priority_tier"], -s["card_level"]))
