"""Retention classes -- how long an archived load's record must be kept.

Company Library, Visibility SOP, section 8: "Do not use one purge clock for
every load. Retention class should be stored with each load/archive record."
Build requirement: "Archive must support a retention_class field. The system
should warn when a record cannot purge under the normal commercial rule."
(Mike Zachary, 2026-09-13: "update the doctrine and build retention class".)

Dispatch deletes no archive record anywhere. This module only answers whether
the normal commercial rule may apply to a record, and why not -- the answer the
Operations Feed's Retention Alert card and the retention API show. Purging a
record stays a person's decision.

The SOP gives no number of years for the normal commercial class ("use
accounting/claims needs before purge"), so none is invented here.
"""

from __future__ import annotations

from datetime import datetime, timezone

NORMAL_COMMERCIAL = "normal_commercial"

#: class -> (label, minimum years or None, what the SOP says)
RETENTION_CLASSES = {
    NORMAL_COMMERCIAL: ("Normal Commercial", None,
                        "Commercial default; use accounting/claims needs before purge."),
    "dispute_detention_claim": ("Broker Dispute / Detention / Claim", None,
                                "Hold until resolved plus applicable retention requirement."),
    "government": ("Government / FEMA / DLA", 4,
                   "Minimum 4 years unless contract-specific period requires longer."),
    "far_contract": ("FAR-Covered Contract", 3,
                     "3 years after final payment unless clause says longer."),
    "high_value_securement": ("High-Value / Securement Sensitive", 4,
                              "Keep longer; 4 years is preferred where evidence protects against later claims."),
    "legal_insurance_audit_hold": ("Legal / Insurance / Audit Hold", None,
                                   "No purge until hold is released."),
}


def validate_class(retention_class: str) -> str:
    key = (retention_class or "").strip().lower()
    if key not in RETENTION_CLASSES:
        raise ValueError(f"Unknown retention class {retention_class!r}; one of {', '.join(RETENTION_CLASSES)}")
    return key


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _plus_years(moment: datetime, years: int) -> datetime:
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:  # 29 February
        return moment.replace(year=moment.year + years, day=28)


def purge_check(record: dict, *, now: datetime | None = None) -> dict:
    """Whether the normal commercial rule may apply to this archive record.

    Returns {"normal_rule_applies": bool, "reasons": [...], "earliest_purge": iso or None,
    "retention_class", "label", "policy"}. Never deletes anything.
    """
    now = now or datetime.now(timezone.utc)
    retention_class = (record.get("retention_class") or NORMAL_COMMERCIAL).strip().lower()
    label, years, policy = RETENTION_CLASSES.get(retention_class, RETENTION_CLASSES[NORMAL_COMMERCIAL])
    reasons: list[str] = []
    earliest = None

    if record.get("legal_hold"):
        note = (record.get("legal_hold_note") or "").strip()
        reasons.append("Legal hold is on" + (f": {note}" if note else "") + ". No purge until it is released.")

    if retention_class == "dispute_detention_claim":
        if not record.get("dispute_resolved_at"):
            reasons.append("The dispute, detention or claim is not recorded as resolved.")
        else:
            reasons.append("Resolved; the applicable retention requirement still has to be confirmed before purge.")
    elif retention_class == "legal_insurance_audit_hold":
        reasons.append("Legal / insurance / audit hold class: no purge until the hold is released.")
    elif retention_class == "far_contract":
        paid = _parse(record.get("final_payment_at"))
        if not paid:
            reasons.append("FAR-covered: final payment date is not recorded, so the 3-year clock has not started.")
        else:
            until = _plus_years(paid, years)
            earliest = until.isoformat()
            if now < until:
                reasons.append(f"FAR-covered: keep until {until.date()} (3 years after final payment).")
    elif years:
        archived = _parse(record.get("archived_at"))
        if not archived:
            reasons.append(f"{label}: archive date is not recorded, so the {years}-year minimum cannot be measured.")
        else:
            until = _plus_years(archived, years)
            earliest = until.isoformat()
            if now < until:
                reasons.append(f"{label}: keep until {until.date()} ({years}-year minimum).")

    return {"retention_class": retention_class, "label": label, "policy": policy,
            "normal_rule_applies": not reasons, "reasons": reasons, "earliest_purge": earliest}
