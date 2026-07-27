"""Broker-risk rule module.

Deterministic read of the Broker Intelligence Library (System Rule 14):
slow payment terms and an incomplete contact record lower the score.
"""

from __future__ import annotations

import re

from .base import IntelligenceScore

NAME = "broker_risk"
VERSION = "1.0.0"

_SLOW_PAY_TERMS = re.compile(r"net[\s-]*(45|60|75|90)", re.IGNORECASE)
_SLOW_PAY_PENALTY = 40
_MISSING_CONTACT_PENALTY = 20
_NO_PROFILE_SCORE = 50


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    if broker is None:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_NO_PROFILE_SCORE,
            flags=["broker_profile_missing"], findings={},
        )

    penalty = 0
    flags: list[str] = []
    terms = broker.payment_terms or ""
    if _SLOW_PAY_TERMS.search(terms):
        penalty += _SLOW_PAY_PENALTY
        flags.append("slow_payment_terms")
    else:
        flags.append("payment_terms_acceptable")

    if not (broker.contact_email or broker.contact_phone):
        penalty += _MISSING_CONTACT_PENALTY
        flags.append("broker_contact_incomplete")

    score = max(100 - penalty, 0)
    findings = {
        "payment_terms": broker.payment_terms,
        "communication_notes": broker.communication_notes,
    }
    return IntelligenceScore(module=NAME, version=VERSION, score=score, flags=flags, findings=findings)
